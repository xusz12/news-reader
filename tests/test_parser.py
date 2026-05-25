from __future__ import annotations

from pathlib import Path

from parser import parse_daily_file


def write_daily(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_parse_extracts_url_and_fields(tmp_path: Path):
    p = tmp_path / "dailyFreshNews_2026-05-25.md"
    write_daily(
        p,
        """## Reuters · World（1条）

### [测试新闻](https://example.com/a)
- 发布时间：2026-05-25 11:22:33
- 摘要：这是一条摘要
""",
    )
    items = parse_daily_file(p)
    assert len(items) == 1
    it = items[0]
    assert it.title == "测试新闻"
    assert it.url == "https://example.com/a"
    assert it.time == "11:22"
    assert it.published_at == "2026-05-25 11:22"
    assert it.summary == "这是一条摘要"


def test_parse_ignores_errors_and_empty_sections(tmp_path: Path):
    p = tmp_path / "dailyFreshNews_2026-05-25.md"
    write_daily(
        p,
        """## Reuters · World（1条）
### [保留新闻](https://example.com/ok)
- 发布时间：2026-05-25 09:00:00

## 本次无更新的分组（1个）
### [不应保留](https://example.com/skip)
- 发布时间：2026-05-25 09:01:00

## errors
### [也不应保留](https://example.com/err)
- 发布时间：2026-05-25 09:02:00
""",
    )
    items = parse_daily_file(p)
    assert len(items) == 1
    assert items[0].title == "保留新闻"
