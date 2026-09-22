"""Phase 8 tests: optional Obsidian/Excalidraw and MemGPT integrations."""

from __future__ import annotations

import httpx

from app.config import settings
from app.integrations.memgpt import augment_guidance_with_memgpt
from app.integrations.obsidian import export_execution_to_obsidian


def test_memgpt_augmentation_is_noop_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "memgpt_base_url", "")
    monkeypatch.setattr(settings, "memgpt_agent_id", "")
    assert augment_guidance_with_memgpt(brand="Jade", platform="linkedin", local_guidance="local note") == "local note"


def test_memgpt_augmentation_appends_remote_guidance(monkeypatch) -> None:
    monkeypatch.setattr(settings, "memgpt_base_url", "http://memgpt.local")
    monkeypatch.setattr(settings, "memgpt_agent_id", "agent-123")
    monkeypatch.setattr(settings, "memgpt_timeout_seconds", 2.0)

    def fake_post(url, json, timeout):
        return httpx.Response(
            200,
            json={"messages": [{"role": "assistant", "content": "Use claim-safe language."}]},
            request=httpx.Request("POST", url),
        )

    import app.integrations.memgpt as memgpt_module

    monkeypatch.setattr(memgpt_module.httpx, "post", fake_post)

    out = augment_guidance_with_memgpt(brand="Jade", platform="linkedin", local_guidance="local note")

    assert "local note" in out
    assert "Use claim-safe language." in out


def test_obsidian_export_writes_note_and_excalidraw(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "obsidian_export_enabled", True)
    monkeypatch.setattr(settings, "obsidian_vault_dir", str(tmp_path))
    monkeypatch.setattr(settings, "excalidraw_export_enabled", True)

    export_execution_to_obsidian(
        state={
            "brand": "Jade",
            "platform": "linkedin",
            "content_id": 42,
            "status": "pending",
            "retry_count": 1,
            "content_type": "post",
        },
        thread_id="thread-abc",
    )

    out_dir = tmp_path / "JA-Assure-Runs"
    files = list(out_dir.iterdir())
    assert any(f.suffix == ".md" for f in files)
    assert any(f.suffix == ".excalidraw" for f in files)
