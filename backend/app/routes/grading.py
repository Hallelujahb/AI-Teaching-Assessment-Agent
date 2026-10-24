"""POST /api/agent/grade. Checks limits, then calls the agent in agent.py.

CONTRACT FOR P3: implement in agent.py

    def run_grading(request_text: str | None, assessment_id: int | None, batch_id: int | None) -> dict

It returns the response body as a dict: {"status": "graded", "run_id": ..., ...} or
{"status": "needs_clarification", "run_id": ..., "clarification": "..."}. It creates the run
with runs.create_run, ends it with runs.save_proposals or runs.finish_run, and raises
errors.AIError(kind, run_id=...) for timeout, quota, invalid_output or tool_limit.

Owner: P2 route, P3 agent
Plan: section 7
"""
from fastapi import APIRouter, Request

from .. import config
from ..errors import NotReady
from ..limits import check_daily_cap, limiter
from ..models import GradeRequest

router = APIRouter()


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
    return run_grading(request_text=text or None, assessment_id=body.assessment_id, batch_id=body.batch_id)
