---
title: Video Assembly & Veo Generative Video Engine
tags: [pipeline, video, veo, media, reels]
tier: Archival
component: "app/media/assembly.py"
---

# Video Assembly & 3-Tier Fallback

Generates vertical 1080x1920 MP4 video reels for [[TikTok]] and [[Instagram]].

## 3-Tier Robust Architecture
1. **Tier 1: Google Veo** — Generative video prompted directly from script keywords.
2. **Tier 2: Pexels Stock Clip** — Real stock footage keyed off script topics (`app/media/stock_video.py`).
3. **Tier 3: ColorClip Safety Net** — Brand-tinted MoviePy ColorClip fallback with subtitles and Edge-TTS voiceover.

Connected entities: [[LangGraph-Engine]], [[TikTok]], [[Instagram]], [[Video-Reel]].
