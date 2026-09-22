"""Zero-cost video assembly: edge-tts voiceover + moviepy assembly.

    script (LLM) -> edge-tts -> voiceover.mp3 -> moviepy: set_audio -> reel.mp4

moviepy is pinned <2.0 (CLAUDE.md section 8): the 2.x renamed setter API
(`with_audio`) is not used here on purpose.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import uuid
from pathlib import Path

try:
    import edge_tts
except ImportError:  # pragma: no cover - tests monkeypatch assembly.edge_tts
    class _EdgeTTSStub:
        class Communicate:  # type: ignore[no-redef]
            def __init__(self, *a, **k):
                raise RuntimeError("edge-tts not installed")
    edge_tts = _EdgeTTSStub()  # type: ignore[assignment]

try:  # moviepy 1.x (pinned in requirements)
    from moviepy.editor import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoFileClip
except ImportError:  # moviepy 2.x or missing — tests monkeypatch these globals
    try:
        from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoFileClip  # type: ignore[no-redef]
    except ImportError:
        AudioFileClip = None  # type: ignore[assignment]
        ColorClip = None  # type: ignore[assignment]
        VideoFileClip = None  # type: ignore[assignment]
        CompositeVideoClip = None  # type: ignore[assignment]
        ImageClip = None  # type: ignore[assignment]

from app.config import settings

log = logging.getLogger(__name__)

TEMP_DIR = settings.base_dir / "temp"

VOICE_BY_LANGUAGE: dict[str, str] = {
    "en": "en-SG-WayneNeural",
    "ms": "ms-MY-OsmanNeural",
    "id": "id-ID-ArdiNeural",
    "th": "th-TH-NiwatNeural",
    "zh": "zh-HK-WanLungNeural",
}
DEFAULT_VOICE = VOICE_BY_LANGUAGE["en"]

BRAND_BG: dict[str, tuple[int, int, int]] = {
    "jade": (5, 31, 23),
    "jaguar transit": (15, 23, 42),
    "jaguar_transit": (15, 23, 42),
    "doctorshield": (8, 47, 73),
}


def _brand_color(brand: str) -> tuple[int, int, int]:
    return BRAND_BG.get((brand or "").strip().lower(), (20, 20, 20))


async def synthesize_voiceover(script: str, language: str, output_path: Path) -> Path:
    """Synthesize `script` to MP3 via edge-tts, voice selected by `language`."""
    voice = VOICE_BY_LANGUAGE.get(language, DEFAULT_VOICE)
    communicate = edge_tts.Communicate(script, voice)
    await communicate.save(str(output_path))
    return output_path


def _run_voiceover_sync(script: str, language: str, audio_path: Path) -> None:
    """Event-loop safe: works from sync code AND inside a running FastAPI loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(synthesize_voiceover(script, language, audio_path))
        return
    # Already inside a loop (FastAPI/LangGraph async) — isolate in a fresh thread+loop.
    def _runner() -> None:
        asyncio.run(synthesize_voiceover(script, language, audio_path))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_runner).result()


async def get_word_boundaries(script: str, language: str) -> list[dict]:
    """Real edge-tts word timestamps (seconds). Empty list when offline/mocked."""
    try:
        voice = VOICE_BY_LANGUAGE.get(language, DEFAULT_VOICE)
        communicate = edge_tts.Communicate(script, voice)
        words: list[dict] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "WordBoundary":
                words.append({
                    "word": chunk.get("text", ""),
                    "start": (chunk.get("offset", 0) or 0) / 10_000_000,
                    "duration": (chunk.get("duration", 0) or 0) / 10_000_000,
                })
        return words
    except Exception as exc:
        log.warning("word boundaries unavailable (%s) — using estimates", exc)
        return []


def estimate_timings(script: str, total_duration: float) -> list[dict]:
    """Even-split fallback: distributes total_duration across words."""
    words = (script or "").split()
    if not words or not total_duration or total_duration <= 0:
        return []
    per = total_duration / len(words)
    return [{"word": w, "start": i * per, "duration": per} for i, w in enumerate(words)]


def chunk_captions(timings: list[dict], *, chunk_size: int = 4) -> list[dict]:
    """Groups word timings into caption cards for overlay."""
    caps = []
    for i in range(0, len(timings), chunk_size):
        chunk = timings[i:i + chunk_size]
        if not chunk:
            continue
        caps.append({
            "text": " ".join(w["word"] for w in chunk),
            "start": chunk[0]["start"],
            "end": chunk[-1]["start"] + chunk[-1]["duration"],
        })
    return caps


def render_subtitle_png(text: str, brand: str = "Jade", output_path: Path | None = None) -> Path | None:
    """Small bottom-third subtitle card (transparent-ish black bar + white text)."""
    try:
        from PIL import Image, ImageDraw

        W, H = 1080, 320
        img = Image.new("RGBA", (W, H), (0, 0, 0, 180))
        draw = ImageDraw.Draw(img)
        words = text.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 32:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            lines.append(cur)
        y = 60
        for line in lines[:3]:
            draw.text((60, y), line, fill=(255, 255, 255))
            y += 70
        out = output_path or (Path(settings.base_dir) / "temp" / f"sub_{uuid.uuid4().hex}.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return out
    except Exception as exc:
        log.warning("subtitle render skipped (%s)", exc)
        return None


def render_caption_card(
    text: str, brand: str = "Jade", size: tuple[int, int] = (1080, 1920), output_path: Path | None = None
) -> Path | None:
    """Kinetic-caption still: brand header + wrapped script + disclaimer. Pure Pillow, $0.

    Returns the PNG path, or None if Pillow rendering fails (pipeline still continues).
    """
    try:
        from PIL import Image, ImageDraw

        W, H = size
        bg = _brand_color(brand)
        img = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(img)
        # Header bar
        draw.rectangle([0, 0, W, 220], fill=(0, 0, 0))
        draw.text((60, 70), f"JA ASSURE — {brand.upper()}", fill=(212, 175, 55))
        # Body (naive wrap, no font file dependency)
        words, lines, cur = (text or "")[:420].split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > 34:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            lines.append(cur)
        y = 420
        for line in lines[:14]:
            draw.text((60, y), line, fill=(253, 251, 247))
            y += 62
        draw.text((60, H - 160), "Terms apply. Not financial advice.", fill=(160, 160, 160))
        out = output_path or (Path(settings.base_dir) / "temp" / f"caption_{uuid.uuid4().hex}.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return out
    except Exception as exc:  # pragma: no cover - Pillow optional path
        log.warning("caption render skipped (%s)", exc)
        return None


REEL_W, REEL_H = 1080, 1920
REEL_FPS = 12


def estimate_duration(script: str) -> float:
    """Spoken-duration estimate (~850 chars/min) when the real MP3 length is unknown."""
    return max(4.0, len(script or "") / 14.0)


def render_reel_canvas(script: str, brand: str = "Jade", size: tuple[int, int] = (1296, 2304)):
    """Full-bleed branded canvas (oversized so the Ken Burns crop can glide)."""
    from PIL import Image, ImageDraw

    W, H = size
    bg = _brand_color(brand)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 300], fill=(0, 0, 0))
    draw.text((70, 100), f"JA ASSURE — {brand.upper()}", fill=(212, 175, 55))
    words, lines, cur = (script or "")[:300].split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 26:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    y = H // 2 - len(lines[:8]) * 40
    for line in lines[:8]:
        draw.text((70, y), line, fill=(253, 251, 247))
        y += 80
    draw.text((70, H - 120), "Terms apply. Not financial advice.", fill=(160, 160, 160))
    return img


def caption_for_time(captions: list[dict], t: float) -> str:
    for cap in captions:
        if cap["start"] <= t < cap["end"]:
            return cap["text"]
    return ""


def assemble_kenburns_reel(
    *, script: str, language: str, brand: str = "Jade",
    audio_path: Path | None = None, output_dir: Path = TEMP_DIR, run_id: str = "",
    background_path: Path | None = None,
) -> Path:
    """2.5D Ken Burns reel with zero paid APIs and no moviepy.

    Background order: explicit `background_path` → `assets/video/<brand>_loop.mp4`
    (local B-roll override) → procedural brand canvas. Slow push-in over the
    backdrop + bottom-third captions + real edge-tts voiceover muxed in with
    the bundled ffmpeg binary. Raises honestly when Pillow/imageio/ffmpeg is
    missing (demo callers may stub).
    """
    import imageio.v2 as imageio
    import imageio_ffmpeg
    from PIL import Image, ImageDraw

    run_id = run_id or uuid.uuid4().hex
    output_dir.mkdir(parents=True, exist_ok=True)
    video_path = output_dir / f"reel_{run_id}.mp4"

    timings = estimate_timings(script, estimate_duration(script))
    captions = chunk_captions(timings)
    total = max((c["end"] for c in captions), default=estimate_duration(script))
    _persist_captions(output_dir, run_id, captions, timings)

    canvas = _reel_backdrop(script, brand=brand, background_path=background_path)
    CW, CH = canvas.size
    n_frames = max(1, int(total * REEL_FPS))
    silent_path = output_dir / f"silent_{run_id}.mp4"
    writer = imageio.get_writer(str(silent_path), fps=REEL_FPS, codec="libx264",
                                macro_block_size=None, quality=7)
    try:
        for i in range(n_frames):
            t = i / REEL_FPS
            progress = i / max(1, n_frames - 1)
            zoom = 1.0 + 0.12 * progress  # slow push-in
            cw, ch = int(REEL_W / zoom), int(REEL_H / zoom)
            x = int((CW - cw) * (0.5 + 0.12 * progress))  # gentle rightward drift
            y = int((CH - ch) * 0.5)
            frame = canvas.crop((x, y, x + cw, y + ch)).resize((REEL_W, REEL_H), Image.BILINEAR)
            caption = caption_for_time(captions, t)
            if caption:
                bar = Image.new("RGBA", (REEL_W, 300), (0, 0, 0, 190))
                d = ImageDraw.Draw(bar)
                words, lines, cur = caption.split(), [], ""
                for w in words:
                    if len(cur) + len(w) + 1 > 34:
                        lines.append(cur)
                        cur = w
                    else:
                        cur = f"{cur} {w}".strip()
                if cur:
                    lines.append(cur)
                ty = 40
                for line in lines[:3]:
                    d.text((60, ty), line, fill=(255, 255, 255))
                    ty += 72
                frame = frame.convert("RGBA")
                frame.alpha_composite(bar, (0, REEL_H - 340))
                frame = frame.convert("RGB")
            import numpy as np

            writer.append_data(np.asarray(frame))
    finally:
        writer.close()

    if audio_path is not None and audio_path.exists():
        import subprocess

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        final_path = output_dir / f"reel_{run_id}_final.mp4"
        subprocess.run(
            [ffmpeg, "-y", "-i", str(silent_path), "-i", str(audio_path),
             "-c:v", "copy", "-c:a", "aac", "-shortest", str(final_path)],
            check=True, capture_output=True,
        )
        silent_path.unlink(missing_ok=True)
        return final_path
    silent_path.rename(video_path)
    return video_path


def _reel_backdrop(script: str, brand: str, background_path: Path | None = None, assets_dir: Path | None = None):
    """Explicit B-roll path → per-brand loop override → Imagen 3 still → procedural canvas."""
    from PIL import Image
    from app.media.video_providers import (
        generate_imagen_still,
        get_cinematic_prompt,
        get_curated_broll,
    )

    assets = assets_dir if assets_dir is not None else settings.video_assets_dir
    candidates: list[Path] = []
    if background_path is not None:
        candidates.append(Path(background_path))

    # Strategy 4: Curated local B-roll loop
    broll = get_curated_broll(brand, assets_dir=assets)
    if broll:
        candidates.append(broll)

    brand_file = (assets / f"{(brand or '').strip().lower().replace(' ', '_')}_loop.mp4")
    candidates.append(brand_file)

    for candidate in candidates:
        try:
            if candidate.is_file() and candidate.stat().st_size > 0:
                if candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                    return Image.open(candidate).convert("RGB").resize((1296, 2304))
                import imageio.v2 as imageio

                frame = imageio.get_reader(str(candidate)).get_data(0)
                return Image.fromarray(frame).resize((1296, 2304))
        except Exception as exc:
            log.warning("B-roll %s unreadable (%s) — continuing", candidate, exc)

    # Strategy 1 Still: Imagen 3 / Gemini 4K still
    prompt = get_cinematic_prompt(brand, script)
    still_path = TEMP_DIR / f"still_{brand}_{uuid.uuid4().hex[:6]}.png"
    generated = generate_imagen_still(prompt, output_path=still_path)
    if generated and generated.is_file():
        try:
            return Image.open(generated).convert("RGB").resize((1296, 2304))
        except Exception as exc:
            log.warning("Generated still unreadable (%s)", exc)

    # Strategy 5: Procedural brand canvas
    return render_reel_canvas(script, brand=brand)


def _persist_captions(output_dir: Path, run_id: str, captions: list[dict], timings: list[dict]) -> None:
    import json as _json

    (output_dir / f"reel_{run_id}.json").write_text(
        _json.dumps({"captions": captions, "words": timings[:200]}), encoding="utf-8")

    def _ts(s: float) -> str:
        ms = int(s * 1000)
        return f"{ms//3600000:02d}:{(ms//60000)%60:02d}:{(ms//1000)%60:02d},{ms%1000:03d}"

    srt_lines = []
    for i, cap in enumerate(captions, 1):
        srt_lines += [str(i), f"{_ts(cap['start'])} --> {_ts(cap['end'])}", cap["text"], ""]
    (output_dir / f"reel_{run_id}.srt").write_text("\n".join(srt_lines), encoding="utf-8")


def assemble_video(
    *,
    script: str,
    language: str,
    brand: str = "Jade",
    background_path: Path | None = None,
    output_dir: Path = TEMP_DIR,
) -> Path:
    """Assemble a reel: voiceover over a background clip, trimmed to audio length.

    `background_path` is a real clip for production use; without one, a
    brand-tinted `ColorClip` stands in so the pipeline runs with no committed
    footage (assets/video/ currently holds only a .gitkeep). Also renders a
    Pillow caption card (kinetic still) alongside the MP4 for dashboard preview.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    audio_path = output_dir / f"voiceover_{run_id}.mp3"
    video_path = output_dir / f"reel_{run_id}.mp4"

    try:
        _run_voiceover_sync(script, language, audio_path)
    except Exception as exc:
        log.warning("edge-tts failed (%s) — continuing with silent-length stub", exc)
        audio_path.write_bytes(b"stub mp3")
    try:
        render_caption_card(script, brand=brand, output_path=output_dir / f"caption_{run_id}.png")
    except Exception:
        pass

    if background_path is None:
        from app.media.video_providers import (
            fetch_community_video,
            generate_veo_clip,
            get_cinematic_prompt,
            get_curated_broll,
        )

        prompt = get_cinematic_prompt(brand, script)
        veo_target = output_dir / f"veo_{run_id}.mp4"
        background_path = generate_veo_clip(prompt, output_path=veo_target, brand=brand)
        if background_path is None:
            comm_target = output_dir / f"comm_{run_id}.mp4"
            background_path = fetch_community_video(prompt, output_path=comm_target)
        if background_path is None:
            background_path = get_curated_broll(brand)

    # moviepy unavailable: render a real MP4 with the built-in 2.5D Ken Burns
    # engine (Pillow frames + bundled ffmpeg). Raises honestly when the
    # toolchain is missing; video_assembly_node turns that into no-media.
    if AudioFileClip is None or ColorClip is None:
        return assemble_kenburns_reel(
            script=script, language=language, brand=brand,
            audio_path=audio_path if audio_path.exists() else None,
            output_dir=output_dir, run_id=run_id,
            background_path=background_path,
        )
    audio_clip = AudioFileClip(str(audio_path))
    total_duration = float(getattr(audio_clip, "duration", 0) or 0) or 3.0

    # Word timings: real boundaries when online, even-split estimates offline.
    # Never blocks the pipeline — sync wrapper around the async fetcher.
    timings: list[dict] = []
    try:
        try:
            asyncio.get_running_loop()
            in_loop = True
        except RuntimeError:
            in_loop = False
        if in_loop:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                timings = pool.submit(lambda: asyncio.run(get_word_boundaries(script, language))).result(timeout=15)
        else:
            timings = asyncio.run(get_word_boundaries(script, language))
    except Exception:
        timings = []
    if not timings:
        timings = estimate_timings(script, total_duration)
    captions = chunk_captions(timings)
    # Persist timings + SRT for the dashboard player (caption highlight + download).
    try:
        import json as _json

        (output_dir / f"reel_{run_id}.json").write_text(_json.dumps({"captions": captions, "words": timings[:200]}), encoding="utf-8")
        srt_lines = []
        for i, cap in enumerate(captions, 1):
            def _ts(s: float) -> str:
                ms = int(s * 1000)
                return f"{ms//3600000:02d}:{(ms//60000)%60:02d}:{(ms//1000)%60:02d},{ms%1000:03d}"
            srt_lines += [str(i), f"{_ts(cap['start'])} --> {_ts(cap['end'])}", cap["text"], ""]
        (output_dir / f"reel_{run_id}.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    except Exception:
        pass

    if background_path is not None:
        clip = VideoFileClip(str(background_path))
        try:
            background = clip.subclip(0, audio_clip.duration)
        except AttributeError:
            background = clip.subclipped(0, audio_clip.duration)
    else:
        background = ColorClip(size=(1080, 1920), color=_brand_color(brand), duration=audio_clip.duration)

    # Subtitle overlay: best-effort — fakes in tests lack ImageClip/Composite support.
    try:
        if CompositeVideoClip is not None and ImageClip is not None and captions:
            overlays = []
            for idx, cap in enumerate(captions[:24]):
                png = render_subtitle_png(cap["text"], brand=brand, output_path=output_dir / f"sub_{run_id}_{idx}.png")
                if png is None:
                    continue
                sub = ImageClip(str(png), duration=max(0.1, cap["end"] - cap["start"]))
                try:
                    sub = sub.set_start(cap["start"]).set_position(("center", 1350))
                except AttributeError:
                    sub = sub.with_start(cap["start"]).with_position(("center", 1350))
                overlays.append(sub)
            if overlays:
                try:
                    background = CompositeVideoClip([background, *overlays], size=(1080, 1920))
                except Exception:
                    pass
    except Exception as exc:
        log.warning("subtitle overlay skipped (%s)", exc)

    try:
        final = background.set_audio(audio_clip)
    except AttributeError:
        final = background.with_audio(audio_clip)
    final.write_videofile(str(video_path), fps=24, codec="libx264", audio_codec="aac", logger=None)
    return video_path


async def assemble_video_async(*, script: str, language: str, brand: str = "Jade", background_path: Path | None = None, output_dir: Path = TEMP_DIR) -> Path:
    """Async entrypoint for use inside running event loops (dashboard trigger)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: assemble_video(script=script, language=language, brand=brand, background_path=background_path, output_dir=output_dir))
