"""A student's exams: the assignments they were given, starting one, and handing in the answer.
Students see the question and the time limit only. The reference answer and the rubric never leave
the staff routes. The answer goes into the assignment's batch, one per student.

Owner: P2
"""
import psycopg
from fastapi import APIRouter, Body, Depends, Request

from .. import config
from ..auth import require
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable
from ..limits import limiter

router = APIRouter()
student = require("student")

EXAM_SQL = """
SELECT a.id, s.title, s.question, a.time_limit_minutes, x.started_at,
  EXISTS (SELECT 1 FROM submissions sub WHERE sub.batch_id=a.batch_id AND sub.student_id=%(sid)s) AS submitted,
  EXISTS (SELECT 1 FROM grading_runs g WHERE g.batch_id=a.batch_id) AS closed,
  CASE WHEN a.time_limit_minutes IS NOT NULL AND x.started_at IS NOT NULL
       THEN x.started_at + make_interval(mins => a.time_limit_minutes) END AS deadline,
  (a.time_limit_minutes IS NOT NULL AND x.started_at IS NOT NULL
   AND now() > x.started_at + make_interval(mins => a.time_limit_minutes) + interval '30 seconds') AS expired
FROM assignment_students x JOIN assignments a ON a.id=x.assignment_id JOIN assessments s ON s.id=a.assessment_id
WHERE x.user_id=%(uid)s
"""


def _status(r: dict) -> str:
    if r["submitted"]:
        return "submitted"
    if r["closed"]:
        return "closed"
    if r["expired"]:
        return "expired"
    return "in_progress" if r["started_at"] else "open"


def _view(r: dict) -> dict:
    """The question stays hidden until a timed exam is started."""
    hidden = r["time_limit_minutes"] is not None and r["started_at"] is None
    return {"id": r["id"], "title": r["title"], "status": _status(r), "time_limit_minutes": r["time_limit_minutes"],
            "started_at": r["started_at"], "deadline": r["deadline"], "question": None if hidden else r["question"]}


def _load(conn, user: dict, exam_id: int) -> dict:
    row = conn.execute(EXAM_SQL + " AND a.id=%(aid)s", {"sid": user["student_id"], "uid": user["id"], "aid": exam_id}).fetchone()
    if not row:
        raise NotFound("Exam not found.")
    return row


@router.get("/api/me/exams")
def my_exams(user: dict = Depends(student)):
    if not user.get("student_id"):
        return []
    with get_conn() as conn:
        rows = conn.execute(EXAM_SQL + " ORDER BY a.id DESC", {"sid": user["student_id"], "uid": user["id"]}).fetchall()
    return [{k: v for k, v in _view(r).items() if k != "question"} for r in rows]


@router.get("/api/me/exams/{exam_id}")
def my_exam(exam_id: int, user: dict = Depends(student)):
    with get_conn() as conn:
        return _view(_load(conn, user, exam_id))


@router.post("/api/me/exams/{exam_id}/start")
def start_exam(exam_id: int, user: dict = Depends(student)):
    with get_conn() as conn:
        row = _load(conn, user, exam_id)
        if _status(row) in ("submitted", "closed", "expired"):
            raise Conflict("This exam can no longer be started.")
        conn.execute("UPDATE assignment_students SET started_at=coalesce(started_at, now()) "
                     "WHERE assignment_id=%s AND user_id=%s", (exam_id, user["id"]))
        return _view(_load(conn, user, exam_id))


@router.post("/api/me/exams/{exam_id}/submit", status_code=201)
@limiter.limit("10/minute")
def submit_exam(request: Request, exam_id: int, body: dict = Body(...), user: dict = Depends(student)):
    answer = str(body.get("answer") or "").strip()
    if not answer:
        raise Unprocessable("Write your answer first.", {"answer": "The answer is empty"})
    if len(answer) > config.MAX_ANSWER_CHARS:
        raise Unprocessable("Your answer is too long.", {"answer": f"Use at most {config.MAX_ANSWER_CHARS} characters"})
    try:
        with get_conn() as conn:
            row = _load(conn, user, exam_id)
            status = _status(row)
            if status == "submitted":
                raise Conflict("You already handed in this exam.")
            if status == "closed":
                raise Conflict("This exam is closed because marking has started.")
            if status == "expired":
                raise Conflict("Time is up, so this answer was not accepted.")
            if row["time_limit_minutes"] is not None and row["started_at"] is None:
                raise Conflict("Start the exam first.")
            conn.execute(
                "INSERT INTO submissions (batch_id, student_id, answer) "
                "SELECT batch_id, %s, %s FROM assignments WHERE id=%s", (user["student_id"], answer, exam_id))
    except psycopg.errors.UniqueViolation:
        raise Conflict("You already handed in this exam.")
    return {"submitted": True}
