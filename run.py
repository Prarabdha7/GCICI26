"""Single-command startup: python run.py — DB + API + worker (mock-safe, zero-key)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings  # noqa: E402
from app.db.database import init_db  # noqa: E402


def main() -> int:
    import uvicorn

    init_db()
    print(f"JA Assure AI Marketing System — http://{settings.app_host}:{settings.app_port}/dashboard")
    print("Zero-key demo mode: no GEMINI/BUFFER keys required (domain fallback + mock publisher).")
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
