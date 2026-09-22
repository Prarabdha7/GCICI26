/* JA Assure Marketing Console — static SPA, same-origin JSON API only.
   Surfaces ONLY implemented backend capabilities; nothing is fabricated here:
   every number, row and status comes from /api/* responses. */
const $ = (s, el = document) => el.querySelector(s);
const view = $("#view"), banner = $("#banner");
let demoMode = false;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const badge = (status, isDemo) =>
  `<span class="badge ${esc(status)}">${esc(status)}</span>` + (isDemo ? ` <span class="badge demo">demo — not real</span>` : "");

function showBanner(msg, kind = "") {
  if (!msg) { banner.hidden = true; return; }
  banner.hidden = false;
  banner.className = "banner " + kind;
  banner.textContent = msg;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  const text = await res.text();
  let data; try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  if (!res.ok) throw new Error((data && data.detail) || `HTTP ${res.status}`);
  return data;
}

async function refreshHealth() {
  try {
    const [h, d] = await Promise.all([api("/health"), api("/api/demo/status")]);
    demoMode = !!d.demo_mode;
    $("#health").className = "health" + (demoMode ? " demo" : "");
    $("#health").innerHTML = `<span class="dot"></span>api ok · llm ${d.llm_configured ? "keyed" : "unkeyed"} · ${demoMode ? "DEMO mode" : "real mode"}`;
  } catch (e) {
    $("#health").textContent = "backend unreachable";
  }
}

/* ---------------- queue ---------------- */
const STATUSES = ["pending", "manual_intervention", "approved", "scheduled", "published", "rejected"];
let qState = { status: "pending", brand: "", platform: "" };

async function renderQueue() {
  const q = new URLSearchParams({ limit: 100 });
  if (qState.status) q.set("status", qState.status);
  if (qState.brand) q.set("brand", qState.brand);
  if (qState.platform) q.set("platform", qState.platform);
  let items = [];
  try { items = await api("/api/queue?" + q.toString()); }
  catch (e) { showBanner("Queue unavailable honestly: " + e.message, "err"); }
  view.innerHTML = `
    <h2>Review queue</h2>
    <div class="card"><div class="formgrid">
      <label>Status<select id="f-status">${STATUSES.map(s => `<option ${s === qState.status ? "selected" : ""}>${s}</option>`).join("")}</select></label>
      <label>Brand<input id="f-brand" placeholder="e.g. Jade" value="${esc(qState.brand)}"></label>
      <label>Platform<input id="f-platform" placeholder="e.g. linkedin" value="${esc(qState.platform)}"></label>
      <div><label>&nbsp;</label><button id="f-go">Filter</button></div>
    </div></div>
    <div class="card"><table><thead><tr><th>ID</th><th>Brand / platform</th><th>Draft</th><th>Status</th></tr></thead>
    <tbody>${items.map(i => `<tr class="clickable" data-id="${i.id}">
      <td>${i.id}</td><td><b>${esc(i.brand)}</b><br><span class="mut">${esc(i.platform)} · ${esc(i.language)}${i.topic ? " · " + esc(i.topic) : ""}</span></td>
      <td>${esc((i.draft_content || "").slice(0, 120))}…</td>
      <td>${badge(i.status, i.is_demo)}</td></tr>`).join("") || `<tr><td colspan="4" class="mut">Nothing here — empty state, not an error.</td></tr>`}</tbody></table></div>`;
  $("#f-go").onclick = () => { qState = { status: $("#f-status").value, brand: $("#f-brand").value.trim(), platform: $("#f-platform").value.trim() }; renderQueue(); };
  view.querySelectorAll("tr.clickable").forEach(tr => tr.onclick = () => renderDetail(+tr.dataset.id));
}

/* ---------------- detail ---------------- */
async function renderDetail(id) {
  let item, extra = { media: {}, captions: [], diff: [], formats: {} }, events = [], feedback = [];
  try {
    [item, extra] = await Promise.all([api(`/api/queue/${id}`), api(`/api/queue/${id}/media`)]);
    [events, feedback] = await Promise.all([
      api(`/api/publish/events/${id}`).catch(() => []),
      api(`/api/queue/${id}/feedback`).catch(() => []),
    ]);
  } catch (e) { showBanner("Item unavailable honestly: " + e.message, "err"); return; }
  const m = extra.media || {}, pack = extra.formats || {};
  view.innerHTML = `
    <span class="back" id="back">← Back to queue</span>
    <h2>${esc(item.brand)} — ${esc(item.platform)} ${badge(item.status, item.is_demo)}</h2>
    <p class="mut">retries ${item.retry_count}${item.topic ? " · topic: " + esc(item.topic) : ""}${item.is_demo ? " · <b>DEMO row — simulated, not real</b>" : ""}</p>
    <div class="grid two">
    <div>
      <div class="card"><h3>Draft</h3><p class="prewrap">${esc(item.draft_content)}</p></div>
      ${item.final_content ? `<div class="card"><h3>Final (edited)</h3><p class="prewrap">${esc(item.final_content)}</p></div>` : ""}
      ${item.healed_content ? `<div class="card"><h3>Self-healed rewrite</h3><p class="prewrap">${esc(item.healed_content)}</p></div>` : ""}
      ${item.audit_transcript ? `<div class="card"><h3>Audit transcript</h3><p class="prewrap">${esc(item.audit_transcript)}</p></div>` : ""}
      ${(item.compliance_errors || []).length ? `<div class="card"><h3>Violations</h3><ul class="compact">${item.compliance_errors.map(v => `<li>${esc(v)}</li>`).join("")}</ul></div>` : ""}
      ${extra.diff.length ? `<div class="card"><h3>Redline diff</h3><ul class="diff">${extra.diff.map(d => `<li class="diff-${d.kind}">${esc(d.text)}</li>`).join("")}</ul></div>` : ""}
    </div>
    <div>
      ${m.video_url ? `<div class="card"><h3>Reel</h3><video controls preload="metadata" src="${esc(m.video_url)}"></video>
        <p class="mut"><a href="${esc(m.video_url)}">MP4</a> · <a href="${esc(m.srt_url)}">SRT</a> · <a href="${esc(m.json_url)}">captions JSON</a></p>
        ${extra.captions.length ? `<ol class="compact">${extra.captions.map(c => `<li>${esc(c.text)} <span class="mut">(${(+c.start).toFixed(1)}s)</span></li>`).join("")}</ol>` : ""}</div>`
        : item.media_path ? `<div class="card"><h3>Media</h3><p class="mut">${esc(item.media_path)} (not servable from this host)</p></div>` : ""}
      ${pack.thread ? `<div class="card"><h3>Multi-format pack</h3>
        <h4>Thread</h4><ol class="compact">${pack.thread.map(t => `<li>${esc(t)}</li>`).join("")}</ol>
        <h4>Carousel</h4><ol class="compact">${pack.carousel.map(s => `<li>${esc(s)}</li>`).join("")}</ol>
        <p><b>A:</b> ${esc(pack.variant_a)}</p><p><b>B:</b> ${esc(pack.variant_b)}</p>
        ${pack.video_script ? `<h4>Video script</h4><p>${esc(pack.video_script)}</p>` : ""}
        ${(pack.hashtags || []).length ? `<h4>Hashtags (${esc(pack.hashtags_source || "suggestion")})</h4><p>${pack.hashtags.map(esc).join(" ")}</p>` : ""}
        ${(pack.focus_group || []).length ? `<h4>Focus group (demo personas)</h4><ul class="compact">${pack.focus_group.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}</div>` : ""}
      <div class="card"><h3>Review actions</h3>
        <p><button id="a-approve">Approve</button> <button id="a-fix" class="secondary">Accept self-healing fix</button></p>
        <label>Reject reason (tag)<input id="r-tag" placeholder="e.g. too_salesy"></label>
        <label>Reject note<textarea id="r-note" rows="2"></textarea></label>
        <p><button id="a-reject" class="danger">Reject</button></p>
        <label>Edit → final content<textarea id="e-content" rows="4">${esc(item.final_content || item.draft_content)}</textarea></label>
        <label>Edit tag<input id="e-tag" placeholder="e.g. wrong_cta"></label>
        <label>Edit note<textarea id="e-note" rows="2"></textarea></label>
        <p><button id="a-edit">Save edit & approve</button></p></div>
      <div class="card"><h3>Publish trail</h3>
        <p class="mut">post id: ${esc(item.external_post_id || "—")}${item.published_url ? ` · <a href="${esc(item.published_url)}">link</a>` : ""}</p>
        <ul class="compact">${events.map(e => `<li><b>${esc(e.event)}</b> [${esc(e.provider)}] ${esc(e.at || "")} ${esc(JSON.stringify(e.payload || {}).slice(0, 120))}</li>`).join("") || "<li class='mut'>No publish events.</li>"}</ul></div>
      <div class="card"><h3>Feedback history</h3>
        <ul class="compact">${feedback.map(f => `<li>[${esc(f.error_tag)}] ${esc(f.human_note)}</li>`).join("") || "<li class='mut'>None.</li>"}</ul></div>
    </div></div>`;
  $("#back").onclick = renderQueue;
  const done = (d) => { showBanner(d.message + (d.is_demo ? " [DEMO row]" : ""), d.is_demo ? "demo" : ""); renderDetail(id); };
  const fail = (e) => showBanner("Action failed honestly: " + e.message, "err");
  $("#a-approve").onclick = () => api(`/api/queue/${id}/approve`, { method: "POST", body: "{}" }).then(done).catch(fail);
  $("#a-fix").onclick = () => api(`/api/queue/${id}/accept-fix`, { method: "POST", body: "{}" }).then(done).catch(fail);
  $("#a-reject").onclick = () => api(`/api/queue/${id}/reject`, { method: "POST", body: JSON.stringify({ error_tag: $("#r-tag").value, human_note: $("#r-note").value }) }).then(done).catch(fail);
  $("#a-edit").onclick = () => api(`/api/queue/${id}/edit`, { method: "POST", body: JSON.stringify({ final_content: $("#e-content").value, error_tag: $("#e-tag").value, human_note: $("#e-note").value }) }).then(done).catch(fail);
}

/* ---------------- generate ---------------- */
async function renderGenerate() {
  let digests = [];
  try { digests = await api("/api/intel/digests"); } catch (e) { /* honest empty */ }
  view.innerHTML = `
    <h2>Generate</h2>
    <p class="mut">Runs the real LangGraph pipeline. Without an LLM key it fails honestly in real mode; in DEMO mode output is labeled DEMO.</p>
    <div class="card"><h3>Latest intel digests (periodic sweep)</h3>
      <ul class="compact">${digests.map(d => `<li><b>${esc(d.brand)} / ${esc(d.country)}</b>${d.is_demo ? " <span class='badge demo'>demo</span>" : ""}<br><span class="mut">${esc((d.digest_text || "no findings this sweep").slice(0, 220))}</span><br><button class="secondary" data-digest="${esc((d.digest_text || "").slice(0, 200))}" data-brand="${esc(d.brand)}">Generate from this</button></li>`).join("") || "<li class='mut'>No digests yet — the 6-hour sweep hasn't stored any, or research found nothing.</li>"}</ul></div>
    <div class="grid two">
    <div class="card"><h3>Campaign</h3><div class="formgrid">
      <label>Brand<select id="g-brand"><option>Jade</option><option>Jaguar Transit</option><option>DoctorShield</option></select></label>
      <label>Platform<select id="g-platform"><option>linkedin</option><option>instagram</option><option>x</option><option>tiktok</option><option>blog</option></select></label>
      <label>Language<select id="g-lang"><option>en</option><option>ms</option><option>id</option><option>th</option><option>zh</option></select></label>
      <label>Type<select id="g-type"><option>post</option><option>video</option><option>carousel</option></select></label>
    </div><label>Topic<input id="g-topic" placeholder="e.g. SIJE memo cover"></label>
    <button id="g-go">Generate campaign</button></div>
    <div class="card"><h3>Newsjack from research</h3>
      <label>Niche<input id="n-niche" value="jewellers block"></label>
      <label>Country<input id="n-country" value="Singapore"></label>
      <button id="n-go">Research + generate</button>
      <p class="mut">Live keyless research (DuckDuckGo + Crawl4AI); mock fallback only when search returns nothing.</p></div>
    </div>`;
  $("#g-go").onclick = async () => {
    try {
      const d = await api("/api/generate", { method: "POST", body: JSON.stringify({ brand: $("#g-brand").value, platform: $("#g-platform").value, language: $("#g-lang").value, topic: $("#g-topic").value, content_type: $("#g-type").value }) });
      showBanner(d.message, d.is_demo ? "demo" : ""); renderDetail(d.content_id);
    } catch (e) { showBanner("Generation failed honestly: " + e.message, "err"); }
  };
  $("#n-go").onclick = async () => {
    try {
      const d = await api("/api/newsjack", { method: "POST", body: JSON.stringify({ brand: $("#g-brand").value, niche: $("#n-niche").value, country: $("#n-country").value }) });
      showBanner(d.message, d.is_demo ? "demo" : ""); renderDetail(d.content_id);
    } catch (e) { showBanner("Newsjack failed honestly: " + e.message, "err"); }
  };
  view.querySelectorAll("[data-digest]").forEach(b => b.onclick = async () => {
    try {
      const d = await api("/api/generate", { method: "POST", body: JSON.stringify({ brand: b.dataset.brand, platform: "linkedin", language: "en", topic: b.dataset.digest, content_type: "post" }) });
      showBanner(d.message, d.is_demo ? "demo" : ""); renderDetail(d.content_id);
    } catch (e) { showBanner("Generation failed honestly: " + e.message, "err"); }
  });
}

/* ---------------- metrics ---------------- */
function svgChart(rows) {
  const W = 640, H = 220, P = 32;
  if (!rows.length) return `<p class="mut">No data yet — empty state, not an error.</p>`;
  const xs = (i) => P + (i * (W - 2 * P)) / Math.max(1, rows.length - 1);
  const yR = (v) => H - P - v * (H - 2 * P);
  const maxE = Math.max(1, ...rows.map(r => r.avg_edit_distance));
  const yE = (v) => H - P - (v / maxE) * (H - 2 * P);
  const line = (pts) => `<polyline fill="none" stroke-width="2" points="${pts}"/>`;
  const rej = line(rows.map((r, i) => `${xs(i)},${yR(r.rejection_rate)}`).join(" "));
  const edt = line(rows.map((r, i) => `${xs(i)},${yE(r.avg_edit_distance)}`).join(" "));
  return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;background:#0b1220;border-radius:8px">
    <g stroke="#38bdf8">${rej}</g><g stroke="#f59e0b">${edt}</g>
    ${rows.map((r, i) => `<circle cx="${xs(i)}" cy="${yR(r.rejection_rate)}" r="3" fill="#38bdf8"><title>${esc(r.date)} rej ${r.rejection_rate}</title></circle>`).join("")}
    <text x="${P}" y="16" fill="#38bdf8" font-size="12">— rejection rate</text>
    <text x="${P + 150}" y="16" fill="#f59e0b" font-size="12">— avg edit distance (max ${maxE})</text></svg>`;
}

async function renderMetrics() {
  let stats = { total: 0, by_status: {}, rejection_rate: 0 }, trend = [], lessons = [];
  try {
    [stats, trend] = await Promise.all([api("/api/stats"), api("/api/metrics/trend?days=14")]);
    lessons = await api("/api/feedback?limit=15");
  } catch (e) { showBanner("Metrics unavailable honestly: " + e.message, "err"); }
  view.innerHTML = `
    <h2>Metrics <span class="mut">(real rows only — demo excluded)</span></h2>
    <div class="kpis">
      <div class="kpi"><b>${stats.total}</b><span>total real assets</span></div>
      <div class="kpi"><b>${(stats.rejection_rate * 100).toFixed(1)}%</b><span>rejection rate</span></div>
      <div class="kpi"><b>${stats.feedback_entries}</b><span>feedback entries</span></div>
      <div class="kpi"><b>${stats.leads}</b><span>leads</span></div>
    </div>
    <div class="card"><h3>Learning curve (14d)</h3>${svgChart(trend)}
      <table><thead><tr><th>date</th><th>created</th><th>rej rate</th><th>avg edit</th><th>avg retries</th></tr></thead>
      <tbody>${trend.map(r => `<tr><td>${esc(r.date)}</td><td>${r.created}</td><td>${r.rejection_rate}</td><td>${r.avg_edit_distance}</td><td>${r.avg_retries}</td></tr>`).join("")}</tbody></table></div>
    <div class="card"><h3>By status</h3><ul class="compact">${Object.entries(stats.by_status).map(([k, v]) => `<li>${esc(k)}: ${v}</li>`).join("") || "<li class='mut'>No data yet.</li>"}</ul></div>
    <div class="card"><h3>Lessons learned</h3><ul class="compact">${lessons.map(f => `<li><b>${esc(f.brand)}/${esc(f.platform)} [${esc(f.error_tag)}]</b>: ${esc(f.human_note)}</li>`).join("") || "<li class='mut'>None yet.</li>"}</ul></div>`;
}

/* ---------------- leads ---------------- */
async function renderLeads() {
  let leads = [];
  try { leads = await api("/api/leads?limit=100"); }
  catch (e) { showBanner("Leads unavailable honestly: " + e.message, "err"); }
  view.innerHTML = `<h2>Leads <span class="mut">(read-only — no outreach actions exist in the backend)</span></h2>
    <div class="card"><table><thead><tr><th>Company</th><th>Segment / country</th><th>Score</th><th>Outreach draft</th></tr></thead><tbody>
    ${leads.map(l => `<tr><td><b>${esc(l.company_name)}</b><br><span class="mut">${esc(l.website || "")}</span></td>
      <td>${esc(l.segment || "")} · ${esc(l.country || "")}</td><td>${l.fit_score ?? "—"}</td><td>${esc((l.score_rationale || "") + (l.score_rationale ? " — " : "") + (l.outreach_draft || ""))}</td></tr>`).join("") || `<tr><td colspan="4" class="mut">No leads yet.</td></tr>`}</tbody></table></div>`;
}

/* ---------------- boot ---------------- */
const routes = { queue: renderQueue, generate: renderGenerate, metrics: renderMetrics, leads: renderLeads };
$("#nav").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#nav button").forEach(x => x.classList.remove("active"));
  b.classList.add("active"); showBanner(""); routes[b.dataset.view]();
});
refreshHealth().then(renderQueue);
