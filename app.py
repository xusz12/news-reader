from __future__ import annotations

import math
import json
import sqlite3
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, request, send_from_directory

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
    "reuters.com": ("Reuters", ["opencli", "reuters", "article-detail"]),
    "bloomberg.com": ("Bloomberg", ["opencli", "bloomberg", "news"]),
    "techcrunch.com": ("TechCrunch", ["opencli", "TechcrunchPublic", "article"]),
    "arstechnica.com": ("Ars Technica", ["opencli", "ArsPublic", "article"]),
}


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    conn = db_conn()
    try:
        apply_schema(conn, SCHEMA_PATH)
    finally:
        conn.close()


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def resolve_detail_route(url: str) -> tuple[str, list[str]] | None:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in ("x.com", "twitter.com"):
        return ("Twitter/X", [])
    return DETAIL_COMMAND_ROUTES.get(host)


def enqueue_detail_job(conn: sqlite3.Connection, item_id: str, url: str, source: str) -> bool:
    route = resolve_detail_route(url)
    ts = now_ts()
    if route and route[0] == "Twitter/X":
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
    source, command = route
    if source == "Twitter/X":
        return False, {}, "SKIPPED_SOURCE"

    cmd = [*command, url, "-f", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
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


def detail_worker_loop() -> None:
    while not WORKER_STOP.is_set():
        processed = False
        try:
            processed = process_pending_jobs_once()
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
    page = max(1, int(request.args.get("page", "1")))
    per = min(100, max(10, int(request.args.get("per", "30"))))
    where = []
    args: list = []
    join_sql = """
    LEFT JOIN item_state st ON st.item_id = items.id
    LEFT JOIN detail_jobs dj ON dj.url = items.url
    LEFT JOIN article_details ad ON ad.url = items.url
    """
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
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

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
                   CASE WHEN ad.url IS NULL THEN 0 ELSE 1 END AS detail_ready
            FROM items
            {join_sql}
            {where_sql}
            ORDER BY items.published_at DESC, items.source_file DESC, items.item_order ASC
            LIMIT ? OFFSET ?
            """,
            [*args, per, offset],
        ).fetchall()
    finally:
        conn.close()

    items = [dict(r) for r in rows]
    pages = max(1, math.ceil(total / per)) if total else 1
    return jsonify(
        {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
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
        if url:
            job = conn.execute(
                "SELECT status, attempts, last_error, queued_at, started_at, finished_at FROM detail_jobs WHERE url=?",
                (url,),
            ).fetchone()
            detail = conn.execute(
                "SELECT title, author, published_at, content, content_length, fetched_at FROM article_details WHERE url=?",
                (url,),
            ).fetchone()
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
        with conn:
            created = enqueue_detail_job(conn, row["id"], row["url"], row["source"] or "")
            if not created:
                conn.execute(
                    "UPDATE detail_jobs SET status='pending', last_error=NULL, queued_at=?, updated_at=? WHERE url=?",
                    (now_ts(), now_ts(), row["url"]),
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


def main() -> None:
    ensure_db()
    start_detail_worker()
    app.run(host="127.0.0.1", port=8080, debug=False)


if __name__ == "__main__":
    main()
