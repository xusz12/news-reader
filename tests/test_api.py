from __future__ import annotations

import importlib
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
