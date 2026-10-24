"""Sign in (with the chosen role), sign-up requests, and the signed-in user.

New lecturer and student accounts start as 'pending'. A super admin approves lecturers;
a lecturer or super admin approves students (see routes/approvals.py).

Owner: P2
"""
import psycopg
from fastapi import APIRouter, Body, Depends, Request

from ..auth import Forbidden, Unauthorized, check_password, current_user, hash_password, make_token, public
from ..db import get_conn
from ..errors import Conflict, Unprocessable
from ..limits import limiter

router = APIRouter()
WANT = {"student": "student", "lecturer": "lecturer", "admin": "superadmin"}
LABEL = {"student": "Student", "lecturer": "Lecturer", "superadmin": "Administrator"}


@router.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, body: dict = Body(...)):
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=%s", (email,)).fetchone()
    if not user or not check_password(password, user["password_hash"]):
        raise Unauthorized("Wrong email or password.")
    want = WANT.get(body.get("as"))
    if want and user["role"] != want:
        raise Forbidden(f"This account belongs under the {LABEL[user['role']]} option. Switch above and try again.")
    if user["status"] != "active":
        raise Forbidden("Your account is waiting for approval. You can sign in once it is approved.")
    return {"token": make_token(user["id"]), "user": public(user)}


@router.post("/api/auth/register", status_code=201)
@limiter.limit("5/minute")
def register(request: Request, body: dict = Body(...)):
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
    if role not in ("student", "lecturer"):
        errors["role"] = "Choose student or lecturer"
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters"
    if role == "student" and not student_id:
        errors["student_id"] = "Enter the student id used on your answers (for example ST001)"
    if errors:
        raise Unprocessable("Please fix the highlighted fields.", errors)
    try:
        with get_conn() as conn:
            if conn.execute("SELECT 1 FROM users WHERE email=%s", (email,)).fetchone():
                raise Conflict("An account with this email already exists.", {"email": "Already used"})
            if role == "student" and conn.execute("SELECT 1 FROM users WHERE role='student' AND student_id=%s", (student_id,)).fetchone():
                raise Conflict("This student id already has an account. If it is yours, ask your lecturer.", {"student_id": "Already has an account"})
            conn.execute(
                "INSERT INTO users (email, name, role, student_id, password_hash, status) VALUES (%s,%s,%s,%s,%s,'pending')",
                (email, name, role, student_id if role == "student" else None, hash_password(password)))
    except psycopg.errors.UniqueViolation:
        raise Conflict("An account with these details already exists.")
    who = "A super admin" if role == "lecturer" else "A lecturer"
    return {"status": "pending", "message": f"Request sent. {who} will review it before you can sign in."}


@router.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return public(user)