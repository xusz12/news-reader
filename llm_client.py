from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any


class LLMClientError(RuntimeError):
    pass


_CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF]")
_GEMINI_CHOICE_RE = re.compile(
    r"Choice A(?P<a>.*?)Choice B(?P<b>.*?)(?:Gemini is AI|$)",
    re.DOTALL,
)


def _configured_model() -> str:
    value = (os.getenv("NEWS_READER_LLM_MODEL") or "").strip()
    return value or "deepseek-chat"


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


def generate_article_ai(*, title: str, source: str, content: str) -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMClientError("MISSING_DEEPSEEK_API_KEY")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env-specific
        raise LLMClientError(f"OPENAI_SDK_IMPORT_FAILED: {exc}") from exc

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/beta")
    model_name = _configured_model()
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
    if not body_text or not _CJK_RE.search(body_text):
        raise LLMClientError("INVALID_BODY_ZH")

    return {
        "model": getattr(resp, "model", None) or model_name,
        "key_points_zh": [x.strip() for x in key_points],
        "conclusion_zh": conclusion.strip(),
        "body_zh": body_text,
        "raw_json": json.dumps(parsed, ensure_ascii=False),
    }


def _strip_opencli_update_noise(text: str) -> str:
    head = text.split("\n\n  Update available:", 1)[0]
    return head.strip()


def _extract_gemini_translation(text: str) -> str:
    cleaned = _strip_opencli_update_noise(text).strip()
    if cleaned.startswith("💬"):
        cleaned = cleaned[1:].strip()

    match = _GEMINI_CHOICE_RE.search(cleaned)
    if match:
        choice_a = match.group("a").strip()
        choice_b = match.group("b").strip()
        if _CJK_RE.search(choice_a):
            return choice_a
        if _CJK_RE.search(choice_b):
            return choice_b

    return cleaned


def generate_gemini_fallback_translation(
    *,
    title: str,
    source: str,
    content: str,
    timeout: int = 90,
    max_chars: int = 12000,
) -> dict[str, Any]:
    body = (content or "").strip()
    if not body:
        raise LLMClientError("GEMINI_FALLBACK_EMPTY_CONTENT")

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

    cmd = [
        "opencli",
        "gemini",
        "ask",
        prompt,
        "--new",
        "true",
        "--timeout",
        str(timeout),
        "-f",
        "plain",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 15,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LLMClientError("GEMINI_FALLBACK_TIMEOUT") from exc
    except Exception as exc:
        raise LLMClientError(f"GEMINI_FALLBACK_FAILED: {exc}") from exc

    output = (proc.stdout or "").strip()
    error = (proc.stderr or "").strip()
    if proc.returncode != 0:
        detail = error or output or f"exit={proc.returncode}"
        raise LLMClientError(f"GEMINI_FALLBACK_FAILED: {detail[:300]}")

    body_zh = _extract_gemini_translation(output)
    if not body_zh or not _CJK_RE.search(body_zh):
        raise LLMClientError("GEMINI_FALLBACK_INVALID_OUTPUT")

    raw_payload = {
        "provider": "gemini-fallback",
        "truncated": truncated,
        "raw_output": output[:4000],
    }
    return {
        "model": "gemini-fallback",
        "key_points_zh": [],
        "conclusion_zh": "",
        "body_zh": body_zh.strip(),
        "raw_json": json.dumps(raw_payload, ensure_ascii=False),
    }
