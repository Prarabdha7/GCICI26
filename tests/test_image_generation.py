"""Tests for Gemini/Imagen image generation: app/media/image_gen.py,
app/graph/nodes.py::image_generation_node, routing, and the carousel
per-slide image path in persist_node.

image_call is monkeypatched everywhere — no network calls, no real SDK use.
The autouse `_no_real_keys` fixture (tests/conftest.py) also blanks
GEMINI_API_KEY, so any accidental un-mocked call fails closed with LLMError
instead of reaching the network.

    pytest tests/test_image_generation.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents import formats as formats_module
from app.db.database import session_scope
from app.db.models import ContentQueue
from app.graph import nodes as nodes_module
from app.graph.graph import route_after_localization
from app.media import image_gen


@pytest.fixture
def tmp_output_dir(tmp_path) -> Path:
    return tmp_path / "temp"


# --------------------------------------------------------------------------- #
# generate_image
# --------------------------------------------------------------------------- #


def test_generate_image_writes_bytes_returned_by_image_call(monkeypatch, tmp_output_dir) -> None:
    monkeypatch.setattr(image_gen, "image_call", lambda **kw: b"fake png bytes")

    path = image_gen.generate_image("a jewellery display case", output_dir=tmp_output_dir)

    assert path.exists()
    assert path.read_bytes() == b"fake png bytes"
    assert path.suffix == ".png"


def test_generate_image_propagates_provider_errors(monkeypatch, tmp_output_dir) -> None:
    from app.llm.client import LLMError

    def boom(**kw):
        raise LLMError("no key")

    monkeypatch.setattr(image_gen, "image_call", boom)

    with pytest.raises(LLMError):
        image_gen.generate_image("prompt", output_dir=tmp_output_dir)


# --------------------------------------------------------------------------- #
# image_generation_node
# --------------------------------------------------------------------------- #


def test_image_generation_node_writes_image_paths(monkeypatch, tmp_output_dir) -> None:
    monkeypatch.setattr(nodes_module, "generate_image", lambda prompt: tmp_output_dir / "img_abc.png")

    state = {
        "brand": "Jade", "platform": "instagram", "language": "en",
        "draft_content": "a discreet jewellery collection", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None,
    }
    result = nodes_module.image_generation_node(state)

    assert result == {"image_paths": [str(tmp_output_dir / "img_abc.png")]}


def test_image_generation_node_never_crashes_the_graph_on_failure() -> None:
    """No GEMINI_API_KEY (blanked by the autouse fixture) -> LLMError inside
    generate_image -> node returns {} instead of raising, same contract as
    video_assembly_node."""
    state = {
        "brand": "Jade", "platform": "instagram", "language": "en",
        "draft_content": "copy", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None,
    }
    assert nodes_module.image_generation_node(state) == {}


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "platform,content_type,expected",
    [
        ("instagram", "post", "image"),
        ("instagram", "", "image"),
        ("instagram", "carousel", "compliance_gate"),  # carousel images made in persist_node instead
        ("instagram", "video", "video"),  # explicit video content_type wins over the image platform
        ("tiktok", "post", "video"),
        ("tiktok", "carousel", "video"),
        ("linkedin", "post", "compliance_gate"),
        ("linkedin", "carousel", "compliance_gate"),
    ],
)
def test_route_after_localization(platform, content_type, expected) -> None:
    state = {"platform": platform, "content_type": content_type}
    assert route_after_localization(state) == expected


# --------------------------------------------------------------------------- #
# persist_node: one image per carousel slide
# --------------------------------------------------------------------------- #


def test_persist_node_generates_one_image_per_carousel_slide(monkeypatch, tmp_output_dir) -> None:
    fake_pack = {
        "linkedin": "post", "thread": ["1/ a"], "carousel": ["Slide 1", "Slide 2", "Slide 3"],
        "video_script": "", "variant_a": "a", "variant_b": "b",
    }
    monkeypatch.setattr(formats_module, "build_format_pack", lambda draft, brand, platform: fake_pack)
    monkeypatch.setattr(formats_module, "pack_to_json", lambda pack: "{}")
    calls = []

    def fake_generate(prompt):
        calls.append(prompt)
        return tmp_output_dir / f"img_{len(calls)}.png"

    monkeypatch.setattr(nodes_module, "generate_image", fake_generate)

    state = {
        "brand": "Jade", "platform": "instagram", "language": "en",
        "draft_content": "copy", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None, "content_type": "carousel",
    }
    result = nodes_module.persist_node(state)

    assert len(calls) == 3
    with session_scope() as db:
        row = db.get(ContentQueue, result["content_id"])
        assert row.image_paths is not None
        assert len(row.image_paths) == 3


def test_persist_node_carousel_survives_one_slide_failing(monkeypatch, tmp_output_dir) -> None:
    fake_pack = {
        "linkedin": "post", "thread": ["1/ a"], "carousel": ["Slide 1", "Slide 2"],
        "video_script": "", "variant_a": "a", "variant_b": "b",
    }
    monkeypatch.setattr(formats_module, "build_format_pack", lambda draft, brand, platform: fake_pack)
    monkeypatch.setattr(formats_module, "pack_to_json", lambda pack: "{}")

    def flaky_generate(prompt):
        if "Slide 1" in prompt:
            raise RuntimeError("rate limited")
        return tmp_output_dir / "img_ok.png"

    monkeypatch.setattr(nodes_module, "generate_image", flaky_generate)

    state = {
        "brand": "Jade", "platform": "instagram", "language": "en",
        "draft_content": "copy", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None, "content_type": "carousel",
    }
    result = nodes_module.persist_node(state)

    with session_scope() as db:
        row = db.get(ContentQueue, result["content_id"])
        assert row.image_paths == [str(tmp_output_dir / "img_ok.png")]


def test_persist_node_passes_through_hero_image_for_non_carousel(monkeypatch) -> None:
    state = {
        "brand": "Jade", "platform": "instagram", "language": "en",
        "draft_content": "copy", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None, "content_type": "post",
        "image_paths": ["temp/img_hero.png"],
    }
    result = nodes_module.persist_node(state)

    with session_scope() as db:
        row = db.get(ContentQueue, result["content_id"])
        assert row.image_paths == ["temp/img_hero.png"]
