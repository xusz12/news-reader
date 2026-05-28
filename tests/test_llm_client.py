from __future__ import annotations

import importlib
import json
import sys
import types

import pytest


def _install_fake_openai(monkeypatch, create_impl):
    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=create_impl)
            )

    fake_module = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_module)


def test_generate_article_ai_success(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

    arguments = json.dumps(
        {
            "key_points_zh": ["要点一", "要点二", "要点三"],
            "conclusion_zh": "一句话结论",
            "body_zh": "中" * 260,
        },
        ensure_ascii=False,
    )

    def create_impl(**kwargs):
        tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(arguments=arguments)
        )
        msg = types.SimpleNamespace(tool_calls=[tool_call])
        choice = types.SimpleNamespace(message=msg)
        return types.SimpleNamespace(model="deepseek-chat", choices=[choice])

    _install_fake_openai(monkeypatch, create_impl)
    import llm_client

    importlib.reload(llm_client)
    out = llm_client.generate_article_ai(
        title="Test Title",
        source="Reuters",
        content="English body " * 50,
    )
    assert out["model"] == "deepseek-chat"
    assert out["conclusion_zh"] == "一句话结论"
    assert out["key_points_zh"] == ["要点一", "要点二", "要点三"]
    assert len(out["body_zh"]) >= 200


def test_generate_article_ai_invalid_tool_payload(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

    def create_impl(**kwargs):
        tool_call = types.SimpleNamespace(
            function=types.SimpleNamespace(arguments='{"oops": 1}')
        )
        msg = types.SimpleNamespace(tool_calls=[tool_call])
        choice = types.SimpleNamespace(message=msg)
        return types.SimpleNamespace(model="deepseek-chat", choices=[choice])

    _install_fake_openai(monkeypatch, create_impl)
    import llm_client

    importlib.reload(llm_client)
    with pytest.raises(llm_client.LLMClientError) as exc:
        llm_client.generate_article_ai(
            title="Test Title",
            source="Reuters",
            content="English body " * 50,
        )
    assert "INVALID_KEY_POINTS" in str(exc.value)
