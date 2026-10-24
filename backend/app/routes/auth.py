"""Sign in (with the chosen role), sign-up requests, forgotten passwords, and the signed-in user.

New lecturer and student accounts start as 'pending' and are issued an id at once.
A super admin approves lecturers; a lecturer or super admin approves students.

Owner: P2
"""
from fastapi import APIRouter, Body, Depends, Request

from .. import config
from ..accounts import create_account
from ..auth import (Forbidden, Unauthorized, check_password, current_user, find_user, forget, hash_password,
                    make_token, public)
from ..db import get_conn
from ..errors import Unprocessable
from ..limits import limiter

router = APIRouter()
WANT = {"student": "student", "lecturer": "lecturer", "admin": "superadmin"}
LABEL = {"student": "Student", "lecturer": "Lecturer", "superadmin": "Administrator"}


@router.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, body: dict = Body(...)):
    identifier = str(body.get("identifier") or body.get("email") or "")
    password = str(body.get("password") or "")
    with get_conn() as conn:
        user = find_user(conn, identifier)
    if not user or not check_password(password, user["password_hash"]):
        raise Unauthorized("Wrong email, ID or password.")
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



FORGOT_MESSAGE = ("If that account exists, your request is now waiting. A lecturer gives students a one-time code, "
                  "and a super admin gives lecturers one. Ask for it, then choose 'I have a code'.")


@router.post("/api/auth/forgot")
@limiter.limit("5/minute")
def forgot(request: Request, body: dict = Body(...)):
    identifier = str(body.get("identifier") or "").strip()
    if not identifier:
        raise Unprocessable("Enter your email, student id or staff id.", {"identifier": "Required"})
    with get_conn() as conn:
        user = find_user(conn, identifier)
        if user and user["status"] == "active" and user["role"] != "superadmin":
            conn.execute(
                "INSERT INTO password_resets (user_id) VALUES (%s) ON CONFLICT (user_id) WHERE used_at IS NULL "
                "DO UPDATE SET requested_at=now(), code_hash=NULL, expires_at=NULL, attempts=0, issued_by=NULL",
                (user["id"],))
    return {"message": FORGOT_MESSAGE}


@router.post("/api/auth/reset")
@limiter.limit("10/minute")
def reset(request: Request, body: dict = Body(...)):
    identifier = str(body.get("identifier") or "")
    code = str(body.get("code") or "").strip()
    password = str(body.get("password") or "")
    if len(password) < 8:
        raise Unprocessable("The password is not valid.", {"password": "Use at least 8 characters"})
    ok = False
    with get_conn() as conn:
        user = find_user(conn, identifier)
        row = user and conn.execute(
            "SELECT id, code_hash FROM password_resets WHERE user_id=%s AND used_at IS NULL "
            "AND code_hash IS NOT NULL AND expires_at > now()", (user["id"],)).fetchone()
        if row and check_password(code, row["code_hash"]):
            ok = True
            conn.execute("UPDATE users SET password_hash=%s WHERE id=%s", (hash_password(password), user["id"]))
            conn.execute("UPDATE password_resets SET used_at=now(), code_hash=NULL WHERE id=%s", (row["id"],))
        elif row:
            conn.execute(
                "UPDATE password_resets SET attempts=attempts+1, "
                "code_hash=CASE WHEN attempts+1 >= %s THEN NULL ELSE code_hash END WHERE id=%s",
                (config.RESET_MAX_ATTEMPTS, row["id"]))
    if not ok:
        raise Unauthorized("That code is not valid or has expired. Ask for a new one.")
    forget(user["id"])
    return {"message": "Your password was changed. You can sign in now."}
