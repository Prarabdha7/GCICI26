"""Unit tests for the Studio API endpoints and media test bench."""

from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.media.image_gen import generate_image, generate_procedural_image


def test_studio_models_endpoint() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/studio/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "image_model" in data
        assert "video_model" in data
        assert "gemini-3.1-flash-image" in data["available_image_models"]
        assert any(s["id"] == "veo" for s in data["available_video_strategies"])
        assert any(s["id"] == "broll" for s in data["available_video_strategies"])


def test_studio_image_generation_procedural_fallback(tmp_path: Path) -> None:
    path = generate_procedural_image("Exclusive vault cover", brand="Jade", output_path=tmp_path / "test.png")
    assert path.exists()
    assert path.stat().st_size > 1000
    assert path.suffix == ".png"


def test_studio_image_api_endpoint(monkeypatch, tmp_path: Path) -> None:
    # Ensure offline safety: generate_image returns a valid PNG
    with TestClient(app) as client:
        resp = client.post(
            "/api/studio/image",
            json={"prompt": "Vault gold coin", "brand": "Jade", "model": "gemini-3.1-flash-image"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["image_url"].startswith("/temp/")


def test_studio_reel_api_endpoint(monkeypatch, tmp_path: Path) -> None:
    from app.media import assembly

    monkeypatch.setattr(assembly, "REEL_FPS", 4)
    with TestClient(app) as client:
        resp = client.post(
            "/api/studio/reel",
            json={
                "script": "Jade Jewellers Block. Terms apply.",
                "brand": "Jade",
                "language": "en",
                "strategy": "kenburns",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["video_url"].startswith("/temp/")
        assert data["srt_url"].startswith("/temp/")
