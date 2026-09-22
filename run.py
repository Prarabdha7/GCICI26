"""JA Assure Autonomous Multi-Agent Marketing System — Application Bootstrap.

This module provides the primary entrypoint for single-command service execution.
It initializes relational database schemas, validates environment configuration,
and binds the Uvicorn ASGI server to host the FastAPI application and embedded
background workers.

Usage:
    $ python run.py
"""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings  # noqa: E402
from app.db.database import init_db  # noqa: E402


def main() -> int:
    """Initialize system dependencies and start the HTTP server.

    Ensures SQLite/PostgreSQL schemas are created before listening on the configured
    host and port. Logs runtime operational mode (production vs demo fallback).

    Returns:
        int: Process exit status code (0 for clean termination).
    """
    import uvicorn

    init_db()
    print(f"JA Assure AI Marketing System — http://{settings.app_host}:{settings.app_port}/app")
    print(f"HTML dashboard (legacy): http://{settings.app_host}:{settings.app_port}/dashboard")
    if settings.demo_mode:
        print("DEMO_MODE=true: fallback/mock output enabled, all labeled DEMO (not real).")
    else:
        print("Real mode: add keys to .env for generation/publishing, or set DEMO_MODE=true for a labeled walkthrough.")
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
