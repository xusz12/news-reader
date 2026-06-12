from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from secret_store import SecretStoreError, read_secret


class LLMClientError(RuntimeError):
    pass


def _contains_cjk(text: str) -> bool:
    for char in text:
        code = ord(char)
        if 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF:
            return True
    return False


def _configured_model() -> str:
    value = (os.getenv("NEWS_READER_LLM_MODEL") or "").strip()
    return value or "deepseek-chat"


def _resolve_api_key(env_name: str) -> str:
    value = (os.getenv(env_name) or "").strip()
    if value:
        return value
    try:
        secret = read_secret(env_name)
    except SecretStoreError:
        return ""
    return (secret or "").strip()


def _build_messages(*, title: str, source: str, content: str) -> list[dict[str, str]]:
    system = (
        "你是专业新闻编辑与翻译。"
        "你必须调用给定函数并严格提供结构化参数。"
        "要求：\n"
        "1) key_points_zh: 3-5 条中文要点，每条一句话。\n"
        "2) conclusion_zh: 一句话中文结论。\n"
        "3) body_zh: 对全文做完整中文翻译，保持段落结构，不遗漏关键事实。"
    )
    user = (
        f"来源: {source or '未知'}\n"
        f"标题: {title or '无标题'}\n\n"
        "请基于以下英文正文生成结构化中文结果：\n\n"
        f"{content}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_article_ai(*, title: str, source: str, content: str, model: str | None = None) -> dict[str, Any]:
    api_key = _resolve_api_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMClientError("MISSING_DEEPSEEK_API_KEY")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env-specific
        raise LLMClientError(f"OPENAI_SDK_IMPORT_FAILED: {exc}") from exc

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/beta")
    model_name = (model or "").strip() or _configured_model()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "save_article_translation",
                "description": "保存文章翻译与摘要结果",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key_points_zh": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 3,
                            "maxItems": 5,
                        },
                        "conclusion_zh": {"type": "string"},
                        "body_zh": {"type": "string"},
                    },
                    "required": ["key_points_zh", "conclusion_zh", "body_zh"],
                    "additionalProperties": False,
                },
            },
        }
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=_build_messages(title=title, source=source, content=content),
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "save_article_translation"}},
            temperature=0.2,
            timeout=180,
        )
    except Exception as exc:
        raise LLMClientError(f"DEEPSEEK_CALL_FAILED: {exc}") from exc

    choices = getattr(resp, "choices", None) or []
    if not choices:
        raise LLMClientError("EMPTY_CHOICES")
    msg = choices[0].message
    tool_calls = getattr(msg, "tool_calls", None) or []
    if not tool_calls:
        raise LLMClientError("NO_TOOL_CALL")

    args_text = getattr(tool_calls[0].function, "arguments", "") or ""
    try:
        parsed = json.loads(args_text)
    except Exception as exc:
        raise LLMClientError(f"INVALID_TOOL_ARGUMENTS_JSON: {exc}") from exc

    key_points = parsed.get("key_points_zh")
    conclusion = parsed.get("conclusion_zh")
    body_zh = parsed.get("body_zh")
    if not isinstance(key_points, list) or not (3 <= len(key_points) <= 5):
        raise LLMClientError("INVALID_KEY_POINTS")
    if not all(isinstance(x, str) and x.strip() for x in key_points):
        raise LLMClientError("INVALID_KEY_POINT_ITEM")
    if not isinstance(conclusion, str) or not conclusion.strip():
        raise LLMClientError("INVALID_CONCLUSION")
    if not isinstance(body_zh, str):
        raise LLMClientError("INVALID_BODY_ZH")
    body_text = body_zh.strip()
    if not body_text or not _contains_cjk(body_text):
        raise LLMClientError("INVALID_BODY_ZH")

    return {
        "model": getattr(resp, "model", None) or model_name,
        "key_points_zh": [x.strip() for x in key_points],
        "conclusion_zh": conclusion.strip(),
        "body_zh": body_text,
        "raw_json": json.dumps(parsed, ensure_ascii=False),
    }


def generate_codex_fallback_translation(
    *,
    title: str,
    source: str,
    content: str,
    model: str | None = None,
    timeout: int = 90,
    max_chars: int = 12000,
) -> dict[str, Any]:
    body = (content or "").strip()
    if not body:
        raise LLMClientError("CODEX_FALLBACK_EMPTY_CONTENT")

    truncated = False
    if len(body) > max_chars:
        body = body[:max_chars]
        truncated = True

    prompt = (
        "把下面英文新闻正文完整翻译成中文，只输出译文，不要总结，不要解释，不要补充标题。\n"
        f"来源：{source or '未知'}\n"
        f"标题：{title or '无标题'}\n\n"
        f"{body}"
    )

    command = ["codex", "exec", prompt, "--skip-git-repo-check"]
    model_name = (model or "").strip()
    if model_name:
        command.extend(["--model", model_name])

    with tempfile.NamedTemporaryFile(prefix="news-reader-codex-fallback-", suffix=".txt", delete=False) as handle:
        output_path = handle.name
    command.extend(["--output-last-message", output_path])

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout + 15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMClientError("CODEX_FALLBACK_TIMEOUT") from exc
    except Exception as exc:
        raise LLMClientError(f"CODEX_FALLBACK_FAILED: {exc}") from exc

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    try:
        body_zh = Path(output_path).read_text(encoding="utf-8").strip()
    except Exception:
        body_zh = ""
    finally:
        Path(output_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        detail = stderr or stdout or f"exit={proc.returncode}"
        raise LLMClientError(f"CODEX_FALLBACK_FAILED: {detail[:300]}")
    if not body_zh or not _contains_cjk(body_zh):
        raise LLMClientError("CODEX_FALLBACK_INVALID_OUTPUT")

    raw_payload = {
        "provider": "codex-fallback",
        "truncated": truncated,
        "stdout": stdout[:4000],
        "stderr": stderr[:1000],
    }
    return {
        "model": model_name or "codex-fallback",
        "key_points_zh": [],
        "conclusion_zh": "",
        "body_zh": body_zh,
        "raw_json": json.dumps(raw_payload, ensure_ascii=False),
    }
