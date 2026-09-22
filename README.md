# JA Assure — AI Marketing System

A multi-agent marketing system for **JA Assure**, a Singapore-based niche InsurTech
(brands: **Jade**, **Jaguar Transit**, **DoctorShield**) operating across Singapore,
Malaysia, Hong Kong, Indonesia and Thailand.

A **LangGraph state machine** researches, writes, localises, renders video and
compliance-gates every asset; failures cycle back for a rewrite with the violations
attached, and a circuit breaker diverts stubborn drafts to a manual queue. A human
approves, edits or rejects — and **every rejection is stored and injected into the
next generation**, so the system stops repeating mistakes. Approved assets are
published automatically by a background worker (mock-safe with no keys).

> Status: **All phases complete (1-7)** — zero-key demo mode works out of the box.
> See `PLAN.md` / `MASTER_ANALYSIS_AND_UPGRADE_PLAN.md` for the blueprint.

## Quick start (zero-key, 1 command)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # keys OPTIONAL — fallback + mock publisher cover demos
python run.py                 # init_db + FastAPI + APScheduler worker
```

- Dashboard: http://127.0.0.1:8000/dashboard (Generate Campaign, approve/edit/reject, video preview)
- Metrics: http://127.0.0.1:8000/dashboard/metrics (rejection rate, edit distance, lessons)
- Health: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

## Zero-failure design

- No `GEMINI_API_KEY`? Domain fallback copy per brand + heuristic compliance gate.
- No `TAVILY/SCRAPE/HUNTER` keys? Mock search/discovery/scraper with JA Assure intel.
- No `BUFFER/AYRSHARE` keys? `MockPublisher` simulates `approved->scheduled->published` + engagement.
- Video works with no footage: brand-tinted reel + Pillow caption card + edge-tts voiceover.

## Demo (3 min)

1. Dashboard → Generate Campaign (DoctorShield / Hong Kong) → compliant draft persists with adversarial transcript + healed rewrite.
2. Queue detail → LinkedIn/X previews, reel player with SRT + captions JSON, redline diff, multi-format pack (thread/carousel/A-B/focus group), Accept self-healing fix.
3. Metrics → rejection/edit-distance trend chart + lessons proves closed-loop learning (`/api/metrics/trend`).
4. Approve → worker publishes (mock ID) → scheduled → published with analytics (`/api/publish/events/{id}` + webhook at `/api/publish/webhook`).
5. Newsjack → Research + Generate turns competitor intel into a campaign; intel sweep runs every 6h.

## Documentation

| File | What it holds |
| --- | --- |
| `PLAN.md` | Phased execution tracker + upgrade blueprint |
| `compliance_rubric.md` | Regulatory rules incl. MAS/BNM/HKIA/OIC/OJK schedules |
| `app/agents/brand_knowledge.py` | Brand voices, colors, jurisdictions |
| `app/llm/fallback.py` | Domain fallback + heuristic gate + self-heal |
| `worker/publisher.py` | Buffer/Ayrshare + MockPublisher + analytics |
