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


def _validate_structured_translation_payload(parsed: object) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise LLMClientError("INVALID_TOOL_ARGUMENTS_JSON: payload_not_object")

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
        "key_points_zh": [x.strip() for x in key_points],
        "conclusion_zh": conclusion.strip(),
        "body_zh": body_text,
    }


def _validate_recommendation_categories_payload(parsed: object, *, allowed_item_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(parsed, dict):
        raise LLMClientError("INVALID_RECOMMENDATION_CATEGORIES_PAYLOAD")

    raw_categories = parsed.get("categories")
    if not isinstance(raw_categories, list) or not raw_categories:
        raise LLMClientError("INVALID_RECOMMENDATION_CATEGORIES")

    normalized: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for raw in raw_categories[:30]:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip().lower().replace(" ", "_")
        label = str(raw.get("label") or "").strip()
        description = str(raw.get("description") or "").strip()
        raw_seed_ids = raw.get("seed_item_ids")
        if not (key and label and description):
            continue
        if key in seen_keys:
            continue
        if not isinstance(raw_seed_ids, list):
            continue
        seed_item_ids = []
        for item_id in raw_seed_ids:
            text = str(item_id or "").strip()
            if text and text in allowed_item_ids and text not in seed_item_ids:
                seed_item_ids.append(text)
        if not seed_item_ids:
            continue
        seen_keys.add(key)
        normalized.append(
            {
                "key": key[:64],
                "label": label[:80],
                "description": description[:200],
                "seed_item_ids": seed_item_ids,
            }
        )

    if not normalized:
        raise LLMClientError("EMPTY_RECOMMENDATION_CATEGORIES")
    return normalized


def _validate_recommendation_classification_payload(
    parsed: object,
    *,
    allowed_category_keys: set[str],
) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise LLMClientError("INVALID_RECOMMENDATION_PAYLOAD")

    normalized: dict[str, Any] = {}
    raw_matches = parsed.get("category_matches")
    if not isinstance(raw_matches, list):
        raise LLMClientError("INVALID_CATEGORY_MATCHES")
    matches = []
    seen_keys: set[str] = set()
    for raw in raw_matches[:8]:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "").strip()
        confidence = str(raw.get("confidence") or "").strip().lower()
        if key not in allowed_category_keys or confidence not in {"high", "medium", "low"}:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        matches.append({"key": key, "confidence": confidence})
    normalized["category_matches"] = matches

    event_type = str(parsed.get("event_type") or "").strip().lower()
    if event_type not in {"regulation", "product", "funding", "earnings", "geopolitics", "policy", "market", "other"}:
        raise LLMClientError("INVALID_EVENT_TYPE")
    normalized["event_type"] = event_type

    for field, max_items in (("entities", 6), ("sectors", 5), ("regions", 5)):
        raw = parsed.get(field)
        if not isinstance(raw, list):
            raise LLMClientError(f"INVALID_{field.upper()}")
        cleaned = []
        for item in raw:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    cleaned.append(text)
        if len(cleaned) > max_items:
            cleaned = cleaned[:max_items]
        normalized[field] = cleaned

    raw_candidates = parsed.get("new_category_candidates")
    if not isinstance(raw_candidates, list):
        raise LLMClientError("INVALID_NEW_CATEGORY_CANDIDATES")
    candidates = []
    for raw in raw_candidates[:5]:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()
        description = str(raw.get("description") or "").strip()
        confidence = str(raw.get("confidence") or "").strip().lower()
        if not (label and description and confidence in {"high", "medium", "low"}):
            continue
        candidates.append(
            {
                "label": label[:80],
                "description": description[:200],
                "confidence": confidence,
            }
        )
    normalized["new_category_candidates"] = candidates

    headline = parsed.get("headline_signal")
    if not isinstance(headline, str) or not headline.strip():
        raise LLMClientError("INVALID_HEADLINE_SIGNAL")
    normalized["headline_signal"] = headline.strip()[:120]
    return normalized


def _contains_cjk(text: str) -> bool:
    for char in text:
        code = ord(char)
        if 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF:
            return True
    return False


def _configured_model() -> str:
    value = (os.getenv("NEWS_READER_LLM_MODEL") or "").strip()
    return value or "deepseek-chat"


def resolve_translation_default_model() -> str:
    return _configured_model()


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


def _build_recommendation_category_messages(
    *,
    positive_samples: list[dict[str, str]],
    trend_contexts: list[dict[str, str]],
) -> list[dict[str, str]]:
    system = (
        "你是用户新闻兴趣类别库生成器。"
        "你必须调用给定函数并严格输出结构化类别定义，不要输出解释。"
        "字段要求：\n"
        "1) categories: 8-30 个类别；样本较少时可少于 8 个，但不要制造空泛类别。\n"
        "2) 每个类别必须有稳定 key（英文下划线风格）、中文 label、中文 description。\n"
        "3) 每个类别必须给出 1 个以上 seed_item_ids，且只能使用给定样本里的 item_id。\n"
        "4) 类别要尽量具体，贴近用户长期偏好，不要输出'综合新闻'、'普通市场动态'之类空泛类别。"
    )
    sample_blocks = []
    for sample in positive_samples:
        sample_blocks.append(
            "\n".join(
                [
                    f"item_id: {sample['item_id']}",
                    f"来源: {sample['source'] or '未知'}",
                    f"标题: {sample['title'] or '无标题'}",
                    f"摘要: {sample['summary'] or '无'}",
                    f"想法: {sample['note'] or '无'}",
                    f"板块: {sample['tags'] or '无'}",
                ]
            )
        )
    user = (
        "以下是用户历史正样本，请总结为稳定的兴趣类别库，并为每个类别附上对应 seed_item_ids：\n\n"
        + "\n\n---\n\n".join(sample_blocks)
    )
    if trend_contexts:
        trend_blocks = []
        for ctx in trend_contexts:
            trend_blocks.append(
                "\n".join(
                    [
                        f"日期: {ctx['date_key'] or '未知'}",
                        f"板块: {ctx['tag'] or '未知'}",
                        f"方向: {ctx['direction'] or '未知'}",
                        f"趋势想法: {ctx['note'] or '无'}",
                    ]
                )
            )
        user += (
            "\n\n补充弱正样本上下文（趋势想法/手动趋势信号，只用于帮助理解长期偏好，不要把它们当成 seed_item_ids）：\n\n"
            + "\n\n---\n\n".join(trend_blocks)
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_recommendation_classification_messages(
    *,
    title: str,
    source: str,
    published_at: str,
    summary: str,
    detail_excerpt: str,
    categories: list[dict[str, str]],
) -> list[dict[str, str]]:
    system = (
        "你是新闻语义归类器。"
        "你必须调用给定函数并严格输出结构化字段，不要输出解释。"
        "你的职责只有语义归类，不要判断是否推荐、不要给推荐分数、不要评价值不值得读。"
        "优先从给定 active 类别库中匹配 category key；匹配不到时可以补充 new_category_candidates，但不能虚构已有 key。"
    )
    category_lines = [
        f"- {category['key']} | {category['label']} | {category['description']}"
        for category in categories
    ]
    user = (
        "当前 active 类别库：\n"
        + "\n".join(category_lines)
        + "\n\n"
        + f"发布时间: {published_at or '未知'}\n"
        + f"来源: {source or '未知'}\n"
        + f"标题: {title or '无标题'}\n"
        + f"摘要: {summary or '无'}\n"
        + f"正文片段: {detail_excerpt or '无'}"
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

    normalized = _validate_structured_translation_payload(parsed)

    return {
        "model": getattr(resp, "model", None) or model_name,
        **normalized,
        "raw_json": json.dumps(parsed, ensure_ascii=False),
    }


def generate_recommendation_categories(
    *,
    positive_samples: list[dict[str, str]],
    trend_contexts: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    api_key = _resolve_api_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMClientError("MISSING_DEEPSEEK_API_KEY")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env-specific
        raise LLMClientError(f"OPENAI_SDK_IMPORT_FAILED: {exc}") from exc

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/beta")
    model_name = (model or "").strip() or _configured_model()
    allowed_item_ids = {str(sample.get("item_id") or "").strip() for sample in positive_samples}
    allowed_item_ids.discard("")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "save_recommendation_categories",
                "description": "保存推荐类别库",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "categories": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "label": {"type": "string"},
                                    "description": {"type": "string"},
                                    "seed_item_ids": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "minItems": 1,
                                    },
                                },
                                "required": ["key", "label", "description", "seed_item_ids"],
                                "additionalProperties": False,
                            },
                            "minItems": 1,
                            "maxItems": 30,
                        },
                    },
                    "required": ["categories"],
                    "additionalProperties": False,
                },
            },
        }
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=_build_recommendation_category_messages(
                positive_samples=positive_samples,
                trend_contexts=trend_contexts or [],
            ),
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "save_recommendation_categories"}},
            temperature=0.1,
            timeout=90,
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

    normalized = _validate_recommendation_categories_payload(parsed, allowed_item_ids=allowed_item_ids)
    return {
        "model": getattr(resp, "model", None) or model_name,
        "categories": normalized,
        "raw_json": json.dumps(parsed, ensure_ascii=False),
    }


def generate_recommendation_classification(
    *,
    title: str,
    source: str,
    published_at: str,
    summary: str,
    detail_excerpt: str = "",
    categories: list[dict[str, str]],
    model: str | None = None,
) -> dict[str, Any]:
    api_key = _resolve_api_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMClientError("MISSING_DEEPSEEK_API_KEY")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env-specific
        raise LLMClientError(f"OPENAI_SDK_IMPORT_FAILED: {exc}") from exc

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/beta")
    model_name = (model or "").strip() or _configured_model()
    allowed_category_keys = {str(category.get("key") or "").strip() for category in categories}
    allowed_category_keys.discard("")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "save_recommendation_classification",
                "description": "保存新闻语义归类结果",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category_matches": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                },
                                "required": ["key", "confidence"],
                                "additionalProperties": False,
                            },
                            "maxItems": 8,
                        },
                        "entities": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
                        "event_type": {
                            "type": "string",
                            "enum": ["regulation", "product", "funding", "earnings", "geopolitics", "policy", "market", "other"],
                        },
                        "sectors": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                        "regions": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                        "new_category_candidates": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string"},
                                    "description": {"type": "string"},
                                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                },
                                "required": ["label", "description", "confidence"],
                                "additionalProperties": False,
                            },
                            "maxItems": 5,
                        },
                        "headline_signal": {"type": "string"},
                    },
                    "required": [
                        "category_matches",
                        "entities",
                        "event_type",
                        "sectors",
                        "regions",
                        "new_category_candidates",
                        "headline_signal",
                    ],
                    "additionalProperties": False,
                },
            },
        }
    ]

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=_build_recommendation_classification_messages(
                title=title,
                source=source,
                published_at=published_at,
                summary=summary,
                detail_excerpt=detail_excerpt,
                categories=categories,
            ),
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "save_recommendation_classification"}},
            temperature=0.1,
            timeout=90,
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

    normalized = _validate_recommendation_classification_payload(
        parsed,
        allowed_category_keys=allowed_category_keys,
    )
    return {
        "model": getattr(resp, "model", None) or model_name,
        **normalized,
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
        "你是专业新闻编辑与翻译。请基于英文新闻正文返回一个 JSON 对象，不要输出 JSON 以外的任何内容。\n"
        "JSON 字段要求：\n"
        '- "key_points_zh": 3 到 5 条中文要点数组，每条一句话\n'
        '- "conclusion_zh": 一句中文结论\n'
        '- "body_zh": 完整中文翻译，保持段落结构，不遗漏关键信息\n'
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
        raw_output = Path(output_path).read_text(encoding="utf-8").strip()
    except Exception:
        raw_output = ""
    finally:
        Path(output_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        detail = stderr or stdout or f"exit={proc.returncode}"
        raise LLMClientError(f"CODEX_FALLBACK_FAILED: {detail[:300]}")

    raw_payload = {
        "provider": "codex-fallback-structured",
        "truncated": truncated,
        "stdout": stdout[:4000],
        "stderr": stderr[:1000],
    }

    try:
        parsed = json.loads(raw_output)
        normalized = _validate_structured_translation_payload(parsed)
        return {
            "model": model_name or "codex-fallback",
            **normalized,
            "raw_json": json.dumps(
                {
                    **raw_payload,
                    "structured_success": True,
                    "parsed": parsed,
                },
                ensure_ascii=False,
            ),
        }
    except Exception as exc:
        body_zh = raw_output.strip()
        if not body_zh or not _contains_cjk(body_zh):
            detail = str(exc) if isinstance(exc, LLMClientError) else "CODEX_FALLBACK_INVALID_OUTPUT"
            raise LLMClientError(detail)
        return {
            "model": model_name or "codex-fallback",
            "key_points_zh": [],
            "conclusion_zh": "",
            "body_zh": body_zh,
            "raw_json": json.dumps(
                {
                    **raw_payload,
                    "provider": "codex-fallback-body-only",
                    "structured_success": False,
                    "structured_error": str(exc),
                },
                ensure_ascii=False,
            ),
        }
