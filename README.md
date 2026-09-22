# JA Assure — AI Marketing System

A multi-agent marketing system for **JA Assure**, a Singapore-based niche InsurTech
(brands: **Jade**, **Jaguar Transit**, **DoctorShield**) operating across Singapore,
Malaysia, Hong Kong, Indonesia and Thailand.

A **LangGraph state machine** researches, writes, localises and compliance-gates
every asset; failures cycle back for a rewrite with the violations attached, and a
circuit breaker diverts stubborn drafts to a manual queue. A human approves, edits
or rejects — and **every rejection is stored and injected into the next generation**,
so the system stops repeating mistakes. Approved assets are published automatically
by a background worker.

> Status: **Phase 1 complete** — see `PLAN.md` for the full roadmap and everything
> `CLAUDE.md` for the architecture of record.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then add your GEMINI_API_KEY
python -m scripts.init_db     # creates content_queue, feedback_memory, leads

uvicorn app.main:app --reload
```

- Health check: http://127.0.0.1:8000/health
- API docs: http://127.0.0.1:8000/docs

## Documentation

| File | What it holds |
| --- | --- |
| `CLAUDE.md` | Architecture of record, git policy, coding standards |
| `PLAN.md` | Phased execution tracker — kept current as work lands |
| `compliance_rubric.md` | Regulatory rules, loaded at runtime by the compliance gate |
