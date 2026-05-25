from __future__ import annotations

import math
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from scanner import apply_schema, reindex
from settings import resolve_daily_news_dir, resolve_db_path


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
STATIC_DIR = BASE_DIR / "static"
DAILY_NEWS_DIR = resolve_daily_news_dir()
DB_PATH = resolve_db_path()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")


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
    join_sql = "LEFT JOIN item_state st ON st.item_id = items.id"
    if q:
        where.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
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
            SELECT id, source_file, item_order, published_at, date, time, source,
                   source_type, source_name, title, summary, url,
                   st.read_at, st.important_at, st.read_later_at
            FROM items
            {join_sql}
            {where_sql}
            ORDER BY published_at DESC, source_file DESC, item_order ASC
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


@app.post("/api/news/mark-all-read")
def api_mark_all_read():
    body = request.get_json(silent=True) or {}
    q = (body.get("q") or "").strip()
    read_filter = (body.get("read_filter") or "all").strip().lower()
    collection = (body.get("collection") or "feed").strip().lower()

    where = []
    args: list = []
    if q:
        where.append("(title LIKE ? OR summary LIKE ? OR source LIKE ?)")
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
    app.run(host="127.0.0.1", port=8080, debug=False)


if __name__ == "__main__":
    main()
