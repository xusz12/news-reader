let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "all",
};

const searchInput = document.getElementById("searchInput");
const refreshBtn = document.getElementById("refreshBtn");
const showAllBtn = document.getElementById("showAllBtn");
const showUnreadBtn = document.getElementById("showUnreadBtn");
const markAllReadBtn = document.getElementById("markAllReadBtn");
const newsList = document.getElementById("newsList");
const meta = document.getElementById("meta");
const pageInfo = document.getElementById("pageInfo");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");

let observer = null;
let lastScrollY = window.scrollY;
const enteredViewport = new Set();
const writeInFlight = new Set();

function updateFilterButtons() {
  showAllBtn.disabled = state.readFilter === "all";
  showUnreadBtn.disabled = state.readFilter === "unread";
}

function isRead(li) {
  return li.dataset.read === "1";
}

function applyReadUI(li, read) {
  li.dataset.read = read ? "1" : "0";
  const dot = li.querySelector(".unread-dot");
  if (dot) dot.classList.toggle("hidden", read);
  const toggle = li.querySelector(".read-toggle");
  if (toggle) toggle.textContent = read ? "标为未读" : "标为已读";
}

async function patchRead(itemId, read) {
  const res = await fetch(`/api/news/${encodeURIComponent(itemId)}/state`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ read }),
  });
  if (!res.ok) throw new Error("state_update_failed");
  return res.json();
}

async function markReadWithRollback(li, read) {
  const itemId = li.dataset.id;
  if (writeInFlight.has(itemId)) return;
  writeInFlight.add(itemId);
  const prevRead = isRead(li);
  applyReadUI(li, read);
  try {
    await patchRead(itemId, read);
  } catch {
    applyReadUI(li, prevRead);
  } finally {
    writeInFlight.delete(itemId);
  }
}

function setupObserver() {
  if (observer) observer.disconnect();
  observer = new IntersectionObserver(
    (entries) => {
      if (document.hidden) return;
      const scrollingDown = window.scrollY > lastScrollY;
      lastScrollY = window.scrollY;

      for (const entry of entries) {
        const el = entry.target;
        const id = el.dataset.id;
        if (entry.isIntersecting) {
          enteredViewport.add(id);
          continue;
        }
        if (!scrollingDown) continue;
        if (!enteredViewport.has(id)) continue;
        if (isRead(el)) continue;

        // "滚过即读": only when row bottom slides past viewport top.
        if (entry.boundingClientRect.bottom < 0) {
          markReadWithRollback(el, true);
        }
      }
    },
    { threshold: [0] }
  );
  document.querySelectorAll(".news-item").forEach((el) => observer.observe(el));
}

function renderItems(items) {
  newsList.innerHTML = "";
  enteredViewport.clear();

  for (const item of items) {
    const li = document.createElement("li");
    li.className = "news-item";
    li.dataset.id = item.id;
    li.dataset.read = item.read_at ? "1" : "0";

    const line1 = document.createElement("div");
    line1.className = "line1";
    const dot = document.createElement("span");
    dot.className = "unread-dot";
    if (item.read_at) dot.classList.add("hidden");
    const metaText = document.createElement("span");
    metaText.textContent = `${item.published_at} · ${item.source || "未知来源"}`;
    line1.appendChild(dot);
    line1.appendChild(metaText);

    const titleRow = document.createElement("div");
    titleRow.className = "title-row";

    const title = document.createElement("a");
    title.className = "title";
    title.href = item.url || "#";
    title.target = "_blank";
    title.rel = "noopener noreferrer";
    title.textContent = item.title;
    if (!item.url) {
      title.style.pointerEvents = "none";
      title.style.opacity = "0.6";
    }
    title.addEventListener("click", async () => {
      if (isRead(li)) return;
      await markReadWithRollback(li, true);
    });

    const toggle = document.createElement("button");
    toggle.className = "read-toggle";
    toggle.textContent = item.read_at ? "标为未读" : "标为已读";
    toggle.addEventListener("click", async () => {
      await markReadWithRollback(li, !isRead(li));
    });

    titleRow.appendChild(title);
    titleRow.appendChild(toggle);
    li.appendChild(line1);
    li.appendChild(titleRow);
    if (item.summary) {
      const p = document.createElement("p");
      p.className = "summary";
      p.textContent = item.summary;
      li.appendChild(p);
    }
    newsList.appendChild(li);
  }
  setupObserver();
}

async function loadNews() {
  const params = new URLSearchParams({
    page: String(state.page),
    per: String(state.per),
    q: state.q,
    read_filter: state.readFilter,
  });
  const res = await fetch(`/api/news?${params.toString()}`);
  const data = await res.json();
  state.pages = data.pages;
  renderItems(data.items);
  meta.textContent = `共 ${data.total} 条`;
  pageInfo.textContent = `${state.page} / ${state.pages}`;
  prevBtn.disabled = state.page <= 1;
  nextBtn.disabled = state.page >= state.pages;
  updateFilterButtons();
}

let searchTimer = null;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = searchInput.value.trim();
    state.page = 1;
    loadNews();
  }, 300);
});

showAllBtn.addEventListener("click", async () => {
  state.readFilter = "all";
  state.page = 1;
  await loadNews();
});

showUnreadBtn.addEventListener("click", async () => {
  state.readFilter = "unread";
  state.page = 1;
  await loadNews();
});

markAllReadBtn.addEventListener("click", async () => {
  const ok = window.confirm("将当前筛选结果（跨页）全部标为已读？");
  if (!ok) return;
  markAllReadBtn.disabled = true;
  try {
    const res = await fetch("/api/news/mark-all-read", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        q: state.q,
        read_filter: state.readFilter,
      }),
    });
    if (!res.ok) throw new Error("mark_all_failed");
    state.page = 1;
    await loadNews();
  } finally {
    markAllReadBtn.disabled = false;
  }
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "刷新中...";
  try {
    await fetch("/api/reindex", { method: "POST" });
    state.page = 1;
    await loadNews();
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "刷新索引";
  }
});

prevBtn.addEventListener("click", async () => {
  if (state.page > 1) {
    state.page -= 1;
    await loadNews();
  }
});

nextBtn.addEventListener("click", async () => {
  if (state.page < state.pages) {
    state.page += 1;
    await loadNews();
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    // Reset scroll direction baseline when coming back.
    lastScrollY = window.scrollY;
  }
});

loadNews();
