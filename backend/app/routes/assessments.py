"""Assessments: list, read, create, edit and delete (question, reference answer and rubric),
plus the list of registered students for the answers form.

An assessment is locked once any batch has been graded or it has been assigned to students, because past runs and results refer to its rubric.

Owner: P2
"""
from fastapi import APIRouter, Body, Request

from .. import tools
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable
from ..limits import limiter

router = APIRouter()
MIN_CRITERIA = 3
MAX_CRITERIA = 8
MAX_CRITERION_SCORE = 1000   # sanity ceiling only; the lecturer picks the real value

LIST_SQL = """
SELECT a.id, a.title, a.question,
  (SELECT count(*) FROM rubric_criteria c WHERE c.assessment_id=a.id)::int AS criteria_count,
  (SELECT coalesce(sum(c.max_score),0) FROM rubric_criteria c WHERE c.assessment_id=a.id)::int AS max_total,
  (SELECT count(*) FROM submission_batches b WHERE b.assessment_id=a.id)::int AS batch_count,
  (EXISTS (SELECT 1 FROM grading_runs g JOIN submission_batches b ON b.id=g.batch_id WHERE b.assessment_id=a.id)
   OR EXISTS (SELECT 1 FROM assignments x WHERE x.assessment_id=a.id)) AS locked
FROM assessments a ORDER BY a.id
"""


def _int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _clean(body: dict) -> dict:
    errors, rows = {}, []
    title = str(body.get("title") or "").strip()
    question = str(body.get("question") or "").strip()
    reference = str(body.get("reference_answer") or "").strip()
    if not title or len(title) > 120:
        errors["title"] = "Enter a title of up to 120 characters"
    if not question or len(question) > 1500:
        errors["question"] = "Enter the question (up to 1500 characters)"
    if not reference or len(reference) > 2000:
        errors["reference_answer"] = "Enter a reference answer (up to 2000 characters)"
    rubric = body.get("rubric")
    if not isinstance(rubric, list) or not MIN_CRITERIA <= len(rubric) <= MAX_CRITERIA:
        errors["rubric"] = f"Add at least {MIN_CRITERIA} criteria (up to {MAX_CRITERIA})"
    else:
        for i, c in enumerate(rubric):
            c = c if isinstance(c, dict) else {}
            name, desc, mx = str(c.get("name") or "").strip(), str(c.get("description") or "").strip(), _int(c.get("max_score"))
            if not name or len(name) > 80:
                errors[f"rubric[{i}].name"] = "Name the criterion (up to 80 characters)"
            if not desc or len(desc) > 600:
                errors[f"rubric[{i}].description"] = "Describe what earns marks (up to 600 characters)"
            if mx is None or not 1 <= mx <= MAX_CRITERION_SCORE:
                errors[f"rubric[{i}].max_score"] = f"Use a whole number from 1 to {MAX_CRITERION_SCORE}"
            rows.append((i + 1, name, desc, mx))
    if errors:
        raise Unprocessable("Please fix the highlighted fields.", errors)
    return {"title": title, "question": question, "reference": reference, "rows": rows}


def _locked(conn, aid: int) -> bool:
    return conn.execute(
        "SELECT EXISTS (SELECT 1 FROM grading_runs g JOIN submission_batches b ON b.id=g.batch_id WHERE b.assessment_id=%s) "
        "OR EXISTS (SELECT 1 FROM assignments WHERE assessment_id=%s) AS locked", (aid, aid)).fetchone()["locked"]


def _save_rubric(conn, aid: int, rows: list) -> None:
    for position, name, desc, mx in rows:
        conn.execute("INSERT INTO rubric_criteria (assessment_id, position, name, description, max_score) VALUES (%s,%s,%s,%s,%s)",
                     (aid, position, name, desc, mx))


@router.get("/api/assessments")
def list_assessments():
    with get_conn() as conn:
        return conn.execute(LIST_SQL).fetchall()


@router.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: int):
    a = tools.fetch_assessment(assessment_id)
    with get_conn() as conn:
        a["locked"] = _locked(conn, assessment_id)
    return a


@router.post("/api/assessments", status_code=201)
@limiter.limit("20/minute")
def create_assessment(request: Request, body: dict = Body(...)):
    d = _clean(body)
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM assessments WHERE lower(title)=lower(%s)", (d["title"],)).fetchone():
            raise Conflict("An assessment with this title already exists.", {"title": "Already used"})
        aid = conn.execute("INSERT INTO assessments (title, question, reference_answer) VALUES (%s,%s,%s) RETURNING id",
                           (d["title"], d["question"], d["reference"])).fetchone()["id"]
        _save_rubric(conn, aid, d["rows"])
    return {"id": aid}


@router.put("/api/assessments/{assessment_id}")
@limiter.limit("20/minute")
def update_assessment(request: Request, assessment_id: int, body: dict = Body(...)):
    d = _clean(body)
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM assessments WHERE id=%s", (assessment_id,)).fetchone():
            raise NotFound("Assessment not found.")
        if _locked(conn, assessment_id):
            raise Conflict("This assessment has been graded or assigned, so its question and rubric are locked.")
        if conn.execute("SELECT 1 FROM assessments WHERE lower(title)=lower(%s) AND id<>%s", (d["title"], assessment_id)).fetchone():
            raise Conflict("An assessment with this title already exists.", {"title": "Already used"})
        conn.execute("UPDATE assessments SET title=%s, question=%s, reference_answer=%s WHERE id=%s",
                     (d["title"], d["question"], d["reference"], assessment_id))
        conn.execute("DELETE FROM rubric_criteria WHERE assessment_id=%s", (assessment_id,))
        _save_rubric(conn, assessment_id, d["rows"])
    return {"id": assessment_id}


@router.delete("/api/assessments/{assessment_id}")
def delete_assessment(assessment_id: int):
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM assessments WHERE id=%s", (assessment_id,)).fetchone():
            raise NotFound("Assessment not found.")
        if _locked(conn, assessment_id):
            raise Conflict("This assessment has been graded or assigned, so it cannot be deleted. Remove its assignments first.")
        conn.execute("DELETE FROM assessments WHERE id=%s", (assessment_id,))
    return {"deleted": assessment_id}


@router.get("/api/students")
def list_students(q: str = "", limit: int = 200):
    """Active students. ?q= searches id and name."""
    q = q.strip()
    like = f"%{q}%"
    limit = max(1, min(limit, 1000))
    with get_conn() as conn:
        return conn.execute(
            "SELECT student_id, name, email FROM users WHERE role='student' AND status='active' "
            "AND student_id IS NOT NULL AND (%s::text = '' OR student_id ILIKE %s OR name ILIKE %s) "
            "ORDER BY student_id LIMIT %s", (q, like, like, limit)).fetchall()
