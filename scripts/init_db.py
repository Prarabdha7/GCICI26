"""Create the database schema.

    python -m scripts.init_db

Idempotent: existing tables are left alone. Works against SQLite or PostgreSQL
depending on DATABASE_URL.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.db.database import engine, init_db  # noqa: E402
from app.db.models import Base  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    log = logging.getLogger("init_db")

    log.info("Target: %s", settings.database_url)
    init_db()

    from sqlalchemy import inspect

    present = sorted(inspect(engine).get_table_names())
    expected = sorted(Base.metadata.tables)
    for table in expected:
        mark = "ok" if table in present else "MISSING"
        log.info("  [%s] %s", mark, table)

    missing = set(expected) - set(present)
    if missing:
        log.error("Tables failed to create: %s", ", ".join(sorted(missing)))
        return 1
    log.info("Schema ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
