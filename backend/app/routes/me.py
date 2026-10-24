"""Student dashboard data: only the signed-in student's own confirmed results.

Owner: P2
"""
from fastapi import APIRouter, Depends

from ..auth import require
from ..db import get_conn

router = APIRouter()


@router.get("/api/me/results")
def my_results(user: dict = Depends(require("student"))):
    if not user.get("student_id"):
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.title, b.label, r.scores, r.total, r.percentage, r.feedback, r.approved_at, g.rubric_snapshot "
            "FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id "
            "JOIN submission_batches b ON b.id=s.batch_id JOIN assessments a ON a.id=b.assessment_id "
            "JOIN grading_runs g ON g.id=r.run_id WHERE s.student_id=%s ORDER BY r.approved_at DESC",
            (user["student_id"],)).fetchall()
    out = []
    for r in rows:
        rubric = r["rubric_snapshot"] or []
        out.append({
            "assessment": r["title"], "batch": r["label"], "approved_at": r["approved_at"],
            "total": r["total"], "max_total": sum(c["max_score"] for c in rubric),
            "percentage": float(r["percentage"]), "feedback": r["feedback"],
            "criteria": [{"name": c.get("name"), "max_score": c["max_score"], "score": r["scores"].get(str(c["id"]))} for c in rubric],
        })
    return out