"""Per-IP rate limits, the daily run cap and the request size limit.

main.py calls install_limits(app) once. Routes use @limiter.limit(...) and check_daily_cap().
In-memory rate limits reset when the host restarts (accepted in plan section 7).

Owner: P2
Plan: section 7
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from . import config
from .errors import TooMany


def client_ip(request: Request) -> str:
    """Behind the host's proxy the real address is the first value of X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip)


def check_daily_cap() -> None:
    """Refuse with a plain message once today's grading runs reach DAILY_RUN_CAP."""
    from .runs import count_runs_today
    if count_runs_today() >= config.daily_run_cap():
        raise TooMany("The daily limit for grading runs has been reached. Please try again tomorrow.")


def install_limits(app: FastAPI) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(request: Request, exc: RateLimitExceeded):
        msg = "Too many requests. Please wait a minute and try again."
        return JSONResponse({"error": msg, "message": msg}, status_code=429)

    @app.middleware("http")
    async def _body_size_limit(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > config.MAX_BODY_BYTES:
            msg = "The request is too large."
            return JSONResponse({"error": msg, "message": msg}, status_code=413)
        return await call_next(request)
