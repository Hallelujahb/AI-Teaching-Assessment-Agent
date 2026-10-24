"""Error types and the JSON bodies for 400, 404, 409, 413, 422, 429 and AI failures.

Every error body is short and never has a stack trace:
    {"error": "short message", "message": "short message", "fields": {"path": "message"}}
("message" repeats "error" so the frontend client can read either.)

Owner: P2 (P3 and P4 send tiny append-only PRs)
Plan: section 6
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("qeleme")


class AppError(Exception):
    status = 400

    def __init__(self, message: str, fields: dict | None = None, **extra):
        super().__init__(message)
        self.message = message
        self.fields = fields or {}
        self.extra = extra

    def body(self) -> dict:
        out = {"error": self.message, "message": self.message}
        if self.fields:
            out["fields"] = self.fields
        out.update({k: v for k, v in self.extra.items() if v is not None})
        return out


class BadRequest(AppError):
    status = 400


class NotFound(AppError):
    status = 404


class Conflict(AppError):
    status = 409


class PayloadTooLarge(AppError):
    status = 413


class Unprocessable(AppError):
    status = 422


class TooMany(AppError):
    status = 429


class NotReady(AppError):
    status = 503


AI_MESSAGES = {
    "timeout": "The AI service took too long. Your input is kept. Try again.",
    "quota": "The AI service is busy or its free quota is used up. Your input is kept. Try again in a minute.",
    "invalid_output": "The AI returned an answer that could not be used. Your input is kept. Try again.",
    "tool_limit": "The agent used too many steps and was stopped. Your input is kept. Try again.",
    "unavailable": "The AI service is not available right now (check the key and model settings). Your input is kept. Try again later.",
}
AI_STATUS = {"timeout": 504, "quota": 503, "invalid_output": 502, "tool_limit": 502, "unavailable": 503}


class AIError(AppError):
    """For P3: raise AIError("quota", run_id=run_id). kind is timeout, quota, invalid_output or tool_limit."""

    def __init__(self, kind: str, message: str | None = None, run_id=None):
        super().__init__(message or AI_MESSAGES.get(kind, "The AI step failed. Try again."),
                         kind=kind, run_id=str(run_id) if run_id else None)
        self.status = AI_STATUS.get(kind, 502)


def fields_from_errors(errors: list[dict]) -> dict:
    """Turn [{"field": "...", "message": "..."}] (from scoring.validate_review) into a dict."""
    out: dict[str, str] = {}
    for e in errors:
        key = str(e.get("field", "request"))
        msg = str(e.get("message", "Invalid value"))
        out[key] = f"{out[key]}; {msg}" if key in out else msg
    return out


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(exc.body(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = {}
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
            fields[".".join(loc) or "request"] = str(err.get("msg", "Invalid value"))
        msg = "The request is not valid."
        return JSONResponse({"error": msg, "message": msg, "fields": fields}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        msg = "Not found." if exc.status_code == 404 else "The request could not be completed."
        return JSONResponse({"error": msg, "message": msg}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)  # server log only
        msg = "Something went wrong on the server. Please try again."
        return JSONResponse({"error": msg, "message": msg}, status_code=500)
