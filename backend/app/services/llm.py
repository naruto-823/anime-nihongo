import json
import re
from functools import lru_cache

from anthropic import Anthropic

from app.config import settings

_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class LLMError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client() -> Anthropic:
    return Anthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url or None,
        max_retries=5,  # 扛 fox 网关突发限流
    )


def extract_json(text: str) -> dict:
    """从模型输出里抽出 JSON 对象：优先代码围栏，其次首个 {...}。"""
    candidates = []
    fence = _FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))
    obj = _OBJ_RE.search(text)
    if obj:
        candidates.append(obj.group(0))
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise LLMError(f"无法从模型输出解析 JSON: {text[:200]}")


def call_json(system: str, user: str, model: str | None = None,
              max_tokens: int = 8000) -> dict:
    """调用 Claude，要求返回 JSON 对象并解析。失败抛 LLMError。"""
    try:
        resp = _client().messages.create(
            model=model or settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"LLM 调用失败: {exc}") from exc
    text = "".join(getattr(b, "text", "") for b in resp.content)
    result = extract_json(text)
    if not isinstance(result, dict):
        raise LLMError(f"模型返回的不是 JSON 对象，而是 {type(result).__name__}")
    return result
