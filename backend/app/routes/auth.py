"""Sign in (with the chosen role), sign-up requests, and the signed-in user.

New lecturer and student accounts start as 'pending' and are issued an id at once.
A super admin approves lecturers; a lecturer or super admin approves students.

Owner: P2
"""
from fastapi import APIRouter, Body, Depends, Request

from ..accounts import create_account
from ..auth import Forbidden, Unauthorized, check_password, current_user, hash_password, make_token, public
from ..db import get_conn
from ..errors import Unprocessable
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
    errors = {}
    if "@" not in email:
        errors["email"] = "Enter a valid email"
    if not name:
        errors["name"] = "Name is required"
    if role not in ("student", "lecturer"):
        errors["role"] = "Choose student or lecturer"
    if len(password) < 8:
        errors["password"] = "Use at least 8 characters"
    if errors:
        raise Unprocessable("Please fix the highlighted fields.", errors)
    create_account(email, name, role, hash_password(password), "pending")
    who = "A super admin" if role == "lecturer" else "A lecturer"
    return {"status": "pending", "message": f"Request sent. {who} will review it. Your id is issued when you are approved and signed in."}


@router.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return public(user)