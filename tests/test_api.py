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
    # 默认隔离 app_settings：指向不存在的路径 → load_app_settings 返回 DEFAULT（chat.provider=codex），
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


def test_ai_fallback_to_codex_success(tmp_path: Path, monkeypatch):
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
            "model": "codex-fallback",
            "key_points_zh": ["要点一", "要点二", "要点三"],
            "conclusion_zh": "兜底结论",
            "body_zh": "这是 Codex 保底译文。",
            "raw_json": '{"provider":"codex-fallback-structured","structured_success":true}',
        }

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_codex_fallback_translation", succeed_fallback)

    assert app_module.process_pending_ai_once() is True

    with app_module.db_conn() as conn:
        ai_row = conn.execute(
            "SELECT model, key_points_zh, conclusion_zh, body_zh, raw_json FROM article_ai WHERE url=?",
            ("https://example.com/fallback",),
        ).fetchone()
        job_row = conn.execute(
            "SELECT status, last_error FROM ai_jobs WHERE url=?",
            ("https://example.com/fallback",),
        ).fetchone()

    assert ai_row["model"] == "codex-fallback"
    assert ai_row["body_zh"] == "这是 Codex 保底译文。"
    assert ai_row["key_points_zh"] == '["要点一", "要点二", "要点三"]'
    assert ai_row["conclusion_zh"] == "兜底结论"
    assert "codex-fallback-structured" in ai_row["raw_json"]
    assert job_row["status"] == "success"
    assert job_row["last_error"] is None


def test_ai_fallback_to_codex_failure_keeps_error(tmp_path: Path, monkeypatch):
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
        raise app_module.LLMClientError("CODEX_FALLBACK_FAILED: bridge down")

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_codex_fallback_translation", fail_fallback)

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
    assert "CODEX_FALLBACK_FAILED" in job_row["last_error"]


def test_ai_fallback_to_codex_body_only_degrades_cleanly(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))

    import app as app_module

    importlib.reload(app_module)
    app_module.ensure_db()
    client = app_module.app.test_client()

    with app_module.db_conn() as conn:
        conn.execute(
            """
            INSERT INTO source_files(path, mtime, size, last_scanned_at, item_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "dailyFreshNews_2026-06-04.md",
                1717488000.0,
                123,
                "2026-06-04 16:59:00",
                1,
            ),
        )
        conn.execute(
            """
            INSERT INTO items(
              id, source_file, item_order, published_at, date, time, source, source_type,
              source_name, title, summary, url, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "fallback-body-item",
                "dailyFreshNews_2026-06-04.md",
                1,
                "2026-06-04 17:00:00",
                "2026-06-04",
                "17:00:00",
                "Reuters",
                "article",
                "Reuters",
                "Fallback body title",
                "Fallback body summary",
                "https://example.com/fallback-body",
                "2026-06-04 17:00:00",
                "2026-06-04 17:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO article_details(url, title, source, content, content_length, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/fallback-body",
                "Fallback body title",
                "Reuters",
                "Original english body",
                21,
                "2026-06-04 17:00:00",
                "2026-06-04 17:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO article_ai(url, model, key_points_zh, conclusion_zh, body_zh, raw_json, generated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/fallback-body",
                "codex-fallback",
                "[]",
                "",
                "这是只有正文的兜底翻译。",
                '{"provider":"codex-fallback-body-only","structured_success":false,"structured_error":"INVALID_JSON"}',
                "2026-06-04 17:10:00",
                "2026-06-04 17:10:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO ai_jobs(url, status, attempts, queued_at, started_at, finished_at, updated_at)
            VALUES (?, 'success', 1, ?, ?, ?, ?)
            """,
            (
                "https://example.com/fallback-body",
                "2026-06-04 17:01:00",
                "2026-06-04 17:02:00",
                "2026-06-04 17:03:00",
                "2026-06-04 17:03:00",
            ),
        )

    detail_res = client.get("/api/news/fallback-body-item/detail")
    assert detail_res.status_code == 200
    payload = detail_res.get_json()
    assert payload["ai"]["model"] == "codex-fallback"
    assert payload["ai"]["key_points_zh"] == "[]"
    assert payload["ai"]["conclusion_zh"] == ""
    assert "codex-fallback-body-only" in payload["ai"]["raw_json"]


def test_ai_fallback_to_pi_success_when_provider_pi(tmp_path: Path, monkeypatch):
    # provider=pi 时 DeepSeek 翻译失败 → 走 generate_pi_fallback_translation，不走 Codex。
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    assert app_module.current_chat_provider() == "pi"
    app_module.ensure_db()

    with app_module.db_conn() as conn:
        conn.execute(
            """
            INSERT INTO article_details(url, title, source, content, content_length, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/pi-fallback",
                "Pi fallback title",
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
            ("https://example.com/pi-fallback", "2026-06-04 17:01:00", "2026-06-04 17:01:00"),
        )

    def fail_primary(**kwargs):
        raise app_module.LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: bad json")

    pi_called = {}
    codex_called = {}

    def succeed_pi(**kwargs):
        pi_called.update(kwargs)
        return {
            "model": "minimax-m3:cloud",
            "key_points_zh": ["要点一", "要点二", "要点三"],
            "conclusion_zh": "Pi 兜底结论",
            "body_zh": "这是 Pi 保底译文。",
            "raw_json": '{"provider":"pi-fallback-structured","structured_success":true}',
        }

    def codex_should_not_run(**kwargs):
        codex_called.update(kwargs)
        return {"model": "codex-fallback", "key_points_zh": [], "conclusion_zh": "", "body_zh": "不应走 Codex", "raw_json": "{}"}

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_pi_fallback_translation", succeed_pi)
    monkeypatch.setattr(app_module, "generate_codex_fallback_translation", codex_should_not_run)

    assert app_module.process_pending_ai_once() is True

    with app_module.db_conn() as conn:
        ai_row = conn.execute(
            "SELECT model, body_zh, raw_json FROM article_ai WHERE url=?",
            ("https://example.com/pi-fallback",),
        ).fetchone()
        job_row = conn.execute("SELECT status, last_error FROM ai_jobs WHERE url=?", ("https://example.com/pi-fallback",)).fetchone()

    assert ai_row["model"] == "minimax-m3:cloud"
    assert ai_row["body_zh"] == "这是 Pi 保底译文。"
    assert "pi-fallback-structured" in ai_row["raw_json"]
    assert job_row["status"] == "success"
    assert pi_called, "provider=pi 时翻译兜底应走 generate_pi_fallback_translation"
    assert not codex_called, "provider=pi 时翻译兜底不应再走 Codex"


def test_ai_fallback_to_pi_failure_does_not_implicitly_use_codex(tmp_path: Path, monkeypatch):
    # provider=pi 时 Pi 兜底失败 → 只记录失败，不隐式回退 Codex。
    daily_dir = tmp_path / "DailyNews"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(daily_dir))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

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
                "https://example.com/pi-fallback-fail",
                "Pi fallback fail title",
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
            ("https://example.com/pi-fallback-fail", "2026-06-04 17:01:00", "2026-06-04 17:01:00"),
        )

    def fail_primary(**kwargs):
        raise app_module.LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: bad json")

    def fail_pi(**kwargs):
        raise app_module.LLMClientError("PI_FALLBACK_FAILED: timeout")

    codex_called = {}

    def codex_should_not_run(**kwargs):
        codex_called.update(kwargs)
        return {"model": "codex-fallback", "key_points_zh": [], "conclusion_zh": "", "body_zh": "不应走 Codex", "raw_json": "{}"}

    monkeypatch.setattr(app_module, "generate_article_ai", fail_primary)
    monkeypatch.setattr(app_module, "generate_pi_fallback_translation", fail_pi)
    monkeypatch.setattr(app_module, "generate_codex_fallback_translation", codex_should_not_run)

    assert app_module.process_pending_ai_once() is True

    with app_module.db_conn() as conn:
        job_row = conn.execute("SELECT status, last_error FROM ai_jobs WHERE url=?", ("https://example.com/pi-fallback-fail",)).fetchone()

    assert job_row["status"] == "failed"
    assert job_row["last_error"] is not None
    assert not codex_called, "Pi 兜底失败不应隐式回退 Codex"


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


def test_news_chat_without_detail_uses_summary_context(tmp_path: Path, monkeypatch):
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
    with app_module.db_conn() as conn:
        with conn:
            conn.execute(
                "UPDATE items SET summary=? WHERE id=?",
                ("Fallback summary for chat route tests.", item["id"]),
            )

    captured = {}

    def fake_run_codex_chat(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "codex",
            "session_id": "summary-session",
            "model": kwargs["model"],
            "answer": "Fallback 回答",
        }

    monkeypatch.setattr(app_module, "run_codex_chat", fake_run_codex_chat)
    res = client.post(
        f"/api/news/{item['id']}/chat",
        json={"question": "这是什么意思？"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["ok"] is True
    assert payload["context_level"] == "summary_context"
    assert payload["context_label"] == "摘要与元数据"
    assert captured["context_level"] == "summary_context"
    assert "Fallback summary for chat route tests." in captured["content"]
    assert "https://example.com/chat-pending" in captured["content"]
    assert "Reuters" in captured["content"]


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
    assert payload["context_level"] == "full_detail"
    assert payload["context_label"] == "完整正文"
    assert captured["title"] == "Chat Ready"
    assert captured["content"] == "Full english body for chat route tests."
    assert captured["context_level"] == "full_detail"
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
    assert resume_res.get_json()["context_level"] == "full_detail"
    assert captured["session_id"] == "session-456"
    assert captured["question"] == "最新进展？"
    assert captured["model"] == "gpt-5-codex"
    assert captured["context_level"] == "full_detail"


def test_news_chat_twitter_skipped_detail_uses_summary_context(tmp_path: Path, monkeypatch):
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
        ts = app_module.now_ts()
        with conn:
            conn.execute(
                "UPDATE items SET source=?, source_name=?, source_type=?, summary=? WHERE id=?",
                ("Twitter", "Twitter", "twitter", "Tweet summary context.", item["id"]),
            )
            conn.execute(
                """
                INSERT INTO detail_jobs(url, item_id, source, status, attempts, last_error, queued_at, started_at, finished_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    item["id"],
                    "Twitter",
                    "skipped",
                    "TWITTER_SKIPPED",
                    ts,
                    ts,
                    ts,
                    ts,
                ),
            )

    captured = {}

    def fake_run_codex_chat(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "codex",
            "session_id": "tweet-session",
            "model": kwargs["model"],
            "answer": "推文 fallback 回答",
        }

    monkeypatch.setattr(app_module, "run_codex_chat", fake_run_codex_chat)
    res = client.post(
        f"/api/news/{item['id']}/chat",
        json={"question": "这条推文在说什么？"},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["ok"] is True
    assert payload["context_level"] == "summary_context"
    assert payload["context_label"] == "摘要与元数据"
    assert captured["context_level"] == "summary_context"
    assert "来源类型：twitter" in captured["content"]
    assert "Tweet summary context." in captured["content"]


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


def test_frontend_is_v219_without_later_visual_experiments():
    app_source = Path("/Users/x/news-reader/news-reader/static/app.js").read_text(encoding="utf-8")
    index_source = Path("/Users/x/news-reader/news-reader/static/index.html").read_text(encoding="utf-8")
    style_source = Path("/Users/x/news-reader/news-reader/static/style.css").read_text(encoding="utf-8")
    review_styles = style_source.split("/* ===== Review (复盘) styles ===== */", 1)[1]

    assert "News Reader v2.1.0.9" in app_source
    assert "News Reader v2.1.0.9" in index_source
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


def test_news_chat_archive_success_and_append(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive](https://example.com/chat-archive)
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

    monkeypatch.setattr(
        app_module,
        "run_codex_chat_archive",
        lambda **kwargs: {
            "provider": "codex",
            "model": kwargs["model"],
            "summary": "关注财报兑现与全年指引是否同时改善。",
        },
    )

    first = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "我真正要看什么？"},
                {"role": "assistant", "content": "重点看财报兑现与全年指引。"},
            ],
            "model": "gpt-5-codex",
        },
    )
    assert first.status_code == 200
    first_payload = first.get_json()
    assert first_payload["ok"] is True
    assert first_payload["archive_summary"] == "关注财报兑现与全年指引是否同时改善。"
    assert "【Chat 归档｜" in first_payload["note"]["note"]
    assert "关注财报兑现与全年指引是否同时改善。" in first_payload["note"]["note"]

    assert client.put(f"/api/news/{item['id']}/note", json={"note": "已有想法"}).status_code == 200

    second = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "下一步怎么跟？"},
                {"role": "assistant", "content": "等财报后再看指引是否确认拐点。"},
            ]
        },
    )
    assert second.status_code == 200
    second_note = second.get_json()["note"]["note"]
    assert second_note.startswith("已有想法")
    assert "\n\n---\n【Chat 归档｜" in second_note


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


def test_news_chat_archive_note_too_long_keeps_old_note(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive Long](https://example.com/chat-archive-long)
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
    long_note = "旧想法" + ("A" * 4988)
    assert client.put(f"/api/news/{item['id']}/note", json={"note": long_note}).status_code == 200

    monkeypatch.setattr(
        app_module,
        "run_codex_chat_archive",
        lambda **kwargs: {
            "provider": "codex",
            "model": kwargs["model"],
            "summary": "这是一个不会被写入的归档摘要。",
        },
    )

    res = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "总结一下"},
                {"role": "assistant", "content": "好的。"},
            ]
        },
    )
    assert res.status_code == 409
    assert res.get_json()["error"] == "note_too_long"
    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["note"]["note"] == long_note


def test_news_chat_archive_provider_failure_does_not_write_note(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive Fail](https://example.com/chat-archive-fail)
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
    monkeypatch.setattr(
        app_module,
        "run_codex_chat_archive",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("codex_failed")),
    )

    res = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "总结一下"},
                {"role": "assistant", "content": "好的。"},
            ]
        },
    )
    assert res.status_code == 502
    assert res.get_json()["error"] == "provider_failed"
    detail = client.get(f"/api/news/{item['id']}/detail").get_json()
    assert detail["has_note"] == 0
    assert detail["note"] is None


def test_news_chat_archive_accepts_200_chars(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive 200](https://example.com/chat-archive-200)
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
    summary = "甲" * 150
    monkeypatch.setattr(
        app_module,
        "run_codex_chat_archive",
        lambda **kwargs: {"provider": "codex", "model": kwargs["model"], "summary": summary},
    )
    res = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "总结一下"},
                {"role": "assistant", "content": "好的。"},
            ]
        },
    )
    assert res.status_code == 200
    assert res.get_json()["archive_summary"] == summary


def test_news_chat_archive_follows_pi_provider(tmp_path: Path, monkeypatch):
    # 归档跟随当前 Chat provider：provider=pi 时归档走 run_pi_chat_archive，不再走 Codex。
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive Pi](https://example.com/chat-archive-pi)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    assert app_module.current_chat_provider() == "pi"
    app_module.ensure_db()
    client = app_module.app.test_client()
    assert client.post("/api/reindex", json={}).status_code == 200

    item = client.get("/api/news?per=20").get_json()["items"][0]

    pi_archive_called = {}
    codex_archive_called = {}

    def fake_pi_archive(**kwargs):
        pi_archive_called.update(kwargs)
        return {"provider": "pi", "model": kwargs["pi_model"], "summary": "Pi 归档结论。"}

    def fake_codex_archive(**kwargs):
        codex_archive_called.update(kwargs)
        return {"provider": "codex", "model": kwargs["model"], "summary": "不应走 Codex"}

    monkeypatch.setattr(app_module, "run_pi_chat_archive", fake_pi_archive)
    monkeypatch.setattr(app_module, "run_codex_chat_archive", fake_codex_archive)
    res = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "总结"},
                {"role": "assistant", "content": "Pi 归档结论。"},
            ]
        },
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["ok"] is True
    assert payload["provider"] == "pi"
    assert payload["model"] == "minimax-m3:cloud"
    assert payload["archive_summary"] == "Pi 归档结论。"
    assert pi_archive_called, "provider=pi 时归档应走 run_pi_chat_archive"
    assert not codex_archive_called, "provider=pi 时归档不应再走 Codex"


def test_news_chat_archive_pi_timeout_maps_to_provider_timeout(tmp_path: Path, monkeypatch):
    # provider=pi 时归档超时映射到中性错误码 provider_timeout（504），不引入 provider 专属码。
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive Pi Timeout](https://example.com/chat-archive-pi-timeout)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
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
    monkeypatch.setattr(
        app_module, "run_pi_chat_archive", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("pi_timeout"))
    )
    res = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "总结"},
                {"role": "assistant", "content": "内容"},
            ]
        },
    )
    assert res.status_code == 504
    assert res.get_json()["error"] == "provider_timeout"


def test_news_chat_archive_pi_empty_maps_to_empty_summary(tmp_path: Path, monkeypatch):
    # provider=pi 时归档返回空摘要 → 中性 empty_archive_summary（502）。
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    (daily_dir / "dailyFreshNews_2026-06-11.md").write_text(
        """## Reuters · World（1条）
### [Chat Archive Pi Empty](https://example.com/chat-archive-pi-empty)
- 发布时间：2026-06-11 09:00:00
""",
        encoding="utf-8",
    )
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
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
    monkeypatch.setattr(
        app_module, "run_pi_chat_archive", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("pi_empty_archive"))
    )
    res = client.post(
        f"/api/news/{item['id']}/chat/archive",
        json={
            "messages": [
                {"role": "user", "content": "总结"},
                {"role": "assistant", "content": "内容"},
            ]
        },
    )
    assert res.status_code == 502
    assert res.get_json()["error"] == "empty_archive_summary"


def test_run_codex_chat_builds_exec_and_resume_commands(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    commands = []
    timeouts = []

    def fake_run(command, capture_output, text, timeout, cwd):
        commands.append(command)
        timeouts.append(timeout)
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
        context_level="full_detail",
        model="gpt-5-codex",
    )
    resumed = app_module.run_codex_chat(
        question="继续说",
        session_id="first-session",
        title="Test",
        source="Reuters",
        published_at="2026-06-11 09:00:00",
        content="Body",
        context_level="full_detail",
        model="gpt-5-codex",
    )

    assert first["session_id"] == "first-session"
    assert resumed["session_id"] == "resume-session"
    assert commands[0][0:2] == ["codex", "exec"]
    assert "resume" not in commands[0]
    assert "--last" not in commands[0]
    assert commands[0][2].startswith("你是一名新闻研究助手。用户当前围绕一篇新闻提问。")
    assert "给你的新闻内容主要用于理解提问场景，不代表答案一定存在于文中。" in commands[0][2]
    assert "如果用户问的是背景、最新进展、实时数据、影响判断或文中没有的细节，应主动搜索最新且可靠的信息后再回答。" in commands[0][2]
    assert "回答时明确区分哪些信息来自新闻上下文，哪些来自你后续搜索到的信息。" in commands[0][2]
    assert "新闻标题：Test" in commands[0][2]
    assert "新闻来源：Reuters" in commands[0][2]
    assert "发布时间：2026-06-11 09:00:00" in commands[0][2]
    assert "上下文级别：full_detail" in commands[0][2]
    assert "以下包含新闻完整正文。回答原文内容、总结或作者观点时，优先基于正文；若用户追问背景、最新进展、实时数据或文外细节，仍应主动搜索补充。" in commands[0][2]
    assert "新闻上下文：\nBody" in commands[0][2]
    assert "用户问题：什么是 codex exec？" in commands[0][2]
    assert commands[1][0:4] == ["codex", "exec", "resume", "first-session"]
    assert "--last" not in commands[1]
    assert timeouts == [180, 180]


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
    monkeypatch.setattr(app_module.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)

    class DummyResponse:
        def __init__(self, payload):
            self.payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        def read(self):
            return self.payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        app_module,
        "urlopen",
        lambda request, timeout=0: DummyResponse(
            {"data": [
                {"id": "deepseek-v4-pro"},
                {"id": "deepseek-v4-flash"},
                {"id": "deepseek-chat"},
                {"id": "deepseek-reasoner"},
            ]}
        ),
    )

    def fake_subprocess_run(cmd, **kwargs):
        if cmd[:3] == ["codex", "exec", "--help"]:
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["codex", "debug", "models"]:
            return types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "models": [
                            {"slug": "gpt-5.5", "display_name": "GPT-5.5", "description": "Fast", "priority": 0, "visibility": "list"},
                            {"slug": "hidden-model", "display_name": "Hidden", "description": "Ignore", "priority": 99, "visibility": "hidden"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected subprocess cmd: {cmd}")

    monkeypatch.setattr(app_module.subprocess, "run", fake_subprocess_run)
    app_module.ensure_db()
    client = app_module.app.test_client()

    initial = client.get("/api/settings")
    assert initial.status_code == 200
    data = initial.get_json()
    assert data["ok"] is True
    assert data["api_status"]["deepseek"]["configured"] is True
    assert data["api_status"]["deepseek"]["models_endpoint_reachable"] is True
    assert data["api_status"]["codex"]["cli_available"] is True
    assert data["api_status"]["codex"]["exec_available"] is True
    assert data["api_status"]["codex"]["models_readable"] is True
    assert data["model_catalogs"]["translation"]["source"] == "official"
    assert data["model_catalogs"]["translation"]["resolved_default_model"] == "deepseek-v4-flash"
    assert data["model_catalogs"]["translation"]["default_label"] == "deepseek-v4-flash"
    assert data["model_catalogs"]["translation"]["options"][0]["value"] == "deepseek-v4-flash"
    option_values = {opt["value"] for opt in data["model_catalogs"]["translation"]["options"]}
    assert "deepseek-chat" not in option_values
    assert "deepseek-reasoner" not in option_values
    assert "deepseek-v4-flash" in option_values
    assert "deepseek-v4-pro" in option_values
    assert data["model_catalogs"]["codex_chat"]["source"] == "codex_debug"
    assert data["tracked"]["default_rule_params"]["threshold"] == 6
    assert data["tracked"]["default_rule_params"]["title_weight"] == 1
    assert data["model_catalogs"]["codex_chat"]["options"][0] == {
        "value": "gpt-5.5",
        "label": "gpt-5.5",
        "description": "",
        "source": "codex_debug",
    }
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
    assert saved["llm"]["translation"]["model"] == "deepseek-v4-pro"
    assert saved["llm"]["codex_chat"]["model"] == "gpt-5-codex"
    assert any(option["value"] == "gpt-5-codex" for option in saved["model_catalogs"]["codex_chat"]["options"])
    assert settings_path.exists() is True
    saved_file = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved_file["llm"]["translation"]["model"] == "deepseek-v4-pro"
    assert saved_file["llm"]["codex_chat"]["model"] == "gpt-5-codex"


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


def test_codex_model_catalog_parse_success_and_fallback(tmp_path: Path, monkeypatch):
    daily_dir = tmp_path / "DailyNews" / "2026年6月"
    daily_dir.mkdir(parents=True)
    db_path = tmp_path / "news_index.sqlite3"
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setenv("NEWS_READER_DAILY_NEWS_DIR", str(tmp_path / "DailyNews"))
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(db_path))
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))

    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.shutil, "which", lambda name: "/usr/bin/codex" if name == "codex" else None)

    def success_run(cmd, **kwargs):
        if cmd[:3] == ["codex", "exec", "--help"]:
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["codex", "debug", "models"]:
            return types.SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "models": [
                            {"slug": "gpt-5", "display_name": "GPT-5", "description": "General", "priority": 2, "visibility": "list"},
                            {"slug": "gpt-5.5", "display_name": "GPT-5.5", "description": "Best", "priority": 0, "visibility": "list"},
                            {"slug": "internal", "display_name": "Internal", "description": "Hidden", "priority": 1, "visibility": "hidden"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )
        raise AssertionError(f"unexpected subprocess cmd: {cmd}")

    monkeypatch.setattr(app_module.subprocess, "run", success_run)
    success_snapshot = app_module.codex_settings_snapshot("gpt-5.5")
    assert success_snapshot["service"]["cli_available"] is True
    assert success_snapshot["service"]["exec_available"] is True
    assert success_snapshot["service"]["models_readable"] is True
    assert success_snapshot["service"]["used_fallback"] is False
    assert success_snapshot["catalog"]["source"] == "codex_debug"
    assert [option["value"] for option in success_snapshot["catalog"]["options"]] == ["gpt-5.5", "gpt-5"]
    assert [option["label"] for option in success_snapshot["catalog"]["options"]] == ["gpt-5.5", "gpt-5"]

    def fallback_run(cmd, **kwargs):
        if cmd[:3] == ["codex", "exec", "--help"]:
            return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")
        if cmd[:3] == ["codex", "debug", "models"]:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="catalog failed")
        raise AssertionError(f"unexpected subprocess cmd: {cmd}")

    monkeypatch.setattr(app_module.subprocess, "run", fallback_run)
    fallback_snapshot = app_module.codex_settings_snapshot("gpt-5-custom-x")
    assert fallback_snapshot["service"]["cli_available"] is True
    assert fallback_snapshot["service"]["exec_available"] is True
    assert fallback_snapshot["service"]["models_readable"] is False
    assert fallback_snapshot["service"]["used_fallback"] is True
    assert fallback_snapshot["service"]["last_error"] == "catalog failed"
    assert fallback_snapshot["catalog"]["source"] == "fallback"
    assert fallback_snapshot["catalog"]["options"][0]["value"] == "gpt-5.5"
    assert fallback_snapshot["catalog"]["options"][-1]["value"] == "gpt-5-custom-x"


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


def test_settings_api_sanitizes_legacy_chat_fields(tmp_path: Path, monkeypatch):
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
    assert payload["llm"]["chat"] == {"provider": "codex"}
    assert payload["llm"]["pi_chat"]["provider"] == "ollama"
    assert payload["llm"]["pi_chat"]["model"] == "minimax-m3:cloud"



def test_current_chat_provider_and_pi_config(tmp_path: Path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    settings_path.write_text(
        json.dumps(
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "qwen3.5:0.8b"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    import app as app_module

    importlib.reload(app_module)
    assert app_module.current_chat_provider() == "pi"
    assert app_module.current_pi_chat_config() == {"provider": "ollama", "model": "qwen3.5:0.8b"}


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
    assert any(opt["value"] == "minimax-m3:cloud" for opt in catalog["options"])


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
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
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
            {"llm": {"chat": {"provider": "pi"}, "pi_chat": {"provider": "ollama", "model": "minimax-m3:cloud"}}},
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
