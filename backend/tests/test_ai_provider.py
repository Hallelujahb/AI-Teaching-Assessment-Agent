"""Tests for ai_provider.py: StubProvider, OpenRouter error mapping, Factory.

No network — OpenRouter is tested through a fake HTTP client pattern.
"""
import pytest

from app.ai_provider import (
    AIError,
    ProviderReply,
    StubProvider,
    ToolCall,
    extract_json,
    get_provider,
    map_error,
)


# -----------------------------------------------------------------------
# StubProvider

def test_stub_provider_returns_dict_as_json():
    provider = StubProvider([{"status": "graded", "results": [{"student_id": "S1"}]}])
    resp = provider.generate([])
    assert resp.model == "stub"
    assert '"graded"' in resp.text


def test_stub_provider_returns_string_as_is():
    provider = StubProvider(["hello world"])
    resp = provider.generate([])
    assert resp.text == "hello world"


def test_stub_provider_raises_aierror():
    provider = StubProvider([AIError("quota", "rate limited")])
    with pytest.raises(AIError, match="rate limited"):
        provider.generate([])


def test_stub_provider_cycles_responses():
    provider = StubProvider([
        {"status": "graded", "results": []},
        {"status": "needs_clarification", "clarification": "which?"},
    ])
    r1 = provider.generate([])
    r2 = provider.generate([])
    r3 = provider.generate([])  # last repeats
    assert "graded" in r1.text
    assert "clarification" in r2.text
    assert "clarification" in r3.text  # repeats
    assert provider.calls == 3


def test_stub_provider_tool_calls():
    from app.ai_provider import _STUB_TOOL_CALLS
    provider = StubProvider([_STUB_TOOL_CALLS])
    resp = provider.generate([])
    assert len(resp.tool_calls) == 2
    assert resp.tool_calls[0].name == "get_assessment_criteria"
    assert resp.tool_calls[1].name == "get_submissions"


def test_stub_provider_default_script():
    provider = StubProvider()
    resp = provider.generate([])
    assert resp.text.strip() == "{}"


# -----------------------------------------------------------------------
# get_provider factory

def test_get_provider_stub(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "stub")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)
    provider = get_provider()
    assert isinstance(provider, StubProvider)


def test_get_provider_force_failure(monkeypatch):
    monkeypatch.setenv("FORCE_AI_FAILURE", "1")
    with pytest.raises(AIError):
        get_provider()


def test_get_provider_openrouter_not_configured(monkeypatch):
    """_OpenRouterProvider() checks OPENROUTER_API_KEY and AI_MODEL."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("AI_MODEL", "")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)
    from app.ai_provider import _OpenRouterProvider
    with pytest.raises(AIError, match="not configured"):
        _OpenRouterProvider()


def test_get_provider_unknown(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "unknown_provider")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)
    with pytest.raises(AIError, match="Unknown"):
        get_provider()


# -----------------------------------------------------------------------
# OpenRouter error mapping (tested via monkeypatched OpenAI client)


def _patch_openai(monkeypatch, create_fn):
    """Patch the OpenAI constructor and chat.completions.create."""
    class FakeChat:
        class completions:
            @staticmethod
            def create(**kwargs):
                return create_fn(**kwargs)
    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        chat = FakeChat()
    monkeypatch.setattr("openai.OpenAI", FakeClient)


def _env_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)


def test_openrouter_timeout(monkeypatch):
    import httpx
    from openai import APITimeoutError as OpenAITimeout
    _env_openrouter(monkeypatch)
    req = httpx.Request("POST", "https://test.com")

    def raise_timeout(**kwargs):
        raise OpenAITimeout(req)
    _patch_openai(monkeypatch, raise_timeout)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="too long"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_rate_limit(monkeypatch):
    import httpx
    from openai import RateLimitError
    _env_openrouter(monkeypatch)
    req = httpx.Request("POST", "https://test.com")
    resp = httpx.Response(429, request=req, content=b'{"error": {"message": "rate limited"}}')

    def raise_rl(**kwargs):
        raise RateLimitError("rate limited", response=resp, body=None)
    _patch_openai(monkeypatch, raise_rl)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="quota"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_503_is_quota(monkeypatch):
    import httpx
    from openai import APIStatusError
    _env_openrouter(monkeypatch)
    req = httpx.Request("POST", "https://test.com")
    resp = httpx.Response(503, request=req, content=b'{"error": {"message": "unavailable"}}')

    def raise_503(**kwargs):
        raise APIStatusError("unavailable", response=resp, body=None)
    _patch_openai(monkeypatch, raise_503)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="quota"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_empty_choices_invalid_output(monkeypatch):
    _env_openrouter(monkeypatch)

    class FakeReply:
        def __init__(self):
            self.choices = []
            self.usage = None
            self.error = None

    def return_empty(**kwargs):
        return FakeReply()
    _patch_openai(monkeypatch, return_empty)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="could not be used"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_error_in_200_body(monkeypatch):
    """200 response with error field → quota error."""
    _env_openrouter(monkeypatch)

    class FakeReply:
        def __init__(self):
            self.choices = []
            self.usage = None
            self.error = {"message": "model not found"}

    def return_with_error(**kwargs):
        return FakeReply()
    _patch_openai(monkeypatch, return_with_error)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="model not found"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_success_returns_provider_response(monkeypatch):
    _env_openrouter(monkeypatch)

    class FakeUsage:
        prompt_tokens = 10
        completion_tokens = 20
        total_tokens = 30

    class FakeMessage:
        content = '{"status": "graded", "results": []}'
        tool_calls = None

    class FakeChoice:
        message = FakeMessage()

    class FakeReply:
        choices = [FakeChoice()]
        usage = FakeUsage()
        error = None
        model = "test-model"

    def return_success(**kwargs):
        return FakeReply()
    _patch_openai(monkeypatch, return_success)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    resp = provider.generate([{"role": "user", "content": "hi"}])
    assert resp.text == '{"status": "graded", "results": []}'
    assert resp.usage["total_tokens"] == 30
    assert resp.model == "test-model"


def test_openrouter_empty_content_no_tool_calls(monkeypatch):
    """200 with choices but empty message content → invalid_output."""
    _env_openrouter(monkeypatch)

    class FakeMessage:
        content = None
        tool_calls = None

    class FakeChoice:
        message = FakeMessage()

    class FakeReply:
        def __init__(self):
            self.choices = [FakeChoice()]
            self.usage = None
            self.error = None

    def return_empty2(**kwargs):
        return FakeReply()
    _patch_openai(monkeypatch, return_empty2)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="could not be used"):
        provider.generate([{"role": "user", "content": "hi"}])


# -----------------------------------------------------------------------
# extract_json


def test_extract_json_clean():
    result = extract_json('{"status": "graded", "results": []}')
    assert result["status"] == "graded"


def test_extract_json_fenced():
    text = '```json\n{"status": "graded"}\n```'
    result = extract_json(text)
    assert result["status"] == "graded"


def test_extract_json_none_for_empty():
    assert extract_json("") is None
    assert extract_json(None) is None
    assert extract_json("not json") is None


def test_extract_json_array_is_none():
    """Top-level JSON array is not a dict."""
    assert extract_json("[1, 2, 3]") is None


# -----------------------------------------------------------------------
# map_error


def test_map_error_timeout():
    result = map_error(TimeoutError("timed out"))
    assert result.extra["kind"] == "timeout"


def test_map_error_rate_limit():
    import httpx
    from openai import RateLimitError
    req = httpx.Request("POST", "https://test.com")
    resp = httpx.Response(429, request=req)
    result = map_error(RateLimitError("rl", response=resp, body=None))
    assert result.extra["kind"] == "quota"


def test_map_error_connection_error():
    import httpx
    from openai import APIConnectionError
    req = httpx.Request("POST", "https://test.com")
    exc = APIConnectionError(request=req)
    result = map_error(exc)
    assert result.extra["kind"] == "unavailable"


# -----------------------------------------------------------------------
# tool_schemas never includes save tool


def test_provider_never_receives_save_tool():
    """The save tool must never be in the tool schemas."""
    from app.prompts import tool_schemas
    names = [s["function"]["name"] for s in tool_schemas]
    assert "save_reviewed_results" not in names
    assert "get_assessment_criteria" in names
    assert "get_submissions" in names
