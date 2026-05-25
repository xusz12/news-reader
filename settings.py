from __future__ import annotations

import os
from pathlib import Path


DEFAULT_DAILY_NEWS_DIR = Path(
    "/Users/x/Library/Mobile Documents/iCloud~md~obsidian/Documents/DailyNews"
)
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "news_index.sqlite3"


def resolve_daily_news_dir() -> Path:
    raw = os.environ.get("NEWS_READER_DAILY_NEWS_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_DAILY_NEWS_DIR


def resolve_db_path() -> Path:
    raw = os.environ.get("NEWS_READER_DB_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_DB_PATH
