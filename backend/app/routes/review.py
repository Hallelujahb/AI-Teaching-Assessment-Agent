"""POST /api/batches/{batch_id}/review: confirm results (save_reviewed_results).

Body: {"run_id": "...", "results": [{"student_id", "scores": [{"criterion_id", "score"}], "feedback"}]}

Owner: P2 with P4
Plan: section 7
"""
from fastapi import APIRouter, Body

from .. import tools

router = APIRouter()


@router.post("/api/batches/{batch_id}/review")
def review(batch_id: int, body: dict = Body(...)):
    assessment_id = tools.assessment_id_for_batch(batch_id)
    return tools.save_reviewed_results(assessment_id, batch_id, body.get("run_id"), body.get("results"))
