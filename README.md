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
integration (with a mock-safe fallback for zero-key demos). Nothing
publishes without a human approving it first.

Full diagrams and a live-pitch script: [`docs/architecture.md`](docs/architecture.md)
and [`docs/demo_runbook.md`](docs/demo_runbook.md).

---

## Architecture highlights

- **Cyclic, not linear.** The content pipeline is a real LangGraph state
  machine with a retry loop and a circuit breaker (`retry_count > 3` routes
  to manual review) — not a one-shot prompt chain.
- **Closed-loop memory.** Every human rejection/edit becomes a
  `feedback_memory` row; the content agent's system prompt is grounded in the
  last 5 relevant notes before it ever writes a new draft.
- **Compliance is data, not code.** The compliance gate is grounded in
  `compliance_rubric.md` (now covering MAS/BNM/HKIA/OIC/OJK jurisdictional
  schedules), read from disk on every call — the rubric changes without
  touching a line of Python.
- **Swappable everything external.** Search, place discovery, and social
  publishing each sit behind one interface with 2+ implementations, selected
  automatically by whichever `.env` key is present.
- **Zero-key fallback mode.** No `GEMINI_API_KEY`? Domain-knowledge fallback
  copy + a heuristic compliance gate. No search/scrape keys? Mock
  search/discovery. No publisher keys? `MockPublisher` simulates the full
  `approved → scheduled → published` lifecycle with engagement metrics — the
  whole demo runs with an empty `.env`.
- **Zero-cost media pipeline.** Voiceover via `edge-tts`, assembly via
  `moviepy` — no paid video API.

## Tech stack

| Concern | Choice |
| --- | --- |
| Backend | Python 3.13, FastAPI |
| Orchestration | LangGraph — cyclic state machine with checkpointing |
| LLM | Gemini (default) or OpenAI, behind one provider-agnostic client, with an offline fallback |
| Database | SQLAlchemy + SQLite (dev) → PostgreSQL (prod), one env var |
| Review UI | FastAPI + Jinja2 + HTMX + PicoCSS, no build step |
| Voiceover | `edge-tts` — free, multilingual |
| Video | `moviepy` (pinned `<2.0`) + `ffmpeg` |
| Research / leads | Tavily, Serper, ScrapeGraphAI, Google Places, Hunter.io — swappable |
| Scheduler | APScheduler |
| Publishing | Buffer or Ayrshare — swappable, with a mock fallback |

## Quickstart

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # keys OPTIONAL — fallback + mock publisher cover demos
python -m scripts.init_db     # creates content_queue, feedback_memory, leads
python -m scripts.seed_demo   # optional: realistic demo data for the dashboard

uvicorn app.main:app --reload
```

Or, for a single zero-key command that also starts the auto-publisher worker:

```bash
python run.py
```

- Dashboard: http://127.0.0.1:8000/dashboard (Generate Campaign, Newsjack, approve/edit/reject, video preview)
- Metrics: http://127.0.0.1:8000/dashboard/metrics (rejection rate, edit distance, learning-curve trend chart, lessons)
- Health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

To run the auto-publisher worker as its own process instead (`run_demo.sh` does this for you, plus seeding):

```bash
python -m worker.scheduler
```

## Zero-key fallback design

- No `GEMINI_API_KEY`? Domain-knowledge fallback copy per brand + a heuristic compliance gate.
- No `TAVILY`/`SCRAPE`/`HUNTER` keys? Mock search/discovery/scraper with baked-in JA Assure intel.
- No `BUFFER`/`AYRSHARE` keys? `MockPublisher` simulates `approved → scheduled → published` with engagement metrics.
- Video works with no footage: brand-tinted reel + caption card + `edge-tts` voiceover.

For the full live-pitch walkthrough (including ngrok setup for public media
URLs), see [`docs/demo_runbook.md`](docs/demo_runbook.md).

## Running the tests

```bash
pytest tests/ -v
```

All tests run against an isolated in-memory database (`tests/conftest.py`) —
they never touch your local `ja_assure.db`, and every external HTTP call
(Gemini's compliance/content calls aside, which are mocked too) is mocked.
As of this writing: 115 tests, all green, covering every phase below.

## What's built

| Area | Covered by |
| --- | --- |
| Content pipeline (state machine, retry, circuit breaker) | `app/graph/`, `app/agents/` |
| Closed-loop memory | `app/memory/` |
| Zero-key LLM fallback + heuristic gate + self-heal | `app/llm/fallback.py` |
| Brand voices, colors, jurisdictions | `app/agents/brand_knowledge.py` |
| Zero-cost video assembly | `app/media/assembly.py` |
| Research & lead generation (swappable providers) | `app/agents/providers.py`, `app/agents/research.py`, `app/agents/leads.py` |
| Human review dashboard | `app/api/dashboard.py`, `app/templates/` |
| Auto-publisher, incl. MockPublisher + analytics (Project 2) | `worker/` |
| Architecture diagrams | `docs/architecture.md` |
| Live demo script | `docs/demo_runbook.md` |
| Regulatory rules, incl. MAS/BNM/HKIA/OIC/OJK schedules (loaded at runtime) | `compliance_rubric.md` |
