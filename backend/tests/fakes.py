"""Stand-in fakes for Phase 0 testing: FakeTools, InMemoryRuns, scripted model.

Owner: P3
Plan: section 4 (C2 dependency ledger)

These replace tools.py, runs.py and stub_model.py until those land.
Marked # STAND-IN: replace when D<n> lands.
"""
from __future__ import annotations

import copy
import uuid
from typing import Any

from .ai_provider import AIError, ProviderResponse, StubProvider, ToolCall
from .prompts import make_nonce


# -----------------------------------------------------------------------
# FakeTools — reads from a fixture dict, writes its own tool log


class FakeTools:
    """STAND-IN: replace when D7 lands (tools.py)."""

    def __init__(self, catalog_data: list[dict], criteria: dict, submissions: dict):
        """catalog_data: [{id, title, batches:[{id, label}]}]
        criteria: the rubric dict returned by get_assessment_criteria
        submissions: {batch_id: {student_id: {student_id, answer}}}
        """
        self._catalog = catalog_data
        self._criteria = criteria
        self._submissions = submissions
        self.calls: list[dict] = []

    def get_assessment_criteria(self, run_id: str, assessment_id: str) -> dict:
        self.calls.append({"tool": "get_assessment_criteria", "args": {"assessment_id": assessment_id}})
        if str(assessment_id) not in self._catalog:
            raise ValueError(f"Unknown assessment: {assessment_id}")
        result = copy.deepcopy(self._criteria)
        result["id"] = str(assessment_id)
        return result

    def get_submissions(self, run_id: str, assessment_id: str, batch_id: str) -> dict:
        self.calls.append({"tool": "get_submissions", "args": {"assessment_id": assessment_id, "batch_id": batch_id}})
        if str(batch_id) not in self._submissions:
            raise ValueError(f"Unknown batch: {batch_id}")
        subs = copy.deepcopy(self._submissions[str(batch_id)])
        return {
            "assessment_id": str(assessment_id),
            "batch_id": str(batch_id),
            "submissions": list(subs.values()),
        }

    def catalog(self) -> list[dict]:
        return copy.deepcopy(self._catalog)


def build_js101_fixture():
    """Build FakeTools + rubric for JS101-B1 from the seed structure (D3)."""
    # STAND-IN: until seed/assessments/js101.json is used directly (D3)
    rubric = {
        "id": "JS101",
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
    submissions = {
        "1": {  # batch_id 1 → "JS101-B1"
            "ST001": {"student_id": "ST001", "answer": (
                "A variable is a named container that stores a value so a program can use it "
                "later. var can be redeclared and reassigned and is function scoped. let can "
                "be reassigned but not redeclared in the same scope and is block scoped. "
                "const cannot be reassigned or redeclared and is block scoped."
            )},
            "ST002": {"student_id": "ST002", "answer": (
                "Variables store values. let and var can be changed but const cannot be reassigned."
            )},
            "ST003": {"student_id": "ST003", "answer": ""},
        },
    }
    catalog = [{"id": "JS101", "title": "JS101: Variables in JavaScript",
                "batches": [{"id": 1, "label": "JS101-B1"}]}]
    return FakeTools(catalog, rubric, submissions), rubric, submissions["1"]


# -----------------------------------------------------------------------
# InMemoryRuns — the RunsPort stand-in


class InMemoryRuns:
    """STAND-IN: replace when D8/D9 lands (runs.py)."""

    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.saved_proposals: dict[str, list[dict]] = {}

    def create_run(self, batch_id: str | None, model: str, rubric_snapshot: dict | None = None) -> str:
        run_id = str(uuid.uuid4())
        self.runs[run_id] = {
            "run_id": run_id, "batch_id": batch_id, "model": model,
            "rubric_snapshot": rubric_snapshot,
            "status": "running", "error": None,
        }
        return run_id

    def save_proposals(self, run_id: str, proposals: list[dict]) -> None:
        self.saved_proposals[run_id] = copy.deepcopy(proposals)
        self.runs[run_id]["status"] = "succeeded"

    def finish_run(self, run_id: str, status: str, error: str | None = None) -> None:
        if run_id in self.runs:
            self.runs[run_id]["status"] = status
            self.runs[run_id]["error"] = error
            self.runs[run_id]["finished_at"] = True


# -----------------------------------------------------------------------
# FakeScoring — uses the real scoring.py since it is READY


class FakeScoring:
    """STAND-IN: delegates to the real scoring.py functions (scoring is READY)."""

    def __init__(self):
        from . import scoring as _scoring
        self._scoring = _scoring

    def detect_answer_status(self, answer: str) -> str | None:
        # STAND-IN: replace with scoring.detect_answer_status when D12 lands
        if answer is None or not isinstance(answer, str):
            return "blank"
        if not any(ch.isalnum() for ch in answer):
            return "blank"
        if sum(ch.isalpha() for ch in answer) < 3:
            return "unassessable"
        return None

    def validate_model_output(self, output, rubric, submissions) -> dict:
        return self._scoring.validate_model_output(output, rubric, submissions)

    def build_proposals(self, submissions, rubric, report) -> list[dict]:
        return self._scoring.build_proposals(submissions, rubric, report)


# -----------------------------------------------------------------------
# Scripted provider — returns canned responses per call


def make_stub_provider(responses: list) -> StubProvider:
    """Build a StubProvider with a scripted list of responses.

    Each item is one of:
      - dict: model's JSON output (returned as JSON text)
      - str: raw text
      - AIError: raised on that call
      - ToolCall list: returned as tool_calls on that call

    The last item repeats.
    """
    return StubProvider(responses)
