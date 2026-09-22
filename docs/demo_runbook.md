# Demo Runbook

A ten-minute live walkthrough. Run the setup once before judges arrive; the
click-through itself takes about five minutes.

---

## 0. Environment startup (before judges arrive)

```bash
# from the repo root
source venv/bin/activate          # or: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
python -m scripts.init_db          # creates the schema if it doesn't exist yet
python scripts/seed_demo.py        # or: python -m scripts.seed_demo — both work
```

Confirm `.env` has at minimum `GEMINI_API_KEY` set, and one of
`BUFFER_ACCESS_TOKEN` / `AYRSHARE_API_KEY` if you want the auto-publisher to
actually schedule a post live.

**Tip for a snappy demo:** the worker polls every `PUBLISH_POLL_INTERVAL`
seconds (60 by default). Set it to `5` in `.env` before the pitch so an
Approve click shows up in the worker log almost immediately instead of
making judges wait up to a minute. Put it back afterward if you care about
being realistic outside a demo.

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

Leave this running in the background for the whole demo — it's what proves
Project 2 is a real, live process, not a slide.

---

## 1. Ngrok public media setup (optional, but strongly recommended)

Buffer/Ayrshare — and a judge's own phone — can't reach `localhost`. Without
a public URL, the auto-publisher will skip attaching media (text-only posts)
and you can't hand someone your dashboard link to click around on their own
device.

```bash
# Terminal 3
ngrok http 8000
```

Copy the `https://<subdomain>.ngrok-free.app` forwarding URL ngrok prints,
then in `.env`:

```bash
PUBLIC_MEDIA_BASE_URL=https://<subdomain>.ngrok-free.app
```

Restart Terminal 1 and Terminal 2 (env vars are only read at process start).
Verify it worked:

```bash
curl -I https://<subdomain>.ngrok-free.app/static/sample.mp4
# expect: HTTP/2 200, content-type: video/mp4
```

Files are served from `assets/generated/` via the `/static` mount added in
`app/main.py` — `scripts/seed_demo.py` already generated a real
`sample.mp4` there using the same edge-tts + moviepy pipeline the content
graph uses (see `docs/architecture.md` §6).

---

## 2. The pitch: what judges are about to see

One sentence to say out loud before clicking anything:

> "This is a cyclic multi-agent system, not a linear chatbot wrapper — when
> content fails compliance, it goes back and rewrites itself, and when a
> human rejects something, the system remembers that mistake and stops
> repeating it, permanently, without a prompt-engineering patch."

---

## 3. Click-through

### 3.1 — Approved queue, across three markets (1 min)

- Open `http://127.0.0.1:8000/api/queue?status=approved` for a quick raw
  look, then go to `http://127.0.0.1:8000/dashboard` and open each of the
  three approved items' detail pages: **Jade / Instagram (English)**,
  **Jaguar Transit / LinkedIn (Bahasa Malaysia)**, **DoctorShield / LinkedIn
  (Thai)**.
- Point out the localisation is real, not templated — the Thai and Malay
  copy carries the brand's mandatory disclaimer, adapted to the market.
- Open the **Media** section on any of the three — this is a real MP4 the
  system generated itself (edge-tts voiceover + moviepy), playing directly
  in the browser via the `/static` mount. If ngrok is up, this is also the
  moment to hand a judge the ngrok URL and let them play it on their phone.

### 3.2 — The circuit breaker, after the fact (30s)

- Click the **Manual Intervention** tab.
- Two rows are sitting there with `retry_count` at 4 and 5, each with two
  compliance violations listed — one used a banned word ("100% guaranteed"),
  the other promised lawsuit immunity DoctorShield's brand rule forbids.
- Say: "the graph tried to fix these automatically, past the retry budget,
  before giving up and routing here instead of looping forever."

### 3.3 — The closed loop, live (2–3 min, the centerpiece)

- Open the **Jade / Instagram** item's detail page again.
- Click **Reject**. Pick `too_salesy`, and type a note, e.g. *"Still reads
  like a discount ad — Jade never discounts."*
- Say: "That note just became a permanent row in `feedback_memory` — right
  now, live." Open `GET /api/feedback?brand=Jade&platform=instagram` in a
  second tab: **two** notes now, the one you just wrote and the one already
  seeded from a prior rejection.
- Say: "Every one of these gets injected into the content agent's system
  prompt as `CRITICAL GUIDANCE: ... You MUST NOT repeat these mistakes.` —
  the exact string is in `docs/architecture.md` §4. The mistake is stored,
  retrieved, and injected automatically — never re-explained by a human."
- Close the loop for the room: reopen the same item, use **Edit & approve**
  to push it back to `approved`. Watch Terminal 2 — within one poll interval
  it picks this exact row up.

### 3.4 — Auto-publish, unattended (30s)

- Point at Terminal 2's scrollback — the two *other* approved items
  (Jaguar Transit, DoctorShield) were already picked up automatically when
  the worker started, no click required. Find their `scheduled
  content_id=... post_id=...` lines (or `publish failed for
  content_id=...` if no live key is configured — say plainly that
  publishing needs a real social account, and the important part is the
  worker only ever touches rows a human explicitly approved).
- Refresh `/api/queue?status=scheduled` to show the status flip from the
  dashboard's own contract, not just the log.

### 3.5 — Metrics (30s)

- Click the **Metrics** tab: rejection rate, average retries per asset,
  feedback-entry count, lead count.
- Say: "this is the evidence the loop is actually learning, not just a nice
  UI."

### 3.6 — Lead generation, if time allows (1 min)

- `GET /api/leads` — three enriched, scored prospects with a written
  rationale and a drafted outreach message each, one per brand.
- Say: "this ran through the same LLM client and the same swappable-provider
  pattern as everything else — Tavily today, Google Places or Serper the
  moment either key is dropped into `.env`, zero code changes."

---

## 4. Pitch script — five points to hit, in any order

- **Zero model training.** Every brand voice, every compliance rule, every
  localisation is prompt- and rubric-driven (`compliance_rubric.md`, loaded
  from disk at runtime) — not a fine-tune, not a training run.
- **Dynamic prompt injection, not static prompts.** `memory_retrieval_node`
  pulls the last 5 human corrections for this exact brand + platform and
  injects them into the system prompt before generation even starts.
- **Compliance is a circuit breaker, not a suggestion.** A draft that fails
  the compliance gate goes back to the content agent with the specific
  violation cited; past 3 retries it stops looping and routes to a human
  queue instead of either publishing something wrong or hanging forever.
- **Every external integration is swappable, not hardcoded.** Search,
  discovery, and publishing each have 2+ provider implementations behind one
  interface, selected by whichever `.env` key is present — see
  `docs/architecture.md` §3.
- **Auto-publishing is unattended, but never unapproved.** The worker only
  ever reads rows a human already moved to `approved`; nothing reaches
  Buffer/Ayrshare without that gate.

---

## 5. If something breaks live

- **LLM call fails / times out:** the dashboard and seeded data don't depend
  on a live LLM call — fall back to the click-through above using only the
  pre-seeded rows.
- **No Buffer/Ayrshare key configured:** show the worker log's
  `publish failed for content_id=...` line — explain the swappable-provider
  design and that it activates the moment a key is added, no redeploy needed.
- **`/static/sample.mp4` 404s:** `scripts/seed_demo.py`'s media generation
  needs network access for edge-tts; re-run it, or skip §3.1's video moment.
- **Someone asks "is this really cyclic, or did you just say that":** open
  `docs/architecture.md`'s first diagram and trace the `retry_count <= 3`
  edge back into `content_node` live.

---

## 6. Closing line

> "Project 1 — the Brain — is fully demoable on its own, exactly as required.
> Project 2 — the auto-publisher — is the bonus, and it's running in that
> second terminal right now, polling a real database, not a mock."
