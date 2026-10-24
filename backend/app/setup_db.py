"""Applies schema.sql to the database in DATABASE_URL. Safe to run twice.

Owner: P2
Plan: section 8
"""
import os
import pathlib

import psycopg
from dotenv import load_dotenv

load_dotenv()

schema = (pathlib.Path(__file__).resolve().parent.parent / "schema.sql").read_text()

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    conn.execute(schema)

print("schema applied")
