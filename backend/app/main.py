"""FastAPI app: CORS from ALLOWED_ORIGINS, routers, error handlers, limits, role checks.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
Access control: lecturer and super admin reach grading, review and results routes.
Students reach only /api/me/* (their results and the exams assigned to them). Only the super admin reaches /api/admin/*.

Owner: P2
"""
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .auth import Forbidden, require
from .errors import install_error_handlers
from .limits import install_limits
from .routes import (admin, approvals, assessments, assignments, auth, batches, classes, dashboard, exams, grading, health,
                     me, resets, results, review, runs)

app = FastAPI(title="Qeleme API")

install_error_handlers(app)
install_limits(app)

# Added last so it is the outermost layer and also covers error responses (401, 413, 429, ...).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",   # any local dev port
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

staff = [Depends(require("lecturer", "superadmin"))]


def lecturer_writes(request: Request, user: dict = Depends(require("lecturer", "superadmin"))) -> None:
    """The super admin oversees: reading is allowed, changing assessments, answers, grading, classes is not."""
    if user["role"] == "superadmin" and request.method not in ("GET", "HEAD", "OPTIONS"):
        raise Forbidden("The super admin oversees the platform. Lecturers create assessments, grade and manage classes.")


# Routes lecturers own (reads stay open to the super admin).
for module in (assessments, batches, grading, review, classes, assignments):
    app.include_router(module.router, dependencies=[Depends(lecturer_writes)])
# Shared with the super admin: reading runs and results, approving sign-ups, issuing reset codes.
for module in (runs, results, dashboard, approvals, resets):
    app.include_router(module.router, dependencies=staff)
for module in (health, auth, me, exams, admin):
    app.include_router(module.router)


@app.get("/")
def root():
    return {"name": "Qeleme API", "docs": "/docs", "health": "/api/health"}
