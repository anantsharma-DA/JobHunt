/* Resume tab, AI settings, and the "Tailor resume" window. Uses the helpers already defined in app.js. */

const resumeState = { profile: null, aiState: null, models: [], job: null, tailor: null, dirty: false };

/* ---------- small helpers ---------- */

function setPath(target, path, value) {
  const keys = path.split(".");
  let node = target;
  keys.slice(0, -1).forEach((key) => (node = node[key]));
  node[keys[keys.length - 1]] = value;
}

function lines(value) {
  return String(value || "")
    .split("\n")
    .map((line) => line.replace(/^[•\-*]\s*/, "").trim())
    .filter(Boolean);
}

function commas(value) {
  return String(value || "")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    const old = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => (button.textContent = old), 1200);
  } catch {
    alert("Could not copy. Select the text and press Ctrl+C.");
  }
}

function field(label, path, value, { type = "text", placeholder = "" } = {}) {
  return `<label class="r-field"><span>${esc(label)}</span>
    <input type="${type}" data-path="${esc(path)}" value="${esc(value || "")}" placeholder="${esc(placeholder)}"></label>`;
}

function area(label, path, value, rows = 3, hint = "") {
  return `<label class="r-field"><span>${esc(label)}${hint ? ` <small>${esc(hint)}</small>` : ""}</span>
    <textarea rows="${rows}" data-path="${esc(path)}">${esc(value || "")}</textarea></label>`;
}

function entryBox(title, removePath, body) {
  return `<div class="r-entry"><div class="r-entry-head"><b>${esc(title)}</b>
      <button type="button" class="link-btn" data-remove="${esc(removePath)}">Remove</button></div>${body}</div>`;
}

/* ---------- Resume tab ---------- */

async function loadResume() {
  const data = await api("/api/resume").catch((err) => ({ error: err.message }));
  if (data.error) return alert(data.error);
  resumeState.profile = data.profile;
  renderResume();
}

function renderResume() {
  const p = resumeState.profile;
  if (!p) return;
  const parts = [];
  parts.push(`<fieldset class="r-group"><legend>About you</legend>
    ${field("Full name", "contact.name", p.contact.name)}
    ${field("Job title", "contact.title", p.contact.title, { placeholder: "e.g. Data Analyst" })}
    ${field("Email", "contact.email", p.contact.email, { type: "email" })}
    ${field("Phone", "contact.phone", p.contact.phone)}
    ${field("City", "contact.location", p.contact.location)}
    ${area("Summary", "summary", p.summary, 3, "2-3 lines; the AI rewrites this per job")}</fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Links <small>shown as clickable links in the PDF</small></legend>
    ${p.links.map((link, i) => entryBox(link.label || "Link", `links.${i}`,
      field("Label", `links.${i}.label`, link.label, { placeholder: "Portfolio" }) +
      field("Address", `links.${i}.url`, link.url, { placeholder: "https://…" }))).join("")}
    <button type="button" class="btn small" data-add="links">Add link</button></fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Skills</legend>
    ${p.skills.map((group, i) => entryBox(group.group || "Skills", `skills.${i}`,
      field("Group name", `skills.${i}.group`, group.group, { placeholder: "Analysis" }) +
      area("Skills", `skills.${i}.items`, (group.items || []).join(", "), 2, "separated by commas"))).join("")}
    <button type="button" class="btn small" data-add="skills">Add skill group</button></fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Work experience</legend>
    ${p.experience.map((job, i) => entryBox(`${job.role || "Role"} · ${job.company || "Company"}`, `experience.${i}`,
      field("Company", `experience.${i}.company`, job.company) +
      field("Role", `experience.${i}.role`, job.role) +
      field("From", `experience.${i}.start`, job.start, { placeholder: "Mar 2023" }) +
      field("To", `experience.${i}.end`, job.end, { placeholder: "Present" }) +
      field("Location", `experience.${i}.location`, job.location) +
      area("What you did", `experience.${i}.bullets`, (job.bullets || []).join("\n"), 5, "one point per line"))).join("")}
    <button type="button" class="btn small" data-add="experience">Add job</button></fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Projects</legend>
    ${p.projects.map((project, i) => entryBox(project.name || "Project", `projects.${i}`,
      field("Name", `projects.${i}.name`, project.name) +
      field("Link", `projects.${i}.link`, project.link, { placeholder: "https://github.com/…" }) +
      area("What it does", `projects.${i}.bullets`, (project.bullets || []).join("\n"), 3, "one point per line"))).join("")}
    <button type="button" class="btn small" data-add="projects">Add project</button></fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Education</legend>
    ${p.education.map((item, i) => entryBox(item.degree || "Qualification", `education.${i}`,
      field("Qualification", `education.${i}.degree`, item.degree) +
      field("School or college", `education.${i}.school`, item.school) +
      field("Year", `education.${i}.year`, item.year) +
      field("Extra", `education.${i}.details`, item.details, { placeholder: "e.g. 78%" }))).join("")}
    <button type="button" class="btn small" data-add="education">Add qualification</button></fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Certifications</legend>
    ${p.certifications.map((item, i) => entryBox(item.name || "Certificate", `certifications.${i}`,
      field("Name", `certifications.${i}.name`, item.name) +
      field("From", `certifications.${i}.issuer`, item.issuer) +
      field("Year", `certifications.${i}.year`, item.year))).join("")}
    <button type="button" class="btn small" data-add="certifications">Add certificate</button></fieldset>`);

  parts.push(`<fieldset class="r-group"><legend>Answers application forms ask for</legend>
    ${field("Total experience", "answers.total_experience", p.answers.total_experience, { placeholder: "3 years" })}
    ${field("Notice period", "answers.notice_period", p.answers.notice_period, { placeholder: "30 days" })}
    ${field("Current CTC", "answers.current_ctc", p.answers.current_ctc, { placeholder: "6 LPA" })}
    ${field("Expected CTC", "answers.expected_ctc", p.answers.expected_ctc, { placeholder: "9 LPA" })}
    ${field("Preferred locations", "answers.preferred_locations", p.answers.preferred_locations)}</fieldset>`);

  $("#resume-form").innerHTML = parts.join("");
}

const BLANKS = {
  links: { label: "", url: "" },
  skills: { group: "", items: [] },
  experience: { company: "", role: "", start: "", end: "", location: "", bullets: [] },
  projects: { name: "", link: "", bullets: [] },
  education: { school: "", degree: "", year: "", details: "" },
  certifications: { name: "", issuer: "", year: "" },
};

$("#resume-form").addEventListener("input", (e) => {
  const path = e.target.dataset.path;
  if (!path) return;
  let value = e.target.value;
  if (path.endsWith(".bullets")) value = lines(value);
  else if (path.endsWith(".items")) value = commas(value);
  setPath(resumeState.profile, path, value);
  resumeState.dirty = true;
  $("#resume-saved").hidden = true;
});

$("#resume-form").addEventListener("click", (e) => {
  const add = e.target.closest("[data-add]");
  const remove = e.target.closest("[data-remove]");
  if (add) {
    resumeState.profile[add.dataset.add].push({ ...BLANKS[add.dataset.add] });
  } else if (remove) {
    const [section, index] = remove.dataset.remove.split(".");
    resumeState.profile[section].splice(Number(index), 1);
  } else {
    return;
  }
  resumeState.dirty = true;
  renderResume();
});

$("#resume-save").addEventListener("click", async () => {
  try {
    const data = await api("/api/resume", { method: "PUT", body: resumeState.profile });
    resumeState.profile = data.profile;
    resumeState.dirty = false;
    renderResume();
    const note = $("#resume-saved");
    note.hidden = false;
    setTimeout(() => (note.hidden = true), 2500);
  } catch (err) {
    alert(err.message);
  }
});

async function importResume(body, filename) {
  const box = $("#resume-import-result");
  box.hidden = false;
  box.className = "import-result";
  box.textContent = "Reading your resume with the AI… this takes a few seconds.";
  try {
    const resp = await fetch(`/api/resume/import?filename=${encodeURIComponent(filename)}`, {
      method: "POST",
      body,
      headers: { "X-JobHunt": "1" },
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `Import failed (${resp.status})`);
    resumeState.profile = data.profile;
    resumeState.dirty = true;
    renderResume();
    box.className = "import-result ok";
    box.textContent = `Filled in from your resume using ${data.model}. Check every field, then press "Save resume details".`;
  } catch (err) {
    box.className = "import-result err";
    box.textContent = err.message;
  }
}

$("#resume-import-btn").addEventListener("click", () => {
  const file = $("#resume-file").files[0];
  if (!file) return alert("Choose a resume file first.");
  importResume(file, file.name);
});

$("#resume-paste-btn").addEventListener("click", () => {
  const text = $("#resume-paste").value.trim();
  if (!text) return alert("Paste your resume text first.");
  importResume(new Blob([text], { type: "text/plain" }), "pasted.txt");
});

/* ---------- AI settings ---------- */

async function loadAiSettings() {
  const data = await api("/api/ai").catch((err) => ({ error: err.message }));
  if (data.error) return;
  // Keep the models already fetched and any key typed but not saved yet.
  const before = new Map((resumeState.aiState || []).map((s) => [s.provider, s]));
  resumeState.aiState = data.chain.map((step) => ({
    ...step,
    available: before.get(step.provider)?.available || [],
    typedKey: before.get(step.provider)?.typedKey || "",
  }));
  renderAiChain();
}

function aiCard(step, index, total) {
  const models = step.available.length ? step.available : step.models.map((id) => ({ id, name: id, free: false }));
  const list = models.length
    ? models
        .map((m) => `<label title="${esc(m.id)}"><input type="checkbox" data-model="${esc(m.id)}"
            ${step.models.includes(m.id) ? "checked" : ""}> ${esc(m.name)}
            ${m.free ? '<span class="chip free">free</span>' : ""}
            ${m.context ? `<small>${Math.round(m.context / 1000)}k</small>` : ""}</label>`)
        .join("")
    : `<p class="hint">Press "Fetch models" to see what this service offers.</p>`;
  const keyNote = step.has_key
    ? `A key is saved (${esc(step.key_hint)}). Leave this empty to keep it, or type a new one.`
    : `Get ${step.free_only ? "a free key" : "a key"} at <a href="${esc(safeUrl(step.key_url))}" target="_blank" rel="noopener noreferrer">${esc(step.key_url)}</a>.`;
  const ready = step.has_key && step.models.length && step.enabled;
  return `<div class="ai-card ${ready ? "ready" : ""} ${step.enabled ? "" : "off"}" data-provider="${esc(step.provider)}">
    <div class="ai-card-head">
      <span class="ai-order">${index + 1}</span>
      <b>${esc(step.label)}</b>
      ${ready ? '<span class="chip good">ready</span>' : ""}
      <label><input type="checkbox" data-enable ${step.enabled ? "checked" : ""}> Use</label>
      <span class="grow"></span>
      <button type="button" class="btn small" data-move="up" ${index === 0 ? "disabled" : ""} title="Try this earlier">↑</button>
      <button type="button" class="btn small" data-move="down" ${index === total - 1 ? "disabled" : ""} title="Try this later">↓</button>
    </div>
    <p class="hint">${esc(step.note)}</p>
    <label class="r-field"><span>API key</span>
      <input type="password" data-key value="${esc(step.typedKey)}" placeholder="Paste your ${esc(step.label)} key"
        autocomplete="off" spellcheck="false">
      <small>${keyNote}</small></label>
    <div class="import-actions">
      <button type="button" class="btn small" data-fetch>Fetch models</button>
      <span class="ai-chosen">${step.models.length ? `Using: ${esc(step.models.join(", "))}` : "No model ticked yet."}</span>
    </div>
    <div class="checks scroll ai-models">${list}</div>
  </div>`;
}

function renderAiChain() {
  const chain = resumeState.aiState || [];
  $("#ai-chain").innerHTML = chain.map((step, i) => aiCard(step, i, chain.length)).join("");
}

function aiStep(element) {
  const provider = element.closest(".ai-card").dataset.provider;
  return resumeState.aiState.find((s) => s.provider === provider);
}

function aiPayload() {
  const keys = {};
  resumeState.aiState.forEach((step) => {
    if (step.typedKey) keys[step.provider] = step.typedKey;
  });
  return {
    chain: resumeState.aiState.map((s) => ({ provider: s.provider, models: s.models, enabled: s.enabled })),
    keys,
  };
}

function aiResult(text, ok) {
  const box = $("#ai-result");
  box.hidden = false;
  box.className = `import-result ${ok ? "ok" : "err"}`;
  box.textContent = text;
}

$("#ai-chain").addEventListener("input", (e) => {
  if (e.target.matches("[data-key]")) aiStep(e.target).typedKey = e.target.value.trim();
});

$("#ai-chain").addEventListener("change", (e) => {
  const step = aiStep(e.target);
  if (e.target.matches("[data-enable]")) {
    step.enabled = e.target.checked;
    renderAiChain();
  } else if (e.target.matches("[data-model]")) {
    const id = e.target.dataset.model;
    step.models = e.target.checked ? [...step.models, id] : step.models.filter((m) => m !== id);
    renderAiChain();
  }
});

$("#ai-chain").addEventListener("click", async (e) => {
  const move = e.target.closest("[data-move]");
  const fetchBtn = e.target.closest("[data-fetch]");
  if (move) {
    const chain = resumeState.aiState;
    const index = chain.indexOf(aiStep(move));
    const to = move.dataset.move === "up" ? index - 1 : index + 1;
    if (to < 0 || to >= chain.length) return;
    [chain[index], chain[to]] = [chain[to], chain[index]];
    renderAiChain();
  } else if (fetchBtn) {
    const step = aiStep(fetchBtn);
    fetchBtn.disabled = true;
    try {
      if (step.typedKey) await api("/api/ai", { method: "PUT", body: aiPayload() }); // some lists need the key
      const data = await api(`/api/ai/models?provider=${encodeURIComponent(step.provider)}`);
      step.available = data.models;
      renderAiChain();
      aiResult(`${step.label}: ${data.models.length} models available.`, true);
    } catch (err) {
      aiResult(`${step.label}: ${err.message}`, false);
    } finally {
      fetchBtn.disabled = false;
    }
  }
});

$("#ai-test").addEventListener("click", async () => {
  $("#ai-test").disabled = true;
  aiResult("Trying your services in order…", true);
  try {
    await api("/api/ai", { method: "PUT", body: aiPayload() });
    const data = await api("/api/ai/test", { method: "POST" });
    aiResult(`Working. ${data.model} replied: "${data.reply}"`, true);
    resumeState.aiState.forEach((s) => (s.typedKey = ""));
    loadAiSettings();
  } catch (err) {
    aiResult(err.message, false);
  } finally {
    $("#ai-test").disabled = false;
  }
});

$("#ai-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/ai", { method: "PUT", body: aiPayload() });
    resumeState.aiState.forEach((s) => (s.typedKey = ""));
    await loadAiSettings();
    const note = $("#ai-saved");
    note.hidden = false;
    setTimeout(() => (note.hidden = true), 2500);
  } catch (err) {
    aiResult(err.message, false);
  }
});

/* ---------- Tailoring a resume for one job ---------- */

function flagsHtml(flags) {
  if (!flags.length) return `<p class="flags-ok">Nothing invented: every word matches your saved details.</p>`;
  return `<div class="flags"><b>${flags.length} thing${flags.length > 1 ? "s" : ""} to check</b>
    <p class="hint">These are not in your resume details. Edit the wording above, or accept them if they are true.</p>
    <ul>${flags
      .map((f) => `<li><span class="flag-where">${esc(f.where)}</span> <span class="flag-why">${esc(f.why)}</span>
        <div class="flag-terms">${f.terms.map((t) => `<span class="chip warn">${esc(t)}</span>`).join("")}</div>
        <div class="flag-text">${esc(f.text)}</div></li>`)
      .join("")}</ul></div>`;
}

function atsHtml(ats) {
  return `<div class="ats"><div class="ats-head"><b>ATS check</b>
      <span class="ats-score ${ats.score >= 75 ? "good" : ats.score >= 50 ? "mid" : "low"}">${ats.score}/100</span></div>
    <p class="hint">${esc(ats.note)} Keyword match ${ats.coverage}% · ${ats.words} words.</p>
    <div class="ats-keys"><b>Matched:</b> ${ats.matched.map((k) => `<span class="chip good">${esc(k)}</span>`).join("") || "none"}</div>
    <div class="ats-keys"><b>Missing:</b> ${ats.missing.map((k) => `<span class="chip">${esc(k)}</span>`).join("") || "none"}</div>
    <ul class="ats-checks">${ats.checks
      .map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${esc(c.name)} <small>${esc(c.detail)}</small></li>`)
      .join("")}</ul></div>`;
}

function draftEditorHtml(result) {
  const d = result.draft;
  return `<div class="tailor-grid">
    <div class="tailor-edit">
      ${area("Summary", "summary", d.summary, 3)}
      ${d.skills.map((g, i) => area(`Skills · ${g.group}`, `skills.${i}.items`, (g.items || []).join(", "), 2, "commas")).join("")}
      ${d.experience.map((e, i) => area(`${e.role} · ${e.company}`, `experience.${i}.bullets`, (e.bullets || []).join("\n"), 5, "one per line")).join("")}
      ${d.projects.map((p, i) => area(`Project · ${p.name}`, `projects.${i}.bullets`, (p.bullets || []).join("\n"), 3, "one per line")).join("")}
      ${d.left_out && d.left_out.length ? `<p class="hint">Left out for this job: ${esc(d.left_out.join("; "))}</p>` : ""}
    </div>
    <div class="tailor-side">${flagsHtml(result.flags)}${atsHtml(result.ats)}${humanHtml(result.human)}</div>
  </div>`;
}

function humanHtml(h) {
  if (!h) return "";
  const level = h.score >= 75 ? "good" : h.score >= 50 ? "mid" : "low";
  const parts = `Built-in check ${h.style_score}${h.reviewer_score != null ? ` · AI reviewer ${h.reviewer_score} (${esc(h.reviewer)})` : ""}`;
  return `<div class="ats human"><div class="ats-head"><b>Sounds human</b>
      <span class="ats-score ${level}">${h.score}/100</span></div>
    <p class="hint">${esc(h.note)} ${parts}.</p>
    ${h.phrases.length ? `<div class="ats-keys"><b>Sounds generated:</b> ${h.phrases.map((p) => `<span class="chip warn">${esc(p)}</span>`).join("")}</div>` : ""}
    ${h.notes.length ? `<ul class="ats-checks">${h.notes.map((n) => `<li class="bad">✗ ${esc(n)}</li>`).join("")}</ul>` : ""}</div>`;
}

function collectDraft() {
  const draft = JSON.parse(JSON.stringify(resumeState.tailor.draft));
  $$("#tailor-body [data-path]").forEach((el) => {
    const path = el.dataset.path;
    let value = el.value;
    if (path.endsWith(".bullets")) value = lines(value);
    else if (path.endsWith(".items")) value = commas(value);
    setPath(draft, path, value);
  });
  return draft;
}

function showTailorOverlay(title) {
  $("#tailor-title").textContent = title;
  $("#tailor-overlay").hidden = false;
  document.body.classList.add("locked");
}

function closeTailor() {
  $("#tailor-overlay").hidden = true;
  document.body.classList.remove("locked");
  resumeState.tailor = null;
  clearTimeout(resumeState.runTimer); // a run keeps going on the server; reopening the job shows it again
}

$("#tailor-close").addEventListener("click", closeTailor);

function tailorButtons({ pdf = false, again = false, stop = false } = {}) {
  $("#tailor-pdf").hidden = !pdf;
  $("#tailor-again").hidden = !again;
  $("#tailor-stop").hidden = !stop;
  $("#tailor-anyway").hidden = true;
}

async function openTailor(job) {
  resumeState.job = job;
  showTailorOverlay(`Tailor resume · ${job.title} · ${job.company}`);
  tailorButtons();
  $("#tailor-status").textContent = "";
  $("#tailor-body").innerHTML = `<p class="hint">Looking for a saved version…</p>`;
  const run = await api("/api/tailor-run/status").catch(() => null);
  if (run && run.running && run.job_id === job.id) return pollRun(); // still working on this job from before
  const saved = await api(`/api/jobs/${job.id}/tailor`).catch(() => null);
  if (saved && saved.draft) {
    resumeState.tailor = saved;
    renderTailor(saved, `Saved draft from ${new Date(saved.created_at).toLocaleString()}`);
  } else {
    runTailor(job);
  }
}

async function runTailor(job) {
  const settings = await api("/api/settings").catch(() => ({}));
  if (settings.ats_target || settings.human_target) return startRun(job, true);
  $("#tailor-body").innerHTML = `<p class="hint">Asking the AI to fit your resume to this job… this can take a minute or two.</p>`;
  tailorButtons();
  try {
    const result = await api(`/api/jobs/${job.id}/tailor`, { method: "POST" });
    resumeState.tailor = result;
    renderTailor(result, `Written by ${result.model}`);
  } catch (err) {
    showTailorError(err.message);
  }
}

function showTailorError(message) {
  $("#tailor-body").innerHTML = `<p class="import-result err">${esc(message)}</p>
    <p class="hint">Check the Settings tab: an AI service, a key and at least one model are needed. Free models are often busy; pick a few as backups.</p>`;
  tailorButtons({ again: true });
}

function renderTailor(result, statusText) {
  $("#tailor-body").innerHTML = draftEditorHtml(result) + applyPackHtml();
  $("#tailor-status").textContent = statusText;
  tailorButtons({ pdf: true, again: true });
  $("#tailor-pdf").textContent = "Make PDF";
  loadApplyPack(resumeState.job.id);
}

/* ---------- Tailoring in rounds until the targets on the Settings tab are met ---------- */

async function startRun(job, checkCeiling) {
  $("#tailor-body").innerHTML = `<p class="hint">Starting…</p>`;
  tailorButtons();
  try {
    const status = await api(`/api/jobs/${job.id}/tailor-run`, { method: "POST", body: { check_ceiling: checkCeiling } });
    if (status.needs_skills) {
      $("#tailor-body").innerHTML = skillsAskHtml(status);
      $("#tailor-status").textContent = "";
      return;
    }
    pollRun();
  } catch (err) {
    showTailorError(err.message);
  }
}

function skillsAskHtml(r) {
  const missing = r.ceiling.missing || [];
  const blockers = r.ceiling.blockers || [];
  const ask = missing.length
    ? `<p class="hint">The advert asks for the skills below, which aren't in your resume details. Tick only the ones you
        really have: they are added to your details (under "Also skilled in") and used from now on.</p>
      <div class="checks">${missing.map((k) => `<label><input type="checkbox" value="${esc(k)}"> ${esc(k)}</label>`).join("")}</div>`
    : "";
  return `<div class="skills-ask">
    <h3>An ATS score of ${r.target} can't be reached honestly with your current details</h3>
    <p class="hint">The best your details allow is about ${r.ceiling.best_score}.</p>
    ${blockers.length ? `<ul class="ats-checks">${blockers.map((b) => `<li class="bad">✗ ${esc(b)}</li>`).join("")}</ul>` : ""}
    ${ask}
    <div class="import-actions">
      ${missing.length ? '<button type="button" class="btn primary" id="skills-add">Add ticked skills and continue</button>' : ""}
      <button type="button" class="btn" id="skills-skip">${missing.length ? "Continue without them" : "Continue anyway"}</button>
    </div></div>`;
}

function runProgressHtml(s) {
  const t = s.targets || {};
  const targets = [t.ats ? `ATS ${t.ats}` : "", t.human ? `sounds human ${t.human}` : ""].filter(Boolean).join(" and ");
  const log = s.log
    .map((e) => `<li>Round ${e.round}: ${e.model ? esc(e.model) : ""}${e.ats != null ? ` · ATS ${e.ats}` : ""}${
      e.human != null ? ` · human ${e.human}` : ""}${e.honest === false ? " · has invented claims" : ""}${e.note ? ` · ${esc(e.note)}` : ""}</li>`)
    .join("");
  return `<div class="run-progress"><p><span class="spinner small"></span> <b>Round ${s.round} of ${s.rounds}</b>
      <span class="hint">${esc(s.phase || "")}</span></p>
    <p class="hint">Target: ${esc(targets)}. It stops as soon as the target is met and keeps the best version either way.</p>
    <ol class="run-log">${log}</ol></div>`;
}

async function pollRun() {
  clearTimeout(resumeState.runTimer);
  const s = await api("/api/tailor-run/status").catch(() => null);
  if (!s || $("#tailor-overlay").hidden) return;
  if (s.running) {
    $("#tailor-body").innerHTML = runProgressHtml(s);
    $("#tailor-status").textContent = s.stopping ? "Stopping after this step…" : "";
    tailorButtons({ stop: !s.stopping });
    resumeState.runTimer = setTimeout(pollRun, 1500);
    return;
  }
  if (!s.result) return showTailorError(s.error || "No version could be written.");
  const r = s.result;
  resumeState.tailor = r;
  const t = r.targets;
  const scores = [t.ats ? `ATS ${r.ats.score} of ${t.ats}` : `ATS ${r.ats.score}`,
    r.human ? (t.human ? `human ${r.human.score} of ${t.human}` : `human ${r.human.score}`) : ""].filter(Boolean).join(" · ");
  const outcome = r.met ? "Target met" : s.stopped ? "Stopped; best version so far" : `Best after ${s.log.length} round${s.log.length > 1 ? "s" : ""}`;
  renderTailor(r, `${outcome}: ${scores} · ${r.model}${s.error ? ` · ${s.error}` : ""}`);
}

$("#tailor-stop").addEventListener("click", async () => {
  $("#tailor-stop").hidden = true;
  await api("/api/tailor-run/stop", { method: "POST" }).catch(() => null);
});

$("#tailor-again").addEventListener("click", () => resumeState.job && runTailor(resumeState.job));

$("#tailor-pdf").addEventListener("click", () => makePdf(false));
$("#tailor-anyway").addEventListener("click", () => makePdf(true));

async function makePdf(acceptFlags) {
  const job = resumeState.job;
  $("#tailor-pdf").disabled = true;
  $("#tailor-status").textContent = "Making the PDF… if it runs past one page, the AI shortens it first (up to a minute).";
  try {
    const result = await api(`/api/jobs/${job.id}/resume`, {
      method: "POST",
      body: { draft: collectDraft(), accept_flags: acceptFlags },
    });
    if (result.shortened) {
      // Every resume is one page: this one ran over, so the AI cut it. Nothing is printed until you check it.
      resumeState.tailor = { ...resumeState.tailor, draft: result.draft, flags: result.flags, ats: result.ats };
      renderTailor(resumeState.tailor, result.fits
        ? `It was about ${result.was_over}% too long for one page, so ${result.model} shortened it. Check the wording, then press Make PDF.`
        : `Shortened by ${result.model}, but still about ${result.still_over}% too long for one page. Remove a few more bullets, then press Make PDF.`);
      return;
    }
    if (result.needs_review) {
      resumeState.tailor = { ...resumeState.tailor, draft: result.draft, flags: result.flags };
      $("#tailor-body").querySelector(".tailor-side").innerHTML = flagsHtml(result.flags) + atsHtml(resumeState.tailor.ats);
      $("#tailor-anyway").hidden = false;
      $("#tailor-status").textContent = "Check the flagged wording first.";
      return;
    }
    const fitted = result.layout > 1 ? " (text and spacing tightened slightly to fit)" : "";
    $("#tailor-status").textContent = `Saved ${result.file} · ATS ${result.ats.score}/100 · 1 page${fitted}`;
    $("#tailor-anyway").hidden = true;
    $("#tailor-body").querySelector(".tailor-side").innerHTML = flagsHtml([]) + atsHtml(result.ats);
    loadApplyPack(job.id);
    loadTailoredList(); // the Resume tab's list shows the new PDF
  } catch (err) {
    $("#tailor-status").textContent = err.message;
  } finally {
    $("#tailor-pdf").disabled = false;
  }
}

/* ---------- Getting ready to apply ---------- */

function applyPackHtml() {
  return `<div class="apply-pack" id="apply-pack"><p class="hint">Loading your application details…</p></div>`;
}

async function loadApplyPack(jobId) {
  const box = $("#apply-pack");
  if (!box) return;
  const pack = await api(`/api/jobs/${jobId}/apply-pack`).catch((err) => ({ error: err.message }));
  if (pack.error) {
    box.innerHTML = `<p class="import-result err">${esc(pack.error)}</p>`;
    return;
  }
  const file = pack.resume.file
    ? `<a class="btn small" href="/api/jobs/${jobId}/resume/file" target="_blank" rel="noopener noreferrer">Open the PDF</a>
       <button type="button" class="btn small" data-copy="${esc(pack.resume.folder)}">Copy folder path</button>
       <span class="hint">${esc(pack.resume.file)} · ATS ${pack.resume.ats_score ?? "–"}/100</span>`
    : `<span class="hint">No PDF yet. Press "Make PDF" above.</span>`;
  const answers = pack.answers
    .map((a) => `<li><b>${esc(a.label)}</b> <span>${esc(a.value)}</span>
      <button type="button" class="btn small" data-copy="${esc(a.value)}">Copy</button></li>`)
    .join("");
  const applied = pack.status === "applied";
  const apply = pack.apply_url
    ? `<a class="btn primary" data-pack-apply href="${esc(pack.apply_url)}" target="_blank" rel="noopener noreferrer">${applied ? "Open again" : "Apply"}</a>
       <span class="hint" id="pack-applied">${applied ? "Applied ✓" : "Opens the job's apply page and moves it to Applied."}</span>`
    : `<span class="hint">This job has no apply link.</span>`;
  box.innerHTML = `<h3>Ready to apply</h3>
    <p class="hint">JobHunt does not send applications for you: open the job's own page and paste these in.</p>
    <div class="pack-row">${apply}</div>
    <div class="pack-row">${file}</div>
    <ul class="pack-answers">${answers || "<li class='hint'>Fill in the Resume tab to have answers ready.</li>"}</ul>
    <div class="pack-note">
      <div class="pack-row"><b>Cover note</b>
        <button type="button" class="btn small" id="note-write">${pack.cover_note ? "Write again" : "Write with AI"}</button>
        <button type="button" class="btn small" data-copy-note>Copy</button></div>
      <textarea id="note-text" rows="5" placeholder="Written from your saved details only.">${esc(pack.cover_note || "")}</textarea>
      <p class="hint" id="note-status"></p>
    </div>`;
}

/* Same as Apply on a job card: the job moves to the Applied tab (the card's toast offers Undo). */
async function markApplied(link) {
  const id = resumeState.job.id;
  const job = state.jobs.find((j) => j.id === id);
  if (job && job.status === "applied") return;
  if (job) {
    setTimeout(() => setStatus(job, "applied"), 0);
  } else {
    await api(`/api/jobs/${id}`, { method: "PATCH", body: { status: "applied" } }).catch((err) => alert(err.message));
  }
  link.textContent = "Open again";
  const note = $("#pack-applied");
  if (note) note.textContent = "Applied ✓";
}

$("#tailor-body").addEventListener("click", async (e) => {
  if (e.target.closest("#skills-add, #skills-skip")) {
    const skills = e.target.closest("#skills-add")
      ? $$("#tailor-body .skills-ask input:checked").map((cb) => cb.value)
      : [];
    if (skills.length) {
      try {
        await api("/api/resume/skills", { method: "POST", body: { skills } });
        resumeState.profile = null; // the Resume tab reloads with the added skills next time it opens
      } catch (err) {
        return alert(err.message);
      }
    }
    return startRun(resumeState.job, false); // you've decided; don't ask again for this run
  }
  const copy = e.target.closest("[data-copy]");
  if (copy) return copyText(copy.dataset.copy, copy);
  const apply = e.target.closest("[data-pack-apply]");
  if (apply) return markApplied(apply); // the link itself opens the apply page in a new tab
  if (e.target.closest("[data-copy-note]")) return copyText($("#note-text").value, e.target);
  if (!e.target.closest("#note-write")) return;
  const button = e.target;
  button.disabled = true;
  $("#note-status").textContent = "Writing…";
  try {
    const result = await api(`/api/jobs/${resumeState.job.id}/cover-note`, { method: "POST" });
    $("#note-text").value = result.note;
    $("#note-status").textContent = result.flags.length
      ? `Written by ${result.model}. Check the highlighted words: ${result.flags.map((f) => f.terms.join(", ")).join("; ")}`
      : `Written by ${result.model}. Nothing in it is outside your saved details.`;
  } catch (err) {
    $("#note-status").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});

/* ---------- Wiring into the rest of the page ---------- */

$("#job-list").addEventListener("click", (e) => {
  const button = e.target.closest("[data-act=tailor]");
  if (!button) return;
  const card = button.closest("article.job-card");
  const job = state.jobs.find((j) => String(j.id) === card.dataset.id);
  if (job) openTailor(job);
});

/* ---------- Tailored resumes on the Resume tab ---------- */

async function loadTailoredList() {
  const box = $("#tailored-list");
  const r = await api("/api/tailored").catch((err) => ({ error: err.message }));
  if (r.error) {
    box.innerHTML = `<p class="import-result err">${esc(r.error)}</p>`;
    return;
  }
  resumeState.tailoredList = r.resumes;
  if (!r.resumes.length) {
    box.innerHTML = `<p class="hint">None yet. Press <b>Tailor resume</b> on a job, then <b>Make PDF</b>.</p>`;
    return;
  }
  const rows = r.resumes.map((t) => {
    const name = t.job_exists ? `${esc(t.title)} · ${esc(t.company || "")}` : `<span class="hint">Job no longer in the list</span>`;
    const made = new Date(t.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    const file = t.file
      ? `<a class="btn small" href="/api/jobs/${t.job_id}/resume/file" target="_blank" rel="noopener noreferrer">Open PDF</a>
         <a class="btn small primary" href="/api/jobs/${t.job_id}/resume/file?download=1" download="${esc(t.file)}">Download</a>`
      : `<span class="hint">Draft only: no PDF yet.</span>`;
    const edit = t.job_exists ? `<button type="button" class="btn small" data-tailored-edit="${t.job_id}">Edit</button>` : "";
    const del = `<button type="button" class="btn small danger" data-tailored-delete="${t.job_id}">Delete</button>`;
    return `<li><div class="tailored-name"><b>${name}</b>
        <span class="hint">${t.file ? esc(t.file) + " · " : ""}made ${esc(made)}${t.ats_score != null ? ` · ATS ${t.ats_score}/100` : ""}</span></div>
      <div class="tailored-actions">${file}${edit}${del}</div></li>`;
  }).join("");
  box.innerHTML = `<ul>${rows}</ul>
    <p class="hint">The PDFs are also saved in <code>${esc(r.folder)}</code>
      <button type="button" class="btn small" data-copy="${esc(r.folder)}">Copy folder path</button></p>`;
}

$("#tailored-list").addEventListener("click", (e) => {
  const copy = e.target.closest("[data-copy]");
  if (copy) return copyText(copy.dataset.copy, copy);
  const del = e.target.closest("[data-tailored-delete]");
  if (del) return deleteTailored(del);
  const edit = e.target.closest("[data-tailored-edit]");
  if (!edit) return;
  const t = (resumeState.tailoredList || []).find((x) => String(x.job_id) === edit.dataset.tailoredEdit);
  if (t) openTailor({ id: t.job_id, title: t.title, company: t.company || "" });
});

async function deleteTailored(button) {
  const t = (resumeState.tailoredList || []).find((x) => String(x.job_id) === button.dataset.tailoredDelete);
  if (!t) return;
  const what = t.job_exists ? `${t.title} · ${t.company || ""}` : "this resume";
  const file = t.file ? `\n\nThe PDF file ${t.file} will be deleted from your computer too.` : "";
  if (!confirm(`Delete the tailored resume for ${what}?${file}\n\nThis can't be undone.`)) return;
  button.disabled = true;
  try {
    await api(`/api/jobs/${t.job_id}/tailored`, { method: "DELETE" });
  } catch (err) {
    button.disabled = false;
    return alert(err.message);
  }
  loadTailoredList();
}

$$(".tab[data-tab=resume]").forEach((tab) => tab.addEventListener("click", () => {
  if (!resumeState.profile) loadResume();
  loadTailoredList();
}));
$$(".tab[data-tab=settings]").forEach((tab) => tab.addEventListener("click", () => {
  if (!resumeState.aiState) loadAiSettings();
  loadTargets();
  loadSearchSettings();
}));

/* ---------- Settings: tailoring targets and the interview-question search key ---------- */

async function loadTargets() {
  const s = await api("/api/settings").catch(() => null);
  if (!s) return;
  $("#t-ats").value = s.ats_target || 0;
  $("#t-human").value = s.human_target || 0;
  $("#t-rounds").value = s.tailor_rounds || 3;
}

$("#targets-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const number = (id, fallback) => Math.round(Number($(id).value || fallback));
  try {
    await api("/api/settings", {
      method: "PUT",
      body: { ats_target: number("#t-ats", 0), human_target: number("#t-human", 0), tailor_rounds: number("#t-rounds", 3) },
    });
    const note = $("#targets-saved");
    note.hidden = false;
    setTimeout(() => (note.hidden = true), 2500);
  } catch (err) {
    alert(err.message);
  }
});

function renderSearchSettings(s) {
  const u = s.usage;
  $("#tavily-note").textContent = s.has_tavily
    ? `A key is saved (${s.tavily_hint}). Leave this empty to keep it, or type a new one.`
    : "No Tavily key saved.";
  const gemini = !s.has_gemini
    ? "Gemini: no key yet"
    : u.gemini_unavailable
      ? "Gemini: Google doesn't offer free web search on this key, so Tavily is used"
      : `Gemini ${u.gemini_today} of ${u.gemini_cap} today`;
  $("#search-usage").textContent = `Used: ${gemini} · Tavily ${u.tavily_month} of ${u.tavily_cap.toLocaleString("en-IN")} credits this month (a search uses 2-4).`;
}

async function loadSearchSettings() {
  const s = await api("/api/interview/settings").catch(() => null);
  if (s) renderSearchSettings(s);
}

$("#search-key-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const key = $("#tavily-key").value.trim();
  if (!key) return alert("Paste a Tavily key first.");
  try {
    renderSearchSettings(await api("/api/interview/settings", { method: "PUT", body: { key } }));
    $("#tavily-key").value = "";
    const note = $("#search-saved");
    note.hidden = false;
    setTimeout(() => (note.hidden = true), 2500);
  } catch (err) {
    alert(err.message);
  }
});

/* ---------- Interview questions: on a job, and on their own tab ---------- */

function qaListHtml(questions) {
  return questions
    .map((q) => {
      const badge = (q.new ? `<span class="chip good">new</span>` : "")
        + (q.verified ? `<span class="chip good">verified · ${q.sites.length} sites</span>` : "");
      const answer = q.answer
        ? `<div class="qa-a">${q.answer_source === "ai"
            ? '<span class="chip warn">AI-drafted: check before using</span>'
            : '<span class="chip">answer from the source</span>'}${esc(q.answer)}</div>`
        : "";
      const sources = q.sources
        .map((s) => (safeUrl(s.url)
          ? `<a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener noreferrer">${esc(s.site || s.url)}</a>`
          : esc(s.site)))
        .join(" · ");
      const copy = `Q: ${q.question}${q.answer ? `\nA: ${q.answer}` : ""}`;
      return `<li class="qa-item"><div class="qa-q">${badge}<b>${esc(q.question)}</b></div>${answer}
        <div class="qa-src">Found on: ${sources}${q.found_on ? ` · saved ${esc(q.found_on)}` : ""}</div>
        <button type="button" class="btn small" data-copy="${esc(copy)}">Copy</button></li>`;
    })
    .join("");
}

/* r: a search reply. onlyNew shows just what this search added (the Interview tab; the saved list has the rest). */
function qaHtml(r, { onlyNew = false } = {}) {
  const shown = onlyNew ? r.questions.filter((q) => q.new) : r.questions;
  const searches = (r.google_searches || []).length
    ? `<div class="qa-searches"><b>Searches used:</b> ${r.google_searches.slice(-3)
        .map((g) => `<a href="${esc(safeUrl(g.url))}" target="_blank" rel="noopener noreferrer">${esc(g.query)}</a>`)
        .join(" ")}</div>`
    : "";
  const verified = shown.filter((q) => q.verified).length;
  let head;
  if (r.new_count == null) {
    head = `${shown.length} saved questions, ${verified} verified${r.saved_at ? ` · last searched ${new Date(r.saved_at).toLocaleString()}` : ""}`;
  } else {
    const total = r.questions.length;
    head = `<b>${r.new_count} new question${r.new_count === 1 ? "" : "s"} found</b>${total ? ` · ${total} saved in total` : ""}`
      + (r.searched_with ? ` · found with ${esc(r.searched_with)}` : "");
  }
  const items = qaListHtml(shown);
  return `<p class="hint">${head}</p>
    ${searches}
    ${r.note ? `<p class="hint">${esc(r.note)}</p>` : ""}
    ${items ? `<ol class="qa-list">${items}</ol>` : (r.note ? "" : `<p class="empty">No reported questions were found.</p>`)}
    ${r.answers_problem ? `<p class="hint">${esc(r.answers_problem)}</p>` : ""}`;
}

async function openQa(job, refresh = false) {
  resumeState.qaJob = job;
  $("#qa-title").textContent = `Frequently Asked Questions · ${job.title} · ${job.company}`;
  $("#qa-overlay").hidden = false;
  document.body.classList.add("locked");
  $("#qa-refresh").disabled = true;
  $("#qa-status").textContent = "";
  $("#qa-body").innerHTML = `<p class="hint">${refresh ? "Searching the web again" : "Looking for questions"}… this can take a minute or two.</p>`;
  try {
    const r = await api(`/api/jobs/${job.id}/interview`, { method: "POST", body: { refresh } });
    $("#qa-body").innerHTML = qaHtml(r);
    $("#qa-status").textContent = r.from_saved ? "Saved questions. Search again looks for new ones." : "";
    if (!r.from_saved) loadSavedQuestions();
  } catch (err) {
    $("#qa-body").innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
  } finally {
    $("#qa-refresh").disabled = false;
  }
}

function closeQa() {
  $("#qa-overlay").hidden = true;
  document.body.classList.remove("locked");
}

$("#qa-close").addEventListener("click", closeQa);
$("#qa-refresh").addEventListener("click", () => resumeState.qaJob && openQa(resumeState.qaJob, true));

for (const box of ["#qa-body", "#iq-results", "#saved-titles", "#saved-companies"]) {
  $(box).addEventListener("click", (e) => {
    const copy = e.target.closest("[data-copy]");
    if (copy) copyText(copy.dataset.copy, copy);
    const again = e.target.closest("[data-iq-refresh]");
    if (again) findTitleQuestions([again.dataset.iqRefresh]);
    const saved = e.target.closest("[data-saved-search]");
    if (saved) findSavedQuestions(saved.dataset.title, saved.dataset.company || "", saved);
  });
}

$("#job-list").addEventListener("click", (e) => {
  const button = e.target.closest("[data-act=faq]");
  if (!button) return;
  const card = button.closest("article.job-card");
  const job = state.jobs.find((j) => String(j.id) === card.dataset.id);
  if (job) openQa(job);
});

function interviewPicker() {
  if (!resumeState.iqPicker) {
    resumeState.iqPicker = createPicker($("#iq-picker"), {
      placeholder: "Pick or type job titles",
      groups: titleGroups,
      allOptions: () => state.allTitles,
      onChange: () => {},
    });
  }
  return resumeState.iqPicker;
}

/* Every search here looks for questions not saved yet; the saved ones are listed further down the tab. */
async function findTitleQuestions(titles) {
  $("#iq-find").disabled = true;
  for (const [i, title] of titles.entries()) {
    $("#iq-status").textContent = `Searching ${i + 1} of ${titles.length}: ${title}… (a minute or two each)`;
    const id = `iq-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    let group = document.getElementById(id);
    if (!group) {
      group = document.createElement("div");
      group.id = id;
      group.className = "iq-group";
      $("#iq-results").prepend(group);
    }
    try {
      const r = await api("/api/interview/search", { method: "POST", body: { title, refresh: true } });
      group.innerHTML = `<h3>${esc(title)} <button type="button" class="link-btn" data-iq-refresh="${esc(title)}">Search again</button></h3>${qaHtml(r, { onlyNew: true })}`;
    } catch (err) {
      group.innerHTML = `<h3>${esc(title)}</h3><p class="import-result err">${esc(err.message)}</p>`;
    }
    loadSavedQuestions();
  }
  $("#iq-status").textContent = "";
  $("#iq-find").disabled = false;
}

/* "Search for new questions" on a saved job title or company, from the Saved Questions tab. */
async function findSavedQuestions(title, company, button) {
  button.disabled = true;
  const status = $(company ? "#saved-companies-status" : "#saved-titles-status");
  const name = company ? `${company} · ${title}` : title;
  status.textContent = `Searching for new ${name} questions… (a minute or two)`;
  try {
    const r = await api("/api/interview/search", { method: "POST", body: { title, company, refresh: true } });
    status.textContent = r.new_count
      ? `${name}: ${r.new_count} new question${r.new_count === 1 ? "" : "s"} found. They're marked new below.`
      : `${name}: ${r.note || "0 new questions found."}`;
    resumeState.newIds = new Set(r.questions.filter((q) => q.new).map((q) => q.question));
    await loadSavedQuestions();
  } catch (err) {
    status.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

/* ---------- Saved questions: by job title, and by company ---------- */

function savedGroupHtml(entry, open) {
  const newOnes = resumeState.newIds || new Set();
  const questions = entry.questions.map((q) => ({ ...q, new: newOnes.has(q.question) }));
  const name = entry.company ? `${esc(entry.company)} · ${esc(entry.title)}` : esc(entry.title);
  const search = `<button type="button" class="btn small" data-saved-search data-title="${esc(entry.title)}"
    data-company="${esc(entry.company || "")}">Search for new questions</button>`;
  const when = new Date(entry.saved_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  return `<details class="saved-qa"${open ? " open" : ""}><summary><b>${name}</b>
      <span class="hint">· ${entry.questions.length} questions · ${entry.searches} search${entry.searches === 1 ? "" : "es"} · last ${esc(when)}</span></summary>
    <div class="pack-row">${search}</div>
    <ol class="qa-list">${qaListHtml(questions)}</ol></details>`;
}

function fillFilter(select, values, allLabel) {
  const current = select.value;
  select.innerHTML = `<option value="">${esc(allLabel)}</option>`
    + values.map(([value, count]) => `<option value="${esc(value)}">${esc(value)} (${count})</option>`).join("");
  select.value = values.some(([v]) => v === current) ? current : "";
}

function countBy(entries, key) {
  const counts = new Map();
  for (const e of entries) counts.set(e[key], (counts.get(e[key]) || 0) + e.questions.length);
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
}

function renderSaved() {
  const saved = resumeState.saved || { titles: [], companies: [] };
  const title = $("#saved-title-filter").value;
  const titles = saved.titles.filter((e) => !title || e.title === title);
  $("#saved-titles").innerHTML = titles.map((e) => savedGroupHtml(e, Boolean(title))).join("")
    || `<p class="hint">${saved.titles.length ? "" : "Nothing saved yet. Pick a job title above and press Find questions."}</p>`;
  const company = $("#saved-company-filter").value;
  const companies = saved.companies.filter((e) => !company || e.company === company);
  $("#saved-companies").innerHTML = companies.map((e) => savedGroupHtml(e, Boolean(company))).join("")
    || `<p class="hint">${saved.companies.length ? "" : "Nothing saved yet. Press Frequently Asked Questions on a job."}</p>`;
}

async function loadSavedQuestions() {
  const saved = await api("/api/interview/saved").catch(() => null);
  if (!saved) return;
  resumeState.saved = saved;
  const titleCount = saved.titles.reduce((n, e) => n + e.questions.length, 0);
  const companyCount = saved.companies.reduce((n, e) => n + e.questions.length, 0);
  fillFilter($("#saved-title-filter"), countBy(saved.titles, "title"), `All job titles (${titleCount})`);
  fillFilter($("#saved-company-filter"), countBy(saved.companies, "company"), `All companies (${companyCount})`);
  $("#saved-titles-count").textContent = titleCount ? String(titleCount) : "";
  $("#saved-companies-count").textContent = companyCount ? String(companyCount) : "";
  renderSaved();
}

function showSavedView(view) {
  $$("[data-saved-view]").forEach((b) => {
    const on = b.dataset.savedView === view;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", String(on));
  });
  $("#saved-view-titles").hidden = view !== "titles";
  $("#saved-view-companies").hidden = view !== "companies";
}

$$("[data-saved-view]").forEach((b) => b.addEventListener("click", () => showSavedView(b.dataset.savedView)));
$("#saved-title-filter").addEventListener("change", renderSaved);
$("#saved-company-filter").addEventListener("change", renderSaved);

$("#iq-find").addEventListener("click", () => {
  const titles = interviewPicker().values;
  if (!titles.length) return alert("Pick at least one job title.");
  findTitleQuestions(titles);
});

$$(".tab[data-tab=interview]").forEach((tab) => tab.addEventListener("click", interviewPicker));
$$(".tab[data-tab=saved-questions]").forEach((tab) => tab.addEventListener("click", loadSavedQuestions));

window.addEventListener("beforeunload", (e) => {
  if (resumeState.dirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
