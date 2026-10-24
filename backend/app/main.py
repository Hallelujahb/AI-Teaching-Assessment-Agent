"""FastAPI app: CORS from ALLOWED_ORIGINS, routers, error handlers, limits.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
Only P2 edits this file. limits.py exposes one function (install_limits) that is called here.
routes/export.py is added after Gate 3 if there is time.

Owner: P2
Plan: sections 7 and 8
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .errors import install_error_handlers
from .limits import install_limits
from .routes import assessments, batches, grading, health, results, review, runs

app = FastAPI(title="Qeleme API")

install_error_handlers(app)
install_limits(app)

# Added last so it is the outermost layer and also covers error responses (413, 429, ...).
# Exact origins only, no wildcard, no cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)

for module in (health, assessments, batches, grading, runs, review, results):
    app.include_router(module.router)


@app.get("/")
def root():
    return {"name": "Qeleme API", "docs": "/docs", "health": "/api/health"}
