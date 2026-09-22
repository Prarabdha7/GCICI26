"""Phase 4 tests: zero-cost video assembly (edge-tts + moviepy).

edge-tts and moviepy are monkeypatched — no network calls, no real encoding.

    pytest tests/test_phase4.py -v
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

    def subclip(self, start: float, end: float) -> FakeVideoClip:
        self.duration = end - start
        return self

    def set_audio(self, audio: FakeAudioClip) -> FakeVideoClip:
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
# synthesize_voiceover
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_synthesize_voiceover_writes_the_audio_file(tmp_path) -> None:
    output_path = tmp_path / "voiceover.mp3"
    result = await assembly.synthesize_voiceover("hello", "en", output_path)
    assert result == output_path
    assert output_path.exists()


@pytest.mark.asyncio
async def test_synthesize_voiceover_selects_voice_by_language(monkeypatch, tmp_path) -> None:
    captured = {}

    class CapturingCommunicate(FakeCommunicate):
        def __init__(self, text, voice):
            captured["voice"] = voice
            super().__init__(text, voice)

    monkeypatch.setattr(assembly.edge_tts, "Communicate", CapturingCommunicate)

    await assembly.synthesize_voiceover("hello", "th", tmp_path / "vo.mp3")

    assert captured["voice"] == assembly.VOICE_BY_LANGUAGE["th"]


@pytest.mark.asyncio
async def test_synthesize_voiceover_falls_back_to_default_voice_for_unknown_language(monkeypatch, tmp_path) -> None:
    captured = {}

    class CapturingCommunicate(FakeCommunicate):
        def __init__(self, text, voice):
            captured["voice"] = voice
            super().__init__(text, voice)

    monkeypatch.setattr(assembly.edge_tts, "Communicate", CapturingCommunicate)

    await assembly.synthesize_voiceover("hello", "fr", tmp_path / "vo.mp3")

    assert captured["voice"] == assembly.DEFAULT_VOICE


def test_voice_by_language_covers_every_market_language() -> None:
    assert set(assembly.VOICE_BY_LANGUAGE) == {"en", "ms", "id", "th", "zh"}


# --------------------------------------------------------------------------- #
# assemble_video
# --------------------------------------------------------------------------- #


def test_assemble_video_uses_color_clip_without_a_background(tmp_output_dir) -> None:
    video_path = assembly.assemble_video(script="hello", language="en", output_dir=tmp_output_dir)

    assert video_path.exists()
    assert video_path.parent == tmp_output_dir


def test_assemble_video_uses_real_background_when_given(tmp_output_dir, tmp_path) -> None:
    background = tmp_path / "bg.mp4"
    background.write_bytes(b"fake background")

    video_path = assembly.assemble_video(
        script="hello", language="en", background_path=background, output_dir=tmp_output_dir
    )

    assert video_path.exists()


def test_assemble_video_trims_to_audio_duration(monkeypatch, tmp_output_dir, tmp_path):
    captured = {}
    original_subclip = FakeVideoClip.subclip

    def capturing_subclip(self, start, end):
        captured["start"], captured["end"] = start, end
        return original_subclip(self, start, end)

    monkeypatch.setattr(FakeVideoClip, "subclip", capturing_subclip)

    background = tmp_path / "bg.mp4"
    background.write_bytes(b"fake background")
    assembly.assemble_video(
        script="hello", language="en", background_path=background, output_dir=tmp_output_dir
    )

    assert captured == {"start": 0, "end": 3.0}


def test_assemble_video_creates_the_output_directory(tmp_path) -> None:
    output_dir = tmp_path / "does" / "not" / "exist"
    assembly.assemble_video(script="hello", language="en", output_dir=output_dir)
    assert output_dir.exists()


# --------------------------------------------------------------------------- #
# video_assembly_node
# --------------------------------------------------------------------------- #


def test_video_assembly_node_writes_media_path(monkeypatch, tmp_output_dir) -> None:
    from app.graph import nodes as nodes_module

    monkeypatch.setattr(nodes_module, "assemble_video", lambda **kw: tmp_output_dir / "reel.mp4")

    state = {
        "brand": "Jade", "platform": "instagram", "language": "en",
        "draft_content": "script text", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None,
    }
    result = nodes_module.video_assembly_node(state)

    assert result == {"media_path": str(tmp_output_dir / "reel.mp4")}


def test_video_assembly_node_passes_draft_content_and_language(monkeypatch) -> None:
    from app.graph import nodes as nodes_module

    captured = {}

    def fake_assemble(*, script, language, **kw):
        captured["script"], captured["language"] = script, language
        return Path("reel.mp4")

    monkeypatch.setattr(nodes_module, "assemble_video", fake_assemble)

    state = {
        "brand": "Jade", "platform": "instagram", "language": "th",
        "draft_content": "the localized script", "compliance_errors": [], "retry_count": 0,
        "feedback_guidance": "", "media_path": None,
    }
    nodes_module.video_assembly_node(state)

    assert captured == {"script": "the localized script", "language": "th"}
