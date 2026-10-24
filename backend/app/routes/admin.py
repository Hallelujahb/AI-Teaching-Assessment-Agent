"""Super admin only: list accounts, add one (the id is issued by the system), reset a password, remove one.

Owner: P2
"""
from fastapi import APIRouter, Body, Depends

from ..accounts import create_account
from ..auth import forget, hash_password, public, require
from ..db import get_conn
from ..errors import Conflict, NotFound, Unprocessable

router = APIRouter(dependencies=[Depends(require("superadmin"))])


@router.get("/api/admin/users")
def list_users():
    with get_conn() as conn:
        return conn.execute("SELECT id, email, name, role, student_id, staff_id, status, created_at FROM users ORDER BY role, name").fetchall()


@router.post("/api/admin/users", status_code=201)
def add_user(body: dict = Body(...)):
    email = str(body.get("email") or "").strip().lower()
    name = str(body.get("name") or "").strip()
    role = body.get("role")
    password = str(body.get("password") or "")
    errors = {}
    if "@" not in email:
        errors["email"] = "Enter a valid email"
    if not name:
        errors["name"] = "Name is required"
    if role not in ("lecturer", "student"):
        errors["role"] = "Choose lecturer or student"
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters"
    if errors:
        raise Unprocessable("The account is not valid.", errors)
    row = create_account(email, name, role, hash_password(password), "active")
    return {**public(row), "issued_id": row["student_id"] or row["staff_id"]}


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


@router.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT role FROM users WHERE id=%s", (user_id,)).fetchone()
        if not row:
            raise NotFound("User not found.")
        if row["role"] == "superadmin":
            raise Conflict("The super admin account cannot be removed.")
        conn.execute("DELETE FROM users WHERE id=%s", (user_id,))
    forget(user_id)
    return {"deleted": user_id}