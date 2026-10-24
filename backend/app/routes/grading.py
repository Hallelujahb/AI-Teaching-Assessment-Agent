"""POST /api/agent/grade. Checks limits, calls the agent in agent.py, and turns the agent's
result into the response shape documented in docs/api-examples.md.

The agent (P3) returns a dict with an "outcome" key:
    {"outcome": "graded", "run_id", "max_total", "results", "tool_log"}
    {"outcome": "needs_clarification", "run_id", "clarification": {"question": "..."}}
    {"outcome": "error", "run_id", "error": {"kind", "message"}}
This route answers with:
    200 {"status": "graded", ...}
    200 {"status": "needs_clarification", "run_id", "clarification": "<the question as text>"}
    503/502/504 {"error", "message", "kind", "run_id"} for AI problems (the input is kept, the UI offers a retry)

Owner: P2 route, P3 agent
Plan: section 7
"""
from fastapi import APIRouter, Request

from .. import config
from ..errors import AIError, AppError, Conflict, NotReady
from ..limits import check_daily_cap, limiter
from ..models import GradeRequest

router = APIRouter()
AI_KINDS = ("timeout", "quota", "invalid_output", "tool_limit", "unavailable")


def shape(result: dict) -> dict:
    outcome = result.get("outcome")
    if outcome is None:                                   # already in the API shape
        return result
    if outcome == "graded":
        return {"status": "graded", **{k: v for k, v in result.items() if k != "outcome"}}
    if outcome == "needs_clarification":
        asked = result.get("clarification")
        question = asked.get("question") if isinstance(asked, dict) else asked
        return {"status": "needs_clarification", "run_id": result.get("run_id"), "clarification": str(question or "")}
    error = result.get("error") or {}
    kind = error.get("kind")
    if kind in AI_KINDS:
        raise AIError(kind, run_id=result.get("run_id"))
    if kind == "bad_request":
        raise Conflict(error.get("message") or "The grading request could not be completed.")
    problem = AppError("Something went wrong while grading. Your input is kept. Try again.", run_id=result.get("run_id"))
    problem.status = 500
    raise problem


@router.post("/api/agent/grade")
@limiter.limit(config.GRADE_RATE_LIMIT)
def grade(request: Request, body: GradeRequest):
    text = (body.request or "").strip()
    if not text and body.assessment_id is None and body.batch_id is None:
        return {"status": "needs_clarification", "run_id": None,
                "clarification": "Which assessment and batch should I grade? Pick one, or describe it in the request."}
    check_daily_cap()
    from .. import agent
    run_grading = getattr(agent, "run_grading", None)
    if run_grading is None:
        raise NotReady("The grading agent is not ready yet.")
    return shape(run_grading(request_text=text or None, assessment_id=body.assessment_id, batch_id=body.batch_id))
