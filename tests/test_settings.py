from __future__ import annotations

from pathlib import Path

import settings


def test_resolve_db_path_prefers_existing_legacy_database(monkeypatch, tmp_path: Path):
    project_db = tmp_path / "project" / "news_index.sqlite3"
    legacy_db = tmp_path / "news_index.sqlite3"
    project_db.parent.mkdir()
    legacy_db.touch()
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", project_db)
    monkeypatch.setattr(settings, "LEGACY_DB_PATH", legacy_db)
    monkeypatch.delenv("NEWS_READER_DB_PATH", raising=False)

    assert settings.resolve_db_path() == legacy_db


def test_resolve_db_path_falls_back_to_project_database(monkeypatch, tmp_path: Path):
    project_db = tmp_path / "project" / "news_index.sqlite3"
    legacy_db = tmp_path / "news_index.sqlite3"
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", project_db)
    monkeypatch.setattr(settings, "LEGACY_DB_PATH", legacy_db)
    monkeypatch.delenv("NEWS_READER_DB_PATH", raising=False)

    assert settings.resolve_db_path() == project_db


def test_resolve_db_path_prefers_explicit_override(monkeypatch, tmp_path: Path):
    project_db = tmp_path / "project" / "news_index.sqlite3"
    legacy_db = tmp_path / "news_index.sqlite3"
    explicit_db = tmp_path / "custom" / "news.sqlite3"
    legacy_db.touch()
    monkeypatch.setattr(settings, "PROJECT_DB_PATH", project_db)
    monkeypatch.setattr(settings, "LEGACY_DB_PATH", legacy_db)
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(explicit_db))

    assert settings.resolve_db_path() == explicit_db
