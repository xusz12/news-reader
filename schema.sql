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
  updated_at TEXT NOT NULL
);
