"""Create the super admin and demo accounts. Safe to run twice (existing emails are kept).
    python -m app.seed_users
Super admin email and password come from SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD (backend/.env).
Demo lecturer and student passwords below are for local demos only: change them on a public site.

Owner: P2
"""
import os
import sys

import psycopg
from dotenv import load_dotenv

from .auth import hash_password

load_dotenv()

DEMO = [
    ("lecturer@qeleme.test", "Demo Lecturer", "lecturer", None, "Lecturer#123"),
    ("st001@qeleme.test", "Student ST001", "student", "ST001", "Student#123"),
    ("st002@qeleme.test", "Student ST002", "student", "ST002", "Student#123"),
    ("py001@qeleme.test", "Student PY001", "student", "PY001", "Student#123"),
]


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    admin_email = os.environ.get("SUPERADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("SUPERADMIN_PASSWORD", "")
    if not url:
        sys.exit("DATABASE_URL is not set.")
    if not admin_email or len(admin_password) < 8 or "replace" in admin_password.lower():
        sys.exit("Set SUPERADMIN_EMAIL and a real SUPERADMIN_PASSWORD (8+ characters) in backend/.env first.")
    people = [(admin_email, "Super Admin", "superadmin", None, admin_password)] + DEMO
    added = 0
    with psycopg.connect(url) as conn:
        for email, name, role, student_id, password in people:
            cur = conn.execute(
                "INSERT INTO users (email, name, role, student_id, password_hash) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (email) DO NOTHING", (email, name, role, student_id, hash_password(password)))
            added += cur.rowcount
    print(f"Users added: {added}. Super admin: {admin_email}")


if __name__ == "__main__":
    main()