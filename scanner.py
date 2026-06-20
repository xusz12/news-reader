from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from parser import parse_daily_file


@dataclass
class ReindexStats:
    scanned_files: int = 0
    changed_files: int = 0
    upserted: int = 0
    deleted_stale: int = 0


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_item_id(date: str, source: str, title: str, url: str) -> str:
    basis = f"{date}|{url}" if url else f"{date}|{source}|{title}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def apply_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(item_state)").fetchall()
    }
    if "important_at" not in cols:
        conn.execute("ALTER TABLE item_state ADD COLUMN important_at TEXT")
    if "read_later_at" not in cols:
        conn.execute("ALTER TABLE item_state ADD COLUMN read_later_at TEXT")
    if "favorite_at" not in cols:
        conn.execute("ALTER TABLE item_state ADD COLUMN favorite_at TEXT")
    if "bookmarked" in cols:
        conn.execute(
            """
            UPDATE item_state
            SET favorite_at = COALESCE(
              favorite_at,
              updated_at,
              read_at,
              important_at,
              read_later_at,
              datetime('now', 'localtime')
            )
            WHERE bookmarked = 1 AND favorite_at IS NULL
            """
        )
    conn.commit()


def list_daily_files(root: Path) -> list[Path]:
    return sorted(root.rglob("dailyFreshNews_*.md"))


def load_source_record(conn: sqlite3.Connection, rel_path: str) -> tuple[float, int] | None:
    row = conn.execute(
        "SELECT mtime, size FROM source_files WHERE path = ?",
        (rel_path,),
    ).fetchone()
    if not row:
        return None
    return float(row[0]), int(row[1])


def reindex(
    conn: sqlite3.Connection,
    daily_root: Path,
    *,
    full: bool = False,
) -> ReindexStats:
    stats = ReindexStats()
    files = list_daily_files(daily_root)
    stats.scanned_files = len(files)

    if full:
        conn.execute("DELETE FROM items")
        conn.execute("DELETE FROM source_files")
        conn.commit()

    for path in files:
        rel_path = str(path.relative_to(daily_root))
        st = path.stat()
        current = (float(st.st_mtime), int(st.st_size))
        old = load_source_record(conn, rel_path)
        if old == current:
            continue

        stats.changed_files += 1
        parsed = parse_daily_file(path)
        ts = now_iso()
        new_ids: list[str] = []

        with conn:
            for it in parsed:
                item_id = make_item_id(it.date, it.source, it.title, it.url)
                new_ids.append(item_id)
                conn.execute(
                    """
                    INSERT INTO items (
                      id, source_file, item_order, published_at, date, time, source,
                      source_type, source_name, title, summary, url, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      source_file=excluded.source_file,
                      item_order=excluded.item_order,
                      published_at=excluded.published_at,
                      date=excluded.date,
                      time=excluded.time,
                      source=excluded.source,
                      source_type=excluded.source_type,
                      source_name=excluded.source_name,
                      title=excluded.title,
                      summary=excluded.summary,
                      url=excluded.url,
                      updated_at=excluded.updated_at
                    """,
                    (
                        item_id,
                        rel_path,
                        it.item_order,
                        it.published_at,
                        it.date,
                        it.time,
                        it.source,
                        it.source_type,
                        it.source_name,
                        it.title,
                        it.summary,
                        it.url,
                        ts,
                        ts,
                    ),
                )
                stats.upserted += 1

            if new_ids:
                placeholders = ",".join("?" for _ in new_ids)
                cur = conn.execute(
                    f"DELETE FROM items WHERE source_file=? AND id NOT IN ({placeholders})",
                    [rel_path, *new_ids],
                )
            else:
                cur = conn.execute("DELETE FROM items WHERE source_file=?", (rel_path,))
            stats.deleted_stale += cur.rowcount

            conn.execute(
                """
                INSERT INTO source_files (path, mtime, size, last_scanned_at, item_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                  mtime=excluded.mtime,
                  size=excluded.size,
                  last_scanned_at=excluded.last_scanned_at,
                  item_count=excluded.item_count
                """,
                (rel_path, current[0], current[1], ts, len(parsed)),
            )

    conn.commit()
    return stats
