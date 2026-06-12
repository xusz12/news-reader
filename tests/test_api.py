from __future__ import annotations

import importlib
import json
import types
from datetime import datetime, timedelta
from pathlib import Path


def test_api_news_and_reindex(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（1条）
### [API 测试新闻](https://example.com/api)
- 发布时间：2026-05-25 12:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()

    r = client.post("/api/reindex", json={})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    r2 = client.get("/api/news?page=1&per=20")
    assert r2.status_code == 200
    data = r2.get_json()
    assert data["total"] == 1
    assert data["items"][0]["url"] == "https://example.com/api"
    assert data["items"][0]["date_key"] == "2026-05-25"
    assert isinstance(data["items"][0]["date_label"], str)
    assert data["items"][0]["date_label"]
    item_id = data["items"][0]["id"]
    assert data["items"][0]["read_at"] is None
    assert data["items"][0]["important_at"] is None
    assert data["items"][0]["read_later_at"] is None

    r3 = client.patch(f"/api/news/{item_id}/state", json={"read": True})
    assert r3.status_code == 200
    assert r3.get_json()["ok"] is True
    assert r3.get_json()["read_at"] is not None

    r4 = client.get("/api/news?read_filter=read")
    assert r4.status_code == 200
    assert r4.get_json()["total"] == 1

    r5 = client.patch(f"/api/news/{item_id}/state", json={"read": False})
    assert r5.status_code == 200
    assert r5.get_json()["read_at"] is None
    assert r5.get_json()["important_at"] is None

    r6 = client.get("/api/news?read_filter=unread")
    assert r6.status_code == 200
    assert r6.get_json()["total"] == 1

    # New flags should be independent and combinable.
    r7 = client.patch(
        f"/api/news/{item_id}/state",
        json={"important": True, "read_later": True},
    )
    assert r7.status_code == 200
    assert r7.get_json()["important_at"] is not None
    assert r7.get_json()["read_later_at"] is not None

    important = client.get("/api/news?collection=important")
    assert important.status_code == 200
    assert important.get_json()["total"] == 1

    read_later = client.get("/api/news?collection=read_later")
    assert read_later.status_code == 200
    assert read_later.get_json()["total"] == 1

    combo = client.get("/api/news?collection=important&read_filter=unread")
    assert combo.status_code == 200
    assert combo.get_json()["total"] == 1


def test_global_search_mvp(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-04.md").write_text(
        """## Reuters · World（2条）
### [AlphaTitle](https://example.com/alpha)
- 发布时间：2026-06-04 09:00:00
### [BetaTitle](https://example.com/beta)
- 发布时间：2026-06-04 11:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: name == "DEEPSEEK_API_KEY")
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news?per=20").get_json()["items"]
    alpha = next(item for item in items if item["title"] == "AlphaTitle")

    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alpha["url"],
                    "Reuters",
                    "AlphaTitle",
                    "Reporter",
                    "2026-06-04 09:00:00",
                    "AlphaX body-needle full english content for search",
                    48,
                    "{}",
                    ts,
                    ts,
                ),
            )
            conn.execute(
                """
                INSERT INTO article_ai(url, model, key_points_zh, conclusion_zh, body_zh, raw_json, generated_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alpha["url"],
                    "deepseek-chat",
                    json.dumps(["锂电扩产"], ensure_ascii=False),
                    "中文结论",
                    "中文正文命中 AlphaX",
                    "{}",
                    ts,
                    ts,
                ),
            )
        
    finally:
        conn.close()

    note_res = client.put(f"/api/news/{alpha['id']}/note", json={"note": "我的独特想法 AlphaX"})
    assert note_res.status_code == 200

    create_tag = client.post("/api/market-tags", json={"display_name": "宏观Beta"})
    assert create_tag.status_code == 200
    tag_key = create_tag.get_json()["tag"]["key"]
    assert client.put(
        f"/api/news/{alpha['id']}/market-tag",
        json={"tag": tag_key, "direction": "bullish"},
    ).status_code == 200
    assert client.patch(
        f"/api/market-tags/{tag_key}",
        json={"display_name": "大宏观"},
    ).status_code == 200

    title_hit = client.get("/api/search?q=AlphaTitle&per=20")
    assert title_hit.status_code == 200
    assert [item["title"] for item in title_hit.get_json()["items"]] == ["AlphaTitle"]

    english_hit = client.get("/api/search?q=body-needle&per=20").get_json()
    assert english_hit["total"] == 1
    assert english_hit["items"][0]["title"] == "AlphaTitle"

    ai_body_hit = client.get("/api/search?q=中文正文命中&per=20").get_json()
    assert ai_body_hit["total"] == 1
    assert ai_body_hit["items"][0]["title"] == "AlphaTitle"

    ai_points_hit = client.get("/api/search?q=锂电扩产&per=20").get_json()
    assert ai_points_hit["total"] == 1
    assert ai_points_hit["items"][0]["title"] == "AlphaTitle"

    note_hit = client.get("/api/search?q=独特想法&per=20").get_json()
    assert note_hit["total"] == 1
    assert note_hit["items"][0]["title"] == "AlphaTitle"
    assert note_hit["items"][0]["note_preview"] == "我的独特想法 AlphaX"

    tag_key_hit = client.get(f"/api/search?q={tag_key}&per=20").get_json()
    assert tag_key_hit["total"] == 1
    assert tag_key_hit["items"][0]["title"] == "AlphaTitle"

    tag_label_hit = client.get("/api/search?q=大宏观&per=20").get_json()
    assert tag_label_hit["total"] == 1
    assert tag_label_hit["items"][0]["title"] == "AlphaTitle"
    assert tag_label_hit["items"][0]["market_tags"][0]["tag"] == "大宏观"

    dedup_hit = client.get("/api/search?q=AlphaX&per=20").get_json()
    assert dedup_hit["total"] == 1
    assert [item["title"] for item in dedup_hit["items"]] == ["AlphaTitle"]

    empty_hit = client.get("/api/search?q=")
    assert empty_hit.status_code == 200
    assert empty_hit.get_json()["items"] == []
    assert empty_hit.get_json()["total"] == 0

    missing_hit = client.get("/api/search?q=no-such-needle&per=20").get_json()
    assert missing_hit["total"] == 0
    assert missing_hit["items"] == []


def test_feed_and_non_feed_sorting_split(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（3条）
### [Morning](https://example.com/morning)
- 发布时间：2026-06-02 09:00:00
### [Noon](https://example.com/noon)
- 发布时间：2026-06-02 12:00:00
### [Evening](https://example.com/evening)
- 发布时间：2026-06-02 18:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()

    assert client.post("/api/reindex", json={}).status_code == 200

    feed_items = client.get("/api/news?per=20").get_json()["items"]
    assert [item["title"] for item in feed_items] == ["Morning", "Noon", "Evening"]

    for item in feed_items:
        res = client.patch(f"/api/news/{item['id']}/state", json={"important": True})
        assert res.status_code == 200

    important_items = client.get("/api/news?collection=important&per=20").get_json()["items"]
    assert [item["title"] for item in important_items] == ["Evening", "Noon", "Morning"]

    for item in feed_items:
        res = client.patch(f"/api/news/{item['id']}/state", json={"read_later": True})
        assert res.status_code == 200

    read_later_items = client.get("/api/news?collection=read_later&per=20").get_json()["items"]
    assert [item["title"] for item in read_later_items] == ["Morning", "Noon", "Evening"]


def test_read_later_cross_date_order_matches_feed_old_to_new(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（4条）
### [D2-later](https://example.com/d2-later)
- 发布时间：2026-06-02 18:00:00
### [D1-middle](https://example.com/d1-middle)
- 发布时间：2026-06-03 12:00:00
### [D1-early](https://example.com/d1-early)
- 发布时间：2026-06-03 08:00:00
### [D2-early](https://example.com/d2-early)
- 发布时间：2026-06-02 06:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: name == "DEEPSEEK_API_KEY")
    app_module.ensure_db()
    client = app_module.app.test_client()

    assert client.post("/api/reindex", json={}).status_code == 200
    feed_items = client.get("/api/news?per=20").get_json()["items"]
    assert [item["title"] for item in feed_items] == ["D2-early", "D2-later", "D1-early", "D1-middle"]

    for item in feed_items:
        res = client.patch(f"/api/news/{item['id']}/state", json={"read_later": True})
        assert res.status_code == 200

    read_later_items = client.get("/api/news?collection=read_later&per=20").get_json()["items"]
    assert [item["title"] for item in read_later_items] == ["D2-early", "D2-later", "D1-early", "D1-middle"]


def test_feed_unread_cursor_paging_survives_auto_read_shrink(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)

    reuters_items = []
    for idx in range(31):
        minute = idx % 60
        reuters_items.append(
            "\n".join(
                [
                    f"### [Reuters {idx + 1}](https://www.reuters.com/world/test-{idx + 1})",
                    f"- 发布时间：2026-06-02 09:{minute:02d}:00",
                ]
            )
        )

    bloomberg_items = []
    for idx in range(5):
        minute = idx % 60
        bloomberg_items.append(
            "\n".join(
                [
                    f"### [Bloomberg {idx + 1}](https://www.bloomberg.com/news/test-{idx + 1})",
                    f"- 发布时间：2026-06-02 18:{minute:02d}:00",
                ]
            )
        )

    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        "## Reuters · World（31条）\n"
        + "\n".join(reuters_items)
        + "\n\n## Bloomberg · Markets（5条）\n"
        + "\n".join(bloomberg_items)
        + "\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    page1 = client.get("/api/news?collection=feed&read_filter=unread&source_filter=reuters&page=1&per=30")
    assert page1.status_code == 200
    page1_data = page1.get_json()
    assert page1_data["total"] == 31
    assert page1_data["has_more"] is True
    assert page1_data["next_cursor"] is not None
    assert len(page1_data["items"]) == 30
    assert page1_data["items"][0]["title"] == "Reuters 1"
    assert page1_data["items"][-1]["title"] == "Reuters 30"

    for item in page1_data["items"][:10]:
        res = client.patch(f"/api/news/{item['id']}/state", json={"read": True})
        assert res.status_code == 200

    cursor = page1_data["next_cursor"]
    page2 = client.get(
        "/api/news?collection=feed&read_filter=unread&source_filter=reuters&page=2&per=30"
        f"&cursor_date={cursor['date_key']}&cursor_published_at={cursor['published_at']}&cursor_id={cursor['id']}"
    )
    assert page2.status_code == 200
    page2_data = page2.get_json()
    assert [item["title"] for item in page2_data["items"]] == ["Reuters 31"]
    assert page2_data["has_more"] is False
    assert page2_data["next_cursor"] is None

    loaded_ids = [str(item["id"]) for item in page1_data["items"]] + [str(item["id"]) for item in page2_data["items"]]
    mark_loaded = client.post("/api/news/mark-read-by-ids", json={"item_ids": loaded_ids})
    assert mark_loaded.status_code == 200
    assert mark_loaded.get_json()["marked"] == 31

    reuters_unread = client.get("/api/news?collection=feed&read_filter=unread&source_filter=reuters&page=1&per=30")
    assert reuters_unread.status_code == 200
    assert reuters_unread.get_json()["total"] == 0

    bloomberg_unread = client.get("/api/news?collection=feed&read_filter=unread&source_filter=bloomberg&page=1&per=30")
    assert bloomberg_unread.status_code == 200
    assert bloomberg_unread.get_json()["total"] == 5


def test_search_range_and_time_filters(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "news_index.sqlite3"
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: name == "DEEPSEEK_API_KEY")
    app_module.ensure_db()
    client = app_module.app.test_client()

    today = datetime.now().date()
    d5 = today - timedelta(days=5)
    d20 = today - timedelta(days=20)
    d40 = today - timedelta(days=40)
    ts = f"{today.isoformat()} 12:00:00"

    def make_item(item_id: int, title: str, day) -> tuple:
        day_text = day.isoformat()
        published_at = f"{day_text} 09:00:00"
        return (
            item_id,
            "search.md",
            item_id,
            published_at,
            day_text,
            "09:00",
            "Reuters",
            "rss",
            "Reuters",
            title,
            f"summary {title}",
            f"https://example.com/{item_id}",
            ts,
            ts,
        )

    conn = app_module.db_conn()
    try:
        conn.executemany(
            """
            INSERT INTO items(
              id, source_file, item_order, published_at, date, time, source, source_type,
              source_name, title, summary, url, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                make_item(1, "RangeNeedle A", today),
                make_item(2, "RangeNeedle B", d5),
                make_item(3, "RangeNeedle C", d20),
                make_item(4, "RangeNeedle D", d40),
            ],
        )
        conn.execute(
            "INSERT INTO item_state(item_id, important_at, updated_at) VALUES (?, ?, ?)",
            (1, ts, ts),
        )
        conn.executemany(
            "INSERT INTO article_notes(url, note, created_at, updated_at) VALUES (?, ?, ?, ?)",
            [
                ("https://example.com/1", "note A", ts, ts),
                ("https://example.com/2", "note B", ts, ts),
            ],
        )
        conn.executemany(
            "INSERT INTO article_market_tags(url, tag, direction, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("https://example.com/1", "ai", "bullish", ts, ts),
                ("https://example.com/3", "ai", "bearish", ts, ts),
            ],
        )
        conn.executemany(
            "INSERT INTO article_details(url, title, author, published_at, content, content_length, fetched_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("https://example.com/1", "RangeNeedle A", "r", ts, "body", 4, ts, ts),
                ("https://example.com/3", "RangeNeedle C", "r", ts, "body", 4, ts, ts),
                ("https://example.com/4", "RangeNeedle D", "r", ts, "body", 4, ts, ts),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    assert client.get("/api/search?q=RangeNeedle&range=all&time=all&per=20").get_json()["total"] == 4
    assert client.get("/api/search?q=RangeNeedle&range=important&time=all&per=20").get_json()["total"] == 1
    assert client.get("/api/search?q=RangeNeedle&range=notes&time=all&per=20").get_json()["total"] == 2
    assert client.get("/api/search?q=RangeNeedle&range=market_tags&time=all&per=20").get_json()["total"] == 2
    assert client.get("/api/search?q=RangeNeedle&range=detail_ready&time=all&per=20").get_json()["total"] == 3

    assert client.get("/api/search?q=RangeNeedle&range=all&time=today&per=20").get_json()["total"] == 1
    assert client.get("/api/search?q=RangeNeedle&range=all&time=7d&per=20").get_json()["total"] == 2
    assert client.get("/api/search?q=RangeNeedle&range=all&time=30d&per=20").get_json()["total"] == 3

    ignored = client.get(
        "/api/search?q=RangeNeedle&range=all&time=all&collection=important&source_filter=bloomberg&read_filter=read&per=20"
    )
    assert ignored.status_code == 200
    assert ignored.get_json()["total"] == 4


def test_mark_all_read_cross_page_with_filter(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（3条）
### [Alpha 1](https://example.com/a1)
- 发布时间：2026-05-25 12:00:00
### [Alpha 2](https://example.com/a2)
- 发布时间：2026-05-25 11:00:00
### [Beta 1](https://example.com/b1)
- 发布时间：2026-05-25 10:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    r = client.post("/api/reindex", json={})
    assert r.status_code == 200

    # Cross-page condition: per=1 but mark-all-read should touch all filtered hits.
    page1 = client.get("/api/news?per=1&q=Alpha")
    assert page1.status_code == 200
    assert page1.get_json()["total"] == 2

    mark = client.post(
        "/api/news/mark-all-read",
        json={"q": "Alpha", "read_filter": "all"},
    )
    assert mark.status_code == 200
    assert mark.get_json()["marked"] == 2

    read_alpha = client.get("/api/news?read_filter=read&q=Alpha")
    assert read_alpha.status_code == 200
    assert read_alpha.get_json()["total"] == 2

    unread_beta = client.get("/api/news?read_filter=unread&q=Beta")
    assert unread_beta.status_code == 200
    assert unread_beta.get_json()["total"] == 1


def test_mark_all_read_respects_collection(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（2条）
### [Item 1](https://example.com/i1)
- 发布时间：2026-05-25 12:00:00
### [Item 2](https://example.com/i2)
- 发布时间：2026-05-25 11:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news").get_json()["items"]
    item1 = items[0]["id"]
    item2 = items[1]["id"]
    assert client.patch(f"/api/news/{item1}/state", json={"important": True}).status_code == 200

    mark = client.post(
        "/api/news/mark-all-read",
        json={"collection": "important", "read_filter": "all"},
    )
    assert mark.status_code == 200
    assert mark.get_json()["marked"] == 1

    important_read = client.get("/api/news?collection=important&read_filter=read")
    assert important_read.get_json()["total"] == 1

    feed_unread = client.get("/api/news?collection=feed&read_filter=unread")
    ids = {it["id"] for it in feed_unread.get_json()["items"]}
    assert item2 in ids


def test_mark_read_by_ids_only_touches_loaded_rows(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（3条）
### [Alpha 1](https://example.com/a1)
- 发布时间：2026-05-25 12:00:00
### [Alpha 2](https://example.com/a2)
- 发布时间：2026-05-25 11:00:00
### [Alpha 3](https://example.com/a3)
- 发布时间：2026-05-25 10:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    all_items = client.get("/api/news?per=20&q=Alpha").get_json()["items"]
    loaded_ids = [all_items[0]["id"], all_items[1]["id"]]
    untouched_id = all_items[2]["id"]

    mark = client.post(
        "/api/news/mark-read-by-ids",
        json={"item_ids": loaded_ids},
    )
    assert mark.status_code == 200
    assert mark.get_json()["marked"] == 2

    read_alpha = client.get("/api/news?read_filter=read&q=Alpha").get_json()["items"]
    assert {it["id"] for it in read_alpha} == set(loaded_ids)

    unread_alpha = client.get("/api/news?read_filter=unread&q=Alpha").get_json()["items"]
    assert {it["id"] for it in unread_alpha} == {untouched_id}


def test_news_date_counts_follow_filter_and_collection(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（4条）
### [D1 Morning](https://example.com/d1-morning)
- 发布时间：2026-05-25 09:00:00
### [D1 Noon](https://example.com/d1-noon)
- 发布时间：2026-05-25 12:00:00
### [D2 Morning](https://example.com/d2-morning)
- 发布时间：2026-05-26 09:00:00
### [D2 Noon](https://example.com/d2-noon)
- 发布时间：2026-05-26 12:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    feed_all = client.get("/api/news?per=20&read_filter=all").get_json()
    assert feed_all["date_counts"] == {"2026-05-26": 2, "2026-05-25": 2}

    items_by_title = {item["title"]: item for item in feed_all["items"]}
    assert client.patch(f"/api/news/{items_by_title['D1 Noon']['id']}/state", json={"read": True}).status_code == 200
    assert client.patch(f"/api/news/{items_by_title['D2 Noon']['id']}/state", json={"read": True}).status_code == 200
    assert client.patch(f"/api/news/{items_by_title['D2 Noon']['id']}/state", json={"important": True}).status_code == 200
    assert client.patch(f"/api/news/{items_by_title['D2 Morning']['id']}/state", json={"important": True}).status_code == 200

    feed_unread = client.get("/api/news?per=20&read_filter=unread").get_json()
    assert feed_unread["date_counts"] == {"2026-05-26": 1, "2026-05-25": 1}

    important_all = client.get("/api/news?per=20&collection=important&read_filter=all").get_json()
    assert important_all["date_counts"] == {"2026-05-26": 2}

    loaded_ids = [
        items_by_title["D1 Morning"]["id"],
        items_by_title["D2 Morning"]["id"],
    ]
    mark = client.post("/api/news/mark-read-by-ids", json={"item_ids": loaded_ids})
    assert mark.status_code == 200
    assert mark.get_json()["marked"] == 2

    feed_unread_after = client.get("/api/news?per=20&read_filter=unread").get_json()
    assert feed_unread_after["date_counts"] == {}

    feed_all_after = client.get("/api/news?per=20&read_filter=all").get_json()
    assert feed_all_after["date_counts"] == {"2026-05-26": 2, "2026-05-25": 2}


def test_read_later_enqueues_detail_job_and_retry(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（1条）
### [Item 1](https://www.reuters.com/world/example)
- 发布时间：2026-05-25 12:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news").get_json()["items"][0]
    item_id = item["id"]
    assert item["detail_ready"] == 0

    patch = client.patch(f"/api/news/{item_id}/state", json={"read_later": True})
    assert patch.status_code == 200
    assert patch.get_json()["read_later_at"] is not None

    detail = client.get(f"/api/news/{item_id}/detail")
    assert detail.status_code == 200
    payload = detail.get_json()
    assert payload["ok"] is True
    assert payload["detail_status"] in {"pending", "running", "failed", "success"}

    # Plan B: cancel read_later should cancel pending job, but keep detail table untouched.
    cancel = client.patch(f"/api/news/{item_id}/state", json={"read_later": False})
    assert cancel.status_code == 200
    assert cancel.get_json()["read_later_at"] is None

    detail_after_cancel = client.get(f"/api/news/{item_id}/detail")
    assert detail_after_cancel.status_code == 200
    after_payload = detail_after_cancel.get_json()
    assert after_payload["detail_status"] in {"canceled", "success", "failed", "running"}

    retry = client.post(f"/api/news/{item_id}/detail/retry")
    assert retry.status_code == 200
    assert retry.get_json()["ok"] is True


def test_detail_api_includes_ai_fields(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    url = "https://www.reuters.com/world/example-ai"
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        f"""## Reuters · World（1条）
### [Item 1]({url})
- 发布时间：2026-05-25 12:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news").get_json()["items"][0]
    item_id = item["id"]

    conn = app_module.db_conn()
    try:
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
                VALUES (?, 'Reuters', 'T', 'A', '2026-05-25', ?, ?, '{}', ?, ?)
                """,
                (url, "English body " * 30, len("English body " * 30), ts, ts),
            )
            conn.execute(
                """
                INSERT INTO article_ai(url, model, key_points_zh, conclusion_zh, body_zh, raw_json, generated_at, updated_at)
                VALUES (?, 'deepseek-chat', ?, '结论', ?, '{}', ?, ?)
                """,
                (url, '["要点1","要点2","要点3"]', "中" * 260, ts, ts),
            )
            conn.execute(
                """
                INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
                VALUES (?, 'success', 0, ?, ?)
                """,
                (url, ts, ts),
            )
    finally:
        conn.close()

    detail = client.get(f"/api/news/{item_id}/detail")
    assert detail.status_code == 200
    payload = detail.get_json()
    assert payload["ai_status"] == "success"
    assert payload["ai"] is not None
    assert payload["ai"]["conclusion_zh"] == "结论"


def test_sources_and_source_filter(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（1条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-05-25 12:00:00
## Bloomberg · Markets（1条）
### [B1](https://www.bloomberg.com/news/articles/b1)
- 发布时间：2026-05-25 11:00:00
## Twitter · 外汇交易员（1条）
### [X1](https://x.com/fxtrader/status/1)
- 发布时间：2026-05-25 10:00:00
## UnknownFeed（1条）
### [U1](https://example.org/news/u1)
- 发布时间：2026-05-25 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    src_resp = client.get("/api/sources?collection=feed&read_filter=all")
    assert src_resp.status_code == 200
    src_data = src_resp.get_json()
    assert src_data["ok"] is True
    keys = {x["key"] for x in src_data["sources"]}
    assert "reuters" in keys
    assert "bloomberg" in keys
    assert "x" in keys
    assert "host:example.org" in keys

    reuters = client.get("/api/news?source_filter=reuters")
    assert reuters.status_code == 200
    r_items = reuters.get_json()["items"]
    assert len(r_items) == 1
    assert r_items[0]["source_key"] == "reuters"

    xfeed = client.get("/api/news?source_filter=x")
    assert xfeed.status_code == 200
    x_items = xfeed.get_json()["items"]
    assert len(x_items) == 1
    assert x_items[0]["source_key"] == "x"

    unknown = client.get("/api/news?source_filter=host:example.org")
    assert unknown.status_code == 200
    u_items = unknown.get_json()["items"]
    assert len(u_items) == 1
    assert u_items[0]["url"].startswith("https://example.org/")


def test_news_section_order_date_asc_and_intra_date_asc_for_feed(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（4条）
### [D2-later](https://example.com/d2-later)
- 发布时间：2026-05-29 18:00:00
### [D1-middle](https://example.com/d1-middle)
- 发布时间：2026-05-30 12:00:00
### [D1-early](https://example.com/d1-early)
- 发布时间：2026-05-30 08:00:00
### [D2-early](https://example.com/d2-early)
- 发布时间：2026-05-29 06:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    res = client.get("/api/news?per=20")
    assert res.status_code == 200
    items = res.get_json()["items"]
    titles = [x["title"] for x in items]
    # section 间日期旧->新；同一日期内时间旧->新
    assert titles == ["D2-early", "D2-later", "D1-early", "D1-middle"]


def test_reading_checkpoint_save_get_and_locate(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（4条）
### [A](https://example.com/a)
- 发布时间：2026-05-30 08:00:00
### [B](https://example.com/b)
- 发布时间：2026-05-30 12:00:00
### [C](https://example.com/c)
- 发布时间：2026-05-29 06:00:00
### [D](https://example.com/d)
- 发布时间：2026-05-29 18:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    put = client.put(
        "/api/reading-checkpoint",
        json={"scope": "feed", "url": "https://example.com/d", "item_id": "x", "title": "D"},
    )
    assert put.status_code == 200
    assert put.get_json()["ok"] is True

    got = client.get("/api/reading-checkpoint?scope=feed")
    assert got.status_code == 200
    cp = got.get_json()["checkpoint"]
    assert cp["url"] == "https://example.com/d"

    loc = client.get("/api/reading-checkpoint/locate?scope=feed&per=2")
    assert loc.status_code == 200
    payload = loc.get_json()
    assert payload["ok"] is True
    assert payload["found"] is True
    assert payload["url"] == "https://example.com/d"
    # 使用当前后端排序规则定位到目标并返回分页位置
    assert payload["page"] == 1
    assert payload["offset"] == 1


def test_reading_checkpoint_locate_not_found(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（1条）
### [A](https://example.com/a)
- 发布时间：2026-05-30 08:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200
    assert client.put(
        "/api/reading-checkpoint",
        json={"scope": "feed", "url": "https://example.com/not-exist", "title": "X"},
    ).status_code == 200

    loc = client.get("/api/reading-checkpoint/locate?scope=feed&per=20")
    assert loc.status_code == 200
    payload = loc.get_json()
    assert payload["ok"] is True
    assert payload["found"] is False
    assert payload["reason"] == "not_in_current_scope"


def test_news_status_batch_endpoint(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（2条）
### [A](https://example.com/a)
- 发布时间：2026-05-30 08:00:00
### [B](https://example.com/b)
- 发布时间：2026-05-30 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news?per=20").get_json()["items"]
    ids = [x["id"] for x in items]
    bad = client.get("/api/news/status")
    assert bad.status_code == 400
    assert bad.get_json()["error"] == "missing_ids"

    ok = client.get(f"/api/news/status?ids={ids[0]},{ids[1]}")
    assert ok.status_code == 200
    payload = ok.get_json()
    assert payload["ok"] is True
    assert len(payload["items"]) == 2
    returned_ids = {x["id"] for x in payload["items"]}
    assert returned_ids == set(ids)


def test_article_note_save_read_and_clear(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-01.md").write_text(
        """## Reuters · World（1条）
### [Note Item](https://example.com/n1)
- 发布时间：2026-06-01 08:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    item_id = item["id"]
    assert int(item.get("has_note") or 0) == 0

    save = client.put(
        f"/api/news/{item_id}/note",
        json={"note": "这是我的第一条想法。"},
    )
    assert save.status_code == 200
    save_payload = save.get_json()
    assert save_payload["ok"] is True
    assert save_payload["has_note"] == 1
    assert save_payload["note"]["note"] == "这是我的第一条想法。"
    assert save_payload["note_preview"] == "这是我的第一条想法。"

    detail = client.get(f"/api/news/{item_id}/detail")
    assert detail.status_code == 200
    detail_payload = detail.get_json()
    assert detail_payload["ok"] is True
    assert detail_payload["has_note"] == 1
    assert detail_payload["note"]["note"] == "这是我的第一条想法。"

    listed = client.get("/api/news?per=20").get_json()["items"][0]
    assert int(listed.get("has_note") or 0) == 1
    assert listed["note_preview"] == "这是我的第一条想法。"

    clear = client.put(f"/api/news/{item_id}/note", json={"note": "   "})
    assert clear.status_code == 200
    clear_payload = clear.get_json()
    assert clear_payload["ok"] is True
    assert clear_payload["has_note"] == 0
    assert clear_payload["note"] is None
    assert clear_payload["note_preview"] == ""

    detail2 = client.get(f"/api/news/{item_id}/detail").get_json()
    assert detail2["has_note"] == 0
    assert detail2["note"] is None


def test_notes_collection_and_sources_filter(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-01.md").write_text(
        """## Reuters · World（2条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-01 09:00:00
## Bloomberg · Tech（1条）
### [B1](https://www.bloomberg.com/news/articles/b1)
- 发布时间：2026-06-01 08:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news?per=20").get_json()["items"]
    reuters_item = next(x for x in items if "reuters.com" in (x.get("url") or ""))
    bloomberg_item = next(x for x in items if "bloomberg.com" in (x.get("url") or ""))

    assert client.put(f"/api/news/{reuters_item['id']}/note", json={"note": "R note"}).status_code == 200
    assert client.put(f"/api/news/{bloomberg_item['id']}/note", json={"note": "B note"}).status_code == 200

    notes_all = client.get("/api/news?collection=notes&per=20")
    assert notes_all.status_code == 200
    notes_items = notes_all.get_json()["items"]
    assert notes_all.get_json()["total"] == 2
    assert all(int(x.get("has_note") or 0) == 1 for x in notes_items)

    notes_reuters = client.get("/api/news?collection=notes&source_filter=reuters&per=20")
    assert notes_reuters.status_code == 200
    assert notes_reuters.get_json()["total"] == 1
    assert notes_reuters.get_json()["items"][0]["source_key"] == "reuters"

    sources_notes = client.get("/api/sources?collection=notes&read_filter=all")
    assert sources_notes.status_code == 200
    payload = sources_notes.get_json()
    assert payload["ok"] is True
    keys = {x["key"] for x in payload["sources"]}
    assert "reuters" in keys
    assert "bloomberg" in keys

    assert client.put(f"/api/news/{reuters_item['id']}/note", json={"note": ""}).status_code == 200
    notes_after_clear = client.get("/api/news?collection=notes&per=20").get_json()
    assert notes_after_clear["total"] == 1
    assert notes_after_clear["items"][0]["source_key"] == "bloomberg"


def test_market_tags_crud_and_collection_filter(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-01.md").write_text(
        """## Reuters · World（2条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-01 09:00:00
## Bloomberg · Tech（1条）
### [B1](https://www.bloomberg.com/news/articles/b1)
- 发布时间：2026-06-01 08:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news?per=20").get_json()["items"]
    reuters_item = next(x for x in items if "reuters.com" in (x.get("url") or ""))
    bloomberg_item = next(x for x in items if "bloomberg.com" in (x.get("url") or ""))

    p1 = client.put(
        f"/api/news/{reuters_item['id']}/market-tag",
        json={"tag": "AI", "direction": "bullish"},
    )
    assert p1.status_code == 200
    assert p1.get_json()["has_market_tags"] == 1
    assert p1.get_json()["market_tags"][0]["direction"] == "bullish"
    assert p1.get_json()["important_at"] is not None

    # 同 tag 覆盖方向
    p2 = client.put(
        f"/api/news/{reuters_item['id']}/market-tag",
        json={"tag": "AI", "direction": "bearish"},
    )
    assert p2.status_code == 200
    ai_tag = next(x for x in p2.get_json()["market_tags"] if x["tag"] == "AI")
    assert ai_tag["direction"] == "bearish"

    # 多 tag 共存
    p3 = client.put(
        f"/api/news/{reuters_item['id']}/market-tag",
        json={"tag": "新能源", "direction": "bullish"},
    )
    assert p3.status_code == 200
    assert len(p3.get_json()["market_tags"]) == 2

    p4 = client.put(
        f"/api/news/{bloomberg_item['id']}/market-tag",
        json={"tag": "房地产", "direction": "bearish"},
    )
    assert p4.status_code == 200

    m_all = client.get("/api/news?collection=market_tags&per=20")
    assert m_all.status_code == 200
    all_payload = m_all.get_json()
    assert all_payload["total"] == 2
    assert all(int(x.get("has_market_tags") or 0) == 1 for x in all_payload["items"])

    m_reuters = client.get("/api/news?collection=market_tags&source_filter=reuters&per=20")
    assert m_reuters.status_code == 200
    assert m_reuters.get_json()["total"] == 1
    assert m_reuters.get_json()["items"][0]["source_key"] == "reuters"

    d1 = client.get(f"/api/news/{reuters_item['id']}/detail")
    assert d1.status_code == 200
    d_payload = d1.get_json()
    assert d_payload["has_market_tags"] == 1
    assert len(d_payload["market_tags"]) == 2

    s1 = client.get("/api/sources?collection=market_tags&read_filter=all")
    assert s1.status_code == 200
    s_payload = s1.get_json()
    assert s_payload["ok"] is True
    keys = {x["key"] for x in s_payload["sources"]}
    assert "reuters" in keys
    assert "bloomberg" in keys

    # 删除单个 tag
    d_tag = client.delete(f"/api/news/{reuters_item['id']}/market-tag?tag=AI")
    assert d_tag.status_code == 200
    assert d_tag.get_json()["ok"] is True
    assert len(d_tag.get_json()["market_tags"]) == 1

    # 删除剩余 tag 后不再属于 market_tags 集合
    client.delete(f"/api/news/{reuters_item['id']}/market-tag?tag=新能源")
    m_after = client.get("/api/news?collection=market_tags&per=20").get_json()
    assert m_after["total"] == 1
    assert m_after["items"][0]["source_key"] == "bloomberg"

    # 删除标签不会自动取消 important
    feed = client.get("/api/news?per=20").get_json()["items"]
    r1_after = next(x for x in feed if x["id"] == reuters_item["id"])
    assert r1_after["important_at"] is not None


def test_market_trends_matrix_and_detail(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（2条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-02 09:00:00
### [R2](https://www.reuters.com/world/r2)
- 发布时间：2026-06-02 10:00:00
## Bloomberg · Tech（1条）
### [B1](https://www.bloomberg.com/news/articles/b1)
- 发布时间：2026-06-01 08:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news?per=20").get_json()["items"]
    r1 = next(x for x in items if x["title"] == "R1")
    r2 = next(x for x in items if x["title"] == "R2")
    b1 = next(x for x in items if x["title"] == "B1")

    assert client.put(f"/api/news/{r1['id']}/market-tag", json={"tag": "AI", "direction": "bullish"}).status_code == 200
    assert client.put(f"/api/news/{r2['id']}/market-tag", json={"tag": "AI", "direction": "bullish"}).status_code == 200
    assert client.put(f"/api/news/{b1['id']}/market-tag", json={"tag": "AI", "direction": "bearish"}).status_code == 200
    assert client.put(f"/api/news/{b1['id']}/note", json={"note": "留意 Apple 链条影响"}).status_code == 200

    trends = client.get("/api/market-trends?days=7")
    assert trends.status_code == 200
    payload = trends.get_json()
    assert payload["ok"] is True
    assert payload["dates"] == ["2026-06-01", "2026-06-02"]
    ai_row = next(row for row in payload["rows"] if row["tag"] == "AI")
    counts_by_date = {slot["date"]: slot for slot in ai_row["values"]}
    assert counts_by_date["2026-06-02"]["bullish"] == 2
    assert counts_by_date["2026-06-02"]["bearish"] == 0
    assert counts_by_date["2026-06-01"]["bullish"] == 0
    assert counts_by_date["2026-06-01"]["bearish"] == 1

    detail = client.get("/api/market-trends/detail?date=2026-06-02&tag=AI&direction=bullish")
    assert detail.status_code == 200
    detail_payload = detail.get_json()
    assert detail_payload["ok"] is True
    assert detail_payload["total"] == 2
    assert [item["title"] for item in detail_payload["items"]] == ["R1", "R2"]
    assert all(item["date_key"] == "2026-06-02" for item in detail_payload["items"])
    assert all(item["source_key"] == "reuters" for item in detail_payload["items"])

    bearish_detail = client.get("/api/market-trends/detail?date=2026-06-01&tag=AI&direction=bearish")
    assert bearish_detail.status_code == 200
    bearish_payload = bearish_detail.get_json()
    assert bearish_payload["total"] == 1
    assert bearish_payload["items"][0]["title"] == "B1"
    assert bearish_payload["items"][0]["has_note"] == 1
    assert bearish_payload["items"][0]["note"]["note"] == "留意 Apple 链条影响"
    assert bearish_payload["items"][0]["market_tags"][0]["direction"] == "bearish"


def test_market_tag_definitions_crud_and_dynamic_usage(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（1条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-02 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    tags_res = client.get("/api/market-tags")
    assert tags_res.status_code == 200
    tags_payload = tags_res.get_json()
    assert tags_payload["ok"] is True
    assert any(tag["display_name"] == "AI" for tag in tags_payload["tags"])

    create_res = client.post("/api/market-tags", json={"display_name": "宏观观察"})
    assert create_res.status_code == 200
    created_tag = create_res.get_json()["tag"]
    assert created_tag["display_name"] == "宏观观察"
    assert created_tag["active"] == 1

    item = client.get("/api/news?per=20").get_json()["items"][0]
    put_res = client.put(
        f"/api/news/{item['id']}/market-tag",
        json={"tag": created_tag["key"], "direction": "bullish"},
    )
    assert put_res.status_code == 200
    assert put_res.get_json()["market_tags"][0]["tag"] == "宏观观察"

    rename_res = client.patch(
        f"/api/market-tags/{created_tag['key']}",
        json={"display_name": "大宏观"},
    )
    assert rename_res.status_code == 200
    assert rename_res.get_json()["tag"]["display_name"] == "大宏观"

    detail_res = client.get(f"/api/news/{item['id']}/detail")
    assert detail_res.status_code == 200
    detail_payload = detail_res.get_json()
    renamed_tag = next(tag for tag in detail_payload["market_tags"] if tag["key"] == created_tag["key"])
    assert renamed_tag["tag"] == "大宏观"
    choice = next(tag for tag in detail_payload["market_tag_choices"] if tag["key"] == created_tag["key"])
    assert choice["display_name"] == "大宏观"

    deactivate_res = client.patch(
        f"/api/market-tags/{created_tag['key']}",
        json={"active": False},
    )
    assert deactivate_res.status_code == 200
    assert deactivate_res.get_json()["tag"]["active"] == 0

    active_tags = client.get("/api/market-tags?active_only=1").get_json()["tags"]
    assert all(tag["key"] != created_tag["key"] for tag in active_tags)

    trends = client.get("/api/market-trends?days=7").get_json()
    assert all(row["tag_key"] != created_tag["key"] for row in trends["rows"])

    detail_after_deactivate = client.get(f"/api/news/{item['id']}/detail").get_json()
    historical_tag = next(tag for tag in detail_after_deactivate["market_tags"] if tag["key"] == created_tag["key"])
    assert historical_tag["tag"] == "大宏观"


def test_market_trend_notes_manual_signal(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（1条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-02 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    assert client.put(
        f"/api/news/{item['id']}/market-tag",
        json={"tag": "AI", "direction": "bullish"},
    ).status_code == 200

    bullish_note = client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-02", "tag_key": "AI", "direction": "bullish", "note": "继续看多 AI 主线"},
    )
    assert bullish_note.status_code == 200
    assert bullish_note.get_json()["trend_note"]["note"] == "继续看多 AI 主线"
    bullish_note_2 = client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-02", "tag_key": "AI", "direction": "bullish", "note": "继续加仓，但分批做"},
    )
    assert bullish_note_2.status_code == 200

    bearish_note = client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-02", "tag_key": "AI", "direction": "bearish", "note": "短线也要警惕回撤"},
    )
    assert bearish_note.status_code == 200
    assert bearish_note.get_json()["has_trend_note"] == 1

    trends = client.get("/api/market-trends?days=7")
    assert trends.status_code == 200
    ai_row = next(row for row in trends.get_json()["rows"] if row["tag_key"] == "AI")
    slot = next(value for value in ai_row["values"] if value["date"] == "2026-06-02")
    assert slot["bullish"] == 1
    assert slot["bullish_notes"] == 2
    assert slot["bullish_has_item_note"] == 0
    assert slot["bearish"] == 0
    assert slot["bearish_notes"] == 1

    bullish_detail = client.get("/api/market-trends/detail?date=2026-06-02&tag=AI&direction=bullish")
    assert bullish_detail.status_code == 200
    bullish_payload = bullish_detail.get_json()
    assert bullish_payload["total"] == 1
    assert bullish_payload["trend_note_total"] == 2
    assert [note["note"] for note in bullish_payload["trend_notes"]] == ["继续加仓，但分批做", "继续看多 AI 主线"]
    edited_note = bullish_payload["trend_notes"][1]

    bearish_detail = client.get("/api/market-trends/detail?date=2026-06-02&tag=AI&direction=bearish")
    assert bearish_detail.status_code == 200
    bearish_payload = bearish_detail.get_json()
    assert bearish_payload["total"] == 0
    assert bearish_payload["trend_notes"][0]["note"] == "短线也要警惕回撤"

    patch_res = client.patch(
        f"/api/market-trends/note/{edited_note['id']}",
        json={"note": "继续看多 AI 主线，暂不追高"},
    )
    assert patch_res.status_code == 200
    assert patch_res.get_json()["trend_note"]["note"] == "继续看多 AI 主线，暂不追高"

    delete_res = client.delete(f"/api/market-trends/note/{bearish_payload['trend_notes'][0]['id']}")
    assert delete_res.status_code == 200
    assert delete_res.get_json()["has_trend_note"] == 0


def test_market_trend_tag_detail_overview(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-03.md").write_text(
        """## Reuters · World（2条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-03 09:00:00
### [R2](https://www.reuters.com/world/r2)
- 发布时间：2026-06-02 10:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    items = client.get("/api/news?per=20").get_json()["items"]
    r1 = next(x for x in items if x["title"] == "R1")
    r2 = next(x for x in items if x["title"] == "R2")

    assert client.put(
        f"/api/news/{r1['id']}/market-tag",
        json={"tag": "AI", "direction": "bullish"},
    ).status_code == 200
    assert client.put(
        f"/api/news/{r2['id']}/market-tag",
        json={"tag": "AI", "direction": "bearish"},
    ).status_code == 200
    assert client.put(
        f"/api/news/{r2['id']}/note",
        json={"note": "旧新闻想法"},
    ).status_code == 200

    assert client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-03", "tag_key": "AI", "direction": "bullish", "note": "最新看多想法"},
    ).status_code == 200
    assert client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-01", "tag_key": "AI", "direction": "bearish", "note": "更早看空想法"},
    ).status_code == 200

    detail = client.get("/api/market-trends/tag-detail?tag=AI")
    assert detail.status_code == 200
    payload = detail.get_json()
    assert payload["ok"] is True
    assert payload["view"] == "tag"
    assert payload["tag_key"] == "AI"
    assert payload["item_total"] == 2
    assert payload["trend_note_total"] == 2
    assert [item["title"] for item in payload["items"]] == ["R1", "R2"]
    assert [item["direction"] for item in payload["items"]] == ["bullish", "bearish"]
    assert [note["date_key"] for note in payload["trend_notes"]] == ["2026-06-03", "2026-06-01"]
    assert payload["items"][1]["note"]["note"] == "旧新闻想法"


def test_ai_fallback_to_gemini_success(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    with app_module.db_conn() as conn:
        conn.execute(
            """
            INSERT INTO article_details(url, title, source, content, content_length, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/fallback",
                "Fallback title",
                "Reuters",
                "Original english body",
                21,
                "2026-06-04 17:00:00",
                "2026-06-04 17:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
            VALUES (?, 'pending', 0, ?, ?)
            """,
            (
                "https://example.com/fallback",
                "2026-06-04 17:01:00",
                "2026-06-04 17:01:00",
            ),
        )

    def fail_primary(**kwargs):
        raise app_module.LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: bad json")

    def succeed_fallback(**kwargs):
        return {
            "model": "gemini-fallback",
            "key_points_zh": [],
            "conclusion_zh": "",
            "body_zh": "这是 Gemini 保底译文。",
            "raw_json": '{"provider":"gemini-fallback"}',
        }

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_gemini_fallback_translation", succeed_fallback)

    assert app_module.process_pending_ai_once() is True

    with app_module.db_conn() as conn:
        ai_row = conn.execute(
            "SELECT model, key_points_zh, conclusion_zh, body_zh FROM article_ai WHERE url=?",
            ("https://example.com/fallback",),
        ).fetchone()
        job_row = conn.execute(
            "SELECT status, last_error FROM ai_jobs WHERE url=?",
            ("https://example.com/fallback",),
        ).fetchone()

    assert ai_row["model"] == "gemini-fallback"
    assert ai_row["body_zh"] == "这是 Gemini 保底译文。"
    assert ai_row["key_points_zh"] == "[]"
    assert ai_row["conclusion_zh"] == ""
    assert job_row["status"] == "success"
    assert job_row["last_error"] is None


def test_ai_fallback_to_gemini_failure_keeps_error(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    with app_module.db_conn() as conn:
        conn.execute(
            """
            INSERT INTO article_details(url, title, source, content, content_length, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/fallback-failed",
                "Fallback failed title",
                "Reuters",
                "Original english body",
                21,
                "2026-06-04 17:00:00",
                "2026-06-04 17:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
            VALUES (?, 'pending', 0, ?, ?)
            """,
            (
                "https://example.com/fallback-failed",
                "2026-06-04 17:01:00",
                "2026-06-04 17:01:00",
            ),
        )

    def fail_primary(**kwargs):
        raise app_module.LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: bad json")

    def fail_fallback(**kwargs):
        raise app_module.LLMClientError("GEMINI_FALLBACK_FAILED: bridge down")

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_gemini_fallback_translation", fail_fallback)

    assert app_module.process_pending_ai_once() is True

    with app_module.db_conn() as conn:
        ai_row = conn.execute(
            "SELECT url FROM article_ai WHERE url=?",
            ("https://example.com/fallback-failed",),
        ).fetchone()
        job_row = conn.execute(
            "SELECT status, last_error FROM ai_jobs WHERE url=?",
            ("https://example.com/fallback-failed",),
        ).fetchone()

    assert ai_row is None
    assert job_row["status"] == "failed"
    assert "INVALID_TOOL_ARGUMENTS_JSON" in job_row["last_error"]
    assert "GEMINI_FALLBACK_FAILED" in job_row["last_error"]


def test_error_stats_today_with_and_without_errors(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    empty = client.get("/api/error-stats?day=2026-06-07")
    assert empty.status_code == 200
    assert empty.get_json() == {"ok": True, "day": "2026-06-07", "days": []}

    (daily_dir / "dailyFreshNews_2026-06-07.md").write_text(
        """## errors

### 1. middle-east
- 抓取时间：2026-06-07 21:03:38
- 命令：`opencli ReutersBrowser news https://www.reuters.com/world/middle-east/ --limit 10 --format json`
- 错误：message: 'TypeError: Failed to fetch'

### 2. china
- 抓取时间：2026-06-07 10:00:57
- 命令：`opencli ReutersBrowser news https://www.reuters.com/world/china/ --limit 10 --format json`
- 错误：message: 'TypeError: Failed to fetch'
""",
        encoding="utf-8",
    )

    payload = client.get("/api/error-stats?day=2026-06-07").get_json()
    assert payload["ok"] is True
    assert payload["day"] == "2026-06-07"
    assert payload["days"] == [
        {
            "date": "2026-06-07",
            "groups": [
                {"time": "21:03:38", "labels": ["middle-east error"]},
                {"time": "10:00:57", "labels": ["china error"]},
            ],
        }
    ]


def test_detail_endpoint_includes_chat_providers(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Detail](https://example.com/chat-detail)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    payload = client.get(f"/api/news/{item['id']}/detail").get_json()

    assert payload["ok"] is True
    assert payload["chat_providers"]["codex"]["available"] is True
    assert payload["chat_providers"]["codex"]["label"] == "Codex"


def test_news_chat_requires_ready_detail(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Pending](https://example.com/chat-pending)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    res = client.post(
        f"/api/news/{item['id']}/chat",
        json={"question": "这是什么意思？"},
    )
    assert res.status_code == 409
    assert res.get_json()["error"] == "detail_not_ready"


def test_news_chat_first_turn_uses_context_and_returns_session(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Ready](https://example.com/chat-ready)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    with app_module.db_conn() as conn:
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    "Reuters",
                    "Chat Ready",
                    "Reporter",
                    "2026-06-11 09:00:00",
                    "Full english body for chat route tests.",
                    37,
                    "{}",
                    ts,
                    ts,
                ),
            )

    captured = {}

    def fake_run_codex_chat(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "codex",
            "session_id": "session-123",
            "model": kwargs["model"],
            "answer": "Codex 回答",
        }

    monkeypatch.setattr(app_module, "run_codex_chat", fake_run_codex_chat)
    res = client.post(
        f"/api/news/{item['id']}/chat",
        json={"question": "那最新影响呢？", "model": "gpt-5-codex"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["ok"] is True
    assert payload["answer"] == "Codex 回答"
    assert payload["session_id"] == "session-123"
    assert captured["title"] == "Chat Ready"
    assert captured["content"] == "Full english body for chat route tests."
    assert captured["question"] == "那最新影响呢？"
    assert captured["session_id"] == ""
    assert captured["model"] == "gpt-5-codex"
    assert captured["reset"] is False


def test_news_chat_resume_uses_explicit_session_id(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Config](https://example.com/chat-config)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    with app_module.db_conn() as conn:
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    "Reuters",
                    "Chat Config",
                    "Reporter",
                    "2026-06-11 09:00:00",
                    "Ready detail body",
                    17,
                    "{}",
                    ts,
                    ts,
                ),
            )

    captured = {}

    def fake_run_codex_chat(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "codex",
            "session_id": kwargs["session_id"] or "session-456",
            "model": kwargs["model"],
            "answer": "续问回答",
        }

    monkeypatch.setattr(app_module, "run_codex_chat", fake_run_codex_chat)

    resume_res = client.post(
        f"/api/news/{item['id']}/chat",
        json={"question": "最新进展？", "session_id": "session-456", "model": "gpt-5-codex"},
    )
    assert resume_res.status_code == 200
    assert resume_res.get_json()["session_id"] == "session-456"
    assert captured["session_id"] == "session-456"
    assert captured["question"] == "最新进展？"
    assert captured["model"] == "gpt-5-codex"


def test_news_chat_errors_and_busy(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Error](https://example.com/chat-error)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    with app_module.db_conn() as conn:
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    "Reuters",
                    "Chat Error",
                    "Reporter",
                    "2026-06-11 09:00:00",
                    "Ready detail body",
                    17,
                    "{}",
                    ts,
                    ts,
                ),
            )

    monkeypatch.setattr(app_module, "run_codex_chat", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("codex_timeout")))
    timeout_res = client.post(f"/api/news/{item['id']}/chat", json={"question": "最新进展？"})
    assert timeout_res.status_code == 504
    assert timeout_res.get_json()["error"] == "provider_timeout"

    monkeypatch.setattr(app_module, "run_codex_chat", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("codex_session_invalid")))
    invalid_res = client.post(f"/api/news/{item['id']}/chat", json={"question": "继续", "session_id": "bad-session"})
    assert invalid_res.status_code == 409
    assert invalid_res.get_json()["error"] == "session_invalid"

    lock = app_module.codex_chat_lock(item["id"])
    assert lock.acquire(blocking=False) is True
    try:
        busy_res = client.post(f"/api/news/{item['id']}/chat", json={"question": "继续"})
    finally:
        lock.release()
    assert busy_res.status_code == 409
    assert busy_res.get_json()["error"] == "provider_busy"


def test_run_codex_chat_builds_exec_and_resume_commands(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    commands = []

    def fake_run(command, capture_output, text, timeout, cwd):
        commands.append(command)
        output_path = command[command.index("--output-last-message") + 1]
        Path(output_path).write_text("回答内容", encoding="utf-8")
        if "resume" in command:
            stdout = '{"type":"thread.started","thread_id":"resume-session"}\n{"type":"turn.completed"}\n'
        else:
            stdout = '{"type":"thread.started","thread_id":"first-session"}\n{"type":"turn.completed"}\n'
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.subprocess, "run", fake_run)

    first = app_module.run_codex_chat(
        question="什么是 codex exec？",
        title="Test",
        source="Reuters",
        published_at="2026-06-11 09:00:00",
        content="Body",
        model="gpt-5-codex",
    )
    resumed = app_module.run_codex_chat(
        question="继续说",
        session_id="first-session",
        title="Test",
        source="Reuters",
        published_at="2026-06-11 09:00:00",
        content="Body",
        model="gpt-5-codex",
    )

    assert first["session_id"] == "first-session"
    assert resumed["session_id"] == "resume-session"
    assert commands[0][0:2] == ["codex", "exec"]
    assert "resume" not in commands[0]
    assert "--last" not in commands[0]
    assert commands[1][0:4] == ["codex", "exec", "resume", "first-session"]
    assert "--last" not in commands[1]


def test_release_notes_api_returns_items(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(tmp_path / "app_settings.json"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    payload = client.get("/api/release-notes").get_json()
    assert payload["ok"] is True
    assert payload["items"]
    first = payload["items"][0]
    assert "date" in first and "title" in first and "category" in first
    assert first["category"] in {"NEW", "IMPROVE", "FIX"}


def test_settings_api_status_and_save(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    initial = client.get("/api/settings")
    assert initial.status_code == 200
    data = initial.get_json()
    assert data["ok"] is True
    assert data["api_status"]["deepseek"]["configured"] is True
    assert data["llm"]["codex_chat"]["model"] == ""
    dumped = json.dumps(data, ensure_ascii=False)
    assert "sk-deepseek-test" not in dumped

    save_res = client.put(
        "/api/settings",
        json={
            "llm": {
                "translation": {"provider": "deepseek", "model": "deepseek-reasoner"},
                "codex_chat": {"model": "gpt-5-codex"},
            }
        },
    )
    assert save_res.status_code == 200
    saved = save_res.get_json()
    assert saved["llm"]["translation"]["model"] == "deepseek-reasoner"
    assert saved["llm"]["codex_chat"]["model"] == "gpt-5-codex"
    assert settings_path.exists() is True
    saved_file = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved_file["llm"]["translation"]["model"] == "deepseek-reasoner"
    assert saved_file["llm"]["codex_chat"]["model"] == "gpt-5-codex"


def test_settings_secret_api_save_and_delete(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    saved = {}

    monkeypatch.setattr(app_module, "has_secret", lambda name: name in saved)
    monkeypatch.setattr(app_module, "write_secret", lambda name, value: saved.__setitem__(name, value))
    monkeypatch.setattr(app_module, "delete_secret", lambda name: saved.pop(name, None))

    initial = client.get("/api/settings").get_json()
    assert initial["api_status"]["deepseek"]["configured"] is False

    save_res = client.put("/api/settings/secrets/deepseek", json={"key": "sk-test-deepseek"})
    assert save_res.status_code == 200
    saved_payload = save_res.get_json()
    assert saved_payload["api_status"]["deepseek"]["configured"] is True
    assert "DEEPSEEK_API_KEY" in saved
    dumped = json.dumps(saved_payload, ensure_ascii=False)
    assert "sk-test-deepseek" not in dumped
    assert settings_path.exists() is False

    delete_res = client.delete("/api/settings/secrets/deepseek")
    assert delete_res.status_code == 200
    deleted_payload = delete_res.get_json()
    assert deleted_payload["api_status"]["deepseek"]["configured"] is False
    assert "DEEPSEEK_API_KEY" not in saved


def test_settings_secret_api_rejects_invalid_provider_and_empty_key(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    bad_provider = client.put("/api/settings/secrets/unknown", json={"key": "x"})
    assert bad_provider.status_code == 400
    assert bad_provider.get_json()["error"] == "unsupported_provider"

    empty_key = client.put("/api/settings/secrets/deepseek", json={"key": "   "})
    assert empty_key.status_code == 400
    assert empty_key.get_json()["error"] == "empty_key"


def test_settings_secret_api_keychain_failure_does_not_leak_key(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    def raise_failure(name, value):
        raise app_module.SecretStoreError("write_failed")

    monkeypatch.setattr(app_module, "write_secret", raise_failure)

    res = client.put("/api/settings/secrets/deepseek", json={"key": "sk-sensitive-value"})
    assert res.status_code == 500
    payload = res.get_json()
    assert payload["error"] == "write_failed"
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "sk-sensitive-value" not in dumped


def test_saved_models_are_used_by_translation_and_codex_chat(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Settings Route](https://example.com/settings-route)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200
    assert client.put(
        "/api/settings",
        json={
            "llm": {
                "translation": {"provider": "deepseek", "model": "deepseek-translator-x"},
                "codex_chat": {"model": "gpt-5-codex-x"},
            }
        },
    ).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    with app_module.db_conn() as conn:
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    "Reuters",
                    "Settings Route",
                    "Reporter",
                    "2026-06-11 09:00:00",
                    "Body for settings route tests.",
                    30,
                    "{}",
                    ts,
                    ts,
                ),
            )
            conn.execute(
                """
                INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
                VALUES (?, 'pending', 0, ?, ?)
                """,
                (item["url"], ts, ts),
            )

    captured = {}

    def fake_generate_article_ai(**kwargs):
        captured["translation_model"] = kwargs["model"]
        return {
            "model": kwargs["model"],
            "key_points_zh": ["要点一", "要点二", "要点三"],
            "conclusion_zh": "结论",
            "body_zh": "中文正文",
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_article_ai", fake_generate_article_ai)

    assert app_module.process_pending_ai_once() is True
    assert captured["translation_model"] == "deepseek-translator-x"

    monkeypatch.setattr(
        app_module,
        "run_codex_chat",
        lambda **kwargs: {
            "provider": "codex",
            "session_id": "session-test",
            "model": kwargs["model"],
            "answer": "回答",
        },
    )
    chat_res = client.post(f"/api/news/{item['id']}/chat", json={"question": "最新进展？"})
    assert chat_res.status_code == 200
    assert chat_res.get_json()["model"] == "gpt-5-codex-x"


def test_settings_api_ignores_legacy_chat_fields(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "translation": {"provider": "deepseek", "model": "deepseek-legacy"},
                    "codex_chat": {"model": "gpt-5-codex-legacy"},
                    "chat": {
                        "default_provider": "openai",
                        "providers": {
                            "deepseek": {"model": "deepseek-chat-legacy"},
                            "openai": {"model": "gpt-4.1-legacy"},
                        },
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    payload = client.get("/api/settings").get_json()
    assert payload["ok"] is True
    assert payload["llm"]["translation"]["model"] == "deepseek-legacy"
    assert payload["llm"]["codex_chat"]["model"] == "gpt-5-codex-legacy"
    assert "chat" not in payload["llm"]
