let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "all",
  total: 0,
  loading: false,
  hasMore: true,
};

const mediaIconMap = {
  Reuters: "/static/source-icons/reuters.ico",
  Bloomberg: "/static/source-icons/bloomberg.png",
  TechCrunch: "/static/source-icons/techcrunch.png",
  "Ars Technica": "/static/source-icons/arstechnica.ico",
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
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");

let readObserver = null;
let loadObserver = null;
let lastScrollY = window.scrollY;
const enteredViewport = new Set();
const writeInFlight = new Set();

function sourcePrefix(source) {
  if (!source) return "";
  return source.split("·")[0].trim();
}

function createSourceIcon(item) {
  const wrap = document.createElement("span");
  wrap.className = "source-icon";

  let iconSrc = "";
  if (item.source_type === "twitter") {
    iconSrc = "/static/source-icons/x.svg";
  } else {
    iconSrc = mediaIconMap[sourcePrefix(item.source)] || "";
  }

  if (iconSrc) {
    const img = document.createElement("img");
    img.className = "source-icon-img";
    img.src = iconSrc;
    img.alt = sourcePrefix(item.source) || "来源图标";
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("error", () => {
      wrap.textContent = "🗞️";
      wrap.classList.add("fallback");
    });
    wrap.appendChild(img);
    return wrap;
  }

  wrap.textContent = "🗞️";
  wrap.classList.add("fallback");
  return wrap;
}

function updateFilterButtons() {
  showAllBtn.disabled = state.readFilter === "all";
  showUnreadBtn.disabled = state.readFilter === "unread";
}

function setHint(text) {
  listHint.textContent = text || "";
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

function setupReadObserver() {
  if (readObserver) readObserver.disconnect();
  readObserver = new IntersectionObserver(
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
        if (entry.boundingClientRect.bottom < 0) {
          markReadWithRollback(el, true);
        }
      }
    },
    { threshold: [0] }
  );
  document.querySelectorAll(".news-item").forEach((el) => readObserver.observe(el));
}

function setupLoadObserver() {
  if (loadObserver) loadObserver.disconnect();
  loadObserver = new IntersectionObserver(
    async (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        if (state.loading || !state.hasMore) continue;
        await loadNextPage();
      }
    },
    { threshold: [0.1] }
  );
  loadObserver.observe(loadMoreSentinel);
}

function buildItemRow(item) {
  const li = document.createElement("li");
  li.className = "news-item";
  li.dataset.id = item.id;
  li.dataset.read = item.read_at ? "1" : "0";

  const line1 = document.createElement("div");
  line1.className = "line1";
  const dot = document.createElement("span");
  dot.className = "unread-dot";
  if (item.read_at) dot.classList.add("hidden");
  const icon = createSourceIcon(item);
  const metaText = document.createElement("span");
  metaText.textContent = `${item.source || "未知来源"} · ${item.published_at}`;
  line1.appendChild(dot);
  line1.appendChild(icon);
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
  return li;
}

async function fetchNewsPage(page) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    q: state.q,
    read_filter: state.readFilter,
  });
  const res = await fetch(`/api/news?${params.toString()}`);
  if (!res.ok) throw new Error("news_fetch_failed");
  return res.json();
}

function resetList() {
  newsList.innerHTML = "";
  enteredViewport.clear();
  state.page = 1;
  state.pages = 1;
  state.total = 0;
  state.hasMore = true;
}

function renderMeta() {
  meta.textContent = `共 ${state.total} 条`;
  pageInfo.textContent = `${state.page} / ${state.pages}`;
}

async function loadFirstPage() {
  state.loading = true;
  try {
    const data = await fetchNewsPage(1);
    resetList();
    state.total = data.total;
    state.pages = data.pages;
    state.page = 1;
    state.hasMore = state.page < state.pages;
    data.items.forEach((item) => newsList.appendChild(buildItemRow(item)));
    renderMeta();
    if (state.total === 0) {
      setHint("暂无数据");
    } else if (state.hasMore) {
      setHint("继续下滑加载更多");
    } else {
      setHint("已加载全部新闻");
    }
    setupReadObserver();
  } finally {
    state.loading = false;
    updateFilterButtons();
  }
}

async function loadNextPage() {
  if (!state.hasMore) return;
  const next = state.page + 1;
  state.loading = true;
  try {
    const data = await fetchNewsPage(next);
    data.items.forEach((item) => {
      const row = buildItemRow(item);
      newsList.appendChild(row);
      if (readObserver) readObserver.observe(row);
    });
    state.page = next;
    state.pages = data.pages;
    state.total = data.total;
    state.hasMore = state.page < state.pages;
    renderMeta();
    setHint(state.hasMore ? "继续下滑加载更多" : "已加载全部新闻");
  } finally {
    state.loading = false;
  }
}

async function autoReindexAndLoad() {
  setHint("正在同步最新新闻...");
  try {
    const r = await fetch("/api/reindex", { method: "POST" });
    if (!r.ok) throw new Error("reindex_failed");
    await loadFirstPage();
    setHint(state.hasMore ? "继续下滑加载更多" : "已加载全部新闻");
  } catch {
    setHint("自动同步失败，已展示本地索引，可点“刷新索引”重试。");
    await loadFirstPage();
  }
}

let searchTimer = null;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    state.q = searchInput.value.trim();
    await loadFirstPage();
  }, 300);
});

showAllBtn.addEventListener("click", async () => {
  state.readFilter = "all";
  await loadFirstPage();
});

showUnreadBtn.addEventListener("click", async () => {
  state.readFilter = "unread";
  await loadFirstPage();
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
    await loadFirstPage();
  } finally {
    markAllReadBtn.disabled = false;
  }
});

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "刷新中...";
  try {
    const r = await fetch("/api/reindex", { method: "POST" });
    if (!r.ok) throw new Error("reindex_failed");
    await loadFirstPage();
  } catch {
    setHint("同步失败，可稍后重试。");
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "刷新索引";
  }
});

// Pager hidden in v1.1.2 (kept for compatibility).
prevBtn.addEventListener("click", () => {});
nextBtn.addEventListener("click", () => {});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    lastScrollY = window.scrollY;
  }
});

setupLoadObserver();
autoReindexAndLoad();
