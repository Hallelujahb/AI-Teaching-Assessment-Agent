"""Super admin only: overview and user management.

Owner: P2
"""
import psycopg
from fastapi import APIRouter, Body, Depends

from ..auth import hash_password, public, require
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable

router = APIRouter(dependencies=[Depends(require("superadmin"))])


@router.get("/api/admin/overview")
def overview():
    with get_conn() as conn:
        one = lambda sql: conn.execute(sql).fetchone()["n"]  # noqa: E731
        return {
            "lecturers": one("SELECT count(*)::int AS n FROM users WHERE role='lecturer'"),
            "students": one("SELECT count(*)::int AS n FROM users WHERE role='student'"),
            "assessments": one("SELECT count(*)::int AS n FROM assessments"),
            "batches": one("SELECT count(*)::int AS n FROM submission_batches"),
            "runs": one("SELECT count(*)::int AS n FROM grading_runs"),
            "confirmed": one("SELECT count(DISTINCT s.batch_id)::int AS n FROM reviewed_results r JOIN submissions s ON s.id=r.submission_id"),
        }


@router.get("/api/admin/users")
def list_users():
    with get_conn() as conn:
        return conn.execute("SELECT id, email, name, role, student_id, status, created_at FROM users ORDER BY role, name").fetchall()


@router.post("/api/admin/users", status_code=201)
def add_user(body: dict = Body(...)):
    email = str(body.get("email") or "").strip().lower()
    name = str(body.get("name") or "").strip()
    role = body.get("role")
    password = str(body.get("password") or "")
    student_id = str(body.get("student_id") or "").strip() or None
    errors = {}
    if "@" not in email:
        errors["email"] = "Enter a valid email"
    if not name:
        errors["name"] = "Name is required"
    if role not in ("lecturer", "student"):
        errors["role"] = "Choose lecturer or student"
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters"
    if role == "student" and not student_id:
        errors["student_id"] = "Students need the student id used in their answers (for example ST001)"
    if errors:
        raise Unprocessable("The account is not valid.", errors)
    try:
        with get_conn() as conn:
            row = conn.execute(
                "INSERT INTO users (email, name, role, student_id, password_hash) VALUES (%s,%s,%s,%s,%s) "
                "RETURNING id, email, name, role, student_id",
                (email, name, role, student_id if role == "student" else None, hash_password(password))).fetchone()
    except psycopg.errors.UniqueViolation:
        raise Conflict("An account with this email already exists.", {"email": "Already used"})
    return public(row)


@router.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT role FROM users WHERE id=%s", (user_id,)).fetchone()
        if not row:
            raise NotFound("User not found.")
        if row["role"] == "superadmin":
            raise Conflict("The super admin account cannot be removed.")
        conn.execute("DELETE FROM users WHERE id=%s", (user_id,))
    return {"deleted": user_id}


@router.post("/api/admin/users/{user_id}/password")
def reset_password(user_id: int, body: dict = Body(...)):
    password = str(body.get("password") or "")
    if len(password) < 8:
        raise Unprocessable("The password is not valid.", {"password": "Use at least 8 characters"})
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET password_hash=%s WHERE id=%s AND role <> 'superadmin'", (hash_password(password), user_id))
        if cur.rowcount == 0:
            raise NotFound("User not found.")
    return {"updated": user_id}