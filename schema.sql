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

CREATE TABLE IF NOT EXISTS market_tag_deleted_keys (
  key TEXT PRIMARY KEY,
  deleted_at TEXT NOT NULL
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
