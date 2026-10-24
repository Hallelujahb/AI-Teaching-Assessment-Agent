"""Database access through a connection pool.

Opening a fresh connection to a remote database costs several network round trips (TCP, TLS,
login). A pool opens connections once and reuses them, so each request pays only for its queries.
Same use as before:

    with get_conn() as conn:
        rows = conn.execute("SELECT ... WHERE id = %s", (value,)).fetchall()

Commits when the block ends normally, rolls back if it raises.

Owner: P2
"""
import threading
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool = None
_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                pool = ConnectionPool(
                    config.database_url(), min_size=1, max_size=6, open=False, timeout=30,
                    max_idle=240,                                   # drop idle links before the host does
                    check=ConnectionPool.check_connection,          # replace a dead link instead of failing
                    kwargs={"row_factory": dict_row, "connect_timeout": 15, "prepare_threshold": None})
                pool.open()
                _pool = pool
    return _pool


@contextmanager
def get_conn():
    with _get_pool().connection() as conn:
        yield conn