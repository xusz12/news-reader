from __future__ import annotations

import math
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_from_directory

from daily_briefings import list_daily_briefing_files, parse_daily_briefing_date, parse_daily_briefing_file
from llm_client import (
    LLMClientError,
    generate_codex_fallback_translation,
    generate_article_ai,
    generate_body_translation_only,
    generate_market_tag_summary,
    generate_twitter_comments_summary,
    generate_tracked_topic_rule_draft,
    generate_tracked_topic_daily_summary,
    resolve_translation_default_model,
)
from parser import parse_daily_errors
from scanner import apply_schema, list_daily_files, reindex
from secret_store import SecretStoreError, delete_secret, has_secret, read_secret, write_secret
from settings import (
    default_app_settings,
    load_app_settings,
    resolve_daily_briefing_dir,
    resolve_daily_news_dir,
    resolve_db_path,
    save_app_settings,
)


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
STATIC_DIR = BASE_DIR / "static"
DAILY_NEWS_DIR = resolve_daily_news_dir()
DAILY_BRIEFING_DIR = resolve_daily_briefing_dir()
DB_PATH = resolve_db_path()
README_PATH = BASE_DIR / "README.md"


def resolve_media_cache_dir() -> Path:
    env = os.environ.get("NEWS_READER_MEDIA_CACHE_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return DB_PATH.parent / "media-cache"


MEDIA_CACHE_DIR = resolve_media_cache_dir()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

DETAIL_LOCK = threading.Lock()
CODEX_CHAT_LOCKS: dict[str, threading.Lock] = {}
CODEX_CHAT_LOCKS_GUARD = threading.Lock()
WORKER_THREAD: threading.Thread | None = None
WORKER_STOP = threading.Event()

DETAIL_COMMAND_ROUTES = {
    "reuters.com": {"source": "Reuters", "command": ["opencli", "reuters", "article-detail"], "timeout": 45},
    "bloomberg.com": {"source": "Bloomberg", "command": ["opencli", "bloomberg", "news"], "timeout": 90},
    "techcrunch.com": {"source": "TechCrunch", "command": ["opencli", "TechcrunchPublic", "article"], "timeout": 45},
    "arstechnica.com": {"source": "Ars Technica", "command": ["opencli", "ArsPublic", "article"], "timeout": 45},
}
TWITTER_THREAD_COMMAND = ["opencli", "twitter", "thread"]
TWITTER_ARTICLE_COMMAND = ["opencli", "twitter", "article"]
TWITTER_COMMENT_FETCH_LIMIT = 50
TWITTER_THREAD_TIMEOUT = 90
TWITTER_ARTICLE_TIMEOUT = 60

SOURCE_LABELS = {
    "all": "全部来源",
    "reuters": "Reuters",
    "bloomberg": "Bloomberg",
    "techcrunch": "TechCrunch",
    "ars": "Ars Technica",
    "x": "X",
}

DEFAULT_MARKET_TAG_CHOICES = [
    "存储",
    "电力",
    "房地产",
    "APPLE",
    "AI",
    "电子消费",
    "医疗",
    "国际形势",
    "稀土",
    "矿产",
    "新能源",
    "中国资产",
]
MARKET_DIRECTIONS = {"bullish", "bearish"}
REMINDER_STATUSES = {"active", "done", "dismissed"}

FEED_NEWS_ORDER_BY_SQL = """
COALESCE(NULLIF(items.date, ''), substr(items.published_at, 1, 10)) ASC,
items.published_at ASC,
items.id ASC
"""

NON_FEED_NEWS_ORDER_BY_SQL = """
COALESCE(NULLIF(items.date, ''), substr(items.published_at, 1, 10)) DESC,
items.published_at DESC,
items.id DESC
"""

ITEM_DATE_SQL = "COALESCE(NULLIF(items.date, ''), substr(items.published_at, 1, 10))"
NEWS_SORT_ORDERS = {"default", "reverse"}
IDEA_TYPE_FILTERS = {"all", "article", "trend"}
TRACKED_TOPIC_SCOPES = {"important", "all"}
TRACKED_BACKFILL_MODES = {"recent_important", "all_important", "all_news"}
TRACKED_MATCH_METHODS = {"keyword", "manual"}
TRACKED_DAILY_SUMMARY_STATUSES = {"success", "failed"}
MARKET_TAG_SUMMARY_STATUSES = {"success", "failed"}
TRACKED_DAILY_SUMMARY_VERSION = "v1.9.8.5"
TRACKED_RULE_DRAFT_VERSION = "v1.9.8.6"
MARKET_TAG_SUMMARY_VERSION = "v1.9.8.9"
TRACKED_RULE_FIELD_SCORES = {
    "title": {"strong": 8, "core": 4, "context": 2},
    "note": {"strong": 6, "core": 3, "context": 2},
    "summary": {"strong": 5, "core": 2, "context": 1},
    "content": {"strong": 2, "core": 1, "context": 1},
}
TRACKED_RULE_FIELD_WEIGHT_DEFAULTS = {
    "title": 1.0,
    "note": 1.0,
    "summary": 1.0,
    "content": 1.0,
}
TRACKED_RULE_TERM_SCORE_DEFAULTS = {
    "strong": 1.0,
    "core": 1.0,
    "context": 1.0,
    "exclude": 1.0,
}
TRACKED_DEFAULT_RULE_PARAM_KEYS = (
    "title_weight",
    "note_weight",
    "summary_weight",
    "content_weight",
    "strong_score",
    "core_score",
    "context_score",
    "exclude_penalty",
    "threshold",
)
TRACKED_RULE_FIELD_LABELS = {
    "title": "标题",
    "note": "笔记",
    "summary": "摘要",
    "content": "正文",
}
TRACKED_RULE_THRESHOLD_DEFAULT = 6
TRACKED_RULE_THRESHOLD_MIN = 1
TRACKED_RULE_THRESHOLD_MAX = 50
TRACKED_RULE_CANDIDATE_THRESHOLD_DEFAULT = 4
TRACKED_RULE_WEIGHT_MIN = 0
TRACKED_RULE_WEIGHT_MAX = 20
TRACKED_RULE_EXCLUDE_PENALTY_BASE = 100
TRACKED_DAILY_SUMMARY_TEXT_LIMIT = 12000
TRACKED_DAILY_SUMMARY_CONTENT_LIMIT = 4000
TRACKED_DAILY_SUMMARY_AI_BODY_LIMIT = 2000
TRACKED_DAILY_SUMMARY_NOTE_LIMIT = 800
TRACKED_DAILY_SUMMARY_SUMMARY_LIMIT = 800
TRACKED_DAILY_SUMMARY_MIN_CHARS = 120
TRACKED_DAILY_SUMMARY_MAX_CHARS = 600
TRACKED_RULE_DRAFT_THRESHOLD_MIN = 3
TRACKED_RULE_DRAFT_THRESHOLD_MAX = 20
MARKET_WORKBENCH_SUMMARY_RANGE_DAYS = 30
MARKET_WORKBENCH_SUMMARY_MAX_NEWS = 50
MARKET_WORKBENCH_SUMMARY_TEXT_LIMIT = 16000
MARKET_WORKBENCH_SUMMARY_SUMMARY_LIMIT = 800
MARKET_WORKBENCH_SUMMARY_NOTE_LIMIT = 1200
MARKET_WORKBENCH_SUMMARY_BODY_LIMIT = 2000
MARKET_WORKBENCH_CONTENT_FILTERS = {"all", "ideas", "bullish", "bearish"}
MARKET_PIN_NOTE_MAX_LEN = 5000
CHAT_ARCHIVE_SUMMARY_MAX_LEN = 200
RELEASE_NOTE_HEADING_RE = re.compile(r"^###\s+(?P<date>\d{4}-\d{2}-\d{2})\s+—\s+(?P<title>.+?)\s*$")
VERSION_RE = re.compile(r"\bv\d+(?:\.\d+){1,3}\b", re.IGNORECASE)
SECRET_PROVIDER_MAP = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
}
DEEPSEEK_MODEL_FALLBACKS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-chat",
    "deepseek-reasoner",
]
CODEX_MODEL_FALLBACKS = [
    "gpt-5.5",
    "gpt-5-codex",
    "gpt-5",
]
SETTINGS_MODEL_OPTION_LIMIT = 40
DEEPSEEK_MODELS_URL = "https://api.deepseek.com/models"


def news_order_by_sql(collection: str, sort_order: str = "default") -> str:
    ascending = collection in ("feed", "read_later")
    if sort_order == "reverse":
        ascending = not ascending
    direction = "ASC" if ascending else "DESC"
    return f"""
    {ITEM_DATE_SQL} {direction},
    items.published_at {direction},
    items.id {direction}
    """


def use_feed_unread_cursor_paging(collection: str, read_filter: str) -> bool:
    return collection == "feed" and read_filter == "unread"


def parse_news_sort_order(args) -> str:
    sort_order = (args.get("sort_order") or "default").strip().lower()
    if sort_order not in NEWS_SORT_ORDERS:
        raise ValueError("invalid_sort_order")
    return sort_order


def parse_idea_type_filter(args) -> str:
    idea_type = (args.get("type") or "all").strip().lower()
    if idea_type not in IDEA_TYPE_FILTERS:
        raise ValueError("invalid_idea_type")
    return idea_type


def parse_feed_unread_cursor(args) -> dict | None:
    cursor_date = (args.get("cursor_date") or "").strip()
    cursor_published_at = (args.get("cursor_published_at") or "").strip()
    cursor_id = (args.get("cursor_id") or "").strip()
    if not (cursor_date or cursor_published_at or cursor_id):
        return None
    if not (cursor_date and cursor_published_at and cursor_id):
        raise ValueError("invalid_cursor")
    return {
        "date_key": cursor_date,
        "published_at": cursor_published_at,
        "id": cursor_id,
    }


def build_feed_unread_cursor_clause(cursor: dict | None, ascending: bool) -> tuple[str, list]:
    if not cursor:
        return "", []
    op = ">" if ascending else "<"
    clause = f"""
    AND (
      {ITEM_DATE_SQL} {op} ? OR
      ({ITEM_DATE_SQL} = ? AND items.published_at {op} ?) OR
      ({ITEM_DATE_SQL} = ? AND items.published_at = ? AND items.id {op} ?)
    )
    """
    return clause, [
        cursor["date_key"],
        cursor["date_key"],
        cursor["published_at"],
        cursor["date_key"],
        cursor["published_at"],
        cursor["id"],
    ]


def _source_prefix(source: str | None) -> str:
    if not source:
        return ""
    return source.split("·", 1)[0].strip()


def derive_source_key(url: str | None, source_type: str | None, source: str | None) -> str:
    st = (source_type or "").strip().lower()
    if st == "twitter":
        return "x"

    host = (urlparse(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("x.com", "twitter.com"):
        return "x"
    if host.endswith("reuters.com"):
        return "reuters"
    if host.endswith("bloomberg.com"):
        return "bloomberg"
    if host.endswith("techcrunch.com"):
        return "techcrunch"
    if host.endswith("arstechnica.com"):
        return "ars"
    if host:
        return f"host:{host}"

    prefix = _source_prefix(source).lower()
    if prefix == "reuters":
        return "reuters"
    if prefix == "bloomberg":
        return "bloomberg"
    if prefix == "techcrunch":
        return "techcrunch"
    if prefix in ("ars technica", "ars"):
        return "ars"
    if prefix in ("x", "twitter"):
        return "x"
    if prefix:
        return f"name:{prefix}"
    return "unknown"


def source_label_for_key(key: str, source: str | None = None) -> str:
    if key in SOURCE_LABELS:
        return SOURCE_LABELS[key]
    if key.startswith("host:"):
        return key[5:]
    if key.startswith("name:"):
        return source or key[5:]
    return source or key


def build_source_filter_clause(source_filter: str) -> tuple[str, list[str]]:
    sf = (source_filter or "all").strip().lower()
    if sf in ("", "all"):
        return "", []
    if sf == "x":
        return "(items.source_type='twitter' OR lower(items.url) LIKE 'https://x.com/%' OR lower(items.url) LIKE 'https://www.x.com/%' OR lower(items.url) LIKE 'https://twitter.com/%' OR lower(items.url) LIKE 'https://www.twitter.com/%')", []
    if sf == "reuters":
        return "(lower(items.url) LIKE 'https://reuters.com/%' OR lower(items.url) LIKE 'https://www.reuters.com/%')", []
    if sf == "bloomberg":
        return "(lower(items.url) LIKE 'https://bloomberg.com/%' OR lower(items.url) LIKE 'https://www.bloomberg.com/%')", []
    if sf == "techcrunch":
        return "(lower(items.url) LIKE 'https://techcrunch.com/%' OR lower(items.url) LIKE 'https://www.techcrunch.com/%')", []
    if sf == "ars":
        return "(lower(items.url) LIKE 'https://arstechnica.com/%' OR lower(items.url) LIKE 'https://www.arstechnica.com/%')", []
    if sf.startswith("host:"):
        host = sf[5:]
        if host:
            return "(lower(items.url) LIKE ? OR lower(items.url) LIKE ?)", [f"https://{host}/%", f"https://www.{host}/%"]
    return "", []


def _build_news_where_clause(
    q: str,
    read_filter: str,
    collection: str,
    source_filter: str,
) -> tuple[str, list]:
    where = []
    args: list = []
    if q:
        where.append("(items.title LIKE ? OR items.summary LIKE ? OR items.source LIKE ?)")
        like = f"%{q}%"
        args.extend([like, like, like])
    if collection == "read_later":
        if read_filter == "unread":
            where.append("st.read_later_at IS NOT NULL")
        elif read_filter == "read":
            where.append("(ad.url IS NOT NULL AND st.read_later_at IS NULL)")
        else:
            where.append("(st.read_later_at IS NOT NULL OR ad.url IS NOT NULL)")
    else:
        if read_filter == "unread":
            where.append("st.read_at IS NULL")
        elif read_filter == "read":
            where.append("st.read_at IS NOT NULL")
    if collection == "important":
        where.append("st.important_at IS NOT NULL")
    elif collection == "favorites":
        where.append("st.favorite_at IS NOT NULL")
    elif collection == "notes":
        where.append("EXISTS (SELECT 1 FROM article_notes an WHERE an.url = items.url)")
    elif collection == "market_tags":
        where.append("EXISTS (SELECT 1 FROM article_market_tags mt WHERE mt.url = items.url)")
    source_clause, source_args = build_source_filter_clause(source_filter)
    if source_clause:
        where.append(source_clause)
        args.extend(source_args)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return where_sql, args


def _build_search_filter_clause(range_value: str, time_value: str) -> tuple[str, list]:
    where = []
    args: list = []

    if range_value == "important":
        where.append("st.important_at IS NOT NULL")
    elif range_value == "notes":
        where.append("EXISTS (SELECT 1 FROM article_notes an2 WHERE an2.url = items.url)")
    elif range_value == "market_tags":
        where.append("EXISTS (SELECT 1 FROM article_market_tags mt2 WHERE mt2.url = items.url)")
    elif range_value == "detail_ready":
        where.append("ad.url IS NOT NULL")

    if time_value == "today":
        where.append(f"{ITEM_DATE_SQL} = date('now', 'localtime')")
    elif time_value == "7d":
        where.append(f"{ITEM_DATE_SQL} >= date('now', 'localtime', '-6 day')")
    elif time_value == "30d":
        where.append(f"{ITEM_DATE_SQL} >= date('now', 'localtime', '-29 day')")

    where_sql = (" AND " + " AND ".join(where)) if where else ""
    return where_sql, args


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = db_conn()
    try:
        apply_schema(conn, SCHEMA_PATH)
        migrate_market_trend_notes(conn)
        seed_market_tag_definitions(conn)
        _cleanup_media_cache(conn)
        conn.commit()
    finally:
        conn.close()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_reminder_event_date(value: str) -> str:
    normalized = (value or "").strip()
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("invalid_event_date") from exc


def parse_reminder_remind_at(value: str) -> str:
    normalized = (value or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError("invalid_remind_at")


def reminder_is_due(remind_at: str | None, status: str | None) -> bool:
    return bool(status == "active" and remind_at and remind_at <= now_ts())


def build_note_preview(note_text: str | None, limit: int = 120) -> str:
    if not isinstance(note_text, str):
        return ""
    compact = " ".join(note_text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def normalize_keyword_list(value: object) -> list[str]:
    raw_values: list[str] = []
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                raw_values.append(entry)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    for entry in parsed:
                        if isinstance(entry, str):
                            raw_values.append(entry)
                else:
                    raw_values.extend(re.split(r"[\n,，]+", value))
            except Exception:
                raw_values.extend(re.split(r"[\n,，]+", value))
        else:
            raw_values.extend(re.split(r"[\n,，]+", value))

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        text = " ".join((raw or "").split()).strip()
        lowered = text.lower()
        if not text or lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def sanitize_tracked_rule_draft_terms(value: object, *, min_items: int = 0, max_items: int, max_len: int = 40) -> list[str]:
    normalized = normalize_keyword_list(value)
    cleaned: list[str] = []
    seen: set[str] = set()
    for text in normalized:
        if len(text) > max_len:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    if len(cleaned) < min_items:
        return cleaned
    return cleaned


def sanitize_tracked_rule_draft(payload: dict[str, object]) -> dict[str, object]:
    title = " ".join(str(payload.get("title") or "").split()).strip()
    if not title:
        raise ValueError("empty_title")
    if len(title) > 120:
        raise ValueError("title_too_long")

    strong_phrases = sanitize_tracked_rule_draft_terms(
        payload.get("strong_phrases"),
        max_items=12,
    )
    core_terms = sanitize_tracked_rule_draft_terms(
        payload.get("core_terms"),
        max_items=24,
    )
    context_terms = sanitize_tracked_rule_draft_terms(
        payload.get("context_terms"),
        max_items=32,
    )
    exclude_terms = sanitize_tracked_rule_draft_terms(
        payload.get("exclude_terms"),
        max_items=24,
    )
    if not strong_phrases and not core_terms:
        raise ValueError("invalid_rule_draft")

    try:
        threshold_value = payload.get("threshold")
        threshold = int(float(str(threshold_value).strip()))
    except Exception as exc:
        raise ValueError("invalid_tracked_threshold") from exc
    threshold = min(TRACKED_RULE_DRAFT_THRESHOLD_MAX, max(TRACKED_RULE_DRAFT_THRESHOLD_MIN, threshold))

    return {
        "title": title,
        "strong_phrases": strong_phrases,
        "core_terms": core_terms,
        "context_terms": context_terms,
        "exclude_terms": exclude_terms,
        "threshold": threshold,
    }


def tracked_scope_value(value: object) -> str:
    scope = str(value or "important").strip().lower()
    if scope not in TRACKED_TOPIC_SCOPES:
        raise ValueError("invalid_scope")
    return scope


def tracked_backfill_mode_value(value: object) -> str:
    mode = str(value or "recent_important").strip().lower()
    if mode not in TRACKED_BACKFILL_MODES:
        raise ValueError("invalid_backfill_mode")
    return mode


def tracked_daily_summary_status_value(value: object) -> str:
    status = str(value or "success").strip().lower()
    if status not in TRACKED_DAILY_SUMMARY_STATUSES:
        raise ValueError("invalid_daily_summary_status")
    return status


def parse_tracked_threshold(value: object, *, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(str(value).strip())
    except Exception as exc:
        raise ValueError("invalid_tracked_threshold") from exc
    if parsed < TRACKED_RULE_THRESHOLD_MIN or parsed > TRACKED_RULE_THRESHOLD_MAX:
        raise ValueError("invalid_tracked_threshold")
    return parsed


def parse_tracked_weight(value: object, *, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        parsed = float(str(value).strip())
    except Exception as exc:
        raise ValueError("invalid_tracked_weight") from exc
    if parsed < TRACKED_RULE_WEIGHT_MIN or parsed > TRACKED_RULE_WEIGHT_MAX:
        raise ValueError("invalid_tracked_weight")
    return parsed


def parse_key_points_text(value: object) -> str:
    key_points = value or ""
    if isinstance(key_points, str):
        try:
            parsed = json.loads(key_points)
            if isinstance(parsed, list):
                return " ".join(str(part) for part in parsed if part)
        except Exception:
            return key_points
    if isinstance(key_points, list):
        return " ".join(str(part) for part in key_points if part)
    return str(key_points or "")


def tracked_default_rules(
    include_keywords: list[str] | None = None,
    exclude_keywords: list[str] | None = None,
    default_rule_params: dict | None = None,
) -> dict:
    base_params = tracked_default_rule_params(default_rule_params)
    return {
        "strong_phrases": [],
        "core_terms": list(include_keywords or []),
        "context_terms": [],
        "exclude_terms": list(exclude_keywords or []),
        "required_terms": [],
        "threshold": base_params["threshold"],
        "candidate_threshold": TRACKED_RULE_CANDIDATE_THRESHOLD_DEFAULT,
        "title_weight": base_params["title_weight"],
        "note_weight": base_params["note_weight"],
        "summary_weight": base_params["summary_weight"],
        "content_weight": base_params["content_weight"],
        "strong_score": base_params["strong_score"],
        "core_score": base_params["core_score"],
        "context_score": base_params["context_score"],
        "exclude_penalty": base_params["exclude_penalty"],
    }


def tracked_default_rule_params(raw_params: object = None) -> dict:
    params = raw_params if isinstance(raw_params, dict) else {}
    return {
        "title_weight": parse_tracked_weight(
            params.get("title_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["title"],
        ),
        "note_weight": parse_tracked_weight(
            params.get("note_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["note"],
        ),
        "summary_weight": parse_tracked_weight(
            params.get("summary_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["summary"],
        ),
        "content_weight": parse_tracked_weight(
            params.get("content_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["content"],
        ),
        "strong_score": parse_tracked_weight(
            params.get("strong_score"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["strong"],
        ),
        "core_score": parse_tracked_weight(
            params.get("core_score"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["core"],
        ),
        "context_score": parse_tracked_weight(
            params.get("context_score"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["context"],
        ),
        "exclude_penalty": parse_tracked_weight(
            params.get("exclude_penalty"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["exclude"],
        ),
        "threshold": parse_tracked_threshold(
            params.get("threshold"),
            default=TRACKED_RULE_THRESHOLD_DEFAULT,
        ),
    }


def tracked_default_rule_params_from_rules(raw_rules: object) -> dict:
    rules = normalize_tracked_rules(raw_rules)
    return {key: rules[key] for key in TRACKED_DEFAULT_RULE_PARAM_KEYS}


def normalize_tracked_rules(raw_rules: object, *, fallback_keywords: list[str] | None = None, fallback_excludes: list[str] | None = None) -> dict:
    rules = raw_rules if isinstance(raw_rules, dict) else {}
    strong_phrases = normalize_keyword_list(rules.get("strong_phrases"))
    core_terms = normalize_keyword_list(rules.get("core_terms"))
    context_terms = normalize_keyword_list(rules.get("context_terms"))
    exclude_terms = normalize_keyword_list(rules.get("exclude_terms"))
    required_terms = normalize_keyword_list(rules.get("required_terms"))

    if not strong_phrases and not core_terms and fallback_keywords:
        core_terms = list(fallback_keywords)
    if not exclude_terms and fallback_excludes:
        exclude_terms = list(fallback_excludes)

    return {
        "strong_phrases": strong_phrases,
        "core_terms": core_terms,
        "context_terms": context_terms,
        "exclude_terms": exclude_terms,
        "required_terms": required_terms,
        "threshold": parse_tracked_threshold(rules.get("threshold"), default=TRACKED_RULE_THRESHOLD_DEFAULT),
        "candidate_threshold": parse_tracked_threshold(
            rules.get("candidate_threshold"),
            default=TRACKED_RULE_CANDIDATE_THRESHOLD_DEFAULT,
        ),
        "title_weight": parse_tracked_weight(
            rules.get("title_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["title"],
        ),
        "note_weight": parse_tracked_weight(
            rules.get("note_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["note"],
        ),
        "summary_weight": parse_tracked_weight(
            rules.get("summary_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["summary"],
        ),
        "content_weight": parse_tracked_weight(
            rules.get("content_weight"),
            default=TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["content"],
        ),
        "strong_score": parse_tracked_weight(
            rules.get("strong_score"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["strong"],
        ),
        "core_score": parse_tracked_weight(
            rules.get("core_score"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["core"],
        ),
        "context_score": parse_tracked_weight(
            rules.get("context_score"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["context"],
        ),
        "exclude_penalty": parse_tracked_weight(
            rules.get("exclude_penalty"),
            default=TRACKED_RULE_TERM_SCORE_DEFAULTS["exclude"],
        ),
    }


def tracked_rules_from_topic(topic: sqlite3.Row | dict) -> dict:
    payload = dict(topic)
    keywords = normalize_keyword_list(payload.get("keywords_json") or "[]")
    excludes = normalize_keyword_list(payload.get("exclude_keywords_json") or "[]")
    raw_rules = payload.get("rules_json") or ""
    parsed_rules: object = {}
    if isinstance(raw_rules, str) and raw_rules.strip():
        try:
            parsed_rules = json.loads(raw_rules)
        except Exception:
            parsed_rules = {}
    elif isinstance(raw_rules, dict):
        parsed_rules = raw_rules
    return normalize_tracked_rules(parsed_rules, fallback_keywords=keywords, fallback_excludes=excludes)


def tracked_text_fields(row: sqlite3.Row | dict) -> dict[str, str]:
    payload = dict(row)
    summary_parts = [
        payload.get("summary") or "",
        parse_key_points_text(payload.get("key_points_zh")),
        payload.get("conclusion_zh") or "",
    ]
    return {
        "title": str(payload.get("title") or ""),
        "note": str(payload.get("note") or ""),
        "summary": "\n".join(part for part in summary_parts if part),
        "content": str(payload.get("body_zh") or ""),
    }


def format_tracked_score(score: float) -> str:
    return f"{score:.2f}".rstrip("0").rstrip(".")


def compact_tracked_reason(
    evidence: dict[str, dict[str, list[str]]] | None,
    score: float,
    *,
    required_hits: list[str] | None = None,
) -> str:
    if not evidence:
        return ""
    segments: list[str] = []
    if required_hits:
        segments.append(f"必要词命中：{'/'.join(required_hits[:4])}")
    for field_key in ("title", "note", "summary", "content"):
        field_hits = evidence.get(field_key) or {}
        terms: list[str] = []
        if field_hits.get("strong"):
            terms.extend(field_hits["strong"])
        if field_hits.get("core"):
            terms.extend(field_hits["core"])
        if field_hits.get("context"):
            terms.extend(field_hits["context"])
        if not terms:
            continue
        deduped_terms: list[str] = []
        seen: set[str] = set()
        for term in terms:
            lowered = term.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped_terms.append(term)
        segments.append(f"{TRACKED_RULE_FIELD_LABELS[field_key]}命中：{'/'.join(deduped_terms[:4])}")
    reason = "；".join(segments[:3])
    if reason:
        reason = f"{reason}；score={format_tracked_score(score)}"
    return reason[:200]


def match_tracked_topic_row(row: sqlite3.Row | dict, rules: dict) -> tuple[bool, float, str]:
    strong_phrases = rules.get("strong_phrases") or []
    core_terms = rules.get("core_terms") or []
    context_terms = rules.get("context_terms") or []
    exclude_terms = rules.get("exclude_terms") or []
    required_terms = rules.get("required_terms") or []
    threshold = int(rules.get("threshold") or TRACKED_RULE_THRESHOLD_DEFAULT)
    if not strong_phrases and not core_terms:
        return False, 0.0, ""
    field_weights = {
        "title": float(rules.get("title_weight", TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["title"])),
        "note": float(rules.get("note_weight", TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["note"])),
        "summary": float(rules.get("summary_weight", TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["summary"])),
        "content": float(rules.get("content_weight", TRACKED_RULE_FIELD_WEIGHT_DEFAULTS["content"])),
    }
    term_scores = {
        "strong": float(rules.get("strong_score", TRACKED_RULE_TERM_SCORE_DEFAULTS["strong"])),
        "core": float(rules.get("core_score", TRACKED_RULE_TERM_SCORE_DEFAULTS["core"])),
        "context": float(rules.get("context_score", TRACKED_RULE_TERM_SCORE_DEFAULTS["context"])),
    }

    text_fields = tracked_text_fields(row)
    normalized_fields = {
        key: value.lower().strip()
        for key, value in text_fields.items()
        if str(value or "").strip()
    }
    if not normalized_fields:
        return False, 0.0, ""

    exclude_hits: list[str] = []
    for field_text in normalized_fields.values():
        for term in exclude_terms:
            lowered = term.lower()
            if lowered and lowered in field_text:
                exclude_hits.append(term)
    if exclude_hits:
        return False, 0.0, ""

    required_hits: list[str] = []
    if required_terms:
        seen_required: set[str] = set()
        for field_text in normalized_fields.values():
            for term in required_terms:
                lowered = term.lower()
                if lowered and lowered in field_text and lowered not in seen_required:
                    seen_required.add(lowered)
                    required_hits.append(term)
        if not required_hits:
            return False, 0.0, ""

    score = 0.0
    evidence: dict[str, dict[str, list[str]]] = {}
    strong_hit = False
    non_body_signal = False
    core_hit = False
    context_hit = False

    for field_key, field_text in normalized_fields.items():
        field_scores = TRACKED_RULE_FIELD_SCORES[field_key]
        field_weight = field_weights[field_key]
        strong_hits = [term for term in strong_phrases if term.lower() in field_text]
        core_hits = [term for term in core_terms if term.lower() in field_text]
        context_hits = [term for term in context_terms if term.lower() in field_text]
        if not strong_hits and not core_hits and not context_hits:
            continue
        field_evidence: dict[str, list[str]] = {}
        if strong_hits:
            score += field_scores["strong"] * term_scores["strong"] * field_weight * len(strong_hits)
            field_evidence["strong"] = strong_hits
            strong_hit = True
        if core_hits:
            score += field_scores["core"] * term_scores["core"] * field_weight * len(core_hits)
            field_evidence["core"] = core_hits
            core_hit = True
        if context_hits:
            score += field_scores["context"] * term_scores["context"] * field_weight * len(context_hits)
            field_evidence["context"] = context_hits
            context_hit = True
        evidence[field_key] = field_evidence
        if field_key != "content":
            non_body_signal = True

    if not evidence:
        return False, 0.0, ""
    if not non_body_signal:
        return False, 0, ""
    if score < threshold:
        return False, score, ""

    if strong_hit:
        return True, score, compact_tracked_reason(evidence, score, required_hits=required_hits)
    if core_hit and context_hit:
        return True, score, compact_tracked_reason(evidence, score, required_hits=required_hits)
    return False, score, ""


def serialize_tracked_topic_row(row: sqlite3.Row | dict) -> dict:
    topic = dict(row)
    topic["description"] = topic.get("description") or ""
    topic["scope"] = topic.get("scope") or "important"
    topic["active"] = 1 if topic.get("active") else 0
    topic["keywords"] = normalize_keyword_list(topic.get("keywords_json") or "[]")
    topic["exclude_keywords"] = normalize_keyword_list(topic.get("exclude_keywords_json") or "[]")
    topic["rules"] = tracked_rules_from_topic(topic)
    topic["rules_json"] = json.dumps(topic["rules"], ensure_ascii=False)
    topic["visible_item_count"] = int(topic.get("visible_item_count") or 0)
    topic["hidden_item_count"] = int(topic.get("hidden_item_count") or 0)
    topic["latest_published_at"] = topic.get("latest_published_at") or ""
    topic["latest_matched_at"] = topic.get("latest_matched_at") or ""
    return topic


def parse_tracked_topic_body(body: dict, *, partial: bool = False) -> dict:
    payload: dict[str, object] = {}
    if not partial or "title" in body:
        title = " ".join(str(body.get("title") or "").split()).strip()
        if not title:
            raise ValueError("empty_title")
        if len(title) > 120:
            raise ValueError("title_too_long")
        payload["title"] = title
    if not partial or "description" in body:
        description = str(body.get("description") or "").strip()
        if len(description) > 1000:
            raise ValueError("description_too_long")
        payload["description"] = description
    rules_touched = any(
        key in body
        for key in (
            "strong_phrases",
            "core_terms",
            "context_terms",
            "exclude_terms",
            "required_terms",
            "threshold",
            "candidate_threshold",
            "title_weight",
            "note_weight",
            "summary_weight",
            "content_weight",
            "strong_score",
            "core_score",
            "context_score",
            "exclude_penalty",
            "keywords",
            "exclude_keywords",
        )
    )
    if not partial or rules_touched:
        default_rule_params = None if partial else current_runtime_settings()["tracked"]["default_rule_params"]
        incoming_rules: dict[str, object] = {**(default_rule_params or {})}
        incoming_rules["strong_phrases"] = body.get("strong_phrases")
        incoming_rules["core_terms"] = body.get("core_terms", body.get("keywords"))
        incoming_rules["context_terms"] = body.get("context_terms")
        incoming_rules["exclude_terms"] = body.get("exclude_terms", body.get("exclude_keywords"))
        incoming_rules["required_terms"] = body.get("required_terms")
        for key in (
            "threshold",
            "candidate_threshold",
            "title_weight",
            "note_weight",
            "summary_weight",
            "content_weight",
            "strong_score",
            "core_score",
            "context_score",
            "exclude_penalty",
        ):
            if key in body:
                incoming_rules[key] = body.get(key)
        rules = normalize_tracked_rules(incoming_rules)
        if not rules["strong_phrases"] and not rules["core_terms"]:
            raise ValueError("empty_rules")
        payload["rules"] = rules
        payload["keywords"] = list(rules["core_terms"])
        payload["exclude_keywords"] = list(rules["exclude_terms"])
    if not partial or "scope" in body:
        payload["scope"] = tracked_scope_value(body.get("scope"))
    if not partial or "active" in body:
        active = body.get("active", True)
        if not isinstance(active, bool):
            raise ValueError("invalid_active")
        payload["active"] = active
    return payload


def categorize_release_note(title: str) -> str:
    lowered = title.lower()
    if "fix:" in lowered or lowered.startswith("fix"):
        return "FIX"
    if "feat:" in lowered or lowered.startswith("feat"):
        return "NEW"
    return "IMPROVE"


def parse_release_notes() -> list[dict]:
    if not README_PATH.exists():
        return []
    lines = README_PATH.read_text(encoding="utf-8").splitlines()
    notes: list[dict] = []
    in_changes = False
    current: dict | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        if not in_changes:
            if line.strip() == "## What's Changed":
                in_changes = True
            continue
        if line.startswith("## ") and line.strip() != "## What's Changed":
            break
        match = RELEASE_NOTE_HEADING_RE.match(line)
        if match:
            if current:
                notes.append(current)
            title = match.group("title").strip()
            version_match = VERSION_RE.search(title)
            current = {
                "date": match.group("date"),
                "title": title,
                "version": version_match.group(0) if version_match else "",
                "category": categorize_release_note(title),
                "lines": [],
            }
            continue
        if current is None:
            continue
        if not line.strip():
            continue
        cleaned = line.strip()
        if cleaned.startswith("- "):
            cleaned = cleaned[2:].strip()
        cleaned = cleaned.replace("**", "")
        current["lines"].append(cleaned)

    if current:
        notes.append(current)
    return notes


def current_runtime_settings() -> dict:
    raw = load_app_settings()
    merged = default_app_settings()
    llm = raw.get("llm") if isinstance(raw, dict) else {}
    if isinstance(llm, dict):
        translation = llm.get("translation")
        if isinstance(translation, dict):
            provider = (translation.get("provider") or "").strip().lower()
            model = (translation.get("model") or "").strip()
            if provider in {"deepseek"}:
                merged["llm"]["translation"]["provider"] = provider
            if isinstance(model, str):
                merged["llm"]["translation"]["model"] = model
        codex_chat = llm.get("codex_chat")
        if isinstance(codex_chat, dict):
            model = codex_chat.get("model")
            if isinstance(model, str):
                merged["llm"]["codex_chat"]["model"] = model.strip()
    tracked = raw.get("tracked") if isinstance(raw, dict) else {}
    if isinstance(tracked, dict):
        merged["tracked"]["default_rule_params"] = tracked_default_rule_params(
            tracked.get("default_rule_params")
        )
    return merged


def provider_secret_name(provider: str) -> str:
    secret_name = SECRET_PROVIDER_MAP.get((provider or "").strip().lower())
    if not secret_name:
        raise ValueError("unsupported_provider")
    return secret_name


def provider_has_configured_key(provider: str) -> bool:
    secret_name = provider_secret_name(provider)
    if (os.getenv(secret_name) or "").strip():
        return True
    try:
        return has_secret(secret_name)
    except SecretStoreError:
        return False


def provider_secret_value(provider: str) -> str:
    secret_name = provider_secret_name(provider)
    value = (os.getenv(secret_name) or "").strip()
    if value:
        return value
    try:
        return (read_secret(secret_name) or "").strip()
    except SecretStoreError:
        return ""


def save_provider_secret(provider: str, value: object) -> None:
    secret_name = provider_secret_name(provider)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("empty_key")
    write_secret(secret_name, value.strip())


def remove_provider_secret(provider: str) -> None:
    secret_name = provider_secret_name(provider)
    delete_secret(secret_name)


def build_model_option(value: str, *, label: str = "", description: str = "", source: str = "") -> dict:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("empty_model_value")
    return {
        "value": normalized,
        "label": (label or normalized).strip(),
        "description": (description or "").strip(),
        "source": (source or "").strip(),
    }


def merge_model_options(options: list[dict], saved_model: str) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for item in options:
        if not isinstance(item, dict):
            continue
        value = (item.get("value") or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        merged.append(
            {
                "value": value,
                "label": (item.get("label") or value).strip(),
                "description": (item.get("description") or "").strip(),
                "source": (item.get("source") or "").strip(),
            }
        )
    saved = (saved_model or "").strip()
    if saved and saved not in seen:
        merged.append(build_model_option(saved, description="当前已保存模型", source="saved"))
    return merged[:SETTINGS_MODEL_OPTION_LIMIT]


def trim_settings_error(value: object, limit: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 1]}…"


def fallback_model_options(values: list[str], *, source: str) -> list[dict]:
    return [build_model_option(value, source=source) for value in values]


def sort_deepseek_model_ids(model_ids: list[str]) -> list[str]:
    priority = {name: index for index, name in enumerate(DEEPSEEK_MODEL_FALLBACKS)}
    return sorted(
        {model_id.strip() for model_id in model_ids if model_id and model_id.strip()},
        key=lambda model_id: (priority.get(model_id, len(priority)), model_id),
    )


def parse_deepseek_model_options(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_id = (row.get("id") or "").strip()
        if model_id:
            ids.append(model_id)
    return [build_model_option(model_id, source="official") for model_id in sort_deepseek_model_ids(ids)]


def deepseek_settings_snapshot(saved_model: str) -> dict:
    resolved_default_model = resolve_translation_default_model()
    configured = provider_has_configured_key("deepseek")
    options = fallback_model_options(DEEPSEEK_MODEL_FALLBACKS, source="fallback")
    status_text = "未配置 key，使用默认候选。"
    last_error = ""
    models_endpoint_reachable = None
    used_fallback = True
    source = "fallback"

    if configured:
        api_key = provider_secret_value("deepseek")
        if not api_key:
            status_text = "检测到已配置 key，但当前读取失败，使用默认候选。"
            last_error = "read_failed"
        else:
            request = Request(
                DEEPSEEK_MODELS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "User-Agent": "news-reader-settings/1.0",
                },
            )
            try:
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                parsed_options = parse_deepseek_model_options(payload)
                if parsed_options:
                    options = parsed_options
                    models_endpoint_reachable = True
                    used_fallback = False
                    source = "official"
                    status_text = "官方 /models 可访问。"
                else:
                    models_endpoint_reachable = False
                    last_error = "empty_models"
                    status_text = "官方 /models 返回空列表，使用默认候选。"
            except HTTPError as exc:
                models_endpoint_reachable = False
                last_error = f"http_{exc.code}"
                status_text = f"官方 /models 访问失败（HTTP {exc.code}），使用默认候选。"
            except URLError as exc:
                models_endpoint_reachable = False
                last_error = trim_settings_error(getattr(exc, "reason", exc))
                status_text = "官方 /models 暂不可达，使用默认候选。"
            except Exception as exc:  # pragma: no cover - env-specific
                models_endpoint_reachable = False
                last_error = trim_settings_error(exc)
                status_text = "官方 /models 检查失败，使用默认候选。"

    return {
        "service": {
            "configured": configured,
            "models_endpoint_reachable": models_endpoint_reachable,
            "used_fallback": used_fallback,
            "last_error": last_error,
            "status_text": status_text,
        },
        "catalog": {
            "source": source,
            "saved_model": (saved_model or "").strip(),
            "resolved_default_model": resolved_default_model,
            "custom_allowed": True,
            "default_label": resolved_default_model,
            "options": merge_model_options(options, saved_model),
        },
    }


def parse_codex_model_options(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("models")
    if not isinstance(rows, list):
        return []

    parsed_rows: list[tuple[int, str, dict]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = (row.get("slug") or "").strip()
        if not slug:
            continue
        visibility = (row.get("visibility") or "").strip().lower()
        if visibility and visibility not in {"list", "default"}:
            continue
        label = slug
        description = ""
        priority = row.get("priority")
        if not isinstance(priority, int):
            priority = 9999
        parsed_rows.append((priority, label.lower(), build_model_option(slug, label=label, description=description, source="codex_debug")))

    parsed_rows.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in parsed_rows[:SETTINGS_MODEL_OPTION_LIMIT]]


def codex_settings_snapshot(saved_model: str) -> dict:
    cli_available = bool(shutil.which("codex"))
    exec_available = False
    models_readable = False
    options = fallback_model_options(CODEX_MODEL_FALLBACKS, source="fallback")
    used_fallback = True
    last_error = ""
    source = "fallback"
    status_bits: list[str] = []

    if not cli_available:
        status_bits.append("未发现 Codex CLI，使用默认候选。")
    else:
        try:
            exec_probe = subprocess.run(
                ["codex", "exec", "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                cwd=str(BASE_DIR),
            )
            exec_available = exec_probe.returncode == 0
            status_bits.append("codex exec 可用。" if exec_available else "codex exec 不可用。")
            if not exec_available and not last_error:
                last_error = trim_settings_error(exec_probe.stderr or exec_probe.stdout or f"exit_{exec_probe.returncode}")
        except Exception as exc:  # pragma: no cover - env-specific
            last_error = trim_settings_error(exc)
            status_bits.append("codex exec 检查失败。")

        try:
            models_probe = subprocess.run(
                ["codex", "debug", "models"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
                cwd=str(BASE_DIR),
            )
            if models_probe.returncode == 0:
                payload = json.loads(models_probe.stdout or "{}")
                parsed_options = parse_codex_model_options(payload)
                if parsed_options:
                    options = parsed_options
                    models_readable = True
                    used_fallback = False
                    source = "codex_debug"
                    status_bits.append("codex debug models 可读取。")
                else:
                    if not last_error:
                        last_error = "empty_models"
                    status_bits.append("codex debug models 返回空列表，使用默认候选。")
            else:
                if not last_error:
                    last_error = trim_settings_error(models_probe.stderr or models_probe.stdout or f"exit_{models_probe.returncode}")
                status_bits.append("codex debug models 不可读取，使用默认候选。")
        except Exception as exc:  # pragma: no cover - env-specific
            if not last_error:
                last_error = trim_settings_error(exc)
            status_bits.append("codex debug models 检查失败，使用默认候选。")

    return {
        "service": {
            "cli_available": cli_available,
            "exec_available": exec_available,
            "models_readable": models_readable,
            "used_fallback": used_fallback,
            "last_error": last_error,
            "status_text": " ".join(status_bits).strip(),
        },
        "catalog": {
            "source": source,
            "saved_model": (saved_model or "").strip(),
            "custom_allowed": True,
            "default_label": "留空则使用 Codex 默认模型",
            "options": merge_model_options(options, saved_model),
        },
    }


def serialize_runtime_settings() -> dict:
    settings = current_runtime_settings()
    translation_model = (settings["llm"]["translation"].get("model") or "").strip()
    codex_chat_model = (settings["llm"]["codex_chat"].get("model") or "").strip()
    deepseek_snapshot = deepseek_settings_snapshot(translation_model)
    codex_snapshot = codex_settings_snapshot(codex_chat_model)
    return {
        "api_status": {
            "deepseek": deepseek_snapshot["service"],
            "codex": codex_snapshot["service"],
        },
        "model_catalogs": {
            "translation": deepseek_snapshot["catalog"],
            "codex_chat": codex_snapshot["catalog"],
        },
        "llm": settings["llm"],
        "tracked": settings["tracked"],
        "restart_notice": "翻译 / 总结与 Codex chat 的新请求通常立即生效；涉及 app.py 本版改动，终验前请重启 Flask。",
    }


def validate_runtime_settings(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("invalid_payload")
    llm = payload.get("llm")
    if not isinstance(llm, dict):
        raise ValueError("invalid_llm_settings")

    translation = llm.get("translation")
    if not isinstance(translation, dict):
        raise ValueError("invalid_llm_settings")

    translation_provider = (translation.get("provider") or "").strip().lower()
    translation_model = (translation.get("model") or "").strip()
    codex_chat = llm.get("codex_chat") if isinstance(llm.get("codex_chat"), dict) else {}
    codex_chat_model = (codex_chat.get("model") or "").strip()
    if translation_provider != "deepseek":
        raise ValueError("unsupported_translation_provider")
    if len(translation_model) > 120:
        raise ValueError("invalid_translation_model")
    if len(codex_chat_model) > 120:
        raise ValueError("invalid_codex_chat_model")

    normalized = {
        "llm": {
            "translation": {
                "provider": "deepseek",
                "model": translation_model,
            },
            "codex_chat": {
                "model": codex_chat_model,
            },
        },
        "tracked": current_runtime_settings()["tracked"],
    }
    return normalized


def chat_provider_catalog() -> dict[str, dict]:
    llm = current_runtime_settings()["llm"]
    model = (llm.get("codex_chat", {}).get("model") or "").strip()
    return {
        "codex": {
            "label": "Codex",
            "available": True,
            "note": "基于当前新闻可用上下文回答；有正文时使用正文，无正文时退回标题、摘要与元数据。",
            "model": model,
        }
    }


def current_codex_chat_model() -> str:
    llm = current_runtime_settings()["llm"]
    return (llm.get("codex_chat", {}).get("model") or "").strip()


def codex_chat_lock(item_id: str) -> threading.Lock:
    with CODEX_CHAT_LOCKS_GUARD:
        return CODEX_CHAT_LOCKS.setdefault(item_id, threading.Lock())


def truncate_chat_context_text(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def build_news_chat_context(
    *,
    item: sqlite3.Row | dict,
    detail: sqlite3.Row | dict | None = None,
    ai: sqlite3.Row | dict | None = None,
    note_row: sqlite3.Row | dict | None = None,
    market_tags: list[dict] | None = None,
) -> dict | None:
    item_payload = dict(item or {})
    detail_payload = dict(detail or {})
    ai_payload = dict(ai or {})
    note_payload = dict(note_row or {})
    tags = market_tags or []

    title = str(detail_payload.get("title") or item_payload.get("title") or "").strip()
    source = str(
        detail_payload.get("source")
        or item_payload.get("source")
        or item_payload.get("source_name")
        or item_payload.get("source_type")
        or ""
    ).strip()
    published_at = str(detail_payload.get("published_at") or item_payload.get("published_at") or "").strip()
    url = str(item_payload.get("url") or "").strip()
    detail_content = str(detail_payload.get("content") or "").strip()
    if detail_content:
        return {
            "title": title,
            "source": source,
            "published_at": published_at,
            "content": detail_content,
            "context_level": "full_detail",
            "context_label": "完整正文",
        }

    lines: list[str] = []
    if title:
        lines.append(f"新闻标题：{title}")
    if source:
        lines.append(f"新闻来源：{source}")
    if item_payload.get("source_type"):
        lines.append(f"来源类型：{item_payload['source_type']}")
    if published_at:
        lines.append(f"发布时间：{published_at}")
    if url:
        lines.append(f"原文链接：{url}")

    summary = truncate_chat_context_text(item_payload.get("summary") or "", 1200)
    if summary:
        lines.append(f"新闻摘要：\n{summary}")

    key_points = truncate_chat_context_text(parse_key_points_text(ai_payload.get("key_points_zh")), 1200)
    if key_points:
        lines.append(f"AI 中文要点：\n{key_points}")

    conclusion = truncate_chat_context_text(ai_payload.get("conclusion_zh") or "", 800)
    if conclusion:
        lines.append(f"AI 中文结论：\n{conclusion}")

    ai_body = truncate_chat_context_text(ai_payload.get("body_zh") or "", 2400)
    if ai_body:
        lines.append(f"AI 中文正文摘录：\n{ai_body}")

    note = truncate_chat_context_text(note_payload.get("note") or "", 1200)
    if note:
        lines.append(f"用户想法：\n{note}")

    if tags:
        tag_labels: list[str] = []
        for tag in tags:
            label = str(tag.get("display_name") or tag.get("tag") or "").strip()
            if not label:
                continue
            direction = str(tag.get("direction") or "").strip()
            if direction == "bullish":
                label = f"{label}(看多)"
            elif direction == "bearish":
                label = f"{label}(看空)"
            tag_labels.append(label)
        if tag_labels:
            lines.append(f"板块标签：{', '.join(tag_labels)}")

    content = "\n\n".join(part for part in lines if part).strip()
    if not content:
        return None
    return {
        "title": title,
        "source": source,
        "published_at": published_at,
        "content": content,
        "context_level": "summary_context",
        "context_label": "摘要与元数据",
    }


def build_codex_chat_prompt(
    *,
    title: str,
    source: str,
    published_at: str,
    content: str,
    question: str,
    context_level: str,
) -> str:
    context_header = (
        "以下包含新闻完整正文。回答原文内容、总结或作者观点时，优先基于正文；若用户追问背景、最新进展、实时数据或文外细节，仍应主动搜索补充。"
        if context_level == "full_detail"
        else "以下不是完整正文，只包含标题、摘要、元数据、用户笔记等上下文。它主要用于理解提问场景，不代表答案一定存在于文中；不要假装读过全文，无法确认全文细节时要明确说明，并在需要时主动搜索补充。"
    )
    return (
        "你是一名新闻研究助手。用户当前围绕一篇新闻提问。\n"
        "给你的新闻内容主要用于理解提问场景，不代表答案一定存在于文中。\n"
        "回答规则：\n"
        "1. 使用中文，回答尽量简洁，但关键信息要完整。\n"
        "2. 如果用户问的是原文内容、总结或作者观点，优先基于新闻上下文回答。\n"
        "3. 如果用户问的是背景、最新进展、实时数据、影响判断或文中没有的细节，应主动搜索最新且可靠的信息后再回答。\n"
        "4. 如果新闻上下文本身不足以直接回答，也应主动搜索补全，不要被局限在文内。\n"
        "5. 回答时明确区分哪些信息来自新闻上下文，哪些来自你后续搜索到的信息。\n"
        "6. 如果搜索后仍无法确认，要明确说明不确定点，不要编造。\n"
        f"新闻标题：{title}\n"
        f"新闻来源：{source}\n"
        f"发布时间：{published_at}\n"
        f"上下文级别：{context_level}\n"
        f"{context_header}\n"
        "新闻上下文：\n"
        f"{content}\n\n"
        f"用户问题：{question}"
    )


def run_codex_chat(
    *,
    question: str,
    title: str,
    source: str,
    published_at: str,
    content: str,
    context_level: str,
    session_id: str = "",
    model: str = "",
    reset: bool = False,
    timeout: int = 180,
) -> dict:
    prompt = question.strip()
    if not prompt:
        raise ValueError("empty_question")

    session = (session_id or "").strip()
    use_resume = bool(session) and not reset
    command = ["codex", "exec"]
    if use_resume:
        command.extend(["resume", session, prompt])
    else:
        command.append(
            build_codex_chat_prompt(
                title=title,
                source=source,
                published_at=published_at,
                content=content,
                question=prompt,
                context_level=context_level,
            )
        )
    command.extend(["--json", "--skip-git-repo-check"])
    if model:
        command.extend(["--model", model])

    with tempfile.NamedTemporaryFile(prefix="news-reader-codex-", suffix=".txt", delete=False) as handle:
        output_path = handle.name
    command.extend(["--output-last-message", output_path])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(BASE_DIR),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("codex_timeout") from exc

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    thread_id = ""
    for line in stdout.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("type") == "thread.started":
            thread_id = (payload.get("thread_id") or "").strip()
            break

    answer = ""
    try:
        answer = Path(output_path).read_text(encoding="utf-8").strip()
    except Exception:
        answer = ""
    finally:
        Path(output_path).unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = (stderr or stdout).strip()
        lowered = detail.lower()
        if use_resume and ("no session" in lowered or "not found" in lowered or "invalid" in lowered):
            raise RuntimeError("codex_session_invalid")
        raise RuntimeError(detail or "codex_failed")

    if not thread_id:
        raise RuntimeError("codex_missing_session_id")
    if not answer:
        raise RuntimeError("codex_empty_answer")

    return {
        "provider": "codex",
        "session_id": thread_id,
        "model": model,
        "answer": answer,
    }


def build_chat_archive_prompt(*, title: str, source: str, published_at: str, messages: list[dict[str, str]]) -> str:
    transcript = "\n".join(
        f"{'用户' if message['role'] == 'user' else '助手'}：{message['content']}"
        for message in messages
    )
    return (
        "你是一名新闻研究助手。请把下面这轮围绕同一篇新闻的对话压缩成一条中文归档结论。\n"
        "硬性要求：\n"
        "1. 只输出最终归档内容，不要任何前后缀。\n"
        f"2. 必须是中文，且不超过{CHAT_ARCHIVE_SUMMARY_MAX_LEN}字。\n"
        "3. 不复述问答过程，不列Q/A。\n"
        "4. 不写“用户问了”“助手回答了”“本轮对话”。\n"
        "5. 只保留最终解决的核心信息、判断或行动线索。\n"
        "6. 如果对话没有形成有效答案，直接输出空字符串。\n\n"
        f"新闻标题：{title}\n"
        f"来源：{source}\n"
        f"发布时间：{published_at}\n"
        "对话记录：\n"
        f"{transcript}"
    )


def run_codex_chat_archive(*, title: str, source: str, published_at: str, messages: list[dict[str, str]], model: str = "", timeout: int = 90) -> dict:
    prompt = build_chat_archive_prompt(
        title=title,
        source=source,
        published_at=published_at,
        messages=messages,
    )
    command = ["codex", "exec", prompt, "--json", "--skip-git-repo-check"]
    if model:
        command.extend(["--model", model])

    with tempfile.NamedTemporaryFile(prefix="news-reader-codex-archive-", suffix=".txt", delete=False) as handle:
        output_path = handle.name
    command.extend(["--output-last-message", output_path])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(BASE_DIR),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("codex_timeout") from exc

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""

    summary = ""
    try:
        summary = " ".join(Path(output_path).read_text(encoding="utf-8").split())
    except Exception:
        summary = ""
    finally:
        Path(output_path).unlink(missing_ok=True)

    if completed.returncode != 0:
        detail = (stderr or stdout).strip()
        raise RuntimeError(detail or "codex_failed")
    if not summary:
        raise RuntimeError("codex_empty_archive")

    return {
        "provider": "codex",
        "model": model,
        "summary": summary,
    }


def normalize_chat_messages(raw_messages: object, *, max_messages: int = 20, max_chars: int = 4000) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list) or not raw_messages:
        raise ValueError("invalid_messages")
    if len(raw_messages) > max_messages:
        raise ValueError("too_many_messages")
    normalized: list[dict[str, str]] = []
    for entry in raw_messages:
        if not isinstance(entry, dict):
            raise ValueError("invalid_messages")
        role = (entry.get("role") or "").strip().lower()
        content = entry.get("content")
        if role not in {"user", "assistant"}:
            raise ValueError("invalid_message_role")
        if not isinstance(content, str):
            raise ValueError("invalid_message_content")
        text = content.strip()
        if not text:
            raise ValueError("empty_message_content")
        if len(text) > max_chars:
            raise ValueError("message_too_long")
        normalized.append({"role": role, "content": text})
    return normalized


def load_error_stats(day: str) -> list[dict]:
    target_name = f"dailyFreshNews_{day}.md"
    target_path = next((path for path in list_daily_files(DAILY_NEWS_DIR) if path.name == target_name), None)
    if not target_path or not target_path.exists():
        return []

    grouped: dict[str, list[str]] = {}
    for entry in parse_daily_errors(target_path):
        time_key = entry["time"]
        grouped.setdefault(time_key, []).append(f"{entry['label']} error")

    if not grouped:
        return []

    ordered = [
        {"time": time_key, "labels": labels}
        for time_key, labels in grouped.items()
    ]
    return [{"date": day, "groups": ordered}]


def load_daily_briefing_index() -> tuple[list[dict], int]:
    months: list[dict] = []
    current_month = ""
    current_items: list[dict] = []
    total = 0
    for path in list_daily_briefing_files(DAILY_BRIEFING_DIR):
        parsed = parse_daily_briefing_file(path)
        month_key = parsed.get("month") or ""
        if month_key != current_month:
            if current_month:
                months.append(
                    {
                        "month": current_month,
                        "label": current_items[0]["month_label"] if current_items else current_month,
                        "count": len(current_items),
                        "items": current_items,
                    }
                )
            current_month = month_key
            current_items = []
        current_items.append(
            {
                "date": parsed["date"],
                "filename": parsed.get("filename") or "",
                "mtime": parsed.get("mtime") or "",
                "date_label": parsed["date_label"],
                "weekday_label": parsed["weekday_label"],
                "month": parsed["month"],
                "month_label": parsed["month_label"],
                "title": parsed["title"],
                "page_title": parsed.get("page_title") or "",
                "metadata": parsed.get("metadata") or [],
                "metadata_summary": parsed.get("metadata_summary") or "",
                "parse_mode": parsed.get("parse_mode") or "structured",
                "parse_warning": parsed.get("parse_warning") or "",
            }
        )
        total += 1
    if current_month:
        months.append(
            {
                "month": current_month,
                "label": current_items[0]["month_label"] if current_items else current_month,
                "count": len(current_items),
                "items": current_items,
            }
        )
    return months, total


def find_daily_briefing_path(date_key: str) -> Path | None:
    target = f"{date_key}_daily.md"
    for path in list_daily_briefing_files(DAILY_BRIEFING_DIR):
        if path.name == target:
            return path
    return None


def serialize_news_rows(items: list[dict], market_tags_map: dict[str, list[dict]]) -> list[dict]:
    for item in items:
        tags = market_tags_map.get(item.get("url") or "", [])
        item["note_preview"] = build_note_preview(item.pop("note_preview_source", None))
        item["market_tags"] = tags
        item["has_market_tags"] = 1 if tags else 0
        item["source_key"] = derive_source_key(item.get("url"), item.get("source_type"), item.get("source"))
        date_key, date_label = derive_date_meta(item.get("published_at"), item.get("date"))
        item["date_key"] = date_key
        item["date_label"] = date_label
    return items


def serialize_reminder_rows(rows: list[sqlite3.Row | dict]) -> list[dict]:
    reminders: list[dict] = []
    for row in rows:
        reminder = dict(row)
        reminder["note"] = reminder.get("note") or ""
        reminder["is_due"] = reminder_is_due(reminder.get("remind_at"), reminder.get("status"))
        reminder["item_exists"] = 1 if reminder.get("item_exists") else 0
        reminders.append(reminder)
    return reminders


def load_reminder_summary(conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active_total,
          SUM(CASE WHEN status='active' AND remind_at <= datetime('now', 'localtime') THEN 1 ELSE 0 END) AS due_total,
          SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done_total,
          SUM(CASE WHEN status='dismissed' THEN 1 ELSE 0 END) AS dismissed_total
        FROM news_reminders
        """
    ).fetchone()
    return {
        "total": int((row["total"] if row else 0) or 0),
        "active_total": int((row["active_total"] if row else 0) or 0),
        "due_total": int((row["due_total"] if row else 0) or 0),
        "done_total": int((row["done_total"] if row else 0) or 0),
        "dismissed_total": int((row["dismissed_total"] if row else 0) or 0),
    }


def load_news_item_map(conn: sqlite3.Connection, item_ids: list[str]) -> dict[str, dict]:
    ordered_ids = [item_id for item_id in item_ids if item_id]
    if not ordered_ids:
        return {}
    placeholders = ",".join(["?"] * len(ordered_ids))
    rows = conn.execute(
        f"""
        SELECT items.id, items.source_file, items.item_order, items.published_at,
               items.date, items.time, items.source, items.source_type,
               items.source_name, items.title, items.summary, items.url,
               st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
               dj.status AS detail_status,
               dj.last_error AS detail_error,
               CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
               an.note AS note_preview_source,
               CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
               aj.status AS ai_status,
               aj.last_error AS ai_error,
               CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready,
               {ITEM_DATE_SQL} AS date_key,
               (
                 SELECT COUNT(*)
                 FROM news_reminders nr
                 WHERE nr.item_id = items.id AND nr.status = 'active'
               ) AS active_reminder_count,
               (
                 SELECT COUNT(*)
                 FROM news_reminders nr
                 WHERE nr.item_id = items.id
                   AND nr.status = 'active'
                   AND nr.remind_at <= datetime('now', 'localtime')
               ) AS due_reminder_count,
               (
                 SELECT MIN(nr.remind_at)
                 FROM news_reminders nr
                 WHERE nr.item_id = items.id AND nr.status = 'active'
               ) AS next_remind_at
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN detail_jobs dj ON dj.url = items.url
        LEFT JOIN article_details ad ON ad.url = items.url
        LEFT JOIN article_notes an ON an.url = items.url
        LEFT JOIN ai_jobs aj ON aj.url = items.url
        LEFT JOIN article_ai aa ON aa.url = items.url
        WHERE items.id IN ({placeholders})
        """,
        ordered_ids,
    ).fetchall()
    urls = [row["url"] for row in rows if row["url"]]
    market_tags_map = load_market_tags_map(conn, urls)
    serialized = serialize_news_rows([dict(row) for row in rows], market_tags_map)
    return {item["id"]: item for item in serialized}


def load_idea_rows(conn: sqlite3.Connection, idea_type: str, sort_order: str) -> list[dict]:
    ideas: list[dict] = []

    if idea_type in ("all", "article"):
        article_rows = conn.execute(
            f"""
            SELECT items.id, items.source_file, items.item_order, items.published_at,
                   items.date, items.time, items.source, items.source_type,
                   items.source_name, items.title, items.summary, items.url,
                   st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
                   dj.status AS detail_status,
                   dj.last_error AS detail_error,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
                   an.note AS note,
                   an.note AS note_preview_source,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
                   aj.status AS ai_status,
                   aj.last_error AS ai_error,
                   CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS active_reminder_count,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id
                       AND nr.status = 'active'
                       AND nr.remind_at <= datetime('now', 'localtime')
                   ) AS due_reminder_count,
                   (
                     SELECT MIN(nr.remind_at)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS next_remind_at,
                   an.created_at AS idea_created_at,
                   an.updated_at AS idea_updated_at
            FROM article_notes an
            JOIN items ON items.url = an.url
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN detail_jobs dj ON dj.url = items.url
            LEFT JOIN article_details ad ON ad.url = items.url
            LEFT JOIN ai_jobs aj ON aj.url = items.url
            LEFT JOIN article_ai aa ON aa.url = items.url
            """
        ).fetchall()
        article_items = [dict(row) for row in article_rows]
        article_tags_map = load_market_tags_map(conn, [item["url"] for item in article_items if item.get("url")])
        article_items = serialize_news_rows(article_items, article_tags_map)
        for item in article_items:
            item["idea_id"] = f"article:{item['id']}"
            item["idea_type"] = "article_note"
            item["idea_context_label"] = "新闻想法"
            item["created_at"] = item.get("idea_created_at") or ""
            item["updated_at"] = item.get("idea_updated_at") or ""
            date_key, date_label = derive_ts_date_meta(item.get("updated_at"))
            item["date_key"] = date_key
            item["date_label"] = date_label
            ideas.append(item)

    if idea_type in ("all", "trend"):
        trend_rows = conn.execute(
            """
            SELECT mtn.id,
                   mtn.date_key,
                   mtn.tag,
                   mtn.direction,
                   mtn.note,
                   mtn.created_at,
                   mtn.updated_at,
                   mtd.display_name
            FROM market_trend_notes mtn
            LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
            """
        ).fetchall()
        for row in trend_rows:
            direction_label = "看多" if row["direction"] == "bullish" else "看空"
            tag_label = row["display_name"] or row["tag"]
            updated_at = row["updated_at"] or ""
            date_key, date_label = derive_ts_date_meta(updated_at)
            ideas.append(
                {
                    "id": None,
                    "idea_id": f"trend:{row['id']}",
                    "idea_type": "trend_note",
                    "idea_context_label": "趋势想法",
                    "trend_note_id": row["id"],
                    "trend_date_key": row["date_key"],
                    "tag_key": row["tag"],
                    "tag_label": tag_label,
                    "direction": row["direction"],
                    "direction_label": direction_label,
                    "title": f"{tag_label} · {direction_label}",
                    "summary": f"{row['date_key']} · {tag_label} · {direction_label}",
                    "source": "趋势",
                    "published_at": row["date_key"],
                    "url": "",
                    "note": row["note"],
                    "note_preview": build_note_preview(row["note"]),
                    "created_at": row["created_at"] or "",
                    "updated_at": updated_at,
                    "date_key": date_key,
                    "date_label": date_label,
                }
            )

    reverse = sort_order != "reverse"
    ideas.sort(
        key=lambda idea: (
            idea.get("updated_at") or "",
            str(idea.get("idea_id") or idea.get("id") or ""),
        ),
        reverse=reverse,
    )
    return ideas


def load_item_reminders(conn: sqlite3.Connection, item_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT nr.*,
               CASE WHEN items.id IS NULL THEN 0 ELSE 1 END AS item_exists
        FROM news_reminders nr
        LEFT JOIN items ON items.id = nr.item_id
        WHERE nr.item_id = ?
        ORDER BY
          CASE
            WHEN nr.status = 'active' AND nr.remind_at <= datetime('now', 'localtime') THEN 0
            WHEN nr.status = 'active' THEN 1
            WHEN nr.status = 'done' THEN 2
            ELSE 3
          END ASC,
          CASE WHEN nr.status = 'active' THEN nr.remind_at ELSE nr.updated_at END ASC,
          nr.id DESC
        """,
        (item_id,),
    ).fetchall()
    return serialize_reminder_rows(rows)


def load_tracked_topic_choices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, title
        FROM tracked_topics
        WHERE active = 1
        ORDER BY updated_at DESC, id DESC
        """
    ).fetchall()
    return [{"id": row["id"], "title": row["title"]} for row in rows]


def load_tracked_topics(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT tt.*,
               (
                 SELECT COUNT(*)
                 FROM tracked_topic_items tti
                 WHERE tti.topic_id = tt.id
                   AND tti.hidden_at IS NULL
                   AND tti.item_id NOT LIKE 'trend_note:%'
               ) AS visible_item_count,
               (
                 SELECT COUNT(*)
                 FROM tracked_topic_items tti
                 WHERE tti.topic_id = tt.id
                   AND tti.hidden_at IS NOT NULL
                   AND tti.item_id NOT LIKE 'trend_note:%'
               ) AS hidden_item_count,
               (
                 SELECT MAX(items.published_at)
                 FROM tracked_topic_items tti
                 JOIN items ON items.id = tti.item_id
                 WHERE tti.topic_id = tt.id AND tti.hidden_at IS NULL
               ) AS latest_published_at,
               (
                 SELECT MAX(tti.updated_at)
                 FROM tracked_topic_items tti
                 WHERE tti.topic_id = tt.id
                   AND tti.item_id NOT LIKE 'trend_note:%'
               ) AS latest_matched_at
        FROM tracked_topics tt
        ORDER BY tt.updated_at DESC, tt.id DESC
        """
    ).fetchall()
    return [serialize_tracked_topic_row(row) for row in rows]


def load_tracked_topic(conn: sqlite3.Connection, topic_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT tt.*,
               (
                 SELECT COUNT(*)
                 FROM tracked_topic_items tti
                 WHERE tti.topic_id = tt.id
                   AND tti.hidden_at IS NULL
                   AND tti.item_id NOT LIKE 'trend_note:%'
               ) AS visible_item_count,
               (
                 SELECT COUNT(*)
                 FROM tracked_topic_items tti
                 WHERE tti.topic_id = tt.id
                   AND tti.hidden_at IS NOT NULL
                   AND tti.item_id NOT LIKE 'trend_note:%'
               ) AS hidden_item_count,
               (
                 SELECT MAX(items.published_at)
                 FROM tracked_topic_items tti
                 JOIN items ON items.id = tti.item_id
                 WHERE tti.topic_id = tt.id AND tti.hidden_at IS NULL
               ) AS latest_published_at,
               (
                 SELECT MAX(tti.updated_at)
                 FROM tracked_topic_items tti
                 WHERE tti.topic_id = tt.id
                   AND tti.item_id NOT LIKE 'trend_note:%'
               ) AS latest_matched_at
        FROM tracked_topics tt
        WHERE tt.id = ?
        """,
        (topic_id,),
    ).fetchone()
    if not row:
        return None
    return serialize_tracked_topic_row(row)


def tracked_topic_item_status(conn: sqlite3.Connection, topic_id: int, item_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, hidden_at, manual_added_at, match_method, score, reason
        FROM tracked_topic_items
        WHERE topic_id = ? AND item_id = ?
        """,
        (topic_id, item_id),
    ).fetchone()


def tracked_topic_candidate_rows(
    conn: sqlite3.Connection,
    *,
    scope: str,
    created_after: str | None = None,
    date_after: str | None = None,
) -> list[dict]:
    where = []
    args: list[object] = []
    if scope == "important":
        where.append("st.important_at IS NOT NULL")
    if created_after:
        where.append("items.created_at >= ?")
        args.append(created_after)
    if date_after:
        where.append(f"{ITEM_DATE_SQL} >= ?")
        args.append(date_after)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    news_rows = conn.execute(
        f"""
        SELECT items.id,
               items.url,
               items.title,
               items.summary,
               items.published_at,
               items.date,
               aa.key_points_zh,
               aa.conclusion_zh,
               aa.body_zh,
               an.note
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN article_ai aa ON aa.url = items.url
        LEFT JOIN article_notes an ON an.url = items.url
        {where_sql}
        ORDER BY items.published_at DESC, items.id DESC
        """,
        args,
    ).fetchall()
    return [dict(row) for row in news_rows]


def upsert_tracked_topic_match(
    conn: sqlite3.Connection,
    *,
    topic_id: int,
    item_row: sqlite3.Row | dict,
    match_method: str,
    score: float,
    reason: str,
    manual_added_at: str | None = None,
    clear_hidden: bool = False,
) -> bool:
    ts = now_ts()
    item = dict(item_row)
    existing = tracked_topic_item_status(conn, topic_id, str(item["id"]))
    created_or_restored = not existing
    if existing and existing["hidden_at"] and not manual_added_at and not clear_hidden:
        return False
    if existing and existing["manual_added_at"] and not manual_added_at:
        return False
    if existing and existing["hidden_at"] and (manual_added_at or clear_hidden):
        created_or_restored = True

    hidden_value = None if (manual_added_at or clear_hidden) else (existing["hidden_at"] if existing else None)
    conn.execute(
        """
        INSERT INTO tracked_topic_items(
          topic_id, item_id, item_url, match_method, score, reason,
          hidden_at, manual_added_at, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(topic_id, item_id) DO UPDATE SET
          item_url=excluded.item_url,
          match_method=excluded.match_method,
          score=excluded.score,
          reason=excluded.reason,
          hidden_at=excluded.hidden_at,
          manual_added_at=COALESCE(excluded.manual_added_at, tracked_topic_items.manual_added_at),
          updated_at=excluded.updated_at
        """,
        (
            topic_id,
            str(item["id"]),
            item.get("url") or "",
            match_method,
            score,
            reason[:200],
            hidden_value,
            manual_added_at,
            ts,
            ts,
        ),
    )
    return created_or_restored or bool(manual_added_at)


def run_tracked_topic_match(
    conn: sqlite3.Connection,
    *,
    topic: dict,
    candidate_rows: list[sqlite3.Row],
    preserve_last_incremental: bool = False,
    replace_existing_auto_matches: bool = False,
) -> int:
    topic_id = int(topic["id"])
    rules = topic.get("rules") if isinstance(topic.get("rules"), dict) else tracked_rules_from_topic(topic)
    matched = 0
    matched_ids: set[str] = set()
    candidate_ids = {str(dict(row)["id"]) for row in candidate_rows}
    for row in candidate_rows:
        ok, score, reason = match_tracked_topic_row(row, rules)
        if not ok:
            continue
        matched_ids.add(str(dict(row)["id"]))
        if upsert_tracked_topic_match(
            conn,
            topic_id=topic_id,
            item_row=row,
            match_method="keyword",
            score=score,
            reason=reason,
        ):
            matched += 1
    if replace_existing_auto_matches and candidate_ids:
        placeholders = ",".join("?" for _ in candidate_ids)
        args: list[object] = [topic_id, *candidate_ids]
        sql = f"""
            DELETE FROM tracked_topic_items
            WHERE topic_id = ?
              AND match_method = 'keyword'
              AND manual_added_at IS NULL
              AND hidden_at IS NULL
              AND item_id IN ({placeholders})
        """
        if matched_ids:
            matched_placeholders = ",".join("?" for _ in matched_ids)
            sql += f" AND item_id NOT IN ({matched_placeholders})"
            args.extend(matched_ids)
        conn.execute(sql, args)
    if not preserve_last_incremental:
        conn.execute(
            "UPDATE tracked_topics SET last_incremental_at=?, updated_at=? WHERE id=?",
            (now_ts(), now_ts(), topic_id),
        )
    return len(matched_ids) if replace_existing_auto_matches else matched


def run_tracked_topics_incremental(conn: sqlite3.Connection) -> int:
    topics = [topic for topic in load_tracked_topics(conn) if topic["active"]]
    total_matched = 0
    for topic in topics:
        candidate_rows = tracked_topic_candidate_rows(
            conn,
            scope=topic["scope"],
            created_after=topic.get("last_incremental_at") or topic.get("created_at"),
        )
        total_matched += run_tracked_topic_match(conn, topic=topic, candidate_rows=candidate_rows)
    return total_matched


def tracked_topic_timeline_items(conn: sqlite3.Connection, topic_id: int) -> list[dict]:
    tracked_rows = conn.execute(
        """
        SELECT item_id, item_url, match_method, score, reason, manual_added_at, updated_at AS tracked_updated_at
        FROM tracked_topic_items
        WHERE topic_id = ?
          AND hidden_at IS NULL
          AND item_id NOT LIKE 'trend_note:%'
        """,
        (topic_id,),
    ).fetchall()
    news_ids = [row["item_id"] for row in tracked_rows]

    news_map: dict[str, dict] = {}
    if news_ids:
        placeholders = ",".join(["?"] * len(news_ids))
        rows = conn.execute(
            f"""
            SELECT items.id,
                   items.source_file,
                   items.item_order,
                   items.published_at,
                   items.date,
                   items.time,
                   items.source,
                   items.source_type,
                   items.source_name,
                   items.title,
                   items.summary,
                   items.url,
                   st.read_at,
                   st.important_at,
                   st.read_later_at,
                   st.read_later_done_at,
                   st.favorite_at,
                   dj.status AS detail_status,
                   dj.last_error AS detail_error,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
                   an.note AS note_preview_source,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
                   aj.status AS ai_status,
                   aj.last_error AS ai_error,
                   CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS active_reminder_count,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id
                       AND nr.status = 'active'
                       AND nr.remind_at <= datetime('now', 'localtime')
                   ) AS due_reminder_count,
                   (
                     SELECT MIN(nr.remind_at)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS next_remind_at
            FROM items
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN detail_jobs dj ON dj.url = items.url
            LEFT JOIN article_details ad ON ad.url = items.url
            LEFT JOIN article_notes an ON an.url = items.url
            LEFT JOIN ai_jobs aj ON aj.url = items.url
            LEFT JOIN article_ai aa ON aa.url = items.url
            WHERE items.id IN ({placeholders})
            """,
            news_ids,
        ).fetchall()
        urls = [row["url"] for row in rows if row["url"]]
        market_tags_map = load_market_tags_map(conn, urls)
        serialized = serialize_news_rows([dict(row) for row in rows], market_tags_map)
        for item in serialized:
            item["entry_type"] = "news"
            item["tracked_item_id"] = str(item["id"])
            item["tracked_sort_ts"] = item.get("published_at") or ""
            news_map[str(item["id"])] = item

    items: list[dict] = []
    for tracked_row in tracked_rows:
        tracked_item_id = str(tracked_row["item_id"])
        item = news_map.get(tracked_item_id)
        if not item:
            continue
        item = dict(item)
        item["tracked_match_method"] = tracked_row["match_method"] or "keyword"
        item["tracked_score"] = float(tracked_row["score"] or 0)
        item["tracked_reason"] = tracked_row["reason"] or ""
        item["tracked_manual_added_at"] = tracked_row["manual_added_at"] or ""
        item["tracked_updated_at"] = tracked_row["tracked_updated_at"] or ""
        items.append(item)
    items.sort(
        key=lambda item: (
            item.get("tracked_sort_ts") or item.get("published_at") or "",
            str(item.get("tracked_item_id") or item.get("id") or ""),
        ),
        reverse=True,
    )
    return items


def tracked_daily_summary_source_rows(conn: sqlite3.Connection, topic_id: int, *, date: str | None = None) -> list[dict]:
    tracked_rows = conn.execute(
        """
        SELECT item_id, updated_at AS tracked_updated_at
        FROM tracked_topic_items
        WHERE topic_id = ?
          AND hidden_at IS NULL
          AND item_id NOT LIKE 'trend_note:%'
        """,
        (topic_id,),
    ).fetchall()
    news_ids = [row["item_id"] for row in tracked_rows]

    rows: list[dict] = []
    tracked_updated_by_item_id = {str(row["item_id"]): row["tracked_updated_at"] or "" for row in tracked_rows}
    if news_ids:
        placeholders = ",".join(["?"] * len(news_ids))
        news_rows = conn.execute(
            f"""
            SELECT items.id,
                   items.url,
                   items.title,
                   items.summary,
                   items.published_at,
                   items.date,
                   items.time,
                   items.source,
                   items.source_name,
                   an.note,
                   aa.conclusion_zh,
                   aa.body_zh,
                   ad.content,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS has_detail,
                   items.updated_at AS item_updated_at,
                   COALESCE(an.updated_at, '') AS note_updated_at,
                   COALESCE(aa.updated_at, '') AS ai_updated_at,
                   COALESCE(ad.updated_at, '') AS detail_updated_at
            FROM items
            LEFT JOIN article_notes an ON an.url = items.url
            LEFT JOIN article_ai aa ON aa.url = items.url
            LEFT JOIN article_details ad ON ad.url = items.url
            WHERE items.id IN ({placeholders})
            """,
            news_ids,
        ).fetchall()
        for row in news_rows:
            payload = dict(row)
            payload["entry_type"] = "news"
            payload["tracked_item_id"] = str(payload["id"])
            payload["tracked_updated_at"] = tracked_updated_by_item_id.get(str(payload["id"]), "")
            payload["date_key"] = payload.get("date") or (str(payload.get("published_at") or "")[:10])
            rows.append(payload)
    if date:
        rows = [row for row in rows if (row.get("date_key") or "") == date]
    rows.sort(
        key=lambda row: (
            row.get("date_key") or "",
            row.get("published_at") or "",
            str(row.get("tracked_item_id") or row.get("id") or ""),
        ),
        reverse=False,
    )
    return rows


def tracked_daily_summary_row(conn: sqlite3.Connection, topic_id: int, date: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT topic_id, date, item_ids_hash, summary_text, status, error, model, raw_json, created_at, updated_at
        FROM tracked_topic_daily_summaries
        WHERE topic_id = ? AND date = ?
        """,
        (topic_id, date),
    ).fetchone()


def truncate_daily_summary_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def tracked_daily_summary_char_limit(news_count: int) -> int:
    safe_count = max(0, int(news_count or 0))
    return min(TRACKED_DAILY_SUMMARY_MAX_CHARS, max(TRACKED_DAILY_SUMMARY_MIN_CHARS, safe_count * 50))


def enforce_daily_summary_char_limit(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text or len(text) <= limit:
        return text
    natural_limit = max(1, limit - 1)
    window = text[:natural_limit]
    cut_at = -1
    for marker in ("。", "；", ";", "\n", "！", "？", "……", "，", ",", "、", "：", ":"):
        pos = window.rfind(marker)
        if pos > cut_at:
            cut_at = pos
    if cut_at >= 0:
        clipped = window[: cut_at + 1].rstrip()
    else:
        clipped = window.rstrip()
    if not clipped:
        clipped = window.rstrip()
    return clipped + "…"


def build_tracked_daily_summary_hash(rows: list[dict]) -> str:
    basis = []
    budget = tracked_daily_summary_char_limit(len(rows))
    basis.append(f"version={TRACKED_DAILY_SUMMARY_VERSION}")
    basis.append(f"max_summary_chars={budget}")
    for row in rows:
        basis.append(
            "||".join(
                [
                    str(row.get("id") or ""),
                    str(row.get("published_at") or ""),
                    str(row.get("title") or ""),
                    str(row.get("summary") or ""),
                    str(row.get("note") or ""),
                    str(row.get("conclusion_zh") or ""),
                    str(row.get("body_zh") or ""),
                    str(row.get("content") or ""),
                    str(row.get("item_updated_at") or ""),
                    str(row.get("tracked_updated_at") or ""),
                    str(row.get("note_updated_at") or ""),
                    str(row.get("ai_updated_at") or ""),
                    str(row.get("detail_updated_at") or ""),
                ]
            )
        )
    return hashlib.sha256("\n".join(basis).encode("utf-8")).hexdigest()


def build_tracked_daily_summary_materials(topic: dict, date: str, rows: list[dict]) -> str:
    blocks = [f"主题：{topic.get('title') or '未命名主题'}", f"日期：{date}"]
    for index, row in enumerate(rows, start=1):
        source_label = row.get("source_name") or row.get("source") or "未知来源"
        published_at = row.get("published_at") or row.get("date") or ""
        lines = [
            f"新闻 {index}",
            f"发布时间：{published_at}",
            f"来源：{source_label}",
            f"标题：{row.get('title') or '无标题'}",
        ]
        summary = truncate_daily_summary_text(row.get("summary"), TRACKED_DAILY_SUMMARY_SUMMARY_LIMIT)
        if summary:
            lines.append(f"摘要：{summary}")
        conclusion = truncate_daily_summary_text(row.get("conclusion_zh"), TRACKED_DAILY_SUMMARY_SUMMARY_LIMIT)
        if conclusion:
            lines.append(f"AI 摘要：{conclusion}")
        note = truncate_daily_summary_text(row.get("note"), TRACKED_DAILY_SUMMARY_NOTE_LIMIT)
        if note:
            lines.append(f"用户想法：{note}")
        body_zh = truncate_daily_summary_text(row.get("body_zh"), TRACKED_DAILY_SUMMARY_AI_BODY_LIMIT)
        if body_zh:
            lines.append(f"AI 正文摘录：{body_zh}")
        content = truncate_daily_summary_text(row.get("content"), TRACKED_DAILY_SUMMARY_CONTENT_LIMIT)
        if content:
            lines.append(f"正文：{content}")
        blocks.append("\n".join(lines))
    materials = "\n\n".join(blocks).strip()
    if len(materials) <= TRACKED_DAILY_SUMMARY_TEXT_LIMIT:
        return materials
    return materials[:TRACKED_DAILY_SUMMARY_TEXT_LIMIT].rstrip()


def serialize_tracked_daily_summary_group(topic: dict, date: str, rows: list[dict], summary_row: sqlite3.Row | None) -> dict:
    current_hash = build_tracked_daily_summary_hash(rows)
    max_summary_chars = tracked_daily_summary_char_limit(len(rows))
    saved_hash = (summary_row["item_ids_hash"] if summary_row else "") or ""
    saved_status = (summary_row["status"] if summary_row else "") or ""
    if not summary_row:
        status = "missing"
    elif saved_hash != current_hash:
        status = "stale"
    elif saved_status == "failed":
        status = "failed"
    else:
        status = "success"

    items = []
    for row in rows:
        items.append(
            {
                "id": row.get("tracked_item_id") or row.get("id") or "",
                "entry_type": "news",
                "url": row.get("url") or "",
                "title": row.get("title") or "未命名新闻",
                "published_at": row.get("published_at") or "",
                "source": row.get("source_name") or row.get("source") or "",
                "summary": row.get("summary") or "",
                "has_detail": bool(row.get("has_detail")),
            }
        )

    return {
        "date": date,
        "item_count": len(items),
        "item_ids_hash": current_hash,
        "max_summary_chars": max_summary_chars,
        "status": status,
        "summary_text": (summary_row["summary_text"] if summary_row else "") or "",
        "error": (summary_row["error"] if summary_row else "") or "",
        "model": (summary_row["model"] if summary_row else "") or "",
        "created_at": (summary_row["created_at"] if summary_row else "") or "",
        "updated_at": (summary_row["updated_at"] if summary_row else "") or "",
        "items": items,
    }


def load_tracked_topic_daily_summaries(conn: sqlite3.Connection, topic: dict) -> list[dict]:
    rows = tracked_daily_summary_source_rows(conn, int(topic["id"]))
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        date = (row.get("date_key") or row.get("date") or "") or ((row.get("published_at") or "")[:10])
        if not date:
            continue
        grouped.setdefault(date, []).append(row)

    payload: list[dict] = []
    for date in sorted(grouped.keys(), reverse=True):
        source_rows = grouped[date]
        summary_row = tracked_daily_summary_row(conn, int(topic["id"]), date)
        payload.append(serialize_tracked_daily_summary_group(topic, date, source_rows, summary_row))
    return payload


def save_tracked_daily_summary(
    conn: sqlite3.Connection,
    *,
    topic_id: int,
    date: str,
    item_ids_hash: str,
    status: str,
    summary_text: str,
    error: str,
    model: str,
    raw_json: str,
) -> None:
    ts = now_ts()
    conn.execute(
        """
        INSERT INTO tracked_topic_daily_summaries(
          topic_id, date, item_ids_hash, summary_text, status, error, model, raw_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(topic_id, date) DO UPDATE SET
          item_ids_hash=excluded.item_ids_hash,
          summary_text=excluded.summary_text,
          status=excluded.status,
          error=excluded.error,
          model=excluded.model,
          raw_json=excluded.raw_json,
          updated_at=excluded.updated_at
        """,
        (
            topic_id,
            date,
            item_ids_hash,
            summary_text,
            status,
            error[:500] if error else None,
            model,
            raw_json or "{}",
            ts,
            ts,
        ),
    )


def load_market_tag_definitions(conn: sqlite3.Connection, active_only: bool = False) -> list[dict]:
    where_sql = "WHERE mtd.active=1" if active_only else ""
    rows = conn.execute(
        f"""
        SELECT mtd.key,
               mtd.display_name,
               mtd.active,
               mtd.sort_order,
               mtd.created_at,
               mtd.updated_at,
               COALESCE(amt.item_tag_count, 0) AS item_tag_count,
               COALESCE(mtn.trend_note_count, 0) AS trend_note_count
        FROM market_tag_definitions mtd
        LEFT JOIN (
            SELECT tag, COUNT(*) AS item_tag_count
            FROM article_market_tags
            GROUP BY tag
        ) amt ON amt.tag = mtd.key
        LEFT JOIN (
            SELECT tag, COUNT(*) AS trend_note_count
            FROM market_trend_notes
            GROUP BY tag
        ) mtn ON mtn.tag = mtd.key
        {where_sql}
        ORDER BY mtd.sort_order ASC, mtd.created_at ASC, mtd.key ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def load_market_tag_definition_map(conn: sqlite3.Connection) -> dict[str, dict]:
    return {row["key"]: row for row in load_market_tag_definitions(conn, active_only=False)}


def seed_market_tag_definitions(conn: sqlite3.Connection) -> None:
    deleted_keys = {
        row["key"]
        for row in conn.execute("SELECT key FROM market_tag_deleted_keys").fetchall()
    }
    existing = {
        row["key"]: row["display_name"]
        for row in conn.execute("SELECT key, display_name FROM market_tag_definitions").fetchall()
    }
    ts = now_ts()
    with conn:
        for idx, tag in enumerate(DEFAULT_MARKET_TAG_CHOICES):
            if tag in deleted_keys:
                continue
            if tag in existing:
                continue
            conn.execute(
                """
                INSERT INTO market_tag_definitions(key, display_name, active, sort_order, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (tag, tag, idx, ts, ts),
            )


def migrate_market_trend_notes(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_trend_notes'"
    ).fetchone()
    if not exists:
        return

    index_rows = conn.execute("PRAGMA index_list('market_trend_notes')").fetchall()
    legacy_unique_index = None
    for row in index_rows:
        if int(row["unique"] or 0) != 1:
            continue
        index_name = row["name"]
        cols = [
            info["name"]
            for info in conn.execute(f"PRAGMA index_info('{index_name}')").fetchall()
        ]
        if cols == ["date_key", "tag", "direction"]:
            legacy_unique_index = index_name
            break
    if not legacy_unique_index:
        return

    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_trend_notes_v2 (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              date_key TEXT NOT NULL,
              tag TEXT NOT NULL,
              direction TEXT NOT NULL,
              note TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO market_trend_notes_v2(id, date_key, tag, direction, note, created_at, updated_at)
            SELECT id, date_key, tag, direction, note, created_at, updated_at
            FROM market_trend_notes
            ORDER BY id ASC
            """
        )
        conn.execute("DROP TABLE market_trend_notes")
        conn.execute("ALTER TABLE market_trend_notes_v2 RENAME TO market_trend_notes")


def create_market_tag_key(conn: sqlite3.Connection, display_name: str) -> str:
    base = display_name.strip()
    candidate = base
    suffix = 2
    while (
        conn.execute("SELECT 1 FROM market_tag_definitions WHERE key=?", (candidate,)).fetchone()
        or conn.execute("SELECT 1 FROM market_tag_deleted_keys WHERE key=?", (candidate,)).fetchone()
    ):
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


def market_tag_impact_counts(conn: sqlite3.Connection, tag_key: str) -> dict[str, int]:
    return {
        "item_tag_count": int(
            conn.execute("SELECT COUNT(*) FROM article_market_tags WHERE tag=?", (tag_key,)).fetchone()[0] or 0
        ),
        "trend_note_count": int(
            conn.execute("SELECT COUNT(*) FROM market_trend_notes WHERE tag=?", (tag_key,)).fetchone()[0] or 0
        ),
    }


def load_market_tags_map(conn: sqlite3.Connection, urls: list[str]) -> dict[str, list[dict]]:
    if not urls:
        return {}
    uniq_urls = [u for u in dict.fromkeys(urls) if u]
    if not uniq_urls:
        return {}
    placeholders = ",".join(["?"] * len(uniq_urls))
    rows = conn.execute(
        f"""
        SELECT amt.url,
               amt.tag,
               amt.direction,
               amt.created_at,
               amt.updated_at,
               mtd.display_name
        FROM article_market_tags amt
        LEFT JOIN market_tag_definitions mtd ON mtd.key = amt.tag
        WHERE amt.url IN ({placeholders})
        ORDER BY amt.updated_at DESC, amt.tag ASC
        """,
        uniq_urls,
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        grouped.setdefault(r["url"], []).append(
            {
                "key": r["tag"],
                "tag": r["display_name"] or r["tag"],
                "direction": r["direction"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        )
    return grouped


def load_notes_map(conn: sqlite3.Connection, urls: list[str]) -> dict[str, dict]:
    if not urls:
        return {}
    uniq_urls = [u for u in dict.fromkeys(urls) if u]
    if not uniq_urls:
        return {}
    placeholders = ",".join(["?"] * len(uniq_urls))
    rows = conn.execute(
        f"""
        SELECT url, note, created_at, updated_at
        FROM article_notes
        WHERE url IN ({placeholders})
        """,
        uniq_urls,
    ).fetchall()
    return {r["url"]: dict(r) for r in rows}


def load_trend_notes_map(
    conn: sqlite3.Connection,
    keys: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], list[dict]]:
    if not keys:
        return {}
    uniq_keys = list(dict.fromkeys(keys))
    placeholders = ",".join(["(?, ?, ?)"] * len(uniq_keys))
    args: list[str] = []
    for date_key, tag_key, direction in uniq_keys:
        args.extend([date_key, tag_key, direction])
    rows = conn.execute(
        f"""
        SELECT mtn.id,
               mtn.date_key,
               mtn.tag,
               mtn.direction,
               mtn.note,
               mtn.created_at,
               mtn.updated_at,
               mtd.display_name
        FROM market_trend_notes mtn
        LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
        WHERE (mtn.date_key, mtn.tag, mtn.direction) IN ({placeholders})
        ORDER BY mtn.updated_at DESC, mtn.id DESC
        """,
        args,
    ).fetchall()
    mapped: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        key = (r["date_key"], r["tag"], r["direction"])
        mapped.setdefault(key, []).append(
            {
                "id": r["id"],
                "date_key": r["date_key"],
                "tag_key": r["tag"],
                "tag": r["display_name"] or r["tag"],
                "direction": r["direction"],
                "note": r["note"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
        )
    return mapped


def parse_market_workbench_content_filter(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    if normalized not in MARKET_WORKBENCH_CONTENT_FILTERS:
        raise ValueError("invalid_market_workbench_content_filter")
    return normalized


def market_workbench_filter_sql_parts(content_filter: str) -> tuple[str, str]:
    if content_filter == "ideas":
        return (
            "AND an.url IS NOT NULL",
            "",
        )
    if content_filter == "bullish":
        return (
            "AND mt.direction = 'bullish'",
            "AND mtn.direction = 'bullish'",
        )
    if content_filter == "bearish":
        return (
            "AND mt.direction = 'bearish'",
            "AND mtn.direction = 'bearish'",
        )
    return ("", "")


def load_market_workbench_overview(conn: sqlite3.Connection, content_filter: str) -> list[dict]:
    item_filter_sql, note_filter_sql = market_workbench_filter_sql_parts(content_filter)
    rows = conn.execute(
        f"""
        SELECT
          mtd.key,
          mtd.display_name,
          mtd.active,
          mtd.sort_order,
          COALESCE(total_items.total, 0) AS total_items,
          COALESCE(recent_items.recent_total, 0) AS recent_total,
          COALESCE(recent_items.bullish_total, 0) AS bullish_total,
          COALESCE(recent_items.bearish_total, 0) AS bearish_total,
          COALESCE(total_notes.total, 0) AS trend_note_total,
          COALESCE(recent_notes.recent_total, 0) AS recent_note_total,
          recent_items.latest_published_at,
          recent_notes.latest_note_updated_at
        FROM market_tag_definitions mtd
        LEFT JOIN (
          SELECT mt.tag, COUNT(*) AS total
          FROM article_market_tags mt
          LEFT JOIN article_notes an ON an.url = mt.url
          WHERE 1=1 {item_filter_sql}
          GROUP BY mt.tag
        ) total_items ON total_items.tag = mtd.key
        LEFT JOIN (
          SELECT mt.tag,
                 COUNT(*) AS recent_total,
                 SUM(CASE WHEN mt.direction = 'bullish' THEN 1 ELSE 0 END) AS bullish_total,
                 SUM(CASE WHEN mt.direction = 'bearish' THEN 1 ELSE 0 END) AS bearish_total,
                 MAX(items.published_at) AS latest_published_at
          FROM article_market_tags mt
          JOIN items ON items.url = mt.url
          LEFT JOIN article_notes an ON an.url = mt.url
          WHERE items.published_at >= datetime('now', '-30 days')
            {item_filter_sql}
          GROUP BY mt.tag
        ) recent_items ON recent_items.tag = mtd.key
        LEFT JOIN (
          SELECT mtn.tag, COUNT(*) AS total
          FROM market_trend_notes mtn
          WHERE 1=1 {note_filter_sql}
          GROUP BY mtn.tag
        ) total_notes ON total_notes.tag = mtd.key
        LEFT JOIN (
          SELECT mtn.tag,
                 COUNT(*) AS recent_total,
                 MAX(mtn.updated_at) AS latest_note_updated_at
          FROM market_trend_notes mtn
          WHERE mtn.updated_at >= datetime('now', '-30 days')
            {note_filter_sql}
          GROUP BY mtn.tag
        ) recent_notes ON recent_notes.tag = mtd.key
        WHERE mtd.active = 1
        ORDER BY COALESCE(recent_items.latest_published_at, recent_notes.latest_note_updated_at, '') DESC,
                 mtd.sort_order ASC,
                 mtd.display_name COLLATE NOCASE ASC
        """
    ).fetchall()
    payload = []
    for row in rows:
        total_items = int(row["total_items"] or 0)
        trend_note_total = int(row["trend_note_total"] or 0)
        if total_items <= 0 and trend_note_total <= 0:
            continue
        payload.append(
            {
                "tag_key": row["key"],
                "tag_label": row["display_name"],
                "active": int(row["active"] or 0),
                "total_items": total_items,
                "recent_total": int(row["recent_total"] or 0),
                "bullish_total": int(row["bullish_total"] or 0),
                "bearish_total": int(row["bearish_total"] or 0),
                "trend_note_total": trend_note_total,
                "recent_note_total": int(row["recent_note_total"] or 0),
                "latest_published_at": row["latest_published_at"] or "",
                "latest_note_updated_at": row["latest_note_updated_at"] or "",
            }
        )
    return payload


def load_market_tag_feed(
    conn: sqlite3.Connection,
    *,
    tag_key: str | None,
    content_filter: str,
    sort_order: str,
    page: int,
    per: int,
) -> dict:
    item_filter_sql, note_filter_sql = market_workbench_filter_sql_parts(content_filter)
    sort_direction = "ASC" if sort_order == "reverse" else "DESC"
    if tag_key:
        union_sql = f"""
        SELECT
          'news' AS row_kind,
          items.id AS ref_id,
          items.published_at AS sort_ts,
          items.id AS tie_breaker
        FROM items
        JOIN article_market_tags mt ON mt.url = items.url
        LEFT JOIN article_notes an ON an.url = items.url
        WHERE mt.tag = ?
          {item_filter_sql}
        UNION ALL
        SELECT
          'trend_note' AS row_kind,
          CAST(mtn.id AS TEXT) AS ref_id,
          COALESCE(mtn.updated_at, mtn.created_at, mtn.date_key) AS sort_ts,
          CAST(mtn.id AS TEXT) AS tie_breaker
        FROM market_trend_notes mtn
        WHERE mtn.tag = ?
          {note_filter_sql}
    """
        args = [tag_key, tag_key]
    else:
        union_sql = f"""
        SELECT
          'news' AS row_kind,
          items.id AS ref_id,
          items.published_at AS sort_ts,
          items.id AS tie_breaker
        FROM items
        JOIN article_market_tags mt ON mt.url = items.url
        LEFT JOIN article_notes an ON an.url = items.url
        WHERE 1=1
          {item_filter_sql}
        GROUP BY items.id
        UNION ALL
        SELECT
          'trend_note' AS row_kind,
          CAST(mtn.id AS TEXT) AS ref_id,
          COALESCE(mtn.updated_at, mtn.created_at, mtn.date_key) AS sort_ts,
          CAST(mtn.id AS TEXT) AS tie_breaker
        FROM market_trend_notes mtn
        WHERE 1=1
          {note_filter_sql}
        """
        args = []
    total = int(conn.execute(f"SELECT COUNT(*) FROM ({union_sql}) feed_rows", args).fetchone()[0] or 0)
    offset = (page - 1) * per
    page_rows = conn.execute(
        f"""
        SELECT row_kind, ref_id
        FROM ({union_sql}) feed_rows
        ORDER BY sort_ts {sort_direction}, tie_breaker {sort_direction}
        LIMIT ? OFFSET ?
        """,
        [*args, per, offset],
    ).fetchall()
    news_ids = [row["ref_id"] for row in page_rows if row["row_kind"] == "news"]
    trend_note_ids = [int(row["ref_id"]) for row in page_rows if row["row_kind"] == "trend_note"]

    news_map: dict[str, dict] = {}
    if news_ids:
        placeholders = ",".join(["?"] * len(news_ids))
        rows = conn.execute(
            f"""
            SELECT items.id, items.source_file, items.item_order, items.published_at,
                   items.date, items.time, items.source, items.source_type,
                   items.source_name, items.title, items.summary, items.url,
                   st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
                   dj.status AS detail_status,
                   dj.last_error AS detail_error,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
                   an.note AS note_preview_source,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
                   aj.status AS ai_status,
                   aj.last_error AS ai_error,
                   CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS active_reminder_count,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id
                       AND nr.status = 'active'
                       AND nr.remind_at <= datetime('now', 'localtime')
                   ) AS due_reminder_count,
                   (
                     SELECT MIN(nr.remind_at)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS next_remind_at,
                   {ITEM_DATE_SQL} AS date_key
            FROM items
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN detail_jobs dj ON dj.url = items.url
            LEFT JOIN article_details ad ON ad.url = items.url
            LEFT JOIN article_notes an ON an.url = items.url
            LEFT JOIN ai_jobs aj ON aj.url = items.url
            LEFT JOIN article_ai aa ON aa.url = items.url
            WHERE items.id IN ({placeholders})
            """,
            news_ids,
        ).fetchall()
        urls = [row["url"] for row in rows if row["url"]]
        market_tags_map = load_market_tags_map(conn, urls)
        serialized = serialize_news_rows([dict(row) for row in rows], market_tags_map)
        news_map = {str(item["id"]): item for item in serialized}

    trend_note_map: dict[int, dict] = {}
    if trend_note_ids:
        placeholders = ",".join(["?"] * len(trend_note_ids))
        rows = conn.execute(
            f"""
            SELECT mtn.id,
                   mtn.date_key,
                   mtn.tag,
                   mtn.direction,
                   mtn.note,
                   mtn.created_at,
                   mtn.updated_at,
                   mtd.display_name
            FROM market_trend_notes mtn
            LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
            WHERE mtn.id IN ({placeholders})
            """,
            trend_note_ids,
        ).fetchall()
        for row in rows:
            updated_at = row["updated_at"] or ""
            date_key, date_label = derive_ts_date_meta(updated_at)
            trend_note_map[int(row["id"])] = {
                "id": None,
                "idea_id": f"trend:{row['id']}",
                "idea_type": "trend_note",
                "idea_context_label": "趋势想法",
                "trend_note_id": row["id"],
                "trend_date_key": row["date_key"],
                "tag_key": row["tag"],
                "tag_label": row["display_name"] or row["tag"],
                "direction": row["direction"],
                "direction_label": "看多" if row["direction"] == "bullish" else "看空",
                "title": f"{row['display_name'] or row['tag']} · {'看多' if row['direction'] == 'bullish' else '看空'}",
                "summary": f"{row['date_key']} · {row['display_name'] or row['tag']}",
                "source": "趋势",
                "published_at": row["date_key"],
                "url": "",
                "note": row["note"],
                "note_preview": build_note_preview(row["note"]),
                "created_at": row["created_at"] or "",
                "updated_at": updated_at,
                "date_key": date_key,
                "date_label": date_label,
            }

    items: list[dict] = []
    for row in page_rows:
        if row["row_kind"] == "news":
            item = news_map.get(str(row["ref_id"]))
            if item:
                item["entry_type"] = "news"
                items.append(item)
        else:
            note = trend_note_map.get(int(row["ref_id"]))
            if note:
                note["entry_type"] = "trend_note"
                items.append(note)
    pages = max(1, math.ceil(total / per)) if total else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": pages,
        "has_more": page < pages,
    }


def market_tag_summary_row(conn: sqlite3.Connection, tag_key: str, range_days: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT tag_key, range_days, source_hash, summary_text, status, error, model, raw_json, created_at, updated_at
        FROM market_tag_summaries
        WHERE tag_key = ? AND range_days = ?
        """,
        (tag_key, range_days),
    ).fetchone()


def load_market_tag_summary_sources(
    conn: sqlite3.Connection,
    *,
    tag_key: str,
    range_days: int,
    limit: int,
) -> tuple[list[dict], list[dict]]:
    news_rows = conn.execute(
        f"""
        SELECT items.id,
               items.published_at,
               items.source,
               items.source_type,
               items.source_name,
               items.title,
               items.summary,
               items.url,
               mt.direction,
               an.note,
               an.updated_at AS note_updated_at,
               aa.conclusion_zh,
               aa.body_zh,
               ai.updated_at AS ai_updated_at,
               ad.content,
               ad.updated_at AS detail_updated_at,
               mt.updated_at AS tag_updated_at
        FROM items
        JOIN article_market_tags mt ON mt.url = items.url
        LEFT JOIN article_notes an ON an.url = items.url
        LEFT JOIN article_ai aa ON aa.url = items.url
        LEFT JOIN ai_jobs ai ON ai.url = items.url
        LEFT JOIN article_details ad ON ad.url = items.url
        WHERE mt.tag = ?
          AND items.published_at >= datetime('now', ?)
        ORDER BY items.published_at DESC, items.id DESC
        LIMIT ?
        """,
        (tag_key, f"-{int(range_days)} days", limit),
    ).fetchall()
    note_rows = conn.execute(
        """
        SELECT id, date_key, direction, note, created_at, updated_at
        FROM market_trend_notes
        WHERE tag = ?
          AND COALESCE(updated_at, created_at, date_key) >= datetime('now', ?)
        ORDER BY COALESCE(updated_at, created_at, date_key) DESC, id DESC
        """,
        (tag_key, f"-{int(range_days)} days"),
    ).fetchall()
    return [dict(row) for row in news_rows], [dict(row) for row in note_rows]


def market_pin_scope_and_tag(tag_key: str | None) -> tuple[str, str]:
    normalized = (tag_key or "").strip()
    return ("overview", "") if not normalized else ("tag", normalized)


def load_market_pinned_note(conn: sqlite3.Connection, tag_key: str | None) -> dict:
    scope, normalized_tag_key = market_pin_scope_and_tag(tag_key)
    row = conn.execute(
        """
        SELECT scope, tag_key, note, collapsed, created_at, updated_at
        FROM market_pinned_notes
        WHERE scope = ? AND tag_key = ?
        """,
        (scope, normalized_tag_key),
    ).fetchone()
    return {
        "scope": scope,
        "tag_key": normalized_tag_key,
        "note": (row["note"] if row else "") or "",
        "collapsed": int((row["collapsed"] if row else 0) or 0),
        "created_at": row["created_at"] if row else None,
        "updated_at": row["updated_at"] if row else None,
    }


def serialize_market_pinned_note(pin_row: dict, tag_def: dict | None = None) -> dict:
    scope = pin_row.get("scope") or "overview"
    tag_key = pin_row.get("tag_key") or ""
    tag_label = tag_def["display_name"] if tag_def else ""
    return {
        "scope": scope,
        "tag_key": tag_key,
        "tag_label": tag_label,
        "title": "板块集合置顶" if scope == "overview" else f"{tag_label or tag_key} · 置顶信息",
        "scope_label": "全部板块" if scope == "overview" else (tag_label or tag_key),
        "note": pin_row.get("note") or "",
        "collapsed": int(pin_row.get("collapsed") or 0),
        "updated_at": pin_row.get("updated_at"),
        "created_at": pin_row.get("created_at"),
    }


def build_market_tag_summary_hash(news_rows: list[dict], note_rows: list[dict], range_days: int) -> str:
    basis = [f"version={MARKET_TAG_SUMMARY_VERSION}", f"range_days={range_days}"]
    for row in news_rows:
        basis.append(
            "||".join(
                [
                    str(row.get("id") or ""),
                    str(row.get("published_at") or ""),
                    str(row.get("title") or ""),
                    str(row.get("summary") or ""),
                    str(row.get("note") or ""),
                    str(row.get("direction") or ""),
                    str(row.get("conclusion_zh") or ""),
                    str(row.get("body_zh") or ""),
                    str(row.get("content") or ""),
                    str(row.get("tag_updated_at") or ""),
                    str(row.get("note_updated_at") or ""),
                    str(row.get("ai_updated_at") or ""),
                    str(row.get("detail_updated_at") or ""),
                ]
            )
        )
    for row in note_rows:
        basis.append(
            "||".join(
                [
                    str(row.get("id") or ""),
                    str(row.get("date_key") or ""),
                    str(row.get("direction") or ""),
                    str(row.get("note") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("updated_at") or ""),
                ]
            )
        )
    return hashlib.sha256("\n".join(basis).encode("utf-8")).hexdigest()


def build_market_tag_summary_materials(tag_label: str, news_rows: list[dict], note_rows: list[dict], range_days: int) -> str:
    blocks = [
        f"板块：{tag_label}",
        f"范围：最近 {range_days} 天",
        "【新闻事实】",
    ]
    for index, row in enumerate(news_rows, start=1):
        lines = [
            f"新闻 {index}",
            f"发布时间：{row.get('published_at') or ''}",
            f"来源：{row.get('source_name') or row.get('source') or '未知来源'}",
            f"标题：{row.get('title') or '无标题'}",
            f"方向：{'看多' if row.get('direction') == 'bullish' else '看空'}",
        ]
        summary = truncate_daily_summary_text(row.get("summary"), MARKET_WORKBENCH_SUMMARY_SUMMARY_LIMIT)
        if summary:
            lines.append(f"摘要：{summary}")
        ai_summary = truncate_daily_summary_text(row.get("conclusion_zh"), MARKET_WORKBENCH_SUMMARY_SUMMARY_LIMIT)
        if ai_summary:
            lines.append(f"AI 摘要：{ai_summary}")
        ai_body = truncate_daily_summary_text(row.get("body_zh"), MARKET_WORKBENCH_SUMMARY_BODY_LIMIT)
        if ai_body:
            lines.append(f"AI 正文摘录：{ai_body}")
        content = truncate_daily_summary_text(row.get("content"), MARKET_WORKBENCH_SUMMARY_BODY_LIMIT)
        if content:
            lines.append(f"正文摘录：{content}")
        note = truncate_daily_summary_text(row.get("note"), MARKET_WORKBENCH_SUMMARY_NOTE_LIMIT)
        if note:
            lines.append(f"对应新闻想法：{note}")
        blocks.append("\n".join(lines))
    blocks.append("【用户想法】")
    if note_rows:
        for index, row in enumerate(note_rows, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"独立趋势想法 {index}",
                        f"日期：{row.get('date_key') or ''}",
                        f"方向：{'看多' if row.get('direction') == 'bullish' else '看空'}",
                        f"内容：{truncate_daily_summary_text(row.get('note'), MARKET_WORKBENCH_SUMMARY_NOTE_LIMIT)}",
                    ]
                )
            )
    else:
        blocks.append("无独立趋势想法。")
    text = "\n\n".join(blocks).strip()
    if len(text) <= MARKET_WORKBENCH_SUMMARY_TEXT_LIMIT:
        return text
    return text[:MARKET_WORKBENCH_SUMMARY_TEXT_LIMIT].rstrip()


def serialize_market_tag_summary(
    tag_def: dict,
    range_days: int,
    news_rows: list[dict],
    note_rows: list[dict],
    summary_row: sqlite3.Row | None,
) -> dict:
    current_hash = build_market_tag_summary_hash(news_rows, note_rows, range_days)
    saved_hash = (summary_row["source_hash"] if summary_row else "") or ""
    saved_status = (summary_row["status"] if summary_row else "") or ""
    if not summary_row:
        status = "missing"
    elif current_hash != saved_hash:
        status = "stale"
    elif saved_status == "failed":
        status = "failed"
    else:
        status = "success"
    return {
        "tag_key": tag_def["key"],
        "tag_label": tag_def["display_name"],
        "range_days": range_days,
        "scope_label": f"最近 {range_days} 天，最多 {MARKET_WORKBENCH_SUMMARY_MAX_NEWS} 条本地新闻",
        "news_count": len(news_rows),
        "trend_note_count": len(note_rows),
        "source_hash": current_hash,
        "status": status,
        "summary_text": (summary_row["summary_text"] if summary_row else "") or "",
        "error": (summary_row["error"] if summary_row else "") or "",
        "model": (summary_row["model"] if summary_row else "") or "",
        "created_at": (summary_row["created_at"] if summary_row else "") or "",
        "updated_at": (summary_row["updated_at"] if summary_row else "") or "",
    }


def save_market_tag_summary(
    conn: sqlite3.Connection,
    *,
    tag_key: str,
    range_days: int,
    source_hash: str,
    status: str,
    summary_text: str,
    error: str,
    model: str,
    raw_json: str,
) -> None:
    ts = now_ts()
    conn.execute(
        """
        INSERT INTO market_tag_summaries(
          tag_key, range_days, source_hash, summary_text, status, error, model, raw_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tag_key, range_days) DO UPDATE SET
          source_hash=excluded.source_hash,
          summary_text=excluded.summary_text,
          status=excluded.status,
          error=excluded.error,
          model=excluded.model,
          raw_json=excluded.raw_json,
          updated_at=excluded.updated_at
        """,
        (
            tag_key,
            range_days,
            source_hash,
            summary_text,
            status,
            error[:500] if error else None,
            model,
            raw_json or "{}",
            ts,
            ts,
        ),
    )


def derive_date_meta(published_at: str | None, raw_date: str | None) -> tuple[str, str]:
    date_key = (raw_date or "").strip()
    if not date_key and published_at:
        date_key = str(published_at).strip()[:10]
    if not date_key:
        return ("unknown", "未知日期")

    try:
        day = datetime.strptime(date_key, "%Y-%m-%d").date()
    except ValueError:
        return (date_key, date_key)

    today = datetime.now().date()
    if day == today:
        return (date_key, "今天")
    if day == today.fromordinal(today.toordinal() - 1):
        return (date_key, "昨天")
    return (date_key, f"{day.year}年{day.month}月{day.day}日")


def derive_ts_date_meta(timestamp: str | None) -> tuple[str, str]:
    normalized = (timestamp or "").strip()
    if len(normalized) >= 10:
        return normalized[:10], normalized[:10]
    return "unknown", "未知日期"


def resolve_detail_route(url: str) -> dict | None:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("x.com", "twitter.com"):
        return {"source": "Twitter/X", "command": TWITTER_THREAD_COMMAND, "timeout": TWITTER_THREAD_TIMEOUT}
    return DETAIL_COMMAND_ROUTES.get(host)


def enqueue_detail_job(conn: sqlite3.Connection, item_id: str, url: str, source: str) -> bool:
    route = resolve_detail_route(url)
    ts = now_ts()
    existing_detail = conn.execute(
        "SELECT url FROM article_details WHERE url=?",
        (url,),
    ).fetchone()
    if existing_detail:
        conn.execute(
            """
            INSERT INTO detail_jobs(url, item_id, source, status, attempts, queued_at, updated_at)
            VALUES (?, ?, ?, 'success', 0, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              item_id=excluded.item_id,
              source=excluded.source,
              status='success',
              updated_at=excluded.updated_at
            """,
            (url, item_id, source, ts, ts),
        )
        return False

    row = conn.execute(
        "SELECT status FROM detail_jobs WHERE url=?",
        (url,),
    ).fetchone()
    if row and row["status"] in ("pending", "running", "success", "skipped"):
        conn.execute(
            "UPDATE detail_jobs SET item_id=?, source=?, updated_at=? WHERE url=?",
            (item_id, source, ts, url),
        )
        return False

    conn.execute(
        """
        INSERT INTO detail_jobs(url, item_id, source, status, attempts, queued_at, updated_at)
        VALUES (?, ?, ?, 'pending', 0, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
          item_id=excluded.item_id,
          source=excluded.source,
          status='pending',
          queued_at=excluded.queued_at,
          updated_at=excluded.updated_at
        """,
        (url, item_id, source, ts, ts),
    )
    return True


def _run_opencli_json_command(cmd: list[str], timeout: int) -> tuple[bool, object, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, None, "TIMEOUT"
    except Exception as exc:
        return False, None, f"SUBPROCESS_ERROR: {exc}"

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, None, err or f"EXIT_{proc.returncode}"

    try:
        parsed = json.loads(proc.stdout or "[]")
    except Exception as exc:
        return False, None, f"INVALID_JSON: {exc}"
    return True, parsed, ""


def _normalize_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_normalize_text(item) for item in value) if part)
    if isinstance(value, dict):
        return _normalize_text(value.get("text") or value.get("content") or value.get("body"))
    return ""


def _normalize_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _normalize_text(item)
        if text:
            result.append(text)
    return result


def _strip_twitter_comment_summary_prefix(text: str, comment_count: int) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""
    prefixes = [
        f"基于已抓取的 {comment_count} 条评论总结：",
        f"基于已抓取的{comment_count}条评论总结：",
        f"基于已抓取的 {comment_count} 条评论总结",
        f"基于已抓取的{comment_count}条评论总结",
    ]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    return normalized.lstrip("：: ").strip()


def _looks_like_same_content(left: str, right: str) -> bool:
    a = re.sub(r"\s+", " ", (left or "").strip())
    b = re.sub(r"\s+", " ", (right or "").strip())
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 80 and shorter in longer


def _extract_twitter_thread_payload(parsed: object) -> tuple[dict, list[dict]]:
    if isinstance(parsed, list):
        tweets = [item for item in parsed if isinstance(item, dict)]
        if not tweets:
            return {}, []
        return tweets[0], tweets[1:]

    record = parsed if isinstance(parsed, dict) else {}
    if not record:
        return {}, []
    main = record.get("tweet") if isinstance(record.get("tweet"), dict) else record
    comments: list[dict] = []
    for key in ("comments", "replies", "reply_tweets", "tweets"):
        value = record.get(key)
        if isinstance(value, list):
            entries = [item for item in value if isinstance(item, dict)]
            if entries:
                comments = entries[1:] if key == "tweets" and entries and main is entries[0] else entries
                break
    return main if isinstance(main, dict) else {}, comments


def _extract_twitter_article_payload(parsed: object) -> dict:
    record = parsed[0] if isinstance(parsed, list) and parsed else parsed
    return record if isinstance(record, dict) else {}


_TWITTER_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_TWITTER_VIDEO_HOSTS = {"video.twimg.com"}
_TWITTER_VIDEO_PATTERNS = (".mp4", ".m3u8", ".mov", "amplify_video", "ext_tw_video", "/video/")


def _is_cacheable_twitter_media_url(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host != "pbs.twimg.com" or "/media/" not in path:
        return False
    url_lower = url.lower()
    if any(pattern in url_lower for pattern in _TWITTER_VIDEO_PATTERNS):
        return False
    return True


def _is_twitter_image_url(url: str) -> bool:
    return _is_cacheable_twitter_media_url(url)


def _extract_tweet_media_urls(tweet: dict) -> list[str]:
    urls: list[str] = []
    media_urls = tweet.get("media_urls")
    if isinstance(media_urls, str):
        media_urls = [media_urls]
    if isinstance(media_urls, list):
        for value in media_urls:
            if isinstance(value, str) and value.startswith("http"):
                urls.append(value)
    media_list = tweet.get("media")
    if isinstance(media_list, list):
        for entry in media_list:
            if not isinstance(entry, dict):
                continue
            for key in ("media_url_https", "url", "media_url"):
                value = entry.get(key)
                if isinstance(value, str) and value.startswith("http"):
                    urls.append(value)
                    break
    return urls


def _build_twitter_media_images(main_tweet: dict, quoted_tweet: dict | None) -> list[dict]:
    seen: set[str] = set()
    images: list[dict] = []
    for source, tweet in (("tweet", main_tweet), ("quoted_tweet", quoted_tweet or {})):
        if not isinstance(tweet, dict):
            continue
        for url in _extract_tweet_media_urls(tweet):
            if url in seen:
                continue
            if _is_twitter_image_url(url):
                seen.add(url)
                images.append({"url": url, "source": source})
    return images


def _is_twitter_url(url: str) -> bool:
    route = resolve_detail_route(url)
    return route is not None and route.get("source") == "Twitter/X"


_MEDIA_CACHE_MAX_SIZE = 10 * 1024 * 1024
_MEDIA_CACHE_ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MEDIA_CACHE_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_MEDIA_CACHE_MAX_AGE_DAYS = 30
_MEDIA_CACHE_KEY_RE = re.compile(r"^[a-f0-9]{64}$")


def _media_cache_key_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _extension_for_mime_type(mime_type: str | None) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get((mime_type or "").lower(), "")


def _media_cache_relative_path(cache_key: str, ext: str = "") -> str:
    return f"{cache_key[:2]}/{cache_key[2:4]}/{cache_key}{ext}"


def _is_path_within_media_cache_dir(full_path: Path) -> bool:
    try:
        resolved = full_path.resolve()
        root = MEDIA_CACHE_DIR.resolve()
        return resolved == root or root in resolved.parents
    except Exception:
        return False


def _download_media_file(url: str, dest_path: Path) -> tuple[bool, str | None, int]:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as resp:
            final_url = resp.geturl()
            if not _is_cacheable_twitter_media_url(final_url):
                return False, f"redirect_to_non_whitelist: {final_url}", 0
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type:
                if content_type not in _MEDIA_CACHE_ALLOWED_MIME_TYPES:
                    return False, f"unsupported_content_type: {content_type}", 0
            else:
                parsed_path = urlparse(final_url).path.lower()
                ext = os.path.splitext(parsed_path)[1]
                if ext not in _MEDIA_CACHE_ALLOWED_EXTENSIONS:
                    return False, f"unsupported_extension: {ext}", 0
            data = resp.read(_MEDIA_CACHE_MAX_SIZE + 1)
            if len(data) > _MEDIA_CACHE_MAX_SIZE:
                return False, "content_too_large", 0
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(data)
            return True, content_type or None, len(data)
    except HTTPError as exc:
        return False, f"http_{exc.code}", 0
    except Exception as exc:
        return False, str(exc), 0


def _cleanup_media_cache(conn: sqlite3.Connection) -> None:
    cutoff = (datetime.now() - timedelta(days=_MEDIA_CACHE_MAX_AGE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT url, relative_path FROM media_cache WHERE created_at < ?",
        (cutoff,),
    ).fetchall()
    for row in rows:
        try:
            full_path = (MEDIA_CACHE_DIR / row["relative_path"]).resolve()
            if _is_path_within_media_cache_dir(full_path) and full_path.exists():
                full_path.unlink()
        except Exception:
            pass
    conn.execute("DELETE FROM media_cache WHERE created_at < ?", (cutoff,))


def _cache_twitter_image(conn: sqlite3.Connection, url: str) -> dict | None:
    if not _is_cacheable_twitter_media_url(url):
        return None
    cache_key = _media_cache_key_for_url(url)
    relative_path = _media_cache_relative_path(cache_key)
    dest_path = MEDIA_CACHE_DIR / relative_path
    existing = conn.execute(
        "SELECT status, relative_path FROM media_cache WHERE url=?",
        (url,),
    ).fetchone()
    if existing and existing["status"] == "success":
        existing_path = MEDIA_CACHE_DIR / existing["relative_path"]
        if existing_path.exists():
            return {"cache_key": cache_key, "cached_url": f"/api/media-cache/{cache_key}", "status": "success"}
    ok, mime_type, size = _download_media_file(url, dest_path)
    ts = now_ts()
    if not ok:
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              status=excluded.status,
              updated_at=excluded.updated_at,
              last_error=excluded.last_error
            """,
            (url, cache_key, relative_path, None, 0, "failed", ts, ts, mime_type or "download_failed"),
        )
        return None
    ext = _extension_for_mime_type(mime_type)
    if ext:
        relative_path = _media_cache_relative_path(cache_key, ext)
        final_path = MEDIA_CACHE_DIR / relative_path
        if final_path != dest_path:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest_path), str(final_path))
    else:
        final_path = dest_path
    conn.execute(
        """
        INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at, last_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
          cache_key=excluded.cache_key,
          relative_path=excluded.relative_path,
          mime_type=excluded.mime_type,
          size_bytes=excluded.size_bytes,
          status=excluded.status,
          created_at=excluded.created_at,
          updated_at=excluded.updated_at,
          last_error=NULL
        """,
        (url, cache_key, relative_path, mime_type, size, "success", ts, ts, None),
    )
    return {"cache_key": cache_key, "cached_url": f"/api/media-cache/{cache_key}", "status": "success"}


def _sanitize_twitter_media_images(raw_images: object) -> list[dict]:
    if not isinstance(raw_images, list):
        return []
    seen: set[str] = set()
    result: list[dict] = []
    for entry in raw_images:
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        if source not in ("tweet", "quoted_tweet"):
            continue
        url = entry.get("url")
        if not _is_cacheable_twitter_media_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append({"url": url, "source": source})
    return result


def _build_twitter_comments_summary_text(comments: list[dict]) -> str:
    parts: list[str] = []
    for index, comment in enumerate(comments, start=1):
        author = _normalize_text(comment.get("author") or comment.get("username") or comment.get("screen_name"))
        text = _normalize_text(comment.get("text") or comment.get("content") or comment.get("full_text") or comment.get("body"))
        if not text:
            continue
        label = f"评论 {index}"
        if author:
            label += f"（{author}）"
        parts.append(f"{label}：{text}")
    return "\n".join(parts).strip()


def run_opencli_twitter_detail(url: str) -> tuple[bool, dict, str]:
    thread_cmd = [
        *TWITTER_THREAD_COMMAND,
        url,
        "--limit",
        str(TWITTER_COMMENT_FETCH_LIMIT),
        "-f",
        "json",
        "--window",
        "background",
        "--site-session",
        "persistent",
    ]
    ok, parsed_thread, error = _run_opencli_json_command(thread_cmd, TWITTER_THREAD_TIMEOUT)
    if not ok:
        return False, {}, error

    main_tweet, comments = _extract_twitter_thread_payload(parsed_thread)
    main_text = _normalize_text(main_tweet.get("text") or main_tweet.get("content") or main_tweet.get("full_text") or main_tweet.get("body"))
    if len(main_text) < 20:
        return False, {}, "EMPTY_TWITTER_THREAD"

    quoted = main_tweet.get("quoted_tweet") if isinstance(main_tweet.get("quoted_tweet"), dict) else {}
    quoted_text = _normalize_text(quoted.get("text") or quoted.get("content") or quoted.get("full_text") or quoted.get("body"))

    article_record: dict = {}
    article_error = ""
    article_cmd = [
        *TWITTER_ARTICLE_COMMAND,
        url,
        "-f",
        "json",
        "--window",
        "background",
        "--site-session",
        "persistent",
    ]
    article_ok, parsed_article, article_err = _run_opencli_json_command(article_cmd, TWITTER_ARTICLE_TIMEOUT)
    if article_ok:
        article_record = _extract_twitter_article_payload(parsed_article)
    else:
        article_error = article_err

    article_text = _normalize_text(article_record.get("content") or article_record.get("body") or article_record.get("text") or article_record.get("full_text"))
    if _looks_like_same_content(main_text, article_text):
        article_text = ""

    comment_count = len(comments)
    comment_summary_text = ""
    comment_summary_error = ""
    if comment_count > 5:
        comments_text = _build_twitter_comments_summary_text(comments)
        if comments_text:
            try:
                summary_payload = generate_twitter_comments_summary(
                    title=_normalize_text(main_tweet.get("title")) or "Twitter/X 评论区",
                    source="Twitter/X",
                    comments_text=comments_text,
                    comment_count=comment_count,
                )
                comment_summary_text = _strip_twitter_comment_summary_prefix(
                    summary_payload.get("summary_text", ""),
                    comment_count,
                )
            except LLMClientError as exc:
                comment_summary_error = str(exc)

    lines = ["【主推文】", main_text]
    if quoted_text:
        lines.extend(["", "【引用推文】", quoted_text])
    if article_text:
        lines.extend(["", "【长文补充】", article_text])
    if comment_count <= 5:
        comment_lines = _normalize_text_list(
            [
                f"{_normalize_text(comment.get('author') or comment.get('username') or comment.get('screen_name'))}：{_normalize_text(comment.get('text') or comment.get('content') or comment.get('full_text') or comment.get('body'))}"
                for comment in comments
            ]
        )
        if comment_lines:
            lines.extend(["", "【评论区观点】", *comment_lines])
        else:
            lines.extend(
                [
                    "",
                    "【评论区观点】",
                    "未获取到评论；opencli thread 本次返回 0 条评论，可能是该推文无可见评论、登录态/权限限制或 X 分页未返回。",
                ]
            )
    elif comment_summary_text:
        lines.extend(["", "【评论区观点】", f"基于已抓取的 {comment_count} 条评论总结：{comment_summary_text}"])
    elif comment_count:
        fallback_lines = _normalize_text_list(
            [
                f"{_normalize_text(comment.get('author') or comment.get('username') or comment.get('screen_name'))}：{_normalize_text(comment.get('text') or comment.get('content') or comment.get('full_text') or comment.get('body'))}"
                for comment in comments[:5]
            ]
        )
        lines.extend(
            [
                "",
                "【评论区观点】",
                f"评论区观点总结失败，以下仅展示已抓取评论样本（共 {comment_count} 条）。",
                *fallback_lines,
            ]
        )

    content = "\n".join(part for part in lines if part is not None).strip()
    media_images = _build_twitter_media_images(main_tweet, quoted)
    cached_images: list[dict] = []
    if media_images:
        conn = db_conn()
        try:
            for image in media_images:
                cached = _cache_twitter_image(conn, image["url"])
                if cached:
                    cached_images.append({**image, **cached})
                else:
                    cached_images.append(image)
            _cleanup_media_cache(conn)
            conn.commit()
        finally:
            conn.close()
    else:
        cached_images = media_images
    payload = {
        "source": "Twitter/X",
        "tweet": main_tweet,
        "quoted_tweet": quoted or None,
        "comments": comments,
        "comment_count": comment_count,
        "article": article_record or None,
        "article_error": article_error or None,
        "comment_summary_error": comment_summary_error or None,
        "media_images": cached_images,
    }
    return (
        True,
        {
            "source": "Twitter/X",
            "title": _normalize_text(main_tweet.get("title")) or _normalize_text(main_tweet.get("author")) or "Twitter/X",
            "author": _normalize_text(main_tweet.get("author") or main_tweet.get("username") or main_tweet.get("screen_name")),
            "published_at": _normalize_text(main_tweet.get("published_at") or main_tweet.get("created_at") or main_tweet.get("date") or main_tweet.get("time")),
            "content": content,
            "content_length": len(content),
            "raw_json": json.dumps(payload, ensure_ascii=False),
        },
        "",
    )


def run_opencli_detail(url: str) -> tuple[bool, dict, str]:
    route = resolve_detail_route(url)
    if not route:
        return False, {}, "UNSUPPORTED_URL"
    source = route["source"]
    command = route["command"]
    timeout = int(route.get("timeout", 30))
    if source == "Twitter/X":
        return run_opencli_twitter_detail(url)

    parsed_url = urlparse(url)
    if source == "Bloomberg" and "/news/videos/" in parsed_url.path:
        return False, {}, "SKIPPED_SOURCE: BLOOMBERG_VIDEO"

    cmd = [*command, url, "-f", "json"]
    ok, parsed, error = _run_opencli_json_command(cmd, timeout)
    if not ok:
        return False, {}, error

    record = parsed[0] if isinstance(parsed, list) and parsed else parsed
    if not isinstance(record, dict):
        return False, {}, "EMPTY_RESULT"

    if record.get("status") == "failed":
        code = record.get("error_code") or "FETCH_FAILED"
        reason = record.get("reason") or ""
        return False, {}, f"{code}: {reason}".strip()

    content = (record.get("content") or record.get("body") or record.get("body_text") or "").strip()
    if len(content) < 200:
        return False, {}, f"CONTENT_TOO_SHORT: {len(content)}"

    normalized = {
        "source": source,
        "title": (record.get("title") or record.get("headline") or "").strip(),
        "author": (record.get("author") or record.get("authors") or record.get("byline") or "").strip(),
        "published_at": (record.get("published_at") or record.get("date") or record.get("time") or record.get("publish_time") or "").strip(),
        "content": content,
        "content_length": int(record.get("content_length") or len(content)),
        "raw_json": json.dumps(record, ensure_ascii=False),
    }
    return True, normalized, ""


def process_pending_jobs_once() -> bool:
    conn = db_conn()
    try:
        job = conn.execute(
            """
            SELECT url, item_id, source, attempts
            FROM detail_jobs
            WHERE status='pending'
            ORDER BY queued_at ASC
            LIMIT 1
            """
        ).fetchone()
        if not job:
            return False

        started = now_ts()
        with conn:
            conn.execute(
                "UPDATE detail_jobs SET status='running', started_at=?, updated_at=? WHERE url=?",
                (started, started, job["url"]),
            )

        ok, detail, error = run_opencli_detail(job["url"])
        finished = now_ts()
        with conn:
            if ok:
                conn.execute(
                    """
                    INSERT INTO article_details(
                      url, source, title, author, published_at, content,
                      content_length, raw_json, fetched_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                      source=excluded.source,
                      title=excluded.title,
                      author=excluded.author,
                      published_at=excluded.published_at,
                      content=excluded.content,
                      content_length=excluded.content_length,
                      raw_json=excluded.raw_json,
                      fetched_at=excluded.fetched_at,
                      updated_at=excluded.updated_at
                    """,
                    (
                        job["url"],
                        detail["source"],
                        detail["title"],
                        detail["author"],
                        detail["published_at"],
                        detail["content"],
                        detail["content_length"],
                        detail["raw_json"],
                        finished,
                        finished,
                    ),
                )
                conn.execute(
                    """
                    UPDATE detail_jobs
                    SET status='success',
                        last_error=NULL,
                        finished_at=?,
                        updated_at=?
                    WHERE url=?
                    """,
                    (finished, finished, job["url"]),
                )
                if detail["source"] != "Twitter/X":
                    enqueue_ai_job(conn, job["url"])
            else:
                attempts = int(job["attempts"] or 0) + 1
                conn.execute(
                    """
                    UPDATE detail_jobs
                    SET status='failed',
                        attempts=?,
                        last_error=?,
                        finished_at=?,
                        updated_at=?
                    WHERE url=?
                    """,
                    (attempts, error[:500], finished, finished, job["url"]),
                )
        return True
    finally:
        conn.close()


def enqueue_ai_job(conn: sqlite3.Connection, url: str) -> bool:
    ts = now_ts()
    existing_ai = conn.execute("SELECT url FROM article_ai WHERE url=?", (url,)).fetchone()
    if existing_ai:
        conn.execute(
            """
            INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
            VALUES (?, 'success', 0, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              status='success',
              last_error=NULL,
              updated_at=excluded.updated_at
            """,
            (url, ts, ts),
        )
        return False

    row = conn.execute("SELECT status FROM ai_jobs WHERE url=?", (url,)).fetchone()
    if row and row["status"] in ("pending", "running", "success"):
        conn.execute("UPDATE ai_jobs SET updated_at=? WHERE url=?", (ts, url))
        return False

    conn.execute(
        """
        INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
        VALUES (?, 'pending', 0, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
          status='pending',
          queued_at=excluded.queued_at,
          updated_at=excluded.updated_at
        """,
        (url, ts, ts),
    )
    return True


def process_pending_ai_once() -> bool:
    conn = db_conn()
    try:
        job = conn.execute(
            """
            SELECT url, attempts
            FROM ai_jobs
            WHERE status='pending'
            ORDER BY queued_at ASC
            LIMIT 1
            """
        ).fetchone()
        if not job:
            return False

        detail = conn.execute(
            "SELECT title, source, content FROM article_details WHERE url=?",
            (job["url"],),
        ).fetchone()
        if not detail or not (detail["content"] or "").strip():
            failed = now_ts()
            with conn:
                conn.execute(
                    """
                    UPDATE ai_jobs
                    SET status='failed', attempts=?, last_error=?, finished_at=?, updated_at=?
                    WHERE url=?
                    """,
                    (int(job["attempts"] or 0) + 1, "MISSING_ARTICLE_DETAILS", failed, failed, job["url"]),
                )
            return True

        started = now_ts()
        with conn:
            conn.execute(
                "UPDATE ai_jobs SET status='running', started_at=?, updated_at=? WHERE url=?",
                (started, started, job["url"]),
            )

        ok = False
        payload: dict = {}
        error = ""
        try:
            llm_settings = current_runtime_settings()["llm"]
            if (detail["source"] or "").strip() == "Twitter/X":
                payload = generate_body_translation_only(
                    title=(detail["title"] or "").strip(),
                    source=(detail["source"] or "").strip(),
                    content=(detail["content"] or "").strip(),
                    model=llm_settings["translation"]["model"],
                )
            else:
                payload = generate_article_ai(
                    title=(detail["title"] or "").strip(),
                    source=(detail["source"] or "").strip(),
                    content=(detail["content"] or "").strip(),
                    model=llm_settings["translation"]["model"],
                )
            ok = True
        except LLMClientError as exc:
            primary_error = str(exc)
            try:
                payload = generate_codex_fallback_translation(
                    title=(detail["title"] or "").strip(),
                    source=(detail["source"] or "").strip(),
                    content=(detail["content"] or "").strip(),
                    model=(llm_settings.get("codex_chat", {}).get("model") or "").strip(),
                )
                if (detail["source"] or "").strip() == "Twitter/X":
                    payload["key_points_zh"] = []
                    payload["conclusion_zh"] = ""
                ok = True
            except LLMClientError as fallback_exc:
                error = f"{primary_error} | {fallback_exc}"
        except Exception as exc:
            error = f"AI_UNKNOWN_ERROR: {exc}"

        finished = now_ts()
        with conn:
            if ok:
                conn.execute(
                    """
                    INSERT INTO article_ai(
                      url, model, key_points_zh, conclusion_zh, body_zh, raw_json, generated_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                      model=excluded.model,
                      key_points_zh=excluded.key_points_zh,
                      conclusion_zh=excluded.conclusion_zh,
                      body_zh=excluded.body_zh,
                      raw_json=excluded.raw_json,
                      generated_at=excluded.generated_at,
                      updated_at=excluded.updated_at
                    """,
                    (
                        job["url"],
                        payload.get("model", "deepseek-chat"),
                        json.dumps(payload.get("key_points_zh", []), ensure_ascii=False),
                        payload.get("conclusion_zh", ""),
                        payload.get("body_zh", ""),
                        payload.get("raw_json", "{}"),
                        finished,
                        finished,
                    ),
                )
                conn.execute(
                    """
                    UPDATE ai_jobs
                    SET status='success', last_error=NULL, finished_at=?, updated_at=?
                    WHERE url=?
                    """,
                    (finished, finished, job["url"]),
                )
            else:
                conn.execute(
                    """
                    UPDATE ai_jobs
                    SET status='failed', attempts=?, last_error=?, finished_at=?, updated_at=?
                    WHERE url=?
                    """,
                    (int(job["attempts"] or 0) + 1, error[:500], finished, finished, job["url"]),
                )
        return True
    finally:
        conn.close()


def detail_worker_loop() -> None:
    while not WORKER_STOP.is_set():
        processed = False
        try:
            processed = process_pending_jobs_once()
        except Exception:
            pass
        if not processed:
            try:
                processed = process_pending_ai_once()
            except Exception:
                pass
        if processed:
            time.sleep(2)
        else:
            WORKER_STOP.wait(2)


def start_detail_worker() -> None:
    global WORKER_THREAD
    with DETAIL_LOCK:
        if WORKER_THREAD and WORKER_THREAD.is_alive():
            return
        WORKER_STOP.clear()
        WORKER_THREAD = threading.Thread(target=detail_worker_loop, name="detail-worker", daemon=True)
        WORKER_THREAD.start()


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/daily-briefings")
def api_daily_briefings():
    months, total = load_daily_briefing_index()
    return jsonify(
        {
            "ok": True,
            "months": months,
            "total": total,
        }
    )


@app.get("/api/daily-briefings/<date_key>")
def api_daily_briefing_detail(date_key: str):
    try:
        normalized = parse_daily_briefing_date(date_key)
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_date"}), 400

    path = find_daily_briefing_path(normalized)
    if not path:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({"ok": True, "briefing": parse_daily_briefing_file(path)})


@app.get("/api/news")
def api_news():
    q = (request.args.get("q") or "").strip()
    read_filter = (request.args.get("read_filter") or "all").strip().lower()
    collection = (request.args.get("collection") or "feed").strip().lower()
    source_filter = (request.args.get("source_filter") or "all").strip().lower()
    page = max(1, int(request.args.get("page", "1")))
    per = min(100, max(10, int(request.args.get("per", "30"))))
    cursor_mode = use_feed_unread_cursor_paging(collection, read_filter)
    try:
        sort_order = parse_news_sort_order(request.args)
        cursor = parse_feed_unread_cursor(request.args) if cursor_mode else None
    except ValueError as exc:
        error = "invalid_sort_order" if str(exc) == "invalid_sort_order" else "invalid_cursor"
        return jsonify({"ok": False, "error": error}), 400
    join_sql = """
    LEFT JOIN item_state st ON st.item_id = items.id
    LEFT JOIN detail_jobs dj ON dj.url = items.url
    LEFT JOIN article_details ad ON ad.url = items.url
    LEFT JOIN article_notes an ON an.url = items.url
    """
    where_sql, args = _build_news_where_clause(q, read_filter, collection, source_filter)
    order_by_sql = news_order_by_sql(collection, sort_order)
    ascending_order = collection in ("feed", "read_later")
    if sort_order == "reverse":
        ascending_order = not ascending_order

    conn = db_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM items {join_sql} {where_sql}",
            args,
        ).fetchone()[0]

        date_count_rows = conn.execute(
            f"""
            SELECT {ITEM_DATE_SQL} AS date_key, COUNT(DISTINCT items.id) AS total
            FROM items
            {join_sql}
            {where_sql}
            GROUP BY date_key
            ORDER BY date_key DESC
            """,
            args,
        ).fetchall()

        base_select_sql = f"""
        SELECT DISTINCT items.id, items.source_file, items.item_order, items.published_at,
               items.date, items.time, items.source, items.source_type,
               items.source_name, items.title, items.summary, items.url,
               st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
               dj.status AS detail_status,
               dj.last_error AS detail_error,
               CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
               an.note AS note_preview_source,
               CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
               aj.status AS ai_status,
               aj.last_error AS ai_error,
               CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready,
               (
                 SELECT COUNT(*)
                 FROM news_reminders nr
                 WHERE nr.item_id = items.id AND nr.status = 'active'
               ) AS active_reminder_count,
               (
                 SELECT COUNT(*)
                 FROM news_reminders nr
                 WHERE nr.item_id = items.id
                   AND nr.status = 'active'
                   AND nr.remind_at <= datetime('now', 'localtime')
               ) AS due_reminder_count,
               (
                 SELECT MIN(nr.remind_at)
                 FROM news_reminders nr
                 WHERE nr.item_id = items.id AND nr.status = 'active'
               ) AS next_remind_at,
               {ITEM_DATE_SQL} AS date_key
        FROM items
        {join_sql}
        LEFT JOIN ai_jobs aj ON aj.url = items.url
        LEFT JOIN article_ai aa ON aa.url = items.url
        {where_sql}
        """

        has_more = False
        next_cursor = None
        if cursor_mode:
            cursor_clause, cursor_args = build_feed_unread_cursor_clause(cursor, ascending_order)
            raw_rows = conn.execute(
                f"""
                {base_select_sql}
                {cursor_clause}
                ORDER BY {order_by_sql}
                LIMIT ?
                """,
                [*args, *cursor_args, per + 1],
            ).fetchall()
            has_more = len(raw_rows) > per
            rows = raw_rows[:per]
            if rows and has_more:
                last = rows[-1]
                next_cursor = {
                    "date_key": last["date_key"],
                    "published_at": last["published_at"],
                    "id": str(last["id"]),
                }
        else:
            offset = (page - 1) * per
            rows = conn.execute(
                f"""
                {base_select_sql}
                ORDER BY {order_by_sql}
                LIMIT ? OFFSET ?
                """,
                [*args, per, offset],
            ).fetchall()
        urls = [r["url"] for r in rows if r["url"]]
        market_tags_map = load_market_tags_map(conn, urls)
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    date_counts = {
        row["date_key"]: row["total"]
        for row in date_count_rows
        if row["date_key"]
    }
    items = serialize_news_rows(items, market_tags_map)
    pages = max(1, math.ceil(total / per)) if total else 1
    if cursor_mode:
        pages = max(page, pages)
    return jsonify(
        {
            "items": items,
            "total": total,
            "date_counts": date_counts,
            "page": page,
            "pages": pages,
            "has_more": has_more if cursor_mode else page < pages,
            "next_cursor": next_cursor if cursor_mode else None,
            "sort_order": sort_order,
        }
    )


@app.get("/api/ideas")
def api_ideas():
    page = max(1, int(request.args.get("page", "1")))
    per = min(100, max(10, int(request.args.get("per", "30"))))
    try:
        sort_order = parse_news_sort_order(request.args)
        idea_type = parse_idea_type_filter(request.args)
    except ValueError as exc:
        error = "invalid_idea_type" if str(exc) == "invalid_idea_type" else "invalid_sort_order"
        return jsonify({"ok": False, "error": error}), 400

    conn = db_conn()
    try:
        ideas = load_idea_rows(conn, idea_type, sort_order)
    finally:
        conn.close()

    total = len(ideas)
    date_counts: dict[str, int] = {}
    for idea in ideas:
        date_key = idea.get("date_key") or "unknown"
        date_counts[date_key] = date_counts.get(date_key, 0) + 1

    offset = (page - 1) * per
    page_items = ideas[offset: offset + per]
    pages = max(1, math.ceil(total / per)) if total else 1
    return jsonify(
        {
            "items": page_items,
            "total": total,
            "date_counts": date_counts,
            "page": page,
            "pages": pages,
            "has_more": page < pages,
            "sort_order": sort_order,
            "type": idea_type,
        }
    )


@app.get("/api/news/status")
def api_news_status():
    raw_ids = (request.args.get("ids") or "").strip()
    if not raw_ids:
        return jsonify({"ok": False, "error": "missing_ids"}), 400
    ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
    if not ids:
        return jsonify({"ok": False, "error": "invalid_ids"}), 400
    if len(ids) > 50:
        return jsonify({"ok": False, "error": "too_many_ids"}), 400

    placeholders = ",".join(["?"] * len(ids))
    conn = db_conn()
    try:
        rows = conn.execute(
            f"""
            SELECT items.id,
                   st.favorite_at,
                   st.read_later_at,
                   st.read_later_done_at,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS active_reminder_count,
                   (
                     SELECT COUNT(*)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id
                       AND nr.status = 'active'
                       AND nr.remind_at <= datetime('now', 'localtime')
                   ) AS due_reminder_count,
                   (
                     SELECT MIN(nr.remind_at)
                     FROM news_reminders nr
                     WHERE nr.item_id = items.id AND nr.status = 'active'
                   ) AS next_remind_at,
                   dj.status AS detail_status,
                   dj.last_error AS detail_error,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
                   aj.status AS ai_status
            FROM items
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN detail_jobs dj ON dj.url = items.url
            LEFT JOIN article_details ad ON ad.url = items.url
            LEFT JOIN ai_jobs aj ON aj.url = items.url
            WHERE items.id IN ({placeholders})
            """,
            ids,
        ).fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "items": [dict(r) for r in rows]})


@app.get("/api/tracked-topics")
def api_tracked_topics():
    conn = db_conn()
    try:
        topics = load_tracked_topics(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "items": topics})


@app.post("/api/tracked-topics/rule-draft")
def api_tracked_topic_rule_draft():
    body = request.get_json(silent=True) or {}
    title = " ".join(str(body.get("title") or "").split()).strip()
    description = str(body.get("description") or "").strip()
    if not title:
        return jsonify({"ok": False, "error": "empty_title"}), 400
    if len(title) > 120:
        return jsonify({"ok": False, "error": "title_too_long"}), 400
    if len(description) > 1000:
        return jsonify({"ok": False, "error": "description_too_long"}), 400

    llm_settings = current_runtime_settings()["llm"]
    model_name = (llm_settings["translation"].get("model") or "").strip()
    try:
        payload = generate_tracked_topic_rule_draft(
            title=title,
            description=description,
            model=model_name,
        )
        draft = sanitize_tracked_rule_draft(payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except LLMClientError as exc:
        return jsonify({"ok": False, "error": "tracked_rule_draft_generate_failed", "detail": str(exc)}), 502

    return jsonify(
        {
            "ok": True,
            "draft": draft,
            "model": payload.get("model", model_name or "deepseek-chat"),
            "version": TRACKED_RULE_DRAFT_VERSION,
        }
    )


@app.post("/api/tracked-topics")
def api_tracked_topics_create():
    body = request.get_json(silent=True) or {}
    try:
        payload = parse_tracked_topic_body(body, partial=False)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    ts = now_ts()
    conn = db_conn()
    try:
        with conn:
            cur = conn.execute(
                """
                INSERT INTO tracked_topics(
                  title, description, keywords_json, exclude_keywords_json, rules_json,
                  scope, active, last_incremental_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["title"],
                    payload.get("description") or "",
                    json.dumps(payload["keywords"], ensure_ascii=False),
                    json.dumps(payload["exclude_keywords"], ensure_ascii=False),
                    json.dumps(payload["rules"], ensure_ascii=False),
                    payload["scope"],
                    1 if payload["active"] else 0,
                    ts,
                    ts,
                    ts,
                ),
            )
            topic = load_tracked_topic(conn, int(cur.lastrowid))
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic})


@app.patch("/api/tracked-topics/<int:topic_id>")
def api_tracked_topics_update(topic_id: int):
    body = request.get_json(silent=True) or {}
    try:
        payload = parse_tracked_topic_body(body, partial=True)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not payload:
        return jsonify({"ok": False, "error": "empty_patch"}), 400

    conn = db_conn()
    try:
        existing = load_tracked_topic(conn, topic_id)
        if not existing:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        title = payload.get("title", existing["title"])
        description = payload.get("description", existing["description"])
        rules = payload.get("rules", existing["rules"])
        keywords = payload.get("keywords", existing["keywords"])
        exclude_keywords = payload.get("exclude_keywords", existing["exclude_keywords"])
        scope = payload.get("scope", existing["scope"])
        active = payload.get("active", bool(existing["active"]))
        ts = now_ts()
        with conn:
            conn.execute(
                """
                UPDATE tracked_topics
                SET title=?,
                    description=?,
                    keywords_json=?,
                    exclude_keywords_json=?,
                    rules_json=?,
                    scope=?,
                    active=?,
                    updated_at=?
                WHERE id=?
                """,
                (
                    title,
                    description,
                    json.dumps(keywords, ensure_ascii=False),
                    json.dumps(exclude_keywords, ensure_ascii=False),
                    json.dumps(rules, ensure_ascii=False),
                    scope,
                    1 if active else 0,
                    ts,
                    topic_id,
                ),
            )
            topic = load_tracked_topic(conn, topic_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic})


@app.delete("/api/tracked-topics/<int:topic_id>")
def api_tracked_topics_delete(topic_id: int):
    conn = db_conn()
    try:
        existing = load_tracked_topic(conn, topic_id)
        if not existing:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        with conn:
            conn.execute("DELETE FROM tracked_topic_items WHERE topic_id=?", (topic_id,))
            conn.execute("DELETE FROM tracked_topics WHERE id=?", (topic_id,))
    finally:
        conn.close()
    return jsonify({"ok": True, "deleted_id": topic_id})


@app.get("/api/tracked-topics/<int:topic_id>/items")
def api_tracked_topic_items(topic_id: int):
    conn = db_conn()
    try:
        topic = load_tracked_topic(conn, topic_id)
        if not topic:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        items = tracked_topic_timeline_items(conn, topic_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic, "items": items, "total": len(items)})


@app.get("/api/tracked-topics/<int:topic_id>/daily-summaries")
def api_tracked_topic_daily_summaries(topic_id: int):
    conn = db_conn()
    try:
        topic = load_tracked_topic(conn, topic_id)
        if not topic:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        days = load_tracked_topic_daily_summaries(conn, topic)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic, "days": days, "total": len(days)})


@app.post("/api/tracked-topics/<int:topic_id>/daily-summaries/<summary_date>/generate")
def api_tracked_topic_daily_summary_generate(topic_id: int, summary_date: str):
    try:
        normalized_date = datetime.strptime((summary_date or "").strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_summary_date"}), 400

    conn = db_conn()
    try:
        topic = load_tracked_topic(conn, topic_id)
        if not topic:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        rows = [dict(row) for row in tracked_daily_summary_source_rows(conn, topic_id, date=normalized_date)]
        if not rows:
            return jsonify({"ok": False, "error": "summary_source_items_not_found"}), 404
        item_ids_hash = build_tracked_daily_summary_hash(rows)
        materials = build_tracked_daily_summary_materials(topic, normalized_date, rows)
        llm_settings = current_runtime_settings()["llm"]
        model_name = (llm_settings["translation"].get("model") or "").strip()

        try:
            payload = generate_tracked_topic_daily_summary(
                topic_title=(topic.get("title") or "").strip(),
                summary_date=normalized_date,
                materials=materials,
                news_count=len(rows),
                max_summary_chars=tracked_daily_summary_char_limit(len(rows)),
                model=model_name,
            )
        except LLMClientError as exc:
            with conn:
                save_tracked_daily_summary(
                    conn,
                    topic_id=topic_id,
                    date=normalized_date,
                    item_ids_hash=item_ids_hash,
                    status="failed",
                    summary_text="",
                    error=str(exc),
                    model=model_name or "deepseek-chat",
                    raw_json="{}",
                )
            summary_row = tracked_daily_summary_row(conn, topic_id, normalized_date)
            day = serialize_tracked_daily_summary_group(topic, normalized_date, rows, summary_row)
            return jsonify(
                {
                    "ok": False,
                    "error": "daily_summary_generate_failed",
                    "detail": str(exc),
                    "day": day,
                }
            ), 502

        with conn:
            save_tracked_daily_summary(
                conn,
                topic_id=topic_id,
                date=normalized_date,
                item_ids_hash=item_ids_hash,
                status="success",
                summary_text=enforce_daily_summary_char_limit(
                    payload.get("summary_text", ""),
                    tracked_daily_summary_char_limit(len(rows)),
                ),
                error="",
                model=payload.get("model", model_name or "deepseek-chat"),
                raw_json=payload.get("raw_json", "{}"),
            )
        summary_row = tracked_daily_summary_row(conn, topic_id, normalized_date)
        day = serialize_tracked_daily_summary_group(topic, normalized_date, rows, summary_row)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic, "day": day})


@app.post("/api/tracked-topics/<int:topic_id>/backfill")
def api_tracked_topic_backfill(topic_id: int):
    body = request.get_json(silent=True) or {}
    try:
        mode = tracked_backfill_mode_value(body.get("mode"))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    conn = db_conn()
    try:
        topic = load_tracked_topic(conn, topic_id)
        if not topic:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        date_after = None if mode in {"all_important", "all_news"} else datetime.now().strftime("%Y-%m-%d")
        if mode == "recent_important":
            date_after = (datetime.now().date().fromordinal(datetime.now().date().toordinal() - 179)).strftime("%Y-%m-%d")
        candidate_rows = tracked_topic_candidate_rows(
            conn,
            scope="all" if mode == "all_news" else "important",
            date_after=date_after,
        )
        with conn:
            matched = run_tracked_topic_match(
                conn,
                topic=topic,
                candidate_rows=candidate_rows,
                replace_existing_auto_matches=True,
            )
            topic = load_tracked_topic(conn, topic_id)
            items = tracked_topic_timeline_items(conn, topic_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic, "items": items, "matched_count": matched, "mode": mode})


@app.post("/api/tracked-topics/<int:topic_id>/items")
def api_tracked_topic_item_create(topic_id: int):
    body = request.get_json(silent=True) or {}
    item_id = str(body.get("item_id") or "").strip()
    if not item_id:
        return jsonify({"ok": False, "error": "missing_item_id"}), 400
    if item_id.startswith("trend_note:"):
        return jsonify({"ok": False, "error": "invalid_item_id"}), 400

    conn = db_conn()
    try:
        topic = load_tracked_topic(conn, topic_id)
        if not topic:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        item = conn.execute("SELECT id, url FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        with conn:
            upsert_tracked_topic_match(
                conn,
                topic_id=topic_id,
                item_row=item,
                match_method="manual",
                score=0,
                reason="手动加入",
                manual_added_at=now_ts(),
                clear_hidden=True,
            )
            conn.execute(
                "UPDATE tracked_topics SET updated_at=? WHERE id=?",
                (now_ts(), topic_id),
            )
            topic = load_tracked_topic(conn, topic_id)
        item_row = tracked_topic_item_status(conn, topic_id, item_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "topic": topic, "item_id": item_id, "tracked_item": dict(item_row) if item_row else None})


@app.patch("/api/tracked-topics/<int:topic_id>/items/<item_id>")
def api_tracked_topic_item_update(topic_id: int, item_id: str):
    body = request.get_json(silent=True) or {}
    hidden = body.get("hidden")
    if not isinstance(hidden, bool):
        return jsonify({"ok": False, "error": "invalid_hidden"}), 400

    conn = db_conn()
    try:
        topic = load_tracked_topic(conn, topic_id)
        if not topic:
            return jsonify({"ok": False, "error": "topic_not_found"}), 404
        existing = tracked_topic_item_status(conn, topic_id, item_id)
        if not existing:
            return jsonify({"ok": False, "error": "tracked_item_not_found"}), 404
        ts = now_ts()
        with conn:
            conn.execute(
                """
                UPDATE tracked_topic_items
                SET hidden_at=?,
                    updated_at=?
                WHERE topic_id=? AND item_id=?
                """,
                (ts if hidden else None, ts, topic_id, item_id),
            )
            conn.execute("UPDATE tracked_topics SET updated_at=? WHERE id=?", (ts, topic_id))
        tracked_item = tracked_topic_item_status(conn, topic_id, item_id)
    finally:
        conn.close()
    return jsonify({"ok": True, "tracked_item": dict(tracked_item) if tracked_item else None})


@app.get("/api/reminders")
def api_reminders():
    status = (request.args.get("status") or "active").strip().lower()
    if status not in {"active", "done", "dismissed", "all"}:
        return jsonify({"ok": False, "error": "invalid_status"}), 400

    conn = db_conn()
    try:
        summary = load_reminder_summary(conn)
        where_sql = ""
        args: list[str] = []
        order_by_sql = "nr.updated_at DESC, nr.id DESC"
        if status != "all":
            where_sql = "WHERE nr.status = ?"
            args.append(status)
        if status in {"active", "all"}:
            order_by_sql = """
            CASE
              WHEN nr.status = 'active' AND nr.remind_at <= datetime('now', 'localtime') THEN 0
              WHEN nr.status = 'active' THEN 1
              WHEN nr.status = 'done' THEN 2
              ELSE 3
            END ASC,
            CASE WHEN nr.status = 'active' THEN nr.remind_at ELSE nr.updated_at END ASC,
            nr.id DESC
            """
        rows = conn.execute(
            f"""
            SELECT nr.*,
                   CASE WHEN items.id IS NULL THEN 0 ELSE 1 END AS item_exists
            FROM news_reminders nr
            LEFT JOIN items ON items.id = nr.item_id
            {where_sql}
            ORDER BY {order_by_sql}
            """,
            args,
        ).fetchall()
        reminders = serialize_reminder_rows(rows)
        item_map = load_news_item_map(
            conn,
            [reminder["item_id"] for reminder in reminders if reminder.get("item_exists")],
        )
    finally:
        conn.close()

    for reminder in reminders:
        reminder["item"] = item_map.get(reminder.get("item_id"))
    return jsonify({"ok": True, "items": reminders, "summary": summary})


@app.get("/api/reminders/summary")
def api_reminders_summary():
    conn = db_conn()
    try:
        summary = load_reminder_summary(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "summary": summary})


@app.get("/api/search")
def api_search():
    q = (request.args.get("q") or "").strip()
    range_value = (request.args.get("range") or "all").strip().lower()
    time_value = (request.args.get("time") or "all").strip().lower()
    page = max(1, int(request.args.get("page", "1")))
    per = min(100, max(10, int(request.args.get("per", "30"))))
    valid_ranges = {"all", "important", "notes", "market_tags", "detail_ready"}
    valid_times = {"all", "today", "7d", "30d"}
    if range_value not in valid_ranges:
        return jsonify({"ok": False, "error": "invalid_range"}), 400
    if time_value not in valid_times:
        return jsonify({"ok": False, "error": "invalid_time"}), 400
    if not q:
        return jsonify({"items": [], "total": 0, "date_counts": {}, "page": 1, "pages": 1})

    like = f"%{q}%"
    search_args = [like] * 9 + [like, like]
    join_sql = """
    LEFT JOIN item_state st ON st.item_id = items.id
    LEFT JOIN detail_jobs dj ON dj.url = items.url
    LEFT JOIN article_details ad ON ad.url = items.url
    LEFT JOIN article_notes an ON an.url = items.url
    LEFT JOIN ai_jobs aj ON aj.url = items.url
    LEFT JOIN article_ai aa ON aa.url = items.url
    """
    where_sql = """
    WHERE (
      items.title LIKE ? OR
      COALESCE(items.summary, '') LIKE ? OR
      COALESCE(items.source, '') LIKE ? OR
      COALESCE(items.source_name, '') LIKE ? OR
      COALESCE(ad.content, '') LIKE ? OR
      COALESCE(aa.body_zh, '') LIKE ? OR
      COALESCE(aa.key_points_zh, '') LIKE ? OR
      COALESCE(aa.conclusion_zh, '') LIKE ? OR
      COALESCE(an.note, '') LIKE ? OR
      EXISTS (
        SELECT 1
        FROM article_market_tags mt
        LEFT JOIN market_tag_definitions mtd ON mtd.key = mt.tag
        WHERE mt.url = items.url
          AND (mt.tag LIKE ? OR COALESCE(mtd.display_name, '') LIKE ?)
      )
    )
    """
    filter_sql, filter_args = _build_search_filter_clause(range_value, time_value)
    all_args = [*search_args, *filter_args]

    conn = db_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(DISTINCT items.id) FROM items {join_sql} {where_sql}{filter_sql}",
            all_args,
        ).fetchone()[0]

        date_count_rows = conn.execute(
            f"""
            SELECT {ITEM_DATE_SQL} AS date_key, COUNT(DISTINCT items.id) AS total
            FROM items
            {join_sql}
            {where_sql}{filter_sql}
            GROUP BY date_key
            ORDER BY date_key DESC
            """,
            all_args,
        ).fetchall()

        offset = (page - 1) * per
        rows = conn.execute(
            f"""
            SELECT DISTINCT items.id, items.source_file, items.item_order, items.published_at,
                   items.date, items.time, items.source, items.source_type,
                   items.source_name, items.title, items.summary, items.url,
                   st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
                   dj.status AS detail_status,
                   dj.last_error AS detail_error,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
                   an.note AS note_preview_source,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
                   aj.status AS ai_status,
                   aj.last_error AS ai_error,
                   CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready
            FROM items
            {join_sql}
            {where_sql}{filter_sql}
            ORDER BY {NON_FEED_NEWS_ORDER_BY_SQL}
            LIMIT ? OFFSET ?
            """,
            [*all_args, per, offset],
        ).fetchall()
        urls = [r["url"] for r in rows if r["url"]]
        market_tags_map = load_market_tags_map(conn, urls)
    finally:
        conn.close()

    items = serialize_news_rows([dict(r) for r in rows], market_tags_map)
    date_counts = {row["date_key"]: row["total"] for row in date_count_rows if row["date_key"]}
    pages = max(1, math.ceil(total / per)) if total else 1
    return jsonify({"items": items, "total": total, "date_counts": date_counts, "page": page, "pages": pages})


@app.get("/api/sources")
def api_sources():
    q = (request.args.get("q") or "").strip()
    read_filter = (request.args.get("read_filter") or "all").strip().lower()
    collection = (request.args.get("collection") or "feed").strip().lower()

    where = []
    args: list = []
    join_sql = """
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN article_details ad ON ad.url = items.url
    """
    if q:
        where.append("(items.title LIKE ? OR items.summary LIKE ? OR items.source LIKE ?)")
        like = f"%{q}%"
        args.extend([like, like, like])
    if collection == "read_later":
        if read_filter == "unread":
            where.append("st.read_later_at IS NOT NULL")
        elif read_filter == "read":
            where.append("(ad.url IS NOT NULL AND st.read_later_at IS NULL)")
        else:
            where.append("(st.read_later_at IS NOT NULL OR ad.url IS NOT NULL)")
    else:
        if read_filter == "unread":
            where.append("st.read_at IS NULL")
        elif read_filter == "read":
            where.append("st.read_at IS NOT NULL")
    if collection == "important":
        where.append("st.important_at IS NOT NULL")
    elif collection == "favorites":
        where.append("st.favorite_at IS NOT NULL")
    elif collection == "notes":
        where.append("EXISTS (SELECT 1 FROM article_notes an WHERE an.url = items.url)")
    elif collection == "market_tags":
        where.append("EXISTS (SELECT 1 FROM article_market_tags mt WHERE mt.url = items.url)")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = db_conn()
    try:
        rows = conn.execute(
            f"SELECT items.url, items.source_type, items.source FROM items {join_sql} {where_sql}",
            args,
        ).fetchall()
    finally:
        conn.close()

    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for r in rows:
        key = derive_source_key(r["url"], r["source_type"], r["source"])
        counts[key] = counts.get(key, 0) + 1
        labels.setdefault(key, source_label_for_key(key, r["source"]))

    known_order = ["reuters", "bloomberg", "techcrunch", "ars", "x"]
    ordered: list[dict] = []
    for key in known_order:
        if key in counts:
            ordered.append({"key": key, "label": SOURCE_LABELS[key], "count": counts[key]})

    unknown = [k for k in counts.keys() if k not in set(known_order)]
    unknown.sort(key=lambda x: labels.get(x, x))
    for key in unknown:
        ordered.append({"key": key, "label": labels.get(key, key), "count": counts[key]})

    return jsonify({"ok": True, "sources": ordered})


@app.get("/api/error-stats")
def api_error_stats():
    day = (request.args.get("day") or datetime.now().strftime("%Y-%m-%d")).strip()
    if len(day) != 10:
        return jsonify({"ok": False, "error": "invalid_day"}), 400
    days = load_error_stats(day)
    return jsonify({"ok": True, "day": day, "days": days})


@app.get("/api/release-notes")
def api_release_notes():
    return jsonify({"ok": True, "items": parse_release_notes()})


@app.get("/api/settings")
def api_settings():
    return jsonify({"ok": True, **serialize_runtime_settings()})


@app.put("/api/settings")
def api_settings_update():
    body = request.get_json(silent=True) or {}
    try:
        normalized = validate_runtime_settings(body)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    save_app_settings(normalized)
    return jsonify({"ok": True, **serialize_runtime_settings()})


@app.put("/api/settings/tracked-default-rule-params")
def api_settings_tracked_default_rule_params_update():
    body = request.get_json(silent=True) or {}
    params = body.get("default_rule_params")
    if not isinstance(params, dict):
        return jsonify({"ok": False, "error": "invalid_default_rule_params"}), 400
    settings = current_runtime_settings()
    settings["tracked"]["default_rule_params"] = tracked_default_rule_params(params)
    save_app_settings(settings)
    return jsonify({"ok": True, **serialize_runtime_settings()})


@app.put("/api/settings/secrets/<provider>")
def api_settings_secret_save(provider: str):
    body = request.get_json(silent=True) or {}
    try:
        save_provider_secret(provider, body.get("key"))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except SecretStoreError as exc:
        status = 503 if exc.code == "keychain_unavailable" else 500
        return jsonify({"ok": False, "error": exc.code}), status
    return jsonify({"ok": True, **serialize_runtime_settings()})


@app.delete("/api/settings/secrets/<provider>")
def api_settings_secret_delete(provider: str):
    try:
        remove_provider_secret(provider)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except SecretStoreError as exc:
        status = 503 if exc.code == "keychain_unavailable" else 500
        return jsonify({"ok": False, "error": exc.code}), status
    return jsonify({"ok": True, **serialize_runtime_settings()})


@app.get("/api/market-trends")
def api_market_trends():
    try:
        days = int(request.args.get("days", "7"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_days"}), 400
    days = min(30, max(3, days))

    conn = db_conn()
    try:
        active_tags = load_market_tag_definitions(conn, active_only=True)
        date_rows = conn.execute(
            f"""
            SELECT date_key
            FROM (
              SELECT DISTINCT {ITEM_DATE_SQL} AS date_key
              FROM items
              WHERE EXISTS (SELECT 1 FROM article_market_tags mt WHERE mt.url = items.url)
                AND {ITEM_DATE_SQL} IS NOT NULL
                AND {ITEM_DATE_SQL} != ''
              UNION
              SELECT DISTINCT date_key
              FROM market_trend_notes
            )
            ORDER BY date_key DESC
            LIMIT ?
            """,
            (days,),
        ).fetchall()
        latest_dates_desc = [r["date_key"] for r in date_rows]
        if not latest_dates_desc:
            return jsonify({
                "ok": True,
                "days": days,
                "dates": [],
                "rows": [],
                "tag_count": 0,
                "tagged_item_count": 0,
            })

        latest_dates = list(reversed(latest_dates_desc))
        placeholders = ",".join(["?"] * len(latest_dates_desc))
        agg_rows = conn.execute(
            f"""
            SELECT {ITEM_DATE_SQL} AS date_key,
                   mt.tag,
                   mt.direction,
                   COUNT(*) AS total,
                   MAX(CASE WHEN an.url IS NULL THEN 0 ELSE 1 END) AS has_item_note
            FROM items
            JOIN article_market_tags mt ON mt.url = items.url
            LEFT JOIN article_notes an ON an.url = items.url
            WHERE {ITEM_DATE_SQL} IN ({placeholders})
            GROUP BY date_key, mt.tag, mt.direction
            ORDER BY date_key ASC, mt.tag ASC, mt.direction ASC
            """,
            latest_dates_desc,
        ).fetchall()
        note_rows = conn.execute(
            f"""
            SELECT date_key, tag, direction, COUNT(*) AS total
            FROM market_trend_notes
            WHERE date_key IN ({placeholders})
            GROUP BY date_key, tag, direction
            ORDER BY date_key ASC, tag ASC, direction ASC
            """,
            latest_dates_desc,
        ).fetchall()
        tagged_item_count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM items
            WHERE EXISTS (SELECT 1 FROM article_market_tags mt WHERE mt.url = items.url)
              AND {ITEM_DATE_SQL} IN ({placeholders})
            """,
            latest_dates_desc,
        ).fetchone()[0]
    finally:
        conn.close()

    counts: dict[tuple[str, str], dict[str, int]] = {}
    item_note_flags: dict[tuple[str, str], dict[str, int]] = {}
    note_counts: dict[tuple[str, str], dict[str, int]] = {}
    non_zero_tags: set[str] = set()
    for row in agg_rows:
        date_key = row["date_key"]
        tag = row["tag"]
        direction = row["direction"]
        total = int(row["total"] or 0)
        non_zero_tags.add(tag)
        slot = counts.setdefault((tag, date_key), {"bullish": 0, "bearish": 0})
        slot[direction] = total
        note_flag_slot = item_note_flags.setdefault((tag, date_key), {"bullish": 0, "bearish": 0})
        note_flag_slot[direction] = int(row["has_item_note"] or 0)
    for row in note_rows:
        date_key = row["date_key"]
        tag = row["tag"]
        direction = row["direction"]
        total = int(row["total"] or 0)
        non_zero_tags.add(tag)
        slot = note_counts.setdefault((tag, date_key), {"bullish": 0, "bearish": 0})
        slot[direction] = total

    tags_in_use = [tag for tag in active_tags if tag["key"] in non_zero_tags]
    rows_payload = []
    for tag_def in tags_in_use:
        tag_key = tag_def["key"]
        values = []
        row_total = 0
        for date_key in latest_dates:
            slot = counts.get((tag_key, date_key), {"bullish": 0, "bearish": 0})
            note_slot = note_counts.get((tag_key, date_key), {"bullish": 0, "bearish": 0})
            item_note_slot = item_note_flags.get((tag_key, date_key), {"bullish": 0, "bearish": 0})
            bullish = int(slot.get("bullish") or 0)
            bearish = int(slot.get("bearish") or 0)
            bullish_notes = int(note_slot.get("bullish") or 0)
            bearish_notes = int(note_slot.get("bearish") or 0)
            row_total += bullish + bearish
            values.append(
                {
                    "date": date_key,
                    "bullish": bullish,
                    "bearish": bearish,
                    "bullish_notes": bullish_notes,
                    "bearish_notes": bearish_notes,
                    "bullish_has_item_note": int(item_note_slot.get("bullish") or 0),
                    "bearish_has_item_note": int(item_note_slot.get("bearish") or 0),
                }
            )
        rows_payload.append(
            {
                "tag": tag_key,
                "tag_key": tag_key,
                "tag_label": tag_def["display_name"],
                "values": values,
                "total": row_total,
            }
        )

    return jsonify(
        {
            "ok": True,
            "days": days,
            "dates": latest_dates,
            "rows": rows_payload,
            "tag_count": len(rows_payload),
            "tagged_item_count": int(tagged_item_count or 0),
        }
    )


@app.get("/api/market-trends/detail")
def api_market_trends_detail():
    date_key = (request.args.get("date") or "").strip()
    tag = (request.args.get("tag") or "").strip()
    direction = (request.args.get("direction") or "").strip().lower()
    if not date_key:
        return jsonify({"ok": False, "error": "missing_date"}), 400
    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key, display_name, active FROM market_tag_definitions WHERE key=?",
            (tag,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "invalid_tag"}), 400
        if direction not in MARKET_DIRECTIONS:
            return jsonify({"ok": False, "error": "invalid_direction"}), 400
        rows = conn.execute(
            f"""
            SELECT items.id, items.source_file, items.item_order, items.published_at,
                   items.date, items.time, items.source, items.source_type,
                   items.source_name, items.title, items.summary, items.url,
                   st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note
            FROM items
            JOIN article_market_tags mt ON mt.url = items.url
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN article_notes an ON an.url = items.url
            WHERE {ITEM_DATE_SQL} = ?
              AND mt.tag = ?
              AND mt.direction = ?
            ORDER BY items.published_at ASC, items.id ASC
            """,
            (date_key, tag, direction),
        ).fetchall()
        urls = [r["url"] for r in rows if r["url"]]
        notes_map = load_notes_map(conn, urls)
        market_tags_map = load_market_tags_map(conn, urls)
        trend_notes = load_trend_notes_map(conn, [(date_key, tag_def["key"], direction)]).get((date_key, tag_def["key"], direction), [])
    finally:
        conn.close()

    items = []
    for row in rows:
        item = dict(row)
        url = item.get("url") or ""
        note = notes_map.get(url)
        tags = market_tags_map.get(url, [])
        item["note"] = note
        item["has_note"] = 1 if note else 0
        item["note_preview"] = build_note_preview(note["note"] if note else None)
        item["market_tags"] = tags
        item["has_market_tags"] = 1 if tags else 0
        item["source_key"] = derive_source_key(item.get("url"), item.get("source_type"), item.get("source"))
        key, label = derive_date_meta(item.get("published_at"), item.get("date"))
        item["date_key"] = key
        item["date_label"] = label
        items.append(item)

    return jsonify(
        {
            "ok": True,
            "view": "cell",
            "date": date_key,
            "tag": tag_def["display_name"],
            "tag_key": tag_def["key"],
            "direction": direction,
            "trend_notes": trend_notes,
            "trend_note_total": len(trend_notes),
            "total": len(items),
            "items": items,
        }
    )


@app.get("/api/market-trends/tag-detail")
def api_market_trends_tag_detail():
    tag = (request.args.get("tag") or "").strip()
    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key, display_name, active FROM market_tag_definitions WHERE key=?",
            (tag,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "invalid_tag"}), 400

        item_rows = conn.execute(
            f"""
            SELECT items.id, items.source_file, items.item_order, items.published_at,
                   items.date, items.time, items.source, items.source_type,
                   items.source_name, items.title, items.summary, items.url,
                   st.read_at, st.important_at, st.read_later_at, st.read_later_done_at, st.favorite_at,
                   amt.direction,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note
            FROM items
            JOIN article_market_tags amt ON amt.url = items.url
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN article_notes an ON an.url = items.url
            WHERE amt.tag = ?
            ORDER BY {ITEM_DATE_SQL} DESC, items.published_at DESC, items.id DESC
            """,
            (tag,),
        ).fetchall()
        urls = [r["url"] for r in item_rows if r["url"]]
        notes_map = load_notes_map(conn, urls)
        market_tags_map = load_market_tags_map(conn, urls)

        trend_note_rows = conn.execute(
            """
            SELECT mtn.id,
                   mtn.date_key,
                   mtn.tag,
                   mtn.direction,
                   mtn.note,
                   mtn.created_at,
                   mtn.updated_at,
                   mtd.display_name
            FROM market_trend_notes mtn
            LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
            WHERE mtn.tag = ?
            ORDER BY mtn.date_key DESC, mtn.updated_at DESC, mtn.id DESC
            """,
            (tag,),
        ).fetchall()
    finally:
        conn.close()

    items = []
    for row in item_rows:
        item = dict(row)
        url = item.get("url") or ""
        note = notes_map.get(url)
        tags = market_tags_map.get(url, [])
        item["note"] = note
        item["has_note"] = 1 if note else 0
        item["note_preview"] = build_note_preview(note["note"] if note else None)
        item["market_tags"] = tags
        item["has_market_tags"] = 1 if tags else 0
        item["source_key"] = derive_source_key(item.get("url"), item.get("source_type"), item.get("source"))
        key, label = derive_date_meta(item.get("published_at"), item.get("date"))
        item["date_key"] = key
        item["date_label"] = label
        items.append(item)

    trend_notes = []
    for row in trend_note_rows:
        note = {
            "id": row["id"],
            "date_key": row["date_key"],
            "tag_key": row["tag"],
            "tag": row["display_name"] or row["tag"],
            "direction": row["direction"],
            "note": row["note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        trend_notes.append(note)

    return jsonify(
        {
            "ok": True,
            "view": "tag",
            "tag": tag_def["display_name"],
            "tag_key": tag_def["key"],
            "total": len(items),
            "item_total": len(items),
            "trend_note_total": len(trend_notes),
            "items": items,
            "trend_notes": trend_notes,
        }
    )


@app.get("/api/market-workbench")
def api_market_workbench():
    tag_key = (request.args.get("tag") or "").strip()
    try:
        content_filter = parse_market_workbench_content_filter(request.args.get("content_filter"))
        sort_order = parse_news_sort_order(request.args)
    except ValueError as exc:
        error = "invalid_market_workbench_content_filter" if str(exc) == "invalid_market_workbench_content_filter" else "invalid_sort_order"
        return jsonify({"ok": False, "error": error}), 400
    page = max(1, int(request.args.get("page", "1")))
    per = min(100, max(10, int(request.args.get("per", "30"))))

    conn = db_conn()
    try:
        tags = load_market_tag_definitions(conn, active_only=True)
        if not tag_key:
            feed = load_market_tag_feed(conn, tag_key=None, content_filter=content_filter, sort_order=sort_order, page=page, per=per)
            pin_payload = serialize_market_pinned_note(load_market_pinned_note(conn, None))
            return jsonify(
                {
                    "ok": True,
                    "mode": "all",
                    "selected_tag": None,
                    "content_filter": content_filter,
                    "sort_order": sort_order,
                    "tags": tags,
                    "items": feed["items"],
                    "total": feed["total"],
                    "page": feed["page"],
                    "pages": feed["pages"],
                    "has_more": feed["has_more"],
                    "pin": pin_payload,
                }
            )

        tag_def = next((tag for tag in tags if tag["key"] == tag_key), None)
        if not tag_def:
            return jsonify({"ok": False, "error": "invalid_tag"}), 400

        feed = load_market_tag_feed(conn, tag_key=tag_key, content_filter=content_filter, sort_order=sort_order, page=page, per=per)
        summary_news_rows, summary_note_rows = load_market_tag_summary_sources(
            conn,
            tag_key=tag_key,
            range_days=MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
            limit=MARKET_WORKBENCH_SUMMARY_MAX_NEWS,
        )
        summary_row = market_tag_summary_row(conn, tag_key, MARKET_WORKBENCH_SUMMARY_RANGE_DAYS)
        summary_payload = serialize_market_tag_summary(
            tag_def,
            MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
            summary_news_rows,
            summary_note_rows,
            summary_row,
        )
        pin_payload = serialize_market_pinned_note(load_market_pinned_note(conn, tag_key), tag_def)
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "mode": "tag",
            "selected_tag": {"key": tag_def["key"], "display_name": tag_def["display_name"]},
            "content_filter": content_filter,
            "sort_order": sort_order,
            "tags": tags,
            "items": feed["items"],
            "total": feed["total"],
            "page": feed["page"],
            "pages": feed["pages"],
            "has_more": feed["has_more"],
            "summary": summary_payload,
            "pin": pin_payload,
        }
    )


@app.put("/api/market-workbench/pin")
def api_market_workbench_pin_save():
    body = request.get_json(silent=True) or {}
    tag_key_value = body.get("tag_key")
    if tag_key_value is None:
        normalized_tag_key = ""
    elif isinstance(tag_key_value, str):
        normalized_tag_key = tag_key_value.strip()
    else:
        return jsonify({"ok": False, "error": "invalid_tag"}), 400

    note_value = body.get("note")
    if note_value is None:
        note_text = ""
    elif isinstance(note_value, str):
        note_text = note_value.strip()
    else:
        return jsonify({"ok": False, "error": "invalid_note"}), 400
    if len(note_text) > MARKET_PIN_NOTE_MAX_LEN:
        return jsonify({"ok": False, "error": "note_too_long"}), 400

    collapsed_value = body.get("collapsed", False)
    if isinstance(collapsed_value, bool):
        collapsed = 1 if collapsed_value else 0
    elif collapsed_value in (0, 1):
        collapsed = int(collapsed_value)
    else:
        return jsonify({"ok": False, "error": "invalid_collapsed"}), 400

    conn = db_conn()
    try:
        tag_def = None
        if normalized_tag_key:
            tag_def = conn.execute(
                "SELECT key, display_name FROM market_tag_definitions WHERE key=? AND active=1",
                (normalized_tag_key,),
            ).fetchone()
            if not tag_def:
                return jsonify({"ok": False, "error": "invalid_tag"}), 400

        scope, scope_tag_key = market_pin_scope_and_tag(normalized_tag_key)
        existing = load_market_pinned_note(conn, scope_tag_key)
        ts = now_ts()
        created_at = existing.get("created_at") or ts
        with conn:
            conn.execute(
                """
                INSERT INTO market_pinned_notes(scope, tag_key, note, collapsed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, tag_key) DO UPDATE SET
                  note=excluded.note,
                  collapsed=excluded.collapsed,
                  updated_at=excluded.updated_at
                """,
                (scope, scope_tag_key, note_text, collapsed, created_at, ts),
            )
        payload = serialize_market_pinned_note(load_market_pinned_note(conn, scope_tag_key), dict(tag_def) if tag_def else None)
    finally:
        conn.close()
    return jsonify({"ok": True, "pin": payload})


@app.get("/api/market-tags/<tag_key>/summary")
def api_market_tag_summary(tag_key: str):
    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key, display_name, active FROM market_tag_definitions WHERE key=? AND active=1",
            (tag_key,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "invalid_tag"}), 400
        news_rows, note_rows = load_market_tag_summary_sources(
            conn,
            tag_key=tag_key,
            range_days=MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
            limit=MARKET_WORKBENCH_SUMMARY_MAX_NEWS,
        )
        summary_row = market_tag_summary_row(conn, tag_key, MARKET_WORKBENCH_SUMMARY_RANGE_DAYS)
        payload = serialize_market_tag_summary(dict(tag_def), MARKET_WORKBENCH_SUMMARY_RANGE_DAYS, news_rows, note_rows, summary_row)
    finally:
        conn.close()
    return jsonify({"ok": True, "summary": payload})


@app.post("/api/market-tags/<tag_key>/summary/generate")
def api_market_tag_summary_generate(tag_key: str):
    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key, display_name, active FROM market_tag_definitions WHERE key=? AND active=1",
            (tag_key,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "invalid_tag"}), 400
        news_rows, note_rows = load_market_tag_summary_sources(
            conn,
            tag_key=tag_key,
            range_days=MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
            limit=MARKET_WORKBENCH_SUMMARY_MAX_NEWS,
        )
        if not news_rows and not note_rows:
            return jsonify({"ok": False, "error": "summary_source_items_not_found"}), 404
        source_hash = build_market_tag_summary_hash(news_rows, note_rows, MARKET_WORKBENCH_SUMMARY_RANGE_DAYS)
        materials = build_market_tag_summary_materials(
            tag_def["display_name"],
            news_rows,
            note_rows,
            MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
        )
        llm_settings = current_runtime_settings()["llm"]
        model_name = (llm_settings["translation"].get("model") or "").strip()
        try:
            payload = generate_market_tag_summary(
                tag_label=tag_def["display_name"],
                range_days=MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
                news_count=len(news_rows),
                note_count=len(note_rows),
                materials=materials,
                model=model_name,
            )
        except LLMClientError as exc:
            with conn:
                save_market_tag_summary(
                    conn,
                    tag_key=tag_key,
                    range_days=MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
                    source_hash=source_hash,
                    status="failed",
                    summary_text="",
                    error=str(exc),
                    model=model_name or "deepseek-chat",
                    raw_json="{}",
                )
            summary_row = market_tag_summary_row(conn, tag_key, MARKET_WORKBENCH_SUMMARY_RANGE_DAYS)
            summary = serialize_market_tag_summary(dict(tag_def), MARKET_WORKBENCH_SUMMARY_RANGE_DAYS, news_rows, note_rows, summary_row)
            return jsonify({"ok": False, "error": "market_tag_summary_generate_failed", "detail": str(exc), "summary": summary}), 502

        with conn:
            save_market_tag_summary(
                conn,
                tag_key=tag_key,
                range_days=MARKET_WORKBENCH_SUMMARY_RANGE_DAYS,
                source_hash=source_hash,
                status="success",
                summary_text=(payload.get("summary_text") or "").strip(),
                error="",
                model=payload.get("model", model_name or "deepseek-chat"),
                raw_json=payload.get("raw_json", "{}"),
            )
        summary_row = market_tag_summary_row(conn, tag_key, MARKET_WORKBENCH_SUMMARY_RANGE_DAYS)
        summary = serialize_market_tag_summary(dict(tag_def), MARKET_WORKBENCH_SUMMARY_RANGE_DAYS, news_rows, note_rows, summary_row)
    finally:
        conn.close()
    return jsonify({"ok": True, "summary": summary})


@app.put("/api/market-trend-note")
@app.put("/api/market-trends/note")
def api_market_trend_note_create():
    body = request.get_json(silent=True) or {}
    date_key = (body.get("date_key") or body.get("date") or "").strip()
    tag_key = (body.get("tag_key") or body.get("tag") or "").strip()
    direction = (body.get("direction") or "").strip().lower()
    raw_note = body.get("note")
    if not date_key:
        return jsonify({"ok": False, "error": "missing_date"}), 400
    if not isinstance(raw_note, str):
        return jsonify({"ok": False, "error": "invalid_note"}), 400
    if direction not in MARKET_DIRECTIONS:
        return jsonify({"ok": False, "error": "invalid_direction"}), 400

    note_text = raw_note.strip()
    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key, display_name FROM market_tag_definitions WHERE key=? AND active=1",
            (tag_key,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "unsupported_tag"}), 400
        if not note_text:
            return jsonify({"ok": False, "error": "empty_note"}), 400
        ts = now_ts()
        with conn:
            cur = conn.execute(
                """
                INSERT INTO market_trend_notes(date_key, tag, direction, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (date_key, tag_key, direction, note_text, ts, ts),
            )
        note_id = cur.lastrowid
        trend_notes = load_trend_notes_map(conn, [(date_key, tag_key, direction)]).get((date_key, tag_key, direction), [])
        trend_note = next((note for note in trend_notes if note["id"] == note_id), None)
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "date": date_key,
            "tag": tag_def["display_name"],
            "tag_key": tag_key,
            "direction": direction,
            "trend_note": trend_note,
            "trend_notes": trend_notes,
            "has_trend_note": 1 if trend_notes else 0,
        }
    )


@app.patch("/api/market-trends/note/<int:note_id>")
def api_market_trend_note_update(note_id: int):
    body = request.get_json(silent=True) or {}
    raw_note = body.get("note")
    if not isinstance(raw_note, str):
        return jsonify({"ok": False, "error": "invalid_note"}), 400
    note_text = raw_note.strip()
    if not note_text:
        return jsonify({"ok": False, "error": "empty_note"}), 400
    conn = db_conn()
    try:
        existing = conn.execute(
            """
            SELECT mtn.id, mtn.date_key, mtn.tag, mtn.direction, mtd.display_name
            FROM market_trend_notes mtn
            LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
            WHERE mtn.id=?
            """,
            (note_id,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "note_not_found"}), 404
        with conn:
            conn.execute(
                "UPDATE market_trend_notes SET note=?, updated_at=? WHERE id=?",
                (note_text, now_ts(), note_id),
            )
        trend_notes = load_trend_notes_map(
            conn,
            [(existing["date_key"], existing["tag"], existing["direction"])],
        ).get((existing["date_key"], existing["tag"], existing["direction"]), [])
        trend_note = next((note for note in trend_notes if note["id"] == note_id), None)
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "date": existing["date_key"],
            "tag": existing["display_name"] or existing["tag"],
            "tag_key": existing["tag"],
            "direction": existing["direction"],
            "trend_note": trend_note,
            "trend_notes": trend_notes,
            "has_trend_note": 1 if trend_notes else 0,
        }
    )


@app.delete("/api/market-trends/note/<int:note_id>")
def api_market_trend_note_delete(note_id: int):
    conn = db_conn()
    try:
        existing = conn.execute(
            """
            SELECT mtn.id, mtn.date_key, mtn.tag, mtn.direction, mtd.display_name
            FROM market_trend_notes mtn
            LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
            WHERE mtn.id=?
            """,
            (note_id,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "note_not_found"}), 404
        with conn:
            conn.execute("DELETE FROM market_trend_notes WHERE id=?", (note_id,))
        trend_notes = load_trend_notes_map(
            conn,
            [(existing["date_key"], existing["tag"], existing["direction"])],
        ).get((existing["date_key"], existing["tag"], existing["direction"]), [])
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "date": existing["date_key"],
            "tag": existing["display_name"] or existing["tag"],
            "tag_key": existing["tag"],
            "direction": existing["direction"],
            "trend_notes": trend_notes,
            "has_trend_note": 1 if trend_notes else 0,
        }
    )


@app.get("/api/reading-checkpoint")
def api_get_reading_checkpoint():
    scope = (request.args.get("scope") or "feed").strip().lower()
    if scope != "feed":
        return jsonify({"ok": False, "error": "unsupported_scope"}), 400

    conn = db_conn()
    try:
        row = conn.execute(
            "SELECT scope, item_id, url, title, updated_at FROM reading_checkpoints WHERE scope=?",
            (scope,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"ok": True, "checkpoint": None})
    return jsonify({"ok": True, "checkpoint": dict(row)})


@app.put("/api/reading-checkpoint")
def api_put_reading_checkpoint():
    body = request.get_json(silent=True) or {}
    scope = (body.get("scope") or "feed").strip().lower()
    if scope != "feed":
        return jsonify({"ok": False, "error": "unsupported_scope"}), 400

    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "missing_url"}), 400
    item_id = (body.get("item_id") or "").strip() or None
    title = (body.get("title") or "").strip() or None
    ts = now_ts()

    conn = db_conn()
    try:
        conn.execute(
            """
            INSERT INTO reading_checkpoints(scope, item_id, url, title, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(scope) DO UPDATE SET
              item_id=excluded.item_id,
              url=excluded.url,
              title=excluded.title,
              updated_at=excluded.updated_at
            """,
            (scope, item_id, url, title, ts),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.get("/api/reading-checkpoint/locate")
def api_locate_reading_checkpoint():
    scope = (request.args.get("scope") or "feed").strip().lower()
    if scope != "feed":
        return jsonify({"ok": False, "error": "unsupported_scope"}), 400

    q = (request.args.get("q") or "").strip()
    read_filter = (request.args.get("read_filter") or "all").strip().lower()
    source_filter = (request.args.get("source_filter") or "all").strip().lower()
    per = min(100, max(10, int(request.args.get("per", "30"))))

    conn = db_conn()
    try:
        cp = conn.execute(
            "SELECT item_id, url, title, updated_at FROM reading_checkpoints WHERE scope=?",
            (scope,),
        ).fetchone()
        if not cp or not cp["url"]:
            return jsonify({"ok": True, "found": False, "reason": "no_checkpoint"})

        where_sql, args = _build_news_where_clause(q, read_filter, "feed", source_filter)
        sql = f"""
        WITH filtered AS (
          SELECT items.id, items.url,
                 ROW_NUMBER() OVER (ORDER BY {FEED_NEWS_ORDER_BY_SQL}) AS rn,
                 COUNT(*) OVER () AS total
          FROM items
          LEFT JOIN item_state st ON st.item_id = items.id
          {where_sql}
        )
        SELECT id, url, rn, total
        FROM filtered
        WHERE url = ?
        ORDER BY rn
        LIMIT 1
        """
        hit = conn.execute(sql, [*args, cp["url"]]).fetchone()
    finally:
        conn.close()

    if not hit:
        return jsonify(
            {
                "ok": True,
                "found": False,
                "reason": "not_in_current_scope",
                "checkpoint": dict(cp),
            }
        )

    row_num = int(hit["rn"])
    total = int(hit["total"])
    page = ((row_num - 1) // per) + 1
    offset = row_num - ((page - 1) * per) - 1
    return jsonify(
        {
            "ok": True,
            "found": True,
            "item_id": hit["id"],
            "url": hit["url"],
            "row_num": row_num,
            "total": total,
            "page": page,
            "offset": offset,
            "per": per,
            "checkpoint": dict(cp),
        }
    )


@app.post("/api/reindex")
def api_reindex():
    full = bool((request.get_json(silent=True) or {}).get("full", False))
    conn = db_conn()
    try:
        stats = reindex(conn, DAILY_NEWS_DIR, full=full)
        tracked_incremental_matches = run_tracked_topics_incremental(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify(
        {
            "ok": True,
            "scanned_files": stats.scanned_files,
            "changed_files": stats.changed_files,
            "upserted": stats.upserted,
            "deleted_stale": stats.deleted_stale,
            "ingest_counts": stats.ingest_counts,
            "tracked_incremental_matches": tracked_incremental_matches,
        }
    )


@app.patch("/api/news/<item_id>/state")
def api_update_item_state(item_id: str):
    body = request.get_json(silent=True) or {}
    allowed = ("read", "important", "read_later", "favorite")
    provided = [k for k in allowed if k in body]
    if not provided:
        return jsonify({"ok": False, "error": "missing_state_flags"}), 400
    for k in provided:
        if not isinstance(body[k], bool):
            return jsonify({"ok": False, "error": f"invalid_{k}_flag"}), 400

    conn = db_conn()
    try:
        row = conn.execute("SELECT id FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        old_state = conn.execute(
            "SELECT read_at, important_at, read_later_at, read_later_done_at, favorite_at FROM item_state WHERE item_id=?",
            (item_id,),
        ).fetchone()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        read_at = old_state["read_at"] if old_state else None
        important_at = old_state["important_at"] if old_state else None
        read_later_at = old_state["read_later_at"] if old_state else None
        read_later_done_at = old_state["read_later_done_at"] if old_state else None
        favorite_at = old_state["favorite_at"] if old_state else None
        if "read" in body:
            read_at = ts if body["read"] else None
        if "important" in body:
            important_at = ts if body["important"] else None
        if "read_later" in body:
            read_later_at = ts if body["read_later"] else None
            read_later_done_at = None if body["read_later"] else ts
        if "favorite" in body:
            favorite_at = ts if body["favorite"] else None
        with conn:
            conn.execute(
                """
                INSERT INTO item_state(item_id, read_at, important_at, read_later_at, read_later_done_at, favorite_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                  read_at=excluded.read_at,
                  important_at=excluded.important_at,
                  read_later_at=excluded.read_later_at,
                  read_later_done_at=excluded.read_later_done_at,
                  favorite_at=excluded.favorite_at,
                  updated_at=excluded.updated_at
                """,
                (item_id, read_at, important_at, read_later_at, read_later_done_at, favorite_at, ts),
            )
            if "read_later" in body:
                item_row = conn.execute(
                    "SELECT id, url, source FROM items WHERE id=?",
                    (item_id,),
                ).fetchone()
                if item_row and item_row["url"]:
                    if body["read_later"]:
                        enqueue_detail_job(conn, item_row["id"], item_row["url"], item_row["source"] or "")
                    else:
                        # Plan B: cancel only pending jobs; do not kill running/success detail fetch.
                        conn.execute(
                            """
                            UPDATE detail_jobs
                            SET status='canceled', updated_at=?
                            WHERE url=? AND status='pending'
                            """,
                            (ts, item_row["url"]),
                        )
                        conn.execute(
                            """
                            UPDATE ai_jobs
                            SET status='canceled', updated_at=?
                            WHERE url=? AND status='pending'
                            """,
                            (ts, item_row["url"]),
                        )
    finally:
        conn.close()
    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "read_at": read_at,
            "important_at": important_at,
            "read_later_at": read_later_at,
            "read_later_done_at": read_later_done_at,
            "favorite_at": favorite_at,
        }
    )


@app.get("/api/media-cache/<cache_key>")
def api_media_cache(cache_key: str):
    if not _MEDIA_CACHE_KEY_RE.match(cache_key):
        return jsonify({"ok": False, "error": "invalid_cache_key"}), 400
    conn = db_conn()
    try:
        row = conn.execute(
            "SELECT relative_path, mime_type FROM media_cache WHERE cache_key=? AND status='success'",
            (cache_key,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404
    full_path = (MEDIA_CACHE_DIR / row["relative_path"]).resolve()
    if not _is_path_within_media_cache_dir(full_path):
        return jsonify({"ok": False, "error": "invalid_path"}), 400
    if not full_path.exists():
        return jsonify({"ok": False, "error": "file_missing"}), 404
    return send_from_directory(
        str(MEDIA_CACHE_DIR),
        row["relative_path"],
        mimetype=row["mime_type"] or None,
    )


@app.get("/api/news/<item_id>/detail")
def api_news_detail(item_id: str):
    conn = db_conn()
    try:
        item = conn.execute(
            """
            SELECT
              items.id,
              items.title,
              items.url,
              items.source,
              items.source_name,
              items.source_type,
              items.summary,
              items.published_at,
              source_files.ingest_mode,
              source_files.ingest_warning
            FROM items
            LEFT JOIN source_files ON source_files.path = items.source_file
            WHERE items.id=?
            """,
            (item_id,),
        ).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        url = item["url"] or ""
        job = None
        detail = None
        ai_job = None
        ai = None
        note_row = None
        market_tags: list[dict] = []
        tracked_topic_choices: list[dict] = []
        reminders: list[dict] = []
        reminder_summary = {
            "active_total": 0,
            "due_total": 0,
            "done_total": 0,
            "dismissed_total": 0,
            "total": 0,
        }
        state_row = conn.execute(
            "SELECT read_at, important_at, read_later_at, read_later_done_at, favorite_at FROM item_state WHERE item_id=?",
            (item_id,),
        ).fetchone()
        market_tag_choices = load_market_tag_definitions(conn, active_only=True)
        tracked_topic_choices = load_tracked_topic_choices(conn)
        reminders = load_item_reminders(conn, item_id)
        reminder_summary = {
            "total": len(reminders),
            "active_total": sum(1 for reminder in reminders if reminder["status"] == "active"),
            "due_total": sum(1 for reminder in reminders if reminder["is_due"]),
            "done_total": sum(1 for reminder in reminders if reminder["status"] == "done"),
            "dismissed_total": sum(1 for reminder in reminders if reminder["status"] == "dismissed"),
        }
        detail = None
        detail_out = None
        if url:
            job = conn.execute(
                "SELECT status, attempts, last_error, queued_at, started_at, finished_at FROM detail_jobs WHERE url=?",
                (url,),
            ).fetchone()
            ai_job = conn.execute(
                "SELECT status, attempts, last_error, queued_at, started_at, finished_at FROM ai_jobs WHERE url=?",
                (url,),
            ).fetchone()
            detail = conn.execute(
                "SELECT title, author, published_at, content, content_length, fetched_at, raw_json FROM article_details WHERE url=?",
                (url,),
            ).fetchone()
            ai = conn.execute(
                "SELECT model, key_points_zh, conclusion_zh, body_zh, raw_json, generated_at FROM article_ai WHERE url=?",
                (url,),
            ).fetchone()
            note_row = conn.execute(
                "SELECT note, created_at, updated_at FROM article_notes WHERE url=?",
                (url,),
            ).fetchone()
            market_tags = load_market_tags_map(conn, [url]).get(url, [])

            detail_out = dict(detail) if detail else None
            if detail_out and (_is_twitter_url(url) or item["source_type"] == "twitter"):
                try:
                    raw_payload = json.loads(detail_out.get("raw_json") or "{}")
                    detail_out["media_images"] = _sanitize_twitter_media_images(raw_payload.get("media_images"))
                    for image in detail_out["media_images"]:
                        cached = conn.execute(
                            "SELECT cache_key FROM media_cache WHERE url=? AND status='success'",
                            (image["url"],),
                        ).fetchone()
                        if cached:
                            image["cached_url"] = f"/api/media-cache/{cached['cache_key']}"
                except Exception:
                    detail_out["media_images"] = []
            if detail_out and "raw_json" in detail_out:
                del detail_out["raw_json"]
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "url": item["url"],
            "read_at": (state_row["read_at"] if state_row else None),
            "important_at": (state_row["important_at"] if state_row else None),
            "read_later_at": (state_row["read_later_at"] if state_row else None),
            "read_later_done_at": (state_row["read_later_done_at"] if state_row else None),
            "favorite_at": (state_row["favorite_at"] if state_row else None),
            "detail_status": (job["status"] if job else "none"),
            "job": dict(job) if job else None,
            "detail": detail_out,
            "ai_status": (ai_job["status"] if ai_job else "none"),
            "ai_job": dict(ai_job) if ai_job else None,
            "ai": dict(ai) if ai else None,
            "has_note": 1 if note_row else 0,
            "note": (dict(note_row) if note_row else None),
            "market_tags": market_tags,
            "has_market_tags": 1 if market_tags else 0,
            "market_tag_choices": market_tag_choices,
            "tracked_topic_choices": tracked_topic_choices,
            "reminders": reminders,
            "reminder_summary": reminder_summary,
            "ingest_mode": item["ingest_mode"],
            "ingest_warning": item["ingest_warning"],
            "chat_context": build_news_chat_context(
                item=item,
                detail=detail,
                ai=ai,
                note_row=note_row,
                market_tags=market_tags,
            ),
            "chat_providers": chat_provider_catalog(),
        }
    )


@app.post("/api/news/<item_id>/reminders")
def api_news_reminder_create(item_id: str):
    body = request.get_json(silent=True) or {}
    event_title = (body.get("event_title") or "").strip()
    if not event_title:
        return jsonify({"ok": False, "error": "empty_event_title"}), 400
    if len(event_title) > 200:
        return jsonify({"ok": False, "error": "event_title_too_long"}), 400
    try:
        event_date = parse_reminder_event_date(body.get("event_date") or "")
        remind_at = parse_reminder_remind_at(body.get("remind_at") or "")
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    note = body.get("note")
    if note is None:
        note_text = ""
    elif isinstance(note, str):
        note_text = note.strip()
    else:
        return jsonify({"ok": False, "error": "invalid_note"}), 400
    if len(note_text) > 5000:
        return jsonify({"ok": False, "error": "note_too_long"}), 400

    conn = db_conn()
    try:
        item = conn.execute(
            "SELECT id, title, url FROM items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        ts = now_ts()
        with conn:
            cur = conn.execute(
                """
                INSERT INTO news_reminders(
                  item_id, item_title_snapshot, item_url_snapshot,
                  event_title, event_date, remind_at, note,
                  status, created_at, updated_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, NULL)
                """,
                (
                    item_id,
                    item["title"] or "",
                    item["url"] or "",
                    event_title,
                    event_date,
                    remind_at,
                    note_text,
                    ts,
                    ts,
                ),
            )
        reminder = next((row for row in load_item_reminders(conn, item_id) if row["id"] == cur.lastrowid), None)
        summary = load_reminder_summary(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "reminder": reminder, "summary": summary})


@app.patch("/api/reminders/<int:reminder_id>")
def api_reminder_update(reminder_id: int):
    body = request.get_json(silent=True) or {}
    allowed = {"event_title", "event_date", "remind_at", "note", "status"}
    provided = [key for key in allowed if key in body]
    if not provided:
        return jsonify({"ok": False, "error": "missing_fields"}), 400

    conn = db_conn()
    try:
        existing = conn.execute(
            "SELECT * FROM news_reminders WHERE id=?",
            (reminder_id,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "reminder_not_found"}), 404

        event_title = existing["event_title"]
        event_date = existing["event_date"]
        remind_at = existing["remind_at"]
        note_text = existing["note"] or ""
        status = existing["status"]
        completed_at = existing["completed_at"]

        if "event_title" in body:
            event_title = (body.get("event_title") or "").strip()
            if not event_title:
                return jsonify({"ok": False, "error": "empty_event_title"}), 400
            if len(event_title) > 200:
                return jsonify({"ok": False, "error": "event_title_too_long"}), 400
        if "event_date" in body:
            try:
                event_date = parse_reminder_event_date(body.get("event_date") or "")
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
        if "remind_at" in body:
            try:
                remind_at = parse_reminder_remind_at(body.get("remind_at") or "")
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
        if "note" in body:
            note = body.get("note")
            if note is None:
                note_text = ""
            elif isinstance(note, str):
                note_text = note.strip()
            else:
                return jsonify({"ok": False, "error": "invalid_note"}), 400
            if len(note_text) > 5000:
                return jsonify({"ok": False, "error": "note_too_long"}), 400
        if "status" in body:
            status = (body.get("status") or "").strip().lower()
            if status not in REMINDER_STATUSES:
                return jsonify({"ok": False, "error": "invalid_status"}), 400
            if status == "done":
                completed_at = now_ts()
            elif status == "active":
                completed_at = None

        updated_at = now_ts()
        with conn:
            conn.execute(
                """
                UPDATE news_reminders
                SET event_title=?,
                    event_date=?,
                    remind_at=?,
                    note=?,
                    status=?,
                    updated_at=?,
                    completed_at=?
                WHERE id=?
                """,
                (
                    event_title,
                    event_date,
                    remind_at,
                    note_text,
                    status,
                    updated_at,
                    completed_at,
                    reminder_id,
                ),
            )
        updated = conn.execute(
            """
            SELECT nr.*,
                   CASE WHEN items.id IS NULL THEN 0 ELSE 1 END AS item_exists
            FROM news_reminders nr
            LEFT JOIN items ON items.id = nr.item_id
            WHERE nr.id=?
            """,
            (reminder_id,),
        ).fetchone()
        summary = load_reminder_summary(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "reminder": serialize_reminder_rows([updated])[0], "summary": summary})


@app.delete("/api/reminders/<int:reminder_id>")
def api_reminder_delete(reminder_id: int):
    conn = db_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM news_reminders WHERE id=?",
            (reminder_id,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "reminder_not_found"}), 404
        with conn:
            conn.execute("DELETE FROM news_reminders WHERE id=?", (reminder_id,))
        summary = load_reminder_summary(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, "deleted_id": reminder_id, "summary": summary})


@app.post("/api/news/<item_id>/chat")
def api_news_chat(item_id: str):
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"ok": False, "error": "empty_question"}), 400

    session_id = (body.get("session_id") or "").strip()
    requested_model = (body.get("model") or "").strip()
    reset = bool(body.get("reset"))
    model = requested_model or current_codex_chat_model()

    conn = db_conn()
    try:
        item = conn.execute(
            "SELECT id, title, url, source, source_name, source_type, summary, published_at FROM items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        url = (item["url"] or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "missing_url"}), 400
        detail = conn.execute(
            """
            SELECT title, source, published_at, content
            FROM article_details
            WHERE url=?
            """,
            (url,),
        ).fetchone()
        ai = conn.execute(
            """
            SELECT key_points_zh, conclusion_zh, body_zh
            FROM article_ai
            WHERE url=?
            """,
            (url,),
        ).fetchone()
        note_row = conn.execute(
            """
            SELECT note
            FROM article_notes
            WHERE url=?
            """,
            (url,),
        ).fetchone()
        market_tags = load_market_tags_map(conn, [url]).get(url, [])
    finally:
        conn.close()

    chat_context = build_news_chat_context(
        item=item,
        detail=detail,
        ai=ai,
        note_row=note_row,
        market_tags=market_tags,
    )
    if not chat_context:
        return jsonify({"ok": False, "error": "context_unavailable"}), 409

    lock = codex_chat_lock(item_id)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "provider_busy"}), 409

    try:
        payload = run_codex_chat(
            question=question,
            session_id=session_id,
            model=model,
            reset=reset,
            title=chat_context["title"],
            source=chat_context["source"],
            published_at=chat_context["published_at"],
            content=chat_context["content"],
            context_level=chat_context["context_level"],
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        error = str(exc)
        if error == "codex_timeout":
            return jsonify({"ok": False, "error": "provider_timeout"}), 504
        if error == "codex_session_invalid":
            return jsonify({"ok": False, "error": "session_invalid"}), 409
        if error == "codex_missing_session_id":
            return jsonify({"ok": False, "error": "missing_session_id"}), 502
        if error == "codex_empty_answer":
            return jsonify({"ok": False, "error": "empty_answer"}), 502
        return jsonify({"ok": False, "error": "provider_failed", "detail": error}), 502
    finally:
        lock.release()

    return jsonify(
        {
            "ok": True,
            **payload,
            "context_level": chat_context["context_level"],
            "context_label": chat_context["context_label"],
        }
    )


@app.post("/api/news/<item_id>/chat/archive")
def api_news_chat_archive(item_id: str):
    body = request.get_json(silent=True) or {}
    try:
        messages = normalize_chat_messages(body.get("messages"))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not any(message["role"] == "assistant" for message in messages):
        return jsonify({"ok": False, "error": "empty_archive_source"}), 400

    requested_model = (body.get("model") or "").strip()
    model = requested_model or current_codex_chat_model()

    conn = db_conn()
    try:
        item = conn.execute(
            "SELECT id, title, url, source, published_at FROM items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        url = (item["url"] or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "missing_url"}), 400
        existing_note_row = conn.execute(
            "SELECT note, created_at, updated_at FROM article_notes WHERE url=?",
            (url,),
        ).fetchone()
    finally:
        conn.close()

    lock = codex_chat_lock(item_id)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "provider_busy"}), 409

    try:
        payload = run_codex_chat_archive(
            title=(item["title"] or "").strip(),
            source=(item["source"] or "").strip(),
            published_at=(item["published_at"] or "").strip(),
            messages=messages,
            model=model,
        )
    except RuntimeError as exc:
        error = str(exc)
        if error == "codex_timeout":
            return jsonify({"ok": False, "error": "provider_timeout"}), 504
        if error == "codex_empty_archive":
            return jsonify({"ok": False, "error": "empty_archive_summary"}), 502
        return jsonify({"ok": False, "error": "provider_failed", "detail": error}), 502
    finally:
        lock.release()

    summary = " ".join((payload.get("summary") or "").split()).strip()
    if not summary:
        return jsonify({"ok": False, "error": "empty_archive_summary"}), 502
    if len(summary) > CHAT_ARCHIVE_SUMMARY_MAX_LEN:
        return jsonify({"ok": False, "error": "invalid_archive_summary"}), 502

    stamp = now_ts()[:16]
    block = f"【Chat 归档｜{stamp}】\n{summary}"
    existing_note = (existing_note_row["note"] or "").strip() if existing_note_row else ""
    merged_note = block if not existing_note else f"{existing_note}\n\n---\n{block}"
    if len(merged_note) > 5000:
        return jsonify({"ok": False, "error": "note_too_long"}), 409

    conn = db_conn()
    try:
        with conn:
            ts = now_ts()
            conn.execute(
                """
                INSERT INTO article_notes(url, note, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                  note=excluded.note,
                  updated_at=excluded.updated_at
                """,
                (url, merged_note, ts, ts),
            )
        saved = conn.execute(
            "SELECT note, created_at, updated_at FROM article_notes WHERE url=?",
            (url,),
        ).fetchone()
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "provider": payload.get("provider") or "codex",
            "model": payload.get("model") or model,
            "archive_summary": summary,
            "has_note": 1 if saved else 0,
            "note": (dict(saved) if saved else None),
            "note_preview": build_note_preview(saved["note"] if saved else None),
        }
    )


@app.get("/api/market-tags")
def api_market_tags():
    active_only = ((request.args.get("active_only") or "").strip().lower() in ("1", "true", "yes"))
    conn = db_conn()
    try:
        tags = load_market_tag_definitions(conn, active_only=active_only)
    finally:
        conn.close()
    return jsonify({"ok": True, "tags": tags})


@app.post("/api/market-tags")
def api_market_tags_create():
    body = request.get_json(silent=True) or {}
    raw_name = body.get("display_name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return jsonify({"ok": False, "error": "invalid_display_name"}), 400
    display_name = raw_name.strip()

    conn = db_conn()
    try:
        duplicate = conn.execute(
            "SELECT key FROM market_tag_definitions WHERE display_name=? COLLATE NOCASE",
            (display_name,),
        ).fetchone()
        if duplicate:
            return jsonify({"ok": False, "error": "display_name_exists"}), 400
        key = create_market_tag_key(conn, display_name)
        row = conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM market_tag_definitions").fetchone()
        sort_order = int(row[0] or 0)
        ts = now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO market_tag_definitions(key, display_name, active, sort_order, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
                """,
                (key, display_name, sort_order, ts, ts),
            )
        created = conn.execute(
            """
            SELECT key, display_name, active, sort_order, created_at, updated_at
            FROM market_tag_definitions
            WHERE key=?
            """,
            (key,),
        ).fetchone()
    finally:
        conn.close()
    return jsonify({"ok": True, "tag": dict(created)})


@app.patch("/api/market-tags/<tag_key>")
def api_market_tags_update(tag_key: str):
    body = request.get_json(silent=True) or {}
    updates: list[str] = []
    args: list = []
    display_name = body.get("display_name")
    active = body.get("active")

    conn = db_conn()
    try:
        existing = conn.execute(
            "SELECT key FROM market_tag_definitions WHERE key=?",
            (tag_key,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "tag_not_found"}), 404

        if display_name is not None:
            if not isinstance(display_name, str) or not display_name.strip():
                return jsonify({"ok": False, "error": "invalid_display_name"}), 400
            normalized_name = display_name.strip()
            duplicate = conn.execute(
                "SELECT key FROM market_tag_definitions WHERE display_name=? COLLATE NOCASE AND key<>?",
                (normalized_name, tag_key),
            ).fetchone()
            if duplicate:
                return jsonify({"ok": False, "error": "display_name_exists"}), 400
            updates.append("display_name=?")
            args.append(normalized_name)

        if active is not None:
            if not isinstance(active, bool):
                return jsonify({"ok": False, "error": "invalid_active"}), 400
            updates.append("active=?")
            args.append(1 if active else 0)

        if not updates:
            return jsonify({"ok": False, "error": "missing_updates"}), 400

        ts = now_ts()
        updates.append("updated_at=?")
        args.append(ts)
        args.append(tag_key)
        with conn:
            conn.execute(
                f"UPDATE market_tag_definitions SET {', '.join(updates)} WHERE key=?",
                args,
            )
        updated = conn.execute(
            """
            SELECT key, display_name, active, sort_order, created_at, updated_at
            FROM market_tag_definitions
            WHERE key=?
            """,
            (tag_key,),
        ).fetchone()
    finally:
        conn.close()
    return jsonify({"ok": True, "tag": dict(updated)})


@app.get("/api/market-tags/<tag_key>/impact")
def api_market_tags_impact(tag_key: str):
    conn = db_conn()
    try:
        existing = conn.execute(
            "SELECT key, display_name FROM market_tag_definitions WHERE key=?",
            (tag_key,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "tag_not_found"}), 404
        affected = market_tag_impact_counts(conn, tag_key)
    finally:
        conn.close()
    return jsonify({"ok": True, "tag": dict(existing), "affected": affected})


@app.delete("/api/market-tags/<tag_key>")
def api_market_tags_delete(tag_key: str):
    conn = db_conn()
    try:
        existing = conn.execute(
            "SELECT key, display_name FROM market_tag_definitions WHERE key=?",
            (tag_key,),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "tag_not_found"}), 404
        affected = market_tag_impact_counts(conn, tag_key)
        ts = now_ts()
        with conn:
            conn.execute("DELETE FROM article_market_tags WHERE tag=?", (tag_key,))
            conn.execute("DELETE FROM market_trend_notes WHERE tag=?", (tag_key,))
            conn.execute("DELETE FROM market_tag_definitions WHERE key=?", (tag_key,))
            if tag_key in DEFAULT_MARKET_TAG_CHOICES:
                conn.execute(
                    """
                    INSERT INTO market_tag_deleted_keys(key, deleted_at)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET deleted_at=excluded.deleted_at
                    """,
                    (tag_key, ts),
                )
        remaining_tags = load_market_tag_definitions(conn, active_only=False)
    finally:
        conn.close()
    return jsonify(
        {
            "ok": True,
            "deleted_tag": dict(existing),
            "affected": affected,
            "tags": remaining_tags,
        }
    )


@app.post("/api/market-tags/<tag_key>/merge")
def api_market_tags_merge(tag_key: str):
    body = request.get_json(silent=True) or {}
    target_key = (body.get("target_key") or "").strip()
    if not target_key:
        return jsonify({"ok": False, "error": "missing_target_key"}), 400
    if target_key == tag_key:
        return jsonify({"ok": False, "error": "same_source_target"}), 400

    conn = db_conn()
    try:
        source = conn.execute(
            "SELECT key, display_name FROM market_tag_definitions WHERE key=?",
            (tag_key,),
        ).fetchone()
        if not source:
            return jsonify({"ok": False, "error": "tag_not_found"}), 404
        target = conn.execute(
            "SELECT key, display_name FROM market_tag_definitions WHERE key=?",
            (target_key,),
        ).fetchone()
        if not target:
            return jsonify({"ok": False, "error": "target_tag_not_found"}), 404

        moved_item_tag_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM article_market_tags src
                WHERE src.tag=?
                  AND NOT EXISTS (
                      SELECT 1 FROM article_market_tags dst
                      WHERE dst.url = src.url AND dst.tag = ?
                  )
                """,
                (tag_key, target_key),
            ).fetchone()[0]
            or 0
        )
        skipped_duplicate_item_tag_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM article_market_tags src
                WHERE src.tag=?
                  AND EXISTS (
                      SELECT 1 FROM article_market_tags dst
                      WHERE dst.url = src.url AND dst.tag = ?
                  )
                """,
                (tag_key, target_key),
            ).fetchone()[0]
            or 0
        )
        moved_trend_note_count = int(
            conn.execute("SELECT COUNT(*) FROM market_trend_notes WHERE tag=?", (tag_key,)).fetchone()[0] or 0
        )
        ts = now_ts()
        with conn:
            conn.execute(
                """
                DELETE FROM article_market_tags
                WHERE tag=?
                  AND EXISTS (
                      SELECT 1 FROM article_market_tags dst
                      WHERE dst.url = article_market_tags.url AND dst.tag = ?
                  )
                """,
                (tag_key, target_key),
            )
            conn.execute(
                "UPDATE article_market_tags SET tag=?, updated_at=? WHERE tag=?",
                (target_key, ts, tag_key),
            )
            conn.execute(
                "UPDATE market_trend_notes SET tag=?, updated_at=? WHERE tag=?",
                (target_key, ts, tag_key),
            )
            conn.execute("DELETE FROM market_tag_definitions WHERE key=?", (tag_key,))
            conn.execute("DELETE FROM market_tag_deleted_keys WHERE key=?", (tag_key,))
        remaining_tags = load_market_tag_definitions(conn, active_only=False)
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "source_tag": dict(source),
            "target_tag": dict(target),
            "moved_item_tag_count": moved_item_tag_count,
            "skipped_duplicate_item_tag_count": skipped_duplicate_item_tag_count,
            "moved_trend_note_count": moved_trend_note_count,
            "tags": remaining_tags,
        }
    )


@app.put("/api/news/<item_id>/note")
def api_news_note_upsert(item_id: str):
    body = request.get_json(silent=True) or {}
    raw_note = body.get("note")
    if raw_note is None:
        return jsonify({"ok": False, "error": "missing_note"}), 400
    if not isinstance(raw_note, str):
        return jsonify({"ok": False, "error": "invalid_note"}), 400
    note_text = raw_note.strip()

    conn = db_conn()
    try:
        item = conn.execute("SELECT id, url FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        url = (item["url"] or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "missing_url"}), 400

        with conn:
            if note_text:
                ts = now_ts()
                conn.execute(
                    """
                    INSERT INTO article_notes(url, note, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                      note=excluded.note,
                      updated_at=excluded.updated_at
                    """,
                    (url, note_text, ts, ts),
                )
            else:
                conn.execute("DELETE FROM article_notes WHERE url=?", (url,))

        saved = conn.execute(
            "SELECT note, created_at, updated_at FROM article_notes WHERE url=?",
            (url,),
        ).fetchone()
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "has_note": 1 if saved else 0,
            "note": (dict(saved) if saved else None),
            "note_preview": build_note_preview(saved["note"] if saved else None),
        }
    )


@app.put("/api/news/<item_id>/market-tag")
def api_news_market_tag_upsert(item_id: str):
    body = request.get_json(silent=True) or {}
    raw_tag = body.get("tag")
    raw_direction = body.get("direction")
    if not isinstance(raw_tag, str) or not raw_tag.strip():
        return jsonify({"ok": False, "error": "invalid_tag"}), 400
    if not isinstance(raw_direction, str):
        return jsonify({"ok": False, "error": "invalid_direction"}), 400
    tag = raw_tag.strip()
    direction = raw_direction.strip().lower()
    if direction not in MARKET_DIRECTIONS:
        return jsonify({"ok": False, "error": "invalid_direction"}), 400

    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key FROM market_tag_definitions WHERE key=? AND active=1",
            (tag,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "unsupported_tag"}), 400
        item = conn.execute("SELECT id, url FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        url = (item["url"] or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "missing_url"}), 400

        ts = now_ts()
        important_at = None
        with conn:
            conn.execute(
                """
                INSERT INTO article_market_tags(url, tag, direction, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(url, tag) DO UPDATE SET
                  direction=excluded.direction,
                  updated_at=excluded.updated_at
                """,
                (url, tag, direction, ts, ts),
            )
            row = conn.execute(
                "SELECT read_at, important_at, read_later_at, read_later_done_at, favorite_at FROM item_state WHERE item_id=?",
                (item_id,),
            ).fetchone()
            read_at = row["read_at"] if row else None
            important_at = row["important_at"] if row else None
            read_later_at = row["read_later_at"] if row else None
            read_later_done_at = row["read_later_done_at"] if row else None
            favorite_at = row["favorite_at"] if row else None
            if not important_at:
                important_at = ts
                conn.execute(
                    """
                    INSERT INTO item_state(item_id, read_at, important_at, read_later_at, read_later_done_at, favorite_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(item_id) DO UPDATE SET
                      read_at=excluded.read_at,
                      important_at=excluded.important_at,
                      read_later_at=excluded.read_later_at,
                      read_later_done_at=excluded.read_later_done_at,
                      favorite_at=excluded.favorite_at,
                      updated_at=excluded.updated_at
                    """,
                    (item_id, read_at, important_at, read_later_at, read_later_done_at, favorite_at, ts),
                )
        market_tags = load_market_tags_map(conn, [url]).get(url, [])
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "market_tags": market_tags,
            "has_market_tags": 1 if market_tags else 0,
            "important_at": important_at,
            "favorite_at": favorite_at,
        }
    )


@app.delete("/api/news/<item_id>/market-tag")
def api_news_market_tag_delete(item_id: str):
    raw_tag = (request.args.get("tag") or "").strip()
    if not raw_tag:
        return jsonify({"ok": False, "error": "missing_tag"}), 400

    conn = db_conn()
    try:
        tag_def = conn.execute(
            "SELECT key FROM market_tag_definitions WHERE key=?",
            (raw_tag,),
        ).fetchone()
        if not tag_def:
            return jsonify({"ok": False, "error": "unsupported_tag"}), 400
        item = conn.execute("SELECT id, url FROM items WHERE id=?", (item_id,)).fetchone()
        if not item:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        url = (item["url"] or "").strip()
        if not url:
            return jsonify({"ok": False, "error": "missing_url"}), 400
        with conn:
            conn.execute(
                "DELETE FROM article_market_tags WHERE url=? AND tag=?",
                (url, raw_tag),
            )
        market_tags = load_market_tags_map(conn, [url]).get(url, [])
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "market_tags": market_tags,
            "has_market_tags": 1 if market_tags else 0,
        }
    )


@app.post("/api/news/<item_id>/detail/retry")
def api_news_detail_retry(item_id: str):
    conn = db_conn()
    try:
        row = conn.execute("SELECT id, url, source, source_type FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        if not row["url"]:
            return jsonify({"ok": False, "error": "missing_url"}), 400
        body = request.get_json(silent=True) or {}
        mode = (request.args.get("mode") or body.get("mode") or "").strip().lower()
        url = row["url"]
        is_twitter = _is_twitter_url(url) or row["source_type"] == "twitter"
        has_detail = conn.execute("SELECT 1 FROM article_details WHERE url=?", (url,)).fetchone()
        with conn:
            ts = now_ts()
            if has_detail:
                if is_twitter and mode != "ai":
                    # For Twitter/X, retry re-fetches the tweet detail even if it already exists,
                    # so that images and updated text can be refreshed without losing the old view.
                    conn.execute(
                        """
                        INSERT INTO detail_jobs(url, item_id, source, status, attempts, queued_at, updated_at, started_at, finished_at)
                        VALUES (?, ?, ?, 'pending', 0, ?, ?, NULL, NULL)
                        ON CONFLICT(url) DO UPDATE SET
                          item_id=excluded.item_id,
                          source=excluded.source,
                          status='pending',
                          last_error=NULL,
                          attempts=0,
                          queued_at=excluded.queued_at,
                          updated_at=excluded.updated_at,
                          started_at=NULL,
                          finished_at=NULL
                        """,
                        (url, row["id"], row["source"] or "", ts, ts),
                    )
                else:
                    enqueue_ai_job(conn, url)
                    conn.execute(
                        """
                        UPDATE ai_jobs
                        SET status='pending', last_error=NULL, queued_at=?, updated_at=?
                        WHERE url=?
                        """,
                        (ts, ts, url),
                    )
            else:
                created = enqueue_detail_job(conn, row["id"], url, row["source"] or "")
                if not created:
                    conn.execute(
                        "UPDATE detail_jobs SET status='pending', last_error=NULL, queued_at=?, updated_at=? WHERE url=?",
                        (ts, ts, url),
                    )
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.post("/api/news/mark-all-read")
def api_mark_all_read():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    read_filter = (body.get("read_filter") or "all").strip().lower()
    collection = (body.get("collection") or "feed").strip().lower()
    source_filter = (body.get("source_filter") or "all").strip().lower()

    where = []
    args: list = []
    if q:
        where.append("(items.title LIKE ? OR items.summary LIKE ? OR items.source LIKE ?)")
        like = f"%{q}%"
        args.extend([like, like, like])
    join_sql = "LEFT JOIN item_state st ON st.item_id = items.id"
    if read_filter == "unread":
        where.append("st.read_at IS NULL")
    elif read_filter == "read":
        where.append("st.read_at IS NOT NULL")
    if collection == "important":
        where.append("st.important_at IS NOT NULL")
    elif collection == "read_later":
        where.append("st.read_later_at IS NOT NULL")
    elif collection == "favorites":
        where.append("st.favorite_at IS NOT NULL")
    source_clause, source_args = build_source_filter_clause(source_filter)
    if source_clause:
        where.append(source_clause)
        args.extend(source_args)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = db_conn()
    try:
        item_ids = [
            r[0]
            for r in conn.execute(
                f"SELECT items.id FROM items {join_sql} {where_sql}",
                args,
            ).fetchall()
        ]
        if not item_ids:
            return jsonify({"ok": True, "marked": 0})

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.executemany(
                """
                INSERT INTO item_state(item_id, read_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                  read_at=excluded.read_at,
                  updated_at=excluded.updated_at
                """,
                [(item_id, ts, ts) for item_id in item_ids],
            )
    finally:
        conn.close()
    return jsonify({"ok": True, "marked": len(item_ids)})


@app.post("/api/news/mark-read-by-ids")
def api_mark_read_by_ids():
    body = request.get_json(silent=True) or {}
    raw_item_ids = body.get("item_ids")
    if not isinstance(raw_item_ids, list):
        return jsonify({"ok": False, "error": "invalid_item_ids"}), 400

    item_ids = [str(x).strip() for x in raw_item_ids if str(x).strip()]
    if not item_ids:
        return jsonify({"ok": True, "marked": 0})

    placeholders = ",".join(["?"] * len(item_ids))
    conn = db_conn()
    try:
        existing_ids = [
            r[0]
            for r in conn.execute(
                f"SELECT id FROM items WHERE id IN ({placeholders})",
                item_ids,
            ).fetchall()
        ]
        if not existing_ids:
            return jsonify({"ok": True, "marked": 0})

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.executemany(
                """
                INSERT INTO item_state(item_id, read_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                  read_at=excluded.read_at,
                  updated_at=excluded.updated_at
                """,
                [(item_id, ts, ts) for item_id in existing_ids],
            )
    finally:
        conn.close()
    return jsonify({"ok": True, "marked": len(existing_ids)})


@app.post("/api/news/clear-read-later")
def api_clear_read_later():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    collection = (body.get("collection") or "read_later").strip().lower()
    read_filter = (body.get("read_filter") or "all").strip().lower()
    source_filter = (body.get("source_filter") or "all").strip().lower()

    where = []
    args: list = []
    if q:
        where.append("(items.title LIKE ? OR items.summary LIKE ? OR items.source LIKE ?)")
        like = f"%{q}%"
        args.extend([like, like, like])
    join_sql = "LEFT JOIN item_state st ON st.item_id = items.id"

    # 默认仅清理 read_later 集合；即使传入其它 collection，也不允许扩大到全量。
    if collection == "important":
        where.append("st.important_at IS NOT NULL")
    elif collection == "notes":
        where.append("EXISTS (SELECT 1 FROM article_notes an WHERE an.url = items.url)")
    elif collection == "market_tags":
        where.append("EXISTS (SELECT 1 FROM article_market_tags mt WHERE mt.url = items.url)")
    if read_filter == "read":
        where.append("0 = 1")
    else:
        where.append("st.read_later_at IS NOT NULL")
    source_clause, source_args = build_source_filter_clause(source_filter)
    if source_clause:
        where.append(source_clause)
        args.extend(source_args)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    conn = db_conn()
    try:
        rows = conn.execute(
            f"SELECT items.id, items.url FROM items {join_sql} {where_sql}",
            args,
        ).fetchall()
        if not rows:
            return jsonify({"ok": True, "cleared": 0})
        item_ids = [r["id"] for r in rows]
        urls = [r["url"] for r in rows if r["url"]]
        ts = now_ts()
        with conn:
            conn.executemany(
                """
                INSERT INTO item_state(item_id, read_later_at, read_later_done_at, updated_at)
                VALUES (?, NULL, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                  read_later_at=NULL,
                  read_later_done_at=excluded.read_later_done_at,
                  updated_at=excluded.updated_at
                """,
                [(item_id, ts, ts) for item_id in item_ids],
            )
            if urls:
                placeholders = ",".join("?" for _ in urls)
                conn.execute(
                    f"UPDATE detail_jobs SET status='canceled', updated_at=? WHERE status='pending' AND url IN ({placeholders})",
                    [ts, *urls],
                )
                conn.execute(
                    f"UPDATE ai_jobs SET status='canceled', updated_at=? WHERE status='pending' AND url IN ({placeholders})",
                    [ts, *urls],
                )
    finally:
        conn.close()
    return jsonify({"ok": True, "cleared": len(item_ids)})


def main() -> None:
    ensure_db()
    start_detail_worker()
    host = (os.getenv("NEWS_READER_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port_raw = (os.getenv("NEWS_READER_PORT") or "8080").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 8080
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
