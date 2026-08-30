from __future__ import annotations

import importlib
import json
import pytest
import sqlite3
import subprocess
import textwrap
import types
from datetime import datetime, timedelta
from pathlib import Path


@pytest.fixture(autouse=True)
def _isolate_app_settings(tmp_path: Path, monkeypatch):
    # 默认隔离 app_settings：指向不存在的路径 → load_app_settings 返回默认设置。
    # 避免测试读到本机运行态 app_settings.json（可能被设成 provider=pi）而分叉。
    # 需要 provider=pi 的测试在自己的 body 里 setenv NEWS_READER_APP_SETTINGS_PATH 覆盖。
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(tmp_path / "absent-app_settings.json"))


def make_api_daily(path: Path, title: str, url: str, summary: str | None = None):
    lines = [
        "## Reuters · World（1条）",
        f"### [{title}]({url})",
        "- 发布时间：2026-05-25 12:00:00",
    ]
    if summary:
        lines.append(f"- 摘要：{summary}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_api_sidecar(path: Path, *, title: str, url: str, summary: str | None = None):
    path.write_text(
        json.dumps(
            {
                "schema_version": "newsreader.daily.v1",
                "items": [
                    {
                        "item_order": 1,
                        "section": "Reuters · World",
                        "title": title,
                        "summary": summary,
                        "published_at": "2026-05-25 12:00:00",
                        "url": url,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def make_daily_briefing(path: Path, body: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")


DAILY_BRIEFING_0629 = """
## 简报信息
- 执行模式：`daily`
- 使用文件：`dailyFreshNews_2026-06-29.md`
- 执行时间：`6月29日 21:03`

## 当前关注

- 特朗普称伊朗已提出会谈请求，明日将于卡塔尔多哈举行——外交窗口开启

## 地缘政治

- **中东**：特朗普称伊朗提出会谈请求，明日多哈会谈
"""


DAILY_BRIEFING_0630 = """
## 简报信息
- 执行模式：daily（今日终版）
- 使用文件：dailyFreshNews_2026-06-30.md
- 执行时间：6月30日 21:02
- 全日采集：197条，10轮运行（14/14源全部成功，0错误）

---

## 📋 6月30日 全日摘要

### 💾 存储/AI芯片（全日主线）
- **韩国芯片风暴**：科技巨头承诺超5500亿美元缓解"内存末日"

### 🔍 关注追踪
【市场】韩国芯片巨投：内存末日应对+李在明8800亿AI豪赌
【科技】内存短缺推动AI基础设施投资，韩国核电建设加速

---

*今日数据：197条，10轮运行（00:01→21:00），14/14源全部成功*
"""


DAILY_BRIEFING_0701 = """
## 简报信息
- 执行模式：daily
- 使用文件：dailyFreshNews_2026-07-01.md
- 执行时间：7月1日 8:03
- 全日累计：102条（含00:01/04:00夜间轮），29条新增（14/14源全部成功）

---

## 📋 7月1日 晨间简报

### 🤖 AI动态
- **美国解除对Anthropic Fable和Mythos AI模型的出口管制**
- **Anthropic推出Claude Science**用于科学研究自动化；同时发布`Claude Sonnet 5`

### 💰 市场/金融
- **耐克业绩超预期**，Q2收官
"""


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
    assert data["items"][0]["favorite_at"] is None
    assert data["items"][0]["important_at"] is None
    assert data["items"][0]["read_later_at"] is None
    assert data["items"][0].get("read_later_done_at") is None

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
    assert r5.get_json()["favorite_at"] is None
    assert r5.get_json()["important_at"] is None

    r6 = client.get("/api/news?read_filter=unread")
    assert r6.status_code == 200
    assert r6.get_json()["total"] == 1

    # New flags should be independent and combinable.
    r7 = client.patch(
        f"/api/news/{item_id}/state",
        json={"favorite": True, "important": True, "read_later": True},
    )
    assert r7.status_code == 200
    assert r7.get_json()["favorite_at"] is not None
    assert r7.get_json()["important_at"] is not None
    assert r7.get_json()["read_later_at"] is not None
    assert r7.get_json()["read_later_done_at"] is None

    favorites = client.get("/api/news?collection=favorites")
    assert favorites.status_code == 200
    assert favorites.get_json()["total"] == 1

    important = client.get("/api/news?collection=important")
    assert important.status_code == 200
    assert important.get_json()["total"] == 1

    read_later = client.get("/api/news?collection=read_later")
    assert read_later.status_code == 200
    assert read_later.get_json()["total"] == 1

    done = client.patch(f"/api/news/{item_id}/state", json={"read_later": False})
    assert done.status_code == 200
    assert done.get_json()["read_later_at"] is None
    assert done.get_json()["read_later_done_at"] is not None

    read_later_unread = client.get("/api/news?collection=read_later&read_filter=unread")
    assert read_later_unread.status_code == 200
    assert read_later_unread.get_json()["total"] == 0

    read_later_read = client.get("/api/news?collection=read_later&read_filter=read")
    assert read_later_read.status_code == 200
    assert read_later_read.get_json()["total"] == 0

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO article_details(
                url, source, title, published_at, content, content_length, raw_json, fetched_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/api",
                "API Source",
                "API News",
                "2026-05-25 10:00:00",
                "cached detail",
                len("cached detail"),
                "{}",
                "2026-05-25 10:05:00",
                "2026-05-25 10:05:00",
            ),
        )

    read_later_read = client.get("/api/news?collection=read_later&read_filter=read")
    assert read_later_read.status_code == 200
    assert read_later_read.get_json()["total"] == 1

    read_later_all = client.get("/api/news?collection=read_later&read_filter=all")
    assert read_later_all.status_code == 200
    assert read_later_all.get_json()["total"] == 1

    combo = client.get("/api/news?collection=important&read_filter=unread")
    assert combo.status_code == 200
    assert combo.get_json()["total"] == 1


def test_daily_briefings_index_and_detail(tmp_path: Path, monkeypatch):
    briefing_dir = tmp_path / "briefings" / "daily"
    make_daily_briefing(briefing_dir / "2026-06-29_daily.md", DAILY_BRIEFING_0629)
    make_daily_briefing(briefing_dir / "2026-06-30_daily.md", DAILY_BRIEFING_0630)
    make_daily_briefing(briefing_dir / "2026-07-01_daily.md", DAILY_BRIEFING_0701)
    daily_root = tmp_path / "DailyNews"
    daily_root.mkdir()
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_root))
    monkeypatch.setenv("NEWS_READER_DAILY_BRIEFING_DIR", str(briefing_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    index = client.get("/api/daily-briefings")
    assert index.status_code == 200
    payload = index.get_json()
    assert payload["ok"] is True
    assert payload["total"] == 3
    assert [month["month"] for month in payload["months"]] == ["2026-07", "2026-06"]
    assert payload["months"][0]["items"][0]["title"] == "📋 7月1日 晨间简报"
    assert "执行模式：daily" in payload["months"][0]["items"][0]["metadata_summary"]

    june29 = client.get("/api/daily-briefings/2026-06-29")
    assert june29.status_code == 200
    june29_payload = june29.get_json()["briefing"]
    assert june29_payload["metadata"][0]["value"] == "daily"
    assert june29_payload["title"] == "6月29日 日报"
    assert june29_payload["sections"][0]["title"] == "当前关注"
    assert june29_payload["sections"][1]["items"][0]["parts"][0] == {"type": "bold", "text": "中东"}

    june30 = client.get("/api/daily-briefings/2026-06-30")
    assert june30.status_code == 200
    june30_payload = june30.get_json()["briefing"]
    assert june30_payload["title"] == "📋 6月30日 全日摘要"
    assert june30_payload["footer_note"].startswith("今日数据：197条")
    tracking = next(section for section in june30_payload["sections"] if section["title"] == "🔍 关注追踪")
    assert [item["type"] for item in tracking["items"]] == ["paragraph", "paragraph"]

    july01 = client.get("/api/daily-briefings/2026-07-01")
    assert july01.status_code == 200
    july01_payload = july01.get_json()["briefing"]
    ai_section = next(section for section in july01_payload["sections"] if section["title"] == "🤖 AI动态")
    assert any(part["type"] == "code" and part["text"] == "Claude Sonnet 5" for part in ai_section["items"][1]["parts"])


def test_daily_briefings_missing_dir_and_invalid_date(tmp_path: Path, monkeypatch):
    missing_briefing_dir = tmp_path / "missing-briefings"
    daily_root = tmp_path / "DailyNews"
    daily_root.mkdir()
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_root))
    monkeypatch.setenv("NEWS_READER_DAILY_BRIEFING_DIR", str(missing_briefing_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    empty_index = client.get("/api/daily-briefings")
    assert empty_index.status_code == 200
    assert empty_index.get_json()["months"] == []
    assert empty_index.get_json()["total"] == 0

    invalid = client.get("/api/daily-briefings/2026-99-99")
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_date"

    traversal = client.get("/api/daily-briefings/..")
    assert traversal.status_code == 400
    assert traversal.get_json()["error"] == "invalid_date"

    missing = client.get("/api/daily-briefings/2026-07-31")
    assert missing.status_code == 404
    assert missing.get_json()["error"] == "not_found"


def test_reindex_and_detail_return_ingest_provenance(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    md_path = daily_dir / "dailyFreshNews_2026-05-25.md"
    sidecar_path = daily_dir / "dailyFreshNews_2026-05-25.newsreader.json"
    make_api_daily(md_path, "Markdown 标题", "https://example.com/api-sidecar", summary="Markdown 摘要")
    make_api_sidecar(sidecar_path, title="JSON 标题", url="https://example.com/api-sidecar", summary="JSON 摘要")
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()

    reindex_payload = client.post("/api/reindex", json={}).get_json()
    assert reindex_payload["ingest_counts"] == {
        "sidecar_json": 1,
        "markdown_fallback": 0,
        "markdown_only": 0,
    }

    item = client.get("/api/news?per=20").get_json()["items"][0]
    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["ingest_mode"] == "sidecar_json"
    assert detail["ingest_warning"] is None

    sidecar_path.write_text(json.dumps({"schema_version": "newsreader.daily.v0", "items": []}), encoding="utf-8")

    reindex_payload_2 = client.post("/api/reindex", json={}).get_json()
    assert reindex_payload_2["ingest_counts"] == {
        "sidecar_json": 0,
        "markdown_fallback": 1,
        "markdown_only": 0,
    }
    detail_2 = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail_2["ingest_mode"] == "markdown_fallback"
    assert detail_2["ingest_warning"] == "unsupported_newsreader_daily_schema"


def test_sidecar_source_identity_survives_section_only_source(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    md_path = daily_dir / "dailyFreshNews_2026-06-30.md"
    sidecar_path = daily_dir / "dailyFreshNews_2026-06-30.newsreader.json"
    md_path.write_text("", encoding="utf-8")
    sidecar_path.write_text(
        json.dumps(
            {
                "schema_version": "newsreader.daily.v1",
                "items": [
                    {
                        "item_order": 1,
                        "section": "world",
                        "source_type": "reuters",
                        "source_name": "Reuters",
                        "title": "Sidecar section source",
                        "summary": "JSON 摘要",
                        "published_at": "2026-06-30 09:30:00",
                        "url": "https://www.reuters.com/world/example-2026-06-30/",
                    }
                ],
            },
            ensure_ascii=False,
        ),
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

    item = client.get("/api/news?read_filter=all&per=20").get_json()["items"][0]
    assert item["source"] == "world"
    assert item["source_type"] == "reuters"
    assert item["source_name"] == "Reuters"
    assert item["source_key"] == "reuters"


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


def test_news_reminders_crud_and_snapshot_summary(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    daily_file = daily_dir / "dailyFreshNews_2026-06-20.md"
    daily_file.write_text(
        """## Reuters · World（1条）
### [Reminder Alpha](https://example.com/reminder-alpha)
- 发布时间：2026-06-20 09:00:00
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
    item = client.get("/api/news?per=20").get_json()["items"][0]
    assert item["active_reminder_count"] == 0
    assert item["due_reminder_count"] == 0
    assert item["next_remind_at"] is None

    create = client.post(
        f"/api/news/{item['id']}/reminders",
        json={
            "event_title": "英伟达财报",
            "event_date": "2026-06-25",
            "remind_at": "2026-06-24T21:30",
            "note": "回看毛利率和指引",
        },
    )
    assert create.status_code == 200
    created_payload = create.get_json()
    reminder = created_payload["reminder"]
    assert reminder["status"] == "active"
    assert reminder["event_date"] == "2026-06-25"
    assert reminder["remind_at"] == "2026-06-24 21:30:00"
    assert created_payload["summary"]["active_total"] == 1

    reminders = client.get("/api/reminders").get_json()
    assert reminders["summary"]["active_total"] == 1
    assert reminders["items"][0]["item_title_snapshot"] == "Reminder Alpha"
    assert reminders["items"][0]["item_url_snapshot"] == "https://example.com/reminder-alpha"
    assert reminders["items"][0]["item"]["id"] == item["id"]

    feed_item = client.get("/api/news?per=20").get_json()["items"][0]
    assert feed_item["active_reminder_count"] == 1
    assert feed_item["next_remind_at"] == "2026-06-24 21:30:00"

    status_item = client.get(f"/api/news/status?ids={item['id']}").get_json()["items"][0]
    assert status_item["active_reminder_count"] == 1
    assert status_item["next_remind_at"] == "2026-06-24 21:30:00"

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["reminder_summary"]["active_total"] == 1
    assert detail["reminders"][0]["event_title"] == "英伟达财报"

    done = client.patch(
        f"/api/reminders/{reminder['id']}",
        json={"status": "done"},
    )
    assert done.status_code == 200
    assert done.get_json()["reminder"]["status"] == "done"
    assert done.get_json()["reminder"]["completed_at"] is not None

    reopened = client.patch(
        f"/api/reminders/{reminder['id']}",
        json={
            "status": "active",
            "event_title": "英伟达财报更新",
            "remind_at": "2026-06-24 22:00:00",
        },
    )
    assert reopened.status_code == 200
    reopened_payload = reopened.get_json()["reminder"]
    assert reopened_payload["status"] == "active"
    assert reopened_payload["completed_at"] is None
    assert reopened_payload["event_title"] == "英伟达财报更新"
    assert reopened_payload["remind_at"] == "2026-06-24 22:00:00"

    deleted = client.delete(f"/api/reminders/{reminder['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["summary"]["active_total"] == 0
    assert client.get("/api/reminders").get_json()["items"] == []


def test_reminder_snapshot_survives_stale_item_deletion(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    daily_file = daily_dir / "dailyFreshNews_2026-06-20.md"
    daily_file.write_text(
        """## Reuters · World（1条）
### [Snapshot Beta](https://example.com/snapshot-beta)
- 发布时间：2026-06-20 10:00:00
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
    item = client.get("/api/news?per=20").get_json()["items"][0]
    create = client.post(
        f"/api/news/{item['id']}/reminders",
        json={
            "event_title": "回看政策落地",
            "event_date": "2026-06-30",
            "remind_at": "2026-06-29 09:00:00",
            "note": "",
        },
    )
    assert create.status_code == 200

    daily_file.unlink()
    assert client.post("/api/reindex", json={"full": True}).status_code == 200
    assert client.get("/api/news?per=20").get_json()["total"] == 0

    reminders = client.get("/api/reminders").get_json()
    assert reminders["summary"]["active_total"] == 1
    assert reminders["items"][0]["item_exists"] == 0
    assert reminders["items"][0]["item"] is None
    assert reminders["items"][0]["item_title_snapshot"] == "Snapshot Beta"
    assert reminders["items"][0]["item_url_snapshot"] == "https://example.com/snapshot-beta"


def test_apply_schema_adds_favorite_at_and_read_later_done_at_and_migrates_legacy_bookmarked(tmp_path: Path, monkeypatch):
    daily_root = tmp_path / "DailyNews"
    daily_root.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_root))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE item_state (
              item_id TEXT PRIMARY KEY,
              bookmarked INTEGER DEFAULT 0,
              skipped INTEGER DEFAULT 0,
              read_at TEXT,
              important_at TEXT,
              read_later_at TEXT,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO item_state(item_id, bookmarked, updated_at)
            VALUES ('legacy-1', 1, '2026-06-20 10:00:00')
            """
        )
        conn.commit()
    finally:
        conn.close()

    app_module.ensure_db()
    app_module.ensure_db()

    conn = app_module.db_conn()
    try:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(item_state)").fetchall()}
        assert "favorite_at" in cols
        assert "read_later_done_at" in cols
        migrated = conn.execute(
            "SELECT favorite_at FROM item_state WHERE item_id='legacy-1'"
        ).fetchone()
        assert migrated is not None
        assert migrated["favorite_at"] == "2026-06-20 10:00:00"
    finally:
        conn.close()


def test_apply_schema_creates_news_reminders_table_and_indexes(tmp_path: Path, monkeypatch):
    daily_root = tmp_path / "DailyNews"
    daily_root.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_root))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    app_module.ensure_db()

    conn = app_module.db_conn()
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "news_reminders" in tables

        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_news_reminders_status_remind_at" in indexes
        assert "idx_news_reminders_item_id" in indexes
    finally:
        conn.close()


def test_apply_schema_creates_tracked_topic_tables_and_indexes(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "news_index.sqlite3"
    daily_root = tmp_path / "DailyNews"
    daily_root.mkdir()

    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_root))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    app_module.ensure_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "tracked_topics" in tables
        assert "tracked_topic_items" in tables
        assert "tracked_topic_daily_summaries" in tables
        tracked_topic_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(tracked_topics)").fetchall()
        }
        assert "rules_json" in tracked_topic_cols

        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_tracked_topics_active_updated_at" in indexes
        assert "idx_tracked_topic_items_topic_hidden" in indexes
        assert "idx_tracked_topic_items_item_id" in indexes
        assert "idx_tracked_topic_daily_summaries_topic_date" in indexes
    finally:
        conn.close()


def test_apply_schema_creates_market_tag_summary_table(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "news_index.sqlite3"
    daily_root = tmp_path / "DailyNews"
    daily_root.mkdir()

    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_root))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        assert "market_tag_summaries" in tables
        assert "idx_market_tag_summaries_tag_range" in indexes
    finally:
        conn.close()


def test_tracked_topics_backfill_incremental_and_overrides(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    old_daily = tmp_path / "DailyNews" / "2025年12月"
    old_daily.mkdir(parents=True)

    (old_daily / "dailyFreshNews_2025-12-01.md").write_text(
        """## Reuters · World（1条）
### [乌克兰俄罗斯谈判旧战况](https://example.com/ru-old)
- 发布时间：2025-12-01 09:00:00
- 摘要：旧战况整理
""",
        encoding="utf-8",
    )
    (daily_dir / "dailyFreshNews_2026-06-20.md").write_text(
        """## Reuters · World（8条）
### [乌克兰无人机袭击俄军机场](https://example.com/ru-now)
- 发布时间：2026-06-20 08:00:00
- 摘要：俄罗斯多个机场遭袭

### [俄罗斯股市观察](https://example.com/russia-market)
- 发布时间：2026-06-20 08:30:00
- 摘要：俄罗斯市场波动

### [俄罗斯方块大赛开幕](https://example.com/tetris)
- 发布时间：2026-06-20 09:00:00
- 摘要：体育游戏活动

### [欧洲防务观察](https://example.com/note-match)
- 发布时间：2026-06-20 09:30:00
- 摘要：欧洲局势观察

### [欧洲防务观察二](https://example.com/summary-match)
- 发布时间：2026-06-20 10:00:00
- 摘要：普通摘要

### [国际局势综述](https://example.com/body-only)
- 发布时间：2026-06-20 10:30:00
- 摘要：普通摘要

### [乌克兰基辅停火进展](https://example.com/all-news-match)
- 发布时间：2026-06-20 10:45:00
- 摘要：俄罗斯与乌克兰讨论停火

### [无关宏观观察](https://example.com/macro)
- 发布时间：2026-06-20 11:00:00
- 摘要：美元指数波动
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

    first_reindex = client.post("/api/reindex", json={})
    assert first_reindex.status_code == 200
    assert first_reindex.get_json()["tracked_incremental_matches"] == 0

    items = client.get("/api/news?per=20").get_json()["items"]
    by_title = {item["title"]: item for item in items}
    old_item = by_title["乌克兰俄罗斯谈判旧战况"]
    recent_item = by_title["乌克兰无人机袭击俄军机场"]
    broad_item = by_title["俄罗斯股市观察"]
    exclude_item = by_title["俄罗斯方块大赛开幕"]
    note_match_item = by_title["欧洲防务观察"]
    summary_match_item = by_title["欧洲防务观察二"]
    body_only_item = by_title["国际局势综述"]
    all_news_match_item = by_title["乌克兰基辅停火进展"]
    manual_item = by_title["无关宏观观察"]

    for item in (
        old_item,
        recent_item,
        broad_item,
        exclude_item,
        note_match_item,
        summary_match_item,
        body_only_item,
    ):
        assert client.patch(
            f"/api/news/{item['id']}/state",
            json={"important": True},
        ).status_code == 200

    conn = sqlite3.connect(db_path)
    try:
        ts = "2026-06-20 12:00:00"
        conn.execute(
            """
            INSERT INTO article_notes(url, note, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                note_match_item["url"],
                "乌克兰 无人机 袭击升级",
                ts,
                ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO article_notes(url, note, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                exclude_item["url"],
                "乌克兰 无人机 袭击升级",
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
                summary_match_item["url"],
                "deepseek-chat",
                json.dumps(["乌克兰", "俄罗斯", "基辅"], ensure_ascii=False),
                "袭击升级",
                "补充正文",
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
                body_only_item["url"],
                "deepseek-chat",
                json.dumps([], ensure_ascii=False),
                "",
                "乌克兰 俄罗斯 无人机 袭击",
                "{}",
                ts,
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    create_topic = client.post(
        "/api/tracked-topics",
        json={
            "title": "俄乌战争",
            "description": "长期观察俄乌事件",
            "core_terms": ["乌克兰", "俄罗斯"],
            "context_terms": ["无人机", "袭击", "谈判", "机场", "基辅"],
            "exclude_terms": ["俄罗斯方块", "旅游", "文学", "体育"],
            "threshold": 6,
            "scope": "all",
            "active": True,
        },
    )
    assert create_topic.status_code == 200
    topic = create_topic.get_json()["topic"]
    topic_id = topic["id"]
    assert topic["rules"]["core_terms"] == ["乌克兰", "俄罗斯"]
    assert topic["rules"]["threshold"] == 6
    assert topic["rules"]["title_weight"] == 1
    assert topic["rules"]["note_weight"] == 1
    assert topic["rules"]["strong_score"] == 1
    assert topic["rules"]["exclude_penalty"] == 1

    all_backfill = client.post(
        f"/api/tracked-topics/{topic_id}/backfill",
        json={"mode": "all_important"},
    )
    assert all_backfill.status_code == 200
    all_payload = all_backfill.get_json()
    assert [item["title"] for item in all_payload["items"]] == [
        "欧洲防务观察二",
        "欧洲防务观察",
        "乌克兰无人机袭击俄军机场",
        "乌克兰俄罗斯谈判旧战况",
    ]
    assert any(
        marker in all_payload["items"][0]["tracked_reason"]
        for marker in ("标题命中", "笔记命中", "摘要命中")
    )
    assert "score=" in all_payload["items"][0]["tracked_reason"]
    assert broad_item["title"] not in [item["title"] for item in all_payload["items"]]
    assert exclude_item["title"] not in [item["title"] for item in all_payload["items"]]
    assert body_only_item["title"] not in [item["title"] for item in all_payload["items"]]
    assert all_news_match_item["title"] not in [item["title"] for item in all_payload["items"]]

    all_news_backfill = client.post(
        f"/api/tracked-topics/{topic_id}/backfill",
        json={"mode": "all_news"},
    )
    assert all_news_backfill.status_code == 200
    assert [item["title"] for item in all_news_backfill.get_json()["items"]] == [
        "乌克兰基辅停火进展",
        "欧洲防务观察二",
        "欧洲防务观察",
        "乌克兰无人机袭击俄军机场",
        "乌克兰俄罗斯谈判旧战况",
    ]

    hide_recent = client.patch(
        f"/api/tracked-topics/{topic_id}/items/{recent_item['id']}",
        json={"hidden": True},
    )
    assert hide_recent.status_code == 200

    no_revive = client.post(
        f"/api/tracked-topics/{topic_id}/backfill",
        json={"mode": "all_news"},
    )
    assert no_revive.status_code == 200
    assert [item["title"] for item in no_revive.get_json()["items"]] == [
        "乌克兰基辅停火进展",
        "欧洲防务观察二",
        "欧洲防务观察",
        "乌克兰俄罗斯谈判旧战况",
    ]

    manual_add = client.post(
        f"/api/tracked-topics/{topic_id}/items",
        json={"item_id": manual_item["id"]},
    )
    assert manual_add.status_code == 200

    after_manual = client.get(f"/api/tracked-topics/{topic_id}/items")
    assert after_manual.status_code == 200
    assert [item["title"] for item in after_manual.get_json()["items"]] == [
        "无关宏观观察",
        "乌克兰基辅停火进展",
        "欧洲防务观察二",
        "欧洲防务观察",
        "乌克兰俄罗斯谈判旧战况",
    ]

    update_topic = client.patch(
        f"/api/tracked-topics/{topic_id}",
        json={
            "core_terms": ["乌克兰", "俄罗斯"],
            "context_terms": ["停火"],
            "threshold": 6,
        },
    )
    assert update_topic.status_code == 200

    recomputed = client.post(
        f"/api/tracked-topics/{topic_id}/backfill",
        json={"mode": "all_news"},
    )
    assert recomputed.status_code == 200
    recomputed_titles = [item["title"] for item in recomputed.get_json()["items"]]
    assert recomputed_titles == [
        "无关宏观观察",
        "乌克兰基辅停火进展",
    ]

    (daily_dir / "dailyFreshNews_2026-06-21.md").write_text(
        """## Reuters · World（1条）
### [乌克兰停火新消息](https://example.com/ru-new)
- 发布时间：2026-06-21 11:00:00
- 摘要：俄罗斯与乌克兰回应停火
""",
        encoding="utf-8",
    )
    second_reindex = client.post("/api/reindex", json={})
    assert second_reindex.status_code == 200
    assert second_reindex.get_json()["tracked_incremental_matches"] == 1

    final_timeline = client.get(f"/api/tracked-topics/{topic_id}/items").get_json()
    assert [item["title"] for item in final_timeline["items"]] == [
        "乌克兰停火新消息",
        "无关宏观观察",
        "乌克兰基辅停火进展",
    ]
    assert final_timeline["items"][1]["tracked_match_method"] == "manual"
    assert "标题命中" in final_timeline["items"][0]["tracked_reason"]

    custom_weight_topic = client.post(
        "/api/tracked-topics",
        json={
            "title": "笔记权重测试",
            "core_terms": ["乌克兰"],
            "context_terms": ["袭击"],
            "exclude_terms": ["俄罗斯方块"],
            "threshold": 7,
            "note_weight": 1.5,
            "scope": "all",
            "active": False,
        },
    )
    assert custom_weight_topic.status_code == 200
    custom_topic = custom_weight_topic.get_json()["topic"]
    assert custom_topic["rules"]["note_weight"] == 1.5
    custom_topic_id = custom_topic["id"]

    custom_backfill = client.post(
        f"/api/tracked-topics/{custom_topic_id}/backfill",
        json={"mode": "all_important"},
    )
    assert custom_backfill.status_code == 200
    custom_items = custom_backfill.get_json()["items"]
    assert [item["title"] for item in custom_items] == ["欧洲防务观察"]
    assert custom_items[0]["tracked_score"] == 7.5
    assert "笔记命中" in custom_items[0]["tracked_reason"]
    assert "score=7.5" in custom_items[0]["tracked_reason"]

    zero_weight_update = client.patch(
        f"/api/tracked-topics/{custom_topic_id}",
        json={
            "title": custom_topic["title"],
            "description": custom_topic["description"],
            "core_terms": ["乌克兰"],
            "context_terms": ["袭击"],
            "exclude_terms": ["俄罗斯方块"],
            "threshold": 7,
            "note_weight": 0,
            "scope": "all",
            "active": False,
        },
    )
    assert zero_weight_update.status_code == 200
    assert zero_weight_update.get_json()["topic"]["rules"]["note_weight"] == 0

    zero_weight_backfill = client.post(
        f"/api/tracked-topics/{custom_topic_id}/backfill",
        json={"mode": "all_important"},
    )
    assert zero_weight_backfill.status_code == 200
    assert zero_weight_backfill.get_json()["items"] == []

    detail = client.get(f"/api/news/{manual_item['id']}/detail")
    assert detail.status_code == 200
    assert detail.get_json()["tracked_topic_choices"][0]["title"] == "俄乌战争"


def test_tracked_required_terms_gate_and_backfill_preserves_manual_hidden(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-20.md").write_text(
        """## Reuters · World（4条）
### [霍尔木兹海峡美伊战争升级](https://example.com/hormuz)
- 发布时间：2026-06-20 08:00:00
- 摘要：局势升级

### [德黑兰美伊战争升级](https://example.com/tehran)
- 发布时间：2026-06-20 08:30:00
- 摘要：局势升级

### [波斯湾美伊战争观察](https://example.com/gulf)
- 发布时间：2026-06-20 09:00:00
- 摘要：局势观察

### [霍尔木兹海峡美伊演习升级](https://example.com/drill)
- 发布时间：2026-06-20 09:30:00
- 摘要：演习升级
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
    by_title = {item["title"]: item for item in items}
    hormuz_item = by_title["霍尔木兹海峡美伊战争升级"]
    tehran_item = by_title["德黑兰美伊战争升级"]
    gulf_item = by_title["波斯湾美伊战争观察"]
    drill_item = by_title["霍尔木兹海峡美伊演习升级"]

    for item in (hormuz_item, tehran_item, gulf_item, drill_item):
        assert client.patch(f"/api/news/{item['id']}/state", json={"important": True}).status_code == 200

    create_topic = client.post(
        "/api/tracked-topics",
        json={
            "title": "美伊战争",
            "core_terms": ["美伊"],
            "context_terms": ["战争", "升级"],
            "exclude_terms": ["演习"],
            "required_terms": ["霍尔木兹"],
            "threshold": 6,
            "scope": "all",
            "active": True,
        },
    )
    assert create_topic.status_code == 200
    topic_id = create_topic.get_json()["topic"]["id"]

    first_backfill = client.post(
        f"/api/tracked-topics/{topic_id}/backfill",
        json={"mode": "all_important"},
    )
    assert first_backfill.status_code == 200
    first_items = first_backfill.get_json()["items"]
    assert [item["title"] for item in first_items] == ["霍尔木兹海峡美伊战争升级"]
    assert "必要词命中：霍尔木兹" in first_items[0]["tracked_reason"]

    hide_hormuz = client.patch(
        f"/api/tracked-topics/{topic_id}/items/{hormuz_item['id']}",
        json={"hidden": True},
    )
    assert hide_hormuz.status_code == 200

    manual_add = client.post(
        f"/api/tracked-topics/{topic_id}/items",
        json={"item_id": gulf_item["id"]},
    )
    assert manual_add.status_code == 200

    update_topic = client.patch(
        f"/api/tracked-topics/{topic_id}",
        json={
            "title": "美伊战争",
            "core_terms": ["美伊"],
            "context_terms": ["战争", "升级"],
            "exclude_terms": ["演习"],
            "required_terms": ["霍尔木兹", "德黑兰"],
            "threshold": 6,
            "scope": "all",
            "active": True,
        },
    )
    assert update_topic.status_code == 200

    second_backfill = client.post(
        f"/api/tracked-topics/{topic_id}/backfill",
        json={"mode": "all_important"},
    )
    assert second_backfill.status_code == 200
    second_items = second_backfill.get_json()["items"]
    assert [item["title"] for item in second_items] == [
        "波斯湾美伊战争观察",
        "德黑兰美伊战争升级",
    ]
    assert second_items[0]["tracked_match_method"] == "manual"
    assert "必要词命中：德黑兰" in second_items[1]["tracked_reason"]
    assert hormuz_item["title"] not in [item["title"] for item in second_items]
    assert drill_item["title"] not in [item["title"] for item in second_items]


def test_tracked_topic_daily_summaries_generate_and_stale(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-20.md").write_text(
        """## Reuters · World（4条）
### [俄乌战争：乌克兰回应](https://example.com/ru-day-1)
- 发布时间：2026-06-20 09:00:00
- 摘要：乌克兰方面作出回应

### [俄乌战争：俄罗斯表态](https://example.com/ru-day-2)
- 发布时间：2026-06-20 11:00:00
- 摘要：俄罗斯方面发布声明

### [补充战况](https://example.com/ru-day-manual)
- 发布时间：2026-06-20 12:00:00
- 摘要：更多细节出现

### [俄乌战争：停火谈判](https://example.com/ru-day-3)
- 发布时间：2026-06-21 08:30:00
- 摘要：谈判出现新进展
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
    items = client.get("/api/news?per=20").get_json()["items"]
    by_title = {item["title"]: item for item in items}
    create_tag = client.post("/api/market-tags", json={"display_name": "俄乌战争"})
    assert create_tag.status_code == 200
    tag_key = create_tag.get_json()["tag"]["key"]
    assert client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-20", "tag_key": tag_key, "direction": "bullish", "note": "独立想法也在跟踪主题里补充判断"},
    ).status_code == 200

    topic_res = client.post(
        "/api/tracked-topics",
        json={
            "title": "俄乌战争",
            "strong_phrases": ["俄乌战争"],
            "core_terms": ["俄乌"],
            "context_terms": ["补充判断"],
            "threshold": 6,
            "scope": "all",
            "active": True,
        },
    )
    assert topic_res.status_code == 200
    topic_id = topic_res.get_json()["topic"]["id"]

    conn = sqlite3.connect(db_path)
    try:
        ts = "2026-06-20 13:00:00"
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                by_title["俄乌战争：乌克兰回应"]["url"],
                "Reuters",
                "俄乌战争：乌克兰回应",
                "2026-06-20 09:00:00",
                "Full local body 1",
                17,
                "{}",
                ts,
                ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                by_title["俄乌战争：俄罗斯表态"]["url"],
                "Reuters",
                "俄乌战争：俄罗斯表态",
                "2026-06-20 11:00:00",
                "Full local body 2",
                17,
                "{}",
                ts,
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    backfill = client.post(f"/api/tracked-topics/{topic_id}/backfill", json={"mode": "all_news"})
    assert backfill.status_code == 200

    listing = client.get(f"/api/tracked-topics/{topic_id}/daily-summaries")
    assert listing.status_code == 200
    days = listing.get_json()["days"]
    assert [day["date"] for day in days] == ["2026-06-21", "2026-06-20"]
    assert days[0]["status"] == "missing"
    assert days[0]["items"][0]["has_detail"] is False
    assert all(item["entry_type"] == "news" for item in days[1]["items"])
    assert [item["title"] for item in days[1]["items"]] == [
        "俄乌战争：乌克兰回应",
        "俄乌战争：俄罗斯表态",
    ]
    assert days[1]["max_summary_chars"] == 120
    assert all(item["has_detail"] is True for item in days[1]["items"][:2])

    def fail_summary(**kwargs):
        raise app_module.LLMClientError("DEEPSEEK_CALL_FAILED: unavailable")

    monkeypatch.setattr(app_module, "generate_tracked_topic_daily_summary", fail_summary)
    failed = client.post(f"/api/tracked-topics/{topic_id}/daily-summaries/2026-06-20/generate")
    assert failed.status_code == 502
    assert failed.get_json()["error"] == "daily_summary_generate_failed"

    failed_listing = client.get(f"/api/tracked-topics/{topic_id}/daily-summaries").get_json()["days"]
    failed_day = next(day for day in failed_listing if day["date"] == "2026-06-20")
    assert failed_day["status"] == "failed"

    captured: dict[str, object] = {}

    def ok_summary(**kwargs):
        captured["materials"] = kwargs["materials"]
        captured["max_summary_chars"] = kwargs["max_summary_chars"]
        captured["news_count"] = kwargs["news_count"]
        return {
            "model": "deepseek-chat",
            "summary_text": "甲" * 180,
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_tracked_topic_daily_summary", ok_summary)
    generated = client.post(f"/api/tracked-topics/{topic_id}/daily-summaries/2026-06-20/generate")
    assert generated.status_code == 200
    generated_day = generated.get_json()["day"]
    assert generated_day["status"] == "success"
    assert generated_day["max_summary_chars"] == 120
    assert captured["max_summary_chars"] == 120
    assert captured["news_count"] == 2
    assert len(generated_day["summary_text"]) <= 120
    assert generated_day["summary_text"].endswith("…")
    assert captured["materials"].index("标题：俄乌战争：乌克兰回应") < captured["materials"].index("标题：俄乌战争：俄罗斯表态")
    assert "正文：Full local body 1" in captured["materials"]
    assert "正文：Full local body 2" in captured["materials"]
    assert "【独立想法 / 用户判断】" not in captured["materials"]
    assert "无独立想法。" not in captured["materials"]

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE tracked_topic_daily_summaries SET item_ids_hash=? WHERE topic_id=? AND date=?",
            ("legacy-v1.9.8.4-hash", topic_id, "2026-06-20"),
        )
        conn.commit()
    stale_from_version = client.get(f"/api/tracked-topics/{topic_id}/daily-summaries").get_json()["days"]
    stale_version_day = next(day for day in stale_from_version if day["date"] == "2026-06-20")
    assert stale_version_day["status"] == "stale"

    manual_add = client.post(
        f"/api/tracked-topics/{topic_id}/items",
        json={"item_id": by_title["补充战况"]["id"]},
    )
    assert manual_add.status_code == 200

    stale_listing = client.get(f"/api/tracked-topics/{topic_id}/daily-summaries").get_json()["days"]
    stale_day = next(day for day in stale_listing if day["date"] == "2026-06-20")
    assert stale_day["status"] == "stale"
    assert stale_day["item_count"] == 3


def test_tracked_daily_summary_limits_and_truncation_helpers(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    assert app_module.tracked_daily_summary_char_limit(1) == 120
    assert app_module.tracked_daily_summary_char_limit(3) == 150
    assert app_module.tracked_daily_summary_char_limit(10) == 500
    assert app_module.tracked_daily_summary_char_limit(20) == 600
    assert app_module.enforce_daily_summary_char_limit("第一句。第二句。第三句。", 6) == "第一句。…"
    assert app_module.enforce_daily_summary_char_limit("abcdefghijklmnopqrstuvwxyz", 8) == "abcdefg…"


def test_tracked_topic_manual_add_trend_note_rejected(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-20.md").write_text(
        """## Reuters · World（1条）
### [普通新闻](https://example.com/plain)
- 发布时间：2026-06-20 09:00:00
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

    create_tag = client.post("/api/market-tags", json={"display_name": "AI 跟踪测试"})
    assert create_tag.status_code == 200
    tag_key = create_tag.get_json()["tag"]["key"]
    note_res = client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-20", "tag_key": tag_key, "direction": "bullish", "note": "AI 独立趋势判断"},
    )
    assert note_res.status_code == 200
    note_id = note_res.get_json()["trend_note"]["id"]

    topic_res = client.post(
        "/api/tracked-topics",
        json={
            "title": "AI",
            "strong_phrases": ["AI"],
            "threshold": 6,
            "scope": "all",
            "active": True,
        },
    )
    assert topic_res.status_code == 200
    topic_id = topic_res.get_json()["topic"]["id"]

    add_res = client.post(
        f"/api/tracked-topics/{topic_id}/items",
        json={"item_id": f"trend_note:{note_id}"},
    )
    assert add_res.status_code == 400
    assert add_res.get_json()["error"] == "invalid_item_id"


def test_tracked_topic_rule_draft_generate_and_save(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-20.md").write_text("", encoding="utf-8")
    db_path = tmp_path / "news_index.sqlite3"

    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()

    empty = client.post("/api/tracked-topics/rule-draft", json={"title": ""})
    assert empty.status_code == 400
    assert empty.get_json()["error"] == "empty_title"

    def fake_generate_rule_draft(**kwargs):
        assert kwargs["title"] == "美伊战争"
        return {
            "model": "deepseek-chat",
            "title": "美伊战争",
            "strong_phrases": ["美伊战争", "美伊战争", "", "美国伊朗战争"],
            "core_terms": ["美国", "伊朗", "特朗普", "X" * 60],
            "context_terms": ["空袭", "导弹", "报复", "空袭"],
            "exclude_terms": ["电影", "游戏", "", "旅游"],
            "threshold": 99,
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_tracked_topic_rule_draft", fake_generate_rule_draft)
    res = client.post("/api/tracked-topics/rule-draft", json={"title": "美伊战争"})
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["ok"] is True
    assert payload["version"] == "v1.9.8.6"
    assert payload["draft"]["title"] == "美伊战争"
    assert payload["draft"]["strong_phrases"] == ["美伊战争", "美国伊朗战争"]
    assert payload["draft"]["core_terms"] == ["美国", "伊朗", "特朗普"]
    assert payload["draft"]["context_terms"] == ["空袭", "导弹", "报复"]
    assert payload["draft"]["exclude_terms"] == ["电影", "游戏", "旅游"]
    assert payload["draft"]["threshold"] == 20

    listed = client.get("/api/tracked-topics").get_json()
    assert listed["items"] == []

    create_res = client.post(
        "/api/tracked-topics",
        json={
            "title": payload["draft"]["title"],
            "strong_phrases": ", ".join(payload["draft"]["strong_phrases"]),
            "core_terms": ", ".join(payload["draft"]["core_terms"]),
            "context_terms": ", ".join(payload["draft"]["context_terms"]),
            "exclude_terms": ", ".join(payload["draft"]["exclude_terms"]),
            "threshold": payload["draft"]["threshold"],
            "scope": "important",
            "active": True,
        },
    )
    assert create_res.status_code == 200
    topic = create_res.get_json()["topic"]
    assert topic["title"] == "美伊战争"
    assert topic["rules"]["strong_phrases"] == ["美伊战争", "美国伊朗战争"]
    assert topic["rules"]["core_terms"] == ["美国", "伊朗", "特朗普"]
    assert topic["rules"]["threshold"] == 20

    invalid_calls = []

    def fake_invalid_rule_draft(**kwargs):
        invalid_calls.append(kwargs["title"])
        raise app_module.LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: broken")

    monkeypatch.setattr(app_module, "generate_tracked_topic_rule_draft", fake_invalid_rule_draft)
    bad = client.post("/api/tracked-topics/rule-draft", json={"title": "AI 发展"})
    assert bad.status_code == 502
    assert bad.get_json()["error"] == "tracked_rule_draft_generate_failed"
    assert invalid_calls == ["AI 发展"]


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

    for item in feed_items:
        res = client.patch(f"/api/news/{item['id']}/state", json={"favorite": True})
        assert res.status_code == 200

    favorite_items = client.get("/api/news?collection=favorites&per=20").get_json()["items"]
    assert [item["title"] for item in favorite_items] == ["Evening", "Noon", "Morning"]

    favorite_reverse = client.get("/api/news?collection=favorites&sort_order=reverse&per=20").get_json()["items"]
    assert [item["title"] for item in favorite_reverse] == ["Morning", "Noon", "Evening"]

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


def test_feed_unread_reverse_sort_keeps_cursor_direction(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)

    reuters_items = []
    for idx in range(31):
        minute = idx % 60
        reuters_items.append(
            "\n".join(
                [
                    f"### [Reuters Reverse {idx + 1}](https://www.reuters.com/world/reverse-{idx + 1})",
                    f"- 发布时间：2026-06-03 09:{minute:02d}:00",
                ]
            )
        )

    (daily_dir / "dailyFreshNews_2026-06-03.md").write_text(
        "## Reuters · World（31条）\n" + "\n".join(reuters_items) + "\n",
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

    page1 = client.get("/api/news?collection=feed&read_filter=unread&sort_order=reverse&page=1&per=30")
    assert page1.status_code == 200
    page1_data = page1.get_json()
    assert page1_data["items"][0]["title"] == "Reuters Reverse 31"
    assert page1_data["items"][-1]["title"] == "Reuters Reverse 2"
    assert page1_data["has_more"] is True
    assert page1_data["next_cursor"] is not None

    for item in page1_data["items"][:10]:
        res = client.patch(f"/api/news/{item['id']}/state", json={"read": True})
        assert res.status_code == 200

    cursor = page1_data["next_cursor"]
    page2 = client.get(
        "/api/news?collection=feed&read_filter=unread&sort_order=reverse&page=2&per=30"
        f"&cursor_date={cursor['date_key']}&cursor_published_at={cursor['published_at']}&cursor_id={cursor['id']}"
    )
    assert page2.status_code == 200
    page2_data = page2.get_json()
    assert [item["title"] for item in page2_data["items"]] == ["Reuters Reverse 1"]
    assert page2_data["has_more"] is False
    assert page2_data["next_cursor"] is None


def test_news_sort_order_switches_default_and_reverse_by_collection(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-04.md").write_text(
        """## Reuters · World（4条）
### [Alpha Early](https://example.com/sort-alpha-early)
- 发布时间：2026-06-04 08:00:00
### [Alpha Late](https://example.com/sort-alpha-late)
- 发布时间：2026-06-04 18:00:00

## Bloomberg · Markets（2条）
### [Beta Early](https://example.com/sort-beta-early)
- 发布时间：2026-06-05 09:00:00
### [Beta Late](https://example.com/sort-beta-late)
- 发布时间：2026-06-05 20:00:00
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

    feed_default = client.get("/api/news?collection=feed&read_filter=all&per=20").get_json()["items"]
    assert [item["title"] for item in feed_default[:4]] == ["Alpha Early", "Alpha Late", "Beta Early", "Beta Late"]

    feed_reverse = client.get("/api/news?collection=feed&read_filter=all&sort_order=reverse&per=20").get_json()["items"]
    assert [item["title"] for item in feed_reverse[:4]] == ["Beta Late", "Beta Early", "Alpha Late", "Alpha Early"]

    title_to_id = {item["title"]: item["id"] for item in feed_default}
    assert client.patch(f"/api/news/{title_to_id['Alpha Early']}/state", json={"important": True, "read_later": True}).status_code == 200
    assert client.patch(f"/api/news/{title_to_id['Beta Late']}/state", json={"important": True, "read_later": True}).status_code == 200
    assert client.patch(f"/api/news/{title_to_id['Beta Early']}/state", json={"important": True}).status_code == 200
    assert client.put(f"/api/news/{title_to_id['Alpha Late']}/note", json={"note": "排序测试想法 A"}).status_code == 200
    assert client.put(f"/api/news/{title_to_id['Beta Early']}/note", json={"note": "排序测试想法 B"}).status_code == 200

    create_tag = client.post("/api/market-tags", json={"display_name": "排序板块"})
    assert create_tag.status_code == 200
    tag_key = create_tag.get_json()["tag"]["key"]
    assert client.put(
        f"/api/news/{title_to_id['Beta Early']}/market-tag",
        json={"tag": tag_key, "direction": "bullish"},
    ).status_code == 200
    assert client.put(
        f"/api/news/{title_to_id['Alpha Early']}/market-tag",
        json={"tag": tag_key, "direction": "bearish"},
    ).status_code == 200

    important_default = client.get("/api/news?collection=important&per=20").get_json()["items"]
    assert [item["title"] for item in important_default] == ["Beta Late", "Beta Early", "Alpha Early"]
    important_reverse = client.get("/api/news?collection=important&sort_order=reverse&per=20").get_json()["items"]
    assert [item["title"] for item in important_reverse] == ["Alpha Early", "Beta Early", "Beta Late"]

    read_later_default = client.get("/api/news?collection=read_later&per=20").get_json()["items"]
    assert [item["title"] for item in read_later_default] == ["Alpha Early", "Beta Late"]
    read_later_reverse = client.get("/api/news?collection=read_later&sort_order=reverse&per=20").get_json()["items"]
    assert [item["title"] for item in read_later_reverse] == ["Beta Late", "Alpha Early"]

    notes_default = client.get("/api/news?collection=notes&per=20").get_json()["items"]
    assert [item["title"] for item in notes_default] == ["Beta Early", "Alpha Late"]
    notes_reverse = client.get("/api/news?collection=notes&sort_order=reverse&per=20").get_json()["items"]
    assert [item["title"] for item in notes_reverse] == ["Alpha Late", "Beta Early"]

    tags_default = client.get("/api/news?collection=market_tags&per=20").get_json()["items"]
    assert [item["title"] for item in tags_default] == ["Beta Early", "Alpha Early"]
    tags_reverse = client.get("/api/news?collection=market_tags&sort_order=reverse&per=20").get_json()["items"]
    assert [item["title"] for item in tags_reverse] == ["Alpha Early", "Beta Early"]

    invalid = client.get("/api/news?collection=feed&sort_order=sideways")
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_sort_order"


def test_unified_ideas_feed_combines_article_and_trend_notes(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-06.md").write_text(
        """## Reuters · World（2条）
### [Idea Alpha](https://example.com/idea-alpha)
- 发布时间：2026-06-06 08:00:00
### [Idea Beta](https://example.com/idea-beta)
- 发布时间：2026-06-06 10:00:00
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

    items = client.get("/api/news?per=20").get_json()["items"]
    alpha = next(item for item in items if item["title"] == "Idea Alpha")
    beta = next(item for item in items if item["title"] == "Idea Beta")

    assert client.put(f"/api/news/{alpha['id']}/note", json={"note": "新闻想法 Alpha"}).status_code == 200
    assert client.put(f"/api/news/{beta['id']}/note", json={"note": "新闻想法 Beta"}).status_code == 200
    assert client.put(
        f"/api/news/{alpha['id']}/market-tag",
        json={"tag": "AI", "direction": "bullish"},
    ).status_code == 200

    trend_create = client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-06", "tag_key": "AI", "direction": "bullish", "note": "趋势想法 Bull"},
    )
    assert trend_create.status_code == 200
    trend_note_id = trend_create.get_json()["trend_note"]["id"]

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE article_notes SET created_at=?, updated_at=? WHERE url=?",
            ("2026-06-06 09:00:00", "2026-06-06 09:00:00", alpha["url"]),
        )
        conn.execute(
            "UPDATE article_notes SET created_at=?, updated_at=? WHERE url=?",
            ("2026-06-06 11:00:00", "2026-06-06 11:00:00", beta["url"]),
        )
        conn.execute(
            "UPDATE market_trend_notes SET created_at=?, updated_at=? WHERE id=?",
            ("2026-06-06 12:30:00", "2026-06-06 12:30:00", trend_note_id),
        )
        conn.commit()

    ideas = client.get("/api/ideas?per=20")
    assert ideas.status_code == 200
    payload = ideas.get_json()
    assert payload["total"] == 3
    assert [item["idea_type"] for item in payload["items"]] == ["trend_note", "article_note", "article_note"]
    assert [item["idea_id"] for item in payload["items"]] == [f"trend:{trend_note_id}", f"article:{beta['id']}", f"article:{alpha['id']}"]
    trend_item = payload["items"][0]
    assert trend_item["tag_key"] == "AI"
    assert trend_item["trend_date_key"] == "2026-06-06"
    assert trend_item["direction"] == "bullish"
    assert trend_item["note"] == "趋势想法 Bull"
    assert trend_item["created_at"] == "2026-06-06 12:30:00"
    assert trend_item["updated_at"] == "2026-06-06 12:30:00"
    article_item = payload["items"][1]
    assert article_item["title"] == "Idea Beta"
    assert article_item["url"] == beta["url"]
    assert article_item["note"] == "新闻想法 Beta"
    assert article_item["created_at"] == "2026-06-06 11:00:00"
    assert article_item["updated_at"] == "2026-06-06 11:00:00"

    article_only = client.get("/api/ideas?type=article&per=20")
    assert article_only.status_code == 200
    assert [item["title"] for item in article_only.get_json()["items"]] == ["Idea Beta", "Idea Alpha"]

    trend_only = client.get("/api/ideas?type=trend&per=20")
    assert trend_only.status_code == 200
    assert [item["idea_id"] for item in trend_only.get_json()["items"]] == [f"trend:{trend_note_id}"]

    reverse = client.get("/api/ideas?per=20&sort_order=reverse")
    assert reverse.status_code == 200
    assert [item["idea_id"] for item in reverse.get_json()["items"]] == [f"article:{alpha['id']}", f"article:{beta['id']}", f"trend:{trend_note_id}"]

    legacy_notes = client.get("/api/news?collection=notes&per=20")
    assert legacy_notes.status_code == 200
    assert [item["title"] for item in legacy_notes.get_json()["items"]] == ["Idea Beta", "Idea Alpha"]

    delete_res = client.delete(f"/api/market-trends/note/{trend_note_id}")
    assert delete_res.status_code == 200
    trend_after_delete = client.get("/api/ideas?type=trend&per=20")
    assert trend_after_delete.status_code == 200
    assert trend_after_delete.get_json()["total"] == 0

    invalid_type = client.get("/api/ideas?type=weird")
    assert invalid_type.status_code == 400
    assert invalid_type.get_json()["error"] == "invalid_idea_type"


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
    assert cancel.get_json()["read_later_done_at"] is not None

    read_later_done = client.get("/api/news?collection=read_later&read_filter=read").get_json()
    assert read_later_done["total"] == 0

    detail_after_cancel = client.get(f"/api/news/{item_id}/detail")
    assert detail_after_cancel.status_code == 200
    after_payload = detail_after_cancel.get_json()
    assert after_payload["detail_status"] in {"canceled", "success", "failed", "running"}

    retry = client.post(f"/api/news/{item_id}/detail/retry")
    assert retry.status_code == 200
    assert retry.get_json()["ok"] is True


def test_twitter_read_later_enqueues_pending_detail_job(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## X · Social（1条）
### [Tweet Update](https://x.com/example/status/123)
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
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=?, summary=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", "Tweet summary context.", item["id"]),
        )
        conn.commit()

    patch = client.patch(f"/api/news/{item['id']}/state", json={"read_later": True})
    assert patch.status_code == 200
    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["detail_status"] == "pending"


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


def test_favorite_state_surfaces_in_status_detail_and_sources(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-05-25.md").write_text(
        """## Reuters · World（1条）
### [Fav Reuters](https://www.reuters.com/world/fav-r)
- 发布时间：2026-05-25 12:00:00
## Bloomberg · Markets（1条）
### [Fav Bloomberg](https://www.bloomberg.com/news/articles/fav-b)
- 发布时间：2026-05-25 13:00:00
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
    first_id = items[0]["id"]
    second_id = items[1]["id"]

    first_patch = client.patch(f"/api/news/{first_id}/state", json={"favorite": True})
    second_patch = client.patch(f"/api/news/{second_id}/state", json={"favorite": True})
    assert first_patch.status_code == 200
    assert second_patch.status_code == 200
    assert first_patch.get_json()["favorite_at"] is not None

    favorites = client.get("/api/news?collection=favorites&per=20").get_json()
    assert favorites["total"] == 2
    assert all(item["favorite_at"] is not None for item in favorites["items"])

    status = client.get(f"/api/news/status?ids={first_id},{second_id}")
    assert status.status_code == 200
    status_items = {item["id"]: item for item in status.get_json()["items"]}
    assert status_items[first_id]["favorite_at"] is not None
    assert status_items[second_id]["favorite_at"] is not None

    detail = client.get(f"/api/news/{first_id}/detail")
    assert detail.status_code == 200
    assert detail.get_json()["favorite_at"] is not None

    sources = client.get("/api/sources?collection=favorites&read_filter=all")
    assert sources.status_code == 200
    source_keys = {item["key"] for item in sources.get_json()["sources"]}
    assert "reuters" in source_keys
    assert "bloomberg" in source_keys

    cancel = client.patch(f"/api/news/{first_id}/state", json={"favorite": False})
    assert cancel.status_code == 200
    assert cancel.get_json()["favorite_at"] is None

    favorites_after = client.get("/api/news?collection=favorites&per=20").get_json()
    assert favorites_after["total"] == 1
    assert favorites_after["items"][0]["id"] == second_id


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


def test_bloomberg_video_pages_are_hidden_server_side_without_deleting_history(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年8月"
    daily_dir.mkdir(parents=True)
    normal_rows = []
    for idx in range(11):
        normal_rows.extend(
            [
                f"### [Bloomberg Filter Normal {idx + 1}](https://www.bloomberg.com/news/articles/2026-08-20/normal-{idx + 1})",
                f"- 发布时间：2026-08-20 09:{idx:02d}:00",
            ]
        )
    normal_rows.extend(
        [
            "### [Bloomberg Filter Ordinary Video Topic](https://www.bloomberg.com/news/articles/2026-08-20/meta-removes-a-video)",
            "- 发布时间：2026-08-20 10:00:00",
        ]
    )
    video_urls = [
        "https://www.bloomberg.com/news/videos/2026-08-20/hidden-one-video",
        "https://bloomberg.com/news/videos/2026-08-20/hidden-two-video?leadSource=uverify",
        "https://markets.bloomberg.com/news/videos/2026-08-20/hidden-three-video",
    ]
    video_rows = []
    for idx, url in enumerate(video_urls):
        video_rows.extend(
            [
                f"### [Bloomberg Filter Hidden {idx + 1}]({url})",
                f"- 发布时间：2026-08-20 11:{idx:02d}:00",
            ]
        )
    (daily_dir / "dailyFreshNews_2026-08-20.md").write_text(
        "## Bloomberg · Markets（15条）\n" + "\n".join([*normal_rows, *video_rows]) + "\n",
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

    with app_module.db_conn() as conn:
        rows = conn.execute("SELECT id, url FROM items ORDER BY url").fetchall()
        assert len(rows) == 15  # Filtering is non-destructive.
        ids_by_url = {row["url"]: row["id"] for row in rows}
        normal_url = "https://www.bloomberg.com/news/articles/2026-08-20/meta-removes-a-video"
        now = "2026-08-20 12:00:00"
        tagged_urls = [normal_url, *video_urls]
        conn.execute(
            "INSERT OR REPLACE INTO market_tag_definitions(key, display_name, active, sort_order, created_at, updated_at) VALUES (?, ?, 1, 0, ?, ?)",
            ("video-filter-test", "Video Filter Test", now, now),
        )
        conn.executemany(
            "INSERT OR REPLACE INTO article_market_tags(url, tag, direction, created_at, updated_at) VALUES (?, ?, 'bullish', ?, ?)",
            [(url, "video-filter-test", now, now) for url in tagged_urls],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO article_notes(url, note, created_at, updated_at) VALUES (?, ?, ?, ?)",
            [(url, "Bloomberg Filter Note", now, now) for url in tagged_urls],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO item_state(item_id, favorite_at, important_at, updated_at) VALUES (?, ?, ?, ?)",
            [(ids_by_url[url], now, now, now) for url in tagged_urls],
        )
        conn.commit()

    feed_page_1 = client.get("/api/news?q=Bloomberg+Filter&read_filter=all&page=1&per=10").get_json()
    feed_page_2 = client.get("/api/news?q=Bloomberg+Filter&read_filter=all&page=2&per=10").get_json()
    assert feed_page_1["total"] == 12
    assert feed_page_1["pages"] == 2
    assert len(feed_page_1["items"]) == 10
    assert len(feed_page_2["items"]) == 2
    assert all("/news/videos/" not in item["url"] for item in [*feed_page_1["items"], *feed_page_2["items"]])
    assert normal_url in {item["url"] for item in [*feed_page_1["items"], *feed_page_2["items"]]}

    search = client.get("/api/search?q=Bloomberg+Filter&range=all&time=all&page=1&per=20").get_json()
    assert search["total"] == 12
    assert all("/news/videos/" not in item["url"] for item in search["items"])

    for collection in ("favorites", "important", "notes", "market_tags"):
        payload = client.get(f"/api/news?collection={collection}&read_filter=all&per=20").get_json()
        assert payload["total"] == 1
        assert payload["items"][0]["url"] == normal_url

    sources = client.get("/api/sources?collection=feed&read_filter=all").get_json()["sources"]
    bloomberg = next(source for source in sources if source["key"] == "bloomberg")
    assert bloomberg["count"] == 12
    assert client.get("/api/nav-summary").get_json()["summary"]["feed_unread"] == 12

    trend = client.get(
        "/api/market-trends/detail?date=2026-08-20&tag=video-filter-test&direction=bullish"
    ).get_json()
    assert trend["total"] == 1
    assert trend["items"][0]["url"] == normal_url
    workbench = client.get("/api/market-workbench?tag=video-filter-test&per=20").get_json()
    assert workbench["total"] == 1
    assert workbench["items"][0]["url"] == normal_url

    for url in video_urls:
        assert client.get(f"/api/news/{ids_by_url[url]}/detail").status_code == 404
    assert client.get(f"/api/news/{ids_by_url[normal_url]}/detail").status_code == 200

    status = client.get(
        "/api/news/status?ids=" + ",".join([ids_by_url[normal_url], *[ids_by_url[url] for url in video_urls]])
    ).get_json()
    assert [item["id"] for item in status["items"]] == [ids_by_url[normal_url]]

    checkpoint = client.put(
        "/api/reading-checkpoint",
        json={"scope": "feed", "item_id": ids_by_url[video_urls[0]], "url": video_urls[0], "title": "hidden"},
    )
    assert checkpoint.status_code == 404
    visible_checkpoint = client.put(
        "/api/reading-checkpoint",
        json={"scope": "feed", "item_id": ids_by_url[normal_url], "url": normal_url, "title": "visible"},
    )
    assert visible_checkpoint.status_code == 200
    assert client.get("/api/reading-checkpoint?scope=feed").get_json()["checkpoint"]["url"] == normal_url

    with app_module.db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reading_checkpoints(scope, item_id, url, title, updated_at)
            VALUES ('feed', ?, ?, 'legacy hidden', '2026-08-20 12:30:00')
            """,
            (ids_by_url[video_urls[0]], video_urls[0]),
        )
        conn.commit()
    assert client.get("/api/reading-checkpoint?scope=feed").get_json()["checkpoint"] is None
    locate = client.get("/api/reading-checkpoint/locate?scope=feed&read_filter=all&per=20").get_json()
    assert locate["found"] is False
    assert locate["reason"] == "no_checkpoint"
    assert "checkpoint" not in locate


def test_v2125_title_clamps_and_version_contract():
    css = Path("static/style.css").read_text(encoding="utf-8")
    html = Path("static/index.html").read_text(encoding="utf-8")

    title_rule = css.split(".title {", 1)[1].split("}", 1)[0]
    selected_title_rule = css.split(".news-item.selected .title {", 1)[1].split("}", 1)[0]
    detail_title_rule = css.split("#detailTitle {", 1)[1].split("}", 1)[0]
    summary_rule = css.split("\n.summary {", 1)[1].split("}", 1)[0]
    assert "-webkit-line-clamp: 5" in title_rule
    assert "-webkit-line-clamp: 5" in selected_title_rule
    assert "-webkit-line-clamp: 5" in detail_title_rule
    assert "-webkit-line-clamp: 3" in summary_rule
    assert "News Reader v2.1.4.2" in html
    assert "/static/style.css?v=2.1.4.2" in html
    assert "/static/app.js?v=2.1.4.2" in html


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


def test_market_workbench_pinned_notes(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-01.md").write_text(
        """## Reuters · World（1条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-01 09:00:00
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
    reuters_item = items[0]
    assert client.put(
        f"/api/news/{reuters_item['id']}/market-tag",
        json={"tag": "AI", "direction": "bullish"},
    ).status_code == 200

    overview = client.get("/api/market-workbench")
    assert overview.status_code == 200
    overview_payload = overview.get_json()
    assert overview_payload["pin"]["scope"] == "overview"
    assert overview_payload["pin"]["tag_key"] == ""
    assert overview_payload["pin"]["note"] == ""
    assert overview_payload["pin"]["collapsed"] == 0

    save_overview = client.put(
        "/api/market-workbench/pin",
        json={"tag_key": "", "note": "总置顶说明", "collapsed": True},
    )
    assert save_overview.status_code == 200
    save_overview_payload = save_overview.get_json()["pin"]
    assert save_overview_payload["scope"] == "overview"
    assert save_overview_payload["note"] == "总置顶说明"
    assert save_overview_payload["collapsed"] == 1

    overview_after = client.get("/api/market-workbench").get_json()
    assert overview_after["pin"]["note"] == "总置顶说明"
    assert overview_after["pin"]["collapsed"] == 1

    tag_view = client.get("/api/market-workbench?tag=AI")
    assert tag_view.status_code == 200
    tag_payload = tag_view.get_json()
    assert tag_payload["pin"]["scope"] == "tag"
    assert tag_payload["pin"]["tag_key"] == "AI"
    assert tag_payload["pin"]["tag_label"] == "AI"
    assert tag_payload["pin"]["note"] == ""

    save_tag = client.put(
        "/api/market-workbench/pin",
        json={"tag_key": "AI", "note": "AI 板块置顶", "collapsed": False},
    )
    assert save_tag.status_code == 200
    save_tag_payload = save_tag.get_json()["pin"]
    assert save_tag_payload["scope"] == "tag"
    assert save_tag_payload["tag_key"] == "AI"
    assert save_tag_payload["note"] == "AI 板块置顶"
    assert save_tag_payload["collapsed"] == 0

    tag_after = client.get("/api/market-workbench?tag=AI").get_json()
    assert tag_after["pin"]["note"] == "AI 板块置顶"
    assert tag_after["pin"]["collapsed"] == 0
    assert client.get("/api/market-workbench").get_json()["pin"]["note"] == "总置顶说明"

    clear_tag = client.put(
        "/api/market-workbench/pin",
        json={"tag_key": "AI", "note": "", "collapsed": True},
    )
    assert clear_tag.status_code == 200
    clear_tag_payload = clear_tag.get_json()["pin"]
    assert clear_tag_payload["note"] == ""
    assert clear_tag_payload["collapsed"] == 1

    invalid = client.put(
        "/api/market-workbench/pin",
        json={"tag_key": "NOT_FOUND", "note": "bad", "collapsed": False},
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_tag"


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


def test_market_tag_reorder_is_atomic_and_normalizes_after_delete_merge(tmp_path: Path, monkeypatch):
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

    first = client.post("/api/market-tags", json={"display_name": "第一自定义"}).get_json()["tag"]
    second = client.post("/api/market-tags", json={"display_name": "第二自定义"}).get_json()["tag"]
    initial_keys = [tag["key"] for tag in client.get("/api/market-tags").get_json()["tags"]]
    assert initial_keys[-2:] == [first["key"], second["key"]]

    reordered_keys = [second["key"], *[key for key in initial_keys if key != second["key"]]]
    reorder = client.post("/api/market-tags/reorder", json={"ordered_keys": reordered_keys})
    assert reorder.status_code == 200
    payload = reorder.get_json()
    assert [tag["key"] for tag in payload["tags"]] == reordered_keys
    assert [tag["sort_order"] for tag in payload["tags"]] == list(range(len(reordered_keys)))

    persisted_keys = [tag["key"] for tag in client.get("/api/market-tags").get_json()["tags"]]
    assert persisted_keys == reordered_keys

    def assert_rejected(body, error):
        before = [tag["key"] for tag in client.get("/api/market-tags").get_json()["tags"]]
        res = client.post("/api/market-tags/reorder", json=body)
        assert res.status_code == 400
        assert res.get_json()["error"] == error
        after = [tag["key"] for tag in client.get("/api/market-tags").get_json()["tags"]]
        assert after == before

    assert_rejected({"ordered_keys": [reordered_keys[0], reordered_keys[0], *reordered_keys[1:]]}, "duplicate_ordered_keys")
    assert_rejected({"ordered_keys": [*reordered_keys, "missing-key"]}, "unknown_ordered_keys")
    assert_rejected({"ordered_keys": reordered_keys[:-1]}, "missing_ordered_keys")

    delete_res = client.delete(f"/api/market-tags/{first['key']}")
    assert delete_res.status_code == 200
    tags_after_delete = delete_res.get_json()["tags"]
    assert all(tag["key"] != first["key"] for tag in tags_after_delete)
    assert [tag["sort_order"] for tag in tags_after_delete] == list(range(len(tags_after_delete)))

    third = client.post("/api/market-tags", json={"display_name": "第三自定义"}).get_json()["tag"]
    merge_res = client.post(f"/api/market-tags/{third['key']}/merge", json={"target_key": second["key"]})
    assert merge_res.status_code == 200
    tags_after_merge = merge_res.get_json()["tags"]
    assert all(tag["key"] != third["key"] for tag in tags_after_merge)
    assert [tag["sort_order"] for tag in tags_after_merge] == list(range(len(tags_after_merge)))


def test_market_tag_delete_removes_associations_and_blocks_default_reseed(tmp_path: Path, monkeypatch):
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
    note_res = client.put(
        "/api/market-trend-note",
        json={"date_key": "2026-06-02", "tag": "AI", "direction": "bullish", "note": "继续看多 AI"},
    )
    assert note_res.status_code == 200

    impact = client.get("/api/market-tags/AI/impact")
    assert impact.status_code == 200
    assert impact.get_json()["affected"] == {"item_tag_count": 1, "trend_note_count": 1}

    delete_res = client.delete("/api/market-tags/AI")
    assert delete_res.status_code == 200
    payload = delete_res.get_json()
    assert payload["deleted_tag"]["key"] == "AI"
    assert payload["affected"] == {"item_tag_count": 1, "trend_note_count": 1}
    assert all(tag["key"] != "AI" for tag in payload["tags"])

    detail_payload = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert all(tag["key"] != "AI" for tag in detail_payload["market_tags"])

    market_tags_payload = client.get("/api/news?collection=market_tags&per=20").get_json()
    assert market_tags_payload["items"] == []

    trend_payload = client.get("/api/market-trends?days=7").get_json()
    assert all(row["tag_key"] != "AI" for row in trend_payload["rows"])

    with app_module.db_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM article_market_tags WHERE tag='AI'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM market_trend_notes WHERE tag='AI'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM market_tag_deleted_keys WHERE key='AI'").fetchone()[0] == 1

    app_module.ensure_db()
    tags_after_reseed = client.get("/api/market-tags").get_json()["tags"]
    assert all(tag["key"] != "AI" for tag in tags_after_reseed)


def test_market_tag_merge_moves_links_and_notes_and_dedupes_urls(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（2条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-02 09:00:00
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

    create_res = client.post("/api/market-tags", json={"display_name": "人工智能"})
    assert create_res.status_code == 200
    source_key = create_res.get_json()["tag"]["key"]

    items = client.get("/api/news?per=20").get_json()["items"]
    item1 = next(item for item in items if item["title"] == "R1")
    item2 = next(item for item in items if item["title"] == "R2")
    assert client.put(f"/api/news/{item1['id']}/market-tag", json={"tag": source_key, "direction": "bullish"}).status_code == 200
    assert client.put(f"/api/news/{item1['id']}/market-tag", json={"tag": "AI", "direction": "bearish"}).status_code == 200
    assert client.put(f"/api/news/{item2['id']}/market-tag", json={"tag": source_key, "direction": "bullish"}).status_code == 200
    assert client.put(
        "/api/market-trend-note",
        json={"date_key": "2026-06-02", "tag": source_key, "direction": "bullish", "note": "AI 主线继续强化"},
    ).status_code == 200

    merge_res = client.post(f"/api/market-tags/{source_key}/merge", json={"target_key": "AI"})
    assert merge_res.status_code == 200
    payload = merge_res.get_json()
    assert payload["moved_item_tag_count"] == 1
    assert payload["skipped_duplicate_item_tag_count"] == 1
    assert payload["moved_trend_note_count"] == 1
    assert all(tag["key"] != source_key for tag in payload["tags"])

    detail1 = client.get(f"/api/news/{item1['id']}/detail").get_json()
    item1_ai_tags = [tag for tag in detail1["market_tags"] if tag["key"] == "AI"]
    assert len(item1_ai_tags) == 1
    assert item1_ai_tags[0]["direction"] == "bearish"

    detail2 = client.get(f"/api/news/{item2['id']}/detail").get_json()
    item2_ai_tags = [tag for tag in detail2["market_tags"] if tag["key"] == "AI"]
    assert len(item2_ai_tags) == 1
    assert item2_ai_tags[0]["direction"] == "bullish"

    tag_detail = client.get("/api/market-trends/tag-detail?tag=AI").get_json()
    assert tag_detail["ok"] is True
    assert tag_detail["tag_key"] == "AI"
    assert any(note["tag_key"] == "AI" for note in tag_detail["trend_notes"])

    with app_module.db_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM market_tag_definitions WHERE key=?", (source_key,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM article_market_tags WHERE tag=?", (source_key,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM market_trend_notes WHERE tag=?", (source_key,)).fetchone()[0] == 0


def test_market_tag_merge_errors(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text("", encoding="utf-8")
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    same_res = client.post("/api/market-tags/AI/merge", json={"target_key": "AI"})
    assert same_res.status_code == 400
    assert same_res.get_json()["error"] == "same_source_target"

    missing_target = client.post("/api/market-tags/AI/merge", json={"target_key": "missing"})
    assert missing_target.status_code == 404
    assert missing_target.get_json()["error"] == "target_tag_not_found"

    missing_source = client.post("/api/market-tags/missing/merge", json={"target_key": "AI"})
    assert missing_source.status_code == 404
    assert missing_source.get_json()["error"] == "tag_not_found"


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


def test_market_workbench_overview_and_tag_feed(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-03.md").write_text(
        """## Reuters · World（3条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：2026-06-03 09:00:00
### [R2](https://www.reuters.com/world/r2)
- 发布时间：2026-06-02 10:00:00
### [R3](https://www.reuters.com/world/r3)
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
    r3 = next(x for x in items if x["title"] == "R3")

    assert client.put(f"/api/news/{r1['id']}/market-tag", json={"tag": "AI", "direction": "bullish"}).status_code == 200
    assert client.put(f"/api/news/{r2['id']}/market-tag", json={"tag": "AI", "direction": "bearish"}).status_code == 200
    assert client.put(f"/api/news/{r2['id']}/note", json={"note": "这条属于我的板块想法"}).status_code == 200
    assert client.put(f"/api/news/{r3['id']}/market-tag", json={"tag": "存储", "direction": "bullish"}).status_code == 200
    assert client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-03", "tag_key": "AI", "direction": "bullish", "note": "独立看多 AI"},
    ).status_code == 200

    overview = client.get("/api/market-workbench?content_filter=all&per=20")
    assert overview.status_code == 200
    overview_payload = overview.get_json()
    assert overview_payload["mode"] == "all"
    assert overview_payload["tags"]
    assert [item["entry_type"] for item in overview_payload["items"]] == ["trend_note", "news", "news", "news"]
    assert overview_payload["items"][0]["idea_type"] == "trend_note"
    assert [item["title"] for item in overview_payload["items"][1:]] == ["R1", "R2", "R3"]

    overview_ideas = client.get("/api/market-workbench?content_filter=ideas&per=20").get_json()
    assert [item["entry_type"] for item in overview_ideas["items"]] == ["trend_note", "news"]
    assert overview_ideas["items"][1]["title"] == "R2"

    overview_bullish = client.get("/api/market-workbench?content_filter=bullish&per=20").get_json()
    assert [item["entry_type"] for item in overview_bullish["items"]] == ["trend_note", "news", "news"]
    assert [item["title"] for item in overview_bullish["items"][1:]] == ["R1", "R3"]

    overview_bearish = client.get("/api/market-workbench?content_filter=bearish&per=20").get_json()
    assert [item["entry_type"] for item in overview_bearish["items"]] == ["news"]
    assert overview_bearish["items"][0]["title"] == "R2"

    tag_feed = client.get("/api/market-workbench?tag=AI&content_filter=all&per=20")
    assert tag_feed.status_code == 200
    tag_payload = tag_feed.get_json()
    assert tag_payload["mode"] == "tag"
    assert tag_payload["selected_tag"]["key"] == "AI"
    assert [item["entry_type"] for item in tag_payload["items"]] == ["trend_note", "news", "news"]
    assert tag_payload["items"][0]["idea_type"] == "trend_note"
    assert tag_payload["items"][1]["title"] == "R1"
    assert tag_payload["items"][2]["title"] == "R2"

    ideas_only = client.get("/api/market-workbench?tag=AI&content_filter=ideas&per=20").get_json()
    assert [item["entry_type"] for item in ideas_only["items"]] == ["trend_note", "news"]
    assert ideas_only["items"][1]["title"] == "R2"

    bullish_only = client.get("/api/market-workbench?tag=AI&content_filter=bullish&per=20").get_json()
    assert [item["entry_type"] for item in bullish_only["items"]] == ["trend_note", "news"]
    assert bullish_only["items"][1]["title"] == "R1"

    bearish_only = client.get("/api/market-workbench?tag=AI&content_filter=bearish&per=20").get_json()
    assert [item["entry_type"] for item in bearish_only["items"]] == ["news"]
    assert bearish_only["items"][0]["title"] == "R2"


def test_market_tag_summary_generate_and_stale(tmp_path: Path, monkeypatch):
    today = datetime.now().date()
    day_one = today - timedelta(days=2)
    day_two = today - timedelta(days=3)
    daily_dir = tmp_path / "DailyNews" / f"{day_one.year}年{day_one.month}月"
    daily_dir.mkdir(parents=True)
    (daily_dir / f"dailyFreshNews_{day_one:%Y-%m-%d}.md").write_text(
        f"""## Reuters · World（2条）
### [R1](https://www.reuters.com/world/r1)
- 发布时间：{day_one:%Y-%m-%d} 09:00:00
- 摘要：AI 继续上涨
### [R2](https://www.reuters.com/world/r2)
- 发布时间：{day_two:%Y-%m-%d} 10:00:00
- 摘要：算力继续扩张
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
    assert client.put(f"/api/news/{r1['id']}/market-tag", json={"tag": "AI", "direction": "bullish"}).status_code == 200
    assert client.put(f"/api/news/{r2['id']}/market-tag", json={"tag": "AI", "direction": "bearish"}).status_code == 200
    assert client.put(f"/api/news/{r1['id']}/note", json={"note": "我倾向继续关注主线"}).status_code == 200
    assert client.put(
        "/api/market-trends/note",
        json={"date_key": day_one.strftime("%Y-%m-%d"), "tag_key": "AI", "direction": "bullish", "note": "独立趋势判断"},
    ).status_code == 200

    captured = {}

    def fake_summary(**kwargs):
        captured.update(kwargs)
        return {
            "model": "deepseek-chat",
            "summary_text": "新闻事实：AI 与算力链维持强势。用户想法：继续围绕主线观察，但要区分判断与事实。",
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_market_tag_summary", fake_summary)

    missing = client.get("/api/market-tags/AI/summary")
    assert missing.status_code == 200
    assert missing.get_json()["summary"]["status"] == "missing"

    generated = client.post("/api/market-tags/AI/summary/generate")
    assert generated.status_code == 200
    summary = generated.get_json()["summary"]
    assert summary["status"] == "success"
    assert "最近 30 天" in summary["scope_label"]
    assert "新闻事实" in summary["summary_text"]
    assert "用户想法" in summary["summary_text"]
    assert captured["range_days"] == 30
    assert captured["news_count"] == 2
    assert captured["note_count"] == 1
    assert "【新闻事实】" in captured["materials"]
    assert "【用户想法】" in captured["materials"]
    assert "方向：看多" in captured["materials"]
    assert "方向：看空" in captured["materials"]
    assert "对应新闻想法" in captured["materials"]

    stale_note = client.put(f"/api/news/{r2['id']}/note", json={"note": "补充一条新的新闻想法"})
    assert stale_note.status_code == 200

    stale = client.get("/api/market-tags/AI/summary")
    assert stale.status_code == 200
    assert stale.get_json()["summary"]["status"] == "stale"

    def fail_summary(**kwargs):
        raise app_module.LLMClientError("DEEPSEEK_CALL_FAILED: boom")

    monkeypatch.setattr(app_module, "generate_market_tag_summary", fail_summary)
    failed = client.post("/api/market-tags/AI/summary/generate")
    assert failed.status_code == 502
    failed_payload = failed.get_json()
    assert failed_payload["summary"]["status"] == "failed"
    assert "boom" in failed_payload["summary"]["error"]


def test_generate_pi_fallback_translation_layered(tmp_path: Path, monkeypatch):
    # generate_pi_fallback_translation 复用结构化/body-only/失败分层。
    import app as app_module
    import llm_client as llm

    def make_proc(stdout):
        class Completed:
            returncode = 0
            stderr = ""
        Completed.stdout = stdout
        return Completed()

    structured = (
        '{"type":"session","id":"s"}\n'
        '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"{\\"key_points_zh\\":[\\"一\\",\\"二\\",\\"三\\"],\\"conclusion_zh\\":\\"结论\\",\\"body_zh\\":\\"译文\\"}"}}\n'
        '{"type":"message_update","assistantMessageEvent":{"type":"text_end"}}\n'
    )
    monkeypatch.setattr(llm.subprocess, "run", lambda args, **kwargs: make_proc(structured))
    out = llm.generate_pi_fallback_translation(title="t", source="s", content="body", pi_provider="ollama", pi_model="minimax-m3:cloud")
    assert out["key_points_zh"] == ["一", "二", "三"]
    assert out["body_zh"] == "译文"
    assert "pi-fallback-structured" in out["raw_json"]

    # body-only：输出非 JSON 但含中文
    body_only = '{"type":"session","id":"s"}\n{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"这是一段中文译文，不是 JSON"}}\n{"type":"message_update","assistantMessageEvent":{"type":"text_end"}}\n'
    monkeypatch.setattr(llm.subprocess, "run", lambda args, **kwargs: make_proc(body_only))
    out2 = llm.generate_pi_fallback_translation(title="t", source="s", content="body", pi_provider="ollama", pi_model="minimax-m3:cloud")
    assert out2["body_zh"] == "这是一段中文译文，不是 JSON"
    assert out2["key_points_zh"] == []
    assert "pi-fallback-body-only" in out2["raw_json"]

    # 完全失败：空输出
    monkeypatch.setattr(llm.subprocess, "run", lambda args, **kwargs: make_proc('{"type":"session","id":"s"}\n'))
    raised = False
    try:
        llm.generate_pi_fallback_translation(title="t", source="s", content="body", pi_provider="ollama", pi_model="minimax-m3:cloud")
    except llm.LLMClientError:
        raised = True
    assert raised, "空输出应抛 LLMClientError"

    # PI_PACKAGE_DIR 清理断言
    captured = {}

    def capture_run(args, **kwargs):
        captured["env"] = kwargs.get("env")
        return make_proc(structured)

    monkeypatch.setattr(llm.subprocess, "run", capture_run)
    llm.generate_pi_fallback_translation(title="t", source="s", content="body", pi_provider="ollama", pi_model="minimax-m3:cloud")
    assert captured["env"] is not None
    assert captured["env"].get("PI_PACKAGE_DIR") is None


def test_deepseek_failure_uses_pi_fallback_and_persists_result(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    stamp = "2026-06-04 17:00:00"
    with app_module.db_conn() as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(url, title, source, content, content_length, fetched_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("https://example.com/pi-fallback", "Fallback title", "Reuters", "English body", 12, stamp, stamp),
            )
            conn.execute(
                "INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at) VALUES (?, 'pending', 0, ?, ?)",
                ("https://example.com/pi-fallback", stamp, stamp),
            )

    def fail_primary(**kwargs):
        raise app_module.LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: bad json")

    fallback_called = {}

    def succeed_fallback(**kwargs):
        fallback_called.update(kwargs)
        return {
            "model": "minimax-m3:cloud",
            "key_points_zh": ["要点一", "要点二", "要点三"],
            "conclusion_zh": "兜底结论",
            "body_zh": "这是 Pi 兜底译文。",
            "raw_json": '{"provider":"pi-fallback-structured"}',
        }

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_pi_fallback_translation", succeed_fallback)
    assert app_module.process_pending_ai_once() is True

    with app_module.db_conn() as conn:
        ai_row = conn.execute(
            "SELECT model, body_zh, raw_json FROM article_ai WHERE url=?",
            ("https://example.com/pi-fallback",),
        ).fetchone()
        job_row = conn.execute(
            "SELECT status, last_error FROM ai_jobs WHERE url=?",
            ("https://example.com/pi-fallback",),
        ).fetchone()
    assert ai_row["model"] == "minimax-m3:cloud"
    assert ai_row["body_zh"] == "这是 Pi 兜底译文。"
    assert "pi-fallback-structured" in ai_row["raw_json"]
    assert job_row["status"] == "success"
    assert job_row["last_error"] is None
    assert fallback_called["pi_provider"] == "ollama"


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


def test_process_pending_jobs_once_twitter_success_and_comment_summary(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## X · Social（1条）
### [Tweet Update](https://x.com/example/status/123)
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
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        app_module.enqueue_detail_job(conn, item["id"], item["url"], "Twitter")
        conn.commit()

    def fake_twitter_detail(url):
        return (
            True,
            {
                "source": "Twitter/X",
                "title": "Tweet Update",
                "author": "alice",
                "published_at": "2026-06-11 09:00:00",
                "content": "【主推文】\n主推文内容\n\n【引用推文】\n引用内容\n\n【长文补充】\n长文内容\n\n【评论区观点】\n基于已抓取的 6 条评论总结：评论区主要围绕利好与估值分歧展开。",
                "content_length": 120,
                "raw_json": json.dumps(
                    {
                        "tweet": {"text": "主推文内容"},
                        "quoted_tweet": {"text": "引用内容"},
                        "article": {"content": "长文内容"},
                        "comments": [{"text": f"评论 {i}"} for i in range(6)],
                    },
                    ensure_ascii=False,
                ),
            },
            "",
        )

    monkeypatch.setattr(app_module, "run_opencli_twitter_detail", fake_twitter_detail)
    assert app_module.process_pending_jobs_once() is True

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["detail_status"] == "success"
    assert detail["detail"]["content"].count("【主推文】") == 1
    assert "基于已抓取的 6 条评论总结" in detail["detail"]["content"]
    assert detail["ai_status"] == "none"


def test_process_pending_jobs_once_twitter_article_failure_does_not_fail_detail(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## X · Social（1条）
### [Tweet Update](https://x.com/example/status/123)
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
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        app_module.enqueue_detail_job(conn, item["id"], item["url"], "Twitter")
        conn.commit()

    def fake_twitter_detail(url):
        return (
            True,
            {
                "source": "Twitter/X",
                "title": "Tweet Update",
                "author": "alice",
                "published_at": "2026-06-11 09:00:00",
                "content": "【主推文】\n主推文内容\n\n【评论区观点】\n评论区观点总结失败，以下仅展示已抓取评论样本（共 6 条）。",
                "content_length": 80,
                "raw_json": json.dumps(
                    {
                        "tweet": {"text": "主推文内容"},
                        "article_error": "Article not found",
                        "comment_summary_error": "MISSING_DEEPSEEK_API_KEY",
                        "comments": [{"text": f"评论 {i}"} for i in range(6)],
                    },
                    ensure_ascii=False,
                ),
            },
            "",
        )

    monkeypatch.setattr(app_module, "run_opencli_twitter_detail", fake_twitter_detail)
    assert app_module.process_pending_jobs_once() is True

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["detail_status"] == "success"
    assert "评论区观点总结失败" in detail["detail"]["content"]


def test_run_opencli_twitter_detail_parses_list_thread_payload(monkeypatch):
    import app as app_module

    thread_payload = [
        {
            "id": "tweet-1",
            "author": "alice",
            "text": "主推文内容比较完整，足够通过正文长度校验。",
            "quoted_tweet": {"text": "引用内容"},
            "created_at": "2026-06-11 09:00:00",
        },
        {"id": "reply-1", "author": "bob", "text": "评论一"},
        {"id": "reply-2", "author": "carol", "text": "评论二"},
    ]
    article_payload = {"content": "长文内容"}

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return True, article_payload, ""

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)
    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    assert "【评论区观点】" in detail["content"]
    assert "评论一" in detail["content"]
    assert "评论二" in detail["content"]


def test_run_opencli_twitter_detail_includes_zero_comment_notice(monkeypatch):
    import app as app_module

    thread_payload = [
        {
            "id": "tweet-1",
            "author": "alice",
            "text": "主推文内容比较完整，足够通过正文长度校验。",
            "created_at": "2026-06-11 09:00:00",
        }
    ]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)
    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    assert "【评论区观点】" in detail["content"]
    assert "opencli thread 本次返回 0 条评论" in detail["content"]
    payload = json.loads(detail["raw_json"])
    assert payload["comment_count"] == 0


def test_run_opencli_twitter_detail_deduplicates_summary_prefix(monkeypatch):
    import app as app_module

    thread_payload = [
        {
            "id": "tweet-1",
            "author": "alice",
            "text": "主推文内容比较完整，足够通过正文长度校验。",
            "created_at": "2026-06-11 09:00:00",
        },
        *({"id": f"reply-{i}", "author": "bob", "text": f"评论 {i}"} for i in range(6)),
    ]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    def fake_summary(**kwargs):
        count = kwargs["comment_count"]
        return {
            "model": "deepseek-chat",
            "summary_text": f"基于已抓取的 {count} 条评论总结：评论区主要围绕利好与估值分歧展开。",
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)
    monkeypatch.setattr(app_module, "generate_twitter_comments_summary", fake_summary)
    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    assert detail["content"].count("基于已抓取的 6 条评论总结：") == 1


def test_process_pending_ai_once_twitter_generates_body_only(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## X · Social（1条）
### [Tweet Update](https://x.com/example/status/123)
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
    ts = app_module.now_ts()
    with app_module.db_conn() as conn:
        conn.execute("UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?", ("Twitter", "Twitter", "twitter", item["id"]))
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, 'Twitter/X', 'Tweet Update', 'alice', '2026-06-11 09:00:00', ?, ?, '{}', ?, ?)
            """,
            (item["url"], "【主推文】\n主推文内容", len("【主推文】\n主推文内容"), ts, ts),
        )
        conn.execute(
            """
            INSERT INTO ai_jobs(url, status, attempts, queued_at, updated_at)
            VALUES (?, 'pending', 0, ?, ?)
            """,
            (item["url"], ts, ts),
        )
        conn.commit()

    def fake_generate_body_translation_only(**kwargs):
        return {
            "model": "deepseek-chat",
            "key_points_zh": [],
            "conclusion_zh": "",
            "body_zh": "这是推文中文翻译。",
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_body_translation_only", fake_generate_body_translation_only)
    assert app_module.process_pending_ai_once() is True

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["ai_status"] == "success"
    assert detail["ai"]["body_zh"] == "这是推文中文翻译。"
    assert detail["ai"]["key_points_zh"] == "[]"
    assert detail["ai"]["conclusion_zh"] == ""


def test_row_title_text_truncates_twitter_titles():
    path = Path("/Users/x/news-reader/news-reader/static/app.js")
    source = path.read_text(encoding="utf-8")
    assert "const TITLE_CHAR_LIMIT = 100" in source
    assert "function rowTitleText(item)" in source
    assert "item?.source_type === \"twitter\"" in source
    assert "return truncateTitleText(title)" in source
    assert "document.getElementById(\"detailTitle\").textContent = rowTitleText(item)" in source


def test_frontend_uses_stable_source_identity_for_icons_and_detail_layout():
    path = Path("/Users/x/news-reader/news-reader/static/app.js")
    source = path.read_text(encoding="utf-8")
    assert "function sourceIconKey(item)" in source
    assert "canonicalSourceIconKey(item?.source_type)" in source
    assert "canonicalSourceIconKey(item?.source_name)" in source
    assert "sourceIconKeyFromUrl(item?.url)" in source
    assert "sourceIconMap[sourceIconKey(item)]" in source
    assert "const hasSummary = !hasDetailContent" in source
    assert "function setDetailReminderCardExpanded(expanded)" in source


def test_frontend_keeps_failures_near_the_affected_workflow():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")

    assert "function setInlineFeedback(container, message, options = {})" in app_source
    assert "function showStatePatchError(itemId, payload)" in app_source
    assert 'actionLabel: "重试"' in app_source
    assert 'tone === "failed" ? "alert" : "status"' in app_source
    assert "当前输入已保留，请稍后重试。" in app_source
    assert ".inline-feedback.failed" in style_source
    assert ".row-inline-feedback" in style_source
    assert ".detail-action-feedback" in style_source


def test_frontend_feed_source_visibility_uses_debounced_save_and_close_refresh():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")

    assert "const FEED_SOURCE_SAVE_DEBOUNCE_MS = 400;" in app_source
    assert "scheduleFeedSourceVisibilitySave();" in app_source
    assert "const nextHiddenSnapshot = Array.from(nextHidden);" in app_source
    assert "syncRuntimeFeedHiddenSourceSubkeys(nextHiddenSnapshot);" in app_source
    assert "feedSourceHiddenKey(nextHiddenSnapshot)" in app_source
    assert "await flushFeedSourceVisibilitySave({ force: true })" in app_source
    assert "await refreshFeedSourceVisibilityAfterClose()" in app_source
    assert "信源设置已保存，关闭设置后刷新新闻流。" in app_source
    assert "信源设置保存失败，已恢复原状态。" in app_source
    assert "await loadSources();" not in app_source
    assert "await refreshNavSummary().catch(() => {});" not in app_source.split("async function startFeedSourceVisibilitySave", 1)[1].split("async function openSettingsOverlay", 1)[0]
    assert "window.confirm(`恢复显示“${label}”？将重新显示 ${unread} 条未读新闻。`)" not in app_source
    assert "settingsFeedSourceSaveBtn" not in index_source
    assert "保存信源设置" not in index_source


def test_frontend_is_v2120_without_later_visual_experiments():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")
    review_styles = style_source.split("/* ===== Review (复盘) styles ===== */", 1)[1]

    assert "News Reader v2.1.4.2" in app_source
    assert "News Reader v2.1.4.2" in index_source
    assert "/static/style.css?v=2.1.4.2" in index_source
    assert "/static/app.js?v=2.1.4.2" in index_source
    assert 'id="navFeedBadge"' in index_source
    assert 'id="navReadLaterBadge"' in index_source
    assert 'id="navReviewsBadge"' in index_source
    assert '.news-item[data-read="1"] .title:not(.tone-important):not(.tone-bullish):not(.tone-bearish):not(.tone-mixed)' in style_source
    assert 'state.collection === "tracked" ||' in app_source
    assert 'state.collection !== "reviews" && state.collection !== "tracked"' in app_source
    assert 'function reorderMarketTagDefinitions(orderedKeys)' in app_source
    assert 'className = "detail-tag-admin-order-btn"' in app_source
    assert 'function resetList({ preserveTagAdmin = false } = {})' in app_source
    assert 'const preserveTagAdminView = preserveTagAdmin && state.tagAdminOpen' in app_source
    assert 'refreshMarketWorkbenchAfterTrendCompose({ preserveTagAdmin: true })' in app_source
    assert 'function startMarketTagDrag(event, tagKey)' in app_source
    assert 'function finishMarketTagDrag(event)' in app_source
    assert 'gridTemplateColumns' in app_source
    assert 'dropPosition' in app_source
    assert '放到此板块前' in app_source
    assert '放到此板块后' in app_source
    assert 'detail-tag-admin-drop-indicator' in app_source
    assert 'detail-tag-admin-drag-handle' in app_source
    assert 'touch-action: none' in style_source
    assert '.detail-tag-admin-drop-indicator' in style_source
    assert "v2.1.0.10" not in app_source
    assert "v2.1.0.10" not in index_source
    assert "--navigation-surface" not in style_source
    assert "--toolbar-surface" not in style_source
    assert "--liquid-glass-" not in style_source
    assert "--desktop-liquid-" not in style_source
    assert "Desktop light preview" not in style_source
    assert "--review-tone" not in review_styles
    assert "--review-result-tone" not in review_styles
    assert "text-transform: uppercase" in review_styles


def test_frontend_syncs_feed_rhythm_tuning_across_themes_and_devices():
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")

    assert "margin: 0 var(--space-5) var(--space-3)" in style_source
    assert "margin: var(--space-2) 0 var(--space-1)" in style_source
    assert "font-weight: 600" in style_source
    assert "Phase 2: desktop-light feed rhythm only" not in style_source
    assert "margin: 6px 10px 8px" not in style_source


def test_frontend_keeps_daily_metadata_groups_readable_on_narrow_layouts():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")

    assert "function renderDailyMetadata(container, briefing = {}, { includeDate = false, fallbackText = \"\" } = {})" in app_source
    assert 'renderDailyMetadata(summary, item, { includeDate: false, fallbackText: "无额外元数据" })' in app_source
    assert "renderDailyMetadata(detailDailyMeta, briefing, { includeDate: true })" in app_source
    assert ".daily-meta-pair" in style_source
    assert "white-space: nowrap" in style_source
    assert ".daily-meta-fallback" in style_source
    assert ".daily-briefing-row .summary .daily-meta-separator" in style_source
    assert ".detail-daily-body .detail-meta .daily-meta-separator" in style_source
    assert "part.dataset.dailyMetaKey = fragment.key" in app_source
    assert '.daily-meta-pair[data-daily-meta-key="执行时间"]' in style_source
    assert '.daily-meta-pair[data-daily-meta-key="使用文件"]' in style_source


def test_frontend_separates_visible_feed_action_groups_without_changing_targets():
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")

    assert ".feed-toolbar-action-group:has(> :not(.hidden)) + .feed-toolbar-action-group:has(> :not(.hidden))" in style_source
    assert "left: calc(-1 * var(--space-2))" in style_source
    assert "width: 1px" in style_source
    assert "background: var(--hairline)" in style_source
    assert 'aria-label="阅读与排序"' in index_source
    assert 'aria-label="批量与维护"' in index_source
    assert "width: 32px" in style_source


def test_detail_empty_state_is_compact_and_keeps_collection_context():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")
    empty_style = style_source.split(".detail-empty {", 1)[1].split("}", 1)[0]

    assert 'id="detailEmptyIcon"' in index_source
    assert 'id="detailEmptyTitle"' in index_source
    assert "详情与相关操作会显示在这里" in index_source
    assert 'if (name === "newspaper")' in app_source
    assert "if (detailEmptyTitle) detailEmptyTitle.textContent = message" in app_source
    assert "detailEmpty.textContent = message" not in app_source
    assert "min-height: 0" in empty_style
    assert "border: 0" in empty_style
    assert "background: transparent" in empty_style
    assert "1px dashed" not in empty_style
    assert "min-height: 178px" not in style_source
    assert ".detail-empty-icon svg" in style_source
    assert ".detail-empty-copy" in style_source


def test_settings_shell_uses_visible_labels_and_content_fitted_desktop_height():
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")

    assert '<h2 class="settings-title">设置</h2>' in index_source
    assert '<div class="settings-eyebrow">Settings</div>' not in index_source
    assert '<span class="settings-nav-label">服务</span>' in index_source
    assert '<span class="settings-nav-label">模型</span>' in index_source
    assert '<span class="settings-nav-label">更新</span>' in index_source
    assert 'aria-label="更新记录"' in index_source
    assert '<h3 class="settings-card-title">更新记录</h3>' in index_source
    assert ".settings-overlay {" in style_source
    assert "place-items: center" in style_source
    assert "width: min(1220px, calc(100vw - 48px))" in style_source
    assert "height: auto" in style_source
    assert "max-height: calc(100vh - 48px)" in style_source
    assert "grid-template-columns: 132px minmax(0, 1fr)" in style_source
    assert ".settings-nav-label {" in style_source
    assert ".settings-nav-icon" not in style_source
    assert "height: calc(100vh - 16px)" in style_source


def test_scrollbars_are_hidden_but_scrollable():
    path = Path("/Users/x/news-reader/news-reader/static/style.css")
    source = path.read_text(encoding="utf-8")
    assert "--scrollbar-thumb" in source
    assert "scrollbar-width: none" in source
    assert "-ms-overflow-style: none" in source
    assert "*::-webkit-scrollbar" in source
    assert "display: none" in source


def test_process_pending_jobs_once_twitter_success_does_not_enqueue_ai_job(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## X · Social（1条）
### [Tweet Update](https://x.com/example/status/123)
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
        conn.execute("UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?", ("Twitter", "Twitter", "twitter", item["id"]))
        app_module.enqueue_detail_job(conn, item["id"], item["url"], "Twitter")
        conn.commit()

    def fake_twitter_detail(url):
        return (
            True,
            {
                "source": "Twitter/X",
                "title": "Tweet Update",
                "author": "alice",
                "published_at": "2026-06-11 09:00:00",
                "content": "【主推文】\n主推文内容\n\n【评论区观点】\n未获取到评论；opencli thread 本次返回 0 条评论，可能是该推文无可见评论、登录态/权限限制或 X 分页未返回。",
                "content_length": 120,
                "raw_json": json.dumps({"tweet": {"text": "主推文内容"}, "comments": [], "comment_count": 0}, ensure_ascii=False),
            },
            "",
        )

    monkeypatch.setattr(app_module, "run_opencli_twitter_detail", fake_twitter_detail)
    assert app_module.process_pending_jobs_once() is True

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["detail_status"] == "success"
    assert detail["ai_status"] == "none"


def test_news_chat_archive_rejects_missing_assistant(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive Missing](https://example.com/chat-archive-missing)
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
        f"/api/news/{item['id']}/chat/archive",
        json={"messages": [{"role": "user", "content": "还没回答"}]},
    )
    assert res.status_code == 400
    assert res.get_json()["error"] == "empty_archive_source"


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

def test_feed_source_subkey_visibility_settings_only_filter_feed(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年7月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    ts = "2026-07-30 10:00:00"
    rows = [
        ("1", "manual.md", 1, "2026-07-30 09:00:00", "2026-07-30", "09:00", "Reuters · China", "rss", "Reuters", "China visible", "s", "https://www.reuters.com/world/china/visible", ts, ts),
        ("2", "manual.md", 2, "2026-07-30 09:01:00", "2026-07-30", "09:01", "Reuters · Middle East", "rss", "Reuters", "ME hidden", "s", "https://www.reuters.com/world/middle-east/hidden", ts, ts),
        ("3", "manual.md", 3, "2026-07-30 09:02:00", "2026-07-30", "09:02", "MacroMargin", "twitter", "X", "X hidden", "s", "https://x.com/MacroMargin/status/1", ts, ts),
        ("4", "manual.md", 4, "2026-07-30 09:03:00", "2026-07-30", "09:03", "Reuters · Middle East", "rss", "Reuters", "ME important", "s", "https://www.reuters.com/world/middle-east/important", ts, ts),
    ]
    conn = app_module.db_conn()
    try:
        with conn:
            conn.executemany(
                """
                INSERT INTO items(
                  id, source_file, item_order, published_at, date, time, source, source_type,
                  source_name, title, summary, url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.execute("INSERT INTO item_state(item_id, important_at, updated_at) VALUES (?, ?, ?)", ("4", ts, ts))
            conn.execute("INSERT INTO item_state(item_id, read_later_at, updated_at) VALUES (?, ?, ?)", ("2", ts, ts))
    finally:
        conn.close()

    settings = app_module.default_app_settings()
    settings["feed"]["hidden_source_subkeys"] = ["reuters/middle-east", "x/macromargin"]
    app_module.save_app_settings(settings)
    client = app_module.app.test_client()

    feed = client.get("/api/news?collection=feed&read_filter=all&per=10").get_json()
    assert feed["total"] == 1
    assert [item["id"] for item in feed["items"]] == ["1"]

    unread_feed = client.get("/api/news?collection=feed&read_filter=unread&per=10").get_json()
    assert unread_feed["total"] == 1
    assert unread_feed["date_counts"] == {"2026-07-30": 1}

    sources = client.get("/api/sources?collection=feed&read_filter=unread").get_json()["sources"]
    assert sources == [{"key": "reuters", "label": "Reuters", "count": 1}]

    important = client.get("/api/news?collection=important&read_filter=all&per=10").get_json()
    assert [item["id"] for item in important["items"]] == ["4"]

    read_later = client.get("/api/news?collection=read_later&read_filter=all&per=10").get_json()
    assert [item["id"] for item in read_later["items"]] == ["2"]

    settings_payload = client.get("/api/settings").get_json()
    assert settings_payload["feed"]["hidden_source_subkeys"] == ["reuters/middle-east", "x/macromargin"]
    groups = {group["source_key"]: group for group in settings_payload["feed_source_subkeys"]["groups"]}
    reuters_items = {item["key"]: item for item in groups["reuters"]["items"]}
    x_items = {item["key"]: item for item in groups["x"]["items"]}
    assert reuters_items["reuters/middle-east"]["hidden"] is True
    assert reuters_items["reuters/middle-east"]["unread_count"] == 2
    assert x_items["x/macromargin"]["label"] == "@MacroMargin"
    assert x_items["x/macromargin"]["hidden"] is True

    marked = client.post(
        "/api/news/mark-all-read",
        json={"collection": "feed", "read_filter": "unread", "source_filter": "all"},
    ).get_json()
    assert marked == {"ok": True, "marked": 1}
    conn = app_module.db_conn()
    try:
        states = {
            row["item_id"]: row["read_at"]
            for row in conn.execute("SELECT item_id, read_at FROM item_state WHERE item_id IN ('1','2','3','4')").fetchall()
        }
    finally:
        conn.close()
    assert states["1"]
    assert states["2"] is None
    assert "3" not in states or states["3"] is None
    assert states["4"] is None


def test_nav_summary_counts_use_independent_collection_semantics(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    ts = "2026-07-31 10:00:00"
    rows = [
        ("visible", "manual.md", 1, "2026-07-31 09:00:00", "2026-07-31", "09:00", "Reuters · China", "rss", "Reuters", "Visible unread", "s", "https://www.reuters.com/world/china/visible", ts, ts),
        ("hidden", "manual.md", 2, "2026-07-31 09:01:00", "2026-07-31", "09:01", "Reuters · Middle East", "rss", "Reuters", "Hidden unread", "s", "https://www.reuters.com/world/middle-east/hidden", ts, ts),
        ("read", "manual.md", 3, "2026-07-31 09:02:00", "2026-07-31", "09:02", "Reuters · China", "rss", "Reuters", "Read feed item", "s", "https://www.reuters.com/world/china/read", ts, ts),
        ("later", "manual.md", 4, "2026-07-31 09:03:00", "2026-07-31", "09:03", "Reuters · China", "rss", "Reuters", "Read later queue", "s", "https://www.reuters.com/world/china/later", ts, ts),
    ]
    conn = app_module.db_conn()
    try:
        with conn:
            conn.executemany(
                """
                INSERT INTO items(
                  id, source_file, item_order, published_at, date, time, source, source_type,
                  source_name, title, summary, url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.execute("INSERT INTO item_state(item_id, read_at, updated_at) VALUES (?, ?, ?)", ("read", ts, ts))
            conn.execute(
                "INSERT INTO item_state(item_id, read_at, read_later_at, updated_at) VALUES (?, ?, ?, ?)",
                ("later", ts, ts, ts),
            )
    finally:
        conn.close()

    settings = app_module.default_app_settings()
    settings["feed"]["hidden_source_subkeys"] = ["reuters/middle-east"]
    app_module.save_app_settings(settings)
    client = app_module.app.test_client()

    idea_id = _create_standalone_idea(client, "待复盘角标想法")
    pending = client.post("/api/reviews", json={
        "source_type": "standalone_idea",
        "source_key": str(idea_id),
        "judgment": "到期判断",
        "plan_review_date": "2020-01-01",
    })
    assert pending.status_code == 200
    pending_id = pending.get_json()["review"]["id"]
    future_idea_id = _create_standalone_idea(client, "未来复盘想法")
    future = client.post("/api/reviews", json={
        "source_type": "standalone_idea",
        "source_key": str(future_idea_id),
        "judgment": "未来判断",
        "plan_review_date": "2099-01-01",
    })
    assert future.status_code == 200

    summary = client.get("/api/nav-summary")
    assert summary.status_code == 200
    assert summary.get_json()["summary"] == {
        "feed_unread": 1,
        "read_later_unread": 1,
        "pending_review": 1,
    }

    settings["feed"]["hidden_source_subkeys"] = []
    app_module.save_app_settings(settings)
    restored = client.get("/api/nav-summary").get_json()["summary"]
    assert restored["feed_unread"] == 2
    assert restored["read_later_unread"] == 1

    removed = client.patch("/api/news/later/state", json={"read_later": False})
    assert removed.status_code == 200
    after_later_done = client.get("/api/nav-summary").get_json()["summary"]
    assert after_later_done["read_later_unread"] == 0

    completed = client.post(f"/api/reviews/{pending_id}/complete", json={
        "result": "confirmed",
        "actual_text": "事实",
        "experience": "经验",
    })
    assert completed.status_code == 200
    assert client.get("/api/nav-summary").get_json()["summary"]["pending_review"] == 0


def test_feed_source_subkeys_use_collection_source_for_x_and_merge_bloomberg(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年7月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    ts = "2026-07-30 10:00:00"
    rows = [
        ("x1", "manual.md", 1, "2026-07-30 09:00:00", "2026-07-30", "09:00", "卡比卡比", "twitter", "卡比卡比", "Kabi retweeted external", "s", "https://x.com/aiandcloud/status/1", ts, ts),
        ("x2", "manual.md", 2, "2026-07-30 09:01:00", "2026-07-30", "09:01", "seekinganythingbutalpha", "twitter", "seekinganythingbutalpha", "Seeking quoted external", "s", "https://x.com/DonMiami3/status/1", ts, ts),
        ("x3", "manual.md", 3, "2026-07-30 09:02:00", "2026-07-30", "09:02", "ChinaMacroFacts", "other", "ChinaMacroFacts", "New handle source", "s", "https://x.com/ChinaMacroFacts/status/1", ts, ts),
        ("b1", "manual.md", 4, "2026-07-30 09:03:00", "2026-07-30", "09:03", "bloomberg_tech", "bloomberg", "Bloomberg", "Bloomberg sidecar tech", "s", "https://www.bloomberg.com/news/articles/1", ts, ts),
        ("b2", "manual.md", 5, "2026-07-30 09:04:00", "2026-07-30", "09:04", "Bloomberg · Tech", None, None, "Bloomberg display tech", "s", "https://www.bloomberg.com/news/articles/2", ts, ts),
        ("b3", "manual.md", 6, "2026-07-30 09:05:00", "2026-07-30", "09:05", "Bloomberg · Economics", None, None, "Bloomberg economics", "s", "https://www.bloomberg.com/news/articles/3", ts, ts),
    ]
    conn = app_module.db_conn()
    try:
        with conn:
            conn.executemany(
                """
                INSERT INTO items(
                  id, source_file, item_order, published_at, date, time, source, source_type,
                  source_name, title, summary, url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
    finally:
        conn.close()

    settings = app_module.default_app_settings()
    settings["feed"]["hidden_source_subkeys"] = ["x/aiandcloud", "bloomberg/bloomberg_tech"]
    app_module.save_app_settings(settings)
    client = app_module.app.test_client()

    settings_payload = client.get("/api/settings").get_json()
    assert settings_payload["feed"]["hidden_source_subkeys"] == ["x/aiandcloud", "bloomberg/tech"]
    assert settings_payload["feed_source_subkeys"]["hidden_source_subkeys"] == ["bloomberg/tech"]
    groups = {group["source_key"]: group for group in settings_payload["feed_source_subkeys"]["groups"]}
    x_items = {item["key"]: item for item in groups["x"]["items"]}
    assert set(x_items) == {"x/jakevin7", "x/ivanalog_com", "x/chinamacrofacts"}
    assert x_items["x/jakevin7"]["label"] == "卡比卡比 (@jakevin7)"
    assert x_items["x/ivanalog_com"]["label"] == "seekinganythingbutalpha (@ivanalog_com)"
    assert "x/aiandcloud" not in x_items
    assert "x/donmiami3" not in x_items
    bloomberg_items = {item["key"]: item for item in groups["bloomberg"]["items"]}
    assert bloomberg_items["bloomberg/tech"]["count"] == 2
    assert bloomberg_items["bloomberg/tech"]["hidden"] is True
    assert bloomberg_items["bloomberg/economics"]["count"] == 1

    feed = client.get("/api/news?collection=feed&read_filter=all&per=20").get_json()
    assert feed["total"] == 4
    assert {item["id"] for item in feed["items"]} == {"x1", "x2", "x3", "b3"}

    settings["feed"]["hidden_source_subkeys"] = ["x/jakevin7"]
    app_module.save_app_settings(settings)
    feed = client.get("/api/news?collection=feed&read_filter=all&per=20").get_json()
    assert feed["total"] == 5
    assert {item["id"] for item in feed["items"]} == {"x2", "x3", "b1", "b2", "b3"}



def test_feed_source_subkey_settings_roundtrip_normalizes_values(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年7月"
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

    res = client.put(
        "/api/settings",
        json={
            "llm": {
                "translation": {"provider": "deepseek", "model": ""},
                "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"},
            },
            "feed": {"hidden_source_subkeys": ["Reuters / Middle East", "x/MacroMargin", "Bloomberg / bloomberg_tech", "bad", "x/MacroMargin"]},
        },
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["feed"]["hidden_source_subkeys"] == ["reuters/middle-east", "x/macromargin", "bloomberg/tech"]
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["feed"]["hidden_source_subkeys"] == ["reuters/middle-east", "x/macromargin", "bloomberg/tech"]


def test_settings_tracked_default_rule_params_roundtrip_and_new_topic_defaults(tmp_path: Path, monkeypatch):
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

    save_res = client.put(
        "/api/settings/tracked-default-rule-params",
        json={
            "default_rule_params": {
                "title_weight": 1.8,
                "note_weight": 1.2,
                "summary_weight": 0.9,
                "content_weight": 0.5,
                "strong_score": 1.4,
                "core_score": 1.1,
                "context_score": 0.8,
                "exclude_penalty": 1.6,
                "threshold": 9,
            }
        },
    )
    assert save_res.status_code == 200
    saved = save_res.get_json()
    assert saved["tracked"]["default_rule_params"]["threshold"] == 9
    assert saved["tracked"]["default_rule_params"]["title_weight"] == 1.8
    saved_file = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved_file["tracked"]["default_rule_params"]["exclude_penalty"] == 1.6

    created = client.post(
        "/api/tracked-topics",
        json={
            "title": "默认参数测试",
            "core_terms": ["苹果"],
            "context_terms": ["财报"],
            "scope": "important",
            "active": True,
        },
    )
    assert created.status_code == 200
    rules = created.get_json()["topic"]["rules"]
    assert rules["threshold"] == 9
    assert rules["title_weight"] == 1.8
    assert rules["note_weight"] == 1.2
    assert rules["summary_weight"] == 0.9
    assert rules["content_weight"] == 0.5
    assert rules["strong_score"] == 1.4
    assert rules["core_score"] == 1.1
    assert rules["context_score"] == 0.8
    assert rules["exclude_penalty"] == 1.6

    reset_res = client.put(
        "/api/settings/tracked-default-rule-params",
        json={"default_rule_params": {"threshold": 6}},
    )
    assert reset_res.status_code == 200
    assert reset_res.get_json()["tracked"]["default_rule_params"]["threshold"] == 6


def test_settings_translation_resolved_default_model_respects_env(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("NEWS_READER_LLM_MODEL", "deepseek-v4-flash")

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: None)
    app_module.ensure_db()
    client = app_module.app.test_client()

    payload = client.get("/api/settings").get_json()
    assert payload["model_catalogs"]["translation"]["resolved_default_model"] == "deepseek-v4-flash"
    assert payload["model_catalogs"]["translation"]["default_label"] == "deepseek-v4-flash"
    assert payload["llm"]["translation"]["model"] == ""


def test_deepseek_model_catalog_fallback_keeps_saved_model(tmp_path: Path, monkeypatch):
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
    monkeypatch.setattr(app_module, "urlopen", lambda request, timeout=0: (_ for _ in ()).throw(app_module.HTTPError(app_module.DEEPSEEK_MODELS_URL, 503, "boom", None, None)))

    snapshot = app_module.deepseek_settings_snapshot("deepseek-custom-x")
    assert snapshot["service"]["configured"] is True
    assert snapshot["service"]["models_endpoint_reachable"] is False
    assert snapshot["service"]["used_fallback"] is True
    assert snapshot["service"]["last_error"] == "http_503"
    assert snapshot["catalog"]["source"] == "fallback"
    assert snapshot["catalog"]["options"][0]["value"] == "deepseek-v4-flash"
    assert snapshot["catalog"]["options"][-1]["value"] == "deepseek-custom-x"
    assert snapshot["catalog"]["options"][-1]["source"] == "saved"


def test_settings_are_pi_only_and_ignore_unknown_executor_fields(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "translation": {"provider": "deepseek", "model": "deepseek-saved"},
                    "legacy_chat": {"provider": "unused"},
                    "second_executor": {"model": "unused"},
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: None)
    app_module.ensure_db()
    client = app_module.app.test_client()

    initial = client.get("/api/settings").get_json()
    assert set(initial["llm"]) == {"translation", "pi_chat"}
    assert set(initial["api_status"]) == {"deepseek", "pi"}
    assert set(initial["model_catalogs"]) == {"translation", "pi_chat"}
    assert initial["llm"]["translation"]["model"] == "deepseek-saved"

    saved = client.put(
        "/api/settings",
        json={
            "llm": {
                "translation": {"provider": "deepseek", "model": "deepseek-new"},
                "pi_chat": {"provider": "ollama", "model": "qwen3.5:4b"},
                "legacy_chat": {"provider": "ignored"},
                "second_executor": {"model": "ignored"},
            }
        },
    )
    assert saved.status_code == 200
    payload = saved.get_json()
    assert set(payload["llm"]) == {"translation", "pi_chat"}
    persisted = json.loads(settings_path.read_text(encoding="utf-8"))
    assert set(persisted["llm"]) == {"translation", "pi_chat"}
    assert persisted["llm"]["pi_chat"] == {"provider": "ollama", "model": "qwen3.5:4b"}


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


def test_parse_pi_providers():
    import app as app_module

    stdout = (
        "provider  model              context  max-out  thinking  images\n"
        "deepseek  deepseek-v4-flash  1M       384K     yes       no\n"
        "deepseek  deepseek-v4-pro    1M       384K     yes       no\n"
        "ollama    minimax-m3:cloud   524.3K   16.4K    yes       yes\n"
        "ollama    qwen3.5:4b         262.1K   16.4K    yes       yes\n"
    )
    assert app_module.parse_pi_providers(stdout) == ["deepseek", "ollama"]
    assert app_module.parse_pi_providers("") == []
    assert app_module.parse_pi_providers("provider  model\n") == []


def test_parse_pi_model_catalog():
    import app as app_module

    stdout = (
        "provider  model              context  max-out  thinking  images\n"
        "deepseek  deepseek-v4-flash  1M       384K     yes       no\n"
        "deepseek  deepseek-v4-pro    1M       384K     yes       no\n"
        "deepseek  deepseek-v4-flash  1M       384K     yes       no\n"
        "\n"
        "ollama    minimax-m3:cloud   524.3K   16.4K    yes       yes\n"
        "ollama    minimax-m3:cloud   524.3K   16.4K    yes       yes\n"
        "broken-row\n"
        "ollama    qwen3.5:4b         262.1K   16.4K    yes       yes\n"
    )
    providers, grouped = app_module.parse_pi_model_catalog(stdout)
    assert providers == ["deepseek", "ollama"]
    assert grouped == {
        "deepseek": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "ollama": ["minimax-m3:cloud", "qwen3.5:4b"],
    }
    # 表头/空行/畸形行（不足两列）/空输出都安全跳过；两列以上的行取前两列。
    assert app_module.parse_pi_model_catalog("provider  model\n") == ([], {})
    assert app_module.parse_pi_model_catalog("") == ([], {})
    assert app_module.parse_pi_model_catalog("onlyprovider\n") == ([], {})
    providers_two, grouped_two = app_module.parse_pi_model_catalog("deepseek  deepseek-v4-pro  1M  384K  yes  no\n")
    assert providers_two == ["deepseek"]
    assert grouped_two == {"deepseek": ["deepseek-v4-pro"]}


def _fake_pi_subprocess(*, help_ok=True, models_stdout=None, models_ok=True):
    def _run(args, **kwargs):
        class Completed:
            pass

        if "--help" in args:
            Completed.returncode = 0 if help_ok else 1
            Completed.stdout = "pi help"
            Completed.stderr = "" if help_ok else "boom"
            return Completed()
        if "--list-models" in args:
            Completed.returncode = 0 if (models_ok and models_stdout is not None) else 1
            Completed.stdout = models_stdout or ""
            Completed.stderr = "" if models_ok else "boom"
            return Completed()
        Completed.returncode = 0
        Completed.stdout = ""
        Completed.stderr = ""
        return Completed()

    return _run


def test_pi_chat_settings_snapshot_detects_providers(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: "/opt/homebrew/bin/pi")
    monkeypatch.setattr(
        app_module.subprocess,
        "run",
        _fake_pi_subprocess(
            models_stdout=(
                "provider  model              context  max-out  thinking  images\n"
                "deepseek  deepseek-v4-flash  1M       384K     yes       no\n"
                "ollama    minimax-m3:cloud   524.3K   16.4K    yes       yes\n"
            )
        ),
    )
    snapshot = app_module.pi_chat_settings_snapshot("minimax-m3:cloud", "deepseek")
    catalog = snapshot["catalog"]
    assert catalog["saved_provider"] == "deepseek"
    assert catalog["resolved_default_provider"] == "ollama"
    provider_values = [opt["value"] for opt in catalog["provider_options"]]
    assert "deepseek" in provider_values and "ollama" in provider_values
    # 默认模型选项仍保留
    assert catalog["resolved_default_model"] == "minimax-m3:cloud"
    # 真实目录成功：source/used_fallback 准确反映 pi-list-models。
    assert catalog["source"] == "pi-list-models"
    assert snapshot["service"]["used_fallback"] is False
    grouped = catalog["model_options_by_provider"]
    # 已保存模型不在其保存 provider 的真实目录内时，只追加到保存 provider 组。
    assert [opt["value"] for opt in grouped["deepseek"]] == ["deepseek-v4-flash", "minimax-m3:cloud"]
    assert [opt["value"] for opt in grouped["ollama"]] == ["minimax-m3:cloud"]
    assert [opt["source"] for opt in grouped["deepseek"]][-1] == "saved"
    # 顶层兼容 options 为保存 provider 的分组（含已保存追加）。
    assert [opt["value"] for opt in catalog["options"]] == ["deepseek-v4-flash", "minimax-m3:cloud"]


def test_pi_chat_settings_snapshot_falls_back_and_keeps_saved_provider(tmp_path: Path, monkeypatch):
    # pi --list-models 失败时回退默认 ollama，且不丢已保存 provider。
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: "/opt/homebrew/bin/pi")
    monkeypatch.setattr(app_module.subprocess, "run", _fake_pi_subprocess(help_ok=True, models_stdout=None, models_ok=False))
    snapshot = app_module.pi_chat_settings_snapshot("minimax-m3:cloud", "custom-provider")
    provider_values = [opt["value"] for opt in snapshot["catalog"]["provider_options"]]
    # 回退默认 ollama + 已保存 custom-provider 被追加保留
    assert "ollama" in provider_values
    assert "custom-provider" in provider_values
    assert snapshot["catalog"]["saved_provider"] == "custom-provider"
    # 失败回退：source/used_fallback 准确，且无分组目录。
    assert snapshot["catalog"]["source"] == "fallback"
    assert snapshot["service"]["used_fallback"] is True
    assert snapshot["catalog"]["model_options_by_provider"] == {}
    option_values = [opt["value"] for opt in snapshot["catalog"]["options"]]
    assert option_values[0] == "minimax-m3:cloud"


def test_pi_chat_settings_snapshot_appends_saved_provider_not_detected(tmp_path: Path, monkeypatch):
    # 已保存 provider 不在检测列表时，追加到下拉并保留为当前选项。
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: "/opt/homebrew/bin/pi")
    monkeypatch.setattr(
        app_module.subprocess,
        "run",
        _fake_pi_subprocess(models_stdout="provider  model\nollama  minimax-m3:cloud  524K  16K  yes  yes\n"),
    )
    snapshot = app_module.pi_chat_settings_snapshot("minimax-m3:cloud", "deepseek")
    provider_values = [opt["value"] for opt in snapshot["catalog"]["provider_options"]]
    assert "ollama" in provider_values
    assert "deepseek" in provider_values  # saved 不在检测结果里，仍追加
    assert snapshot["catalog"]["saved_provider"] == "deepseek"
    # 已保存 provider 缺失时补组，且已保存模型只进自己的组；ollama 组不被污染。
    grouped = snapshot["catalog"]["model_options_by_provider"]
    assert [opt["value"] for opt in grouped["deepseek"]] == ["minimax-m3:cloud"]
    assert grouped["deepseek"][-1]["source"] == "saved"
    assert [opt["value"] for opt in grouped["ollama"]] == ["minimax-m3:cloud"]


def test_pi_chat_settings_snapshot_keeps_saved_model_in_real_group_without_duplicate(tmp_path: Path, monkeypatch):
    # 已保存 provider/model 都在真实目录内：不重复追加，options 即真实分组。
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: "/opt/homebrew/bin/pi")
    monkeypatch.setattr(
        app_module.subprocess,
        "run",
        _fake_pi_subprocess(
            models_stdout=(
                "provider  model              context  max-out  thinking  images\n"
                "deepseek  deepseek-v4-flash  1M       384K     yes       no\n"
                "deepseek  deepseek-v4-pro    1M       384K     yes       no\n"
            )
        ),
    )
    snapshot = app_module.pi_chat_settings_snapshot("deepseek-v4-pro", "deepseek")
    catalog = snapshot["catalog"]
    grouped = catalog["model_options_by_provider"]
    values = [opt["value"] for opt in grouped["deepseek"]]
    assert values == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert all(opt["source"] == "pi-list-models" for opt in grouped["deepseek"])
    assert [opt["value"] for opt in catalog["options"]] == values


def test_frontend_pi_chat_provider_model_linkage_contract():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")

    # 切换 Pi provider 时即时重建模型下拉。
    assert "function syncPiChatModelSelectForProvider()" in app_source
    listener_block = app_source.split("if (settingsPiChatProviderSelect) {", 1)[1].split("}", 1)[0]
    assert "syncPiChatModelSelectForProvider();" in listener_block
    # 联动读取按 provider 分组的真实目录，并保留当前/已保存值或选首个候选；自定义输入入口保留。
    assert "catalog.model_options_by_provider" in app_source
    assert "const belongs = !!currentModel && options.some((opt) => (opt?.value || \"\").trim() === currentModel);" in app_source
    assert "const nextValue = belongs ? currentModel : ((options[0]?.value || \"\").trim());" in app_source
    assert "SETTINGS_CUSTOM_MODEL_VALUE" in app_source
    # 回归：真实目录成功时未知/自定义 provider 不得回退到已保存 provider 的 catalog.options（跨组串组）。
    assert "const hasRealCatalog = Object.keys(grouped).length > 0;" in app_source
    assert "const options = hasGroup ? groupValues : (hasRealCatalog ? [] : fallbackOptions);" in app_source
    assert "const options = hasGroup ? groupValues : fallbackOptions;" not in app_source
    # 不混入 ollama list。
    assert "ollama list" not in app_source


def test_frontend_settings_expose_translation_and_pi_only():
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    legacy_model_id = "settings" + "LegacyChatModelSelect"
    assert 'id="settingsPiChatProviderSelect"' in index_source
    assert 'id="settingsPiChatModelSelect"' in index_source
    assert 'id="settingsChatProviderSelect"' not in index_source
    assert f'id="{legacy_model_id}"' not in index_source
    assert "chat_providers" not in app_source
    assert "settingsChatProviderSelect" not in app_source
    assert legacy_model_id not in app_source


def test_parse_pi_stdout_success_text_delta():
    import app as app_module

    stdout = (
        '{"type":"session","id":"pi-session-1"}\n'
        '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"你好"}}\n'
        '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"世界"}}\n'
        '{"type":"message_update","assistantMessageEvent":{"type":"text_end","content":"你好世界"}}\n'
    )
    session_id, answer, has_error, error_message = app_module._parse_pi_stdout(stdout)
    assert session_id == "pi-session-1"
    assert answer == "你好世界"
    assert has_error is False
    assert error_message == ""


def test_parse_pi_stdout_falls_back_to_message_end():
    import app as app_module

    stdout = (
        '{"type":"session","id":"pi-session-2"}\n'
        '{"type":"message_end","message":{"content":[{"type":"text","text":"fallback"}]}}\n'
    )
    session_id, answer, has_error, error_message = app_module._parse_pi_stdout(stdout)
    assert session_id == "pi-session-2"
    assert answer == "fallback"
    assert has_error is False


def test_parse_pi_stdout_detects_auto_retry_failure():
    import app as app_module

    stdout = (
        '{"type":"session","id":"pi-session-3"}\n'
        '{"type":"auto_retry_end","success":false,"finalError":"rate limit"}\n'
    )
    _, _, has_error, error_message = app_module._parse_pi_stdout(stdout)
    assert has_error is True
    assert "rate limit" in error_message


def test_parse_pi_stdout_detects_will_retry():
    import app as app_module

    stdout = '{"type":"agent_end","willRetry":true}\n'
    _, _, has_error, error_message = app_module._parse_pi_stdout(stdout)
    assert has_error is True
    assert error_message == "pi_will_retry"


def test_run_pi_chat_success(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env")
        class Completed:
            returncode = 0
            stdout = (
                '{"type":"session","id":"pi-session-run"}\n'
                '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"Pi 回答"}}\n'
                '{"type":"message_update","assistantMessageEvent":{"type":"text_end"}}\n'
            )
            stderr = ""
        return Completed()

    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    result = app_module.run_pi_chat(
        item_id="item-1",
        question="怎么看？",
        title="News",
        source="Reuters",
        published_at="2026-06-11",
        content="body",
        context_level="full_detail",
        pi_provider="ollama",
        pi_model="minimax-m3:cloud",
    )
    assert result["provider"] == "pi"
    assert result["session_id"] == "pi-session-run"
    assert result["model"] == "minimax-m3:cloud"
    assert result["answer"] == "Pi 回答"
    assert captured["env"] is not None
    assert captured["env"].get("PI_PACKAGE_DIR") is None
    assert "--provider" in captured["args"] and "ollama" in captured["args"]
    assert "--model" in captured["args"] and "minimax-m3:cloud" in captured["args"]


def test_run_pi_chat_archive_success(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env")

        class Completed:
            returncode = 0
            stdout = (
                '{"type":"session","id":"archive-session"}\n'
                '{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"归档结论"}}\n'
                '{"type":"message_update","assistantMessageEvent":{"type":"text_end"}}\n'
            )
            stderr = ""
        return Completed()

    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    result = app_module.run_pi_chat_archive(
        title="News",
        source="Reuters",
        published_at="2026-06-11",
        messages=[{"role": "user", "content": "总结"}, {"role": "assistant", "content": "结论"}],
        pi_provider="ollama",
        pi_model="minimax-m3:cloud",
    )
    assert result["provider"] == "pi"
    assert result["model"] == "minimax-m3:cloud"
    assert result["summary"] == "归档结论"
    # 归档单次无会话：必须带 --no-session，不复用原 chat session。
    assert "--no-session" in captured["args"]
    assert "--session-id" not in captured["args"]
    # 仍清理 PI_PACKAGE_DIR，避免 Slock 注入导致 pi 启动崩溃。
    assert captured["env"] is not None
    assert captured["env"].get("PI_PACKAGE_DIR") is None


def test_run_pi_chat_archive_empty_raises(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)

    monkeypatch.setattr(
        app_module.subprocess,
        "run",
        lambda args, **kwargs: type(
            "Completed",
            (),
            {"returncode": 0, "stdout": '{"type":"session","id":"archive-session"}\n', "stderr": ""},
        )(),
    )
    raised = False
    try:
        app_module.run_pi_chat_archive(
            title="News",
            source="Reuters",
            published_at="2026-06-11",
            messages=[{"role": "user", "content": "总结"}, {"role": "assistant", "content": "结论"}],
            pi_provider="ollama",
            pi_model="minimax-m3:cloud",
        )
    except RuntimeError as exc:
        raised = True
        assert "pi_empty_archive" in str(exc)
    assert raised, "空摘要应抛 RuntimeError(pi_empty_archive)"


def test_news_chat_dispatches_to_pi_when_configured(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Pi Dispatch](https://example.com/pi-dispatch)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
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
                    "Pi Dispatch",
                    "Reporter",
                    "2026-06-11 09:00:00",
                    "Full body for pi dispatch test.",
                    33,
                    "{}",
                    ts,
                    ts,
                ),
            )

    captured = {}

    def fake_run_pi_chat(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "pi",
            "session_id": "pi-sess-1",
            "model": kwargs["pi_model"],
            "answer": "Pi 已回答",
        }

    monkeypatch.setattr(app_module, "run_pi_chat", fake_run_pi_chat)
    res = client.post(f"/api/news/{item['id']}/chat", json={"question": "最新进展？"})
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["ok"] is True
    assert payload["provider"] == "pi"
    assert payload["answer"] == "Pi 已回答"
    assert payload["session_id"] == "pi-sess-1"
    assert captured["item_id"] == item["id"]
    assert captured["pi_provider"] == "ollama"
    assert captured["pi_model"] == "minimax-m3:cloud"


def test_pi_chat_first_and_follow_up_reuse_the_same_session(tmp_path: Path, monkeypatch):
    import app as app_module

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return types.SimpleNamespace(
            returncode=0,
            stdout='{"type":"session","id":"pi-chat-session"}\n{"type":"message_update","assistantMessageEvent":{"type":"text_delta","delta":"回答"}}\n',
            stderr="",
        )

    monkeypatch.setattr(app_module.subprocess, "run", fake_run)
    first = app_module.run_pi_chat(
        item_id="item-1",
        question="首问",
        title="标题",
        source="Reuters",
        published_at="2026-06-11 09:00:00",
        content="English body",
        context_level="full_detail",
        pi_provider="ollama",
        pi_model="minimax-m3:cloud",
    )
    second = app_module.run_pi_chat(
        item_id="item-1",
        question="追问",
        title="标题",
        source="Reuters",
        published_at="2026-06-11 09:00:00",
        content="English body",
        context_level="full_detail",
        pi_provider="ollama",
        pi_model="minimax-m3:cloud",
        session_id=first["session_id"],
    )
    assert first["session_id"] == second["session_id"] == "pi-chat-session"
    assert calls[0][0:4] == ["pi", "-p", "--mode", "json"]
    assert calls[1][calls[1].index("--session-id") + 1] == "pi-chat-session"
    assert all("--no-session" not in command for command in calls)


def test_news_chat_archive_always_uses_pi_and_appends_note(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive](https://example.com/chat-archive)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200
    item = client.get("/api/news?per=20").get_json()["items"][0]
    captured = {}

    def fake_archive(**kwargs):
        captured.update(kwargs)
        return {"provider": "pi", "model": kwargs["pi_model"], "summary": "归档结论。"}

    monkeypatch.setattr(app_module, "run_pi_chat_archive", fake_archive)
    response = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={"messages": [{"role": "user", "content": "总结"}, {"role": "assistant", "content": "结论"}]},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["provider"] == "pi"
    assert payload["archive_summary"] == "归档结论。"
    assert captured["pi_provider"] == "ollama"
    assert captured["pi_model"] == "minimax-m3:cloud"
    assert "归档结论。" in payload["note"]["note"]


def test_news_chat_pi_timeout_maps_to_provider_timeout(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Pi Timeout](https://example.com/pi-timeout)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
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
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    with app_module.db_conn() as conn:
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item["url"], "Reuters", "Pi Timeout", "Reporter", "2026-06-11 09:00:00",
                 "body", 4, "{}", ts, ts),
            )

    monkeypatch.setattr(
        app_module, "run_pi_chat", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("pi_timeout"))
    )
    res = client.post(f"/api/news/{item['id']}/chat", json={"question": "？"})
    assert res.status_code == 504
    assert res.get_json()["error"] == "provider_timeout"


def test_twitter_image_url_filtering():
    import app as app_module

    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.jpg") is True
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.png") is True
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.webp?format=webp") is True
    assert app_module._is_twitter_image_url("https://example.com/image.jpeg") is False
    assert app_module._is_twitter_image_url("http://pbs.twimg.com/media/abc.jpg") is False
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/profile_images/abc.jpg") is False
    assert app_module._is_twitter_image_url("https://video.twimg.com/ext_tw_video/abc.mp4") is False
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.mp4") is False
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.m3u8") is False
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.jpg/amplify_video/123") is False
    assert app_module._is_twitter_image_url("https://pbs.twimg.com/media/abc.ext_tw_video.jpg") is False


def test_build_twitter_media_images_extracts_deduplicates_and_marks_source():
    import app as app_module

    main = {
        "media_urls": [
            "https://pbs.twimg.com/media/a.jpg",
            "https://video.twimg.com/v.mp4",
            "https://pbs.twimg.com/media/a.jpg",
        ]
    }
    quoted = {"media_urls": ["https://pbs.twimg.com/media/b.webp", "https://pbs.twimg.com/media/a.jpg"]}
    images = app_module._build_twitter_media_images(main, quoted)
    assert [img["url"] for img in images] == [
        "https://pbs.twimg.com/media/a.jpg",
        "https://pbs.twimg.com/media/b.webp",
    ]
    assert images[0]["source"] == "tweet"
    assert images[1]["source"] == "quoted_tweet"


def test_build_twitter_media_images_ignores_media_posters():
    import app as app_module

    main = {
        "media_urls": ["https://pbs.twimg.com/media/poster.jpg"],
        "media_posters": ["https://pbs.twimg.com/media/poster.jpg"],
    }
    # media_posters itself is not used as an image source; only media_urls is read.
    images = app_module._build_twitter_media_images(main, None)
    assert [img["url"] for img in images] == ["https://pbs.twimg.com/media/poster.jpg"]


def test_run_opencli_twitter_detail_includes_media_images(monkeypatch):
    import app as app_module

    thread_payload = [
        {
            "text": "主推文内容比较完整，足够通过正文长度校验。",
            "media_urls": [
                "https://pbs.twimg.com/media/a.jpg",
                "https://video.twimg.com/v.mp4",
            ],
            "quoted_tweet": {
                "text": "引用推文内容",
                "media_urls": ["https://pbs.twimg.com/media/b.webp"],
            },
        }
    ]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)
    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    payload = json.loads(detail["raw_json"])
    assert payload["media_images"] == [
        {"url": "https://pbs.twimg.com/media/a.jpg", "source": "tweet"},
        {"url": "https://pbs.twimg.com/media/b.webp", "source": "quoted_tweet"},
    ]


def test_detail_api_returns_twitter_media_images_and_hides_raw_json(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    url = "https://x.com/example/status/123"
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        f"""## X · Social（1条）
### [Tweet Update]({url})
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
    ts = app_module.now_ts()
    raw = json.dumps(
        {"media_images": [{"url": "https://pbs.twimg.com/media/a.jpg", "source": "tweet"}]},
        ensure_ascii=False,
    )
    conn = app_module.db_conn()
    try:
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Twitter/X", "Tweet Update", "alice", "2026-06-11 09:00:00", "content", len("content"), raw, ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["ok"] is True
    assert detail["detail"]["media_images"] == [{"url": "https://pbs.twimg.com/media/a.jpg", "source": "tweet"}]
    assert "raw_json" not in detail["detail"]


def test_detail_api_non_twitter_has_no_media_images(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    url = "https://www.reuters.com/world/example"
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

    item = client.get("/api/news?per=20").get_json()["items"][0]
    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Reuters", "T", "A", "2026-05-25", "English body " * 30, len("English body " * 30), "{}", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["ok"] is True
    assert detail["detail"].get("media_images") in (None, [])


def test_detail_retry_twitter_with_detail_requeues_detail_job(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    url = "https://x.com/example/status/123"
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        f"""## X · Social（1条）
### [Tweet Update]({url})
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
    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Twitter/X", "Tweet Update", "alice", "2026-06-11 09:00:00", "content", len("content"), "{}", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    retry = client.post(f"/api/news/{item['id']}/detail/retry")
    assert retry.status_code == 200
    assert retry.get_json()["ok"] is True

    conn = app_module.db_conn()
    try:
        job = conn.execute("SELECT status FROM detail_jobs WHERE url=?", (url,)).fetchone()
        assert job is not None
        assert job["status"] == "pending"
    finally:
        conn.close()


def test_detail_retry_twitter_with_detail_mode_ai_requeues_ai_job(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    url = "https://x.com/example/status/123"
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        f"""## X · Social（1条）
### [Tweet Update]({url})
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
    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Twitter/X", "Tweet Update", "alice", "2026-06-11 09:00:00", "content", len("content"), "{}", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    called = {}

    def fake_generate_body_translation_only(**kwargs):
        called.update(kwargs)
        return {
            "model": "deepseek-v4-flash",
            "key_points_zh": [],
            "conclusion_zh": "",
            "body_zh": "重试后的推文中文翻译。",
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_body_translation_only", fake_generate_body_translation_only)
    retry = client.post(f"/api/news/{item['id']}/detail/retry", json={"mode": "ai"})
    assert retry.status_code == 200
    assert retry.get_json()["ok"] is True

    conn = app_module.db_conn()
    try:
        job = conn.execute("SELECT status FROM ai_jobs WHERE url=?", (url,)).fetchone()
        assert job is not None
        assert job["status"] == "pending"
    finally:
        conn.close()

    assert app_module.process_pending_ai_once() is True
    assert called["title"] == "Tweet Update"
    assert called["source"] == "Twitter/X"
    assert called["content"] == "content"
    assert called["model"] == ""


def test_detail_retry_non_twitter_with_detail_still_requeues_ai_job(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年5月"
    daily_dir.mkdir(parents=True)
    url = "https://www.reuters.com/world/example"
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

    item = client.get("/api/news?per=20").get_json()["items"][0]
    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Reuters", "T", "A", "2026-05-25", "English body " * 30, len("English body " * 30), "{}", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    called = {}

    def fake_generate_article_ai(**kwargs):
        called.update(kwargs)
        return {
            "model": "deepseek-v4-flash",
            "key_points_zh": ["重试要点一", "重试要点二", "重试要点三"],
            "conclusion_zh": "重试结论。",
            "body_zh": "重试后的普通新闻中文翻译。",
            "raw_json": "{}",
        }

    monkeypatch.setattr(app_module, "generate_article_ai", fake_generate_article_ai)
    retry = client.post(f"/api/news/{item['id']}/detail/retry")
    assert retry.status_code == 200
    assert retry.get_json()["ok"] is True

    conn = app_module.db_conn()
    try:
        job = conn.execute("SELECT status FROM ai_jobs WHERE url=?", (url,)).fetchone()
        assert job is not None
        assert job["status"] == "pending"
    finally:
        conn.close()

    assert app_module.process_pending_ai_once() is True
    assert called["title"] == "T"
    assert called["source"] == "Reuters"
    assert called["content"] == ("English body " * 30).strip()
    assert called["model"] == ""



def test_sanitize_twitter_media_images_filters_invalid_items():
    import app as app_module

    raw = [
        {"url": "https://pbs.twimg.com/media/valid.jpg", "source": "tweet"},
        {"url": "https://example.com/image.jpg", "source": "tweet"},
        {"url": "https://video.twimg.com/ext_tw_video/x.mp4", "source": "tweet"},
        {"url": "https://pbs.twimg.com/media/valid2.png", "source": "quoted_tweet"},
        {"url": "https://pbs.twimg.com/media/duplicate.jpg", "source": "tweet"},
        {"url": "https://pbs.twimg.com/media/other.jpg", "source": "comments"},
        {"url": "https://pbs.twimg.com/media/amplify_video.jpg", "source": "tweet"},
        "not a dict",
    ]
    result = app_module._sanitize_twitter_media_images(raw)
    assert result == [
        {"url": "https://pbs.twimg.com/media/valid.jpg", "source": "tweet"},
        {"url": "https://pbs.twimg.com/media/valid2.png", "source": "quoted_tweet"},
        {"url": "https://pbs.twimg.com/media/duplicate.jpg", "source": "tweet"},
    ]


def test_detail_api_sanitizes_twitter_media_images_and_hides_raw_json(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    url = "https://x.com/example/status/123"
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        f"""## X · Social（1条）
### [Tweet Update]({url})
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
    ts = app_module.now_ts()
    raw = json.dumps(
        {
            "media_images": [
                {"url": "https://pbs.twimg.com/media/valid.jpg", "source": "tweet"},
                {"url": "https://example.com/image.jpg", "source": "tweet"},
                {"url": "https://video.twimg.com/ext_tw_video/x.mp4", "source": "tweet"},
                {"url": "https://pbs.twimg.com/media/valid2.png", "source": "quoted_tweet"},
                {"url": "https://pbs.twimg.com/media/valid.jpg", "source": "tweet"},
                {"url": "https://pbs.twimg.com/media/other.jpg", "source": "comments"},
            ]
        },
        ensure_ascii=False,
    )
    conn = app_module.db_conn()
    try:
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Twitter/X", "Tweet Update", "alice", "2026-06-11 09:00:00", "content", len("content"), raw, ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["ok"] is True
    assert detail["detail"]["media_images"] == [
        {"url": "https://pbs.twimg.com/media/valid.jpg", "source": "tweet"},
        {"url": "https://pbs.twimg.com/media/valid2.png", "source": "quoted_tweet"},
    ]
    assert "raw_json" not in detail["detail"]


def test_detail_retry_twitter_resets_detail_job_attempts_and_timestamps(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    url = "https://x.com/example/status/123"
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        f"""## X · Social（1条）
### [Tweet Update]({url})
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
    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Twitter/X", "Tweet Update", "alice", "2026-06-11 09:00:00", "content", len("content"), "{}", ts, ts),
        )
        conn.execute(
            """
            INSERT INTO detail_jobs(url, item_id, source, status, attempts, last_error, queued_at, started_at, finished_at, updated_at)
            VALUES (?, ?, ?, 'failed', 2, 'old error', ?, ?, ?, ?)
            """,
            (url, item["id"], "Twitter", ts, ts, ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    retry = client.post(f"/api/news/{item['id']}/detail/retry")
    assert retry.status_code == 200

    conn = app_module.db_conn()
    try:
        job = conn.execute("SELECT status, attempts, last_error, started_at, finished_at FROM detail_jobs WHERE url=?", (url,)).fetchone()
        assert job["status"] == "pending"
        assert job["attempts"] == 0
        assert job["last_error"] is None
        assert job["started_at"] is None
        assert job["finished_at"] is None
    finally:
        conn.close()



def test_media_cache_key_is_deterministic_sha256():
    import app as app_module

    key1 = app_module._media_cache_key_for_url("https://pbs.twimg.com/media/a.jpg")
    key2 = app_module._media_cache_key_for_url("https://pbs.twimg.com/media/a.jpg")
    assert isinstance(key1, str) and len(key1) == 64
    assert key1 == key2
    assert app_module._media_cache_key_for_url("https://pbs.twimg.com/media/b.jpg") != key1


def test_extension_for_mime_type():
    import app as app_module

    assert app_module._extension_for_mime_type("image/jpeg") == ".jpg"
    assert app_module._extension_for_mime_type("image/png") == ".png"
    assert app_module._extension_for_mime_type("image/webp") == ".webp"
    assert app_module._extension_for_mime_type("video/mp4") == ""
    assert app_module._extension_for_mime_type(None) == ""


def test_cache_twitter_image_downloads_and_records(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    def fake_download(url, dest_path):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"fake-image")
        return True, "image/jpeg", len(b"fake-image")

    monkeypatch.setattr(app_module, "_download_media_file", fake_download)

    url = "https://pbs.twimg.com/media/sample.jpg"
    conn = app_module.db_conn()
    try:
        result = app_module._cache_twitter_image(conn, url)
        conn.commit()
    finally:
        conn.close()

    assert result is not None
    assert result["cached_url"].startswith("/api/media-cache/")
    cache_key = result["cache_key"]

    conn = app_module.db_conn()
    try:
        row = conn.execute("SELECT * FROM media_cache WHERE url=?", (url,)).fetchone()
        assert row["status"] == "success"
        assert row["mime_type"] == "image/jpeg"
        assert row["size_bytes"] == len(b"fake-image")
        assert (media_dir / row["relative_path"]).exists()
    finally:
        conn.close()

    # Second call should return existing cache without re-downloading.
    conn = app_module.db_conn()
    try:
        result2 = app_module._cache_twitter_image(conn, url)
    finally:
        conn.close()
    assert result2["cache_key"] == cache_key


def test_cache_twitter_image_failure_records_failed_status(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    def fake_download(url, dest_path):
        return False, "http_404", 0

    monkeypatch.setattr(app_module, "_download_media_file", fake_download)

    url = "https://pbs.twimg.com/media/missing.jpg"
    conn = app_module.db_conn()
    try:
        result = app_module._cache_twitter_image(conn, url)
        conn.commit()
    finally:
        conn.close()

    assert result is None
    conn = app_module.db_conn()
    try:
        row = conn.execute("SELECT status, last_error FROM media_cache WHERE url=?", (url,)).fetchone()
        assert row["status"] == "failed"
        assert "404" in row["last_error"]
    finally:
        conn.close()


def test_cleanup_media_cache_removes_old_files_and_records(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    old_file = media_dir / "ab" / "cd" / "old.jpg"
    old_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.write_bytes(b"old")
    new_file = media_dir / "ef" / "gh" / "new.jpg"
    new_file.parent.mkdir(parents=True, exist_ok=True)
    new_file.write_bytes(b"new")

    conn = app_module.db_conn()
    try:
        ts = app_module.now_ts()
        old_ts = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("https://pbs.twimg.com/media/old.jpg", "oldkey", "ab/cd/old.jpg", "image/jpeg", 3, "success", old_ts, old_ts),
        )
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("https://pbs.twimg.com/media/new.jpg", "newkey", "ef/gh/new.jpg", "image/jpeg", 3, "success", ts, ts),
        )
        conn.commit()
        app_module._cleanup_media_cache(conn)
        conn.commit()
    finally:
        conn.close()

    conn = app_module.db_conn()
    try:
        rows = conn.execute("SELECT url FROM media_cache").fetchall()
        assert [r["url"] for r in rows] == ["https://pbs.twimg.com/media/new.jpg"]
    finally:
        conn.close()
    assert not old_file.exists()
    assert new_file.exists()


def test_run_opencli_twitter_detail_caches_images(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(tmp_path / "media-cache"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    thread_payload = [
        {
            "text": "主推文内容比较完整，足够通过正文长度校验。",
            "media_urls": [
                "https://pbs.twimg.com/media/a.jpg",
                "https://video.twimg.com/v.mp4",
            ],
            "quoted_tweet": {"text": "引用内容", "media_urls": ["https://pbs.twimg.com/media/b.png"]},
        }
    ]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    downloaded: set[str] = set()

    def fake_download(url, dest_path):
        downloaded.add(url)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"img")
        return True, "image/jpeg", 3

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)
    monkeypatch.setattr(app_module, "_download_media_file", fake_download)

    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    payload = json.loads(detail["raw_json"])
    assert len(payload["media_images"]) == 2
    for img in payload["media_images"]:
        assert "cache_key" in img
        assert img["cached_url"].startswith("/api/media-cache/")
    assert "https://video.twimg.com/v.mp4" not in downloaded


def test_detail_api_returns_cached_urls_for_twitter_images(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    url = "https://x.com/example/status/123"
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        f"""## X · Social（1条）
### [Tweet Update]({url})
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]
    ts = app_module.now_ts()
    cache_key = app_module._media_cache_key_for_url("https://pbs.twimg.com/media/a.jpg")
    raw = json.dumps(
        {
            "media_images": [
                {"url": "https://pbs.twimg.com/media/a.jpg", "source": "tweet"},
                {"url": "https://video.twimg.com/v.mp4", "source": "tweet"},
                {"url": "https://pbs.twimg.com/media/missing.jpg", "source": "tweet"},
            ]
        },
        ensure_ascii=False,
    )
    conn = app_module.db_conn()
    try:
        conn.execute(
            "UPDATE items SET source=?, source_name=?, source_type=? WHERE id=?",
            ("Twitter", "Twitter", "twitter", item["id"]),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, source, title, author, published_at, content, content_length, raw_json, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, "Twitter/X", "Tweet Update", "alice", "2026-06-11 09:00:00", "content", len("content"), raw, ts, ts),
        )
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("https://pbs.twimg.com/media/a.jpg", cache_key, f"{cache_key}.jpg", "image/jpeg", 3, "success", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["ok"] is True
    images = detail["detail"]["media_images"]
    assert len(images) == 2  # video dropped, missing not sanitized to valid because no cache
    valid = [img for img in images if img["url"] == "https://pbs.twimg.com/media/a.jpg"][0]
    assert valid["cached_url"] == f"/api/media-cache/{cache_key}"
    assert "raw_json" not in detail["detail"]


def test_media_cache_route_serves_cached_file(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    url = "https://pbs.twimg.com/media/route.jpg"
    cache_key = app_module._media_cache_key_for_url(url)
    relative_path = f"{cache_key[:2]}/{cache_key[2:4]}/{cache_key}.jpg"
    full_path = media_dir / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"cached-data")

    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (url, cache_key, relative_path, "image/jpeg", len(b"cached-data"), "success", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    client = app_module.app.test_client()
    res = client.get(f"/api/media-cache/{cache_key}")
    assert res.status_code == 200
    assert res.data == b"cached-data"
    assert res.mimetype == "image/jpeg"


def test_media_cache_route_rejects_invalid_and_missing_keys(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    assert client.get("/api/media-cache/not-hex").status_code == 400
    assert client.get("/api/media-cache/" + "0" * 64).status_code == 404



def test_media_cache_route_blocks_traversal_and_sibling_prefix(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    evil_sibling = tmp_path / "media-cache-evil"
    evil_sibling.mkdir(parents=True, exist_ok=True)
    evil_file = evil_sibling / "stolen.jpg"
    evil_file.write_bytes(b"evil")

    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    ts = app_module.now_ts()
    conn = app_module.db_conn()
    try:
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("https://pbs.twimg.com/media/evil.jpg", "e" * 64, "../media-cache-evil/stolen.jpg", "image/jpeg", 4, "success", ts, ts),
        )
        conn.commit()
    finally:
        conn.close()

    client = app_module.app.test_client()
    res = client.get(f"/api/media-cache/{'e' * 64}")
    assert res.status_code == 400
    assert evil_file.exists()


def test_cleanup_media_cache_does_not_delete_outside_files(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    outside_file = tmp_path / "outside.jpg"
    outside_file.write_bytes(b"outside")

    conn = app_module.db_conn()
    try:
        old_ts = (datetime.now() - timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO media_cache(url, cache_key, relative_path, mime_type, size_bytes, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("https://pbs.twimg.com/media/outside.jpg", "0" * 64, "../outside.jpg", "image/jpeg", 7, "success", old_ts, old_ts),
        )
        conn.commit()
        app_module._cleanup_media_cache(conn)
        conn.commit()
    finally:
        conn.close()

    assert outside_file.exists()
    conn = app_module.db_conn()
    try:
        row = conn.execute("SELECT url FROM media_cache WHERE cache_key=?", ("0" * 64,)).fetchone()
        assert row is None
    finally:
        conn.close()



def test_cache_twitter_image_rejects_non_whitelisted_url(tmp_path: Path, monkeypatch):
    media_dir = tmp_path / "media-cache"
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(media_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    downloaded: set[str] = set()

    def fake_download(url, dest_path):
        downloaded.add(url)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"img")
        return True, "image/jpeg", 3

    monkeypatch.setattr(app_module, "_download_media_file", fake_download)

    conn = app_module.db_conn()
    try:
        assert app_module._cache_twitter_image(conn, "https://example.com/image.jpeg") is None
        assert app_module._cache_twitter_image(conn, "http://pbs.twimg.com/media/a.jpg") is None
        assert app_module._cache_twitter_image(conn, "https://pbs.twimg.com/profile_images/a.jpg") is None
        conn.commit()
    finally:
        conn.close()

    assert not downloaded



def test_run_opencli_twitter_detail_allows_short_tweet_with_media(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(tmp_path / "media-cache"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    thread_payload = [
        {
            "text": "看图。",
            "media_urls": ["https://pbs.twimg.com/media/a.jpg"],
        }
    ]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)
    def fake_download(url, dest_path):
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"img")
        return True, "image/jpeg", 3

    monkeypatch.setattr(app_module, "_download_media_file", fake_download)

    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    payload = json.loads(detail["raw_json"])
    assert len(payload["media_images"]) == 1
    assert payload["media_images"][0]["url"] == "https://pbs.twimg.com/media/a.jpg"


def test_run_opencli_twitter_detail_allows_short_tweet_with_quoted_text(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(tmp_path / "media-cache"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    thread_payload = [
        {
            "text": "短评。",
            "quoted_tweet": {"text": "这是一条内容足够长的引用推文，用来验证短主推文不会因为正文长度不足而被判定为空线程。"},
        }
    ]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)

    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    assert "短评" in detail["content"]


def test_run_opencli_twitter_detail_rejects_truly_empty_thread(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(tmp_path / "media-cache"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    thread_payload = [{"text": ""}]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)

    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is False
    assert error == "EMPTY_TWITTER_THREAD"



def test_run_opencli_twitter_detail_allows_single_character_tweet(monkeypatch, tmp_path):
    monkeypatch.setenv("NEWS_READER_MEDIA_CACHE_DIR", str(tmp_path / "media-cache"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(tmp_path / "news_index.sqlite3"))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()

    thread_payload = [{"text": "早"}]

    def fake_run(cmd, timeout):
        if "thread" in cmd:
            return True, thread_payload, ""
        return False, None, "Article not found"

    monkeypatch.setattr(app_module, "_run_opencli_json_command", fake_run)

    ok, detail, error = app_module.run_opencli_twitter_detail("https://x.com/example/status/123")
    assert ok is True
    assert error == ""
    assert "早" in detail["content"]



def test_normalize_deepseek_model_maps_deprecated_names():
    import app as app_module

    assert app_module.normalize_deepseek_model("deepseek-chat") == "deepseek-v4-flash"
    assert app_module.normalize_deepseek_model("deepseek-reasoner") == "deepseek-v4-pro"
    assert app_module.normalize_deepseek_model("deepseek-v4-flash") == "deepseek-v4-flash"
    assert app_module.normalize_deepseek_model("  DeepSeek-Chat  ") == "deepseek-v4-flash"
    assert app_module.normalize_deepseek_model("") == ""


def test_settings_load_normalizes_deprecated_deepseek_model(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"translation": {"provider": "deepseek", "model": "deepseek-chat"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    settings = app_module.current_runtime_settings()
    assert settings["llm"]["translation"]["model"] == "deepseek-v4-flash"


def test_settings_save_normalizes_deprecated_deepseek_model(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    normalized = app_module.validate_runtime_settings(
        {"llm": {"translation": {"provider": "deepseek", "model": "deepseek-chat"}}}
    )
    assert normalized["llm"]["translation"]["model"] == "deepseek-v4-flash"


def test_standalone_idea_crud_and_merge(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()

    # create
    resp = client.post("/api/standalone-ideas", json={"note": "  第一个独立想法  "})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    idea = data["idea"]
    assert idea["idea_type"] == "standalone_note"
    assert idea["idea_id"].startswith("standalone:")
    assert idea["standalone_id"] is not None
    assert idea["note"] == "第一个独立想法"
    assert idea["title"] == "独立想法"
    idea_id = idea["standalone_id"]

    # empty note rejected
    assert client.post("/api/standalone-ideas", json={"note": "   "}).status_code == 400
    assert client.post("/api/standalone-ideas", json={"note": ""}).status_code == 400
    # invalid type
    assert client.post("/api/standalone-ideas", json={"note": 123}).status_code == 400
    # too long
    assert client.post("/api/standalone-ideas", json={"note": "x" * 5001}).status_code == 400
    # max length boundary ok
    resp_max = client.post("/api/standalone-ideas", json={"note": "y" * 5000})
    assert resp_max.status_code == 200

    # list merged in /api/ideas
    ideas = client.get("/api/ideas?per=100")
    assert ideas.status_code == 200
    payload = ideas.get_json()
    standalone_items = [item for item in payload["items"] if item["idea_type"] == "standalone_note"]
    assert len(standalone_items) == 2

    # filter standalone only
    standalone_only = client.get("/api/ideas?type=standalone&per=100")
    assert standalone_only.status_code == 200
    assert standalone_only.get_json()["total"] == 2
    assert all(item["idea_type"] == "standalone_note" for item in standalone_only.get_json()["items"])

    # filter article only — no standalone
    article_only = client.get("/api/ideas?type=article&per=100")
    assert article_only.status_code == 200
    assert all(item["idea_type"] == "article_note" for item in article_only.get_json()["items"])

    # update
    resp = client.patch(f"/api/standalone-ideas/{idea_id}", json={"note": "  更新后的想法  "})
    assert resp.status_code == 200
    updated = resp.get_json()["idea"]
    assert updated["note"] == "更新后的想法"

    # update empty rejected
    assert client.patch(f"/api/standalone-ideas/{idea_id}", json={"note": "  "}).status_code == 400
    # update too long
    assert client.patch(f"/api/standalone-ideas/{idea_id}", json={"note": "x" * 5001}).status_code == 400
    # update non-existent
    assert client.patch("/api/standalone-ideas/99999", json={"note": "test"}).status_code == 404

    # delete
    assert client.delete(f"/api/standalone-ideas/{idea_id}").status_code == 200
    # delete again → 404
    assert client.delete(f"/api/standalone-ideas/{idea_id}").status_code == 404

    # verify deleted from ideas list
    after_delete = client.get("/api/ideas?type=standalone&per=100")
    assert after_delete.get_json()["total"] == 1

    # invalid filter type still rejected
    assert client.get("/api/ideas?type=weird").status_code == 400


def test_market_trend_note_patch_date_tag_direction(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-02.md").write_text(
        """## Reuters · World（1条）
### [API 测试新闻](https://www.reuters.com/world/r1)
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

    # Create initial note: AI bullish on 2026-06-02
    create_res = client.put(
        "/api/market-trends/note",
        json={"date_key": "2026-06-02", "tag_key": "AI", "direction": "bullish", "note": "初始想法"},
    )
    assert create_res.status_code == 200
    note_id = create_res.get_json()["trend_note"]["id"]

    # Backward compatibility: only update note text
    patch_only_note = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "仅更新正文"},
    )
    assert patch_only_note.status_code == 200
    data = patch_only_note.get_json()
    assert data["trend_note"]["note"] == "仅更新正文"
    assert data["date"] == "2026-06-02"
    assert data["tag_key"] == "AI"
    assert data["direction"] == "bullish"

    # Update all four fields: move to new date/tag/direction
    patch_all = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={
            "note": "迁移后的想法",
            "date_key": "2026-06-03",
            "tag_key": "AI",
            "direction": "bearish",
        },
    )
    assert patch_all.status_code == 200
    data = patch_all.get_json()
    assert data["trend_note"]["note"] == "迁移后的想法"
    assert data["date"] == "2026-06-03"
    assert data["direction"] == "bearish"

    # Old group should be empty
    old_detail = client.get("/api/market-trends/detail?date=2026-06-02&tag=AI&direction=bullish")
    assert old_detail.status_code == 200
    assert old_detail.get_json()["trend_note_total"] == 0

    # New group should contain the migrated note
    new_detail = client.get("/api/market-trends/detail?date=2026-06-03&tag=AI&direction=bearish")
    assert new_detail.status_code == 200
    new_payload = new_detail.get_json()
    assert new_payload["trend_note_total"] == 1
    assert new_payload["trend_notes"][0]["note"] == "迁移后的想法"

    # Invalid direction should be rejected
    invalid = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "无效方向", "direction": "sideways"},
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["ok"] is False

    # Invalid tag should be rejected
    invalid_tag = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "无效板块", "tag_key": "Unknown"},
    )
    assert invalid_tag.status_code == 400
    assert invalid_tag.get_json()["ok"] is False

    # Empty note should be rejected
    empty = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "   "},
    )
    assert empty.status_code == 400
    assert empty.get_json()["ok"] is False

    # Invalid date format should be rejected
    invalid_date_fmt = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "日期格式非法", "date_key": "not-a-date"},
    )
    assert invalid_date_fmt.status_code == 400
    assert invalid_date_fmt.get_json()["ok"] is False

    # Invalid calendar date should be rejected
    invalid_calendar = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "日历日期不存在", "date_key": "2026-02-30"},
    )
    assert invalid_calendar.status_code == 400
    assert invalid_calendar.get_json()["ok"] is False

    # Valid date update should be accepted
    valid_date = client.patch(
        f"/api/market-trends/note/{note_id}",
        json={"note": "日期有效", "date_key": "2026-06-01"},
    )
    assert valid_date.status_code == 200
    data = valid_date.get_json()
    assert data["date"] == "2026-06-01"
    assert data["trend_note"]["note"] == "日期有效"


# ── 复盘功能测试 (v2.1.0) ──


def _setup_review_env(tmp_path: Path, monkeypatch):
    """Set up a clean env with DB and reindexed news for review tests."""
    db_path = tmp_path / "news_index.sqlite3"
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-07-01.md").write_text(
        """## Reuters · World（1条）
### [复盘测试新闻](https://example.com/review-test)
- 发布时间：2026-07-01 12:00:00
- 摘要：新能源政策即将出台
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()
    client.post("/api/reindex", json={})
    return client, app_module


def _create_standalone_idea(client, note: str = "这项政策长期可能利好新能源") -> int:
    resp = client.post("/api/standalone-ideas", json={"note": note})
    assert resp.status_code == 200
    return resp.get_json()["idea"]["standalone_id"]


def _create_article_note(client, url: str, note: str = "新能源板块即将大涨") -> None:
    resp = client.put(f"/api/news/url/{url}/note", json={"note": note})
    if resp.status_code != 200:
        # fallback: use item-based note endpoint
        # find item_id for this url
        news = client.get("/api/news?per=100").get_json()
        for item in news["items"]:
            if item["url"] == url:
                resp = client.put(f"/api/news/{item['id']}/note", json={"note": note})
                assert resp.status_code == 200
                return
        raise RuntimeError(f"cannot find item with url {url}")


def test_review_schema_migration_idempotent(tmp_path: Path, monkeypatch):
    """Schema migration should be idempotent — ensure_db twice without error."""
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    app_module.ensure_db()  # second call should not error

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Verify review tables exist
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "review_chains" in tables
    assert "review_versions" in tables
    assert "review_events" in tables
    assert "review_evidence" in tables
    # Verify news_reminders has review_chain_id
    cols = {r[1] for r in conn.execute("PRAGMA table_info(news_reminders)").fetchall()}
    assert "review_chain_id" in cols
    conn.close()


def test_review_create_from_standalone_idea(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)

    resp = client.post("/api/reviews", json={
        "source_type": "standalone_idea",
        "source_key": str(idea_id),
        "judgment": "政策实施后三个月内新能源融资成本下降",
        "criteria": "新能源企业平均融资成本数据下降5%以上",
        "plan_review_date": "2026-10-01",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    review = data["review"]
    assert review["status"] == "active"
    assert review["effective_status"] == "in_progress"
    assert review["current_version"] == 1
    assert review["source_note"] == "这项政策长期可能利好新能源"
    assert len(review["versions"]) == 1
    assert review["versions"][0]["judgment"] == "政策实施后三个月内新能源融资成本下降"
    assert len(review["events"]) == 1


def test_review_create_from_article_note(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    url = "https://example.com/review-test"
    # Create article note
    news = client.get("/api/news?per=100").get_json()
    item_id = None
    for item in news["items"]:
        if item["url"] == url:
            item_id = item["id"]
            break
    assert item_id is not None
    resp = client.put(f"/api/news/{item_id}/note", json={"note": "新能源板块要涨"})
    assert resp.status_code == 200

    resp = client.post("/api/reviews", json={
        "source_type": "article_note",
        "source_key": url,
        "judgment": "新能源板块一周内上涨",
        "criteria": "板块指数涨幅超过3%",
        "plan_review_date": "2026-07-08",
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert review["source_note"] == "新能源板块要涨"
    assert review["source_snapshot"]["news_list"][0]["title"] == "复盘测试新闻"


def test_review_create_source_not_found(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    resp = client.post("/api/reviews", json={
        "source_type": "standalone_idea",
        "source_key": "99999",
        "judgment": "test",
        "criteria": "test",
        "plan_review_date": "2026-10-01",
    })
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "source_not_found"


def test_review_create_missing_fields(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    base = {"source_type": "standalone_idea", "source_key": str(idea_id)}
    # missing judgment
    assert client.post("/api/reviews", json={**base, "criteria": "c", "plan_review_date": "2026-10-01"}).status_code == 400
    # missing criteria is now OK (optional)
    resp = client.post("/api/reviews", json={**base, "judgment": "j", "plan_review_date": "2026-10-01"})
    assert resp.status_code == 200
    assert resp.get_json()["review"]["source_note"]
    # missing date
    assert client.post("/api/reviews", json={**base, "judgment": "j", "criteria": "c"}).status_code == 400
    # invalid date
    assert client.post("/api/reviews", json={**base, "judgment": "j", "criteria": "c", "plan_review_date": "bad"}).status_code == 400


def test_review_revise_without_criteria(tmp_path: Path, monkeypatch):
    """Criteria is optional in revise."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "V1判断", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/revise", json={
        "judgment": "V2判断", "revision_reason": "新证据", "event_date": "2026-07-06",
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert review["current_version"] == 2
    assert review["versions"][1]["criteria"] == ""


def test_review_retrack_without_criteria(tmp_path: Path, monkeypatch):
    """Criteria is optional in retrack."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "V1判断", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Complete the chain first
    client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "confirmed", "actual_text": "结果", "experience": "经验",
    })
    # Retrack without criteria
    resp = client.post(f"/api/reviews/{chain_id}/retrack", json={
        "judgment": "新判断", "plan_review_date": "2099-12-01",
    })
    assert resp.status_code == 200
    assert resp.get_json()["review"]["source_note"]




def test_review_list_date_key_label(tmp_path: Path, monkeypatch):
    """Reviews list should return date_key/date_label derived from plan_review_date."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "未来判断", "plan_review_date": "2099-03-15",
    })
    r = client.get("/api/reviews?per=100")
    assert r.status_code == 200
    item = r.get_json()["items"][0]
    assert item["date_key"] == "2099-03-15"
    assert item["date_label"] == "2099年3月15日"


def test_review_list_groups_same_plan_date_together(tmp_path: Path, monkeypatch):
    """Reviews with the same plan_review_date must be contiguous regardless of updated_at order."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    # A1 and A2 share plan date; B has a different plan date
    idea_a1 = _create_standalone_idea(client, "A1 想法")
    idea_b = _create_standalone_idea(client, "B 想法")
    idea_a2 = _create_standalone_idea(client, "A2 想法")

    r_a1 = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_a1),
        "judgment": "A1", "plan_review_date": "2026-08-12",
    })
    r_b = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_b),
        "judgment": "B", "plan_review_date": "2026-09-01",
    })
    r_a2 = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_a2),
        "judgment": "A2", "plan_review_date": "2026-08-12",
    })
    id_a1 = r_a1.get_json()["review"]["id"]
    id_b = r_b.get_json()["review"]["id"]
    id_a2 = r_a2.get_json()["review"]["id"]

    # Force interleaved updated_at: A2 newest, B middle, A1 oldest
    db_path = tmp_path / "news_index.sqlite3"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE review_chains SET updated_at = ? WHERE id = ?",
        ("2026-07-13T10:00:00", id_a1),
    )
    conn.execute(
        "UPDATE review_chains SET updated_at = ? WHERE id = ?",
        ("2026-07-13T11:00:00", id_b),
    )
    conn.execute(
        "UPDATE review_chains SET updated_at = ? WHERE id = ?",
        ("2026-07-13T12:00:00", id_a2),
    )
    conn.commit()
    conn.close()

    r = client.get("/api/reviews?per=100")
    assert r.status_code == 200
    items = r.get_json()["items"]
    date_keys = [item["date_key"] for item in items]
    # Same plan date should be contiguous, and latest-updated within group comes first
    assert date_keys == ["2026-08-12", "2026-08-12", "2026-09-01"], date_keys
    assert items[0]["id"] == id_a2
    assert items[1]["id"] == id_a1
    assert items[2]["id"] == id_b


def test_review_initial_event_date_is_today_not_plan_date(tmp_path: Path, monkeypatch):
    """Initial revision event must record the actual creation date, not plan_review_date."""
    client, app_module = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "V1", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    detail = client.get(f"/api/reviews/{chain_id}").get_json()["review"]
    assert len(detail["events"]) == 1
    ev = detail["events"][0]
    assert ev["event_type"] == "revision"
    assert ev["version_id"] is None
    today = app_module._today_str()
    assert ev["event_date"] == today, f"event_date {ev['event_date']} != today {today}"
    assert ev["event_date"] != "2099-01-01"


def test_review_old_record_event_date_fallback_to_created_at(tmp_path: Path, monkeypatch):
    """Old records whose initial revision stored plan_review_date should display created_at."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "V1", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Simulate legacy record: force initial event_date to plan_review_date
    conn = sqlite3.connect(str(tmp_path / "news_index.sqlite3"))
    conn.execute(
        "UPDATE review_events SET event_date = '2099-01-01' WHERE chain_id = ? AND event_type = 'revision' AND version_id IS NULL",
        (chain_id,),
    )
    conn.commit()
    conn.close()
    detail = client.get(f"/api/reviews/{chain_id}").get_json()["review"]
    ev = detail["events"][0]
    assert ev["event_date"] == detail["created_at"][:10]
    assert ev["event_date"] != "2099-01-01"


def test_review_criteria_empty_in_versions(tmp_path: Path, monkeypatch):
    """When criteria is omitted, version criteria should be empty string, not missing."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "无标准判断", "plan_review_date": "2099-01-01",
    })
    review = r.get_json()["review"]
    assert review["versions"][0]["criteria"] == ""

def test_review_list_and_filter(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)

    # Create in_progress review (future date)
    client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "未来判断", "criteria": "标准", "plan_review_date": "2099-01-01",
    })
    # Create pending_review review (past date)
    idea_id2 = _create_standalone_idea(client, "第二条想法")
    client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id2),
        "judgment": "到期判断", "criteria": "标准2", "plan_review_date": "2020-01-01",
    })

    # All
    r = client.get("/api/reviews?per=100")
    assert r.status_code == 200
    assert r.get_json()["total"] == 2

    # In progress
    r = client.get("/api/reviews?status=in_progress")
    assert r.get_json()["total"] == 1
    assert r.get_json()["items"][0]["current_judgment"] == "未来判断"

    # Pending review
    r = client.get("/api/reviews?status=pending_review")
    assert r.get_json()["total"] == 1
    assert r.get_json()["items"][0]["effective_status"] == "pending_review"

    # Done (none yet)
    r = client.get("/api/reviews?status=done")
    assert r.get_json()["total"] == 0


def test_review_done_list_result_filter_is_paginated_server_side(tmp_path: Path, monkeypatch):
    """Result filters must constrain the API query instead of only loaded rows."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    confirmed_ids = []
    for index in range(11):
        idea_id = _create_standalone_idea(client, f"成立想法 {index}")
        created = client.post("/api/reviews", json={
            "source_type": "standalone_idea", "source_key": str(idea_id),
            "judgment": f"成立判断 {index}", "plan_review_date": "2020-01-01",
        })
        chain_id = created.get_json()["review"]["id"]
        completed = client.post(f"/api/reviews/{chain_id}/complete", json={
            "result": "confirmed", "actual_text": "事实结果", "experience": "复盘经验",
        })
        assert completed.status_code == 200
        confirmed_ids.append(chain_id)

    refuted_idea_id = _create_standalone_idea(client, "未成立想法")
    created = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(refuted_idea_id),
        "judgment": "未成立判断", "plan_review_date": "2020-01-01",
    })
    refuted_id = created.get_json()["review"]["id"]
    client.post(f"/api/reviews/{refuted_id}/complete", json={
        "result": "refuted", "actual_text": "事实结果", "experience": "复盘经验",
    })

    first_page = client.get("/api/reviews?status=done&result=confirmed&per=10")
    assert first_page.status_code == 200
    assert first_page.get_json()["total"] == 11
    assert first_page.get_json()["has_more"] is True
    assert {item["result"] for item in first_page.get_json()["items"]} == {"confirmed"}

    second_page = client.get("/api/reviews?status=done&result=confirmed&per=10&page=2")
    assert second_page.status_code == 200
    assert second_page.get_json()["total"] == 11
    assert second_page.get_json()["has_more"] is False
    assert len(second_page.get_json()["items"]) == 1
    assert second_page.get_json()["items"][0]["id"] in confirmed_ids

    refuted = client.get("/api/reviews?status=done&result=refuted")
    assert refuted.status_code == 200
    assert refuted.get_json()["total"] == 1
    assert refuted.get_json()["items"][0]["id"] == refuted_id

    invalid = client.get("/api/reviews?status=done&result=partial")
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "invalid_result_filter"


def test_review_progress(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]

    resp = client.post(f"/api/reviews/{chain_id}/progress", json={
        "event_text": "新政策已发布",
        "event_date": "2026-07-05",
        "evidence": [{"news_title": "新政策发布", "news_url": "https://example.com/policy", "news_summary": "政策细则"}],
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert len(review["events"]) == 2  # initial revision + progress
    assert review["events"][-1]["event_type"] == "progress"
    assert len(review["evidence"]) == 1
    assert review["evidence"][0]["news_title"] == "新政策发布"


def test_review_revise(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "V1判断", "criteria": "V1标准", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]

    resp = client.post(f"/api/reviews/{chain_id}/revise", json={
        "judgment": "V2判断", "criteria": "V2标准",
        "revision_reason": "新证据出现", "event_date": "2026-07-06",
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert review["current_version"] == 2
    assert len(review["versions"]) == 2
    assert review["versions"][0]["judgment"] == "V1判断"
    assert review["versions"][1]["judgment"] == "V2判断"
    assert review["versions"][1]["revision_reason"] == "新证据出现"


def test_review_complete(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]

    resp = client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "confirmed",
        "actual_text": "新能源融资成本确实下降",
        "bias_text": "低估了政策力度",
        "experience": "关注政策实施力度而非仅看方向",
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert review["status"] == "done"
    assert review["effective_status"] == "done"
    assert review["result"] == "confirmed"
    assert review["experience"] == "关注政策实施力度而非仅看方向"
    assert review["completed_at"] != ""


def test_review_complete_missing_experience(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "confirmed", "actual_text": "a", "bias_text": "b",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "missing_experience"


def test_review_complete_invalid_result(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "wrong", "actual_text": "a", "bias_text": "b", "experience": "e",
    })
    assert resp.status_code == 400


def test_review_done_blocks_actions(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "confirmed", "actual_text": "a", "bias_text": "b", "experience": "e",
    })
    # Cannot revise
    assert client.post(f"/api/reviews/{chain_id}/revise", json={
        "judgment": "j2", "criteria": "c2", "revision_reason": "r", "event_date": "2026-07-06",
    }).status_code == 409
    # Cannot progress
    assert client.post(f"/api/reviews/{chain_id}/progress", json={
        "event_text": "t", "event_date": "2026-07-06",
    }).status_code == 409
    # Cannot continue observing
    assert client.post(f"/api/reviews/{chain_id}/continue-observing", json={
        "new_review_date": "2026-12-01",
    }).status_code == 409


def test_review_continue_observing(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/continue-observing", json={
        "event_text": "暂不可判断，继续观察",
        "new_review_date": "2026-12-01",
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert review["status"] == "active"  # still active, not done
    assert review["plan_review_date"] == "2026-12-01"
    assert review["effective_status"] == "in_progress"  # future date
    # Check event recorded
    assert any(e["event_type"] == "continue_observing" for e in review["events"])


def test_review_retrack(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "refuted", "actual_text": "a", "bias_text": "b", "experience": "e",
    })
    # Retrack
    resp = client.post(f"/api/reviews/{chain_id}/retrack", json={
        "judgment": "新判断", "criteria": "新标准", "plan_review_date": "2027-01-01",
    })
    assert resp.status_code == 200
    new_review = resp.get_json()["review"]
    assert new_review["parent_chain_id"] == chain_id
    assert new_review["status"] == "active"
    assert new_review["current_version"] == 1
    assert new_review["source_note"] == "这项政策长期可能利好新能源"  # snapshot preserved


def test_review_retrack_event_date_is_today(tmp_path: Path, monkeypatch):
    """Retracked chain's first 'retracked' event must use actual creation date, not plan_review_date."""
    client, app_module = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2020-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    client.post(f"/api/reviews/{chain_id}/complete", json={
        "result": "refuted", "actual_text": "a", "experience": "e",
    })
    future = "2027-12-01"
    resp = client.post(f"/api/reviews/{chain_id}/retrack", json={
        "judgment": "新判断", "criteria": "新标准", "plan_review_date": future,
    })
    assert resp.status_code == 200
    new_review = resp.get_json()["review"]
    assert new_review["plan_review_date"] == future
    retracked_events = [e for e in new_review["events"] if e["event_type"] == "retracked"]
    assert len(retracked_events) == 1
    today = app_module._today_str()
    assert retracked_events[0]["event_date"] == today
    assert retracked_events[0]["event_date"] != future


def test_review_retrack_not_done(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/retrack", json={
        "judgment": "j2", "criteria": "c2", "plan_review_date": "2027-01-01",
    })
    assert resp.status_code == 409


def test_review_evidence_add_and_delete(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Add
    resp = client.post(f"/api/reviews/{chain_id}/evidence", json={
        "news_title": "证据新闻", "news_url": "https://example.com/ev1", "news_summary": "摘要",
    })
    assert resp.status_code == 200
    ev_id = resp.get_json()["evidence_id"]
    # Delete
    resp = client.delete(f"/api/reviews/{chain_id}/evidence/{ev_id}")
    assert resp.status_code == 200
    # Verify gone
    detail = client.get(f"/api/reviews/{chain_id}").get_json()["review"]
    assert len(detail["evidence"]) == 0


def test_review_evidence_wrong_chain(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r1 = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j1", "criteria": "c1", "plan_review_date": "2099-01-01",
    })
    chain1 = r1.get_json()["review"]["id"]
    idea_id2 = _create_standalone_idea(client, "想法2")
    r2 = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id2),
        "judgment": "j2", "criteria": "c2", "plan_review_date": "2099-01-01",
    })
    chain2 = r2.get_json()["review"]["id"]
    client.post(f"/api/reviews/{chain2}/evidence", json={
        "news_title": "证据", "news_url": "https://example.com/ev",
    })
    # Try to delete chain2's evidence from chain1
    ev_id = client.get(f"/api/reviews/{chain2}").get_json()["review"]["evidence"][0]["id"]
    resp = client.delete(f"/api/reviews/{chain1}/evidence/{ev_id}")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "evidence_not_belong"


def test_review_source_snapshot_survives_idea_deletion(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client, "原始想法文本")
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Delete the original idea
    client.delete(f"/api/standalone-ideas/{idea_id}")
    # Review should still be readable with snapshot
    detail = client.get(f"/api/reviews/{chain_id}").get_json()["review"]
    assert detail["source_note"] == "原始想法文本"
    assert detail["source_snapshot"]["source_note"] == "原始想法文本"


def test_review_reminder_decoupled(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    # Create review with reminder
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": True,
    })
    chain_id = r.get_json()["review"]["id"]
    # Find the reminder
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    reminder_id = review_reminders[0]["id"]
    # Delete the reminder
    client.delete(f"/api/reminders/{reminder_id}")
    # Review should be unaffected
    detail = client.get(f"/api/reviews/{chain_id}").get_json()["review"]
    assert detail["status"] == "active"
    assert detail["plan_review_date"] == "2099-01-01"


def test_review_reminder_create_endpoint(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Create reminder via dedicated endpoint
    resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
        "event_date": "2026-08-01",
        "note": "记得回来复盘",
    })
    assert resp.status_code == 200
    assert resp.get_json()["reminder_id"] is not None


def test_review_full_text_search(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client, "新能源政策观察")
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "新能源融资成本将下降", "criteria": "融资成本数据",
        "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Add evidence
    client.post(f"/api/reviews/{chain_id}/evidence", json={
        "news_title": "新能源融资报告", "news_url": "https://example.com/report",
    })
    # Search by judgment text
    r = client.get("/api/reviews?q=融资成本")
    assert r.status_code == 200
    assert r.get_json()["total"] == 1
    # Search by evidence title
    r = client.get("/api/reviews?q=融资报告")
    assert r.get_json()["total"] == 1
    # Search by source note
    r = client.get("/api/reviews?q=新能源政策")
    assert r.get_json()["total"] == 1
    # No match
    r = client.get("/api/reviews?q=完全不相关")
    assert r.get_json()["total"] == 0


def test_review_detail_not_found(tmp_path: Path, monkeypatch):
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    assert client.get("/api/reviews/99999").status_code == 404


def test_review_progress_with_evidence_complete(tmp_path: Path, monkeypatch):
    """Progress with evidence should create both event and evidence atomically."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/progress", json={
        "event_text": "新证据出现",
        "event_date": "2026-07-05",
        "evidence": [
            {"news_title": "证据1", "news_url": "https://example.com/e1"},
            {"news_title": "证据2", "news_url": "https://example.com/e2"},
        ],
    })
    assert resp.status_code == 200
    review = resp.get_json()["review"]
    assert len(review["evidence"]) == 2
    # Evidence should be linked to the progress event
    event_id = review["events"][-1]["id"]
    assert all(ev["event_id"] == event_id for ev in review["evidence"])


def test_review_news_reminders_migration_compatible(tmp_path: Path, monkeypatch):
    """Old reminders without review_chain_id should still work after migration."""
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    # Insert a legacy reminder directly
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """INSERT INTO news_reminders
           (item_id, item_title_snapshot, item_url_snapshot, event_title, event_date,
            remind_at, note, status, created_at, updated_at)
           VALUES (NULL, 'old', 'http://old', 'old event', '2026-07-01',
                   '2026-07-01', '', 'active', '2026-07-01 00:00:00', '2026-07-01 00:00:00')"""
    )
    conn.commit()
    conn.close()
    # Reload and ensure_db again
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "has_secret", lambda name: False)
    app_module.ensure_db()
    client = app_module.app.test_client()
    r = client.get("/api/reminders?filter=all")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(i["event_title"] == "old event" for i in items)


def test_review_create_remind_at_default(tmp_path: Path, monkeypatch):
    """add_reminder with no remind_at should default to plan_review_date 09:00."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": True,
    })
    chain_id = r.get_json()["review"]["id"]
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    assert "09:00" in review_reminders[0]["remind_at"]


def test_review_create_remind_at_custom(tmp_path: Path, monkeypatch):
    """add_reminder with explicit remind_at should use it."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": True,
        "remind_at": "2099-01-01T14:30",
    })
    chain_id = r.get_json()["review"]["id"]
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    assert "14:30" in review_reminders[0]["remind_at"]


def test_review_create_remind_at_invalid(tmp_path: Path, monkeypatch):
    """add_reminder with invalid remind_at should fail."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": True,
        "remind_at": "not-a-time",
    })
    assert r.status_code == 400
    assert r.get_json()["error"] == "invalid_remind_at"


def test_review_create_no_reminder_when_unchecked(tmp_path: Path, monkeypatch):
    """add_reminder=False should not create any reminder."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": False,
    })
    chain_id = r.get_json()["review"]["id"]
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    assert not any(rm.get("review_chain_id") == chain_id for rm in reminders)


def test_review_reminder_endpoint_custom_remind_at(tmp_path: Path, monkeypatch):
    """Dedicated reminder endpoint should accept remind_at."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
        "event_date": "2026-08-01",
        "remind_at": "2026-08-01T10:00",
    })
    assert resp.status_code == 200
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    assert "10:00" in review_reminders[0]["remind_at"]


def test_review_reminder_endpoint_invalid_remind_at(tmp_path: Path, monkeypatch):
    """Dedicated reminder endpoint should reject invalid remind_at."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
        "event_date": "2026-08-01",
        "remind_at": "garbage",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_remind_at"


def test_review_create_remind_at_trailing_garbage(tmp_path: Path, monkeypatch):
    """Trailing characters after YYYY-MM-DDTHH:MM must be rejected."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": True,
        "remind_at": "2099-01-01T14:30abc",
    })
    assert r.status_code == 400
    assert r.get_json()["error"] == "invalid_remind_at"


def test_review_reminder_endpoint_trailing_garbage(tmp_path: Path, monkeypatch):
    """Dedicated reminder endpoint must reject trailing garbage."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
        "event_date": "2026-08-01",
        "remind_at": "2026-08-01T10:00abc",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_remind_at"


def test_review_create_remind_at_semantic_invalid(tmp_path: Path, monkeypatch):
    """Non-existent date/time (e.g. 24:00) must be rejected."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    for bad in ("2099-02-30T09:00", "2099-01-01T24:00", "2099-01-01T09:00+08:00"):
        r = client.post("/api/reviews", json={
            "source_type": "standalone_idea", "source_key": str(idea_id),
            "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
            "add_reminder": True,
            "remind_at": bad,
        })
        assert r.status_code == 400, f"expected 400 for {bad}"
        assert r.get_json()["error"] == "invalid_remind_at"


def test_review_reminder_endpoint_semantic_invalid(tmp_path: Path, monkeypatch):
    """Dedicated endpoint must reject non-existent date/time and seconds."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    for bad in ("2026-02-30T10:00", "2026-08-01T10:00:00", "2026-08-01T24:00"):
        resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
            "event_date": "2026-08-01",
            "remind_at": bad,
        })
        assert resp.status_code == 400, f"expected 400 for {bad}"
        assert resp.get_json()["error"] == "invalid_remind_at"


def test_review_create_remind_at_canonical_format(tmp_path: Path, monkeypatch):
    """Review create should store remind_at in canonical space format."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
        "add_reminder": True,
        "remind_at": "2099-01-01T14:30",
    })
    assert r.status_code == 200
    chain_id = r.get_json()["review"]["id"]
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    assert review_reminders[0]["remind_at"] == "2099-01-01 14:30:00"


def test_review_reminder_endpoint_canonical_format(tmp_path: Path, monkeypatch):
    """Dedicated reminder endpoint should store remind_at in canonical space format."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
        "event_date": "2026-08-01",
        "remind_at": "2026-08-01T10:00",
    })
    assert resp.status_code == 200
    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    assert review_reminders[0]["remind_at"] == "2026-08-01 10:00:00"


def test_review_reminder_is_due_with_canonical_format(tmp_path: Path, monkeypatch):
    """A reminder set to a past time today must be marked is_due in the list and SQL summary."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "j", "criteria": "c", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Pick a time one hour ago to guarantee it is past, while still using today's date.
    now = datetime.now()
    past = now - timedelta(hours=1)
    remind_at_str = past.strftime("%Y-%m-%dT%H:%M")
    resp = client.post(f"/api/reviews/{chain_id}/reminders", json={
        "event_date": past.strftime("%Y-%m-%d"),
        "remind_at": remind_at_str,
    })
    assert resp.status_code == 200

    reminders = client.get("/api/reminders?filter=all").get_json()["items"]
    review_reminders = [rm for rm in reminders if rm.get("review_chain_id") == chain_id]
    assert len(review_reminders) == 1
    assert review_reminders[0]["is_due"] is True
    # The SQL-level summary should also reflect at least one due reminder.
    summary = client.get("/api/reminders").get_json()["summary"]
    assert summary["due_total"] >= 1


def test_review_search_snapshot_news_title(tmp_path: Path, monkeypatch):
    """Full-text search should find reviews by snapshot-associated news title."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    _create_article_note(client, "https://example.com/review-test", "新闻想法备注")
    r = client.post("/api/reviews", json={
        "source_type": "article_note", "source_key": "https://example.com/review-test",
        "judgment": "判断A", "criteria": "标准A", "plan_review_date": "2099-01-01",
    })
    assert r.status_code == 200
    # The snapshot should contain the news title "复盘测试新闻"
    r = client.get("/api/reviews?q=复盘测试新闻")
    assert r.get_json()["total"] == 1


def test_review_search_snapshot_news_summary(tmp_path: Path, monkeypatch):
    """Full-text search should find reviews by snapshot-associated news summary."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    _create_article_note(client, "https://example.com/review-test", "新闻想法备注")
    r = client.post("/api/reviews", json={
        "source_type": "article_note", "source_key": "https://example.com/review-test",
        "judgment": "判断B", "criteria": "标准B", "plan_review_date": "2099-01-01",
    })
    assert r.status_code == 200
    # The snapshot should contain the news summary "新能源政策即将出台"
    r = client.get("/api/reviews?q=新能源政策即将出台")
    assert r.get_json()["total"] == 1


def test_review_search_evidence_url(tmp_path: Path, monkeypatch):
    """Full-text search should find reviews by evidence URL."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client)
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "判断C", "criteria": "标准C", "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    client.post(f"/api/reviews/{chain_id}/evidence", json={
        "news_title": "证据标题",
        "news_url": "https://evidence-test-url.example.com/unique",
    })
    r = client.get("/api/reviews?q=evidence-test-url")
    assert r.get_json()["total"] == 1


def test_review_search_no_duplicate(tmp_path: Path, monkeypatch):
    """Search results should not duplicate reviews even with multiple matches."""
    client, _ = _setup_review_env(tmp_path, monkeypatch)
    idea_id = _create_standalone_idea(client, "新能源政策观察")
    r = client.post("/api/reviews", json={
        "source_type": "standalone_idea", "source_key": str(idea_id),
        "judgment": "新能源融资成本将下降", "criteria": "融资成本数据",
        "plan_review_date": "2099-01-01",
    })
    chain_id = r.get_json()["review"]["id"]
    # Add evidence that also matches the search term
    client.post(f"/api/reviews/{chain_id}/evidence", json={
        "news_title": "新能源融资报告", "news_url": "https://example.com/report",
    })
    r = client.get("/api/reviews?q=新能源")
    assert r.get_json()["total"] == 1
    assert len(r.get_json()["items"]) == 1



def test_review_create_function_loads_in_global_scope():
    """Review creation must remain callable after the front-end script has loaded."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) {
  throw new Error("front-end bootstrap marker missing");
}
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by scope regression test");

const noop = () => {};
const element = new Proxy(noop, {
  get(target, prop) {
    if (["addEventListener", "removeEventListener", "appendChild", "removeChild", "setAttribute", "removeAttribute", "focus", "blur", "click"].includes(prop)) return noop;
    if (["querySelectorAll", "getElementsByTagName"].includes(prop)) return () => [];
    if (prop === "querySelector") return () => element;
    if (prop === "classList") return { add: noop, remove: noop, toggle: noop, contains: () => false };
    if (prop === "style" || prop === "dataset") return element;
    if (prop === "children" || prop === "options") return [];
    if (prop === "length") return 0;
    if (["value", "textContent", "innerHTML", "className"].includes(prop)) return "";
    if (prop === "checked" || prop === "disabled") return false;
    if (prop === Symbol.iterator) return function* () {};
    return element;
  },
  set() { return true; },
  apply() { return undefined; },
});
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const document = {
  getElementById: () => element,
  querySelector: () => element,
  querySelectorAll: () => [],
  createElement: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
const requests = [];
const fetch = async (url, init = {}) => {
  requests.push([url, init]);
  const isReviewCreate = url === "/api/reviews" && init.method === "POST";
  return {
    ok: true,
    json: async () => isReviewCreate
      ? { ok: true, review: { id: "new-review" } }
      : { ok: true, items: [], summary: {}, page: 1, pages: 1, total: 0, has_more: false },
  };
};
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

(async () => {
  if (typeof context.createReview !== "function") {
    throw new Error(`createReview type=${typeof context.createReview}`);
  }
  const review = await context.createReview({ source_type: "standalone_idea", source_key: "1" });
  if (review.id !== "new-review") throw new Error("createReview response was not returned");
  if (!requests.some(([url, init]) => url === "/api/reviews" && init.method === "POST")) {
    throw new Error("createReview did not issue POST /api/reviews");
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_article_highlights_api_persists_validates_and_reanchors(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年8月"
    daily_dir.mkdir(parents=True)
    first_url = "https://example.com/highlight-one"
    second_url = "https://example.com/highlight-two"
    (daily_dir / "dailyFreshNews_2026-08-07.md").write_text(
        f"""## Reuters · World（2条）
### [高亮新闻一]({first_url})
- 发布时间：2026-08-07 09:00:00
### [高亮新闻二]({second_url})
- 发布时间：2026-08-07 08:00:00
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
    items = client.get("/api/news?per=20&read_filter=all").get_json()["items"]
    by_url = {item["url"]: item for item in items}
    first = by_url[first_url]
    second = by_url[second_url]
    body = "第一句中文。\n第二句需要标记。\n第三句。"
    ts = app_module.now_ts()
    start = body.index("第二句需要标记。")
    end = start + len("第二句需要标记。")

    with app_module.db_conn() as conn:
        conn.execute(
            """
            INSERT INTO article_details(
              url, source, title, author, published_at, content, content_length,
              raw_json, fetched_at, updated_at
            ) VALUES (?, 'Reuters', '高亮新闻一', '作者', '2026-08-07', ?, ?, '{}', ?, ?)
            """,
            (first_url, "English source body", len("English source body"), ts, ts),
        )
        conn.execute(
            """
            INSERT INTO article_ai(
              url, model, key_points_zh, conclusion_zh, body_zh, raw_json,
              generated_at, updated_at
            ) VALUES (?, 'test', ?, '最后总结段', ?, '{}', ?, ?)
            """,
            (first_url, json.dumps(["要点一内容", "第二个要点"], ensure_ascii=False), body, ts, ts),
        )
        conn.execute(
            """
            INSERT INTO ai_jobs(url, status, attempts, finished_at, updated_at)
            VALUES (?, 'success', 1, ?, ?)
            """,
            (first_url, ts, ts),
        )
        conn.commit()

    detail = client.get(f"/api/news/{first['id']}/detail").get_json()
    assert detail["highlight_body_ready"] is True
    assert detail["highlights"] == []
    assert detail["highlight_summary"] == {"active": 0, "orphan": 0, "total": 0}

    created = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "body_kind": "ai_zh",
            "start_offset": start,
            "end_offset": end,
            "selected_text": "第二句需要标记。",
        },
    )
    assert created.status_code == 201
    created_payload = created.get_json()
    assert created_payload["highlight"]["status"] == "active"
    highlight_id = created_payload["highlight"]["id"]
    assert created_payload["highlight"]["color"] == "yellow"
    assert created_payload["highlight"]["annotation_text"] == ""
    assert created_payload["highlight"]["content_hash"] == app_module.article_highlight_content_hash(body)

    annotation_get = client.get(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation"
    )
    assert annotation_get.status_code == 200
    assert annotation_get.get_json()["annotation_text"] == ""
    annotation_saved = client.put(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation",
        json={"annotation_text": "  先记录这段判断  "},
    )
    assert annotation_saved.status_code == 200
    assert annotation_saved.get_json()["highlight"]["annotation_text"] == "先记录这段判断"
    assert annotation_saved.get_json()["highlight"]["updated_at"]
    annotation_edited = client.put(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation",
        json={"annotation_text": "修改后的纯文本批注"},
    )
    assert annotation_edited.status_code == 200
    assert annotation_edited.get_json()["highlight"]["annotation_text"] == "修改后的纯文本批注"
    invalid_annotation_type = client.put(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation",
        json={"annotation_text": ["不允许"]},
    )
    assert invalid_annotation_type.status_code == 400
    assert invalid_annotation_type.get_json()["error"] == "invalid_annotation_type"
    empty_annotation = client.put(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation",
        json={"annotation_text": "  \n  "},
    )
    assert empty_annotation.status_code == 400
    assert empty_annotation.get_json()["error"] == "empty_annotation"
    too_long_annotation = client.put(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation",
        json={"annotation_text": "字" * 2001},
    )
    assert too_long_annotation.status_code == 400
    assert too_long_annotation.get_json()["error"] == "annotation_too_long"

    recolored = client.patch(
        f"/api/news/{first['id']}/highlights/{highlight_id}",
        json={"color": "green"},
    )
    assert recolored.status_code == 200
    assert recolored.get_json()["highlight"]["color"] == "green"

    same_hash = client.get(f"/api/news/{first['id']}/highlights").get_json()
    assert same_hash["highlights"][0]["resolved_start_offset"] == start
    assert same_hash["highlights"][0]["resolved_end_offset"] == end
    assert same_hash["highlights"][0]["color"] == "green"
    assert same_hash["highlights"][0]["annotation_text"] == "修改后的纯文本批注"

    annotation_cleared = client.delete(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation"
    )
    assert annotation_cleared.status_code == 200
    assert annotation_cleared.get_json()["highlight"]["id"] == highlight_id
    assert annotation_cleared.get_json()["highlight"]["annotation_text"] == ""
    assert client.get(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation"
    ).get_json()["annotation_text"] == ""

    points_body = "要点一内容第二个要点"
    points_start = points_body.index("第二个要点")
    points_end = points_start + len("第二个要点")
    points_created = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "body_kind": "ai_points_zh",
            "color": "blue",
            "start_offset": points_start,
            "end_offset": points_end,
            "selected_text": "第二个要点",
        },
    )
    assert points_created.status_code == 201
    points_payload = points_created.get_json()
    assert points_payload["highlight"]["body_kind"] == "ai_points_zh"
    assert points_payload["highlight"]["color"] == "blue"
    points_id = points_payload["highlight"]["id"]
    assert points_payload["highlight_surfaces"]["ai_points_zh"]["highlights"][0]["status"] == "active"
    points_annotation = client.put(
        f"/api/news/{first['id']}/highlights/{points_id}/annotation",
        json={"annotation_text": "要点批注"},
    )
    assert points_annotation.status_code == 200
    assert points_annotation.get_json()["highlight"]["annotation_text"] == "要点批注"
    points_list = client.get(f"/api/news/{first['id']}/highlights?body_kind=ai_points_zh").get_json()
    assert points_list["body_kind"] == "ai_points_zh"
    assert points_list["highlights"][0]["color"] == "blue"
    with app_module.db_conn() as conn:
        conn.execute(
            "UPDATE article_ai SET key_points_zh=?, updated_at=? WHERE url=?",
            (json.dumps(["前置要点", "要点一内容", "第二个要点"], ensure_ascii=False), app_module.now_ts(), first_url),
        )
        conn.commit()
    points_reanchored = client.get(f"/api/news/{first['id']}/highlights?body_kind=ai_points_zh").get_json()
    assert points_reanchored["highlight_summary"] == {"active": 1, "orphan": 0, "total": 1}
    assert points_reanchored["highlights"][0]["resolved_start_offset"] == len("前置要点要点一内容")

    conclusion_body = "最后总结段"
    conclusion_start = 0
    conclusion_end = len(conclusion_body)
    conclusion_created = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "body_kind": "ai_conclusion_zh",
            "color": "pink",
            "start_offset": conclusion_start,
            "end_offset": conclusion_end,
            "selected_text": conclusion_body,
        },
    )
    assert conclusion_created.status_code == 201
    conclusion_payload = conclusion_created.get_json()
    assert conclusion_payload["highlight"]["body_kind"] == "ai_conclusion_zh"
    assert conclusion_payload["highlight"]["color"] == "pink"
    conclusion_id = conclusion_payload["highlight"]["id"]
    assert conclusion_payload["highlight_surfaces"]["ai_conclusion_zh"]["highlights"][0]["status"] == "active"
    conclusion_annotation = client.put(
        f"/api/news/{first['id']}/highlights/{conclusion_id}/annotation",
        json={"annotation_text": "总结批注"},
    )
    assert conclusion_annotation.status_code == 200
    assert conclusion_annotation.get_json()["highlight"]["annotation_text"] == "总结批注"
    conclusion_list = client.get(
        f"/api/news/{first['id']}/highlights?body_kind=ai_conclusion_zh"
    ).get_json()
    assert conclusion_list["body_kind"] == "ai_conclusion_zh"
    assert conclusion_list["highlights"][0]["selected_text"] == conclusion_body
    deleted_annotated_highlight = client.delete(
        f"/api/news/{first['id']}/highlights/{conclusion_id}"
    )
    assert deleted_annotated_highlight.status_code == 200
    assert client.get(
        f"/api/news/{first['id']}/highlights/{conclusion_id}/annotation"
    ).status_code == 404

    invalid_color = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "body_kind": "ai_points_zh",
            "color": "rainbow",
            "start_offset": 0,
            "end_offset": 2,
            "selected_text": "要点",
        },
    )
    assert invalid_color.status_code == 400
    assert invalid_color.get_json()["error"] == "invalid_color"

    invalid_recolor = client.patch(
        f"/api/news/{first['id']}/highlights/{highlight_id}",
        json={"color": "rainbow"},
    )
    assert invalid_recolor.status_code == 400
    assert invalid_recolor.get_json()["error"] == "invalid_color"

    invalid_body_kind = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "body_kind": ["ai_zh"],
            "start_offset": 0,
            "end_offset": 2,
            "selected_text": "要点",
        },
    )
    assert invalid_body_kind.status_code == 400
    assert invalid_body_kind.get_json()["error"] == "invalid_body_kind"

    invalid_offset = client.post(
        f"/api/news/{first['id']}/highlights",
        json={"start_offset": -1, "end_offset": 2, "selected_text": "第一"},
    )
    assert invalid_offset.status_code == 400
    assert invalid_offset.get_json()["error"] == "invalid_offset"
    mismatch = client.post(
        f"/api/news/{first['id']}/highlights",
        json={"start_offset": start, "end_offset": end, "selected_text": "错误选区"},
    )
    assert mismatch.status_code == 400
    assert mismatch.get_json()["error"] == "selected_text_mismatch"
    overlap_text = body[start + 1 : end + 1]
    overlap = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "start_offset": start + 1,
            "end_offset": end + 1,
            "selected_text": overlap_text,
        },
    )
    assert overlap.status_code == 409
    assert overlap.get_json()["error"] == "highlight_overlap"

    not_ready = client.post(
        f"/api/news/{second['id']}/highlights",
        json={"start_offset": 0, "end_offset": 1, "selected_text": "高"},
    )
    assert not_ready.status_code == 409
    assert not_ready.get_json()["error"] == "body_not_ready"
    cross_news_delete = client.delete(f"/api/news/{second['id']}/highlights/{highlight_id}")
    assert cross_news_delete.status_code == 404
    assert cross_news_delete.get_json()["error"] == "highlight_not_found"
    cross_news_annotation = client.put(
        f"/api/news/{second['id']}/highlights/{highlight_id}/annotation",
        json={"annotation_text": "越权"},
    )
    assert cross_news_annotation.status_code == 404
    assert cross_news_annotation.get_json()["error"] == "highlight_not_found"
    cross_news_recolor = client.patch(
        f"/api/news/{second['id']}/highlights/{highlight_id}",
        json={"color": "pink"},
    )
    assert cross_news_recolor.status_code == 404
    assert cross_news_recolor.get_json()["error"] == "highlight_not_found"

    with app_module.db_conn() as conn:
        conn.execute("SELECT body_zh FROM article_ai WHERE url=?", (first_url,)).fetchone()
        original_ai = conn.execute("SELECT body_zh FROM article_ai WHERE url=?", (first_url,)).fetchone()["body_zh"]
        original_detail = conn.execute("SELECT content FROM article_details WHERE url=?", (first_url,)).fetchone()["content"]
        assert original_ai == body
        assert original_detail == "English source body"

    deleted = client.delete(f"/api/news/{first['id']}/highlights/{highlight_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["highlights"] == []
    deleted_annotation = client.get(
        f"/api/news/{first['id']}/highlights/{highlight_id}/annotation"
    )
    assert deleted_annotation.status_code == 404

    reanchor_body = "甲乙丙丁\n唯一句子\n收尾"
    reanchor_start = reanchor_body.index("唯一句子")
    reanchor_end = reanchor_start + len("唯一句子")
    with app_module.db_conn() as conn:
        conn.execute(
            "UPDATE article_ai SET body_zh=?, updated_at=? WHERE url=?",
            (reanchor_body, app_module.now_ts(), first_url),
        )
        conn.execute(
            "UPDATE ai_jobs SET status='success', updated_at=? WHERE url=?",
            (app_module.now_ts(), first_url),
        )
        conn.commit()
    created = client.post(
        f"/api/news/{first['id']}/highlights",
        json={
            "start_offset": reanchor_start,
            "end_offset": reanchor_end,
            "selected_text": "唯一句子",
        },
    )
    assert created.status_code == 201
    reanchor_id = created.get_json()["highlight"]["id"]
    reanchor_annotation = client.put(
        f"/api/news/{first['id']}/highlights/{reanchor_id}/annotation",
        json={"annotation_text": "重定位后仍应保留"},
    )
    assert reanchor_annotation.status_code == 200
    with app_module.db_conn() as conn:
        conn.execute(
            "UPDATE article_ai SET body_zh=?, updated_at=? WHERE url=?",
            ("前缀\n" + reanchor_body + "\n后缀", app_module.now_ts(), first_url),
        )
        conn.commit()
    reanchored = client.get(f"/api/news/{first['id']}/highlights").get_json()
    assert reanchored["highlight_summary"] == {"active": 1, "orphan": 0, "total": 1}
    assert reanchored["highlights"][0]["id"] == reanchor_id
    assert reanchored["highlights"][0]["resolved_start_offset"] == len("前缀\n甲乙丙丁\n")
    assert reanchored["highlights"][0]["annotation_text"] == "重定位后仍应保留"

    with app_module.db_conn() as conn:
        conn.execute(
            "UPDATE article_ai SET body_zh=?, updated_at=? WHERE url=?",
            (
                "甲乙丙丁\n唯一句子\n收尾\n甲乙丙丁\n唯一句子\n收尾",
                app_module.now_ts(),
                first_url,
            ),
        )
        conn.commit()
    ambiguous = client.get(f"/api/news/{first['id']}/highlights").get_json()
    assert ambiguous["highlight_summary"] == {"active": 0, "orphan": 1, "total": 1}
    assert ambiguous["highlights"][0]["status"] == "orphan"

    with app_module.db_conn() as conn:
        conn.execute(
            "UPDATE ai_jobs SET status='running', updated_at=? WHERE url=?",
            (app_module.now_ts(), first_url),
        )
        conn.commit()
    pending = client.get(f"/api/news/{first['id']}/highlights").get_json()
    assert pending["body_ready"] is False
    assert pending["highlights"] == []


def test_article_highlights_schema_migrates_legacy_body_kind_and_color(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "legacy-highlights.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE article_highlights (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              url TEXT NOT NULL,
              body_kind TEXT NOT NULL DEFAULT 'ai_zh' CHECK (body_kind = 'ai_zh'),
              content_hash TEXT NOT NULL,
              start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
              end_offset INTEGER NOT NULL CHECK (end_offset > start_offset),
              selected_text TEXT NOT NULL CHECK (length(selected_text) > 0),
              prefix TEXT NOT NULL DEFAULT '',
              suffix TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (url, body_kind, content_hash, start_offset, end_offset)
            );
            INSERT INTO article_highlights(
              url, body_kind, content_hash, start_offset, end_offset,
              selected_text, prefix, suffix, created_at, updated_at
            ) VALUES ('https://example.com/legacy', 'ai_zh', 'hash', 0, 2, '旧', '', '', 'now', 'now');
            """
        )

    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    with app_module.db_conn() as conn:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='article_highlights'"
        ).fetchone()[0]
        columns = {row[1] for row in conn.execute("PRAGMA table_info(article_highlights)").fetchall()}
        row = conn.execute("SELECT body_kind, color FROM article_highlights").fetchone()
    assert "ai_points_zh" in table_sql
    assert "ai_conclusion_zh" in table_sql
    assert "twitter_detail" in table_sql
    assert "color" in columns
    assert "annotation_text" in columns
    row = conn.execute("SELECT body_kind, color, annotation_text FROM article_highlights").fetchone()
    assert tuple(row) == ("ai_zh", "yellow", "")


def test_twitter_detail_highlights_use_stable_article_detail_and_gate_ordinary_news(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "twitter-highlights.sqlite3"
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    ts = app_module.now_ts()
    twitter_id = "twitter-highlight-item"
    twitter_url = "https://x.com/example/status/123"
    missing_id = "twitter-highlight-missing"
    missing_url = "https://x.com/example/status/456"
    ordinary_id = "ordinary-highlight-item"
    ordinary_url = "https://example.com/ordinary-highlight"
    body = "推文开头\n唯一推文片段\n推文结尾"
    selected = "唯一推文片段"
    start = body.index(selected)
    end = start + len(selected)

    with app_module.db_conn() as conn:
        for item_id, url, source_type, title in (
            (twitter_id, twitter_url, "twitter", "推文高亮"),
            (missing_id, missing_url, "twitter", "无正文推文"),
            (ordinary_id, ordinary_url, "rss", "普通新闻"),
        ):
            conn.execute(
                """
                INSERT INTO items(
                  id, source_file, item_order, published_at, date, time,
                  source, source_type, source_name, title, summary, url,
                  created_at, updated_at
                ) VALUES (?, 'test.md', 1, '2026-08-10 10:00', '2026-08-10', '10:00',
                          'test', ?, 'test', ?, '', ?, ?, ?)
                """,
                (item_id, source_type, title, url, ts, ts),
            )
        for url, title, content in (
            (twitter_url, "推文高亮", body),
            (ordinary_url, "普通新闻", "Ordinary source body"),
        ):
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content, content_length,
                  raw_json, fetched_at, updated_at
                ) VALUES (?, 'test', ?, '', '2026-08-10', ?, ?, '{}', ?, ?)
                """,
                (url, title, content, len(content), ts, ts),
            )
        conn.commit()

    missing = client.post(
        f"/api/news/{missing_id}/highlights",
        json={
            "body_kind": "twitter_detail",
            "start_offset": 0,
            "end_offset": 1,
            "selected_text": "缺",
        },
    )
    assert missing.status_code == 409
    assert missing.get_json()["error"] == "body_not_ready"

    ordinary = client.post(
        f"/api/news/{ordinary_id}/highlights",
        json={
            "body_kind": "twitter_detail",
            "start_offset": 0,
            "end_offset": 8,
            "selected_text": "Ordinary",
        },
    )
    assert ordinary.status_code == 409
    assert ordinary.get_json()["error"] == "body_not_ready"

    created = client.post(
        f"/api/news/{twitter_id}/highlights",
        json={
            "body_kind": "twitter_detail",
            "color": "blue",
            "start_offset": start,
            "end_offset": end,
            "selected_text": selected,
        },
    )
    assert created.status_code == 201
    payload = created.get_json()
    highlight_id = payload["highlight"]["id"]
    assert payload["highlight"]["body_kind"] == "twitter_detail"
    assert payload["highlight"]["color"] == "blue"
    assert payload["highlight_surfaces"]["twitter_detail"]["body_ready"] is True

    overlap = client.post(
        f"/api/news/{twitter_id}/highlights",
        json={
            "body_kind": "twitter_detail",
            "start_offset": start + 1,
            "end_offset": end,
            "selected_text": selected[1:],
        },
    )
    assert overlap.status_code == 409
    assert overlap.get_json()["error"] == "highlight_overlap"

    recolored = client.patch(
        f"/api/news/{twitter_id}/highlights/{highlight_id}",
        json={"color": "pink"},
    )
    assert recolored.status_code == 200
    assert recolored.get_json()["highlight"]["color"] == "pink"

    annotated = client.put(
        f"/api/news/{twitter_id}/highlights/{highlight_id}/annotation",
        json={"annotation_text": "推文批注"},
    )
    assert annotated.status_code == 200
    assert annotated.get_json()["highlight"]["annotation_text"] == "推文批注"

    listed = client.get(
        f"/api/news/{twitter_id}/highlights?body_kind=twitter_detail"
    ).get_json()
    assert listed["body_kind"] == "twitter_detail"
    assert listed["highlights"][0]["annotation_text"] == "推文批注"

    with app_module.db_conn() as conn:
        conn.execute(
            "UPDATE article_details SET content=?, content_length=?, updated_at=? WHERE url=?",
            ("新增前缀\n" + body, len("新增前缀\n" + body), app_module.now_ts(), twitter_url),
        )
        conn.commit()
    reanchored = client.get(
        f"/api/news/{twitter_id}/highlights?body_kind=twitter_detail"
    ).get_json()
    assert reanchored["highlights"][0]["status"] == "active"
    assert reanchored["highlights"][0]["resolved_start_offset"] == len("新增前缀\n推文开头\n")

    with app_module.db_conn() as conn:
        ambiguous_body = body + "\n" + body
        conn.execute(
            "UPDATE article_details SET content=?, content_length=?, updated_at=? WHERE url=?",
            (ambiguous_body, len(ambiguous_body), app_module.now_ts(), twitter_url),
        )
        conn.commit()
    orphaned = client.get(
        f"/api/news/{twitter_id}/highlights?body_kind=twitter_detail"
    ).get_json()
    assert orphaned["highlights"][0]["status"] == "orphan"

    deleted = client.delete(f"/api/news/{twitter_id}/highlights/{highlight_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["highlight_surfaces"]["twitter_detail"]["highlights"] == []


def test_frontend_article_highlight_contract_and_version():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")
    render_source = app_source.split("function renderDetail(item", 1)[1].split("function renderDetailMediaGallery", 1)[0]

    assert "News Reader v2.1.4.2" in app_source
    assert "News Reader v2.1.4.2" in index_source
    assert "/static/style.css?v=2.1.4.2" in index_source
    assert "/static/app.js?v=2.1.4.2" in index_source
    assert 'id="detailHighlightPopover"' in index_source
    assert 'id="detailHighlightActionBtn"' not in index_source
    assert 'id="detailHighlightColorButtons"' in index_source
    assert 'data-highlight-color="yellow"' in index_source
    assert 'data-highlight-color="green"' in index_source
    assert 'data-highlight-color="blue"' in index_source
    assert 'data-highlight-color="pink"' in index_source
    assert index_source.count('class="detail-highlight-color-button"') == 4
    assert 'aria-pressed="false"' in index_source
    assert "detailHighlightSelectedColor: null" in app_source
    assert 'type="color"' not in index_source
    assert 'id="detailHighlightColorSelect"' not in index_source
    assert "ai_points_zh" in app_source
    assert "twitter_detail" in app_source
    assert "annotation_text" in app_source
    assert 'id="detailHighlightAnnotationPopover"' in index_source
    assert 'id="detailHighlightAnnotationInput"' in index_source
    assert 'id="detailHighlightAnnotationView"' in index_source
    assert 'id="detailHighlightAnnotationEditBtn"' in index_source
    assert 'id="detailHighlightAnnotationActionBtn"' in index_source
    assert "article-highlight-annotation-button" in app_source
    assert 'state.detailHighlightAnnotationMode = annotation.trim() ? "view" : "edit"' in app_source
    assert 'annotationButton.setAttribute("aria-label", "查看高亮批注")' in app_source
    assert "if (hasAnnotation) {" in app_source
    assert 'action?.type === "remove"' in app_source
    assert "preserveHighlightAnnotationEditor" in render_source
    assert 'document.addEventListener("pointerdown"' in app_source
    assert 'document.addEventListener("scroll"' in app_source
    assert 'document.addEventListener("touchmove"' in app_source
    assert "dismissDetailHighlightTransientUi" in app_source
    assert "detailHighlightAnnotationRequestToken" in app_source
    assert "ai_conclusion_zh" in app_source
    assert "runDetailHighlightColorChange" in app_source
    assert "detailHighlightColorButtons" in app_source
    assert 'method: "PATCH"' in app_source
    assert "runDetailHighlightAction();" in app_source
    assert "为选中文本添加高亮？" not in app_source
    assert "取消这段高亮？" not in app_source
    assert "article-highlight" in app_source
    assert "createElement(\"mark\")" in app_source
    assert "contentEl.replaceChildren()" in app_source
    assert "contentEl.innerHTML" not in render_source
    assert "contenteditable" not in index_source.lower()
    assert ".detail-content mark.article-highlight" in style_source
    assert ".detail-highlight-popover" in style_source


def test_frontend_original_article_selection_is_agent_only():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    original_selection = app_source.split("function detailSelectionRangeSurface", 1)[1].split(
        "function updateDetailHighlightSelection", 1
    )[0]
    assert 'const DETAIL_ORIGINAL_AGENT_BODY_KIND = "original_detail"' in app_source
    assert "detailOriginalAgentEligible" in app_source
    assert 'detailOriginalContent.addEventListener("mouseup", scheduleDetailHighlightSelectionUpdate)' in app_source
    assert "askOnly: true" in original_selection
    assert 'action: { type: "ask", bodyKind: surface.bodyKind, ...offsets }' in app_source
    assert 'if (surface.askOnly)' in app_source
    assert '["create", "ask"].includes(action?.type)' in app_source
    assert '[DETAIL_ORIGINAL_AGENT_BODY_KIND]: "英文原文引用"' in app_source
    assert 'action?.type === "create" || action?.type === "remove"' in app_source


def test_frontend_highlight_annotation_save_failure_preserves_edit_state():
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by annotation failure regression test");
source = source.replace("let state = {", "var state = {");

const noop = () => {};
const element = new Proxy(noop, {
  get(target, prop) {
    if (["addEventListener", "removeEventListener", "appendChild", "removeChild", "replaceChildren", "setAttribute", "removeAttribute", "focus", "blur", "click", "scrollTo"].includes(prop)) return noop;
    if (["querySelectorAll", "getElementsByTagName"].includes(prop)) return () => [];
    if (prop === "querySelector" || prop === "closest") return () => element;
    if (prop === "contains") return () => false;
    if (prop === "classList") return { add: noop, remove: noop, toggle: noop, contains: () => false };
    if (prop === "style" || prop === "dataset") return element;
    if (prop === "children" || prop === "options") return [];
    if (prop === "length" || prop === "scrollTop" || prop === "scrollHeight" || prop === "clientHeight") return 0;
    if (["value", "textContent", "innerHTML", "className"].includes(prop)) return "";
    if (prop === "checked" || prop === "disabled" || prop === "open") return false;
    if (prop === Symbol.iterator) return function* () {};
    return element;
  },
  set() { return true; },
  apply() { return undefined; },
});
let focusCount = 0;
const annotationInput = {
  value: "失败后必须保留的草稿",
  disabled: false,
  classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  addEventListener: noop,
  focus: () => { focusCount += 1; },
};
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const document = {
  getElementById: (id) => id === "detailHighlightAnnotationInput" ? annotationInput : element,
  querySelector: () => element,
  querySelectorAll: () => [],
  createElement: () => element,
  createTextNode: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
const fetch = async () => ({
  ok: false,
  json: async () => ({ ok: false, error: "annotation_save_failed" }),
});
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  innerHeight: 800,
  localStorage,
  getSelection: () => ({ removeAllRanges: noop }),
};
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

(async () => {
  context.state.selectedId = "news-1";
  context.state.itemsById.set("news-1", { id: "news-1", url: "https://example.com/news-1" });
  context.state.detailHighlightAnnotationOpen = true;
  context.state.detailHighlightAnnotationMode = "edit";
  context.state.detailHighlightAnnotationHighlightId = 7;
  context.state.detailHighlightAnnotationBodyKind = "ai_zh";
  context.state.detailHighlightAnnotationDraft = "原草稿";
  context.state.detailHighlightAnnotationOriginal = "原批注";
  annotationInput.value = "失败后必须保留的草稿";
  await context.runDetailHighlightAnnotationSave();
  if (!context.state.detailHighlightAnnotationOpen) throw new Error("failure closed the annotation surface");
  if (context.state.detailHighlightAnnotationMode !== "edit") throw new Error("failure left edit mode");
  if (context.state.detailHighlightAnnotationOriginal !== "原批注") throw new Error("failure replaced the saved annotation");
  if (context.state.detailHighlightAnnotationDraft !== "失败后必须保留的草稿") throw new Error("failure lost the draft");
  if (context.state.detailHighlightAnnotationBusy) throw new Error("failure left the editor busy");
  if (focusCount < 1) throw new Error("failure did not restore textarea focus");
  const requestToken = context.state.detailHighlightAnnotationRequestToken;
  context.dismissDetailHighlightTransientUi();
  if (context.state.detailHighlightAnnotationOpen) throw new Error("outside dismissal left the editor open");
  if (context.state.detailHighlightAnnotationMode !== "") throw new Error("outside dismissal kept edit mode");
  if (context.state.detailHighlightAnnotationDraft !== "") throw new Error("outside dismissal kept the unsaved draft");
  if (context.state.detailHighlightAnnotationOriginal !== "") throw new Error("outside dismissal kept stale annotation state");
  if (context.state.detailHighlightAnnotationHighlightId !== null) throw new Error("outside dismissal kept the highlight target");
  if (context.state.detailHighlightAnnotationRequestToken !== requestToken + 1) throw new Error("outside dismissal did not invalidate late requests");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)

def test_review_timeline_criteria_empty_not_rendered():
    """Criteria must not render an empty '成立标准：' tag when criteria is blank."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) {
  throw new Error("front-end bootstrap marker missing");
}
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by criteria render regression test");
source = source.replace("let state = {", "var state = {");

function makeElement(tag) {
  const children = [];
  const el = {
    tagName: tag,
    className: "",
    textContent: "",
    innerHTML: "",
    dataset: {},
    style: {},
    classList: {
      add: (c) => { el.className += (el.className ? " " : "") + c; },
      remove: (c) => { el.className = el.className.split(" ").filter(x => x !== c).join(" "); },
      toggle: (c, force) => { force ? el.classList.add(c) : el.classList.remove(c); },
      contains: (c) => el.className.split(" ").includes(c),
    },
    appendChild: (child) => { children.push(child); return child; },
    removeChild: (child) => { const i = children.indexOf(child); if (i >= 0) children.splice(i, 1); return child; },
    remove: () => {},
    querySelector: (sel) => query(el, sel),
    querySelectorAll: (sel) => queryAll(el, sel),
    addEventListener: () => {},
    removeEventListener: () => {},
    setAttribute: (k, v) => { el[k] = v; },
    removeAttribute: (k) => { delete el[k]; },
    focus: () => {},
    blur: () => {},
    click: () => {},
    get children() { return children; },
  };
  return el;
}

function query(root, sel) {
  const parts = sel.split(/[.>#]/).filter(Boolean);
  const cls = sel.includes(".") ? sel.split(".")[1] : null;
  for (const c of root.children) {
    if (cls && c.className.split(" ").includes(cls)) return c;
    const r = query(c, sel); if (r) return r;
  }
  return null;
}
function queryAll(root, sel) {
  const cls = sel.includes(".") ? sel.split(".")[1] : null;
  let out = [];
  for (const c of root.children) {
    if (cls && c.className.split(" ").includes(cls)) out.push(c);
    out = out.concat(queryAll(c, sel));
  }
  return out;
}

const root = makeElement("div");
const detailReviewTimeline = root;
const detailReviewBody = makeElement("div");
const detailReviewSourceInfo = makeElement("div");

document = {
  getElementById: (id) => {
    if (id === "detailReviewTimeline") return detailReviewTimeline;
    if (id === "detailReviewBody") return detailReviewBody;
    if (id === "detailReviewSourceInfo") return detailReviewSourceInfo;
    return makeElement("div");
  },
  querySelector: () => makeElement("div"),
  querySelectorAll: () => [],
  createElement: (tag) => makeElement(tag),
  addEventListener: () => {},
  body: makeElement("body"),
  documentElement: makeElement("html"),
};

const noop = () => {};
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout, clearTimeout, setInterval, clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const context = {
  console, document, window, localStorage, IntersectionObserver,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

context.renderReviewTimeline({
  versions: [
    { version_no: 1, judgment: "V1", criteria: "", revision_reason: "" },
    { version_no: 2, judgment: "V2", criteria: "标准", revision_reason: "修正" },
  ],
  events: [],
});

const criteriaEls = queryAll(detailReviewTimeline, ".review-timeline-criteria");
if (criteriaEls.length !== 1) {
  throw new Error(`expected exactly 1 criteria element, got ${criteriaEls.length}`);
}
if (criteriaEls[0].textContent !== "成立标准：标准") {
  throw new Error(`unexpected criteria text: ${criteriaEls[0].textContent}`);
}
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_review_create_cancel_restores_news_detail_from_any_collection():
    """Canceling '加入复盘' from a non-feed news collection should restore the news detail."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) {
  throw new Error("front-end bootstrap marker missing");
}
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by cancel restore regression test");
source = source.replace("let state = {", "var state = {");

function makeButton() {
  const listeners = [];
  return {
    addEventListener: (type, fn) => { listeners.push([type, fn]); },
    removeEventListener: () => {},
    click: () => { listeners.filter(([t]) => t === "click").forEach(([, fn]) => fn()); },
    classList: { add: () => {}, remove: () => {}, toggle: () => {}, contains: () => false },
  };
}

const noop = () => {};
const element = new Proxy(noop, {
  get(target, prop) {
    if (["addEventListener", "removeEventListener", "appendChild", "removeChild", "setAttribute", "removeAttribute", "focus", "blur", "click"].includes(prop)) return noop;
    if (["querySelectorAll", "getElementsByTagName"].includes(prop)) return () => [];
    if (prop === "querySelector") return () => element;
    if (prop === "classList") return { add: noop, remove: noop, toggle: noop, contains: () => false };
    if (prop === "style" || prop === "dataset") return element;
    if (prop === "children" || prop === "options") return [];
    if (prop === "length") return 0;
    if (["value", "textContent", "innerHTML", "className"].includes(prop)) return "";
    if (prop === "checked" || prop === "disabled") return false;
    if (prop === Symbol.iterator) return function* () {};
    return element;
  },
  set() { return true; },
  apply() { return undefined; },
});
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const cancelBtn = makeButton();
const document = {
  getElementById: (id) => {
    if (id === "reviewCreateCancelBtn") return cancelBtn;
    return element;
  },
  querySelector: () => element,
  querySelectorAll: () => [],
  createElement: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
const fetch = async () => ({ ok: true, json: async () => ({ ok: true }) });
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout, clearTimeout, setInterval, clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

const renderedItems = [];
let detailEmptyCalled = false;
context.renderDetail = (item) => { renderedItems.push(item); };
context.renderDetailEmpty = () => { detailEmptyCalled = true; };
context.state.itemsById = new Map([
  ["news-42", { id: "news-42", url: "https://example.com/news-42", title: "T", summary: "S", source: "Reuters", published_at: "2026-07-01" }],
]);
context.state.collection = "daily"; // not feed
context.state.selectedId = "news-42";

context.openReviewCreateFromArticle();
if (!context.state.pendingReviewSource) {
  throw new Error("pendingReviewSource was not set");
}
if (context.state.pendingReviewSource._prevSelectedId !== "news-42") {
  throw new Error("_prevSelectedId was not saved");
}

// Cancel should restore the news detail regardless of collection
context.document.getElementById("reviewCreateCancelBtn").click();
if (renderedItems.length !== 1 || renderedItems[0].id !== "news-42") {
  throw new Error(`renderDetail not called with news-42, got ${JSON.stringify(renderedItems)}`);
}
if (detailEmptyCalled) {
  throw new Error("renderDetailEmpty should not be called when news item is restorable");
}
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_review_create_source_key_extraction():
    """"加入复盘" open handlers must extract numeric source keys from composite idea_id."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) {
  throw new Error("front-end bootstrap marker missing");
}
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by source_key regression test");
source = source.replace("let state = {", "var state = {");

const noop = () => {};
const element = new Proxy(noop, {
  get(target, prop) {
    if (["addEventListener", "removeEventListener", "appendChild", "removeChild", "setAttribute", "removeAttribute", "focus", "blur", "click"].includes(prop)) return noop;
    if (["querySelectorAll", "getElementsByTagName"].includes(prop)) return () => [];
    if (prop === "querySelector") return () => element;
    if (prop === "classList") return { add: noop, remove: noop, toggle: noop, contains: () => false };
    if (prop === "style" || prop === "dataset") return element;
    if (prop === "children" || prop === "options") return [];
    if (prop === "length") return 0;
    if (["value", "textContent", "innerHTML", "className"].includes(prop)) return "";
    if (prop === "checked" || prop === "disabled") return false;
    if (prop === Symbol.iterator) return function* () {};
    return element;
  },
  set() { return true; },
  apply() { return undefined; },
});
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const document = {
  getElementById: () => element,
  querySelector: () => element,
  querySelectorAll: () => [],
  createElement: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
const fetch = async () => ({ ok: true, json: async () => ({ ok: true }) });
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout, clearTimeout, setInterval, clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

function assert(cond, msg) { if (!cond) throw new Error(msg); }

// Article path: source_key should be the news URL.
context.state.itemsById = new Map([
  ["item-1", { url: "https://example.com/news-1", title: "t", summary: "s" }]
]);
context.state.selectedId = "item-1";
context.openReviewCreateFromArticle();
assert(context.state.pendingReviewSource.source_type === "article_note", "article type mismatch");
assert(context.state.pendingReviewSource.source_key === "https://example.com/news-1", "article source_key should be URL");

// Trend path: source_key should be numeric trend_note_id.
context.state.selectedTrendIdea = { trend_note_id: 7, note: "n", tag_label: "", trend_date_key: "" };
context.openReviewCreateFromTrendIdea();
assert(context.state.pendingReviewSource.source_type === "market_trend_note", "trend type mismatch");
assert(context.state.pendingReviewSource.source_key === "7", "trend source_key should be numeric id");

// Standalone path: source_key should be numeric standalone_id.
context.state.selectedStandaloneIdea = { standalone_id: 42, note: "n", created_at: "2026-07-01" };
context.openReviewCreateFromStandaloneIdea();
assert(context.state.pendingReviewSource.source_type === "standalone_idea", "standalone type mismatch");
assert(context.state.pendingReviewSource.source_key === "42", "standalone source_key should be numeric id");
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)



def test_detail_polling_preserves_transient_ui_but_switching_clears_it():
    """Same-item background refresh must not destroy in-progress right-pane editors."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) throw new Error("front-end bootstrap marker missing");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by transient detail UI regression test");
source = source.replace("let state = {", "var state = {");
source = source.replace("let marketPickerDirection = null;", "var marketPickerDirection = null;");

function assert(cond, msg) { if (!cond) throw new Error(msg); }
function classTokens(el) { return String(el.className || "").split(/\s+/).filter(Boolean); }
function matchesSelector(el, selector) {
  if (!el) return false;
  if (selector.includes(",")) return selector.split(",").some((part) => matchesSelector(el, part.trim()));
  if (selector.startsWith(".")) return classTokens(el).includes(selector.slice(1));
  if (selector.startsWith("#")) return el.id === selector.slice(1);
  if (selector.includes("[data-id=")) {
    const cls = selector.match(/\.([\w-]+)/)?.[1];
    const id = selector.match(/data-id=\\?"([^"\\]+)\\?"/)?.[1];
    return (!cls || classTokens(el).includes(cls)) && (!id || el.dataset.id === id);
  }
  return el.tagName.toLowerCase() === selector.toLowerCase();
}
function findAll(root, selector) {
  let out = [];
  for (const child of root.children) {
    if (matchesSelector(child, selector)) out.push(child);
    out = out.concat(findAll(child, selector));
  }
  return out;
}
class Element {
  constructor(tag = "div", id = "") {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.className = "";
    this._textContent = "";
    this._innerHTML = "";
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.parentElement = null;
    this.listeners = {};
    this.attributes = {};
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.href = "";
    this.title = "";
    this.classList = {
      add: (...cs) => { const set = new Set(classTokens(this)); cs.forEach((c) => set.add(c)); this.className = [...set].join(" "); },
      remove: (...cs) => { const rm = new Set(cs); this.className = classTokens(this).filter((c) => !rm.has(c)).join(" "); },
      toggle: (c, force) => { const next = force === undefined ? !this.classList.contains(c) : !!force; if (next) this.classList.add(c); else this.classList.remove(c); return next; },
      contains: (c) => classTokens(this).includes(c),
    };
  }
  set innerHTML(v) { this._innerHTML = String(v); this.children = []; }
  get innerHTML() { return this._innerHTML; }
  set textContent(v) { this._textContent = String(v); this.children = []; }
  get textContent() { return this._textContent; }
  appendChild(child) { child.parentElement = this; this.children.push(child); return child; }
  removeChild(child) { const i = this.children.indexOf(child); if (i >= 0) this.children.splice(i, 1); child.parentElement = null; return child; }
  remove() { if (this.parentElement) this.parentElement.removeChild(this); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener() {}
  focus() { document.activeElement = this; }
  blur() { if (document.activeElement === this) document.activeElement = null; }
  setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
  querySelectorAll(selector) { return findAll(this, selector); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  getElementsByTagName(tag) { return findAll(this, tag); }
  setAttribute(k, v) { this.attributes[k] = String(v); if (k === "aria-label") this.ariaLabel = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  removeAttribute(k) { delete this.attributes[k]; }
  get childElementCount() { return this.children.length; }
  contains(node) { let cur = node; while (cur) { if (cur === this) return true; cur = cur.parentElement; } return false; }
  click() { for (const fn of this.listeners.click || []) fn({ target: this, stopPropagation() {} }); }
}
class FakeDocument extends Element {
  constructor() {
    super("document");
    this.map = new Map();
    this.body = new Element("body");
    this.documentElement = new Element("html");
    this.activeElement = null;
    this.hidden = false;
    this.appendChild(this.body);
  }
  getElementById(id) {
    if (!this.map.has(id)) {
      const tag = id.includes("Input") ? "textarea" : (id.includes("Select") ? "select" : (id.includes("Btn") ? "button" : "div"));
      this.map.set(id, new Element(tag, id));
    }
    return this.map.get(id);
  }
  createElement(tag) { return new Element(tag); }
}
const document = new FakeDocument();
const newsList = document.getElementById("newsList");
const detailReminderCard = document.getElementById("detailReminderCard");
detailReminderCard.appendChild(new Element("h4"));
document.getElementById("detailScrollArea");
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const localStorage = { getItem: () => null, setItem: () => {} };
const window = {
  addEventListener: () => {},
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  setTimeout, clearTimeout, setInterval, clearInterval,
  confirm: () => false,
  innerWidth: 1440,
  localStorage,
};
const fetch = async (url) => {
  if (String(url).startsWith("/api/news/status?")) {
    return { ok: true, json: async () => ({ ok: true, items: [{ id: "n1", read_later_at: "2026-07-21 10:00:00", read_later_done_at: null, active_reminder_count: 1, due_reminder_count: 0, next_remind_at: null, detail_status: "running", detail_error: "", detail_ready: 0, ai_status: "none" }] }) };
  }
  return { ok: true, json: async () => ({ ok: true, detail_status: "running", read_at: null, favorite_at: null, important_at: null, read_later_at: "2026-07-21 10:00:00", read_later_done_at: null, has_note: 1, note: { note: "server note" }, market_tags: [], has_market_tags: 0, ai_status: "none", ai: null, detail: null, reminder_summary: { active_total: 1, due_total: 0, done_total: 0 }, reminders: [] }) };
};
const context = { console, document, window, localStorage, IntersectionObserver, fetch,
  URL, URLSearchParams, Date, Map, Set, JSON, encodeURIComponent, CSS: { escape: (s) => String(s).replace(/"/g, '\"') },
  setTimeout, clearTimeout, setInterval, clearInterval, Node: Element };
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

const item = { id: "n1", url: "https://example.com/n1", title: "News 1", source: "Reuters", published_at: "2026-07-21", read_later_at: "2026-07-21 10:00:00", detail_status: "running", detail_ready: 0, ai_status: "none", has_note: 1, has_market_tags: 0 };
context.state.selectedId = "n1";
context.state.itemsById.set("n1", item);
context.state.detailCacheByUrl.set(item.url, { note: { note: "server note" }, reminders: [], reminder_summary: { active_total: 0, due_total: 0, done_total: 0 }, tracked_topic_choices: [{ id: 1, title: "T1" }, { id: 2, title: "T2" }] });
context.state.marketTagChoices = [{ key: "ai", display_name: "AI" }, { key: "chips", display_name: "Chips" }];
const realRenderDetail = context.renderDetail;

context.setDetailNoteEditorOpen(true);
const noteEditor = document.getElementById("detailNoteEditor");
const noteInput = document.getElementById("detailNoteInput");
noteInput.value = "unique-draft-v214";
noteInput.focus();
noteInput.setSelectionRange(7, 12);
realRenderDetail(item, { preserveTransientUi: true });
assert(!noteEditor.classList.contains("hidden"), "note editor should stay open on preserve render");
assert(noteInput.value === "unique-draft-v214", `note draft changed to ${noteInput.value}`);
assert(document.activeElement === noteInput, "note textarea focus should stay during preserve render");
assert(noteInput.selectionStart === 7 && noteInput.selectionEnd === 12, "note selection should stay during preserve render");

context.openMarketPicker(item, "bullish");
const picker = document.getElementById("detailMarketPicker");
const pickerOptions = document.getElementById("detailMarketPickerOptions");
assert(!picker.classList.contains("hidden") && context.marketPickerDirection === "bullish", "bullish picker should be open before refresh");
const optionText = pickerOptions.children.map((el) => el.textContent).join("|");
realRenderDetail(item, { preserveTransientUi: true });
assert(!picker.classList.contains("hidden"), "bullish picker should stay open on preserve render");
assert(context.marketPickerDirection === "bullish", `market direction changed to ${context.marketPickerDirection}`);
assert(pickerOptions.children.map((el) => el.textContent).join("|") === optionText, "market picker options should stay stable");

context.closeMarketPicker();
context.openMarketPicker(item, "bearish");
realRenderDetail(item, { preserveTransientUi: true });
assert(!picker.classList.contains("hidden") && context.marketPickerDirection === "bearish", "bearish picker should stay open on preserve render");

context.openReminderEditor(item);
const reminderEditor = document.getElementById("detailReminderEditor");
const reminderDate = document.getElementById("detailReminderEventDateInput");
const reminderNote = document.getElementById("detailReminderNoteInput");
reminderDate.value = "2026-08-01";
reminderNote.value = "reminder-draft-v214";
realRenderDetail(item, { preserveTransientUi: true });
assert(!reminderEditor.classList.contains("hidden"), "reminder editor should stay open on preserve render");
assert(reminderDate.value === "2026-08-01" && reminderNote.value === "reminder-draft-v214", "reminder draft should stay during preserve render");

(async () => {
  await context.openDetailTrackEditor(item);
  const trackEditor = document.getElementById("detailTrackEditor");
  const trackSelect = document.getElementById("detailTrackTopicSelect");
  trackSelect.value = "2";
  realRenderDetail(item, { preserveTransientUi: true });
  assert(!trackEditor.classList.contains("hidden"), "track editor should stay open on preserve render");
  assert(trackSelect.value === "2", `track selection changed to ${trackSelect.value}`);

  const routed = [];
  context.renderDetail = (rendered, options = {}) => routed.push({ id: rendered?.id || null, preserve: !!options.preserveTransientUi });
  await context.loadDetail("n1");
  assert(routed.some((r) => r.id === "n1" && r.preserve), `loadDetail did not route preserve render: ${JSON.stringify(routed)}`);
  const row = new Element("div");
  row.className = "news-item";
  row.dataset.id = "n1";
  newsList.appendChild(row);
  await context.pollRowStatusesOnce();
  assert(routed.filter((r) => r.id === "n1" && r.preserve).length >= 2, `pollRowStatusesOnce did not route preserve render: ${JSON.stringify(routed)}`);

  context.renderDetail = realRenderDetail;
  const other = { id: "n2", url: "https://example.com/n2", title: "News 2", source: "Reuters", published_at: "2026-07-21", read_later_at: null, detail_ready: 0, detail_status: "none", ai_status: "none" };
  context.state.selectedId = "n2";
  context.state.itemsById.set("n2", other);
  realRenderDetail(other);
  assert(noteEditor.classList.contains("hidden"), "switching item should close note editor");
  assert(picker.classList.contains("hidden") && context.marketPickerDirection === null, "switching item should close market picker");
  assert(reminderEditor.classList.contains("hidden"), "switching item should close reminder editor");
  assert(trackEditor.classList.contains("hidden"), "switching item should close track editor");
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)

def test_read_later_rollback_restores_detail_ai_status_and_polling():
    """Failed read-later toggles must restore detail/AI status fields and polling."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) {
  throw new Error("front-end bootstrap marker missing");
}
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by read-later rollback regression test");
source = source.replace("let state = {", "var state = {");

const noop = () => {};
const element = new Proxy(noop, {
  get(target, prop) {
    if (["addEventListener", "removeEventListener", "appendChild", "removeChild", "setAttribute", "removeAttribute", "focus", "blur", "click"].includes(prop)) return noop;
    if (["querySelectorAll", "getElementsByTagName"].includes(prop)) return () => [];
    if (prop === "querySelector") return () => null;
    if (prop === "classList") return { add: noop, remove: noop, toggle: noop, contains: () => false };
    if (prop === "style" || prop === "dataset") return element;
    if (prop === "children" || prop === "options") return [];
    if (prop === "length" || prop === "childElementCount") return 0;
    if (["value", "textContent", "innerHTML", "className"].includes(prop)) return "";
    if (prop === "checked" || prop === "disabled") return false;
    if (prop === Symbol.iterator) return function* () {};
    return element;
  },
  set() { return true; },
  apply() { return undefined; },
});
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const document = {
  getElementById: () => element,
  querySelector: () => null,
  querySelectorAll: () => [],
  createElement: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout, clearTimeout, setInterval, clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
const context = {
  console, document, window, localStorage, IntersectionObserver,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

const calls = { rendered: [], errors: [], rowPolling: 0, detailPolling: [], stopDetail: 0 };
context.patchState = async () => { throw new Error("network failed"); };
context.adjustDateCountForScopeTransition = () => {};
context.rerenderOne = (id) => calls.rendered.push({ id, item: { ...context.state.itemsById.get(id) } });
context.showStatePatchError = (id, payload) => calls.errors.push({ id, payload });
context.ensureRowStatusPolling = () => { calls.rowPolling += 1; };
context.startDetailPolling = (id) => calls.detailPolling.push(id);
context.stopDetailPolling = () => { calls.stopDetail += 1; };

function assert(cond, msg) { if (!cond) throw new Error(msg); }

(async () => {
  context.state.itemsById = new Map();
  context.state.selectedId = "";
  context.state.itemsById.set("add", {
    id: "add",
    date_key: "2026-07-16",
    read_at: null,
    favorite_at: null,
    important_at: null,
    read_later_at: null,
    read_later_done_at: null,
    detail_status: "success",
    detail_ready: 1,
    ai_status: "success",
    ai_ready: 1,
    has_note: 0,
    has_market_tags: 0,
  });
  await context.patchStateWithRollback("add", { read_later: true });
  const add = context.state.itemsById.get("add");
  assert(add.read_later_at === null, "add failure should restore read_later_at");
  assert(add.read_later_done_at === null, "add failure should restore read_later_done_at");
  assert(add.detail_status === "success", `add failure detail_status=${add.detail_status}`);
  assert(add.detail_ready === 1, `add failure detail_ready=${add.detail_ready}`);
  assert(add.ai_status === "success", `add failure ai_status=${add.ai_status}`);
  assert(add.ai_ready === 1, `add failure ai_ready=${add.ai_ready}`);

  context.state.selectedId = "remove";
  context.state.itemsById.set("remove", {
    id: "remove",
    date_key: "2026-07-16",
    read_at: null,
    favorite_at: null,
    important_at: null,
    read_later_at: "2026-07-16 10:00:00",
    read_later_done_at: null,
    detail_status: "running",
    detail_ready: 0,
    ai_status: "none",
    ai_ready: 0,
    has_note: 0,
    has_market_tags: 0,
  });
  await context.patchStateWithRollback("remove", { read_later: false });
  const remove = context.state.itemsById.get("remove");
  assert(remove.read_later_at === "2026-07-16 10:00:00", "remove failure should restore read_later_at");
  assert(remove.read_later_done_at === null, "remove failure should restore read_later_done_at");
  assert(remove.detail_status === "running", `remove failure detail_status=${remove.detail_status}`);
  assert(remove.detail_ready === 0, `remove failure detail_ready=${remove.detail_ready}`);
  assert(remove.ai_status === "none", `remove failure ai_status=${remove.ai_status}`);
  assert(remove.ai_ready === 0, `remove failure ai_ready=${remove.ai_ready}`);
  assert(calls.stopDetail === 1, `optimistic remove should stop detail polling once, got ${calls.stopDetail}`);
  assert(calls.rowPolling >= 1, "remove failure should restore row status polling");
  assert(calls.detailPolling.includes("remove"), "remove failure should restore detail polling for selected item");
  assert(calls.errors.length === 2, `expected two rollback feedback calls, got ${calls.errors.length}`);
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_feed_keyboard_navigation_desktop_mode_and_tail_detail():
    """Desktop feed rows should support roving arrow navigation with delayed detail side effects."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) throw new Error("front-end bootstrap marker missing");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by keyboard navigation regression test");
source = source.replace("let state = {", "var state = {");
source = source.replace("let feedKeyboardMode = false;", "var feedKeyboardMode = false;");
source = source.replace("let feedKeyboardDetailTimer = null;", "var feedKeyboardDetailTimer = null;");
source = source.replace("let feedKeyboardDetailTimerItemId = \"\";", "var feedKeyboardDetailTimerItemId = \"\";");
source = source.replace("let feedKeyboardLoadMorePromise = null;", "var feedKeyboardLoadMorePromise = null;");
source = source.replace("let feedKeyboardDetailFocusMode = false;", "var feedKeyboardDetailFocusMode = false;");

function assert(cond, msg) { if (!cond) throw new Error(msg); }
function wait(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

class FakeEvent {
  constructor(type, props = {}) {
    this.type = type;
    this.key = props.key || "";
    this.target = props.target || null;
    this.isComposing = !!props.isComposing;
    this.ctrlKey = !!props.ctrlKey;
    this.metaKey = !!props.metaKey;
    this.altKey = !!props.altKey;
    this.shiftKey = !!props.shiftKey;
    this.repeat = !!props.repeat;
    this.defaultPrevented = false;
    this.cancelBubble = false;
  }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() { this.cancelBubble = true; }
}

function classTokens(el) { return String(el.className || "").split(/\s+/).filter(Boolean); }
function matchesSelector(el, selector) {
  if (!el) return false;
  if (selector.includes(",")) return selector.split(",").some((part) => matchesSelector(el, part.trim()));
  if (selector.startsWith(".")) return classTokens(el).includes(selector.slice(1));
  if (selector.startsWith("#")) return el.id === selector.slice(1);
  if (selector.includes("[data-id=")) {
    const cls = selector.match(/\.([\w-]+)/)?.[1];
    const id = selector.match(/data-id=\\?"([^"\\]+)\\?"/)?.[1];
    return (!cls || classTokens(el).includes(cls)) && (!id || el.dataset.id === id);
  }
  if (selector === "input" || selector === "textarea" || selector === "select" || selector === "button" || selector === "a") {
    return el.tagName.toLowerCase() === selector;
  }
  if (selector === "[contenteditable]") return !!el.isContentEditable;
  return el.tagName.toLowerCase() === selector.toLowerCase();
}
function findAll(root, selector) {
  let out = [];
  for (const child of root.children) {
    if (matchesSelector(child, selector)) out.push(child);
    out = out.concat(findAll(child, selector));
  }
  return out;
}

class Element {
  constructor(tag = "div", id = "") {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.className = "";
    this.textContent = "";
    this.innerHTML = "";
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.parentElement = null;
    this.listeners = {};
    this.attributes = {};
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.scrollIntoViewCalls = [];
    this.tabIndex = -1;
    this.isContentEditable = false;
    this.classList = {
      add: (...classes) => { const set = new Set(classTokens(this)); classes.forEach((c) => set.add(c)); this.className = [...set].join(" "); },
      remove: (...classes) => { const remove = new Set(classes); this.className = classTokens(this).filter((c) => !remove.has(c)).join(" "); },
      toggle: (c, force) => {
        const has = classTokens(this).includes(c);
        const next = force === undefined ? !has : !!force;
        if (next) this.classList.add(c); else this.classList.remove(c);
        return next;
      },
      contains: (c) => classTokens(this).includes(c),
    };
  }
  appendChild(child) { child.parentElement = this; this.children.push(child); return child; }
  insertBefore(child, ref) {
    child.parentElement = this;
    const i = this.children.indexOf(ref);
    if (i >= 0) this.children.splice(i, 0, child); else this.children.push(child);
    return child;
  }
  removeChild(child) { const i = this.children.indexOf(child); if (i >= 0) this.children.splice(i, 1); child.parentElement = null; return child; }
  remove() { if (this.parentElement) this.parentElement.removeChild(this); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener() {}
  dispatchEvent(event) {
    if (!event.target) event.target = this;
    for (const fn of this.listeners[event.type] || []) fn(event);
    if (!event.cancelBubble && this.parentElement) this.parentElement.dispatchEvent(event);
    return !event.defaultPrevented;
  }
  click() { this.dispatchEvent(new FakeEvent("click", { target: this })); }
  focus() { document.activeElement = this; }
  blur() { if (document.activeElement === this) document.activeElement = null; }
  scrollIntoView(opts) { this.scrollIntoViewCalls.push(opts); }
  querySelectorAll(selector) { return findAll(this, selector); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  getElementsByTagName(tag) { return findAll(this, tag); }
  setAttribute(k, v) { this.attributes[k] = String(v); if (k === "aria-current") this.ariaCurrent = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  removeAttribute(k) { delete this.attributes[k]; if (k === "aria-current") delete this.ariaCurrent; }
  closest(selector) {
    let node = this;
    while (node) {
      if (selector.includes(",")) {
        if (selector.split(",").some((part) => matchesSelector(node, part.trim()))) return node;
      } else if (matchesSelector(node, selector)) return node;
      node = node.parentElement;
    }
    return null;
  }
  get childElementCount() { return this.children.length; }
  contains(node) { let cur = node; while (cur) { if (cur === this) return true; cur = cur.parentElement; } return false; }
  getBoundingClientRect() { return { top: 0, bottom: 100, left: 0, right: 100, width: 100, height: 100 }; }
}

class FakeDocument extends Element {
  constructor() { super("document"); this.map = new Map(); this.body = new Element("body"); this.documentElement = new Element("html"); this.activeElement = null; this.appendChild(this.body); }
  getElementById(id) { if (!this.map.has(id)) this.map.set(id, new Element("div", id)); return this.map.get(id); }
  createElement(tag) { return new Element(tag); }
}

const document = new FakeDocument();
const feedColumn = new Element("section");
feedColumn.className = "feed-column";
const newsList = document.getElementById("newsList");
const listHint = document.getElementById("listHint");
const loadMoreSentinel = document.getElementById("loadMoreSentinel");
feedColumn.appendChild(newsList);
document.body.appendChild(feedColumn);
const detailPanel = document.getElementById("detailPanel");
const detailBody = document.getElementById("detailBody");
const detailScrollArea = document.getElementById("detailScrollArea");
detailBody.appendChild(detailScrollArea);
detailPanel.appendChild(detailBody);
document.body.appendChild(detailPanel);

class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const localStorage = { getItem: () => null, setItem: () => {} };
const window = {
  addEventListener: () => {},
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  setTimeout, clearTimeout, setInterval, clearInterval,
  confirm: () => false,
  innerWidth: 1440,
  localStorage,
};
const context = { console, document, window, localStorage, IntersectionObserver, FakeEvent,
  URL, URLSearchParams, Date, Map, Set, JSON, encodeURIComponent, CSS: { escape: (s) => String(s).replace(/"/g, '\\"') },
  setTimeout, clearTimeout, setInterval, clearInterval, Node: Element };
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

newsList.appendChild(listHint);
newsList.appendChild(loadMoreSentinel);
const calls = { renders: [], loads: [], polls: [], checkpoints: [], stops: 0 };
context.renderDetail = (item) => calls.renders.push(item ? item.id : null);
context.loadDetail = async (id) => { calls.loads.push(id); };
context.startDetailPolling = (id) => { calls.polls.push(id); };
context.stopDetailPolling = () => { calls.stops += 1; };
context.saveReadingCheckpoint = async (item) => { calls.checkpoints.push(item.id); };

function append(item) { context.appendNewsRow(item, context.buildItemRow(item)); }
[1, 2, 3, 4].forEach((n) => append({ id: `n${n}`, url: `https://example.com/${n}`, title: `T${n}`, summary: `S${n}`, source: "Reuters", published_at: "2026-07-19" }));
const rows = newsList.querySelectorAll(".feed-news-item");
assert(rows.length === 4, `rows=${rows.length}`);

(async () => {
  rows[1].click();
  assert(context.feedKeyboardMode === true, "clicking selected feed row should enter keyboard mode");
  assert(context.state.selectedId === "n2", `selected after click=${context.state.selectedId}`);
  assert(document.activeElement === rows[1], "clicked row should receive focus for keyboard mode");
  assert(rows[1].tabIndex === 0 && rows[1].getAttribute("aria-current") === "page", "selected row should be roving tab stop/current");

  rows[1].dispatchEvent(new FakeEvent("keydown", { key: "ArrowDown", target: rows[1] }));
  rows[2].dispatchEvent(new FakeEvent("keydown", { key: "ArrowDown", target: rows[2] }));
  assert(context.state.selectedId === "n4", `selected after quick arrows=${context.state.selectedId}`);
  assert(document.activeElement === rows[3], "final selected row should be focused");
  assert(rows[3].scrollIntoViewCalls.some((opts) => opts.block === "nearest" && opts.behavior === "auto"), "keyboard move should use nearest/auto scrollIntoView");
  assert(calls.renders.includes("n3") && calls.renders.includes("n4"), "right-pane base render should update immediately during movement");
  await wait(170);
  assert(calls.loads.filter((id) => id === "n3").length === 0, "intermediate row should not trigger delayed detail fetch");
  assert(calls.loads.filter((id) => id === "n4").length === 1, `final detail load count=${JSON.stringify(calls.loads)}`);
  assert(calls.checkpoints[calls.checkpoints.length - 1] === "n4", `final checkpoint=${calls.checkpoints[calls.checkpoints.length - 1]}`);

  detailPanel.click();
  assert(context.feedKeyboardMode === false, "outside middle column click should exit keyboard mode");
  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowUp", target: rows[3] }));
  assert(context.state.selectedId === "n4", "arrows after exit should not move selection");

  rows[3].click();
  assert(context.feedKeyboardMode === true && context.state.selectedId === "n4", "clicking retained selected row should re-enter keyboard mode without clearing detail");
  const patches = [];
  context.patchState = async (id, payload) => {
    patches.push({ id, payload: { ...payload } });
    if ("important" in payload) return { important_at: payload.important ? "server-important" : null };
    if ("read_later" in payload) return { read_later_at: payload.read_later ? "server-read-later" : null, read_later_done_at: payload.read_later ? null : "done" };
    return {};
  };

  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowLeft", target: rows[3] }));
  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowLeft", target: rows[3], repeat: true }));
  await wait(0);
  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowLeft", target: rows[3] }));
  await wait(0);
  assert(JSON.stringify(patches.map((p) => p.payload)) === JSON.stringify([{ important: true }, { important: false }]), `important patches=${JSON.stringify(patches)}`);
  assert(context.state.selectedId === "n4" && document.activeElement === rows[3], "left toggle should keep selected row focus");

  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowRight", target: rows[3] }));
  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowRight", target: rows[3], repeat: true }));
  await wait(0);
  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowRight", target: rows[3] }));
  await wait(0);
  assert(JSON.stringify(patches.slice(2).map((p) => p.payload)) === JSON.stringify([{ read_later: true }, { read_later: false }]), `read-later patches=${JSON.stringify(patches)}`);

  append({ id: "video", url: "https://www.bloomberg.com/news/videos/2026-07-19/example-video", title: "V", source: "Bloomberg", published_at: "2026-07-19" });
  const videoRow = newsList.querySelectorAll(".feed-news-item").find((row) => row.dataset.id === "video");
  videoRow.click();
  const beforeUnsupported = patches.length;
  videoRow.dispatchEvent(new FakeEvent("keydown", { key: "ArrowRight", target: videoRow }));
  await wait(0);
  assert(patches.length === beforeUnsupported, "unsupported read-later row should not patch on ArrowRight");

  rows[3].click();
  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "ArrowUp", target: rows[3] }));
  detailBody.classList.remove("hidden");
  assert(context.state.selectedId === "n3" && context.feedKeyboardDetailTimer, "ArrowUp should select n3 and leave a pending detail timer");
  const loadsBeforeEnter = calls.loads.filter((id) => id === "n3").length;
  rows[2].dispatchEvent(new FakeEvent("keydown", { key: "Enter", target: rows[2] }));
  assert(context.feedKeyboardMode === false && context.feedKeyboardDetailFocusMode === true, "Enter should move from list mode into detail focus mode");
  assert(document.activeElement === detailScrollArea, "Enter should focus detail scroll area");
  assert(detailScrollArea.classList.contains("detail-keyboard-focus"), "detail scroll area should show keyboard focus mode");
  await wait(170);
  assert(calls.loads.filter((id) => id === "n3").length === loadsBeforeEnter + 1, `Enter should flush once, loads=${JSON.stringify(calls.loads)}`);

  const textarea = new Element("textarea");
  textarea.value = "draft text";
  detailScrollArea.appendChild(textarea);
  textarea.dispatchEvent(new FakeEvent("keydown", { key: "Escape", target: textarea }));
  assert(textarea.value === "draft text", "detail Escape should preserve editor draft value");
  assert(context.feedKeyboardMode === true && context.feedKeyboardDetailFocusMode === false, "detail Escape should restore list keyboard mode");
  assert(context.state.selectedId === "n3" && document.activeElement === rows[2], "detail Escape should focus original selected row");
  rows[2].dispatchEvent(new FakeEvent("keydown", { key: "ArrowDown", target: rows[2] }));
  assert(context.state.selectedId === "n4", "restored list mode should accept ArrowDown after detail Escape");

  const input = new Element("input");
  rows[3].appendChild(input);
  input.dispatchEvent(new FakeEvent("keydown", { key: "ArrowUp", target: input }));
  assert(context.state.selectedId === "n4", "interactive input target should not be hijacked");

  rows[3].dispatchEvent(new FakeEvent("keydown", { key: "Escape", target: rows[3] }));
  assert(context.feedKeyboardMode === false && context.state.selectedId === "n4", "Escape should exit mode and preserve detail selection");
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_feed_keyboard_navigation_loads_next_page_once():
    """ArrowDown on the loaded tail should reuse existing pagination once and select the new row."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) throw new Error("front-end bootstrap marker missing");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by keyboard load-more regression test");
source = source.replace("let state = {", "var state = {");
source = source.replace("let feedKeyboardMode = false;", "var feedKeyboardMode = false;");
source = source.replace("let feedKeyboardDetailTimer = null;", "var feedKeyboardDetailTimer = null;");
source = source.replace("let feedKeyboardDetailTimerItemId = \"\";", "var feedKeyboardDetailTimerItemId = \"\";");
source = source.replace("let feedKeyboardLoadMorePromise = null;", "var feedKeyboardLoadMorePromise = null;");
source = source.replace("let feedKeyboardDetailFocusMode = false;", "var feedKeyboardDetailFocusMode = false;");

function assert(cond, msg) { if (!cond) throw new Error(msg); }
function wait(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }
class FakeEvent { constructor(type, props = {}) { this.type = type; this.key = props.key || ""; this.target = props.target || null; this.repeat = !!props.repeat; this.defaultPrevented = false; this.cancelBubble = false; this.isComposing = false; this.ctrlKey = false; this.metaKey = false; this.altKey = false; this.shiftKey = false; } preventDefault(){this.defaultPrevented=true;} stopPropagation(){this.cancelBubble=true;} }
function classTokens(el) { return String(el.className || "").split(/\s+/).filter(Boolean); }
function matchesSelector(el, selector) {
  if (!el) return false;
  if (selector.includes(",")) return selector.split(",").some((part) => matchesSelector(el, part.trim()));
  if (selector.startsWith(".")) return classTokens(el).includes(selector.slice(1));
  if (selector === "input" || selector === "textarea" || selector === "select" || selector === "button" || selector === "a") return el.tagName.toLowerCase() === selector;
  if (selector === "[contenteditable]") return !!el.isContentEditable;
  return el.tagName.toLowerCase() === selector.toLowerCase();
}
function findAll(root, selector) { let out = []; for (const child of root.children) { if (matchesSelector(child, selector)) out.push(child); out = out.concat(findAll(child, selector)); } return out; }
class Element {
  constructor(tag = "div", id = "") { this.tagName = tag.toUpperCase(); this.id = id; this.className = ""; this.textContent = ""; this.innerHTML = ""; this.dataset = {}; this.style = {}; this.children = []; this.parentElement = null; this.listeners = {}; this.attributes = {}; this.value = ""; this.checked = false; this.disabled = false; this.tabIndex = -1; this.isContentEditable = false; this.classList = { add: (...cs) => { const s = new Set(classTokens(this)); cs.forEach((c) => s.add(c)); this.className = [...s].join(" "); }, remove: (...cs) => { const r = new Set(cs); this.className = classTokens(this).filter((c) => !r.has(c)).join(" "); }, toggle: (c, force) => { const next = force === undefined ? !this.classList.contains(c) : !!force; if (next) this.classList.add(c); else this.classList.remove(c); return next; }, contains: (c) => classTokens(this).includes(c) }; }
  appendChild(child) { child.parentElement = this; this.children.push(child); return child; }
  insertBefore(child, ref) { child.parentElement = this; const i = this.children.indexOf(ref); if (i >= 0) this.children.splice(i, 0, child); else this.children.push(child); return child; }
  removeChild(child) { const i = this.children.indexOf(child); if (i >= 0) this.children.splice(i, 1); child.parentElement = null; return child; }
  remove() { if (this.parentElement) this.parentElement.removeChild(this); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  removeEventListener() {}
  dispatchEvent(event) { if (!event.target) event.target = this; for (const fn of this.listeners[event.type] || []) fn(event); if (!event.cancelBubble && this.parentElement) this.parentElement.dispatchEvent(event); return !event.defaultPrevented; }
  click() { this.dispatchEvent(new FakeEvent("click", { target: this })); }
  focus() { document.activeElement = this; }
  blur() {}
  scrollIntoView() {}
  querySelectorAll(selector) { return findAll(this, selector); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  getElementsByTagName(tag) { return findAll(this, tag); }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  removeAttribute(k) { delete this.attributes[k]; }
  closest(selector) { let node = this; while (node) { if (matchesSelector(node, selector)) return node; node = node.parentElement; } return null; }
  get childElementCount() { return this.children.length; }
  contains(node) { let cur = node; while (cur) { if (cur === this) return true; cur = cur.parentElement; } return false; }
  getBoundingClientRect() { return { top: 0, bottom: 100, left: 0, right: 100, width: 100, height: 100 }; }
}
class FakeDocument extends Element { constructor(){ super("document"); this.map = new Map(); this.body = new Element("body"); this.documentElement = new Element("html"); this.activeElement = null; this.appendChild(this.body); } getElementById(id){ if (!this.map.has(id)) this.map.set(id, new Element("div", id)); return this.map.get(id); } createElement(tag){ return new Element(tag); } }
const document = new FakeDocument();
const feedColumn = new Element("section"); feedColumn.className = "feed-column";
const newsList = document.getElementById("newsList"); const listHint = document.getElementById("listHint"); const loadMoreSentinel = document.getElementById("loadMoreSentinel");
feedColumn.appendChild(newsList); document.body.appendChild(feedColumn);
class IntersectionObserver { constructor(){} observe(){} disconnect(){} }
const localStorage = { getItem: () => null, setItem: () => {} };
const window = { addEventListener: () => {}, matchMedia: () => ({ matches: false, addEventListener: () => {} }), setTimeout, clearTimeout, setInterval, clearInterval, confirm: () => false, innerWidth: 1440, localStorage };
const context = { console, document, window, localStorage, IntersectionObserver, FakeEvent, URLSearchParams, Date, Map, Set, JSON, encodeURIComponent, CSS: { escape: (s) => String(s) }, setTimeout, clearTimeout, setInterval, clearInterval, Node: Element };
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });
newsList.appendChild(listHint); newsList.appendChild(loadMoreSentinel);
context.renderDetail = () => {}; context.loadDetail = async () => {}; context.startDetailPolling = () => {}; context.stopDetailPolling = () => {}; context.saveReadingCheckpoint = async () => {};
function append(item) { context.appendNewsRow(item, context.buildItemRow(item)); }
append({ id: "n1", url: "https://example.com/1", title: "T1", source: "Reuters", published_at: "2026-07-19" });
append({ id: "n2", url: "https://example.com/2", title: "T2", source: "Reuters", published_at: "2026-07-19" });
const rows = () => newsList.querySelectorAll(".feed-news-item");
(async () => {
  rows()[1].click();
  context.state.hasMore = true;
  context.state.loading = false;
  let loadCalls = 0;
  context.loadNextPage = async () => {
    loadCalls += 1;
    await wait(30);
    append({ id: "n3", url: "https://example.com/3", title: "T3", source: "Reuters", published_at: "2026-07-19" });
    context.state.hasMore = false;
  };
  rows()[1].dispatchEvent(new FakeEvent("keydown", { key: "ArrowDown", target: rows()[1] }));
  rows()[1].dispatchEvent(new FakeEvent("keydown", { key: "ArrowDown", target: rows()[1] }));
  await wait(80);
  assert(loadCalls === 1, `loadCalls=${loadCalls}`);
  assert(context.state.selectedId === "n3", `selected=${context.state.selectedId}`);
  rows()[2].dispatchEvent(new FakeEvent("keydown", { key: "ArrowDown", target: rows()[2] }));
  await wait(20);
  assert(loadCalls === 1, "last row without hasMore should no-op");
  window.innerWidth = 1180;
  rows()[2].dispatchEvent(new FakeEvent("keydown", { key: "ArrowUp", target: rows()[2] }));
  assert(context.state.selectedId === "n3", "1180px should not enable arrow navigation");
  const disabledPatches = [];
  context.patchState = async (id, payload) => { disabledPatches.push({ id, payload }); return {}; };
  rows()[2].dispatchEvent(new FakeEvent("keydown", { key: "ArrowLeft", target: rows()[2] }));
  rows()[2].dispatchEvent(new FakeEvent("keydown", { key: "ArrowRight", target: rows()[2] }));
  rows()[2].dispatchEvent(new FakeEvent("keydown", { key: "Enter", target: rows()[2] }));
  await wait(20);
  assert(disabledPatches.length === 0, `1180px should not toggle state, patches=${JSON.stringify(disabledPatches)}`);
  assert(context.feedKeyboardMode === true, "1180px ignored Enter should not switch to detail focus mode");
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_frontend_eink_theme_contract():
    """墨水屏外观一期：首帧初始化、第四外观项、覆盖层与非颜色状态契约。"""
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")

    # 首帧主题初始化：内联脚本必须出现在样式表链接之前，且含 eink 与会话覆盖逻辑。
    head_part, head_rest = index_source.split("<link rel=\"stylesheet\"", 1)
    assert "news_reader_theme_mode_url" in head_part
    assert '"eink"' in head_part
    assert 'document.documentElement.setAttribute("data-theme", mode);' in head_part
    assert "__newsReaderThemeMode" in head_part

    # 外观选择器新增第四项。
    assert '<option value="eink">墨水屏</option>' in index_source
    # 移动端更多面板同步。
    assert '{ value: "eink", label: "墨水屏" }' in app_source

    # applyThemeMode 支持 eink 与 persist 语义；启动不重复写长期偏好。
    assert '["system", "light", "dark", "eink"].includes(mode)' in app_source
    assert "function applyThemeMode(mode, { persist = true } = {})" in app_source
    assert "applyThemeMode(window.__newsReaderThemeMode || localStorage.getItem(THEME_KEY) || \"system\", { persist: false });" in app_source
    listener_block = app_source.split("if (themeModeSelect) {", 1)[1].split("}", 1)[0]
    assert 'window.sessionStorage.removeItem("news_reader_theme_mode_url")' in listener_block

    # 覆盖层：全局动效/阴影/模糊/背景图清零。
    eink_block = style_source.split('html[data-theme="eink"] *', 1)[1].split("/* 面板与关键组件", 1)[0]
    assert "transition-duration: 0s !important;" in eink_block
    assert "animation: none !important;" in eink_block
    assert "box-shadow: none !important;" in eink_block
    assert "backdrop-filter: none !important;" in eink_block
    assert "-webkit-backdrop-filter: none !important;" in eink_block
    assert "background-image: none !important;" in eink_block

    # 触控优先：hover 常显 + 触控目标 + 低透明度弱化移除。
    assert 'html[data-theme="eink"] .news-item .row-actions {\n    opacity: 1 !important;\n  }' in style_source
    assert "html[data-theme=\"eink\"] .nav-btn-secondary," in style_source
    assert "min-height: 44px;" in style_source.split("常用触控目标约 44px", 1)[1]

    # 状态脱离颜色：标题前缀、未读点、选中描边、四色高亮线型、禁用虚线。
    assert 'html[data-theme="eink"] .title.tone-important::before {\n  content: "★ ";' in style_source
    assert 'html[data-theme="eink"] .title.tone-bullish::before {\n  content: "↑ ";' in style_source
    assert 'html[data-theme="eink"] .title.tone-bearish::before {\n  content: "↓ ";' in style_source
    assert 'html[data-theme="eink"] .title.tone-mixed::before {\n  content: "↕ ";' in style_source
    assert "html[data-theme=\"eink\"] .unread-dot {\n  background: #111827;\n}" in style_source
    assert "outline: 2px solid #111827;" in style_source
    assert 'mark.article-highlight[data-highlight-color="yellow"] {\n  text-decoration-style: solid;' in style_source
    assert 'mark.article-highlight[data-highlight-color="green"] {\n  text-decoration-style: dashed;' in style_source
    assert 'mark.article-highlight[data-highlight-color="blue"] {\n  text-decoration-style: double;' in style_source
    assert 'mark.article-highlight[data-highlight-color="pink"] {\n  text-decoration-style: dotted;' in style_source
    assert "border-style: dashed;" in style_source

    # 正文排版与键盘焦点态。
    assert "font-size: max(1rem, calc(var(--detail-font-base) * var(--detail-font-scale)));" in style_source
    assert "line-height: 1.65;" in style_source
    assert "html[data-theme=\"eink\"] :focus-visible {" in style_source

    # 返修回归：可见 UI 实底灰阶（日期栏/移动更多行/设置导航/状态徽章）。
    assert "html[data-theme=\"eink\"] .date-section {\n  background: #ffffff;\n  border: 1px solid var(--border);\n}" in style_source
    assert "html[data-theme=\"eink\"] .mobile-more-row,\nhtml[data-theme=\"eink\"] .mobile-more-select-row {\n  background: #ffffff;" in style_source
    assert "html[data-theme=\"eink\"] .settings-nav {\n  background-color: #f7f7f7;" in style_source
    assert "html[data-theme=\"eink\"] .settings-api-badge.ok," in style_source
    assert "html[data-theme=\"eink\"] .settings-release-badge.fix {\n  color: #000000;\n  background: #ffffff;" in style_source
    # 稍后阅读五态：展示状态只增加 data-detail-ready，不改状态机或点击语义。
    assert 'li.dataset.detailReady = Number(item.detail_ready || 0) === 1 ? "1" : "0";' in app_source
    assert 'html[data-theme="eink"] .news-item[data-read-later="1"][data-detail-ready="1"] .btn-read-later {' in style_source
    assert 'html[data-theme="eink"] .news-item[data-read-later="0"][data-detail-ready="1"] .btn-read-later {' in style_source
    assert 'html[data-theme="eink"] .news-item[data-read-later="0"][data-detail-ready="0"] .btn-read-later {' in style_source
    assert 'html[data-theme="eink"] .news-item[data-read-later="1"][data-detail-ready="0"] .btn-read-later {' in style_source
    assert 'html[data-theme="eink"] .news-item[data-read-later="1"][data-detail-status="failed"] .btn-read-later {' in style_source
    assert 'border: 2px solid #111827;' in style_source
    assert 'border: 2px dotted #111827;' in style_source
    assert 'border: 2px dashed #111827;' in style_source
    assert 'width: 44px;' in style_source
    assert 'height: 44px;' in style_source
    # 失败只用虚线；不得再追加文字或隐藏原书签 glyph。
    assert 'content: "⚠ 失败";' not in style_source
    assert 'html[data-theme="eink"] .news-item[data-read-later="1"][data-detail-status="failed"] .btn-read-later::after' not in style_source
    # 冲突冗余规则不得残留：tone-danger eink 覆盖与 glyph 隐藏必须不存在。
    assert 'html[data-theme="eink"] .btn-read-later.tone-danger' not in style_source
    eink_layer = style_source.split('===== E-Ink theme', 1)[1]
    assert '.glyph {\n  display: none;' not in eink_layer
    # aria/title 语义保持准确（取消稍后再看 + 详情抓取失败），点击行为不改。
    assert 'detailFailed ? "取消稍后再看（详情抓取失败）"' in app_source

    # 现有三主题不被回退：dark/system 规则仍存在且位于 eink 层之前。
    dark_pos = style_source.index('html[data-theme="dark"] {')
    system_pos = style_source.index('@media (prefers-color-scheme: dark) {')
    eink_pos = style_source.index("===== E-Ink theme")
    assert dark_pos < system_pos < eink_pos


def test_index_theme_init_script_precedes_stylesheet():
    """首帧脚本必须在样式表之前执行，避免普通主题先渲染。"""
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    script_pos = index_source.index("(function () {")
    css_pos = index_source.index('<link rel="stylesheet"')
    js_pos = index_source.index('<script src="/static/app.js')
    assert script_pos < css_pos < js_pos


def _setup_agent_api_fixture(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年8月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-08-27.md").write_text(
        """## Reuters · World（1条）
### [Agent API 新闻](https://example.com/agent-api)
- 发布时间：2026-08-27 09:00:00
- 摘要：不应被研究 Agent 当作完整原文上下文。
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    agent_db_path = tmp_path / "agent_sessions.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_AGENT_DB_PATH", str(agent_db_path))
    monkeypatch.setenv("NEWS_READER_AGENT_RUNTIME_DIR", str(tmp_path / "agent-runtime"))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200
    item = client.get("/api/news?per=20").get_json()["items"][0]
    with app_module.db_conn() as conn:
        stamp = app_module.now_ts()
        with conn:
            conn.execute(
                """
                INSERT INTO article_details(
                  url, source, title, author, published_at, content,
                  content_length, raw_json, fetched_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    "Reuters",
                    item["title"],
                    "Reporter",
                    "2026-08-27 09:00:00",
                    "The complete original article used as the authoritative context.",
                    68,
                    "{}",
                    stamp,
                    stamp,
                ),
            )
    return app_module, client, item, db_path, agent_db_path


def test_agent_session_new_and_clear_are_real_and_idempotent(tmp_path: Path, monkeypatch):
    app_module, client, item, _db_path, agent_db_path = _setup_agent_api_fixture(tmp_path, monkeypatch)

    empty_clear = client.delete(f"/api/news/{item['id']}/agent/session")
    assert empty_clear.status_code == 200
    assert empty_clear.get_json() == {"ok": True, "cleared": True}

    first = client.post(f"/api/news/{item['id']}/agent/session", json={})
    assert first.status_code == 200
    first_id = first.get_json()["session"]["id"]
    old_job = client.post(
        f"/api/news/{item['id']}/agent/jobs",
        json={
            "question": "旧会话问题",
            "quote_text": "旧引用",
            "quote_source": "英文原文引用",
        },
    )
    assert old_job.status_code == 202
    old_job_id = old_job.get_json()["job_id"]
    with app_module.agent_db_conn() as conn:
        with conn:
            conn.execute(
                "UPDATE agent_jobs SET status='failed', error='old_error', finished_at=?, updated_at=? WHERE id=?",
                (app_module.now_ts(), app_module.now_ts(), old_job_id),
            )
    old_runtime = app_module.agent_session_runtime_dir(first_id)
    old_runtime.mkdir(parents=True)
    (old_runtime / "stale-session.json").write_text("stale", encoding="utf-8")

    replaced = client.post(
        f"/api/news/{item['id']}/agent/session",
        json={"new_session": True},
    )
    assert replaced.status_code == 200
    second_id = replaced.get_json()["session"]["id"]
    assert second_id != first_id
    with sqlite3.connect(agent_db_path) as conn:
        assert conn.execute("SELECT id, status FROM agent_sessions").fetchall() == [(second_id, "active")]
        assert conn.execute("SELECT 1 FROM agent_sessions WHERE id=?", (first_id,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM agent_jobs WHERE id=?", (old_job_id,)).fetchone() is None
        assert conn.execute("SELECT COUNT(*) FROM agent_jobs WHERE item_id=?", (item["id"],)).fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM agent_messages WHERE session_id=?", (first_id,)).fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM agent_messages").fetchone() == (0,)
        assert conn.execute(
            "SELECT status FROM agent_sessions WHERE id=?", (second_id,)
        ).fetchone() == ("active",)
    assert not old_runtime.exists()

    first_clear = client.delete(f"/api/news/{item['id']}/agent/session")
    second_clear = client.delete(f"/api/news/{item['id']}/agent/session")
    assert first_clear.status_code == second_clear.status_code == 200
    assert first_clear.get_json()["cleared"] is True
    assert second_clear.get_json()["cleared"] is True
    with sqlite3.connect(agent_db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM agent_sessions").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM agent_jobs").fetchone() == (0,)
        assert conn.execute("SELECT COUNT(*) FROM agent_messages").fetchone() == (0,)


def test_agent_frontend_diagnoses_stale_backend_and_contains_composer():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")

    assert "[404, 405].includes(status)" in app_source
    assert '"agent_api_unavailable"' in app_source
    assert "Agent 后端尚未加载（HTTP ${httpStatus}）" in app_source
    assert "Number.isInteger(error?.httpStatus)" in app_source
    assert "error instanceof TypeError" in app_source
    assert "payload?.error || payload?.message" in app_source
    assert "parseDetailAgentResponse(res, \"agent_session_failed\")" in app_source
    assert "parseDetailAgentResponse(res, \"agent_job_failed\")" in app_source
    assert "detailAgentClearBtn" not in app_source
    assert 'id="detailAgentLauncher"' in index_source
    assert 'id="detailAgentResizeHandle"' in index_source
    assert 'id="detailAgentExpandBtn"' in index_source
    assert 'id="detailChatBody"' in index_source
    assert 'id="detailChatCapability"' not in index_source
    assert "detailChatCapability" not in app_source
    assert "renderDetailChatKeyPoints" not in app_source
    assert "detail-chat-capability" not in style_source
    assert '清空本篇' not in index_source
    assert index_source.index('id="detailAgentLauncher"') < index_source.index('id="detailBody"')
    assert index_source.index('id="detailChatBody"') < index_source.index('id="detailBody"')
    assert "detailChatPanelMaximized" in app_source
    assert "closeDetailAgentPanel();" in app_source
    assert "detailChatBody.contains(target)" in app_source

    panel_rule = style_source[style_source.index(".detail-agent-panel {"):]
    panel_rule = panel_rule[:panel_rule.index("}")]
    assert "display: flex" in panel_rule
    assert "flex-direction: column" in panel_rule
    assert "overflow: hidden" in panel_rule
    assert "position: absolute" in panel_rule
    assert "height: min(66.6667%, 760px)" in panel_rule
    assert "min-height: 240px" in panel_rule
    assert "max-height: calc(100% - 24px)" in panel_rule
    assert "background: var(--agent-panel-bg)" in panel_rule
    assert "box-shadow: 0 18px 44px rgba(15, 23, 42, 0.32), 0 4px 12px rgba(15, 23, 42, 0.18)" in panel_rule
    assert ".detail-agent-panel.is-maximized" in style_source
    assert "height: min(58dvh, 520px)" in style_source
    assert ".detail-agent-launcher" in style_source
    assert ".detail-agent-resize-handle" in style_source
    assert "cursor: ns-resize" in style_source
    assert "touch-action: none" in style_source
    assert "DETAIL_AGENT_HEIGHT_STORAGE_KEY" in app_source
    assert "DETAIL_AGENT_DEFAULT_HEIGHT_RATIO = 2 / 3" in app_source
    assert "state.detailChatPanelHeightCustom" in app_source
    assert "setItem(" in app_source
    assert "state.detailChatPanelMaximized" in app_source
    actions_rule = style_source[style_source.rindex(".detail-agent-actions {"):]
    actions_rule = actions_rule[:actions_rule.index("}")]
    assert "justify-content: flex-start" in actions_rule
    assert "--agent-panel-bg: #f7fbff" in style_source
    assert "--agent-panel-bg: #172033" in style_source
    assert "html[data-theme=\"eink\"] .detail-agent-panel" in style_source
    assert "background-color: #ffffff" in style_source
    agent_rules = style_source[style_source.index(".detail-agent-panel {"):style_source.index(".detail-chat-composer {")]
    assert "max-height: 230px" not in agent_rules
    assert "max-height: 180px" not in agent_rules
    composer_rule = style_source[style_source.index(".detail-agent-panel .detail-chat-composer {"):]
    composer_rule = composer_rule[:composer_rule.index("}")]
    assert "flex: 0 0 auto" in composer_rule
    messages_rule = style_source[style_source.index(".detail-agent-panel .detail-chat-messages {"):]
    messages_rule = messages_rule[:messages_rule.index("}")]
    assert "overflow-y: auto" in style_source[style_source.index(".detail-chat-messages {"):style_source.index(".detail-chat-message {")]
    assert "flex: 1 1 auto" in messages_rule


def test_agent_frontend_height_defaults_persistence_resize_and_mobile_contract():
    """Desktop height is 2/3 by default, while drag persistence and mobile rules stay isolated."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) throw new Error("front-end bootstrap marker missing");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by height regression test");
source = source.replace("let state = {", "var state = {");

const noop = () => {};
const listeners = new Map();
const storage = new Map();
const classList = { add: noop, remove: noop, toggle: noop, contains: () => false };
const makeElement = (id) => {
  const element = {
    id,
    value: "",
    disabled: false,
    hidden: false,
    className: "",
    style: {
      height: "",
      removeProperty(name) { this[name] = ""; },
    },
    classList,
    dataset: {},
    children: [],
    options: [],
    getBoundingClientRect() {
      const height = Number.parseFloat(this.style.height);
      return { height: Number.isFinite(height) && height > 0 ? height : 387 };
    },
    setPointerCapture: noop,
    releasePointerCapture: noop,
    appendChild: noop,
    removeChild: noop,
    replaceChildren: noop,
    setAttribute: noop,
    removeAttribute: noop,
    addEventListener: noop,
    removeEventListener: noop,
    focus: noop,
    blur: noop,
    click: noop,
    querySelector: () => element,
    querySelectorAll: () => [],
  };
  return element;
};
const elements = new Map();
const elementFor = (id) => {
  if (!elements.has(id)) elements.set(id, makeElement(id));
  return elements.get(id);
};
const detailPanel = elementFor("detailPanel");
detailPanel.getBoundingClientRect = () => ({ height: 600 });
const detailChatBody = elementFor("detailChatBody");
const detailAgentResizeHandle = elementFor("detailAgentResizeHandle");
const document = {
  getElementById: elementFor,
  querySelector: () => elementFor("querySelector"),
  querySelectorAll: () => [],
  createElement: () => makeElement("created"),
  addEventListener: noop,
  body: elementFor("body"),
  documentElement: elementFor("documentElement"),
};
const window = {
  addEventListener(name, fn) { listeners.set(name, fn); },
  removeEventListener(name, fn) { if (listeners.get(name) === fn) listeners.delete(name); },
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  getComputedStyle: () => ({ paddingTop: "10px", paddingBottom: "10px", borderTopWidth: "1px", borderBottomWidth: "1px" }),
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  confirm: () => false,
  innerWidth: 1600,
  localStorage: {
    getItem: (key) => storage.has(key) ? storage.get(key) : null,
    setItem: (key, value) => storage.set(key, String(value)),
  },
};
const localStorage = window.localStorage;
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch: noop,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent, Node: function Node() {},
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

function assert(cond, msg) { if (!cond) throw new Error(msg); }
const item = { id: "news-1", url: "https://example.com/news-1" };
context.state.selectedId = item.id;
context.state.itemsById = new Map([[item.id, item]]);
context.state.detailChatPanelOpen = true;
context.state.detailChatPanelMaximized = false;
context.state.detailChatPanelHeightPx = null;
context.state.detailChatPanelHeightCustom = false;
context.syncDetailAgentPanelHeight();
assert(detailChatBody.style.height === "385px", `default height=${detailChatBody.style.height}`);

storage.set("news_reader_detail_agent_height", "420");
context.state.detailChatPanelHeightPx = null;
context.state.detailChatPanelHeightCustom = false;
context.syncDetailAgentPanelHeight();
assert(detailChatBody.style.height === "420px", `stored height=${detailChatBody.style.height}`);

context.startDetailAgentResize({ button: 0, pointerId: 7, clientY: 100, preventDefault: noop, stopPropagation: noop });
context.handleDetailAgentResize({ pointerId: 7, clientY: 50, preventDefault: noop });
context.finishDetailAgentResize({ pointerId: 7 });
assert(detailChatBody.style.height === "470px", `drag height=${detailChatBody.style.height}`);
assert(storage.get("news_reader_detail_agent_height") === "470", `persisted height=${storage.get("news_reader_detail_agent_height")}`);

context.startDetailAgentResize({ button: 0, pointerId: 8, clientY: 100, preventDefault: noop, stopPropagation: noop });
context.handleDetailAgentResize({ pointerId: 8, clientY: 1000, preventDefault: noop });
context.finishDetailAgentResize({ pointerId: 8 });
assert(detailChatBody.style.height === "240px", `minimum height=${detailChatBody.style.height}`);

context.state.detailChatPanelMaximized = true;
context.syncDetailAgentPanelHeight();
assert(detailChatBody.style.height === "", "maximize did not remove inline height");
context.state.detailChatPanelMaximized = false;
context.syncDetailAgentPanelHeight();
assert(detailChatBody.style.height === "240px", `restore height=${detailChatBody.style.height}`);

window.innerWidth = 390;
context.syncDetailAgentPanelHeight();
assert(detailChatBody.style.height === "", "mobile sync unexpectedly kept inline height");
context.startDetailAgentResize({ button: 0, pointerId: 9, clientY: 100, preventDefault: noop, stopPropagation: noop });
assert(detailChatBody.style.height === "", "mobile resize unexpectedly started");
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_agent_frontend_diagnostics_preserve_actual_http_status():
    """Agent diagnostics must retain non-JSON HTTP status and business errors."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) throw new Error("front-end bootstrap marker missing");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by diagnostics regression test");

const noop = () => {};
const element = new Proxy(noop, {
  get(target, prop) {
    if (["addEventListener", "removeEventListener", "appendChild", "removeChild", "setAttribute", "removeAttribute", "focus", "blur", "click"].includes(prop)) return noop;
    if (["querySelectorAll", "getElementsByTagName"].includes(prop)) return () => [];
    if (prop === "querySelector") return () => element;
    if (prop === "classList") return { add: noop, remove: noop, toggle: noop, contains: () => false };
    if (prop === "style" || prop === "dataset") return element;
    if (prop === "children" || prop === "options") return [];
    if (prop === "length") return 0;
    if (["value", "textContent", "innerHTML", "className"].includes(prop)) return "";
    if (["checked", "disabled"].includes(prop)) return false;
    if (prop === Symbol.iterator) return function* () {};
    return element;
  },
  set() { return true; },
  apply() { return undefined; },
});
const document = {
  getElementById: () => element,
  querySelector: () => element,
  querySelectorAll: () => [],
  createElement: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
const localStorage = { getItem: () => null, setItem: noop };
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch: noop,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

function assert(cond, msg) { if (!cond) throw new Error(msg); }
async function diagnose(response) {
  try {
    await context.parseDetailAgentResponse(response, "agent_job_failed");
    throw new Error("expected response failure");
  } catch (error) {
    return { error, message: context.detailAgentErrorMessage(error, "fallback") };
  }
}
function nonJsonResponse(status) {
  return { ok: false, status, json: async () => { throw new Error("HTML response"); } };
}

(async () => {
  const stale = await diagnose(nonJsonResponse(404));
  assert(stale.error.httpStatus === 404, "404 status was not retained");
  assert(stale.message.includes("HTTP 404"), `404 message=${stale.message}`);

  const method = await diagnose(nonJsonResponse(405));
  assert(method.error.httpStatus === 405, "405 status was not retained");
  assert(method.message.includes("HTTP 405"), `405 message=${method.message}`);
  assert(!method.message.includes("HTTP 404"), `405 was misreported: ${method.message}`);

  const other = await diagnose(nonJsonResponse(502));
  assert(other.error.httpStatus === 502, "502 status was not retained");
  assert(other.message.includes("HTTP 502"), `502 message=${other.message}`);

  const connectionError = vm.runInContext('new TypeError("Failed to fetch")', context);
  const connection = context.detailAgentErrorMessage(connectionError, "fallback");
  assert(connection.includes("无法连接 Agent 后端"), `connection message=${connection}`);
  assert(!/HTTP \d+/.test(connection), `connection fabricated a status: ${connection}`);

  const business = await diagnose({
    ok: false,
    status: 405,
    json: async () => ({ ok: false, error: "detail_not_ready" }),
  });
  assert(business.message === "正文尚未抓取完成，暂时不能提问。", `business message=${business.message}`);
  assert(!business.message.includes("HTTP 405"), `business error was replaced: ${business.message}`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_agent_frontend_clears_transient_status_after_job_success():
    """Successful send/retry must remove the transient creating-task status."""
    script = r'''
const fs = require("fs");
const vm = require("vm");
let source = fs.readFileSync("static/app.js", "utf8");
if (!source.includes("\nautoReindexAndLoad();")) throw new Error("front-end bootstrap marker missing");
source = source.replace("\nautoReindexAndLoad();", "\n// bootstrap skipped by job status regression test");
source = source.replace("let state = {", "var state = {");
const renderStart = source.indexOf("function renderDetailChat(item) {");
const sendStart = source.indexOf("async function sendDetailChatMessage()", renderStart);
if (renderStart < 0 || sendStart < 0) throw new Error("agent render/send functions missing");
source = source.slice(0, renderStart) + "function renderDetailChat(item) {}\n\n" + source.slice(sendStart);

const noop = () => {};
const target = {
  value: "",
  disabled: false,
  className: "",
  classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
};
const element = new Proxy(target, {
  get(obj, prop) {
    if (prop in obj) return obj[prop];
    if (["children", "options"].includes(prop)) return [];
    if (prop === Symbol.iterator) return function* () {};
    return noop;
  },
  set(obj, prop, value) { obj[prop] = value; return true; },
});
const document = {
  getElementById: () => element,
  querySelector: () => element,
  querySelectorAll: () => [],
  createElement: () => element,
  addEventListener: noop,
  body: element,
  documentElement: element,
};
class IntersectionObserver { constructor() {} observe() {} disconnect() {} }
const localStorage = { getItem: () => null, setItem: noop };
const window = {
  addEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  confirm: () => false,
  innerWidth: 1200,
  localStorage,
};
const jobPayload = {
  ok: true,
  agent: {
    session: { id: "session-1", provider: "pi", model: "pi-test" },
    messages: [{ id: "message-1", job_id: "job-1", role: "assistant", content: "完成", status: "succeeded" }],
    jobs: [{ id: "job-1", status: "succeeded", created_at: "2026-08-28T00:00:00Z", answer_text: "完成" }],
  },
};
let fetchMode = "success";
const fetch = async (url, init = {}) => {
  if (fetchMode === "send-failure" || fetchMode === "retry-failure") {
    return { ok: false, status: 500, json: async () => ({ ok: false, error: "agent_job_failed" }) };
  }
  return { ok: true, status: 202, json: async () => jobPayload };
};
const context = {
  console, document, window, localStorage, IntersectionObserver, fetch,
  URLSearchParams, Date, Map, Set, JSON, encodeURIComponent,
  setTimeout, clearTimeout, setInterval, clearInterval,
};
vm.createContext(context);
vm.runInContext(source, context, { filename: "static/app.js" });

function assert(cond, msg) { if (!cond) throw new Error(msg); }
(async () => {
  const item = { id: "news-1", url: "https://example.com/news-1" };
  context.state.selectedId = item.id;
  context.state.itemsById = new Map([[item.id, item]]);
  context.state.detailChatSession = { id: "session-1", provider: "pi", model: "pi-test" };
  context.state.detailChatStatus = "正在创建后台研究任务…";
  element.value = "请总结";
  await context.sendDetailChatMessage();
  assert(context.state.detailChatStatus === "", `send status=${context.state.detailChatStatus}`);
  assert(context.state.detailChatSending === false, "send remained busy");

  await context.retryDetailAgentJob(item, "old-job");
  assert(context.state.detailChatStatus === "", `retry status=${context.state.detailChatStatus}`);
  assert(context.state.detailChatSending === false, "retry remained busy");

  fetchMode = "send-failure";
  element.value = "失败路径";
  await context.sendDetailChatMessage();
  assert(context.state.detailChatStatus.includes("后台研究任务创建失败"), `send failure status=${context.state.detailChatStatus}`);

  fetchMode = "retry-failure";
  await context.retryDetailAgentJob(item, "old-job");
  assert(context.state.detailChatStatus === "重试失败，请稍后重试。", `retry failure status=${context.state.detailChatStatus}`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
'''
    subprocess.run(["node", "-e", textwrap.dedent(script)], check=True)


def test_agent_first_and_follow_up_use_one_full_pi_session(tmp_path: Path, monkeypatch):
    app_module, client, item, _db_path, agent_db_path = _setup_agent_api_fixture(tmp_path, monkeypatch)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_pi = fake_bin / "pi"
    fake_pi.write_text(
        "#!/bin/sh\nprintf '%s\\0' \"$@\" >> \"$PI_ARGS_LOG\"\nprintf '%s\\0' '__CALL_END__' >> \"$PI_ARGS_LOG\"\nprintf '%s\\n' '{\"type\":\"session\",\"id\":\"pi-output-session\"}' '{\"type\":\"message_update\",\"assistantMessageEvent\":{\"type\":\"text_delta\",\"delta\":\"完成\"}}'\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    args_log = tmp_path / "pi-args.log"
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.setenv("PI_ARGS_LOG", str(args_log))

    first = client.post(f"/api/news/{item['id']}/agent/jobs", json={"question": "首问"})
    assert first.status_code == 202
    session_id = first.get_json()["session"]["id"]
    assert app_module.process_pending_agent_once() is True

    second = client.post(
        f"/api/news/{item['id']}/agent/jobs",
        json={"question": "依赖上一轮的追问", "session_id": session_id},
    )
    assert second.status_code == 202
    assert app_module.process_pending_agent_once() is True

    calls: list[list[str]] = [[]]
    for raw in args_log.read_bytes().split(b"\0"):
        if not raw:
            continue
        value = raw.decode("utf-8")
        if value == "__CALL_END__":
            calls.append([])
        else:
            calls[-1].append(value)
    calls = [call for call in calls if call]
    assert len(calls) == 2
    expected_executor_id = f"newsreader-agent-full-{session_id}"
    assert all(call[call.index("--session-id") + 1] == expected_executor_id for call in calls)
    assert calls[0][calls[0].index("--session-dir") + 1] == calls[1][calls[1].index("--session-dir") + 1]
    assert "complete original article" in calls[0][-1]
    assert "首问" in calls[0][-1]
    assert "complete original article" not in calls[1][-1]
    assert "首问" not in calls[1][-1]
    assert calls[1][-1].endswith("本轮用户问题：依赖上一轮的追问")
    restricted_flags = {
        "--tools", "--no-extensions", "--no-builtin-tools", "--no-context-files",
        "--no-skills", "--no-prompt-templates", "--no-themes",
    }
    assert not restricted_flags.intersection(calls[0] + calls[1])
    with sqlite3.connect(agent_db_path) as conn:
        assert conn.execute(
            "SELECT executor_session_id FROM agent_sessions WHERE id=?", (session_id,)
        ).fetchone() == (expected_executor_id,)


def test_agent_existing_temp_db_is_migrated_before_session_use(tmp_path: Path, monkeypatch):
    agent_db_path = tmp_path / "agent_sessions.sqlite3"
    with sqlite3.connect(agent_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE agent_sessions (
              id TEXT PRIMARY KEY,
              item_id TEXT NOT NULL,
              url TEXT NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL DEFAULT '',
              executor_session_id TEXT NOT NULL DEFAULT '',
              context_hash TEXT NOT NULL,
              context_json TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              created_at TEXT NOT NULL,
              last_activity_at TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
    monkeypatch.setenv("NEWS_READER_AGENT_DB_PATH", str(agent_db_path))
    monkeypatch.setenv("NEWS_READER_AGENT_RUNTIME_DIR", str(tmp_path / "agent-runtime"))
    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_agent_db()
    with sqlite3.connect(agent_db_path) as conn:
        session_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(agent_sessions)").fetchall()
        }
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
    assert "executor_provider" in session_columns
    assert {"agent_sessions", "agent_jobs", "agent_messages"}.issubset(tables)


def test_agent_legacy_pi_session_switches_with_one_time_visible_history(tmp_path: Path, monkeypatch):
    app_module, _client, item, _db_path, _agent_db_path = _setup_agent_api_fixture(tmp_path, monkeypatch)
    with app_module.db_conn() as conn:
        detail = conn.execute("SELECT * FROM article_details WHERE url=?", (item["url"],)).fetchone()
    context = app_module.build_agent_context(item, detail)
    legacy_id = "newsreader-agent-legacy-session"
    legacy_runtime = app_module.agent_session_runtime_dir(legacy_id)
    legacy_runtime.mkdir(parents=True)
    (legacy_runtime / "old-session.jsonl").write_text("legacy", encoding="utf-8")

    command, _env, runtime_dir = app_module._agent_process_command(
        {"provider": "pi", "model": "minimax-m3:cloud", "question": "新问题", "quote_text": "",},
        {"id": "session-legacy", "executor_provider": "ollama", "executor_session_id": legacy_id},
        context,
        [{"role": "user", "content": "旧问题"}, {"role": "assistant", "content": "旧回答"}],
    )
    assert command[command.index("--session-id") + 1] == "newsreader-agent-full-session-legacy"
    assert str(runtime_dir).endswith("newsreader-agent-full-session-legacy")
    assert "complete original article" in command[-1]
    assert "此前会话记录（仅用于连续对话）" in command[-1]
    assert "旧问题" in command[-1]
    assert "旧回答" in command[-1]
    assert not legacy_runtime.exists()

    pi_session = {
        "id": "session-legacy",
        "executor_provider": "ollama",
        "executor_session_id": "newsreader-agent-full-session-legacy",
    }
    follow_up, _env, _runtime_dir = app_module._agent_process_command(
        {"provider": "pi", "model": "minimax-m3:cloud", "question": "再问", "quote_text": ""},
        pi_session,
        context,
        [{"role": "user", "content": "旧问题"}, {"role": "assistant", "content": "旧回答"}],
    )
    assert follow_up[-1].endswith("本轮用户问题：再问")
    assert "此前会话记录（仅用于连续对话）" not in follow_up[-1]
    assert "旧问题" not in follow_up[-1]
    assert "旧回答" not in follow_up[-1]


def test_agent_legacy_pi_migration_persists_and_stops_replaying_history(tmp_path: Path, monkeypatch):
    app_module, client, item, _db_path, agent_db_path = _setup_agent_api_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "_agent_provider_model", lambda: ("pi", "minimax-m3:cloud", "ollama"))
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_pi = fake_bin / "pi"
    fake_pi.write_text(
        "#!/bin/sh\nprintf '%s\\0' \"$@\" >> \"$PI_ARGS_LOG\"\nprintf '%s\\0' '__CALL_END__' >> \"$PI_ARGS_LOG\"\nprintf '%s\\n' '{\"type\":\"session\",\"id\":\"pi-output-session\"}' '{\"type\":\"message_update\",\"assistantMessageEvent\":{\"type\":\"text_delta\",\"delta\":\"完成\"}}'\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    args_log = tmp_path / "pi-args.log"
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.setenv("PI_ARGS_LOG", str(args_log))

    first = client.post(f"/api/news/{item['id']}/agent/jobs", json={"question": "旧问题"})
    assert first.status_code == 202
    first_payload = first.get_json()
    session_id = first_payload["session"]["id"]
    legacy_id = "newsreader-agent-legacy-session"
    with sqlite3.connect(agent_db_path) as conn:
        stamp = app_module.now_ts()
        with conn:
            conn.execute(
                "UPDATE agent_sessions SET executor_session_id=? WHERE id=?",
                (legacy_id, session_id),
            )
            conn.execute(
                "UPDATE agent_jobs SET status='succeeded', answer_text='旧回答', finished_at=?, updated_at=? WHERE id=?",
                (stamp, stamp, first_payload["job_id"]),
            )
            conn.execute(
                "UPDATE agent_messages SET content='旧回答', status='succeeded', updated_at=? WHERE job_id=? AND role='assistant'",
                (stamp, first_payload["job_id"]),
            )

    second = client.post(
        f"/api/news/{item['id']}/agent/jobs",
        json={"question": "新问题", "session_id": session_id},
    )
    assert second.status_code == 202
    assert app_module.process_pending_agent_once() is True

    third = client.post(
        f"/api/news/{item['id']}/agent/jobs",
        json={"question": "再问", "session_id": session_id},
    )
    assert third.status_code == 202
    assert app_module.process_pending_agent_once() is True

    calls: list[list[str]] = [[]]
    for raw in args_log.read_bytes().split(b"\0"):
        if not raw:
            continue
        value = raw.decode("utf-8")
        if value == "__CALL_END__":
            calls.append([])
        else:
            calls[-1].append(value)
    calls = [call for call in calls if call]
    assert len(calls) == 2
    assert "旧问题" in calls[0][-1]
    assert "旧回答" in calls[0][-1]
    assert "此前会话记录（仅用于连续对话）" not in calls[1][-1]
    assert "旧问题" not in calls[1][-1]
    assert "旧回答" not in calls[1][-1]
    with sqlite3.connect(agent_db_path) as conn:
        stored = conn.execute(
            "SELECT executor_session_id FROM agent_sessions WHERE id=?", (session_id,)
        ).fetchone()
    assert stored == (f"newsreader-agent-full-{session_id}",)


def test_agent_ttl_setting_persists_and_ui_exposes_cleanup_controls(tmp_path: Path, monkeypatch):
    app_module, client, _item, _db_path, _agent_db_path = _setup_agent_api_fixture(tmp_path, monkeypatch)
    assert client.get("/api/settings").get_json()["agent"]["session_ttl_hours"] == 72
    saved = client.put(
        "/api/settings",
        json={
            "llm": {"translation": {"provider": "deepseek", "model": ""}},
            "agent": {"session_ttl_hours": 24},
        },
    )
    assert saved.status_code == 200
    assert saved.get_json()["agent"]["session_ttl_hours"] == 24
    assert app_module.load_app_settings()["agent"]["session_ttl_hours"] == 24
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    assert 'id="settingsAgentTtlSelect"' in index_source
    assert 'id="settingsAgentClearAllBtn"' in index_source
    assert 'id="detailAgentNewBtn"' in index_source
    assert 'id="detailAgentClearBtn"' not in index_source
    assert "payload.agent.session_ttl_hours = draftAgentTtl;" in app_source
    assert "clearAllAgentSessions();" in app_source
