---
title: Image Generation Engine
tags: [pipeline, image, gemini, pollinations, media]
tier: Archival
component: "app/llm/client.py"
---

# Image Generation Engine

Renders hero images and carousel slides.

## Architecture
- **Primary**: Gemini native image-output models (`gemini-3.1-flash-image`).
- **Keyless Fallback**: Pollinations free REST image API when Gemini quota/billing is unavailable.
- Prompting: Derived strictly from copy topics — never artificially injected with brand names to prevent topic drift.

Connected entities: [[LangGraph-Engine]], [[Instagram]], [[Carousel-Format]].
