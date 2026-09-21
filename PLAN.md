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
| 1 | Foundation — repo, FastAPI, database schema | `main` | `[x]` verified locally, committed |
| 2 | LangGraph state machine and core agents | `main` | `[x]` merged via PR #1 |
| 3 | Closed-loop memory engine | `feature/memory-engine` | `[~]` retrieval + injection built, awaiting review |
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
- [x] Verified locally: `pip install -r requirements.txt`, `python -m scripts.init_db`
      and `pytest tests/ -v` all pass (14/14 Phase 1 tests green) in a `venv` on the
      owner's machine — the sandbox's PyPI egress block no longer applies.
- [x] **PHASE 1 SIGNED OFF** — committed to `main` as
      `feat: initialize phase 1 architecture, database schema, and test suite`

**Notes:** SQLite for development via a single `DATABASE_URL`; switching to
PostgreSQL for the demo is a one-line env change. Three tables only — 
`research_digest` lands in Phase 5, publishing columns are already present on
`content_queue` so Project 2 needs no migration.

---

## Phase 2 — LangGraph state machine and core agents

**Goal:** the cyclic pipeline runs end to end and writes a row to `content_queue`.
**Depends on:** Phase 1.

- [x] `app/graph/state.py` — `MarketingState` TypedDict (core fields: `draft_content`,
      `brand`, `platform`, `language`, `compliance_errors`, `retry_count`); additive
      fields (`topic`, `content_type`, `research_notes`, `feedback_guidance`,
      `media_path`, `status`, `content_id`) land with the phases that need them
- [x] `app/agents/prompts.py` — brand voice cards for Jade, Jaguar Transit, DoctorShield
      and prompt builders for the content, localization and compliance agents
- [ ] `research_node` — deferred; not in this phase's scope, needed before Phase 5
- [x] `content_node` — per-brand, per-platform generation (single-format for now;
      multi-format/A-B variants deferred to a later pass)
- [x] `localization_node` — tone and cultural adaptation, branches on `language`
- [x] `compliance_gate_node` — structured `{is_compliant, violations}`, temperature 0,
      loads `compliance_rubric.md` from disk on every call
- [x] `route_after_compliance` — conditional edge: pass → END, fail → content
      (persist_node lands in a later phase; compliant drafts end the graph for now)
- [x] Circuit breaker — `retry_count > settings.max_compliance_retries` (3) routes to
      `manual_intervention`
- [x] Previous `compliance_errors` injected into the rewrite prompt on every cycle
- [ ] `persist_node` — deferred; no `content_queue` row is written yet, so
      `manual_intervention_node` is currently a logging-only terminal node
- [x] Graph compiled with a checkpointer (`MemorySaver`, swappable); every node and
      the routing decision logs `brand`, `retry_count`, and violations
- [x] Verified: `tests/test_phase2.py` — 11/11 passing, including a deliberately
      always-non-compliant draft that cycles exactly `max_retries + 1` times and
      then trips the breaker into `manual_intervention` without looping forever
- [x] **MERGED** — PR #1, squash-merged to `main` (`f4db61b`). `research_node`
      and `persist_node` remain deferred; `memory_retrieval_node` landed in
      Phase 3 instead.

---

## Phase 3 — Closed-loop memory engine

**Goal:** the system demonstrably stops repeating a mistake a human flagged.
**Depends on:** Phase 2.

- [ ] `app/memory/store.py` — write a `feedback_memory` row on every reject/edit;
      deferred, this needs the review dashboard's reject/edit action (Phase 6)
- [x] `app/memory/retrieval.py` — `get_recent_feedback()`, top N (default
      `settings.feedback_memory_limit` = 5) most recent notes for `brand` + `platform`
- [x] `memory_retrieval_node` wired in **before** `content_node`; retry cycles
      loop back to `content_node` directly and do not re-run retrieval
- [x] Exact injection contract implemented in `format_guidance()`:
      `CRITICAL GUIDANCE: Previously, human reviewers rejected content for this brand due to: {fetched_notes}. You MUST NOT repeat these mistakes.`
- [x] No guidance block injected when there is no feedback yet (`format_guidance([])`
      returns `""`, and `content_system_prompt` only appends a non-empty block)
- [ ] Controlled `error_tag` vocabulary — already defined as `ErrorTag` in
      `app/db/models.py`; UI enforcement is Phase 6's job
- [ ] Metrics: rejection rate over time, retries per asset, human edit distance —
      deferred to the review dashboard (Phase 6)
- [x] Verified: `tests/test_phase3.py` — 14/14 passing, covering retrieval
      filtering/ordering/limits, the exact injection string, and a full graph
      run proving `memory_retrieval_node` populates `feedback_guidance` before
      `content_node` reads it
- [ ] **PAUSED FOR REVIEW** — `app/memory/store.py`, the `error_tag` UI, and the
      metrics panel are intentionally deferred to Phase 6 (they need the review
      dashboard's reject/edit action to exist). Awaiting sign-off before Phase 4.

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
