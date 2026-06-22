let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "unread", // all | unread
  feedReadFilter: "unread", // 仅新闻流记忆 all | unread
  sourceFilter: "all", // all | reuters | bloomberg | techcrunch | ars | x | host:*
  collection: "feed", // search | feed | favorites | reminders | important | read_later | notes | tracked | market_tags | trends
  total: 0,
  loading: false,
  hasMore: true,
  selectedId: null,
  selectedIdeaId: "",
  selectedReminderId: null,
  selectedReminderDraftId: null,
  selectedTrackedTopicId: null,
  reminderFilter: "active", // active | done | all
  ideaFilter: "all", // all | article | trend
  itemsById: new Map(),
  reminderItems: [],
  trackedTopics: [],
  trackedTimelineItems: [],
  trackedDailySummaries: [],
  trackedBackfillMode: "recent_important",
  trackedDetailView: "timeline",
  reminderSummary: {
    total: 0,
    active_total: 0,
    due_total: 0,
    done_total: 0,
    dismissed_total: 0,
  },
  detailCacheByUrl: new Map(),
  readingCheckpoint: null,
  trendDays: 7,
  trendRows: [],
  trendDates: [],
  trendSelection: null,
  selectedTrendIdea: null,
  trendNoteContext: null,
  marketTagChoices: [],
  selectedTagAdminKey: "",
  tagAdminOpen: false,
  trendComposeOpen: false,
  newsSortOrderByCollection: {},
  dateCounts: new Map(),
  lastNewsCollectionBeforeTrends: "feed",
  detailReturnToTrend: false,
  detailReturnToTrackedTopicId: null,
  searchRange: "all",
  searchTime: "all",
  feedUnreadCursor: null,
  detailView: "detail",
  trackedFormMode: "create",
  detailChatMessages: [],
  detailChatSessionId: "",
  detailChatModel: "",
  detailChatStatus: "",
  detailChatSending: false,
  detailChatArchiving: false,
  settingsOpen: false,
  settingsLoading: false,
  settingsSaving: false,
  settingsSecretBusyProvider: "",
  settingsSecretEditorProvider: "",
  settingsSection: "services",
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
const SETTINGS_CUSTOM_MODEL_VALUE = "__custom__";

const refreshBtn = document.getElementById("refreshBtn");
const resumeAnchorBtn = document.getElementById("resumeAnchorBtn");
const readFilterToggleBtn = document.getElementById("readFilterToggleBtn");
const sortOrderBtn = document.getElementById("sortOrderBtn");
const trackedCreateInlineBtn = document.getElementById("trackedCreateInlineBtn");
const markAllReadBtn = document.getElementById("markAllReadBtn");
const manageMarketTagsBtn = document.getElementById("manageMarketTagsBtn");

const navSearchBtn = document.getElementById("navSearchBtn");
const navFeedBtn = document.getElementById("navFeedBtn");
const navFavoritesBtn = document.getElementById("navFavoritesBtn");
const navRemindersBtn = document.getElementById("navRemindersBtn");
const navImportantBtn = document.getElementById("navImportantBtn");
const navReadLaterBtn = document.getElementById("navReadLaterBtn");
const navNotesBtn = document.getElementById("navNotesBtn");
const navTrackedBtn = document.getElementById("navTrackedBtn");
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
const reminderFilterBar = document.getElementById("reminderFilterBar");
const reminderFilterActiveBtn = document.getElementById("reminderFilterActiveBtn");
const reminderFilterDoneBtn = document.getElementById("reminderFilterDoneBtn");
const reminderFilterAllBtn = document.getElementById("reminderFilterAllBtn");
const ideaFilterBar = document.getElementById("ideaFilterBar");
const ideaFilterAllBtn = document.getElementById("ideaFilterAllBtn");
const ideaFilterArticleBtn = document.getElementById("ideaFilterArticleBtn");
const ideaFilterTrendBtn = document.getElementById("ideaFilterTrendBtn");
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");
const workspace = document.getElementById("workspace");
const trendsView = document.getElementById("trendsView");
const trendsTable = document.getElementById("trendsTable");
const trackedView = document.getElementById("trackedView");
const trackedBackfillModeSelect = document.getElementById("trackedBackfillModeSelect");
const trackedBackfillBtn = document.getElementById("trackedBackfillBtn");
const trackedEditBtn = document.getElementById("trackedEditBtn");
const trackedDeleteBtn = document.getElementById("trackedDeleteBtn");
const trackedViewTimelineBtn = document.getElementById("trackedViewTimelineBtn");
const trackedViewTimeflowBtn = document.getElementById("trackedViewTimeflowBtn");
const trackedTimelineHint = document.getElementById("trackedTimelineHint");
const trackedTimelineList = document.getElementById("trackedTimelineList");

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
const detailTrendIdeaBody = document.getElementById("detailTrendIdeaBody");
const detailTrendIdeaTitle = document.getElementById("detailTrendIdeaTitle");
const detailTrendIdeaMeta = document.getElementById("detailTrendIdeaMeta");
const detailTrendIdeaCard = document.getElementById("detailTrendIdeaCard");
const detailTrendIdeaText = document.getElementById("detailTrendIdeaText");
const detailTrendIdeaEditBtn = document.getElementById("detailTrendIdeaEditBtn");
const detailTrendIdeaDeleteBtn = document.getElementById("detailTrendIdeaDeleteBtn");
const detailTrendIdeaEditor = document.getElementById("detailTrendIdeaEditor");
const detailTrendIdeaInput = document.getElementById("detailTrendIdeaInput");
const detailTrendIdeaSaveBtn = document.getElementById("detailTrendIdeaSaveBtn");
const detailTrendIdeaCancelBtn = document.getElementById("detailTrendIdeaCancelBtn");
const detailTagAdminBody = document.getElementById("detailTagAdminBody");
const detailTagCreateInput = document.getElementById("detailTagCreateInput");
const detailTagCreateBtn = document.getElementById("detailTagCreateBtn");
const detailTagAdminList = document.getElementById("detailTagAdminList");
const detailTrackedBody = document.getElementById("detailTrackedBody");
const detailTrackedTitle = document.getElementById("detailTrackedTitle");
const detailTrackedMeta = document.getElementById("detailTrackedMeta");
const detailTrackedKeywords = document.getElementById("detailTrackedKeywords");
const detailTrackedFormBody = document.getElementById("detailTrackedFormBody");
const detailTrackedFormBackBtn = document.getElementById("detailTrackedFormBackBtn");
const detailTrackedFormTitle = document.getElementById("detailTrackedFormTitle");
const detailTrackedFormMeta = document.getElementById("detailTrackedFormMeta");
const detailTrackedTitleInput = document.getElementById("detailTrackedTitleInput");
const detailTrackedStrongInput = document.getElementById("detailTrackedStrongInput");
const detailTrackedCoreInput = document.getElementById("detailTrackedCoreInput");
const detailTrackedContextInput = document.getElementById("detailTrackedContextInput");
const detailTrackedExcludeInput = document.getElementById("detailTrackedExcludeInput");
const detailTrackedThresholdInput = document.getElementById("detailTrackedThresholdInput");
const detailTrackedTitleWeightInput = document.getElementById("detailTrackedTitleWeightInput");
const detailTrackedNoteWeightInput = document.getElementById("detailTrackedNoteWeightInput");
const detailTrackedSummaryWeightInput = document.getElementById("detailTrackedSummaryWeightInput");
const detailTrackedContentWeightInput = document.getElementById("detailTrackedContentWeightInput");
const detailTrackedStrongScoreInput = document.getElementById("detailTrackedStrongScoreInput");
const detailTrackedCoreScoreInput = document.getElementById("detailTrackedCoreScoreInput");
const detailTrackedContextScoreInput = document.getElementById("detailTrackedContextScoreInput");
const detailTrackedExcludePenaltyInput = document.getElementById("detailTrackedExcludePenaltyInput");
const detailTrackedScopeSelect = document.getElementById("detailTrackedScopeSelect");
const detailTrackedActiveInput = document.getElementById("detailTrackedActiveInput");
const detailTrackedFormSaveBtn = document.getElementById("detailTrackedFormSaveBtn");
const detailTrackedFormCancelBtn = document.getElementById("detailTrackedFormCancelBtn");
const detailBody = document.getElementById("detailBody");
const detailChatBody = document.getElementById("detailChatBody");
const detailAskBtn = document.getElementById("detailAskBtn");
const detailChatBackBtn = document.getElementById("detailChatBackBtn");
const detailChatMeta = document.getElementById("detailChatMeta");
const detailChatCapability = document.getElementById("detailChatCapability");
const detailChatStatus = document.getElementById("detailChatStatus");
const detailChatMessages = document.getElementById("detailChatMessages");
const detailChatInput = document.getElementById("detailChatInput");
const detailChatArchiveBtn = document.getElementById("detailChatArchiveBtn");
const detailChatSendBtn = document.getElementById("detailChatSendBtn");
const settingsOverlay = document.getElementById("settingsOverlay");
const settingsBackdrop = document.getElementById("settingsBackdrop");
const settingsCloseBtn = document.getElementById("settingsCloseBtn");
const settingsStatus = document.getElementById("settingsStatus");
const settingsApiStatus = document.getElementById("settingsApiStatus");
const settingsNavServices = document.getElementById("settingsNavServices");
const settingsNavModels = document.getElementById("settingsNavModels");
const settingsNavRelease = document.getElementById("settingsNavRelease");
const settingsSectionServices = document.getElementById("settingsSectionServices");
const settingsSectionModels = document.getElementById("settingsSectionModels");
const settingsSectionRelease = document.getElementById("settingsSectionRelease");
const settingsTranslationProvider = document.getElementById("settingsTranslationProvider");
const settingsTranslationModelSelect = document.getElementById("settingsTranslationModelSelect");
const settingsTranslationModelCustom = document.getElementById("settingsTranslationModelCustom");
const settingsTranslationModelCurrent = document.getElementById("settingsTranslationModelCurrent");
const settingsCodexChatModelSelect = document.getElementById("settingsCodexChatModelSelect");
const settingsCodexChatModelCustom = document.getElementById("settingsCodexChatModelCustom");
const settingsCodexChatModelCurrent = document.getElementById("settingsCodexChatModelCurrent");
const settingsSaveBtn = document.getElementById("settingsSaveBtn");
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
const detailReturnToTrackedBtn = document.getElementById("detailReturnToTrackedBtn");
const detailBullishBtn = document.getElementById("detailBullishBtn");
const detailBearishBtn = document.getElementById("detailBearishBtn");
const detailReminderToggleBtn = document.getElementById("detailReminderToggleBtn");
const detailTrackBtn = document.getElementById("detailTrackBtn");
const detailFavoriteBtn = document.getElementById("detailFavoriteBtn");
const detailInlineMarketTags = document.getElementById("detailInlineMarketTags");
const detailMarketPicker = document.getElementById("detailMarketPicker");
const detailMarketPickerTitle = document.getElementById("detailMarketPickerTitle");
const detailMarketPickerOptions = document.getElementById("detailMarketPickerOptions");
const detailReminderEditor = document.getElementById("detailReminderEditor");
const detailReminderEditorTitle = document.getElementById("detailReminderEditorTitle");
const detailReminderEventTitleText = document.getElementById("detailReminderEventTitleText");
const detailReminderEventDateInput = document.getElementById("detailReminderEventDateInput");
const detailReminderNoteInput = document.getElementById("detailReminderNoteInput");
const detailReminderSaveBtn = document.getElementById("detailReminderSaveBtn");
const detailReminderDeleteBtn = document.getElementById("detailReminderDeleteBtn");
const detailReminderCancelBtn = document.getElementById("detailReminderCancelBtn");
const detailReminderCard = document.getElementById("detailReminderCard");
const detailReminderSummary = document.getElementById("detailReminderSummary");
const detailReminderList = document.getElementById("detailReminderList");
const detailTrackEditor = document.getElementById("detailTrackEditor");
const detailTrackEditorMeta = document.getElementById("detailTrackEditorMeta");
const detailTrackTopicSelect = document.getElementById("detailTrackTopicSelect");
const detailTrackSaveBtn = document.getElementById("detailTrackSaveBtn");
const detailTrackCancelBtn = document.getElementById("detailTrackCancelBtn");

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
let reminderSummaryTimer = null;
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

function reminderDueCount() {
  return Number(state.reminderSummary?.due_total || 0);
}

function reminderNavLabel() {
  const due = reminderDueCount();
  return due > 0 ? `提醒 (${due})` : "提醒";
}

function reminderStatusLabel(status) {
  const mapping = { active: "进行中", done: "已完成", dismissed: "已关闭" };
  return mapping[status] || "提醒";
}

function reminderFilterLabel(filter = state.reminderFilter) {
  const mapping = { active: "进行中", done: "已完成", all: "全部" };
  return mapping[filter] || "进行中";
}

function normalizeReminderItems(items) {
  const rows = Array.isArray(items) ? [...items] : [];
  rows.sort((a, b) => {
    const rank = (row) => {
      if (row.status === "active" && row.is_due) return 0;
      if (row.status === "active") return 1;
      if (row.status === "done") return 2;
      return 3;
    };
    const diff = rank(a) - rank(b);
    if (diff !== 0) return diff;
    const at = String(a.remind_at || "");
    const bt = String(b.remind_at || "");
    if (at !== bt) return at.localeCompare(bt);
    return Number(b.id || 0) - Number(a.id || 0);
  });
  return rows;
}

function formatReminderDateTime(value) {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 16);
}

function toDateTimeLocalValue(value) {
  if (!value) return "";
  return String(value).replace(" ", "T").slice(0, 16);
}

function reminderDateToDefaultRemindAt(dateValue) {
  if (!dateValue) return "";
  return `${dateValue} 08:00:00`;
}

function startReminderSummaryTimer() {
  if (reminderSummaryTimer) return;
  reminderSummaryTimer = window.setInterval(() => {
    refreshReminderSummary().catch(() => {});
  }, 60000);
}

function stopReminderSummaryTimer() {
  if (!reminderSummaryTimer) return;
  window.clearInterval(reminderSummaryTimer);
  reminderSummaryTimer = null;
}

function applyReminderSummary(summary) {
  state.reminderSummary = {
    total: Number(summary?.total || 0),
    active_total: Number(summary?.active_total || 0),
    due_total: Number(summary?.due_total || 0),
    done_total: Number(summary?.done_total || 0),
    dismissed_total: Number(summary?.dismissed_total || 0),
  };
  if (navRemindersBtn) navRemindersBtn.textContent = reminderNavLabel();
  updateCollectionButtons();
}

async function fetchReminderSummary() {
  const res = await fetch("/api/reminders/summary");
  if (!res.ok) throw new Error("reminder_summary_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "reminder_summary_fetch_failed");
  return data.summary || {};
}

async function refreshReminderSummary() {
  const summary = await fetchReminderSummary();
  applyReminderSummary(summary);
}

async function fetchReminders(status = "active") {
  const params = new URLSearchParams({ status });
  const res = await fetch(`/api/reminders?${params.toString()}`);
  if (!res.ok) throw new Error("reminders_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "reminders_fetch_failed");
  return data;
}

async function createReminder(itemId, payload) {
  const res = await fetch(`/api/news/${encodeURIComponent(itemId)}/reminders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "reminder_create_failed");
  return data;
}

async function updateReminder(reminderId, payload) {
  const res = await fetch(`/api/reminders/${encodeURIComponent(reminderId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "reminder_update_failed");
  return data;
}

async function deleteReminder(reminderId) {
  const res = await fetch(`/api/reminders/${encodeURIComponent(reminderId)}`, {
    method: "DELETE",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "reminder_delete_failed");
  return data;
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
  if (trackedView) trackedView.classList.toggle("hidden", true);
  newsList.classList.toggle("hidden", !!show);
}

function showTrackedView(show) {
  if (trackedView) trackedView.classList.toggle("hidden", true);
  trendsView.classList.toggle("hidden", true);
  newsList.classList.toggle("hidden", false);
}

function updateWorkspaceLayout() {
  if (!workspace) return;
  const trendsMode = state.collection === "trends";
  const trendDetailOpen = trendsMode && (!!state.trendSelection || state.tagAdminOpen || state.trendComposeOpen);
  workspace.classList.toggle("trends-mode", trendsMode);
  workspace.classList.toggle("trends-detail-open", trendDetailOpen);
}

function updateSourceFilterVisibility() {
  const visible = state.collection !== "trends" && state.collection !== "tracked" && state.collection !== "search" && state.collection !== "reminders" && state.collection !== "notes";
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

async function fetchMarketTagImpact(tagKey) {
  const res = await fetch(`/api/market-tags/${encodeURIComponent(tagKey)}/impact`);
  if (!res.ok) throw new Error("market_tag_impact_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tag_impact_failed");
  return data;
}

async function deleteMarketTagDefinition(tagKey) {
  const res = await fetch(`/api/market-tags/${encodeURIComponent(tagKey)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("market_tag_delete_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tag_delete_failed");
  return data;
}

async function mergeMarketTagDefinition(tagKey, targetKey) {
  const res = await fetch(`/api/market-tags/${encodeURIComponent(tagKey)}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_key: targetKey }),
  });
  if (!res.ok) throw new Error("market_tag_merge_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tag_merge_failed");
  return data;
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
  if (!item || state.collection === "trends" || state.collection === "search" || state.collection === "reminders") return false;
  let inCollection = false;
  if (state.collection === "feed") inCollection = true;
  else if (state.collection === "favorites") inCollection = !!item.favorite_at;
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

async function saveApiSecret(provider, key) {
  const res = await fetch(`/api/settings/secrets/${provider}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || "settings_secret_save_failed");
  return data;
}

async function deleteApiSecret(provider) {
  const res = await fetch(`/api/settings/secrets/${provider}`, {
    method: "DELETE",
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || "settings_secret_delete_failed");
  return data;
}

function renderSettingsApiStatus() {
  if (!settingsApiStatus) return;
  settingsApiStatus.innerHTML = "";
  const apiStatus = state.runtimeSettings?.api_status || {};
  [
    ["deepseek", "DeepSeek"],
    ["codex", "Codex exec"],
  ].forEach(([key, label]) => {
    const service = apiStatus[key] || {};
    const row = document.createElement("div");
    row.className = "settings-api-item";
    const top = document.createElement("div");
    top.className = "settings-api-item-top";
    const head = document.createElement("div");
    const name = document.createElement("div");
    name.className = "settings-api-name";
    name.textContent = label;
    head.appendChild(name);

    const summary = document.createElement("div");
    summary.className = "settings-api-meta";
    if (key === "deepseek") {
      const configured = !!service.configured;
      const endpointStatus = service.models_endpoint_reachable === true
        ? "/models 可访问"
        : service.models_endpoint_reachable === false
          ? "/models fallback"
          : "/models 未检查";
      summary.textContent = `Key ${configured ? "已配置" : "未配置"} · ${endpointStatus}`;
    } else {
      const cliStatus = service.cli_available ? "CLI 可见" : "CLI 缺失";
      const execStatus = service.exec_available ? "exec 可用" : "exec 不可用";
      const modelsStatus = service.models_readable ? "models 可读" : "models fallback";
      summary.textContent = `${cliStatus} · ${execStatus} · ${modelsStatus}`;
    }
    head.appendChild(summary);

    const badge = document.createElement("span");
    const healthy = key === "deepseek" ? !!service.configured : !!service.exec_available;
    badge.className = `settings-api-badge ${healthy ? "ok" : "muted"}`;
    badge.textContent = healthy ? "可用" : "待处理";
    top.appendChild(head);
    top.appendChild(badge);
    row.appendChild(top);

    const statusLine = document.createElement("div");
    statusLine.className = "settings-api-meta";
    statusLine.textContent = service.status_text || "暂无状态信息。";
    row.appendChild(statusLine);

    if (service.last_error) {
      const errorLine = document.createElement("div");
      errorLine.className = "settings-api-meta";
      errorLine.textContent = `最近状态：${service.last_error}`;
      row.appendChild(errorLine);
    }

    if (key === "deepseek") {
      const configured = !!service.configured;
      const actions = document.createElement("div");
      actions.className = "settings-actions";
      const showEditor = !configured || state.settingsSecretEditorProvider === key || state.settingsSecretBusyProvider === key;

      if (showEditor) {
        const input = document.createElement("input");
        input.className = "settings-input";
        input.type = "password";
        input.autocomplete = "off";
        input.placeholder = configured ? "输入新 key 后保存" : "粘贴 API key";
        input.disabled = state.settingsSaving || state.settingsSecretBusyProvider === key;
        row.appendChild(input);

        const saveBtn = document.createElement("button");
        saveBtn.className = "detail-retry-btn";
        saveBtn.type = "button";
        saveBtn.textContent = configured ? "保存 key" : "保存 key";
        saveBtn.disabled = state.settingsSaving || state.settingsSecretBusyProvider === key;
        saveBtn.addEventListener("click", async () => {
          const draft = (input.value || "").trim();
          if (!draft) {
            state.settingsMessage = "请输入非空 API key。";
            state.settingsMessageTone = "failed";
            renderSettingsOverlay();
            return;
          }
          state.settingsSecretBusyProvider = key;
          state.settingsMessage = `${label} key 保存中...`;
          state.settingsMessageTone = "pending";
          renderSettingsOverlay();
          try {
            state.runtimeSettings = await saveApiSecret(key, draft);
            state.settingsSecretEditorProvider = "";
            state.settingsMessage = "已保存，重启 Flask 后生效。";
            state.settingsMessageTone = "ready";
          } catch (error) {
            const code = error instanceof Error ? error.message : "";
            state.settingsMessage =
              code === "keychain_unavailable"
                ? "当前机器不可用 macOS Keychain，无法保存。"
                : "保存失败，请稍后重试。";
            state.settingsMessageTone = "failed";
          } finally {
            state.settingsSecretBusyProvider = "";
            renderSettingsOverlay();
          }
        });
        actions.appendChild(saveBtn);

        if (configured) {
          const cancelBtn = document.createElement("button");
          cancelBtn.className = "detail-retry-btn";
          cancelBtn.type = "button";
          cancelBtn.textContent = "取消";
          cancelBtn.disabled = state.settingsSaving || state.settingsSecretBusyProvider === key;
          cancelBtn.addEventListener("click", () => {
            state.settingsSecretEditorProvider = "";
            renderSettingsOverlay();
          });
          actions.appendChild(cancelBtn);
        }
      } else {
        const updateBtn = document.createElement("button");
        updateBtn.className = "detail-retry-btn";
        updateBtn.type = "button";
        updateBtn.textContent = "更新 key";
        updateBtn.disabled = state.settingsSaving || state.settingsSecretBusyProvider === key;
        updateBtn.addEventListener("click", () => {
          state.settingsSecretEditorProvider = key;
          renderSettingsOverlay();
        });
        actions.appendChild(updateBtn);
      }

      const deleteBtn = document.createElement("button");
      deleteBtn.className = "detail-retry-btn";
      deleteBtn.type = "button";
      deleteBtn.textContent = "删除 key";
      deleteBtn.disabled = !configured || state.settingsSaving || state.settingsSecretBusyProvider === key;
      deleteBtn.addEventListener("click", async () => {
        if (!window.confirm(`确认删除 ${label} API key？`)) return;
        state.settingsSecretBusyProvider = key;
        state.settingsMessage = `${label} key 删除中...`;
        state.settingsMessageTone = "pending";
        renderSettingsOverlay();
        try {
          state.runtimeSettings = await deleteApiSecret(key);
          state.settingsMessage = "已删除，重启 Flask 后生效。";
          state.settingsMessageTone = "ready";
        } catch (error) {
          const code = error instanceof Error ? error.message : "";
          state.settingsMessage =
            code === "keychain_unavailable"
              ? "当前机器不可用 macOS Keychain，无法删除。"
              : "删除失败，请稍后重试。";
          state.settingsMessageTone = "failed";
        } finally {
          state.settingsSecretBusyProvider = "";
          renderSettingsOverlay();
        }
      });
      actions.appendChild(deleteBtn);
      row.appendChild(actions);
    }
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

function populateModelSelect(select, customInput, catalog, currentValue) {
  if (!select || !customInput) return;
  const savedValue = (currentValue || "").trim();
  const options = Array.isArray(catalog?.options) ? catalog.options : [];
  select.innerHTML = "";

  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = catalog?.default_label || "deepseek-chat";
  select.appendChild(defaultOption);

  const values = new Set([""]);
  options.forEach((item) => {
    const value = (item?.value || "").trim();
    if (!value || values.has(value)) return;
    values.add(value);
    const option = document.createElement("option");
    option.value = value;
    option.textContent = item?.label || value;
    select.appendChild(option);
  });

  if (savedValue && !values.has(savedValue)) {
    values.add(savedValue);
    const savedOption = document.createElement("option");
    savedOption.value = savedValue;
    savedOption.textContent = savedValue;
    select.appendChild(savedOption);
  }

  const customOption = document.createElement("option");
  customOption.value = SETTINGS_CUSTOM_MODEL_VALUE;
  customOption.textContent = "自定义输入...";
  select.appendChild(customOption);

  if (savedValue && values.has(savedValue)) {
    select.value = savedValue;
    customInput.value = "";
    customInput.classList.add("hidden");
  } else if (savedValue) {
    select.value = SETTINGS_CUSTOM_MODEL_VALUE;
    customInput.value = savedValue;
    customInput.classList.remove("hidden");
  } else {
    select.value = "";
    customInput.value = "";
    customInput.classList.add("hidden");
  }
}

function renderSettingsNav() {
  [
    [settingsNavServices, "services"],
    [settingsNavModels, "models"],
    [settingsNavRelease, "release"],
  ].forEach(([button, section]) => {
    if (!button) return;
    const active = state.settingsSection === section;
    button.classList.toggle("active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
}

function renderSettingsSections() {
  [
    [settingsSectionServices, "services"],
    [settingsSectionModels, "models"],
    [settingsSectionRelease, "release"],
  ].forEach(([sectionEl, section]) => {
    if (!sectionEl) return;
    sectionEl.classList.toggle("hidden", state.settingsSection !== section);
  });
}

function syncModelCustomVisibility(select, customInput) {
  if (!select || !customInput) return;
  const useCustom = select.value === SETTINGS_CUSTOM_MODEL_VALUE;
  customInput.classList.toggle("hidden", !useCustom);
  if (useCustom) {
    customInput.focus();
  } else {
    customInput.value = "";
  }
}

function readModelSetting(select, customInput) {
  if (!select) return "";
  if (select.value === SETTINGS_CUSTOM_MODEL_VALUE) {
    return (customInput?.value || "").trim();
  }
  return (select.value || "").trim();
}

function populateSettingsForm() {
  const llm = state.runtimeSettings?.llm;
  if (!llm) return;
  settingsTranslationProvider.value = llm.translation?.provider || "deepseek";
  populateModelSelect(
    settingsTranslationModelSelect,
    settingsTranslationModelCustom,
    state.runtimeSettings?.model_catalogs?.translation,
    llm.translation?.model || "",
  );
  populateModelSelect(
    settingsCodexChatModelSelect,
    settingsCodexChatModelCustom,
    state.runtimeSettings?.model_catalogs?.codex_chat,
    llm.codex_chat?.model || "",
  );
  if (settingsTranslationModelCurrent) {
    const currentTranslationModel = (llm.translation?.model || "").trim();
    const resolvedDefaultTranslationModel = (state.runtimeSettings?.model_catalogs?.translation?.resolved_default_model || "deepseek-chat").trim();
    if (currentTranslationModel) {
      settingsTranslationModelCurrent.textContent = currentTranslationModel === resolvedDefaultTranslationModel
        ? `当前：${currentTranslationModel}`
        : `当前：${currentTranslationModel} · 结构化兼容性未验证`;
    } else {
      settingsTranslationModelCurrent.textContent = `当前：${resolvedDefaultTranslationModel}（默认）`;
    }
  }
  if (settingsCodexChatModelCurrent) {
    const currentCodexModel = (llm.codex_chat?.model || "").trim();
    settingsCodexChatModelCurrent.textContent = currentCodexModel
      ? `当前：${currentCodexModel}`
      : "当前：Codex 默认模型";
  }
}

function renderSettingsOverlay() {
  if (!settingsOverlay) return;
  settingsOverlay.classList.toggle("hidden", !state.settingsOpen);
  settingsOverlay.setAttribute("aria-hidden", state.settingsOpen ? "false" : "true");
  if (!state.settingsOpen) return;
  renderSettingsNav();
  renderSettingsSections();
  renderSettingsApiStatus();
  renderReleaseNotes();
  populateSettingsForm();
  settingsSaveBtn.disabled = state.settingsSaving;
  const statusText = state.settingsLoading
    ? "读取中..."
    : state.settingsSaving
      ? "保存中..."
      : state.settingsMessage || "";
  const tone = state.settingsLoading || state.settingsSaving ? "pending" : (state.settingsMessageTone || "muted");
  settingsStatus.textContent = statusText;
  settingsStatus.className = `detail-status ${tone}${statusText ? "" : " hidden"}`;
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
  state.settingsSecretEditorProvider = "";
  renderSettingsOverlay();
}

async function saveRuntimeSettings() {
  const draftTranslationProvider = settingsTranslationProvider.value || "deepseek";
  const draftTranslationModel = readModelSetting(settingsTranslationModelSelect, settingsTranslationModelCustom);
  const draftCodexChatModel = readModelSetting(settingsCodexChatModelSelect, settingsCodexChatModelCustom);
  state.settingsSaving = true;
  renderSettingsOverlay();
  try {
    const previousCodexModel = state.runtimeSettings?.llm?.codex_chat?.model || "";
    const payload = {
      llm: {
        translation: {
          provider: draftTranslationProvider,
          model: draftTranslationModel,
        },
        codex_chat: {
          model: draftCodexChatModel,
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
    const currentCodexModel = data.llm?.codex_chat?.model || "";
    if (currentCodexModel !== previousCodexModel) {
      state.detailChatSessionId = "";
      state.detailChatModel = "";
      state.detailChatMessages = [];
      state.detailChatStatus = "Codex chat 模型已切换，当前临时对话已清空。";
    }
    state.settingsMessage = "保存成功。新请求通常立即生效；终验前建议重启 Flask。";
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
    item.active_reminder_count = Number(st.active_reminder_count || 0);
    item.due_reminder_count = Number(st.due_reminder_count || 0);
    item.next_remind_at = st.next_remind_at || null;
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
  if (name === "star") {
    if (filled) {
      return `<svg ${common}><path d="m12 4.7 2.2 4.5 5 .7-3.6 3.5.9 4.9-4.5-2.4-4.5 2.4.9-4.9L4.8 9.9l5-.7L12 4.7Z" fill="currentColor" stroke="currentColor"/></svg>`;
    }
    return `<svg ${common}><path d="m12 4.7 2.2 4.5 5 .7-3.6 3.5.9 4.9-4.5-2.4-4.5 2.4.9-4.9L4.8 9.9l5-.7L12 4.7Z"/></svg>`;
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
  if (name === "message-circle") {
    return `<svg ${common}><path d="M8.5 17.5 5 19l1-3.4A6.8 6.8 0 1 1 8.5 17.5Z"/></svg>`;
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
  if (name === "sort-asc") {
    return `<svg ${common}><path d="M8 17V7"/><path d="m5.5 9.5 2.5-2.5 2.5 2.5"/><path d="M14 8.5h4"/><path d="M14 12h3"/><path d="M14 15.5h2"/></svg>`;
  }
  if (name === "sort-desc") {
    return `<svg ${common}><path d="M8 7v10"/><path d="m5.5 14.5 2.5 2.5 2.5-2.5"/><path d="M14 8.5h2"/><path d="M14 12h3"/><path d="M14 15.5h4"/></svg>`;
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
  li.dataset.favorite = item.favorite_at ? "1" : "0";
  li.dataset.important = item.important_at ? "1" : "0";
  li.dataset.readLater = item.read_later_at ? "1" : "0";
  li.dataset.hasReminder = Number(item.active_reminder_count || 0) > 0 ? "1" : "0";

  const unreadDot = li.querySelector(".unread-dot");
  if (unreadDot) unreadDot.classList.toggle("hidden", !!item.read_at);
  const noteBadge = li.querySelector(".note-badge");
  if (noteBadge) {
    const hasNote = Number(item.has_note || 0) === 1;
    noteBadge.classList.toggle("hidden", !hasNote);
  }
  const reminderBadge = li.querySelector(".reminder-badge");
  if (reminderBadge) {
    const activeCount = Number(item.active_reminder_count || 0);
    const dueCount = Number(item.due_reminder_count || 0);
    reminderBadge.textContent = dueCount > 0 ? `到期 ${dueCount}` : `提醒 ${activeCount}`;
    reminderBadge.classList.toggle("hidden", activeCount <= 0);
    reminderBadge.classList.toggle("due", dueCount > 0);
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

  const favoriteBtn = li.querySelector(".btn-favorite");
  if (favoriteBtn) {
    applyIcon(favoriteBtn, "star", {
      filled: !!item.favorite_at,
      tone: item.favorite_at ? "warning" : "default",
      label: item.favorite_at ? "取消收藏" : "加入收藏",
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

function updateIdeaFilterBar() {
  if (!ideaFilterBar) return;
  const visible = state.collection === "notes";
  ideaFilterBar.classList.toggle("hidden", !visible);
  if (!visible) return;
  [
    [ideaFilterAllBtn, "all"],
    [ideaFilterArticleBtn, "article"],
    [ideaFilterTrendBtn, "trend"],
  ].forEach(([button, value]) => {
    if (!button) return;
    button.classList.toggle("active", state.ideaFilter === value);
  });
}

function updateReminderFilterBar() {
  if (!reminderFilterBar) return;
  const visible = state.collection === "reminders";
  reminderFilterBar.classList.toggle("hidden", !visible);
  if (!visible) return;
  const buttons = [
    [reminderFilterActiveBtn, "active"],
    [reminderFilterDoneBtn, "done"],
    [reminderFilterAllBtn, "all"],
  ];
  buttons.forEach(([button, value]) => {
    if (!button) return;
    button.classList.toggle("active", state.reminderFilter === value);
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

function supportsSortToggle(collection = state.collection) {
  return ["feed", "favorites", "important", "read_later", "notes", "market_tags"].includes(collection);
}

function getNewsSortOrder(collection = state.collection) {
  return state.newsSortOrderByCollection[collection] || "default";
}

function getEffectiveSortDirection(collection = state.collection, sortOrder = getNewsSortOrder(collection)) {
  let ascending = collection === "feed" || collection === "read_later";
  if (sortOrder === "reverse") ascending = !ascending;
  return ascending ? "asc" : "desc";
}

function updateSortOrderButton() {
  if (!sortOrderBtn) return;
  const visible = supportsSortToggle(state.collection);
  sortOrderBtn.classList.toggle("hidden", !visible);
  if (!visible) {
    sortOrderBtn.disabled = false;
    return;
  }
  const direction = getEffectiveSortDirection();
  const label = direction === "asc" ? "当前排序：旧到新，点击切换为新到旧" : "当前排序：新到旧，点击切换为旧到新";
  applyIcon(sortOrderBtn, direction === "asc" ? "sort-asc" : "sort-desc", {
    label,
    tone: getNewsSortOrder() === "reverse" ? "accent" : "default",
  });
}

function updateBatchActionButton() {
  if (
    state.collection === "search" ||
    state.collection === "favorites" ||
    state.collection === "reminders" ||
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

function updateTrackedCreateButton() {
  if (!trackedCreateInlineBtn) return;
  trackedCreateInlineBtn.classList.toggle("hidden", state.collection !== "tracked");
}

function updateCollectionButtons() {
  if (navSearchBtn) navSearchBtn.classList.toggle("active", state.collection === "search");
  navFeedBtn.classList.toggle("active", state.collection === "feed");
  if (navFavoritesBtn) navFavoritesBtn.classList.toggle("active", state.collection === "favorites");
  if (navRemindersBtn) navRemindersBtn.classList.toggle("active", state.collection === "reminders");
  navImportantBtn.classList.toggle("active", state.collection === "important");
  navReadLaterBtn.classList.toggle("active", state.collection === "read_later");
  if (navNotesBtn) navNotesBtn.classList.toggle("active", state.collection === "notes");
  if (navTrackedBtn) navTrackedBtn.classList.toggle("active", state.collection === "tracked");
  if (navMarketTagsBtn) navMarketTagsBtn.classList.toggle("active", state.collection === "market_tags");
  if (navTrendsBtn) navTrendsBtn.classList.toggle("active", state.collection === "trends");
  if (mobileCollectionTriggerBtn) {
    mobileCollectionTriggerBtn.classList.toggle("active", state.collection !== "trends");
    const names = {
      search: "搜索",
      feed: "新闻流",
      favorites: "收藏",
      reminders: reminderNavLabel(),
      important: "重要",
      read_later: "稍后",
      notes: "想法",
      tracked: "跟踪",
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
    mobileTabFilterBtn.classList.toggle("hidden", state.collection === "search" || state.collection === "reminders" || state.collection === "notes" || state.collection === "tracked");
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
  updateIdeaFilterBar();
  updateReminderFilterBar();
  updateTrackedCreateButton();
}

function updateMobileFilterCollectionText() {
  if (!mobileFilterCollection) return;
  const names = {
    search: "搜索",
    feed: "新闻流",
    favorites: "收藏",
    reminders: "提醒",
    important: "重要新闻",
    read_later: "稍后再看",
    notes: "想法",
    tracked: "跟踪",
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
    { key: "read_later", label: "稍后阅读" },
    { key: "important", label: "重要" },
    { key: "reminders", label: reminderNavLabel() },
    { key: "favorites", label: "收藏" },
    { key: "notes", label: "想法" },
    { key: "tracked", label: "跟踪" },
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
  if (!mobileFilterSheet || state.collection === "search" || state.collection === "reminders" || state.collection === "notes" || state.collection === "tracked") return;
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

function selectedTrackedTopic() {
  return state.trackedTopics.find((topic) => String(topic.id) === String(state.selectedTrackedTopicId)) || null;
}

function trackedScopeLabel(topic) {
  return topic?.scope === "all" ? "全部新闻增量" : "重要新闻增量";
}

function trackedRuleList(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function trackedRuleSummary(topic) {
  const rules = topic?.rules || {};
  const strong = trackedRuleList(rules.strong_phrases);
  const core = trackedRuleList(rules.core_terms);
  const context = trackedRuleList(rules.context_terms);
  const exclude = trackedRuleList(rules.exclude_terms);
  const bits = [];
  if (strong.length) bits.push(`强短语：${strong.join(" / ")}`);
  if (core.length) bits.push(`核心词：${core.join(" / ")}`);
  if (context.length) bits.push(`场景词：${context.join(" / ")}`);
  if (exclude.length) bits.push(`排除：${exclude.join(" / ")}`);
  bits.push(`阈值：${Number(rules.threshold || 0) || 6}`);
  return bits.join(" · ");
}

function trackedKeywordSummary(topic) {
  return trackedRuleSummary(topic);
}

function trackedDescriptionSummary(topic) {
  const strong = trackedRuleList(topic?.rules?.strong_phrases);
  const core = trackedRuleList(topic?.rules?.core_terms);
  if (strong.length) return `强短语：${strong.join(" / ")}`;
  return core.length ? `核心词：${core.join(" / ")}` : "还没有规则说明";
}

function renderTrackedTopicsList() {
  newsList.querySelectorAll(".news-item, .date-section").forEach((node) => node.remove());
  lastRenderedDateKey = null;
  state.trackedTopics.forEach((topic) => {
    const row = document.createElement("li");
    row.className = "news-item tracked-list-item";
    row.dataset.topicId = String(topic.id);
    if (String(topic.id) === String(state.selectedTrackedTopicId)) row.classList.add("selected");

    const titleRow = document.createElement("div");
    titleRow.className = "row-top";

    const title = document.createElement("div");
    title.className = "row-title";
    title.textContent = topic.title || "未命名主题";
    titleRow.appendChild(title);

    const badge = document.createElement("span");
    badge.className = `tracked-topic-badge ${Number(topic.active || 0) === 1 ? "active" : "muted"}`;
    badge.textContent = Number(topic.active || 0) === 1 ? "启用中" : "已停用";
    titleRow.appendChild(badge);
    row.appendChild(titleRow);

    const summary = document.createElement("div");
    summary.className = "row-summary";
    summary.textContent = trackedDescriptionSummary(topic);
    row.appendChild(summary);

    const metaLine = document.createElement("div");
    metaLine.className = "row-meta";
    const updatedAt = topic.updated_at ? String(topic.updated_at).replace("T", " ").slice(0, 16) : "未知";
    metaLine.textContent = `${trackedScopeLabel(topic)} · 命中 ${Number(topic.visible_item_count || 0)} · 更新 ${updatedAt}`;
    row.appendChild(metaLine);

    row.addEventListener("click", async () => {
      await openTrackedTopicDetailById(topic.id);
    });
    if (listHint && listHint.parentElement === newsList) {
      newsList.insertBefore(row, listHint);
    } else {
      newsList.appendChild(row);
    }
  });
}

function buildTrackedTimelineRow(item) {
  const row = document.createElement("div");
  row.className = "tracked-timeline-row";

  const main = document.createElement("button");
  main.type = "button";
  main.className = "tracked-timeline-main";

  const title = document.createElement("div");
  title.className = "tracked-timeline-title";
  title.textContent = item.title || "未命名新闻";
  main.appendChild(title);

  const metaLine = document.createElement("div");
  metaLine.className = "tracked-timeline-meta";
  const reason = item.tracked_reason || (item.tracked_match_method === "manual" ? "手动加入" : "规则命中");
  metaLine.textContent = `${item.published_at || item.date_key || ""} · ${item.source || ""} · ${reason}`;
  main.appendChild(metaLine);

  if (item.summary) {
    const summary = document.createElement("div");
    summary.className = "tracked-timeline-summary";
    summary.textContent = item.summary;
    main.appendChild(summary);
  }

  main.addEventListener("click", async () => {
    await openItemDetail(item, { fromTrackedTopicId: state.selectedTrackedTopicId });
  });

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "detail-retry-btn";
  removeBtn.textContent = "移除";
  removeBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (!topic) return;
    const ok = window.confirm(`从“${topic.title}”移除这条新闻？`);
    if (!ok) return;
    await setTrackedTopicItemHidden(topic.id, item.id, true);
    await loadTrackedTopicTimeline(topic.id);
    setHint("已从当前跟踪主题移除");
  });

  row.appendChild(main);
  row.appendChild(removeBtn);
  return row;
}

function trackedDailySummaryStatusLabel(day) {
  if (day?.status === "success") return "已生成";
  if (day?.status === "stale") return "已过期";
  if (day?.status === "failed") return "生成失败";
  return "未生成";
}

function renderTrackedViewSwitch() {
  if (trackedViewTimelineBtn) trackedViewTimelineBtn.classList.toggle("active", state.trackedDetailView === "timeline");
  if (trackedViewTimeflowBtn) trackedViewTimeflowBtn.classList.toggle("active", state.trackedDetailView === "timeflow");
}

function buildTrackedTimeflowRow(day) {
  const row = document.createElement("div");
  row.className = "tracked-timeflow-row";

  const axis = document.createElement("div");
  axis.className = "tracked-timeflow-axis";

  const date = document.createElement("div");
  date.className = "tracked-timeflow-date";
  date.textContent = day.date || "未知日期";
  axis.appendChild(date);

  const dot = document.createElement("div");
  dot.className = "tracked-timeflow-dot";
  axis.appendChild(dot);

  const body = document.createElement("div");
  body.className = "tracked-timeflow-body";

  const meta = document.createElement("div");
  meta.className = "tracked-timeflow-meta";
  meta.textContent = `${trackedDailySummaryStatusLabel(day)} · ${Number(day.item_count || 0)} 条新闻`;
  body.appendChild(meta);

  if (day.summary_text) {
    const summary = document.createElement("div");
    summary.className = "tracked-timeflow-summary";
    summary.textContent = day.summary_text;
    body.appendChild(summary);
  } else {
    const empty = document.createElement("div");
    empty.className = "tracked-timeflow-summary muted";
    empty.textContent = day.status === "failed" ? "上次生成失败，可重试。" : "当前还没有生成这一天的时间流总结。";
    body.appendChild(empty);
  }

  if (day.error && day.status === "failed") {
    const error = document.createElement("div");
    error.className = "tracked-timeflow-error";
    error.textContent = `失败原因：${day.error}`;
    body.appendChild(error);
  }

  const actions = document.createElement("div");
  actions.className = "tracked-timeflow-actions";

  const generateBtn = document.createElement("button");
  generateBtn.type = "button";
  generateBtn.className = "detail-retry-btn";
  generateBtn.textContent = day.status === "stale" ? "重新生成" : "生成当日总结";
  if (day.status === "success") generateBtn.textContent = "重新生成";
  generateBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (!topic) return;
    generateBtn.disabled = true;
    try {
      await generateTrackedTopicDailySummary(topic.id, day.date);
      await loadTrackedTopicDailySummaries(topic.id);
      setHint(`已生成 ${day.date} 的时间流总结`);
    } catch (error) {
      setHint(`时间流总结生成失败：${error?.message || error}`);
      await loadTrackedTopicDailySummaries(topic.id).catch(() => {});
    } finally {
      generateBtn.disabled = false;
    }
  });
  actions.appendChild(generateBtn);
  body.appendChild(actions);

  const details = document.createElement("details");
  details.className = "tracked-timeflow-details";
  const summaryToggle = document.createElement("summary");
  summaryToggle.textContent = `展开原始新闻 ${Number(day.item_count || 0)} 条`;
  details.appendChild(summaryToggle);

  const list = document.createElement("div");
  list.className = "tracked-timeflow-items";
  (Array.isArray(day.items) ? day.items : []).forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tracked-timeflow-item";
    button.textContent = `${item.published_at || ""} · ${item.title || "未命名新闻"}`;
    button.addEventListener("click", async () => {
      const matched = state.trackedTimelineItems.find((row) => String(row.id) === String(item.id));
      if (matched) {
        await openItemDetail(matched, { fromTrackedTopicId: state.selectedTrackedTopicId });
      }
    });
    list.appendChild(button);
  });
  details.appendChild(list);
  body.appendChild(details);

  row.appendChild(axis);
  row.appendChild(body);
  return row;
}

function renderTrackedTopicEmpty(message = "选择一个跟踪主题，右栏会展示详情、回扫和时间线。") {
  closeTagAdminView();
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeTrendNoteEditor();
  closeReminderEditor();
  closeDetailTrackEditor();
  if (detailTrendBody) detailTrendBody.classList.add("hidden");
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  detailEmpty.classList.remove("hidden");
  detailEmpty.textContent = message;
  updateWorkspaceLayout();
}

function renderTrackedTopicDetail(topic, items = state.trackedTimelineItems) {
  if (!detailTrackedBody || !trackedTimelineList) return;
  if (!topic) {
    renderTrackedTopicEmpty();
    return;
  }

  closeTagAdminView();
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeTrendNoteEditor();
  closeReminderEditor();
  closeDetailTrackEditor();
  detailEmpty.classList.add("hidden");
  if (detailTrendBody) detailTrendBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  detailTrackedBody.classList.remove("hidden");
  detailTrackedTitle.textContent = topic.title || "未命名主题";
  detailTrackedMeta.textContent = `${trackedScopeLabel(topic)} · 可见 ${Number(topic.visible_item_count || 0)} · 隐藏 ${Number(topic.hidden_item_count || 0)}`;
  detailTrackedKeywords.textContent = trackedDescriptionSummary(topic);
  if (trackedBackfillModeSelect) trackedBackfillModeSelect.value = state.trackedBackfillMode;
  renderTrackedViewSwitch();
  trackedTimelineList.innerHTML = "";
  if (state.trackedDetailView === "timeflow") {
    if (state.trackedDailySummaries.length) {
      trackedTimelineHint.textContent = `时间流按日期新→旧展示；需手动逐日生成或重新生成。共 ${state.trackedDailySummaries.length} 天。`;
      state.trackedDailySummaries.forEach((day) => trackedTimelineList.appendChild(buildTrackedTimeflowRow(day)));
    } else {
      trackedTimelineHint.textContent = items.length
        ? "当前主题已有原始新闻，但还没有任何时间流总结。可逐日点击“生成当日总结”。"
        : "当前主题还没有命中新闻，暂时无法生成时间流总结。";
    }
  } else {
    trackedTimelineHint.textContent = items.length
      ? `时间线按新闻发布时间新→旧，共 ${items.length} 条`
      : "当前主题还没有命中新闻。可先执行历史回扫，或从新闻详情里手动加入。";
    items.forEach((item) => trackedTimelineList.appendChild(buildTrackedTimelineRow(item)));
  }
  updateWorkspaceLayout();
  openDetailOnMobile();
}

async function loadTrackedTopicTimeline(topicId) {
  const data = await fetchTrackedTopicItems(topicId);
  state.trackedTimelineItems = Array.isArray(data.items) ? data.items : [];
  if (state.trackedDetailView === "timeflow") {
    const daily = await fetchTrackedTopicDailySummaries(topicId);
    state.trackedDailySummaries = Array.isArray(daily.days) ? daily.days : [];
  } else {
    state.trackedDailySummaries = [];
  }
  if (data.topic) {
    state.trackedTopics = state.trackedTopics.map((topic) => String(topic.id) === String(data.topic.id) ? data.topic : topic);
  }
  renderTrackedTopicsList();
  renderTrackedTopicDetail(data.topic, state.trackedTimelineItems);
  renderMeta();
}

async function loadTrackedTopicDailySummaries(topicId) {
  const data = await fetchTrackedTopicDailySummaries(topicId);
  state.trackedDailySummaries = Array.isArray(data.days) ? data.days : [];
  if (data.topic) {
    state.trackedTopics = state.trackedTopics.map((topic) => String(topic.id) === String(data.topic.id) ? data.topic : topic);
  }
  renderTrackedTopicsList();
  renderTrackedTopicDetail(data.topic || selectedTrackedTopic(), state.trackedTimelineItems);
  renderMeta();
}

function fillTrackedTopicForm(topic = null) {
  if (!detailTrackedTitleInput) return;
  const rules = topic?.rules || {};
  const ruleNumber = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };
  detailTrackedTitleInput.value = topic?.title || "";
  detailTrackedStrongInput.value = trackedRuleList(rules.strong_phrases).join(", ");
  detailTrackedCoreInput.value = trackedRuleList(rules.core_terms).join(", ");
  detailTrackedContextInput.value = trackedRuleList(rules.context_terms).join(", ");
  detailTrackedExcludeInput.value = trackedRuleList(rules.exclude_terms).join(", ");
  detailTrackedThresholdInput.value = String(ruleNumber(rules.threshold, 6));
  detailTrackedTitleWeightInput.value = String(ruleNumber(rules.title_weight, 1));
  detailTrackedNoteWeightInput.value = String(ruleNumber(rules.note_weight, 1));
  detailTrackedSummaryWeightInput.value = String(ruleNumber(rules.summary_weight, 1));
  detailTrackedContentWeightInput.value = String(ruleNumber(rules.content_weight, 1));
  detailTrackedStrongScoreInput.value = String(ruleNumber(rules.strong_score, 1));
  detailTrackedCoreScoreInput.value = String(ruleNumber(rules.core_score, 1));
  detailTrackedContextScoreInput.value = String(ruleNumber(rules.context_score, 1));
  detailTrackedExcludePenaltyInput.value = String(ruleNumber(rules.exclude_penalty, 1));
  detailTrackedScopeSelect.value = topic?.scope || "important";
  detailTrackedActiveInput.checked = Number(topic?.active ?? 1) === 1;
}

function openTrackedTopicForm(mode, topic = null) {
  state.trackedFormMode = mode;
  closeTagAdminView();
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeTrendNoteEditor();
  closeReminderEditor();
  closeDetailTrackEditor();
  detailEmpty.classList.add("hidden");
  if (detailTrendBody) detailTrendBody.classList.add("hidden");
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  detailTrackedFormBody.classList.remove("hidden");
  detailTrackedFormTitle.textContent = mode === "edit" ? "编辑跟踪主题" : "新建跟踪主题";
  detailTrackedFormMeta.textContent = mode === "edit"
    ? "修改规则、增量范围和启用状态；字段说明和打分说明都放在当前编辑页内。"
    : "创建后即可在右栏查看时间线，并可从新闻详情手动加入；先按当前页说明填写规则，再逐步调分。";
  detailTrackedFormBackBtn.classList.toggle("hidden", mode !== "edit" || !topic);
  fillTrackedTopicForm(topic);
  updateWorkspaceLayout();
  openDetailOnMobile();
}

function trackedFormPayload() {
  return {
    title: detailTrackedTitleInput.value.trim(),
    strong_phrases: detailTrackedStrongInput.value.trim(),
    core_terms: detailTrackedCoreInput.value.trim(),
    context_terms: detailTrackedContextInput.value.trim(),
    exclude_terms: detailTrackedExcludeInput.value.trim(),
    threshold: detailTrackedThresholdInput.value.trim(),
    title_weight: detailTrackedTitleWeightInput.value.trim(),
    note_weight: detailTrackedNoteWeightInput.value.trim(),
    summary_weight: detailTrackedSummaryWeightInput.value.trim(),
    content_weight: detailTrackedContentWeightInput.value.trim(),
    strong_score: detailTrackedStrongScoreInput.value.trim(),
    core_score: detailTrackedCoreScoreInput.value.trim(),
    context_score: detailTrackedContextScoreInput.value.trim(),
    exclude_penalty: detailTrackedExcludePenaltyInput.value.trim(),
    scope: detailTrackedScopeSelect.value,
    active: detailTrackedActiveInput.checked,
  };
}

async function openTrackedTopicDetailById(topicId) {
  state.selectedTrackedTopicId = topicId;
  await loadTrackedTopicTimeline(topicId);
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
    favorites: "收藏",
    reminders: "提醒",
    important: "重要新闻",
    read_later: "稍后再看",
    notes: "想法",
    tracked: "跟踪",
    market_tags: "板块",
    trends: "趋势",
  };
  if (state.collection === "trends") {
    meta.textContent = `趋势 · 近 ${state.trendDays} 天 · ${state.trendRows.length} 个板块 · ${state.total} 条标记`;
    pageInfo.textContent = "- / -";
    return;
  }
  if (state.collection === "reminders") {
    meta.textContent = `提醒 · ${reminderFilterLabel()} · 进行中 ${state.reminderSummary.active_total || 0} · 到期 ${state.reminderSummary.due_total || 0} · 已完成 ${state.reminderSummary.done_total || 0}`;
    pageInfo.textContent = "- / -";
    return;
  }
  if (state.collection === "notes") {
    const ideaNames = {
      all: "全部",
      article: "新闻想法",
      trend: "趋势想法",
    };
    meta.textContent = `想法 · ${ideaNames[state.ideaFilter] || "全部"} · 共 ${state.total} 条`;
    pageInfo.textContent = `${state.page} / ${state.pages}`;
    return;
  }
  if (state.collection === "tracked") {
    const topic = selectedTrackedTopic();
    meta.textContent = topic
      ? `跟踪 · ${topic.title} · 共 ${state.trackedTimelineItems.length} 条`
      : `跟踪 · ${state.trackedTopics.length} 个主题`;
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

function setTrendIdeaEditorOpen(open) {
  if (!detailTrendIdeaEditor) return;
  detailTrendIdeaEditor.classList.toggle("hidden", !open);
}

function clearTrendIdeaDetailState() {
  state.selectedTrendIdea = null;
  if (detailTrendIdeaBody) detailTrendIdeaBody.classList.add("hidden");
  setTrendIdeaEditorOpen(false);
}

function emptyDetailMessage() {
  if (state.collection === "trends") return "选择一个趋势单元格查看新闻明细";
  if (state.collection === "notes") return "选择一条想法查看详情";
  return "选择一条新闻查看摘要与正文";
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
  clearTrendIdeaDetailState();
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
  state.selectedTagAdminKey = "";
  if (detailTagAdminBody) {
    detailTagAdminBody.classList.add("hidden");
  }
}

function getSelectedTagAdminItem() {
  if (!state.selectedTagAdminKey) return null;
  return state.marketTagChoices.find((tag) => tag.key === state.selectedTagAdminKey) || null;
}

function renderTagAdminList() {
  if (!detailTagAdminList) return;
  detailTagAdminList.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "detail-tag-admin-grid";

  state.marketTagChoices.forEach((tag) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `detail-tag-admin-card${state.selectedTagAdminKey === tag.key ? " is-active" : ""}`;
    card.setAttribute("aria-pressed", state.selectedTagAdminKey === tag.key ? "true" : "false");
    card.addEventListener("click", () => {
      state.selectedTagAdminKey = state.selectedTagAdminKey === tag.key ? "" : tag.key;
      renderTagAdminList();
    });

    const title = document.createElement("strong");
    title.className = "detail-tag-admin-card-title";
    title.textContent = tag.display_name || tag.key;

    const metaText = document.createElement("span");
    metaText.className = "detail-tag-admin-card-meta";
    metaText.textContent = `新闻 ${Number(tag.item_tag_count || 0)} · 想法 ${Number(tag.trend_note_count || 0)}`;

    card.appendChild(title);
    card.appendChild(metaText);
    grid.appendChild(card);
  });

  detailTagAdminList.appendChild(grid);

  const selectedTag = getSelectedTagAdminItem();
  if (!selectedTag) return;

  const panel = document.createElement("section");
  panel.className = "detail-tag-admin-panel";

  const panelTitle = document.createElement("div");
  panelTitle.className = "detail-tag-admin-panel-title";
  panelTitle.textContent = `选中板块：${selectedTag.display_name || selectedTag.key}`;
  panel.appendChild(panelTitle);

  const renameRow = document.createElement("div");
  renameRow.className = "detail-tag-admin-action-row";

  const renameLabel = document.createElement("span");
  renameLabel.className = "detail-tag-admin-action-label";
  renameLabel.textContent = "重命名";

  const renameInput = document.createElement("input");
  renameInput.type = "text";
  renameInput.className = "detail-tag-admin-input";
  renameInput.value = selectedTag.display_name || selectedTag.key;
  renameInput.maxLength = 40;

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "detail-retry-btn";
  saveBtn.textContent = "保存";
  const syncSaveState = () => {
    const nextName = renameInput.value.trim();
    saveBtn.disabled = !nextName || nextName === (selectedTag.display_name || selectedTag.key);
  };
  syncSaveState();
  renameInput.addEventListener("input", syncSaveState);
  saveBtn.addEventListener("click", async () => {
    const nextName = renameInput.value.trim();
    if (!nextName || nextName === (selectedTag.display_name || selectedTag.key)) return;
    saveBtn.disabled = true;
    renameInput.disabled = true;
    try {
      await updateMarketTagDefinition(selectedTag.key, { display_name: nextName });
      await refreshTrendTagAdminState(selectedTag.key);
    } finally {
      renameInput.disabled = false;
    }
  });

  renameRow.appendChild(renameLabel);
  renameRow.appendChild(renameInput);
  renameRow.appendChild(saveBtn);
  panel.appendChild(renameRow);

  const mergeRow = document.createElement("div");
  mergeRow.className = "detail-tag-admin-action-row";

  const mergeLabel = document.createElement("span");
  mergeLabel.className = "detail-tag-admin-action-label";
  mergeLabel.textContent = "合并到";

  const mergeSelect = document.createElement("select");
  mergeSelect.className = "detail-tag-admin-input";
  const mergePlaceholder = document.createElement("option");
  mergePlaceholder.value = "";
  mergePlaceholder.textContent = "选择目标板块";
  mergeSelect.appendChild(mergePlaceholder);
  state.marketTagChoices
    .filter((candidate) => candidate.key !== selectedTag.key)
    .forEach((candidate) => {
      const option = document.createElement("option");
      option.value = candidate.key;
      option.textContent = candidate.display_name || candidate.key;
      mergeSelect.appendChild(option);
    });

  const mergeBtn = document.createElement("button");
  mergeBtn.type = "button";
  mergeBtn.className = "detail-retry-btn";
  mergeBtn.textContent = "合并";
  mergeBtn.disabled = true;
  mergeSelect.addEventListener("change", () => {
    mergeBtn.disabled = !mergeSelect.value;
  });
  mergeBtn.addEventListener("click", async () => {
    const targetKey = mergeSelect.value || "";
    if (!targetKey) return;
    const target = state.marketTagChoices.find((candidate) => candidate.key === targetKey);
    const ok = window.confirm(
      `确认将“${selectedTag.display_name || selectedTag.key}”合并到“${target?.display_name || targetKey}”？该板块的新闻关联和趋势想法会迁移到目标板块，旧板块将被删除。`
    );
    if (!ok) return;
    mergeBtn.disabled = true;
    mergeSelect.disabled = true;
    try {
      await mergeMarketTagDefinition(selectedTag.key, targetKey);
      await refreshTrendTagAdminState(targetKey);
    } finally {
      mergeSelect.disabled = false;
    }
  });

  mergeRow.appendChild(mergeLabel);
  mergeRow.appendChild(mergeSelect);
  mergeRow.appendChild(mergeBtn);
  panel.appendChild(mergeRow);

  const dangerZone = document.createElement("div");
  dangerZone.className = "detail-tag-admin-danger";

  const dangerTitle = document.createElement("div");
  dangerTitle.className = "detail-tag-admin-danger-title";
  dangerTitle.textContent = "危险操作";

  const dangerMeta = document.createElement("div");
  dangerMeta.className = "detail-tag-admin-danger-meta";
  dangerMeta.textContent = `删除板块将解除 ${Number(selectedTag.item_tag_count || 0)} 条新闻关联，并删除 ${Number(selectedTag.trend_note_count || 0)} 条板块想法。`;

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "detail-retry-btn detail-tag-admin-danger-btn";
  deleteBtn.textContent = "删除板块";
  deleteBtn.addEventListener("click", async () => {
    deleteBtn.disabled = true;
    try {
      const impact = await fetchMarketTagImpact(selectedTag.key);
      const ok = window.confirm(
        `确认删除“${selectedTag.display_name || selectedTag.key}”？\n将解除 ${impact.affected.item_tag_count} 条新闻关联，并删除 ${impact.affected.trend_note_count} 条板块想法。`
      );
      if (!ok) return;
      await deleteMarketTagDefinition(selectedTag.key);
      await refreshTrendTagAdminState("");
    } finally {
      deleteBtn.disabled = false;
    }
  });

  dangerZone.appendChild(dangerTitle);
  dangerZone.appendChild(dangerMeta);
  dangerZone.appendChild(deleteBtn);
  panel.appendChild(dangerZone);
  detailTagAdminList.appendChild(panel);
}

async function refreshTrendTagAdminState(nextSelectedTagKey = state.selectedTagAdminKey) {
  state.selectedTagAdminKey = nextSelectedTagKey || "";
  await fetchMarketTagDefinitions();
  if (state.selectedTagAdminKey) {
    const exists = state.marketTagChoices.some((tag) => tag.key === state.selectedTagAdminKey);
    if (!exists) state.selectedTagAdminKey = "";
  }
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
  clearTrendIdeaDetailState();
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
  clearTrendIdeaDetailState();
  state.detailReturnToTrend = false;
  syncDetailReturnButton();
  detailBody.classList.add("hidden");
  if (!payload) {
    detailTrendBody.classList.add("hidden");
    detailTrendNoteCard.classList.add("hidden");
    detailTrendList.innerHTML = "";
    detailEmpty.classList.remove("hidden");
    detailEmpty.textContent = emptyDetailMessage();
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
  if ("favorite_at" in patchResult) item.favorite_at = patchResult.favorite_at;
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
    favorite_at: item.favorite_at,
    important_at: item.important_at,
    read_later_at: item.read_later_at,
    has_note: item.has_note,
    has_market_tags: item.has_market_tags,
  };

  const now = new Date().toISOString().slice(0, 19).replace("T", " ");
  const beforeItem = { ...backup };
  if ("read" in payload) item.read_at = payload.read ? now : null;
  if ("favorite" in payload) item.favorite_at = payload.favorite ? now : null;
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
    if (state.collection === "favorites" && "favorite" in payload && !payload.favorite) {
      if (state.selectedId === itemId) {
        state.selectedId = null;
        renderDetail(null);
      }
      await loadFirstPage();
      return;
    }
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
    item.favorite_at = backup.favorite_at;
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
  if (open) {
    closeMarketPicker();
    closeReminderEditor();
    closeDetailTrackEditor();
  }
  detailNoteEditor.classList.toggle("hidden", !open);
}

function canReturnToTrendDetail() {
  return !!(state.detailReturnToTrend && state.trendSelection?.detailPayload);
}

function canReturnToTrackedTopic() {
  return !!state.detailReturnToTrackedTopicId;
}

function syncDetailReturnButton() {
  if (!detailReturnToTrendBtn) return;
  detailReturnToTrendBtn.classList.toggle("hidden", !canReturnToTrendDetail());
  if (detailReturnToTrackedBtn) {
    detailReturnToTrackedBtn.classList.toggle("hidden", !canReturnToTrackedTopic());
  }
}

function restoreTrendDetailFromDetail() {
  if (!canReturnToTrendDetail()) return;
  state.selectedId = null;
  state.detailReturnToTrend = false;
  stopDetailPolling();
  renderTrendDetail(state.trendSelection.detailPayload);
  openDetailOnMobile();
}

async function restoreTrackedTopicFromDetail() {
  if (!canReturnToTrackedTopic()) return;
  const topicId = state.detailReturnToTrackedTopicId;
  state.selectedId = null;
  state.detailReturnToTrackedTopicId = null;
  stopDetailPolling();
  await openTrackedTopicDetailById(topicId);
}

async function openItemDetail(item, { fromTrend = false, fromTrackedTopicId = null } = {}) {
  if (!item) return;
  if (state.selectedId !== item.id) resetDetailChatState();
  state.itemsById.set(item.id, item);
  state.selectedId = item.id;
  state.detailReturnToTrend = fromTrend;
  state.detailReturnToTrackedTopicId = fromTrackedTopicId || null;
  renderDetail(state.itemsById.get(item.id) || item);
  if (!item.snapshotOnly) {
    loadDetail(item.id);
    startDetailPolling(item.id);
    if (!fromTrend) saveReadingCheckpoint(item).catch(() => {});
  }
  openDetailOnMobile();
}

function normalizedDetailNote(cached) {
  const text = cached?.note?.note;
  return typeof text === "string" ? text.trim() : "";
}

function resetDetailChatState({ keepProvider = false } = {}) {
  state.detailView = "detail";
  state.detailChatMessages = [];
  state.detailChatSessionId = "";
  state.detailChatModel = "";
  state.detailChatStatus = "";
  state.detailChatSending = false;
  state.detailChatArchiving = false;
  if (detailChatInput) detailChatInput.value = "";
}

function chatProvidersFromItem(item) {
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  return cached?.chat_providers || {};
}

function currentCodexChatModel() {
  return (state.runtimeSettings?.llm?.codex_chat?.model || "").trim();
}

function chatModelLabel(meta) {
  const model = (meta?.model || currentCodexChatModel()).trim();
  return model || "Codex 默认模型";
}

function parseKeyPoints(raw) {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.map((point) => (typeof point === "string" ? point.trim() : "")).filter(Boolean)
      : [];
  } catch {
    return [];
  }
}

function fallbackProviderFromAi(ai) {
  if (!ai?.raw_json) return "";
  try {
    return (JSON.parse(ai.raw_json || "{}")?.provider || "").trim();
  } catch {
    return "";
  }
}

function isCodexFallbackAi(ai) {
  const provider = fallbackProviderFromAi(ai);
  return provider.startsWith("codex-fallback") || (ai?.model || "") === "codex-fallback";
}

function renderDetailChatMeta(item, codexMeta) {
  if (!detailChatMeta) return;
  detailChatMeta.innerHTML = "";

  const source = document.createElement("span");
  source.className = "detail-chat-source";
  source.textContent = item.source || "未知来源";
  detailChatMeta.appendChild(source);

  const modelBadge = document.createElement("span");
  modelBadge.className = `detail-chat-model-badge ${codexMeta.available ? "ok" : "failed"}`;
  modelBadge.textContent = `● ${chatModelLabel(codexMeta)}`;
  detailChatMeta.appendChild(modelBadge);
}

function renderDetailChatKeyPoints(item) {
  if (!detailChatCapability) return;
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  const points = parseKeyPoints(cached?.ai?.key_points_zh).slice(0, 4);
  if (!points.length) {
    detailChatCapability.textContent = "";
    detailChatCapability.classList.add("hidden");
    return;
  }
  detailChatCapability.textContent = points.join(" · ");
  detailChatCapability.classList.remove("hidden");
}

function renderDetailChat(item) {
  if (!item) return;
  const providers = chatProvidersFromItem(item);
  const codexMeta = providers.codex || { available: true, model: currentCodexChatModel() };
  const chatEnabled = !!codexMeta.available;
  const archiveEnabled = chatEnabled
    && !state.detailChatSending
    && !state.detailChatArchiving
    && state.detailChatMessages.some((message) => message.role === "assistant");

  renderDetailChatMeta(item, codexMeta);
  renderDetailChatKeyPoints(item);
  detailChatInput.disabled = state.detailChatSending || state.detailChatArchiving || !chatEnabled;
  detailChatSendBtn.disabled = state.detailChatSending || state.detailChatArchiving || !chatEnabled;
  if (detailChatArchiveBtn) {
    detailChatArchiveBtn.disabled = !archiveEnabled;
  }
  detailChatInput.placeholder = chatEnabled
    ? "围绕这条新闻继续追问，例如：这件事对相关公司/板块意味着什么？"
    : "Codex chat 当前不可用。";

  const chatReady = !!(state.detailChatMessages && state.detailChatMessages.length);
  const statusText = state.detailChatStatus || (chatReady ? "" : (chatEnabled ? "" : "Codex chat 当前不可用。"));
  detailChatStatus.textContent = statusText;
  detailChatStatus.className = `detail-status ${state.detailChatSending ? "pending" : statusText ? "muted" : "hidden"}`;

  detailChatMessages.innerHTML = "";
  if (!chatReady) {
    const empty = document.createElement("div");
    empty.className = "detail-chat-empty";
    empty.textContent = chatEnabled
      ? "围绕正文继续追问。"
      : "Codex chat 当前不可用。";
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

async function requestNewsChat(item, requestPayload) {
  const res = await fetch(`/api/news/${encodeURIComponent(item.id)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestPayload),
  });
  const payload = await res.json().catch(() => ({ ok: false, error: "chat_request_failed" }));
  if (!res.ok || !payload.ok) {
    const err = new Error(payload.error || "chat_request_failed");
    err.detail = payload.detail || "";
    throw err;
  }
  return payload;
}

async function archiveNewsChat(item, requestPayload) {
  const res = await fetch(`/api/news/${encodeURIComponent(item.id)}/chat/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestPayload),
  });
  const payload = await res.json().catch(() => ({ ok: false, error: "archive_request_failed" }));
  if (!res.ok || !payload.ok) {
    const err = new Error(payload.error || "archive_request_failed");
    err.detail = payload.detail || "";
    throw err;
  }
  return payload;
}

async function sendDetailChatMessage() {
  if (!state.selectedId || state.detailChatSending) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  const content = (detailChatInput.value || "").trim().slice(0, DETAIL_CHAT_MAX_LEN);
  if (!content) return;
  const configuredModel = currentCodexChatModel();
  const reset = !!state.detailChatSessionId && !!state.detailChatModel && configuredModel !== state.detailChatModel;
  if (reset) {
    state.detailChatMessages = [];
    state.detailChatSessionId = "";
    state.detailChatStatus = "Codex chat 模型已切换，已为你重新开始一轮对话。";
  }

  state.detailChatMessages = [...state.detailChatMessages, { role: "user", content }];
  state.detailChatSending = true;
  state.detailChatStatus = "正在生成回答...";
  detailChatInput.value = "";
  renderDetailChat(item);

  try {
    const payload = await requestNewsChat(item, {
      question: content,
      session_id: state.detailChatSessionId,
      model: configuredModel,
      reset,
    });
    state.detailChatMessages = [...state.detailChatMessages, { role: "assistant", content: payload.answer || "" }];
    state.detailChatSessionId = payload.session_id || "";
    state.detailChatModel = configuredModel;
    state.detailChatStatus = `${payload.provider === "codex" ? "Codex" : "助手"} · ${payload.model || "默认模型"}`.trim();
  } catch (error) {
    const code = error instanceof Error ? error.message : "chat_request_failed";
    const labelMap = {
      detail_not_ready: "正文还没准备好，暂时不能提问。",
      provider_busy: "该模型当前正忙，请稍后重试。",
      provider_timeout: "请求超时，请稍后重试。",
      provider_failed: "Codex 调用失败，请稍后重试。",
      session_invalid: "上轮对话 session 已失效，请重新开始。",
      missing_session_id: "Codex 没有返回可继续对话的 session id，请重试。",
      empty_answer: "Codex 没有返回有效回答，请重试。",
    };
    if (code === "session_invalid") {
      state.detailChatSessionId = "";
      state.detailChatModel = "";
      state.detailChatMessages = state.detailChatMessages.slice(0, -1);
    }
    state.detailChatStatus = labelMap[code] || "发送失败，请稍后重试。";
  } finally {
    state.detailChatSending = false;
    renderDetailChat(item);
  }
}

async function archiveDetailChat() {
  if (!state.selectedId || state.detailChatSending || state.detailChatArchiving) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  if (!state.detailChatMessages.some((message) => message.role === "assistant")) return;

  const configuredModel = currentCodexChatModel();
  state.detailChatArchiving = true;
  state.detailChatStatus = "正在归档到想法...";
  renderDetailChat(item);

  try {
    const payload = await archiveNewsChat(item, {
      messages: state.detailChatMessages,
      model: configuredModel,
    });
    const cached = item.url ? (state.detailCacheByUrl.get(item.url) || {}) : {};
    cached.has_note = payload.has_note;
    cached.note = payload.note;
    cached.note_preview = payload.note_preview || "";
    if (item.url) state.detailCacheByUrl.set(item.url, cached);
    item.has_note = payload.has_note;
    item.note_preview = payload.note_preview || "";
    state.itemsById.set(item.id, item);
    rerenderOne(item.id);
    refreshDetailNoteUI(item);
    state.detailChatStatus = "已归档到想法。";
  } catch (error) {
    const code = error instanceof Error ? error.message : "archive_request_failed";
    const labelMap = {
      empty_archive_source: "没有可归档回答。",
      empty_archive_summary: "没有生成可归档结论。",
      invalid_archive_summary: "归档结果无效，请重试。",
      note_too_long: "想法过长，无法追加归档。",
      provider_busy: "Codex 当前正忙，请稍后重试。",
      provider_timeout: "归档超时，请稍后重试。",
      provider_failed: "Codex 归档失败，请稍后重试。",
    };
    state.detailChatStatus = labelMap[code] || "归档失败，请稍后重试。";
  } finally {
    state.detailChatArchiving = false;
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
    favorite_at: item.favorite_at,
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
  if ("favorite_at" in payload) item.favorite_at = payload.favorite_at;
  if ("important_at" in payload && payload.important_at) item.important_at = payload.important_at;
  state.itemsById.set(item.id, item);
  adjustDateCountForScopeTransition(beforeItem, item);
  rerenderOne(item.id);
}

async function deleteMarketTag(item, tag) {
  const beforeItem = {
    date_key: item.date_key,
    read_at: item.read_at,
    favorite_at: item.favorite_at,
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
    favorite_at: item.favorite_at,
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

function currentDetailReminders(item) {
  if (item?.snapshotOnly && state.selectedReminderId) {
    const selected = state.reminderItems.find((reminder) => reminder.id === state.selectedReminderId);
    return selected ? [selected] : [];
  }
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  return Array.isArray(cached?.reminders) ? cached.reminders : [];
}

function currentDetailReminderSummary(item) {
  if (item?.snapshotOnly) {
    const reminders = currentDetailReminders(item);
    return {
      total: reminders.length,
      active_total: reminders.filter((reminder) => reminder.status === "active").length,
      due_total: reminders.filter((reminder) => reminder.is_due).length,
      done_total: reminders.filter((reminder) => reminder.status === "done").length,
      dismissed_total: reminders.filter((reminder) => reminder.status === "dismissed").length,
    };
  }
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  return cached?.reminder_summary || {
    total: 0,
    active_total: 0,
    due_total: 0,
    done_total: 0,
    dismissed_total: 0,
  };
}

function closeReminderEditor() {
  state.selectedReminderDraftId = null;
  if (detailReminderEditor) detailReminderEditor.classList.add("hidden");
  if (detailReminderEventTitleText) detailReminderEventTitleText.textContent = "";
  if (detailReminderEventDateInput) detailReminderEventDateInput.value = "";
  if (detailReminderNoteInput) detailReminderNoteInput.value = "";
  if (detailReminderDeleteBtn) detailReminderDeleteBtn.classList.add("hidden");
  if (detailReminderEditorTitle) detailReminderEditorTitle.textContent = "添加提醒";
}

function openReminderEditor(item, reminder = null) {
  if (!detailReminderEditor || !item) return;
  setDetailNoteEditorOpen(false);
  closeMarketPicker();
  closeDetailTrackEditor();
  state.selectedReminderDraftId = reminder?.id || null;
  if (detailReminderEditorTitle) {
    detailReminderEditorTitle.textContent = reminder ? "编辑提醒" : "添加提醒";
  }
  if (detailReminderEventTitleText) {
    detailReminderEventTitleText.textContent = `关联新闻：${item.title || reminder?.event_title || ""}`;
  }
  detailReminderEventDateInput.value = reminder?.event_date || item.date_key || "";
  detailReminderNoteInput.value = reminder?.note || "";
  detailReminderDeleteBtn.classList.toggle("hidden", !reminder);
  detailReminderEditor.classList.remove("hidden");
}

function refreshDetailReminderUI(item) {
  if (!detailReminderCard || !detailReminderList || !detailReminderSummary) return;
  const reminders = normalizeReminderItems(currentDetailReminders(item));
  const summary = currentDetailReminderSummary(item);
  detailReminderSummary.textContent = `进行中 ${summary.active_total || 0} · 到期 ${summary.due_total || 0} · 已完成 ${summary.done_total || 0}`;
  detailReminderList.innerHTML = "";
  if (!reminders.length) {
    detailReminderCard.classList.add("hidden");
    return;
  }
  reminders.forEach((reminder) => {
    const card = document.createElement("div");
    card.className = "detail-reminder-item";
    if (state.selectedReminderId === reminder.id) card.classList.add("active");
    if (reminder.status === "done") card.classList.add("done");

    const meta = document.createElement("div");
    meta.className = "detail-reminder-item-meta";
    meta.textContent = `${reminderStatusLabel(reminder.status)} · 事件日 ${reminder.event_date} · 提醒 ${formatReminderDateTime(reminder.remind_at)}`;
    if (reminder.is_due) meta.classList.add("due");

    card.appendChild(meta);
    if (reminder.note) {
      const note = document.createElement("div");
      note.className = "detail-reminder-item-note";
      if (reminder.status === "done") note.classList.add("done");
      note.textContent = reminder.note;
      card.appendChild(note);
    }

    const actions = document.createElement("div");
    actions.className = "detail-note-actions";

    if (reminder.status !== "done") {
      const doneBtn = document.createElement("button");
      doneBtn.className = "detail-retry-btn";
      doneBtn.type = "button";
      doneBtn.textContent = "标记完成";
      doneBtn.addEventListener("click", async (event) => {
        event.stopPropagation();
        const current = state.itemsById.get(state.selectedId);
        if (!current) return;
        await saveReminderDraft(current, reminder.id, { status: "done" });
      });
      actions.appendChild(doneBtn);
    }

    if (reminder.status !== "active") {
      const reopenBtn = document.createElement("button");
      reopenBtn.className = "detail-retry-btn";
      reopenBtn.type = "button";
      reopenBtn.textContent = "重新激活";
      reopenBtn.addEventListener("click", async (event) => {
        event.stopPropagation();
        const current = state.itemsById.get(state.selectedId);
        if (!current) return;
        await saveReminderDraft(current, reminder.id, { status: "active" });
      });
      actions.appendChild(reopenBtn);
    }

    const editBtn = document.createElement("button");
    editBtn.className = "detail-retry-btn";
    editBtn.type = "button";
    editBtn.textContent = "编辑";
    editBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      openReminderEditor(item, reminder);
    });
    actions.appendChild(editBtn);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "detail-retry-btn";
    deleteBtn.type = "button";
    deleteBtn.textContent = "删除";
    deleteBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      const current = state.itemsById.get(state.selectedId);
      if (!current) return;
      if (!window.confirm("确认删除这个提醒？")) return;
      await removeReminderDraft(current, reminder.id);
    });
    actions.appendChild(deleteBtn);

    card.appendChild(actions);
    card.addEventListener("click", () => {
      state.selectedReminderId = reminder.id;
      refreshDetailReminderUI(item);
    });
    detailReminderList.appendChild(card);
  });
  detailReminderCard.classList.remove("hidden");
}

function closeDetailTrackEditor() {
  if (detailTrackEditor) detailTrackEditor.classList.add("hidden");
  if (detailTrackTopicSelect) detailTrackTopicSelect.innerHTML = "";
  if (detailTrackEditorMeta) {
    detailTrackEditorMeta.textContent = "选择现有主题，把当前新闻加入时间线。";
  }
}

async function currentDetailTrackedTopicChoices(item) {
  if (!item || item.snapshotOnly || !item.id) return [];
  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  if (Array.isArray(cached?.tracked_topic_choices)) return cached.tracked_topic_choices;
  const payload = await fetchDetail(item.id);
  if (!payload?.ok) return [];
  if (item.url) {
    const nextCached = { ...(state.detailCacheByUrl.get(item.url) || {}) };
    nextCached.tracked_topic_choices = Array.isArray(payload.tracked_topic_choices) ? payload.tracked_topic_choices : [];
    state.detailCacheByUrl.set(item.url, nextCached);
  }
  return Array.isArray(payload.tracked_topic_choices) ? payload.tracked_topic_choices : [];
}

async function openDetailTrackEditor(item) {
  if (!detailTrackEditor || !detailTrackTopicSelect || !item) return;
  setDetailNoteEditorOpen(false);
  closeMarketPicker();
  closeReminderEditor();
  const choices = await currentDetailTrackedTopicChoices(item);
  detailTrackTopicSelect.innerHTML = "";
  if (!choices.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "暂无可用跟踪主题";
    detailTrackTopicSelect.appendChild(option);
    detailTrackTopicSelect.disabled = true;
    detailTrackSaveBtn.disabled = true;
    if (detailTrackEditorMeta) {
      detailTrackEditorMeta.textContent = "还没有可加入的主题。先进入“跟踪”集合，点击“新建跟踪”创建一个。";
    }
  } else {
    detailTrackTopicSelect.disabled = false;
    detailTrackSaveBtn.disabled = false;
    choices.forEach((topic) => {
      const option = document.createElement("option");
      option.value = String(topic.id);
      option.textContent = topic.title || `主题 ${topic.id}`;
      detailTrackTopicSelect.appendChild(option);
    });
    const selected = choices.find((topic) => String(topic.id) === String(state.selectedTrackedTopicId));
    if (selected) detailTrackTopicSelect.value = String(selected.id);
    if (detailTrackEditorMeta) {
      detailTrackEditorMeta.textContent = "选择现有主题，把当前新闻加入时间线。";
    }
  }
  detailTrackEditor.classList.remove("hidden");
}

async function saveReminderDraft(item, reminderId = null, overridePayload = null) {
  if (!item) return;
  const payload = overridePayload || {
    event_title: (item.title || "").trim(),
    event_date: detailReminderEventDateInput.value,
    remind_at: reminderDateToDefaultRemindAt(detailReminderEventDateInput.value),
    note: detailReminderNoteInput.value.trim(),
  };
  const result = reminderId
    ? await updateReminder(reminderId, payload)
    : await createReminder(item.id, payload);
  applyReminderSummary(result.summary || state.reminderSummary);
  state.selectedReminderId = result.reminder?.id || state.selectedReminderId;
  closeReminderEditor();
  if (item.snapshotOnly) return;
  await loadDetail(item.id);
  if (state.collection === "reminders") await loadFirstPage();
}

async function removeReminderDraft(item, reminderId) {
  if (!item || !reminderId) return;
  const result = await deleteReminder(reminderId);
  applyReminderSummary(result.summary || state.reminderSummary);
  if (state.selectedReminderId === reminderId) state.selectedReminderId = null;
  closeReminderEditor();
  if (!item.snapshotOnly) await loadDetail(item.id);
  if (state.collection === "reminders") await loadFirstPage();
}

function buildReminderListRow(reminder) {
  const li = document.createElement("li");
  li.className = "news-item reminder-item";
  li.dataset.id = String(reminder.id);
  if (state.selectedReminderId === reminder.id) li.classList.add("selected");
  if (reminder.status === "done") li.classList.add("done");

  const line1 = document.createElement("div");
  line1.className = "line1";
  const status = document.createElement("span");
  status.className = "note-badge reminder-badge";
  status.textContent = reminder.is_due ? "已到期" : reminderStatusLabel(reminder.status);
  if (reminder.is_due) status.classList.add("due");
  line1.appendChild(status);

  const text = document.createElement("span");
  text.className = "line1-text";
  text.textContent = `${formatReminderDateTime(reminder.remind_at)} · 事件日 ${reminder.event_date}`;
  line1.appendChild(text);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = reminder.item_title_snapshot || reminder.event_title || "关联新闻";

  const summary = document.createElement("p");
  summary.className = "summary";
  const summaryParts = [];
  if (reminder.item?.source) {
    summaryParts.push(reminder.item.source);
  }
  if (reminder.note) {
    summaryParts.push(reminder.note);
  }
  summary.textContent = summaryParts.join(" · ") || "无备注";

  li.appendChild(line1);
  li.appendChild(title);
  li.appendChild(summary);
  if (reminder.note) {
    const note = document.createElement("p");
    note.className = "row-note-preview";
    note.textContent = reminder.note;
    li.appendChild(note);
  }
  li.addEventListener("click", async () => {
    await openReminderCard(reminder);
  });
  return li;
}

async function openReminderCard(reminder) {
  if (!reminder) return;
  state.selectedReminderId = reminder.id;
  if (reminder.item) {
    openItemDetail(reminder.item);
    return;
  }
  const pseudoItem = {
    id: `reminder-snapshot-${reminder.id}`,
    title: reminder.item_title_snapshot || reminder.event_title || "提醒快照",
    summary: reminder.note || "原新闻已不在当前索引中，仅保留提醒快照。",
    url: reminder.item_url_snapshot || "",
    source: "提醒快照",
    published_at: reminder.event_date || "",
    date_key: reminder.event_date || "",
    date_label: reminder.event_date || "",
    snapshotOnly: true,
    active_reminder_count: reminder.status === "active" ? 1 : 0,
    due_reminder_count: reminder.is_due ? 1 : 0,
    favorite_at: null,
    important_at: null,
    read_later_at: null,
    has_note: 0,
    has_market_tags: 0,
  };
  openItemDetail(pseudoItem);
}

function renderDetail(item) {
  closeTagAdminView();
  clearTrendIdeaDetailState();
  if (!item) {
    resetDetailChatState({ keepProvider: true });
    state.detailReturnToTrend = false;
    state.detailReturnToTrackedTopicId = null;
    stopDetailPolling();
    closeMarketPicker();
    closeReminderEditor();
    closeDetailTrackEditor();
    if (detailReminderCard) detailReminderCard.classList.add("hidden");
    syncDetailReturnButton();
    detailTrendBody.classList.add("hidden");
    if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
    if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
    detailBody.classList.add("hidden");
    detailChatBody.classList.add("hidden");
    detailEmpty.classList.remove("hidden");
    detailEmpty.textContent = emptyDetailMessage();
    updateWorkspaceLayout();
    return;
  }
  detailTrendBody.classList.add("hidden");
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
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
  const fallbackProvider = fallbackProviderFromAi(ai);
  const isCodexFallback = isCodexFallbackAi(ai);
  const isCodexFallbackBodyOnly = fallbackProvider === "codex-fallback-body-only";

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
  closeReminderEditor();
  closeDetailTrackEditor();

  if (item.snapshotOnly) {
    statusEl.textContent = "原新闻已不在当前索引中，仅保留提醒快照。";
    statusEl.className = "detail-status muted";
    contentEl.textContent = item.summary || "";
    contentEl.classList.toggle("hidden", !item.summary);
    retryBtn.classList.add("hidden");
    retranslateBtn.classList.add("hidden");
    askBtn.classList.add("hidden");
    stopDetailPolling();
  } else if (detail && detail.content) {
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
      if ((Array.isArray(keyPoints) && keyPoints.length) || (ai.conclusion_zh || "").trim()) {
        detailAiConclusion.textContent = ai.conclusion_zh || "";
        detailAiBox.classList.remove("hidden");
      }

      statusEl.textContent = isCodexFallbackBodyOnly
        ? "已由 GPT 完成翻译；结构化 fallback 失败，仅保留正文翻译"
        : isCodexFallback
          ? "已由 GPT 完成翻译"
        : "中文摘要与翻译已生成";
      statusEl.className = isCodexFallbackBodyOnly ? "detail-status pending" : "detail-status ready";
      contentEl.textContent = ai.body_zh;
      contentEl.classList.remove("hidden");
      stopDetailPolling();
    } else if (aiStatus === "failed") {
      const err = cached?.ai_job?.last_error || item.ai_error || "中文生成失败";
      statusEl.textContent = err.includes("CODEX_FALLBACK")
        ? `DeepSeek 失败，Codex fallback 也失败：${err}`
        : `中文生成失败，可重试：${err}`;
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
  applyIcon(askBtn, "message-circle", {
    label: "提问",
    tone: chatReady ? "accent" : "default",
  });
  const snapshotOnly = !!item.snapshotOnly;
  applyIcon(detailFavoriteBtn, "star", {
    filled: !!item.favorite_at,
    tone: item.favorite_at ? "warning" : "default",
    label: item.favorite_at ? "取消收藏" : "加入收藏",
  });
  applyIcon(importantBtn, "important", {
    filled: !!item.important_at,
    tone: item.important_at ? "danger" : "default",
    label: item.important_at ? "取消重要" : "标为重要",
  });
  applyIcon(detailBullishBtn, "trend-up", { tone: "danger", label: "看多板块标记" });
  applyIcon(detailBearishBtn, "trend-down", { tone: "success", label: "看空板块标记" });
  applyIcon(detailReminderToggleBtn, "bell", {
    filled: Number(item.active_reminder_count || 0) > 0,
    tone: Number(item.due_reminder_count || 0) > 0 ? "danger" : (Number(item.active_reminder_count || 0) > 0 ? "warning" : "default"),
    label: Number(item.active_reminder_count || 0) > 0 ? "查看或新增提醒" : "添加提醒",
  });
  applyIcon(detailTrackBtn, "crosshair", {
    label: "加入跟踪主题",
    tone: "default",
  });
  detailNoteToggleBtn.disabled = snapshotOnly || !item.url;
  detailBullishBtn.disabled = snapshotOnly;
  detailBearishBtn.disabled = snapshotOnly;
  detailFavoriteBtn.disabled = snapshotOnly;
  importantBtn.disabled = snapshotOnly;
  detailReminderToggleBtn.disabled = snapshotOnly;
  detailTrackBtn.disabled = snapshotOnly || !item.id;
  refreshDetailNoteUI(item);
  refreshDetailMarketTagsUI(item);
  refreshDetailReminderUI(item);
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

  const cached = { ...payload };
  state.detailCacheByUrl.set(item.url, cached);
  state.marketTagChoices = Array.isArray(payload.market_tag_choices) ? payload.market_tag_choices : state.marketTagChoices;
  item.detail_status = payload.detail_status;
  item.read_at = payload.read_at;
  item.favorite_at = payload.favorite_at;
  item.important_at = payload.important_at;
  item.read_later_at = payload.read_later_at;
  item.active_reminder_count = Number(payload.reminder_summary?.active_total || 0);
  item.due_reminder_count = Number(payload.reminder_summary?.due_total || 0);
  item.detail_ready = payload.detail ? 1 : 0;
  item.has_note = Number(payload.has_note || 0);
  item.market_tags = normalizeMarketTags(payload.market_tags || []);
  item.has_market_tags = Number(payload.has_market_tags || 0);
  item.ai_status = payload.ai_status || "none";
  item.ai_ready = payload.ai ? 1 : 0;
  if (payload.job && payload.job.last_error) item.detail_error = payload.job.last_error;
  if (payload.ai_job && payload.ai_job.last_error) item.ai_error = payload.ai_job.last_error;
  cached.reminders = Array.isArray(payload.reminders) ? payload.reminders : [];
  cached.reminder_summary = payload.reminder_summary || null;
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
  const reminderBadge = document.createElement("span");
  reminderBadge.className = "note-badge reminder-badge hidden";
  line1.appendChild(reminderBadge);

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

  const btnFavorite = document.createElement("button");
  btnFavorite.className = "btn-favorite icon-btn";
  btnFavorite.type = "button";
  btnFavorite.addEventListener("click", (e) => {
    e.stopPropagation();
    const current = !!state.itemsById.get(item.id)?.favorite_at;
    patchStateWithRollback(item.id, { favorite: !current });
  });

  actions.appendChild(btnImportant);
  if (!isBloombergVideoUrl(item.url) && item.source_type !== "twitter") {
    actions.appendChild(btnReadLater);
  }
  actions.appendChild(btnFavorite);

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

function ideaDirectionLabel(item) {
  if (item.direction_label) return item.direction_label;
  if (item.direction === "bullish") return "看多";
  if (item.direction === "bearish") return "看空";
  return "";
}

function syncIdeaRowSelection() {
  newsList.querySelectorAll(".idea-item").forEach((row) => {
    row.classList.toggle("selected", row.dataset.ideaId === state.selectedIdeaId);
  });
}

async function openIdeaCard(item) {
  if (!item) return;
  state.selectedIdeaId = item.idea_id || "";
  syncIdeaRowSelection();
  if (item.idea_type === "trend_note") {
    state.selectedId = null;
    state.selectedTrendIdea = { ...item };
    renderTrendIdeaDetail(state.selectedTrendIdea);
    openDetailOnMobile();
    return;
  }
  state.selectedTrendIdea = null;
  openItemDetail(item, { fromTrend: false });
}

function buildIdeaRow(item) {
  const li = document.createElement("li");
  li.className = "news-item idea-item";
  li.dataset.ideaId = item.idea_id || "";

  const line1 = document.createElement("div");
  line1.className = "line1";

  const kindBadge = document.createElement("span");
  kindBadge.className = `note-badge idea-kind-badge ${item.idea_type === "trend_note" ? "trend" : "article"}`;
  kindBadge.textContent = item.idea_type === "trend_note" ? "趋势想法" : "新闻想法";

  const text = document.createElement("span");
  text.className = "line1-text";
  if (item.idea_type === "trend_note") {
    text.textContent = `${item.updated_at || ""} · ${item.trend_date_key || ""}`;
  } else {
    text.textContent = `${item.source || "未知来源"} · ${item.updated_at || ""}`;
  }

  line1.appendChild(kindBadge);
  line1.appendChild(text);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = item.title || "";

  const summary = document.createElement("p");
  summary.className = "summary";
  if (item.idea_type === "trend_note") {
    summary.textContent = `${item.tag_label || ""} · ${ideaDirectionLabel(item)} · ${item.trend_date_key || ""}`;
  } else {
    summary.textContent = `${item.source || "未知来源"} · ${item.published_at || ""}`;
  }

  const notePreview = document.createElement("p");
  notePreview.className = "row-note-preview";
  notePreview.textContent = item.note || item.note_preview || "";
  if (item.idea_type === "trend_note") {
    notePreview.classList.add("full-text");
  }

  li.appendChild(line1);
  li.appendChild(title);
  if (summary.textContent) li.appendChild(summary);
  li.appendChild(notePreview);

  li.addEventListener("click", async () => {
    await openIdeaCard(item);
  });

  li.classList.toggle("selected", li.dataset.ideaId === state.selectedIdeaId);
  return li;
}

function updateIdeaDateCountOnDelete(item) {
  const dateKey = item?.date_key || "unknown";
  if (!state.dateCounts.has(dateKey)) return;
  const next = Math.max(0, Number(state.dateCounts.get(dateKey) || 0) - 1);
  state.dateCounts.set(dateKey, next);
  updateDateSectionCount(dateKey);
}

function removeIdeaRow(ideaId) {
  if (!newsList || !ideaId) return;
  const row = newsList.querySelector(`.idea-item[data-idea-id="${CSS.escape(ideaId)}"]`);
  if (!row) return;
  const prev = row.previousElementSibling;
  row.remove();
  if (prev && prev.classList.contains("date-section")) {
    const next = prev.nextElementSibling;
    if (!next || !next.classList.contains("idea-item")) {
      prev.remove();
    }
  }
}

function updateIdeaRow(item) {
  if (!newsList || !item?.idea_id) return;
  const row = newsList.querySelector(`.idea-item[data-idea-id="${CSS.escape(item.idea_id)}"]`);
  if (!row) return;
  const summary = row.querySelector(".summary");
  const notePreview = row.querySelector(".row-note-preview");
  if (summary) {
    summary.textContent = `${item.tag_label || ""} · ${ideaDirectionLabel(item)} · ${item.trend_date_key || ""}`;
  }
  if (notePreview) {
    notePreview.textContent = item.note || item.note_preview || "";
  }
  const lineText = row.querySelector(".line1-text");
  if (lineText) {
    lineText.textContent = `${item.updated_at || ""} · ${item.trend_date_key || ""}`;
  }
}

function renderTrendIdeaDetail(item) {
  closeTagAdminView();
  closeTrendComposerView();
  closeTrendNoteEditor();
  resetDetailChatState({ keepProvider: true });
  stopDetailPolling();
  closeMarketPicker();
  closeReminderEditor();
  if (detailReminderCard) detailReminderCard.classList.add("hidden");
  state.detailReturnToTrend = false;
  syncDetailReturnButton();
  detailBody.classList.add("hidden");
  detailTrendBody.classList.add("hidden");
  detailChatBody.classList.add("hidden");
  if (!item) {
    clearTrendIdeaDetailState();
    detailEmpty.classList.remove("hidden");
    detailEmpty.textContent = emptyDetailMessage();
    updateWorkspaceLayout();
    return;
  }

  state.selectedTrendIdea = { ...item };
  detailEmpty.classList.add("hidden");
  detailTrendIdeaBody.classList.remove("hidden");
  setTrendIdeaEditorOpen(false);
  detailTrendIdeaTitle.textContent = `${item.tag_label || ""} · ${ideaDirectionLabel(item)}`;
  detailTrendIdeaMeta.textContent = `${item.trend_date_key || ""} · 创建 ${item.created_at || "-"} · 更新 ${item.updated_at || "-"}`;
  detailTrendIdeaText.textContent = item.note || "";
  updateWorkspaceLayout();
}

async function fetchNewsPage(page) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    q: "",
    read_filter: state.readFilter,
    collection: state.collection,
    source_filter: state.sourceFilter,
    sort_order: getNewsSortOrder(state.collection),
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

async function fetchIdeasPage(page) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    type: state.ideaFilter,
    sort_order: getNewsSortOrder("notes"),
  });
  const res = await fetch(`/api/ideas?${params.toString()}`);
  if (!res.ok) throw new Error("ideas_fetch_failed");
  return res.json();
}

async function fetchTrackedTopics() {
  const res = await fetch("/api/tracked-topics");
  if (!res.ok) throw new Error("tracked_topics_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "tracked_topics_fetch_failed");
  return Array.isArray(data.items) ? data.items : [];
}

async function fetchTrackedTopicItems(topicId) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}/items`);
  if (!res.ok) throw new Error("tracked_topic_items_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "tracked_topic_items_fetch_failed");
  return data;
}

async function fetchTrackedTopicDailySummaries(topicId) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}/daily-summaries`);
  if (!res.ok) throw new Error("tracked_topic_daily_summaries_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "tracked_topic_daily_summaries_fetch_failed");
  return data;
}

async function generateTrackedTopicDailySummary(topicId, summaryDate) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}/daily-summaries/${encodeURIComponent(summaryDate)}/generate`, {
    method: "POST",
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_daily_summary_generate_failed" }));
  if (!res.ok || !data.ok) {
    const detail = data.detail ? `: ${data.detail}` : "";
    throw new Error((data.error || "tracked_topic_daily_summary_generate_failed") + detail);
  }
  return data;
}

async function createTrackedTopic(payload) {
  const res = await fetch("/api/tracked-topics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_create_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_topic_create_failed");
  return data;
}

async function updateTrackedTopic(topicId, payload) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_update_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_topic_update_failed");
  return data;
}

async function deleteTrackedTopic(topicId) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}`, { method: "DELETE" });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_delete_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_topic_delete_failed");
  return data;
}

async function backfillTrackedTopic(topicId, mode) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}/backfill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_backfill_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_topic_backfill_failed");
  return data;
}

async function addItemToTrackedTopic(topicId, itemId) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: itemId }),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_item_create_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_topic_item_create_failed");
  return data;
}

async function setTrackedTopicItemHidden(topicId, itemId, hidden) {
  const res = await fetch(`/api/tracked-topics/${encodeURIComponent(topicId)}/items/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ hidden }),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_topic_item_update_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_topic_item_update_failed");
  return data;
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
  state.selectedIdeaId = "";
  state.selectedReminderId = null;
  state.selectedReminderDraftId = null;
  state.reminderItems = [];
  state.trackedTimelineItems = [];
  stopDetailPolling();
  stopRowStatusPolling();
  clearFeedEndAutoReadTimer();
  feedEndAutoReadFiredKey = "";
  state.trendRows = [];
  state.trendDates = [];
  state.trendSelection = null;
  state.selectedTrendIdea = null;
  state.trendNoteContext = null;
  state.tagAdminOpen = false;
  state.trendComposeOpen = false;
  state.dateCounts = new Map();
  state.detailReturnToTrend = false;
  state.feedUnreadCursor = null;
  resetDetailChatState();
  showTrendsView(false);
  showTrackedView(false);
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
  startReminderSummaryTimer();
  await refreshReminderSummary().catch(() => {});
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

    if (state.collection === "tracked") {
      state.trackedTopics = await fetchTrackedTopics();
      if (state.selectedTrackedTopicId && !state.trackedTopics.some((topic) => String(topic.id) === String(state.selectedTrackedTopicId))) {
        state.selectedTrackedTopicId = null;
      }
      state.total = state.trackedTopics.length;
      state.pages = 1;
      state.page = 1;
      state.hasMore = false;
      state.dateCounts = new Map();
      showTrackedView(true);
      renderTrackedTopicsList();
      if (state.selectedTrackedTopicId) {
        await loadTrackedTopicTimeline(state.selectedTrackedTopicId);
        setHint(state.trackedTimelineItems.length ? "中列仅保留主题列表；右栏展示当前主题时间线。" : "当前主题还没有命中新闻，可在右栏执行历史回扫。");
      } else {
        renderTrackedTopicEmpty(state.trackedTopics.length ? "选择一个跟踪主题，右栏会显示详情与时间线。" : "还没有跟踪主题，点击“新建跟踪”开始。");
        setHint(state.trackedTopics.length ? "点击中列主题打开右栏详情。" : "还没有跟踪主题，点击“新建跟踪”开始。");
      }
      renderMeta();
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
      stopRowStatusPolling();
      return;
    }

    if (state.collection === "reminders") {
      const data = await fetchReminders(state.reminderFilter);
      state.reminderItems = normalizeReminderItems(data.items);
      applyReminderSummary(data.summary || state.reminderSummary);
      state.total = state.reminderItems.length;
      state.pages = 1;
      state.page = 1;
      state.hasMore = false;
      state.dateCounts = new Map();
      showTrendsView(false);
      state.reminderItems.forEach((reminder) => {
        const row = buildReminderListRow(reminder);
        if (listHint && listHint.parentElement === newsList) {
          newsList.insertBefore(row, listHint);
        } else {
          newsList.appendChild(row);
        }
      });
      renderMeta();
      if (state.total) {
        setHint("点击提醒查看关联新闻");
      } else if (state.reminderFilter === "done") {
        setHint("还没有已完成提醒。");
      } else if (state.reminderFilter === "all") {
        setHint("还没有提醒，去任意新闻右栏添加一个。");
      } else {
        setHint("还没有进行中的提醒，去任意新闻右栏添加一个。");
      }
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
      stopRowStatusPolling();
      return;
    }

    if (state.collection === "notes") {
      const data = await fetchIdeasPage(1);
      state.total = data.total;
      setDateCounts(data.date_counts);
      state.pages = data.pages;
      state.page = 1;
      state.hasMore = state.page < state.pages;
      showTrendsView(false);
      data.items.forEach((item) => appendNewsRow(item, buildIdeaRow(item)));
      renderMeta();
      if (state.total === 0) {
        setHint("还没有想法，去新闻详情或趋势页记录第一条。");
      } else if (state.hasMore) {
        setHint("继续下滑加载更多");
      } else {
        setHint("已加载全部想法");
      }
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
    updateSortOrderButton();
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
  if (state.collection === "notes") {
    if (!state.hasMore) return;
    const next = state.page + 1;
    state.loading = true;
    try {
      const data = await fetchIdeasPage(next);
      setDateCounts(data.date_counts);
      data.items.forEach((item) => appendNewsRow(item, buildIdeaRow(item)));
      state.page = next;
      state.pages = data.pages;
      state.total = data.total;
      state.hasMore = state.page < state.pages;
      renderMeta();
      setHint(state.hasMore ? "继续下滑加载更多" : "已加载全部想法");
    } finally {
      state.loading = false;
    }
    return;
  }
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

[
  [reminderFilterActiveBtn, "active"],
  [reminderFilterDoneBtn, "done"],
  [reminderFilterAllBtn, "all"],
].forEach(([button, filter]) => {
  if (!button) return;
  button.addEventListener("click", async () => {
    if (state.reminderFilter === filter) return;
    state.reminderFilter = filter;
    await loadFirstPage();
  });
});

[
  [ideaFilterAllBtn, "all"],
  [ideaFilterArticleBtn, "article"],
  [ideaFilterTrendBtn, "trend"],
].forEach(([button, filter]) => {
  if (!button) return;
  button.addEventListener("click", async () => {
    if (state.ideaFilter === filter) return;
    state.ideaFilter = filter;
    await loadFirstPage();
  });
});

if (sortOrderBtn) {
  sortOrderBtn.addEventListener("click", async () => {
    if (!supportsSortToggle()) return;
    const current = getNewsSortOrder();
    state.newsSortOrderByCollection[state.collection] = current === "default" ? "reverse" : "default";
    await loadFirstPage();
  });
}

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

if (navFavoritesBtn) {
  navFavoritesBtn.addEventListener("click", async () => {
    await switchCollection("favorites");
  });
}

if (navRemindersBtn) {
  navRemindersBtn.addEventListener("click", async () => {
    await switchCollection("reminders");
  });
}

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
if (navTrackedBtn) {
  navTrackedBtn.addEventListener("click", async () => {
    await switchCollection("tracked");
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

if (trackedCreateInlineBtn) {
  trackedCreateInlineBtn.addEventListener("click", () => {
    openTrackedTopicForm("create");
  });
}

if (trackedEditBtn) {
  trackedEditBtn.addEventListener("click", () => {
    const topic = selectedTrackedTopic();
    if (!topic) return;
    openTrackedTopicForm("edit", topic);
  });
}

if (trackedViewTimelineBtn) {
  trackedViewTimelineBtn.addEventListener("click", async () => {
    if (state.trackedDetailView === "timeline") return;
    state.trackedDetailView = "timeline";
    renderTrackedViewSwitch();
    renderTrackedTopicDetail(selectedTrackedTopic(), state.trackedTimelineItems);
  });
}

if (trackedViewTimeflowBtn) {
  trackedViewTimeflowBtn.addEventListener("click", async () => {
    if (state.trackedDetailView === "timeflow") return;
    state.trackedDetailView = "timeflow";
    renderTrackedViewSwitch();
    const topic = selectedTrackedTopic();
    if (!topic) {
      renderTrackedTopicDetail(null, state.trackedTimelineItems);
      return;
    }
    try {
      await loadTrackedTopicDailySummaries(topic.id);
    } catch (error) {
      state.trackedDailySummaries = [];
      renderTrackedTopicDetail(topic, state.trackedTimelineItems);
      setHint(`读取时间流失败：${error?.message || error}`);
    }
  });
}

if (trackedDeleteBtn) {
  trackedDeleteBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (!topic) return;
    const ok = window.confirm(`删除跟踪主题“${topic.title}”？这会清理该主题下的全部关系数据。`);
    if (!ok) return;
    await deleteTrackedTopic(topic.id);
    state.trackedTopics = await fetchTrackedTopics();
    state.selectedTrackedTopicId = null;
    state.trackedTimelineItems = [];
    state.trackedDailySummaries = [];
    renderTrackedTopicsList();
    renderTrackedTopicEmpty(state.trackedTopics.length ? "主题已删除。请选择其他主题。" : "跟踪主题已删除，点击“新建跟踪”开始新的主题。");
    renderMeta();
    setHint("跟踪主题已删除");
  });
}

if (trackedBackfillModeSelect) {
  trackedBackfillModeSelect.addEventListener("change", () => {
    state.trackedBackfillMode = trackedBackfillModeSelect.value;
  });
}

if (trackedBackfillBtn) {
  trackedBackfillBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (!topic) return;
    const modeLabelMap = {
      recent_important: "近180天重要新闻",
      all_important: "全部重要新闻",
      all_news: "全部新闻",
    };
    const modeLabel = modeLabelMap[state.trackedBackfillMode] || state.trackedBackfillMode;
    const ok = window.confirm(
      `确认重新回扫“${topic.title}”吗？\n\n` +
      `范围：${modeLabel}\n` +
      "本操作会按当前规则重新计算该主题在所选范围内的自动命中，并覆盖旧自动匹配结果。\n" +
      "手动加入和手动隐藏不会被覆盖。"
    );
    if (!ok) return;
    const data = await backfillTrackedTopic(topic.id, state.trackedBackfillMode);
    state.trackedTopics = await fetchTrackedTopics();
    state.trackedTimelineItems = Array.isArray(data.items) ? data.items : [];
    if (state.trackedDetailView === "timeflow") {
      await loadTrackedTopicDailySummaries(topic.id);
    } else {
      state.trackedDailySummaries = [];
      renderTrackedTopicsList();
      renderTrackedTopicDetail(data.topic || selectedTrackedTopic(), state.trackedTimelineItems);
      renderMeta();
    }
    setHint(`历史回扫完成，当前范围命中 ${Number(data.matched_count || 0)} 条`);
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

[
  [settingsNavServices, "services"],
  [settingsNavModels, "models"],
  [settingsNavRelease, "release"],
].forEach(([button, section]) => {
  if (!button) return;
  button.addEventListener("click", () => {
    state.settingsSection = section;
    renderSettingsOverlay();
  });
});

if (settingsTranslationModelSelect) {
  settingsTranslationModelSelect.addEventListener("change", () => {
    syncModelCustomVisibility(settingsTranslationModelSelect, settingsTranslationModelCustom);
  });
}

if (settingsCodexChatModelSelect) {
  settingsCodexChatModelSelect.addEventListener("change", () => {
    syncModelCustomVisibility(settingsCodexChatModelSelect, settingsCodexChatModelCustom);
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
    state.collection === "favorites" ||
    state.collection === "reminders" ||
    state.collection === "important" ||
    state.collection === "notes" ||
    state.collection === "tracked" ||
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
  if (canReturnToTrackedTopic()) {
    restoreTrackedTopicFromDetail().catch(() => {});
    return;
  }
  closeDetailOnMobile();
  stopDetailPolling();
});
if (detailReturnToTrendBtn) {
  detailReturnToTrendBtn.addEventListener("click", restoreTrendDetailFromDetail);
}
if (detailReturnToTrackedBtn) {
  detailReturnToTrackedBtn.addEventListener("click", () => {
    restoreTrackedTopicFromDetail().catch(() => {});
  });
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

detailFavoriteBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const current = !!state.itemsById.get(state.selectedId)?.favorite_at;
  await patchStateWithRollback(state.selectedId, { favorite: !current });
});

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

if (detailReminderToggleBtn) {
  detailReminderToggleBtn.addEventListener("click", () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item || item.snapshotOnly) return;
    if (!detailReminderEditor.classList.contains("hidden")) {
      closeReminderEditor();
      return;
    }
    openReminderEditor(item);
  });
}

if (detailTrackBtn) {
  detailTrackBtn.addEventListener("click", async () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item || item.snapshotOnly) return;
    if (!detailTrackEditor.classList.contains("hidden")) {
      closeDetailTrackEditor();
      return;
    }
    await openDetailTrackEditor(item);
  });
}

if (detailReminderSaveBtn) {
  detailReminderSaveBtn.addEventListener("click", async () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item) return;
    await saveReminderDraft(item, state.selectedReminderDraftId || null);
  });
}

if (detailReminderDeleteBtn) {
  detailReminderDeleteBtn.addEventListener("click", async () => {
    if (!state.selectedId || !state.selectedReminderDraftId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item) return;
    if (!window.confirm("确认删除这个提醒？")) return;
    await removeReminderDraft(item, state.selectedReminderDraftId);
  });
}

if (detailReminderCancelBtn) {
  detailReminderCancelBtn.addEventListener("click", closeReminderEditor);
}

if (detailTrackSaveBtn) {
  detailTrackSaveBtn.addEventListener("click", async () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item || !detailTrackTopicSelect?.value) return;
    const topicId = Number(detailTrackTopicSelect.value);
    await addItemToTrackedTopic(topicId, item.id);
    closeDetailTrackEditor();
    state.trackedTopics = await fetchTrackedTopics();
    if (state.collection === "tracked" && String(state.selectedTrackedTopicId) === String(topicId)) {
      await loadTrackedTopicTimeline(topicId);
    } else if (state.collection === "tracked") {
      renderTrackedTopicsList();
      renderMeta();
    }
    const topic = state.trackedTopics.find((row) => String(row.id) === String(topicId));
    setHint(`已加入跟踪主题：${topic?.title || topicId}`);
  });
}

if (detailTrackCancelBtn) {
  detailTrackCancelBtn.addEventListener("click", closeDetailTrackEditor);
}

if (detailTrackedFormBackBtn) {
  detailTrackedFormBackBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (!topic) {
      renderTrackedTopicEmpty();
      return;
    }
    await openTrackedTopicDetailById(topic.id);
  });
}

if (detailTrackedFormCancelBtn) {
  detailTrackedFormCancelBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (topic) {
      await openTrackedTopicDetailById(topic.id);
      return;
    }
    renderTrackedTopicEmpty(state.trackedTopics.length ? "创建已取消。选择一个主题继续查看。" : "创建已取消。点击“新建跟踪”重新开始。");
  });
}

if (detailTrackedFormSaveBtn) {
  detailTrackedFormSaveBtn.addEventListener("click", async () => {
    const payload = trackedFormPayload();
    if (!payload.title) {
      setHint("请先填写跟踪主题名称");
      detailTrackedTitleInput?.focus();
      return;
    }
    detailTrackedFormSaveBtn.disabled = true;
    try {
      let topicId = state.selectedTrackedTopicId;
      if (state.trackedFormMode === "edit" && topicId) {
        await updateTrackedTopic(topicId, payload);
      } else {
        const result = await createTrackedTopic(payload);
        topicId = result.topic?.id || topicId;
      }
      state.trackedTopics = await fetchTrackedTopics();
      state.selectedTrackedTopicId = topicId || null;
      renderTrackedTopicsList();
      if (state.selectedTrackedTopicId) {
        await loadTrackedTopicTimeline(state.selectedTrackedTopicId);
      } else {
        renderTrackedTopicEmpty();
      }
      setHint(state.trackedFormMode === "edit" ? "跟踪主题已更新" : "跟踪主题已创建");
    } finally {
      detailTrackedFormSaveBtn.disabled = false;
    }
  });
}

if (detailTagCreateBtn) {
  detailTagCreateBtn.addEventListener("click", async () => {
    const displayName = detailTagCreateInput.value.trim();
    if (!displayName) return;
    detailTagCreateBtn.disabled = true;
    try {
      const payload = await createMarketTagDefinition(displayName);
      detailTagCreateInput.value = "";
      await refreshTrendTagAdminState(payload?.tag?.key || "");
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

if (detailChatSendBtn) {
  detailChatSendBtn.addEventListener("click", () => {
    sendDetailChatMessage();
  });
}

if (detailChatArchiveBtn) {
  detailChatArchiveBtn.addEventListener("click", () => {
    archiveDetailChat();
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
  closeReminderEditor();
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

if (detailTrendIdeaEditBtn) {
  detailTrendIdeaEditBtn.addEventListener("click", () => {
    if (!state.selectedTrendIdea) return;
    detailTrendIdeaInput.value = state.selectedTrendIdea.note || "";
    setTrendIdeaEditorOpen(true);
    detailTrendIdeaInput.focus();
  });
}

if (detailTrendIdeaCancelBtn) {
  detailTrendIdeaCancelBtn.addEventListener("click", () => {
    if (!state.selectedTrendIdea) return;
    detailTrendIdeaInput.value = state.selectedTrendIdea.note || "";
    setTrendIdeaEditorOpen(false);
  });
}

if (detailTrendIdeaSaveBtn) {
  detailTrendIdeaSaveBtn.addEventListener("click", async () => {
    const item = state.selectedTrendIdea;
    if (!item) return;
    detailTrendIdeaSaveBtn.disabled = true;
    if (detailTrendIdeaCancelBtn) detailTrendIdeaCancelBtn.disabled = true;
    try {
      const result = await updateTrendNote(item.trend_note_id, detailTrendIdeaInput.value);
      const updated = {
        ...item,
        note: result.trend_note.note,
        note_preview: result.trend_note.note,
        updated_at: result.trend_note.updated_at,
      };
      state.selectedTrendIdea = updated;
      updateIdeaRow(updated);
      renderTrendIdeaDetail(updated);
    } finally {
      detailTrendIdeaSaveBtn.disabled = false;
      if (detailTrendIdeaCancelBtn) detailTrendIdeaCancelBtn.disabled = false;
    }
  });
}

if (detailTrendIdeaDeleteBtn) {
  detailTrendIdeaDeleteBtn.addEventListener("click", async () => {
    const item = state.selectedTrendIdea;
    if (!item) return;
    const ok = window.confirm(`删除这条趋势想法？\n\n${item.tag_label || ""} · ${ideaDirectionLabel(item)} · ${item.trend_date_key || ""}`);
    if (!ok) return;
    detailTrendIdeaDeleteBtn.disabled = true;
    try {
      await deleteTrendNote(item.trend_note_id);
      removeIdeaRow(item.idea_id);
      updateIdeaDateCountOnDelete(item);
      state.total = Math.max(0, Number(state.total || 0) - 1);
      state.pages = Math.max(1, Math.ceil(state.total / state.per));
      state.page = Math.min(state.page, state.pages);
      state.selectedIdeaId = "";
      syncIdeaRowSelection();
      renderMeta();
      renderTrendIdeaDetail(null);
      setHint(state.total > 0 ? "趋势想法已删除" : "还没有想法，去新闻详情或趋势页记录第一条。");
    } finally {
      detailTrendIdeaDeleteBtn.disabled = false;
    }
  });
}

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
updateSortOrderButton();
fetchReadingCheckpoint()
  .then((cp) => {
    state.readingCheckpoint = cp;
    updateResumeButton();
  })
  .catch(() => {});
fetchRuntimeSettings()
  .then((data) => {
    state.runtimeSettings = data;
  })
  .catch(() => {});
autoReindexAndLoad();
