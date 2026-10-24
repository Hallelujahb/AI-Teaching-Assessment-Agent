"""Applies schema.sql to the database in DATABASE_URL. Safe to run twice.

Command line only:
    python -m app.setup_db            create tables if missing
    python -m app.setup_db --drop     delete ALL tables first (asks you to type yes)

Owner: P2
Plan: section 8
"""
import os
import pathlib
import sys

import psycopg
from dotenv import load_dotenv

load_dotenv()

TABLES = ["password_resets", "assignment_students", "assignments", "class_members", "classes", "users", "reviewed_results", "ai_proposals", "tool_logs", "grading_runs",
          "submissions", "submission_batches", "rubric_criteria", "assessments"]


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set.")
    schema = (pathlib.Path(__file__).resolve().parent.parent / "schema.sql").read_text(encoding="utf-8")
    with psycopg.connect(url) as conn:
        if "--drop" in sys.argv:
            if input("This deletes every Qeleme table in this database. Type yes to continue: ").strip() != "yes":
                sys.exit("Cancelled.")
            for table in TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
            print("tables dropped")
        conn.execute(schema)
    print("schema applied")


if __name__ == "__main__":
    main()
