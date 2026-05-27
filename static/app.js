let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "all", // all | unread
  collection: "feed", // feed | important | read_later
  total: 0,
  loading: false,
  hasMore: true,
  selectedId: null,
  itemsById: new Map(),
  detailCacheByUrl: new Map(),
};

const mediaIconMap = {
  Reuters: "/static/source-icons/reuters.ico",
  Bloomberg: "/static/source-icons/bloomberg.png",
  TechCrunch: "/static/source-icons/techcrunch.png",
  "Ars Technica": "/static/source-icons/arstechnica.ico",
};

const refreshBtn = document.getElementById("refreshBtn");
const readFilterToggleBtn = document.getElementById("readFilterToggleBtn");
const markAllReadBtn = document.getElementById("markAllReadBtn");

const navFeedBtn = document.getElementById("navFeedBtn");
const navImportantBtn = document.getElementById("navImportantBtn");
const navReadLaterBtn = document.getElementById("navReadLaterBtn");

const newsList = document.getElementById("newsList");
const meta = document.getElementById("meta");
const pageInfo = document.getElementById("pageInfo");
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");

const detailPanel = document.getElementById("detailPanel");
const detailEmpty = document.getElementById("detailEmpty");
const detailBody = document.getElementById("detailBody");
const detailCloseBtn = document.getElementById("detailCloseBtn");

let readObserver = null;
let loadObserver = null;
let detailPollTimer = null;
let lastScrollY = window.scrollY;
const enteredViewport = new Set();
const writeInFlight = new Set();

function setHint(text) {
  listHint.textContent = text || "";
}

function stopDetailPolling() {
  if (detailPollTimer) {
    window.clearInterval(detailPollTimer);
    detailPollTimer = null;
  }
}

function iconSvg(name, filled = false) {
  const common = 'width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  if (name === "circle") {
    if (filled) {
      return `<svg ${common}><circle cx="12" cy="12" r="7.5" fill="currentColor" stroke="currentColor"/></svg>`;
    }
    return `<svg ${common}><circle cx="12" cy="12" r="7.5"/></svg>`;
  }
  if (name === "check-circle") {
    return `<svg ${common}><circle cx="12" cy="12" r="8"/><path d="m8.5 12 2.2 2.2 4.8-4.8"/></svg>`;
  }
  if (name === "refresh") {
    return `<svg ${common}><path d="M8 4.5a7.5 7.5 0 0 1 9.6 2.1"/><path d="m17.2 4.8.5 3.3-3.3.5"/><path d="M16 19.5a7.5 7.5 0 0 1-9.6-2.1"/><path d="m6.8 19.2-.5-3.3 3.3-.5"/></svg>`;
  }
  if (name === "important") {
    if (filled) {
      return `<svg ${common}><circle cx="12" cy="12" r="8" fill="currentColor" stroke="currentColor"/><path d="M12 7.2v6" stroke="#fff"/><circle cx="12" cy="16.9" r="0.9" fill="#fff" stroke="none"/></svg>`;
    }
    return `<svg ${common}><circle cx="12" cy="12" r="8"/><path d="M12 7.2v6"/><circle cx="12" cy="16.9" r="0.9" fill="currentColor" stroke="none"/></svg>`;
  }
  if (name === "bookmark") {
    if (filled) {
      return `<svg ${common}><path d="M8 4.5h8a1 1 0 0 1 1 1V20l-5-3-5 3V5.5a1 1 0 0 1 1-1Z" fill="currentColor" stroke="currentColor"/></svg>`;
    }
    return `<svg ${common}><path d="M8 4.5h8a1 1 0 0 1 1 1V20l-5-3-5 3V5.5a1 1 0 0 1 1-1Z"/></svg>`;
  }
  return `<svg ${common}><circle cx="12" cy="12" r="7.5"/></svg>`;
}

function applyIcon(btn, iconName, { filled = false, label = "", tone = "default" } = {}) {
  btn.innerHTML = `<span class="glyph">${iconSvg(iconName, filled)}</span>`;
  btn.classList.remove("tone-default", "tone-danger", "tone-warning", "tone-success");
  btn.classList.add(`tone-${tone}`);
  btn.dataset.icon = iconName;
  btn.dataset.filled = filled ? "1" : "0";
  btn.title = label;
  btn.setAttribute("aria-label", label);
}

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

function rowIsRead(li) {
  return li.dataset.read === "1";
}

function syncRowUI(li, item) {
  li.dataset.read = item.read_at ? "1" : "0";
  li.dataset.important = item.important_at ? "1" : "0";
  li.dataset.readLater = item.read_later_at ? "1" : "0";

  const unreadDot = li.querySelector(".unread-dot");
  if (unreadDot) unreadDot.classList.toggle("hidden", !!item.read_at);

  const importantBtn = li.querySelector(".btn-important");
  if (importantBtn) {
    applyIcon(importantBtn, "important", {
      filled: !!item.important_at,
      tone: item.important_at ? "danger" : "default",
      label: item.important_at ? "取消重要" : "标为重要",
    });
  }

  const readLaterBtn = li.querySelector(".btn-read-later");
  if (readLaterBtn) {
    const detailReady = Number(item.detail_ready || 0) === 1;
    const detailFailed = item.detail_status === "failed";
    applyIcon(readLaterBtn, "bookmark", {
      filled: !!item.read_later_at,
      tone: item.read_later_at ? (detailReady ? "success" : "warning") : "default",
      label: item.read_later_at
        ? (detailReady ? "取消稍后再看（详情已就绪）" : (detailFailed ? "取消稍后再看（详情失败）" : "取消稍后再看（详情抓取中）"))
        : "稍后再看",
    });
  }

  li.classList.toggle("selected", state.selectedId === item.id);
}

function updateFilterButtons() {
  const isAll = state.readFilter === "all";
  applyIcon(readFilterToggleBtn, "circle", {
    filled: isAll,
    tone: isAll ? "default" : "muted",
    label: isAll ? "全部显示" : "仅未读",
  });
}

function updateCollectionButtons() {
  navFeedBtn.classList.toggle("active", state.collection === "feed");
  navImportantBtn.classList.toggle("active", state.collection === "important");
  navReadLaterBtn.classList.toggle("active", state.collection === "read_later");
}

function renderMeta() {
  const names = {
    feed: "新闻流",
    important: "重要新闻",
    read_later: "稍后再看",
  };
  const readNames = {
    all: "全部",
    unread: "仅未读",
  };
  meta.textContent = `${names[state.collection]} · ${readNames[state.readFilter]} · 共 ${state.total} 条`;
  pageInfo.textContent = `${state.page} / ${state.pages}`;
}

async function patchState(itemId, payload) {
  const res = await fetch(`/api/news/${encodeURIComponent(itemId)}/state`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("state_update_failed");
  return res.json();
}

function applyPatchToItem(item, patchResult) {
  if ("read_at" in patchResult) item.read_at = patchResult.read_at;
  if ("important_at" in patchResult) item.important_at = patchResult.important_at;
  if ("read_later_at" in patchResult) item.read_later_at = patchResult.read_later_at;
  state.itemsById.set(item.id, item);
}

function rerenderOne(itemId) {
  const item = state.itemsById.get(itemId);
  const row = newsList.querySelector(`.news-item[data-id=\"${itemId}\"]`);
  if (item && row) syncRowUI(row, item);
  if (item && state.selectedId === itemId) renderDetail(item);
}

async function patchStateWithRollback(itemId, payload) {
  if (writeInFlight.has(itemId)) return;
  writeInFlight.add(itemId);
  const item = state.itemsById.get(itemId);
  if (!item) {
    writeInFlight.delete(itemId);
    return;
  }
  const backup = {
    read_at: item.read_at,
    important_at: item.important_at,
    read_later_at: item.read_later_at,
  };

  const now = new Date().toISOString().slice(0, 19).replace("T", " ");
  if ("read" in payload) item.read_at = payload.read ? now : null;
  if ("important" in payload) item.important_at = payload.important ? now : null;
  if ("read_later" in payload) {
    item.read_later_at = payload.read_later ? now : null;
    if (payload.read_later) {
      item.detail_status = "pending";
      if (!Number(item.detail_ready || 0)) item.detail_ready = 0;
    } else {
      item.detail_status = "canceled";
      stopDetailPolling();
    }
  }
  rerenderOne(itemId);

  try {
    const result = await patchState(itemId, payload);
    applyPatchToItem(item, result);
    rerenderOne(itemId);
  } catch {
    item.read_at = backup.read_at;
    item.important_at = backup.important_at;
    item.read_later_at = backup.read_later_at;
    rerenderOne(itemId);
  } finally {
    writeInFlight.delete(itemId);
  }
}

function openDetailOnMobile() {
  if (window.matchMedia("(max-width: 980px)").matches) {
    detailPanel.classList.add("open");
  }
}

function closeDetailOnMobile() {
  detailPanel.classList.remove("open");
}

function renderDetail(item) {
  if (!item) {
    stopDetailPolling();
    detailBody.classList.add("hidden");
    detailEmpty.classList.remove("hidden");
    return;
  }
  detailEmpty.classList.add("hidden");
  detailBody.classList.remove("hidden");

  document.getElementById("detailTitle").textContent = item.title || "";
  document.getElementById("detailMeta").textContent = `${item.source || "未知来源"} · ${item.published_at || ""}`;
  document.getElementById("detailSummary").textContent = item.summary || "暂无摘要";

  const link = document.getElementById("detailLink");
  const statusEl = document.getElementById("detailStatus");
  const contentEl = document.getElementById("detailContent");
  const retryBtn = document.getElementById("detailRetryBtn");

  if (item.url) {
    link.href = item.url;
    link.classList.remove("disabled");
    link.textContent = "打开原文";
  } else {
    link.href = "#";
    link.classList.add("disabled");
    link.textContent = "无原文链接";
  }

  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  const detail = cached?.detail || null;
  const status = cached?.detail_status || item.detail_status || "none";

  if (detail && detail.content) {
    statusEl.textContent = `详情已完成 · 正文长度 ${detail.content_length || detail.content.length}`;
    statusEl.className = "detail-status ready";
    contentEl.textContent = detail.content;
    contentEl.classList.remove("hidden");
    retryBtn.classList.add("hidden");
    stopDetailPolling();
  } else if (!item.read_later_at) {
    statusEl.textContent = "未加入稍后再看";
    statusEl.className = "detail-status muted";
    contentEl.classList.add("hidden");
    retryBtn.classList.add("hidden");
    stopDetailPolling();
  } else if (status === "pending" || status === "running") {
    statusEl.textContent = status === "pending" ? "排队中" : "正在抓取";
    statusEl.className = "detail-status pending";
    contentEl.classList.add("hidden");
    retryBtn.classList.add("hidden");
  } else if (status === "failed") {
    const err = cached?.job?.last_error || item.detail_error || "详情获取失败";
    statusEl.textContent = `获取失败，可重试：${err}`;
    statusEl.className = "detail-status failed";
    contentEl.classList.add("hidden");
    retryBtn.classList.remove("hidden");
    stopDetailPolling();
  } else if (status === "skipped") {
    statusEl.textContent = "已跳过（该来源暂不抓正文）";
    statusEl.className = "detail-status muted";
    contentEl.classList.add("hidden");
    retryBtn.classList.add("hidden");
    stopDetailPolling();
  } else {
    statusEl.textContent = "稍后再看已标记，等待详情任务";
    statusEl.className = "detail-status pending";
    contentEl.classList.add("hidden");
    retryBtn.classList.remove("hidden");
  }

  const importantBtn = document.getElementById("detailImportantBtn");
  applyIcon(importantBtn, "important", {
    filled: !!item.important_at,
    tone: item.important_at ? "danger" : "default",
    label: item.important_at ? "取消重要" : "标为重要",
  });

  const readLaterBtn = document.getElementById("detailReadLaterBtn");
  const detailReady = Number(item.detail_ready || 0) === 1;
  applyIcon(readLaterBtn, "bookmark", {
    filled: !!item.read_later_at,
    tone: item.read_later_at ? (detailReady ? "success" : "warning") : "default",
    label: item.read_later_at ? "取消稍后再看" : "稍后再看",
  });
}

async function fetchDetail(itemId) {
  const res = await fetch(`/api/news/${encodeURIComponent(itemId)}/detail`);
  if (!res.ok) return null;
  return res.json();
}

async function loadDetail(itemId) {
  const item = state.itemsById.get(itemId);
  if (!item || !item.url) return;
  const payload = await fetchDetail(itemId);
  if (!payload || !payload.ok) return;

  state.detailCacheByUrl.set(item.url, payload);
  item.detail_status = payload.detail_status;
  item.detail_ready = payload.detail ? 1 : 0;
  if (payload.job && payload.job.last_error) item.detail_error = payload.job.last_error;
  state.itemsById.set(item.id, item);
  rerenderOne(item.id);
}

function startDetailPolling(itemId) {
  stopDetailPolling();
  const current = state.itemsById.get(itemId);
  if (!current || !current.read_later_at) return;
  if (Number(current.detail_ready || 0) === 1) return;

  detailPollTimer = window.setInterval(async () => {
    if (!state.selectedId || state.selectedId !== itemId) {
      stopDetailPolling();
      return;
    }
    await loadDetail(itemId);
    const refreshed = state.itemsById.get(itemId);
    if (!refreshed) {
      stopDetailPolling();
      return;
    }
    const status = refreshed.detail_status || "none";
    if (Number(refreshed.detail_ready || 0) === 1 || status === "failed" || status === "skipped") {
      stopDetailPolling();
    }
  }, 2000);
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
        if (rowIsRead(el)) continue;
        if (entry.boundingClientRect.bottom < 0) {
          patchStateWithRollback(id, { read: true });
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

  const line1 = document.createElement("div");
  line1.className = "line1";

  const unreadDot = document.createElement("span");
  unreadDot.className = "unread-dot";

  const icon = createSourceIcon(item);

  const text = document.createElement("span");
  text.className = "line1-text";
  text.textContent = `${item.source || "未知来源"} · ${item.published_at || ""}`;

  line1.appendChild(unreadDot);
  line1.appendChild(icon);
  line1.appendChild(text);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = item.title || "";

  const summary = document.createElement("p");
  summary.className = "summary";
  summary.textContent = item.summary || "";

  const actions = document.createElement("div");
  actions.className = "row-actions";
  const btnImportant = document.createElement("button");
  btnImportant.className = "btn-important icon-btn";
  btnImportant.type = "button";
  btnImportant.addEventListener("click", (e) => {
    e.stopPropagation();
    const current = !!state.itemsById.get(item.id)?.important_at;
    patchStateWithRollback(item.id, { important: !current });
  });

  const btnReadLater = document.createElement("button");
  btnReadLater.className = "btn-read-later icon-btn";
  btnReadLater.type = "button";
  btnReadLater.addEventListener("click", (e) => {
    e.stopPropagation();
    const current = !!state.itemsById.get(item.id)?.read_later_at;
    patchStateWithRollback(item.id, { read_later: !current });
  });

  actions.appendChild(btnImportant);
  actions.appendChild(btnReadLater);

  li.appendChild(line1);
  li.appendChild(title);
  if (item.summary) li.appendChild(summary);
  li.appendChild(actions);

  li.addEventListener("click", () => {
    if (state.selectedId === item.id) {
      state.selectedId = null;
      stopDetailPolling();
      closeDetailOnMobile();
      renderDetail(null);
    } else {
      state.selectedId = item.id;
      renderDetail(state.itemsById.get(item.id));
      loadDetail(item.id);
      startDetailPolling(item.id);
      openDetailOnMobile();
    }
    newsList.querySelectorAll(".news-item").forEach((row) => {
      row.classList.toggle("selected", row.dataset.id === state.selectedId);
    });
  });

  state.itemsById.set(item.id, item);
  syncRowUI(li, item);
  return li;
}

async function fetchNewsPage(page) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    q: state.q,
    read_filter: state.readFilter,
    collection: state.collection,
  });
  const res = await fetch(`/api/news?${params.toString()}`);
  if (!res.ok) throw new Error("news_fetch_failed");
  return res.json();
}

function resetList() {
  newsList.innerHTML = "";
  enteredViewport.clear();
  state.itemsById.clear();
  state.detailCacheByUrl.clear();
  state.page = 1;
  state.pages = 1;
  state.total = 0;
  state.hasMore = true;
  state.selectedId = null;
  stopDetailPolling();
  closeDetailOnMobile();
  renderDetail(null);
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
    updateCollectionButtons();
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
  } catch {
    setHint("自动同步失败，已展示本地索引，可点“刷新索引”重试。");
    await loadFirstPage();
  }
}

readFilterToggleBtn.addEventListener("click", async () => {
  state.readFilter = state.readFilter === "all" ? "unread" : "all";
  await loadFirstPage();
});

navFeedBtn.addEventListener("click", async () => {
  state.collection = "feed";
  await loadFirstPage();
});

navImportantBtn.addEventListener("click", async () => {
  state.collection = "important";
  await loadFirstPage();
});

navReadLaterBtn.addEventListener("click", async () => {
  state.collection = "read_later";
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
        collection: state.collection,
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
  refreshBtn.classList.add("loading");
  applyIcon(refreshBtn, "refresh", { label: "刷新中..." });
  try {
    const r = await fetch("/api/reindex", { method: "POST" });
    if (!r.ok) throw new Error("reindex_failed");
    await loadFirstPage();
  } catch {
    setHint("同步失败，可稍后重试。");
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.classList.remove("loading");
    applyIcon(refreshBtn, "refresh", { label: "刷新索引" });
  }
});

detailCloseBtn.addEventListener("click", closeDetailOnMobile);
detailCloseBtn.addEventListener("click", stopDetailPolling);

const detailImportantBtn = document.getElementById("detailImportantBtn");
const detailReadLaterBtn = document.getElementById("detailReadLaterBtn");
const detailLink = document.getElementById("detailLink");

detailImportantBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const current = !!state.itemsById.get(state.selectedId)?.important_at;
  await patchStateWithRollback(state.selectedId, { important: !current });
});

detailReadLaterBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const current = !!state.itemsById.get(state.selectedId)?.read_later_at;
  await patchStateWithRollback(state.selectedId, { read_later: !current });
  if (!current) {
    await loadDetail(state.selectedId);
  }
});

const detailRetryBtn = document.getElementById("detailRetryBtn");
detailRetryBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  detailRetryBtn.disabled = true;
  try {
    const res = await fetch(`/api/news/${encodeURIComponent(state.selectedId)}/detail/retry`, {
      method: "POST",
    });
    if (!res.ok) return;
    const item = state.itemsById.get(state.selectedId);
    if (item) {
      item.detail_status = "pending";
      state.itemsById.set(item.id, item);
      rerenderOne(item.id);
    }
    await loadDetail(state.selectedId);
    startDetailPolling(state.selectedId);
  } finally {
    detailRetryBtn.disabled = false;
  }
});

detailLink.addEventListener("click", async (e) => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item || !item.url) {
    e.preventDefault();
    return;
  }
  if (!item.read_at) {
    await patchStateWithRollback(state.selectedId, { read: true });
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    lastScrollY = window.scrollY;
  }
});

setupLoadObserver();
renderDetail(null);
applyIcon(markAllReadBtn, "check-circle", { label: "当前结果全部标为已读" });
applyIcon(refreshBtn, "refresh", { label: "刷新索引" });
updateFilterButtons();
autoReindexAndLoad();
