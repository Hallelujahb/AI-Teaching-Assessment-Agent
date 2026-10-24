"""ModelOutput, ModelStudentGrade, CriterionGrade and ProposalStatus. Agreed by P3 and P4.

These describe what the model is asked to return. The agent does NOT feed the model's raw JSON
through these classes: one bad score would then reject the whole batch. The raw dict goes to
scoring.validate_model_output, which rejects only the student who is wrong and says why.
That is also why proposed_score is a plain int with no ge=0 (see docs/rule-coverage.md).

Owner: P3
Plan: section 4
"""
from typing import Literal

from pydantic import BaseModel


class CriterionGrade(BaseModel):
    criterion_id: int
    proposed_score: int          # no ge=0 on purpose: scoring.py rejects bad scores per student
    evidence: str
    explanation: str


class ModelStudentGrade(BaseModel):
    student_id: str
    answer_status: Literal["complete", "incomplete", "unassessable"]
    criteria: list[CriterionGrade]
    feedback: str
    attention_flags: list[str]


class ModelOutput(BaseModel):
    status: Literal["graded", "needs_clarification"]
    clarification: str | None = None
    results: list[ModelStudentGrade] = []


# Set by the backend only. The model can never return blank or needs_manual_grading.
ProposalStatus = Literal["complete", "incomplete", "unassessable", "blank", "needs_manual_grading"]


def output_schema() -> dict:
    """JSON schema of ModelOutput, for providers that accept one."""
    return ModelOutput.model_json_schema()
