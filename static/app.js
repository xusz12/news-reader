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
const readPending = new Map();
const readTouched = new Set();

function updateFilterButtons() {
  showAllBtn.disabled = state.readFilter === "all";
  showUnreadBtn.disabled = state.readFilter === "unread";
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

function clearObserve(itemId) {
  const timer = readPending.get(itemId);
  if (timer) {
    clearTimeout(timer);
    readPending.delete(itemId);
  }
}

function setupObserver() {
  if (observer) observer.disconnect();
  observer = new IntersectionObserver(
    (entries) => {
      if (document.hidden) {
        for (const entry of entries) clearObserve(entry.target.dataset.id);
        return;
      }
      for (const entry of entries) {
        const el = entry.target;
        const id = el.dataset.id;
        const isRead = el.dataset.read === "1";
        if (isRead || readTouched.has(id)) {
          clearObserve(id);
          continue;
        }
        const rowHeight = entry.boundingClientRect.height || el.offsetHeight || 0;
        const visibleHeight = entry.intersectionRect.height || 0;
        const viewportCap = window.innerHeight * 0.6;
        const needVisible = Math.min(rowHeight * 0.75, viewportCap);
        if (visibleHeight >= needVisible && !readPending.has(id)) {
          const timer = setTimeout(async () => {
            readPending.delete(id);
            readTouched.add(id);
            el.classList.add("is-read");
            el.dataset.read = "1";
            try {
              await patchRead(id, true);
            } catch (e) {
              el.classList.remove("is-read");
              el.dataset.read = "0";
              readTouched.delete(id);
            }
          }, 2000);
          readPending.set(id, timer);
        } else if (visibleHeight < needVisible) {
          clearObserve(id);
        }
      }
    },
    { threshold: [0, 0.25, 0.5, 0.75, 1.0] }
  );

  document.querySelectorAll(".news-item").forEach((el) => observer.observe(el));
}

function renderItems(items) {
  newsList.innerHTML = "";
  for (const item of items) {
    const li = document.createElement("li");
    li.className = "news-item";
    li.dataset.id = item.id;
    li.dataset.read = item.read_at ? "1" : "0";
    if (item.read_at) li.classList.add("is-read");

    const line1 = document.createElement("div");
    line1.className = "line1";
    line1.textContent = `${item.published_at} · ${item.source || "未知来源"}`;

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
      if (li.dataset.read === "1") return;
      li.classList.add("is-read");
      li.dataset.read = "1";
      try {
        await patchRead(item.id, true);
      } catch (e) {
        li.classList.remove("is-read");
        li.dataset.read = "0";
      }
    });

    const toggle = document.createElement("button");
    toggle.className = "read-toggle";
    const setToggleText = () => {
      toggle.textContent = li.dataset.read === "1" ? "标为未读" : "标为已读";
    };
    setToggleText();
    toggle.addEventListener("click", async () => {
      const nextRead = li.dataset.read !== "1";
      const prevRead = li.dataset.read;
      li.dataset.read = nextRead ? "1" : "0";
      li.classList.toggle("is-read", nextRead);
      setToggleText();
      try {
        await patchRead(item.id, nextRead);
      } catch (e) {
        li.dataset.read = prevRead;
        li.classList.toggle("is-read", prevRead === "1");
        setToggleText();
      }
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
    for (const id of readPending.keys()) clearObserve(id);
  }
});

loadNews();
