"""Confirmed results: GET /api/results (list) and GET /api/batches/{batch_id}/results (reopen,
with the AI proposal next to the lecturer's scores).

Owner: P2
Plan: section 7
"""
from fastapi import APIRouter

from ..db import get_conn
from ..errors import NotFound
from ..runs import proposal_view

router = APIRouter()


@router.get("/api/results")
def list_confirmed():
    with get_conn() as conn:
        return conn.execute(
            "SELECT b.id AS batch_id, b.label, a.id AS assessment_id, a.title AS assessment_title, "
            " max(r.approved_at) AS approved_at, count(*)::int AS student_count "
            "FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id "
            "JOIN submission_batches b ON b.id=s.batch_id JOIN assessments a ON a.id=b.assessment_id "
            "GROUP BY b.id, b.label, a.id, a.title ORDER BY max(r.approved_at) DESC").fetchall()


@router.get("/api/batches/{batch_id}/results")
def batch_results(batch_id: int):
    with get_conn() as conn:
        batch = conn.execute("SELECT id, assessment_id, label FROM submission_batches WHERE id=%s",
                             (batch_id,)).fetchone()
        if not batch:
            raise NotFound("Batch not found.")
        rows = conn.execute(
            "SELECT s.student_id, s.answer, r.run_id, r.scores AS final_scores, r.total, r.percentage, "
            " r.feedback AS final_feedback, r.approved_at, p.answer_status, p.scores, p.evidence, "
            " p.explanations, p.flags, p.feedback "
            "FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id "
            "JOIN ai_proposals p ON p.id=r.proposal_id WHERE s.batch_id=%s ORDER BY s.id", (batch_id,)).fetchall()
        if not rows:
            raise NotFound("This batch has not been confirmed yet.")
        run = conn.execute("SELECT rubric_snapshot FROM grading_runs WHERE id=%s", (rows[0]["run_id"],)).fetchone()
    rubric = run["rubric_snapshot"]
    max_total = sum(c["max_score"] for c in rubric)
    results = []
    for r in rows:
        results.append({
            "student_id": r["student_id"], "answer": r["answer"],
            "scores": [{"criterion_id": c["id"], "score": r["final_scores"].get(str(c["id"]))} for c in rubric],
            "total": r["total"], "percentage": float(r["percentage"]), "feedback": r["final_feedback"],
            "ai_proposal": proposal_view(r, rubric, max_total),
        })
    return {"batch_id": batch_id, "batch_label": batch["label"], "assessment_id": batch["assessment_id"],
            "run_id": str(rows[0]["run_id"]), "approved_at": max(r["approved_at"] for r in rows),
            "max_total": max_total,
            "rubric": [{"id": c["id"], "position": c.get("position"), "name": c.get("name"),
                        "max_score": c["max_score"]} for c in rubric],
            "results": results}
