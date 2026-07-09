from __future__ import annotations

import os
import json
from pathlib import Path


DEFAULT_DAILY_NEWS_DIR = Path(
    "/Users/x/Library/Mobile Documents/iCloud~md~obsidian/Documents/DailyNews"
)
DEFAULT_DAILY_BRIEFING_DIR = DEFAULT_DAILY_NEWS_DIR / "briefings" / "daily"
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "news_index.sqlite3"
DEFAULT_APP_SETTINGS_PATH = Path(__file__).resolve().parent / "app_settings.json"

DEFAULT_CHAT_PROVIDER = "codex"
DEFAULT_PI_CHAT_PROVIDER = "ollama"
DEFAULT_PI_CHAT_MODEL = "minimax-m3:cloud"

DEFAULT_APP_SETTINGS = {
    "llm": {
        "translation": {
            "provider": "deepseek",
            "model": "",
        },
        "chat": {
            "provider": DEFAULT_CHAT_PROVIDER,
        },
        "codex_chat": {
            "model": "",
        },
        "pi_chat": {
            "provider": DEFAULT_PI_CHAT_PROVIDER,
            "model": DEFAULT_PI_CHAT_MODEL,
        },
    },
    "tracked": {
        "default_rule_params": {
            "title_weight": 1,
            "note_weight": 1,
            "summary_weight": 1,
            "content_weight": 1,
            "strong_score": 1,
            "core_score": 1,
            "context_score": 1,
            "exclude_penalty": 1,
            "threshold": 6,
        },
    },
}


def resolve_daily_news_dir() -> Path:
    raw = os.environ.get("NEWS_READER_DAILY_NEWS_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_DAILY_NEWS_DIR


def resolve_daily_briefing_dir() -> Path:
    raw = os.environ.get("NEWS_READER_DAILY_BRIEFING_DIR", "").strip()
    return Path(raw) if raw else DEFAULT_DAILY_BRIEFING_DIR


def resolve_db_path() -> Path:
    raw = os.environ.get("NEWS_READER_DB_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_DB_PATH


def resolve_app_settings_path() -> Path:
    raw = os.environ.get("NEWS_READER_APP_SETTINGS_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_APP_SETTINGS_PATH


def default_app_settings() -> dict:
    return json.loads(json.dumps(DEFAULT_APP_SETTINGS))


def load_app_settings() -> dict:
    path = resolve_app_settings_path()
    base = default_app_settings()
    if not path.exists():
        return base
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return base

    llm = payload.get("llm") if isinstance(payload, dict) else None
    if not isinstance(llm, dict):
        return base

    translation = llm.get("translation")
    if isinstance(translation, dict):
        provider = translation.get("provider")
        model = translation.get("model")
        if isinstance(provider, str) and provider.strip():
            base["llm"]["translation"]["provider"] = provider.strip()
        if isinstance(model, str):
            base["llm"]["translation"]["model"] = model.strip()

    chat = llm.get("chat")
    if isinstance(chat, dict):
        provider = (chat.get("provider") or "").strip().lower()
        if provider in {"codex", "pi"}:
            base["llm"]["chat"]["provider"] = provider

    codex_chat = llm.get("codex_chat")
    if isinstance(codex_chat, dict):
        model = codex_chat.get("model")
        if isinstance(model, str):
            base["llm"]["codex_chat"]["model"] = model.strip()

    pi_chat = llm.get("pi_chat")
    if isinstance(pi_chat, dict):
        provider = (pi_chat.get("provider") or "").strip()
        model = pi_chat.get("model")
        if isinstance(provider, str):
            base["llm"]["pi_chat"]["provider"] = provider
        if isinstance(model, str):
            base["llm"]["pi_chat"]["model"] = model.strip()

    tracked = payload.get("tracked") if isinstance(payload, dict) else None
    if isinstance(tracked, dict):
        default_rule_params = tracked.get("default_rule_params")
        if isinstance(default_rule_params, dict):
            for key in base["tracked"]["default_rule_params"].keys():
                value = default_rule_params.get(key)
                if isinstance(value, (int, float)):
                    base["tracked"]["default_rule_params"][key] = value

    return base


def save_app_settings(payload: dict) -> Path:
    path = resolve_app_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
