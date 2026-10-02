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


def test_resolve_db_path_prefers_saved_configured_database(monkeypatch, tmp_path: Path):
    settings_path = tmp_path / "app_settings.json"
    configured_db = tmp_path / "configured.sqlite3"
    configured_db.touch()
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    monkeypatch.delenv("NEWS_READER_DB_PATH", raising=False)
    settings_path.write_text(
        '{"database": {"path": "' + str(configured_db) + '"}}',
        encoding="utf-8",
    )

    assert settings.resolve_db_path() == configured_db


def test_environment_database_path_still_overrides_saved_configured_database(monkeypatch, tmp_path: Path):
    settings_path = tmp_path / "app_settings.json"
    configured_db = tmp_path / "configured.sqlite3"
    environment_db = tmp_path / "environment.sqlite3"
    configured_db.touch()
    environment_db.touch()
    monkeypatch.setenv("NEWS_READER_APP_SETTINGS_PATH", str(settings_path))
    settings_path.write_text(
        '{"database": {"path": "' + str(configured_db) + '"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("NEWS_READER_DB_PATH", str(environment_db))

    assert settings.resolve_db_path() == environment_db
