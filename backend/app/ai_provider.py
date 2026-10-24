"""One interface to the AI provider through an OpenAI-compatible chat API.

generate(messages, tools=None, schema=None, deadline=None) -> ProviderReply

* Timeouts and provider errors become AIError with kind timeout, quota, invalid_output or
  unavailable. No stack trace, key or URL ever reaches the message.
* FORCE_AI_FAILURE=1 makes every call fail with the quota error before any network call (test case 5).
* Function calling and a response schema are never mixed in one request. The agent runs the tool
  phase first (tools, no schema) and then one grading call (schema, no tools).
* max_retries=0 on the client: the only retry in a run is the agent's single grading retry.
  The one thing done here is a fallback when a provider rejects JSON mode (see below).

Owner: P3
Plan: section 4
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .errors import AIError

log = logging.getLogger("qeleme")

# Some providers reject response_format=json_object. Remember that for the life of the process.
_json_mode_ok = True


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ProviderReply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_message: dict = field(default_factory=dict)  # append to messages before tool results


# ---------------------------------------------------------------- errors


def _status_of(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


def map_error(exc: Exception) -> AIError:
    """Turn any provider or network exception into one of our error kinds."""
    import openai
    status = _status_of(exc)
    if isinstance(exc, (openai.APITimeoutError, TimeoutError)) or status in (408, 504):
        kind = "timeout"
    elif isinstance(exc, openai.RateLimitError) or status in (402, 429, 500, 502, 503):
        kind = "quota"
    elif isinstance(exc, openai.APIConnectionError):
        kind = "unavailable"
    elif status in (401, 403, 404):
        kind = "unavailable"
    elif status in (400, 422):
        kind = "invalid_output"
    else:
        kind = "unavailable"
    log.warning("AI provider error: %s (status %s) -> %s", type(exc).__name__, status, kind)  # never the message
    return AIError(kind)


# ---------------------------------------------------------------- the call


def _client(timeout: float):
    from openai import OpenAI
    return OpenAI(base_url=config.ai_base_url(), api_key=config.ai_api_key(), timeout=timeout, max_retries=0)


def generate(messages: list[dict], tools: list[dict] | None = None, schema: Any = None,
             deadline: float | None = None) -> ProviderReply:
    """One model call. `deadline` is a time.monotonic() value for the whole run.

    schema: pass any truthy value to ask for JSON output (JSON mode). Pass tools OR schema, not both."""
    global _json_mode_ok
    if config.force_ai_failure():
        raise AIError("quota")
    if not config.ai_configured():
        raise AIError("unavailable")

    timeout = 45.0
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining < 2:
            raise AIError("timeout")
        timeout = min(timeout, remaining)

    kwargs: dict[str, Any] = {"model": config.ai_model(), "messages": messages, "temperature": 0}
    if tools:
        kwargs["tools"] = tools
    use_json_mode = bool(schema) and not tools and _json_mode_ok
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    import openai
    client = _client(timeout)
    try:
        try:
            response = client.chat.completions.create(**kwargs)
        except openai.BadRequestError:
            if not use_json_mode:
                raise
            _json_mode_ok = False                      # provider has no JSON mode: ask in the prompt only
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
    except AIError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise map_error(exc) from None
    return _parse_response(response)


def _parse_response(response: Any) -> ProviderReply:
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        raise AIError("invalid_output") from None
    calls: list[ToolCall] = []
    raw_calls: list[dict] = []
    for tc in (getattr(message, "tool_calls", None) or []):
        raw_args = getattr(tc.function, "arguments", None) or "{}"
        try:
            args = json.loads(raw_args)
        except (TypeError, ValueError):
            args = {}
        if not isinstance(args, dict):
            args = {}
        calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        raw_calls.append({"id": tc.id, "type": "function",
                          "function": {"name": tc.function.name, "arguments": raw_args if isinstance(raw_args, str) else "{}"}})
    text = getattr(message, "content", None)
    assistant: dict = {"role": "assistant", "content": text or ""}
    if raw_calls:
        assistant["tool_calls"] = raw_calls
    return ProviderReply(text=text, tool_calls=calls, assistant_message=assistant)


# ---------------------------------------------------------------- reading the model's text

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.M)


def extract_json(text: str | None) -> dict | None:
    """Best effort: the JSON object in the model's text, or None. Never raises."""
    if not isinstance(text, str):
        return None
    cleaned = _FENCE.sub("", _THINK.sub("", text)).strip()
    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        candidates.append(cleaned[start:end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return None
