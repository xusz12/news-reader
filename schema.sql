PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_files (
  path TEXT PRIMARY KEY,
  mtime REAL NOT NULL,
  size INTEGER NOT NULL,
  last_scanned_at TEXT NOT NULL,
  item_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  source_file TEXT NOT NULL,
  item_order INTEGER NOT NULL,
  published_at TEXT NOT NULL,
  date TEXT NOT NULL,
  time TEXT,
  source TEXT,
  source_type TEXT,
  source_name TEXT,
  title TEXT NOT NULL,
  summary TEXT,
  url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source ON items(source);
CREATE INDEX IF NOT EXISTS idx_items_source_type ON items(source_type);

CREATE TABLE IF NOT EXISTS item_state (
  item_id TEXT PRIMARY KEY,
  bookmarked INTEGER DEFAULT 0,
  skipped INTEGER DEFAULT 0,
  read_at TEXT,
  important_at TEXT,
  read_later_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS detail_jobs (
  url TEXT PRIMARY KEY,
  item_id TEXT,
  source TEXT,
  status TEXT NOT NULL,
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  queued_at TEXT,
  started_at TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_detail_jobs_status ON detail_jobs(status);

CREATE TABLE IF NOT EXISTS article_details (
  url TEXT PRIMARY KEY,
  source TEXT,
  title TEXT,
  author TEXT,
  published_at TEXT,
  content TEXT,
  content_length INTEGER,
  raw_json TEXT,
  fetched_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_jobs (
  url TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  attempts INTEGER DEFAULT 0,
  last_error TEXT,
  queued_at TEXT,
  started_at TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_jobs_status ON ai_jobs(status);

CREATE TABLE IF NOT EXISTS article_ai (
  url TEXT PRIMARY KEY,
  model TEXT,
  key_points_zh TEXT,
  conclusion_zh TEXT,
  body_zh TEXT,
  raw_json TEXT,
  generated_at TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_checkpoints (
  scope TEXT PRIMARY KEY,
  item_id TEXT,
  url TEXT,
  title TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_notes (
  url TEXT PRIMARY KEY,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_market_tags (
  url TEXT NOT NULL,
  tag TEXT NOT NULL,
  direction TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (url, tag)
);

CREATE TABLE IF NOT EXISTS market_tag_definitions (
  key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_trend_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date_key TEXT NOT NULL,
  tag TEXT NOT NULL,
  direction TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendation_evals (
  item_id TEXT NOT NULL,
  status TEXT NOT NULL,
  features_json TEXT,
  score INTEGER,
  recommended INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  prompt_version TEXT,
  schema_version TEXT,
  weights_version TEXT,
  model TEXT,
  evaluated_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (item_id, schema_version)
);

CREATE INDEX IF NOT EXISTS idx_recommendation_evals_status ON recommendation_evals(status);
CREATE INDEX IF NOT EXISTS idx_recommendation_evals_recommended ON recommendation_evals(schema_version, recommended, status);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  source_context TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recommendation_feedback_item ON recommendation_feedback(item_id, event_type, source_context);

CREATE TABLE IF NOT EXISTS recommendation_categories (
  key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT NOT NULL,
  positive_count INTEGER NOT NULL DEFAULT 0,
  weight INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  version TEXT NOT NULL,
  seed_item_ids_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recommendation_categories_active ON recommendation_categories(active, version);

CREATE TABLE IF NOT EXISTS recommendation_meta (
  key TEXT PRIMARY KEY,
  value_text TEXT,
  updated_at TEXT NOT NULL
);
