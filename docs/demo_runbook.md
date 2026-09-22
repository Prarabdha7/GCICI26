# Demo Runbook

A ten-minute live walkthrough. Run the setup once before judges arrive; the
click-through itself takes about five minutes.

---

## 0. Setup (before judges arrive)

```bash
# from the repo root
source venv/bin/activate          # or: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python -m scripts.init_db          # creates the schema if it doesn't exist yet
python -m scripts.seed_demo        # loads realistic pending/approved/manual-intervention rows, feedback history, and leads
```

Confirm `.env` has at minimum `GEMINI_API_KEY` set (needed for the live-generation
part of the demo) and, if you want to show the auto-publisher actually
scheduling a post, one of `BUFFER_ACCESS_TOKEN` / `AYRSHARE_API_KEY`.

**Terminal 1 — the API + dashboard:**

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` once to confirm `rubric_loaded: true` and
`llm_configured: true` before you start.

**Terminal 2 — the auto-publisher worker (Project 2, bonus):**

```bash
python -m worker.scheduler
```

Leave this running in the background for the whole demo — it polls every
`PUBLISH_POLL_INTERVAL` seconds (60 by default) and is what proves Project 2
is a real, live process, not a slide.

---

## 1. The pitch: what judges are about to see

One sentence to say out loud before clicking anything:

> "This is a cyclic multi-agent system, not a linear chatbot wrapper — when
> content fails compliance, it goes back and rewrites itself, and when a
> human rejects something, the system remembers that mistake and stops
> repeating it, permanently, without a prompt-engineering patch."

---

## 2. Click-through

### 2.1 — The review queue looks alive (30s)

- Open `http://127.0.0.1:8000/dashboard`.
- Point out: real brand voices (Jade / Jaguar Transit / DoctorShield), real
  platforms, real localised copy (the Bahasa Malaysia post is already there).
- This is `scripts/seed_demo.py`'s work — say so. It's the same schema a live
  run writes to; nothing here is UI mockery.

### 2.2 — The circuit breaker, after the fact (30s)

- Click the **Manual Intervention** tab.
- Two rows are sitting there with `retry_count` at 4 and 5, each with two
  compliance violations listed — one used a banned word ("100% guaranteed"),
  the other promised lawsuit immunity DoctorShield's brand rule forbids.
- Say: "the graph tried to fix these three times automatically before giving
  up and routing here instead of looping forever."

### 2.3 — The closed loop, live (2–3 min, the centerpiece)

- Click into the **Jade / LinkedIn** pending item.
- Click **Reject**. Pick `too_salesy` as the reason, and type a note, e.g.
  *"Still reads like a discount ad — Jade never discounts."*
- Say: "That note just became a permanent row in `feedback_memory`."
- Now go generate a **new** Jade / LinkedIn draft (see 2.5 below, or if you've
  pre-wired a `/generate` trigger, use it here) and show the compliance-gate
  pass reasoning, or simply open `GET /api/feedback?brand=Jade&platform=linkedin`
  in a second tab and show the note is already there, ready to be injected
  into the next draft's system prompt — the exact
  `CRITICAL GUIDANCE: ... You MUST NOT repeat these mistakes.` string is what
  the content agent actually sees.
- This is the single fact that differentiates this system from "an LLM
  wrapper": the mistake is stored, retrieved, and injected — not
  re-explained by a human every time.

### 2.4 — Approve → auto-publish (1 min)

- Go back to the queue, open the **DoctorShield / LinkedIn** approved item
  (or approve a pending one live).
- Click **Approve**.
- Switch to Terminal 2 — within one poll interval, the worker log line
  `scheduled content_id=... post_id=...` appears (or, without a live
  Buffer/Ayrshare key, `publish failed for content_id=...` — say plainly that
  publishing needs a live social account, and the important part is that the
  loop only ever touches rows a human explicitly approved).
- Refresh `/api/queue?status=scheduled` (or `?status=approved` if no key is
  configured) to show the status flip.

### 2.5 — Metrics (30s)

- Click the **Metrics** tab.
- Rejection rate, average retries per asset, feedback-entry count, lead
  count — say: "this is the evidence the loop is actually learning, not just
  a nice UI."

### 2.6 — Lead generation, if time allows (1 min)

- `GET /api/leads` — three enriched, scored prospects with a written
  rationale and a drafted outreach message each, one per brand.
- Say: "this ran through the same LLM client and the same swappable-provider
  pattern as everything else — Tavily today, Google Places or Serper the
  moment either key is dropped into `.env`, zero code changes."

---

## 3. If something breaks live

- **LLM call fails / times out:** the dashboard and seeded data don't depend
  on a live LLM call — fall back to the click-through above using only the
  pre-seeded rows and skip live generation.
- **No Buffer/Ayrshare key configured:** show the worker log's
  `publish failed for content_id=...` line — explain the swappable-provider
  design and that it activates the moment a key is added, no redeploy needed.
- **Someone asks "is this really cyclic, or did you just say that":** open
  `docs/architecture.md`'s first diagram and trace the `retry_count <= 3`
  edge back into `content_node` live.

---

## 4. Closing line

> "Project 1 — the Brain — is fully demoable on its own, exactly as required.
> Project 2 — the auto-publisher — is the bonus, and it's running in that
> second terminal right now, polling a real database, not a mock."
