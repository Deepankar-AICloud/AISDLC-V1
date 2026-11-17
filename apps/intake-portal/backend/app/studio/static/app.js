"use strict";

// AISDLC Studio front end. All dynamic text is inserted with textContent; the
// Markdown renderer escapes HTML before adding its own tags. No secrets live here:
// sign-in is checked by the server and the session is an HttpOnly cookie.

const state = { csrf: "", stages: [], jobs: [], current: null, docStage: null, pollTimer: null, listTimer: null };

const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  let payload;
  if (method !== "GET") headers["X-CSRF-Token"] = state.csrf;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(path, { method, headers, body: payload, credentials: "same-origin" });
  let data = null;
  try { data = await res.json(); } catch {
    throw new Error(`The server returned an unreadable response (${res.status}). Please try again.`);
  }
  if (!res.ok) {
    if (res.status === 401 && path !== "/api/login") showLogin();
    const msg = (data && data.error && data.error.message) || `Request failed (${res.status}).`;
    throw new Error(msg);
  }
  return data;
}

function showError(id, msg) {
  const node = $(id);
  node.textContent = msg || "";
  node.hidden = !msg;
}

// ---- auth -----------------------------------------------------------------
function showLogin() {
  clearTimers();
  $("app-view").hidden = true;
  $("who").hidden = true;
  $("login-view").hidden = false;
  $("login-user").focus();
}

async function enterApp(session) {
  state.csrf = session.csrf_token;
  state.stages = session.stages;
  $("username").textContent = session.username;
  const badge = $("mode-badge");
  badge.textContent = session.mode === "ai" ? "AI mode" : "Dry-run mode";
  badge.className = "badge " + (session.mode === "ai" ? "ok" : "warn");
  $("accept-hint").textContent = `Supported: ${session.accept.join(", ")} (max ${session.max_file_mb} MB each)`;
  $("new-files").setAttribute("accept", session.accept.join(","));
  $("login-view").hidden = true;
  $("who").hidden = false;
  $("app-view").hidden = false;
  await refreshList();
  state.listTimer = setInterval(refreshList, 10000);
  const fromHash = location.hash.replace("#", "");
  if (fromHash && /^[0-9a-f]{16}$/.test(fromHash)) openJob(fromHash);
  else showPanel("empty-view");
}

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("login-error", "");
  try {
    await api("/api/login", { method: "POST", body: { username: $("login-user").value, password: $("login-pass").value } });
    $("login-pass").value = "";
    await enterApp(await api("/api/session"));
  } catch (err) {
    showError("login-error", err.message);
  }
});

$("logout").addEventListener("click", async () => {
  try { await api("/api/logout", { method: "POST" }); } catch (err) {
    showError("app-error", `Sign out failed: ${err.message}`);
    return;
  }
  state.current = null;
  location.hash = "";
  showLogin();
});

// ---- layout -----------------------------------------------------------------
function showPanel(id) {
  for (const p of ["new-view", "empty-view", "job-view"]) $(p).hidden = p !== id;
}

function clearTimers() {
  clearInterval(state.listTimer);
  clearTimeout(state.pollTimer);
}

const STATUS_TEXT = {
  queued: "Queued", running: "Running", awaiting_model: "Choose model", awaiting_info: "Needs information",
  review: "Ready for review", needs_attention: "Needs attention", completed: "Completed", failed: "Failed",
};

function stageLabel(key) {
  const s = state.stages.find((x) => x.key === key);
  return s ? s.label : key;
}

async function refreshList() {
  try {
    state.jobs = await api("/api/jobs");
    showError("app-error", "");
  } catch (err) {
    showError("app-error", err.message);
    return;
  }
  const list = $("job-list");
  list.replaceChildren(
    ...state.jobs.map((j) =>
      el("li", { class: state.current && state.current.id === j.id ? "active" : "", onclick: () => openJob(j.id) },
        el("div", { class: "job-title" }, j.title),
        el("div", { class: "job-sub" },
          el("span", { class: `pill ${j.status}` }, STATUS_TEXT[j.status] || j.status),
          ` ${stageLabel(j.stage)}`)))
  );
  if (!state.jobs.length) list.append(el("li", { class: "muted" }, "No requests yet."));
}

$("new-btn").addEventListener("click", () => {
  state.current = null;
  location.hash = "";
  clearTimeout(state.pollTimer);
  showError("new-error", "");
  showPanel("new-view");
  refreshList();
});

$("new-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("new-error", "");
  const form = new FormData();
  form.append("title", $("new-title").value);
  form.append("text", $("new-text").value);
  for (const f of $("new-files").files) form.append("files", f);
  const btn = $("new-submit");
  btn.disabled = true;
  btn.textContent = "Reading documents…";
  try {
    const job = await api("/api/jobs", { method: "POST", form });
    $("new-form").reset();
    await refreshList();
    openJob(job.id);
  } catch (err) {
    showError("new-error", err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Start generation";
  }
});

// ---- job view -----------------------------------------------------------------
async function openJob(id) {
  clearTimeout(state.pollTimer);
  try {
    const job = await api(`/api/jobs/${id}`);
    const switched = !state.current || state.current.id !== id;
    state.current = job;
    if (switched) state.docStage = null;
    location.hash = id;
    showPanel("job-view");
    renderJob(job);
    refreshList();
    if (job.busy) state.pollTimer = setTimeout(() => openJob(id), 3000);
  } catch (err) {
    showPanel("empty-view");
    showError("app-error", err.message);
  }
}

function renderJob(job) {
  $("job-title").textContent = job.title;
  $("job-meta").textContent = `Request #${job.number} · created ${new Date(job.created_at).toLocaleString()}`;
  const dl = $("download");
  dl.hidden = !job.available.length || job.busy;
  dl.href = `/api/jobs/${job.id}/download`;
  $("delete-btn").hidden = job.busy;

  // Stepper
  $("stepper").replaceChildren(
    ...state.stages.map((s) => {
      let cls = "todo";
      if (job.approved.includes(s.key)) cls = "done";
      else if (s.key === job.stage) cls = job.status === "completed" ? "done" : "current";
      return el("li", { class: cls }, el("span", { class: "dot" }), el("span", {}, s.label));
    })
  );

  // Status
  const box = $("status-box");
  box.className = `status ${job.status}`;
  box.replaceChildren(
    ...[
      el("strong", {}, STATUS_TEXT[job.status] || job.status),
      job.busy ? el("span", { class: "spinner" }) : null,
      el("p", {}, job.message || ""),
    ].filter(Boolean)
  );

  renderActions(job);
  renderDocs(job);
  $("events").replaceChildren(
    ...job.events.slice().reverse().map((e) => el("li", {}, el("time", {}, new Date(e.ts).toLocaleTimeString()), " ", e.text))
  );
}

function qcBlock(result) {
  if (!result || result.qc_score === null || result.qc_score === undefined) return null;
  const issues = result.qc_issues || [];
  return el("div", { class: "qc" },
    el("div", {}, "Quality check: ", el("strong", {}, `${result.qc_status || ""} ${result.qc_score}`),
      result.selected_model ? ` · model ${result.selected_model}` : ""),
    result.diagnosis ? el("p", { class: "muted" }, result.diagnosis) : null,
    issues.length ? el("details", {}, el("summary", {}, `${issues.length} finding(s)`),
      el("ul", {}, issues.map((i) => el("li", {}, i)))) : null);
}

function action(label, cls, fn) {
  return el("button", {
    class: cls,
    onclick: async (e) => {
      const b = e.currentTarget;
      b.disabled = true;
      showError("action-error", "");
      try { await fn(); } catch (err) { showError("action-error", err.message); b.disabled = false; }
    },
  }, label);
}

async function post(path, body) {
  const job = await api(`/api/jobs/${state.current.id}/${path}`, { method: "POST", body });
  openJob(job.id);
}

function feedbackForm(label) {
  const ta = el("textarea", { rows: 4, maxlength: 20000, placeholder: "Describe what should change (e.g. add a section on data retention, the users are external customers…)" });
  return el("div", { class: "feedback" },
    el("label", {}, label, ta),
    action("Request changes", "", () => {
      if (!ta.value.trim()) throw new Error("Describe the changes you want first.");
      return post("revise", { text: ta.value });
    }));
}

function renderActions(job) {
  const box = $("action-box");
  const err = el("p", { id: "action-error", class: "error", hidden: true });
  const parts = [];
  const r = job.result || {};
  if (job.busy) {
    parts.push(el("p", { class: "muted" }, "This page updates automatically. Large stages (especially Code) can take a while."));
  } else if (job.status === "awaiting_model") {
    const rec = r.recommendation || {};
    const options = [{ model: rec.model, profile: "Recommended" }, ...(rec.alternatives || [])].filter((o) => o.model);
    const radios = options.map((o, i) =>
      el("label", { class: "radio" },
        el("input", { type: "radio", name: "model", value: o.model, checked: i === 0 }),
        el("strong", {}, o.model), " — ", o.profile || ""));
    const reason = el("input", { placeholder: "Reason for choosing a different model (optional)", maxlength: 500 });
    parts.push(
      el("p", {}, rec.reason || ""),
      rec.estimated_cost ? el("p", { class: "muted" }, `Estimated cost: ${rec.estimated_cost}`) : null,
      el("div", { class: "radios" }, radios),
      reason,
      el("div", { class: "row" }, action("Use this model and generate", "primary", () => {
        const chosen = document.querySelector('input[name="model"]:checked');
        const model = chosen ? chosen.value : null;
        const body = model && model !== rec.model ? { model, reason: reason.value } : {};
        return post("model", body);
      })));
  } else if (job.status === "awaiting_info") {
    const ta = el("textarea", { rows: 6, maxlength: 20000, placeholder: "Answer the questions above…" });
    parts.push(
      el("ol", { class: "questions" }, job.questions.map((q) => el("li", {}, q))),
      el("label", {}, "Your answers", ta),
      el("div", { class: "row" }, action("Submit answers", "primary", () => {
        if (!ta.value.trim()) throw new Error("Enter your answers first.");
        return post("answer", { text: ta.value });
      })));
  } else if (job.status === "review") {
    parts.push(qcBlock(r), el("div", { class: "row" }, action("Approve & continue", "primary", () => post("approve"))),
      feedbackForm("Not quite right? Ask for changes:"));
  } else if (job.status === "needs_attention") {
    parts.push(qcBlock(r), el("div", { class: "row" }, action("Retry", "primary", () => post("retry"))),
      feedbackForm("Give the agent guidance and regenerate:"));
  } else if (job.status === "failed") {
    parts.push(el("div", { class: "row" }, action("Retry", "primary", () => post("retry"))));
  } else if (job.status === "completed") {
    parts.push(el("p", {}, "Every stage is approved. Use “Download bundle” for all documents and the generated code."));
  }
  box.replaceChildren(...parts.filter(Boolean), err);
}

async function renderDocs(job) {
  const card = $("docs-card");
  if (!job.available.length) { card.hidden = true; return; }
  card.hidden = false;
  if (!state.docStage || !job.available.includes(state.docStage)) {
    state.docStage = job.available.includes(job.stage) ? job.stage : job.available[job.available.length - 1];
  }
  $("doc-tabs").replaceChildren(
    ...job.available.map((k) => el("button", {
      class: "tab" + (k === state.docStage ? " active" : ""),
      onclick: () => { state.docStage = k; renderDocs(state.current); },
    }, stageLabel(k)))
  );
  try {
    const doc = await api(`/api/jobs/${job.id}/artifacts/${state.docStage}`);
    $("doc-body").innerHTML = renderMarkdown(doc.markdown);
  } catch (err) {
    $("doc-body").textContent = err.message;
  }
}

$("delete-btn").addEventListener("click", async () => {
  if (!state.current || !confirm("Delete this request and all its generated files?")) return;
  try {
    await api(`/api/jobs/${state.current.id}`, { method: "DELETE" });
    state.current = null;
    location.hash = "";
    showPanel("empty-view");
    refreshList();
  } catch (err) {
    alert(err.message);
  }
});

// ---- safe Markdown -----------------------------------------------------------
function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function inline(s) {
  let out = esc(s);
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  return out;
}

function renderMarkdown(md) {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let i = 0;
  const isTableSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
  const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => inline(c.trim()));
  while (i < lines.length) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {
      const buf = [];
      i++;
      while (i < lines.length && !/^\s*```/.test(lines[i])) buf.push(lines[i++]);
      i++;
      html.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`);
      continue;
    }
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { html.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i++; continue; }
    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) { html.push("<hr>"); i++; continue; }
    if (line.includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) rows.push(cells(lines[i++]));
      html.push(`<div class="table-wrap"><table><thead><tr>${head.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>${
        rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
      continue;
    }
    if (/^\s*>/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
      html.push(`<blockquote>${buf.map(inline).join("<br>")}</blockquote>`);
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line);
      const buf = [];
      while (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) {
        const nested = /^\s{2,}/.test(lines[i]) ? ' class="nested"' : "";
        buf.push(`<li${nested}>${inline(lines[i].replace(/^\s*([-*+]|\d+[.)])\s+/, "").replace(/^\[( |x)\]\s*/i, (m) => (m.includes("x") || m.includes("X") ? "☑ " : "☐ ")))}</li>`);
        i++;
      }
      html.push(ordered ? `<ol>${buf.join("")}</ol>` : `<ul>${buf.join("")}</ul>`);
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*```|\s*>|\s*([-*+]|\d+[.)])\s+)/.test(lines[i])
      && !(lines[i].includes("|") && i + 1 < lines.length && isTableSep(lines[i + 1]))) buf.push(lines[i++]);
    html.push(`<p>${buf.map(inline).join("<br>")}</p>`);
  }
  return html.join("\n");
}

// ---- boot -----------------------------------------------------------------
(async () => {
  try { await enterApp(await api("/api/session")); } catch (err) {
    showLogin();
    if (err.message !== "Please sign in.") showError("login-error", err.message);
  }
})();
