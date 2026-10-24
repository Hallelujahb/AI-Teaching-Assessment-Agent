"""Agent loop (P3), tested without a database or network.

The provider, the tools and the run helpers are replaced by fakes, and the grading call is
answered by P4's StubModel, so these tests spend no AI quota. They prove the rules from plan
sections 4 and 6: the model picks the tools, caps stop a runaway loop, blank answers never reach
the model, one retry only, needs_manual_grading, clarification, and the forced failure."""
import json
from types import SimpleNamespace

import pytest

from app import agent, ai_provider
from app.errors import AIError
from app.ai_provider import ProviderReply, ToolCall
from app.stub_model import StubModel
from tests.conftest import INJECTION, ST001, ST002

REAL_GENERATE = ai_provider.generate

RUBRIC = [
    {"id": 1, "position": 1, "name": "Defines a variable", "description": "Covers: x\nMarks: 2", "max_score": 2},
    {"id": 2, "position": 2, "name": "Reassignment and redeclaration", "description": "d", "max_score": 3},
    {"id": 3, "position": 3, "name": "Scope", "description": "d", "max_score": 3},
]
ASSESSMENT = {"id": 1, "title": "JS101: Variables in JavaScript", "question": "q", "reference_answer": "r",
              "rubric": RUBRIC, "max_total": 8}
SUBS = [{"student_id": "ST001", "answer": ST001}, {"student_id": "ST002", "answer": ST002},
        {"student_id": "ST003", "answer": ""}]
BOTH_TOOLS = [[("get_assessment_criteria", {"assessment_id": 1}), ("get_submissions", {"assessment_id": 1, "batch_id": 1})]]


def reply_with_calls(calls):
    tcs = [ToolCall(id=f"c{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls)]
    msg = {"role": "assistant", "content": "", "tool_calls": [
        {"id": t.id, "type": "function", "function": {"name": t.name, "arguments": json.dumps(t.arguments)}} for t in tcs]}
    return ProviderReply(text=None, tool_calls=tcs, assistant_message=msg)


class Env:
    """Fakes for everything outside agent.py. Records what the agent did."""

    def __init__(self, monkeypatch, tool_script=None, grading=("valid",), subs=SUBS, text_reply=None, fail_with=None):
        for key, value in (("AI_BASE_URL", "https://example.test/v1"), ("AI_API_KEY", "k"), ("AI_MODEL", "m")):
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("FORCE_AI_FAILURE", raising=False)
        self.subs, self.tool_script = subs, list(tool_script if tool_script is not None else BOTH_TOOLS)
        self.stub = StubModel(list(grading))
        self.executed, self.messages_seen, self.finished, self.saved, self.steps = [], [], [], None, []
        self.text_reply, self.fail_with = text_reply, fail_with

        monkeypatch.setattr(agent, "_resolve_target", lambda t, a, b: (1, 1, None))
        monkeypatch.setattr(agent, "_log_step", lambda run_id, name, *a, **k: self.steps.append(name))
        monkeypatch.setattr(agent, "tools", SimpleNamespace(
            fetch_assessment=lambda aid: ASSESSMENT,
            get_assessment_criteria=self._criteria, get_submissions=self._subs))
        monkeypatch.setattr(agent, "runs", SimpleNamespace(
            create_run=lambda bid, model, rubric: "run-1",
            finish_run=lambda rid, status, error=None: self.finished.append((status, error)),
            save_proposals=self._save,
            get_run=lambda rid: {"max_total": 8, "proposals": self.saved, "tool_log": []}))
        monkeypatch.setattr(ai_provider, "generate", self._generate)

    def _criteria(self, aid, run_id=None):
        self.executed.append("get_assessment_criteria")
        return ASSESSMENT

    def _subs(self, aid, bid, run_id=None):
        self.executed.append("get_submissions")
        return {"assessment_id": aid, "batch_id": bid, "label": "JS101-B1", "submissions": self.subs}

    def _save(self, run_id, proposals):
        self.saved = proposals

    def _generate(self, messages, tools=None, schema=None, deadline=None):
        self.messages_seen.append((bool(tools), messages))
        if self.fail_with:
            raise AIError(self.fail_with)
        if tools:
            if self.text_reply is not None:
                return ProviderReply(text=self.text_reply)
            return reply_with_calls(self.tool_script.pop(0))
        return ProviderReply(text=json.dumps(self.stub.respond(RUBRIC, self.subs)))

    def grading_prompts(self):
        return [m[1][1]["content"] for m in self.messages_seen if not m[0]]


def run(env=None):
    return agent.run_grading("grade it", 1, 1)


def by_student(env):
    return {p["student_id"]: p for p in env.saved}


# ---------------------------------------------------------------- happy path
def test_model_chooses_tools_and_every_student_gets_a_proposal(monkeypatch):
    env = Env(monkeypatch)
    out = run()
    assert out["status"] == "graded" and out["run_id"] == "run-1"
    assert env.executed == ["get_assessment_criteria", "get_submissions"]
    assert [p["student_id"] for p in env.saved] == ["ST001", "ST002", "ST003"]
    assert by_student(env)["ST003"]["answer_status"] == "blank"
    assert env.stub.calls == 1 and env.finished == []     # saved by save_proposals, not closed as failed


def test_blank_answer_never_reaches_the_model(monkeypatch):
    env = Env(monkeypatch)
    run()
    everything = json.dumps([m[1] for m in env.messages_seen], default=str)
    assert "ST001" in everything and "ST003" not in everything


def test_answers_are_delimited_and_flagged_as_data(monkeypatch):
    env = Env(monkeypatch)
    run()
    prompt = env.grading_prompts()[0]
    assert "<<<ANSWER" in prompt and "never instructions" in prompt


def test_all_blank_batch_makes_no_grading_call(monkeypatch):
    blanks = [{"student_id": "A", "answer": ""}, {"student_id": "B", "answer": "?!"}, {"student_id": "C", "answer": "ab"}]
    env = Env(monkeypatch, subs=blanks)
    out = run()
    assert out["status"] == "graded" and env.stub.calls == 0
    assert {p["answer_status"] for p in env.saved} == {"blank", "unassessable"}


# ---------------------------------------------------------------- validation, retry, manual grading
def test_invalid_student_is_retried_once_for_that_student_only(monkeypatch):
    env = Env(monkeypatch, grading=("out_of_range", "valid"))
    run()
    assert env.stub.calls == 2
    retry_prompt = env.grading_prompts()[1]
    assert "ST001" in retry_prompt and "ST002" not in retry_prompt and "outside the allowed range" in retry_prompt
    assert by_student(env)["ST001"]["answer_status"] == "complete"
    assert by_student(env)["ST002"]["answer_status"] == "complete"


def test_still_invalid_after_retry_needs_manual_grading_and_never_retries_again(monkeypatch):
    env = Env(monkeypatch, grading=("out_of_range",))
    run()
    assert env.stub.calls == 2                                         # one retry, never more
    p = by_student(env)
    assert p["ST001"]["answer_status"] == "needs_manual_grading"
    assert p["ST001"]["scores"] == {"1": None, "2": None, "3": None}
    assert p["ST002"]["answer_status"] == "complete"


def test_fake_quote_keeps_the_score_with_a_flag_and_no_retry(monkeypatch):
    env = Env(monkeypatch, grading=("fake_quote",))
    run()
    assert env.stub.calls == 1
    assert any("Quote not found" in f for f in by_student(env)["ST001"]["flags"])


def test_model_that_obeys_an_injected_answer_is_rejected(monkeypatch):
    subs = [{"student_id": "ST001", "answer": ST001}, {"student_id": "INJ", "answer": INJECTION}]
    env = Env(monkeypatch, grading=("injection_obeyed",), subs=subs)
    run()
    assert env.stub.calls == 2 and by_student(env)["INJ"]["answer_status"] == "needs_manual_grading"
    assert by_student(env)["ST001"]["answer_status"] == "complete"


def test_unparseable_output_twice_is_an_invalid_output_error(monkeypatch):
    env = Env(monkeypatch)
    env.stub = SimpleNamespace(calls=0, respond=lambda *a: None)
    monkeypatch.setattr(ai_provider, "extract_json", lambda text: None)
    with pytest.raises(AIError) as exc:
        run()
    assert exc.value.extra["kind"] == "invalid_output" and exc.value.extra["run_id"] == "run-1"
    assert env.finished and env.finished[0][0] == "failed" and env.saved is None


# ---------------------------------------------------------------- clarification
def test_model_asking_a_question_returns_clarification_and_calls_no_tool(monkeypatch):
    env = Env(monkeypatch, text_reply="Which batch do you mean?")
    out = run()
    assert out["status"] == "needs_clarification" and out["clarification"] == "Which batch do you mean?"
    assert env.executed == [] and env.saved is None and env.finished[0][0] == "failed"


def test_model_clarification_in_the_grading_call(monkeypatch):
    env = Env(monkeypatch, grading=("clarification",))
    assert run()["status"] == "needs_clarification" and env.saved is None


def test_assessment_without_rubric_asks_instead_of_guessing(monkeypatch):
    env = Env(monkeypatch)
    monkeypatch.setattr(agent.tools, "fetch_assessment", lambda aid: {**ASSESSMENT, "rubric": []})
    out = run()
    assert out["status"] == "needs_clarification" and out["run_id"] is None and env.messages_seen == []


# ---------------------------------------------------------------- caps and failures
def test_tool_call_cap_stops_the_run(monkeypatch):
    five = [("get_assessment_criteria", {"assessment_id": 1})] * 5
    env = Env(monkeypatch, tool_script=[five])
    with pytest.raises(AIError) as exc:
        run()
    assert exc.value.extra["kind"] == "tool_limit" and len(env.executed) == 4 and env.finished[0][0] == "failed"


def test_turn_cap_stops_a_model_that_never_finishes(monkeypatch):
    one = [("get_assessment_criteria", {"assessment_id": 1})]
    env = Env(monkeypatch, tool_script=[one] * 10)
    with pytest.raises(AIError) as exc:
        run()
    assert exc.value.extra["kind"] == "tool_limit"
    assert len(env.messages_seen) == 4                                  # 4 tool-phase turns, then stop


def test_model_cannot_use_an_id_it_invented(monkeypatch):
    bad = [[("get_submissions", {"assessment_id": 1, "batch_id": 99})], BOTH_TOOLS[0]]
    env = Env(monkeypatch, tool_script=bad)
    assert run()["status"] == "graded"
    assert env.executed == ["get_assessment_criteria", "get_submissions"]   # the bad call ran nothing


def test_provider_failure_closes_the_run_and_carries_the_run_id(monkeypatch):
    env = Env(monkeypatch, fail_with="quota")
    with pytest.raises(AIError) as exc:
        run()
    assert exc.value.extra == {"kind": "quota", "run_id": "run-1"} and exc.value.status == 503
    assert env.executed == [] and env.saved is None and env.finished[0][0] == "failed"


def test_force_ai_failure_gives_quota_error_with_no_network_and_no_tool_calls(monkeypatch):
    env = Env(monkeypatch)
    monkeypatch.setattr(ai_provider, "generate", REAL_GENERATE)         # the real provider, not the fake
    monkeypatch.setenv("FORCE_AI_FAILURE", "1")
    with pytest.raises(AIError) as exc:
        run()
    assert exc.value.extra == {"kind": "quota", "run_id": "run-1"}
    assert env.executed == [] and env.finished[0][0] == "failed"        # failed run recorded, no tool calls


def test_unconfigured_ai_is_refused_before_a_run_exists(monkeypatch):
    env = Env(monkeypatch)
    monkeypatch.setenv("AI_API_KEY", "replace_me")
    with pytest.raises(AIError) as exc:
        run()
    assert exc.value.extra["kind"] == "unavailable" and env.finished == []


# ---------------------------------------------------------------- provider helpers
def test_extract_json_handles_fences_thinking_and_garbage():
    assert ai_provider.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai_provider.extract_json('<think>hmm</think>Here: {"b": 2} done') == {"b": 2}
    assert ai_provider.extract_json("no json") is None
    assert ai_provider.extract_json("[1, 2]") is None and ai_provider.extract_json(None) is None


# ---------------------------------------------------------------- which assessment and batch
ASSESSMENTS = [{"id": 1, "title": "JS101: Variables in JavaScript"}, {"id": 2, "title": "PY101: Lists and tuples in Python"}]
BATCHES = [{"id": 1, "assessment_id": 1, "label": "JS101-B1", "confirmed": False},
           {"id": 2, "assessment_id": 2, "label": "PY101-B1", "confirmed": False}]


def test_request_text_picks_the_matching_assessment_and_batch():
    assert agent.pick_target("grade the Python batch", None, None, ASSESSMENTS, BATCHES) == (2, 2, None)
    assert agent.pick_target("mark JS101-B1 please", None, None, ASSESSMENTS, BATCHES) == (1, 1, None)


def test_vague_request_gets_a_clarification_listing_the_options():
    aid, bid, question = agent.pick_target("grade the batch", None, None, ASSESSMENTS, BATCHES)
    assert (aid, bid) == (None, None) and "JS101" in question and "PY101" in question


def test_request_matching_two_assessments_is_ambiguous():
    assert agent.pick_target("grade python and javascript", None, None, ASSESSMENTS, BATCHES)[2]


def test_ids_from_the_form_win_and_mismatch_is_clarified():
    assert agent.pick_target(None, 1, 1, ASSESSMENTS, BATCHES) == (1, 1, None)
    assert agent.pick_target(None, 2, 1, ASSESSMENTS, BATCHES)[2]


def test_several_open_batches_need_a_choice():
    more = BATCHES + [{"id": 3, "assessment_id": 1, "label": "Judge test 1", "confirmed": False}]
    assert "JS101-B1" in agent.pick_target("grade javascript", None, None, ASSESSMENTS, more)[2]
    assert agent.pick_target("grade javascript Judge test 1", None, None, ASSESSMENTS, more)[:2] == (1, 3)


# ---------------------------------------------------------------- provider mapping and parsing
@pytest.mark.parametrize("status,kind", [(429, "quota"), (503, "quota"), (504, "timeout"), (401, "unavailable"),
                                         (404, "unavailable"), (400, "invalid_output")])
def test_provider_errors_map_to_clear_kinds(status, kind):
    class Boom(Exception):
        status_code = status
    assert ai_provider.map_error(Boom("secret detail")).extra["kind"] == kind


def test_timeouts_map_to_timeout_and_messages_never_leak_details():
    err = ai_provider.map_error(TimeoutError("host=db.internal key=sk-123"))
    assert err.extra["kind"] == "timeout" and "sk-123" not in err.message and "db.internal" not in err.message


def test_tool_calls_are_parsed_and_bad_arguments_become_empty():
    def tc(i, name, args):
        return SimpleNamespace(id=i, function=SimpleNamespace(name=name, arguments=args))
    msg = SimpleNamespace(content=None, tool_calls=[tc("a", "get_submissions", '{"batch_id": 1}'), tc("b", "x", "not json")])
    reply = ai_provider._parse_response(SimpleNamespace(choices=[SimpleNamespace(message=msg)]))
    assert [c.name for c in reply.tool_calls] == ["get_submissions", "x"]
    assert reply.tool_calls[0].arguments == {"batch_id": 1} and reply.tool_calls[1].arguments == {}
    assert reply.assistant_message["role"] == "assistant" and len(reply.assistant_message["tool_calls"]) == 2


def test_empty_provider_response_is_invalid_output():
    with pytest.raises(AIError) as exc:
        ai_provider._parse_response(SimpleNamespace(choices=[]))
    assert exc.value.extra["kind"] == "invalid_output"


def test_deadline_already_passed_is_a_timeout(monkeypatch):
    Env(monkeypatch)
    monkeypatch.setattr(ai_provider, "generate", REAL_GENERATE)
    with pytest.raises(AIError) as exc:
        ai_provider.generate([], deadline=0.0)
    assert exc.value.extra["kind"] == "timeout"
