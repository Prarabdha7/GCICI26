"""2.5D Ken Burns engine: real MP4s with no moviepy and no paid APIs.

Hermetic: silent reels touch no network. Uses tmp dirs only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.media import assembly


def test_estimate_duration_scales_with_script() -> None:
    assert assembly.estimate_duration("Hi.") == 4.0
    assert assembly.estimate_duration("word " * 500) > 4.0


def test_caption_for_time_selects_active_window() -> None:
    caps = [
        {"text": "first", "start": 0.0, "end": 2.0},
        {"text": "second", "start": 2.0, "end": 4.0},
    ]
    assert assembly.caption_for_time(caps, 1.0) == "first"
    assert assembly.caption_for_time(caps, 3.0) == "second"
    assert assembly.caption_for_time(caps, 9.0) == ""


def test_kenburns_renders_real_mp4_with_captions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(assembly, "REEL_FPS", 4)
    out = assembly.assemble_kenburns_reel(
        script="Jade covers memo goods. Terms apply.",
        language="en", brand="Jade", audio_path=None, output_dir=tmp_path,
        run_id="test123",
    )
    assert out.exists()
    assert out.read_bytes()[4:8] == b"ftyp"  # real MP4 container, not a stub
    assert (tmp_path / "reel_test123.json").exists()
    assert (tmp_path / "reel_test123.srt").exists()


def test_kenburns_muxes_real_audio(monkeypatch, tmp_path: Path) -> None:
    import imageio_ffmpeg

    monkeypatch.setattr(assembly, "REEL_FPS", 4)
    silent_audio = tmp_path / "silence.mp3"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    import subprocess

    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", "2", str(silent_audio)],
        check=True, capture_output=True,
    )
    out = assembly.assemble_kenburns_reel(
        script="Hi.", language="en", brand="Jade",
        audio_path=silent_audio, output_dir=tmp_path, run_id="testaud",
    )
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.asyncio
async def test_word_boundaries_offline_returns_list(monkeypatch) -> None:
    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("offline")

    monkeypatch.setattr(assembly.edge_tts, "Communicate", Boom)
    result = await assembly.get_word_boundaries("hello world", "en")
    assert result == []


def test_reel_backdrop_prefers_local_broll(tmp_path: Path) -> None:
    import imageio.v2 as imageio
    import numpy as np

    broll = tmp_path / "jade_loop.mp4"
    writer = imageio.get_writer(str(broll), fps=4, codec="libx264", macro_block_size=None)
    writer.append_data(np.zeros((480, 270, 3), dtype="uint8"))
    writer.close()
    canvas = assembly._reel_backdrop("hello", brand="Jade", assets_dir=tmp_path)
    assert canvas.size == (1296, 2304)


def test_reel_backdrop_falls_back_to_canvas(tmp_path: Path) -> None:
    canvas = assembly._reel_backdrop("hello", brand="Jade",
                                     background_path=tmp_path / "missing.mp4")
    assert canvas.size == (1296, 2304)
