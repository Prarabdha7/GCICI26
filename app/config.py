"""Environment-driven settings.

Every secret, URL and tuning knob lives here and is read from the environment.
Nothing in this project may hardcode a key, a connection string or a brand rule.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- application ---
    app_name: str = "JA Assure AI Marketing System"
    environment: Literal["dev", "demo", "prod"] = "dev"
    debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # --- database ---
    # SQLite in development, PostgreSQL for the demo. One variable, no code change.
    database_url: str = f"sqlite:///{BASE_DIR / 'ja_assure.db'}"

    # --- LLM ---
    llm_provider: Literal["gemini", "openai"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    # The compliance judge is always deterministic. Creativity is a defect there.
    compliance_temperature: float = 0.0

    # --- state machine ---
    max_compliance_retries: int = 3
    feedback_memory_limit: int = 5

    # --- optional memory/visual integrations ---
    obsidian_export_enabled: bool = False
    obsidian_vault_dir: str = ""
    excalidraw_export_enabled: bool = False
    memgpt_base_url: str = ""
    memgpt_agent_id: str = ""
    memgpt_timeout_seconds: float = 4.0

    # --- demo mode ---------------------------------------------------------
    # Demo writes (fallback copy, mock providers/publisher, stub reels, seed
    # rows) are allowed ONLY when DEMO_MODE=true, and are always labeled
    # demo/mock in the DB and UI. Default false = real-only, honest failures.
    demo_mode: bool = False
    # Machine-local sample content backing the demo path (gitignored; see
    # local/samples.example.json). Relative paths resolve against BASE_DIR.
    local_samples_path: str = "local/demo_samples.json"

    # --- research / scraping (Phase 5) ---
    serper_api_key: str = ""
    scrapegraph_api_key: str = ""
    google_places_api_key: str = ""
    hunter_api_key: str = ""

    # --- publishing (Phase 7) ---
    buffer_access_token: str = ""
    ayrshare_api_key: str = ""
    public_media_base_url: str = ""
    publish_poll_interval: int = 60
    # Embedded worker serves `python run.py`; standalone `python -m
    # worker.scheduler` (run_demo.sh) sets WORKER_EMBEDDED=false so two
    # schedulers never poll the approved queue at once.
    worker_embedded: bool = True

    # --- paths ---
    @property
    def base_dir(self) -> Path:
        return BASE_DIR

    @property
    def compliance_rubric_path(self) -> Path:
        """The gate loads its rules from disk at runtime, never from code."""
        return BASE_DIR / "compliance_rubric.md"

    @property
    def video_assets_dir(self) -> Path:
        return BASE_DIR / "assets" / "video"

    @property
    def generated_dir(self) -> Path:
        return BASE_DIR / "assets" / "generated"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
