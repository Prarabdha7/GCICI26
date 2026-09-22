# JA Assure — AI Marketing System

A multi-agent marketing system for **JA Assure**, a Singapore-based niche
InsurTech with three brands — **Jade** (jewellers block), **Jaguar Transit**
(high-value goods transit), **DoctorShield** (medical indemnity) — operating
across Singapore, Malaysia, Hong Kong, Indonesia and Thailand.

**Project 1 — the Brain (required):** a cyclic LangGraph state machine
researches, writes, localises, renders video and compliance-gates every
asset. A failure routes back to the content agent with the specific
violations attached; a circuit breaker diverts a stubborn draft to a
manual-review queue instead of looping forever. A human approves, edits, or
rejects from a review dashboard — and **every rejection is stored and
injected into the next generation**, so the system measurably stops
repeating the same mistake.

**Project 2 — the Hands (bonus):** a background worker polls the approved
queue and publishes automatically through a swappable Buffer/Ayrshare
integration (with a labeled mock dispatcher for keyless walkthroughs).
Nothing publishes without a human approving it first.

Full diagrams and a live-pitch script: [`docs/architecture.md`](docs/architecture.md)
and [`docs/demo_runbook.md`](docs/demo_runbook.md).

---

## Architecture highlights

- **Cyclic, not linear.** The content pipeline is a real LangGraph state
  machine with live market research, a retry loop and a circuit breaker
  (`retry_count > 3` routes to manual review) — not a one-shot prompt chain.
- **Closed-loop memory.** Every human rejection/edit becomes a
  `feedback_memory` row; the content agent's system prompt is grounded in the
  last 5 relevant notes before it ever writes a new draft.
- **Compliance is data, not code.** The compliance gate is grounded in
  `compliance_rubric.md` (now covering MAS/BNM/HKIA/OIC/OJK jurisdictional
  schedules), read from disk on every call — the rubric changes without
  touching a line of Python.
- **Keyless live research.** Competitor/market context comes from DuckDuckGo +
  Crawl4AI scraping (`app/utils/research.py`) — no search API key, no quota.
  Discovery/enrichment (Google Places, Hunter.io) and publishing
  (Buffer/Ayrshare) remain swappable by whichever `.env` key is present.
- **Real by default, labeled demo on demand.** Unconfigured stages fail
  honestly instead of fabricating. With `DEMO_MODE=true`, domain-knowledge
  fallback copy, mock providers/publisher, stub reels and seed rows engage —
  all tagged `[DEMO]` / `mock-` / `is_demo` and excluded from real metrics.
- **Zero-cost media pipeline.** Voiceover via `edge-tts`, assembly via
  `moviepy` — no paid video API.

## Tech stack

| Concern | Choice |
| --- | --- |
| Backend | Python 3.13, FastAPI |
| Orchestration | LangGraph — cyclic state machine with checkpointing |
| LLM | Gemini (default, `gemini-3.6-flash`) or OpenAI, behind one provider-agnostic client |
| Database | SQLAlchemy + SQLite (dev) → PostgreSQL (prod), one env var |
| Review UI | FastAPI + Jinja2 + HTMX + PicoCSS, no build step — plus a static SPA at `/app` on the JSON actions API |
| Voiceover | `edge-tts` — free, multilingual |
| Video | `moviepy` (pinned `<2.0`) + `ffmpeg` |
| Research | DuckDuckGo + Crawl4AI (keyless, live) |
| Discovery / enrichment | Google Places, Hunter.io — swappable, keyed |
| Scheduler | APScheduler (embedded in API, or standalone `python -m worker.scheduler`) |
| Publishing | Buffer or Ayrshare — swappable, with a labeled mock dispatcher for demos |

## Quickstart

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # add GEMINI_API_KEY + BUFFER/AYRSHARE keys for the real path
python -m scripts.init_db     # creates content_queue, feedback_memory, leads
python -m scripts.seed_demo   # DEMO_MODE=true only: labeled walkthrough rows

uvicorn app.main:app --reload
```

Or, for a single command that also starts the embedded auto-publisher worker:

```bash
python run.py
```

- New console: http://127.0.0.1:8000/app (queue, detail, generate, metrics, leads)
- Legacy dashboard: http://127.0.0.1:8000/dashboard (Generate Campaign, Newsjack, approve/edit/reject, video preview)
- Metrics: http://127.0.0.1:8000/dashboard/metrics (rejection rate, edit distance, learning-curve trend chart, lessons)
- Health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

To run the auto-publisher worker as its own process instead (`run_demo.sh` does this for you, plus seeding):

```bash
python -m worker.scheduler
```

## Real vs demo contract

- **Default (`DEMO_MODE=false`) is real-only.** Unconfigured LLM / providers / publisher fail
  honestly with a clear message — nothing is fabricated, stubbed, or counted.
  `GET /api/stats` and `/api/metrics/trend` exclude demo rows; the worker never
  confirms real `scheduled` rows without a real webhook (`POST /api/publish/webhook`).
- **Demo (`DEMO_MODE=true`) is for walkthroughs without keys.** Fallback copy, mock
  providers/publisher, stub reels, and `python -m scripts.seed_demo` engage — and every
  output is labeled: `[DEMO]` copy prefix, `mock-` post IDs, `provider='mock-demo'`,
  `is_demo=true` rows, DEMO badges in the dashboard. Demo rows never enter real metrics.
- Simulated writes exist **only** to demonstrate how the pipeline works. They are never
  used for, mixed into, or claimed as real results.
- Sample content (mock intel, personas, seed rows) lives machine-local in `local/`
  (gitignored; see `local/samples.example.json` for the shape). The repo ships zero
  baked-in samples — without that file the app runs real-only and says so honestly.

## Demo (3 min)

1. Dashboard → Generate Campaign (DoctorShield / Hong Kong) → compliant draft persists with adversarial transcript + healed rewrite.
2. Queue detail → LinkedIn/X previews, reel player with SRT + captions JSON, redline diff, multi-format pack (thread/carousel/A-B/focus group), Accept self-healing fix.
3. Metrics → rejection/edit-distance trend chart + lessons proves closed-loop learning (`/api/metrics/trend`).
4. Approve → worker publishes (mock ID in demo, real post ID with keys) → scheduled → published with analytics (`/api/publish/events/{id}` + webhook at `/api/publish/webhook`).
5. Newsjack → live Crawl4AI research + Generate turns competitor intel into a campaign; intel sweep runs every 6h.

For the full live-pitch walkthrough (including ngrok setup for public media
URLs), see [`docs/demo_runbook.md`](docs/demo_runbook.md).

## Running the tests

```bash
pytest tests/ -v
```

All tests run against an isolated in-memory database (`tests/conftest.py`) with
keys blanked and live research auto-mocked — they never touch your local
`ja_assure.db`, your `.env` keys, or the network.

## What's built

| Area | Covered by |
| --- | --- |
| Content pipeline (research, state machine, retry, circuit breaker) | `app/graph/`, `app/agents/`, `app/utils/research.py` |
| Closed-loop memory | `app/memory/` |
| Heuristic gate + self-heal + demo-gated domain fallback | `app/llm/fallback.py` |
| Brand voices, colors, jurisdictions | `app/agents/brand_knowledge.py` |
| Multi-format pack (thread/carousel/A-B/video script) | `app/agents/formats.py` |
| Zero-cost video assembly | `app/media/assembly.py` |
| Discovery / enrichment (swappable providers) | `app/agents/providers.py`, `app/agents/leads.py` |
| Human review dashboard + JSON actions API + static console | `app/api/`, `app/templates/`, `frontend/` |
| Auto-publisher, incl. labeled mock dispatcher + analytics (Project 2) | `worker/` |
| Demo seed (labeled, DEMO-gated) | `scripts/seed_demo.py` |
| Architecture diagrams | `docs/architecture.md` |
| Live demo script | `docs/demo_runbook.md` |
| Regulatory rules, incl. MAS/BNM/HKIA/OIC/OJK schedules (loaded at runtime) | `compliance_rubric.md` |
