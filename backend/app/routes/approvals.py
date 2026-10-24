"""Pending sign-ups. Super admin approves lecturers and students; a lecturer approves students only.

Owner: P2
"""
from fastapi import APIRouter, Depends

from ..auth import Forbidden, require
from ..db import get_conn
from ..errors import Conflict, NotFound

router = APIRouter()
staff = require("lecturer", "superadmin")


@router.get("/api/approvals")
def list_pending(user: dict = Depends(staff)):
    only_students = "" if user["role"] == "superadmin" else " AND u.role='student'"
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.id, u.name, u.email, u.role, u.student_id, u.staff_id, u.created_at, "
            "EXISTS (SELECT 1 FROM submissions s WHERE s.student_id=u.student_id) AS has_answers "
            f"FROM users u WHERE u.status='pending'{only_students} ORDER BY u.created_at").fetchall()


def _pending(conn, user, uid):
    row = conn.execute("SELECT id, role, status FROM users WHERE id=%s", (uid,)).fetchone()
    if not row:
        raise NotFound("Request not found.")
    if user["role"] != "superadmin" and row["role"] != "student":
        raise Forbidden("Only a super admin can approve a lecturer.")
    if row["status"] != "pending":
        raise Conflict("This request was already handled.")


@router.post("/api/approvals/{uid}/approve")
def approve(uid: int, user: dict = Depends(staff)):
    with get_conn() as conn:
        _pending(conn, user, uid)
        conn.execute("UPDATE users SET status='active' WHERE id=%s", (uid,))
    return {"approved": uid}


@router.post("/api/approvals/{uid}/reject")
def reject(uid: int, user: dict = Depends(staff)):
    with get_conn() as conn:
        _pending(conn, user, uid)
        conn.execute("DELETE FROM users WHERE id=%s", (uid,))
    return {"rejected": uid}