"""FastAPI entrypoint.

Serves the REST API and (from Phase 6) the human review dashboard.

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    if not settings.compliance_rubric_path.exists():
        log.warning("compliance_rubric.md is missing — the compliance gate has nothing to ground on.")
    yield
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

app.include_router(api_router)


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
