"""Phase 1 smoke tests.

Deliberately dependency-light: these cover configuration, the compliance-gate
schema contract and the API response models, and run without a database or a
network connection.

    pytest tests/test_phase1.py -v
"""

from __future__ import annotations

import pytest

from app.api.schemas import ContentQueueOut, FeedbackMemoryOut, QueueStats
from app.config import Settings
from app.llm.client import COMPLIANCE_SCHEMA, LLMError, structured_call


@pytest.fixture
def settings() -> Settings:
    """Settings with no .env, so we assert on documented defaults."""
    return Settings(_env_file=None)


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def test_defaults_are_zero_setup(settings: Settings) -> None:
    assert settings.is_sqlite, "development must work with no database install"


def test_circuit_breaker_and_memory_defaults(settings: Settings) -> None:
    assert settings.max_compliance_retries == 3
    assert settings.feedback_memory_limit == 5


def test_compliance_judge_is_deterministic(settings: Settings) -> None:
    """Creativity is a defect in a compliance check."""
    assert settings.compliance_temperature == 0.0
    assert settings.llm_temperature > 0.0


def test_no_secrets_are_baked_into_code(settings: Settings) -> None:
    assert settings.gemini_api_key == ""
    assert settings.openai_api_key == ""
    assert settings.buffer_access_token == ""
    assert settings.ayrshare_api_key == ""


def test_rubric_is_loaded_from_disk(settings: Settings) -> None:
    assert settings.compliance_rubric_path.name == "compliance_rubric.md"
    assert settings.compliance_rubric_path.exists(), "the gate has nothing to ground on"


@pytest.mark.parametrize(
    "env_var,value,attr,expected",
    [
        ("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/ja", "is_sqlite", False),
        ("MAX_COMPLIANCE_RETRIES", "7", "max_compliance_retries", 7),
        ("LLM_PROVIDER", "openai", "llm_provider", "openai"),
    ],
)
def test_environment_overrides_apply(monkeypatch, env_var, value, attr, expected) -> None:
    """Swapping SQLite for PostgreSQL must be a one-variable change."""
    monkeypatch.setenv(env_var, value)
    assert getattr(Settings(_env_file=None), attr) == expected


# --------------------------------------------------------------------------- #
# Compliance gate contract
# --------------------------------------------------------------------------- #


def test_compliance_schema_is_exact() -> None:
    """The gate must return {"is_compliant": boolean, "violations": ["string"]}."""
    props = COMPLIANCE_SCHEMA["properties"]
    assert set(props) == {"is_compliant", "violations"}
    assert props["is_compliant"]["type"] == "boolean"
    assert props["violations"]["type"] == "array"
    assert props["violations"]["items"]["type"] == "string"
    assert set(COMPLIANCE_SCHEMA["required"]) == {"is_compliant", "violations"}


def test_llm_client_fails_closed_without_a_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")
    with pytest.raises(LLMError):
        structured_call(system="s", user="u", schema=COMPLIANCE_SCHEMA)


def test_llm_client_rejects_unknown_provider() -> None:
    with pytest.raises(LLMError):
        structured_call(system="s", user="u", schema=COMPLIANCE_SCHEMA, provider="bogus")


# --------------------------------------------------------------------------- #
# API contracts
# --------------------------------------------------------------------------- #


def test_content_queue_carries_state_machine_fields() -> None:
    row = ContentQueueOut(
        id=1,
        brand="Jade",
        platform="linkedin",
        language="ms",
        content_type="post",
        draft_content="draft",
        status="pending",
        retry_count=2,
        compliance_errors=["Uses 'guaranteed' about payouts (Rubric 2.1)"],
    )
    assert row.retry_count == 2
    assert len(row.compliance_errors) == 1


def test_feedback_memory_shape() -> None:
    entry = FeedbackMemoryOut(
        id=1,
        brand="Jade",
        platform="linkedin",
        error_tag="too_salesy",
        human_note="Reads like a pitch, not an insight.",
    )
    assert entry.error_tag == "too_salesy"


def test_queue_stats_exposes_rejection_rate() -> None:
    stats = QueueStats(
        total=10,
        by_status={"approved": 6, "rejected": 4},
        feedback_entries=4,
        leads=0,
        rejection_rate=0.4,
    )
    assert stats.rejection_rate == 0.4
