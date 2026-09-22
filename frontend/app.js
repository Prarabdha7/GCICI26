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

/* ---------------- memory (Second Brain) ---------------- */
const KIND_COLORS = { brand: "#38bdf8", regulation: "#a78bfa", competitor: "#ec4899", feedback: "#f59e0b", asset: "#22c55e", intel: "#f472b6" };

async function renderMemory() {
  let graph = { nodes: [], edges: [] };
  try { graph = await api("/api/memory/vault"); }
  catch (e) { showBanner("Vault unavailable honestly: " + e.message, "err"); }
  const W = 680, H = 380, cx = W / 2, cy = H / 2;
  const kinds = [...new Set(graph.nodes.map(n => n.kind))];
  const pos = {};
  graph.nodes.forEach((n, i) => {
    const ring = kinds.indexOf(n.kind);
    const same = graph.nodes.filter(x => x.kind === n.kind);
    const k = same.indexOf(n);
    const R = 60 + ring * 62;
    const a = (2 * Math.PI * k) / Math.max(1, same.length) + ring * 0.5;
    pos[n.id] = [cx + R * Math.cos(a), cy + R * Math.sin(a) * 0.72];
  });
  const byId = Object.fromEntries(graph.nodes.map(n => [n.id, n]));
  const edgeSvg = graph.edges.filter(e => pos[e[0]] && pos[e[1]])
    .map(e => `<line x1="${pos[e[0]][0]}" y1="${pos[e[0]][1]}" x2="${pos[e[1]][0]}" y2="${pos[e[1]][1]}" stroke="#334155"/>`).join("");
  const nodeSvg = graph.nodes.map(n => {
    const [x, y] = pos[n.id];
    return `<g class="vnode" data-path="${esc(n.path || "")}" style="cursor:pointer">
      <circle cx="${x}" cy="${y}" r="9" fill="${KIND_COLORS[n.kind] || "#94a3b8"}"/>
      <text x="${x + 12}" y="${y + 4}" fill="#f1f5f9" font-size="11">${esc(n.label)}</text></g>`;
  }).join("");
  view.innerHTML = `
    <h2>Memory vault <span class="mut">(every node is a real DB row — open the folder in Obsidian for Graph View)</span></h2>
    <div class="grid two"><div class="card">
      <svg viewBox="0 0 ${W} ${H}" style="width:100%;background:#0b1220;border-radius:8px">${edgeSvg}${nodeSvg}</svg>
      <p class="mut">${graph.nodes.length} nodes · ${graph.edges.length} links · brands <span style="color:#38bdf8">●</span> competitors <span style="color:#ec4899">●</span> regulations <span style="color:#a78bfa">●</span> feedback <span style="color:#f59e0b">●</span> assets <span style="color:#22c55e">●</span> intel <span style="color:#f472b6">●</span></p>
      <p><a href="/vault/JA_Assure_Second_Brain.canvas" download="JA_Assure_Second_Brain.canvas" class="btn" style="display:inline-block;padding:4px 10px;background:#1e293b;border:1px solid #38bdf8;border-radius:4px;color:#38bdf8;text-decoration:none">📥 Download Obsidian Canvas (.canvas)</a></p>
    </div><div class="card"><h3>Node preview</h3><div id="vprev" class="mut">Click a node to read its markdown (served from <code>/vault/</code>).</div></div></div>`;
  view.querySelectorAll(".vnode").forEach(g => g.addEventListener("click", async () => {
    const p = g.dataset.path;
    if (!p) return;
    try {
      const md = await (await fetch("/vault/" + p)).text();
      $("#vprev").innerHTML = `<pre class="prewrap">${esc(md.slice(0, 2000))}</pre><p><a href="/vault/${esc(p)}">open raw →</a></p>`;
    } catch (e) { $("#vprev").textContent = "Could not load file honestly: " + e.message; }
  }));
}

/* ---------------- studio (Test Lab) ---------------- */
const PRESET_SCRIPTS = {
  "Jade": "Discretion is paramount. Jade protects high-value gems, luxury watches, and bespoke jewellery from vault to exhibition. MAS compliant.",
  "DoctorShield": "Clinical decisions belong to physicians. Financial protection against malpractice suits belongs to DoctorShield. Terms apply.",
  "Jaguar Transit": "High-value freight moving across Southeast Asian borders. Unbroken chain-of-custody protection on road, air, and sea. Terms apply."
};

const PRESET_PROMPTS = {
  "Jade": "Emerald and diamond brooch resting on black velvet inside a bank vault, dramatic lighting, 4K macro sweep, photorealistic luxury jewellery",
  "DoctorShield": "Dramatic clinical lighting in a modern diagnostic surgical theater, sterile, blue ambient glow, ultra-detailed 4K medical technology",
  "Jaguar Transit": "Armored security logistics convoy transport vehicle on wet asphalt at night under neon streetlights, rain reflections, 4K"
};

async function renderStudio() {
  let modelInfo = { image_model: "gemini-3.1-flash-image", video_model: "veo-3.1-fast-generate-preview", available_image_models: [], available_video_strategies: [] };
  try { modelInfo = await api("/api/studio/models"); } catch (e) { /* fallback */ }

  view.innerHTML = `
    <div class="studio-header" style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;flex-wrap:wrap;gap:10px">
      <div>
        <h2>Interactive Test Studio <span class="badge" style="background:#38bdf8;color:#090d16;font-weight:700">Test Lab</span></h2>
        <p class="mut">Real-time testing bench for Sora-like Video Reels, Gemini Image Generation, and Obsidian Second Brain.</p>
      </div>
      <div style="background:#1e293b;padding:8px 14px;border-radius:6px;border:1px solid #334155;font-size:.85rem;display:flex;gap:12px">
        <span>Image: <code style="color:#38bdf8">${esc(modelInfo.image_model)}</code></span>
        <span>Video: <code style="color:#a78bfa">${esc(modelInfo.video_model)}</code></span>
      </div>
    </div>

    <div class="grid two">
      <!-- Reel Studio Card -->
      <div class="card">
        <h3>🎬 Sora-Like Cinematic Video Reel</h3>
        <p class="mut">Assembles Edge-TTS voiceover, 9:16 vertical video (Veo / Pollinations / Curated B-Roll / Ken Burns), and kinetic highlighted subtitles.</p>
        <div class="formgrid">
          <label>Brand
            <select id="s-vbrand">
              <option value="Jade">Jade (Jewellers Block)</option>
              <option value="DoctorShield">DoctorShield (Medical Indemnity)</option>
              <option value="Jaguar Transit">Jaguar Transit (High-Value Cargo)</option>
            </select>
          </label>
          <label>Strategy
            <select id="s-vstrat">
              <option value="auto">Auto Cascade (Veo → Pollinations → B-roll → Ken Burns)</option>
              <option value="broll">Curated 4K B-Roll Loop (assets/video/)</option>
              <option value="veo">Google Veo (veo-3.1-fast-generate-preview)</option>
              <option value="community">Community Diffusion (Pollinations.ai)</option>
              <option value="kenburns">2.5D Ken Burns Cinematic Motion</option>
            </select>
          </label>
          <label>Voice Accent
            <select id="s-vlang">
              <option value="en">English (Singapore - Wayne)</option>
              <option value="ms">Malay (Malaysia - Osman)</option>
              <option value="id">Indonesian (Ardi)</option>
              <option value="th">Thai (Niwat)</option>
              <option value="zh">Cantonese (Hong Kong - WanLung)</option>
            </select>
          </label>
        </div>
        <label>Narration Script
          <textarea id="s-vscript" rows="3">${esc(PRESET_SCRIPTS["Jade"])}</textarea>
        </label>
        <div style="display:flex;gap:6px;margin:6px 0 10px">
          <button type="button" class="secondary" id="s-vpre-jade" style="padding:3px 8px;font-size:.78rem">Preset: Jade</button>
          <button type="button" class="secondary" id="s-vpre-doc" style="padding:3px 8px;font-size:.78rem">Preset: DoctorShield</button>
          <button type="button" class="secondary" id="s-vpre-jag" style="padding:3px 8px;font-size:.78rem">Preset: Jaguar Transit</button>
        </div>
        <p><button id="s-vbtn" style="background:#0284c7;color:#fff;border:none;padding:8px 18px;border-radius:6px;font-weight:600;cursor:pointer">Generate Video Reel</button></p>
        <div id="s-vresult" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid #334155">
          <h4>Video Preview</h4>
          <video id="s-vplayer" controls preload="metadata" style="width:100%;max-width:300px;border-radius:8px;background:#000;margin-bottom:8px;display:block"></video>
          <div id="s-vdownloads" class="mut" style="margin-bottom:8px"></div>
          <div id="s-vcaptions" style="max-height:120px;overflow-y:auto"></div>
        </div>
      </div>

      <!-- Image Studio Card -->
      <div class="card">
        <h3>🎨 High-Definition Image Studio</h3>
        <p class="mut">Tests Gemini Image Generation (gemini-3.1-flash-image with fallbacks) or procedural luxury cards.</p>
        <div class="formgrid">
          <label>Brand
            <select id="s-ibrand">
              <option value="Jade">Jade</option>
              <option value="DoctorShield">DoctorShield</option>
              <option value="Jaguar Transit">Jaguar Transit</option>
            </select>
          </label>
          <label>Image Model
            <select id="s-imodel">
              <option value="gemini-3.1-flash-image">gemini-3.1-flash-image (Default)</option>
              <option value="gemini-3.1-flash-lite-image">gemini-3.1-flash-lite-image</option>
              <option value="gemini-2.5-flash-image">gemini-2.5-flash-image</option>
              <option value="gemini-3-pro-image">gemini-3-pro-image</option>
              <option value="procedural">procedural-luxury (Zero-Key)</option>
            </select>
          </label>
        </div>
        <label>Visual Prompt
          <textarea id="s-iprompt" rows="3">${esc(PRESET_PROMPTS["Jade"])}</textarea>
        </label>
        <div style="display:flex;gap:6px;margin:6px 0 10px">
          <button type="button" class="secondary" id="s-ipre-jade" style="padding:3px 8px;font-size:.78rem">Prompt: Vault</button>
          <button type="button" class="secondary" id="s-ipre-doc" style="padding:3px 8px;font-size:.78rem">Prompt: Clinic</button>
          <button type="button" class="secondary" id="s-ipre-jag" style="padding:3px 8px;font-size:.78rem">Prompt: Convoy</button>
        </div>
        <p><button id="s-ibtn" style="background:#059669;color:#fff;border:none;padding:8px 18px;border-radius:6px;font-weight:600;cursor:pointer">Generate Visual</button></p>
        <div id="s-iresult" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid #334155">
          <h4>Generated Image</h4>
          <img id="s-iimg" src="" alt="Generated Preview" style="width:100%;max-width:300px;border-radius:8px;background:#0b1220;border:1px solid #334155;margin-bottom:8px;display:block">
          <div><a id="s-idownload" href="" download="image.png" class="btn" style="display:inline-block;padding:4px 10px;background:#1e293b;border:1px solid #38bdf8;border-radius:4px;color:#38bdf8;text-decoration:none">📥 Download PNG</a></div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3>🧠 Obsidian Second Brain & Flow Tester</h3>
      <p class="mut">Rebuilds and exports the entire memory graph, competitors, regulations, and native <code>.canvas</code> flow view.</p>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <button id="s-mrebuild" class="secondary">🔄 Sync & Rebuild Vault</button>
        <a href="/vault/JA_Assure_Second_Brain.canvas" download="JA_Assure_Second_Brain.canvas" class="btn" style="display:inline-block;padding:6px 12px;background:#1e293b;border:1px solid #38bdf8;border-radius:4px;color:#38bdf8;text-decoration:none">📥 Download Obsidian Canvas (.canvas)</a>
        <button id="s-mview" class="secondary" style="color:#a78bfa;border-color:#a78bfa">Open Memory Graph View →</button>
      </div>
      <div id="s-mstatus" class="mut" style="margin-top:8px"></div>
    </div>
  `;

  // Bind video presets
  $("#s-vpre-jade").onclick = () => { $("#s-vbrand").value = "Jade"; $("#s-vscript").value = PRESET_SCRIPTS["Jade"]; };
  $("#s-vpre-doc").onclick = () => { $("#s-vbrand").value = "DoctorShield"; $("#s-vscript").value = PRESET_SCRIPTS["DoctorShield"]; };
  $("#s-vpre-jag").onclick = () => { $("#s-vbrand").value = "Jaguar Transit"; $("#s-vscript").value = PRESET_SCRIPTS["Jaguar Transit"]; };

  // Bind image presets
  $("#s-ipre-jade").onclick = () => { $("#s-ibrand").value = "Jade"; $("#s-iprompt").value = PRESET_PROMPTS["Jade"]; };
  $("#s-ipre-doc").onclick = () => { $("#s-ibrand").value = "DoctorShield"; $("#s-iprompt").value = PRESET_PROMPTS["DoctorShield"]; };
  $("#s-ipre-jag").onclick = () => { $("#s-ibrand").value = "Jaguar Transit"; $("#s-iprompt").value = PRESET_PROMPTS["Jaguar Transit"]; };

  // Video generation handler
  $("#s-vbtn").onclick = async () => {
    const btn = $("#s-vbtn");
    btn.disabled = true;
    btn.textContent = "Rendering Reel…";
    showBanner("Assembling reel with Edge-TTS and video engine…");
    try {
      const data = await api("/api/studio/reel", {
        method: "POST",
        body: JSON.stringify({
          brand: $("#s-vbrand").value,
          script: $("#s-vscript").value,
          language: $("#s-vlang").value,
          strategy: $("#s-vstrat").value,
        }),
      });
      showBanner("Reel generated successfully!", "demo");
      const resBox = $("#s-vresult");
      resBox.style.display = "block";
      const player = $("#s-vplayer");
      player.src = data.video_url;
      player.load();
      $("#s-vdownloads").innerHTML = `<a href="${esc(data.video_url)}" download>Download MP4</a> · <a href="${esc(data.srt_url)}" download>Download SRT</a> · Strategy: <b>${esc(data.strategy)}</b>`;
      if (data.captions && data.captions.length) {
        $("#s-vcaptions").innerHTML = `<ol class="compact">${data.captions.map(c => `<li>${esc(c.text)} <span class="mut">(${c.start.toFixed(1)}s - ${c.end.toFixed(1)}s)</span></li>`).join("")}</ol>`;
      }
    } catch (e) {
      showBanner("Video generation failed: " + e.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate Video Reel";
    }
  };

  // Image generation handler
  $("#s-ibtn").onclick = async () => {
    const btn = $("#s-ibtn");
    btn.disabled = true;
    btn.textContent = "Generating Visual…";
    showBanner("Calling image engine…");
    try {
      const data = await api("/api/studio/image", {
        method: "POST",
        body: JSON.stringify({
          prompt: $("#s-iprompt").value,
          brand: $("#s-ibrand").value,
          model: $("#s-imodel").value,
        }),
      });
      showBanner("Image generated successfully!", "demo");
      $("#s-iresult").style.display = "block";
      $("#s-iimg").src = data.image_url + "?t=" + Date.now();
      $("#s-idownload").href = data.image_url;
    } catch (e) {
      showBanner("Image generation failed: " + e.message, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate Visual";
    }
  };

  // Obsidian actions
  $("#s-mrebuild").onclick = async () => {
    try {
      showBanner("Rebuilding Obsidian vault…");
      const g = await api("/api/memory/vault");
      $("#s-mstatus").textContent = `Vault rebuilt: ${g.nodes.length} nodes, ${g.edges.length} links written to /vault/ and JA_Assure_Second_Brain.canvas`;
      showBanner("Vault rebuilt successfully!");
    } catch (e) {
      showBanner("Vault rebuild failed: " + e.message, "err");
    }
  };
  $("#s-mview").onclick = () => {
    document.querySelectorAll("#nav button").forEach(x => x.classList.remove("active"));
    $("[data-view=memory]").classList.add("active");
    renderMemory();
  };
}

/* ---------------- boot ---------------- */
const routes = { queue: renderQueue, generate: renderGenerate, studio: renderStudio, metrics: renderMetrics, leads: renderLeads, memory: renderMemory };
$("#nav").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  document.querySelectorAll("#nav button").forEach(x => x.classList.remove("active"));
  b.classList.add("active"); showBanner(""); routes[b.dataset.view]();
});
refreshHealth().then(renderQueue);
