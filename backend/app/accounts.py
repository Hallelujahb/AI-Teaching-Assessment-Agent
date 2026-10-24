"""Creating accounts with a system-issued id (never typed by hand).

Students get ST001, ST002 ... The next number skips every id already used by an account OR by a
submission, so a new student can never be handed an id that belongs to someone else's answers.
Lecturers get LT001, LT002 ...

    python -m app.accounts      gives an id to any lecturer account that has none

Owner: P2
"""
import psycopg

from .db import get_conn
from .errors import Conflict

PREFIX = {"student": ("ST", "student_id"), "lecturer": ("LT", "staff_id")}


def _next_number(conn, role: str) -> int:
    prefix, col = PREFIX[role]
    sql = f"SELECT substring({col} from 3)::int AS n FROM users WHERE {col} ~ '^{prefix}[0-9]+$'"
    if role == "student":
        sql += " UNION ALL SELECT substring(student_id from 3)::int FROM submissions WHERE student_id ~ '^ST[0-9]+$'"
    row = conn.execute(f"SELECT coalesce(max(n), 0) AS n FROM ({sql}) t").fetchone()
    return row["n"] + 1


def create_account(email: str, name: str, role: str, password_hash: str, status: str) -> dict:
    prefix, col = PREFIX[role]
    for _ in range(4):                                    # retry if two sign-ups drew the same number
        try:
            with get_conn() as conn:
                if conn.execute("SELECT 1 FROM users WHERE email=%s", (email,)).fetchone():
                    raise Conflict("An account with this email already exists.", {"email": "Already used"})
                code = f"{prefix}{_next_number(conn, role):03d}"
                return conn.execute(
                    f"INSERT INTO users (email, name, role, {col}, password_hash, status) VALUES (%s,%s,%s,%s,%s,%s) "
                    "RETURNING id, email, name, role, student_id, staff_id, status",
                    (email, name, role, code, password_hash, status)).fetchone()
        except psycopg.errors.UniqueViolation:
            continue
    raise Conflict("Could not issue an id. Please try again.")


def backfill() -> None:
    with get_conn() as conn:
        for r in conn.execute("SELECT id FROM users WHERE role='lecturer' AND staff_id IS NULL ORDER BY id").fetchall():
            conn.execute("UPDATE users SET staff_id=%s WHERE id=%s", (f"LT{_next_number(conn, 'lecturer'):03d}", r["id"]))
    print("Lecturer ids are in place.")


if __name__ == "__main__":
    backfill()