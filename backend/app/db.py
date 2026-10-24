"""Database connection and transaction helpers. Parameterised queries only (%s placeholders).

    with get_conn() as conn:
        rows = conn.execute("SELECT ... WHERE id = %s", (value,)).fetchall()

Commits when the block ends normally, rolls back if it raises. One connection per call,
with one retry because free databases sleep and the first connection can fail.

Owner: P2
Plan: sections 5 and 6
"""
import time
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from . import config


@contextmanager
def get_conn():
    conn = None
    for attempt in (1, 2):
        try:
            conn = psycopg.connect(config.database_url(), row_factory=dict_row, connect_timeout=15)
            break
        except psycopg.OperationalError:
            if attempt == 2:
                raise
            time.sleep(2)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
