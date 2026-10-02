"use strict";
// The Applied tab as a board: one column per stage, the reminders that are due at the top, and a tracker panel for
// each application (dates, interview time, notes, recruiter). Also the "Reminders and daily auto-search" settings.
// Uses the helpers in app.js ($, esc, api, state, setStatus) and resume.js (openTailor, openQa).

const DEFAULT_STAGES = [
  { id: "applied", label: "Applied" }, { id: "followed_up", label: "Followed up" }, { id: "interview", label: "Interview" },
  { id: "offer", label: "Offer" }, { id: "rejected", label: "Rejected" }, { id: "no_reply", label: "No reply" },
];
const TRACK_FIELDS = ["stage", "applied_on", "followup_on", "interview_at", "notes", "contact_name", "contact_email", "contact_phone"];

const trackState = { stages: DEFAULT_STAGES, items: {}, due: [], followupDays: 7, job: null, loaded: null, autoTask: false, polling: null };

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDays(iso, days) {
  const d = new Date(`${iso}T00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function interviewText(at) {
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }); // like shortDate
}

// A job that has just been moved to Applied has no record on the server yet; show it as the server will.
function appFor(job) {
  const saved = trackState.items[String(job.id)];
  if (saved) return saved;
  const applied = (job.applied_at || "").slice(0, 10) || todayIso();
  return { job_id: job.id, stage: "applied", applied_on: applied, followup_on: null, interview_at: null, notes: "",
           contact_name: "", contact_email: "", contact_phone: "", history: [], followup_due: addDays(applied, trackState.followupDays) };
}

async function loadApplications() {
  try {
    const d = await api("/api/applications");
    Object.assign(trackState, { stages: d.stages, items: d.items, due: d.due, followupDays: d.followup_days, loaded: true });
  } catch {
    return; // the board still shows, from the job list
  }
  renderDueCount();
  if (state.view === "applied" && !$("#tab-jobs").hidden) renderJobs();
}

function renderDueCount() {
  const el = $("#due-count");
  el.textContent = trackState.due.length ? `${trackState.due.length} due` : "";
}

/* ---------- The board (called by renderJobs in app.js on the Applied tab) ---------- */
function dueHtml() {
  if (!trackState.due.length) return "";
  const rows = trackState.due.map((item) => {
    const job = state.jobs.find((j) => j.id === item.job_id);
    if (!job) return "";
    const buttons = {
      followup: `<button class="btn small" data-track-set="followed_up">Mark followed up</button>`,
      no_reply: `<button class="btn small" data-track-again>Follow up again</button><button class="btn small" data-track-set="no_reply">Mark No reply</button>`,
      interview: "",
    }[item.kind];
    return `<li class="due-item ${item.kind}" data-id="${job.id}"><span>${esc(item.text)}</span>
      <span class="due-actions">${buttons}<button class="btn small" data-track-open>Open</button></span></li>`;
  }).join("");
  return `<section class="due-list" aria-label="Reminders due"><h3>Due now</h3><ul>${rows}</ul></section>`;
}

function boardCardHtml(job, app) {
  const url = safeUrl(job.apply_url);
  const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" data-act="apply">${esc(job.title)}</a>` : esc(job.title);
  const today = todayIso();
  const lines = [`Applied ${app.applied_on ? shortDate(app.applied_on) : "(date unknown)"}`];
  if (app.followup_due && ["applied", "followed_up"].includes(app.stage)) {
    const late = app.followup_due <= today;
    lines.push(`<span class="${late ? "late" : ""}">Follow up ${late ? "now" : shortDate(app.followup_due)}</span>`);
  }
  if (app.interview_at) lines.push(`<span class="interview">Interview ${esc(interviewText(app.interview_at))}</span>`);
  const options = trackState.stages.map((s) => `<option value="${s.id}"${s.id === app.stage ? " selected" : ""}>${esc(s.label)}</option>`).join("");
  return `
  <article class="job-card board-card applied" data-id="${job.id}">
    <h4>${title}</h4>
    <div class="company"><b>${esc(job.company)}</b></div>
    <div class="board-dates">${lines.join(" · ")}</div>
    ${app.notes ? `<div class="board-notes">${esc(app.notes.slice(0, 140))}${app.notes.length > 140 ? "…" : ""}</div>` : ""}
    <div class="board-actions">
      <select data-track-stage aria-label="Stage">${options}</select>
      <button class="btn small" data-track-open>Tracker</button>
    </div>
  </article>`;
}

function renderBoard(jobs) {
  if (trackState.loaded === null) {
    trackState.loaded = false;
    loadApplications();
  }
  $("#more-btn").hidden = true; // the board shows every applied job
  const columns = new Map(trackState.stages.map((s) => [s.id, []]));
  jobs.forEach((job) => {
    const app = appFor(job);
    (columns.get(app.stage) || columns.get("applied")).push(boardCardHtml(job, app));
  });
  const board = trackState.stages.map((s) => {
    const cards = columns.get(s.id);
    return `<section class="board-col" data-stage="${s.id}"><h3>${esc(s.label)} <span class="count">${cards.length || ""}</span></h3>
      ${cards.join("") || `<p class="board-empty">None</p>`}</section>`;
  }).join("");
  $("#job-list").innerHTML = `${dueHtml()}<div class="board">${board}</div>`;
}

async function saveApplication(job, changes) {
  const saved = await api(`/api/jobs/${job.id}/application`, { method: "PUT", body: changes });
  trackState.items[String(job.id)] = saved;
  await loadApplications(); // due reminders and the board follow the change
  return saved;
}

$("#job-list").addEventListener("change", async (e) => {
  const select = e.target.closest("[data-track-stage]");
  if (!select) return;
  const job = state.jobs.find((j) => String(j.id) === select.closest("[data-id]").dataset.id);
  select.disabled = true;
  try {
    await saveApplication(job, { stage: select.value });
  } catch (err) {
    alert(err.message);
    renderJobs();
  }
});

$("#job-list").addEventListener("click", async (e) => {
  const target = e.target.closest("[data-track-open], [data-track-set], [data-track-again]");
  if (!target) return;
  const job = state.jobs.find((j) => String(j.id) === target.closest("[data-id]").dataset.id);
  if (!job) return;
  if (target.matches("[data-track-open]")) return openTracker(job);
  target.disabled = true;
  try {
    if (target.matches("[data-track-set]")) await saveApplication(job, { stage: target.dataset.trackSet });
    else await saveApplication(job, { stage: "followed_up", followup_on: addDays(todayIso(), trackState.followupDays) });
  } catch (err) {
    alert(err.message);
    target.disabled = false;
  }
});

/* ---------- Tracker panel ---------- */
function trackerHtml(job, app) {
  const options = trackState.stages.map((s) => `<option value="${s.id}"${s.id === app.stage ? " selected" : ""}>${esc(s.label)}</option>`).join("");
  const next = app.followup_on ? "" : app.followup_due && ["applied", "followed_up"].includes(app.stage)
    ? `Empty: ${shortDate(app.followup_due)} (${trackState.followupDays} days after you ${app.stage === "applied" ? "applied" : "followed up"}).`
    : "Empty: no follow-up reminder at this stage.";
  const labels = Object.fromEntries(trackState.stages.map((s) => [s.id, s.label]));
  const history = (app.history || []).map((h) => `<li>${esc(labels[h.stage] || h.stage)} · ${esc(shortDate(h.on))}</li>`).join("");
  const url = safeUrl(job.apply_url);
  return `
    <div class="track-grid">
      <label class="field"><span>Stage</span><select id="tk-stage">${options}</select></label>
      <label class="field"><span>Applied on</span><input type="date" id="tk-applied_on" value="${esc(app.applied_on || "")}"></label>
      <label class="field"><span>Follow up on</span><input type="date" id="tk-followup_on" value="${esc(app.followup_on || "")}">
        <small>${esc(next)}</small></label>
      <label class="field"><span>Interview</span><input type="datetime-local" id="tk-interview_at" value="${esc(app.interview_at || "")}">
        <small>Reminders a day before and 2 hours before.</small></label>
    </div>
    <label class="field"><span>Notes</span><textarea id="tk-notes" rows="4" maxlength="4000">${esc(app.notes || "")}</textarea></label>
    <h3 class="track-sub">Recruiter or contact</h3>
    <div class="track-grid three">
      <label class="field"><span>Name</span><input id="tk-contact_name" maxlength="120" value="${esc(app.contact_name || "")}"></label>
      <label class="field"><span>Email</span><input type="email" id="tk-contact_email" maxlength="200" value="${esc(app.contact_email || "")}"></label>
      <label class="field"><span>Phone</span><input type="tel" id="tk-contact_phone" maxlength="40" value="${esc(app.contact_phone || "")}"></label>
    </div>
    ${history ? `<h3 class="track-sub">History</h3><ol class="track-history">${history}</ol>` : ""}
    <div class="track-links">
      ${url ? `<a class="btn small" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Open the job page</a>` : ""}
      <button type="button" class="btn small" data-tk="tailor">Tailor resume</button>
      <button type="button" class="btn small" data-tk="outreach">Referral</button>
      <button type="button" class="btn small" data-tk="faq">Frequently Asked Questions</button>
      <button type="button" class="btn small" data-tk="unapply">Not applied</button>
    </div>`;
}

function openTracker(job) {
  trackState.job = job;
  const app = appFor(job);
  $("#track-title").textContent = `${job.title} · ${job.company}`;
  $("#track-body").innerHTML = trackerHtml(job, app);
  $("#track-status").textContent = "";
  $("#track-save").disabled = false;
  $("#track-overlay").hidden = false;
  document.body.classList.add("locked");
}

function closeTracker() {
  $("#track-overlay").hidden = true;
  document.body.classList.remove("locked");
  trackState.job = null;
}

$("#track-close").addEventListener("click", closeTracker);

// Only what you changed is sent, so a stage change still restarts the follow-up clock unless you set a date.
$("#track-save").addEventListener("click", async () => {
  const job = trackState.job;
  const app = appFor(job);
  const changes = {};
  TRACK_FIELDS.forEach((field) => {
    const value = $(`#tk-${field}`).value.trim();
    if (value !== (app[field] || "")) changes[field] = value;
  });
  if (!Object.keys(changes).length) return closeTracker();
  $("#track-save").disabled = true;
  $("#track-status").textContent = "Saving…";
  try {
    await saveApplication(job, changes);
    closeTracker();
  } catch (err) {
    $("#track-status").textContent = err.message;
    $("#track-save").disabled = false;
  }
});

$("#track-body").addEventListener("click", (e) => {
  const button = e.target.closest("[data-tk]");
  if (!button) return;
  const job = trackState.job;
  closeTracker();
  if (button.dataset.tk === "tailor") openTailor(job);
  else if (button.dataset.tk === "faq") openQa(job);
  else if (button.dataset.tk === "outreach") openOutreach(job); // insights.js
  else setStatus(job, "new"); // with Undo, like the card button
});

/* ---------- Settings: reminders and daily auto-search ---------- */
function lastRunText(last) {
  if (!last || !last.at) return "The daily search hasn't run yet."; // {} until the first run
  const when = interviewText(last.at);
  if (last.skipped) return `Last daily search (${when}): skipped, ${last.skipped}.`;
  let text = `Last daily search (${when}): ${last.new} new jobs, ${last.strong} strong matches (${last.min_match}%+).`;
  if (last.top && last.top.length) text += ` Top: ${last.top.join("; ")}`;
  return text;
}

function syncWindowsBox() {
  $("#a-windows").disabled = !$("#a-on").checked;
}

async function loadAutoSettings() {
  const [s, auto] = await Promise.all([api("/api/settings"), api("/api/autosearch").catch(() => ({ task: false, last: null }))]);
  $("#a-followup").value = s.followup_days;
  $("#a-notify").checked = s.notify_on;
  $("#a-on").checked = s.autosearch_on;
  $("#a-time").value = s.autosearch_time;
  $("#a-match").value = s.autosearch_min_match;
  $$("#a-days input").forEach((cb) => (cb.checked = s.autosearch_days.includes(cb.value)));
  trackState.autoTask = auto.task;
  $("#a-windows").checked = auto.task;
  $("#auto-last").textContent = lastRunText(auto.last);
  $("#auto-note").textContent = s.autosearch_windows && !auto.task
    ? "Windows no longer has the JobHunt task (it may have been removed). Press Save to add it again." : "";
  syncWindowsBox();
  if (auto.running) watchAutoSearch();
}

$("#a-on").addEventListener("change", syncWindowsBox);

$("#auto-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const days = $$("#a-days input:checked").map((cb) => cb.value);
  const on = $("#a-on").checked;
  if (on && !days.length) return alert("Tick at least one day for the daily search.");
  if (on && !$("#a-time").value) return alert("Pick a time for the daily search.");
  const body = {
    followup_days: Math.max(1, Math.min(60, Math.round(Number($("#a-followup").value) || 7))),
    notify_on: $("#a-notify").checked,
    autosearch_on: on,
    autosearch_min_match: Math.max(0, Math.min(100, Math.round(Number($("#a-match").value) || 70))),
  };
  if (days.length) body.autosearch_days = days;
  if ($("#a-time").value) body.autosearch_time = $("#a-time").value;
  const note = $("#auto-note");
  try {
    await api("/api/settings", { method: "PUT", body });
    // The Windows task follows the time and days you saved; it's only kept while the daily search is on.
    const wantTask = on && $("#a-windows").checked;
    note.textContent = "";
    if (wantTask || trackState.autoTask) {
      const r = await api("/api/autosearch/schedule", { method: "POST", body: { enabled: wantTask } });
      trackState.autoTask = r.task;
      $("#a-windows").checked = r.task;
      note.textContent = r.message;
    }
  } catch (err) {
    note.textContent = err.message;
    $("#a-windows").checked = trackState.autoTask;
    return;
  }
  const saved = $("#auto-saved");
  saved.hidden = false;
  setTimeout(() => (saved.hidden = true), 2500);
  loadApplications(); // a new follow-up gap changes what's due
});

async function watchAutoSearch() {
  clearTimeout(trackState.polling);
  const auto = await api("/api/autosearch").catch(() => null);
  if (auto && auto.running) {
    $("#auto-now").disabled = true;
    $("#auto-now").textContent = "Searching…";
    trackState.polling = setTimeout(watchAutoSearch, 5000);
    return;
  }
  $("#auto-now").disabled = false;
  $("#auto-now").textContent = "Run the daily search now";
  if (auto) $("#auto-last").textContent = lastRunText(auto.last);
  loadJobs(); // the new jobs are on the Jobs tab
}

$("#auto-now").addEventListener("click", async () => {
  try {
    await api("/api/autosearch/run", { method: "POST" });
  } catch (err) {
    return alert(err.message);
  }
  $("#auto-note").textContent = "Searching jobs posted in the last day with your saved titles, cities and sites. This takes a few minutes; you'll get a notification when it's done.";
  setTimeout(watchAutoSearch, 1500);
});

// Moving to the Applied tab refreshes the board; the due count is refreshed every few minutes.
$(".tab[data-view=applied]").addEventListener("click", loadApplications);
setInterval(loadApplications, 5 * 60 * 1000);
loadApplications();
loadAutoSettings().catch(() => {});
