let state = {
  page: 1,
  pages: 1,
  q: "",
  per: 30,
  readFilter: "unread", // all | unread | read
  feedReadFilter: "unread", // 仅新闻流记忆 all | unread
  readLaterReadFilter: "unread", // 稍后阅读记忆 all | unread | read
  sourceFilter: "all", // all | reuters | bloomberg | techcrunch | ars | x | host:*
  collection: "feed", // search | feed | daily | favorites | reminders | important | read_later | notes | tracked | market_tags
  total: 0,
  loading: false,
  hasMore: true,
  selectedId: null,
  selectedIdeaId: "",
  selectedReminderId: null,
  selectedReminderDraftId: null,
  selectedTrackedTopicId: null,
  reminderFilter: "active", // active | done | all
  ideaFilter: "all", // all | article | trend | standalone
  reviewFilter: "all", // all | in_progress | pending_review | done
  reviewOutcomeFilter: "all", // all | confirmed | refuted | inconclusive; only used for done reviews
  selectedReviewId: null,
  reviewListItems: [],
  currentReview: null,
  pendingReviewSource: null,
  reviewReminderUserTouched: false,
  itemsById: new Map(),
  reminderItems: [],
  dailyBriefings: [],
  dailyExpandedMonths: {},
  selectedDailyDate: "",
  selectedDailyBriefing: null,
  trackedTopics: [],
  trackedTimelineItems: [],
  trackedDailySummaries: [],
  trackedBackfillMode: "recent_important",
  trackedDetailView: "timeline",
  trackedTimeflowBatchMode: "all",
  trackedTimeflowBatchToken: "",
  reminderSummary: {
    total: 0,
    active_total: 0,
    due_total: 0,
    done_total: 0,
    dismissed_total: 0,
  },
  detailCacheByUrl: new Map(),
  readingCheckpoint: null,
  selectedTrendIdea: null,
  selectedStandaloneIdea: null,
  marketTagChoices: [],
  marketWorkbenchTag: "",
  marketWorkbenchFilter: "all",
  marketWorkbenchSummary: null,
  marketWorkbenchPin: null,
  marketWorkbenchPinEditing: false,
  marketWorkbenchPinSaving: false,
  selectedTagAdminKey: "",
  tagAdminOpen: false,
  trendComposeOpen: false,
  newsSortOrderByCollection: {},
  dateCounts: new Map(),
  detailReturnToTrackedTopicId: null,
  searchRange: "all",
  searchTime: "all",
  feedUnreadCursor: null,
  detailView: "detail",
  trackedFormMode: "create",
  detailChatMessages: [],
  detailChatSessionId: "",
  detailChatProvider: "",
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

const TITLE_CHAR_LIMIT = 100;
const FEED_KEYBOARD_NAV_MIN_WIDTH = 1181;
const FEED_KEYBOARD_DETAIL_DELAY_MS = 120;
const sourceIconMap = {
  reuters: "/static/source-icons/reuters.ico",
  bloomberg: "/static/source-icons/bloomberg.png",
  techcrunch: "/static/source-icons/techcrunch.png",
  ars: "/static/source-icons/arstechnica.ico",
  x: "/static/source-icons/x.svg",
};
const sourceIconAliases = {
  "ars technica": "ars",
  twitter: "x",
};
const SETTINGS_CUSTOM_MODEL_VALUE = "__custom__";
const TRACKED_SYSTEM_DEFAULT_RULE_PARAMS = {
  title_weight: 1,
  note_weight: 1,
  summary_weight: 1,
  content_weight: 1,
  strong_score: 1,
  core_score: 1,
  context_score: 1,
  exclude_penalty: 1,
  threshold: 6,
};

const feedControlsFrame = document.getElementById("feedControlsFrame");
const feedControlsScroll = document.getElementById("feedControlsScroll");
const refreshBtn = document.getElementById("refreshBtn");
const resumeAnchorBtn = document.getElementById("resumeAnchorBtn");
const readFilterToggleBtn = document.getElementById("readFilterToggleBtn");
const sortOrderBtn = document.getElementById("sortOrderBtn");
const trackedCreateInlineBtn = document.getElementById("trackedCreateInlineBtn");
const trackedDefaultsInlineBtn = document.getElementById("trackedDefaultsInlineBtn");
const markAllReadBtn = document.getElementById("markAllReadBtn");
const manageMarketTagsBtn = document.getElementById("manageMarketTagsBtn");
const readLaterFilterBar = document.getElementById("readLaterFilterBar");
const readLaterFilterReadBtn = document.getElementById("readLaterFilterReadBtn");
const readLaterFilterUnreadBtn = document.getElementById("readLaterFilterUnreadBtn");
const readLaterFilterAllBtn = document.getElementById("readLaterFilterAllBtn");

const navSearchBtn = document.getElementById("navSearchBtn");
const navFeedBtn = document.getElementById("navFeedBtn");
const navDailyBtn = document.getElementById("navDailyBtn");
const navFavoritesBtn = document.getElementById("navFavoritesBtn");
const navRemindersBtn = document.getElementById("navRemindersBtn");
const navReminderBadge = document.getElementById("navReminderBadge");
const navImportantBtn = document.getElementById("navImportantBtn");
const navReadLaterBtn = document.getElementById("navReadLaterBtn");
const navNotesBtn = document.getElementById("navNotesBtn");
const navReviewsBtn = document.getElementById("navReviewsBtn");
const navTrackedBtn = document.getElementById("navTrackedBtn");
const navMarketTagsBtn = document.getElementById("navMarketTagsBtn");
// Review elements
const reviewFilterBar = document.getElementById("reviewFilterBar");
const reviewFilterAllBtn = document.getElementById("reviewFilterAllBtn");
const reviewFilterActiveBtn = document.getElementById("reviewFilterActiveBtn");
const reviewFilterPendingBtn = document.getElementById("reviewFilterPendingBtn");
const reviewFilterDoneBtn = document.getElementById("reviewFilterDoneBtn");
const reviewOutcomeFilterBar = document.getElementById("reviewOutcomeFilterBar");
const reviewOutcomeFilterAllBtn = document.getElementById("reviewOutcomeFilterAllBtn");
const reviewOutcomeFilterConfirmedBtn = document.getElementById("reviewOutcomeFilterConfirmedBtn");
const reviewOutcomeFilterRefutedBtn = document.getElementById("reviewOutcomeFilterRefutedBtn");
const reviewOutcomeFilterInconclusiveBtn = document.getElementById("reviewOutcomeFilterInconclusiveBtn");
const detailReviewBody = document.getElementById("detailReviewBody");
const detailReviewCreateBody = document.getElementById("detailReviewCreateBody");
const detailReviewAddBtn = document.getElementById("detailReviewAddBtn");
const detailTrendIdeaReviewBtn = document.getElementById("detailTrendIdeaReviewBtn");
const detailStandaloneIdeaReviewBtn = document.getElementById("detailStandaloneIdeaReviewBtn");
// Review detail elements
const detailReviewTitle = document.getElementById("detailReviewTitle");
const detailReviewMeta = document.getElementById("detailReviewMeta");
const detailReviewResultBadge = document.getElementById("detailReviewResultBadge");
const detailReviewTimeline = document.getElementById("detailReviewTimeline");
const detailReviewScrollArea = document.getElementById("detailReviewScrollArea");
const detailReviewProgressBtn = document.getElementById("detailReviewProgressBtn");
const detailReviewReviseBtn = document.getElementById("detailReviewReviseBtn");
const detailReviewCompleteBtn = document.getElementById("detailReviewCompleteBtn");
const detailReviewRetrackBtn = document.getElementById("detailReviewRetrackBtn");
const detailReviewProgressForm = document.getElementById("detailReviewProgressForm");
const detailReviewReviseForm = document.getElementById("detailReviewReviseForm");
const detailReviewCompleteForm = document.getElementById("detailReviewCompleteForm");
const detailReviewRetrackForm = document.getElementById("detailReviewRetrackForm");
// Review create form elements
const reviewCreateSourceNote = document.getElementById("reviewCreateSourceNote");
const reviewCreateSourceMeta = document.getElementById("reviewCreateSourceMeta");
const reviewCreateJudgment = document.getElementById("reviewCreateJudgment");
const reviewCreateCriteria = document.getElementById("reviewCreateCriteria");
const reviewCreateDate = document.getElementById("reviewCreateDate");
const reviewCreateAddReminder = document.getElementById("reviewCreateAddReminder");
const reviewCreateRemindAt = document.getElementById("reviewCreateRemindAt");
const reviewCreateSaveBtn = document.getElementById("reviewCreateSaveBtn");
const reviewCreateCancelBtn = document.getElementById("reviewCreateCancelBtn");
// Review progress form elements
const reviewProgressText = document.getElementById("reviewProgressText");
const reviewProgressDate = document.getElementById("reviewProgressDate");
const reviewProgressSaveBtn = document.getElementById("reviewProgressSaveBtn");
const reviewProgressCancelBtn = document.getElementById("reviewProgressCancelBtn");
// Review revise form elements
const reviewReviseJudgment = document.getElementById("reviewReviseJudgment");
const reviewReviseCriteria = document.getElementById("reviewReviseCriteria");
const reviewReviseReason = document.getElementById("reviewReviseReason");
const reviewReviseDate = document.getElementById("reviewReviseDate");
const reviewReviseSaveBtn = document.getElementById("reviewReviseSaveBtn");
const reviewReviseCancelBtn = document.getElementById("reviewReviseCancelBtn");
// Review complete form elements
const reviewCompleteVersions = document.getElementById("reviewCompleteVersions");
const reviewCompleteActual = document.getElementById("reviewCompleteActual");
const reviewCompleteResult = document.getElementById("reviewCompleteResult");
const reviewCompleteBias = document.getElementById("reviewCompleteBias");
const reviewCompleteExperience = document.getElementById("reviewCompleteExperience");
const reviewCompleteSaveBtn = document.getElementById("reviewCompleteSaveBtn");
const reviewCompleteCancelBtn = document.getElementById("reviewCompleteCancelBtn");
const reviewContinueObserveSection = document.getElementById("reviewContinueObserveSection");
const reviewContinueDate = document.getElementById("reviewContinueDate");
const reviewContinueSaveBtn = document.getElementById("reviewContinueSaveBtn");
const reviewContinueDoneBtn = document.getElementById("reviewContinueDoneBtn");
// Review retrack form elements
const reviewRetrackJudgment = document.getElementById("reviewRetrackJudgment");
const reviewRetrackCriteria = document.getElementById("reviewRetrackCriteria");
const reviewRetrackDate = document.getElementById("reviewRetrackDate");
const reviewRetrackSaveBtn = document.getElementById("reviewRetrackSaveBtn");
const reviewRetrackCancelBtn = document.getElementById("reviewRetrackCancelBtn");
const mobileCollectionTriggerBtn = document.getElementById("mobileCollectionTriggerBtn");
const mobileReadLaterTabBtn = document.getElementById("mobileReadLaterTabBtn");
const mobileMoreTabBtn = document.getElementById("mobileMoreTabBtn");
const mobileSourceEntryBtn = document.getElementById("mobileSourceEntryBtn");
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
const topbarViewMenu = document.getElementById("topbarViewMenu");
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
const feedKicker = document.getElementById("feedKicker");
const feedTitle = document.getElementById("feedTitle");
const sourceFilterCount = document.getElementById("sourceFilterCount");
const pageInfo = document.getElementById("pageInfo");
const reminderFilterBar = document.getElementById("reminderFilterBar");
const reminderFilterActiveBtn = document.getElementById("reminderFilterActiveBtn");
const reminderFilterDoneBtn = document.getElementById("reminderFilterDoneBtn");
const reminderFilterAllBtn = document.getElementById("reminderFilterAllBtn");
const ideaFilterBar = document.getElementById("ideaFilterBar");
const ideaFilterAllBtn = document.getElementById("ideaFilterAllBtn");
const ideaFilterArticleBtn = document.getElementById("ideaFilterArticleBtn");
const ideaFilterTrendBtn = document.getElementById("ideaFilterTrendBtn");
const marketWorkbenchBar = document.getElementById("marketWorkbenchBar");
const marketWorkbenchTagSelect = document.getElementById("marketWorkbenchTagSelect");
const marketWorkbenchFilterSelect = document.getElementById("marketWorkbenchFilterSelect");
const marketWorkbenchSummaryBtn = document.getElementById("marketWorkbenchSummaryBtn");
const marketWorkbenchComposeBtn = document.getElementById("marketWorkbenchComposeBtn");
const marketWorkbenchPinCard = document.getElementById("marketWorkbenchPinCard");
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");
const trackedView = document.getElementById("trackedView");
const trackedBackfillModeSelect = document.getElementById("trackedBackfillModeSelect");
const trackedBackfillBtn = document.getElementById("trackedBackfillBtn");
const trackedEditBtn = document.getElementById("trackedEditBtn");
const trackedDeleteBtn = document.getElementById("trackedDeleteBtn");
const trackedViewTimelineBtn = document.getElementById("trackedViewTimelineBtn");
const trackedViewTimeflowBtn = document.getElementById("trackedViewTimeflowBtn");
const trackedTimeflowBatchBar = document.getElementById("trackedTimeflowBatchBar");
const trackedTimeflowBatchModeSelect = document.getElementById("trackedTimeflowBatchModeSelect");
const trackedTimeflowBatchGenerateBtn = document.getElementById("trackedTimeflowBatchGenerateBtn");
const trackedTimelineHint = document.getElementById("trackedTimelineHint");
const trackedTimelineList = document.getElementById("trackedTimelineList");

const detailPanel = document.getElementById("detailPanel");
const detailEmpty = document.getElementById("detailEmpty");
const detailEmptyIcon = document.getElementById("detailEmptyIcon");
const detailEmptyTitle = document.getElementById("detailEmptyTitle");
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
const detailTrendIdeaEditMeta = document.getElementById("detailTrendIdeaEditMeta");
const detailTrendIdeaDateSelect = document.getElementById("detailTrendIdeaDateSelect");
const detailTrendIdeaTagSelect = document.getElementById("detailTrendIdeaTagSelect");
const detailTrendIdeaDirectionSelect = document.getElementById("detailTrendIdeaDirectionSelect");
const detailTrendIdeaInput = document.getElementById("detailTrendIdeaInput");
const detailTrendIdeaSaveBtn = document.getElementById("detailTrendIdeaSaveBtn");
const detailTrendIdeaCancelBtn = document.getElementById("detailTrendIdeaCancelBtn");
const detailStandaloneIdeaBody = document.getElementById("detailStandaloneIdeaBody");
const detailStandaloneIdeaMeta = document.getElementById("detailStandaloneIdeaMeta");
const detailStandaloneIdeaText = document.getElementById("detailStandaloneIdeaText");
const detailStandaloneIdeaEditBtn = document.getElementById("detailStandaloneIdeaEditBtn");
const detailStandaloneIdeaDeleteBtn = document.getElementById("detailStandaloneIdeaDeleteBtn");
const detailStandaloneIdeaEditor = document.getElementById("detailStandaloneIdeaEditor");
const detailStandaloneIdeaInput = document.getElementById("detailStandaloneIdeaInput");
const detailStandaloneIdeaSaveBtn = document.getElementById("detailStandaloneIdeaSaveBtn");
const detailStandaloneIdeaCancelBtn = document.getElementById("detailStandaloneIdeaCancelBtn");
const detailStandaloneIdeaNewBody = document.getElementById("detailStandaloneIdeaNewBody");
const detailStandaloneIdeaNewInput = document.getElementById("detailStandaloneIdeaNewInput");
const detailStandaloneIdeaNewSaveBtn = document.getElementById("detailStandaloneIdeaNewSaveBtn");
const detailStandaloneIdeaNewCancelBtn = document.getElementById("detailStandaloneIdeaNewCancelBtn");
const ideaNewBtn = document.getElementById("ideaNewBtn");
const ideaFilterStandaloneBtn = document.getElementById("ideaFilterStandaloneBtn");
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
const detailTrackedDraftBtn = document.getElementById("detailTrackedDraftBtn");
const detailTrackedStrongInput = document.getElementById("detailTrackedStrongInput");
const detailTrackedCoreInput = document.getElementById("detailTrackedCoreInput");
const detailTrackedContextInput = document.getElementById("detailTrackedContextInput");
const detailTrackedExcludeInput = document.getElementById("detailTrackedExcludeInput");
const detailTrackedRequiredInput = document.getElementById("detailTrackedRequiredInput");
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
const detailTrackedSaveDefaultsBtn = document.getElementById("detailTrackedSaveDefaultsBtn");
const detailTrackedFormSaveBtn = document.getElementById("detailTrackedFormSaveBtn");
const detailTrackedFormCancelBtn = document.getElementById("detailTrackedFormCancelBtn");
const detailTrackedDefaultsBody = document.getElementById("detailTrackedDefaultsBody");
const trackedDefaultsThresholdInput = document.getElementById("trackedDefaultsThresholdInput");
const trackedDefaultsTitleWeightInput = document.getElementById("trackedDefaultsTitleWeightInput");
const trackedDefaultsNoteWeightInput = document.getElementById("trackedDefaultsNoteWeightInput");
const trackedDefaultsSummaryWeightInput = document.getElementById("trackedDefaultsSummaryWeightInput");
const trackedDefaultsContentWeightInput = document.getElementById("trackedDefaultsContentWeightInput");
const trackedDefaultsStrongScoreInput = document.getElementById("trackedDefaultsStrongScoreInput");
const trackedDefaultsCoreScoreInput = document.getElementById("trackedDefaultsCoreScoreInput");
const trackedDefaultsContextScoreInput = document.getElementById("trackedDefaultsContextScoreInput");
const trackedDefaultsExcludePenaltyInput = document.getElementById("trackedDefaultsExcludePenaltyInput");
const trackedDefaultsSaveBtn = document.getElementById("trackedDefaultsSaveBtn");
const trackedDefaultsRestoreBtn = document.getElementById("trackedDefaultsRestoreBtn");
const detailBody = document.getElementById("detailBody");
const detailToolbarFrame = document.getElementById("detailToolbarFrame");
const detailToolbarScroll = document.getElementById("detailToolbarScroll");
const detailDailyBody = document.getElementById("detailDailyBody");
const detailDailyTitle = document.getElementById("detailDailyTitle");
const detailDailyMeta = document.getElementById("detailDailyMeta");
const detailDailyStatus = document.getElementById("detailDailyStatus");
const detailDailyContent = document.getElementById("detailDailyContent");
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
const settingsChatProviderSelect = document.getElementById("settingsChatProviderSelect");
const settingsChatProviderCurrent = document.getElementById("settingsChatProviderCurrent");
const settingsCodexChatModelSelect = document.getElementById("settingsCodexChatModelSelect");
const settingsCodexChatModelCustom = document.getElementById("settingsCodexChatModelCustom");
const settingsCodexChatModelCurrent = document.getElementById("settingsCodexChatModelCurrent");
const settingsPiChatProviderSelect = document.getElementById("settingsPiChatProviderSelect");
const settingsPiChatProviderCustom = document.getElementById("settingsPiChatProviderCustom");
const settingsPiChatModelSelect = document.getElementById("settingsPiChatModelSelect");
const settingsPiChatModelCustom = document.getElementById("settingsPiChatModelCustom");
const settingsPiChatModelCurrent = document.getElementById("settingsPiChatModelCurrent");
const settingsPiChatProviderField = document.getElementById("settingsPiChatProviderField");
const settingsPiChatModelField = document.getElementById("settingsPiChatModelField");
const settingsChatArchiveNote = document.getElementById("settingsChatArchiveNote");
const settingsSaveBtn = document.getElementById("settingsSaveBtn");
const settingsReleaseNotes = document.getElementById("settingsReleaseNotes");
const detailCloseBtn = document.getElementById("detailCloseBtn");
const detailAiBox = document.getElementById("detailAiBox");
const detailAiPoints = document.getElementById("detailAiPoints");
const detailAiConclusion = document.getElementById("detailAiConclusion");
const detailOriginalWrap = document.getElementById("detailOriginalWrap");
const detailOriginalContent = document.getElementById("detailOriginalContent");
const detailMediaGallery = document.getElementById("detailMediaGallery");
const detailRefreshTweetBtn = document.getElementById("detailRefreshTweetBtn");
const detailNoteToggleBtn = document.getElementById("detailNoteToggleBtn");
const detailNoteCard = document.getElementById("detailNoteCard");
const detailNoteText = document.getElementById("detailNoteText");
const detailNoteEditor = document.getElementById("detailNoteEditor");
const detailNoteInput = document.getElementById("detailNoteInput");
const detailNoteSaveBtn = document.getElementById("detailNoteSaveBtn");
const detailNoteCancelBtn = document.getElementById("detailNoteCancelBtn");
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
let feedKeyboardDetailTimer = null;
let feedKeyboardLoadMorePromise = null;
let feedKeyboardMode = false;
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

function inlineFeedbackNode(container, className = "") {
  if (!container) return null;
  const extraClass = className.trim();
  let feedback = Array.from(container.children).find((child) => (
    child.classList?.contains("inline-feedback") &&
    (!extraClass || child.classList.contains(extraClass))
  ));
  if (feedback) return feedback;

  feedback = document.createElement("div");
  feedback.className = `inline-feedback hidden${extraClass ? ` ${extraClass}` : ""}`;
  feedback.setAttribute("aria-live", "polite");
  const actionRow = Array.from(container.children).reverse().find((child) => (
    child.classList?.contains("detail-note-actions")
  ));
  container.insertBefore(feedback, actionRow || null);
  return feedback;
}

function setInlineFeedback(container, message, options = {}) {
  const {
    tone = "muted",
    actionLabel = "",
    onAction = null,
    className = "",
    before = null,
  } = options;
  const feedback = inlineFeedbackNode(container, className);
  if (!feedback) return;
  if (before && before.parentElement === container && feedback.nextElementSibling !== before) {
    container.insertBefore(feedback, before);
  }
  feedback.classList.remove("hidden", "muted", "pending", "ready", "failed");
  feedback.classList.add(tone);
  feedback.setAttribute("role", tone === "failed" ? "alert" : "status");
  feedback.replaceChildren();

  const text = document.createElement("span");
  text.className = "inline-feedback-text";
  text.textContent = message || "";
  feedback.appendChild(text);

  if (actionLabel && typeof onAction === "function") {
    const action = document.createElement("button");
    action.className = "inline-feedback-action";
    action.type = "button";
    action.textContent = actionLabel;
    action.addEventListener("click", (event) => {
      event.stopPropagation();
      onAction(event);
    });
    feedback.appendChild(action);
  }
}

function clearInlineFeedback(container, className = "") {
  if (!container) return;
  const extraClass = className.trim();
  Array.from(container.children).forEach((child) => {
    if (!child.classList?.contains("inline-feedback")) return;
    if (extraClass && !child.classList.contains(extraClass)) return;
    child.classList.add("hidden");
    child.replaceChildren();
  });
}

function friendlyActionError(error, fallback) {
  const raw = String(error?.message || error || "").trim();
  if (!raw || /^[a-z0-9_:-]+$/i.test(raw)) return fallback;
  return raw;
}

function setButtonBusy(button, busy, busyLabel = "处理中…") {
  if (!button) return;
  if (busy) {
    if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent || "";
    button.textContent = busyLabel;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    return;
  }
  if (button.dataset.idleLabel) button.textContent = button.dataset.idleLabel;
  delete button.dataset.idleLabel;
  button.disabled = false;
  button.removeAttribute("aria-busy");
}

function formatReindexHint(payload) {
  const scanned = Number(payload?.scanned_files || 0);
  const changed = Number(payload?.changed_files || 0);
  const upserted = Number(payload?.upserted || 0);
  const deleted = Number(payload?.deleted_stale || 0);
  return `同步完成：扫描 ${scanned} 个文件，更新 ${changed} 个文件，写入 ${upserted} 条，清理 ${deleted} 条失效新闻`;
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

function updateReminderNavButton() {
  const due = reminderDueCount();
  if (navReminderBadge) {
    navReminderBadge.textContent = due > 0 ? String(due) : "";
    navReminderBadge.classList.toggle("hidden", due <= 0);
  }
  if (navRemindersBtn) {
    navRemindersBtn.setAttribute("aria-label", due > 0 ? `提醒，${due} 项已到期` : "提醒");
  }
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
  updateReminderNavButton();
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

function showListView() {
  if (trackedView) trackedView.classList.add("hidden");
  newsList.classList.remove("hidden");
}

function showTrackedView(show) {
  if (trackedView) trackedView.classList.toggle("hidden", !show);
  newsList.classList.remove("hidden");
}

function updateWorkspaceLayout() {}

function updateSourceFilterVisibility() {
  const visible = state.collection !== "tracked" && state.collection !== "search" && state.collection !== "reminders" && state.collection !== "notes" && state.collection !== "market_tags" && state.collection !== "daily" && state.collection !== "reviews";
  document.querySelectorAll("#sourceFilterPanel").forEach((node) => {
    node.classList.toggle("hidden", !visible);
  });
  if (!visible) closeMobileFilterSheet();
}

async function fetchMarketTagDefinitions() {
  const res = await fetch("/api/market-tags");
  if (!res.ok) throw new Error("market_tags_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_tags_fetch_failed");
  state.marketTagChoices = Array.isArray(data.tags) ? data.tags : [];
  return state.marketTagChoices;
}

async function fetchMarketWorkbenchPage(page = 1) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    content_filter: state.marketWorkbenchFilter || "all",
    sort_order: getNewsSortOrder(state.collection),
  });
  if (state.marketWorkbenchTag) params.set("tag", state.marketWorkbenchTag);
  const res = await fetch(`/api/market-workbench?${params.toString()}`);
  if (!res.ok) throw new Error("market_workbench_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_workbench_fetch_failed");
  state.marketTagChoices = Array.isArray(data.tags) ? data.tags : state.marketTagChoices;
  return data;
}

async function saveMarketWorkbenchPin(payload) {
  const res = await fetch("/api/market-workbench/pin", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("market_workbench_pin_save_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "market_workbench_pin_save_failed");
  return data.pin || null;
}

async function generateMarketTagSummary(tagKey) {
  const res = await fetch(`/api/market-tags/${encodeURIComponent(tagKey)}/summary/generate`, {
    method: "POST",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    const error = new Error(data.detail || data.error || "market_tag_summary_generate_failed");
    error.payload = data.summary || null;
    throw error;
  }
  return data.summary;
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

function feedKeyboardRows() {
  if (!newsList) return [];
  return Array.from(newsList.querySelectorAll(".feed-news-item"));
}

function isFeedKeyboardDesktopEnabled() {
  return Number(window.innerWidth || 0) >= FEED_KEYBOARD_NAV_MIN_WIDTH;
}

function isKeyboardInteractiveTarget(target) {
  if (!target) return false;
  if (target.isContentEditable) return true;
  if (typeof target.closest !== "function") return false;
  return !!target.closest("input, textarea, select, button, a, [contenteditable]");
}

function clearFeedKeyboardDetailTimer() {
  if (!feedKeyboardDetailTimer) return;
  window.clearTimeout(feedKeyboardDetailTimer);
  feedKeyboardDetailTimer = null;
}

function syncFeedKeyboardRows({ focusSelected = false } = {}) {
  const rows = feedKeyboardRows();
  let selectedRow = null;
  rows.forEach((row) => {
    const active = !!state.selectedId && row.dataset.id === state.selectedId;
    row.classList.toggle("selected", active);
    row.tabIndex = active ? 0 : -1;
    if (active) {
      row.setAttribute("aria-current", "page");
      selectedRow = row;
    } else {
      row.removeAttribute("aria-current");
    }
  });
  if (focusSelected && selectedRow && typeof selectedRow.focus === "function") {
    try {
      selectedRow.focus({ preventScroll: true });
    } catch {
      selectedRow.focus();
    }
  }
  return selectedRow;
}

function enterFeedKeyboardMode() {
  if (!isFeedKeyboardDesktopEnabled()) {
    feedKeyboardMode = false;
    clearFeedKeyboardDetailTimer();
    syncFeedKeyboardRows();
    return false;
  }
  feedKeyboardMode = true;
  syncFeedKeyboardRows();
  return true;
}

function exitFeedKeyboardMode() {
  feedKeyboardMode = false;
  syncFeedKeyboardRows();
}

function scrollFeedKeyboardRowIntoView(row) {
  if (!row || typeof row.scrollIntoView !== "function") return;
  row.scrollIntoView({ block: "nearest", behavior: "auto" });
}

function scheduleFeedKeyboardDetailOpen(item) {
  clearFeedKeyboardDetailTimer();
  if (!item || !feedKeyboardMode || !isFeedKeyboardDesktopEnabled()) return;
  feedKeyboardDetailTimer = window.setTimeout(() => {
    feedKeyboardDetailTimer = null;
    if (state.selectedId !== item.id) return;
    openItemDetail(item);
  }, FEED_KEYBOARD_DETAIL_DELAY_MS);
}

function selectFeedKeyboardRow(row) {
  const itemId = row?.dataset?.id || "";
  const item = itemId ? state.itemsById.get(itemId) : null;
  if (!item) return false;
  const changed = state.selectedId !== item.id;
  if (changed) {
    resetDetailChatState();
    stopDetailPolling();
  }
  state.itemsById.set(item.id, item);
  state.selectedId = item.id;
  state.detailReturnToTrackedTopicId = null;
  const selectedRow = syncFeedKeyboardRows({ focusSelected: true }) || row;
  scrollFeedKeyboardRowIntoView(selectedRow);
  renderDetail(state.itemsById.get(item.id) || item);
  scheduleFeedKeyboardDetailOpen(item);
  return true;
}

async function moveFeedKeyboardSelection(delta) {
  if (!feedKeyboardMode || !isFeedKeyboardDesktopEnabled() || state.loading) return;
  const rows = feedKeyboardRows();
  if (!rows.length) return;
  const currentIndex = rows.findIndex((row) => row.dataset.id === state.selectedId);
  if (currentIndex < 0) {
    if (delta > 0) selectFeedKeyboardRow(rows[0]);
    return;
  }
  const nextIndex = currentIndex + delta;
  if (nextIndex >= 0 && nextIndex < rows.length) {
    selectFeedKeyboardRow(rows[nextIndex]);
    return;
  }
  if (delta <= 0 || currentIndex !== rows.length - 1 || !state.hasMore || feedKeyboardLoadMorePromise) return;

  const currentId = state.selectedId;
  feedKeyboardLoadMorePromise = loadNextPage()
    .then(() => {
      const nextRows = feedKeyboardRows();
      const stillCurrentIndex = nextRows.findIndex((row) => row.dataset.id === currentId);
      const nextRow = stillCurrentIndex >= 0 ? nextRows[stillCurrentIndex + 1] : null;
      if (state.selectedId === currentId && nextRow) selectFeedKeyboardRow(nextRow);
    })
    .catch(() => {})
    .finally(() => {
      feedKeyboardLoadMorePromise = null;
    });
  await feedKeyboardLoadMorePromise;
}

function handleFeedKeyboardKeydown(event) {
  if (!feedKeyboardMode || !isFeedKeyboardDesktopEnabled()) return;
  if (event.isComposing || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
  if (isKeyboardInteractiveTarget(event.target)) return;

  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    event.stopPropagation();
    moveFeedKeyboardSelection(event.key === "ArrowDown" ? 1 : -1).catch(() => {});
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    exitFeedKeyboardMode();
  }
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
  if (!item || state.collection === "search" || state.collection === "reminders") return false;
  let inCollection = false;
  if (state.collection === "feed") inCollection = true;
  else if (state.collection === "favorites") inCollection = !!item.favorite_at;
  else if (state.collection === "important") inCollection = !!item.important_at;
  else if (state.collection === "read_later") {
    const detailReady = Number(item.detail_ready || 0) === 1;
    if (state.readFilter === "unread") inCollection = !!item.read_later_at;
    else if (state.readFilter === "read") inCollection = detailReady && !item.read_later_at;
    else inCollection = !!item.read_later_at || detailReady;
  }
  else if (state.collection === "notes") inCollection = !!item.has_note;
  else if (state.collection === "market_tags") inCollection = !!item.has_market_tags;
  if (!inCollection) return false;
  if (state.collection === "read_later") return true;
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

  const defaultModelValue = (catalog?.resolved_default_model || "").trim();
  const values = new Set([""]);
  const realOptions = [];
  options.forEach((item) => {
    const value = (item?.value || "").trim();
    if (!value || values.has(value)) return;
    values.add(value);
    const option = document.createElement("option");
    option.value = value;
    option.textContent = item?.label || value;
    realOptions.push(option);
  });

  // 当默认模型已在可选项中时，不再单独显示"默认：X"占位项，直接预选中那条；
  // 否则保留占位项以支持"留空=用默认模型"。
  const defaultInOptions = !!defaultModelValue && values.has(defaultModelValue);
  if (!defaultInOptions) {
    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = catalog?.default_label ? `默认：${catalog.default_label}` : "deepseek-v4-flash";
    select.appendChild(defaultOption);
  }
  realOptions.forEach((option) => select.appendChild(option));

  // 已保存但不在当前目录内的值，追加为下拉选项并选中，避免已保存配置因目录变化/检测失败而消失；
  // 用户仍可选"自定义输入..."输入新值。
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
    select.value = defaultInOptions ? defaultModelValue : "";
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
  if (settingsChatProviderSelect) {
    settingsChatProviderSelect.value = llm.chat?.provider || "codex";
  }
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
  populateModelSelect(
    settingsPiChatProviderSelect,
    settingsPiChatProviderCustom,
    {
      options: (state.runtimeSettings?.model_catalogs?.pi_chat?.provider_options) || [{ value: "ollama", label: "ollama" }],
      resolved_default_model: (state.runtimeSettings?.model_catalogs?.pi_chat?.resolved_default_provider) || "ollama",
      default_label: (state.runtimeSettings?.model_catalogs?.pi_chat?.resolved_default_provider) || "ollama",
    },
    llm.pi_chat?.provider || "ollama",
  );
  populateModelSelect(
    settingsPiChatModelSelect,
    settingsPiChatModelCustom,
    state.runtimeSettings?.model_catalogs?.pi_chat,
    llm.pi_chat?.model || "",
  );
  if (settingsTranslationModelCurrent) {
    const currentTranslationModel = (llm.translation?.model || "").trim();
    const catalogResolvedDefault = state.runtimeSettings?.model_catalogs?.translation?.resolved_default_model;
    if (!catalogResolvedDefault) {
      console.warn("[settings] model catalog missing resolved_default_model; falling back to deepseek-v4-flash");
    }
    const resolvedDefaultTranslationModel = (catalogResolvedDefault || "deepseek-v4-flash").trim();
    if (currentTranslationModel) {
      settingsTranslationModelCurrent.textContent = currentTranslationModel === resolvedDefaultTranslationModel
        ? `当前：${currentTranslationModel}`
        : `当前：${currentTranslationModel} · 结构化兼容性未验证`;
    } else {
      settingsTranslationModelCurrent.textContent = `当前：${resolvedDefaultTranslationModel}（默认）`;
    }
  }
  if (settingsChatProviderCurrent) {
    const providerLabel = { codex: "Codex", pi: "Pi" }[llm.chat?.provider || "codex"];
    settingsChatProviderCurrent.textContent = `当前：${providerLabel}`;
  }
  if (settingsCodexChatModelCurrent) {
    const currentCodexModel = (llm.codex_chat?.model || "").trim();
    settingsCodexChatModelCurrent.textContent = currentCodexModel
      ? `当前：${currentCodexModel}`
      : "当前：Codex 默认模型";
  }
  if (settingsPiChatModelCurrent) {
    const currentPiModel = (llm.pi_chat?.model || "").trim();
    settingsPiChatModelCurrent.textContent = currentPiModel
      ? `当前：${currentPiModel}`
      : "当前：Pi 默认模型";
  }
  renderChatProviderFieldVisibility();
}

function renderChatProviderFieldVisibility() {
  if (!settingsChatProviderSelect) return;
  const isPi = settingsChatProviderSelect.value === "pi";
  if (settingsCodexChatModelSelect) {
    const field = settingsCodexChatModelSelect.closest(".settings-field");
    if (field) field.classList.toggle("hidden", isPi);
  }
  if (settingsPiChatProviderField) {
    settingsPiChatProviderField.classList.toggle("hidden", !isPi);
  }
  if (settingsPiChatModelField) {
    settingsPiChatModelField.classList.toggle("hidden", !isPi);
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
  const draftChatProvider = settingsChatProviderSelect?.value || "codex";
  const draftCodexChatModel = readModelSetting(settingsCodexChatModelSelect, settingsCodexChatModelCustom);
  const draftPiChatProvider = readModelSetting(settingsPiChatProviderSelect, settingsPiChatProviderCustom);
  const draftPiChatModel = readModelSetting(settingsPiChatModelSelect, settingsPiChatModelCustom);
  state.settingsSaving = true;
  renderSettingsOverlay();
  try {
    const previousProvider = state.runtimeSettings?.llm?.chat?.provider || "codex";
    const previousCodexModel = state.runtimeSettings?.llm?.codex_chat?.model || "";
    const previousPiProvider = state.runtimeSettings?.llm?.pi_chat?.provider || "";
    const previousPiModel = state.runtimeSettings?.llm?.pi_chat?.model || "";
    const payload = {
      llm: {
        translation: {
          provider: draftTranslationProvider,
          model: draftTranslationModel,
        },
        chat: {
          provider: draftChatProvider,
        },
        codex_chat: {
          model: draftCodexChatModel,
        },
        pi_chat: {
          provider: draftPiChatProvider,
          model: draftPiChatModel,
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
    const currentProvider = data.llm?.chat?.provider || "codex";
    const currentCodexModel = data.llm?.codex_chat?.model || "";
    const currentPiProvider = data.llm?.pi_chat?.provider || "";
    const currentPiModel = data.llm?.pi_chat?.model || "";
    const providerChanged = currentProvider !== previousProvider;
    const modelChanged = currentProvider === "codex"
      ? currentCodexModel !== previousCodexModel
      : (currentPiModel !== previousPiModel || currentPiProvider !== previousPiProvider);
    if (providerChanged || modelChanged) {
      state.detailChatSessionId = "";
      state.detailChatProvider = "";
      state.detailChatModel = "";
      state.detailChatMessages = [];
      state.detailChatStatus = `${currentProvider === "pi" ? "Pi" : "Codex"} chat 配置已切换，当前临时对话已清空。`;
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
    item.read_later_done_at = st.read_later_done_at;
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
  if (name === "target") {
    return `<svg ${common}><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3"/><path d="M12 19v3"/><path d="M2 12h3"/><path d="M19 12h3"/></svg>`;
  }
  if (name === "newspaper") {
    return `<svg ${common}><path d="M6.5 5.5h10.8a1.2 1.2 0 0 1 1.2 1.2v11.8H7.7a2.2 2.2 0 0 1-2.2-2.2V6.5a1 1 0 0 0-2 0v9.8a2.2 2.2 0 0 0 2.2 2.2"/><path d="M9 9h6"/><path d="M9 12.5h6"/><path d="M9 16h4"/></svg>`;
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

function canonicalSourceIconKey(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  if (sourceIconMap[raw]) return raw;
  if (sourceIconAliases[raw]) return sourceIconAliases[raw];
  const prefix = raw.split(/[·•-]/)[0].trim();
  if (sourceIconMap[prefix]) return prefix;
  return sourceIconAliases[prefix] || "";
}

function sourceIconKeyFromUrl(url) {
  if (!url) return "";
  try {
    let host = new URL(url).hostname.toLowerCase();
    if (host.startsWith("www.")) host = host.slice(4);
    if (host === "x.com" || host === "twitter.com") return "x";
    if (host.endsWith("reuters.com")) return "reuters";
    if (host.endsWith("bloomberg.com")) return "bloomberg";
    if (host.endsWith("techcrunch.com")) return "techcrunch";
    if (host.endsWith("arstechnica.com")) return "ars";
  } catch {
    return "";
  }
  return "";
}

function sourceIconKey(item) {
  return (
    canonicalSourceIconKey(item?.source_key) ||
    canonicalSourceIconKey(item?.source_type) ||
    canonicalSourceIconKey(item?.source_name) ||
    sourceIconKeyFromUrl(item?.url) ||
    canonicalSourceIconKey(sourcePrefix(item?.source)) ||
    canonicalSourceIconKey(item?.source)
  );
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

  const iconSrc = sourceIconMap[sourceIconKey(item)] || "";

  if (iconSrc) {
    const img = document.createElement("img");
    img.className = "source-icon-img";
    img.src = iconSrc;
    img.alt = item.source_name || sourcePrefix(item.source) || "来源图标";
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

function truncateTitleText(value, limit = TITLE_CHAR_LIMIT) {
  const title = String(value || "");
  if (title.length <= limit) return title;
  return `${title.slice(0, limit).trimEnd()}...`;
}

function rowTitleText(item) {
  const title = String(item?.title || "");
  if (item?.source_type === "twitter" && title.length > 100) {
    return truncateTitleText(title);
  }
  return title;
}

function rowIsRead(li) {
  return li.dataset.read === "1";
}

function syncRowUI(li, item) {
  li.dataset.read = item.read_at ? "1" : "0";
  li.dataset.favorite = item.favorite_at ? "1" : "0";
  li.dataset.important = item.important_at ? "1" : "0";
  li.dataset.readLater = item.read_later_at ? "1" : "0";
  li.dataset.readLaterCompleted = Number(item.detail_ready || 0) === 1 && !item.read_later_at ? "1" : "0";
  li.dataset.readLaterDone = item.read_later_done_at ? "1" : "0";
  li.dataset.hasReminder = Number(item.active_reminder_count || 0) > 0 ? "1" : "0";
  li.dataset.detailStatus = item.detail_status || "none";

  const unreadDot = li.querySelector(".unread-dot");
  if (unreadDot) unreadDot.classList.toggle("is-read", !!item.read_at);
  const noteBadge = li.querySelector(".row-note-badge");
  const noteState = li.querySelector(".row-note-state");
  let hasNote = false;
  if (noteBadge) {
    hasNote = Number(item.has_note || 0) === 1;
    noteBadge.classList.toggle("hidden", !hasNote);
  }
  const reminderBadge = li.querySelector(".reminder-badge");
  let hasReminder = false;
  if (reminderBadge) {
    const activeCount = Number(item.active_reminder_count || 0);
    const dueCount = Number(item.due_reminder_count || 0);
    hasReminder = activeCount > 0;
    reminderBadge.textContent = dueCount > 0 ? `到期 ${dueCount}` : `提醒 ${activeCount}`;
    reminderBadge.classList.toggle("hidden", !hasReminder);
    reminderBadge.classList.toggle("due", dueCount > 0);
  }
  const notePreview = li.querySelector(".row-note-preview");
  let hasNotePreview = false;
  if (notePreview) {
    const previewText = typeof item.note_preview === "string" ? item.note_preview.trim() : "";
    hasNotePreview = !!previewText;
    notePreview.textContent = previewText;
    notePreview.classList.toggle("hidden", !hasNotePreview);
  }
  if (noteState) noteState.classList.toggle("hidden", !hasNote && !hasNotePreview);

  const marketTagsWrap = li.querySelector(".market-tags");
  const titleEl = li.querySelector(".title");
  let hasMarketTags = false;
  if (marketTagsWrap) {
    marketTagsWrap.innerHTML = "";
    const tags = marketTagsFromItem(item);
    hasMarketTags = tags.length > 0;
    tags.forEach((mt) => {
      const badge = document.createElement("span");
      badge.className = `market-tag-badge ${mt.direction}`;
      badge.textContent = mt.tag;
      marketTagsWrap.appendChild(badge);
    });
    marketTagsWrap.classList.toggle("hidden", !hasMarketTags);
  }

  const contextStrip = li.querySelector(".row-context-strip");
  const hasContextStrip = hasReminder || hasMarketTags;
  if (contextStrip) contextStrip.classList.toggle("hidden", !hasContextStrip);
  const context = li.querySelector(".news-row-context");
  if (context) context.classList.toggle("hidden", !hasNote && !hasNotePreview && !hasContextStrip);

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
    const completed = detailReady && !item.read_later_at;
    const tone = item.read_later_at
      ? (detailFailed ? "danger" : (detailReady ? "success" : "warning"))
      : (completed ? "success" : (detailReady ? "success" : "default"));
    applyIcon(readLaterBtn, "bookmark", {
      filled: !!item.read_later_at,
      tone,
      label: item.read_later_at
        ? (detailFailed ? "取消稍后再看（详情抓取失败）" : (detailReady ? "取消稍后再看（详情已就绪）" : "取消稍后再看（详情抓取中）"))
        : (completed ? "重新加入稍后再看" : (detailReady ? "详情已缓存，加入稍后再看" : "稍后再看")),
    });
  }

  const selected = state.selectedId === item.id;
  li.classList.toggle("selected", selected);
  li.tabIndex = selected ? 0 : -1;
  if (selected) li.setAttribute("aria-current", "page");
  else li.removeAttribute("aria-current");
}

function updateFilterButtons() {
  const showReadFilter = state.collection === "feed";
  const showReadLaterFilter = state.collection === "read_later";
  readFilterToggleBtn.classList.toggle("hidden", !showReadFilter);
  if (showReadFilter) {
    const isAll = state.readFilter === "all";
    applyIcon(readFilterToggleBtn, "circle", {
      filled: isAll,
      tone: isAll ? "default" : "muted",
      label: isAll ? "全部显示" : "仅未读",
    });
  }
  if (!readLaterFilterBar) return;
  readLaterFilterBar.classList.toggle("hidden", !showReadLaterFilter);
  if (!showReadLaterFilter) return;
  [
    [readLaterFilterUnreadBtn, "unread"],
    [readLaterFilterReadBtn, "read"],
    [readLaterFilterAllBtn, "all"],
  ].forEach(([button, value]) => {
    if (!button) return;
    button.classList.toggle("active", state.readFilter === value);
  });
}

function updateIdeaFilterBar() {
  const visible = state.collection === "notes";
  if (ideaFilterBar) ideaFilterBar.classList.toggle("hidden", !visible);

  const reviewVisible = state.collection === "reviews";
  if (reviewFilterBar) {
    reviewFilterBar.classList.toggle("hidden", !reviewVisible);
    if (reviewVisible) {
      [
        [reviewFilterAllBtn, "all"],
        [reviewFilterActiveBtn, "in_progress"],
        [reviewFilterPendingBtn, "pending_review"],
        [reviewFilterDoneBtn, "done"],
      ].forEach(([button, value]) => {
        if (!button) return;
        button.classList.toggle("active", state.reviewFilter === value);
      });
    }
  }

  const showOutcomeFilter = reviewVisible && state.reviewFilter === "done";
  if (reviewOutcomeFilterBar) {
    reviewOutcomeFilterBar.classList.toggle("hidden", !showOutcomeFilter);
    if (showOutcomeFilter) {
      [
        [reviewOutcomeFilterAllBtn, "all"],
        [reviewOutcomeFilterConfirmedBtn, "confirmed"],
        [reviewOutcomeFilterRefutedBtn, "refuted"],
        [reviewOutcomeFilterInconclusiveBtn, "inconclusive"],
      ].forEach(([button, value]) => {
        if (!button) return;
        button.classList.toggle("active", state.reviewOutcomeFilter === value);
      });
    }
  }

  if (!visible) return;
  [
    [ideaFilterAllBtn, "all"],
    [ideaFilterArticleBtn, "article"],
    [ideaFilterTrendBtn, "trend"],
    [ideaFilterStandaloneBtn, "standalone"],
  ].forEach(([button, value]) => {
    if (!button) return;
    button.classList.toggle("active", state.ideaFilter === value);
  });
}

function renderMarketWorkbenchControls() {
  if (!marketWorkbenchTagSelect || !marketWorkbenchFilterSelect) return;
  marketWorkbenchTagSelect.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "全部板块";
  marketWorkbenchTagSelect.appendChild(allOption);
  activeMarketTagChoices().forEach((tag) => {
    const option = document.createElement("option");
    option.value = tag.key;
    option.textContent = tag.display_name;
    marketWorkbenchTagSelect.appendChild(option);
  });
  marketWorkbenchTagSelect.value = state.marketWorkbenchTag || "";
  marketWorkbenchFilterSelect.value = state.marketWorkbenchFilter || "all";
}

function activeMarketWorkbenchPinTitle() {
  if (!state.marketWorkbenchTag) return "板块集合置顶";
  const selected = activeMarketTagChoices().find((tag) => tag.key === state.marketWorkbenchTag);
  return `${selected?.display_name || state.marketWorkbenchTag} · 置顶信息`;
}

function activeMarketWorkbenchPinScopeLabel() {
  if (!state.marketWorkbenchTag) return "全部板块";
  const selected = activeMarketTagChoices().find((tag) => tag.key === state.marketWorkbenchTag);
  return selected?.display_name || state.marketWorkbenchTag;
}

function marketWorkbenchPinPreview(note) {
  const text = String(note || "").trim().replace(/\s+/g, " ");
  if (!text) return "添加置顶信息";
  return text.length > 80 ? `${text.slice(0, 80)}...` : text;
}

function renderMarketWorkbenchPinCard() {
  if (!marketWorkbenchPinCard) return;
  const visible = state.collection === "market_tags";
  marketWorkbenchPinCard.classList.toggle("hidden", !visible);
  if (!visible) {
    marketWorkbenchPinCard.innerHTML = "";
    return;
  }

  const pin = state.marketWorkbenchPin || {
    note: "",
    collapsed: 0,
    title: activeMarketWorkbenchPinTitle(),
    scope_label: activeMarketWorkbenchPinScopeLabel(),
  };
  const note = String(pin.note || "");
  const collapsed = Number(pin.collapsed || 0) === 1;
  const titleText = pin.title || activeMarketWorkbenchPinTitle();
  const scopeLabel = pin.scope_label || activeMarketWorkbenchPinScopeLabel();
  const updatedText = pin.updated_at ? `更新 ${pin.updated_at}` : "尚未保存";

  marketWorkbenchPinCard.innerHTML = "";

  if (state.marketWorkbenchPinEditing) {
    const title = document.createElement("h4");
    title.textContent = titleText;
    const meta = document.createElement("div");
    meta.className = "detail-meta";
    meta.textContent = `${scopeLabel} · 最多 5000 字`;

    const textarea = document.createElement("textarea");
    textarea.className = "detail-note-input market-pin-textarea";
    textarea.rows = 5;
    textarea.maxLength = 5000;
    textarea.placeholder = "记录这个板块工作台的长期说明、判断或操作备忘...";
    textarea.value = note;

    const collapsedLabel = document.createElement("label");
    collapsedLabel.className = "detail-inline-checkbox";
    const collapsedText = document.createElement("span");
    collapsedText.textContent = "默认折叠";
    const collapsedInput = document.createElement("input");
    collapsedInput.type = "checkbox";
    collapsedInput.checked = collapsed;
    collapsedLabel.appendChild(collapsedText);
    collapsedLabel.appendChild(collapsedInput);

    const actions = document.createElement("div");
    actions.className = "detail-note-actions";
    const saveBtn = document.createElement("button");
    saveBtn.className = "detail-retry-btn";
    saveBtn.type = "button";
    saveBtn.textContent = state.marketWorkbenchPinSaving ? "保存中..." : "保存";
    saveBtn.disabled = state.marketWorkbenchPinSaving;
    const cancelBtn = document.createElement("button");
    cancelBtn.className = "detail-retry-btn";
    cancelBtn.type = "button";
    cancelBtn.textContent = "取消";
    cancelBtn.disabled = state.marketWorkbenchPinSaving;

    saveBtn.addEventListener("click", async () => {
      state.marketWorkbenchPinSaving = true;
      renderMarketWorkbenchPinCard();
      try {
        const saved = await saveMarketWorkbenchPin({
          tag_key: state.marketWorkbenchTag || "",
          note: textarea.value || "",
          collapsed: collapsedInput.checked,
        });
        state.marketWorkbenchPin = saved;
        state.marketWorkbenchPinEditing = false;
        setHint("置顶信息已保存");
      } catch (error) {
        setHint(`保存置顶信息失败：${error?.message || error}`);
      } finally {
        state.marketWorkbenchPinSaving = false;
        renderMarketWorkbenchPinCard();
      }
    });

    cancelBtn.addEventListener("click", () => {
      state.marketWorkbenchPinEditing = false;
      state.marketWorkbenchPinSaving = false;
      renderMarketWorkbenchPinCard();
    });

    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
    marketWorkbenchPinCard.appendChild(title);
    marketWorkbenchPinCard.appendChild(meta);
    marketWorkbenchPinCard.appendChild(textarea);
    marketWorkbenchPinCard.appendChild(collapsedLabel);
    marketWorkbenchPinCard.appendChild(actions);
    return;
  }

  const header = document.createElement("div");
  header.className = "market-pin-header";
  const titleWrap = document.createElement("div");
  titleWrap.className = "market-pin-title-wrap";
  const title = document.createElement("h4");
  title.textContent = titleText;
  const meta = document.createElement("div");
  meta.className = "detail-meta";
  meta.textContent = `${scopeLabel} · ${updatedText}`;
  titleWrap.appendChild(title);
  titleWrap.appendChild(meta);

  const editBtn = document.createElement("button");
  editBtn.className = "detail-retry-btn";
  editBtn.type = "button";
  editBtn.textContent = note ? "编辑" : "添加置顶信息";
  editBtn.addEventListener("click", () => {
    state.marketWorkbenchPinEditing = true;
    renderMarketWorkbenchPinCard();
  });
  header.appendChild(titleWrap);
  header.appendChild(editBtn);

  const details = document.createElement("details");
  details.className = "market-summary-details";
  details.open = !collapsed;
  details.addEventListener("toggle", async () => {
    const nextCollapsed = details.open ? 0 : 1;
    if (nextCollapsed === Number((state.marketWorkbenchPin?.collapsed || 0))) return;
    try {
      const saved = await saveMarketWorkbenchPin({
        tag_key: state.marketWorkbenchTag || "",
        note,
        collapsed: nextCollapsed === 1,
      });
      state.marketWorkbenchPin = saved;
      renderMarketWorkbenchPinCard();
    } catch (error) {
      details.open = !details.open;
      setHint(`保存折叠状态失败：${error?.message || error}`);
    }
  });

  const detailsSummary = document.createElement("summary");
  detailsSummary.className = "market-summary-toggle";
  const summaryMeta = document.createElement("div");
  summaryMeta.className = "market-summary-toggle-text";
  const preview = document.createElement("div");
  preview.className = "detail-meta";
  preview.textContent = marketWorkbenchPinPreview(note);
  summaryMeta.appendChild(preview);
  detailsSummary.appendChild(summaryMeta);
  const caret = document.createElement("span");
  caret.className = "market-summary-caret";
  caret.textContent = collapsed ? "展开" : "收起";
  detailsSummary.appendChild(caret);
  details.appendChild(detailsSummary);

  const text = document.createElement("p");
  text.className = "detail-note-text";
  text.textContent = note || "当前还没有置顶信息。";
  details.appendChild(text);

  marketWorkbenchPinCard.appendChild(header);
  marketWorkbenchPinCard.appendChild(details);
}

function updateMarketWorkbenchBar() {
  if (!marketWorkbenchBar) return;
  const visible = state.collection === "market_tags";
  marketWorkbenchBar.classList.toggle("hidden", !visible);
  if (!visible) {
    removeMarketWorkbenchSummaryInline();
    renderMarketWorkbenchPinCard();
    return;
  }
  renderMarketWorkbenchControls();
  if (marketWorkbenchSummaryBtn) {
    marketWorkbenchSummaryBtn.classList.toggle("hidden", !state.marketWorkbenchTag);
  }
  renderMarketWorkbenchPinCard();
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
    state.collection === "daily" ||
    state.collection === "favorites" ||
    state.collection === "reminders" ||
    state.collection === "important" ||
    state.collection === "notes" ||
    state.collection === "market_tags" ||
    state.collection === "reviews"
  ) {
    markAllReadBtn.classList.add("hidden");
    markAllReadBtn.disabled = false;
    return;
  }
  markAllReadBtn.classList.remove("hidden");
  if (state.collection === "read_later") {
    const hideForCompleted = state.readFilter === "read";
    markAllReadBtn.classList.toggle("hidden", hideForCompleted);
    if (hideForCompleted) {
      markAllReadBtn.disabled = false;
      return;
    }
    applyIcon(markAllReadBtn, "bookmark", { label: "全部看完（完成当前未读稍后阅读）" });
  } else {
    applyIcon(markAllReadBtn, "check-circle", { label: "当前结果全部标为已读" });
  }
}

function updateRefreshButton() {
  if (!refreshBtn) return;
  const visible = state.collection !== "reviews";
  refreshBtn.classList.toggle("hidden", !visible);
  if (!visible) refreshBtn.disabled = false;
}

function updateTrackedCreateButton() {
  if (trackedCreateInlineBtn) trackedCreateInlineBtn.classList.toggle("hidden", state.collection !== "tracked");
  if (trackedDefaultsInlineBtn) trackedDefaultsInlineBtn.classList.toggle("hidden", state.collection !== "tracked");
}

function mobileFilterAvailable(collection = state.collection) {
  return ["feed", "read_later", "important", "favorites"].includes(collection);
}

function updateMobileSourceEntryButton() {
  if (!mobileSourceEntryBtn) return;
  const visible = mobileFilterAvailable();
  const label = state.sourceFilter === "all" ? "来源" : sourceLabel(state.sourceFilter);
  mobileSourceEntryBtn.classList.toggle("hidden", !visible);
  mobileSourceEntryBtn.classList.toggle("active", visible && state.sourceFilter !== "all");
  mobileSourceEntryBtn.textContent = label;
  mobileSourceEntryBtn.title = `来源筛选：${sourceLabel(state.sourceFilter)}`;
  mobileSourceEntryBtn.setAttribute("aria-label", `来源筛选，当前 ${sourceLabel(state.sourceFilter)}`);
}

function updateCollectionButtons() {
  [
    [navSearchBtn, "search"],
    [navFeedBtn, "feed"],
    [navDailyBtn, "daily"],
    [navReadLaterBtn, "read_later"],
    [navImportantBtn, "important"],
    [navRemindersBtn, "reminders"],
    [navFavoritesBtn, "favorites"],
    [navNotesBtn, "notes"],
    [navReviewsBtn, "reviews"],
    [navTrackedBtn, "tracked"],
    [navMarketTagsBtn, "market_tags"],
  ].forEach(([button, collection]) => {
    if (!button) return;
    const active = state.collection === collection;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (mobileCollectionTriggerBtn) {
    const active = state.collection === "feed";
    mobileCollectionTriggerBtn.classList.toggle("active", active);
    mobileCollectionTriggerBtn.textContent = "新闻";
    if (active) mobileCollectionTriggerBtn.setAttribute("aria-current", "page");
    else mobileCollectionTriggerBtn.removeAttribute("aria-current");
  }
  if (mobileReadLaterTabBtn) {
    const active = state.collection === "read_later";
    mobileReadLaterTabBtn.classList.toggle("active", active);
    if (active) mobileReadLaterTabBtn.setAttribute("aria-current", "page");
    else mobileReadLaterTabBtn.removeAttribute("aria-current");
  }
  if (mobileMoreTabBtn) {
    const moreCollectionLabels = {
      search: "搜索",
      daily: "日报",
      important: "重要",
      favorites: "收藏",
      reminders: "提醒",
      notes: "想法",
      reviews: "复盘",
      tracked: "跟踪",
      market_tags: "板块",
    };
    const active = state.collection !== "feed" && state.collection !== "read_later";
    mobileMoreTabBtn.classList.toggle("active", active);
    mobileMoreTabBtn.textContent = active ? (moreCollectionLabels[state.collection] || "更多") : "更多";
    if (active) mobileMoreTabBtn.setAttribute("aria-current", "page");
    else mobileMoreTabBtn.removeAttribute("aria-current");
  }
  updateMobileSourceEntryButton();
  if (manageMarketTagsBtn) {
    manageMarketTagsBtn.classList.toggle("hidden", state.collection !== "market_tags");
    if (state.collection === "market_tags") {
      applyIcon(manageMarketTagsBtn, "pen", {
        tone: state.tagAdminOpen ? "accent" : "default",
        label: "管理板块",
      });
    }
  }
  updateIdeaFilterBar();
  updateMarketWorkbenchBar();
  updateReminderFilterBar();
  updateTrackedCreateButton();
}

function updateMobileFilterCollectionText() {
  if (!mobileFilterCollection) return;
  const names = {
    search: "搜索",
    feed: "新闻",
    daily: "日报",
    favorites: "收藏",
    reminders: "提醒",
    important: "重要新闻",
    read_later: "稍后阅读",
    notes: "想法",
    tracked: "跟踪",
    market_tags: "板块",
    reviews: "复盘",
  };
  mobileFilterCollection.textContent = `当前视图：${names[state.collection] || "新闻"}`;
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
  updateCollectionButtons();
}

function appendMobileMoreAction(container, item) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "mobile-more-row";
  btn.classList.toggle("active", !!item.active);
  if (item.active) btn.setAttribute("aria-current", "page");
  const label = document.createElement("span");
  label.className = "mobile-more-label";
  label.textContent = item.label;
  const desc = document.createElement("span");
  desc.className = "mobile-more-desc";
  desc.textContent = item.desc || "";
  btn.appendChild(label);
  btn.appendChild(desc);
  btn.addEventListener("click", async (event) => {
    event.stopPropagation();
    await item.onClick();
  });
  container.appendChild(btn);
}

function appendMobileMoreSelect(container, config) {
  const label = document.createElement("label");
  label.className = "mobile-more-select-row";
  const text = document.createElement("span");
  text.className = "mobile-more-label";
  text.textContent = config.label;
  const select = document.createElement("select");
  select.className = "pref-select mobile-more-select";
  config.options.forEach((option) => {
    const opt = document.createElement("option");
    opt.value = option.value;
    opt.textContent = option.label;
    select.appendChild(opt);
  });
  select.value = config.value;
  select.addEventListener("change", () => config.onChange(select.value));
  label.appendChild(text);
  label.appendChild(select);
  container.appendChild(label);
}

function renderMobileMoreOptions() {
  if (!mobileCollectionOptions) return;
  mobileCollectionOptions.innerHTML = "";
  const groups = [
    {
      title: "阅读",
      items: [
        { key: "search", label: "搜索", desc: "标题、正文、AI、想法与板块" },
        { key: "daily", label: "日报", desc: "查看日报集合与结构化简报" },
      ],
    },
    {
      title: "个人队列",
      items: [
        { key: "important", label: "重要", desc: "已标记的重要新闻" },
        { key: "reminders", label: reminderNavLabel(), desc: "待处理与已完成提醒" },
        { key: "favorites", label: "收藏", desc: "长期保留的新闻" },
      ],
    },
    {
      title: "研究",
      items: [
        { key: "notes", label: "想法", desc: "新闻想法与板块想法" },
        { key: "reviews", label: "复盘", desc: "版本化判断复盘" },
        { key: "tracked", label: "跟踪", desc: "长期主题与时间线" },
      ],
    },
    {
      title: "市场",
      items: [
        { key: "market_tags", label: "板块", desc: "板块工作台与置顶信息" },
      ],
    },
  ];

  for (const group of groups) {
    const section = document.createElement("section");
    section.className = "mobile-more-group";
    const title = document.createElement("h4");
    title.textContent = group.title;
    section.appendChild(title);
    group.items.forEach((item) => {
      appendMobileMoreAction(section, {
        ...item,
        active: state.collection === item.key,
        onClick: async () => {
          await switchCollection(item.key);
          closeMobileCollectionSheet();
        },
      });
    });
    mobileCollectionOptions.appendChild(section);
  }

  const system = document.createElement("section");
  system.className = "mobile-more-group";
  const systemTitle = document.createElement("h4");
  systemTitle.textContent = "系统";
  system.appendChild(systemTitle);
  appendMobileMoreAction(system, {
    label: "设置",
    desc: "模型、服务与运行配置",
    onClick: async () => {
      closeMobileCollectionSheet();
      state.settingsSection = "services";
      await openSettingsOverlay();
    },
  });
  appendMobileMoreSelect(system, {
    label: "外观",
    value: themeModeSelect?.value || "system",
    options: [
      { value: "system", label: "跟随系统" },
      { value: "light", label: "浅色" },
      { value: "dark", label: "深色" },
    ],
    onChange: applyThemeMode,
  });
  appendMobileMoreSelect(system, {
    label: "正文字体",
    value: detailFontSelect?.value || "medium",
    options: [
      { value: "small", label: "小" },
      { value: "medium", label: "中" },
      { value: "large", label: "大" },
    ],
    onChange: applyDetailFontMode,
  });
  appendMobileMoreAction(system, {
    label: "错误统计",
    desc: "查看当日处理错误",
    onClick: async () => {
      closeMobileCollectionSheet();
      await openErrorStatsPanel();
    },
  });
  appendMobileMoreAction(system, {
    label: "Release Notes",
    desc: "查看 README 中的版本记录",
    onClick: async () => {
      closeMobileCollectionSheet();
      state.settingsSection = "release";
      await openSettingsOverlay();
    },
  });
  const version = document.createElement("div");
  version.className = "mobile-more-version";
  version.textContent = "News Reader v2.1.0.12";
  system.appendChild(version);
  mobileCollectionOptions.appendChild(system);
}

function openMobileCollectionSheet() {
  if (!mobileCollectionSheet) return;
  closeMobileFilterSheet();
  renderMobileMoreOptions();
  mobileCollectionSheet.classList.remove("hidden");
  mobileCollectionSheet.setAttribute("aria-hidden", "false");
  if (mobileCollectionTriggerBtn) mobileCollectionTriggerBtn.classList.remove("active");
  if (mobileReadLaterTabBtn) mobileReadLaterTabBtn.classList.remove("active");
  if (mobileMoreTabBtn) mobileMoreTabBtn.classList.add("active");
}

function openMobileFilterSheet() {
  if (!mobileFilterSheet || !mobileFilterAvailable()) return;
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
  const totalCount = latestSourceOptions.reduce((sum, src) => sum + Number(src.count || 0), 0);
  if (sourceFilterCount) {
    sourceFilterCount.textContent = latestSourceOptions.length ? `${latestSourceOptions.length} 个源` : "";
  }

  const setButtonContent = (btn, label, count, desktop) => {
    if (!desktop) {
      btn.textContent = count == null ? label : `${label} (${count})`;
      return;
    }
    const labelEl = document.createElement("span");
    labelEl.className = "source-filter-label";
    labelEl.textContent = label;
    btn.appendChild(labelEl);
    if (count != null) {
      const countEl = document.createElement("span");
      countEl.className = "source-filter-badge";
      countEl.textContent = String(count);
      btn.appendChild(countEl);
    }
  };

  const fillContainer = (container, className, desktop = false) => {
    if (!container) return;
    container.innerHTML = "";

    const allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = className;
    allBtn.dataset.sourceKey = "all";
    setButtonContent(allBtn, "全部来源", totalCount || null, desktop);
    allBtn.setAttribute("aria-label", totalCount ? `全部来源，${totalCount} 条` : "全部来源");
    allBtn.classList.toggle("active", state.sourceFilter === "all");
    allBtn.setAttribute("aria-pressed", String(state.sourceFilter === "all"));
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
      setButtonContent(btn, sourceLabel(src.key) || src.label, src.count, desktop);
      btn.setAttribute("aria-label", `${sourceLabel(src.key) || src.label}，${src.count} 条`);
      btn.classList.toggle("active", state.sourceFilter === src.key);
      btn.setAttribute("aria-pressed", String(state.sourceFilter === src.key));
      btn.addEventListener("click", async () => {
        if (state.sourceFilter === src.key) return;
        state.sourceFilter = src.key;
        await loadFirstPage();
        closeMobileFilterSheet();
      });
      container.appendChild(btn);
    }
  };

  fillContainer(sourceFilters, "source-filter-btn", true);
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

function trackedRuleNumber(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function getTrackedDefaultRuleParams() {
  const saved = state.runtimeSettings?.tracked?.default_rule_params || {};
  return {
    title_weight: trackedRuleNumber(saved.title_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.title_weight),
    note_weight: trackedRuleNumber(saved.note_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.note_weight),
    summary_weight: trackedRuleNumber(saved.summary_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.summary_weight),
    content_weight: trackedRuleNumber(saved.content_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.content_weight),
    strong_score: trackedRuleNumber(saved.strong_score, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.strong_score),
    core_score: trackedRuleNumber(saved.core_score, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.core_score),
    context_score: trackedRuleNumber(saved.context_score, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.context_score),
    exclude_penalty: trackedRuleNumber(saved.exclude_penalty, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.exclude_penalty),
    threshold: trackedRuleNumber(saved.threshold, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.threshold),
  };
}

function trackedDefaultParamsPayloadFromInputs(inputs) {
  const fallback = getTrackedDefaultRuleParams();
  return {
    title_weight: trackedRuleNumber(inputs.title_weight?.value, fallback.title_weight),
    note_weight: trackedRuleNumber(inputs.note_weight?.value, fallback.note_weight),
    summary_weight: trackedRuleNumber(inputs.summary_weight?.value, fallback.summary_weight),
    content_weight: trackedRuleNumber(inputs.content_weight?.value, fallback.content_weight),
    strong_score: trackedRuleNumber(inputs.strong_score?.value, fallback.strong_score),
    core_score: trackedRuleNumber(inputs.core_score?.value, fallback.core_score),
    context_score: trackedRuleNumber(inputs.context_score?.value, fallback.context_score),
    exclude_penalty: trackedRuleNumber(inputs.exclude_penalty?.value, fallback.exclude_penalty),
    threshold: trackedRuleNumber(inputs.threshold?.value, fallback.threshold),
  };
}

function trackedRuleSummary(topic) {
  const rules = topic?.rules || {};
  const strong = trackedRuleList(rules.strong_phrases);
  const core = trackedRuleList(rules.core_terms);
  const context = trackedRuleList(rules.context_terms);
  const exclude = trackedRuleList(rules.exclude_terms);
  const required = trackedRuleList(rules.required_terms);
  const bits = [];
  if (strong.length) bits.push(`强短语：${strong.join(" / ")}`);
  if (core.length) bits.push(`核心词：${core.join(" / ")}`);
  if (context.length) bits.push(`场景词：${context.join(" / ")}`);
  if (exclude.length) bits.push(`排除：${exclude.join(" / ")}`);
  if (required.length) bits.push(`必要：${required.join(" / ")}`);
  bits.push(`阈值：${Number(rules.threshold || 0) || 6}`);
  return bits.join(" · ");
}

function trackedKeywordSummary(topic) {
  return trackedRuleSummary(topic);
}

function trackedDescriptionSummary(topic) {
  const strong = trackedRuleList(topic?.rules?.strong_phrases);
  const core = trackedRuleList(topic?.rules?.core_terms);
  const required = trackedRuleList(topic?.rules?.required_terms);
  if (required.length) return `必要词：${required.join(" / ")}`;
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
  title.classList.toggle("tracked-title-detail-ready", Number(item.detail_ready || 0) === 1);
  main.appendChild(title);

  const metaLine = document.createElement("div");
  metaLine.className = "tracked-timeline-meta";
  const reason = item.tracked_reason || (item.tracked_match_method === "manual" ? "手动加入" : "规则命中");
  metaLine.textContent = `${item.published_at || item.date_key || ""} · ${item.source || ""} · ${reason}`;
  main.appendChild(metaLine);

  const summaryText = item.summary;
  if (summaryText) {
    const summary = document.createElement("div");
    summary.className = "tracked-timeline-summary";
    summary.textContent = summaryText;
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
  if (trackedTimeflowBatchBar) trackedTimeflowBatchBar.classList.toggle("hidden", state.trackedDetailView !== "timeflow");
  if (trackedTimeflowBatchModeSelect) trackedTimeflowBatchModeSelect.value = state.trackedTimeflowBatchMode || "all";
}

function groupedTrackedTimelineItems(items = []) {
  const groups = [];
  let current = null;
  items.forEach((item) => {
    const dateKey = ((item.published_at || item.date_key || "").slice(0, 10) || "未知日期");
    if (!current || current.dateKey !== dateKey) {
      current = { dateKey, items: [] };
      groups.push(current);
    }
    current.items.push(item);
  });
  return groups;
}

function buildTrackedTimeflowRow(day) {
  const row = document.createElement("div");
  row.className = "tracked-timeflow-row";

  const axis = document.createElement("div");
  axis.className = "tracked-timeflow-axis";

  const dot = document.createElement("div");
  dot.className = "tracked-timeflow-dot";
  axis.appendChild(dot);

  const body = document.createElement("div");
  body.className = "tracked-timeflow-body";

  const date = document.createElement("div");
  date.className = "tracked-timeflow-date";
  date.textContent = day.date || "未知日期";
  body.appendChild(date);

  const card = document.createElement("div");
  card.className = "tracked-timeflow-card";

  const header = document.createElement("div");
  header.className = "tracked-timeflow-header";

  const meta = document.createElement("div");
  meta.className = "tracked-timeflow-meta";
  meta.textContent = `${trackedDailySummaryStatusLabel(day)} · ${Number(day.item_count || 0)} 条新闻`;
  header.appendChild(meta);

  const actions = document.createElement("div");
  actions.className = "tracked-timeflow-actions";

  const generateBtn = document.createElement("button");
  generateBtn.type = "button";
  generateBtn.className = "tracked-timeflow-action-btn";
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

  const details = document.createElement("details");
  details.className = "tracked-timeflow-details";
  const summaryToggle = document.createElement("summary");
  summaryToggle.textContent = "⌄";
  summaryToggle.title = `展开原始新闻（${Number(day.item_count || 0)} 条）`;
  summaryToggle.setAttribute("aria-label", `展开原始新闻（${Number(day.item_count || 0)} 条）`);
  details.appendChild(summaryToggle);
  actions.appendChild(details);
  header.appendChild(actions);
  card.appendChild(header);

  if (day.summary_text) {
    const summary = document.createElement("div");
    summary.className = "tracked-timeflow-summary";
    summary.textContent = day.summary_text;
    card.appendChild(summary);
  } else {
    const empty = document.createElement("div");
    empty.className = "tracked-timeflow-summary muted";
    empty.textContent = day.status === "failed" ? "上次生成失败，可重试。" : "当前还没有生成这一天的时间流总结。";
    card.appendChild(empty);
  }

  if (day.error && day.status === "failed") {
    const error = document.createElement("div");
    error.className = "tracked-timeflow-error";
    error.textContent = `失败原因：${day.error}`;
    card.appendChild(error);
  }

  const list = document.createElement("div");
  list.className = "tracked-timeflow-items";
  (Array.isArray(day.items) ? day.items : []).forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tracked-timeflow-item";
    const itemTitle = document.createElement("span");
    itemTitle.className = "tracked-timeflow-item-title";
    itemTitle.textContent = `${item.published_at || ""} · ${item.title || "未命名新闻"}`;
    itemTitle.classList.toggle("tracked-title-detail-ready", item.has_detail);
    button.appendChild(itemTitle);
    button.addEventListener("click", async () => {
      const matched = state.trackedTimelineItems.find((row) => String(row.id) === String(item.id));
      if (matched) {
        await openItemDetail(matched, { fromTrackedTopicId: state.selectedTrackedTopicId });
      }
    });
    list.appendChild(button);
  });
  details.appendChild(list);
  card.appendChild(details);
  body.appendChild(card);

  row.appendChild(axis);
  row.appendChild(body);
  return row;
}

function renderTrackedTopicEmpty(message = "选择一个跟踪主题，右栏会展示详情、回扫和时间线。") {
  closeTagAdminView();
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeReminderEditor();
  closeDetailTrackEditor();
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailTrackedDefaultsBody) detailTrackedDefaultsBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  renderDetailEmpty(message);
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
  closeReminderEditor();
  closeDetailTrackEditor();
  detailEmpty.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailTrackedDefaultsBody) detailTrackedDefaultsBody.classList.add("hidden");
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
      trackedTimelineHint.textContent = `时间流按日期新→旧展示；支持逐日生成和一键批量生成。共 ${state.trackedDailySummaries.length} 天。`;
      state.trackedDailySummaries.forEach((day) => trackedTimelineList.appendChild(buildTrackedTimeflowRow(day)));
    } else {
      trackedTimelineHint.textContent = items.length
        ? "当前主题已有原始新闻，但还没有任何时间流总结。可逐日点击“生成当日总结”。"
        : "当前主题还没有命中新闻，暂时无法生成时间流总结。";
    }
  } else {
    trackedTimelineHint.textContent = items.length
      ? `时间线按日期分组、整体新→旧，共 ${items.length} 条`
      : "当前主题还没有命中新闻。可先执行历史回扫，或从新闻详情里手动加入。";
    groupedTrackedTimelineItems(items).forEach((group) => {
      const heading = document.createElement("div");
      heading.className = "tracked-timeline-date-group";
      heading.textContent = group.dateKey || "未知日期";
      trackedTimelineList.appendChild(heading);
      group.items.forEach((item) => trackedTimelineList.appendChild(buildTrackedTimelineRow(item)));
    });
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
  const fallbackRules = getTrackedDefaultRuleParams();
  const rules = topic?.rules || fallbackRules;
  detailTrackedTitleInput.value = topic?.title || "";
  detailTrackedStrongInput.value = trackedRuleList(rules.strong_phrases).join(", ");
  detailTrackedCoreInput.value = trackedRuleList(rules.core_terms).join(", ");
  detailTrackedContextInput.value = trackedRuleList(rules.context_terms).join(", ");
  detailTrackedExcludeInput.value = trackedRuleList(rules.exclude_terms).join(", ");
  detailTrackedRequiredInput.value = trackedRuleList(rules.required_terms).join(", ");
  detailTrackedThresholdInput.value = String(trackedRuleNumber(rules.threshold, fallbackRules.threshold));
  detailTrackedTitleWeightInput.value = String(trackedRuleNumber(rules.title_weight, fallbackRules.title_weight));
  detailTrackedNoteWeightInput.value = String(trackedRuleNumber(rules.note_weight, fallbackRules.note_weight));
  detailTrackedSummaryWeightInput.value = String(trackedRuleNumber(rules.summary_weight, fallbackRules.summary_weight));
  detailTrackedContentWeightInput.value = String(trackedRuleNumber(rules.content_weight, fallbackRules.content_weight));
  detailTrackedStrongScoreInput.value = String(trackedRuleNumber(rules.strong_score, fallbackRules.strong_score));
  detailTrackedCoreScoreInput.value = String(trackedRuleNumber(rules.core_score, fallbackRules.core_score));
  detailTrackedContextScoreInput.value = String(trackedRuleNumber(rules.context_score, fallbackRules.context_score));
  detailTrackedExcludePenaltyInput.value = String(trackedRuleNumber(rules.exclude_penalty, fallbackRules.exclude_penalty));
  detailTrackedScopeSelect.value = topic?.scope || "important";
  detailTrackedActiveInput.checked = Number(topic?.active ?? 1) === 1;
}

function fillTrackedDefaultsForm(params = getTrackedDefaultRuleParams()) {
  trackedDefaultsThresholdInput.value = String(trackedRuleNumber(params.threshold, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.threshold));
  trackedDefaultsTitleWeightInput.value = String(trackedRuleNumber(params.title_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.title_weight));
  trackedDefaultsNoteWeightInput.value = String(trackedRuleNumber(params.note_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.note_weight));
  trackedDefaultsSummaryWeightInput.value = String(trackedRuleNumber(params.summary_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.summary_weight));
  trackedDefaultsContentWeightInput.value = String(trackedRuleNumber(params.content_weight, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.content_weight));
  trackedDefaultsStrongScoreInput.value = String(trackedRuleNumber(params.strong_score, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.strong_score));
  trackedDefaultsCoreScoreInput.value = String(trackedRuleNumber(params.core_score, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.core_score));
  trackedDefaultsContextScoreInput.value = String(trackedRuleNumber(params.context_score, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.context_score));
  trackedDefaultsExcludePenaltyInput.value = String(trackedRuleNumber(params.exclude_penalty, TRACKED_SYSTEM_DEFAULT_RULE_PARAMS.exclude_penalty));
}

function resetTrackedEditorScroll(container) {
  const panel = container?.querySelector(".detail-tracked-form-panel");
  if (panel) panel.scrollTop = 0;
}

function trackedEditorPanel(container) {
  return container?.querySelector(".detail-tracked-form-panel") || null;
}

function trackedFeedbackHost(container) {
  return container?.querySelector(".tracked-form-actions") || trackedEditorPanel(container);
}

function openTrackedDefaultsPanel() {
  closeTagAdminView();
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeReminderEditor();
  closeDetailTrackEditor();
  detailEmpty.classList.add("hidden");
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  detailTrackedDefaultsBody.classList.remove("hidden");
  resetTrackedEditorScroll(detailTrackedDefaultsBody);
  clearInlineFeedback(trackedFeedbackHost(detailTrackedDefaultsBody));
  fillTrackedDefaultsForm(getTrackedDefaultRuleParams());
  updateWorkspaceLayout();
  openDetailOnMobile();
}

function openTrackedTopicForm(mode, topic = null) {
  state.trackedFormMode = mode;
  closeTagAdminView();
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeReminderEditor();
  closeDetailTrackEditor();
  detailEmpty.classList.add("hidden");
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedDefaultsBody) detailTrackedDefaultsBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  detailTrackedFormBody.classList.remove("hidden");
  resetTrackedEditorScroll(detailTrackedFormBody);
  clearInlineFeedback(trackedFeedbackHost(detailTrackedFormBody));
  detailTrackedFormTitle.textContent = mode === "edit" ? "编辑跟踪主题" : "新建跟踪主题";
  detailTrackedFormMeta.textContent = mode === "edit"
    ? "修改规则、增量范围和启用状态；字段说明和打分说明都放在当前编辑页内。"
    : "创建后即可在右栏查看时间线，并可从新闻详情手动加入；先按当前页说明填写规则，再逐步调分。";
  detailTrackedFormBackBtn.classList.toggle("hidden", mode !== "edit" || !topic);
  if (detailTrackedDraftBtn) {
    detailTrackedDraftBtn.classList.toggle("hidden", mode === "edit");
    detailTrackedDraftBtn.disabled = false;
    detailTrackedDraftBtn.textContent = "一键填写";
  }
  if (detailTrackedSaveDefaultsBtn) {
    detailTrackedSaveDefaultsBtn.classList.toggle("hidden", mode !== "edit");
  }
  if (detailTrackedFormSaveBtn) {
    detailTrackedFormSaveBtn.disabled = false;
    detailTrackedFormSaveBtn.textContent = "保存";
    detailTrackedFormSaveBtn.removeAttribute("aria-busy");
    delete detailTrackedFormSaveBtn.dataset.idleLabel;
  }
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
    required_terms: detailTrackedRequiredInput.value.trim(),
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

function trackedFormHasRuleContent() {
  return [
    detailTrackedStrongInput,
    detailTrackedCoreInput,
    detailTrackedContextInput,
    detailTrackedExcludeInput,
    detailTrackedRequiredInput,
  ].some((input) => (input?.value || "").trim());
}

function applyTrackedRuleDraft(draft) {
  if (!draft) return;
  detailTrackedStrongInput.value = Array.isArray(draft.strong_phrases) ? draft.strong_phrases.join(", ") : "";
  detailTrackedCoreInput.value = Array.isArray(draft.core_terms) ? draft.core_terms.join(", ") : "";
  detailTrackedContextInput.value = Array.isArray(draft.context_terms) ? draft.context_terms.join(", ") : "";
  detailTrackedExcludeInput.value = Array.isArray(draft.exclude_terms) ? draft.exclude_terms.join(", ") : "";
}

async function openTrackedTopicDetailById(topicId) {
  state.selectedTrackedTopicId = topicId;
  await loadTrackedTopicTimeline(topicId);
}

async function fetchSources() {
  const params = new URLSearchParams({
    q: "",
    collection: state.collection,
    read_filter: ["feed", "read_later"].includes(state.collection) ? state.readFilter : "all",
  });
  const res = await fetch(`/api/sources?${params.toString()}`);
  if (!res.ok) return [];
  const data = await res.json();
  if (!data.ok) return [];
  return Array.isArray(data.sources) ? data.sources : [];
}

function updateFeedHeader() {
  if (!feedKicker || !feedTitle) return;
  const headers = {
    search: ["全局检索", "搜索"],
    feed: ["今日阅读队列", "新闻流"],
    daily: ["日报集合", "日报"],
    favorites: ["长期收藏", "收藏"],
    reminders: ["待回访事项", "提醒"],
    important: ["重点追踪", "重要新闻"],
    read_later: ["个人队列", "稍后再看"],
    notes: ["个人判断", "想法"],
    tracked: ["主题时间线", "跟踪"],
    market_tags: ["板块工作台", "板块"],
    reviews: ["版本化判断复盘", "复盘"],
  };
  const [kicker, title] = headers[state.collection] || headers.feed;
  feedKicker.textContent = kicker;
  feedTitle.textContent = title;
}

function renderMeta() {
  updateFeedHeader();
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
    daily: "日报",
    favorites: "收藏",
    reminders: "提醒",
    important: "重要新闻",
    read_later: "稍后再看",
    notes: "想法",
    tracked: "跟踪",
    market_tags: "板块",
  };
  if (state.collection === "daily") {
    meta.textContent = `日报 · 共 ${state.total} 份 · ${state.dailyBriefings.length} 个月`;
    pageInfo.textContent = "- / -";
    return;
  }
  if (state.collection === "market_tags") {
    const selected = activeMarketTagChoices().find((tag) => tag.key === state.marketWorkbenchTag);
    const filterNames = {
      all: "全部",
      ideas: "仅想法",
      bullish: "看多",
      bearish: "看空",
    };
    meta.textContent = selected
      ? `板块工作台 · ${selected.display_name} · ${filterNames[state.marketWorkbenchFilter] || "全部"} · 共 ${state.total} 条`
      : `板块工作台 · 全部板块 · ${filterNames[state.marketWorkbenchFilter] || "全部"} · 共 ${state.total} 条`;
    pageInfo.textContent = `${state.page} / ${state.pages}`;
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
      trend: "板块想法",
      standalone: "独立想法",
    };
    meta.textContent = `想法 · ${ideaNames[state.ideaFilter] || "全部"} · 共 ${state.total} 条`;
    pageInfo.textContent = `${state.page} / ${state.pages}`;
    return;
  }
  if (state.collection === "reviews") {
    const reviewFilterNames = {
      all: "全部",
      in_progress: "进行中",
      pending_review: "待复盘",
      done: "已完成",
    };
    meta.textContent = `复盘 · ${reviewFilterNames[state.reviewFilter] || "全部"} · 共 ${state.total} 条`;
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
    read: "已读",
  };
  const readFilterName = ["feed", "read_later"].includes(state.collection)
    ? (readNames[state.readFilter] || readNames.all)
    : readNames.all;
  const sourceName = state.sourceFilter === "all" ? "全部来源" : sourceLabel(state.sourceFilter);
  meta.textContent = `${names[state.collection]} · ${readFilterName} · ${sourceName} · 共 ${state.total} 条`;
  pageInfo.textContent = `${state.page} / ${state.pages}`;
}

function activeMarketTagChoices() {
  return state.marketTagChoices.filter((tag) => Number(tag.active || 0) === 1);
}

function defaultTrendComposeDates() {
  const dates = [];
  const today = new Date();
  for (let offset = 0; offset < 7; offset += 1) {
    const next = new Date(today);
    next.setDate(today.getDate() - offset);
    dates.push(next.toISOString().slice(0, 10));
  }
  return dates;
}

function closeTrendComposerView() {
  state.trendComposeOpen = false;
  if (detailTrendComposerBody) {
    detailTrendComposerBody.classList.add("hidden");
  }
}

function restoreMarketWorkbenchDetailState() {
  if (detailTrendIdeaBody) detailTrendIdeaBody.classList.add("hidden");
  if (detailDailyBody) detailDailyBody.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailEmpty) {
    renderDetailEmpty();
  }
  updateWorkspaceLayout();
}

function setTrendIdeaEditorOpen(open) {
  if (!detailTrendIdeaEditor) return;
  detailTrendIdeaEditor.classList.toggle("hidden", !open);
  if (detailTrendIdeaCard) detailTrendIdeaCard.classList.toggle("hidden", open);
}

function clearTrendIdeaDetailState() {
  state.selectedTrendIdea = null;
  if (detailTrendIdeaBody) detailTrendIdeaBody.classList.add("hidden");
  setTrendIdeaEditorOpen(false);
  clearStandaloneIdeaDetailState();
}

function setStandaloneIdeaEditorOpen(open) {
  if (!detailStandaloneIdeaEditor) return;
  detailStandaloneIdeaEditor.classList.toggle("hidden", !open);
}

function clearStandaloneIdeaDetailState() {
  state.selectedStandaloneIdea = null;
  if (detailStandaloneIdeaBody) detailStandaloneIdeaBody.classList.add("hidden");
  setStandaloneIdeaEditorOpen(false);
  if (detailStandaloneIdeaNewBody) detailStandaloneIdeaNewBody.classList.add("hidden");
}

function emptyDetailMessage() {
  if (state.collection === "daily") return "选择一份日报查看详情";
  if (state.collection === "notes") return "选择一条想法查看详情";
  if (state.collection === "reviews") return "选择一条复盘查看详情";
  if (state.collection === "market_tags") return state.marketWorkbenchTag ? "选择一条板块内容查看详情" : "选择一条板块新闻查看详情";
  return "选择一条新闻查看摘要与正文";
}

function renderDetailEmpty(message = emptyDetailMessage()) {
  if (!detailEmpty) return;
  if (detailEmptyTitle) detailEmptyTitle.textContent = message;
  detailEmpty.classList.remove("hidden");
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

async function updateTrendNote(noteId, { note, date_key, tag_key, direction }) {
  const payload = { note };
  if (date_key) payload.date_key = date_key;
  if (tag_key) payload.tag_key = tag_key;
  if (direction) payload.direction = direction;
  const res = await fetch(`/api/market-trends/note/${encodeURIComponent(noteId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
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
  const dateOptions = defaultTrendComposeDates();
  const tagOptions = activeMarketTagChoices();
  trendNoteDateSelect.innerHTML = "";
  dateOptions.forEach((date) => {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = date;
    trendNoteDateSelect.appendChild(option);
  });
  trendNoteTagSelect.innerHTML = "";
  tagOptions.forEach((tag) => {
    const option = document.createElement("option");
    option.value = tag.key;
    option.textContent = tag.display_name;
    trendNoteTagSelect.appendChild(option);
  });
  trendNoteComposeSaveBtn.disabled = !dateOptions.length || !tagOptions.length;
}

function openTrendComposeView(prefill = null) {
  clearTrendIdeaDetailState();
  closeTagAdminView();
  detailBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  detailTrendComposerBody.classList.remove("hidden");
  clearInlineFeedback(trendNoteComposeSaveBtn?.closest(".detail-note-editor"));
  state.trendComposeOpen = true;
  renderTrendComposeOptions();
  if (trendNoteComposeSaveBtn) {
    trendNoteComposeSaveBtn.textContent = "保存";
    trendNoteComposeSaveBtn.removeAttribute("aria-busy");
    delete trendNoteComposeSaveBtn.dataset.idleLabel;
  }
  if (trendNoteDateSelect.options.length) {
    trendNoteDateSelect.value = trendNoteDateSelect.options[0].value;
  }
  if (trendNoteTagSelect.options.length) {
    trendNoteTagSelect.value = trendNoteTagSelect.options[0].value;
  }
  if (prefill) {
    trendNoteDateSelect.value = prefill.date;
    trendNoteTagSelect.value = prefill.tagKey;
  }
  trendNoteComposeInput.value = "";
  if (trendNoteComposeDeleteBtn) trendNoteComposeDeleteBtn.classList.add("hidden");
  updateWorkspaceLayout();
  openDetailOnMobile();
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
      `确认将“${selectedTag.display_name || selectedTag.key}”合并到“${target?.display_name || targetKey}”？该板块的新闻关联和板块想法会迁移到目标板块，旧板块将被删除。`
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
  renderTagAdminList();
}

async function refreshMarketWorkbenchAfterTrendCompose() {
  if (state.collection !== "market_tags") return;
  await fetchMarketTagDefinitions().catch(() => {});
  resetList();
  removeMarketWorkbenchSummaryInline();
  const data = await fetchMarketWorkbenchPage(1);
  state.total = Number(data.total || 0);
  state.pages = Number(data.pages || 1);
  state.page = Number(data.page || 1);
  state.hasMore = !!data.has_more;
  state.marketWorkbenchSummary = data.summary || null;
  showListView();
  renderMeta();
  (data.items || []).forEach((item) => {
    const row = item.entry_type === "trend_note" ? buildIdeaRow(item) : buildItemRow(item);
    appendNewsRow(item, row);
  });
  if (state.marketWorkbenchTag) {
    renderMarketWorkbenchSummaryInline();
  } else {
    removeMarketWorkbenchSummaryInline();
  }
  if (!state.total) {
    setHint("当前板块筛选下暂无内容");
  } else if (state.hasMore) {
    setHint("继续下滑加载更多");
  } else {
    setHint("已加载当前板块集合的全部结果");
  }
  ensureRowStatusPolling();
  if (readObserver) {
    readObserver.disconnect();
    readObserver = null;
  }
}

async function openTagAdminView() {
  state.tagAdminOpen = true;
  clearTrendIdeaDetailState();
  closeTrendComposerView();
  closeMarketPicker();
  detailBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  await refreshTrendTagAdminState();
  detailTagAdminBody.classList.remove("hidden");
  updateWorkspaceLayout();
  openDetailOnMobile();
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
  if ("read_later_done_at" in patchResult) item.read_later_done_at = patchResult.read_later_done_at;
  state.itemsById.set(item.id, item);
}

function rerenderOne(itemId) {
  const item = state.itemsById.get(itemId);
  const row = newsList.querySelector(`.news-item[data-id=\"${itemId}\"]`);
  if (item && row) syncRowUI(row, item);
  if (item && state.selectedId === itemId) renderDetail(item);
}

function statePatchActionLabel(payload) {
  if ("favorite" in payload) return payload.favorite ? "加入收藏" : "取消收藏";
  if ("important" in payload) return payload.important ? "标为重要" : "取消重要";
  if ("read_later" in payload) return payload.read_later ? "加入稍后再看" : "取消稍后再看";
  return "";
}

function clearDetailActionFeedback() {
  clearInlineFeedback(detailBody, "detail-action-feedback");
}

function showDetailActionFeedback(message, options = {}) {
  setInlineFeedback(detailBody, message, {
    tone: options.tone || "failed",
    actionLabel: options.actionLabel || "",
    onAction: options.onAction || null,
    className: "detail-action-feedback",
    before: detailBody?.querySelector(".detail-scroll-area") || null,
  });
}

function clearStatePatchFeedback(itemId) {
  const row = newsList.querySelector(`.news-item[data-id=\"${itemId}\"]`);
  clearInlineFeedback(row, "row-inline-feedback");
  if (state.selectedId === itemId) clearDetailActionFeedback();
}

function showStatePatchError(itemId, payload) {
  const actionLabel = statePatchActionLabel(payload);
  if (!actionLabel) return;
  const message = `${actionLabel}未保存，已恢复原状态。`;
  const retry = () => patchStateWithRollback(itemId, { ...payload });
  const row = newsList.querySelector(`.news-item[data-id=\"${itemId}\"]`);
  setInlineFeedback(row, message, {
    tone: "failed",
    actionLabel: "重试",
    onAction: retry,
    className: "row-inline-feedback",
  });
  if (state.selectedId === itemId && detailBody && !detailBody.classList.contains("hidden")) {
    showDetailActionFeedback(message, {
      actionLabel: "重试",
      onAction: retry,
    });
  }
}

async function patchStateWithRollback(itemId, payload) {
  if (writeInFlight.has(itemId)) return;
  writeInFlight.add(itemId);
  clearStatePatchFeedback(itemId);
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
    read_later_done_at: item.read_later_done_at,
    detail_status: item.detail_status,
    detail_ready: item.detail_ready,
    ai_status: item.ai_status,
    ai_ready: item.ai_ready,
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
    item.read_later_done_at = payload.read_later ? null : now;
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
    item.read_later_done_at = backup.read_later_done_at;
    item.detail_status = backup.detail_status;
    item.detail_ready = backup.detail_ready;
    item.ai_status = backup.ai_status;
    item.ai_ready = backup.ai_ready;
    rerenderOne(itemId);
    if ("read_later" in payload) {
      if (rowNeedsStatusPolling(item)) ensureRowStatusPolling();
      if (state.selectedId === itemId) startDetailPolling(itemId);
    }
    showStatePatchError(itemId, payload);
  } finally {
    writeInFlight.delete(itemId);
  }
}

function openDetailOnMobile() {
  if (window.matchMedia("(max-width: 1180px)").matches) {
    detailPanel.style.transition = "";
    detailPanel.style.transform = "";
    detailPanel.classList.add("open");
    scheduleDetailToolbarOverflowSync();
  }
}

let detailToolbarOverflowFrame = 0;

function syncDetailToolbarOverflow() {
  detailToolbarOverflowFrame = 0;
  if (!detailToolbarFrame || !detailToolbarScroll) return;
  const threshold = 2;
  const maxScrollLeft = Math.max(0, detailToolbarScroll.scrollWidth - detailToolbarScroll.clientWidth);
  const isOverflowing = detailToolbarScroll.clientWidth > 0 && maxScrollLeft > threshold;
  detailToolbarFrame.classList.toggle("is-overflowing", isOverflowing);
  detailToolbarFrame.classList.toggle(
    "is-at-start",
    !isOverflowing || detailToolbarScroll.scrollLeft <= threshold,
  );
  detailToolbarFrame.classList.toggle(
    "is-at-end",
    !isOverflowing || detailToolbarScroll.scrollLeft >= maxScrollLeft - threshold,
  );
}

function scheduleDetailToolbarOverflowSync() {
  if (!detailToolbarFrame || !detailToolbarScroll || detailToolbarOverflowFrame) return;
  if (typeof window.requestAnimationFrame !== "function") {
    syncDetailToolbarOverflow();
    return;
  }
  detailToolbarOverflowFrame = window.requestAnimationFrame(syncDetailToolbarOverflow);
}

function setupDetailToolbarOverflowCue() {
  if (!detailBody || !detailToolbarFrame || !detailToolbarScroll) return;
  detailToolbarScroll.addEventListener("scroll", scheduleDetailToolbarOverflowSync, { passive: true });
  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(scheduleDetailToolbarOverflowSync);
    resizeObserver.observe(detailToolbarFrame);
    resizeObserver.observe(detailToolbarScroll);
  }
  if ("MutationObserver" in window) {
    const mutationObserver = new MutationObserver(scheduleDetailToolbarOverflowSync);
    mutationObserver.observe(detailBody, {
      attributes: true,
      childList: true,
      subtree: true,
      attributeFilter: ["class"],
    });
  }
  scheduleDetailToolbarOverflowSync();
}

let feedControlsOverflowFrame = 0;

function syncFeedControlsOverflow() {
  feedControlsOverflowFrame = 0;
  if (!feedControlsFrame || !feedControlsScroll) return;
  const threshold = 2;
  const maxScrollLeft = Math.max(0, feedControlsScroll.scrollWidth - feedControlsScroll.clientWidth);
  const isOverflowing = feedControlsScroll.clientWidth > 0 && maxScrollLeft > threshold;
  feedControlsFrame.classList.toggle("is-overflowing", isOverflowing);
  feedControlsFrame.classList.toggle(
    "is-at-start",
    !isOverflowing || feedControlsScroll.scrollLeft <= threshold,
  );
  feedControlsFrame.classList.toggle(
    "is-at-end",
    !isOverflowing || feedControlsScroll.scrollLeft >= maxScrollLeft - threshold,
  );
}

function scheduleFeedControlsOverflowSync() {
  if (!feedControlsFrame || !feedControlsScroll || feedControlsOverflowFrame) return;
  if (typeof window.requestAnimationFrame !== "function") {
    syncFeedControlsOverflow();
    return;
  }
  feedControlsOverflowFrame = window.requestAnimationFrame(syncFeedControlsOverflow);
}

function setupFeedControlsOverflowCue() {
  if (!feedControlsFrame || !feedControlsScroll) return;
  feedControlsScroll.addEventListener("scroll", scheduleFeedControlsOverflowSync, { passive: true });
  if ("ResizeObserver" in window) {
    const resizeObserver = new ResizeObserver(scheduleFeedControlsOverflowSync);
    resizeObserver.observe(feedControlsFrame);
    resizeObserver.observe(feedControlsScroll);
  }
  if ("MutationObserver" in window) {
    const mutationObserver = new MutationObserver(scheduleFeedControlsOverflowSync);
    mutationObserver.observe(feedControlsScroll, {
      attributes: true,
      childList: true,
      subtree: true,
      attributeFilter: ["class"],
    });
  }
  scheduleFeedControlsOverflowSync();
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

function canReturnToTrackedTopic() {
  return !!state.detailReturnToTrackedTopicId;
}

function syncDetailReturnButton() {
  if (detailReturnToTrackedBtn) {
    detailReturnToTrackedBtn.classList.toggle("hidden", !canReturnToTrackedTopic());
  }
}

async function restoreTrackedTopicFromDetail() {
  if (!canReturnToTrackedTopic()) return;
  const topicId = state.detailReturnToTrackedTopicId;
  state.selectedId = null;
  state.detailReturnToTrackedTopicId = null;
  stopDetailPolling();
  await openTrackedTopicDetailById(topicId);
}

async function openItemDetail(item, { fromTrackedTopicId = null } = {}) {
  if (!item) return;
  clearFeedKeyboardDetailTimer();
  if (state.selectedId !== item.id) resetDetailChatState();
  state.itemsById.set(item.id, item);
  state.selectedId = item.id;
  state.detailReturnToTrackedTopicId = fromTrackedTopicId || null;
  syncFeedKeyboardRows();
  renderDetail(state.itemsById.get(item.id) || item);
  if (!item.snapshotOnly) {
    loadDetail(item.id);
    startDetailPolling(item.id);
    saveReadingCheckpoint(item).catch(() => {});
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
  state.detailChatProvider = keepProvider ? state.detailChatProvider : "";
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

function currentChatProvider() {
  return (state.runtimeSettings?.llm?.chat?.provider || "codex").trim();
}

function currentChatModel() {
  const provider = currentChatProvider();
  if (provider === "pi") {
    return (state.runtimeSettings?.llm?.pi_chat?.model || "").trim();
  }
  return currentCodexChatModel();
}

function chatModelLabel(meta) {
  const model = (meta?.model || currentChatModel()).trim();
  return model || "默认模型";
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

function renderDetailChatMeta(item, providerMeta) {
  if (!detailChatMeta) return;
  detailChatMeta.innerHTML = "";
  const contextMeta = detailChatContextMeta(item);
  const label = providerMeta?.label || (currentChatProvider() === "pi" ? "Pi" : "Codex");

  const source = document.createElement("span");
  source.className = "detail-chat-source";
  source.textContent = item.source || "未知来源";
  detailChatMeta.appendChild(source);

  const modelBadge = document.createElement("span");
  modelBadge.className = `detail-chat-model-badge ${providerMeta?.available ? "ok" : "failed"}`;
  modelBadge.textContent = `● ${label}${chatModelLabel(providerMeta) ? ` · ${chatModelLabel(providerMeta)}` : ""}`;
  detailChatMeta.appendChild(modelBadge);

  if (contextMeta?.context_label) {
    const contextBadge = document.createElement("span");
    contextBadge.className = "detail-chat-source";
    contextBadge.textContent = contextMeta.context_label;
    detailChatMeta.appendChild(contextBadge);
  }
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

function detailChatContextMeta(item) {
  const cached = item?.url ? state.detailCacheByUrl.get(item.url) : null;
  const context = cached?.chat_context || null;
  if (context?.context_label) return context;
  if (cached?.detail?.content) {
    return { context_level: "full_detail", context_label: "完整正文" };
  }
  return { context_level: "summary_context", context_label: "摘要与元数据" };
}

function renderDetailChat(item) {
  if (!item) return;
  const providers = chatProvidersFromItem(item);
  const activeKey = currentChatProvider();
  const providerMeta = providers[activeKey] || { available: true, model: currentChatModel(), label: activeKey === "pi" ? "Pi" : "Codex" };
  const chatEnabled = !!providerMeta.available;
  // 归档跟随当前 Chat provider：按钮可用性看当前 provider 是否可用 + 已有 assistant 消息 + 非发送/归档中。
  const archiveEnabled = chatEnabled
    && !state.detailChatSending
    && !state.detailChatArchiving
    && state.detailChatMessages.some((message) => message.role === "assistant");
  const contextMeta = detailChatContextMeta(item);
  const contextLabel = contextMeta?.context_label || "摘要与元数据";
  const contextHint = contextMeta?.context_level === "full_detail"
    ? "可基于完整正文继续追问；涉及背景或最新信息时，助手会主动搜索补充。"
    : "当前只有摘要与元数据；助手会把它当作提问场景，并在需要时主动搜索补充。";

  renderDetailChatMeta(item, providerMeta);
  renderDetailChatKeyPoints(item);
  detailChatInput.disabled = state.detailChatSending || state.detailChatArchiving || !chatEnabled;
  detailChatSendBtn.disabled = state.detailChatSending || state.detailChatArchiving || !chatEnabled;
  if (detailChatArchiveBtn) {
    detailChatArchiveBtn.disabled = !archiveEnabled;
  }
  const unavailableLabel = `${providerMeta.label || (activeKey === "pi" ? "Pi" : "Codex")} chat 当前不可用。`;
  detailChatInput.placeholder = chatEnabled
    ? (contextMeta?.context_level === "full_detail"
      ? "围绕这条新闻提问，例如：这件事现在的最新进展是什么？"
      : "结合这条新闻背景提问，例如：这件事现在有哪些最新进展？")
    : unavailableLabel;

  const chatReady = !!(state.detailChatMessages && state.detailChatMessages.length);
  const statusText = state.detailChatStatus || (chatReady ? "" : (chatEnabled ? "" : unavailableLabel));
  detailChatStatus.textContent = statusText;
  detailChatStatus.className = `detail-status ${state.detailChatSending ? "pending" : statusText ? "muted" : "hidden"}`;

  detailChatMessages.innerHTML = "";
  if (!chatReady) {
    const empty = document.createElement("div");
    empty.className = "detail-chat-empty";
    empty.textContent = chatEnabled
      ? `${contextHint}当前上下文：${contextLabel}。`
      : unavailableLabel;
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
  const configuredProvider = currentChatProvider();
  const configuredModel = currentChatModel();
  const reset = !!state.detailChatSessionId
    && (!!state.detailChatProvider && state.detailChatProvider !== configuredProvider
      || !!state.detailChatModel && state.detailChatModel !== configuredModel);
  if (reset) {
    state.detailChatMessages = [];
    state.detailChatSessionId = "";
    state.detailChatProvider = "";
    state.detailChatModel = "";
    state.detailChatStatus = `${configuredProvider === "pi" ? "Pi" : "Codex"} chat 配置已切换，已为你重新开始一轮对话。`;
  }

  state.detailChatMessages = [...state.detailChatMessages, { role: "user", content }];
  state.detailChatSending = true;
  state.detailChatStatus = "正在生成回答，可能会搜索资料...";
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
    state.detailChatProvider = payload.provider || configuredProvider;
    state.detailChatModel = configuredModel;
    const providerLabel = payload.provider === "pi" ? "Pi" : "Codex";
    state.detailChatStatus = `${providerLabel} · ${payload.model || "默认模型"} · ${payload.context_label || "摘要与元数据"}`.trim();
  } catch (error) {
    const code = error instanceof Error ? error.message : "chat_request_failed";
    const labelMap = {
      detail_not_ready: "正文还没准备好，暂时不能提问。",
      context_unavailable: "这条新闻缺少可提问的上下文，请稍后重试。",
      provider_busy: "该模型当前正忙，请稍后重试。",
      provider_timeout: "请求超时，请稍后重试。",
      provider_failed: "调用失败，请稍后重试。",
      session_invalid: "上轮对话 session 已失效，请重新开始。",
      missing_session_id: "没有返回可继续对话的 session id，请重试。",
      empty_answer: "没有返回有效回答，请重试。",
    };
    if (code === "session_invalid") {
      state.detailChatSessionId = "";
      state.detailChatProvider = "";
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

  const configuredModel = currentChatModel();
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
    const archiveLabel = currentChatProvider() === "pi" ? "Pi" : "Codex";
    const labelMap = {
      empty_archive_source: "没有可归档回答。",
      empty_archive_summary: "没有生成可归档结论。",
      invalid_archive_summary: "归档结果无效，请重试。",
      note_too_long: "想法过长，无法追加归档。",
      provider_busy: `${archiveLabel} 当前正忙，请稍后重试。`,
      provider_timeout: `${archiveLabel} 归档超时，请稍后重试。`,
      provider_failed: `${archiveLabel} 归档失败，请稍后重试。`,
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
  if (detailReviewAddBtn) {
    detailReviewAddBtn.classList.toggle("hidden", !hasNote);
    applyIcon(detailReviewAddBtn, "target", { label: "加入复盘" });
  }
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
      clearDetailActionFeedback();
      removeBtn.disabled = true;
      try {
        await deleteMarketTag(item, mt.key || mt.tag);
        refreshDetailMarketTagsUI(item);
      } catch (error) {
        showDetailActionFeedback(
          `删除板块标记失败：${friendlyActionError(error, "原标记仍然保留，请稍后重试。")}`,
        );
      } finally {
        removeBtn.disabled = false;
      }
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
  clearInlineFeedback(detailMarketPicker);
  detailMarketPickerOptions.innerHTML = "";
  detailMarketPickerTitle.textContent = direction === "bullish" ? "选择看多板块" : "选择看空板块";
  activeMarketTagChoices().forEach((tagDef) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "detail-market-option";
    btn.textContent = tagDef.display_name;
    btn.addEventListener("click", async () => {
      clearInlineFeedback(detailMarketPicker);
      btn.disabled = true;
      setInlineFeedback(detailMarketPicker, "正在保存板块方向…", { tone: "pending" });
      try {
        await upsertMarketTag(item, tagDef.key, direction);
        closeMarketPicker();
        refreshDetailMarketTagsUI(item);
      } catch (error) {
        setInlineFeedback(
          detailMarketPicker,
          `保存板块方向失败：${friendlyActionError(error, "请保留当前选择并稍后重试。")}`,
          { tone: "failed" },
        );
      } finally {
        btn.disabled = false;
      }
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
  clearInlineFeedback(detailReminderEditor);
  detailReminderEditor.classList.remove("hidden");
}

function detailReminderCardKey(item) {
  return String(item?.id || item?.url || "");
}

function ensureDetailReminderToggle() {
  if (!detailReminderCard) return null;
  const heading = detailReminderCard.querySelector("h4");
  if (!heading) return null;
  heading.classList.add("detail-reminder-heading");
  let toggle = heading.querySelector(".detail-reminder-toggle");
  if (!toggle) {
    heading.textContent = "";
    toggle = document.createElement("button");
    toggle.className = "detail-reminder-toggle";
    toggle.type = "button";
    heading.appendChild(toggle);
  }
  return toggle;
}

function setDetailReminderCardExpanded(expanded) {
  if (!detailReminderCard) return;
  detailReminderCard.dataset.expanded = expanded ? "1" : "0";
  detailReminderCard.classList.toggle("is-expanded", expanded);
  const toggle = detailReminderCard.querySelector(".detail-reminder-toggle");
  if (toggle) {
    toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
  }
}

function refreshDetailReminderUI(item) {
  if (!detailReminderCard || !detailReminderList || !detailReminderSummary) return;
  const reminders = normalizeReminderItems(currentDetailReminders(item));
  const summary = currentDetailReminderSummary(item);
  const summaryText = `进行中 ${summary.active_total || 0} · 到期 ${summary.due_total || 0} · 已完成 ${summary.done_total || 0}`;
  const cardKey = detailReminderCardKey(item);
  const isSameCard = detailReminderCard.dataset.itemKey === cardKey;
  if (!isSameCard) {
    detailReminderCard.dataset.expanded = "0";
  }
  detailReminderCard.dataset.itemKey = cardKey;
  const toggle = ensureDetailReminderToggle();
  if (toggle) {
    toggle.innerHTML = `<span>新闻事件提醒</span><span class="detail-reminder-toggle-meta">${summaryText}</span>`;
    toggle.onclick = () => {
      setDetailReminderCardExpanded(detailReminderCard.dataset.expanded !== "1");
    };
  }
  detailReminderSummary.textContent = summaryText;
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
    const runReminderAction = async (button, pendingMessage, failureLabel, task) => {
      clearInlineFeedback(card);
      setButtonBusy(button, true, "处理中…");
      setInlineFeedback(card, pendingMessage, { tone: "pending" });
      try {
        await task();
      } catch (error) {
        setInlineFeedback(
          card,
          `${failureLabel}：${friendlyActionError(error, "提醒未改变，请稍后重试。")}`,
          { tone: "failed" },
        );
      } finally {
        setButtonBusy(button, false);
      }
    };

    if (reminder.status !== "done") {
      const doneBtn = document.createElement("button");
      doneBtn.className = "detail-retry-btn";
      doneBtn.type = "button";
      doneBtn.textContent = "标记完成";
      doneBtn.addEventListener("click", async (event) => {
        event.stopPropagation();
        const current = state.itemsById.get(state.selectedId);
        if (!current) return;
        await runReminderAction(
          doneBtn,
          "正在标记提醒为已完成…",
          "标记提醒失败",
          () => saveReminderDraft(current, reminder.id, { status: "done" }),
        );
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
        await runReminderAction(
          reopenBtn,
          "正在重新激活提醒…",
          "重新激活提醒失败",
          () => saveReminderDraft(current, reminder.id, { status: "active" }),
        );
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
      await runReminderAction(
        deleteBtn,
        "正在删除提醒…",
        "删除提醒失败",
        () => removeReminderDraft(current, reminder.id),
      );
    });
    actions.appendChild(deleteBtn);

    card.appendChild(actions);
    card.addEventListener("click", () => {
      state.selectedReminderId = reminder.id;
      refreshDetailReminderUI(item);
    });
    detailReminderList.appendChild(card);
  });
  setDetailReminderCardExpanded(isSameCard && detailReminderCard.dataset.expanded === "1");
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
  clearInlineFeedback(detailTrackEditor);
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
    state.detailReturnToTrackedTopicId = null;
    stopDetailPolling();
    closeMarketPicker();
    closeReminderEditor();
    closeDetailTrackEditor();
    if (detailReminderCard) detailReminderCard.classList.add("hidden");
    syncDetailReturnButton();
    if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
    if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
    if (detailDailyBody) detailDailyBody.classList.add("hidden");
    detailBody.classList.add("hidden");
    detailChatBody.classList.add("hidden");
    closeAllReviewPanels();
    renderDetailEmpty();
    updateWorkspaceLayout();
    return;
  }
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailDailyBody) detailDailyBody.classList.add("hidden");
  closeAllReviewPanels();
  detailEmpty.classList.add("hidden");
  detailBody.classList.remove("hidden");
  syncDetailReturnButton();

  document.getElementById("detailTitle").textContent = rowTitleText(item);
  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  const detail = cached?.detail || null;
  document.getElementById("detailMeta").textContent = `${item.source || "未知来源"} · ${item.published_at || ""}`;
  const summaryEl = document.getElementById("detailSummary");
  const hasDetailContent = !!(detail && detail.content);
  const hasSummary = !hasDetailContent && typeof item.summary === "string" && item.summary.trim().length > 0;
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

  const status = cached?.detail_status || item.detail_status || "none";
  const detailErr = cached?.job?.last_error || item.detail_error || "";
  const ai = cached?.ai || null;
  const aiStatus = cached?.ai_status || item.ai_status || "none";
  const isTwitterDetail = item.source_type === "twitter" || detail?.source === "Twitter/X";
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
  if (detailRefreshTweetBtn) {
    detailRefreshTweetBtn.classList.add("hidden");
    detailRefreshTweetBtn.disabled = false;
  }
  if (detailMediaGallery) {
    detailMediaGallery.innerHTML = "";
    detailMediaGallery.classList.add("hidden");
  }
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
    if (isTwitterDetail) retranslateBtn.textContent = "翻译正文";

    if (aiStatus === "pending" || aiStatus === "running" || aiStatus === "none") {
      if (isTwitterDetail && aiStatus === "none") {
        statusEl.textContent = `详情已完成 · 正文长度 ${detail.content_length || detail.content.length}`;
        statusEl.className = "detail-status ready";
        contentEl.textContent = original;
        contentEl.classList.remove("hidden");
        stopDetailPolling();
      } else {
        statusEl.textContent = aiStatus === "pending" ? "排队生成中文内容" : "正在生成中文内容";
        statusEl.className = "detail-status pending";
        contentEl.textContent = ai && ai.body_zh ? ai.body_zh : original;
        contentEl.classList.remove("hidden");
        retranslateBtn.textContent = isTwitterDetail ? "正在翻译正文..." : "正在重新翻译...";
        retranslateBtn.disabled = true;
      }
    } else if (ai && ai.body_zh) {
      let keyPoints = [];
      try {
        keyPoints = JSON.parse(ai.key_points_zh || "[]");
      } catch {
        keyPoints = [];
      }
      if (!isTwitterDetail && Array.isArray(keyPoints) && keyPoints.length) {
        keyPoints.forEach((point) => {
          const li = document.createElement("li");
          li.textContent = point;
          detailAiPoints.appendChild(li);
        });
      }
      if (!isTwitterDetail && ((Array.isArray(keyPoints) && keyPoints.length) || (ai.conclusion_zh || "").trim())) {
        detailAiConclusion.textContent = ai.conclusion_zh || "";
        detailAiBox.classList.remove("hidden");
      }

      statusEl.textContent = isTwitterDetail
        ? (isCodexFallback ? "已由 GPT 完成正文翻译" : "中文正文翻译已生成")
        : isCodexFallbackBodyOnly
          ? "已由 GPT 完成翻译；结构化 fallback 失败，仅保留正文翻译"
          : isCodexFallback
            ? "已由 GPT 完成翻译"
            : "中文摘要与翻译已生成";
      statusEl.className = isTwitterDetail ? "detail-status ready" : (isCodexFallbackBodyOnly ? "detail-status pending" : "detail-status ready");
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

    if (isTwitterDetail && detailMediaGallery) {
      const images = Array.isArray(detail.media_images) ? detail.media_images : [];
      const missingCache = renderDetailMediaGallery(images);
      if (missingCache) {
        statusEl.textContent += " · 部分图片未缓存，可重新抓取推文";
      }
      if (detailRefreshTweetBtn) {
        detailRefreshTweetBtn.classList.remove("hidden");
        detailRefreshTweetBtn.disabled = status === "pending" || status === "running";
      }
      if (status === "pending" || status === "running") {
        statusEl.textContent = "正在重新抓取推文详情";
        statusEl.className = "detail-status pending";
      }
    }
  } else if (!item.read_later_at) {
    statusEl.textContent = Number(item.detail_ready || 0) === 1 ? "已完成稍后阅读" : "未加入稍后再看";
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
      statusEl.textContent = "这是旧版推文详情任务，当前可重试抓取正文";
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

  const chatReady = !item.snapshotOnly && !!item.id && !!item.url;
  askBtn.classList.toggle("hidden", !chatReady);
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

function renderDetailMediaGallery(images) {
  if (!detailMediaGallery) return;
  detailMediaGallery.innerHTML = "";
  let missingCache = false;
  for (const image of images) {
    const url = image && (image.cached_url || image.url);
    if (!url) {
      if (image && image.url) missingCache = true;
      continue;
    }
    if (!image.cached_url) {
      missingCache = true;
      continue;
    }
    const a = document.createElement("a");
    a.href = image.cached_url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    const img = document.createElement("img");
    img.src = image.cached_url;
    img.alt = "推文图片";
    img.loading = "lazy";
    img.onerror = () => {
      a.remove();
      if (detailMediaGallery.childElementCount === 0) {
        detailMediaGallery.classList.add("hidden");
      }
    };
    a.appendChild(img);
    detailMediaGallery.appendChild(a);
  }
  detailMediaGallery.classList.toggle("hidden", detailMediaGallery.childElementCount === 0);
  return missingCache;
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
  item.read_later_done_at = payload.read_later_done_at;
  item.active_reminder_count = Number(payload.reminder_summary?.active_total || 0);
  item.due_reminder_count = Number(payload.reminder_summary?.due_total || 0);
  item.detail_ready = payload.detail ? 1 : 0;
  item.has_note = Number(payload.has_note || 0);
  item.market_tags = normalizeMarketTags(payload.market_tags || []);
  item.has_market_tags = Number(payload.has_market_tags || 0);
  item.ai_status = payload.ai_status || "none";
  item.ai_ready = payload.ai ? 1 : 0;
  item.ingest_mode = payload.ingest_mode || "";
  item.ingest_warning = payload.ingest_warning || "";
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
  const detailStatus = current.detail_status || "none";
  const aiStatus = current.ai_status || "none";
  const isRefetching = detailStatus === "pending" || detailStatus === "running";
  const shouldPollDetail = (!!current.read_later_at && !detailReady) || (detailReady && isRefetching);
  const shouldPollAi = detailReady && !isRefetching && (aiStatus === "pending" || aiStatus === "running" || aiStatus === "none");
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
    const detailPolling = status === "pending" || status === "running";
    const aiPolling = aiStatus === "pending" || aiStatus === "running" || aiStatus === "none";
    if (!detailPolling && !aiPolling) {
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
  li.className = "news-item feed-news-item";
  li.dataset.id = item.id;

  const header = document.createElement("div");
  header.className = "news-row-header";

  const line1 = document.createElement("div");
  line1.className = "line1";

  const unreadDot = document.createElement("span");
  unreadDot.className = "unread-dot";

  const icon = createSourceIcon(item);

  const text = document.createElement("span");
  text.className = "line1-text";
  const source = document.createElement("span");
  source.className = "line1-source";
  source.textContent = item.source || "未知来源";
  text.appendChild(source);
  if (item.published_at) {
    const separator = document.createElement("span");
    separator.className = "line1-separator";
    separator.textContent = "·";
    separator.setAttribute("aria-hidden", "true");
    const publishedAt = document.createElement("span");
    publishedAt.className = "line1-time";
    publishedAt.textContent = item.published_at;
    text.appendChild(separator);
    text.appendChild(publishedAt);
  }

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
  title.textContent = rowTitleText(item);

  const summary = document.createElement("p");
  summary.className = "summary";
  summary.textContent = item.summary || "";

  const notePreview = document.createElement("p");
  notePreview.className = "row-note-preview hidden";

  const noteState = document.createElement("div");
  noteState.className = "row-note-state hidden";
  const noteBadge = document.createElement("span");
  noteBadge.className = "note-badge row-note-badge hidden";
  noteBadge.textContent = "想法";
  noteState.appendChild(noteBadge);
  noteState.appendChild(notePreview);

  const contextStrip = document.createElement("div");
  contextStrip.className = "row-context-strip hidden";
  const reminderBadge = document.createElement("span");
  reminderBadge.className = "note-badge reminder-badge hidden";
  contextStrip.appendChild(reminderBadge);

  const marketTagsWrap = document.createElement("div");
  marketTagsWrap.className = "market-tags hidden";
  contextStrip.appendChild(marketTagsWrap);

  const context = document.createElement("div");
  context.className = "news-row-context hidden";
  context.appendChild(noteState);
  context.appendChild(contextStrip);

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
  if (!isBloombergVideoUrl(item.url)) {
    actions.appendChild(btnReadLater);
  }
  actions.appendChild(btnFavorite);
  header.appendChild(line1);
  header.appendChild(actions);

  li.appendChild(header);
  li.appendChild(title);
  if (item.summary) li.appendChild(summary);
  li.appendChild(context);

  li.addEventListener("click", () => {
    if (state.selectedId === item.id) {
      if (!feedKeyboardMode && enterFeedKeyboardMode()) {
        syncFeedKeyboardRows({ focusSelected: true });
        return;
      }
      state.selectedId = null;
      clearFeedKeyboardDetailTimer();
      exitFeedKeyboardMode();
      stopDetailPolling();
      closeDetailOnMobile();
      renderDetail(null);
    } else {
      const keyboardEntered = enterFeedKeyboardMode();
      openItemDetail(item);
      syncFeedKeyboardRows({ focusSelected: keyboardEntered });
    }
    syncFeedKeyboardRows();
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
  if (item.idea_type === "standalone_note") {
    state.selectedId = null;
    state.selectedTrendIdea = null;
    renderStandaloneIdeaDetail(item);
    openDetailOnMobile();
    return;
  }
  state.selectedTrendIdea = null;
  openItemDetail(item);
}

function buildIdeaRow(item) {
  const li = document.createElement("li");
  li.className = "news-item idea-item";
  li.dataset.ideaId = item.idea_id || "";

  const line1 = document.createElement("div");
  line1.className = "line1";

  const kindBadge = document.createElement("span");
  const badgeClass = item.idea_type === "trend_note" ? "trend" : item.idea_type === "standalone_note" ? "standalone" : "article";
  kindBadge.className = `note-badge idea-kind-badge ${badgeClass}`;
  kindBadge.textContent = item.idea_type === "trend_note" ? "板块想法" : item.idea_type === "standalone_note" ? "独立想法" : "新闻想法";

  const text = document.createElement("span");
  text.className = "line1-text";
  if (item.idea_type === "trend_note") {
    text.textContent = `${item.updated_at || ""} · ${item.trend_date_key || ""}`;
  } else if (item.idea_type === "standalone_note") {
    text.textContent = item.updated_at || "";
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
  } else if (item.idea_type === "standalone_note") {
    summary.textContent = "";
  } else {
    summary.textContent = `${item.source || "未知来源"} · ${item.published_at || ""}`;
  }

  const notePreview = document.createElement("p");
  notePreview.className = "row-note-preview";
  notePreview.textContent = item.note || item.note_preview || "";
  if (item.idea_type === "trend_note" || item.idea_type === "standalone_note") {
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

function buildMarketOverviewRow(item) {
  const li = document.createElement("li");
  li.className = "news-item market-overview-item";
  li.dataset.tagKey = item.tag_key || "";

  const line1 = document.createElement("div");
  line1.className = "line1";
  const badge = document.createElement("span");
  badge.className = "note-badge idea-kind-badge trend";
  badge.textContent = "板块";
  const text = document.createElement("span");
  text.className = "line1-text";
  text.textContent = `近30天新闻 ${item.recent_total || 0} · 看多 ${item.bullish_total || 0} · 看空 ${item.bearish_total || 0}`;
  line1.appendChild(badge);
  line1.appendChild(text);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = item.tag_label || item.tag_key || "";

  const summary = document.createElement("p");
  summary.className = "summary";
  const latestTime = item.latest_published_at || item.latest_note_updated_at || "暂无更新";
  summary.textContent = `总新闻 ${item.total_items || 0} · 独立想法 ${item.trend_note_total || 0} · 最近更新 ${latestTime}`;

  li.appendChild(line1);
  li.appendChild(title);
  li.appendChild(summary);
  li.addEventListener("click", async () => {
    state.marketWorkbenchTag = item.tag_key || "";
    state.marketWorkbenchSummary = null;
    await loadFirstPage();
  });
  return li;
}


function reviewStatusLabel(status) {
  if (status === "done") return "已完成";
  if (status === "pending_review") return "待复盘";
  return "进行中";
}

function reviewResultLabel(result) {
  if (result === "confirmed") return "成立";
  if (result === "refuted") return "未成立";
  if (result === "inconclusive") return "暂不可判断";
  return "";
}

function reviewSourceTypeLabel(sourceType) {
  if (sourceType === "article_note") return "新闻想法";
  if (sourceType === "market_trend_note") return "板块想法";
  if (sourceType === "standalone_idea") return "独立想法";
  return sourceType;
}

function buildReviewRow(item) {
  const li = document.createElement("li");
  li.className = "news-item review-item";
  li.dataset.reviewId = String(item.id);
  if (String(state.selectedReviewId) === String(item.id)) li.classList.add("selected");

  const line1 = document.createElement("div");
  line1.className = "line1";
  const statusBadge = document.createElement("span");
  const effStatus = item.effective_status || "in_progress";
  statusBadge.className = `note-badge review-status-badge ${effStatus}`;
  statusBadge.textContent = reviewStatusLabel(effStatus);
  line1.appendChild(statusBadge);

  const versionBadge = document.createElement("span");
  versionBadge.className = "note-badge review-version-badge";
  versionBadge.textContent = `V${item.current_version || 1}`;
  line1.appendChild(versionBadge);

  const resultBadge = document.createElement("span");
  if (item.result && item.status === "done") {
    resultBadge.className = `note-badge review-result-badge ${item.result}`;
    resultBadge.textContent = reviewResultLabel(item.result);
    line1.appendChild(resultBadge);
  }

  const text = document.createElement("span");
  text.className = "line1-text";
  const parts = [];
  if (item.plan_review_date) parts.push(`计划 ${item.plan_review_date}`);
  if (item.latest_event_at) parts.push(`最近 ${item.latest_event_at.slice(0, 10)}`);
  text.textContent = parts.join(" · ");
  line1.appendChild(text);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = item.current_judgment || "(无判断)";

  const summary = document.createElement("p");
  summary.className = "summary";
  const summaryParts = [];
  summaryParts.push(reviewSourceTypeLabel(item.source_type));
  if (item.source_tag_label) summaryParts.push(item.source_tag_label);
  summary.textContent = summaryParts.join(" · ");

  const notePreview = document.createElement("p");
  notePreview.className = "row-note-preview";
  notePreview.textContent = item.source_note || "";
  notePreview.classList.add("full-text");

  li.appendChild(line1);
  li.appendChild(title);
  li.appendChild(summary);
  li.appendChild(notePreview);

  li.addEventListener("click", async () => {
    await openReviewCard(item);
  });
  return li;
}

function syncReviewRowSelection() {
  newsList.querySelectorAll(".review-item").forEach((row) => {
    row.classList.toggle("selected", row.dataset.reviewId === String(state.selectedReviewId));
  });
}
function removeMarketWorkbenchSummaryInline() {
  if (!newsList) return;
  newsList.querySelectorAll(".market-summary-row").forEach((node) => node.remove());
}

function renderMarketWorkbenchSummaryInline() {
  removeMarketWorkbenchSummaryInline();
  if (!newsList || state.collection !== "market_tags" || !state.marketWorkbenchTag || !state.marketWorkbenchSummary) return;
  const summary = state.marketWorkbenchSummary;
  const statusMap = {
    missing: "尚未生成，点击“总结近期趋势”手动生成。",
    stale: "本地新闻或想法有更新，当前总结已过期，可重新生成。",
    failed: `上次生成失败：${summary?.error || "未知错误"}`,
    success: `已生成 · 新闻 ${summary?.news_count || 0} 条 · 独立想法 ${summary?.trend_note_count || 0} 条`,
  };

  const li = document.createElement("li");
  li.className = "market-summary-row";
  const card = document.createElement("section");
  card.className = "detail-note-card";

  const title = document.createElement("h4");
  title.textContent = "近期趋势总结";
  const details = document.createElement("details");
  details.className = "market-summary-details";
  const detailsSummary = document.createElement("summary");
  detailsSummary.className = "market-summary-toggle";
  const summaryMeta = document.createElement("div");
  summaryMeta.className = "market-summary-toggle-text";
  const scope = document.createElement("div");
  scope.className = "detail-meta";
  scope.textContent = summary?.scope_label || "";
  const status = document.createElement("div");
  status.className = "detail-meta";
  status.textContent = statusMap[summary?.status] || "";
  summaryMeta.appendChild(title);
  summaryMeta.appendChild(scope);
  summaryMeta.appendChild(status);
  detailsSummary.appendChild(summaryMeta);
  const caret = document.createElement("span");
  caret.className = "market-summary-caret";
  caret.textContent = "展开";
  detailsSummary.appendChild(caret);
  details.appendChild(detailsSummary);

  const text = document.createElement("p");
  text.className = "detail-note-text";
  text.textContent = summary?.summary_text || "当前还没有正文总结。";
  details.appendChild(text);
  card.appendChild(details);
  li.appendChild(card);
  newsList.prepend(li);
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

async function reloadIdeasAndSelect(targetIdeaId) {
  if (!newsList) return;

  if (state.collection === "notes") {
    const data = await fetchIdeasPage(1);
    resetList();
    state.total = data.total;
    setDateCounts(data.date_counts);
    state.pages = data.pages;
    state.page = 1;
    state.hasMore = state.page < state.pages;
    showListView();
    data.items.forEach((item) => appendNewsRow(item, buildIdeaRow(item)));
    renderMeta();
    if (state.total === 0) {
      setHint("还没有想法，去新闻详情或板块里记录第一条。");
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
    const matched = (data.items || []).find((item) => item.idea_id === targetIdeaId);
    if (matched) {
      openIdeaCard(matched);
    } else {
      state.selectedIdeaId = "";
      syncIdeaRowSelection();
      clearTrendIdeaDetailState();
      renderDetailEmpty();
    }
    return;
  }

  if (state.collection === "market_tags") {
    removeMarketWorkbenchSummaryInline();
    const data = await fetchMarketWorkbenchPage(1);
    resetList();
    state.total = Number(data.total || 0);
    state.pages = Number(data.pages || 1);
    state.page = Number(data.page || 1);
    state.hasMore = !!data.has_more;
    state.marketWorkbenchSummary = data.summary || null;
    state.marketWorkbenchPin = data.pin || null;
    state.marketWorkbenchPinEditing = false;
    showListView();
    renderMeta();
    renderMarketWorkbenchPinCard();
    (data.items || []).forEach((item) => {
      const row = item.entry_type === "trend_note" ? buildIdeaRow(item) : buildItemRow(item);
      appendNewsRow(item, row);
    });
    if (state.marketWorkbenchTag) {
      renderMarketWorkbenchSummaryInline();
    } else {
      removeMarketWorkbenchSummaryInline();
    }
    if (!state.total) {
      setHint("当前板块筛选下暂无内容");
    } else if (state.hasMore) {
      setHint("继续下滑加载更多");
    } else {
      setHint("已加载当前板块集合的全部结果");
    }
    if (readObserver) {
      readObserver.disconnect();
      readObserver = null;
    }
    const matched = (data.items || []).find((item) => item.idea_id === targetIdeaId);
    if (matched) {
      openIdeaCard(matched);
    } else {
      state.selectedIdeaId = "";
      syncIdeaRowSelection();
      clearTrendIdeaDetailState();
      renderDetailEmpty();
    }
    return;
  }
}

function updateIdeaRow(item) {
  if (!newsList || !item?.idea_id) return;
  const row = newsList.querySelector(`.idea-item[data-idea-id="${CSS.escape(item.idea_id)}"]`);
  if (!row) return;
  const summary = row.querySelector(".summary");
  const notePreview = row.querySelector(".row-note-preview");
  if (item.idea_type === "standalone_note") {
    if (summary) summary.textContent = "";
    if (notePreview) notePreview.textContent = item.note || item.note_preview || "";
    const lineText = row.querySelector(".line1-text");
    if (lineText) lineText.textContent = item.updated_at || "";
    return;
  }
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
  resetDetailChatState({ keepProvider: true });
  stopDetailPolling();
  closeMarketPicker();
  closeReminderEditor();
  if (detailReminderCard) detailReminderCard.classList.add("hidden");
  syncDetailReturnButton();
  detailBody.classList.add("hidden");
  if (detailDailyBody) detailDailyBody.classList.add("hidden");
  detailChatBody.classList.add("hidden");
  closeAllReviewPanels();
  if (!item) {
    clearTrendIdeaDetailState();
    renderDetailEmpty();
    updateWorkspaceLayout();
    return;
  }

  state.selectedTrendIdea = { ...item };
  detailEmpty.classList.add("hidden");
  if (detailStandaloneIdeaBody) detailStandaloneIdeaBody.classList.add("hidden");
  if (detailStandaloneIdeaNewBody) detailStandaloneIdeaNewBody.classList.add("hidden");
  detailTrendIdeaBody.classList.remove("hidden");
  setTrendIdeaEditorOpen(false);
  detailTrendIdeaTitle.textContent = `${item.tag_label || ""} · ${ideaDirectionLabel(item)}`;
  detailTrendIdeaMeta.textContent = `${item.trend_date_key || ""} · 创建 ${item.created_at || "-"} · 更新 ${item.updated_at || "-"}`;
  detailTrendIdeaText.textContent = item.note || "";
  updateWorkspaceLayout();
}

function renderStandaloneIdeaDetail(item) {
  closeTagAdminView();
  closeTrendComposerView();
  resetDetailChatState({ keepProvider: true });
  stopDetailPolling();
  closeMarketPicker();
  closeReminderEditor();
  if (detailReminderCard) detailReminderCard.classList.add("hidden");
  syncDetailReturnButton();
  detailBody.classList.add("hidden");
  if (detailDailyBody) detailDailyBody.classList.add("hidden");
  detailChatBody.classList.add("hidden");
  closeAllReviewPanels();
  if (detailTrendIdeaBody) detailTrendIdeaBody.classList.add("hidden");
  if (!item) {
    clearStandaloneIdeaDetailState();
    renderDetailEmpty();
    updateWorkspaceLayout();
    return;
  }
  state.selectedStandaloneIdea = { ...item };
  detailEmpty.classList.add("hidden");
  if (detailStandaloneIdeaNewBody) detailStandaloneIdeaNewBody.classList.add("hidden");
  detailStandaloneIdeaBody.classList.remove("hidden");
  setStandaloneIdeaEditorOpen(false);
  detailStandaloneIdeaMeta.textContent = `创建 ${item.created_at || "-"} · 更新 ${item.updated_at || "-"}`;
  detailStandaloneIdeaText.textContent = item.note || "";
  updateWorkspaceLayout();
}


function closeAllReviewPanels() {
  if (detailReviewBody) detailReviewBody.classList.add("hidden");
  if (detailReviewCreateBody) detailReviewCreateBody.classList.add("hidden");
}

function hideAllDetailPanelsForReview() {
  closeTagAdminView();
  closeTrendComposerView();
  resetDetailChatState({ keepProvider: true });
  stopDetailPolling();
  closeMarketPicker();
  closeReminderEditor();
  if (detailReminderCard) detailReminderCard.classList.add("hidden");
  if (detailBody) detailBody.classList.add("hidden");
  if (detailDailyBody) detailDailyBody.classList.add("hidden");
  if (detailChatBody) detailChatBody.classList.add("hidden");
  if (detailTrendIdeaBody) detailTrendIdeaBody.classList.add("hidden");
  if (detailStandaloneIdeaBody) detailStandaloneIdeaBody.classList.add("hidden");
  if (detailStandaloneIdeaNewBody) detailStandaloneIdeaNewBody.classList.add("hidden");
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  if (detailTagAdminBody) detailTagAdminBody.classList.add("hidden");
}

async function openReviewCard(item) {
  if (!item) return;
  state.selectedReviewId = item.id;
  syncReviewRowSelection();
  hideAllDetailPanelsForReview();
  detailEmpty.classList.add("hidden");
  closeAllReviewPanels();
  detailReviewBody.classList.remove("hidden");

  // Show loading state
  detailReviewTitle.textContent = "加载中…";
  detailReviewMeta.textContent = "";
  if (detailReviewResultBadge) {
    detailReviewResultBadge.classList.add("hidden");
    detailReviewResultBadge.textContent = "";
    detailReviewResultBadge.className = "review-result-badge hidden";
  }
  detailReviewTimeline.innerHTML = "";
  if (detailReviewScrollArea) detailReviewScrollArea.scrollTop = 0;
  hideAllReviewForms();

  try {
    const review = await fetchReviewDetail(item.id);
    renderReviewDetail(review);
  } catch (err) {
    detailReviewTitle.textContent = "复盘暂不可用";
    detailReviewMeta.textContent = "列表位置和当前选择已保留。";
    setInlineFeedback(
      detailReviewTimeline,
      `复盘详情读取失败：${friendlyActionError(err, "网络或服务暂时不可用。")}`,
      {
        tone: "failed",
        actionLabel: "重试",
        onAction: () => openReviewCard(item),
        className: "review-load-feedback",
      },
    );
  }
  openDetailOnMobile();
  updateWorkspaceLayout();
}

function hideAllReviewForms() {
  if (detailReviewProgressForm) detailReviewProgressForm.classList.add("hidden");
  if (detailReviewReviseForm) detailReviewReviseForm.classList.add("hidden");
  if (detailReviewCompleteForm) detailReviewCompleteForm.classList.add("hidden");
  if (detailReviewRetrackForm) detailReviewRetrackForm.classList.add("hidden");
}

function showReviewForm(form, firstInput) {
  hideAllReviewForms();
  clearInlineFeedback(form);
  if (form) form.classList.remove("hidden");
  if (detailReviewScrollArea) detailReviewScrollArea.scrollTop = 0;
  window.requestAnimationFrame(() => {
    if (!firstInput) return;
    try {
      firstInput.focus({ preventScroll: true });
    } catch {
      firstInput.focus();
    }
  });
}

function renderReviewDetail(review) {
  const effStatus = review.effective_status || "in_progress";
  const isDone = review.status === "done";
  const isPending = effStatus === "pending_review";

  detailReviewTitle.textContent = review.current_judgment || "(无判断)";

  const metaParts = [];
  metaParts.push(reviewSourceTypeLabel(review.source_type));
  if (review.source_tag_label) metaParts.push(review.source_tag_label);
  metaParts.push(`计划复盘 ${review.plan_review_date || "-"}`);
  if (review.current_version > 1) metaParts.push(`当前 V${review.current_version}`);
  if (review.completed_at) metaParts.push(`完成于 ${review.completed_at.slice(0, 10)}`);
  detailReviewMeta.textContent = metaParts.join(" · ");

  // Result badge
  if (detailReviewResultBadge) {
    if (isDone && review.result) {
      detailReviewResultBadge.className = `review-result-badge ${review.result}`;
      detailReviewResultBadge.textContent = reviewResultLabel(review.result);
      detailReviewResultBadge.classList.remove("hidden");
    } else {
      detailReviewResultBadge.className = "review-result-badge hidden";
      detailReviewResultBadge.textContent = "";
    }
  }

  // Toolbar button visibility
  if (detailReviewProgressBtn) detailReviewProgressBtn.classList.toggle("hidden", isDone);
  if (detailReviewReviseBtn) detailReviewReviseBtn.classList.toggle("hidden", isDone);
  if (detailReviewCompleteBtn) {
    detailReviewCompleteBtn.classList.toggle("hidden", isDone);
    detailReviewCompleteBtn.textContent = isPending ? "开始复盘" : "提前复盘";
  }
  if (detailReviewRetrackBtn) detailReviewRetrackBtn.classList.toggle("hidden", !isDone);

  // Source content + news highlights
  renderReviewSourceInfo(review);

  // Timeline
  renderReviewTimeline(review);

  // Hide all forms
  hideAllReviewForms();

  // Store current review for form handlers
  state.currentReview = review;
}

function renderReviewSourceInfo(review) {
  // Remove existing source-info section
  const existing = detailReviewScrollArea?.querySelector(".review-source-info");
  if (existing) existing.remove();

  const snap = review.source_snapshot || {};
  const sourceNote = snap.source_note || review.source_note || "";
  const newsList = snap.news_list || [];
  if (!sourceNote && !newsList.length) return;

  const section = document.createElement("section");
  section.className = "review-source-info";

  if (sourceNote) {
    const noteDiv = document.createElement("div");
    noteDiv.className = "review-source-note";
    const label = document.createElement("div");
    label.className = "review-timeline-header";
    label.textContent = "来源想法";
    noteDiv.appendChild(label);
    const text = document.createElement("div");
    text.className = "review-source-note-text";
    text.textContent = sourceNote;
    noteDiv.appendChild(text);
    section.appendChild(noteDiv);
  }

  if (newsList.length) {
    const newsDiv = document.createElement("div");
    newsDiv.className = "review-source-news";
    const label = document.createElement("div");
    label.className = "review-timeline-header";
    label.textContent = "关联新闻";
    newsDiv.appendChild(label);
    newsList.forEach((n) => {
      const card = document.createElement("div");
      card.className = "review-timeline-card evidence-card";
      if (n.source || n.published_at) {
        const meta = document.createElement("div");
        meta.className = "review-timeline-evidence-meta";
        meta.textContent = [n.source, n.published_at].filter(Boolean).join(" · ");
        card.appendChild(meta);
      }
      const title = document.createElement("div");
      title.className = "review-timeline-evidence-title";
      title.textContent = n.title || "(无标题)";
      card.appendChild(title);
      if (n.summary) {
        const summary = document.createElement("div");
        summary.className = "review-timeline-evidence-summary";
        summary.textContent = n.summary;
        card.appendChild(summary);
      }
      if (n.url) {
        const link = document.createElement("a");
        link.className = "review-timeline-evidence-link";
        link.href = n.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "查看原文";
        card.appendChild(link);
      }
      newsDiv.appendChild(card);
    });
    section.appendChild(newsDiv);
  }

  // Insert after the result badge, before the independently scrolling timeline.
  if (detailReviewTimeline && detailReviewTimeline.parentElement === detailReviewScrollArea) {
    detailReviewScrollArea.insertBefore(section, detailReviewTimeline);
  } else if (detailReviewScrollArea) {
    detailReviewScrollArea.appendChild(section);
  }
}

function renderReviewTimeline(review) {
  const timeline = detailReviewTimeline;
  if (!timeline) return;
  timeline.innerHTML = "";

  // Versions
  if (review.versions && review.versions.length) {
    const versionsHeader = document.createElement("div");
    versionsHeader.className = "review-timeline-header";
    versionsHeader.textContent = "判断版本";
    timeline.appendChild(versionsHeader);

    review.versions.forEach((v) => {
      const card = document.createElement("div");
      card.className = "review-timeline-card version-card";
      const header = document.createElement("div");
      header.className = "review-timeline-card-header";
      const versionLabel = document.createElement("span");
      versionLabel.className = "note-badge review-version-badge";
      versionLabel.textContent = `V${v.version_no}`;
      header.appendChild(versionLabel);
      const time = document.createElement("span");
      time.className = "review-timeline-time";
      time.textContent = v.created_at ? v.created_at.slice(0, 16).replace("T", " ") : "";
      header.appendChild(time);
      card.appendChild(header);

      const judgment = document.createElement("div");
      judgment.className = "review-timeline-judgment";
      judgment.textContent = v.judgment;
      card.appendChild(judgment);

      if (v.criteria) {
        const criteria = document.createElement("div");
        criteria.className = "review-timeline-criteria";
        criteria.textContent = `成立标准：${v.criteria}`;
        card.appendChild(criteria);
      }

      if (v.revision_reason) {
        const reason = document.createElement("div");
        reason.className = "review-timeline-reason";
        reason.textContent = `修正原因：${v.revision_reason}`;
        card.appendChild(reason);
      }
      timeline.appendChild(card);
    });
  }

  // Events
  if (review.events && review.events.length) {
    const eventsHeader = document.createElement("div");
    eventsHeader.className = "review-timeline-header";
    eventsHeader.textContent = "进展事件";
    timeline.appendChild(eventsHeader);

    review.events.forEach((e) => {
      const card = document.createElement("div");
      card.className = "review-timeline-card event-card";
      const header = document.createElement("div");
      header.className = "review-timeline-card-header";
      const typeLabel = document.createElement("span");
      typeLabel.className = `note-badge review-event-badge ${e.event_type}`;
      const typeNames = {
        revision: "创建/修正",
        progress: "进展",
        review_completed: "完成",
        continue_observing: "继续观察",
        retracked: "再次跟踪",
      };
      typeLabel.textContent = typeNames[e.event_type] || e.event_type;
      header.appendChild(typeLabel);
      const time = document.createElement("span");
      time.className = "review-timeline-time";
      time.textContent = e.event_date || (e.created_at ? e.created_at.slice(0, 10) : "");
      header.appendChild(time);
      card.appendChild(header);

      if (e.event_text) {
        const text = document.createElement("div");
        text.className = "review-timeline-event-text";
        text.textContent = e.event_text;
        card.appendChild(text);
      }
      timeline.appendChild(card);
    });
  }

  // Evidence
  if (review.evidence && review.evidence.length) {
    const evidenceHeader = document.createElement("div");
    evidenceHeader.className = "review-timeline-header";
    evidenceHeader.textContent = "证据新闻";
    timeline.appendChild(evidenceHeader);

    review.evidence.forEach((ev) => {
      const card = document.createElement("div");
      card.className = "review-timeline-card evidence-card";
      const title = document.createElement("div");
      title.className = "review-timeline-evidence-title";
      title.textContent = ev.news_title || "(无标题)";
      card.appendChild(title);
      if (ev.news_summary) {
        const summary = document.createElement("div");
        summary.className = "review-timeline-evidence-summary";
        summary.textContent = ev.news_summary;
        card.appendChild(summary);
      }
      if (ev.news_url) {
        const link = document.createElement("a");
        link.className = "review-timeline-evidence-link";
        link.href = ev.news_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "查看原文";
        card.appendChild(link);
      }
      if (review.status !== "done") {
        const delBtn = document.createElement("button");
        delBtn.className = "detail-retry-btn review-evidence-delete-btn";
        delBtn.type = "button";
        delBtn.textContent = "删除";
        delBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          clearInlineFeedback(card);
          setButtonBusy(delBtn, true, "删除中…");
          try {
            const updated = await reviewDeleteEvidence(review.id, ev.id);
            renderReviewDetail(updated);
          } catch (err) {
            setInlineFeedback(
              card,
              `删除证据失败：${friendlyActionError(err, "服务暂时不可用。")}`,
              {
                tone: "failed",
                actionLabel: "重试",
                onAction: () => delBtn.click(),
              },
            );
          } finally {
            setButtonBusy(delBtn, false);
          }
        });
        card.appendChild(delBtn);
      }
      timeline.appendChild(card);
    });
  }

  // Completed summary
  if (review.status === "done") {
    const doneHeader = document.createElement("div");
    doneHeader.className = "review-timeline-header";
    doneHeader.textContent = "复盘总结";
    timeline.appendChild(doneHeader);

    const card = document.createElement("div");
    card.className = "review-timeline-card done-card";
    if (review.actual_text) {
      const actual = document.createElement("div");
      actual.className = "review-timeline-done-field";
      actual.textContent = `实际发生：${review.actual_text}`;
      card.appendChild(actual);
    }
    if (review.bias_text) {
      const bias = document.createElement("div");
      bias.className = "review-timeline-done-field";
      bias.textContent = `评价与偏差：${review.bias_text}`;
      card.appendChild(bias);
    }
    if (review.experience) {
      const exp = document.createElement("div");
      exp.className = "review-timeline-done-field";
      exp.textContent = `经验：${review.experience}`;
      card.appendChild(exp);
    }
    timeline.appendChild(card);
  }
}
function openStandaloneIdeaNewView() {
  closeTagAdminView();
  closeTrendComposerView();
  resetDetailChatState({ keepProvider: true });
  stopDetailPolling();
  closeMarketPicker();
  closeReminderEditor();
  if (detailReminderCard) detailReminderCard.classList.add("hidden");
  syncDetailReturnButton();
  detailBody.classList.add("hidden");
  if (detailDailyBody) detailDailyBody.classList.add("hidden");
  detailChatBody.classList.add("hidden");
  if (detailTrendIdeaBody) detailTrendIdeaBody.classList.add("hidden");
  detailStandaloneIdeaBody.classList.add("hidden");
  state.selectedStandaloneIdea = null;
  state.selectedIdeaId = "";
  syncIdeaRowSelection();
  detailEmpty.classList.add("hidden");
  detailStandaloneIdeaNewBody.classList.remove("hidden");
  clearInlineFeedback(detailStandaloneIdeaNewSaveBtn?.closest(".detail-note-editor"));
  if (detailStandaloneIdeaNewSaveBtn) {
    detailStandaloneIdeaNewSaveBtn.disabled = false;
    detailStandaloneIdeaNewSaveBtn.textContent = "保存";
    detailStandaloneIdeaNewSaveBtn.removeAttribute("aria-busy");
    delete detailStandaloneIdeaNewSaveBtn.dataset.idleLabel;
  }
  if (detailStandaloneIdeaNewInput) detailStandaloneIdeaNewInput.value = "";
  updateWorkspaceLayout();
  if (detailStandaloneIdeaNewInput) detailStandaloneIdeaNewInput.focus();
}

async function createStandaloneIdea(note) {
  const res = await fetch("/api/standalone-ideas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error("standalone_idea_create_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "standalone_idea_create_failed");
  return data.idea;
}

async function updateStandaloneIdea(ideaId, note) {
  const res = await fetch(`/api/standalone-ideas/${encodeURIComponent(ideaId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new Error("standalone_idea_update_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "standalone_idea_update_failed");
  return data.idea;
}

async function deleteStandaloneIdea(ideaId) {
  const res = await fetch(`/api/standalone-ideas/${encodeURIComponent(ideaId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("standalone_idea_delete_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "standalone_idea_delete_failed");
  return data;
}

async function fetchDailyBriefingsIndex() {
  const res = await fetch("/api/daily-briefings");
  const data = await res.json().catch(() => ({ ok: false, error: "daily_briefings_fetch_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "daily_briefings_fetch_failed");
  return data;
}

async function fetchDailyBriefingDetail(date) {
  const res = await fetch(`/api/daily-briefings/${encodeURIComponent(date)}`);
  const data = await res.json().catch(() => ({ ok: false, error: "daily_briefing_detail_fetch_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "daily_briefing_detail_fetch_failed");
  return data.briefing;
}

function syncDailyRowSelection() {
  newsList.querySelectorAll(".daily-briefing-row").forEach((row) => {
    row.classList.toggle("selected", row.dataset.date === state.selectedDailyDate);
  });
}

function toggleDailyMonth(monthKey) {
  state.dailyExpandedMonths[monthKey] = !state.dailyExpandedMonths[monthKey];
  renderDailyBriefingsList();
}

function ensureDailyMonthState(months) {
  let initialized = false;
  months.forEach((month, index) => {
    if (typeof state.dailyExpandedMonths[month.month] === "boolean") return;
    state.dailyExpandedMonths[month.month] = index === 0;
    initialized = true;
  });
  if (initialized) {
    Object.keys(state.dailyExpandedMonths).forEach((monthKey) => {
      if (!months.some((month) => month.month === monthKey)) {
        delete state.dailyExpandedMonths[monthKey];
      }
    });
  }
}

function buildDailyMonthRow(month) {
  const li = document.createElement("li");
  li.className = "daily-month-section";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "daily-month-toggle";
  button.dataset.month = month.month || "";
  const title = document.createElement("span");
  title.className = "daily-month-title";
  title.textContent = month.label || month.month || "未知月份";
  const meta = document.createElement("span");
  meta.className = "daily-month-meta";
  const expanded = !!state.dailyExpandedMonths[month.month];
  meta.textContent = `${month.count || 0} 份 · ${expanded ? "收起" : "展开"}`;
  button.appendChild(title);
  button.appendChild(meta);
  button.addEventListener("click", () => toggleDailyMonth(month.month));
  li.appendChild(button);
  return li;
}

function buildDailyBriefingRow(item) {
  const li = document.createElement("li");
  li.className = "news-item daily-briefing-row";
  li.dataset.date = item.date || "";

  const line1 = document.createElement("div");
  line1.className = "line1";
  const badge = document.createElement("span");
  badge.className = "note-badge";
  badge.textContent = item.weekday_label || "日报";
  const text = document.createElement("span");
  text.className = "line1-text";
  text.textContent = item.date_label || item.date || "";
  line1.appendChild(badge);
  line1.appendChild(text);

  const title = document.createElement("div");
  title.className = "title";
  title.textContent = item.title || item.page_title || `${item.date_label || item.date || ""} 日报`;

  const summary = document.createElement("p");
  summary.className = "summary";
  renderDailyMetadata(summary, item, { includeDate: false, fallbackText: "无额外元数据" });

  li.appendChild(line1);
  li.appendChild(title);
  li.appendChild(summary);
  li.addEventListener("click", async () => {
    if (state.selectedDailyDate === item.date) {
      state.selectedDailyDate = "";
      state.selectedDailyBriefing = null;
      syncDailyRowSelection();
      closeDetailOnMobile();
      renderDetail(null);
      return;
    }
    state.selectedDailyDate = item.date || "";
    syncDailyRowSelection();
    await openDailyBriefingDetail(item.date, item);
  });
  li.classList.toggle("selected", state.selectedDailyDate === item.date);
  return li;
}

function renderDailyBriefingsList() {
  newsList.querySelectorAll(".daily-month-section, .daily-briefing-row").forEach((node) => node.remove());
  ensureDailyMonthState(state.dailyBriefings);
  const anchor = listHint && listHint.parentElement === newsList ? listHint : loadMoreSentinel;
  state.dailyBriefings.forEach((month) => {
    const monthRow = buildDailyMonthRow(month);
    newsList.insertBefore(monthRow, anchor);
    if (!state.dailyExpandedMonths[month.month]) return;
    (month.items || []).forEach((item) => {
      newsList.insertBefore(buildDailyBriefingRow(item), anchor);
    });
  });
  syncDailyRowSelection();
}

function renderDailyInlineParts(parts, container) {
  (parts || []).forEach((part) => {
    const text = part?.text || "";
    if (!text) return;
    let node;
    if (part.type === "bold") {
      node = document.createElement("strong");
      node.textContent = text;
    } else if (part.type === "code") {
      node = document.createElement("code");
      node.textContent = text;
    } else {
      node = document.createTextNode(text);
    }
    container.appendChild(node);
  });
}

function dailyBriefingTitle(briefing = {}) {
  return briefing.title || briefing.page_title || (briefing.date_label ? `${briefing.date_label} 日报` : "日报");
}

function renderDailyMetadata(container, briefing = {}, { includeDate = false, fallbackText = "" } = {}) {
  if (!container) return false;
  container.replaceChildren();

  const fragments = [];
  if (includeDate) {
    const dateLabel = briefing.date_label || briefing.date || "";
    if (dateLabel) fragments.push({ className: "daily-meta-date", text: dateLabel });
  }

  const metadata = Array.isArray(briefing.metadata)
    ? briefing.metadata.filter((entry) => entry && (entry.key || entry.value))
    : [];
  if (metadata.length) {
    metadata.forEach((entry) => {
      fragments.push({
        className: "daily-meta-pair",
        key: entry.key || "",
        text: `${entry.key || "元数据"}：${entry.value || "-"}`,
      });
    });
  } else {
    const text = briefing.metadata_summary || fallbackText;
    if (text) fragments.push({ className: "daily-meta-fallback", text });
  }

  fragments.forEach((fragment, index) => {
    if (index > 0) {
      const separator = document.createElement("span");
      separator.className = "daily-meta-separator";
      separator.setAttribute("aria-hidden", "true");
      separator.textContent = "·";
      container.appendChild(separator);
    }
    const part = document.createElement("span");
    part.className = fragment.className;
    if (fragment.key) part.dataset.dailyMetaKey = fragment.key;
    part.textContent = fragment.text;
    container.appendChild(part);
  });

  return fragments.length > 0;
}

function setDailyBriefingHeader(briefing = {}, statusText = "", statusClass = "muted") {
  detailDailyTitle.textContent = dailyBriefingTitle(briefing);
  detailDailyTitle.classList.remove("hidden");

  const hasMeta = renderDailyMetadata(detailDailyMeta, briefing, { includeDate: true });
  detailDailyMeta.classList.toggle("hidden", !hasMeta);

  detailDailyStatus.textContent = statusText;
  detailDailyStatus.className = `detail-status ${statusText ? statusClass : "hidden"}`;
}

function renderDailyBriefingDetailLoading(item) {
  if (!detailDailyBody || !detailDailyTitle || !detailDailyMeta || !detailDailyStatus || !detailDailyContent) return;
  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  detailBody.classList.add("hidden");
  detailChatBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  detailDailyBody.classList.remove("hidden");
  setDailyBriefingHeader(item || {}, "读取中...", "pending");
  detailDailyContent.innerHTML = "";
  updateWorkspaceLayout();
}

function renderDailyBriefingDetail(briefing) {
  if (!detailDailyBody || !detailDailyTitle || !detailDailyMeta || !detailDailyStatus || !detailDailyContent) return;
  closeTagAdminView();
  closeTrendComposerView();
  clearTrendIdeaDetailState();
  resetDetailChatState({ keepProvider: true });
  stopDetailPolling();
  closeMarketPicker();
  closeReminderEditor();
  closeDetailTrackEditor();
  if (detailReminderCard) detailReminderCard.classList.add("hidden");
  state.detailReturnToTrackedTopicId = null;
  syncDetailReturnButton();

  if (detailTrackedBody) detailTrackedBody.classList.add("hidden");
  if (detailTrackedFormBody) detailTrackedFormBody.classList.add("hidden");
  detailBody.classList.add("hidden");
  detailChatBody.classList.add("hidden");
  detailEmpty.classList.add("hidden");
  detailDailyBody.classList.remove("hidden");
  setDailyBriefingHeader(briefing || {});
  detailDailyContent.innerHTML = "";

  if (briefing.parse_mode === "fallback" && briefing.parse_warning) {
    const notice = document.createElement("p");
    notice.className = "detail-daily-notice";
    notice.textContent = "当前日报结构已退化为安全文本块展示";
    detailDailyContent.appendChild(notice);
  }

  (briefing.sections || []).forEach((section) => {
    const block = document.createElement("section");
    block.className = "detail-daily-section";
    const title = document.createElement("h4");
    title.className = "detail-daily-section-title";
    title.textContent = section.title || "内容";
    block.appendChild(title);

    const list = document.createElement("div");
    list.className = "detail-daily-items";
    (section.items || []).forEach((item) => {
      const row = document.createElement("div");
      row.className = item.type === "bullet" ? "detail-daily-bullet" : "detail-daily-paragraph";
      renderDailyInlineParts(item.parts || [], row);
      list.appendChild(row);
    });
    block.appendChild(list);
    detailDailyContent.appendChild(block);
  });

  if (briefing.footer_note) {
    const footer = document.createElement("p");
    footer.className = "detail-daily-footer";
    footer.textContent = briefing.footer_note;
    detailDailyContent.appendChild(footer);
  }

  updateWorkspaceLayout();
}

async function openDailyBriefingDetail(date, seedItem = null) {
  if (!date) return;
  renderDailyBriefingDetailLoading(seedItem || { date });
  try {
    const briefing = await fetchDailyBriefingDetail(date);
    if (state.collection !== "daily" || state.selectedDailyDate !== date) return;
    state.selectedDailyBriefing = briefing;
    renderDailyBriefingDetail(briefing);
    openDetailOnMobile();
  } catch (error) {
    if (state.collection !== "daily" || state.selectedDailyDate !== date) return;
    if (detailDailyStatus) {
      detailDailyStatus.textContent = `读取失败：${error?.message || error}`;
      detailDailyStatus.className = "detail-status failed";
    }
    if (detailDailyContent) detailDailyContent.innerHTML = "";
    updateWorkspaceLayout();
  }
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

async function fetchReviewsPage(page) {
  const params = new URLSearchParams({
    page: String(page),
    per: String(state.per),
    status: state.reviewFilter,
    result: state.reviewFilter === "done" ? state.reviewOutcomeFilter : "all",
  });
  const res = await fetch(`/api/reviews?${params.toString()}`);
  if (!res.ok) throw new Error("reviews_fetch_failed");
  return res.json();
}

async function fetchReviewDetail(chainId) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}`);
  if (!res.ok) throw new Error("review_detail_fetch_failed");
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "review_detail_fetch_failed");
  return data.review;
}

async function createReview(payload) {
  const res = await fetch("/api/reviews", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_create_failed");
  return data.review;
}

async function reviewProgress(chainId, payload) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/progress`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_progress_failed");
  return data.review;
}

async function reviewRevise(chainId, payload) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_revise_failed");
  return data.review;
}

async function reviewComplete(chainId, payload) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_complete_failed");
  return data.review;
}

async function reviewContinueObserving(chainId, payload) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/continue-observing`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_continue_failed");
  return data.review;
}

async function reviewRetrack(chainId, payload) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/retrack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_retrack_failed");
  return data.review;
}

async function reviewAddEvidence(chainId, payload) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/evidence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_evidence_add_failed");
  return data.review;
}

async function reviewDeleteEvidence(chainId, evidenceId) {
  const res = await fetch(`/api/reviews/${encodeURIComponent(chainId)}/evidence/${encodeURIComponent(evidenceId)}`, {
    method: "DELETE",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) throw new Error(data.error || "review_evidence_delete_failed");
  return data.review;
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

function trackedTimeflowBatchTargets(days, mode = state.trackedTimeflowBatchMode) {
  const rows = Array.isArray(days) ? days : [];
  if (mode === "missing") return rows.filter((day) => day?.status === "missing");
  if (mode === "stale") return rows.filter((day) => day?.status === "stale");
  return rows;
}

async function runTrackedTimeflowBatch(topicId) {
  const topic = selectedTrackedTopic();
  if (!topic || String(topic.id) !== String(topicId)) return;
  const targets = trackedTimeflowBatchTargets(state.trackedDailySummaries, state.trackedTimeflowBatchMode);
  if (!targets.length) {
    const modeLabel = state.trackedTimeflowBatchMode === "missing" ? "未生成" : (state.trackedTimeflowBatchMode === "stale" ? "已过期" : "可处理");
    setHint(`没有需要一键生成的${modeLabel}日期`);
    return;
  }
  const token = `${topicId}:${Date.now()}`;
  state.trackedTimeflowBatchToken = token;
  let successCount = 0;
  let failedCount = 0;
  for (const day of targets) {
    if (state.trackedTimeflowBatchToken !== token || String(state.selectedTrackedTopicId) !== String(topicId) || state.collection !== "tracked") {
      break;
    }
    try {
      await generateTrackedTopicDailySummary(topicId, day.date);
      successCount += 1;
    } catch (_) {
      failedCount += 1;
    }
    if (state.trackedTimeflowBatchToken !== token || String(state.selectedTrackedTopicId) !== String(topicId) || state.collection !== "tracked") {
      break;
    }
    await loadTrackedTopicDailySummaries(topicId);
  }
  if (state.trackedTimeflowBatchToken === token) {
    state.trackedTimeflowBatchToken = "";
    if (String(state.selectedTrackedTopicId) === String(topicId) && state.collection === "tracked") {
      setHint(`时间流一键生成完成：成功 ${successCount} 天，失败 ${failedCount} 天`);
    }
  }
}

async function generateTrackedTopicRuleDraft(payload) {
  const res = await fetch("/api/tracked-topics/rule-draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_rule_draft_generate_failed" }));
  if (!res.ok || !data.ok) {
    const detail = data.detail ? `: ${data.detail}` : "";
    throw new Error((data.error || "tracked_rule_draft_generate_failed") + detail);
  }
  return data;
}

async function saveTrackedDefaultRuleParams(defaultRuleParams) {
  const res = await fetch("/api/settings/tracked-default-rule-params", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ default_rule_params: defaultRuleParams }),
  });
  const data = await res.json().catch(() => ({ ok: false, error: "tracked_default_rule_params_save_failed" }));
  if (!res.ok || !data.ok) throw new Error(data.error || "tracked_default_rule_params_save_failed");
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
  clearFeedKeyboardDetailTimer();
  exitFeedKeyboardMode();
  newsList.querySelectorAll(".news-item, .date-section, .market-summary-row, .daily-month-section").forEach((node) => node.remove());
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
  state.dailyBriefings = [];
  state.selectedDailyDate = "";
  state.selectedDailyBriefing = null;
  state.trackedTimelineItems = [];
  stopDetailPolling();
  stopRowStatusPolling();
  clearFeedEndAutoReadTimer();
  feedEndAutoReadFiredKey = "";
  state.selectedTrendIdea = null;
  state.selectedReviewId = null;
  state.currentReview = null;
  state.pendingReviewSource = null;
  state.tagAdminOpen = false;
  state.trendComposeOpen = false;
  state.dateCounts = new Map();
  state.feedUnreadCursor = null;
  resetDetailChatState();
  showListView();
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
  // Review items don't have date_key; skip date-section header for them
  const dateKey = item.date_key;
  if (dateKey && dateKey !== lastRenderedDateKey) {
    const section = buildDateSectionRow(item);
    if (listHint && listHint.parentElement === newsList) {
      newsList.insertBefore(section, listHint);
    } else {
      newsList.appendChild(section);
    }
    lastRenderedDateKey = dateKey;
  } else if (!dateKey) {
    lastRenderedDateKey = null;
  }
  if (listHint && listHint.parentElement === newsList) {
    newsList.insertBefore(row, listHint);
    return;
  }
  newsList.appendChild(row);
}

async function loadFeedPage(page = 1) {
  const normalizedPage = Math.max(1, Number(page) || 1);
  const data = await fetchNewsPage(normalizedPage);
  state.total = data.total;
  setDateCounts(data.date_counts);
  state.pages = data.pages;
  state.page = Number(data.page || normalizedPage);
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
}

async function loadFirstPage(page = 1) {
  clearFeedEndAutoReadTimer();
  startReminderSummaryTimer();
  await refreshReminderSummary().catch(() => {});
  if (state.collection === "feed") {
    state.readFilter = state.feedReadFilter;
  } else if (state.collection === "read_later") {
    state.readFilter = state.readLaterReadFilter;
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
      showListView();
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

    if (state.collection === "daily") {
      const data = await fetchDailyBriefingsIndex();
      state.dailyBriefings = Array.isArray(data.months) ? data.months : [];
      state.total = Number(data.total || 0);
      state.pages = 1;
      state.page = 1;
      state.hasMore = false;
      state.dateCounts = new Map();
      showListView();
      showTrackedView(false);
      renderDailyBriefingsList();
      renderMeta();
      if (state.total === 0) {
        setHint("当前日报目录下还没有可用简报。");
      } else {
        setHint("选择一份日报，在右栏查看结构化内容。");
      }
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
      showListView();
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
      showListView();
      data.items.forEach((item) => appendNewsRow(item, buildIdeaRow(item)));
      renderMeta();
      if (state.total === 0) {
        setHint("还没有想法，去新闻详情或板块里记录第一条。");
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

    if (state.collection === "reviews") {
      const data = await fetchReviewsPage(1);
      state.total = Number(data.total || 0);
      state.pages = Number(data.pages || 1);
      state.page = 1;
      state.hasMore = !!data.has_more;
      state.dateCounts = new Map();
      showListView();
      (data.items || []).forEach((item) => appendNewsRow(item, buildReviewRow(item)));
      renderMeta();
      if (state.total === 0) {
        setHint("还没有复盘，从任意想法右栏点击“加入复盘”开始。");
      } else if (state.hasMore) {
        setHint("继续下滑加载更多");
      } else {
        setHint("已加载全部复盘");
      }
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
      stopRowStatusPolling();
      return;
    }

    if (state.collection === "market_tags") {
      removeMarketWorkbenchSummaryInline();
      const data = await fetchMarketWorkbenchPage(1);
      state.total = Number(data.total || 0);
      state.pages = Number(data.pages || 1);
      state.page = Number(data.page || 1);
      state.hasMore = !!data.has_more;
      state.marketWorkbenchSummary = data.summary || null;
      state.marketWorkbenchPin = data.pin || null;
      state.marketWorkbenchPinEditing = false;
      showListView();
      renderMeta();
      renderMarketWorkbenchPinCard();
      (data.items || []).forEach((item) => {
        const row = item.entry_type === "trend_note" ? buildIdeaRow(item) : buildItemRow(item);
        appendNewsRow(item, row);
      });
      if (state.marketWorkbenchTag) {
        renderMarketWorkbenchSummaryInline();
      } else {
        removeMarketWorkbenchSummaryInline();
      }
      if (!state.total) {
        setHint("当前板块筛选下暂无内容");
      } else if (state.hasMore) {
        setHint("继续下滑加载更多");
      } else {
        setHint("已加载当前板块集合的全部结果");
      }
      ensureRowStatusPolling();
      if (readObserver) {
        readObserver.disconnect();
        readObserver = null;
      }
      return;
    }

    const sourceList = await fetchSources();
    const available = new Set(sourceList.map((x) => x.key));
    if (state.sourceFilter !== "all" && !available.has(state.sourceFilter)) {
      state.sourceFilter = "all";
    }
    renderSourceFilters(sourceList);

    await loadFeedPage(page);
  } finally {
    state.loading = false;
    syncSearchPageControls();
    updateFilterButtons();
    updateBatchActionButton();
    updateRefreshButton();
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
  if (state.collection === "daily") return;
  if (state.collection === "market_tags") {
    if (!state.hasMore || !state.marketWorkbenchTag) return;
    const next = state.page + 1;
    state.loading = true;
    try {
      const data = await fetchMarketWorkbenchPage(next);
      (data.items || []).forEach((item) => {
        const row = item.entry_type === "trend_note" ? buildIdeaRow(item) : buildItemRow(item);
        appendNewsRow(item, row);
      });
      state.page = Number(data.page || next);
      state.pages = Number(data.pages || state.pages);
      state.total = Number(data.total || state.total);
      state.hasMore = !!data.has_more;
      state.marketWorkbenchSummary = data.summary || state.marketWorkbenchSummary;
      state.marketWorkbenchPin = data.pin || state.marketWorkbenchPin;
      renderMeta();
      renderMarketWorkbenchPinCard();
      if (state.marketWorkbenchTag) {
        renderMarketWorkbenchSummaryInline();
      } else {
        removeMarketWorkbenchSummaryInline();
      }
      setHint(state.hasMore ? "继续下滑加载更多" : "已加载该板块的全部当前结果");
      ensureRowStatusPolling();
    } finally {
      state.loading = false;
    }
    return;
  }
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
  if (state.collection === "reviews") {
    if (!state.hasMore) return;
    const next = state.page + 1;
    state.loading = true;
    try {
      const data = await fetchReviewsPage(next);
      (data.items || []).forEach((item) => appendNewsRow(item, buildReviewRow(item)));
      state.page = Number(data.page || next);
      state.pages = Number(data.pages || state.pages);
      state.total = Number(data.total || state.total);
      state.hasMore = !!data.has_more;
      renderMeta();
      setHint(state.hasMore ? "继续下滑加载更多" : "已加载全部复盘");
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
    state.page = Number(data.page || next);
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
    const data = await r.json();
    await loadFirstPage();
    setHint(formatReindexHint(data));
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
  [readLaterFilterUnreadBtn, "unread"],
  [readLaterFilterReadBtn, "read"],
  [readLaterFilterAllBtn, "all"],
].forEach(([button, filter]) => {
  if (!button) return;
  button.addEventListener("click", async () => {
    if (state.readLaterReadFilter === filter) return;
    state.readLaterReadFilter = filter;
    if (state.collection === "read_later") state.readFilter = filter;
    await loadFirstPage();
  });
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
  [ideaFilterStandaloneBtn, "standalone"],
].forEach(([button, filter]) => {
  if (!button) return;
  button.addEventListener("click", async () => {
    if (state.ideaFilter === filter) return;
    state.ideaFilter = filter;
    await loadFirstPage();
  });
});

if (marketWorkbenchTagSelect) {
  marketWorkbenchTagSelect.addEventListener("change", async () => {
    removeMarketWorkbenchSummaryInline();
    state.marketWorkbenchTag = marketWorkbenchTagSelect.value || "";
    state.marketWorkbenchSummary = null;
    state.marketWorkbenchPin = null;
    state.marketWorkbenchPinEditing = false;
    await loadFirstPage();
  });
}

if (marketWorkbenchFilterSelect) {
  marketWorkbenchFilterSelect.addEventListener("change", async () => {
    removeMarketWorkbenchSummaryInline();
    state.marketWorkbenchFilter = marketWorkbenchFilterSelect.value || "all";
    state.marketWorkbenchSummary = null;
    state.marketWorkbenchPinEditing = false;
    await loadFirstPage();
  });
}

if (marketWorkbenchSummaryBtn) {
  marketWorkbenchSummaryBtn.addEventListener("click", async () => {
    if (!state.marketWorkbenchTag) return;
    const requestedTag = state.marketWorkbenchTag;
    marketWorkbenchSummaryBtn.disabled = true;
    try {
      const summary = await generateMarketTagSummary(requestedTag);
      if (state.collection !== "market_tags" || state.marketWorkbenchTag !== requestedTag) {
        return;
      }
      state.marketWorkbenchSummary = summary;
      renderMarketWorkbenchSummaryInline();
      setHint("板块近期趋势总结已更新");
    } catch (error) {
      if (state.collection !== "market_tags" || state.marketWorkbenchTag !== requestedTag) {
        return;
      }
      if (error?.payload) {
        state.marketWorkbenchSummary = error.payload;
        renderMarketWorkbenchSummaryInline();
      }
      setHint(`板块近期趋势总结失败：${error?.message || error}`);
    } finally {
      marketWorkbenchSummaryBtn.disabled = false;
    }
  });
}

if (marketWorkbenchComposeBtn) {
  marketWorkbenchComposeBtn.addEventListener("click", () => {
    const selected = activeMarketTagChoices().find((tag) => tag.key === state.marketWorkbenchTag);
    openTrendComposeView(
      state.marketWorkbenchTag
        ? {
            date: new Date().toISOString().slice(0, 10),
            tagKey: state.marketWorkbenchTag,
            tagLabel: selected?.display_name || state.marketWorkbenchTag,
          }
        : null
    );
  });
}

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
    state.readLaterReadFilter = "unread";
    state.sourceFilter = "all";
    await loadFirstPage(located.page);

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
  removeMarketWorkbenchSummaryInline();
  closeAllReviewPanels();
  state.selectedReviewId = null;
  state.collection = collection;
  if (feedControlsScroll) feedControlsScroll.scrollLeft = 0;
  scheduleFeedControlsOverflowSync();
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

if (navDailyBtn) {
  navDailyBtn.addEventListener("click", async () => {
    await switchCollection("daily");
  });
}

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
if (navReviewsBtn) {
  navReviewsBtn.addEventListener("click", async () => {
    await switchCollection("reviews");
  });
}
if (reviewFilterAllBtn) {
  reviewFilterAllBtn.addEventListener("click", async () => {
    state.reviewFilter = "all";
    await loadFirstPage();
  });
}
if (reviewFilterActiveBtn) {
  reviewFilterActiveBtn.addEventListener("click", async () => {
    state.reviewFilter = "in_progress";
    await loadFirstPage();
  });
}
if (reviewFilterPendingBtn) {
  reviewFilterPendingBtn.addEventListener("click", async () => {
    state.reviewFilter = "pending_review";
    await loadFirstPage();
  });
}
if (reviewFilterDoneBtn) {
  reviewFilterDoneBtn.addEventListener("click", async () => {
    state.reviewFilter = "done";
    await loadFirstPage();
  });
}

[
  [reviewOutcomeFilterAllBtn, "all"],
  [reviewOutcomeFilterConfirmedBtn, "confirmed"],
  [reviewOutcomeFilterRefutedBtn, "refuted"],
  [reviewOutcomeFilterInconclusiveBtn, "inconclusive"],
].forEach(([button, filter]) => {
  if (!button) return;
  button.addEventListener("click", async () => {
    state.reviewOutcomeFilter = filter;
    await loadFirstPage();
  });
});
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

if (mobileCollectionTriggerBtn) {
  mobileCollectionTriggerBtn.addEventListener("click", async () => {
    await switchCollection("feed");
  });
}

if (mobileReadLaterTabBtn) {
  mobileReadLaterTabBtn.addEventListener("click", async () => {
    await switchCollection("read_later");
  });
}

if (mobileMoreTabBtn) {
  mobileMoreTabBtn.addEventListener("click", () => {
    openMobileCollectionSheet();
  });
}

if (mobileSourceEntryBtn) {
  mobileSourceEntryBtn.addEventListener("click", () => {
    openMobileFilterSheet();
  });
}

if (trackedCreateInlineBtn) {
  trackedCreateInlineBtn.addEventListener("click", () => {
    openTrackedTopicForm("create");
  });
}

if (trackedDefaultsInlineBtn) {
  trackedDefaultsInlineBtn.addEventListener("click", () => {
    openTrackedDefaultsPanel();
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

if (trackedTimeflowBatchModeSelect) {
  trackedTimeflowBatchModeSelect.addEventListener("change", () => {
    state.trackedTimeflowBatchMode = trackedTimeflowBatchModeSelect.value || "all";
  });
}

if (trackedTimeflowBatchGenerateBtn) {
  trackedTimeflowBatchGenerateBtn.addEventListener("click", async () => {
    const topic = selectedTrackedTopic();
    if (!topic) return;
    trackedTimeflowBatchGenerateBtn.disabled = true;
    try {
      await runTrackedTimeflowBatch(topic.id);
    } finally {
      trackedTimeflowBatchGenerateBtn.disabled = false;
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
    if (state.collection !== "market_tags") return;
    await openTagAdminView();
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

if (settingsChatProviderSelect) {
  settingsChatProviderSelect.addEventListener("change", () => {
    renderChatProviderFieldVisibility();
  });
}

if (settingsCodexChatModelSelect) {
  settingsCodexChatModelSelect.addEventListener("change", () => {
    syncModelCustomVisibility(settingsCodexChatModelSelect, settingsCodexChatModelCustom);
  });
}

if (settingsPiChatProviderSelect) {
  settingsPiChatProviderSelect.addEventListener("change", () => {
    syncModelCustomVisibility(settingsPiChatProviderSelect, settingsPiChatProviderCustom);
  });
}

if (settingsPiChatModelSelect) {
  settingsPiChatModelSelect.addEventListener("change", () => {
    syncModelCustomVisibility(settingsPiChatModelSelect, settingsPiChatModelCustom);
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
    state.collection === "market_tags"
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
    body.read_filter = state.readFilter;
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
    const data = await r.json();
    await loadFirstPage();
    newsList.scrollTo({ top: 0, behavior: "auto" });
    setHint(formatReindexHint(data));
  } catch {
    setHint("同步失败，可稍后重试。");
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.classList.remove("loading");
    applyIcon(refreshBtn, "refresh", { label: "刷新索引" });
  }
});

detailCloseBtn.addEventListener("click", () => {
  if (canReturnToTrackedTopic()) {
    restoreTrackedTopicFromDetail().catch(() => {});
    return;
  }
  closeDetailOnMobile();
  stopDetailPolling();
});
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
  const target = event.target;
  if (topbarViewMenu?.open && target instanceof Node && !topbarViewMenu.contains(target)) {
    topbarViewMenu.removeAttribute("open");
  }
  if (!errorStatsPanel || errorStatsPanel.classList.contains("hidden")) return;
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
    clearDetailActionFeedback();
    detailTrackBtn.disabled = true;
    try {
      await openDetailTrackEditor(item);
    } catch (error) {
      showDetailActionFeedback(
        `读取跟踪主题失败：${friendlyActionError(error, "请稍后重试。")}`,
      );
    } finally {
      detailTrackBtn.disabled = false;
    }
  });
}

if (detailReminderSaveBtn) {
  detailReminderSaveBtn.addEventListener("click", async () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item) return;
    clearInlineFeedback(detailReminderEditor);
    setButtonBusy(detailReminderSaveBtn, true, "保存中…");
    setInlineFeedback(detailReminderEditor, "正在保存提醒…", { tone: "pending" });
    try {
      await saveReminderDraft(item, state.selectedReminderDraftId || null);
    } catch (error) {
      setInlineFeedback(
        detailReminderEditor,
        `保存提醒失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailReminderSaveBtn, false);
    }
  });
}

if (detailReminderDeleteBtn) {
  detailReminderDeleteBtn.addEventListener("click", async () => {
    if (!state.selectedId || !state.selectedReminderDraftId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item) return;
    if (!window.confirm("确认删除这个提醒？")) return;
    clearInlineFeedback(detailReminderEditor);
    setButtonBusy(detailReminderDeleteBtn, true, "删除中…");
    setInlineFeedback(detailReminderEditor, "正在删除提醒…", { tone: "pending" });
    try {
      await removeReminderDraft(item, state.selectedReminderDraftId);
    } catch (error) {
      setInlineFeedback(
        detailReminderEditor,
        `删除提醒失败：${friendlyActionError(error, "提醒仍然保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailReminderDeleteBtn, false);
    }
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
    clearInlineFeedback(detailTrackEditor);
    setButtonBusy(detailTrackSaveBtn, true, "加入中…");
    setInlineFeedback(detailTrackEditor, "正在加入跟踪主题…", { tone: "pending" });
    try {
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
    } catch (error) {
      setInlineFeedback(
        detailTrackEditor,
        `加入跟踪主题失败：${friendlyActionError(error, "当前选择已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailTrackSaveBtn, false);
    }
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

if (detailTrackedSaveDefaultsBtn) {
  detailTrackedSaveDefaultsBtn.addEventListener("click", async () => {
    const form = trackedFeedbackHost(detailTrackedFormBody);
    const payload = trackedDefaultParamsPayloadFromInputs({
      threshold: detailTrackedThresholdInput,
      title_weight: detailTrackedTitleWeightInput,
      note_weight: detailTrackedNoteWeightInput,
      summary_weight: detailTrackedSummaryWeightInput,
      content_weight: detailTrackedContentWeightInput,
      strong_score: detailTrackedStrongScoreInput,
      core_score: detailTrackedCoreScoreInput,
      context_score: detailTrackedContextScoreInput,
      exclude_penalty: detailTrackedExcludePenaltyInput,
    });
    detailTrackedSaveDefaultsBtn.disabled = true;
    setInlineFeedback(form, "正在保存默认参数…", { tone: "pending" });
    try {
      state.runtimeSettings = await saveTrackedDefaultRuleParams(payload);
      setInlineFeedback(form, "当前数字参数已保存为默认值，只影响后续新建主题。", { tone: "ready" });
    } catch (error) {
      setInlineFeedback(
        form,
        `保存默认参数失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      detailTrackedSaveDefaultsBtn.disabled = false;
    }
  });
}

if (detailTrackedDraftBtn) {
  detailTrackedDraftBtn.addEventListener("click", async () => {
    const form = trackedFeedbackHost(detailTrackedFormBody);
    clearInlineFeedback(form);
    const title = detailTrackedTitleInput?.value.trim() || "";
    if (!title) {
      setInlineFeedback(form, "请先输入主题名称，再生成规则草稿。", { tone: "failed" });
      detailTrackedTitleInput?.focus();
      return;
    }
    if (trackedFormHasRuleContent()) {
      const ok = window.confirm("当前规则字段已有内容，一键填写会覆盖这些字段。是否继续？");
      if (!ok) return;
    }
    detailTrackedDraftBtn.disabled = true;
    detailTrackedDraftBtn.textContent = "生成中...";
    setInlineFeedback(form, `正在为“${title}”生成规则草稿…`, { tone: "pending" });
    try {
      const data = await generateTrackedTopicRuleDraft({ title });
      applyTrackedRuleDraft(data.draft || {});
      setInlineFeedback(form, `已生成“${title}”的规则草稿，请检查后再保存。`, { tone: "ready" });
    } catch (error) {
      setInlineFeedback(
        form,
        `规则草稿生成失败：${friendlyActionError(error, "可手动填写，或稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      detailTrackedDraftBtn.disabled = false;
      detailTrackedDraftBtn.textContent = "一键填写";
    }
  });
}

if (trackedDefaultsSaveBtn) {
  trackedDefaultsSaveBtn.addEventListener("click", async () => {
    const form = trackedFeedbackHost(detailTrackedDefaultsBody);
    const payload = trackedDefaultParamsPayloadFromInputs({
      threshold: trackedDefaultsThresholdInput,
      title_weight: trackedDefaultsTitleWeightInput,
      note_weight: trackedDefaultsNoteWeightInput,
      summary_weight: trackedDefaultsSummaryWeightInput,
      content_weight: trackedDefaultsContentWeightInput,
      strong_score: trackedDefaultsStrongScoreInput,
      core_score: trackedDefaultsCoreScoreInput,
      context_score: trackedDefaultsContextScoreInput,
      exclude_penalty: trackedDefaultsExcludePenaltyInput,
    });
    trackedDefaultsSaveBtn.disabled = true;
    setInlineFeedback(form, "正在保存默认匹配参数…", { tone: "pending" });
    try {
      state.runtimeSettings = await saveTrackedDefaultRuleParams(payload);
      fillTrackedDefaultsForm(getTrackedDefaultRuleParams());
      setInlineFeedback(form, "默认匹配参数已保存，新建主题会自动带入。", { tone: "ready" });
    } catch (error) {
      setInlineFeedback(
        form,
        `保存默认参数失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      trackedDefaultsSaveBtn.disabled = false;
    }
  });
}

if (trackedDefaultsRestoreBtn) {
  trackedDefaultsRestoreBtn.addEventListener("click", async () => {
    const form = trackedFeedbackHost(detailTrackedDefaultsBody);
    trackedDefaultsRestoreBtn.disabled = true;
    setInlineFeedback(form, "正在恢复系统默认参数…", { tone: "pending" });
    try {
      state.runtimeSettings = await saveTrackedDefaultRuleParams(TRACKED_SYSTEM_DEFAULT_RULE_PARAMS);
      fillTrackedDefaultsForm(getTrackedDefaultRuleParams());
      setInlineFeedback(form, "已恢复系统默认参数。", { tone: "ready" });
    } catch (error) {
      setInlineFeedback(
        form,
        `恢复系统默认失败：${friendlyActionError(error, "请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      trackedDefaultsRestoreBtn.disabled = false;
    }
  });
}

if (detailTrackedFormSaveBtn) {
  detailTrackedFormSaveBtn.addEventListener("click", async () => {
    const form = trackedFeedbackHost(detailTrackedFormBody);
    clearInlineFeedback(form);
    const payload = trackedFormPayload();
    if (!payload.title) {
      setInlineFeedback(form, "请先填写跟踪主题名称。", { tone: "failed" });
      detailTrackedTitleInput?.focus();
      return;
    }
    setButtonBusy(detailTrackedFormSaveBtn, true, "保存中…");
    setInlineFeedback(form, "正在保存跟踪主题，当前输入会保留到操作完成。", { tone: "pending" });
    let writeConfirmed = false;
    try {
      let topicId = state.selectedTrackedTopicId;
      if (state.trackedFormMode === "edit" && topicId) {
        await updateTrackedTopic(topicId, payload);
      } else {
        const result = await createTrackedTopic(payload);
        topicId = result.topic?.id || topicId;
      }
      writeConfirmed = true;
      state.trackedTopics = await fetchTrackedTopics();
      state.selectedTrackedTopicId = topicId || null;
      renderTrackedTopicsList();
      if (state.selectedTrackedTopicId) {
        await loadTrackedTopicTimeline(state.selectedTrackedTopicId);
      } else {
        renderTrackedTopicEmpty();
      }
      setHint(state.trackedFormMode === "edit" ? "跟踪主题已更新" : "跟踪主题已创建");
    } catch (error) {
      setInlineFeedback(
        form,
        writeConfirmed
          ? `跟踪主题已保存，但刷新详情失败：${friendlyActionError(error, "请返回跟踪列表后重新打开，不要重复提交。")}`
          : `${state.trackedFormMode === "edit" ? "更新" : "创建"}跟踪主题失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailTrackedFormSaveBtn, false);
      if (writeConfirmed) {
        detailTrackedFormSaveBtn.textContent = "已保存";
        detailTrackedFormSaveBtn.disabled = true;
      }
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

if (trendNoteComposeCancelBtn) {
  trendNoteComposeCancelBtn.addEventListener("click", () => {
    closeTrendComposerView();
    if (state.collection === "market_tags") {
      restoreMarketWorkbenchDetailState();
      return;
    }
    renderDetailEmpty();
  });
}

if (trendNoteComposeSaveBtn) {
  trendNoteComposeSaveBtn.addEventListener("click", async () => {
    const form = trendNoteComposeSaveBtn.closest(".detail-note-editor");
    clearInlineFeedback(form);
    const date = trendNoteDateSelect.value;
    const tag = trendNoteTagSelect.value;
    const direction = trendNoteDirectionSelect.value;
    const note = (trendNoteComposeInput.value || "").trim();
    if (!date || !tag || !direction) {
      setInlineFeedback(form, "请先选择日期、板块和方向。", { tone: "failed" });
      return;
    }
    if (!note) {
      setInlineFeedback(form, "请先输入板块想法内容。", { tone: "failed" });
      trendNoteComposeInput?.focus();
      return;
    }
    setButtonBusy(trendNoteComposeSaveBtn, true, "保存中…");
    setInlineFeedback(form, "正在保存板块想法…", { tone: "pending" });
    let writeConfirmed = false;
    try {
      await saveTrendNote({
        date,
        tag,
        direction,
        note,
      });
      writeConfirmed = true;
      if (state.collection === "market_tags") {
        await refreshMarketWorkbenchAfterTrendCompose();
        closeTrendComposerView();
        restoreMarketWorkbenchDetailState();
        setHint("板块想法已保存");
        return;
      }
      closeTrendComposerView();
      renderDetailEmpty();
      setHint("板块想法已保存");
    } catch (error) {
      setInlineFeedback(
        form,
        writeConfirmed
          ? `板块想法已保存，但刷新工作台失败：${friendlyActionError(error, "请重新进入板块查看，不要重复提交。")}`
          : `保存板块想法失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(trendNoteComposeSaveBtn, false);
      if (writeConfirmed) {
        trendNoteComposeSaveBtn.textContent = "已保存";
        trendNoteComposeSaveBtn.disabled = true;
      }
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

function isTwitterItem(item) {
  return item && (item.source_type === "twitter" || /^https?:\/\/(x\.com|twitter\.com)\//i.test(item.url || ""));
}

detailRetryBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  clearDetailActionFeedback();
  setButtonBusy(detailRetryBtn, true, "重试中…");
  showDetailActionFeedback("正在重新提交详情抓取…", { tone: "pending" });
  try {
    const item = state.itemsById.get(state.selectedId);
    const mode = isTwitterItem(item) && Number(item?.detail_ready || 0) === 1 ? "detail" : "";
    const res = await fetch(`/api/news/${encodeURIComponent(state.selectedId)}/detail/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mode ? { mode } : {}),
    });
    if (!res.ok) throw new Error("detail_retry_failed");
    if (item) {
      if (isTwitterItem(item) && Number(item.detail_ready || 0) === 1) {
        item.detail_status = "pending";
      } else if (Number(item.detail_ready || 0) === 1) {
        item.ai_status = "pending";
      } else {
        item.detail_status = "pending";
      }
      state.itemsById.set(item.id, item);
      rerenderOne(item.id);
    }
    await loadDetail(state.selectedId);
    startDetailPolling(state.selectedId);
    clearDetailActionFeedback();
  } catch (error) {
    showDetailActionFeedback(
      `重试详情抓取失败：${friendlyActionError(error, "请稍后再次重试。")}`,
    );
  } finally {
    setButtonBusy(detailRetryBtn, false);
  }
});

detailRetranslateBtn.addEventListener("click", async () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item || Number(item.detail_ready || 0) !== 1) return;
  clearDetailActionFeedback();
  setButtonBusy(detailRetranslateBtn, true, "提交中…");
  showDetailActionFeedback("正在重新提交中文生成…", { tone: "pending" });
  try {
    const res = await fetch(`/api/news/${encodeURIComponent(state.selectedId)}/detail/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "ai" }),
    });
    if (!res.ok) throw new Error("detail_retranslate_failed");
    item.ai_status = "pending";
    state.itemsById.set(item.id, item);
    rerenderOne(item.id);
    await loadDetail(state.selectedId);
    startDetailPolling(state.selectedId);
    clearDetailActionFeedback();
  } catch (error) {
    showDetailActionFeedback(
      `重新翻译提交失败：${friendlyActionError(error, "现有内容未改变，请稍后重试。")}`,
    );
  } finally {
    setButtonBusy(detailRetranslateBtn, false);
  }
});

if (detailRefreshTweetBtn) {
  detailRefreshTweetBtn.addEventListener("click", async () => {
    if (!state.selectedId) return;
    const item = state.itemsById.get(state.selectedId);
    if (!item || !isTwitterItem(item)) return;
    clearDetailActionFeedback();
    setButtonBusy(detailRefreshTweetBtn, true, "提交中…");
    showDetailActionFeedback("正在重新提交推文抓取…", { tone: "pending" });
    try {
      const res = await fetch(`/api/news/${encodeURIComponent(state.selectedId)}/detail/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "detail" }),
      });
      if (!res.ok) throw new Error("tweet_detail_retry_failed");
      item.detail_status = "pending";
      state.itemsById.set(item.id, item);
      rerenderOne(item.id);
      await loadDetail(state.selectedId);
      startDetailPolling(state.selectedId);
      clearDetailActionFeedback();
    } catch (error) {
      showDetailActionFeedback(
        `重新抓取推文提交失败：${friendlyActionError(error, "现有正文和图片未改变，请稍后重试。")}`,
      );
    } finally {
      setButtonBusy(detailRefreshTweetBtn, false);
    }
  });
}

detailNoteToggleBtn.addEventListener("click", () => {
  if (!state.selectedId) return;
  const item = state.itemsById.get(state.selectedId);
  if (!item) return;
  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  closeReminderEditor();
  detailNoteInput.value = normalizedDetailNote(cached);
  clearInlineFeedback(detailNoteEditor);
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
  clearInlineFeedback(detailNoteEditor);
  const noteText = detailNoteInput.value.slice(0, NOTE_MAX_LEN);
  setButtonBusy(detailNoteSaveBtn, true, "保存中…");
  detailNoteCancelBtn.disabled = true;
  setInlineFeedback(detailNoteEditor, "正在保存想法…", { tone: "pending" });
  try {
    await saveDetailNote(item, noteText);
    setDetailNoteEditorOpen(false);
  } catch (error) {
    setInlineFeedback(
      detailNoteEditor,
      `保存想法失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
      { tone: "failed" },
    );
  } finally {
    setButtonBusy(detailNoteSaveBtn, false);
    detailNoteCancelBtn.disabled = false;
  }
});

if (detailTrendIdeaEditBtn) {
  detailTrendIdeaEditBtn.addEventListener("click", () => {
    const item = state.selectedTrendIdea;
    if (!item) return;
    detailTrendIdeaInput.value = item.note || "";

    if (detailTrendIdeaEditMeta) {
      detailTrendIdeaEditMeta.textContent = `${item.trend_date_key || ""} · 创建 ${item.created_at || "-"} · 更新 ${item.updated_at || "-"}`;
    }

    if (detailTrendIdeaDateSelect) {
      const dateOptions = defaultTrendComposeDates();
      if (item.trend_date_key && !dateOptions.includes(item.trend_date_key)) {
        dateOptions.push(item.trend_date_key);
      }
      detailTrendIdeaDateSelect.innerHTML = "";
      dateOptions.forEach((date) => {
        const opt = document.createElement("option");
        opt.value = date;
        opt.textContent = date;
        detailTrendIdeaDateSelect.appendChild(opt);
      });
      detailTrendIdeaDateSelect.value = item.trend_date_key || dateOptions[0] || "";
    }

    if (detailTrendIdeaTagSelect) {
      const tagOptions = activeMarketTagChoices();
      const currentTagIncluded = tagOptions.some((t) => t.key === item.tag_key);
      if (item.tag_key && !currentTagIncluded) {
        tagOptions.push({ key: item.tag_key, display_name: item.tag_label || item.tag_key });
      }
      detailTrendIdeaTagSelect.innerHTML = "";
      tagOptions.forEach((tag) => {
        const opt = document.createElement("option");
        opt.value = tag.key;
        opt.textContent = tag.display_name || tag.key;
        detailTrendIdeaTagSelect.appendChild(opt);
      });
      if (item.tag_key) detailTrendIdeaTagSelect.value = item.tag_key;
    }

    if (detailTrendIdeaDirectionSelect) {
      detailTrendIdeaDirectionSelect.value = item.direction || "bullish";
    }

    setTrendIdeaEditorOpen(true);
    clearInlineFeedback(detailTrendIdeaSaveBtn?.closest(".detail-note-editor"));
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
    const form = detailTrendIdeaSaveBtn.closest(".detail-note-editor");
    clearInlineFeedback(form);
    const item = state.selectedTrendIdea;
    if (!item) return;
    if (!(detailTrendIdeaInput?.value || "").trim()) {
      setInlineFeedback(form, "板块想法内容不能为空。", { tone: "failed" });
      detailTrendIdeaInput?.focus();
      return;
    }
    setButtonBusy(detailTrendIdeaSaveBtn, true, "保存中…");
    if (detailTrendIdeaCancelBtn) detailTrendIdeaCancelBtn.disabled = true;
    setInlineFeedback(form, "正在更新板块想法…", { tone: "pending" });
    try {
      const date_key = detailTrendIdeaDateSelect ? detailTrendIdeaDateSelect.value : item.trend_date_key;
      const tag_key = detailTrendIdeaTagSelect ? detailTrendIdeaTagSelect.value : item.tag_key;
      const direction = detailTrendIdeaDirectionSelect ? detailTrendIdeaDirectionSelect.value : item.direction;
      const result = await updateTrendNote(item.trend_note_id, {
        note: detailTrendIdeaInput.value,
        date_key,
        tag_key,
        direction,
      });
      const moved = date_key !== item.trend_date_key || tag_key !== item.tag_key || direction !== item.direction;
      const updated = {
        ...item,
        note: result.trend_note.note,
        note_preview: result.trend_note.note,
        trend_date_key: result.date,
        tag_key: result.tag_key,
        tag_label: result.tag,
        direction: result.direction,
        updated_at: result.trend_note.updated_at,
      };
      state.selectedTrendIdea = updated;
      if (moved) {
        await reloadIdeasAndSelect(item.idea_id);
      } else {
        updateIdeaRow(updated);
        renderTrendIdeaDetail(updated);
      }
    } catch (error) {
      setInlineFeedback(
        form,
        `更新板块想法失败：${friendlyActionError(error, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailTrendIdeaSaveBtn, false);
      if (detailTrendIdeaCancelBtn) detailTrendIdeaCancelBtn.disabled = false;
    }
  });
}

if (detailTrendIdeaDeleteBtn) {
  detailTrendIdeaDeleteBtn.addEventListener("click", async () => {
    const item = state.selectedTrendIdea;
    if (!item) return;
    const ok = window.confirm(`删除这条板块想法？\n\n${item.tag_label || ""} · ${ideaDirectionLabel(item)} · ${item.trend_date_key || ""}`);
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
      setHint(state.total > 0 ? "板块想法已删除" : "还没有想法，去新闻详情或板块里记录第一条。");
    } finally {
      detailTrendIdeaDeleteBtn.disabled = false;
    }
  });
}

if (ideaNewBtn) {
  ideaNewBtn.addEventListener("click", () => {
    openStandaloneIdeaNewView();
  });
}

if (detailStandaloneIdeaNewSaveBtn) {
  detailStandaloneIdeaNewSaveBtn.addEventListener("click", async () => {
    const form = detailStandaloneIdeaNewSaveBtn.closest(".detail-note-editor");
    clearInlineFeedback(form);
    const note = (detailStandaloneIdeaNewInput?.value || "").trim();
    if (!note) {
      setInlineFeedback(form, "请输入想法内容再保存。", { tone: "failed" });
      detailStandaloneIdeaNewInput?.focus();
      return;
    }
    setButtonBusy(detailStandaloneIdeaNewSaveBtn, true, "保存中…");
    if (detailStandaloneIdeaNewCancelBtn) detailStandaloneIdeaNewCancelBtn.disabled = true;
    setInlineFeedback(form, "正在保存独立想法…", { tone: "pending" });
    let writeConfirmed = false;
    try {
      const idea = await createStandaloneIdea(note);
      writeConfirmed = true;
      await loadFirstPage();
      state.selectedIdeaId = idea.idea_id;
      syncIdeaRowSelection();
      renderStandaloneIdeaDetail(idea);
      setHint("独立想法已保存");
    } catch (err) {
      setInlineFeedback(
        form,
        writeConfirmed
          ? `独立想法已保存，但刷新列表失败：${friendlyActionError(err, "请返回想法列表重新打开，不要重复提交。")}`
          : `保存独立想法失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailStandaloneIdeaNewSaveBtn, false);
      if (writeConfirmed) {
        detailStandaloneIdeaNewSaveBtn.textContent = "已保存";
        detailStandaloneIdeaNewSaveBtn.disabled = true;
      }
      if (detailStandaloneIdeaNewCancelBtn) detailStandaloneIdeaNewCancelBtn.disabled = false;
    }
  });
}

if (detailStandaloneIdeaNewCancelBtn) {
  detailStandaloneIdeaNewCancelBtn.addEventListener("click", () => {
    clearStandaloneIdeaDetailState();
    renderDetailEmpty();
    updateWorkspaceLayout();
  });
}

if (detailStandaloneIdeaEditBtn) {
  detailStandaloneIdeaEditBtn.addEventListener("click", () => {
    if (!state.selectedStandaloneIdea) return;
    detailStandaloneIdeaInput.value = state.selectedStandaloneIdea.note || "";
    setStandaloneIdeaEditorOpen(true);
    clearInlineFeedback(detailStandaloneIdeaEditor);
    detailStandaloneIdeaInput.focus();
  });
}

if (detailStandaloneIdeaCancelBtn) {
  detailStandaloneIdeaCancelBtn.addEventListener("click", () => {
    if (!state.selectedStandaloneIdea) return;
    detailStandaloneIdeaInput.value = state.selectedStandaloneIdea.note || "";
    setStandaloneIdeaEditorOpen(false);
  });
}

if (detailStandaloneIdeaSaveBtn) {
  detailStandaloneIdeaSaveBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailStandaloneIdeaEditor);
    const item = state.selectedStandaloneIdea;
    if (!item) return;
    const note = (detailStandaloneIdeaInput?.value || "").trim();
    if (!note) {
      setInlineFeedback(detailStandaloneIdeaEditor, "想法内容不能为空。", { tone: "failed" });
      detailStandaloneIdeaInput?.focus();
      return;
    }
    setButtonBusy(detailStandaloneIdeaSaveBtn, true, "保存中…");
    if (detailStandaloneIdeaCancelBtn) detailStandaloneIdeaCancelBtn.disabled = true;
    setInlineFeedback(detailStandaloneIdeaEditor, "正在更新独立想法…", { tone: "pending" });
    try {
      const updated = await updateStandaloneIdea(item.standalone_id, note);
      state.selectedStandaloneIdea = updated;
      updateIdeaRow(updated);
      renderStandaloneIdeaDetail(updated);
      setHint("独立想法已更新");
    } catch (err) {
      setInlineFeedback(
        detailStandaloneIdeaEditor,
        `更新独立想法失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(detailStandaloneIdeaSaveBtn, false);
      if (detailStandaloneIdeaCancelBtn) detailStandaloneIdeaCancelBtn.disabled = false;
    }
  });
}

if (detailStandaloneIdeaDeleteBtn) {
  detailStandaloneIdeaDeleteBtn.addEventListener("click", async () => {
    const item = state.selectedStandaloneIdea;
    if (!item) return;
    const ok = window.confirm("删除这条独立想法？");
    if (!ok) return;
    detailStandaloneIdeaDeleteBtn.disabled = true;
    try {
      await deleteStandaloneIdea(item.standalone_id);
      removeIdeaRow(item.idea_id);
      updateIdeaDateCountOnDelete(item);
      state.total = Math.max(0, Number(state.total || 0) - 1);
      state.pages = Math.max(1, Math.ceil(state.total / state.per));
      state.page = Math.min(state.page, state.pages);
      state.selectedIdeaId = "";
      syncIdeaRowSelection();
      renderMeta();
      clearStandaloneIdeaDetailState();
      renderDetailEmpty();
      updateWorkspaceLayout();
      setHint(state.total > 0 ? "独立想法已删除" : "还没有想法，去新闻详情或板块里记录第一条。");
    } finally {
      detailStandaloneIdeaDeleteBtn.disabled = false;
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

newsList.addEventListener("keydown", handleFeedKeyboardKeydown);

document.addEventListener("click", (event) => {
  if (!feedKeyboardMode) return;
  const target = event.target;
  const insideFeedColumn = !!(target && typeof target.closest === "function" && target.closest(".feed-column"));
  if (!insideFeedColumn) exitFeedKeyboardMode();
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
  scheduleFeedControlsOverflowSync();
  scheduleDetailToolbarOverflowSync();
  if (feedKeyboardMode && !isFeedKeyboardDesktopEnabled()) exitFeedKeyboardMode();
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.settingsOpen) {
    closeSettingsOverlay();
  }
});

setupLoadObserver();
setupFeedControlsOverflowCue();
setupDetailToolbarOverflowCue();
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
if (detailEmptyIcon) {
  detailEmptyIcon.innerHTML = iconSvg("newspaper");
}
if (searchPageSubmitBtn) {
  searchPageSubmitBtn.textContent = "搜索";
  searchPageSubmitBtn.setAttribute("aria-label", "执行搜索");
}
syncSearchPageControls();
updateFilterButtons();
updateBatchActionButton();
updateRefreshButton();
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

// ===== Review: "加入复盘" create flow =====

function openReviewCreateFromArticle() {
  const item = state.selectedId ? state.itemsById.get(state.selectedId) : null;
  if (!item) {
    setHint("请先选择一条新闻想法");
    return;
  }
  const cached = item.url ? state.detailCacheByUrl.get(item.url) : null;
  const noteText = normalizedDetailNote(cached);
  openReviewCreateForm({
    source_type: "article_note",
    source_key: item.url || "",
    source_note: noteText || item.summary || "",
    source_tag_label: "",
    source_meta: `${item.source || ""} · ${item.published_at || ""}`,
    news_list: [{ title: item.title || "", summary: item.summary || "", url: item.url || "" }],
  });
}

function openReviewCreateFromTrendIdea() {
  const item = state.selectedTrendIdea;
  if (!item) {
    setHint("请先选择一条板块想法");
    return;
  }
  openReviewCreateForm({
    source_type: "market_trend_note",
    source_key: String(item.trend_note_id || ""),
    source_note: item.note || "",
    source_tag_label: item.tag_label || "",
    source_meta: `${item.tag_label || ""} · ${item.trend_date_key || ""}`,
    news_list: [],
  });
}

function openReviewCreateFromStandaloneIdea() {
  const item = state.selectedStandaloneIdea;
  if (!item) {
    setHint("请先选择一条独立想法");
    return;
  }
  openReviewCreateForm({
    source_type: "standalone_idea",
    source_key: String(item.standalone_id || ""),
    source_note: item.note || "",
    source_tag_label: "",
    source_meta: `创建 ${item.created_at || "-"}`,
    news_list: [],
  });
}

function openReviewCreateForm(ctx) {
  state.pendingReviewSource = ctx;
  // Save source context for cancel-to-restore
  state.pendingReviewSource._prevCollection = state.collection;
  state.pendingReviewSource._prevSelectedId = state.selectedId;
  state.pendingReviewSource._prevSelectedTrendIdea = state.selectedTrendIdea;
  state.pendingReviewSource._prevSelectedStandaloneIdea = state.selectedStandaloneIdea;
  hideAllDetailPanelsForReview();
  closeAllReviewPanels();
  detailReviewCreateBody.classList.remove("hidden");
  clearInlineFeedback(reviewCreateSaveBtn?.closest(".detail-note-editor"));
  if (reviewCreateSaveBtn) {
    reviewCreateSaveBtn.disabled = false;
    reviewCreateSaveBtn.textContent = "创建复盘";
    reviewCreateSaveBtn.removeAttribute("aria-busy");
    delete reviewCreateSaveBtn.dataset.idleLabel;
  }
  reviewCreateSourceNote.textContent = ctx.source_note || "";
  reviewCreateSourceMeta.textContent = ctx.source_meta || "";
  if (reviewCreateJudgment) reviewCreateJudgment.value = "";
  if (reviewCreateCriteria) reviewCreateCriteria.value = "";
  const today = new Date();
  const defaultDate = new Date(today);
  defaultDate.setMonth(today.getMonth() + 1);
  if (reviewCreateDate) reviewCreateDate.value = defaultDate.toISOString().slice(0, 10);
  if (reviewCreateAddReminder) reviewCreateAddReminder.checked = false;
  if (reviewCreateRemindAt) {
    reviewCreateRemindAt.value = "";
    reviewCreateRemindAt.classList.add("hidden");
  }
  state.reviewReminderUserTouched = false;
  openDetailOnMobile();
  updateWorkspaceLayout();
}

if (detailReviewAddBtn) {
  detailReviewAddBtn.addEventListener("click", openReviewCreateFromArticle);
}
if (detailTrendIdeaReviewBtn) {
  detailTrendIdeaReviewBtn.addEventListener("click", openReviewCreateFromTrendIdea);
}
if (detailStandaloneIdeaReviewBtn) {
  detailStandaloneIdeaReviewBtn.addEventListener("click", openReviewCreateFromStandaloneIdea);
}

if (reviewCreateAddReminder) {
  reviewCreateAddReminder.addEventListener("change", () => {
    if (!reviewCreateRemindAt) return;
    const checked = reviewCreateAddReminder.checked;
    reviewCreateRemindAt.classList.toggle("hidden", !checked);
    if (checked) {
      const planDate = reviewCreateDate ? reviewCreateDate.value.trim() : "";
      if (planDate && !state.reviewReminderUserTouched) {
        reviewCreateRemindAt.value = `${planDate}T09:00`;
      }
    }
  });
}

if (reviewCreateDate) {
  reviewCreateDate.addEventListener("change", () => {
    if (!reviewCreateRemindAt || !reviewCreateAddReminder) return;
    if (reviewCreateAddReminder.checked && !state.reviewReminderUserTouched) {
      const planDate = reviewCreateDate.value.trim();
      if (planDate) {
        reviewCreateRemindAt.value = `${planDate}T09:00`;
      }
    }
  });
}

if (reviewCreateRemindAt) {
  reviewCreateRemindAt.addEventListener("input", () => {
    state.reviewReminderUserTouched = true;
  });
  reviewCreateRemindAt.addEventListener("change", () => {
    state.reviewReminderUserTouched = true;
  });
}

if (reviewCreateCancelBtn) {
  reviewCreateCancelBtn.addEventListener("click", () => {
    const ctx = state.pendingReviewSource;
    closeAllReviewPanels();
    state.pendingReviewSource = null;
    if (ctx && ctx._prevSelectedId) {
      const item = state.itemsById.get(ctx._prevSelectedId);
      if (item) { renderDetail(item); return; }
    }
    if (ctx && ctx._prevSelectedTrendIdea) {
      renderTrendIdeaDetail(ctx._prevSelectedTrendIdea);
      return;
    }
    if (ctx && ctx._prevSelectedStandaloneIdea) {
      renderStandaloneIdeaDetail(ctx._prevSelectedStandaloneIdea);
      return;
    }
    renderDetailEmpty();
  });
}

if (reviewCreateSaveBtn) {
  reviewCreateSaveBtn.addEventListener("click", async () => {
    const form = reviewCreateSaveBtn.closest(".detail-note-editor");
    clearInlineFeedback(form);
    const ctx = state.pendingReviewSource;
    if (!ctx) return;
    const judgment = reviewCreateJudgment ? reviewCreateJudgment.value.trim() : "";
    const criteria = reviewCreateCriteria ? reviewCreateCriteria.value.trim() : "";
    const planDate = reviewCreateDate ? reviewCreateDate.value.trim() : "";
    const addReminder = reviewCreateAddReminder ? reviewCreateAddReminder.checked : false;
    let remindAt = "";
    if (addReminder) {
      remindAt = reviewCreateRemindAt ? reviewCreateRemindAt.value.trim() : "";
      if (!remindAt) {
        remindAt = `${planDate}T09:00`;
      }
    }
    if (!judgment) {
      setInlineFeedback(form, "请填写验证判断。", { tone: "failed" });
      reviewCreateJudgment?.focus();
      return;
    }
    if (!planDate) {
      setInlineFeedback(form, "请选择计划验证日期。", { tone: "failed" });
      reviewCreateDate?.focus();
      return;
    }
    setButtonBusy(reviewCreateSaveBtn, true, "创建中…");
    setInlineFeedback(form, "正在创建复盘，当前输入会保留到操作完成。", { tone: "pending" });
    let writeConfirmed = false;
    try {
      const review = await createReview({
        source_type: ctx.source_type,
        source_key: ctx.source_key,
        judgment,
        criteria,
        plan_review_date: planDate,
        add_reminder: addReminder,
        remind_at: remindAt,
      });
      writeConfirmed = true;
      state.pendingReviewSource = null;
      setHint("复盘已创建");
      state.collection = "reviews";
      state.reviewFilter = "all";
      await loadFirstPage();
      state.selectedReviewId = review.id;
      syncReviewRowSelection();
      await openReviewCard(review);
    } catch (err) {
      setInlineFeedback(
        form,
        writeConfirmed
          ? `复盘已创建，但刷新详情失败：${friendlyActionError(err, "请进入复盘列表重新打开，不要重复提交。")}`
          : `创建复盘失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewCreateSaveBtn, false);
      if (writeConfirmed) {
        reviewCreateSaveBtn.textContent = "已创建";
        reviewCreateSaveBtn.disabled = true;
      }
    }
  });
}

// ===== Review: progress form =====

if (detailReviewProgressBtn) {
  detailReviewProgressBtn.addEventListener("click", () => {
    if (reviewProgressText) reviewProgressText.value = "";
    if (reviewProgressDate) reviewProgressDate.value = new Date().toISOString().slice(0, 10);
    showReviewForm(detailReviewProgressForm, reviewProgressText);
  });
}

if (reviewProgressCancelBtn) {
  reviewProgressCancelBtn.addEventListener("click", () => {
    if (detailReviewProgressForm) detailReviewProgressForm.classList.add("hidden");
  });
}

if (reviewProgressSaveBtn) {
  reviewProgressSaveBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailReviewProgressForm);
    const review = state.currentReview;
    if (!review) return;
    const text = reviewProgressText ? reviewProgressText.value.trim() : "";
    const date = reviewProgressDate ? reviewProgressDate.value.trim() : "";
    if (!text) {
      setInlineFeedback(detailReviewProgressForm, "请填写进展内容。", { tone: "failed" });
      reviewProgressText?.focus();
      return;
    }
    if (!date) {
      setInlineFeedback(detailReviewProgressForm, "请选择进展发生日期。", { tone: "failed" });
      reviewProgressDate?.focus();
      return;
    }
    setButtonBusy(reviewProgressSaveBtn, true, "保存中…");
    setInlineFeedback(detailReviewProgressForm, "正在保存进展…", { tone: "pending" });
    try {
      const updated = await reviewProgress(review.id, { event_text: text, event_date: date });
      renderReviewDetail(updated);
      setHint("进展已记录");
    } catch (err) {
      setInlineFeedback(
        detailReviewProgressForm,
        `记录进展失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewProgressSaveBtn, false);
    }
  });
}

// ===== Review: revise form =====

if (detailReviewReviseBtn) {
  detailReviewReviseBtn.addEventListener("click", () => {
    const review = state.currentReview;
    if (review) {
      if (reviewReviseJudgment) reviewReviseJudgment.value = review.current_judgment || "";
      if (reviewReviseCriteria) reviewReviseCriteria.value = review.current_criteria || "";
    }
    if (reviewReviseReason) reviewReviseReason.value = "";
    if (reviewReviseDate) reviewReviseDate.value = new Date().toISOString().slice(0, 10);
    showReviewForm(detailReviewReviseForm, reviewReviseJudgment);
  });
}

if (reviewReviseCancelBtn) {
  reviewReviseCancelBtn.addEventListener("click", () => {
    if (detailReviewReviseForm) detailReviewReviseForm.classList.add("hidden");
  });
}

if (reviewReviseSaveBtn) {
  reviewReviseSaveBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailReviewReviseForm);
    const review = state.currentReview;
    if (!review) return;
    const judgment = reviewReviseJudgment ? reviewReviseJudgment.value.trim() : "";
    const criteria = reviewReviseCriteria ? reviewReviseCriteria.value.trim() : "";
    const reason = reviewReviseReason ? reviewReviseReason.value.trim() : "";
    const date = reviewReviseDate ? reviewReviseDate.value.trim() : "";
    if (!judgment) {
      setInlineFeedback(detailReviewReviseForm, "请填写新判断。", { tone: "failed" });
      reviewReviseJudgment?.focus();
      return;
    }
    if (!reason) {
      setInlineFeedback(detailReviewReviseForm, "请填写修正原因。", { tone: "failed" });
      reviewReviseReason?.focus();
      return;
    }
    if (!date) {
      setInlineFeedback(detailReviewReviseForm, "请选择判断修正日期。", { tone: "failed" });
      reviewReviseDate?.focus();
      return;
    }
    setButtonBusy(reviewReviseSaveBtn, true, "保存中…");
    setInlineFeedback(detailReviewReviseForm, "正在保存修正后的判断…", { tone: "pending" });
    try {
      const updated = await reviewRevise(review.id, { judgment, criteria, revision_reason: reason, event_date: date });
      renderReviewDetail(updated);
      setHint("判断已修正");
    } catch (err) {
      setInlineFeedback(
        detailReviewReviseForm,
        `修正判断失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewReviseSaveBtn, false);
    }
  });
}

// ===== Review: complete form =====

if (detailReviewCompleteBtn) {
  detailReviewCompleteBtn.addEventListener("click", () => {
    const review = state.currentReview;
    if (review && reviewCompleteVersions) {
      reviewCompleteVersions.innerHTML = "";
      (review.versions || []).forEach((v) => {
        const card = document.createElement("div");
        card.className = "review-complete-version-card";
        const header = document.createElement("div");
        header.className = "review-complete-version-header";
        const badge = document.createElement("span");
        badge.className = "note-badge review-version-badge";
        badge.textContent = `V${v.version_no}`;
        header.appendChild(badge);
        const time = document.createElement("span");
        time.className = "review-timeline-time";
        time.textContent = v.created_at ? v.created_at.slice(0, 16).replace("T", " ") : "";
        header.appendChild(time);
        card.appendChild(header);
        const j = document.createElement("div");
        j.className = "review-timeline-judgment";
        j.textContent = v.judgment;
        card.appendChild(j);
        if (v.criteria) {
          const c = document.createElement("div");
          c.className = "review-timeline-criteria";
          c.textContent = `成立标准：${v.criteria}`;
          card.appendChild(c);
        }
        if (v.revision_reason) {
          const r = document.createElement("div");
          r.className = "review-timeline-reason";
          r.textContent = `修正原因：${v.revision_reason}`;
          card.appendChild(r);
        }
        reviewCompleteVersions.appendChild(card);
      });
    }
    if (reviewCompleteActual) reviewCompleteActual.value = review ? review.actual_text || "" : "";
    if (reviewCompleteResult) reviewCompleteResult.value = "";
    if (reviewCompleteBias) reviewCompleteBias.value = review ? review.bias_text || "" : "";
    if (reviewCompleteExperience) reviewCompleteExperience.value = "";
    if (reviewContinueObserveSection) reviewContinueObserveSection.classList.add("hidden");
    showReviewForm(detailReviewCompleteForm, reviewCompleteActual);
  });
}

if (reviewCompleteResult) {
  reviewCompleteResult.addEventListener("change", () => {
    if (reviewContinueObserveSection) {
      reviewContinueObserveSection.classList.toggle("hidden", reviewCompleteResult.value !== "inconclusive");
    }
  });
}

if (reviewCompleteCancelBtn) {
  reviewCompleteCancelBtn.addEventListener("click", () => {
    if (detailReviewCompleteForm) detailReviewCompleteForm.classList.add("hidden");
  });
}

if (reviewCompleteSaveBtn) {
  reviewCompleteSaveBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailReviewCompleteForm);
    const review = state.currentReview;
    if (!review) return;
    const result = reviewCompleteResult ? reviewCompleteResult.value.trim() : "";
    const actual = reviewCompleteActual ? reviewCompleteActual.value.trim() : "";
    const bias = reviewCompleteBias ? reviewCompleteBias.value.trim() : "";
    const experience = reviewCompleteExperience ? reviewCompleteExperience.value.trim() : "";
    if (!result) {
      setInlineFeedback(detailReviewCompleteForm, "请选择复盘结果。", { tone: "failed" });
      reviewCompleteResult?.focus();
      return;
    }
    if (!experience) {
      setInlineFeedback(detailReviewCompleteForm, "请填写一条可复用的经验。", { tone: "failed" });
      reviewCompleteExperience?.focus();
      return;
    }
    setButtonBusy(reviewCompleteSaveBtn, true, "完成中…");
    setInlineFeedback(detailReviewCompleteForm, "正在完成复盘…", { tone: "pending" });
    try {
      const updated = await reviewComplete(review.id, { result, actual_text: actual, bias_text: bias, experience });
      renderReviewDetail(updated);
      setHint("复盘已完成");
    } catch (err) {
      setInlineFeedback(
        detailReviewCompleteForm,
        `完成复盘失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewCompleteSaveBtn, false);
    }
  });
}

if (reviewContinueSaveBtn) {
  reviewContinueSaveBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailReviewCompleteForm);
    const review = state.currentReview;
    if (!review) return;
    const newDate = reviewContinueDate ? reviewContinueDate.value.trim() : "";
    if (!newDate) {
      setInlineFeedback(detailReviewCompleteForm, "请选择新的验证日期。", { tone: "failed" });
      reviewContinueDate?.focus();
      return;
    }
    setButtonBusy(reviewContinueSaveBtn, true, "保存中…");
    setInlineFeedback(detailReviewCompleteForm, "正在延长观察周期…", { tone: "pending" });
    try {
      const updated = await reviewContinueObserving(review.id, { new_review_date: newDate });
      renderReviewDetail(updated);
      setHint("已继续观察");
    } catch (err) {
      setInlineFeedback(
        detailReviewCompleteForm,
        `继续观察失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewContinueSaveBtn, false);
    }
  });
}

if (reviewContinueDoneBtn) {
  reviewContinueDoneBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailReviewCompleteForm);
    const review = state.currentReview;
    if (!review) return;
    const actual = reviewCompleteActual ? reviewCompleteActual.value.trim() : "";
    const bias = reviewCompleteBias ? reviewCompleteBias.value.trim() : "";
    const experience = reviewCompleteExperience ? reviewCompleteExperience.value.trim() : "";
    if (!experience) {
      setInlineFeedback(detailReviewCompleteForm, "请填写一条可复用的经验。", { tone: "failed" });
      reviewCompleteExperience?.focus();
      return;
    }
    setButtonBusy(reviewContinueDoneBtn, true, "结束中…");
    setInlineFeedback(detailReviewCompleteForm, "正在以“暂不可判断”结束复盘…", { tone: "pending" });
    try {
      const updated = await reviewComplete(review.id, { result: "inconclusive", actual_text: actual, bias_text: bias, experience });
      renderReviewDetail(updated);
      setHint("复盘已结束（暂不可判断）");
    } catch (err) {
      setInlineFeedback(
        detailReviewCompleteForm,
        `结束复盘失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewContinueDoneBtn, false);
    }
  });
}

// ===== Review: retrack form =====

if (detailReviewRetrackBtn) {
  detailReviewRetrackBtn.addEventListener("click", () => {
    const review = state.currentReview;
    if (review) {
      if (reviewRetrackJudgment) reviewRetrackJudgment.value = review.current_judgment || "";
      if (reviewRetrackCriteria) reviewRetrackCriteria.value = review.current_criteria || "";
    }
    const today = new Date();
    const defaultDate = new Date(today);
    defaultDate.setMonth(today.getMonth() + 1);
    if (reviewRetrackDate) reviewRetrackDate.value = defaultDate.toISOString().slice(0, 10);
    showReviewForm(detailReviewRetrackForm, reviewRetrackJudgment);
  });
}

if (reviewRetrackCancelBtn) {
  reviewRetrackCancelBtn.addEventListener("click", () => {
    if (detailReviewRetrackForm) detailReviewRetrackForm.classList.add("hidden");
  });
}

if (reviewRetrackSaveBtn) {
  reviewRetrackSaveBtn.addEventListener("click", async () => {
    clearInlineFeedback(detailReviewRetrackForm);
    const review = state.currentReview;
    if (!review) return;
    const judgment = reviewRetrackJudgment ? reviewRetrackJudgment.value.trim() : "";
    const criteria = reviewRetrackCriteria ? reviewRetrackCriteria.value.trim() : "";
    const date = reviewRetrackDate ? reviewRetrackDate.value.trim() : "";
    if (!judgment) {
      setInlineFeedback(detailReviewRetrackForm, "请填写新判断。", { tone: "failed" });
      reviewRetrackJudgment?.focus();
      return;
    }
    if (!date) {
      setInlineFeedback(detailReviewRetrackForm, "请选择计划验证日期。", { tone: "failed" });
      reviewRetrackDate?.focus();
      return;
    }
    setButtonBusy(reviewRetrackSaveBtn, true, "创建中…");
    setInlineFeedback(detailReviewRetrackForm, "正在创建新的复盘链…", { tone: "pending" });
    try {
      const updated = await reviewRetrack(review.id, { judgment, criteria, plan_review_date: date });
      state.selectedReviewId = updated.id;
      await loadFirstPage();
      await openReviewCard(updated);
      setHint("已派生新复盘链");
    } catch (err) {
      setInlineFeedback(
        detailReviewRetrackForm,
        `再次跟踪失败：${friendlyActionError(err, "当前输入已保留，请稍后重试。")}`,
        { tone: "failed" },
      );
    } finally {
      setButtonBusy(reviewRetrackSaveBtn, false);
    }
  });
}
