"""Password reset requests. A lecturer handles students; the super admin handles lecturers too.
The one-time code is shown once to the person who issues it and only a hash is stored.

Owner: P2
"""
from fastapi import APIRouter, Depends

from .. import config
from ..auth import Forbidden, hash_password, new_reset_code, require
from ..db import get_conn
from ..errors import NotFound

router = APIRouter()
staff = require("lecturer", "superadmin")


def _open_request(conn, user, rid):
    row = conn.execute(
        "SELECT p.id, u.role, u.name FROM password_resets p JOIN users u ON u.id=p.user_id "
        "WHERE p.id=%s AND p.used_at IS NULL", (rid,)).fetchone()
    if not row:
        raise NotFound("Request not found.")
    if user["role"] != "superadmin" and row["role"] != "student":
        raise Forbidden("Only a super admin can reset a lecturer's password.")
    return row


@router.get("/api/resets")
def list_requests(user: dict = Depends(staff)):
    only_students = "" if user["role"] == "superadmin" else " AND u.role='student'"
    with get_conn() as conn:
        return conn.execute(
            "SELECT p.id, u.name, u.email, u.role, u.student_id, u.staff_id, p.requested_at, "
            "(p.code_hash IS NOT NULL AND p.expires_at > now()) AS issued "
            f"FROM password_resets p JOIN users u ON u.id=p.user_id WHERE p.used_at IS NULL{only_students} "
            "ORDER BY p.requested_at").fetchall()


@router.post("/api/resets/{rid}/issue")
def issue(rid: int, user: dict = Depends(staff)):
    code = new_reset_code()
    with get_conn() as conn:
        row = _open_request(conn, user, rid)
        conn.execute(
            "UPDATE password_resets SET code_hash=%s, expires_at=now() + make_interval(mins => %s), attempts=0, "
            "issued_by=%s WHERE id=%s", (hash_password(code), config.RESET_CODE_MINUTES, user["id"], rid))
    return {"code": code, "minutes": config.RESET_CODE_MINUTES, "name": row["name"]}


@router.post("/api/resets/{rid}/dismiss")
def dismiss(rid: int, user: dict = Depends(staff)):
    with get_conn() as conn:
        _open_request(conn, user, rid)
        conn.execute("UPDATE password_resets SET used_at=now(), code_hash=NULL WHERE id=%s", (rid,))
    return {"dismissed": rid}
