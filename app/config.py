"""Configuration and Environment Settings Module.

This module provides strongly-typed configuration management for the JA Assure
AI Marketing System via Pydantic Settings. It centralizes all application variables,
database URLs, API credentials, model configurations, and runtime flags loaded from
local `.env` files or system environment variables.

Key Features:
    - Provider Switching: Dynamically switch between Google Gemini and OpenAI models.
    - Zero Quota Leaks: Configurable API timeouts and deterministic zero-temperature
      settings for statutory compliance evaluation.
    - Storage Independence: Supports SQLite for zero-setup local execution and PostgreSQL
      for high-throughput production persistence.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application-wide settings schema and environment parser.

    Attributes:
        app_name: Name of the application service.
        environment: Deployment environment identifier ('dev', 'demo', or 'prod').
        debug: Toggles verbose logging output.
        app_host: Network interface for HTTP listening.
        app_port: Network port for HTTP listening.
        database_url: Database connection string (SQLAlchemy format).
        llm_provider: Active LLM vendor ('gemini' or 'openai').
        gemini_api_key: Secret API key for Google Gemini services.
        gemini_model: Core generation model name.
        gemini_image_model: Image generation model name.
        gemini_video_model: Video generation model name.
        openai_api_key: Secret API key for OpenAI services.
        openai_model: Core generation model name for OpenAI fallback.
        llm_temperature: Default sampling temperature for creative agents.
        compliance_temperature: Deterministic sampling temperature (0.0) for regulatory audits.
        max_compliance_retries: Maximum automated self-healing iterations before routing to human review.
        feedback_memory_limit: Context window depth for historical human edit memory injection.
        demo_mode: Flag indicating whether synthetic mock fallback is permitted.
        publish_poll_interval: Scheduling frequency (in seconds) for publisher worker queues.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application Configuration
    app_name: str = "JA Assure AI Marketing System"
    environment: Literal["dev", "demo", "prod"] = "dev"
    debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # Persistence Layer
    database_url: str = f"sqlite:///{BASE_DIR / 'ja_assure.db'}"

    # LLM & Generative Media Engine Configuration
    llm_provider: Literal["gemini", "openai"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_image_model: str = "gemini-3.1-flash-image"
    gemini_video_model: str = "veo-3.1-fast-generate-preview"
    veo_poll_interval_seconds: float = 10.0
    veo_timeout_seconds: float = 300.0
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    compliance_temperature: float = 0.0

    # State Machine & Circuit Breakers
    max_compliance_retries: int = 3
    feedback_memory_limit: int = 5

    # Memory Systems & Knowledge Graphs
    obsidian_export_enabled: bool = False
    obsidian_vault_dir: str = ""
    excalidraw_export_enabled: bool = False
    memgpt_base_url: str = ""
    memgpt_agent_id: str = ""
    memgpt_timeout_seconds: float = 4.0

    # Operational Modes
    demo_mode: bool = False

    # Intelligence & Perception Engine Credentials
    serper_api_key: str = ""
    scrapegraph_api_key: str = ""
    google_places_api_key: str = ""
    hunter_api_key: str = ""

    # Stock Video Fallback Integration
    pexels_api_key: str = ""

    # Social Publishing Integrations
    buffer_access_token: str = ""
    ayrshare_api_key: str = ""
    public_media_base_url: str = ""
    publish_poll_interval: int = 60
    worker_embedded: bool = True

    @property
    def base_dir(self) -> Path:
        """Resolve the absolute root directory of the application repository."""
        return BASE_DIR

    @property
    def compliance_rubric_path(self) -> Path:
        """Resolve the filesystem path to the external statutory compliance rubric."""
        return BASE_DIR / "compliance_rubric.md"

    @property
    def video_assets_dir(self) -> Path:
        """Resolve the base path for static video templates and motion clips."""
        return BASE_DIR / "assets" / "video"

    @property
    def generated_dir(self) -> Path:
        """Resolve the directory used for persistent output media and rendered graphics."""
        return BASE_DIR / "assets" / "generated"

    @property
    def is_sqlite(self) -> bool:
        """Check whether the active database connection URI uses the SQLite engine."""
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retrieve the cached singleton application settings instance.

    Returns:
        Settings: The instantiated and validated settings object.
    """
    return Settings()


settings = get_settings()
