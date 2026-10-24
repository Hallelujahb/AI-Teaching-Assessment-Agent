"""Tests for ai_provider.py: StubProvider, OpenRouter error mapping, Factory.

No network — OpenRouter is tested through a fake HTTP client pattern.
"""
import pytest

from app.ai_provider import (
    AIError,
    ProviderResponse,
    StubProvider,
    ToolCall,
    get_provider,
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
    with pytest.raises(AIError, match="quota"):
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
    with pytest.raises(AIError, match="quota"):
        get_provider()


def test_get_provider_openrouter_not_configured(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
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

class FakeOpenAI:
    """Stand-in for the openai.OpenAI client to test error mapping."""

    def __init__(self, *, completions_response=None, completions_error=None):
        self._response = completions_response
        self._error = completions_error
        self.create_calls = 0

    class chat:
        @staticmethod
        def completions():
            return FakeOpenAI.chat_completions()

    class chat_completions:
        @staticmethod
        def create(**kwargs):
            pass


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
    monkeypatch.setattr("app.ai_provider.OpenAI", FakeClient)


def test_openrouter_timeout(monkeypatch):
    from openai import TimeoutError as OpenAITimeout
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

    def raise_timeout(**kwargs):
        raise OpenAITimeout("timed out")
    _patch_openai(monkeypatch, raise_timeout)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="timeout"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_rate_limit(monkeypatch):
    from openai import RateLimitError

    class FakeResp:
        status_code = 429
        message = "rate limited"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

    def raise_rl(**kwargs):
        raise RateLimitError("rate limited", response=FakeResp())
    _patch_openai(monkeypatch, raise_rl)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="quota"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_503_is_quota(monkeypatch):
    from openai import APIError

    class FakeResp:
        status_code = 503
        message = "unavailable"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

    def raise_503(**kwargs):
        raise APIError("unavailable", response=FakeResp())
    _patch_openai(monkeypatch, raise_503)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="quota"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_empty_choices_invalid_output(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

    class FakeChoices:
        def __iter__(self):
            return iter([])
    class FakeReply:
        choices = []
        usage = None
        error = None
        def __bool__(self):
            return False

    def return_empty(**kwargs):
        return FakeReply
    _patch_openai(monkeypatch, return_empty)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="invalid_output"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_error_in_200_body(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

    class FakeMessage:
        content = None
        tool_calls = None
    class FakeChoice:
        message = FakeMessage()
    class FakeReply:
        choices = [FakeChoice()]
        usage = None
        error = {"message": "model not found"}
        def __bool__(self):
            return True

    def return_with_error(**kwargs):
        return FakeReply
    _patch_openai(monkeypatch, return_with_error)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="quota"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_openrouter_success_returns_provider_response(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

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

    def return_success(**kwargs):
        return FakeReply
    _patch_openai(monkeypatch, return_success)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    resp = provider.generate([{"role": "user", "content": "hi"}])
    assert resp.text == '{"status": "graded", "results": []}'
    assert resp.usage["total_tokens"] == 30
    assert resp.model == "test-model"


def test_openrouter_empty_content_no_tool_calls(monkeypatch):
    """200 with empty choices body → invalid_output."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER", "openrouter")
    monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)

    class FakeMessage:
        content = None
        tool_calls = None
    class FakeChoice:
        message = FakeMessage()
    class FakeReply:
        choices = []
        usage = None
        error = None

    def return_empty2(**kwargs):
        return FakeReply
    _patch_openai(monkeypatch, return_empty2)

    from app.ai_provider import _OpenRouterProvider
    provider = _OpenRouterProvider()
    with pytest.raises(AIError, match="invalid_output"):
        provider.generate([{"role": "user", "content": "hi"}])


def test_provider_never_receives_save_tool():
    """The save tool must never be in the tool schemas."""
    from app.prompts import tool_schemas
    names = [s["function"]["name"] for s in tool_schemas()]
    assert "save_reviewed_results" not in names
