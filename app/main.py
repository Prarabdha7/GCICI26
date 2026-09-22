"""FastAPI entrypoint.

Serves the REST API and (from Phase 6) the human review dashboard.

    uvicorn app.main:app --reload
    python run.py
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.dashboard import router as dashboard_router
from app.api.routes import router as api_router
from app.config import settings
from app.db.database import init_db

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
log = logging.getLogger("ja_assure")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting %s (%s)", settings.app_name, settings.environment)
    init_db()
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    (settings.base_dir / "temp").mkdir(parents=True, exist_ok=True)
    if not settings.compliance_rubric_path.exists():
        log.warning("compliance_rubric.md is missing — the compliance gate has nothing to ground on.")
    scheduler = None
    try:
        from worker.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
        log.info("Publisher worker started (mock-safe, interval=%ss)", settings.publish_poll_interval)
    except Exception as exc:
        log.warning("Worker failed to start (%s) — API still serves", exc)
    yield
    if scheduler is not None:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
    log.info("Shutting down.")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Multi-agent marketing system for JA Assure. A LangGraph state machine "
        "researches, writes, localises and compliance-gates every asset, a human "
        "approves it, and the approved queue is published automatically."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Serve generated reels/captions at /temp/* (mounted at import so TestClient sees it).
try:
    (settings.base_dir / "temp").mkdir(parents=True, exist_ok=True)
    app.mount("/temp", StaticFiles(directory=str(settings.base_dir / "temp")), name="temp")
except Exception:
    pass

app.include_router(api_router)
app.include_router(dashboard_router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, object]:
    """Liveness probe. Also reports which provider and database are wired up."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "llm_provider": settings.llm_provider,
        "llm_configured": bool(
            settings.gemini_api_key if settings.llm_provider == "gemini" else settings.openai_api_key
        ),
        "rubric_loaded": settings.compliance_rubric_path.exists(),
        "max_compliance_retries": settings.max_compliance_retries,
    }
