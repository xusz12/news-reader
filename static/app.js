let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "all", // all | unread
  feedReadFilter: "all", // 仅新闻流记忆 all | unread
  sourceFilter: "all", // all | reuters | bloomberg | techcrunch | ars | x | host:*
  collection: "feed", // feed | important | read_later
  total: 0,
  loading: false,
  hasMore: true,
  selectedId: null,
  itemsById: new Map(),
  detailCacheByUrl: new Map(),
  readingCheckpoint: null,
};

const mediaIconMap = {
  Reuters: "/static/source-icons/reuters.ico",
  Bloomberg: "/static/source-icons/bloomberg.png",
  TechCrunch: "/static/source-icons/techcrunch.png",
  "Ars Technica": "/static/source-icons/arstechnica.ico",
};

const refreshBtn = document.getElementById("refreshBtn");
const resumeAnchorBtn = document.getElementById("resumeAnchorBtn");
const readFilterToggleBtn = document.getElementById("readFilterToggleBtn");
const markAllReadBtn = document.getElementById("markAllReadBtn");

const navFeedBtn = document.getElementById("navFeedBtn");
const navImportantBtn = document.getElementById("navImportantBtn");
const navReadLaterBtn = document.getElementById("navReadLaterBtn");
const mobileCollectionTriggerBtn = document.getElementById("mobileCollectionTriggerBtn");
const mobileTabFilterBtn = document.getElementById("mobileTabFilterBtn");
const sourceFilters = document.getElementById("sourceFilters");
const mobileFilterSheet = document.getElementById("mobileFilterSheet");
const mobileFilterBackdrop = document.getElementById("mobileFilterBackdrop");
const mobileFilterCloseBtn = document.getElementById("mobileFilterCloseBtn");
const mobileFilterCollection = document.getElementById("mobileFilterCollection");
const mobileSourceFilters = document.getElementById("mobileSourceFilters");
const mobileCollectionSheet = document.getElementById("mobileCollectionSheet");
const mobileCollectionBackdrop = document.getElementById("mobileCollectionBackdrop");
const mobileCollectionCloseBtn = document.getElementById("mobileCollectionCloseBtn");
const mobileCollectionOptions = document.getElementById("mobileCollectionOptions");
const themeModeSelect = document.getElementById("themeModeSelect");
const detailFontSelect = document.getElementById("detailFontSelect");

const newsList = document.getElementById("newsList");
const meta = document.getElementById("meta");
const pageInfo = document.getElementById("pageInfo");
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");

const detailPanel = document.getElementById("detailPanel");
const detailEmpty = document.getElementById("detailEmpty");
const detailBody = document.getElementById("detailBody");
const detailCloseBtn = document.getElementById("detailCloseBtn");
const detailAiBox = document.getElementById("detailAiBox");
const detailAiPoints = document.getElementById("detailAiPoints");
const detailAiConclusion = document.getElementById("detailAiConclusion");
const detailOriginalWrap = document.getElementById("detailOriginalWrap");
const detailOriginalContent = document.getElementById("detailOriginalContent");

let readObserver = null;
let loadObserver = null;
let detailPollTimer = null;
let rowStatusPollTimer = null;
let lastListScrollTop = 0;
let lastRenderedDateKey = null;
let latestSourceOptions = [];
const detailSwipeState = {
  tracking: false,
  startX: 0,
  startY: 0,
  deltaX: 0,
  deltaY: 0,
  axis: null,
};
const enteredViewport = new Set();
const writeInFlight = new Set();

const THEME_KEY = "news_reader_theme_mode";
const DETAIL_FONT_KEY = "news_reader_detail_font";
const MOBILE_BREAKPOINT_QUERY = "(max-width: 768px)";
const DETAIL_SWIPE_CLOSE_PX = 72;
const DETAIL_SWIPE_EDGE_PX = 40;
const DETAIL_SWIPE_AXIS_RATIO = 1.5;

function setHint(text) {
  listHint.textContent = text || "";
}

function isMobileLayout() {
  return window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches;
}

function applyThemeMode(mode) {
  const finalMode = ["system", "light", "dark"].includes(mode) ? mode : "system";
  document.documentElement.setAttribute("data-theme", finalMode);
  if (themeModeSelect) themeModeSelect.value = finalMode;
  try {
    localStorage.setItem(THEME_KEY, finalMode);
  } catch {}
}

function applyDetailFontMode(mode) {
  const finalMode = ["small", "medium", "large"].includes(mode) ? mode : "medium";
  document.documentElement.setAttribute("data-detail-font", finalMode);
  if (detailFontSelect) detailFontSelect.value = finalMode;
  try {
    localStorage.setItem(DETAIL_FONT_KEY, finalMode);
  } catch {}
}

function stopDetailPolling() {
  if (detailPollTimer) {
    window.clearInterval(detailPollTimer);
    detailPollTimer = null;
  }
}

function stopRowStatusPolling() {
  if (rowStatusPollTimer) {
    window.clearInterval(rowStatusPollTimer);
    rowStatusPollTimer = null;
  }
}

function rowNeedsStatusPolling(item) {
  if (!item || !item.read_later_at) return false;
  const detailReady = Number(item.detail_ready || 0) === 1;
  const detailStatus = item.detail_status || "none";
  const aiStatus = item.ai_status || "none";
  if (!detailReady) {
    return detailStatus === "pending" || detailStatus === "running";
  }
  return aiStatus === "pending" || aiStatus === "running" || aiStatus === "none";
}

function collectPendingRowIds() {
  if (document.hidden) return [];
  const ids = [];
  newsList.querySelectorAll(".news-item").forEach((row) => {
    const id = row.dataset.id;
    const item = state.itemsById.get(id);
    if (rowNeedsStatusPolling(item)) ids.push(id);
  });
  return ids;
}

async function pollRowStatusesOnce() {
  const ids = collectPendingRowIds();
  if (!ids.length) {
    stopRowStatusPolling();
    return;
  }
  const params = new URLSearchParams({ ids: ids.join(",") });
  const res = await fetch(`/api/news/status?${params.toString()}`);
  if (!res.ok) return;
  const data = await res.json();
  if (!data.ok || !Array.isArray(data.items)) return;
  data.items.forEach((st) => {
    const item = state.itemsById.get(st.id);
    if (!item) return;
    item.read_later_at = st.read_later_at;
    item.detail_status = st.detail_status;
    item.detail_error = st.detail_error;
    item.detail_ready = st.detail_ready;
    item.ai_status = st.ai_status || "none";
    state.itemsById.set(item.id, item);
    rerenderOne(item.id);
  });
  if (!collectPendingRowIds().length) stopRowStatusPolling();
}

function ensureRowStatusPolling() {
  const ids = collectPendingRowIds();
  if (!ids.length) {
    stopRowStatusPolling();
    return;
  }
  if (rowStatusPollTimer) return;
  rowStatusPollTimer = window.setInterval(() => {
    pollRowStatusesOnce().catch(() => {});
  }, 3000);
}

function kickRowStatusPolling() {
  ensureRowStatusPolling();
  pollRowStatusesOnce().catch(() => {});
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
  if (name === "crosshair") {
    return `<svg ${common}><circle cx="12" cy="12" r="6.8"/><path d="M12 3.5v2.2"/><path d="M12 18.3v2.2"/><path d="M3.5 12h2.2"/><path d="M18.3 12h2.2"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/></svg>`;
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

function isBloombergVideoUrl(url) {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return /(?:^|\.)bloomberg\.com$/i.test(parsed.hostname) && parsed.pathname.startsWith("/news/videos/");
  } catch {
    return false;
  }
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
    const tone = item.read_later_at
      ? (detailReady ? "success" : "warning")
      : (detailReady ? "success" : "default");
    applyIcon(readLaterBtn, "bookmark", {
      filled: !!item.read_later_at,
      tone,
      label: item.read_later_at
        ? (detailReady ? "取消稍后再看（详情已就绪）" : (detailFailed ? "取消稍后再看（详情失败）" : "取消稍后再看（详情抓取中）"))
        : (detailReady ? "详情已缓存，加入稍后再看" : "稍后再看"),
    });
  }

  li.classList.toggle("selected", state.selectedId === item.id);
}

function updateFilterButtons() {
  const showReadFilter = state.collection === "feed";
  readFilterToggleBtn.classList.toggle("hidden", !showReadFilter);
  if (!showReadFilter) return;
  const isAll = state.readFilter === "all";
  applyIcon(readFilterToggleBtn, "circle", {
    filled: isAll,
    tone: isAll ? "default" : "muted",
    label: isAll ? "全部显示" : "仅未读",
  });
}

function updateResumeButton() {
  const visible = state.collection === "feed" && !!state.readingCheckpoint?.url;
  resumeAnchorBtn.classList.toggle("hidden", !visible);
  if (!visible) return;
  const title = state.readingCheckpoint?.title || "回到上次阅读";
  applyResumeIcon(`回到上次阅读：${title}`);
}

function applyResumeIcon(label = "回到上次阅读") {
  applyIcon(resumeAnchorBtn, "crosshair", {
    filled: false,
    tone: "success",
    label,
  });
}

function updateBatchActionButton() {
  if (state.collection === "important") {
    markAllReadBtn.classList.add("hidden");
    markAllReadBtn.disabled = false;
    return;
  }
  markAllReadBtn.classList.remove("hidden");
  if (state.collection === "read_later") {
    applyIcon(markAllReadBtn, "bookmark", { label: "全部看完（取消所有稍后阅读）" });
  } else {
    applyIcon(markAllReadBtn, "check-circle", { label: "当前结果全部标为已读" });
  }
}

function updateCollectionButtons() {
  navFeedBtn.classList.toggle("active", state.collection === "feed");
  navImportantBtn.classList.toggle("active", state.collection === "important");
  navReadLaterBtn.classList.toggle("active", state.collection === "read_later");
  if (mobileCollectionTriggerBtn) {
    mobileCollectionTriggerBtn.classList.toggle("active", true);
    const names = {
      feed: "新闻流",
      important: "重要",
      read_later: "稍后",
    };
    mobileCollectionTriggerBtn.textContent = names[state.collection] || "新闻流";
  }
}

function updateMobileFilterCollectionText() {
  if (!mobileFilterCollection) return;
  const names = {
    feed: "新闻流",
    important: "重要新闻",
    read_later: "稍后再看",
  };
  mobileFilterCollection.textContent = `当前集合：${names[state.collection] || "新闻流"}`;
}

function closeMobileFilterSheet() {
  if (!mobileFilterSheet) return;
  mobileFilterSheet.classList.add("hidden");
  mobileFilterSheet.setAttribute("aria-hidden", "true");
}

function closeMobileCollectionSheet() {
  if (!mobileCollectionSheet) return;
  mobileCollectionSheet.classList.add("hidden");
  mobileCollectionSheet.setAttribute("aria-hidden", "true");
}

function renderMobileCollectionOptions() {
  if (!mobileCollectionOptions) return;
  mobileCollectionOptions.innerHTML = "";
  const options = [
    { key: "feed", label: "新闻流" },
    { key: "important", label: "重要" },
    { key: "read_later", label: "稍后阅读" },
  ];
  for (const option of options) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mobile-source-btn";
    btn.textContent = option.label;
    btn.classList.toggle("active", state.collection === option.key);
    btn.addEventListener("click", async () => {
      await switchCollection(option.key);
      closeMobileCollectionSheet();
    });
    mobileCollectionOptions.appendChild(btn);
  }
}

function openMobileCollectionSheet() {
  if (!mobileCollectionSheet) return;
  closeMobileFilterSheet();
  renderMobileCollectionOptions();
  mobileCollectionSheet.classList.remove("hidden");
  mobileCollectionSheet.setAttribute("aria-hidden", "false");
}

function openMobileFilterSheet() {
  if (!mobileFilterSheet) return;
  closeMobileCollectionSheet();
  updateMobileFilterCollectionText();
  renderSourceFilters(latestSourceOptions);
  mobileFilterSheet.classList.remove("hidden");
  mobileFilterSheet.setAttribute("aria-hidden", "false");
}

function sourceLabel(key) {
  const fixed = {
    all: "全部来源",
    reuters: "Reuters",
    bloomberg: "Bloomberg",
    techcrunch: "TechCrunch",
    ars: "Ars Technica",
    x: "X",
  };
  return fixed[key] || key;
}

function renderSourceFilters(options) {
  latestSourceOptions = Array.isArray(options) ? options : [];

  const fillContainer = (container, className) => {
    if (!container) return;
    container.innerHTML = "";

    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = className;
    allBtn.textContent = "全部来源";
    allBtn.classList.toggle("active", state.sourceFilter === "all");
    allBtn.addEventListener("click", async () => {
      if (state.sourceFilter === "all") return;
      state.sourceFilter = "all";
      await loadFirstPage();
      closeMobileFilterSheet();
    });
    container.appendChild(allBtn);

    for (const src of latestSourceOptions) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = className;
      btn.dataset.sourceKey = src.key;
      btn.textContent = `${sourceLabel(src.key) || src.label} (${src.count})`;
      btn.classList.toggle("active", state.sourceFilter === src.key);
      btn.addEventListener("click", async () => {
        if (state.sourceFilter === src.key) return;
        state.sourceFilter = src.key;
        await loadFirstPage();
        closeMobileFilterSheet();
      });
      container.appendChild(btn);
    }
  };

  fillContainer(sourceFilters, "nav-btn source-btn");
  fillContainer(mobileSourceFilters, "mobile-source-btn");
  updateMobileFilterCollectionText();
}

async function fetchSources() {
  const params = new URLSearchParams({
    q: state.q,
    collection: state.collection,
    read_filter: state.collection === "feed" ? state.readFilter : "all",
  });
  const res = await fetch(`/api/sources?${params.toString()}`);
  if (!res.ok) return [];
  const data = await res.json();
  if (!data.ok) return [];
  return Array.isArray(data.sources) ? data.sources : [];
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
  const readFilterName = state.collection === "feed" ? readNames[state.readFilter] : readNames.all;
  const sourceName = state.sourceFilter === "all" ? "全部来源" : sourceLabel(state.sourceFilter);
  meta.textContent = `${names[state.collection]} · ${readFilterName} · ${sourceName} · 共 ${state.total} 条`;
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

async function fetchReadingCheckpoint() {
  const res = await fetch("/api/reading-checkpoint?scope=feed");
  if (!res.ok) return null;
  const data = await res.json();
  if (!data.ok) return null;
  return data.checkpoint || null;
}

async function saveReadingCheckpoint(item) {
  if (!item || state.collection !== "feed" || !item.url) return;
  state.readingCheckpoint = {
    scope: "feed",
    item_id: item.id,
    url: item.url,
    title: item.title || "",
  };
  updateResumeButton();
  await fetch("/api/reading-checkpoint", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.readingCheckpoint),
  });
}

async function locateReadingCheckpoint() {
  const params = new URLSearchParams({
    scope: "feed",
    per: String(state.per),
    q: "",
    read_filter: "all",
    source_filter: "all",
  });
  const res = await fetch(`/api/reading-checkpoint/locate?${params.toString()}`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.ok ? data : null;
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
      item.ai_status = "none";
      item.ai_ready = 0;
    } else {
      item.detail_status = "canceled";
      item.ai_status = "canceled";
      stopDetailPolling();
    }
  }
  rerenderOne(itemId);

  try {
    const result = await patchState(itemId, payload);
    applyPatchToItem(item, result);
    rerenderOne(itemId);
    if ("read_later" in payload) {
      if (payload.read_later) {
        kickRowStatusPolling();
      } else {
        ensureRowStatusPolling();
      }
    }
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
    detailPanel.style.transition = "";
    detailPanel.style.transform = "";
    detailPanel.classList.add("open");
  }
}

function closeDetailOnMobile() {
  detailPanel.style.transition = "";
  detailPanel.style.transform = "";
  detailPanel.classList.remove("open");
}

function resetDetailSwipeState() {
  detailSwipeState.tracking = false;
  detailSwipeState.startX = 0;
  detailSwipeState.startY = 0;
  detailSwipeState.deltaX = 0;
  detailSwipeState.deltaY = 0;
  detailSwipeState.axis = null;
}

function handleDetailTouchStart(e) {
  if (!isMobileLayout()) return;
  if (!detailPanel.classList.contains("open")) return;
  if (!e.touches || e.touches.length !== 1) return;
  const touch = e.touches[0];
  if (touch.clientX > DETAIL_SWIPE_EDGE_PX) return;
  detailSwipeState.tracking = true;
  detailSwipeState.startX = touch.clientX;
  detailSwipeState.startY = touch.clientY;
  detailSwipeState.deltaX = 0;
  detailSwipeState.deltaY = 0;
  detailSwipeState.axis = null;
}

function handleDetailTouchMove(e) {
  if (!detailSwipeState.tracking) return;
  if (!isMobileLayout()) return;
  if (!e.touches || e.touches.length !== 1) return;

  const touch = e.touches[0];
  const dx = touch.clientX - detailSwipeState.startX;
  const dy = touch.clientY - detailSwipeState.startY;
  detailSwipeState.deltaX = dx;
  detailSwipeState.deltaY = dy;

  if (!detailSwipeState.axis) {
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    if (absX < 6 && absY < 6) return;
    detailSwipeState.axis = absX > absY * DETAIL_SWIPE_AXIS_RATIO ? "x" : "y";
  }

  if (detailSwipeState.axis !== "x") return;
  if (dx <= 0) return;

  e.preventDefault();
  const dragX = Math.min(dx, Math.floor(window.innerWidth * 0.9));
  detailPanel.style.transition = "none";
  detailPanel.style.transform = `translateX(${dragX}px)`;
}

function handleDetailTouchEnd() {
  if (!detailSwipeState.tracking) return;
  const shouldClose =
    detailSwipeState.axis === "x" &&
    detailSwipeState.deltaX > DETAIL_SWIPE_CLOSE_PX &&
    detailSwipeState.deltaX > Math.abs(detailSwipeState.deltaY) * DETAIL_SWIPE_AXIS_RATIO;
  resetDetailSwipeState();
  if (shouldClose) {
    closeDetailOnMobile();
    return;
  }
  detailPanel.style.transition = "";
  detailPanel.style.transform = "";
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
  const summaryEl = document.getElementById("detailSummary");
  const hasSummary = typeof item.summary === "string" && item.summary.trim().length > 0;
  if (hasSummary) {
    summaryEl.textContent = item.summary.trim();
    summaryEl.classList.remove("hidden");
  } else {
    summaryEl.textContent = "";
    summaryEl.classList.add("hidden");
  }

  const link = document.getElementById("detailLink");
  const statusEl = document.getElementById("detailStatus");
  const contentEl = document.getElementById("detailContent");
  const retryBtn = document.getElementById("detailRetryBtn");
  const retranslateBtn = document.getElementById("detailRetranslateBtn");

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
  const detailErr = cached?.job?.last_error || item.detail_error || "";
  const ai = cached?.ai || null;
  const aiStatus = cached?.ai_status || item.ai_status || "none";

  detailAiBox.classList.add("hidden");
  detailAiPoints.innerHTML = "";
  detailAiConclusion.textContent = "";
  detailOriginalWrap.classList.add("hidden");
  detailOriginalContent.textContent = "";
  retryBtn.textContent = "重试详情抓取";
  retryBtn.classList.add("hidden");
  retranslateBtn.textContent = "重新翻译";
  retranslateBtn.disabled = false;
  retranslateBtn.classList.add("hidden");

  if (detail && detail.content) {
    const original = detail.content;
    detailOriginalContent.textContent = original;
    detailOriginalWrap.classList.remove("hidden");
    retranslateBtn.classList.remove("hidden");

    if (aiStatus === "pending" || aiStatus === "running" || aiStatus === "none") {
      statusEl.textContent = aiStatus === "pending" ? "排队生成中文内容" : "正在生成中文内容";
      statusEl.className = "detail-status pending";
      contentEl.textContent = ai && ai.body_zh ? ai.body_zh : original;
      contentEl.classList.remove("hidden");
      retranslateBtn.textContent = "正在重新翻译...";
      retranslateBtn.disabled = true;
    } else if (ai && ai.body_zh) {
      let keyPoints = [];
      try {
        keyPoints = JSON.parse(ai.key_points_zh || "[]");
      } catch {
        keyPoints = [];
      }
      if (Array.isArray(keyPoints) && keyPoints.length) {
        keyPoints.forEach((point) => {
          const li = document.createElement("li");
          li.textContent = point;
          detailAiPoints.appendChild(li);
        });
      }
      detailAiConclusion.textContent = ai.conclusion_zh || "";
      detailAiBox.classList.remove("hidden");

      statusEl.textContent = "中文摘要与翻译已生成";
      statusEl.className = "detail-status ready";
      contentEl.textContent = ai.body_zh;
      contentEl.classList.remove("hidden");
      stopDetailPolling();
    } else if (aiStatus === "failed") {
      const err = cached?.ai_job?.last_error || item.ai_error || "中文生成失败";
      statusEl.textContent = `中文生成失败，可重试：${err}`;
      statusEl.className = "detail-status failed";
      contentEl.textContent = original;
      contentEl.classList.remove("hidden");
      stopDetailPolling();
    } else {
      statusEl.textContent = `详情已完成 · 正文长度 ${detail.content_length || detail.content.length}`;
      statusEl.className = "detail-status ready";
      contentEl.textContent = original;
      contentEl.classList.remove("hidden");
      stopDetailPolling();
    }
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
    if (item.source_type === "twitter") {
      statusEl.textContent = "这是推文，当前不提供正文抓取";
    } else if (detailErr.includes("BLOOMBERG_VIDEO") || isBloombergVideoUrl(item.url)) {
      statusEl.textContent = "这是视频新闻，当前不提供正文抓取";
    } else {
      statusEl.textContent = "已跳过（该来源暂不抓正文）";
    }
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
  item.ai_status = payload.ai_status || "none";
  item.ai_ready = payload.ai ? 1 : 0;
  if (payload.job && payload.job.last_error) item.detail_error = payload.job.last_error;
  if (payload.ai_job && payload.ai_job.last_error) item.ai_error = payload.ai_job.last_error;
  state.itemsById.set(item.id, item);
  rerenderOne(item.id);

  // 在“稍后再看”集合中，用户打开且详情已可读后自动取消稍后标记。
  // 仅清 read_later，不影响已抓取详情/AI缓存与其它状态。
  if (
    state.collection === "read_later" &&
    state.selectedId === itemId &&
    item.read_later_at &&
    (Number(item.detail_ready || 0) === 1 || item.ai_status === "success")
  ) {
    await patchStateWithRollback(itemId, { read_later: false });
  }
}

function startDetailPolling(itemId) {
  stopDetailPolling();
  const current = state.itemsById.get(itemId);
  if (!current) return;
  const detailReady = Number(current.detail_ready || 0) === 1;
  const aiStatus = current.ai_status || "none";
  const shouldPollDetail = !!current.read_later_at && !detailReady;
  const shouldPollAi = detailReady && (aiStatus === "pending" || aiStatus === "running" || aiStatus === "none");
  if (!shouldPollDetail && !shouldPollAi) return;

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
    const aiStatus = refreshed.ai_status || "none";
    if (Number(refreshed.detail_ready || 0) !== 1) {
      if (!refreshed.read_later_at || status === "failed" || status === "skipped" || status === "canceled") {
        stopDetailPolling();
      }
      return;
    }
    if (aiStatus === "success" || aiStatus === "failed" || aiStatus === "canceled") {
      stopDetailPolling();
    }
  }, 2000);
}

function setupReadObserver() {
  if (readObserver) readObserver.disconnect();
  readObserver = new IntersectionObserver(
    (entries) => {
      if (document.hidden) return;
      const currentTop = newsList.scrollTop;
      const scrollingDown = currentTop > lastListScrollTop;
      lastListScrollTop = currentTop;
      const listTop = newsList.getBoundingClientRect().top;

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
        if (entry.boundingClientRect.bottom < listTop) {
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
  if (isBloombergVideoUrl(item.url)) {
    const videoBadge = document.createElement("span");
    videoBadge.className = "video-badge";
    videoBadge.textContent = "VIDEO";
    line1.appendChild(videoBadge);
  }

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
  if (!isBloombergVideoUrl(item.url) && item.source_type !== "twitter") {
    actions.appendChild(btnReadLater);
  }

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
      saveReadingCheckpoint(item).catch(() => {});
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
    source_filter: state.sourceFilter,
  });
  const res = await fetch(`/api/news?${params.toString()}`);
  if (!res.ok) throw new Error("news_fetch_failed");
  return res.json();
}

function resetList() {
  newsList.querySelectorAll(".news-item, .date-section").forEach((node) => node.remove());
  enteredViewport.clear();
  state.itemsById.clear();
  state.detailCacheByUrl.clear();
  state.page = 1;
  state.pages = 1;
  state.total = 0;
  state.hasMore = true;
  lastListScrollTop = 0;
  state.selectedId = null;
  stopDetailPolling();
  stopRowStatusPolling();
  closeDetailOnMobile();
  renderDetail(null);
  lastRenderedDateKey = null;
}

function buildDateSectionRow(item) {
  const li = document.createElement("li");
  li.className = "date-section";
  const label = document.createElement("span");
  label.className = "date-section-label";
  label.textContent = item.date_label || item.date_key || "未知日期";
  li.appendChild(label);
  return li;
}

function appendNewsRow(item, row) {
  const dateKey = item.date_key || "unknown";
  if (dateKey !== lastRenderedDateKey) {
    const section = buildDateSectionRow(item);
    if (listHint && listHint.parentElement === newsList) {
      newsList.insertBefore(section, listHint);
    } else {
      newsList.appendChild(section);
    }
    lastRenderedDateKey = dateKey;
  }
  if (listHint && listHint.parentElement === newsList) {
    newsList.insertBefore(row, listHint);
    return;
  }
  newsList.appendChild(row);
}

async function loadFirstPage() {
  if (state.collection === "feed") {
    state.readFilter = state.feedReadFilter;
  } else if (state.readFilter !== "all") {
    state.readFilter = "all";
  }
  state.loading = true;
  try {
    const sourceList = await fetchSources();
    const available = new Set(sourceList.map((x) => x.key));
    if (state.sourceFilter !== "all" && !available.has(state.sourceFilter)) {
      state.sourceFilter = "all";
    }
    renderSourceFilters(sourceList);

    const data = await fetchNewsPage(1);
    resetList();
    state.total = data.total;
    state.pages = data.pages;
    state.page = 1;
    state.hasMore = state.page < state.pages;

    data.items.forEach((item) => appendNewsRow(item, buildItemRow(item)));
    renderMeta();

    if (state.total === 0) {
      setHint("暂无数据");
    } else if (state.hasMore) {
      setHint("继续下滑加载更多");
    } else {
      setHint("已加载全部新闻");
    }

    setupReadObserver();
    ensureRowStatusPolling();
  } finally {
    state.loading = false;
    updateFilterButtons();
    updateBatchActionButton();
    updateCollectionButtons();
    updateResumeButton();
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
      appendNewsRow(item, row);
      if (readObserver) readObserver.observe(row);
    });
    state.page = next;
    state.pages = data.pages;
    state.total = data.total;
    state.hasMore = state.page < state.pages;
    renderMeta();
    setHint(state.hasMore ? "继续下滑加载更多" : "已加载全部新闻");
    ensureRowStatusPolling();
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
  state.feedReadFilter = state.readFilter;
  await loadFirstPage();
});

resumeAnchorBtn.addEventListener("click", async () => {
  resumeAnchorBtn.disabled = true;
  try {
    const located = await locateReadingCheckpoint();
    if (!located || !located.found) {
      setHint("未找到上次阅读锚点，可能已不在当前新闻流。");
      return;
    }

    state.collection = "feed";
    state.q = "";
    state.readFilter = "all";
    state.feedReadFilter = "all";
    state.sourceFilter = "all";
    await loadFirstPage();
    while (state.page < located.page && state.hasMore) {
      await loadNextPage();
    }

    const row = newsList.querySelector(`.news-item[data-id="${located.item_id}"]`);
    if (!row) {
      setHint("锚点定位成功，但当前页未找到目标条目。");
      return;
    }
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    row.classList.add("anchor-flash");
    window.setTimeout(() => row.classList.remove("anchor-flash"), 2000);
    if (!window.matchMedia("(max-width: 768px)").matches) {
      row.click();
    }
  } finally {
    resumeAnchorBtn.disabled = false;
  }
});

async function switchCollection(collection) {
  if (state.collection === collection) return;
  state.collection = collection;
  closeMobileFilterSheet();
  closeMobileCollectionSheet();
  await loadFirstPage();
}

navFeedBtn.addEventListener("click", async () => {
  await switchCollection("feed");
});

navImportantBtn.addEventListener("click", async () => {
  await switchCollection("important");
});

navReadLaterBtn.addEventListener("click", async () => {
  await switchCollection("read_later");
});

if (mobileCollectionTriggerBtn) {
  mobileCollectionTriggerBtn.addEventListener("click", () => {
    openMobileCollectionSheet();
  });
}

if (mobileTabFilterBtn) {
  mobileTabFilterBtn.addEventListener("click", () => {
    openMobileFilterSheet();
  });
}

if (mobileFilterBackdrop) {
  mobileFilterBackdrop.addEventListener("click", closeMobileFilterSheet);
}

if (mobileFilterCloseBtn) {
  mobileFilterCloseBtn.addEventListener("click", closeMobileFilterSheet);
}

if (mobileCollectionBackdrop) {
  mobileCollectionBackdrop.addEventListener("click", closeMobileCollectionSheet);
}

if (mobileCollectionCloseBtn) {
  mobileCollectionCloseBtn.addEventListener("click", closeMobileCollectionSheet);
}

if (themeModeSelect) {
  themeModeSelect.addEventListener("change", () => {
    applyThemeMode(themeModeSelect.value);
  });
}

if (detailFontSelect) {
  detailFontSelect.addEventListener("change", () => {
    applyDetailFontMode(detailFontSelect.value);
  });
}

markAllReadBtn.addEventListener("click", async () => {
  if (state.collection === "important") return;

  const readLaterMode = state.collection === "read_later";
  const ok = window.confirm(
    readLaterMode
      ? "将当前稍后阅读结果（跨页）全部取消标记？"
      : "将当前筛选结果（跨页）全部标为已读？"
  );
  if (!ok) return;
  markAllReadBtn.disabled = true;
  try {
    const endpoint = readLaterMode ? "/api/news/clear-read-later" : "/api/news/mark-all-read";
    const body = {
      q: state.q,
      collection: state.collection,
      source_filter: state.sourceFilter,
    };
    if (!readLaterMode) body.read_filter = state.readFilter;
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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
    newsList.scrollTo({ top: 0, behavior: "auto" });
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
detailPanel.addEventListener("touchstart", handleDetailTouchStart, { passive: true });
detailPanel.addEventListener("touchmove", handleDetailTouchMove, { passive: false });
detailPanel.addEventListener("touchend", handleDetailTouchEnd, { passive: true });
detailPanel.addEventListener("touchcancel", handleDetailTouchEnd, { passive: true });

const detailImportantBtn = document.getElementById("detailImportantBtn");
const detailLink = document.getElementById("detailLink");

detailImportantBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const current = !!state.itemsById.get(state.selectedId)?.important_at;
  await patchStateWithRollback(state.selectedId, { important: !current });
});

const detailRetryBtn = document.getElementById("detailRetryBtn");
const detailRetranslateBtn = document.getElementById("detailRetranslateBtn");
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
      if (Number(item.detail_ready || 0) === 1) {
        item.ai_status = "pending";
      } else {
        item.detail_status = "pending";
      }
      state.itemsById.set(item.id, item);
      rerenderOne(item.id);
    }
    await loadDetail(state.selectedId);
    startDetailPolling(state.selectedId);
  } finally {
    detailRetryBtn.disabled = false;
  }
});

detailRetranslateBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item || Number(item.detail_ready || 0) !== 1) return;
  detailRetranslateBtn.disabled = true;
  try {
    const res = await fetch(`/api/news/${encodeURIComponent(state.selectedId)}/detail/retry`, {
      method: "POST",
    });
    if (!res.ok) return;
    item.ai_status = "pending";
    state.itemsById.set(item.id, item);
    rerenderOne(item.id);
    await loadDetail(state.selectedId);
    startDetailPolling(state.selectedId);
  } finally {
    detailRetranslateBtn.disabled = false;
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
    lastListScrollTop = newsList.scrollTop;
    stopRowStatusPolling();
  } else {
    kickRowStatusPolling();
  }
});

setupLoadObserver();
renderDetail(null);
try {
  applyThemeMode(localStorage.getItem(THEME_KEY) || "system");
} catch {
  applyThemeMode("system");
}
try {
  applyDetailFontMode(localStorage.getItem(DETAIL_FONT_KEY) || "medium");
} catch {
  applyDetailFontMode("medium");
}
applyResumeIcon();
applyIcon(refreshBtn, "refresh", { label: "刷新索引" });
updateFilterButtons();
updateBatchActionButton();
fetchReadingCheckpoint()
  .then((cp) => {
    state.readingCheckpoint = cp;
    updateResumeButton();
  })
  .catch(() => {});
autoReindexAndLoad();
