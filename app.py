from __future__ import annotations

import math
import json
import os
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, request, send_from_directory

from llm_client import LLMClientError, generate_article_ai, generate_gemini_fallback_translation
from scanner import apply_schema, reindex
from settings import resolve_daily_news_dir, resolve_db_path


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
STATIC_DIR = BASE_DIR / "static"
DAILY_NEWS_DIR = resolve_daily_news_dir()
DB_PATH = resolve_db_path()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

DETAIL_LOCK = threading.Lock()
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
COALESCE(NULLIF(items.date, ''), substr(items.published_at, 1, 10)) DESC,
items.published_at ASC,
items.id ASC
"""

NON_FEED_NEWS_ORDER_BY_SQL = """
COALESCE(NULLIF(items.date, ''), substr(items.published_at, 1, 10)) DESC,
items.published_at DESC,
items.id DESC
"""

ITEM_DATE_SQL = "COALESCE(NULLIF(items.date, ''), substr(items.published_at, 1, 10))"


def news_order_by_sql(collection: str) -> str:
    return FEED_NEWS_ORDER_BY_SQL if collection in ("feed", "read_later") else NON_FEED_NEWS_ORDER_BY_SQL


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


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    conn = db_conn()
    try:
        apply_schema(conn, SCHEMA_PATH)
        migrate_market_trend_notes(conn)
        seed_market_tag_definitions(conn)
    finally:
        conn.close()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
            payload = generate_article_ai(
                title=(detail["title"] or "").strip(),
                source=(detail["source"] or "").strip(),
                content=(detail["content"] or "").strip(),
            )
            ok = True
        except LLMClientError as exc:
            primary_error = str(exc)
            try:
                payload = generate_gemini_fallback_translation(
                    title=(detail["title"] or "").strip(),
                    source=(detail["source"] or "").strip(),
                    content=(detail["content"] or "").strip(),
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
    join_sql = """
    LEFT JOIN item_state st ON st.item_id = items.id
    LEFT JOIN detail_jobs dj ON dj.url = items.url
    LEFT JOIN article_details ad ON ad.url = items.url
    LEFT JOIN article_notes an ON an.url = items.url
    """
    where_sql, args = _build_news_where_clause(q, read_filter, collection, source_filter)
    order_by_sql = news_order_by_sql(collection)

    conn = db_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM items {join_sql} {where_sql}",
            args,
        ).fetchone()[0]

        offset = (page - 1) * per
        rows = conn.execute(
            f"""
            SELECT items.id, items.source_file, items.item_order, items.published_at,
                   items.date, items.time, items.source, items.source_type,
                   items.source_name, items.title, items.summary, items.url,
                   st.read_at, st.important_at, st.read_later_at,
                   dj.status AS detail_status,
                   dj.last_error AS detail_error,
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready,
                   CASE WHEN an.url IS NULL THEN 0 ELSE 1 END AS has_note,
                   aj.status AS ai_status,
                   aj.last_error AS ai_error,
                   CASE WHEN aa.url IS NULL THEN 0 ELSE 1 END AS ai_ready
            FROM items
            {join_sql}
            LEFT JOIN ai_jobs aj ON aj.url = items.url
            LEFT JOIN article_ai aa ON aa.url = items.url
            {where_sql}
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
    for item in items:
        tags = market_tags_map.get(item.get("url") or "", [])
        item["market_tags"] = tags
        item["has_market_tags"] = 1 if tags else 0
        item["source_key"] = derive_source_key(item.get("url"), item.get("source_type"), item.get("source"))
        date_key, date_label = derive_date_meta(item.get("published_at"), item.get("date"))
        item["date_key"] = date_key
        item["date_label"] = date_label
    pages = max(1, math.ceil(total / per)) if total else 1
    return jsonify(
        {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
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
    finally:
        conn.close()
    return jsonify(
        {
            "ok": True,
            "scanned_files": stats.scanned_files,
            "changed_files": stats.changed_files,
            "upserted": stats.upserted,
            "deleted_stale": stats.deleted_stale,
        }
    )


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
                "SELECT model, key_points_zh, conclusion_zh, body_zh, generated_at FROM article_ai WHERE url=?",
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
