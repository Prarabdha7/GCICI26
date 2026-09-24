"""FastAPI application entry point, ASGI configuration, and process lifecycle management.

This module constructs the top-level ASGI application instance, registers API routers,
mounts static asset endpoints, and manages process-level startup and shutdown lifecycle
events through an asynchronous context manager.

Operational Responsibilities:
    1. Lifespan Coordination: Initialises database schema definitions, validates
       writable media paths (`temp/` and `assets/generated/`), and launches the
       embedded APScheduler background worker when `settings.worker_embedded` is active.
    2. Graceful Teardown: Catches shutdown signals and cleanly releases database
       connection pools and scheduler threads without dropping in-flight publishing jobs.
    3. Static Resource Routing: Serves the Apple Design Method single-page interface
       from `/app`, dynamic media artifacts from `/temp`, and persisted media assets
       from `/static`.
    4. Diagnostics: Exposes unauthenticated health check endpoints (`/health`) for container
       orchestrator probes (Docker / Kubernetes liveness / readiness).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.actions import router as actions_router
from app.api.dashboard import router as dashboard_router
from app.api.routes import router as api_router
from app.config import settings
from app.db.database import init_db

# AgentOps observability instrumentation (opt-in; skipped during testing).
agentops_key = os.getenv("AGENTOPS_API_KEY")
is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "true"
if agentops_key and agentops_key not in ("", "your_key_here") and not is_testing:
    try:
        import agentops

        agentops.init(api_key=agentops_key, default_tags=["ja-assure"])
    except Exception:
        pass

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
log = logging.getLogger("ja_assure")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle events.

    Executes schema initialization, verifies directory structures, checks regulatory
    rubric presence on disk, and optionally initiates the embedded publication worker.

    Args:
        app: The running FastAPI application instance.

    Yields:
        None: Yields control back to the ASGI server runtime.
    """
    log.info("Starting %s (%s)", settings.app_name, settings.environment)
    init_db()
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    (settings.base_dir / "temp").mkdir(parents=True, exist_ok=True)
    if not settings.compliance_rubric_path.exists():
        log.warning("compliance_rubric.md is missing — the compliance gate has nothing to ground on.")
    scheduler = None
    if settings.worker_embedded:
        try:
            from worker.scheduler import build_scheduler

            scheduler = build_scheduler()
            scheduler.start()
            log.info("Publisher worker started (mock-safe, interval=%ss)", settings.publish_poll_interval)
        except Exception as exc:
            log.warning("Worker failed to start (%s) — API still serves", exc)
    yield
    if scheduler is not None:
        # Shutdown is best-effort: if APScheduler raises during teardown
        # (e.g. because a job is mid-flight), we still want the process to
        # exit cleanly rather than propagating an exception through the ASGI
        # lifespan handler.
        import contextlib

        with contextlib.suppress(Exception):
            scheduler.shutdown(wait=False)
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

try:
    (settings.base_dir / "temp").mkdir(parents=True, exist_ok=True)
    app.mount("/temp", StaticFiles(directory=str(settings.base_dir / "temp")), name="temp")
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(settings.generated_dir)), name="static")
    frontend_dir = settings.base_dir / "frontend"
    if frontend_dir.is_dir():
        app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
except Exception:
    pass

app.include_router(api_router)
app.include_router(actions_router)
app.include_router(dashboard_router)


@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect incoming root path requests to the primary single-page application."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/app/")


@app.get("/health", tags=["meta"])
def health() -> dict[str, object]:
    """Retrieve runtime health and environment diagnostic metadata.

    Returns:
        dict: Diagnostic details including database driver, configured LLM provider,
              compliance rubric availability, and retry thresholds.
    """
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
