"""Stand-in fakes for Phase 0 testing: FakeTools, InMemoryRuns, scripted model.

Owner: P3
Plan: section 4 (C2 dependency ledger)

These replace tools.py, runs.py and ai_provider.py for testing the agent loop
without a network or database. Marked # STAND-IN: replace when D<n> lands.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any

from app.scoring import detect_answer_status, validate_model_output, build_proposals, merge_retry_report
from app.ai_provider import AIError, StubProvider, ToolCall, ProviderReply


# Alias for tests that import ProviderResponse.
ProviderResponse = ProviderReply


# -----------------------------------------------------------------------
# FakeTools — reads from a fixture dict, writes its own tool log

class FakeTools:
    """STAND-IN: replace when D7 lands (tools.py).

    Matches the real tools.py interface: get_assessment_criteria(aid, run_id=None)
    and get_submissions(aid, bid, run_id=None), plus fetch_assessment(aid).
    """

    def __init__(self, assessment: dict, criteria: dict, submissions: dict):
        """assessment: the full assessment dict (with question, reference_answer, rubric).
        criteria: the rubric dict returned by get_assessment_criteria (same as assessment here).
        submissions: {student_id: {student_id, answer, batch_id?}}  — actual submissions for the batch.
        """
        self._assessment = assessment
        self._criteria = criteria
        self._submissions = submissions
        self.calls: list[dict] = []

    def fetch_assessment(self, assessment_id: int) -> dict:
        """Return the full assessment dict. The real tools.fetch_assessment(aid) does this."""
        return copy.deepcopy(self._assessment)

    def get_assessment_criteria(self, assessment_id: int, run_id: str | None = None) -> dict:
        """Return criteria dict with keys: question, reference_answer, max_total, rubric."""
        self.calls.append({"tool": "get_assessment_criteria", "args": {"assessment_id": assessment_id}})
        result = copy.deepcopy(self._criteria)
        return result

    def get_submissions(self, assessment_id: int, batch_id: int, run_id: str | None = None) -> dict:
        """Return {label, submissions: [{student_id, answer, ...}]}."""
        self.calls.append({"tool": "get_submissions", "args": {"assessment_id": assessment_id, "batch_id": batch_id}})
        subs = copy.deepcopy(list(self._submissions.values()))
        return {"label": "B1", "submissions": subs}


def build_js101_fixture():
    """Build FakeTools + rubric + submissions for JS101-B1 from the seed structure (D3).

    Returns (FakeTools, rubric_list, submissions_dict).
    """
    # STAND-IN: until seed/assessments/js101.json is used directly (D3)
    assessment = {
        "id": 1,
        "title": "JS101: Variables in JavaScript",
        "question": "What is a variable in JavaScript, and how do let, const and var differ?",
        "reference_answer": "A variable is a named container that stores a value.",
        "rubric": [
            {"id": 1, "position": 1, "name": "Defines a variable",
             "description": "Covers: a named place that stores a value for later use.\nMarks: 2 = correct; 1 = vague; 0 = missing or wrong.\nNot credited here: anything about var, let or const.",
             "max_score": 2},
            {"id": 2, "position": 2, "name": "Reassignment and redeclaration",
             "description": "Covers: which of var, let and const can be reassigned and which can be redeclared.\nMarks: 3 = all three correct; 0 = none.\nNot credited here: scope.",
             "max_score": 3},
            {"id": 3, "position": 3, "name": "Scope",
             "description": "Covers: var is function scoped; let and const are block scoped.\nMarks: 3 = both facts correct; 0 = none.\nNot credited here: reassignment, redeclaration.",
             "max_score": 3},
        ],
        "max_total": 8,
    }
    rubric = [{"id": c["id"], "position": c["position"], "name": c["name"],
               "description": c["description"], "max_score": c["max_score"]} for c in assessment["rubric"]]
    submissions = {
        "ST001": {"student_id": "ST001", "batch_id": 1,
                  "answer": ("A variable is a named container that stores a value so a program can use it "
                             "later. var can be redeclared and reassigned and is function scoped. let can "
                             "be reassigned but not redeclared in the same scope and is block scoped. "
                             "const cannot be reassigned or redeclared and is block scoped.")},
        "ST002": {"student_id": "ST002", "batch_id": 1,
                  "answer": "Variables store values. let and var can be changed but const cannot be reassigned."},
        "ST003": {"student_id": "ST003", "batch_id": 1, "answer": ""},
    }
    fake_tools = FakeTools(assessment, {**assessment, "id": 1}, submissions)
    return fake_tools, rubric, submissions


# -----------------------------------------------------------------------
# InMemoryRuns — the RunsPort stand-in

class InMemoryRuns:
    """STAND-IN: replace when D8/D9 lands (runs.py).

    Matches the real runs.py interface: create_run, save_proposals, finish_run, get_run.
    """

    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.saved_proposals: dict[str, list[dict]] = {}

    def create_run(self, batch_id: int, model: str | None, rubric_snapshot: list[dict]) -> str:
        run_id = str(uuid.uuid4())
        self.runs[run_id] = {
            "run_id": run_id, "batch_id": batch_id, "model": model,
            "rubric_snapshot": rubric_snapshot,
            "status": "running", "error": None,
            "proposals": [], "tool_log": [], "max_total": sum(c["max_score"] for c in rubric_snapshot),
        }
        return run_id

    def save_proposals(self, run_id: str, proposals: list[dict]) -> None:
        self.saved_proposals[run_id] = copy.deepcopy(proposals)
        self.runs[run_id]["proposals"] = copy.deepcopy(proposals)
        self.runs[run_id]["status"] = "succeeded"

    def finish_run(self, run_id: str, status: str, error: str | None = None) -> None:
        if run_id in self.runs:
            self.runs[run_id]["status"] = status
            self.runs[run_id]["error"] = error

    def get_run(self, run_id: str) -> dict:
        """Return {run_id, max_total, proposals, tool_log}."""
        run = self.runs[run_id]
        return {
            "run_id": run["run_id"],
            "max_total": run["max_total"],
            "proposals": copy.deepcopy(self.saved_proposals.get(run_id, [])),
            "tool_log": run["tool_log"],
            "status": run["status"],
        }


# -----------------------------------------------------------------------
# Scripted provider — returns canned responses per call

def make_stub_provider(responses: list) -> StubProvider:
    """Build a StubProvider with a scripted list of responses.

    Each item is one of:
      - dict: model's JSON output (returned as JSON text)
      - str: raw text
      - AIError: raised on that call
      - list[ToolCall]: returned as tool_calls on that call

    The last item repeats.
    """
    return StubProvider(responses)
