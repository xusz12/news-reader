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


def _configured_openai_chat_model() -> str:
    value = (os.getenv("OPENAI_CHAT_MODEL") or os.getenv("OPENAI_MODEL") or "").strip()
    return value or "gpt-4.1-mini"


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
    api_key = os.getenv("DEEPSEEK_API_KEY")
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
    if not body_text or not _CJK_RE.search(body_text):
        raise LLMClientError("INVALID_BODY_ZH")

    return {
        "model": getattr(resp, "model", None) or model_name,
        "key_points_zh": [x.strip() for x in key_points],
        "conclusion_zh": conclusion.strip(),
        "body_zh": body_text,
        "raw_json": json.dumps(parsed, ensure_ascii=False),
    }


def build_news_chat_transcript(
    *,
    title: str,
    source: str,
    published_at: str,
    content: str,
    messages: list[dict[str, str]],
) -> str:
    body = (content or "").strip()
    if len(body) > 12000:
        body = body[:12000]
    transcript_lines = []
    for msg in messages:
        role = (msg.get("role") or "").strip().lower()
        text = (msg.get("content") or "").strip()
        if role not in {"user", "assistant"} or not text:
            continue
        speaker = "用户" if role == "user" else "助手"
        transcript_lines.append(f"{speaker}：{text}")
    transcript = "\n".join(transcript_lines)
    return (
        "下面是一篇新闻正文，请把它作为背景材料和引用锚点，帮助理解用户问题。\n\n"
        f"标题：{title or '无标题'}\n"
        f"来源：{source or '未知来源'}\n"
        f"时间：{published_at or '未知时间'}\n"
        "正文：\n"
        "<<<NEWS>>>\n"
        f"{body}\n"
        "<<<END>>>\n\n"
        "以下是当前对话记录：\n"
        f"{transcript or '（暂无）'}"
    )


def _news_chat_system_prompt(*, allow_web_search: bool) -> str:
    capability_line = (
        "你可以结合公开知识、背景信息以及你可获得的联网搜索结果来回答。"
        if allow_web_search
        else "你可以结合公开知识和背景信息来回答，但不要假装自己进行了实时联网搜索。"
    )
    return (
        "你是新闻阅读助手。\n"
        f"{capability_line}\n"
        "回答要求：\n"
        "1. 只用中文回答；\n"
        "2. 新闻正文是背景材料和引用锚点，不是回答边界；\n"
        "3. 必须尽量区分：正文事实、正文之外的补充信息、你自己的推断；\n"
        "4. 如果用户问的是最新进展，但你无法确认，请明确说无法确认；\n"
        "5. 回答尽量精炼，优先短要点，不要泛泛扩展。"
    )


def _extract_chat_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def ask_deepseek_news_chat(
    *,
    title: str,
    source: str,
    published_at: str,
    content: str,
    messages: list[dict[str, str]],
    model: str | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMClientError("MISSING_DEEPSEEK_API_KEY")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env-specific
        raise LLMClientError(f"OPENAI_SDK_IMPORT_FAILED: {exc}") from exc

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/beta")
    model_name = (model or "").strip() or _configured_model()
    payload_messages = [
        {"role": "system", "content": _news_chat_system_prompt(allow_web_search=False)},
        {
            "role": "user",
            "content": build_news_chat_transcript(
                title=title,
                source=source,
                published_at=published_at,
                content=content,
                messages=messages,
            ),
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=payload_messages,
            temperature=0.2,
            timeout=timeout,
        )
    except Exception as exc:
        raise LLMClientError(f"DEEPSEEK_CHAT_FAILED: {exc}") from exc

    choices = getattr(resp, "choices", None) or []
    if not choices:
        raise LLMClientError("DEEPSEEK_CHAT_EMPTY_CHOICES")
    message = choices[0].message
    text = _extract_chat_text(getattr(message, "content", ""))
    if not text or not _CJK_RE.search(text):
        raise LLMClientError("DEEPSEEK_CHAT_INVALID_OUTPUT")
    return {
        "provider": "deepseek",
        "model": getattr(resp, "model", None) or model_name,
        "answer": text,
    }


def ask_openai_news_chat(
    *,
    title: str,
    source: str,
    published_at: str,
    content: str,
    messages: list[dict[str, str]],
    model: str | None = None,
    timeout: int = 90,
) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMClientError("MISSING_OPENAI_API_KEY")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env-specific
        raise LLMClientError(f"OPENAI_SDK_IMPORT_FAILED: {exc}") from exc

    model_name = (model or "").strip() or _configured_openai_chat_model()
    client = OpenAI(api_key=api_key)
    transcript = build_news_chat_transcript(
        title=title,
        source=source,
        published_at=published_at,
        content=content,
        messages=messages,
    )

    try:
        resp = client.responses.create(
            model=model_name,
            instructions=_news_chat_system_prompt(allow_web_search=True),
            input=transcript,
            tools=[{"type": "web_search"}],
            temperature=0.2,
            timeout=timeout,
        )
    except Exception as exc:
        raise LLMClientError(f"OPENAI_CHAT_FAILED: {exc}") from exc

    text = (getattr(resp, "output_text", None) or "").strip()
    if not text or not _CJK_RE.search(text):
        raise LLMClientError("OPENAI_CHAT_INVALID_OUTPUT")
    return {
        "provider": "openai",
        "model": getattr(resp, "model", None) or model_name,
        "answer": text,
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
