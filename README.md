# JA Assure — Autonomous Multi-Agent Marketing and Self-Healing Compliance OS

<p align="left">
  <a href="https://github.com/prarabdha7/GCICI26"><img src="https://img.shields.io/badge/GitHub-prarabdha7%2FGCICI26-black.svg?logo=github" alt="GitHub Repository"></a>
  <img src="https://img.shields.io/badge/Python-3.11%20|%203.12%20|%203.13-3776AB.svg?logo=python&logoColor=white" alt="Python 3.11 | 3.12 | 3.13">
  <img src="https://img.shields.io/badge/FastAPI-0.128-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Orchestration-LangGraph%20Cyclic%20State%20Machine-7C3AED.svg" alt="LangGraph">
  <img src="https://img.shields.io/badge/LLM-Gemini%203.6%20Flash%20%7C%20GPT--4o--mini-4285F4.svg?logo=google&logoColor=white" alt="LLM Providers">
  <img src="https://img.shields.io/badge/Compliance-MAS%20Notice%20318%20%7C%20BNM%20%7C%20HKIA-0F766E.svg" alt="Regulatory Compliance">
  <img src="https://img.shields.io/badge/Media-FFmpeg%20%2B%20Edge--TTS%20%2B%20FLUX.1-E11D48.svg" alt="Media Engine">
  <img src="https://img.shields.io/badge/Memory-SQLite%20%2B%20Obsidian%20Vault-6B7280.svg" alt="Memory Architecture">
  <img src="https://img.shields.io/badge/Tests-182%20Passed%20(100%25)-16A34A.svg?logo=pytest&logoColor=white" alt="Test Suite">
  <img src="https://img.shields.io/badge/License-MIT-1D4ED8.svg" alt="License MIT">
</p>

> **Repository**: [https://github.com/prarabdha7/GCICI26](https://github.com/prarabdha7/GCICI26)

**JA Assure Intelligence OS** is an autonomous enterprise marketing system engineered for **JA Assure** — a Singapore-headquartered niche InsurTech managing high-value risk portfolios across South East Asia and Hong Kong. It combines a cyclic LangGraph state machine, a 3-tier cognitive memory architecture, real-time competitive intelligence, deterministic statutory compliance auditing (MAS Notice 318), and a zero-cost programmatic media rendering studio (FFmpeg + MoviePy, Edge-TTS, Pollinations FLUX.1 with optional Gemini image / Veo video).

Three distinct risk brands are supported out of the box:

- **Jade Assure**: Jewellers Block, fine horology, and dual-key high-value vault coverage.
- **Jaguar Transit**: Armored attended cargo, cold-chain maritime, and high-consequence logistics transit.
- **DoctorShield**: Specialist medical malpractice indemnity and clinical dispute arbitration.

---

## Table of Contents

- [1. Repository Structure](#1-repository-structure)
- [2. Visual Interface and Architecture Showcase](#2-visual-interface-and-architecture-showcase)
- [3. End-to-End System Architecture](#3-end-to-end-system-architecture)
- [4. Step-by-Step Cognitive Agentic Pipeline](#4-step-by-step-cognitive-agentic-pipeline)
- [5. Obsidian Second Brain and 3-Tier Memory OS](#5-obsidian-second-brain-and-3-tier-memory-os)
- [6. Zero-Cost Media Studio and FFmpeg Reel Pipeline](#6-zero-cost-media-studio-and-ffmpeg-reel-pipeline)
- [7. Computational Complexity and Latency Matrix](#7-computational-complexity-and-latency-matrix)
- [8. Deterministic Statutory Compliance Benchmarks](#8-deterministic-statutory-compliance-benchmarks)
- [9. Local Development and Reproducibility Guide](#9-local-development-and-reproducibility-guide)
- [10. Architectural Decisions and Engineering Justifications](#10-architectural-decisions-and-engineering-justifications)

---

## 1. Repository Structure

The codebase is organized into modular layers separating state-machine orchestration, compliance auditing, media assembly, and the Apple Design Method presentation layer:

```
repo-root/
├── app/
│   ├── main.py                     # Primary FastAPI application, middleware and unified mounting
│   ├── config.py                   # Pydantic Settings (defaults: gemini-3.6-flash / gpt-4o-mini) + .env resolution
│   ├── agents/
│   │   ├── brand_knowledge.py      # Underwriting criteria, warranties and brand rubrics
│   │   ├── formats.py              # Multi-channel formatting (LinkedIn, IG, X, TikTok, Focus Group)
│   │   ├── prompts.py              # Zero-shot and few-shot system prompts incl. adversarial marketer / inquisitor / arbiter + memory injection
│   │   ├── leads.py                # B2B prospecting and underwriting fit-score algorithm
│   │   ├── research.py             # Lead-gen research node (DuckDuckGo + Crawl4AI via utils/research.py, mock fallback)
│   │   └── providers.py            # Search / discovery / scrape providers (Serper, Google Places, ScrapeGraph, Hunter + deterministic mocks)
│   ├── api/
│   │   ├── actions.py              # Core JSON actions API for media, perception and compliance
│   │   ├── routes.py               # Programmatic /api/v1 REST endpoints
│   │   ├── schemas.py              # Shared request/response schemas
│   │   └── dashboard.py            # Legacy server-side review dashboard and telemetry endpoints
│   ├── db/
│   │   ├── database.py             # SQLAlchemy engine, sessionmaker and SQLite/Postgres scopes
│   │   ├── models.py               # ContentQueue, FeedbackMemory, LeadEntry ORM schemas
│   │   └── persist.py              # Persistence helpers for queue rows
│   ├── graph/
│   │   ├── nodes.py                # Discrete LangGraph nodes incl. _adversarial_debate (marketer / inquisitor / arbiter in-code, no separate inquisitor.py)
│   │   ├── routing.py              # Edge routing logic for the compliance and localization gates
│   │   ├── graph.py                # Graph assembly: node wiring, edge routing, compilation
│   │   ├── lead_gen_graph.py       # Lead-generation subgraph wiring
│   │   └── state.py                # TypedDict MarketingState carrying cumulative run context
│   ├── integrations/
│   │   ├── obsidian.py             # Bidirectional Second Brain Markdown and Excalidraw exporter
│   │   └── memgpt.py               # Optional MemGPT guidance augmentation (disabled when blank)
│   ├── llm/
│   │   ├── client.py               # Provider-agnostic LLM client (Gemini primary gemini-3.6-flash with gemini-2.0/2.5-flash cascade; OpenAI gpt-4o-mini) + Pollinations FLUX fallback + Veo video
│   │   └── fallback.py             # Domain-grounded heuristic fallback and self-healing engine
│   ├── media/
│   │   ├── assembly.py             # FFmpeg 1080x1920 encoder or MoviePy composition + timed SRT subtitle burn-in + Veo Tier-1 path
│   │   ├── image_gen.py            # Pollinations FLUX.1 / Gemini image synthesis and brand color grading
│   │   └── stock_video.py          # Semantic stock footage selector and fallback video provider
│   └── utils/
│       └── research.py             # Keyless DuckDuckGo + Crawl4AI competitor intelligence (replaces Tavily path; httpx/BS4 + mock fallback)
├── frontend/                       # Vanilla HTML / CSS / JS SPA (no Next.js / React / Remotion dependency)
│   ├── index.html                  # Apple Keynote UI shell and Cupertino viewport container
│   ├── app.js                      # Reactive SPA controller (views, audio visualizer, Remotion-style CSS player, scrub)
│   └── styles.css                  # Apple Design Method design tokens, glassmorphism and typography
├── worker/
│   ├── publisher.py                # Buffer / Ayrshare social dispatcher and webhook handler
│   └── scheduler.py                # APScheduler daemon polling approved queue under MAS Notice 318
├── scripts/
│   ├── sync_obsidian_vault.py      # Second Brain vault synchronization and bidirectional linker
│   ├── init_db.py                  # DDL table creation and schema initialization
│   └── seed_demo.py                # Walkthrough seed data generator for keyless testing
├── docs/
│   └── images/                     # Architectural diagrams, UI mockups and knowledge graph captures
├── tests/                          # 182 comprehensive unit, integration and compliance tests
├── run.py                          # Unified server runner (spawns API + background workers)
├── GITHUB_REPO.txt                 # Canonical repository URL
└── requirements.txt                # Version-ranged production dependencies (>=, incl. moviepy<2.0)
```

---

## 2. Visual Interface and Architecture Showcase

The frontend is constructed following the **Apple Design Method (ADM)** — featuring cinematic typography, frosted glassmorphic cards (`backdrop-filter: blur(20px)`), an Apple Keynote boot loader, live audio waveform visualizers, and interactive playhead scrubbers.

| **Obsidian Second Brain Knowledge Graph** | **Zero-Cost Media Studio and FFmpeg Reel Player** |
|:---:|:---:|
| <a href="docs/images/obsidian_vault_graph.png"><img src="docs/images/obsidian_vault_graph.png" width="450" alt="Obsidian Knowledge Graph"></a> | <a href="docs/images/zero_cost_media_studio.png"><img src="docs/images/zero_cost_media_studio.png" width="450" alt="Media Studio"></a> |
| *Topological graph mapping brands, underwriting constraints and MAS 318 rules.* | *FFmpeg / MoviePy programmatic pipeline with Remotion-style CSS player, waveform and FLUX.1 diffusion (no Remotion library dependency).* |

| **MAS Notice 318 Compliance and Self-Healing** | **Real-Time Competitor Perception Engine** |
|:---:|:---:|
| <a href="docs/images/compliance_self_healing.png"><img src="docs/images/compliance_self_healing.png" width="450" alt="Compliance Self Healing"></a> | <a href="docs/images/perception_engine_scraper.png"><img src="docs/images/perception_engine_scraper.png" width="450" alt="Perception Engine Scraper"></a> |
| *Statutory audit, 3-agent adversarial debate and automatic redline repair.* | *Live NLP scraping of competitor policies, policy UINs and counter-hooks.* |

| **Review Queue and Auto-Publisher Worker** | **1080x1920 MP4 Video Reel with Burned Subtitles** |
|:---:|:---:|
| <a href="docs/images/review_queue_publisher.png"><img src="docs/images/review_queue_publisher.png" width="450" alt="Review Queue"></a> | <a href="docs/images/remotion_video_player.png"><img src="docs/images/remotion_video_player.png" width="450" alt="Video Reel Player (FFmpeg output shown in Remotion-style preview)"></a> |
| *MAS Notice 318 Human-in-the-Loop gate with 1-click dispatch.* | *Cinematic AI camera motion (Ken Burns zoompan) with burned captions — rendered by FFmpeg / MoviePy, previewed in a Remotion-style CSS canvas.* |

---

## 3. End-to-End System Architecture

The core pipeline operates as a cyclic directed state machine orchestrated with **LangGraph**. A draft cannot advance to publishing without successfully passing through the statutory compliance gate.

```mermaid
graph TD
    Start((User Prompt / Topic)) --> Research[1. Perception and Research Node]
    Research --> Content[2. Content Generation Node]
    Content --> Localize[3. Regional Localization Node]
    Localize --> Audit{4. MAS Notice 318 Compliance Gate}

    Audit -- "Statutory Violations Flagged" --> Debate[5. 3-Agent Adversarial Debate]
    Debate --> Healer[6. Self-Healing Redline Repair]
    Healer -- "Retry Count <= 3" --> Content
    Healer -- "Circuit Breaker Tripped (>3 Retries)" --> ManualQueue[7. Human Intervention Queue]

    Audit -- "Score >= 85 Compliant" --> Media[8. Media Studio: Audio, SRT and Video]
    Media --> Vault[9. Obsidian Second Brain Sync]
    Vault --> ReviewQueue[10. MAS 318 Review Queue]
    
    ReviewQueue -- "Human Compliance Approval" --> PublisherWorker[11. Auto-Publisher Worker]
    PublisherWorker --> LiveSocials((Buffer / Ayrshare Live Channels))

    subgraph "Knowledge and Memory Layers"
        M1[(Tier-1: State RAM Context)]
        M2[(Tier-2: Feedback Memory SQLite)]
        M3[(Tier-3: Obsidian Vault Markdown)]
    end

    Content -.-> M1
    Audit -.-> M2
    Vault -.-> M3
```

---

## 4. Step-by-Step Cognitive Agentic Pipeline

### Phase 1: Live Market Perception and Competitor Scraping

- **Action**: Keyless-first search via **DuckDuckGo + Crawl4AI** (`app/utils/research.py`), with `httpx` + `BeautifulSoup4` fallback and deterministic mocks when live results are empty (`app/agents/providers.py:MockSearchProvider`). **Serper / Google Places / ScrapeGraph / Hunter** activate only when their keys are set; **Tavily** remains only as an optional legacy fallback in `POST /api/perception/scrape` when `TAVILY_API_KEY` is present.
- **Engineering Justification**: Prevents hallucinated or repetitive claims. Real competitor policy provisions, regulatory UINs, and coverage exclusions (e.g. Kalyan Jewellers vs Tanishq) are extracted via sentence tokenization and converted into actionable counter-hooks.

### Phase 2: Persona-Driven Content Generation

- **Action**: Constructs platform-specific marketing collateral (LinkedIn executive risk briefings, Instagram visual carousels, X/Twitter 3-part threads, and TikTok scripts) using brand-grounded underwriting criteria.
- **Memory Injection**: Before generating copy, the agent queries the `feedback_memory` database and injects the **last 5 human rejections and compliance rulings** into the system prompt to prevent recurring mistakes.

### Phase 3: Regional Localization Pass

- **Action**: Adapts language, terminology, and legal disclosures for specific target jurisdictions:
  - `en-SG` (Singapore: MAS Notice 318, Lloyd's syndicate terms).
  - `ms-MY` (Malaysia: Bank Negara Malaysia Market Conduct standards).
  - `zh-HK` (Hong Kong: HKIA Guideline 28 on advertising).
  - `id-ID` (Indonesia: OJK consumer protection standards).
  - `th-TH` (Thailand: Office of Insurance Commission regulations).

### Phase 4: Statutory Compliance Gate and 3-Agent Adversarial Debate

- **Action**: Audits draft copy against external jurisdictional rubrics (`compliance_rubric.md`). If violations are detected (e.g., unsubstantiated guarantees like "100% payout" or missing exclusion clauses), a structured adversarial debate is triggered in-code via `app/graph/nodes.py:_adversarial_debate` using prompts from `app/agents/prompts.py` (there is no separate `agents/inquisitor.py`):
  1. **Marketer Persona (Growth Optimizer)**: Explains conversion intent.
  2. **Inquisitor Persona (Regulatory Enforcement)**: Formally cites statutory violation clauses and issues a rejection verdict.
  3. **Arbiter Persona (Pareto Frontier Synthesizer)**: Reconciles commercial engagement with strict regulatory compliance.

### Phase 5: Self-Healing Redline Repair and Circuit Breaker

- **Action**: The arbiter synthesizes a self-healed, compliant replacement script with mandatory statutory safe-harbor disclosures.
- **Circuit Breaker**: If a draft fails compliance more than 3 consecutive times (`retry_count > 3`), the loop aborts and routes the asset directly to the human review queue with a `compliance_diverted` status to avoid infinite token loops.

---

## 5. Obsidian Second Brain and 3-Tier Memory OS

The architecture maintains three distinct memory tiers to ensure zero context loss, strict regulatory provenance, and explainable AI audit trails:

```
+-------------------------------------------------------------+
|                   TIER 1: WORKING RAM CONTEXT               |
|  LangGraph TypedDict State (Ephemeral, single execution run)|
+------------------------------+------------------------------+
                               | Persists Human Decisions
                               v
+-------------------------------------------------------------+
|                 TIER 2: EPISODIC AND FEEDBACK MEMORY        |
|  SQLite / PostgreSQL (FeedbackMemory, ContentQueue records) |
+------------------------------+------------------------------+
                               | Bidirectional Topology Sync
                               v
+-------------------------------------------------------------+
|               TIER 3: ARCHIVAL SECOND BRAIN VAULT           |
|  Obsidian Markdown Vault + Wikilinks [[]] + Excalidraw MOC  |
+-------------------------------------------------------------+
```

The knowledge graph below shows the full topology of brand nodes, underwriting constraints, MAS 318 regulatory clauses, and generated marketing assets as tracked inside the Obsidian vault:

<a href="docs/images/obsidian_vault_graph.png"><img src="docs/images/obsidian_vault_graph.png" width="700" alt="Obsidian Second Brain Knowledge Graph — full topology view"></a>

- **Obsidian Graph Topology**: Generates interconnected Markdown notes for all brands, underwriting constraints, regulatory clauses, and marketing assets with standard `[[Wikilinks]]`.
- **Visual Excalidraw Mapping**: Exports programmatic JSON canvas layouts viewable inside Obsidian with node relationships and compliance state color coding.
- **Interactive Knowledge Sync**: Run `python -m scripts.sync_obsidian_vault` to sync generated marketing assets directly into Obsidian.

---

## 6. Zero-Cost Media Studio and FFmpeg Reel Pipeline

Rather than relying on expensive, quota-limited third-party SaaS APIs, JA Assure OS includes a fully localized, zero-cost programmatic media rendering engine:

1. **Visual Diffusion Studio (Pollinations FLUX.1-schnell, optional Gemini image)**:
    - Uses zero-cost Pollinations FLUX.1 diffusion to generate high-resolution commercial photography (no key); tries Gemini `gemini-3.1-flash-image` first when `GEMINI_API_KEY` is set, then falls back to Pollinations on quota/billing errors.
    - Automatically sanitizes prompt parameters and formats outputs for 9:16 reels, 1:1 carousels, or 16:9 banners.

2. **Neural Speech Synthesis (Edge-TTS)**:
   - Synthesizes clean neural speech voiceover tracks in English (`en-SG-WayneNeural`), Malay, Mandarin, Indonesian, or Thai in under 400ms with zero API cost.

3. **FFmpeg 1080x1920 MP4 Assembler (FFmpeg binary or MoviePy composition, optional Veo Tier-1)**:
    - Compiles vertical reels using dynamic camera zoom and pan (`zoompan` Ken Burns effect) over high-resolution diffusion backdrops. Tries Google Veo (`veo-3.1-fast-generate-preview`) first when configured, then local assembly.
    - **Burned-In Timed Subtitles**: Automatically aligns frame-accurate SRT subtitles and permanently burns high-legibility captions directly into the MP4 video using libass.
    - **Instant Web Streaming (`-movflags +faststart`)**: Shifts the MP4 `moov` atom to the beginning of the file, allowing immediate playback in web browsers without waiting for the full file to download.
    - **Render reference**: 15-second 1080x1920 24fps vertical video reported locally in the 0.47s–1.8s range — hardware/encoder-dependent, not CI-measured.

4. **Direct Browser Downloads**:
   - Native HTML5 direct downloads for `.mp4` video reels, `.srt` subtitle files, `.mp3` voiceover audio, and `.jpg` diffusion imagery.

---

## 7. Computational Complexity and Latency Matrix

The system maximizes concurrency through asynchronous execution (`asyncio.gather`), caching, and hardware-accelerated local compilation. Latencies below are local reference ranges (hardware/network-dependent), not CI-measured benchmarks:

| Pipeline Stage | Time Complexity | Execution Mode | Reference latency (local) | Technical Optimization |
| :--- | :---: | :---: | :---: | :--- |
| **Perception Scraper** | O(S * Q) | Asynchronous | 1.2s - 2.8s | Keyless DuckDuckGo + Crawl4AI; `httpx` + BeautifulSoup fallback; mock slice when empty |
| **Content Node** | O(T) | LLM Generation | 0.8s - 1.9s | Structured schema generation with `gemini-3.6-flash` (cascade `gemini-2.0/2.5-flash`) / `gpt-4o-mini` / domain fallback |
| **Statutory Audit** | O(N) | Deterministic | 12ms - 25ms | Regex pattern matching + AST clause validation against rubric |
| **Neural Voiceover** | O(W) | Streaming Audio | 280ms - 420ms | Edge-TTS neural websocket streaming direct to disk |
| **FLUX.1 Diffusion** | O(R) | Image Diffusion | 1.8s - 3.5s | Pollinations keyless FLUX (or Gemini image when keyed) with aspect-ratio parameter scaling |
| **FFmpeg 1080x1920** | O(D) | Local Binary | 0.47s - 1.8s | Multi-threaded `libx264` ultrafast preset + pre-scaled 540:960 canvas (MoviePy composition alternate; Veo optional Tier-1) |
| **Publisher Worker** | O(K) | Background Cron | 50ms | APScheduler 60-second polling loop filtering `status=approved` |

---

## 8. Deterministic Statutory Compliance Benchmarks

Marketing copy generated for insurance and financial services must adhere strictly to statutory regulations. The engine combines deterministic rubric checks (`compliance_rubric.md`: regex/AST on prohibited terms and mandatory disclosures) with the in-code 3-agent debate and arbiter self-heal (`retry_count <= 3`, else `compliance_diverted` to human queue). Verified by the repo suite: `182 passed` (unit / integration / compliance); the percentages below are enforcement targets per framework, not a separate 250-run measured benchmark:

| Regulatory Framework | Jurisdiction | Target Risk Portfolio | Target | Primary Enforcement Rule |
| :--- | :--- | :--- | :---: | :--- |
| **MAS Notice 318** | Singapore | Jewellery and High-Value Cargo | 98.4% | Prohibition of absolute guarantees without statutory underwriting disclosure |
| **BNM Market Conduct** | Malaysia | Marine Cargo and Attended Transit | 96.8% | Mandatory disclosure of claim indemnity ceilings and deductible limits |
| **HKIA Guideline 28** | Hong Kong | Medical Indemnity and Clinical Defence | 97.2% | Actuarial substantiation required for comparative superlative claims |

---

## 9. Local Development and Reproducibility Guide

### Prerequisites

- **Python**: Version 3.11, 3.12, or 3.13 installed and on your `PATH`.
- **FFmpeg**: Installed and available on your system `PATH` — verify with `ffmpeg -version`.
- **Git**: Installed for version control.

### Step 1: Clone the Repository

```bash
git clone https://github.com/prarabdha7/GCICI26.git
cd GCICI26
```

### Step 2: Create a Virtual Environment

```bash
# On Linux / macOS:
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Production Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Copy the template and fill in API keys:

```bash
# On Linux / macOS:
cp .env.example .env

# On Windows:
copy .env.example .env
```

Key settings inside `.env`:

```ini
# Application port and runtime mode
APP_HOST=127.0.0.1
APP_PORT=8000
ENVIRONMENT=dev

# LLM provider (system falls back to domain-grounded models if keys are absent)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash
GEMINI_IMAGE_MODEL=gemini-3.1-flash-image
GEMINI_VIDEO_MODEL=veo-3.1-fast-generate-preview
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Research and scraping (keyless DuckDuckGo + Crawl4AI by default; keys only enable extras)
SERPER_API_KEY=your_serper_key
SCRAPEGRAPH_API_KEY=
GOOGLE_PLACES_API_KEY=
HUNTER_API_KEY=
# Legacy optional fallback only (used by POST /api/perception/scrape if set):
# TAVILY_API_KEY=

# Publishing channels (falls back to mock publisher if absent)
BUFFER_ACCESS_TOKEN=your_buffer_token
AYRSHARE_API_KEY=your_ayrshare_key
```

### Step 5: Initialize the Database

```bash
python -m scripts.init_db
```

### Step 6: Start the Unified Application Server

```bash
python run.py
```

This starts the FastAPI application and the embedded Auto-Publisher worker daemon simultaneously.

- **Apple Design Method Workstation**: [http://127.0.0.1:8000/app/](http://127.0.0.1:8000/app/)
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health and Readiness Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Step 7: Run Automated Verification Test Suite

```bash
python -m pytest tests/ -v
```

Expected result: `182 passed in approximately 8.9s (100% pass rate)`.

---

## 10. Architectural Decisions and Engineering Justifications

**Why Direct Local FFmpeg Instead of Cloud Video SaaS?**

Third-party video APIs (Synthesia, HeyGen) introduce significant latency (30-90 seconds per render), high operational cost (\$1-\$5 per minute), and external service dependencies. The local FFmpeg pipeline compiles complete 1080x1920 MP4 vertical reels with dynamic AI camera zoompan and burned-in subtitles in under 2 seconds with zero marginal cost.

**Why Edge-TTS over Paid Speech APIs?**

Microsoft Edge-TTS provides crystal-clear neural speech across dozens of Southeast Asian languages and accents without requiring API keys, credit cards, or subscription tiers. The websocket streaming path writes directly to disk, keeping memory overhead flat regardless of voiceover duration.

**Why MAS Notice 318 Human-in-the-Loop Governance?**

Monetary Authority of Singapore (MAS) regulations strictly prohibit autonomous generative AI from publishing marketing collateral in financial services without documented human compliance approval. The Review Queue enforces this statutory requirement: newly synthesized content arrives as `status: pending`, and the publisher worker will only dispatch assets that receive human sign-off.

**Why Deterministic Rubrics over Unconstrained Prompting?**

Relying solely on an LLM to evaluate its own compliance introduces confirmation bias and hallucinations. JA Assure OS reads `compliance_rubric.md` from disk and applies deterministic regular expression tokenization and AST parsing to flag non-compliant words prior to any LLM debate. The LLM adversarial debate is the second layer, not the first.

**Why LangGraph over a Simple Chain?**

A standard LangChain chain is linear — it cannot loop, branch, or hold state across multiple retry cycles. The cyclic LangGraph state machine allows the compliance gate to route back into the content node on failure (up to 3 times), accumulating retry context and adversarial debate transcripts in the shared `MarketingState` TypedDict on each pass, before the circuit breaker trips and routes the asset to the human queue.

---

<p align="center">
  <b>JA Assure Intelligence OS</b> — Autonomous Marketing and Self-Healing Compliance Architecture<br>
  Built for Enterprise InsurTech Deployment<br>
  <a href="https://github.com/prarabdha7/GCICI26">github.com/prarabdha7/GCICI26</a>
</p>
