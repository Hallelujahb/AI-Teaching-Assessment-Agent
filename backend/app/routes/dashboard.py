"""GET /api/dashboard: totals, every batch with its stage, and recent runs. Real data only.

Stage: ready (no finished run), review (a run finished, not confirmed), confirmed.
Agreement: share of criterion scores the lecturer kept exactly as the AI proposed.

Owner: P2
"""
from fastapi import APIRouter, Depends

from ..auth import require
from ..db import get_conn

router = APIRouter()

BATCH_SQL = """
SELECT b.id, b.label, b.assessment_id, a.title,
  (SELECT count(*) FROM submissions s WHERE s.batch_id=b.id)::int AS student_count,
  (SELECT coalesce(sum(c.max_score),0) FROM rubric_criteria c WHERE c.assessment_id=a.id)::int AS max_total,
  EXISTS (SELECT 1 FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id WHERE s.batch_id=b.id) AS confirmed,
  (SELECT g.id FROM grading_runs g WHERE g.batch_id=b.id AND g.status='succeeded' ORDER BY g.started_at DESC LIMIT 1) AS latest_run_id
FROM submission_batches b JOIN assessments a ON a.id=b.assessment_id ORDER BY b.id DESC
"""


@router.get("/api/dashboard")
def dashboard(user: dict = Depends(require("lecturer", "superadmin"))):
    with get_conn() as conn:
        rows = conn.execute(BATCH_SQL).fetchall()
        ids = [str(r["latest_run_id"]) for r in rows if r["latest_run_id"]]
        flagged = {}
        if ids:
            for f in conn.execute(
                "SELECT run_id, count(*)::int AS n FROM ai_proposals WHERE run_id = ANY(%s::uuid[]) "
                "AND jsonb_array_length(flags) > 0 GROUP BY run_id", (ids,)).fetchall():
                flagged[str(f["run_id"])] = f["n"]
        pairs = conn.execute("SELECT p.scores AS ai, r.scores AS final FROM reviewed_results r JOIN ai_proposals p ON p.id=r.proposal_id").fetchall()
        same = total = 0
        for p in pairs:
            for k, v in (p["ai"] or {}).items():
                if v is not None:
                    total += 1
                    same += v == (p["final"] or {}).get(k)
        confirmed_students = conn.execute("SELECT count(*)::int AS n FROM reviewed_results").fetchone()["n"]
        assessments = conn.execute("SELECT count(*)::int AS n FROM assessments").fetchone()["n"]
        recent = conn.execute(
            "SELECT g.id, g.status, g.started_at, g.finished_at, g.error, b.label FROM grading_runs g "
            "JOIN submission_batches b ON b.id=g.batch_id ORDER BY g.started_at DESC LIMIT 12").fetchall()
    batches = []
    for r in rows:
        rid = str(r["latest_run_id"]) if r["latest_run_id"] else None
        stage = "confirmed" if r["confirmed"] else ("review" if rid else "ready")
        batches.append({**r, "latest_run_id": rid, "stage": stage, "flagged": flagged.get(rid, 0)})
    count = lambda s: sum(1 for b in batches if b["stage"] == s)  # noqa: E731
    return {
        "stats": {"assessments": assessments, "ready": count("ready"), "review": count("review"),
                  "confirmed_batches": count("confirmed"), "confirmed_students": confirmed_students,
                  "agreement": round(100 * same / total, 1) if total else None},
        "batches": batches,
        "recent_runs": [{**r, "id": str(r["id"])} for r in recent],
    }