"""Classes: a lecturer groups students under a name so an exam can be assigned to the group.
A lecturer manages their own classes; the super admin can manage all of them.
A class holds at most MAX_ANSWERS_PER_BATCH students, because one assignment becomes one grading batch.

Owner: P2
"""
import psycopg
from fastapi import APIRouter, Body, Depends, Request

from .. import config
from ..auth import Forbidden, require
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable
from ..limits import limiter

router = APIRouter()
staff = require("lecturer", "superadmin")

LIST_SQL = """
SELECT c.id, c.name, c.owner_id, o.name AS owner_name,
  coalesce(json_agg(json_build_object('student_id', s.student_id, 'name', s.name) ORDER BY s.student_id)
           FILTER (WHERE s.id IS NOT NULL), '[]'::json) AS students
FROM classes c JOIN users o ON o.id=c.owner_id
LEFT JOIN class_members m ON m.class_id=c.id LEFT JOIN users s ON s.id=m.user_id
{where} GROUP BY c.id, o.name ORDER BY lower(c.name)
"""


def owned_class(conn, user: dict, class_id: int) -> dict:
    row = conn.execute("SELECT id, name, owner_id FROM classes WHERE id=%s", (class_id,)).fetchone()
    if not row:
        raise NotFound("Class not found.")
    if user["role"] != "superadmin" and row["owner_id"] != user["id"]:
        raise Forbidden("This class belongs to another lecturer.")
    return row


def students_by_code(conn, codes: list[str]) -> list[dict]:
    """Active students for the given student ids. Unknown ids raise a 422."""
    rows = conn.execute("SELECT id, student_id FROM users WHERE role='student' AND status='active' "
                        "AND student_id = ANY(%s)", (codes,)).fetchall()
    missing = sorted(set(codes) - {r["student_id"] for r in rows})
    if missing:
        raise Unprocessable("Some students were not found.", {"student_ids": "Unknown: " + ", ".join(missing)})
    return rows


def clean_codes(value) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise Unprocessable("Choose students from the list.", {"student_ids": "Choose students from the list"})
    return list(dict.fromkeys(v.strip() for v in value if v.strip()))


def _clean(conn, body: dict) -> tuple[str, list[dict]]:
    errors = {}
    name = str(body.get("name") or "").strip()
    if not name or len(name) > config.MAX_CLASS_NAME_CHARS:
        errors["name"] = f"Enter a class name of up to {config.MAX_CLASS_NAME_CHARS} characters"
    codes = clean_codes(body.get("student_ids"))
    if not codes:
        errors["student_ids"] = "Choose at least one student"
    if errors:
        raise Unprocessable("Please fix the highlighted fields.", errors)
    return name, students_by_code(conn, codes)


def _set_members(conn, class_id: int, students: list[dict]) -> None:
    conn.execute("DELETE FROM class_members WHERE class_id=%s", (class_id,))
    for s in students:
        conn.execute("INSERT INTO class_members (class_id, user_id) VALUES (%s,%s)", (class_id, s["id"]))


@router.get("/api/classes")
def list_classes(user: dict = Depends(staff)):
    with get_conn() as conn:
        if user["role"] == "superadmin":
            return conn.execute(LIST_SQL.format(where="")).fetchall()
        return conn.execute(LIST_SQL.format(where="WHERE c.owner_id=%s"), (user["id"],)).fetchall()


@router.post("/api/classes", status_code=201)
@limiter.limit("20/minute")
def create_class(request: Request, body: dict = Body(...), user: dict = Depends(staff)):
    try:
        with get_conn() as conn:
            name, students = _clean(conn, body)
            cid = conn.execute("INSERT INTO classes (owner_id, name) VALUES (%s,%s) RETURNING id",
                               (user["id"], name)).fetchone()["id"]
            _set_members(conn, cid, students)
    except psycopg.errors.UniqueViolation:
        raise Conflict("You already have a class with this name.", {"name": "Already used"})
    return {"id": cid}


@router.put("/api/classes/{class_id}")
@limiter.limit("20/minute")
def update_class(request: Request, class_id: int, body: dict = Body(...), user: dict = Depends(staff)):
    try:
        with get_conn() as conn:
            owned_class(conn, user, class_id)
            name, students = _clean(conn, body)
            conn.execute("UPDATE classes SET name=%s WHERE id=%s", (name, class_id))
            _set_members(conn, class_id, students)
    except psycopg.errors.UniqueViolation:
        raise Conflict("You already have a class with this name.", {"name": "Already used"})
    return {"id": class_id}


@router.delete("/api/classes/{class_id}")
def delete_class(class_id: int, user: dict = Depends(staff)):
    with get_conn() as conn:
        owned_class(conn, user, class_id)
        conn.execute("DELETE FROM classes WHERE id=%s", (class_id,))
    return {"deleted": class_id}
