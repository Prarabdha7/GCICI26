# PLAN.md — Execution Tracker

**Project:** AI Marketing System for JA Assure (JA Assure Hackathon)
**Architecture:** see `CLAUDE.md` — read it before starting any phase.

> **How to use this file.** Read it before starting a step. Update it the moment
> a step completes: tick the box, and add a one-line note under the phase saying
> what actually landed. A stale plan is worse than no plan.

**Legend:** `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

---

## Status at a glance

| Phase | Title | Branch | Status |
| --- | --- | --- | --- |
| 1 | Foundation — repo, FastAPI, database schema | `feature/foundation` | `[~]` built, awaiting local run + review |
| 2 | LangGraph state machine and core agents | `feature/core-graph` | `[ ]` |
| 3 | Closed-loop memory engine | `feature/memory-engine` | `[ ]` |
| 4 | Video assembly pipeline | `feature/video-pipeline` | `[ ]` |
| 5 | Lead generation and research scraping | `feature/lead-gen` | `[ ]` |
| 6 | Human review dashboard | `feature/review-ui` | `[ ]` |
| 7 | Project 2 — auto-publisher worker (bonus) | `feature/auto-publisher` | `[ ]` |
| 8 | Documentation, diagrams, demo seed data | `feature/docs-demo` | `[ ]` |

---

## Phase 1 — Foundation: repo init, FastAPI, database schema

**Goal:** a repository that installs, initialises a database, and serves a health
endpoint. Everything later hangs off this.

- [x] Repository initialised, `main` branch, remote configured
- [x] `CLAUDE.md` — rules and architecture blueprint
- [x] `PLAN.md` — this tracker
- [x] `compliance_rubric.md` — placeholder awaiting regulatory guidelines
- [x] `.gitignore` — excludes `.env`, `*.db`, `assets/generated/`, venvs
- [x] `.env.example` — every required variable, empty values, no secrets
- [x] `requirements.txt` — dependencies grouped by phase
- [x] Package tree under `app/` with placeholders for later phases
- [x] `app/config.py` — env-driven settings via pydantic-settings
- [x] `app/db/database.py` — SQLAlchemy engine and session dependency
- [x] `app/db/models.py` — `content_queue`, `feedback_memory`, `leads`
- [x] `app/llm/client.py` — provider-agnostic `structured_call()` skeleton
- [x] `app/main.py` — FastAPI app, health endpoint, lifespan DB init
- [x] `scripts/init_db.py` — create-all bootstrap
- [x] `tests/test_phase1.py` — smoke tests for settings, gate schema, API models
- [x] Verified: all 17 modules compile; settings, the compliance-gate schema contract
      and the API response models pass their unit checks
- [!] **Not yet verified: `pip install`, `init_db`, `/health`.** PyPI is unreachable
      from the sandbox this was built in (egress policy returns 403), so FastAPI and
      SQLAlchemy could not be imported. Run this locally to close it out:
      ```bash
      python3 -m venv .venv && source .venv/bin/activate
      pip install -r requirements.txt
      python -m scripts.init_db
      pytest tests/ -v
      uvicorn app.main:app --reload   # then GET /health
      ```
- [ ] **PAUSED FOR REVIEW** — awaiting sign-off before Phase 2

**Environment note:** the Cowork sandbox cannot unlink files in this folder, so a
stale `.git/index.lock` keeps reappearing and `_to_delete/` holds two dead files.
Both are harmless and git-ignored. Clear them from your own terminal:
`rm -f .git/index.lock && rm -rf _to_delete`

**Notes:** SQLite for development via a single `DATABASE_URL`; switching to
PostgreSQL for the demo is a one-line env change. Three tables only — 
`research_digest` lands in Phase 5, publishing columns are already present on
`content_queue` so Project 2 needs no migration.

---

## Phase 2 — LangGraph state machine and core agents

**Goal:** the cyclic pipeline runs end to end and writes a row to `content_queue`.
**Depends on:** Phase 1.

- [ ] `app/graph/state.py` — `MarketingState` TypedDict
- [ ] `app/agents/prompts.py` — brand voice cards for Jade, Jaguar Transit, DoctorShield
- [ ] `research_node` — competitor/market intel for the seed topic
- [ ] `content_node` — per-brand, per-platform generation; multi-format (post → carousel → thread → caption) with A/B variants
- [ ] `localization_node` — tone and cultural adaptation across `en`/`ms`/`id`/`th`/`zh`
- [ ] `compliance_gate_node` — structured `{is_compliant, violations}`, temperature 0, grounded in `compliance_rubric.md`
- [ ] `route_after_compliance` — conditional edge: pass → persist, fail → content
- [ ] Circuit breaker — `retry_count > 3` routes to `manual_intervention`
- [ ] Previous `compliance_errors` injected into the rewrite prompt on every cycle
- [ ] `persist_node` — writes the row with `status = pending`
- [ ] Graph compiled with a checkpointer; state transitions logged
- [ ] Verified: a deliberately non-compliant draft cycles, then trips the breaker

---

## Phase 3 — Closed-loop memory engine

**Goal:** the system demonstrably stops repeating a mistake a human flagged.
**Depends on:** Phase 2.

- [ ] `app/memory/store.py` — write a `feedback_memory` row on every reject/edit
- [ ] `app/memory/retrieval.py` — top 5 most recent notes for `brand` + `platform`
- [ ] `memory_retrieval_node` wired in **before** `content_node`
- [ ] Exact injection contract: `CRITICAL GUIDANCE: Previously, human reviewers rejected content for this brand due to: {fetched_notes}. You MUST NOT repeat these mistakes.`
- [ ] No guidance block injected when there is no feedback yet
- [ ] Controlled `error_tag` vocabulary defined and enforced in the UI
- [ ] Metrics: rejection rate over time, retries per asset, human edit distance
- [ ] Verified: reject for "too salesy", re-run, confirm the next draft changes

---

## Phase 4 — Video assembly pipeline (zero cost)

**Goal:** a real MP4 reel with voiceover, assembled locally, no paid API.
**Depends on:** Phase 2.

- [ ] Script generation — spoken VO script alongside the caption
- [ ] `app/media/tts.py` — `edge-tts` synthesis, voice selected by `language`
- [ ] `app/media/video.py` — `VideoFileClip` + `.set_audio()`, trimmed to audio duration
- [ ] Background clips committed to `assets/video/`; output to `assets/generated/`
- [ ] `media_path` written back to `content_queue`
- [ ] `ffmpeg` availability checked at startup with a clear error if missing
- [ ] Verified: end-to-end reel renders and plays, in at least two languages

---

## Phase 5 — Lead generation and research scraping

**Goal:** real prospects found, scored and drafted for outreach.
**Depends on:** Phase 1 (`leads` table), Phase 2 (LLM client).

- [ ] Scraping layer with ScrapeGraphAI or Crawl4AI
- [ ] Competitor intelligence — monitor sites/pricing/public posts, produce a periodic digest
- [ ] `research_digest` table for digest history
- [ ] Prospect discovery: jewellers, clinics/doctors, SMEs, couriers across the five markets
- [ ] Enrichment — company, contact, website, segment, country
- [ ] Fit scoring with a written rationale per lead
- [ ] Personalised outreach drafts routed through the same human approval step
- [ ] Respect robots.txt, rate limits and provider terms; log every source URL
- [ ] Verified: a live run returns scored leads with citations

---

## Phase 6 — Human review dashboard

**Goal:** the human-in-the-loop step, and the UI that closes the feedback loop.
**Depends on:** Phase 2, Phase 3.

- [ ] Queue view — filter by brand, platform, language, status
- [ ] Detail view — draft, localised copy, compliance verdict, violation list, media preview
- [ ] **Approve** → `status = approved` (the contract row for Project 2)
- [ ] **Edit** → save `final_content`, write a `feedback_memory` row
- [ ] **Reject** → capture `error_tag` + `human_note`, write a `feedback_memory` row
- [ ] Manual-intervention queue for circuit-breaker casualties
- [ ] Metrics panel — rejection rate, retries, edit distance over time
- [ ] Verified: reject in the UI → row in `feedback_memory` → next run reflects it

---

## Phase 7 — Project 2: auto-publisher worker (bonus)

**Goal:** approved assets publish themselves. Nothing publishes without approval.
**Depends on:** Phase 6.

- [ ] APScheduler worker polling `status = 'approved'` and not yet sent
- [ ] Publisher client — Buffer (GraphQL `createPost`) or Ayrshare
- [ ] Store the returned post ID; flip `status` to `scheduled`
- [ ] Fan-out to Instagram, LinkedIn, X, TikTok
- [ ] Media served at a public URL for the posting API
- [ ] Analytics step — pull engagement back into the database
- [ ] Idempotency and retry with backoff; failures never silently drop a row
- [ ] Demo/test social accounts configured
- [ ] Verified: generate → approve → post, observed live

---

## Phase 8 — Documentation, diagrams and demo seed data

**Goal:** a judge can clone, run, and understand it in ten minutes.
**Depends on:** all phases.

- [ ] `README.md` — what it is, setup, run, demo script
- [ ] Architecture diagram — graph topology and both feedback loops
- [ ] Sequence diagram — the compliance retry cycle and circuit breaker
- [ ] `scripts/seed_demo.py` — pre-loaded feedback history so the loop is visible immediately
- [ ] Demo runbook — the exact click path for the live walkthrough
- [ ] Evidence of improvement — before/after metrics from the feedback loop
- [ ] Final pass: no hard-coded secrets, clean repo, all tests green
