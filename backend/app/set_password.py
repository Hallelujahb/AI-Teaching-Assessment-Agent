"""Set a new password for any account from the command line. Use it when the super admin password is lost.
    python -m app.set_password admin@qeleme.test        (email, student id or staff id)
Asks twice and never prints the password. Reads DATABASE_URL from the environment or backend/.env.

Owner: P2
"""
import getpass
import os
import sys

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from .auth import find_user, hash_password

load_dotenv()


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url or len(sys.argv) != 2:
        sys.exit("Usage: python -m app.set_password EMAIL_OR_ID   (DATABASE_URL must be set)")
    password = getpass.getpass("New password (8+ characters): ")
    if len(password) < 8 or password != getpass.getpass("Again: "):
        sys.exit("Passwords did not match or were shorter than 8 characters.")
    with psycopg.connect(url, row_factory=dict_row) as conn:
        user = find_user(conn, sys.argv[1])
        if not user:
            sys.exit("No account found.")
        conn.execute("UPDATE users SET password_hash=%s WHERE id=%s", (hash_password(password), user["id"]))
    print(f"Password updated for {user['email']}.")


if __name__ == "__main__":
    main()
