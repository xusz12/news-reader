let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "unread", // all | unread
  feedReadFilter: "unread", // 仅新闻流记忆 all | unread
  sourceFilter: "all", // all | reuters | bloomberg | techcrunch | ars | x | host:*
  collection: "feed", // search | feed | important | read_later | notes | market_tags | trends
  total: 0,
  loading: false,
  hasMore: true,
  selectedId: null,
  itemsById: new Map(),
  detailCacheByUrl: new Map(),
  readingCheckpoint: null,
  trendDays: 7,
  trendRows: [],
  trendDates: [],
  trendSelection: null,
  trendNoteContext: null,
  marketTagChoices: [],
  tagAdminOpen: false,
  trendComposeOpen: false,
  dateCounts: new Map(),
  lastNewsCollectionBeforeTrends: "feed",
  detailReturnToTrend: false,
  searchRange: "all",
  searchTime: "all",
  feedUnreadCursor: null,
  detailView: "detail",
  detailChatProvider: "deepseek",
  detailChatMessages: [],
  detailChatStatus: "",
  detailChatSending: false,
  settingsOpen: false,
  settingsLoading: false,
  settingsSaving: false,
  runtimeSettings: null,
  releaseNotes: [],
  settingsMessage: "",
  settingsMessageTone: "muted",
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
const manageMarketTagsBtn = document.getElementById("manageMarketTagsBtn");

const navSearchBtn = document.getElementById("navSearchBtn");
const navFeedBtn = document.getElementById("navFeedBtn");
const navImportantBtn = document.getElementById("navImportantBtn");
const navReadLaterBtn = document.getElementById("navReadLaterBtn");
const navNotesBtn = document.getElementById("navNotesBtn");
const navMarketTagsBtn = document.getElementById("navMarketTagsBtn");
const navTrendsBtn = document.getElementById("navTrendsBtn");
const mobileCollectionTriggerBtn = document.getElementById("mobileCollectionTriggerBtn");
const mobileTabFilterBtn = document.getElementById("mobileTabFilterBtn");
const mobileTrendsTabBtn = document.getElementById("mobileTrendsTabBtn");
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
const settingsBtn = document.getElementById("settingsBtn");
const errorStatsBtn = document.getElementById("errorStatsBtn");
const errorStatsPanel = document.getElementById("errorStatsPanel");
const errorStatsBody = document.getElementById("errorStatsBody");
const searchPageControls = document.getElementById("searchPageControls");
const searchPageInput = document.getElementById("searchPageInput");
const searchRangeSelect = document.getElementById("searchRangeSelect");
const searchTimeSelect = document.getElementById("searchTimeSelect");
const searchPageSubmitBtn = document.getElementById("searchPageSubmitBtn");

const newsList = document.getElementById("newsList");
const meta = document.getElementById("meta");
const pageInfo = document.getElementById("pageInfo");
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");
const workspace = document.getElementById("workspace");
const trendsView = document.getElementById("trendsView");
const trendsTable = document.getElementById("trendsTable");

const detailPanel = document.getElementById("detailPanel");
const detailEmpty = document.getElementById("detailEmpty");
const detailTrendBody = document.getElementById("detailTrendBody");
const detailTrendTitle = document.getElementById("detailTrendTitle");
const detailTrendMeta = document.getElementById("detailTrendMeta");
const trendComposeBtn = document.getElementById("trendComposeBtn");
const trendBullishNoteBtn = document.getElementById("trendBullishNoteBtn");
const trendBearishNoteBtn = document.getElementById("trendBearishNoteBtn");
const detailTrendNoteCard = document.getElementById("detailTrendNoteCard");
const detailTrendNoteTitle = document.getElementById("detailTrendNoteTitle");
const detailTrendNoteText = document.getElementById("detailTrendNoteText");
const detailTrendNoteEditor = document.getElementById("detailTrendNoteEditor");
const detailTrendNoteEditorMeta = document.getElementById("detailTrendNoteEditorMeta");
const detailTrendNoteInput = document.getElementById("detailTrendNoteInput");
const detailTrendNoteSaveBtn = document.getElementById("detailTrendNoteSaveBtn");
const detailTrendNoteDeleteBtn = document.getElementById("detailTrendNoteDeleteBtn");
const detailTrendNoteCancelBtn = document.getElementById("detailTrendNoteCancelBtn");
const detailTrendList = document.getElementById("detailTrendList");
const detailTrendComposerBody = document.getElementById("detailTrendComposerBody");
const trendNoteDateSelect = document.getElementById("trendNoteDateSelect");
const trendNoteTagSelect = document.getElementById("trendNoteTagSelect");
const trendNoteDirectionSelect = document.getElementById("trendNoteDirectionSelect");
const trendNoteComposeInput = document.getElementById("trendNoteComposeInput");
const trendNoteComposeSaveBtn = document.getElementById("trendNoteComposeSaveBtn");
const trendNoteComposeDeleteBtn = document.getElementById("trendNoteComposeDeleteBtn");
const trendNoteComposeCancelBtn = document.getElementById("trendNoteComposeCancelBtn");
const detailTagAdminBody = document.getElementById("detailTagAdminBody");
const detailTagCreateInput = document.getElementById("detailTagCreateInput");
const detailTagCreateBtn = document.getElementById("detailTagCreateBtn");
const detailTagAdminList = document.getElementById("detailTagAdminList");
const detailBody = document.getElementById("detailBody");
const detailChatBody = document.getElementById("detailChatBody");
const detailAskBtn = document.getElementById("detailAskBtn");
const detailChatBackBtn = document.getElementById("detailChatBackBtn");
const detailChatMeta = document.getElementById("detailChatMeta");
const detailChatProviderSelect = document.getElementById("detailChatProviderSelect");
const detailChatCapability = document.getElementById("detailChatCapability");
const detailChatStatus = document.getElementById("detailChatStatus");
const detailChatMessages = document.getElementById("detailChatMessages");
const detailChatInput = document.getElementById("detailChatInput");
const detailChatSendBtn = document.getElementById("detailChatSendBtn");
const settingsOverlay = document.getElementById("settingsOverlay");
const settingsBackdrop = document.getElementById("settingsBackdrop");
const settingsCloseBtn = document.getElementById("settingsCloseBtn");
const settingsStatus = document.getElementById("settingsStatus");
const settingsApiStatus = document.getElementById("settingsApiStatus");
const settingsTranslationProvider = document.getElementById("settingsTranslationProvider");
const settingsTranslationModel = document.getElementById("settingsTranslationModel");
const settingsChatDefaultProvider = document.getElementById("settingsChatDefaultProvider");
const settingsChatDeepseekModel = document.getElementById("settingsChatDeepseekModel");
const settingsChatOpenaiModel = document.getElementById("settingsChatOpenaiModel");
const settingsSaveBtn = document.getElementById("settingsSaveBtn");
const settingsRestartHint = document.getElementById("settingsRestartHint");
const settingsReleaseNotes = document.getElementById("settingsReleaseNotes");
const detailCloseBtn = document.getElementById("detailCloseBtn");
const detailAiBox = document.getElementById("detailAiBox");
const detailAiPoints = document.getElementById("detailAiPoints");
const detailAiConclusion = document.getElementById("detailAiConclusion");
const detailOriginalWrap = document.getElementById("detailOriginalWrap");
const detailOriginalContent = document.getElementById("detailOriginalContent");
const detailNoteToggleBtn = document.getElementById("detailNoteToggleBtn");
const detailNoteCard = document.getElementById("detailNoteCard");
const detailNoteText = document.getElementById("detailNoteText");
const detailNoteEditor = document.getElementById("detailNoteEditor");
const detailNoteInput = document.getElementById("detailNoteInput");
const detailNoteSaveBtn = document.getElementById("detailNoteSaveBtn");
const detailNoteCancelBtn = document.getElementById("detailNoteCancelBtn");
const detailReturnToTrendBtn = document.getElementById("detailReturnToTrendBtn");
const detailBullishBtn = document.getElementById("detailBullishBtn");
const detailBearishBtn = document.getElementById("detailBearishBtn");
const detailInlineMarketTags = document.getElementById("detailInlineMarketTags");
const detailMarketPicker = document.getElementById("detailMarketPicker");
const detailMarketPickerTitle = document.getElementById("detailMarketPickerTitle");
const detailMarketPickerOptions = document.getElementById("detailMarketPickerOptions");

let readObserver = null;
let loadObserver = null;
let detailPollTimer = null;
let rowStatusPollTimer = null;
let feedEndAutoReadTimer = null;
let feedEndAutoReadFiredKey = "";
let marketPickerDirection = null;
let lastListScrollTop = 0;
let lastScrollDirectionDown = false;
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
const NOTE_MAX_LEN = 5000;
const DETAIL_CHAT_MAX_LEN = 4000;

function setHint(text) {
  listHint.textContent = text || "";
}

function closeErrorStatsPanel() {
  if (!errorStatsPanel) return;
  errorStatsPanel.classList.add("hidden");
}

function renderErrorStats(days) {
  if (!errorStatsBody) return;
  errorStatsBody.innerHTML = "";
  if (!Array.isArray(days) || !days.length) {
    const empty = document.createElement("p");
    empty.className = "error-stats-empty";
    empty.textContent = "当日暂无 error 记录";
    errorStatsBody.appendChild(empty);
    return;
  }

  days.forEach((day) => {
    const section = document.createElement("section");

    (day.groups || []).forEach((group) => {
      const label = document.createElement("p");
      label.className = "error-stats-group";
      label.textContent = `${day.date} ${group.time}：`;
      section.appendChild(label);

      const times = document.createElement("ul");
      times.className = "error-stats-times";
      (group.labels || []).forEach((labelText) => {
        const li = document.createElement("li");
        li.textContent = labelText;
        times.appendChild(li);
      });
      section.appendChild(times);
    });

    errorStatsBody.appendChild(section);
  });
}

async function openErrorStatsPanel() {
  if (!errorStatsPanel) return;
  if (errorStatsBody) {
    errorStatsBody.innerHTML = '<p class="error-stats-empty">读取中...</p>';
  }
  errorStatsPanel.classList.remove("hidden");
  try {
    const days = await fetchErrorStats();
    renderErrorStats(days);
  } catch {
    if (errorStatsBody) {
      errorStatsBody.innerHTML = '<p class="error-stats-empty">读取 error 统计失败</p>';
    }
  }
}

function showTrendsView(show) {
  trendsView.classList.toggle("hidden", !show);
  newsList.classList.toggle("hidden", !!show);
}

function updateWorkspaceLayout() {
  if (!workspace) return;
  const trendsMode = state.collection === "trends";
  const trendDetailOpen = trendsMode && (!!state.trendSelection || state.tagAdminOpen || state.trendComposeOpen);
  workspace.classList.toggle("trends-mode", trendsMode);
  workspace.classList.toggle("trends-detail-open", trendDetailOpen);
}

function updateSourceFilterVisibility() {
  const visible = state.collection !== "trends" && state.collection !== "search";
  document.querySelectorAll(".sources-title, #sourceFilters").forEach((node) => {
    node.classList.toggle("hidden", !visible);
  });
  if (!visible) closeMobileFilterSheet();
}

async function fetchMarketTrends() {
  const params = new URLSearchParams({ days: String(state.trendDays || 7) });
  const res = await fetch(`/api/market-trends?${params.toString()}`);
  if (!res.ok) throw new Error("market_trends_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_trends_fetch_failed");
  return data;
}

async function fetchMarketTrendDetail(date, tag, direction) {
  const params = new URLSearchParams({ date, tag, direction });
  const res = await fetch(`/api/market-trends/detail?${params.toString()}`);
  if (!res.ok) throw new Error("market_trend_detail_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_trend_detail_fetch_failed");
  return data;
}

async function fetchMarketTrendTagDetail(tag) {
  const params = new URLSearchParams({ tag });
  const res = await fetch(`/api/market-trends/tag-detail?${params.toString()}`);
  if (!res.ok) throw new Error("market_trend_tag_detail_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_trend_tag_detail_fetch_failed");
  return data;
}

async function fetchMarketTagDefinitions() {
  const res = await fetch("/api/market-tags");
  if (!res.ok) throw new Error("market_tags_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tags_fetch_failed");
  state.marketTagChoices = Array.isArray(data.tags) ? data.tags : [];
  return state.marketTagChoices;
}

async function fetchErrorStats() {
  const res = await fetch("/api/error-stats");
  if (!res.ok) throw new Error("error_stats_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "error_stats_fetch_failed");
  return Array.isArray(data.days) ? data.days : [];
}

async function createMarketTagDefinition(displayName) {
  const res = await fetch("/api/market-tags", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!res.ok) throw new Error("market_tag_create_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tag_create_failed");
  return data.tag;
}

async function updateMarketTagDefinition(tagKey, payload) {
  const res = await fetch(`/api/market-tags/${encodeURIComponent(tagKey)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("market_tag_update_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tag_update_failed");
  return data.tag;
}

function clearFeedEndAutoReadTimer() {
  if (!feedEndAutoReadTimer) return;
  window.clearTimeout(feedEndAutoReadTimer);
  feedEndAutoReadTimer = null;
}

function syncSearchPageControls() {
  if (searchPageControls) {
    searchPageControls.classList.toggle("hidden", state.collection !== "search");
  }
  if (searchPageInput) {
    searchPageInput.value = state.q;
  }
  if (searchRangeSelect) {
    searchRangeSelect.value = state.searchRange;
  }
  if (searchTimeSelect) {
    searchTimeSelect.value = state.searchTime;
  }
}

async function runSearchFromPage() {
  const query = (searchPageInput?.value || "").trim();
  state.q = query;
  closeMobileCollectionSheet();
  closeMobileFilterSheet();
  closeErrorStatsPanel();
  await loadFirstPage();
}

function feedEndAutoReadKey() {
  return `${state.collection}|${state.q}|${state.sourceFilter}|${state.readFilter}|${state.total}`;
}

function isListHintVisible() {
  if (!listHint || !newsList) return false;
  const hintRect = listHint.getBoundingClientRect();
  const listRect = newsList.getBoundingClientRect();
  return hintRect.top < listRect.bottom && hintRect.bottom > listRect.top;
}

function currentLoadedRowIds() {
  if (!newsList) return [];
  return Array.from(newsList.querySelectorAll(".news-item"))
    .map((row) => row.dataset.id || "")
    .filter(Boolean);
}

function setDateCounts(dateCounts) {
  state.dateCounts = new Map(Object.entries(dateCounts || {}));
}

function getDateCount(dateKey) {
  if (!dateKey) return null;
  return state.dateCounts.has(dateKey) ? state.dateCounts.get(dateKey) : null;
}

function formatDateCount(dateKey) {
  const value = getDateCount(dateKey);
  if (value == null) return "";
  return `${value} 条`;
}

function updateDateSectionCount(dateKey) {
  if (!dateKey || !newsList) return;
  const selector = `.date-section[data-date-key="${CSS.escape(dateKey)}"] .date-section-count`;
  const countEl = newsList.querySelector(selector);
  if (!countEl) return;
  countEl.textContent = formatDateCount(dateKey);
}

function itemMatchesCurrentDateCountScope(item) {
  if (!item || state.collection === "trends" || state.collection === "search") return false;
  let inCollection = false;
  if (state.collection === "feed") inCollection = true;
  else if (state.collection === "important") inCollection = !!item.important_at;
  else if (state.collection === "read_later") inCollection = !!item.read_later_at;
  else if (state.collection === "notes") inCollection = !!item.has_note;
  else if (state.collection === "market_tags") inCollection = !!item.has_market_tags;
  if (!inCollection) return false;
  if (state.readFilter === "unread") return !item.read_at;
  if (state.readFilter === "read") return !!item.read_at;
  return true;
}

function adjustDateCountForScopeTransition(beforeItem, afterItem) {
  const dateKey = (afterItem && afterItem.date_key) || (beforeItem && beforeItem.date_key) || null;
  if (!dateKey || !state.dateCounts.has(dateKey)) return;
  const wasIncluded = itemMatchesCurrentDateCountScope(beforeItem);
  const isIncluded = itemMatchesCurrentDateCountScope(afterItem);
  if (wasIncluded === isIncluded) return;
  const current = Number(state.dateCounts.get(dateKey) || 0);
  const next = isIncluded ? current + 1 : Math.max(0, current - 1);
  state.dateCounts.set(dateKey, next);
  updateDateSectionCount(dateKey);
}

function markLoadedRowsReadLocally(itemIds = null) {
  const allow = Array.isArray(itemIds) ? new Set(itemIds) : null;
  const now = new Date().toISOString().slice(0, 19).replace("T", " ");
  state.itemsById.forEach((item) => {
    if (allow && !allow.has(String(item.id))) return;
    if (item.read_at) return;
    const beforeItem = { ...item };
    item.read_at = now;
    state.itemsById.set(item.id, item);
    adjustDateCountForScopeTransition(beforeItem, item);
    rerenderOne(item.id);
  });
}

function scheduleFeedEndAutoReadIfNeeded() {
  const canSchedule =
    state.collection === "feed" &&
    !state.hasMore &&
    state.total > 0 &&
    isListHintVisible();

  if (!canSchedule) {
    clearFeedEndAutoReadTimer();
    return;
  }

  const key = feedEndAutoReadKey();
  if (feedEndAutoReadFiredKey === key) {
    clearFeedEndAutoReadTimer();
    return;
  }

  if (feedEndAutoReadTimer) return;

  feedEndAutoReadTimer = window.setTimeout(async () => {
    feedEndAutoReadTimer = null;
    const stillValid =
      state.collection === "feed" &&
      !state.hasMore &&
      state.total > 0 &&
      isListHintVisible();
    if (!stillValid) return;

    const nowKey = feedEndAutoReadKey();
    if (feedEndAutoReadFiredKey === nowKey) return;
    const itemIds = currentLoadedRowIds();
    if (!itemIds.length) return;

    try {
      const res = await fetch("/api/news/mark-read-by-ids", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_ids: itemIds,
        }),
      });
      if (!res.ok) return;
      feedEndAutoReadFiredKey = nowKey;
      markLoadedRowsReadLocally(itemIds);
      setHint("已将当前范围标为已读，列表将在下次刷新后更新");
    } catch {}
  }, 5000);
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

async function fetchRuntimeSettings() {
  const res = await fetch("/api/settings");
  if (!res.ok) throw new Error("settings_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "settings_fetch_failed");
  return data;
}

async function fetchReleaseNotes() {
  const res = await fetch("/api/release-notes");
  if (!res.ok) throw new Error("release_notes_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "release_notes_fetch_failed");
  return Array.isArray(data.items) ? data.items : [];
}

function currentChatDefaultProvider() {
  const provider = state.runtimeSettings?.llm?.chat?.default_provider;
  return provider === "openai" ? "openai" : "deepseek";
}

function renderSettingsApiStatus() {
  if (!settingsApiStatus) return;
  settingsApiStatus.innerHTML = "";
  const apiStatus = state.runtimeSettings?.api_status || {};
  [
    ["deepseek", "DeepSeek"],
    ["openai", "ChatGPT"],
  ].forEach(([key, label]) => {
    const row = document.createElement("div");
    row.className = "settings-api-item";
    const name = document.createElement("div");
    name.className = "settings-api-name";
    name.textContent = label;
    const badge = document.createElement("span");
    const configured = !!apiStatus[key]?.configured;
    badge.className = `settings-api-badge ${configured ? "ok" : "muted"}`;
    badge.textContent = configured ? "已配置" : "未配置";
    row.appendChild(name);
    row.appendChild(badge);
    settingsApiStatus.appendChild(row);
  });
}

function renderReleaseNotes() {
  if (!settingsReleaseNotes) return;
  settingsReleaseNotes.innerHTML = "";
  if (!state.releaseNotes.length) {
    const empty = document.createElement("div");
    empty.className = "detail-status muted";
    empty.textContent = "暂时没有可展示的 Release Notes";
    settingsReleaseNotes.appendChild(empty);
    return;
  }
  state.releaseNotes.forEach((item) => {
    const card = document.createElement("article");
    card.className = "settings-release-item";
    const top = document.createElement("div");
    top.className = "settings-release-top";
    const head = document.createElement("div");
    const version = document.createElement("div");
    version.className = "settings-release-version";
    version.textContent = item.version || item.date || "未命名版本";
    const title = document.createElement("div");
    title.className = "settings-release-title";
    title.textContent = item.title || "";
    head.appendChild(version);
    head.appendChild(title);
    const meta = document.createElement("div");
    meta.className = "settings-release-meta";
    const badge = document.createElement("span");
    const category = (item.category || "IMPROVE").toUpperCase();
    badge.className = `settings-release-badge ${category.toLowerCase()}`;
    badge.textContent = category;
    const date = document.createElement("span");
    date.className = "settings-release-date";
    date.textContent = item.date || "";
    meta.appendChild(badge);
    meta.appendChild(date);
    top.appendChild(head);
    top.appendChild(meta);
    card.appendChild(top);

    const list = document.createElement("ul");
    list.className = "settings-release-lines";
    (item.lines || []).slice(0, 12).forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      list.appendChild(li);
    });
    card.appendChild(list);
    settingsReleaseNotes.appendChild(card);
  });
}

function populateSettingsForm() {
  const llm = state.runtimeSettings?.llm;
  if (!llm) return;
  settingsTranslationProvider.value = llm.translation?.provider || "deepseek";
  settingsTranslationModel.value = llm.translation?.model || "";
  settingsChatDefaultProvider.value = llm.chat?.default_provider || "deepseek";
  settingsChatDeepseekModel.value = llm.chat?.providers?.deepseek?.model || "";
  settingsChatOpenaiModel.value = llm.chat?.providers?.openai?.model || "";
  settingsRestartHint.textContent = state.runtimeSettings?.restart_notice || "";
}

function renderSettingsOverlay() {
  if (!settingsOverlay) return;
  settingsOverlay.classList.toggle("hidden", !state.settingsOpen);
  settingsOverlay.setAttribute("aria-hidden", state.settingsOpen ? "false" : "true");
  if (!state.settingsOpen) return;
  renderSettingsApiStatus();
  renderReleaseNotes();
  populateSettingsForm();
  settingsSaveBtn.disabled = state.settingsSaving;
  const statusText = state.settingsLoading
    ? "读取中..."
    : state.settingsSaving
      ? "保存中..."
      : state.settingsMessage || "设置保存到本机配置文件；API key 只展示是否已配置，不回显明文。";
  const tone = state.settingsLoading || state.settingsSaving ? "pending" : (state.settingsMessageTone || "muted");
  settingsStatus.textContent = statusText;
  settingsStatus.className = `detail-status ${tone}`;
}

async function openSettingsOverlay() {
  state.settingsOpen = true;
  state.settingsLoading = true;
  state.settingsMessage = "";
  state.settingsMessageTone = "muted";
  renderSettingsOverlay();
  closeErrorStatsPanel();
  try {
    const [runtimeSettings, releaseNotes] = await Promise.all([fetchRuntimeSettings(), fetchReleaseNotes()]);
    state.runtimeSettings = runtimeSettings;
    state.releaseNotes = releaseNotes;
    state.detailChatProvider = currentChatDefaultProvider();
  } catch {
    state.settingsMessage = "读取设置失败，请稍后重试。";
    state.settingsMessageTone = "failed";
  } finally {
    state.settingsLoading = false;
    renderSettingsOverlay();
  }
}

function closeSettingsOverlay() {
  state.settingsOpen = false;
  renderSettingsOverlay();
}

async function saveRuntimeSettings() {
  state.settingsSaving = true;
  renderSettingsOverlay();
  try {
    const payload = {
      llm: {
        translation: {
          provider: settingsTranslationProvider.value || "deepseek",
          model: (settingsTranslationModel.value || "").trim(),
        },
        chat: {
          default_provider: settingsChatDefaultProvider.value || "deepseek",
          providers: {
            deepseek: { model: (settingsChatDeepseekModel.value || "").trim() },
            openai: { model: (settingsChatOpenaiModel.value || "").trim() },
          },
        },
      },
    };
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "settings_save_failed");
    state.runtimeSettings = data;
    state.detailChatProvider = currentChatDefaultProvider();
    state.settingsMessage = "保存成功。新请求通常立即生效；如需与 worker 完全一致，可重启 Flask。";
    state.settingsMessageTone = "ready";
  } catch {
    state.settingsMessage = "保存失败，请检查输入后重试。";
    state.settingsMessageTone = "failed";
  } finally {
    state.settingsSaving = false;
    renderSettingsOverlay();
  }
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
  if (name === "pen") {
    return `<svg ${common}><path d="m4 20 4.1-1 9.3-9.3a1.7 1.7 0 0 0 0-2.4l-.7-.7a1.7 1.7 0 0 0-2.4 0L5 15.9 4 20Z"/><path d="m12.9 7.1 4 4"/></svg>`;
  }
  if (name === "trend-up") {
    return `<svg ${common}><path d="M4.5 15.5 9.2 10.8l3.2 3.2 6.8-6.8"/><path d="M15.6 7.2h3.6v3.6"/></svg>`;
  }
  if (name === "trend-down") {
    return `<svg ${common}><path d="M4.5 8.5 9.2 13.2l3.2-3.2 6.8 6.8"/><path d="M15.6 16.8h3.6v-3.6"/></svg>`;
  }
  if (name === "bell") {
    return `<svg ${common}><path d="M6.5 10.2a5.5 5.5 0 1 1 11 0c0 5 2 5.8 2 7.3H4.5c0-1.5 2-2.3 2-7.3"/><path d="M10 19.3a2.2 2.2 0 0 0 4 0"/></svg>`;
  }
  if (name === "settings") {
    return `<svg ${common}><circle cx="12" cy="12" r="3.2"/><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a1.9 1.9 0 0 1-2.7 2.7l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a1.9 1.9 0 1 1-3.8 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a1.9 1.9 0 1 1-2.7-2.7l.1-.1A1 1 0 0 0 6 15a1 1 0 0 0-.9-.6H5a1.9 1.9 0 1 1 0-3.8h.2A1 1 0 0 0 6 10a1 1 0 0 0-.2-1.1l-.1-.1a1.9 1.9 0 1 1 2.7-2.7l.1.1A1 1 0 0 0 9.6 6a1 1 0 0 0 .6-.9V5a1.9 1.9 0 1 1 3.8 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a1.9 1.9 0 1 1 2.7 2.7l-.1.1A1 1 0 0 0 18 10a1 1 0 0 0 .9.6h.2a1.9 1.9 0 1 1 0 3.8h-.2a1 1 0 0 0-.9.6Z"/></svg>`;
  }
  if (name === "search") {
    return `<svg ${common}><circle cx="11" cy="11" r="5.8"/><path d="m16 16 4 4"/></svg>`;
  }
  if (name === "close") {
    return `<svg ${common}><path d="M6 6 18 18"/><path d="M18 6 6 18"/></svg>`;
  }
  if (name === "help") {
    return `<svg ${common}><path d="M9.4 9.2a2.8 2.8 0 1 1 4.8 2c-.7.7-1.5 1.1-1.9 1.7-.3.4-.4.8-.4 1.6"/><circle cx="12" cy="17.2" r="0.9" fill="currentColor" stroke="none"/></svg>`;
  }
  return `<svg ${common}><circle cx="12" cy="12" r="7.5"/></svg>`;
}

function applyIcon(btn, iconName, { filled = false, label = "", tone = "default" } = {}) {
  btn.innerHTML = `<span class="glyph">${iconSvg(iconName, filled)}</span>`;
  btn.classList.remove("tone-default", "tone-muted", "tone-danger", "tone-warning", "tone-success", "tone-accent");
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
  const noteBadge = li.querySelector(".note-badge");
  if (noteBadge) {
    const hasNote = Number(item.has_note || 0) === 1;
    noteBadge.classList.toggle("hidden", !hasNote);
  }
  const notePreview = li.querySelector(".row-note-preview");
  if (notePreview) {
    const previewText = typeof item.note_preview === "string" ? item.note_preview.trim() : "";
    notePreview.textContent = previewText;
    notePreview.classList.toggle("hidden", !previewText);
  }
  const marketTagsWrap = li.querySelector(".market-tags");
  const titleEl = li.querySelector(".title");
  if (marketTagsWrap) {
    marketTagsWrap.innerHTML = "";
    const tags = marketTagsFromItem(item);
    tags.forEach((mt) => {
      const badge = document.createElement("span");
      badge.className = `market-tag-badge ${mt.direction}`;
      badge.textContent = mt.tag;
      marketTagsWrap.appendChild(badge);
    });
    marketTagsWrap.classList.toggle("hidden", tags.length === 0);
  }

  if (titleEl) {
    titleEl.classList.remove("tone-important", "tone-bullish", "tone-bearish", "tone-mixed");
    const tags = marketTagsFromItem(item);
    const hasBullish = tags.some((mt) => mt.direction === "bullish");
    const hasBearish = tags.some((mt) => mt.direction === "bearish");
    if (hasBullish && hasBearish) {
      titleEl.classList.add("tone-mixed");
    } else if (hasBullish) {
      titleEl.classList.add("tone-bullish");
    } else if (hasBearish) {
      titleEl.classList.add("tone-bearish");
    } else if (item.important_at) {
      titleEl.classList.add("tone-important");
    }
  }

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
  if (
    state.collection === "search" ||
    state.collection === "important" ||
    state.collection === "notes" ||
    state.collection === "market_tags" ||
    state.collection === "trends"
  ) {
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
  if (navSearchBtn) navSearchBtn.classList.toggle("active", state.collection === "search");
  navFeedBtn.classList.toggle("active", state.collection === "feed");
  navImportantBtn.classList.toggle("active", state.collection === "important");
  navReadLaterBtn.classList.toggle("active", state.collection === "read_later");
  if (navNotesBtn) navNotesBtn.classList.toggle("active", state.collection === "notes");
  if (navMarketTagsBtn) navMarketTagsBtn.classList.toggle("active", state.collection === "market_tags");
  if (navTrendsBtn) navTrendsBtn.classList.toggle("active", state.collection === "trends");
  if (mobileCollectionTriggerBtn) {
    mobileCollectionTriggerBtn.classList.toggle("active", state.collection !== "trends");
    const names = {
      search: "搜索",
      feed: "新闻流",
      important: "重要",
      read_later: "稍后",
      notes: "想法",
      market_tags: "板块",
      trends: "趋势",
    };
    const remembered = names[state.lastNewsCollectionBeforeTrends] || "新闻流";
    mobileCollectionTriggerBtn.textContent = state.collection === "trends"
      ? remembered
      : (names[state.collection] || "新闻流");
  }
  if (mobileTrendsTabBtn) {
    mobileTrendsTabBtn.classList.toggle("active", state.collection === "trends");
  }
  if (mobileTabFilterBtn) {
    mobileTabFilterBtn.classList.toggle("hidden", state.collection === "search");
  }
  if (manageMarketTagsBtn) {
    manageMarketTagsBtn.classList.toggle("hidden", state.collection !== "trends");
    if (state.collection === "trends") {
      applyIcon(manageMarketTagsBtn, "pen", {
        tone: state.tagAdminOpen ? "accent" : "default",
        label: "管理板块",
      });
    }
  }
}

function updateMobileFilterCollectionText() {
  if (!mobileFilterCollection) return;
  const names = {
    search: "搜索",
    feed: "新闻流",
    important: "重要新闻",
    read_later: "稍后再看",
    notes: "想法",
    market_tags: "板块",
    trends: "趋势",
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
    { key: "search", label: "搜索" },
    { key: "feed", label: "新闻流" },
    { key: "important", label: "重要" },
    { key: "read_later", label: "稍后阅读" },
    { key: "notes", label: "想法" },
    { key: "market_tags", label: "板块" },
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
  if (!mobileFilterSheet || state.collection === "search") return;
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
    q: "",
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
  if (state.collection === "search") {
    const rangeNames = {
      all: "全部新闻",
      important: "重要",
      notes: "有想法",
      market_tags: "有板块",
      detail_ready: "已抓取正文",
    };
    const timeNames = {
      all: "全部时间",
      today: "今天",
      "7d": "7 天内",
      "30d": "30 天内",
    };
    if (!state.q) {
      meta.textContent = `搜索 · ${rangeNames[state.searchRange]} · ${timeNames[state.searchTime]}`;
    } else {
      meta.textContent = `搜索 · “${state.q}” · ${rangeNames[state.searchRange]} · ${timeNames[state.searchTime]} · 共 ${state.total} 条`;
    }
    pageInfo.textContent = `${state.page} / ${state.pages}`;
    return;
  }
  const names = {
    feed: "新闻流",
    important: "重要新闻",
    read_later: "稍后再看",
    notes: "想法",
    market_tags: "板块",
    trends: "趋势",
  };
  if (state.collection === "trends") {
    meta.textContent = `趋势 · 近 ${state.trendDays} 天 · ${state.trendRows.length} 个板块 · ${state.total} 条标记`;
    pageInfo.textContent = "- / -";
    return;
  }
  const readNames = {
    all: "全部",
    unread: "仅未读",
  };
  const readFilterName = state.collection === "feed" ? readNames[state.readFilter] : readNames.all;
  const sourceName = state.sourceFilter === "all" ? "全部来源" : sourceLabel(state.sourceFilter);
  meta.textContent = `${names[state.collection]} · ${readFilterName} · ${sourceName} · 共 ${state.total} 条`;
  pageInfo.textContent = `${state.page} / ${state.pages}`;
}

function activeMarketTagChoices() {
  return state.marketTagChoices.filter((tag) => Number(tag.active || 0) === 1);
}

function closeTrendComposerView() {
  state.trendComposeOpen = false;
  if (detailTrendComposerBody) {
    detailTrendComposerBody.classList.add("hidden");
  }
}

function closeTrendNoteEditor() {
  state.trendNoteContext = null;
  if (detailTrendNoteEditor) {
    detailTrendNoteEditor.dataset.key = "";
    detailTrendNoteEditor.classList.add("hidden");
  }
  if (detailTrendNoteDeleteBtn) {
    detailTrendNoteDeleteBtn.classList.add("hidden");
  }
}

function currentTrendSelectionBase() {
  if (!state.trendSelection) return null;
  return {
    date: state.trendSelection.date,
    tagKey: state.trendSelection.tagKey,
    tagLabel: state.trendSelection.tagLabel,
  };
}

async function saveTrendNote(payload) {
  const body = {
    date_key: payload.date,
    tag_key: payload.tag,
    direction: payload.direction,
    note: payload.note,
  };
  const res = await fetch("/api/market-trends/note", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("trend_note_save_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "trend_note_save_failed");
  return data;
}

async function updateTrendNote(noteId, note) {
  const res = await fetch(`/api/market-trends/note/${encodeURIComponent(noteId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error("trend_note_update_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "trend_note_update_failed");
  return data;
}

async function deleteTrendNote(noteId) {
  const res = await fetch(`/api/market-trends/note/${encodeURIComponent(noteId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("trend_note_delete_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "trend_note_delete_failed");
  return data;
}

function renderTrendComposeOptions() {
  if (!trendNoteDateSelect || !trendNoteTagSelect) return;
  trendNoteDateSelect.innerHTML = "";
  state.trendDates.forEach((date) => {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = date;
    trendNoteDateSelect.appendChild(option);
  });
  trendNoteTagSelect.innerHTML = "";
  activeMarketTagChoices().forEach((tag) => {
    const option = document.createElement("option");
    option.value = tag.key;
    option.textContent = tag.display_name;
    trendNoteTagSelect.appendChild(option);
  });
}

function openTrendComposeView(prefill = null) {
  const base = prefill || currentTrendSelectionBase();
  closeTagAdminView();
  closeTrendNoteEditor();
  detailBody.classList.add("hidden");
  detailTrendBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  detailTrendComposerBody.classList.remove("hidden");
  state.trendComposeOpen = true;
  renderTrendComposeOptions();
  if (state.trendDates.length) {
    trendNoteDateSelect.value = state.trendDates[state.trendDates.length - 1];
  }
  if (base) {
    trendNoteDateSelect.value = base.date;
    trendNoteTagSelect.value = base.tagKey;
  }
  trendNoteComposeInput.value = "";
  if (trendNoteComposeDeleteBtn) trendNoteComposeDeleteBtn.classList.add("hidden");
  updateWorkspaceLayout();
  openDetailOnMobile();
}

function openTrendNoteEditor(input) {
  const editingNote = typeof input === "object" && input ? input : null;
  const direction = editingNote ? editingNote.direction : input;
  const base = editingNote
    ? {
        date: editingNote.date_key,
        tagKey: editingNote.tag_key,
        tagLabel: editingNote.tag,
      }
    : currentTrendSelectionBase();
  if (!base) return;
  const nextNoteId = editingNote?.id || "";
  const sameKey = `${base.date}|${base.tagKey}|${direction}|${nextNoteId || "new"}`;
  if (detailTrendNoteEditor.dataset.key === sameKey && !detailTrendNoteEditor.classList.contains("hidden")) {
    closeTrendNoteEditor();
    return;
  }
  state.trendNoteContext = {
    ...base,
    direction,
    noteId: editingNote?.id || null,
    mode: editingNote ? "edit" : "create",
  };
  detailTrendNoteEditor.dataset.key = sameKey;
  detailTrendNoteEditorMeta.textContent = `${base.date} · ${base.tagLabel} · ${direction === "bullish" ? "看多" : "看空"} · ${editingNote ? "编辑想法" : "新建想法"}`;
  detailTrendNoteInput.value = editingNote?.note || "";
  detailTrendNoteDeleteBtn.classList.toggle("hidden", !editingNote);
  detailTrendNoteEditor.classList.remove("hidden");
}

function closeTagAdminView() {
  state.tagAdminOpen = false;
  if (detailTagAdminBody) {
    detailTagAdminBody.classList.add("hidden");
  }
}

function renderTagAdminList() {
  if (!detailTagAdminList) return;
  detailTagAdminList.innerHTML = "";
  state.marketTagChoices.forEach((tag) => {
    const row = document.createElement("div");
    row.className = "detail-tag-admin-row";

    const input = document.createElement("input");
    input.type = "text";
    input.className = "detail-tag-admin-input";
    input.value = tag.display_name || tag.key;
    input.maxLength = 40;

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "detail-retry-btn";
    saveBtn.textContent = "保存";
    saveBtn.addEventListener("click", async () => {
      const nextName = input.value.trim();
      if (!nextName || nextName === tag.display_name) return;
      saveBtn.disabled = true;
      try {
        await updateMarketTagDefinition(tag.key, { display_name: nextName });
        await refreshTrendTagAdminState();
      } finally {
        saveBtn.disabled = false;
      }
    });

    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "detail-retry-btn";
    toggleBtn.textContent = Number(tag.active || 0) === 1 ? "停用" : "启用";
    toggleBtn.addEventListener("click", async () => {
      toggleBtn.disabled = true;
      try {
        await updateMarketTagDefinition(tag.key, { active: Number(tag.active || 0) !== 1 });
        await refreshTrendTagAdminState();
      } finally {
        toggleBtn.disabled = false;
      }
    });

    const metaText = document.createElement("span");
    metaText.className = "detail-tag-admin-meta";
    metaText.textContent = Number(tag.active || 0) === 1 ? "启用中" : "已停用";

    row.appendChild(input);
    row.appendChild(saveBtn);
    row.appendChild(toggleBtn);
    row.appendChild(metaText);
    detailTagAdminList.appendChild(row);
  });
}

async function refreshTrendTagAdminState() {
  await fetchMarketTagDefinitions();
  if (state.collection === "trends") {
    const data = await fetchMarketTrends();
    state.total = Number(data.tagged_item_count || 0);
    state.trendDates = Array.isArray(data.dates) ? data.dates : [];
    state.trendRows = Array.isArray(data.rows) ? data.rows : [];
    const activeKeys = new Set(state.trendRows.map((row) => row.tag_key || row.tag));
    if (state.trendSelection && !activeKeys.has(state.trendSelection.tagKey)) {
      state.trendSelection = null;
      renderTrendDetail(null);
    }
    renderTrendsView();
    renderMeta();
  }
  renderTagAdminList();
}

async function refreshTrendSelectionAfterMutation(nextSelection = state.trendSelection) {
  if (state.collection !== "trends") return;
  const data = await fetchMarketTrends();
  state.total = Number(data.tagged_item_count || 0);
  state.trendDates = Array.isArray(data.dates) ? data.dates : [];
  state.trendRows = Array.isArray(data.rows) ? data.rows : [];

  if (!nextSelection) {
    state.trendSelection = null;
    renderTrendsView();
    renderTrendDetail(null);
    renderMeta();
    return;
  }

  const activeKeys = new Set(state.trendRows.map((row) => row.tag_key || row.tag));
  if (!activeKeys.has(nextSelection.tagKey)) {
    state.trendSelection = null;
    renderTrendsView();
    renderTrendDetail(null);
    renderMeta();
    return;
  }

  let payload = null;
  if (nextSelection.kind === "tag") {
    payload = await fetchMarketTrendTagDetail(nextSelection.tagKey);
  } else {
    payload = await fetchMarketTrendDetail(nextSelection.date, nextSelection.tagKey, nextSelection.direction);
    if (!payload.total && !payload.trend_note_total) {
      state.trendSelection = null;
      renderTrendsView();
      renderTrendDetail(null);
      renderMeta();
      return;
    }
  }

  state.trendSelection = {
    ...nextSelection,
    tagLabel: payload.tag,
    detailPayload: payload,
  };
  renderTrendsView();
  renderTrendDetail(payload);
  renderMeta();
}

async function openTagAdminView() {
  state.tagAdminOpen = true;
  closeTrendComposerView();
  closeTrendNoteEditor();
  state.trendSelection = null;
  closeMarketPicker();
  detailBody.classList.add("hidden");
  detailTrendBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  await refreshTrendTagAdminState();
  detailTagAdminBody.classList.remove("hidden");
  updateWorkspaceLayout();
  openDetailOnMobile();
}

function renderTrendDetail(payload) {
  closeTagAdminView();
  closeTrendComposerView();
  closeTrendNoteEditor();
  state.detailReturnToTrend = false;
  syncDetailReturnButton();
  detailBody.classList.add("hidden");
  if (!payload) {
    detailTrendBody.classList.add("hidden");
    detailTrendNoteCard.classList.add("hidden");
    detailTrendList.innerHTML = "";
    detailEmpty.classList.remove("hidden");
    detailEmpty.textContent = state.collection === "trends" ? "选择一个趋势单元格查看新闻明细" : "选择一条新闻查看摘要与正文";
    updateWorkspaceLayout();
    return;
  }

  detailEmpty.classList.add("hidden");
  detailTrendComposerBody.classList.add("hidden");
  detailTrendBody.classList.remove("hidden");
  const isTagOverview = payload.view === "tag";
  trendComposeBtn.classList.toggle("hidden", false);
  trendBullishNoteBtn.classList.toggle("hidden", isTagOverview);
  trendBearishNoteBtn.classList.toggle("hidden", isTagOverview);
  if (isTagOverview) {
    detailTrendTitle.textContent = `${payload.tag} · 板块总览`;
    detailTrendMeta.textContent = `${payload.item_total || 0} 条新闻 · ${payload.trend_note_total || 0} 条趋势想法`;
    detailTrendNoteCard.classList.add("hidden");
  } else {
    detailTrendTitle.textContent = `${payload.tag} · ${payload.direction === "bullish" ? "看多" : "看空"}`;
    detailTrendMeta.textContent = `${payload.date} · ${payload.total || 0} 条新闻 · ${payload.trend_note_total || 0} 条趋势想法`;
    detailTrendNoteCard.classList.add("hidden");
  }
  detailTrendList.innerHTML = "";
  if (isTagOverview) {
    renderTrendTagOverview(payload);
  } else {
    (payload.trend_notes || []).forEach((note) => {
      detailTrendList.appendChild(buildTrendNoteCard(note));
    });
    (payload.items || []).forEach((item) => {
      detailTrendList.appendChild(buildTrendNewsCard(item, payload));
    });
  }
  updateWorkspaceLayout();
}

function buildTrendNewsCard(item, trendContext = null) {
  const card = document.createElement("article");
  card.className = "trend-detail-card trend-detail-card-clickable";

  const header = document.createElement("div");
  header.className = "trend-detail-card-header";

  const title = document.createElement("h4");
  title.className = "trend-detail-title";
  const titleBtn = document.createElement("button");
  titleBtn.type = "button";
  titleBtn.className = "trend-detail-open-btn";
  titleBtn.textContent = item.title || "未命名新闻";
  title.appendChild(titleBtn);
  header.appendChild(title);

  if (item.url) {
    const actions = document.createElement("div");
    actions.className = "trend-detail-inline-actions";
    const sourceLink = document.createElement("a");
    sourceLink.href = item.url;
    sourceLink.target = "_blank";
    sourceLink.rel = "noopener noreferrer";
    sourceLink.className = "trend-detail-inline-link";
    sourceLink.textContent = "原文";
    sourceLink.addEventListener("click", (event) => event.stopPropagation());
    actions.appendChild(sourceLink);
    header.appendChild(actions);
  }

  const directionLabel = item.direction === "bullish" ? "看多" : item.direction === "bearish" ? "看空" : "";
  const metaLine = document.createElement("div");
  metaLine.className = "trend-detail-meta";
  metaLine.textContent = `${directionLabel ? `${directionLabel} · ` : ""}${item.source || "未知来源"} · ${item.published_at || item.date_key || ""}`;

  const summary = document.createElement("p");
  summary.className = "trend-detail-summary";
  const summaryText = typeof item.summary === "string" ? item.summary.trim() : "";
  summary.textContent = summaryText;
  summary.classList.toggle("hidden", !summaryText);

  const notePreviewText = typeof item.note_preview === "string"
    ? item.note_preview.trim()
    : (typeof item.note?.note === "string" ? item.note.note.trim() : "");
  const notePreview = document.createElement("p");
  notePreview.className = "trend-detail-note-preview hidden";
  notePreview.textContent = notePreviewText;
  notePreview.classList.toggle("hidden", !notePreviewText);

  const openDetail = () => openItemDetail(item, { fromTrend: true });
  card.addEventListener("click", openDetail);
  card.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    openDetail();
  });
  card.tabIndex = 0;
  titleBtn.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openDetail();
  });

  card.appendChild(header);
  card.appendChild(metaLine);
  card.appendChild(summary);
  card.appendChild(notePreview);

  if (Array.isArray(item.market_tags) && item.market_tags.length) {
    const tags = document.createElement("div");
    tags.className = "trend-detail-tags";
    item.market_tags.forEach((tag) => {
      const chip = document.createElement("span");
      chip.className = `trend-detail-tag ${tag.direction}`;

      const label = document.createElement("span");
      label.textContent = tag.tag;
      chip.appendChild(label);

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "trend-detail-tag-remove";
      removeBtn.textContent = "×";
      removeBtn.title = `移除${tag.tag}`;
      removeBtn.setAttribute("aria-label", `移除${tag.tag}`);
      removeBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        removeBtn.disabled = true;
        try {
          await deleteMarketTag(item, tag.key || tag.tag);
          await refreshTrendSelectionAfterMutation(state.trendSelection);
        } finally {
          removeBtn.disabled = false;
        }
      });
      chip.appendChild(removeBtn);

      tags.appendChild(chip);
    });
    card.appendChild(tags);
  }

  return card;
}

function buildTrendNoteCard(note) {
  const card = document.createElement("article");
  card.className = "trend-detail-card trend-detail-note-card";

  const header = document.createElement("div");
  header.className = "trend-detail-card-header";

  const title = document.createElement("h4");
  title.className = "trend-detail-title";
  title.textContent = `${note.direction === "bullish" ? "看多" : "看空"}想法`;
  header.appendChild(title);

  const actions = document.createElement("div");
  actions.className = "trend-detail-inline-actions";

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "trend-detail-inline-btn";
  editBtn.textContent = "编辑";
  editBtn.addEventListener("click", () => openTrendNoteEditor(note));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "trend-detail-inline-btn danger";
  deleteBtn.textContent = "删除";
  deleteBtn.addEventListener("click", async () => {
    deleteBtn.disabled = true;
    try {
      await deleteTrendNote(note.id);
      await refreshTrendSelectionAfterMutation(state.trendSelection);
      closeTrendNoteEditor();
    } finally {
      deleteBtn.disabled = false;
    }
  });

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);
  header.appendChild(actions);

  const metaLine = document.createElement("div");
  metaLine.className = "trend-detail-meta";
  metaLine.textContent = `${note.updated_at || note.date_key || ""}`;

  const noteBody = document.createElement("div");
  noteBody.className = "trend-detail-note";
  noteBody.textContent = note.note || "";

  card.appendChild(header);
  card.appendChild(metaLine);
  card.appendChild(noteBody);
  return card;
}

function renderTrendTagOverview(payload) {
  const grouped = new Map();
  (payload.trend_notes || []).forEach((note) => {
    const date = note.date_key || "unknown";
    if (!grouped.has(date)) grouped.set(date, { notes: [], items: [] });
    grouped.get(date).notes.push(note);
  });
  (payload.items || []).forEach((item) => {
    const date = item.date_key || "unknown";
    if (!grouped.has(date)) grouped.set(date, { notes: [], items: [] });
    grouped.get(date).items.push(item);
  });
  const dates = Array.from(grouped.keys()).sort((a, b) => b.localeCompare(a));
  dates.forEach((date) => {
    const section = document.createElement("section");
    section.className = "trend-overview-section";

    const heading = document.createElement("h4");
    heading.className = "trend-overview-date";
    heading.textContent = date;
    section.appendChild(heading);

    const bucket = grouped.get(date);
    bucket.notes.forEach((note) => {
      section.appendChild(buildTrendNoteCard(note));
    });
    bucket.items.forEach((item) => {
      section.appendChild(buildTrendNewsCard(item, payload));
    });
    detailTrendList.appendChild(section);
  });
}

function renderTrendsView() {
  trendsTable.innerHTML = "";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const headDate = document.createElement("th");
  headDate.textContent = "日期";
  headRow.appendChild(headDate);
  state.trendRows.forEach((row) => {
    const th = document.createElement("th");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "trend-header-btn";
    btn.textContent = row.tag_label || row.tag;
    if (
      state.trendSelection &&
      state.trendSelection.kind === "tag" &&
      state.trendSelection.tagKey === (row.tag_key || row.tag)
    ) {
      btn.classList.add("active");
    }
    btn.addEventListener("click", async () => {
      const tagKey = row.tag_key || row.tag;
      if (
        state.trendSelection &&
        state.trendSelection.kind === "tag" &&
        state.trendSelection.tagKey === tagKey
      ) {
        state.trendSelection = null;
        renderTrendsView();
        renderTrendDetail(null);
        return;
      }
      const payload = await fetchMarketTrendTagDetail(tagKey);
      state.trendSelection = {
        kind: "tag",
        key: `tag|${tagKey}`,
        tagKey,
        tagLabel: row.tag_label || row.tag,
        detailPayload: payload,
      };
      renderTrendsView();
      renderTrendDetail(payload);
      openDetailOnMobile();
    });
    th.appendChild(btn);
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  trendsTable.appendChild(thead);

  const tbody = document.createElement("tbody");
  const rowMap = new Map(state.trendRows.map((row) => [row.tag_key || row.tag, row]));
  state.trendDates.forEach((date) => {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = date;
    tr.appendChild(th);

    state.trendRows.forEach((row) => {
      const tagKey = row.tag_key || row.tag;
      const value = rowMap.get(tagKey)?.values.find((entry) => entry.date === date) || {
        date,
        bullish: 0,
        bearish: 0,
      };
      const td = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "trends-cell";
      const activeKey = `${tagKey}|${date}`;

      if (!value.bullish && !value.bearish) {
        if (value.bullish_notes || value.bearish_notes) {
          wrap.classList.add("split");
        } else {
          wrap.classList.add("empty");
          wrap.textContent = "-";
          wrap.addEventListener("click", () => {
            openTrendComposeView({
              date,
              tagKey,
              tagLabel: row.tag_label || row.tag,
            });
          });
        }
      } else {
        if (value.bullish && value.bearish) {
          wrap.classList.add("split");
        }
        if (!value.bullish && value.bullish_notes && !wrap.classList.contains("split")) {
          wrap.classList.add("split");
        }
        if (!value.bearish && value.bearish_notes && !wrap.classList.contains("split")) {
          wrap.classList.add("split");
        }
      }
      if (value.bullish || value.bullish_notes) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "trend-chip-btn bullish";
        if (value.bullish_has_item_note || value.bullish_notes) btn.classList.add("with-item-note");
        if (
          state.trendSelection &&
          state.trendSelection.key === activeKey &&
          state.trendSelection.direction === "bullish"
        ) {
          btn.classList.add("active");
        }
        btn.innerHTML =
          `<span class="trend-chip-label">看多</span>+${value.bullish || 0}` +
          (value.bullish_notes ? `<span class="trend-chip-note">想法 ${value.bullish_notes}</span>` : "");
        btn.addEventListener("click", async () => {
          const payload = await fetchMarketTrendDetail(date, tagKey, "bullish");
          state.trendSelection = {
            kind: "cell",
            key: activeKey,
            tagKey,
            tagLabel: row.tag_label || row.tag,
            date,
            direction: "bullish",
            detailPayload: payload,
          };
          renderTrendsView();
          renderTrendDetail(payload);
          openDetailOnMobile();
        });
        wrap.appendChild(btn);
      }
      if (value.bearish || value.bearish_notes) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "trend-chip-btn bearish";
        if (value.bearish_has_item_note || value.bearish_notes) btn.classList.add("with-item-note");
        if (
          state.trendSelection &&
          state.trendSelection.key === activeKey &&
          state.trendSelection.direction === "bearish"
        ) {
          btn.classList.add("active");
        }
        btn.innerHTML =
          `<span class="trend-chip-label">看空</span>+${value.bearish || 0}` +
          (value.bearish_notes ? `<span class="trend-chip-note">想法 ${value.bearish_notes}</span>` : "");
        btn.addEventListener("click", async () => {
          const payload = await fetchMarketTrendDetail(date, tagKey, "bearish");
          state.trendSelection = {
            kind: "cell",
            key: activeKey,
            tagKey,
            tagLabel: row.tag_label || row.tag,
            date,
            direction: "bearish",
            detailPayload: payload,
          };
          renderTrendsView();
          renderTrendDetail(payload);
          openDetailOnMobile();
        });
        wrap.appendChild(btn);
      }
      td.appendChild(wrap);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  trendsTable.appendChild(tbody);
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
    date_key: item.date_key,
    read_at: item.read_at,
    important_at: item.important_at,
    read_later_at: item.read_later_at,
    has_note: item.has_note,
    has_market_tags: item.has_market_tags,
  };

  const now = new Date().toISOString().slice(0, 19).replace("T", " ");
  const beforeItem = { ...backup };
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
  adjustDateCountForScopeTransition(beforeItem, item);
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
    adjustDateCountForScopeTransition(item, backup);
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

function setDetailNoteEditorOpen(open) {
  if (open) closeMarketPicker();
  detailNoteEditor.classList.toggle("hidden", !open);
}

function canReturnToTrendDetail() {
  return !!(state.detailReturnToTrend && state.trendSelection?.detailPayload);
}

function syncDetailReturnButton() {
  if (!detailReturnToTrendBtn) return;
  detailReturnToTrendBtn.classList.toggle("hidden", !canReturnToTrendDetail());
}

function restoreTrendDetailFromDetail() {
  if (!canReturnToTrendDetail()) return;
  state.selectedId = null;
  state.detailReturnToTrend = false;
  stopDetailPolling();
  renderTrendDetail(state.trendSelection.detailPayload);
  openDetailOnMobile();
}

function openItemDetail(item, { fromTrend = false } = {}) {
  if (!item) return;
  if (state.selectedId !== item.id) resetDetailChatState();
  state.itemsById.set(item.id, item);
  state.selectedId = item.id;
  state.detailReturnToTrend = fromTrend;
  renderDetail(state.itemsById.get(item.id) || item);
  loadDetail(item.id);
  startDetailPolling(item.id);
  if (!fromTrend) saveReadingCheckpoint(item).catch(() => {});
  openDetailOnMobile();
}

function normalizedDetailNote(cached) {
  const text = cached?.note?.note;
  return typeof text === "string" ? text.trim() : "";
}

function resetDetailChatState({ keepProvider = false } = {}) {
  state.detailView = "detail";
  state.detailChatMessages = [];
  state.detailChatStatus = "";
  state.detailChatSending = false;
  if (!keepProvider) state.detailChatProvider = currentChatDefaultProvider();
  if (detailChatInput) detailChatInput.value = "";
}

function chatProvidersFromItem(item) {
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  return cached?.chat_providers || {};
}

function resolveDetailChatProvider(item) {
  const providers = chatProvidersFromItem(item);
  if (providers[state.detailChatProvider]?.available) return state.detailChatProvider;
  if (providers.openai?.available) return "openai";
  if (providers.deepseek?.available) return "deepseek";
  return state.detailChatProvider || "deepseek";
}

function chatCapabilityText(provider, meta) {
  if (!meta) return "";
  if (provider === "openai") {
    return meta.available
      ? "ChatGPT：可尝试联网搜索补充最新公开信息；会区分正文事实、外部补充和推断。"
      : "ChatGPT：当前未配置 OPENAI_API_KEY，已禁用。";
  }
  return meta.available
    ? "DeepSeek：基于新闻正文与已有知识回答，不保证实时联网或最新进展。"
    : "DeepSeek：当前未配置 DEEPSEEK_API_KEY，已禁用。";
}

function renderDetailChat(item) {
  if (!item) return;
  const providers = chatProvidersFromItem(item);
  const provider = resolveDetailChatProvider(item);
  state.detailChatProvider = provider;

  detailChatMeta.textContent = `${item.title || ""} · ${item.source || "未知来源"}`;
  detailChatProviderSelect.innerHTML = "";
  [
    ["deepseek", providers.deepseek],
    ["openai", providers.openai],
  ].forEach(([key, meta]) => {
    if (!meta) return;
    const option = document.createElement("option");
    option.value = key;
    option.textContent = meta.label || key;
    option.disabled = !meta.available;
    if (!meta.available) option.textContent += "（未配置）";
    detailChatProviderSelect.appendChild(option);
  });
  detailChatProviderSelect.value = provider;
  detailChatCapability.textContent = chatCapabilityText(provider, providers[provider]);
  detailChatProviderSelect.disabled = state.detailChatSending;
  detailChatInput.disabled = state.detailChatSending;
  detailChatSendBtn.disabled = state.detailChatSending;

  const chatReady = !!(state.detailChatMessages && state.detailChatMessages.length);
  const statusText = state.detailChatStatus || (chatReady ? "" : "这次对话不会保存；切换新闻或切换模型后会清空。");
  detailChatStatus.textContent = statusText;
  detailChatStatus.className = `detail-status ${state.detailChatSending ? "pending" : statusText ? "muted" : "hidden"}`;

  detailChatMessages.innerHTML = "";
  if (!chatReady) {
    const empty = document.createElement("div");
    empty.className = "detail-chat-empty";
    empty.textContent = "可以追问这条新闻的背景、影响、最新进展判断或相关公司/板块含义。";
    detailChatMessages.appendChild(empty);
    return;
  }
  state.detailChatMessages.forEach((message) => {
    const card = document.createElement("div");
    card.className = `detail-chat-message ${message.role}`;
    const role = document.createElement("div");
    role.className = "detail-chat-role";
    role.textContent = message.role === "user" ? "你" : "助手";
    const text = document.createElement("div");
    text.className = "detail-chat-text";
    text.textContent = message.content || "";
    card.appendChild(role);
    card.appendChild(text);
    detailChatMessages.appendChild(card);
  });
  detailChatMessages.scrollTop = detailChatMessages.scrollHeight;
}

async function requestNewsChat(item, provider, messages) {
  const res = await fetch(`/api/news/${encodeURIComponent(item.id)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, messages }),
  });
  const payload = await res.json().catch(() => ({ ok: false, error: "chat_request_failed" }));
  if (!res.ok || !payload.ok) throw new Error(payload.error || "chat_request_failed");
  return payload;
}

async function sendDetailChatMessage() {
  if (!state.selectedId || state.detailChatSending) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  const content = (detailChatInput.value || "").trim().slice(0, DETAIL_CHAT_MAX_LEN);
  if (!content) return;

  state.detailChatMessages = [...state.detailChatMessages, { role: "user", content }];
  state.detailChatSending = true;
  state.detailChatStatus = "正在生成回答...";
  detailChatInput.value = "";
  renderDetailChat(item);

  try {
    const payload = await requestNewsChat(item, state.detailChatProvider, state.detailChatMessages);
    state.detailChatMessages = [...state.detailChatMessages, { role: "assistant", content: payload.answer || "" }];
    state.detailChatStatus = `${payload.provider === "openai" ? "ChatGPT" : "DeepSeek"} · ${payload.model || ""}`.trim();
  } catch (error) {
    const code = error instanceof Error ? error.message : "chat_request_failed";
    const labelMap = {
      detail_not_ready: "正文还没准备好，暂时不能提问。",
      missing_openai_api_key: "ChatGPT 当前未配置 OPENAI_API_KEY。",
      missing_deepseek_api_key: "DeepSeek 当前未配置 DEEPSEEK_API_KEY。",
      provider_busy: "该模型当前正忙，请稍后重试。",
      provider_timeout: "请求超时，请稍后重试。",
      provider_failed: "模型调用失败，请稍后重试。",
    };
    state.detailChatStatus = labelMap[code] || "发送失败，请稍后重试。";
  } finally {
    state.detailChatSending = false;
    renderDetailChat(item);
  }
}

function normalizeMarketTags(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((x) => {
      const key = typeof x?.key === "string" ? x.key.trim() : "";
      const tag = typeof x?.tag === "string" ? x.tag.trim() : "";
      const direction = x?.direction === "bearish" ? "bearish" : "bullish";
      if (!tag) return null;
      return { key: key || tag, tag, direction };
    })
    .filter(Boolean);
}

function marketTagsFromItem(item) {
  return normalizeMarketTags(item?.market_tags);
}

async function upsertMarketTag(item, tag, direction) {
  const beforeItem = {
    date_key: item.date_key,
    read_at: item.read_at,
    important_at: item.important_at,
    read_later_at: item.read_later_at,
    has_note: item.has_note,
    has_market_tags: item.has_market_tags,
  };
  const res = await fetch(`/api/news/${encodeURIComponent(item.id)}/market-tag`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag, direction }),
  });
  if (!res.ok) throw new Error("save_market_tag_failed");
  const payload = await res.json();
  if (!payload.ok) throw new Error(payload.error || "save_market_tag_failed");
  const tags = normalizeMarketTags(payload.market_tags || []);
  const cached = item.url ? (state.detailCacheByUrl.get(item.url) || {}) : {};
  cached.market_tags = tags;
  cached.has_market_tags = payload.has_market_tags;
  if (item.url) state.detailCacheByUrl.set(item.url, cached);
  item.market_tags = tags;
  item.has_market_tags = Number(payload.has_market_tags || 0);
  if ("important_at" in payload && payload.important_at) item.important_at = payload.important_at;
  state.itemsById.set(item.id, item);
  adjustDateCountForScopeTransition(beforeItem, item);
  rerenderOne(item.id);
}

async function deleteMarketTag(item, tag) {
  const beforeItem = {
    date_key: item.date_key,
    read_at: item.read_at,
    important_at: item.important_at,
    read_later_at: item.read_later_at,
    has_note: item.has_note,
    has_market_tags: item.has_market_tags,
  };
  const params = new URLSearchParams({ tag });
  const res = await fetch(`/api/news/${encodeURIComponent(item.id)}/market-tag?${params.toString()}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("delete_market_tag_failed");
  const payload = await res.json();
  if (!payload.ok) throw new Error(payload.error || "delete_market_tag_failed");
  const tags = normalizeMarketTags(payload.market_tags || []);
  const cached = item.url ? (state.detailCacheByUrl.get(item.url) || {}) : {};
  cached.market_tags = tags;
  cached.has_market_tags = payload.has_market_tags;
  if (item.url) state.detailCacheByUrl.set(item.url, cached);
  item.market_tags = tags;
  item.has_market_tags = Number(payload.has_market_tags || 0);
  state.itemsById.set(item.id, item);
  adjustDateCountForScopeTransition(beforeItem, item);
  rerenderOne(item.id);
}

function refreshDetailNoteUI(item) {
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  const noteText = normalizedDetailNote(cached);
  const hasNote = noteText.length > 0;
  item.has_note = hasNote ? 1 : 0;

  applyIcon(detailNoteToggleBtn, "pen", {
    filled: false,
    tone: hasNote ? "accent" : "default",
    label: hasNote ? "编辑想法" : "写想法",
  });
  detailNoteToggleBtn.title = hasNote ? "编辑想法" : "写想法";
  detailNoteToggleBtn.setAttribute("aria-label", hasNote ? "编辑想法" : "写想法");
  detailNoteCard.classList.toggle("hidden", !hasNote);
  detailNoteText.textContent = hasNote ? noteText : "";
  if (!detailNoteEditor.classList.contains("hidden") && !detailNoteSaveBtn.disabled) {
    detailNoteInput.value = noteText;
  }
}

function closeMarketPicker() {
  detailMarketPicker.classList.add("hidden");
  detailMarketPickerOptions.innerHTML = "";
  marketPickerDirection = null;
}

function refreshDetailMarketTagsUI(item) {
  const tags = marketTagsFromItem(item);
  detailInlineMarketTags.innerHTML = "";
  tags.forEach((mt) => {
    const chip = document.createElement("span");
    chip.className = `detail-market-tag ${mt.direction}`;
    chip.textContent = mt.tag;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "detail-market-remove";
    removeBtn.textContent = "×";
    removeBtn.title = `删除标签：${mt.tag}`;
    removeBtn.setAttribute("aria-label", `删除标签：${mt.tag}`);
    removeBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await deleteMarketTag(item, mt.key || mt.tag);
      refreshDetailMarketTagsUI(item);
    });

    chip.appendChild(removeBtn);
    detailInlineMarketTags.appendChild(chip);
  });
  detailInlineMarketTags.classList.toggle("hidden", tags.length === 0);
}

function openMarketPicker(item, direction) {
  if (!item) return;
  setDetailNoteEditorOpen(false);
  if (!detailMarketPicker.classList.contains("hidden") && marketPickerDirection === direction) {
    closeMarketPicker();
    return;
  }
  marketPickerDirection = direction;
  detailMarketPickerOptions.innerHTML = "";
  detailMarketPickerTitle.textContent = direction === "bullish" ? "选择看多板块" : "选择看空板块";
  activeMarketTagChoices().forEach((tagDef) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "detail-market-option";
    btn.textContent = tagDef.display_name;
    btn.addEventListener("click", async () => {
      await upsertMarketTag(item, tagDef.key, direction);
      closeMarketPicker();
      refreshDetailMarketTagsUI(item);
    });
    detailMarketPickerOptions.appendChild(btn);
  });
  detailMarketPicker.classList.remove("hidden");
}

async function saveDetailNote(item, noteText) {
  const beforeItem = {
    date_key: item.date_key,
    read_at: item.read_at,
    important_at: item.important_at,
    read_later_at: item.read_later_at,
    has_note: item.has_note,
    has_market_tags: item.has_market_tags,
  };
  const res = await fetch(`/api/news/${encodeURIComponent(item.id)}/note`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note: noteText }),
  });
  if (!res.ok) throw new Error("save_note_failed");
  const payload = await res.json();
  if (!payload.ok) throw new Error(payload.error || "save_note_failed");
  const cached = item.url ? (state.detailCacheByUrl.get(item.url) || {}) : {};
  cached.has_note = payload.has_note;
  cached.note = payload.note;
  cached.note_preview = payload.note_preview || "";
  if (item.url) state.detailCacheByUrl.set(item.url, cached);
  item.has_note = payload.has_note;
  item.note_preview = payload.note_preview || "";
  state.itemsById.set(item.id, item);
  adjustDateCountForScopeTransition(beforeItem, item);
  rerenderOne(item.id);
  refreshDetailNoteUI(item);
}

function renderDetail(item) {
  closeTagAdminView();
  if (!item) {
    resetDetailChatState({ keepProvider: true });
    state.detailReturnToTrend = false;
    stopDetailPolling();
    closeMarketPicker();
    syncDetailReturnButton();
    detailTrendBody.classList.add("hidden");
    detailBody.classList.add("hidden");
    detailChatBody.classList.add("hidden");
    detailEmpty.classList.remove("hidden");
    detailEmpty.textContent = state.collection === "trends" ? "选择一个趋势单元格查看新闻明细" : "选择一条新闻查看摘要与正文";
    updateWorkspaceLayout();
    return;
  }
  detailTrendBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  detailBody.classList.remove("hidden");
  syncDetailReturnButton();

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
  const askBtn = document.getElementById("detailAskBtn");

  if (item.url) {
    link.href = item.url;
    link.classList.remove("disabled");
    link.textContent = "打开原文";
    detailNoteToggleBtn.disabled = false;
  } else {
    link.href = "#";
    link.classList.add("disabled");
    link.textContent = "无原文链接";
    detailNoteToggleBtn.disabled = true;
  }

  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  const detail = cached?.detail || null;
  const status = cached?.detail_status || item.detail_status || "none";
  const detailErr = cached?.job?.last_error || item.detail_error || "";
  const ai = cached?.ai || null;
  const aiStatus = cached?.ai_status || item.ai_status || "none";
  const isGeminiFallback = (ai?.model || "").startsWith("gemini-fallback");

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
  closeMarketPicker();
  detailInlineMarketTags.classList.add("hidden");
  detailInlineMarketTags.innerHTML = "";
  setDetailNoteEditorOpen(false);
  detailNoteInput.value = "";

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
      if (!isGeminiFallback && Array.isArray(keyPoints) && keyPoints.length) {
        keyPoints.forEach((point) => {
          const li = document.createElement("li");
          li.textContent = point;
          detailAiPoints.appendChild(li);
        });
      }
      if (!isGeminiFallback) {
        detailAiConclusion.textContent = ai.conclusion_zh || "";
        detailAiBox.classList.remove("hidden");
      }

      statusEl.textContent = isGeminiFallback
        ? "Gemini 保底翻译，结果可能不稳定"
        : "中文摘要与翻译已生成";
      statusEl.className = isGeminiFallback ? "detail-status pending" : "detail-status ready";
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

  const chatReady = !!(detail && detail.content);
  askBtn.classList.toggle("hidden", !chatReady);
  if (!chatReady && state.detailView === "chat") {
    state.detailView = "detail";
    state.detailChatStatus = "正文还没准备好，暂时不能提问。";
  }
  detailBody.classList.toggle("hidden", state.detailView === "chat");
  detailChatBody.classList.toggle("hidden", state.detailView !== "chat");
  if (state.detailView === "chat" && chatReady) {
    renderDetailChat(item);
  }

  const importantBtn = document.getElementById("detailImportantBtn");
  applyIcon(importantBtn, "important", {
    filled: !!item.important_at,
    tone: item.important_at ? "danger" : "default",
    label: item.important_at ? "取消重要" : "标为重要",
  });
  applyIcon(detailBullishBtn, "trend-up", { tone: "danger", label: "看多板块标记" });
  applyIcon(detailBearishBtn, "trend-down", { tone: "success", label: "看空板块标记" });
  refreshDetailNoteUI(item);
  refreshDetailMarketTagsUI(item);
  updateWorkspaceLayout();
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
  state.marketTagChoices = Array.isArray(payload.market_tag_choices) ? payload.market_tag_choices : state.marketTagChoices;
  item.detail_status = payload.detail_status;
  item.detail_ready = payload.detail ? 1 : 0;
  item.has_note = Number(payload.has_note || 0);
  item.market_tags = normalizeMarketTags(payload.market_tags || []);
  item.has_market_tags = Number(payload.has_market_tags || 0);
  item.ai_status = payload.ai_status || "none";
  item.ai_ready = payload.ai ? 1 : 0;
  if (payload.job && payload.job.last_error) item.detail_error = payload.job.last_error;
  if (payload.ai_job && payload.ai_job.last_error) item.ai_error = payload.ai_job.last_error;
  state.itemsById.set(item.id, item);
  rerenderOne(item.id);
  if (state.selectedId === itemId) {
    renderDetail(item);
  }

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
  if (state.collection !== "feed") {
    if (readObserver) {
      readObserver.disconnect();
      readObserver = null;
    }
    return;
  }
  if (readObserver) readObserver.disconnect();
  readObserver = new IntersectionObserver(
    (entries) => {
      if (document.hidden) return;
      if (state.collection !== "feed") return;
      const scrollingDown = lastScrollDirectionDown;
      const listTop = entries[0]?.rootBounds?.top ?? newsList.getBoundingClientRect().top;

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
    { root: newsList, threshold: [0] }
  );

  document.querySelectorAll(".news-item").forEach((el) => readObserver.observe(el));
}

function processFeedAutoReadByScroll() {
  if (state.collection !== "feed") return;
  if (document.hidden) return;
  if (!lastScrollDirectionDown) return;
  const listRect = newsList.getBoundingClientRect();
  const listTop = listRect.top;
  const listBottom = listRect.bottom;
  newsList.querySelectorAll(".news-item").forEach((el) => {
    const id = el.dataset.id;
    if (!id) return;
    const rect = el.getBoundingClientRect();
    const intersectsList = rect.bottom > listTop && rect.top < listBottom;
    if (intersectsList) enteredViewport.add(id);
    if (!enteredViewport.has(id)) return;
    if (rowIsRead(el)) return;
    if (rect.bottom < listTop) {
      patchStateWithRollback(id, { read: true });
    }
  });
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
  const noteBadge = document.createElement("span");
  noteBadge.className = "note-badge hidden";
  noteBadge.textContent = "想法";
  line1.appendChild(noteBadge);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = item.title || "";

  const summary = document.createElement("p");
  summary.className = "summary";
  summary.textContent = item.summary || "";

  const notePreview = document.createElement("p");
  notePreview.className = "row-note-preview hidden";

  const marketTagsWrap = document.createElement("div");
  marketTagsWrap.className = "market-tags hidden";

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
  li.appendChild(notePreview);
  li.appendChild(marketTagsWrap);
  li.appendChild(actions);

  li.addEventListener("click", () => {
    if (state.selectedId === item.id) {
      state.selectedId = null;
      state.detailReturnToTrend = false;
      stopDetailPolling();
      closeDetailOnMobile();
      renderDetail(null);
    } else {
      openItemDetail(item, { fromTrend: false });
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
    q: "",
    read_filter: state.readFilter,
    collection: state.collection,
    source_filter: state.sourceFilter,
  });
  if (state.collection === "feed" && state.readFilter === "unread" && state.feedUnreadCursor) {
    params.set("cursor_date", state.feedUnreadCursor.date_key);
    params.set("cursor_published_at", state.feedUnreadCursor.published_at);
    params.set("cursor_id", String(state.feedUnreadCursor.id));
  }
  const res = await fetch(`/api/news?${params.toString()}`);
  if (!res.ok) throw new Error("news_fetch_failed");
  return res.json();
}

async function fetchSearchPage(page) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    q: state.q,
    range: state.searchRange,
    time: state.searchTime,
  });
  const res = await fetch(`/api/search?${params.toString()}`);
  if (!res.ok) throw new Error("search_fetch_failed");
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
  clearFeedEndAutoReadTimer();
  feedEndAutoReadFiredKey = "";
  state.trendRows = [];
  state.trendDates = [];
  state.trendSelection = null;
  state.trendNoteContext = null;
  state.tagAdminOpen = false;
  state.trendComposeOpen = false;
  state.dateCounts = new Map();
  state.detailReturnToTrend = false;
  state.feedUnreadCursor = null;
  resetDetailChatState();
  showTrendsView(false);
  syncSearchPageControls();
  closeDetailOnMobile();
  renderDetail(null);
  lastRenderedDateKey = null;
}

function isFeedUnreadCursorMode() {
  return state.collection === "feed" && state.readFilter === "unread";
}

function buildDateSectionRow(item) {
  const dateKey = item.date_key || "unknown";
  const li = document.createElement("li");
  li.className = "date-section";
  li.dataset.dateKey = dateKey;
  const label = document.createElement("span");
  label.className = "date-section-label";
  label.textContent = item.date_label || dateKey || "未知日期";
  const count = document.createElement("span");
  count.className = "date-section-count";
  count.textContent = formatDateCount(dateKey);
  li.appendChild(label);
  li.appendChild(count);
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
  clearFeedEndAutoReadTimer();
  if (state.collection === "feed") {
    state.readFilter = state.feedReadFilter;
  } else if (state.readFilter !== "all") {
    state.readFilter = "all";
  }
  state.loading = true;
  try {
    resetList();

    if (state.collection === "search") {
      const data = await fetchSearchPage(1);
      state.total = data.total;
      setDateCounts(data.date_counts);
      state.pages = data.pages;
      state.page = 1;
      state.hasMore = state.page < state.pages;
      data.items.forEach((item) => appendNewsRow(item, buildItemRow(item)));
      renderMeta();
      showTrendsView(false);
      if (!state.q) {
        setHint("输入关键词开始搜索");
      } else if (state.total === 0) {
        setHint(`未找到与“${state.q}”相关的新闻`);
      } else if (state.hasMore) {
        setHint("继续下滑加载更多");
      } else {
        setHint(`已显示与“${state.q}”相关的全部新闻`);
      }
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
      stopRowStatusPolling();
      return;
    }

    if (state.collection === "trends") {
      try {
        await fetchMarketTagDefinitions();
      } catch {
        state.marketTagChoices = [];
      }
      const data = await fetchMarketTrends();
      state.total = Number(data.tagged_item_count || 0);
      state.pages = 1;
      state.page = 1;
      state.hasMore = false;
      state.trendDates = Array.isArray(data.dates) ? data.dates : [];
      state.trendRows = Array.isArray(data.rows) ? data.rows : [];
      state.dateCounts = new Map();
      showTrendsView(true);
      renderTrendsView();
      renderTrendDetail(null);
      renderMeta();
      setHint(state.trendRows.length ? "点击单元格查看趋势明细" : "暂无板块趋势数据");
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
      stopRowStatusPolling();
      return;
    }

    const sourceList = await fetchSources();
    const available = new Set(sourceList.map((x) => x.key));
    if (state.sourceFilter !== "all" && !available.has(state.sourceFilter)) {
      state.sourceFilter = "all";
    }
    renderSourceFilters(sourceList);

    const data = await fetchNewsPage(1);
    state.total = data.total;
    setDateCounts(data.date_counts);
    state.pages = data.pages;
    state.page = 1;
    state.feedUnreadCursor = isFeedUnreadCursorMode() ? (data.next_cursor || null) : null;
    state.hasMore = isFeedUnreadCursorMode() ? !!data.has_more : state.page < state.pages;

    data.items.forEach((item) => appendNewsRow(item, buildItemRow(item)));
    renderMeta();

    if (state.total === 0) {
      setHint("暂无数据");
    } else if (state.hasMore) {
      setHint("继续下滑加载更多");
    } else {
      setHint("已加载全部新闻");
    }

    scheduleFeedEndAutoReadIfNeeded();

    setupReadObserver();
    ensureRowStatusPolling();
  } finally {
    state.loading = false;
    syncSearchPageControls();
    updateFilterButtons();
    updateBatchActionButton();
    updateCollectionButtons();
    updateSourceFilterVisibility();
    updateResumeButton();
  }
}

async function loadNextPage() {
  if (state.collection === "search") {
    if (!state.hasMore) return;
    const next = state.page + 1;
    state.loading = true;
    try {
      const data = await fetchSearchPage(next);
      setDateCounts(data.date_counts);
      data.items.forEach((item) => appendNewsRow(item, buildItemRow(item)));
      state.page = next;
      state.pages = data.pages;
      state.total = data.total;
      state.hasMore = state.page < state.pages;
      renderMeta();
      setHint(state.total === 0 ? `未找到与“${state.q}”相关的新闻` : (state.hasMore ? "继续下滑加载更多" : `已显示与“${state.q}”相关的全部新闻`));
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
    } finally {
      state.loading = false;
    }
    return;
  }
  if (state.collection === "trends") return;
  if (!state.hasMore) return;
  const next = state.page + 1;
  state.loading = true;
  try {
    const data = await fetchNewsPage(next);
    setDateCounts(data.date_counts);
    data.items.forEach((item) => {
      const row = buildItemRow(item);
      appendNewsRow(item, row);
      if (readObserver) readObserver.observe(row);
    });
    state.page = next;
    state.pages = data.pages;
    state.total = data.total;
    state.feedUnreadCursor = isFeedUnreadCursorMode() ? (data.next_cursor || null) : null;
    state.hasMore = isFeedUnreadCursorMode() ? !!data.has_more : state.page < state.pages;
    renderMeta();
    setHint(state.hasMore ? "继续下滑加载更多" : "已加载全部新闻");
    scheduleFeedEndAutoReadIfNeeded();
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
  if (state.collection === collection) {
    return;
  }
  if (collection === "trends" && state.collection !== "trends") {
    state.lastNewsCollectionBeforeTrends = state.collection;
  }
  state.collection = collection;
  closeMobileFilterSheet();
  closeMobileCollectionSheet();
  closeErrorStatsPanel();
  syncSearchPageControls();
  await loadFirstPage();
}

if (navSearchBtn) {
  navSearchBtn.addEventListener("click", async () => {
    await switchCollection("search");
  });
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
if (navNotesBtn) {
  navNotesBtn.addEventListener("click", async () => {
    await switchCollection("notes");
  });
}
if (navMarketTagsBtn) {
  navMarketTagsBtn.addEventListener("click", async () => {
    await switchCollection("market_tags");
  });
}
if (navTrendsBtn) {
  navTrendsBtn.addEventListener("click", async () => {
    await switchCollection("trends");
  });
}

if (mobileCollectionTriggerBtn) {
  mobileCollectionTriggerBtn.addEventListener("click", async () => {
    if (state.collection === "trends") {
      await switchCollection(state.lastNewsCollectionBeforeTrends || "feed");
      return;
    }
    openMobileCollectionSheet();
  });
}

if (mobileTabFilterBtn) {
  mobileTabFilterBtn.addEventListener("click", () => {
    if (state.collection === "search") return;
    openMobileFilterSheet();
  });
}

if (mobileTrendsTabBtn) {
  mobileTrendsTabBtn.addEventListener("click", async () => {
    await switchCollection("trends");
  });
}

if (manageMarketTagsBtn) {
  manageMarketTagsBtn.addEventListener("click", async () => {
    if (state.collection !== "trends") return;
    await openTagAdminView();
  });
}

if (trendComposeBtn) {
  trendComposeBtn.addEventListener("click", () => {
    openTrendComposeView();
  });
}

if (trendBullishNoteBtn) {
  trendBullishNoteBtn.addEventListener("click", () => {
    openTrendNoteEditor("bullish");
  });
}

if (trendBearishNoteBtn) {
  trendBearishNoteBtn.addEventListener("click", () => {
    openTrendNoteEditor("bearish");
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

if (settingsBtn) {
  settingsBtn.addEventListener("click", async () => {
    if (state.settingsOpen) {
      closeSettingsOverlay();
      return;
    }
    await openSettingsOverlay();
  });
}

if (settingsBackdrop) {
  settingsBackdrop.addEventListener("click", closeSettingsOverlay);
}

if (settingsCloseBtn) {
  settingsCloseBtn.addEventListener("click", closeSettingsOverlay);
}

if (settingsSaveBtn) {
  settingsSaveBtn.addEventListener("click", async () => {
    await saveRuntimeSettings();
  });
}

if (searchPageSubmitBtn) {
  searchPageSubmitBtn.addEventListener("click", async () => {
    await runSearchFromPage();
  });
}

if (searchPageInput) {
  searchPageInput.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    await runSearchFromPage();
  });
}

if (searchRangeSelect) {
  searchRangeSelect.addEventListener("change", async () => {
    state.searchRange = searchRangeSelect.value;
    if (state.collection === "search") await loadFirstPage();
  });
}

if (searchTimeSelect) {
  searchTimeSelect.addEventListener("change", async () => {
    state.searchTime = searchTimeSelect.value;
    if (state.collection === "search") await loadFirstPage();
  });
}

if (detailFontSelect) {
  detailFontSelect.addEventListener("change", () => {
    applyDetailFontMode(detailFontSelect.value);
  });
}

markAllReadBtn.addEventListener("click", async () => {
  if (
    state.collection === "important" ||
    state.collection === "notes" ||
    state.collection === "market_tags" ||
    state.collection === "trends"
  ) return;

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

detailCloseBtn.addEventListener("click", () => {
  if (canReturnToTrendDetail()) {
    restoreTrendDetailFromDetail();
    return;
  }
  closeDetailOnMobile();
  stopDetailPolling();
});
if (detailReturnToTrendBtn) {
  detailReturnToTrendBtn.addEventListener("click", restoreTrendDetailFromDetail);
}
if (errorStatsBtn) {
  errorStatsBtn.addEventListener("click", async (event) => {
    event.stopPropagation();
    if (!errorStatsPanel?.classList.contains("hidden")) {
      closeErrorStatsPanel();
      return;
    }
    await openErrorStatsPanel();
  });
}
document.addEventListener("click", (event) => {
  if (!errorStatsPanel || errorStatsPanel.classList.contains("hidden")) return;
  const target = event.target;
  if (!(target instanceof Node)) return;
  if (errorStatsPanel.contains(target) || errorStatsBtn?.contains(target)) return;
  closeErrorStatsPanel();
});
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

detailBullishBtn.addEventListener("click", () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  openMarketPicker(item, "bullish");
});

detailBearishBtn.addEventListener("click", () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  openMarketPicker(item, "bearish");
});

if (detailTagCreateBtn) {
  detailTagCreateBtn.addEventListener("click", async () => {
    const displayName = detailTagCreateInput.value.trim();
    if (!displayName) return;
    detailTagCreateBtn.disabled = true;
    try {
      await createMarketTagDefinition(displayName);
      detailTagCreateInput.value = "";
      await refreshTrendTagAdminState();
    } finally {
      detailTagCreateBtn.disabled = false;
    }
  });
}

if (detailTrendNoteCancelBtn) {
  detailTrendNoteCancelBtn.addEventListener("click", closeTrendNoteEditor);
}

if (detailTrendNoteSaveBtn) {
  detailTrendNoteSaveBtn.addEventListener("click", async () => {
    if (!state.trendNoteContext) return;
    detailTrendNoteSaveBtn.disabled = true;
    try {
      const context = { ...state.trendNoteContext };
      if (context.noteId) {
        await updateTrendNote(context.noteId, detailTrendNoteInput.value);
      } else {
        await saveTrendNote({
          date: context.date,
          tag: context.tagKey,
          direction: context.direction,
          note: detailTrendNoteInput.value,
        });
      }
      await refreshTrendSelectionAfterMutation({
        kind: "cell",
        key: `${context.tagKey}|${context.date}`,
        tagKey: context.tagKey,
        tagLabel: context.tagLabel,
        date: context.date,
        direction: context.direction,
      });
      closeTrendNoteEditor();
    } finally {
      detailTrendNoteSaveBtn.disabled = false;
    }
  });
}

if (detailTrendNoteDeleteBtn) {
  detailTrendNoteDeleteBtn.addEventListener("click", async () => {
    if (!state.trendNoteContext?.noteId) return;
    detailTrendNoteDeleteBtn.disabled = true;
    try {
      const context = { ...state.trendNoteContext };
      await deleteTrendNote(context.noteId);
      await refreshTrendSelectionAfterMutation({
        kind: "cell",
        key: `${context.tagKey}|${context.date}`,
        tagKey: context.tagKey,
        tagLabel: context.tagLabel,
        date: context.date,
        direction: context.direction,
      });
      closeTrendNoteEditor();
    } finally {
      detailTrendNoteDeleteBtn.disabled = false;
    }
  });
}

if (trendNoteComposeCancelBtn) {
  trendNoteComposeCancelBtn.addEventListener("click", () => {
    closeTrendComposerView();
    if (state.trendSelection?.detailPayload) {
      renderTrendDetail(state.trendSelection.detailPayload);
    } else {
      renderTrendDetail(null);
    }
  });
}

if (trendNoteComposeSaveBtn) {
  trendNoteComposeSaveBtn.addEventListener("click", async () => {
    const date = trendNoteDateSelect.value;
    const tag = trendNoteTagSelect.value;
    const direction = trendNoteDirectionSelect.value;
    if (!date || !tag || !direction) return;
    trendNoteComposeSaveBtn.disabled = true;
    try {
      await saveTrendNote({
        date,
        tag,
        direction,
        note: trendNoteComposeInput.value,
      });
      await refreshTrendSelectionAfterMutation({
        kind: "cell",
        key: `${tag}|${date}`,
        tagKey: tag,
        tagLabel: state.marketTagChoices.find((x) => x.key === tag)?.display_name || tag,
        date,
        direction,
      });
      closeTrendComposerView();
    } finally {
      trendNoteComposeSaveBtn.disabled = false;
    }
  });
}

const detailRetryBtn = document.getElementById("detailRetryBtn");
const detailRetranslateBtn = document.getElementById("detailRetranslateBtn");
if (detailAskBtn) {
  detailAskBtn.addEventListener("click", () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item) return;
    state.detailView = "chat";
    renderDetail(item);
    detailChatInput.focus();
  });
}

if (detailChatBackBtn) {
  detailChatBackBtn.addEventListener("click", () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item) return;
    state.detailView = "detail";
    renderDetail(item);
  });
}

if (detailChatProviderSelect) {
  detailChatProviderSelect.addEventListener("change", () => {
    state.detailChatProvider = detailChatProviderSelect.value || "deepseek";
    state.detailChatMessages = [];
    state.detailChatStatus = "已切换模型，临时对话已清空。";
    if (detailChatInput) detailChatInput.value = "";
    const item = state.selectedId ? state.itemsById.get(state.selectedId) : null;
    if (item) renderDetailChat(item);
  });
}

if (detailChatSendBtn) {
  detailChatSendBtn.addEventListener("click", () => {
    sendDetailChatMessage();
  });
}

if (detailChatInput) {
  detailChatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      sendDetailChatMessage();
    }
  });
}

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

detailNoteToggleBtn.addEventListener("click", () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  detailNoteInput.value = normalizedDetailNote(cached);
  setDetailNoteEditorOpen(true);
  detailNoteInput.focus();
});

detailNoteCancelBtn.addEventListener("click", () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  detailNoteInput.value = normalizedDetailNote(cached);
  setDetailNoteEditorOpen(false);
});

detailNoteSaveBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  const noteText = detailNoteInput.value.slice(0, NOTE_MAX_LEN);
  detailNoteSaveBtn.disabled = true;
  detailNoteCancelBtn.disabled = true;
  try {
    await saveDetailNote(item, noteText);
    setDetailNoteEditorOpen(false);
  } finally {
    detailNoteSaveBtn.disabled = false;
    detailNoteCancelBtn.disabled = false;
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

newsList.addEventListener("scroll", () => {
  const currentTop = newsList.scrollTop;
  lastScrollDirectionDown = currentTop > lastListScrollTop;
  lastListScrollTop = currentTop;
  processFeedAutoReadByScroll();
  scheduleFeedEndAutoReadIfNeeded();
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    lastListScrollTop = newsList.scrollTop;
    stopRowStatusPolling();
    clearFeedEndAutoReadTimer();
  } else {
    kickRowStatusPolling();
    scheduleFeedEndAutoReadIfNeeded();
  }
});

window.addEventListener("resize", () => {
  syncSearchPageControls();
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.settingsOpen) {
    closeSettingsOverlay();
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
if (settingsBtn) {
  applyIcon(settingsBtn, "settings", { label: "打开设置" });
}
if (errorStatsBtn) {
  applyIcon(errorStatsBtn, "bell", { label: "查看当日错误统计" });
}
if (searchPageSubmitBtn) {
  searchPageSubmitBtn.textContent = "搜索";
  searchPageSubmitBtn.setAttribute("aria-label", "执行搜索");
}
syncSearchPageControls();
updateFilterButtons();
updateBatchActionButton();
fetchReadingCheckpoint()
  .then((cp) => {
    state.readingCheckpoint = cp;
    updateResumeButton();
  })
  .catch(() => {});
fetchRuntimeSettings()
  .then((data) => {
    state.runtimeSettings = data;
    state.detailChatProvider = currentChatDefaultProvider();
  })
  .catch(() => {});
autoReindexAndLoad();
