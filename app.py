from __future__ import annotations

import math
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request, send_from_directory

from llm_client import (
    LLMClientError,
    generate_codex_fallback_translation,
    generate_article_ai,
    generate_recommendation_categories,
    generate_recommendation_classification,
    generate_recommendation_keywords,
    resolve_translation_default_model,
)
from parser import parse_daily_errors
from scanner import apply_schema, list_daily_files, reindex
from secret_store import SecretStoreError, delete_secret, has_secret, read_secret, write_secret
from settings import default_app_settings, load_app_settings, resolve_daily_news_dir, resolve_db_path, save_app_settings


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
STATIC_DIR = BASE_DIR / "static"
DAILY_NEWS_DIR = resolve_daily_news_dir()
DB_PATH = resolve_db_path()
README_PATH = BASE_DIR / "README.md"

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

SOURCE_LABELS = {
    "all": "全部来源",
    "reuters": "Reuters",
    "bloomberg": "Bloomberg",
    "techcrunch": "TechCrunch",
    "ars": "Ars Technica",
    "x": "X",
}

DEFAULT_RECOMMENDATION_KEYWORD_SEEDS = [
    {"key": "ai", "label": "AI", "type": "concept", "aliases": ["人工智能"]},
    {"key": "chip", "label": "芯片", "type": "concept", "aliases": ["半导体"]},
    {"key": "memory", "label": "存储", "type": "concept", "aliases": ["内存"]},
    {"key": "consumer_electronics", "label": "消费电子", "type": "concept", "aliases": ["智能手机", "电子消费"]},
    {"key": "supply_chain", "label": "供应链", "type": "concept", "aliases": []},
    {"key": "cloud", "label": "云计算", "type": "concept", "aliases": ["数据中心"]},
    {"key": "robotics", "label": "机器人", "type": "concept", "aliases": []},
    {"key": "biotech", "label": "生物科技", "type": "concept", "aliases": ["医药"]},
    {"key": "energy", "label": "能源", "type": "concept", "aliases": []},
    {"key": "crypto", "label": "加密货币", "type": "concept", "aliases": []},
    {"key": "banking", "label": "银行业", "type": "concept", "aliases": ["银行"]},
    {"key": "gold", "label": "黄金", "type": "concept", "aliases": []},
    {"key": "sports", "label": "体育赛事", "type": "concept", "aliases": ["体育"]},
    {"key": "ipo", "label": "IPO", "type": "event", "aliases": ["上市"]},
    {"key": "funding", "label": "融资", "type": "event", "aliases": []},
    {"key": "earnings", "label": "财报", "type": "event", "aliases": []},
    {"key": "lawsuit", "label": "诉讼", "type": "event", "aliases": []},
    {"key": "merger", "label": "并购", "type": "event", "aliases": []},
    {"key": "agreement", "label": "协议", "type": "event", "aliases": ["备忘录"]},
    {"key": "intelligence", "label": "情报", "type": "event", "aliases": []},
    {"key": "pandemic", "label": "疫情", "type": "event", "aliases": ["公共卫生"]},
    {"key": "armed_conflict", "label": "武装冲突", "type": "event", "aliases": ["军事冲突", "战争"]},
    {"key": "aviation_accident", "label": "航空事故", "type": "event", "aliases": ["坠机"]},
    {"key": "talent_flow", "label": "人才流动", "type": "event", "aliases": ["跳槽"]},
    {"key": "united_states", "label": "美国", "type": "region", "aliases": ["US", "USA"]},
    {"key": "china", "label": "中国", "type": "region", "aliases": []},
    {"key": "taiwan", "label": "台湾", "type": "region", "aliases": []},
    {"key": "hong_kong", "label": "香港", "type": "region", "aliases": []},
    {"key": "singapore", "label": "新加坡", "type": "region", "aliases": []},
    {"key": "europe", "label": "欧洲", "type": "region", "aliases": ["欧盟"]},
    {"key": "middle_east", "label": "中东", "type": "region", "aliases": []},
    {"key": "iran", "label": "伊朗", "type": "region", "aliases": []},
    {"key": "pakistan", "label": "巴基斯坦", "type": "region", "aliases": []},
    {"key": "openai", "label": "OpenAI", "type": "entity", "aliases": []},
    {"key": "anthropic", "label": "Anthropic", "type": "entity", "aliases": []},
    {"key": "spacex", "label": "SpaceX", "type": "entity", "aliases": []},
    {"key": "elon_musk", "label": "马斯克", "type": "entity", "aliases": ["Elon Musk"]},
    {"key": "trump", "label": "特朗普", "type": "entity", "aliases": ["Donald Trump"]},
    {"key": "nvidia", "label": "英伟达", "type": "entity", "aliases": ["NVIDIA"]},
    {"key": "tsmc", "label": "台积电", "type": "entity", "aliases": ["TSMC"]},
    {"key": "sk_hynix", "label": "SK海力士", "type": "entity", "aliases": ["SK Hynix"]},
    {"key": "xiaomi", "label": "小米", "type": "entity", "aliases": []},
    {"key": "lei_jun", "label": "雷军", "type": "entity", "aliases": []},
    {"key": "sonos", "label": "Sonos", "type": "entity", "aliases": []},
]

RECOMMENDATION_KEYWORD_DISABLED_KEYS = {
    "analyst",
    "supply_chain_check",
    "x_post",
    "regulation",
    "china_assets",
    "国际形势",
    "中国资产",
    "监管",
    "电子消费",
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
RECOMMENDATION_PROMPT_VERSION = "recommendation-category-v2"
RECOMMENDATION_SCHEMA_VERSION = "keyword-v1"
RECOMMENDATION_WEIGHTS_VERSION = "keyword-v1"
RECOMMENDATION_CATEGORY_VERSION = "keyword-v1"
RECOMMENDATION_KEYWORD_EXTRACTOR_VERSION = "keyword-v1"
RECOMMENDATION_INIT_LIMIT = 200
RECOMMENDATION_CATEGORY_SAMPLE_LIMIT = 120
RECOMMENDATION_BACKGROUND_SAMPLE_LIMIT = 180
RECOMMENDATION_BACKGROUND_FETCH_LIMIT = 720
RECOMMENDATION_TREND_CONTEXT_LIMIT = 24
RECOMMENDATION_SCORE_THRESHOLD = 70
RECOMMENDATION_KEYWORD_INIT_RECENT_LIMIT = 200
RECOMMENDATION_KEYWORD_INIT_POSITIVE_LIMIT = 100
RECOMMENDATION_FEEDBACK_TYPES = {
    "shown",
    "opened",
    "marked_important",
    "noted",
    "tagged",
    "dismissed",
}
RECOMMENDATION_CONFIDENCE_MULTIPLIERS = {
    "high": 1.0,
    "medium": 0.55,
    "low": 0.2,
}
RECOMMENDATION_EVENT_TYPE_WEIGHTS = {
    "regulation": 6,
    "product": 4,
    "funding": 4,
    "earnings": 4,
    "geopolitics": 6,
    "policy": 6,
    "market": 2,
    "other": 0,
}
RECOMMENDATION_KEYWORD_TYPES = {
    "entity",
    "concept",
    "domain",
    "event",
    "region",
    "source_form",
    "content_form",
}
RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX = "deleted:"


def news_order_by_sql(collection: str) -> str:
    if collection == "recommendations":
        return "items.published_at DESC, items.id DESC"
    return FEED_NEWS_ORDER_BY_SQL if collection in ("feed", "read_later") else NON_FEED_NEWS_ORDER_BY_SQL


def use_feed_unread_cursor_paging(collection: str, read_filter: str) -> bool:
    return collection == "feed" and read_filter == "unread"


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


def build_feed_unread_cursor_clause(cursor: dict | None) -> tuple[str, list]:
    if not cursor:
        return "", []
    clause = f"""
    AND (
      {ITEM_DATE_SQL} > ? OR
      ({ITEM_DATE_SQL} = ? AND items.published_at > ?) OR
      ({ITEM_DATE_SQL} = ? AND items.published_at = ? AND items.id > ?)
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
    if read_filter == "unread":
        where.append("st.read_at IS NULL")
    elif read_filter == "read":
        where.append("st.read_at IS NOT NULL")
    if collection == "important":
        where.append("st.important_at IS NOT NULL")
    elif collection == "read_later":
        where.append("st.read_later_at IS NOT NULL")
    elif collection == "recommendations":
        where.append("st.read_at IS NULL")
        where.append(
            "EXISTS (SELECT 1 FROM recommendation_keyword_jobs rkj WHERE rkj.item_id = items.id AND rkj.status='success' AND rkj.keyword_count > 0)"
        )
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
    conn = db_conn()
    try:
        apply_schema(conn, SCHEMA_PATH)
        migrate_market_trend_notes(conn)
        migrate_recommendation_tables(conn)
        migrate_recommendation_categories(conn)
        migrate_recommendation_keyword_tables(conn)
        seed_market_tag_definitions(conn)
        seed_recommendation_keywords(conn)
    finally:
        conn.close()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_keyword_candidate_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def normalize_keyword_key(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^0-9a-z_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:64]


def recommendation_seed_keywords() -> list[dict[str, object]]:
    raw_keywords = [
        {
            "key": seed["key"],
            "label": seed["label"],
            "type": seed["type"],
            "aliases": list(seed.get("aliases") or []),
            "source": "seed",
        }
        for seed in DEFAULT_RECOMMENDATION_KEYWORD_SEEDS
    ]
    deduped: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    seen_labels: set[tuple[str, str]] = set()
    for keyword in raw_keywords:
        key = str(keyword["key"])
        label = str(keyword["label"] or "").strip()
        keyword_type = str(keyword["type"] or "").strip()
        dedupe_label = (normalize_keyword_candidate_label(label), keyword_type)
        if not key or key in seen_keys or not label or dedupe_label in seen_labels:
            continue
        seen_keys.add(key)
        seen_labels.add(dedupe_label)
        deduped.append(keyword)
    return deduped


def seed_recommendation_keywords(conn: sqlite3.Connection) -> None:
    ts = now_ts()
    seeded_keywords = recommendation_seed_keywords()
    seeded_by_key = {str(keyword["key"]): keyword for keyword in seeded_keywords}
    existing = {
        row["key"]: dict(row)
        for row in conn.execute(
            "SELECT key, label, type, aliases_json, active, source FROM recommendation_keywords"
        ).fetchall()
    }

    def merged_aliases(*groups: object) -> list[str]:
        values: list[str] = []
        seen: set[str] = set()
        for group in groups:
            if isinstance(group, str):
                items = [group]
            elif isinstance(group, list):
                items = group
            else:
                items = []
            for item in items:
                text = str(item or "").strip()
                normalized = normalize_keyword_candidate_label(text)
                if not text or normalized in seen:
                    continue
                seen.add(normalized)
                values.append(text[:80])
        return values

    with conn:
        for key, row in existing.items():
            source = str(row.get("source") or "")
            if source.startswith(RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX):
                continue

        for keyword in seeded_keywords:
            key = str(keyword["key"])
            aliases_json = json.dumps(keyword["aliases"], ensure_ascii=False)
            if key in existing:
                existing_source = str(existing[key].get("source") or "")
                if existing_source.startswith(RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX):
                    continue
                try:
                    current_aliases = json.loads(existing[key].get("aliases_json") or "[]")
                except json.JSONDecodeError:
                    current_aliases = []
                merged = merged_aliases(keyword["aliases"], current_aliases)
                active = 0 if key in RECOMMENDATION_KEYWORD_DISABLED_KEYS else 1
                conn.execute(
                    """
                    UPDATE recommendation_keywords
                    SET label=?, type=?, aliases_json=?, source=?, updated_at=?
                    WHERE key=?
                    """,
                    (
                        keyword["label"],
                        keyword["type"],
                        json.dumps(merged, ensure_ascii=False),
                        keyword["source"],
                        ts,
                        key,
                    ),
                )
                continue
            active = 0 if key in RECOMMENDATION_KEYWORD_DISABLED_KEYS else 1
            conn.execute(
                """
                INSERT INTO recommendation_keywords(
                  key, label, type, aliases_json, active, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (key, keyword["label"], keyword["type"], aliases_json, active, keyword["source"], ts, ts),
            )

def load_active_recommendation_keywords(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT key, label, type, aliases_json, source
        FROM recommendation_keywords
        WHERE active=1
        ORDER BY type ASC, label COLLATE NOCASE ASC
        """
    ).fetchall()
    keywords: list[dict[str, object]] = []
    for row in rows:
        try:
            aliases = json.loads(row["aliases_json"] or "[]")
        except json.JSONDecodeError:
            aliases = []
        keywords.append(
            {
                "key": row["key"],
                "label": row["label"],
                "type": row["type"],
                "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
                "source": row["source"],
            }
        )
    return keywords


def recommendation_keyword_library_ready(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM recommendation_keywords WHERE active=1 LIMIT 1"
    ).fetchone()
    return bool(row)


def reset_recommendation_keyword_state(conn: sqlite3.Connection) -> dict[str, int]:
    unread_rows = conn.execute(
        """
        SELECT rkj.item_id
        FROM recommendation_keyword_jobs rkj
        LEFT JOIN item_state st ON st.item_id = rkj.item_id
        WHERE st.read_at IS NULL
        """
    ).fetchall()
    unread_ids = [row["item_id"] for row in unread_rows if row["item_id"]]
    if unread_ids:
        placeholders = ",".join("?" for _ in unread_ids)
        conn.execute(
            f"DELETE FROM recommendation_keyword_jobs WHERE item_id IN ({placeholders})",
            unread_ids,
        )
        conn.execute(
            f"DELETE FROM item_recommendation_keywords WHERE item_id IN ({placeholders})",
            unread_ids,
        )
    deleted_candidates = conn.execute("DELETE FROM recommendation_keyword_candidates").rowcount
    return {
        "jobs": len(unread_ids),
        "candidates": int(deleted_candidates or 0),
    }


def positive_recommendation_seed_item_ids(
    conn: sqlite3.Connection,
    limit: int = RECOMMENDATION_KEYWORD_INIT_POSITIVE_LIMIT,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT items.id
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN article_notes an ON an.url = items.url
        LEFT JOIN article_market_tags mt ON mt.url = items.url
        WHERE st.important_at IS NOT NULL
           OR an.url IS NOT NULL
           OR mt.url IS NOT NULL
        ORDER BY items.published_at DESC, items.id DESC
        LIMIT ?
        """,
        (max(1, min(limit, RECOMMENDATION_KEYWORD_INIT_POSITIVE_LIMIT)),),
    ).fetchall()
    return [row["id"] for row in rows if row["id"]]


def enqueue_recommendation_keyword_job(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute(
        """
        SELECT items.id
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        WHERE items.id=? AND st.read_at IS NULL
        """,
        (item_id,),
    ).fetchone()
    if not row:
        return False
    existing = conn.execute(
        "SELECT status FROM recommendation_keyword_jobs WHERE item_id=?",
        (item_id,),
    ).fetchone()
    if existing:
        return False
    ts = now_ts()
    conn.execute(
        """
        INSERT INTO recommendation_keyword_jobs(
          item_id, status, extractor_version, created_at, updated_at
        )
        VALUES (?, 'pending', ?, ?, ?)
        """,
        (item_id, RECOMMENDATION_KEYWORD_EXTRACTOR_VERSION, ts, ts),
    )
    return True


def enqueue_recommendation_keyword_jobs_for_new_items(conn: sqlite3.Connection, item_ids: list[str]) -> int:
    queued = 0
    for item_id in item_ids:
        if enqueue_recommendation_keyword_job(conn, item_id):
            queued += 1
    return queued


def enqueue_recommendation_keyword_init_jobs(conn: sqlite3.Connection, limit: int = RECOMMENDATION_INIT_LIMIT) -> int:
    capped = max(1, min(RECOMMENDATION_KEYWORD_INIT_RECENT_LIMIT, int(limit or RECOMMENDATION_KEYWORD_INIT_RECENT_LIMIT)))
    candidate_ids: list[str] = []
    unread_rows = conn.execute(
        """
        SELECT items.id
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN recommendation_keyword_jobs rkj ON rkj.item_id = items.id
        WHERE st.read_at IS NULL
          AND rkj.item_id IS NULL
        ORDER BY items.published_at DESC, items.id DESC
        LIMIT ?
        """,
        (capped,),
    ).fetchall()
    candidate_ids.extend(row["id"] for row in unread_rows if row["id"])
    for item_id in positive_recommendation_seed_item_ids(conn):
        if item_id not in candidate_ids:
            candidate_ids.append(item_id)
    queued = 0
    for item_id in candidate_ids:
        if enqueue_recommendation_keyword_job(conn, item_id):
            queued += 1
    return queued


def recommendation_status_snapshot(conn: sqlite3.Connection) -> dict[str, object]:
    library_ready = recommendation_keyword_library_ready(conn)
    counts = conn.execute(
        """
        SELECT status, COUNT(*) AS total
        FROM recommendation_keyword_jobs
        GROUP BY status
        """
    ).fetchall()
    by_status = {row["status"]: int(row["total"] or 0) for row in counts}
    latest_error = conn.execute(
        """
        SELECT item_id, error, updated_at
        FROM recommendation_keyword_jobs
        WHERE status='failed'
        ORDER BY updated_at DESC, item_id DESC
        LIMIT 1
        """
    ).fetchone()
    active_keyword_count = conn.execute(
        "SELECT COUNT(*) FROM recommendation_keywords WHERE active=1"
    ).fetchone()[0]
    candidate_count = conn.execute(
        "SELECT COUNT(*) FROM recommendation_keyword_candidates WHERE status='pending'"
    ).fetchone()[0]
    return {
        "keyword_library_ready": library_ready,
        "keyword_library_status": "ready" if library_ready else "not_ready",
        "active_keyword_count": int(active_keyword_count or 0),
        "pending": by_status.get("pending", 0),
        "running": by_status.get("running", 0),
        "success": by_status.get("success", 0),
        "needs_keyword": by_status.get("needs_keyword", 0),
        "failed": by_status.get("failed", 0),
        "skipped": by_status.get("skipped", 0),
        "candidate_count": int(candidate_count or 0),
        "latest_error": dict(latest_error) if latest_error else None,
    }


def upsert_recommendation_keyword_candidate(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    label: str,
    keyword_type: str,
    reason: str,
    aliases: list[str],
    ts: str,
) -> None:
    normalized_label = normalize_keyword_candidate_label(label)
    existing = conn.execute(
        """
        SELECT id, occurrence_count, sample_item_ids_json, aliases_json
        FROM recommendation_keyword_candidates
        WHERE normalized_label=? AND type=?
        """,
        (normalized_label, keyword_type),
    ).fetchone()
    if existing:
        try:
            sample_item_ids = json.loads(existing["sample_item_ids_json"] or "[]")
        except json.JSONDecodeError:
            sample_item_ids = []
        try:
            existing_aliases = json.loads(existing["aliases_json"] or "[]")
        except json.JSONDecodeError:
            existing_aliases = []
        merged_aliases = []
        for alias in [*existing_aliases, *aliases]:
            text = str(alias or "").strip()
            if text and text not in merged_aliases:
                merged_aliases.append(text[:80])
        if item_id not in sample_item_ids:
            sample_item_ids = [item_id, *sample_item_ids][:12]
        conn.execute(
            """
            UPDATE recommendation_keyword_candidates
            SET label=?,
                aliases_json=?,
                reason=?,
                sample_item_ids_json=?,
                occurrence_count=?,
                updated_at=?
            WHERE id=?
            """,
            (
                label[:80],
                json.dumps(merged_aliases, ensure_ascii=False),
                reason[:200],
                json.dumps(sample_item_ids, ensure_ascii=False),
                int(existing["occurrence_count"] or 0) + 1,
                ts,
                existing["id"],
            ),
        )
        return
    conn.execute(
        """
        INSERT INTO recommendation_keyword_candidates(
          normalized_label, label, type, aliases_json, reason, sample_item_ids_json, occurrence_count, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, 'pending', ?, ?)
        """,
        (
            normalized_label,
            label[:80],
            keyword_type,
            json.dumps(aliases[:6], ensure_ascii=False),
            reason[:200],
            json.dumps([item_id], ensure_ascii=False),
            ts,
            ts,
        ),
        )


def parse_json_array(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def normalize_recommendation_keyword_aliases(value: object, *, limit: int = 12) -> list[str]:
    if isinstance(value, str):
        raw_items = re.split(r"[\n,，、;；]+", value)
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    return merge_unique_texts(raw_items, limit=limit)


def normalize_recommendation_keyword_type(value: object) -> str:
    keyword_type = str(value or "").strip().lower()
    return keyword_type if keyword_type in RECOMMENDATION_KEYWORD_TYPES else ""


def keyword_is_soft_deleted(source: object) -> bool:
    return str(source or "").startswith(RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX)


def collect_recommendation_keyword_item_ids(conn: sqlite3.Connection, keyword_key: str) -> list[str]:
    rows = conn.execute(
        "SELECT item_id FROM item_recommendation_keywords WHERE keyword_key=? ORDER BY item_id ASC",
        (keyword_key,),
    ).fetchall()
    return [str(row["item_id"]).strip() for row in rows if str(row["item_id"] or "").strip()]


def recommendation_keyword_row_exists(
    conn: sqlite3.Connection,
    *,
    label: str,
    exclude_key: str = "",
) -> bool:
    query = """
        SELECT 1
        FROM recommendation_keywords
        WHERE label=? COLLATE NOCASE
          AND source NOT LIKE ?
    """
    args: list[object] = [label, f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}%"]
    if exclude_key:
        query += " AND key<>?"
        args.append(exclude_key)
    query += " LIMIT 1"
    return bool(conn.execute(query, args).fetchone())


def parse_recommendation_keyword_body(body: dict[str, object]) -> tuple[dict[str, object] | None, str | None]:
    label = str(body.get("label") or "").strip()
    keyword_type = normalize_recommendation_keyword_type(body.get("type"))
    active = body.get("active")
    if not label:
        return None, "invalid_label"
    if not keyword_type:
        return None, "invalid_type"
    if not isinstance(active, bool):
        return None, "invalid_active"
    aliases = normalize_recommendation_keyword_aliases(body.get("aliases"))
    return {
        "label": label[:80],
        "type": keyword_type,
        "active": active,
        "aliases": aliases,
    }, None


def merge_unique_texts(*groups: object, limit: int = 12) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if isinstance(group, str):
            items = [group]
        elif isinstance(group, list):
            items = group
        else:
            items = []
        for item in items:
            text = str(item or "").strip()
            normalized = normalize_keyword_candidate_label(text)
            if not text or normalized in seen:
                continue
            seen.add(normalized)
            values.append(text[:80])
            if len(values) >= limit:
                return values
    return values


def build_source_facets(*, source: str, source_type: str, url: str) -> dict[str, str]:
    source_key = derive_source_key(url, source_type, source)
    return {
        "source_key": source_key,
        "source_label": source_label_for_key(source_key, source),
        "source_name": (source or "").strip(),
        "source_type": (source_type or "").strip().lower(),
    }


def create_recommendation_keyword_key(conn: sqlite3.Connection, label: str) -> str:
    base = normalize_keyword_key(label) or "keyword"
    candidate = base
    suffix = 2
    while conn.execute("SELECT 1 FROM recommendation_keywords WHERE key=?", (candidate,)).fetchone():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate[:64]


def reset_recommendation_keyword_jobs_for_items(
    conn: sqlite3.Connection,
    item_ids: list[str],
    *,
    keep_status: str = "pending",
) -> int:
    raw_ids = []
    seen: set[str] = set()
    for item_id in item_ids:
        text = str(item_id or "").strip()
        if text and text not in seen:
            seen.add(text)
            raw_ids.append(text)
    if not raw_ids:
        return 0
    placeholders = ",".join("?" for _ in raw_ids)
    unread_rows = conn.execute(
        f"""
        SELECT items.id
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        WHERE items.id IN ({placeholders}) AND st.read_at IS NULL
        """,
        raw_ids,
    ).fetchall()
    normalized_ids = [row["id"] for row in unread_rows if row["id"]]
    if not normalized_ids:
        return 0
    ts = now_ts()
    with conn:
        placeholders = ",".join("?" for _ in normalized_ids)
        conn.execute(
            f"DELETE FROM item_recommendation_keywords WHERE item_id IN ({placeholders})",
            normalized_ids,
        )
        existing_rows = conn.execute(
            f"SELECT item_id FROM recommendation_keyword_jobs WHERE item_id IN ({placeholders})",
            normalized_ids,
        ).fetchall()
        existing_ids = {row["item_id"] for row in existing_rows if row["item_id"]}
        for item_id in normalized_ids:
            if item_id in existing_ids:
                conn.execute(
                    """
                    UPDATE recommendation_keyword_jobs
                    SET status=?,
                        error=NULL,
                        payload_json=NULL,
                        keyword_count=0,
                        candidate_count=0,
                        updated_at=?,
                        processed_at=NULL
                    WHERE item_id=?
                    """,
                    (keep_status, ts, item_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO recommendation_keyword_jobs(
                      item_id, status, extractor_version, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (item_id, keep_status, RECOMMENDATION_KEYWORD_EXTRACTOR_VERSION, ts, ts),
                )
    return len(normalized_ids)


def recommendation_keyword_sample_items(conn: sqlite3.Connection, item_ids: list[str], limit: int = 5) -> list[dict[str, str]]:
    normalized_ids = [str(item_id or "").strip() for item_id in item_ids if str(item_id or "").strip()]
    if not normalized_ids:
        return []
    placeholders = ",".join("?" for _ in normalized_ids)
    rows = conn.execute(
        f"""
        SELECT id, title, source, published_at
        FROM items
        WHERE id IN ({placeholders})
        ORDER BY published_at DESC, id DESC
        """,
        normalized_ids,
    ).fetchall()
    by_id = {
        row["id"]: {
            "id": row["id"],
            "title": row["title"] or row["id"],
            "source": row["source"] or "",
            "published_at": row["published_at"] or "",
        }
        for row in rows
    }
    samples: list[dict[str, str]] = []
    for item_id in normalized_ids:
        sample = by_id.get(item_id)
        if sample:
            samples.append(sample)
        if len(samples) >= limit:
            break
    return samples


def load_recommendation_keyword_library(conn: sqlite3.Connection) -> dict[str, object]:
    keyword_rows = conn.execute(
        """
        SELECT rk.key,
               rk.label,
               rk.type,
               rk.aliases_json,
               rk.active,
               rk.source,
               rk.created_at,
               rk.updated_at,
               COUNT(DISTINCT irk.item_id) AS linked_item_count
        FROM recommendation_keywords rk
        LEFT JOIN item_recommendation_keywords irk ON irk.keyword_key = rk.key
        WHERE rk.source NOT LIKE ?
        GROUP BY rk.key, rk.label, rk.type, rk.aliases_json, rk.active, rk.source, rk.created_at, rk.updated_at
        ORDER BY rk.active DESC, rk.type ASC, rk.label COLLATE NOCASE ASC
        """
    , (f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}%",)).fetchall()
    keywords: list[dict[str, object]] = []
    all_keywords: list[dict[str, object]] = []
    for row in keyword_rows:
        keyword = {
            "key": row["key"],
            "label": row["label"],
            "type": row["type"],
            "aliases": [str(alias).strip() for alias in parse_json_array(row["aliases_json"]) if str(alias).strip()],
            "active": bool(row["active"]),
            "source": row["source"] or "seed",
            "linked_item_count": int(row["linked_item_count"] or 0),
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or "",
        }
        keywords.append(keyword)
        all_keywords.append(
            {
                "key": keyword["key"],
                "label": keyword["label"],
                "type": keyword["type"],
                "active": keyword["active"],
            }
        )

    candidate_rows = conn.execute(
        """
        SELECT id,
               normalized_label,
               label,
               type,
               aliases_json,
               reason,
               sample_item_ids_json,
               occurrence_count,
               status,
               merged_keyword_key,
               created_at,
               updated_at,
               reviewed_at
        FROM recommendation_keyword_candidates
        ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'merged' THEN 1 WHEN 'accepted' THEN 2 ELSE 3 END,
                 occurrence_count DESC,
                 updated_at DESC,
                 id DESC
        """
    ).fetchall()
    candidates: list[dict[str, object]] = []
    for row in candidate_rows:
        sample_item_ids = [str(item_id).strip() for item_id in parse_json_array(row["sample_item_ids_json"]) if str(item_id).strip()]
        candidates.append(
            {
                "id": int(row["id"]),
                "normalized_label": row["normalized_label"] or "",
                "label": row["label"] or "",
                "type": row["type"] or "domain",
                "aliases": [str(alias).strip() for alias in parse_json_array(row["aliases_json"]) if str(alias).strip()],
                "reason": row["reason"] or "",
                "sample_item_ids": sample_item_ids,
                "sample_items": recommendation_keyword_sample_items(conn, sample_item_ids, limit=5),
                "occurrence_count": int(row["occurrence_count"] or 0),
                "status": row["status"] or "pending",
                "merged_keyword_key": row["merged_keyword_key"] or "",
                "created_at": row["created_at"] or "",
                "updated_at": row["updated_at"] or "",
                "reviewed_at": row["reviewed_at"] or "",
            }
        )

    return {
        "active_keywords": [keyword for keyword in keywords if keyword["active"]],
        "disabled_keywords": [keyword for keyword in keywords if not keyword["active"]],
        "candidate_keywords": candidates,
        "all_keywords": all_keywords,
    }


def process_pending_recommendation_keyword_once() -> bool:
    conn = db_conn()
    item_id = ""
    try:
        if not recommendation_keyword_library_ready(conn):
            return False
        row = conn.execute(
            """
            SELECT rkj.item_id,
                   items.title,
                   items.source,
                   items.source_type,
                   items.summary,
                   items.published_at,
                   items.url,
                   st.read_at,
                   ad.content AS detail_content
            FROM recommendation_keyword_jobs rkj
            LEFT JOIN items ON items.id = rkj.item_id
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN article_details ad ON ad.url = items.url
            WHERE rkj.status='pending'
            ORDER BY rkj.created_at ASC, rkj.item_id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return False

        item_id = row["item_id"]
        ts = now_ts()
        with conn:
            conn.execute(
                "UPDATE recommendation_keyword_jobs SET status='running', updated_at=? WHERE item_id=?",
                (ts, item_id),
            )

        if not row["title"]:
            with conn:
                conn.execute(
                    """
                    UPDATE recommendation_keyword_jobs
                    SET status='skipped', error='ITEM_NOT_FOUND', updated_at=?, processed_at=?
                    WHERE item_id=?
                    """,
                    (ts, ts, item_id),
                )
            return True
        if row["read_at"]:
            with conn:
                conn.execute(
                    """
                    UPDATE recommendation_keyword_jobs
                    SET status='skipped', error='ALREADY_READ', updated_at=?, processed_at=?
                    WHERE item_id=?
                    """,
                    (ts, ts, item_id),
                )
            return True

        llm_settings = current_runtime_settings()["llm"]
        payload = generate_recommendation_keywords(
            title=(row["title"] or "").strip(),
            source=(row["source"] or "").strip(),
            source_type=(row["source_type"] or "").strip(),
            published_at=(row["published_at"] or "").strip(),
            summary=(row["summary"] or "").strip(),
            detail_excerpt=((row["detail_content"] or "").strip())[:2400],
            keywords=load_active_recommendation_keywords(conn),
            model=llm_settings["translation"]["model"],
        )
        canonical_keywords = payload.get("canonical_keywords") or []
        candidate_keywords = payload.get("candidate_keywords") or []
        status = "success" if canonical_keywords else "needs_keyword"
        payload_json = {
            "canonical_keywords": canonical_keywords,
            "candidate_keywords": candidate_keywords,
            "needs_keyword_reason": payload.get("needs_keyword_reason") or "",
            "source_facets": build_source_facets(
                source=(row["source"] or "").strip(),
                source_type=(row["source_type"] or "").strip(),
                url=(row["url"] or "").strip(),
            ),
            "raw_json": payload.get("raw_json", "{}"),
        }
        with conn:
            conn.execute("DELETE FROM item_recommendation_keywords WHERE item_id=?", (item_id,))
            for keyword in canonical_keywords:
                conn.execute(
                    """
                    INSERT INTO item_recommendation_keywords(
                      item_id, keyword_key, confidence, raw_keyword, extractor_version, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        keyword["key"],
                        keyword["confidence"],
                        keyword.get("raw_keyword") or "",
                        RECOMMENDATION_KEYWORD_EXTRACTOR_VERSION,
                        ts,
                    ),
                )
            for candidate in candidate_keywords:
                upsert_recommendation_keyword_candidate(
                    conn,
                    item_id=item_id,
                    label=str(candidate["label"]),
                    keyword_type=str(candidate["type"]),
                    reason=str(candidate.get("reason") or ""),
                    aliases=[str(alias) for alias in candidate.get("aliases") or []],
                    ts=ts,
                )
            conn.execute(
                """
                UPDATE recommendation_keyword_jobs
                SET status=?,
                    error=NULL,
                    payload_json=?,
                    keyword_count=?,
                    candidate_count=?,
                    updated_at=?,
                    processed_at=?
                WHERE item_id=?
                """,
                (
                    status,
                    json.dumps(payload_json, ensure_ascii=False),
                    len(canonical_keywords),
                    len(candidate_keywords),
                    ts,
                    ts,
                    item_id,
                ),
            )
        return True
    except LLMClientError as exc:
        ts = now_ts()
        with conn:
            conn.execute(
                """
                UPDATE recommendation_keyword_jobs
                SET status='failed', error=?, updated_at=?, processed_at=?
                WHERE item_id=?
                """,
                (str(exc)[:500], ts, ts, item_id),
            )
        return True
    finally:
        conn.close()


def current_recommendation_join_sql(alias: str = "re") -> str:
    return (
        f"LEFT JOIN recommendation_evals {alias} "
        f"ON {alias}.item_id = items.id AND {alias}.schema_version = '{RECOMMENDATION_SCHEMA_VERSION}'"
    )


def serialize_recommendation_features(features: dict[str, object]) -> str:
    return json.dumps(features, ensure_ascii=False, sort_keys=True)


def parse_recommendation_features(raw_json: str | None) -> dict[str, object] | None:
    if not isinstance(raw_json, str) or not raw_json.strip():
        return None
    try:
        return _coerce_recommendation_features(json.loads(raw_json))
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _clean_string_list(raw: object, *, limit: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    cleaned: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _coerce_recommendation_features(parsed: object) -> dict[str, object]:
    if not isinstance(parsed, dict):
        raise ValueError("INVALID_RECOMMENDATION_FEATURES")
    normalized: dict[str, object] = {}
    raw_matches = parsed.get("category_matches")
    matches = []
    if isinstance(raw_matches, list):
        seen_keys: set[str] = set()
        for raw in raw_matches[:8]:
            if not isinstance(raw, dict):
                continue
            key = str(raw.get("key") or "").strip()
            confidence = str(raw.get("confidence") or "").strip().lower()
            if not key or confidence not in RECOMMENDATION_CONFIDENCE_MULTIPLIERS or key in seen_keys:
                continue
            seen_keys.add(key)
            matches.append({"key": key, "confidence": confidence})
    normalized["category_matches"] = matches
    event_type = str(parsed.get("event_type") or "").strip().lower()
    normalized["event_type"] = event_type if event_type in RECOMMENDATION_EVENT_TYPE_WEIGHTS else "other"
    normalized["entities"] = _clean_string_list(parsed.get("entities"), limit=6)
    normalized["sectors"] = _clean_string_list(parsed.get("sectors"), limit=5)
    normalized["regions"] = _clean_string_list(parsed.get("regions"), limit=5)
    raw_candidates = parsed.get("new_category_candidates")
    candidates = []
    if isinstance(raw_candidates, list):
        for raw in raw_candidates[:5]:
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label") or "").strip()
            description = str(raw.get("description") or "").strip()
            confidence = str(raw.get("confidence") or "").strip().lower()
            if not (label and description and confidence in RECOMMENDATION_CONFIDENCE_MULTIPLIERS):
                continue
            candidates.append(
                {
                    "label": label[:80],
                    "description": description[:200],
                    "confidence": confidence,
                }
            )
    normalized["new_category_candidates"] = candidates
    headline_signal = str(parsed.get("headline_signal") or "").strip()
    normalized["headline_signal"] = headline_signal[:120]
    return normalized


def load_active_recommendation_categories(conn: sqlite3.Connection) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT key,
               label,
               description,
               positive_count,
               background_count,
               positive_rate,
               background_rate,
               lift_score,
               weight_reason,
               weight,
               active,
               version,
               seed_item_ids_json
        FROM recommendation_categories
        WHERE active=1 AND version=?
        ORDER BY weight DESC, positive_count DESC, key ASC
        """,
        (RECOMMENDATION_CATEGORY_VERSION,),
    ).fetchall()
    categories = []
    for row in rows:
        try:
            seed_item_ids = json.loads(row["seed_item_ids_json"] or "[]")
        except json.JSONDecodeError:
            seed_item_ids = []
        categories.append(
            {
                "key": row["key"],
                "label": row["label"],
                "description": row["description"],
                "positive_count": int(row["positive_count"] or 0),
                "background_count": int(row["background_count"] or 0),
                "positive_rate": float(row["positive_rate"] or 0.0),
                "background_rate": float(row["background_rate"] or 0.0),
                "lift_score": float(row["lift_score"] or 0.0),
                "weight_reason": (row["weight_reason"] or "").strip(),
                "weight": int(row["weight"] or 0),
                "active": int(row["active"] or 0),
                "version": row["version"],
                "seed_item_ids": [str(item).strip() for item in seed_item_ids if str(item).strip()],
            }
        )
    return categories


def recommendation_category_ready(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM recommendation_categories WHERE active=1 AND version=? LIMIT 1",
        (RECOMMENDATION_CATEGORY_VERSION,),
    ).fetchone()
    return bool(row)


def recommendation_meta_get(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT value_text FROM recommendation_meta WHERE key=?", (key,)).fetchone()
    return str(row["value_text"] or "") if row else ""


def recommendation_meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO recommendation_meta(key, value_text, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          value_text=excluded.value_text,
          updated_at=excluded.updated_at
        """,
        (key, value, now_ts()),
    )


def recommendation_category_weight(positive_count: int) -> int:
    return max(50, min(70, 50 + max(0, positive_count) * 5))


def current_recommendation_positive_samples(conn: sqlite3.Connection, limit: int = RECOMMENDATION_CATEGORY_SAMPLE_LIMIT) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT items.id AS item_id,
               items.source,
               items.title,
               items.summary,
               COALESCE(an.note, '') AS note,
               GROUP_CONCAT(DISTINCT mt.tag) AS tags,
               CASE WHEN st.important_at IS NOT NULL THEN 1 ELSE 0 END AS is_important,
               CASE WHEN an.url IS NOT NULL THEN 1 ELSE 0 END AS has_note,
               COUNT(DISTINCT mt.tag) AS tag_count
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN article_notes an ON an.url = items.url
        LEFT JOIN article_market_tags mt ON mt.url = items.url
        WHERE st.important_at IS NOT NULL
           OR an.url IS NOT NULL
           OR mt.url IS NOT NULL
        GROUP BY items.id
        ORDER BY is_important DESC, has_note DESC, tag_count DESC, items.published_at DESC
        LIMIT ?
        """,
        (max(1, limit),),
    ).fetchall()
    samples = []
    for row in rows:
        samples.append(
            {
                "item_id": row["item_id"],
                "source": (row["source"] or "").strip(),
                "title": (row["title"] or "").strip(),
                "summary": (row["summary"] or "").strip(),
                "note": (row["note"] or "").strip(),
                "tags": (row["tags"] or "").strip(),
            }
        )
    return samples


def current_recommendation_trend_contexts(
    conn: sqlite3.Connection,
    limit: int = RECOMMENDATION_TREND_CONTEXT_LIMIT,
) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT mtn.date_key,
               mtn.direction,
               mtn.note,
               mtd.display_name,
               mtn.tag
        FROM market_trend_notes mtn
        LEFT JOIN market_tag_definitions mtd ON mtd.key = mtn.tag
        WHERE COALESCE(mtn.note, '') <> ''
        ORDER BY mtn.updated_at DESC, mtn.id DESC
        LIMIT ?
        """,
        (max(1, limit),),
    ).fetchall()
    contexts: list[dict[str, str]] = []
    for row in rows:
        contexts.append(
            {
                "date_key": (row["date_key"] or "").strip(),
                "direction": (row["direction"] or "").strip(),
                "tag": (row["display_name"] or row["tag"] or "").strip(),
                "note": (row["note"] or "").strip(),
            }
        )
    return contexts


def current_recommendation_background_samples(
    conn: sqlite3.Connection,
    limit: int = RECOMMENDATION_BACKGROUND_SAMPLE_LIMIT,
) -> list[dict[str, str]]:
    fetch_limit = max(limit, RECOMMENDATION_BACKGROUND_FETCH_LIMIT)
    rows = conn.execute(
        """
        SELECT items.id AS item_id,
               items.url,
               items.source,
               items.source_type,
               items.title,
               items.summary,
               items.published_at,
               ad.content AS detail_content
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN article_notes an ON an.url = items.url
        LEFT JOIN article_market_tags mt ON mt.url = items.url
        LEFT JOIN article_details ad ON ad.url = items.url
        WHERE st.important_at IS NULL
          AND an.url IS NULL
          AND mt.url IS NULL
        GROUP BY items.id
        ORDER BY items.published_at DESC, items.id DESC
        LIMIT ?
        """,
        (max(1, fetch_limit),),
    ).fetchall()
    if not rows:
        return []

    per_source_cap = max(6, math.ceil(max(1, limit) / 8))
    per_source_counts: dict[str, int] = {}
    samples: list[dict[str, str]] = []
    for row in rows:
        source_key = derive_source_key(row["url"], row["source_type"], row["source"])
        if per_source_counts.get(source_key, 0) >= per_source_cap:
            continue
        per_source_counts[source_key] = per_source_counts.get(source_key, 0) + 1
        samples.append(
            {
                "item_id": row["item_id"],
                "source": (row["source"] or "").strip(),
                "title": (row["title"] or "").strip(),
                "summary": (row["summary"] or "").strip(),
                "published_at": (row["published_at"] or "").strip(),
                "detail_excerpt": ((row["detail_content"] or "").strip())[:2000],
            }
        )
        if len(samples) >= limit:
            break
    return samples


def recommendation_category_weight_from_stats(
    *,
    positive_count: int,
    background_count: int,
    positive_rate: float,
    background_rate: float,
) -> tuple[int, str, float]:
    epsilon = 0.01
    lift_score = (positive_rate + epsilon) / (background_rate + epsilon)
    positive_bonus = min(18, int(round(positive_rate * 120)))
    background_penalty = min(18, int(round(background_rate * 90)))
    lift_bonus = min(20, int(round(max(0.0, lift_score - 1.0) * 6)))
    count_bonus = min(6, max(0, positive_count - 1) * 2)
    weight = 45 + positive_bonus + count_bonus + lift_bonus - background_penalty
    bounded = max(35, min(85, weight))
    reason = json.dumps(
        {
            "positive_count": positive_count,
            "background_count": background_count,
            "positive_rate": round(positive_rate, 4),
            "background_rate": round(background_rate, 4),
            "lift_score": round(lift_score, 4),
            "positive_bonus": positive_bonus,
            "background_penalty": background_penalty,
            "lift_bonus": lift_bonus,
            "count_bonus": count_bonus,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return bounded, reason, lift_score


def classify_background_samples(
    conn: sqlite3.Connection,
    *,
    categories_for_prompt: list[dict[str, str]],
    model: str,
    samples: list[dict[str, str]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not samples:
        return counts
    for sample in samples:
        try:
            payload = generate_recommendation_classification(
                title=sample["title"],
                source=sample["source"],
                published_at=sample["published_at"],
                summary=sample["summary"],
                detail_excerpt=sample["detail_excerpt"],
                categories=categories_for_prompt,
                model=model,
            )
        except LLMClientError:
            continue
        seen_keys: set[str] = set()
        for match in payload.get("category_matches", []):
            if not isinstance(match, dict):
                continue
            key = str(match.get("key") or "").strip()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            counts[key] = counts.get(key, 0) + 1
    return counts


def recommendation_source_bonus_map(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT items.url, items.source, items.source_type, COUNT(*) AS total
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN article_notes an ON an.url = items.url
        LEFT JOIN article_market_tags mt ON mt.url = items.url
        WHERE st.important_at IS NOT NULL
           OR an.url IS NOT NULL
           OR mt.url IS NOT NULL
        GROUP BY items.url, items.source, items.source_type
        """
    ).fetchall()
    bonuses: dict[str, int] = {}
    for row in rows:
        key = derive_source_key(row["url"], row["source_type"], row["source"])
        bonuses[key] = max(bonuses.get(key, 0), min(8, int(row["total"] or 0) * 2))
    return bonuses


def score_recommendation_features(
    features: dict[str, object],
    *,
    categories_by_key: dict[str, dict[str, object]],
    source_bonus: int,
) -> int:
    score = 0.0
    for match in features.get("category_matches", []):
        if not isinstance(match, dict):
            continue
        key = str(match.get("key") or "").strip()
        confidence = str(match.get("confidence") or "").strip().lower()
        category = categories_by_key.get(key)
        if not category:
            continue
        multiplier = RECOMMENDATION_CONFIDENCE_MULTIPLIERS.get(confidence, 0.0)
        score += int(category["weight"]) * multiplier
    score += int(RECOMMENDATION_EVENT_TYPE_WEIGHTS.get(str(features.get("event_type") or "").strip().lower(), 0))
    score += int(source_bonus)
    return int(round(score))


def recommendation_passes_gate(features: dict[str, object], score: int) -> bool:
    matches = features.get("category_matches", [])
    if not isinstance(matches, list) or not matches:
        return False
    high_count = 0
    medium_count = 0
    for match in matches:
        if not isinstance(match, dict):
            continue
        confidence = str(match.get("confidence") or "").strip().lower()
        if confidence == "high":
            high_count += 1
        elif confidence == "medium":
            medium_count += 1
    if high_count < 1 and medium_count < 2:
        return False
    if score < RECOMMENDATION_SCORE_THRESHOLD:
        return False
    return True


def recommendation_bucket_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT
          CASE
            WHEN COALESCE(score, 0) >= 90 THEN '90+'
            WHEN COALESCE(score, 0) >= 75 THEN '75-89'
            WHEN COALESCE(score, 0) >= 50 THEN '50-74'
            ELSE '<50'
          END AS bucket,
          COUNT(*) AS total
        FROM recommendation_evals
        WHERE status='success'
          AND schema_version=?
        GROUP BY bucket
        """,
        (RECOMMENDATION_SCHEMA_VERSION,),
    ).fetchall()
    counts = {"90+": 0, "75-89": 0, "50-74": 0, "<50": 0}
    for row in rows:
        counts[row["bucket"]] = int(row["total"] or 0)
    return counts


def recompute_recommendation_eval_row(conn: sqlite3.Connection, row: sqlite3.Row, ts: str | None = None) -> bool:
    features = parse_recommendation_features(row["features_json"])
    if not features:
        return False
    categories_by_key = {category["key"]: category for category in load_active_recommendation_categories(conn)}
    source_bonus = recommendation_source_bonus_map(conn).get(
        derive_source_key(row["url"], row["source_type"], row["source"]),
        0,
    )
    current_ts = ts or now_ts()
    score = score_recommendation_features(
        features,
        categories_by_key=categories_by_key,
        source_bonus=source_bonus,
    )
    recommended = 1 if recommendation_passes_gate(features, score) else 0
    conn.execute(
        """
        UPDATE recommendation_evals
        SET score=?,
            recommended=?,
            weights_version=?,
            updated_at=?
        WHERE item_id=? AND schema_version=?
        """,
        (score, recommended, RECOMMENDATION_WEIGHTS_VERSION, current_ts, row["item_id"], row["schema_version"]),
    )
    return True


def recompute_stale_recommendation_evals(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT re.item_id, re.features_json, re.schema_version, items.url, items.source, items.source_type
        FROM recommendation_evals re
        LEFT JOIN items ON items.id = re.item_id
        WHERE re.status='success'
          AND COALESCE(re.features_json, '') <> ''
          AND re.schema_version=?
          AND COALESCE(re.weights_version, '') <> ?
        ORDER BY re.updated_at ASC, re.item_id ASC
        """,
        (RECOMMENDATION_SCHEMA_VERSION, RECOMMENDATION_WEIGHTS_VERSION),
    ).fetchall()
    if not rows:
        return 0
    ts = now_ts()
    updated = 0
    for row in rows:
        if recompute_recommendation_eval_row(conn, row, ts=ts):
            updated += 1
    return updated


def recommendation_status_snapshot(conn: sqlite3.Connection) -> dict[str, object]:
    library_ready = recommendation_keyword_library_ready(conn)
    counts = conn.execute(
        """
        SELECT status, COUNT(*) AS total
        FROM recommendation_keyword_jobs
        GROUP BY status
        """
    ).fetchall()
    by_status = {row["status"]: int(row["total"] or 0) for row in counts}
    latest_error = conn.execute(
        """
        SELECT item_id, error, updated_at
        FROM recommendation_keyword_jobs
        WHERE status='failed'
        ORDER BY updated_at DESC, item_id DESC
        LIMIT 1
        """
    ).fetchone()
    active_keyword_count = conn.execute(
        "SELECT COUNT(*) FROM recommendation_keywords WHERE active=1"
    ).fetchone()[0]
    candidate_count = conn.execute(
        "SELECT COUNT(*) FROM recommendation_keyword_candidates WHERE status='pending'"
    ).fetchone()[0]
    return {
        "schema_version": RECOMMENDATION_SCHEMA_VERSION,
        "weights_version": RECOMMENDATION_WEIGHTS_VERSION,
        "category_version": RECOMMENDATION_CATEGORY_VERSION,
        "keyword_library_ready": library_ready,
        "keyword_library_status": "ready" if library_ready else "not_ready",
        "active_keyword_count": int(active_keyword_count or 0),
        "pending": by_status.get("pending", 0),
        "running": by_status.get("running", 0),
        "success": by_status.get("success", 0),
        "needs_keyword": by_status.get("needs_keyword", 0),
        "failed": by_status.get("failed", 0),
        "skipped": by_status.get("skipped", 0),
        "candidate_count": int(candidate_count or 0),
        "latest_error": dict(latest_error) if latest_error else None,
    }


def build_note_preview(note_text: str | None, limit: int = 120) -> str:
    if not isinstance(note_text, str):
        return ""
    compact = " ".join(note_text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


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
        }
    }
    return normalized


def chat_provider_catalog() -> dict[str, dict]:
    llm = current_runtime_settings()["llm"]
    model = (llm.get("codex_chat", {}).get("model") or "").strip()
    return {
        "codex": {
            "label": "Codex",
            "available": True,
            "note": "基于新闻正文上下文回答；可结合外部知识，无法确认的最新进展会明确说明。",
            "model": model,
        }
    }


def current_codex_chat_model() -> str:
    llm = current_runtime_settings()["llm"]
    return (llm.get("codex_chat", {}).get("model") or "").strip()


def codex_chat_lock(item_id: str) -> threading.Lock:
    with CODEX_CHAT_LOCKS_GUARD:
        return CODEX_CHAT_LOCKS.setdefault(item_id, threading.Lock())


def build_codex_chat_prompt(*, title: str, source: str, published_at: str, content: str, question: str) -> str:
    return (
        "你是一名新闻研究助手。要求：使用中文，回答尽量简洁。\n"
        f"发布时间：{published_at}\n"
        "新闻正文：\n"
        f"{content}\n\n"
        f"用户问题：{question}"
    )


def run_codex_chat(*, question: str, title: str, source: str, published_at: str, content: str, session_id: str = "", model: str = "", reset: bool = False, timeout: int = 90) -> dict:
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


def serialize_news_rows(
    items: list[dict],
    market_tags_map: dict[str, list[dict]],
    recommendation_keywords_map: dict[str, list[dict]] | None = None,
) -> list[dict]:
    recommendation_keywords_map = recommendation_keywords_map or {}
    for item in items:
        tags = market_tags_map.get(item.get("url") or "", [])
        item["recommendation_keywords"] = recommendation_keywords_map.get(item.get("id") or "", [])
        item["note_preview"] = build_note_preview(item.pop("note_preview_source", None))
        item["market_tags"] = tags
        item["has_market_tags"] = 1 if tags else 0
        item["source_key"] = derive_source_key(item.get("url"), item.get("source_type"), item.get("source"))
        date_key, date_label = derive_date_meta(item.get("published_at"), item.get("date"))
        item["date_key"] = date_key
        item["date_label"] = date_label
    return items


def load_recommendation_keywords_map(conn: sqlite3.Connection, item_ids: list[str]) -> dict[str, list[dict]]:
    if not item_ids:
        return {}
    placeholders = ",".join("?" for _ in item_ids)
    rows = conn.execute(
        f"""
        SELECT irk.item_id,
               irk.keyword_key,
               irk.confidence,
               irk.raw_keyword,
               rk.label,
               rk.type
        FROM item_recommendation_keywords irk
        LEFT JOIN recommendation_keywords rk ON rk.key = irk.keyword_key
        WHERE irk.item_id IN ({placeholders})
        ORDER BY irk.item_id ASC,
                 CASE irk.confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END ASC,
                 rk.type ASC,
                 rk.label COLLATE NOCASE ASC
        """,
        item_ids,
    ).fetchall()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["item_id"], []).append(
            {
                "key": row["keyword_key"],
                "label": row["label"] or row["keyword_key"],
                "type": row["type"] or "domain",
                "confidence": row["confidence"],
                "raw_keyword": row["raw_keyword"] or "",
            }
        )
    return result


def load_market_tag_definitions(conn: sqlite3.Connection, active_only: bool = False) -> list[dict]:
    where_sql = "WHERE active=1" if active_only else ""
    rows = conn.execute(
        f"""
        SELECT key, display_name, active, sort_order, created_at, updated_at
        FROM market_tag_definitions
        {where_sql}
        ORDER BY sort_order ASC, created_at ASC, key ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def load_market_tag_definition_map(conn: sqlite3.Connection) -> dict[str, dict]:
    return {row["key"]: row for row in load_market_tag_definitions(conn, active_only=False)}


def seed_market_tag_definitions(conn: sqlite3.Connection) -> None:
    existing = {
        row["key"]: row["display_name"]
        for row in conn.execute("SELECT key, display_name FROM market_tag_definitions").fetchall()
    }
    ts = now_ts()
    with conn:
        for idx, tag in enumerate(DEFAULT_MARKET_TAG_CHOICES):
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


def migrate_recommendation_tables(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='recommendation_evals'"
    ).fetchone()
    if not exists:
        return

    pk_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info('recommendation_evals')").fetchall()
        if int(row["pk"] or 0) > 0
    ]
    if pk_columns != ["item_id"]:
        return

    with conn:
        conn.execute("ALTER TABLE recommendation_evals RENAME TO recommendation_evals_legacy")
        conn.executescript(
            """
            CREATE TABLE recommendation_evals (
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
            CREATE INDEX idx_recommendation_evals_status ON recommendation_evals(status);
            CREATE INDEX idx_recommendation_evals_recommended ON recommendation_evals(schema_version, recommended, status);
            """
        )
        conn.execute(
            """
            INSERT INTO recommendation_evals(
              item_id, status, features_json, score, recommended, error,
              prompt_version, schema_version, weights_version, model, evaluated_at, created_at, updated_at
            )
            SELECT item_id,
                   status,
                   features_json,
                   score,
                   recommended,
                   error,
                   prompt_version,
                   COALESCE(NULLIF(schema_version, ''), 'legacy-v1'),
                   weights_version,
                   model,
                   evaluated_at,
                   created_at,
                   updated_at
            FROM recommendation_evals_legacy
            """
        )
        conn.execute("DROP TABLE recommendation_evals_legacy")


def migrate_recommendation_categories(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='recommendation_categories'"
    ).fetchone()
    if not exists:
        return
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info('recommendation_categories')").fetchall()
    }
    statements: list[str] = []
    if "background_count" not in columns:
        statements.append(
            "ALTER TABLE recommendation_categories ADD COLUMN background_count INTEGER NOT NULL DEFAULT 0"
        )
    if "positive_rate" not in columns:
        statements.append(
            "ALTER TABLE recommendation_categories ADD COLUMN positive_rate REAL NOT NULL DEFAULT 0"
        )
    if "background_rate" not in columns:
        statements.append(
            "ALTER TABLE recommendation_categories ADD COLUMN background_rate REAL NOT NULL DEFAULT 0"
        )
    if "lift_score" not in columns:
        statements.append(
            "ALTER TABLE recommendation_categories ADD COLUMN lift_score REAL NOT NULL DEFAULT 0"
        )
    if "weight_reason" not in columns:
        statements.append(
            "ALTER TABLE recommendation_categories ADD COLUMN weight_reason TEXT NOT NULL DEFAULT ''"
        )
    if not statements:
        return
    with conn:
        for statement in statements:
            conn.execute(statement)


def migrate_recommendation_keyword_tables(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='recommendation_keyword_candidates'"
    ).fetchone()
    if not exists:
        return
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info('recommendation_keyword_candidates')").fetchall()
    }
    statements: list[str] = []
    if "merged_keyword_key" not in columns:
        statements.append(
            "ALTER TABLE recommendation_keyword_candidates ADD COLUMN merged_keyword_key TEXT"
        )
    if "reviewed_at" not in columns:
        statements.append(
            "ALTER TABLE recommendation_keyword_candidates ADD COLUMN reviewed_at TEXT"
        )
    if not statements:
        return
    with conn:
        for statement in statements:
            conn.execute(statement)


def create_market_tag_key(conn: sqlite3.Connection, display_name: str) -> str:
    base = display_name.strip()
    candidate = base
    suffix = 2
    while conn.execute("SELECT 1 FROM market_tag_definitions WHERE key=?", (candidate,)).fetchone():
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


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


def resolve_detail_route(url: str) -> dict | None:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("x.com", "twitter.com"):
        return {"source": "Twitter/X", "command": [], "timeout": 0}
    return DETAIL_COMMAND_ROUTES.get(host)


def enqueue_detail_job(conn: sqlite3.Connection, item_id: str, url: str, source: str) -> bool:
    route = resolve_detail_route(url)
    ts = now_ts()
    if route and route["source"] == "Twitter/X":
        conn.execute(
            """
            INSERT INTO detail_jobs(url, item_id, source, status, attempts, queued_at, updated_at)
            VALUES (?, ?, ?, 'skipped', 0, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
              item_id=excluded.item_id,
              source=excluded.source,
              updated_at=excluded.updated_at
            """,
            (url, item_id, source, ts, ts),
        )
        return False

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


def run_opencli_detail(url: str) -> tuple[bool, dict, str]:
    route = resolve_detail_route(url)
    if not route:
        return False, {}, "UNSUPPORTED_URL"
    source = route["source"]
    command = route["command"]
    timeout = int(route.get("timeout", 30))
    if source == "Twitter/X":
        return False, {}, "SKIPPED_SOURCE"

    parsed_url = urlparse(url)
    if source == "Bloomberg" and "/news/videos/" in parsed_url.path:
        return False, {}, "SKIPPED_SOURCE: BLOOMBERG_VIDEO"

    cmd = [*command, url, "-f", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, {}, "TIMEOUT"
    except Exception as exc:
        return False, {}, f"SUBPROCESS_ERROR: {exc}"

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, {}, err or f"EXIT_{proc.returncode}"

    try:
        parsed = json.loads(proc.stdout or "[]")
    except Exception as exc:
        return False, {}, f"INVALID_JSON: {exc}"

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


def reset_current_recommendation_evals(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT re.item_id
        FROM recommendation_evals re
        LEFT JOIN item_state st ON st.item_id = re.item_id
        WHERE re.schema_version=?
          AND st.read_at IS NULL
        """,
        (RECOMMENDATION_SCHEMA_VERSION,),
    ).fetchall()
    if not rows:
        return 0
    item_ids = [row["item_id"] for row in rows if row["item_id"]]
    if not item_ids:
        return 0
    placeholders = ",".join("?" for _ in item_ids)
    conn.execute(
        f"DELETE FROM recommendation_evals WHERE schema_version=? AND item_id IN ({placeholders})",
        [RECOMMENDATION_SCHEMA_VERSION, *item_ids],
    )
    return len(item_ids)


def initialize_recommendation_categories(conn: sqlite3.Connection) -> dict[str, object]:
    samples = current_recommendation_positive_samples(conn)
    if not samples:
        recommendation_meta_set(conn, "category_init_error", "NO_POSITIVE_SAMPLES")
        return {"ok": False, "error": "NO_POSITIVE_SAMPLES", "created": 0}
    trend_contexts = current_recommendation_trend_contexts(conn)
    background_samples = current_recommendation_background_samples(conn)

    llm_settings = current_runtime_settings()["llm"]
    model_name = llm_settings["translation"]["model"]
    try:
        payload = generate_recommendation_categories(
            positive_samples=samples,
            trend_contexts=trend_contexts,
            model=model_name,
        )
    except LLMClientError as exc:
        recommendation_meta_set(conn, "category_init_error", str(exc)[:500])
        return {"ok": False, "error": str(exc)[:500], "created": 0}

    categories = payload.get("categories") or []
    if not categories:
        recommendation_meta_set(conn, "category_init_error", "EMPTY_RECOMMENDATION_CATEGORIES")
        return {"ok": False, "error": "EMPTY_RECOMMENDATION_CATEGORIES", "created": 0}

    ts = now_ts()
    returned_keys = {str(category["key"]) for category in categories}
    categories_for_prompt = [
        {
            "key": category["key"],
            "label": category["label"],
            "description": category["description"],
        }
        for category in categories
    ]
    background_counts = classify_background_samples(
        conn,
        categories_for_prompt=categories_for_prompt,
        model=model_name,
        samples=background_samples,
    )
    total_positive = max(1, len(samples))
    total_background = max(1, len(background_samples))
    with conn:
        conn.execute(
            "UPDATE recommendation_categories SET active=0, updated_at=? WHERE version=?",
            (ts, RECOMMENDATION_CATEGORY_VERSION),
        )
        for category in categories:
            positive_count = len(category["seed_item_ids"])
            background_count = int(background_counts.get(category["key"], 0))
            positive_rate = positive_count / total_positive
            background_rate = background_count / total_background
            weight, weight_reason, lift_score = recommendation_category_weight_from_stats(
                positive_count=positive_count,
                background_count=background_count,
                positive_rate=positive_rate,
                background_rate=background_rate,
            )
            conn.execute(
                """
                INSERT INTO recommendation_categories(
                  key, label, description, positive_count, background_count, positive_rate, background_rate,
                  lift_score, weight_reason, weight, active, version, seed_item_ids_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  label=excluded.label,
                  description=excluded.description,
                  positive_count=excluded.positive_count,
                  background_count=excluded.background_count,
                  positive_rate=excluded.positive_rate,
                  background_rate=excluded.background_rate,
                  lift_score=excluded.lift_score,
                  weight_reason=excluded.weight_reason,
                  weight=excluded.weight,
                  active=excluded.active,
                  version=excluded.version,
                  seed_item_ids_json=excluded.seed_item_ids_json,
                  updated_at=excluded.updated_at
                """,
                (
                    category["key"],
                    category["label"],
                    category["description"],
                    positive_count,
                    background_count,
                    positive_rate,
                    background_rate,
                    lift_score,
                    weight_reason,
                    weight,
                    RECOMMENDATION_CATEGORY_VERSION,
                    json.dumps(category["seed_item_ids"], ensure_ascii=False),
                    ts,
                    ts,
                ),
            )
        if returned_keys:
            placeholders = ",".join("?" for _ in returned_keys)
            conn.execute(
                f"""
                UPDATE recommendation_categories
                SET active=0, updated_at=?
                WHERE version=?
                  AND key NOT IN ({placeholders})
                """,
                [ts, RECOMMENDATION_CATEGORY_VERSION, *sorted(returned_keys)],
            )
        recommendation_meta_set(conn, "category_init_error", "")
    return {
        "ok": True,
        "error": "",
        "created": len(categories),
        "model": payload.get("model", ""),
        "background_samples": len(background_samples),
        "trend_contexts": len(trend_contexts),
    }


def enqueue_recommendation_eval(conn: sqlite3.Connection, item_id: str) -> bool:
    row = conn.execute(
        """
        SELECT items.id
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        WHERE items.id=? AND st.read_at IS NULL
        """,
        (item_id,),
    ).fetchone()
    if not row:
        return False

    existing = conn.execute(
        "SELECT status FROM recommendation_evals WHERE item_id=? AND schema_version=?",
        (item_id, RECOMMENDATION_SCHEMA_VERSION),
    ).fetchone()
    if existing:
        return False

    ts = now_ts()
    conn.execute(
        """
        INSERT INTO recommendation_evals(
          item_id, status, recommended, prompt_version, schema_version, weights_version, created_at, updated_at
        )
        VALUES (?, 'pending', 0, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            RECOMMENDATION_PROMPT_VERSION,
            RECOMMENDATION_SCHEMA_VERSION,
            RECOMMENDATION_WEIGHTS_VERSION,
            ts,
            ts,
        ),
    )
    return True


def enqueue_recommendation_evals_for_new_items(conn: sqlite3.Connection, item_ids: list[str]) -> int:
    queued = 0
    for item_id in item_ids:
        if enqueue_recommendation_eval(conn, item_id):
            queued += 1
    return queued


def enqueue_recommendation_init_jobs(conn: sqlite3.Connection, limit: int = RECOMMENDATION_INIT_LIMIT) -> int:
    capped = max(1, min(RECOMMENDATION_INIT_LIMIT, int(limit or RECOMMENDATION_INIT_LIMIT)))
    rows = conn.execute(
        """
        SELECT items.id
        FROM items
        LEFT JOIN item_state st ON st.item_id = items.id
        LEFT JOIN recommendation_evals re
          ON re.item_id = items.id
         AND re.schema_version = ?
        WHERE st.read_at IS NULL
          AND re.item_id IS NULL
        ORDER BY items.published_at DESC, items.id DESC
        LIMIT ?
        """,
        (RECOMMENDATION_SCHEMA_VERSION, capped),
    ).fetchall()
    queued = 0
    for row in rows:
        if enqueue_recommendation_eval(conn, row["id"]):
            queued += 1
    return queued


def process_pending_recommendation_once() -> bool:
    conn = db_conn()
    try:
        if not recommendation_category_ready(conn):
            return False

        row = conn.execute(
            """
            SELECT re.item_id,
                   re.schema_version,
                   items.title,
                   items.source,
                   items.source_type,
                   items.summary,
                   items.published_at,
                   items.url,
                   st.read_at,
                   ad.content AS detail_content
            FROM recommendation_evals re
            LEFT JOIN items ON items.id = re.item_id
            LEFT JOIN item_state st ON st.item_id = items.id
            LEFT JOIN article_details ad ON ad.url = items.url
            WHERE re.schema_version=?
              AND re.status='pending'
            ORDER BY re.created_at ASC, re.item_id ASC
            LIMIT 1
            """
        ,
            (RECOMMENDATION_SCHEMA_VERSION,),
        ).fetchone()
        if not row:
            return False

        item_id = row["item_id"]
        schema_version = row["schema_version"]
        ts = now_ts()
        if not row["title"]:
            with conn:
                conn.execute(
                    """
                    UPDATE recommendation_evals
                    SET status='skipped', error='ITEM_NOT_FOUND', evaluated_at=?, updated_at=?
                    WHERE item_id=? AND schema_version=?
                    """,
                    (ts, ts, item_id, schema_version),
                )
            return True

        if row["read_at"]:
            with conn:
                conn.execute(
                    """
                    UPDATE recommendation_evals
                    SET status='skipped', error='ALREADY_READ', evaluated_at=?, updated_at=?
                    WHERE item_id=? AND schema_version=?
                    """,
                    (ts, ts, item_id, schema_version),
                )
            return True

        llm_settings = current_runtime_settings()["llm"]
        categories = load_active_recommendation_categories(conn)
        categories_for_prompt = [
            {
                "key": category["key"],
                "label": category["label"],
                "description": category["description"],
            }
            for category in categories
        ]
        categories_by_key = {category["key"]: category for category in categories}
        source_bonus_map = recommendation_source_bonus_map(conn)
        try:
            payload = generate_recommendation_classification(
                title=(row["title"] or "").strip(),
                source=(row["source"] or "").strip(),
                published_at=(row["published_at"] or "").strip(),
                summary=(row["summary"] or "").strip(),
                detail_excerpt=((row["detail_content"] or "").strip())[:2000],
                categories=categories_for_prompt,
                model=llm_settings["translation"]["model"],
            )
            features = {
                "category_matches": payload["category_matches"],
                "entities": payload["entities"],
                "event_type": payload["event_type"],
                "sectors": payload["sectors"],
                "regions": payload["regions"],
                "new_category_candidates": payload["new_category_candidates"],
                "headline_signal": payload["headline_signal"],
            }
            score = score_recommendation_features(
                features,
                categories_by_key=categories_by_key,
                source_bonus=source_bonus_map.get(
                    derive_source_key(row["url"], row["source_type"], row["source"]),
                    0,
                ),
            )
            recommended = 1 if recommendation_passes_gate(features, score) else 0
            with conn:
                conn.execute(
                    """
                    UPDATE recommendation_evals
                    SET status='success',
                        features_json=?,
                        score=?,
                        recommended=?,
                        error=NULL,
                        prompt_version=?,
                        schema_version=?,
                        weights_version=?,
                        model=?,
                        evaluated_at=?,
                        updated_at=?
                    WHERE item_id=? AND schema_version=?
                    """,
                    (
                        serialize_recommendation_features(features),
                        score,
                        recommended,
                        RECOMMENDATION_PROMPT_VERSION,
                        RECOMMENDATION_SCHEMA_VERSION,
                        RECOMMENDATION_WEIGHTS_VERSION,
                        payload.get("model", ""),
                        ts,
                        ts,
                        item_id,
                        schema_version,
                    ),
                )
            return True
        except LLMClientError as exc:
            with conn:
                conn.execute(
                    """
                    UPDATE recommendation_evals
                    SET status='failed', error=?, evaluated_at=?, updated_at=?
                    WHERE item_id=? AND schema_version=?
                    """,
                    (str(exc)[:500], ts, ts, item_id, schema_version),
                )
            return True
    finally:
        conn.close()


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
        if not processed:
            try:
                processed = process_pending_recommendation_keyword_once()
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
        cursor = parse_feed_unread_cursor(request.args) if cursor_mode else None
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_cursor"}), 400
    join_sql = f"""
    LEFT JOIN item_state st ON st.item_id = items.id
    LEFT JOIN detail_jobs dj ON dj.url = items.url
    LEFT JOIN article_details ad ON ad.url = items.url
    LEFT JOIN article_notes an ON an.url = items.url
    LEFT JOIN recommendation_keyword_jobs rkj ON rkj.item_id = items.id
    """
    where_sql, args = _build_news_where_clause(q, read_filter, collection, source_filter)
    order_by_sql = news_order_by_sql(collection)

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
               st.read_at, st.important_at, st.read_later_at,
               dj.status AS detail_status,
               dj.last_error AS detail_error,
               CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
               an.note AS note_preview_source,
               CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
               aj.status AS ai_status,
               aj.last_error AS ai_error,
               CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready,
               rkj.status AS recommendation_job_status,
               CASE WHEN rkj.status='success' AND COALESCE(rkj.keyword_count, 0) > 0 THEN 1 ELSE 0 END AS recommendation_flag,
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
            cursor_clause, cursor_args = build_feed_unread_cursor_clause(cursor)
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
        item_ids = [r["id"] for r in rows if r["id"]]
        market_tags_map = load_market_tags_map(conn, urls)
        recommendation_keywords_map = load_recommendation_keywords_map(conn, item_ids)
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    date_counts = {
        row["date_key"]: row["total"]
        for row in date_count_rows
        if row["date_key"]
    }
    items = serialize_news_rows(items, market_tags_map, recommendation_keywords_map)
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
                   st.read_later_at,
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
                   st.read_at, st.important_at, st.read_later_at,
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
    join_sql = "LEFT JOIN item_state st ON st.item_id = items.id"
    if q:
        where.append("(items.title LIKE ? OR items.summary LIKE ? OR items.source LIKE ?)")
        like = f"%{q}%"
        args.extend([like, like, like])
    if read_filter == "unread":
        where.append("st.read_at IS NULL")
    elif read_filter == "read":
        where.append("st.read_at IS NOT NULL")
    if collection == "important":
        where.append("st.important_at IS NOT NULL")
    elif collection == "read_later":
        where.append("st.read_later_at IS NOT NULL")
    elif collection == "recommendations":
        where.append("st.read_at IS NULL")
        where.append(
            "EXISTS (SELECT 1 FROM recommendation_keyword_jobs rkj WHERE rkj.item_id = items.id AND rkj.status='success' AND rkj.keyword_count > 0)"
        )
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
                   st.read_at, st.important_at, st.read_later_at,
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
                   st.read_at, st.important_at, st.read_later_at,
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
        queued_recommendations = enqueue_recommendation_keyword_jobs_for_new_items(conn, stats.new_item_ids or [])
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
            "queued_recommendations": queued_recommendations,
        }
    )


@app.get("/api/recommendations/status")
def api_recommendation_status():
    conn = db_conn()
    try:
        snapshot = recommendation_status_snapshot(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, **snapshot})


@app.post("/api/recommendations/init")
def api_recommendation_init():
    body = request.get_json(silent=True) or {}
    raw_limit = body.get("limit", RECOMMENDATION_INIT_LIMIT)
    rebuild = bool(body.get("rebuild"))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_limit"}), 400
    conn = db_conn()
    try:
        seed_recommendation_keywords(conn)
        reset_counts = {"jobs": 0, "candidates": 0}
        if rebuild:
            reset_counts = reset_recommendation_keyword_state(conn)
        queued = enqueue_recommendation_keyword_init_jobs(conn, limit)
        snapshot = recommendation_status_snapshot(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify(
        {
            "ok": True,
            "queued": queued,
            "rebuild": rebuild,
            "reset_jobs": int(reset_counts.get("jobs", 0) or 0),
            "reset_candidates": int(reset_counts.get("candidates", 0) or 0),
            "keyword_seed_count": len(recommendation_seed_keywords()),
            "limit": max(1, min(RECOMMENDATION_KEYWORD_INIT_RECENT_LIMIT, limit)),
            **snapshot,
        }
    )


@app.get("/api/recommendation-keywords")
def api_recommendation_keywords():
    conn = db_conn()
    try:
        library = load_recommendation_keyword_library(conn)
    finally:
        conn.close()
    return jsonify({"ok": True, **library})


@app.post("/api/recommendation-keywords")
def api_recommendation_keyword_create():
    body = request.get_json(silent=True) or {}
    payload, error = parse_recommendation_keyword_body(body)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    conn = db_conn()
    try:
        if recommendation_keyword_row_exists(conn, label=str(payload["label"])):
            return jsonify({"ok": False, "error": "keyword_label_exists"}), 409
        ts = now_ts()
        keyword_key = create_recommendation_keyword_key(conn, str(payload["label"]))
        with conn:
            conn.execute(
                """
                INSERT INTO recommendation_keywords(
                  key, label, type, aliases_json, active, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'manual', ?, ?)
                """,
                (
                    keyword_key,
                    payload["label"],
                    payload["type"],
                    json.dumps(payload["aliases"], ensure_ascii=False),
                    1 if payload["active"] else 0,
                    ts,
                    ts,
                ),
            )
        library = load_recommendation_keyword_library(conn)
        snapshot = recommendation_status_snapshot(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "key": keyword_key, "requeued": 0, **library, **snapshot})


@app.patch("/api/recommendation-keywords/<keyword_key>")
def api_recommendation_keyword_update(keyword_key: str):
    body = request.get_json(silent=True) or {}

    conn = db_conn()
    try:
        existing = conn.execute(
            """
            SELECT key, label, type, aliases_json, active, source
            FROM recommendation_keywords
            WHERE key=? AND source NOT LIKE ?
            """,
            (keyword_key, f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}%"),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "keyword_not_found"}), 404
        merged_body = {
            "label": body.get("label", existing["label"]),
            "type": body.get("type", existing["type"]),
            "aliases": body.get("aliases", parse_json_array(existing["aliases_json"])),
            "active": body.get("active", bool(existing["active"])),
        }
        payload, error = parse_recommendation_keyword_body(merged_body)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        if recommendation_keyword_row_exists(conn, label=str(payload["label"]), exclude_key=keyword_key):
            return jsonify({"ok": False, "error": "keyword_label_exists"}), 409

        current_aliases = [str(alias).strip() for alias in parse_json_array(existing["aliases_json"]) if str(alias).strip()]
        current_active = bool(existing["active"])
        semantic_changed = (
            str(existing["label"] or "").strip() != str(payload["label"])
            or str(existing["type"] or "").strip() != str(payload["type"])
            or current_aliases != list(payload["aliases"])
        )

        ts = now_ts()
        requeued = 0
        item_ids = collect_recommendation_keyword_item_ids(conn, keyword_key) if (semantic_changed or (current_active and not payload["active"])) else []
        with conn:
            conn.execute(
                """
                UPDATE recommendation_keywords
                SET label=?, type=?, aliases_json=?, active=?, updated_at=?
                WHERE key=?
                """,
                (
                    payload["label"],
                    payload["type"],
                    json.dumps(payload["aliases"], ensure_ascii=False),
                    1 if payload["active"] else 0,
                    ts,
                    keyword_key,
                ),
            )
            if item_ids:
                requeued = reset_recommendation_keyword_jobs_for_items(conn, item_ids)
        library = load_recommendation_keyword_library(conn)
        snapshot = recommendation_status_snapshot(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "requeued": requeued, **library, **snapshot})


@app.delete("/api/recommendation-keywords/<keyword_key>")
def api_recommendation_keyword_delete(keyword_key: str):
    conn = db_conn()
    try:
        existing = conn.execute(
            """
            SELECT key, source
            FROM recommendation_keywords
            WHERE key=? AND source NOT LIKE ?
            """,
            (keyword_key, f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}%"),
        ).fetchone()
        if not existing:
            return jsonify({"ok": False, "error": "keyword_not_found"}), 404

        item_ids = collect_recommendation_keyword_item_ids(conn, keyword_key)
        ts = now_ts()
        with conn:
            conn.execute(
                "UPDATE recommendation_keyword_candidates SET merged_keyword_key=NULL WHERE merged_keyword_key=?",
                (keyword_key,),
            )
            if str(existing["source"] or "") == "seed":
                conn.execute(
                    """
                    UPDATE recommendation_keywords
                    SET active=0, source=?, updated_at=?
                    WHERE key=?
                    """,
                    (f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}seed", ts, keyword_key),
                )
            else:
                conn.execute("DELETE FROM recommendation_keywords WHERE key=?", (keyword_key,))
            requeued = reset_recommendation_keyword_jobs_for_items(conn, item_ids)
        library = load_recommendation_keyword_library(conn)
        snapshot = recommendation_status_snapshot(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "requeued": requeued, **library, **snapshot})


@app.post("/api/recommendation-keywords/candidates/<int:candidate_id>/review")
def api_recommendation_keyword_candidate_review(candidate_id: int):
    body = request.get_json(silent=True) or {}
    action = (body.get("action") or "").strip().lower()
    if action not in {"accept_new", "merge", "reject"}:
        return jsonify({"ok": False, "error": "invalid_action"}), 400
    target_keyword_key = (body.get("target_keyword_key") or "").strip()

    conn = db_conn()
    try:
        candidate = conn.execute(
            """
            SELECT id, normalized_label, label, type, aliases_json, reason, sample_item_ids_json, status
            FROM recommendation_keyword_candidates
            WHERE id=?
            """,
            (candidate_id,),
        ).fetchone()
        if not candidate:
            return jsonify({"ok": False, "error": "candidate_not_found"}), 404
        if (candidate["status"] or "pending") != "pending":
            return jsonify({"ok": False, "error": "candidate_already_reviewed"}), 409
        if action == "merge" and not target_keyword_key:
            return jsonify({"ok": False, "error": "missing_target_keyword_key"}), 400

        candidate_aliases = [str(alias).strip() for alias in parse_json_array(candidate["aliases_json"]) if str(alias).strip()]
        sample_item_ids = [str(item_id).strip() for item_id in parse_json_array(candidate["sample_item_ids_json"]) if str(item_id).strip()]
        label = (candidate["label"] or "").strip()
        keyword_type = (candidate["type"] or "domain").strip()
        ts = now_ts()
        requeued = 0
        with conn:
            merged_keyword_key = ""
            if action == "reject":
                conn.execute(
                    """
                    UPDATE recommendation_keyword_candidates
                    SET status='rejected', merged_keyword_key=NULL, reviewed_at=?, updated_at=?
                    WHERE id=?
                    """,
                    (ts, ts, candidate_id),
                )
            elif action == "accept_new":
                duplicate = conn.execute(
                    """
                    SELECT key, aliases_json
                    FROM recommendation_keywords
                    WHERE label=? COLLATE NOCASE
                      AND source NOT LIKE ?
                    """,
                    (label, f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}%"),
                ).fetchone()
                if duplicate:
                    merged_keyword_key = duplicate["key"]
                    merged_aliases = merge_unique_texts(
                        parse_json_array(duplicate["aliases_json"]),
                        candidate_aliases,
                    )
                    conn.execute(
                        """
                        UPDATE recommendation_keywords
                        SET aliases_json=?, active=1, updated_at=?
                        WHERE key=?
                        """,
                        (json.dumps(merged_aliases, ensure_ascii=False), ts, merged_keyword_key),
                    )
                    conn.execute(
                        """
                        UPDATE recommendation_keyword_candidates
                        SET status='merged', merged_keyword_key=?, reviewed_at=?, updated_at=?
                        WHERE id=?
                        """,
                        (merged_keyword_key, ts, ts, candidate_id),
                    )
                else:
                    merged_keyword_key = create_recommendation_keyword_key(conn, label)
                    aliases = merge_unique_texts(candidate_aliases)
                    conn.execute(
                        """
                        INSERT INTO recommendation_keywords(
                          key, label, type, aliases_json, active, source, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, 1, 'candidate_review', ?, ?)
                        """,
                        (
                            merged_keyword_key,
                            label,
                            keyword_type,
                            json.dumps(aliases, ensure_ascii=False),
                            ts,
                            ts,
                        ),
                    )
                    conn.execute(
                        """
                        UPDATE recommendation_keyword_candidates
                        SET status='accepted', merged_keyword_key=?, reviewed_at=?, updated_at=?
                        WHERE id=?
                        """,
                        (merged_keyword_key, ts, ts, candidate_id),
                    )
                requeued = reset_recommendation_keyword_jobs_for_items(conn, sample_item_ids)
            else:
                target = conn.execute(
                    """
                    SELECT key, label, aliases_json
                    FROM recommendation_keywords
                    WHERE key=? AND source NOT LIKE ?
                    """,
                    (target_keyword_key, f"{RECOMMENDATION_KEYWORD_DELETED_SOURCE_PREFIX}%"),
                ).fetchone()
                if not target:
                    return jsonify({"ok": False, "error": "target_keyword_not_found"}), 404
                merged_keyword_key = target["key"]
                merged_aliases = merge_unique_texts(
                    parse_json_array(target["aliases_json"]),
                    [label],
                    candidate_aliases,
                )
                conn.execute(
                    """
                    UPDATE recommendation_keywords
                    SET aliases_json=?, active=1, updated_at=?
                    WHERE key=?
                    """,
                    (json.dumps(merged_aliases, ensure_ascii=False), ts, merged_keyword_key),
                )
                conn.execute(
                    """
                    UPDATE recommendation_keyword_candidates
                    SET status='merged', merged_keyword_key=?, reviewed_at=?, updated_at=?
                    WHERE id=?
                    """,
                    (merged_keyword_key, ts, ts, candidate_id),
                )
                requeued = reset_recommendation_keyword_jobs_for_items(conn, sample_item_ids)

        library = load_recommendation_keyword_library(conn)
        snapshot = recommendation_status_snapshot(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "requeued": requeued, **library, **snapshot})


@app.post("/api/recommendations/feedback")
def api_recommendation_feedback():
    body = request.get_json(silent=True) or {}
    event_type = (body.get("event_type") or "").strip().lower()
    source_context = (body.get("source_context") or "recommendations").strip().lower() or "recommendations"
    if event_type not in RECOMMENDATION_FEEDBACK_TYPES:
        return jsonify({"ok": False, "error": "invalid_event_type"}), 400
    raw_ids = body.get("item_ids")
    item_id = (body.get("item_id") or "").strip()
    item_ids = []
    if isinstance(raw_ids, list):
        item_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
    elif item_id:
        item_ids = [item_id]
    if not item_ids:
        return jsonify({"ok": False, "error": "missing_item_ids"}), 400

    ts = now_ts()
    conn = db_conn()
    try:
        valid_rows = conn.execute(
            f"SELECT id FROM items WHERE id IN ({','.join('?' for _ in item_ids)})",
            item_ids,
        ).fetchall()
        valid_ids = [row["id"] for row in valid_rows]
        if not valid_ids:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        with conn:
            conn.executemany(
                """
                INSERT INTO recommendation_feedback(item_id, event_type, source_context, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [(item, event_type, source_context, ts) for item in valid_ids],
            )
    finally:
        conn.close()
    return jsonify({"ok": True, "count": len(valid_ids)})


@app.patch("/api/news/<item_id>/state")
def api_update_item_state(item_id: str):
    body = request.get_json(silent=True) or {}
    allowed = ("read", "important", "read_later")
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
            "SELECT read_at, important_at, read_later_at FROM item_state WHERE item_id=?",
            (item_id,),
        ).fetchone()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        read_at = old_state["read_at"] if old_state else None
        important_at = old_state["important_at"] if old_state else None
        read_later_at = old_state["read_later_at"] if old_state else None
        if "read" in body:
            read_at = ts if body["read"] else None
        if "important" in body:
            important_at = ts if body["important"] else None
        if "read_later" in body:
            read_later_at = ts if body["read_later"] else None
        with conn:
            conn.execute(
                """
                INSERT INTO item_state(item_id, read_at, important_at, read_later_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                  read_at=excluded.read_at,
                  important_at=excluded.important_at,
                  read_later_at=excluded.read_later_at,
                  updated_at=excluded.updated_at
                """,
                (item_id, read_at, important_at, read_later_at, ts),
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
        }
    )


@app.get("/api/news/<item_id>/detail")
def api_news_detail(item_id: str):
    conn = db_conn()
    try:
        item = conn.execute(
            "SELECT id, title, url, source, summary FROM items WHERE id=?",
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
        market_tag_choices = load_market_tag_definitions(conn, active_only=True)
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
                "SELECT title, author, published_at, content, content_length, fetched_at FROM article_details WHERE url=?",
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
    finally:
        conn.close()

    return jsonify(
        {
            "ok": True,
            "item_id": item_id,
            "url": item["url"],
            "detail_status": (job["status"] if job else "none"),
            "job": dict(job) if job else None,
            "detail": dict(detail) if detail else None,
            "ai_status": (ai_job["status"] if ai_job else "none"),
            "ai_job": dict(ai_job) if ai_job else None,
            "ai": dict(ai) if ai else None,
            "has_note": 1 if note_row else 0,
            "note": (dict(note_row) if note_row else None),
            "market_tags": market_tags,
            "has_market_tags": 1 if market_tags else 0,
            "market_tag_choices": market_tag_choices,
            "chat_providers": chat_provider_catalog(),
        }
    )


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
            "SELECT id, title, url, source, published_at FROM items WHERE id=?",
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
    finally:
        conn.close()

    if not detail or not (detail["content"] or "").strip():
        return jsonify({"ok": False, "error": "detail_not_ready"}), 409

    lock = codex_chat_lock(item_id)
    if not lock.acquire(blocking=False):
        return jsonify({"ok": False, "error": "provider_busy"}), 409

    try:
        payload = run_codex_chat(
            question=question,
            session_id=session_id,
            model=model,
            reset=reset,
            title=(detail["title"] or item["title"] or "").strip(),
            source=(detail["source"] or item["source"] or "").strip(),
            published_at=(detail["published_at"] or item["published_at"] or "").strip(),
            content=(detail["content"] or "").strip(),
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

    return jsonify({"ok": True, **payload})


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
                "SELECT read_at, important_at, read_later_at FROM item_state WHERE item_id=?",
                (item_id,),
            ).fetchone()
            read_at = row["read_at"] if row else None
            important_at = row["important_at"] if row else None
            read_later_at = row["read_later_at"] if row else None
            if not important_at:
                important_at = ts
                conn.execute(
                    """
                    INSERT INTO item_state(item_id, read_at, important_at, read_later_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(item_id) DO UPDATE SET
                      read_at=excluded.read_at,
                      important_at=excluded.important_at,
                      read_later_at=excluded.read_later_at,
                      updated_at=excluded.updated_at
                    """,
                    (item_id, read_at, important_at, read_later_at, ts),
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
        row = conn.execute("SELECT id, url, source FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "item_not_found"}), 404
        if not row["url"]:
            return jsonify({"ok": False, "error": "missing_url"}), 400
        has_detail = conn.execute("SELECT 1 FROM article_details WHERE url=?", (row["url"],)).fetchone()
        with conn:
            ts = now_ts()
            if has_detail:
                enqueue_ai_job(conn, row["url"])
                conn.execute(
                    """
                    UPDATE ai_jobs
                    SET status='pending', last_error=NULL, queued_at=?, updated_at=?
                    WHERE url=?
                    """,
                    (ts, ts, row["url"]),
                )
            else:
                created = enqueue_detail_job(conn, row["id"], row["url"], row["source"] or "")
                if not created:
                    conn.execute(
                        "UPDATE detail_jobs SET status='pending', last_error=NULL, queued_at=?, updated_at=? WHERE url=?",
                        (ts, ts, row["url"]),
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
                INSERT INTO item_state(item_id, read_later_at, updated_at)
                VALUES (?, NULL, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                  read_later_at=NULL,
                  updated_at=excluded.updated_at
                """,
                [(item_id, ts) for item_id in item_ids],
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
