"""Stub model (Person 4). Returns canned ModelOutput-shaped dicts, no network.

Used by tests, by P3 to build the loop without spending quota, and by P5 for the
out-of-range and failure checks.

    from app.stub_model import StubModel, stub_output

    out = stub_output("out_of_range", rubric, submissions)       # one-off dict
    model = StubModel(["out_of_range", "valid"])                   # scripted per call
    model.respond(rubric, submissions)                             # 1st call: bad
    model.respond(rubric, submissions)                             # 2nd call: good
    model.calls                                                    # how many times it was called

Scenarios only grade the students the code would send to the model (not blank, not
under 3 letters), exactly as the real loop does.
"""
from __future__ import annotations

import copy
from typing import Any

from .scoring import detect_answer_status, to_plain

SCENARIOS = (
    "valid", "out_of_range", "negative_score", "non_integer", "duplicate_student",
    "missing_student", "unknown_student", "duplicate_criterion", "missing_criterion",
    "unknown_criterion", "fake_quote", "bad_status", "injection_obeyed",
    "grades_blank_student", "clarification", "failure",
)


class StubProviderError(Exception):
    """Mimics the provider error kinds: 'timeout', 'quota' or 'invalid_output'.
    Adapt or replace with the error class in errors.py once P3 settles it."""

    def __init__(self, kind: str = "quota", message: str = "Stubbed AI failure"):
        super().__init__(message)
        self.kind = kind

StubError = StubProviderError  # alias for cleaner test imports

def _valid_output(rubric: list[dict], submissions: list[dict]) -> dict:
    results = []
    for s in submissions:
        answer = s.get("answer") or ""
        if detect_answer_status(answer):
            continue
        quote = answer.strip()[:60]
        results.append({
            "student_id": s["student_id"],
            "answer_status": "complete",
            "criteria": [
                {"criterion_id": c["id"], "proposed_score": c["max_score"],
                 "evidence": quote, "explanation": "Stub: full marks."}
                for c in rubric
            ],
            "feedback": "Stub feedback.",
            "attention_flags": [],
        })
    return {"status": "graded", "clarification": None, "results": results}


def stub_output(scenario: str, rubric: Any, submissions: Any) -> dict:
    """Build the output for one scenario. Raises StubProviderError for 'failure'."""
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}. Choose from {SCENARIOS}")
    rubric = [to_plain(r) for r in rubric]
    submissions = [to_plain(s) for s in submissions]

    if scenario == "failure":
        raise StubProviderError("quota")
    if scenario == "clarification":
        return {"status": "needs_clarification",
                "clarification": "Which assessment and batch do you want graded?", "results": []}

    out = _valid_output(rubric, submissions)
    res = out["results"]
    if scenario == "valid" or not res:
        return out
    first = res[0]

    if scenario == "out_of_range":
        first["criteria"][0]["proposed_score"] = rubric[0]["max_score"] + 1
    elif scenario == "negative_score":
        first["criteria"][0]["proposed_score"] = -1
    elif scenario == "non_integer":
        first["criteria"][0]["proposed_score"] = 1.5
    elif scenario == "duplicate_student":
        res.append(copy.deepcopy(first))
    elif scenario == "missing_student":
        res.pop()
    elif scenario == "unknown_student":
        extra = copy.deepcopy(first)
        extra["student_id"] = "ST999"
        res.append(extra)
    elif scenario == "duplicate_criterion":
        first["criteria"].append(copy.deepcopy(first["criteria"][0]))
    elif scenario == "missing_criterion":
        first["criteria"].pop()
    elif scenario == "unknown_criterion":
        first["criteria"][0]["criterion_id"] = 999
    elif scenario == "fake_quote":
        first["criteria"][0]["evidence"] = "this sentence was never written by the student"
    elif scenario == "bad_status":
        first["answer_status"] = "blank"  # only the backend may set this
    elif scenario == "injection_obeyed":
        pass  # valid output already gives full marks to everyone, including injected answers
    elif scenario == "grades_blank_student":
        for s in submissions:
            if detect_answer_status(s.get("answer") or ""):
                extra = copy.deepcopy(first)
                extra["student_id"] = s["student_id"]
                res.append(extra)
    return out


class StubModel:
    """Scripted stand-in for the provider. ``script`` is a list of scenario names, one per
    call; the last one repeats. Counts calls so tests can assert 'retried once, never more'."""

    def __init__(self, script: list[str] | str = "valid"):
        self.script = [script] if isinstance(script, str) else list(script)
        self.calls = 0

    def respond(self, rubric: Any, submissions: Any) -> dict:
        scenario = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return stub_output(scenario, rubric, submissions)
