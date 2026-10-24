"""FastAPI app: CORS from ALLOWED_ORIGINS, routers, error handlers, limits, role checks.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
Access control: lecturer and super admin reach grading, review and results routes.
Students reach only /api/me/results. Only the super admin reaches /api/admin/*.

Owner: P2
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .auth import require
from .errors import install_error_handlers
from .limits import install_limits
from .routes import admin, approvals, assessments, auth, batches, dashboard, grading, health, me, results, review, runs

app = FastAPI(title="Qeleme API")

install_error_handlers(app)
install_limits(app)

# Added last so it is the outermost layer and also covers error responses (401, 413, 429, ...).
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)

staff = [Depends(require("lecturer", "superadmin"))]
for module in (assessments, batches, grading, runs, review, results, dashboard, approvals):
    app.include_router(module.router, dependencies=staff)
for module in (health, auth, me, admin):
    app.include_router(module.router)


@app.get("/")
def root():
    return {"name": "Qeleme API", "docs": "/docs", "health": "/api/health"}