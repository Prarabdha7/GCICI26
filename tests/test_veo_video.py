"""Tests for the Veo video path: app.llm.client.video_call and
assemble_video()'s Veo-first, moviepy-fallback contract.

video_call is monkeypatched everywhere — no network calls, no real polling.
edge-tts/moviepy are also monkeypatched (same fakes as test_phase4.py) so the
fallback path is exercised hermetically too. The autouse `_no_real_keys`
fixture (tests/conftest.py) blanks GEMINI_API_KEY, so any accidental
un-mocked call fails closed with LLMError instead of reaching the network.

    pytest tests/test_veo_video.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media import assembly


class FakeCommunicate:
    def __init__(self, text: str, voice: str) -> None:
        self.text = text
        self.voice = voice

    async def save(self, path: str) -> None:
        Path(path).write_bytes(b"fake mp3")


class FakeAudioClip:
    def __init__(self, path: str) -> None:
        self.path = path
        self.duration = 3.0


class FakeVideoClip:
    def __init__(self, size=None, color=None, duration=None, source=None) -> None:
        self.size = size
        self.color = color
        self.duration = duration
        self.source = source
        self.audio = None
        self.written_to: str | None = None

    def subclip(self, start: float, end: float) -> "FakeVideoClip":
        self.duration = end - start
        return self

    def set_audio(self, audio: FakeAudioClip) -> "FakeVideoClip":
        self.audio = audio
        return self

    def write_videofile(self, path: str, **kwargs) -> None:
        self.written_to = path
        Path(path).write_bytes(b"fake mp4")


@pytest.fixture(autouse=True)
def fake_moviepy(monkeypatch):
    monkeypatch.setattr(assembly, "AudioFileClip", FakeAudioClip)
    monkeypatch.setattr(assembly, "ColorClip", lambda size, color, duration: FakeVideoClip(size=size, color=color, duration=duration))
    monkeypatch.setattr(assembly, "VideoFileClip", lambda path: FakeVideoClip(source=path))


@pytest.fixture(autouse=True)
def fake_edge_tts(monkeypatch):
    monkeypatch.setattr(assembly.edge_tts, "Communicate", FakeCommunicate)


@pytest.fixture
def tmp_output_dir(tmp_path) -> Path:
    return tmp_path / "temp"


# --------------------------------------------------------------------------- #
# assemble_video: Veo-first, moviepy-fallback
# --------------------------------------------------------------------------- #


def test_assemble_video_uses_veo_when_available(monkeypatch, tmp_output_dir) -> None:
    monkeypatch.setattr("app.llm.client.video_call", lambda **kw: b"fake veo mp4 bytes")

    video_path = assembly.assemble_video(script="hello", language="en", output_dir=tmp_output_dir)

    assert video_path.exists()
    assert video_path.read_bytes() == b"fake veo mp4 bytes"
    assert video_path.parent == tmp_output_dir


def test_assemble_video_falls_back_to_moviepy_when_veo_fails(monkeypatch, tmp_output_dir) -> None:
    from app.llm.client import LLMError

    def boom(**kw):
        raise LLMError("no key")

    monkeypatch.setattr("app.llm.client.video_call", boom)

    video_path = assembly.assemble_video(script="hello", language="en", output_dir=tmp_output_dir)

    assert video_path.exists()
    assert video_path.read_bytes() == b"fake mp4"  # the moviepy fake's output, not Veo's


def test_assemble_video_never_crashes_on_veo_failure_with_no_key(tmp_output_dir) -> None:
    """No GEMINI_API_KEY (blanked by the autouse fixture) -> LLMError inside
    video_call -> assemble_video falls back to moviepy instead of raising."""
    video_path = assembly.assemble_video(script="hello", language="en", output_dir=tmp_output_dir)
    assert video_path.exists()


# --------------------------------------------------------------------------- #
# video_call / _gemini_video
# --------------------------------------------------------------------------- #


def test_veo_prompt_is_driven_entirely_by_the_script() -> None:
    """Regression guard, same issue as _image_prompt: no hardcoded brand
    name/niche/voice should appear -- the script alone drives the video."""
    prompt = assembly._veo_prompt("The new iPhone: faster, brighter, unbreakable.")

    assert prompt.startswith("The new iPhone")
    assert "Jewellers Block Insurance" not in prompt
    assert "Jade" not in prompt


def test_video_call_unknown_provider_raises() -> None:
    from app.llm.client import LLMError, video_call

    with pytest.raises(LLMError):
        video_call(prompt="x", provider="not-a-real-provider")


def test_gemini_video_requires_api_key() -> None:
    from app.llm.client import LLMError, video_call

    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        video_call(prompt="a jewellery reel")
