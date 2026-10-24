"""Assign an assessment to a class or to chosen students, and follow how many have answered.
An assignment owns one submission batch. Students type their own answers into it, and the lecturer
then grades that batch like any other. The student list is fixed when the assignment is made.

Owner: P2
"""
import psycopg
from fastapi import APIRouter, Body, Depends, Request

from .. import config
from ..auth import Forbidden, require
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable
from ..limits import limiter
from .assessments import _int
from .classes import clean_codes, owned_class, students_by_code

router = APIRouter()
staff = require("lecturer", "superadmin")

LIST_SQL = """
SELECT a.id, a.assessment_id, s.title, a.batch_id, b.label, c.name AS class_name, a.time_limit_minutes, a.created_at,
  (SELECT count(*) FROM assignment_students x WHERE x.assignment_id=a.id)::int AS assigned_count,
  (SELECT count(*) FROM submissions sub WHERE sub.batch_id=a.batch_id)::int AS submitted_count,
  EXISTS (SELECT 1 FROM grading_runs g WHERE g.batch_id=a.batch_id) AS closed
FROM assignments a JOIN assessments s ON s.id=a.assessment_id JOIN submission_batches b ON b.id=a.batch_id
LEFT JOIN classes c ON c.id=a.class_id
WHERE {where} ORDER BY a.id DESC
"""


def _time_limit(value):
    if value in (None, ""):
        return None
    minutes = _int(value)
    if minutes is None or not 1 <= minutes <= config.MAX_TIME_LIMIT_MINUTES:
        raise Unprocessable("Please fix the highlighted fields.",
                            {"time_limit_minutes": f"Use a whole number from 1 to {config.MAX_TIME_LIMIT_MINUTES}"})
    return minutes


def _label(conn, assessment_id: int, base: str) -> str:
    taken = {r["label"] for r in conn.execute("SELECT label FROM submission_batches WHERE assessment_id=%s",
                                              (assessment_id,)).fetchall()}
    base, label, n = base[:config.MAX_LABEL_CHARS - 6], base[:config.MAX_LABEL_CHARS - 6], 1
    while label in taken:
        n += 1
        label = f"{base} ({n})"
    return label


@router.post("/api/assessments/{assessment_id}/assign", status_code=201)
@limiter.limit("20/minute")
def assign(request: Request, assessment_id: int, body: dict = Body(...), user: dict = Depends(staff)):
    minutes = _time_limit(body.get("time_limit_minutes"))
    raw_class = body.get("class_id")
    class_id = None if raw_class in (None, "") else _int(raw_class)
    if raw_class not in (None, "") and class_id is None:
        raise Unprocessable("Please fix the highlighted fields.", {"class_id": "Choose a class from the list"})
    codes = clean_codes(body.get("student_ids") or [])
    try:
        with get_conn() as conn:
            if not conn.execute("SELECT 1 FROM assessments WHERE id=%s", (assessment_id,)).fetchone():
                raise NotFound("Assessment not found.")
            people, class_name = {}, None
            if class_id is not None:
                cls = owned_class(conn, user, class_id)
                class_name = cls["name"]
                for r in conn.execute("SELECT u.id, u.student_id FROM class_members m JOIN users u ON u.id=m.user_id "
                                      "WHERE m.class_id=%s AND u.status='active'", (class_id,)).fetchall():
                    people[r["id"]] = r
            for r in students_by_code(conn, codes):
                people[r["id"]] = r
            if not people:
                raise Unprocessable("Choose a class or at least one student.", {"students": "Nobody is selected"})
            count = conn.execute("SELECT count(*) AS n FROM submission_batches WHERE assessment_id=%s",
                                 (assessment_id,)).fetchone()["n"]
            if count >= config.MAX_BATCHES_PER_ASSESSMENT:
                raise Conflict(f"This assessment already has {config.MAX_BATCHES_PER_ASSESSMENT} batches, the maximum.")
            label = _label(conn, assessment_id, class_name or "Selected students")
            batch_id = conn.execute("INSERT INTO submission_batches (assessment_id, label) VALUES (%s,%s) RETURNING id",
                                    (assessment_id, label)).fetchone()["id"]
            aid = conn.execute(
                "INSERT INTO assignments (assessment_id, batch_id, class_id, assigned_by, time_limit_minutes) "
                "VALUES (%s,%s,%s,%s,%s) RETURNING id", (assessment_id, batch_id, class_id, user["id"], minutes)).fetchone()["id"]
            for uid in people:
                conn.execute("INSERT INTO assignment_students (assignment_id, user_id) VALUES (%s,%s)", (aid, uid))
    except psycopg.errors.UniqueViolation:
        raise Conflict("A batch with this name already exists for this assessment.", {"label": "Name already used"})
    return {"id": aid, "batch_id": batch_id, "label": label, "students": len(people)}


@router.get("/api/assignments")
def list_assignments(assessment_id: int | None = None, user: dict = Depends(staff)):
    where, args = ["true"], []
    if user["role"] != "superadmin":
        where.append("a.assigned_by=%s")
        args.append(user["id"])
    if assessment_id is not None:
        where.append("a.assessment_id=%s")
        args.append(assessment_id)
    with get_conn() as conn:
        return conn.execute(LIST_SQL.format(where=" AND ".join(where)), args).fetchall()


@router.delete("/api/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, user: dict = Depends(staff)):
    with get_conn() as conn:
        row = conn.execute("SELECT batch_id, assigned_by FROM assignments WHERE id=%s", (assignment_id,)).fetchone()
        if not row:
            raise NotFound("Assignment not found.")
        if user["role"] != "superadmin" and row["assigned_by"] != user["id"]:
            raise Forbidden("This assignment belongs to another lecturer.")
        if conn.execute("SELECT 1 FROM grading_runs WHERE batch_id=%s LIMIT 1", (row["batch_id"],)).fetchone():
            raise Conflict("Grading has started on this assignment, so it cannot be removed.")
        conn.execute("DELETE FROM submission_batches WHERE id=%s", (row["batch_id"],))
    return {"deleted": assignment_id}
