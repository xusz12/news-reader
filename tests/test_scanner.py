from __future__ import annotations

import sqlite3
from pathlib import Path

from scanner import apply_schema, reindex


def make_daily(path: Path, title: str, url: str, t: str = "08:00:00"):
    path.write_text(
        f"""## Reuters · World（1条）
### [{title}]({url})
- 发布时间：2026-05-25 {t}
""",
        encoding="utf-8",
    )


def test_reindex_is_idempotent_and_updates(tmp_path: Path):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    f = daily_dir / "dailyFreshNews_2026-05-25.md"
    make_daily(f, "A", "https://example.com/a")

    conn = sqlite3.connect(":memory:")
    apply_schema(conn, Path(__file__).resolve().parents[1] / "schema.sql")

    s1 = reindex(conn, tmp_path / "DailyNews")
    assert s1.changed_files == 1
    c1 = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert c1 == 1

    s2 = reindex(conn, tmp_path / "DailyNews")
    assert s2.changed_files == 0
    c2 = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert c2 == 1

    make_daily(f, "A-UPDATED", "https://example.com/a", "09:00:00")
    s3 = reindex(conn, tmp_path / "DailyNews")
    assert s3.changed_files == 1
    row = conn.execute("SELECT title, published_at FROM items").fetchone()
    assert row[0] == "A-UPDATED"
    assert row[1].endswith("09:00")


def test_stale_delete_and_item_state_preserved(tmp_path: Path):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    f = daily_dir / "dailyFreshNews_2026-05-25.md"
    f.write_text(
        """## Reuters · World（2条）
### [A](https://example.com/a)
- 发布时间：2026-05-25 08:00:00
### [B](https://example.com/b)
- 发布时间：2026-05-25 08:05:00
""",
        encoding="utf-8",
    )

    conn = sqlite3.connect(":memory:")
    apply_schema(conn, Path(__file__).resolve().parents[1] / "schema.sql")
    reindex(conn, tmp_path / "DailyNews")
    ids = [r[0] for r in conn.execute("SELECT id FROM items ORDER BY id").fetchall()]
    assert len(ids) == 2

    conn.execute(
        "INSERT INTO item_state(item_id, bookmarked, skipped, read_at, updated_at) VALUES (?,1,0,NULL,'2026-05-25 10:00:00')",
        (ids[0],),
    )
    conn.commit()

    f.write_text(
        """## Reuters · World（1条）
### [A](https://example.com/a)
- 发布时间：2026-05-25 08:00:00
""",
        encoding="utf-8",
    )
    stats = reindex(conn, tmp_path / "DailyNews")
    assert stats.deleted_stale >= 1
    cnt_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert cnt_items == 1
    cnt_state = conn.execute("SELECT COUNT(*) FROM item_state").fetchone()[0]
    assert cnt_state == 1
