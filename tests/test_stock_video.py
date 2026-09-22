"""Tests for the Pexels stock-footage fallback: app/media/stock_video.py
and its integration into assemble_video()'s Veo -> Pexels -> ColorClip chain.

httpx.get is monkeypatched everywhere — no real network calls. The autouse
_no_real_keys fixture blanks PEXELS_API_KEY, and _no_live_pexels mocks
fetch_stock_video closed, so both layers independently prevent a live call;
tests that exercise the real logic explicitly re-patch what they need.

    pytest tests/test_stock_video.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.providers import ProviderError
from app.media import stock_video
from app.media.stock_video import fetch_stock_video as _real_fetch_stock_video


@pytest.fixture
def tmp_output_dir(tmp_path) -> Path:
    return tmp_path / "temp"


# --------------------------------------------------------------------------- #
# extract_keyword
# --------------------------------------------------------------------------- #


def test_extract_keyword_picks_content_words_in_order() -> None:
    script = "Discretion is not a discount. Jade covers your jewellery collection."
    keyword = stock_video.extract_keyword(script, fallback="jewellery store")
    assert keyword == "discretion discount jade"


def test_extract_keyword_falls_back_when_script_is_all_stopwords() -> None:
    keyword = stock_video.extract_keyword("is a the of", fallback="jewellery store")
    assert keyword == "jewellery store"


def test_extract_keyword_falls_back_on_empty_script() -> None:
    keyword = stock_video.extract_keyword("", fallback="jewellery store")
    assert keyword == "jewellery store"


# --------------------------------------------------------------------------- #
# fetch_stock_video
# --------------------------------------------------------------------------- #


def test_fetch_stock_video_requires_api_key(tmp_output_dir) -> None:
    with pytest.raises(ProviderError, match="PEXELS_API_KEY"):
        _real_fetch_stock_video("jewellery", output_dir=tmp_output_dir)


def test_fetch_stock_video_downloads_the_first_result(monkeypatch, tmp_output_dir) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "pexels_api_key", "test-key")

    class _SearchResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"videos": [{"video_files": [{"width": 640, "link": "https://pexels.example/video.mp4"}]}]}

    class _VideoResponse:
        content = b"real mp4 bytes"

        def raise_for_status(self):
            pass

    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if url == stock_video.SEARCH_URL:
            return _SearchResponse()
        return _VideoResponse()

    monkeypatch.setattr(stock_video.httpx, "get", fake_get)

    path = _real_fetch_stock_video("jewellery display", output_dir=tmp_output_dir)

    assert path.exists()
    assert path.read_bytes() == b"real mp4 bytes"
    assert calls == [stock_video.SEARCH_URL, "https://pexels.example/video.mp4"]


def test_fetch_stock_video_raises_when_pexels_has_no_results(monkeypatch, tmp_output_dir) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "pexels_api_key", "test-key")

    class _EmptyResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"videos": []}

    monkeypatch.setattr(stock_video.httpx, "get", lambda *a, **kw: _EmptyResponse())

    with pytest.raises(ProviderError, match="no videos"):
        _real_fetch_stock_video("an extremely obscure query", output_dir=tmp_output_dir)


# --------------------------------------------------------------------------- #
# assemble_video integration: Veo -> Pexels -> ColorClip
# --------------------------------------------------------------------------- #


class _FakeCommunicate:
    def __init__(self, text: str = "", voice: str = "") -> None:
        self.text, self.voice = text, voice

    async def save(self, path: str) -> None:
        Path(path).write_bytes(b"fake mp3")


class _FakeAudioClip:
    def __init__(self, path: str) -> None:
        self.path = path
        self.duration = 3.0


class _FakeVideoClip:
    def __init__(self, size=None, color=None, duration=None, source=None) -> None:
        self.size, self.color, self.duration, self.source = size, color, duration, source
        self.audio = None
        self.written_to: str | None = None

    def subclip(self, start: float, end: float) -> _FakeVideoClip:
        self.duration = end - start
        return self

    def set_audio(self, audio: _FakeAudioClip) -> _FakeVideoClip:
        self.audio = audio
        return self

    def write_videofile(self, path: str, **kwargs) -> None:
        self.written_to = path
        Path(path).write_bytes(b"fake mp4")


def test_assemble_video_uses_pexels_when_veo_fails_and_no_background_given(monkeypatch, tmp_output_dir) -> None:
    from app.llm.client import LLMError
    from app.media import assembly

    monkeypatch.setattr("app.llm.client.video_call", lambda **kw: (_ for _ in ()).throw(LLMError("no key")))
    monkeypatch.setattr(assembly, "AudioFileClip", _FakeAudioClip)
    monkeypatch.setattr(
        assembly, "ColorClip", lambda size, color, duration: _FakeVideoClip(size=size, color=color, duration=duration)
    )
    monkeypatch.setattr(assembly, "VideoFileClip", lambda path: _FakeVideoClip(source=path))
    monkeypatch.setattr(assembly.edge_tts, "Communicate", _FakeCommunicate)

    used_background = {}

    def fake_fetch(keyword, *, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "stock_fake.mp4"
        path.write_bytes(b"fake stock mp4")
        used_background["keyword"] = keyword
        return path

    monkeypatch.setattr("app.media.stock_video.fetch_stock_video", fake_fetch)

    video_path = assembly.assemble_video(script="hello world", language="en", output_dir=tmp_output_dir)

    assert video_path.exists()
    assert used_background["keyword"]  # extract_keyword ran and produced something


def test_assemble_video_falls_back_to_color_clip_when_pexels_also_fails(monkeypatch, tmp_output_dir) -> None:
    """No key, no results, network down -- whatever the reason, Pexels
    failing must not crash assemble_video; the existing ColorClip path
    (already covered by test_phase4.py) takes over."""
    from app.llm.client import LLMError
    from app.media import assembly

    monkeypatch.setattr("app.llm.client.video_call", lambda **kw: (_ for _ in ()).throw(LLMError("no key")))
    monkeypatch.setattr(assembly, "AudioFileClip", _FakeAudioClip)
    monkeypatch.setattr(
        assembly, "ColorClip", lambda size, color, duration: _FakeVideoClip(size=size, color=color, duration=duration)
    )
    monkeypatch.setattr(assembly, "VideoFileClip", lambda path: _FakeVideoClip(source=path))
    monkeypatch.setattr(assembly.edge_tts, "Communicate", _FakeCommunicate)
    # _no_live_pexels (conftest) already mocks fetch_stock_video closed

    video_path = assembly.assemble_video(script="hello world", language="en", output_dir=tmp_output_dir)

    assert video_path.exists()
