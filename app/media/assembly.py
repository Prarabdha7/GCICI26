"""Zero-cost video assembly: edge-tts voiceover + moviepy assembly.

    script (LLM) -> edge-tts -> voiceover.mp3 -> moviepy: set_audio -> reel.mp4

moviepy is pinned <2.0 (CLAUDE.md section 8): the 2.x renamed setter API
(`with_audio`) is not used here on purpose.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import edge_tts
from moviepy.editor import AudioFileClip, ColorClip, VideoFileClip

from app.config import settings

TEMP_DIR = settings.base_dir / "temp"

VOICE_BY_LANGUAGE: dict[str, str] = {
    "en": "en-SG-WayneNeural",
    "ms": "ms-MY-OsmanNeural",
    "id": "id-ID-ArdiNeural",
    "th": "th-TH-NiwatNeural",
    "zh": "zh-HK-WanLungNeural",
}
DEFAULT_VOICE = VOICE_BY_LANGUAGE["en"]


async def synthesize_voiceover(script: str, language: str, output_path: Path) -> Path:
    """Synthesize `script` to MP3 via edge-tts, voice selected by `language`."""
    voice = VOICE_BY_LANGUAGE.get(language, DEFAULT_VOICE)
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(str(output_path))
    return output_path


def assemble_video(
    *,
    script: str,
    language: str,
    background_path: Path | None = None,
    output_dir: Path = TEMP_DIR,
) -> Path:
    """Assemble a reel: voiceover over a background clip, trimmed to audio length.

    `background_path` is a real clip for production use; without one, a
    solid-color `ColorClip` stands in so the pipeline runs with no committed
    footage (assets/video/ currently holds only a .gitkeep).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    audio_path = output_dir / f"voiceover_{run_id}.mp3"
    video_path = output_dir / f"reel_{run_id}.mp4"

    asyncio.run(synthesize_voiceover(script, language, audio_path))
    audio_clip = AudioFileClip(str(audio_path))

    if background_path is not None:
        background = VideoFileClip(str(background_path)).subclip(0, audio_clip.duration)
    else:
        background = ColorClip(size=(1080, 1920), color=(20, 20, 20), duration=audio_clip.duration)

    final = background.set_audio(audio_clip)
    final.write_videofile(str(video_path), fps=24, codec="libx264", audio_codec="aac", logger=None)
    return video_path
