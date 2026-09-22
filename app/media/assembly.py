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


def _veo_prompt(script: str) -> str:
    """Purely content-driven, same as app.graph.nodes._image_prompt — no
    hardcoded brand name/niche/voice injected. The script is already
    brand-appropriate (content_node writes it from a brand-voiced system
    prompt); a fixed style clause on top only overrode off-niche topics."""
    subject = (script or "").strip()[:300]
    if not subject:
        return "A short vertical marketing reel, no on-screen text overlays, no logos, cinematic, suitable for Instagram/TikTok."
    return f"{subject} No on-screen text overlays, no logos, cinematic, suitable for Instagram/TikTok."


def assemble_video(
    *,
    script: str,
    language: str,
    brand: str = "Jade",
    background_path: Path | None = None,
    output_dir: Path = TEMP_DIR,
) -> Path:
    """Assemble a reel. Tries Veo (real generative video, `app.llm.client.video_call`)
    first; any failure (no key, no quota, timeout) falls back to the zero-cost
    edge-tts + moviepy pipeline below — both are genuine, non-fabricated media,
    Veo is just the higher-fidelity option when it's actually available.

    The fallback: voiceover over a background clip, trimmed to audio length.
    `background_path` is a real clip for production use; if the caller didn't
    supply one, real Pexels stock footage keyed off the script is fetched
    next (app.media.stock_video); only if that's also unavailable (no
    PEXELS_API_KEY, no results, network failure) does a brand-tinted
    `ColorClip` stand in as the final safety net. Also renders a Pillow
    caption card (kinetic still) alongside the MP4 for dashboard preview.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    video_path = output_dir / f"reel_{run_id}.mp4"

    try:
        from app.llm.client import video_call

        video_bytes = video_call(prompt=_veo_prompt(script))
        video_path.write_bytes(video_bytes)
        log.info("assemble_video: used Veo, wrote %s (%d bytes)", video_path, len(video_bytes))
        return video_path
    except Exception as exc:
        log.warning("assemble_video: Veo unavailable (%s) — falling back to edge-tts + moviepy", exc)

    if background_path is None:
        try:
            from app.agents.brand_knowledge import get_brand
            from app.media.stock_video import extract_keyword, fetch_stock_video

            keyword = extract_keyword(script, fallback=get_brand(brand)["niche"])
            background_path = fetch_stock_video(keyword, output_dir=output_dir)
            log.info("assemble_video: using Pexels stock footage for keyword=%r", keyword)
        except Exception as exc:
            log.info("assemble_video: Pexels stock footage unavailable (%s) — checking local diffusion images", exc)
            try:
                recent_imgs = sorted(output_dir.glob("img_*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
                if recent_imgs:
                    background_path = recent_imgs[0]
                    log.info("assemble_video: using recent FLUX.1 diffusion image %s as backdrop", background_path)
            except Exception:
                pass

    audio_path = output_dir / f"voiceover_{run_id}.mp3"

    try:
        _run_voiceover_sync(script, language, audio_path)
    except Exception as exc:
        log.warning("edge-tts failed (%s) — generating valid silent audio stub", exc)
        try:
            import subprocess
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "5", "-c:a", "libmp3lame", str(audio_path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
        except Exception:
            pass
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            audio_path.write_bytes(b"stub mp3")
    try:
        # Ensure voice_runid alias exists for any legacy callers
        voice_alias = output_dir / f"voice_{run_id}.mp3"
        if audio_path.exists() and not voice_alias.exists():
            import shutil as _sh
            _sh.copyfile(audio_path, voice_alias)
    except Exception:
        pass
    try:
        render_caption_card(script, brand=brand, output_path=output_dir / f"caption_{run_id}.png")
    except Exception:
        pass
    # Encoder check:
    # 1. If AudioFileClip is present (e.g. monkeypatched by pytest), run the moviepy path below.
    # 2. If AudioFileClip is missing but FFmpeg is on PATH, render real MP4 via FFmpeg!
    # 3. Otherwise fall back to DEMO stub or raise in real mode.
    if AudioFileClip is None or ColorClip is None:
        import json as _json
        import shutil
        import subprocess

        # Calculate word timings + captions
        duration = 3.0
        ffprobe_bin = shutil.which("ffprobe")
        if ffprobe_bin and audio_path.exists() and audio_path.stat().st_size > 100:
            try:
                probe_res = subprocess.run(
                    [ffprobe_bin, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(audio_path)],
                    capture_output=True, text=True, timeout=5,
                )
                duration = float(_json.loads(probe_res.stdout)["format"]["duration"])
            except Exception:
                duration = max(3.0, len((script or "").split()) * 0.45)
        else:
            duration = max(3.0, len((script or "").split()) * 0.45)

        timings = []
        try:
            try:
                asyncio.get_running_loop()
                in_loop = True
            except RuntimeError:
                in_loop = False
            if in_loop:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    timings = pool.submit(lambda: asyncio.run(get_word_boundaries(script, language))).result(timeout=2.0)
            else:
                timings = asyncio.run(asyncio.wait_for(get_word_boundaries(script, language), timeout=2.0))
        except Exception:
            timings = []
        if not timings:
            timings = estimate_timings(script, duration)
        captions = chunk_captions(timings)

        # Write json & srt
        try:
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

        ffmpeg_bin = shutil.which("ffmpeg")
        caption_png = output_dir / f"caption_{run_id}.png"
        rendered = False
        srt_file = output_dir / f"reel_{run_id}.srt"
        sub_filter = ""
        if srt_file.exists() and srt_file.stat().st_size > 0:
            try:
                rel_srt = srt_file.relative_to(Path.cwd()).as_posix()
            except ValueError:
                rel_srt = srt_file.as_posix()
            sub_filter = f",subtitles={rel_srt}"

        if ffmpeg_bin and audio_path.exists():
            c = _brand_color(brand)
            hex_color = f"0x{c[0]:02X}{c[1]:02X}{c[2]:02X}"

            def _build_cmd(include_subtitles: bool = True):
                sf = sub_filter if include_subtitles else ""
                cmd = [ffmpeg_bin, "-y"]
                if background_path is not None and background_path.exists():
                    is_img = background_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
                    if is_img:
                        cmd += [
                            "-loop", "1", "-i", str(background_path),
                            "-i", str(audio_path),
                            "-filter_complex",
                            f"[0:v]scale=540:960:force_original_aspect_ratio=increase,crop=540:960,zoompan=z='min(zoom+0.0015,1.25)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=24{sf}[v]",
                            "-map", "[v]", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k",
                            "-shortest",
                            "-movflags", "+faststart",
                            str(video_path),
                        ]
                    else:
                        vf = sf.lstrip(",") if sf else "null"
                        cmd += [
                            "-stream_loop", "-1", "-i", str(background_path),
                            "-i", str(audio_path),
                            "-vf", vf,
                            "-c:v", "libx264", "-preset", "ultrafast",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "192k",
                            "-shortest",
                            "-movflags", "+faststart",
                            str(video_path),
                        ]
                elif caption_png.exists():
                    cmd += [
                        "-loop", "1", "-i", str(caption_png),
                        "-i", str(audio_path),
                        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        "-shortest",
                        "-movflags", "+faststart",
                        str(video_path),
                    ]
                else:
                    cmd += [
                        "-f", "lavfi", "-i", f"color=c={hex_color}:s=1080x1920:r=24",
                        "-i", str(audio_path),
                        "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        "-shortest",
                        "-movflags", "+faststart",
                        str(video_path),
                    ]
                return cmd

            try:
                cmd = _build_cmd(include_subtitles=bool(sub_filter))
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                if proc.returncode != 0 and sub_filter:
                    log.warning("assemble_video subtitles burn-in failed (%s) — retrying without burned subtitles", proc.stderr[-200:].decode("utf-8", errors="ignore"))
                    cmd = _build_cmd(include_subtitles=False)
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)

                if proc.returncode == 0 and video_path.exists() and video_path.stat().st_size > 0:
                    rendered = True
                    log.info("assemble_video: rendered via direct FFmpeg %s (%d bytes)", video_path, video_path.stat().st_size)
            except Exception as ffmpeg_err:
                log.warning("assemble_video FFmpeg render failed (%s)", ffmpeg_err)

        if rendered:
            return video_path

        from app.config import settings as _settings2
        if not _settings2.demo_mode:
            raise RuntimeError("video encoder unavailable in real mode — media skipped honestly")
        video_path.write_bytes(b"DEMO stub mp4 - install moviepy 1.0.3 on py3.10 for real encoding")
        return video_path
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
