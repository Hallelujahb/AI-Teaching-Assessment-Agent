"""One interface to the AI provider through an OpenAI-compatible chat API.

generate(messages, tools=None, schema=None, deadline=None) -> ProviderReply

* Timeouts and provider errors become AIError with kind timeout, quota, invalid_output or
  unavailable. No stack trace, key or URL ever reaches the message.
* FORCE_AI_FAILURE=1 makes every call fail with the quota error before any network call (test case 5).
* Function calling and a response schema are never mixed in one request. The agent runs the tool
  phase first (tools, no schema) and then one grading call (schema, no tools).
* max_retries=0 on the client: the one retry in a run is the agent's single grading retry.
  The one thing done here is a fallback when a provider rejects JSON mode (see below).

Owner: P3
Plan: section 4
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .errors import AIError
from .stub_model import StubProviderError

log = logging.getLogger("qeleme")

_json_mode_ok = True  # Some providers reject response_format=json_object; remember that for the process.


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as the provider returns it


@dataclass
class ProviderReply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_message: dict = field(default_factory=dict)
    # Below fields are set by the real OpenRouter provider for token reporting.
    model: str | None = None
    usage: dict = field(default_factory=dict)


# Alias for tests that import ProviderResponse.
ProviderResponse = ProviderReply


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
    log.warning("AI provider error: %s (status %s) -> %s", type(exc).__name__, status, kind)
    return AIError(kind)


# ---------------------------------------------------------------- the call


def _client(timeout: float):
    from openai import OpenAI
    return OpenAI(base_url=config.ai_base_url(), api_key=config.ai_api_key(), timeout=timeout, max_retries=0)


def generate(messages: list[dict], tools: list[dict] | None = None, schema: Any = None,
             deadline: float | None = None) -> ProviderReply:
    """One model call. ``deadline`` is a time.monotonic() value for the whole run.

    ``schema``: pass any truthy value to request JSON output (JSON mode). Pass tools OR schema,
    never both. The agent runs the tool phase first (tools, no schema) and then one grading
    call (schema, no tools) when STRUCTURED_MODE allows it.
    """
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
            _json_mode_ok = False
            kwargs.pop("response_format", None)
            response = client.chat.completions.create(**kwargs)
    except AIError:
        raise
    except Exception as exc:
        raise map_error(exc) from None
    return _parse_response(response)


def _parse_response(response: Any, model: str | None = None) -> ProviderReply:
    """Parse a raw OpenAI/OpenRouter response object into a ProviderReply.

    ``model`` overrides the response.model if needed (e.g. when the provider omits it).
    """
    # OpenRouter returns errors inside a 200 body.
    error = getattr(response, "error", None) or getattr(response, "get", lambda *a: None)([None])
    if isinstance(error, dict) and error.get("message"):
        raise AIError("quota", message=str(error["message"]))
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        raise AIError("invalid_output") from None
    calls: list[ToolCall] = []
    raw_calls: list[dict] = []
    for tc in (getattr(message, "tool_calls", None) or []):
        raw_args = getattr(tc.function, "arguments", None) or "{}"
        calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=raw_args))
        raw_calls.append({"id": tc.id, "type": "function",
                          "function": {"name": tc.function.name, "arguments": raw_args if isinstance(raw_args, str) else "{}"}})
    text = getattr(message, "content", None)
    if (not text or not str(text).strip()) and not calls:
        raise AIError("invalid_output") from None
    assistant: dict = {"role": "assistant", "content": text or ""}
    if raw_calls:
        assistant["tool_calls"] = raw_calls
    usage = {}
    u = getattr(response, "usage", None)
    if u is not None:
        usage = {"prompt_tokens": getattr(u, "prompt_tokens", 0),
                 "completion_tokens": getattr(u, "completion_tokens", 0),
                 "total_tokens": getattr(u, "total_tokens", 0)}
    resp_model = model or getattr(response, "model", None)
    return ProviderReply(text=text, tool_calls=calls, assistant_message=assistant, model=resp_model, usage=usage)


# ---------------------------------------------------------------- reading the model's text

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.M)


def extract_json(text: str | None) -> dict | None:
    """Best effort: the JSON object in the model's text, or None. Never raises.

    Strips markdown code fences, then extracts the first balanced top-level JSON object.
    Returns None if nothing parses as a dict.
    """
    if not isinstance(text, str):
        return None
    cleaned = _FENCE.sub("", text).strip()
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


# ---------------------------------------------------------------- stub provider (for tests + AI_PROVIDER=stub)


# Scripted tool-call turn for testing the agent loop.
_STUB_TOOL_CALLS = [
    ToolCall(id="call_0", name="get_assessment_criteria", arguments='{"assessment_id": 1}'),
    ToolCall(id="call_1", name="get_submissions", arguments='{"assessment_id": 1, "batch_id": 1}'),
]


class StubProvider:
    """Scripted stand-in for the OpenAI/OpenRouter provider.

    Pass a list of scripted responses (the last repeats). Each item:
      - dict: returned as text (JSON-serialised)
      - str: returned verbatim as text
      - AIError: raised on that call
      - StubProviderError: converted to AIError and raised
      - list[ToolCall]: returned as tool_calls (text=None)
    """

    def __init__(self, responses: list | None = None):
        self.responses = list(responses) if responses else [{}]
        self.calls = 0

    def generate(self, messages, tools=None, schema=None, deadline=None) -> ProviderReply:
        self.calls += 1
        idx = min(self.calls - 1, len(self.responses) - 1)
        item = self.responses[idx]
        if isinstance(item, AIError):
            raise item
        if isinstance(item, StubProviderError):
            raise AIError(item.kind, message=str(item))
        if isinstance(item, list) and item and isinstance(item[0], ToolCall):
            return ProviderReply(text=None, tool_calls=item, model="stub", usage={})
        if isinstance(item, dict):
            text = json.dumps(item)
        else:
            text = str(item)
        return ProviderReply(text=text, tool_calls=[], model="stub", usage={})


def get_provider():
    """Return the configured provider object.

    'stub' -> StubProvider. 'openrouter' -> _OpenRouterProvider().
    """
    if config.force_ai_failure():
        raise AIError("quota")
    provider = os.environ.get("AI_PROVIDER", "openrouter")
    if provider == "stub":
        return StubProvider([{"status": "graded", "results": []}])
    if provider == "openrouter":
        return _OpenRouterProvider()
    raise AIError("unavailable", message=f"Unknown AI_PROVIDER: {provider!r}")


class _OpenRouterProvider:
    """OpenRouter provider that reads OPENROUTER_API_KEY and AI_MODEL from env.

    Raises AIError('unavailable', message='not configured') if the key is missing.
    Checks for response.error in 200-body responses (OpenRouter error style).
    """

    def __init__(self):
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("AI_MODEL", "")
        if not api_key or not self.model:
            raise AIError("unavailable", message="not configured")

    def generate(self, messages, tools=None, schema=None, deadline=None) -> ProviderReply:
        if config.force_ai_failure():
            raise AIError("quota")
        timeout = 45.0
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining < 2:
                raise AIError("timeout")
            timeout = min(timeout, remaining)

        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            kwargs["tools"] = tools
        if schema:
            kwargs["response_format"] = {"type": "json_object"}

        from openai import OpenAI
        client = OpenAI(base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                        api_key=os.environ.get("OPENROUTER_API_KEY"), timeout=timeout, max_retries=0)
        try:
            response = client.chat.completions.create(**kwargs)
        except AIError:
            raise
        except Exception as exc:
            raise map_error(exc) from None
        return _parse_response(response, model=self.model)
