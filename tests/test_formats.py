"""Hashtag/SEO optimiser: suggestions for the reviewer, source-labeled."""

from __future__ import annotations

from app.agents.formats import build_format_pack, suggest_hashtags


def test_offline_hashtags_are_brand_scoped() -> None:
    tags, source = suggest_hashtags("hello", "Jade", "instagram")

    assert source == "offline"  # keys are blanked by conftest
    assert all(t.startswith("#") for t in tags)
    assert len(tags) <= 8


def test_offline_hashtags_vary_by_brand() -> None:
    jade, _ = suggest_hashtags("hello", "Jade", "linkedin")
    doc, _ = suggest_hashtags("hello", "DoctorShield", "linkedin")

    assert jade != doc


def test_pack_carries_hashtags_with_source() -> None:
    pack = build_format_pack("Jade covers memo goods. Terms apply.", "Jade", "linkedin")

    assert isinstance(pack["hashtags"], list) and pack["hashtags"]
    assert pack["hashtags_source"] in ("llm", "offline")
