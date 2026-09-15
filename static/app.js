"use strict";

const PAGE_SIZE = 60;
const SOURCE_LABELS = { linkedin: "LinkedIn", indeed: "Indeed", naukri: "Naukri", company: "Company site", companies: "Company sites" };
const FILTER_STORE = "jobhunt.filters.v2";
const NO_TITLE = "Earlier searches"; // jobs saved before search titles were recorded
const APPLICANT_STEPS = [null, 25, 50, 100, 200, 300, 500, 1000, 2000, 5000, 10000]; // null = Any
const EMPTY_TEXT = {
  new: "No new jobs. Pick job titles and skills above, then press <b>Search</b>.",
  saved: "No saved jobs yet. Click <b>Save</b> on a job to keep it here.",
  applied: "No applied jobs yet. Jobs move here when you click <b>Apply</b>.",
  hidden: "No hidden jobs. Jobs you <b>Hide</b> move here.",
};
const MOVE_TEXT = { new: "Moved back to Jobs", saved: "Saved", applied: "Marked as applied", hidden: "Hidden" };
const STATE_ICONS = { pending: "○", running: '<span class="spinner small"></span>', done: "✓", error: "✗", cancelled: "■" };

const state = {
  jobs: [],
  visible: [],
  shown: PAGE_SIZE,
  cities: new Set(),
  view: "new",
  polling: null,
  finishedSources: 0,
  skillsByTitle: new Map(),
  allTitles: [],
  allSkills: [],
  catalog: null,
  titleFilter: new Set(),
  citiesPicker: null,
  cityList: [],
  titlesPicker: null,
  skillsPicker: null,
  toastTimer: null,
  elapsedTimer: null,
  startedAt: null,
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Only plain web links are ever put in an href. Job data comes from other websites and imported files, and must
// never become a javascript: or data: link that runs code when clicked.
function safeUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "";
  } catch {
    return "";
  }
}

function splitTerms(text) {
  return (text || "").split(/[,;\n]/).map((t) => t.trim()).filter(Boolean);
}

// Descriptions arrive as Markdown; show them as readable plain text.
function plainText(markdown) {
  return (markdown || "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/^\s*#{1,6}\s*/gm, "")
    .replace(/^\s*[*-]\s+/gm, "• ")
    .replace(/\\([\\`*_{}\[\]()#+\-.!|>~])/g, "$1")
    .trim();
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    // The server refuses changes without X-JobHunt, so other websites can't send commands to this app.
    headers: { "Content-Type": "application/json", "X-JobHunt": "1" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `Request failed (${resp.status})`);
  return data;
}

/* ---------- Title & skill catalog ---------- */
async function loadCatalog() {
  const resp = await fetch("/static/job_catalog.json", { cache: "no-cache" });
  if (!resp.ok) throw new Error("Could not load the job title list");
  state.catalog = await resp.json();
  const skills = new Set();
  state.catalog.categories.forEach((cat) =>
    cat.titles.forEach((t) => {
      state.allTitles.push(t.title);
      state.skillsByTitle.set(t.title.toLowerCase(), t.skills);
      t.skills.forEach((s) => skills.add(s));
    })
  );
  state.allSkills = [...skills].sort((a, b) => a.localeCompare(b));
}

function titleGroups() {
  return state.catalog.categories.map((cat) => ({ name: cat.name, options: cat.titles.map((t) => t.title) }));
}

function skillGroups() {
  // Only titles from the list have known skills; typed titles are left out of this group.
  const titles = (state.titlesPicker ? state.titlesPicker.values : []).filter((t) => state.skillsByTitle.has(t.toLowerCase()));
  const counts = new Map();
  titles.forEach((t) => state.skillsByTitle.get(t.toLowerCase()).forEach((s) => counts.set(s, (counts.get(s) || 0) + 1)));
  if (!counts.size) return [{ name: "All skills", options: state.allSkills }];
  // Skills needed by more of the chosen titles come first; ties keep the list's own order.
  const forTitles = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a));
  return [
    { name: titles.length === 1 ? `Skills for ${titles[0]}` : `Skills for your ${titles.length} job titles`, options: forTitles },
    { name: "Other skills", options: state.allSkills.filter((s) => !counts.has(s)) },
  ];
}

/* ---------- Tick-box picker with typing ---------- */
function createPicker(root, { placeholder, groups, allOptions, onChange, actions = [] }) {
  let values = [];
  root.classList.add("picker");
  root.innerHTML = `
    <div class="picker-box">
      <span class="picker-chips"></span>
      <input class="picker-input" type="text" autocomplete="off" placeholder="${esc(placeholder)}">
    </div>
    <div class="picker-panel" hidden>
      <div class="picker-bar">
        <span class="picker-hint"></span>
        <span class="picker-actions">
          ${actions.map((a, i) => `<button type="button" class="link-btn" data-action="${i}">${esc(a.label)}</button>`).join("")}
          <button type="button" class="link-btn" data-action="clear">Clear all</button>
        </span>
      </div>
      <div class="picker-list"></div>
    </div>`;
  const box = root.querySelector(".picker-box");
  const chips = root.querySelector(".picker-chips");
  const input = root.querySelector(".picker-input");
  const panel = root.querySelector(".picker-panel");
  const list = root.querySelector(".picker-list");
  const hint = root.querySelector(".picker-hint");

  const has = (v) => values.some((x) => x.toLowerCase() === v.toLowerCase());
  const canonical = (v) => allOptions().find((o) => o.toLowerCase() === v.trim().toLowerCase()) || v.trim();

  function commit() {
    renderChips();
    if (!panel.hidden) renderList();
    onChange([...values]);
  }

  function renderChips() {
    chips.innerHTML = values
      .map((v) => `<span class="sel-chip">${esc(v)}<button type="button" data-remove="${esc(v)}" aria-label="Remove ${esc(v)}">×</button></span>`)
      .join("");
    input.placeholder = values.length ? "Add more…" : placeholder;
  }

  function renderHint(known) {
    const typed = input.value.trim();
    hint.innerHTML =
      typed && !known.has(typed.toLowerCase()) && !has(typed)
        ? `Press <b>Enter</b> to add “${esc(typed)}”`
        : `${values.length} selected`;
  }

  function renderList() {
    const query = input.value.trim().toLowerCase();
    const all = groups();
    const known = new Set(all.flatMap((g) => g.options.map((o) => o.toLowerCase())));
    const custom = values.filter((v) => !known.has(v.toLowerCase()));
    const shown = [...(custom.length ? [{ name: "Added by you", options: custom }] : []), ...all]
      .map((g) => ({ name: g.name, options: query ? g.options.filter((o) => o.toLowerCase().includes(query)) : g.options }))
      .filter((g) => g.options.length);
    const scroll = list.scrollTop;
    list.innerHTML = shown.length
      ? shown
          .map(
            (g) => `<div class="picker-group">
              <div class="picker-group-name">${esc(g.name)} <small>${g.options.length}</small></div>
              ${g.options.map((o) => `<label class="picker-opt"><input type="checkbox" value="${esc(o)}" ${has(o) ? "checked" : ""}><span>${esc(o)}</span></label>`).join("")}
            </div>`
          )
          .join("")
      : `<div class="picker-empty">No matches. Press Enter to add it.</div>`;
    list.scrollTop = query ? 0 : scroll;
    renderHint(known);
  }

  function open() {
    if (!panel.hidden) return;
    panel.hidden = false;
    renderList();
  }

  function close() {
    panel.hidden = true;
    input.value = "";
  }

  box.addEventListener("click", (e) => {
    const remove = e.target.closest("[data-remove]");
    if (remove) {
      values = values.filter((v) => v !== remove.dataset.remove);
      commit();
      return;
    }
    input.focus();
    open();
  });
  input.addEventListener("focus", open);
  input.addEventListener("input", () => {
    open();
    renderList();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault(); // don't submit the search form
      const added = splitTerms(input.value).map(canonical).filter((t) => !has(t));
      if (!added.length) return;
      values.push(...added);
      input.value = "";
      commit();
    } else if (e.key === "Backspace" && !input.value && values.length) {
      values.pop();
      commit();
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });
  list.addEventListener("change", (e) => {
    if (!e.target.matches("input[type=checkbox]")) return;
    const v = e.target.value;
    values = e.target.checked ? (has(v) ? values : [...values, v]) : values.filter((x) => x.toLowerCase() !== v.toLowerCase());
    renderChips();
    // The same skill can appear in two groups; keep every copy of the box in step.
    list.querySelectorAll("input[type=checkbox]").forEach((cb) => (cb.checked = has(cb.value)));
    renderHint(new Set(groups().flatMap((g) => g.options.map((o) => o.toLowerCase()))));
    onChange([...values]);
  });
  panel.querySelector(".picker-bar").addEventListener("click", (e) => {
    const button = e.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "clear") values = [];
    else values = [...new Set([...values, ...actions[button.dataset.action].pick()])];
    commit();
    input.focus();
  });
  document.addEventListener("mousedown", (e) => {
    if (!root.contains(e.target)) close();
  });

  renderChips();
  return {
    get values() {
      return [...values];
    },
    setValues(next) {
      values = [];
      next.map(canonical).forEach((v) => !has(v) && values.push(v));
      renderChips();
      if (!panel.hidden) renderList();
    },
    refresh() {
      if (!panel.hidden) renderList();
    },
  };
}

const CITY_SEARCH_LIMIT = 3; // same as search.py: more cities are searched as all of India, then filtered

function renderCityNote() {
  const values = state.citiesPicker.values;
  const remote = values.some((c) => c.toLowerCase() === "remote");
  const cities = values.filter((c) => c.toLowerCase() !== "remote");
  let note = "";
  if (cities.length > CITY_SEARCH_LIMIT) {
    note = `${cities.length} cities: all of India is searched once, keeping only jobs in these cities${remote ? " or remote" : ""}.`;
  } else if (cities.length) {
    note = `Each site searches ${cities.length === 1 ? "this city" : `these ${cities.length} cities`}${remote ? " and remote jobs" : ""} separately, up to your results limit for each. Jobs listed only in other cities are skipped.`;
  } else if (remote) {
    note = "Only remote jobs in India are searched.";
  }
  $("#city-note").textContent = note;
}

let profileTimer = null;
function saveProfile() {
  clearTimeout(profileTimer);
  profileTimer = setTimeout(async () => {
    await api("/api/settings", {
      method: "PUT",
      body: {
        titles: state.titlesPicker.values.join(", "),
        skills: state.skillsPicker.values.join(", "),
        search_cities: state.citiesPicker ? state.citiesPicker.values : [],
      },
    }).catch((err) => alert(err.message));
    loadJobs(); // titles and skills change the match scores
  }, 500);
}

/* ---------- Tabs ---------- */
function showTab(tab, view = state.view) {
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab && (tab !== "jobs" || b.dataset.view === view)));
  $$(".tab-panel").forEach((p) => (p.hidden = p.id !== `tab-${tab}`));
  if (tab === "jobs") {
    state.view = view;
    $("#search-form").hidden = view !== "new";
    $("#progress").hidden = view !== "new" || !$("#progress").innerHTML;
    $("#applicants-progress").hidden = !["new", "saved"].includes(view) || !$("#applicants-progress").innerHTML;
    renderTitleOptions();
    renderCityOptions();
    applyFilters();
  }
  if (tab === "companies") loadCompanies();
}

$$(".tab").forEach((btn) => btn.addEventListener("click", () => showTab(btn.dataset.tab, btn.dataset.view)));

function renderCounts() {
  $$("[data-count]").forEach((el) => {
    const n = state.jobs.filter((j) => j.status === el.dataset.count).length;
    el.textContent = n ? String(n) : "";
  });
}

/* ---------- Sliders ---------- */
// Browsers colour the filled part of a slider differently (or not at all); the CSS draws it from --fill.
function paintRange(el) {
  const min = Number(el.min || 0);
  const max = Number(el.max || 100);
  el.style.setProperty("--fill", `${((Number(el.value) - min) / (max - min || 1)) * 100}%`);
}

function paintRanges() {
  $$('input[type="range"]').forEach(paintRange);
}

document.addEventListener("input", (e) => {
  if (e.target.matches && e.target.matches('input[type="range"]')) paintRange(e.target);
});

/* ---------- Posted within slider ---------- */
const POSTED_STEPS = [5, 10, 15, 30, 60, 120, 180, 360, 720, 1440, 2880, 4320, 7200, 10080, 14400, 20160, 30240, 43200]; // minutes

function postedLabel(minutes) {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 1440) return `${minutes / 60} hour${minutes === 60 ? "" : "s"}`;
  return `${minutes / 1440} day${minutes === 1440 ? "" : "s"}`;
}

function postedMinutes() {
  return POSTED_STEPS[Number($("#posted-range").value)];
}

function renderPosted() {
  const minutes = postedMinutes();
  $("#posted-val").textContent = postedLabel(minutes);
  paintRange($("#posted-range"));
  let note = "";
  if (minutes < 60) {
    note = "LinkedIn matches exactly. Indeed rounds up to 1 hour, and Naukri only knows the posting day, so they may include jobs posted earlier the same day.";
  } else if (minutes < 1440) {
    note = "LinkedIn and Indeed match to the hour. Naukri only knows the posting day, so it may include jobs posted earlier the same day.";
  }
  $("#posted-note").textContent = note;
}

$("#posted-range").addEventListener("input", renderPosted);

/* ---------- Settings & search ---------- */
async function loadSettings() {
  const s = await api("/api/settings");
  state.titlesPicker.setValues(splitTerms(s.titles));
  state.skillsPicker.setValues(splitTerms(s.skills));
  state.citiesPicker.setValues(s.search_cities || []);
  renderCityNote();
  const step = POSTED_STEPS.findIndex((m) => m >= s.minutes_old);
  $("#posted-range").value = String(step === -1 ? POSTED_STEPS.length - 1 : step);
  renderPosted();
  $$("input[name=source]").forEach((cb) => (cb.checked = s.sources.includes(cb.value)));
  $("#s-results").value = s.results_wanted;
  $("#s-delay").value = s.request_delay;
  $("#s-company-sites").value = s.company_search_sites;
}

$("#search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const titles = state.titlesPicker.values;
  if (!titles.length) return alert("Pick at least one job title.");
  const sources = $$("input[name=source]:checked").map((cb) => cb.value);
  if (!sources.length) return alert("Tick at least one site to search on.");
  clearTimeout(profileTimer);
  try {
    await api("/api/search", {
      method: "POST",
      body: {
        titles: titles.join(", "),
        skills: state.skillsPicker.values.join(", "),
        minutes_old: postedMinutes(),
        sources,
        search_cities: state.citiesPicker.values,
      },
    });
    state.finishedSources = 0;
    pollStatus();
  } catch (err) {
    alert(err.message);
  }
});

$("#cancel-btn").addEventListener("click", async () => {
  $("#cancel-btn").disabled = true;
  $("#cancel-btn").textContent = "Stopping…";
  await api("/api/search/cancel", { method: "POST" }).catch((err) => alert(err.message));
  pollStatus();
});

async function pollStatus() {
  clearTimeout(state.polling);
  const status = await api("/api/search/status").catch(() => null);
  if (!status) {
    if (!$("#search-overlay").hidden) state.polling = setTimeout(pollStatus, 3000);
    return;
  }
  renderProgress(status);
  const finished = Object.values(status.sources).filter((s) => ["done", "error", "cancelled"].includes(s.state)).length;
  if (finished !== state.finishedSources) {
    state.finishedSources = finished;
    loadJobs();
  }
  if (status.running) {
    renderOverlay(status);
    state.polling = setTimeout(pollStatus, 1500);
  } else {
    hideOverlay();
  }
}

function sourceText(s) {
  if (s.state === "pending") return "waiting";
  if (s.state === "running") return `${s.message || "searching…"}${s.count ? ` · ${s.count} jobs so far` : ""}`;
  const skipped = s.skipped ? ` · ${s.skipped} outside your cities skipped` : "";
  if (s.state === "done") return `${s.count} jobs (${s.new} new)${skipped}${s.message ? " · " + s.message : ""}`;
  if (s.state === "cancelled") return `stopped · ${s.count} jobs kept${s.message ? " · " + s.message : ""}`;
  return s.message || "failed";
}

function renderProgress(status) {
  const box = $("#progress");
  const entries = Object.entries(status.sources);
  if (!entries.length) {
    box.innerHTML = "";
    box.hidden = true;
    return;
  }
  const time = status.finished_at ? new Date(status.finished_at).toLocaleTimeString() : "";
  const lead = status.running ? "Searching:" : status.cancelled ? `Search stopped at ${time}:` : `Last search finished ${time}:`;
  box.innerHTML =
    `<span>${esc(lead)}</span>` +
    entries
      .map(([key, s]) => `<span class="pill ${s.state}" title="${esc(s.message || "")}"><b>${esc(SOURCE_LABELS[key] || key)}</b> ${esc(sourceText(s))}</span>`)
      .join("");
  box.hidden = state.view !== "new";
}

function setLocked(locked) {
  $("header.topbar").inert = locked;
  $("main").inert = locked;
  document.body.classList.toggle("locked", locked);
}

function renderOverlay(status) {
  const overlay = $("#search-overlay");
  if (overlay.hidden) {
    overlay.hidden = false;
    setLocked(true);
    document.activeElement?.blur();
    state.startedAt = status.started_at ? new Date(status.started_at) : new Date();
    tickElapsed();
    state.elapsedTimer = setInterval(tickElapsed, 1000);
  }
  $("#overlay-title").textContent = status.cancelling ? "Stopping the search…" : "Searching for jobs…";
  $("#overlay-sub").textContent = status.cancelling
    ? "Each site is finishing the page it is on. Jobs found so far are kept."
    : "The page is locked until the search finishes.";
  const cancel = $("#cancel-btn");
  cancel.disabled = status.cancelling;
  cancel.textContent = status.cancelling ? "Stopping…" : "Cancel search";
  $("#overlay-sources").innerHTML = Object.entries(status.sources)
    .map(
      ([key, s]) => `<div class="ov-row ${s.state}">
        <span class="ov-icon">${STATE_ICONS[s.state] || ""}</span>
        <span class="ov-name">${esc(SOURCE_LABELS[key] || key)}</span>
        <span class="ov-msg">${esc(sourceText(s))}</span>
      </div>`
    )
    .join("");
}

function tickElapsed() {
  const seconds = Math.max(0, Math.round((Date.now() - state.startedAt) / 1000));
  $("#overlay-elapsed").textContent = `Elapsed ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function hideOverlay() {
  if ($("#search-overlay").hidden) return;
  $("#search-overlay").hidden = true;
  clearInterval(state.elapsedTimer);
  setLocked(false);
  loadJobs();
}

/* ---------- Jobs ---------- */
async function loadJobs() {
  const data = await api("/api/jobs");
  state.jobs = data.jobs;
  renderCounts();
  renderTitleOptions();
  renderCityOptions();
  applyFilters({ keepPage: true });
}

function checkedValues(containerSel) {
  return new Set($$(`${containerSel} input:checked`).map((cb) => cb.value));
}

function splitList(text) {
  return text.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
}

function readFilters() {
  const expMin = $("#f-exp-min").value;
  const expMax = $("#f-exp-max").value;
  return {
    text: $("#f-text").value.trim().toLowerCase(),
    minMatch: Number($("#f-match").value),
    minSalary: Number($("#f-salary").value),
    maxApplicants: APPLICANT_STEPS[Number($("#f-applicants").value)] ?? null,
    minRating: Number($("#f-rating").value),
    expMin: expMin === "" ? null : Number(expMin),
    expMax: expMax === "" ? null : Number(expMax),
    days: Number($("#f-date").value),
    modes: checkedValues("#f-mode"),
    types: checkedValues("#f-type"),
    cities: state.cities,
    titles: state.titleFilter,
    sources: checkedValues("#f-source"),
    include: splitList($("#f-company-include").value),
    exclude: splitList($("#f-company-exclude").value),
  };
}

function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function passes(job, f, cutoff) {
  if (job.status !== state.view) return false;
  if (f.titles.size && !jobTitles(job).some((t) => f.titles.has(t))) return false;
  if (job.match_score < f.minMatch) return false;
  if (f.minSalary > 0) {
    const top = job.salary_max ?? job.salary_min;
    if (top != null && top < f.minSalary) return false;
  }
  if (f.maxApplicants != null) {
    const count = applicantValue(job);
    if (count != null && count > f.maxApplicants) return false; // jobs without a count stay
  }
  if (f.minRating > 0 && job.company_rating != null && job.company_rating < f.minRating) return false; // unrated jobs stay
  if (job.exp_min != null) {
    const jobMax = job.exp_max ?? Infinity;
    if (f.expMax != null && job.exp_min > f.expMax) return false;
    if (f.expMin != null && jobMax < f.expMin) return false;
  }
  if (cutoff && job.date_posted && job.date_posted < cutoff) return false;
  if (!f.modes.has(job.work_mode)) return false;
  if (!job.job_types.some((t) => f.types.has(t))) return false;
  if (f.cities.size && !job.cities.some((c) => f.cities.has(c))) return false;
  if (!job.sources.some((s) => f.sources.has(s.site))) return false;
  const company = job.company.toLowerCase();
  if (f.include.length && !f.include.some((t) => company.includes(t))) return false;
  if (f.exclude.some((t) => company.includes(t))) return false;
  if (f.text && !`${job.title} ${job.company}`.toLowerCase().includes(f.text)) return false;
  return true;
}

const SORTERS = {
  match: (a, b) => b.match_score - a.match_score || (b.date_posted || "").localeCompare(a.date_posted || ""),
  newest: (a, b) => (b.date_posted || "").localeCompare(a.date_posted || "") || b.match_score - a.match_score,
  salary: (a, b) => (b.salary_max ?? b.salary_min ?? -1) - (a.salary_max ?? a.salary_min ?? -1) || b.match_score - a.match_score,
  company: (a, b) => a.company.localeCompare(b.company) || b.match_score - a.match_score,
  // Jobs without a count (Indeed, company sites, Naukri before Details) go last.
  applicants: (a, b) => (applicantValue(a) ?? Number.MAX_SAFE_INTEGER) - (applicantValue(b) ?? Number.MAX_SAFE_INTEGER) || b.match_score - a.match_score,
};

function applyFilters({ keepPage = false } = {}) {
  const f = readFilters();
  paintRanges();
  $("#f-match-val").textContent = f.minMatch ? `${f.minMatch}%+` : "Any";
  $("#f-salary-val").textContent = f.minSalary ? `₹${f.minSalary} LPA+` : "Any";
  $("#f-applicants-val").textContent = f.maxApplicants ? `${f.maxApplicants.toLocaleString("en-IN")} or fewer` : "Any";
  $("#f-rating-val").textContent = f.minRating ? `${f.minRating.toFixed(1)}★ and above` : "Any";
  $("#f-city-note").textContent = state.cities.size ? `${state.cities.size} selected` : "all cities";
  $("#f-title-note").textContent = state.titleFilter.size ? `${state.titleFilter.size} selected` : "all titles";
  const cutoff = f.days ? isoDaysAgo(f.days) : null;
  state.visible = state.jobs.filter((j) => passes(j, f, cutoff)).sort(SORTERS[$("#sort").value]);
  if (!keepPage) state.shown = PAGE_SIZE;
  renderJobs();
  saveFilters();
}

function renderJobs() {
  const list = $("#job-list");
  const inView = state.jobs.filter((j) => j.status === state.view).length;
  $("#result-count").textContent = inView ? `${state.visible.length} of ${inView} jobs` : "";
  if (!state.visible.length) {
    list.innerHTML = `<div class="empty">${inView ? "No jobs match these filters." : EMPTY_TEXT[state.view]}</div>`;
    $("#more-btn").hidden = true;
    return;
  }
  list.innerHTML = state.visible.slice(0, state.shown).map(cardHtml).join("");
  $("#more-btn").hidden = state.visible.length <= state.shown;
}

function salaryChip(job) {
  const { salary_min: lo, salary_max: hi } = job;
  if (lo != null && hi != null && lo !== hi) return `<span class="chip salary">₹${lo}–${hi} LPA</span>`;
  if (lo != null && hi != null) return `<span class="chip salary">₹${hi} LPA</span>`;
  if (hi != null) return `<span class="chip salary">Up to ₹${hi} LPA</span>`;
  if (lo != null) return `<span class="chip salary">₹${lo} LPA+</span>`;
  if (job.salary_text) return `<span class="chip muted" title="Not in INR, so the salary filter ignores it">${esc(job.salary_text)}</span>`;
  return `<span class="chip muted">Salary not disclosed</span>`;
}

function ratingBadge(job) {
  if (job.company_rating == null) return "";
  const reviews = job.company_reviews ? ` · ${new Intl.NumberFormat("en", { notation: "compact" }).format(job.company_reviews)} reviews` : "";
  const hover = `AmbitionBox company rating shown by Naukri${job.company_reviews ? `, from ${job.company_reviews.toLocaleString("en-IN")} reviews` : ""}`;
  return `<span class="rating-badge" title="${esc(hover)}">★ ${job.company_rating.toFixed(1)}${reviews}</span>`;
}

// "Over 200 applicants" means at least 201, so it counts as 201 for the filter and the sort.
function applicantValue(job) {
  if (job.applicants == null) return null;
  return job.applicants + (/^over /i.test(job.applicants_text || "") ? 1 : 0);
}

function applicantsChip(job) {
  if (!job.applicants_text) return "";
  const checked = job.applicants_checked ? ` title="Checked ${esc(new Date(job.applicants_checked).toLocaleString())}"` : "";
  return `<span class="chip applicants"${checked}>${esc(job.applicants_text)}</span>`;
}

function postedText(date) {
  if (!date) return "Date unknown";
  const days = Math.round((new Date(isoDaysAgo(0)) - new Date(date)) / 86400000);
  if (days <= 0) return "Posted today";
  if (days === 1) return "Posted yesterday";
  return `Posted ${days} days ago`;
}

function moveButton(to, label) {
  return `<button class="btn small" data-act="move" data-to="${to}">${label}</button>`;
}

function actionsHtml(job) {
  const applyUrl = safeUrl(job.apply_url);
  const apply = applyUrl
    ? `<a class="btn primary" data-act="apply" href="${esc(applyUrl)}" target="_blank" rel="noopener noreferrer">${job.status === "applied" ? "Open again" : "Apply"}</a>`
    : `<span class="btn disabled">No link</span>`;
  const details = `<button class="btn small" data-act="details">Details</button>`;
  switch (job.status) {
    case "saved":
      return apply + moveButton("new", "Unsave") + moveButton("hidden", "Hide") + details;
    case "applied":
      return apply + `<div class="applied-mark">Applied ✓</div>` + moveButton("new", "Not applied") + details;
    case "hidden":
      return moveButton("new", "Unhide") + apply + details;
    default:
      return apply + moveButton("saved", "Save") + moveButton("hidden", "Hide") + details;
  }
}

function cardHtml(job) {
  const pct = job.match_score;
  const matchClass = pct >= 70 ? "high" : pct >= 40 ? "mid" : "low";
  const exp = job.exp_min != null ? `<span class="chip">${job.exp_max != null ? `${job.exp_min}–${job.exp_max}` : `${job.exp_min}+`} yrs exp</span>` : "";
  const types = job.job_types.filter((t) => t !== "Not specified").map((t) => `<span class="chip">${esc(t)}</span>`).join("");
  const mode = job.work_mode !== "Not specified" ? `<span class="chip">${esc(job.work_mode)}</span>` : "";
  const skills = job.skills_total
    ? `<div class="skills">Skills: ${job.matched_skills.map((s) => `<span class="skill">${esc(s)}</span>`).join("")}${job.missing_skills.map((s) => `<span class="skill missing">${esc(s)}</span>`).join("")}</div>`
    : "";
  const sources = job.sources
    .map((s) => {
      const link = safeUrl(s.direct) || safeUrl(s.url);
      const label = esc(SOURCE_LABELS[s.site] || s.site);
      return link ? `<a class="src" href="${esc(link)}" target="_blank" rel="noopener noreferrer">${label}</a>` : label;
    })
    .join(" · ");
  const applyUrl = safeUrl(job.apply_url);
  const title = applyUrl ? `<a href="${esc(applyUrl)}" target="_blank" rel="noopener noreferrer" data-act="apply">${esc(job.title)}</a>` : esc(job.title);
  return `
  <article class="job-card ${job.status}" data-id="${job.id}">
    <div class="card-main">
      <div class="card-title">
        <h3>${title}</h3>
        <span class="match ${matchClass}" title="Match with your job titles and skills">${pct}% match</span>
      </div>
      <div class="company"><b>${esc(job.company)}</b>${ratingBadge(job)} · ${esc(job.location || job.cities.join(", ") || "India")}</div>
      <div class="chips">${salaryChip(job)}${applicantsChip(job)}${mode}${types}${exp}<span class="chip muted">${postedText(job.date_posted)}</span></div>
      ${skills}
      <div class="srcs">Found on: ${sources}${job.search_titles.length ? ` · searched for ${job.search_titles.map(esc).join(", ")}` : ""}</div>
      <div class="details" hidden></div>
    </div>
    <div class="card-actions">${actionsHtml(job)}</div>
  </article>`;
}

async function setStatus(job, status, { toast = true } = {}) {
  const previous = job.status;
  if (previous === status) return;
  job.status = status;
  renderCounts();
  applyFilters({ keepPage: true });
  try {
    await api(`/api/jobs/${job.id}`, { method: "PATCH", body: { status } });
  } catch (err) {
    job.status = previous;
    renderCounts();
    applyFilters({ keepPage: true });
    alert(err.message);
    return;
  }
  if (toast) showToast(`${MOVE_TEXT[status]}: ${job.title}`, () => setStatus(job, previous, { toast: false }));
}

function showToast(text, undo) {
  const toast = $("#toast");
  $("#toast-text").textContent = text;
  toast.hidden = false;
  $("#toast-undo").onclick = () => {
    toast.hidden = true;
    undo();
  };
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => (toast.hidden = true), 6000);
}

$("#job-list").addEventListener("click", async (e) => {
  const target = e.target.closest("[data-act]");
  if (!target) return;
  const card = target.closest(".job-card");
  const job = state.jobs.find((j) => j.id === Number(card.dataset.id));
  const act = target.dataset.act;
  if (act === "apply") {
    // The link itself opens the apply page in a new tab; just record it.
    if (job.status !== "applied") setTimeout(() => setStatus(job, "applied"), 0);
    return;
  }
  if (act === "move") return setStatus(job, target.dataset.to);
  if (act === "details") {
    const box = card.querySelector(".details");
    if (!box.hidden) {
      box.hidden = true;
      target.textContent = "Details";
      return;
    }
    box.hidden = false;
    target.textContent = "Close";
    box.textContent = "Loading…";
    const detail = await api(`/api/jobs/${job.id}`).catch((err) => ({ description: err.message }));
    const skills = detail.skills_listed ? `Skills listed: ${detail.skills_listed}\n\n` : "";
    box.textContent = skills + (plainText(detail.description) || "No description was provided by this source. Open the job link for full details.");
    // Naukri search results don't include applicant counts, so fetch this job's count now
    // (unless Update Applicants (Naukri) is already reading them all).
    if (!job.applicants_text && job.sources.some((s) => s.site === "naukri") && !state.applicantsRunning) {
      const note = document.createElement("div");
      note.className = "applicant-note";
      note.textContent = "Checking how many people applied on Naukri… (a few seconds)";
      box.prepend(note);
      const r = await api(`/api/jobs/${job.id}/applicants`, { method: "POST" }).catch((err) => ({ error: err.message }));
      if (r.applicants_text) {
        Object.assign(job, { applicants: r.applicants, applicants_text: r.applicants_text, applicants_checked: r.applicants_checked });
        const chips = card.querySelector(".chips");
        chips.querySelector(".applicants")?.remove();
        chips.firstElementChild.insertAdjacentHTML("afterend", applicantsChip(job));
        note.remove();
      } else {
        note.textContent = `Applicant count not available: ${r.error || "Naukri doesn't show it for this job"}`;
      }
    }
  }
});

$("#more-btn").addEventListener("click", () => {
  state.shown += PAGE_SIZE;
  renderJobs();
});

/* ---------- Job title filter ---------- */
function jobTitles(job) {
  return job.search_titles.length ? job.search_titles : [NO_TITLE];
}

function renderTitleOptions() {
  const counts = new Map();
  state.jobs.filter((j) => j.status === state.view).forEach((j) => jobTitles(j).forEach((t) => counts.set(t, (counts.get(t) || 0) + 1)));
  // Keep ticked titles listed (with 0) on tabs that have none, so they can be unticked there.
  state.titleFilter.forEach((t) => counts.has(t) || counts.set(t, 0));
  const rows = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  $("#f-titles").innerHTML = rows.length
    ? rows.map(([t, n]) => `<label><input type="checkbox" value="${esc(t)}" ${state.titleFilter.has(t) ? "checked" : ""}> ${esc(t)} <span class="count">${n}</span></label>`).join("")
    : `<small>No jobs yet.</small>`;
}

$("#f-titles").addEventListener("change", (e) => {
  if (e.target.checked) state.titleFilter.add(e.target.value);
  else state.titleFilter.delete(e.target.value);
  applyFilters();
});

/* ---------- City filter ---------- */
function renderCityOptions() {
  const counts = new Map();
  state.jobs.filter((j) => j.status === state.view).forEach((j) => j.cities.forEach((c) => counts.set(c, (counts.get(c) || 0) + 1)));
  const query = $("#f-city-search").value.trim().toLowerCase();
  const rows = [...counts.entries()]
    .filter(([c]) => state.cities.has(c) || !query || c.toLowerCase().includes(query))
    .sort((a, b) => state.cities.has(b[0]) - state.cities.has(a[0]) || b[1] - a[1])
    .slice(0, 60);
  $("#f-cities").innerHTML = rows.length
    ? rows.map(([c, n]) => `<label><input type="checkbox" value="${esc(c)}" ${state.cities.has(c) ? "checked" : ""}> ${esc(c)} <span class="count">${n}</span></label>`).join("")
    : `<small>No cities yet.</small>`;
}

$("#f-cities").addEventListener("change", (e) => {
  if (e.target.checked) state.cities.add(e.target.value);
  else state.cities.delete(e.target.value);
  applyFilters();
});
$("#f-city-search").addEventListener("input", renderCityOptions);

/* ---------- Filter wiring & persistence ---------- */
const FILTER_INPUTS = ["#f-text", "#f-match", "#f-salary", "#f-applicants", "#f-rating", "#f-exp-min", "#f-exp-max", "#f-date", "#f-company-include", "#f-company-exclude", "#sort"];
const FILTER_CHECK_GROUPS = ["#f-mode", "#f-type", "#f-source"];

FILTER_INPUTS.forEach((sel) => $(sel).addEventListener("input", () => applyFilters()));
FILTER_CHECK_GROUPS.forEach((sel) => $(sel).addEventListener("change", () => applyFilters()));

function saveFilters() {
  const data = { cities: [...state.cities], titles: [...state.titleFilter] };
  FILTER_INPUTS.forEach((sel) => (data[sel] = $(sel).value));
  FILTER_CHECK_GROUPS.forEach((sel) => (data[sel] = [...checkedValues(sel)]));
  try {
    localStorage.setItem(FILTER_STORE, JSON.stringify(data));
  } catch {}
}

function restoreFilters() {
  let data;
  try {
    data = JSON.parse(localStorage.getItem(FILTER_STORE) || "null");
  } catch {}
  if (!data) return;
  FILTER_INPUTS.forEach((sel) => sel in data && ($(sel).value = data[sel]));
  FILTER_CHECK_GROUPS.forEach((sel) => {
    if (!(sel in data)) return;
    $$(`${sel} input`).forEach((cb) => (cb.checked = data[sel].includes(cb.value)));
  });
  state.cities = new Set(data.cities || []);
  state.titleFilter = new Set(data.titles || []);
}

$("#reset-filters").addEventListener("click", () => {
  try {
    localStorage.removeItem(FILTER_STORE);
  } catch {}
  ["#f-text", "#f-exp-min", "#f-exp-max", "#f-company-include", "#f-company-exclude", "#f-city-search"].forEach((sel) => ($(sel).value = ""));
  $("#f-match").value = 0;
  $("#f-salary").value = 0;
  $("#f-applicants").value = 0;
  $("#f-rating").value = 0;
  $("#f-date").value = "0";
  FILTER_CHECK_GROUPS.forEach((sel) => $$(`${sel} input`).forEach((cb) => (cb.checked = true)));
  state.cities = new Set();
  state.titleFilter = new Set();
  renderTitleOptions();
  renderCityOptions();
  applyFilters();
});

/* ---------- Companies ---------- */
async function loadCompanies() {
  const companies = await api("/api/companies");
  $("#company-empty").hidden = companies.length > 0;
  $("#company-rows").innerHTML = companies
    .map(
      (c) => `
    <tr data-id="${c.id}">
      <td><b>${esc(c.name)}</b></td>
      <td><span class="platform ${c.platform === "boards" ? "boards" : ""}">${esc(c.platform_label)}</span><div class="note">${esc(c.check_note || "")}</div></td>
      <td class="url">${safeUrl(c.careers_url) ? `<a href="${esc(safeUrl(c.careers_url))}" target="_blank" rel="noopener noreferrer">${esc(c.careers_url)}</a>` : "—"}</td>
      <td><input type="checkbox" data-act="toggle" ${c.enabled ? "checked" : ""}></td>
      <td><button class="btn small" data-act="test">Test</button><span class="test-result"></span></td>
      <td><button class="link-btn" data-act="remove">Remove</button></td>
    </tr>`
    )
    .join("");
}

$("#company-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/companies", { method: "POST", body: { name: $("#company-name").value, careers_url: $("#company-url").value } });
    $("#company-name").value = "";
    $("#company-url").value = "";
    loadCompanies();
  } catch (err) {
    alert(err.message);
  }
});

$("#company-rows").addEventListener("click", async (e) => {
  const target = e.target.closest("[data-act]");
  if (!target) return;
  const row = target.closest("tr");
  const id = row.dataset.id;
  const act = target.dataset.act;
  if (act === "toggle") {
    await api(`/api/companies/${id}`, { method: "PATCH", body: { enabled: target.checked } }).catch((err) => {
      target.checked = !target.checked; // put the tick back as it was
      alert(err.message);
    });
  } else if (act === "remove") {
    if (!confirm("Remove this company?")) return;
    await api(`/api/companies/${id}`, { method: "DELETE" }).catch((err) => alert(err.message));
    loadCompanies();
  } else if (act === "test") {
    const out = row.querySelector(".test-result");
    target.disabled = true;
    out.className = "test-result";
    out.textContent = "testing…";
    try {
      const r = await api(`/api/companies/${id}/test`, { method: "POST" });
      if (r.platform_label) row.querySelector(".platform").textContent = r.platform_label;
      row.querySelector(".note").textContent = r.check_note || "";
      out.className = `test-result ${r.error ? "err" : "ok"}`;
      out.textContent = r.error ? r.error : `${r.count} matching jobs in India`;
    } catch (err) {
      out.className = "test-result err";
      out.textContent = err.message;
    }
    target.disabled = false;
  }
});

function importSummary(d) {
  const lines = [`<b>Added ${d.added} ${d.added === 1 ? "company" : "companies"}.</b>`];
  const via = Object.entries(d.platforms).map(([label, n]) => `${n} via ${esc(label)}`).join(", ");
  if (via) lines.push(`Read via: ${via}.`);
  if (d.found_on_page) lines.push(`${d.found_on_page} had a supported hiring platform behind their careers page.`);
  const more = [];
  if (d.skipped_existing.length)
    more.push(`<details><summary>${d.skipped_existing.length} skipped: already in your list</summary>${esc(d.skipped_existing.join(", "))}</details>`);
  if (d.skipped_duplicates.length)
    more.push(`<details><summary>${d.skipped_duplicates.length} skipped: repeated in the file</summary>${esc(d.skipped_duplicates.join("; "))}</details>`);
  if (d.problems.length)
    more.push(`<details><summary>${d.problems.length} rows with problems</summary>${d.problems.map(esc).join("<br>")}</details>`);
  return `<p>${lines.join(" ")}</p>${more.join("")}<p class="hint">Tick <b>Company sites</b> on the Jobs tab and press Search to find their jobs.</p>`;
}

$("#import-btn").addEventListener("click", async () => {
  const file = $("#import-file").files[0];
  if (!file) return alert("Choose a CSV or Excel file first.");
  const button = $("#import-btn");
  const out = $("#import-result");
  button.disabled = true;
  button.textContent = "Importing…";
  out.hidden = false;
  out.className = "import-result";
  out.textContent = "Reading the file and checking each careers page for a supported hiring platform. Long lists can take a minute or two…";
  try {
    const resp = await fetch(`/api/companies/import?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
      headers: { "X-JobHunt": "1" },
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `Import failed (${resp.status})`);
    out.className = "import-result ok";
    out.innerHTML = importSummary(data);
    $("#import-file").value = "";
    loadCompanies();
  } catch (err) {
    out.className = "import-result err";
    out.textContent = err.message;
  }
  button.disabled = false;
  button.textContent = "Import file";
});

/* ---------- Settings tab ---------- */
$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/settings", {
      method: "PUT",
      body: {
        results_wanted: Number($("#s-results").value),
        request_delay: Number($("#s-delay").value),
        company_search_sites: $("#s-company-sites").value,
      },
    });
  } catch (err) {
    return alert(err.message); // don't show "Saved" when it wasn't
  }
  const note = $("#settings-saved");
  note.hidden = false;
  setTimeout(() => (note.hidden = true), 2000);
});

$("#clear-btn").addEventListener("click", async () => {
  if (!confirm("Remove every job in the Jobs tab? Saved, applied and hidden jobs stay.")) return;
  let r;
  try {
    r = await api("/api/jobs/clear", { method: "POST" });
  } catch (err) {
    return alert(err.message);
  }
  $("#clear-note").hidden = false;
  $("#clear-note").textContent = `Removed ${r.deleted} jobs`;
  loadJobs();
});

/* ---------- Start ---------- */
/* ---------- Update Applicants (Naukri) ---------- */
const APPLICANTS_LABEL = "Update Applicants (Naukri)";

$("#applicants-btn").addEventListener("click", async () => {
  $("#applicants-btn").disabled = true;
  try {
    const status = await api("/api/applicants/update", { method: "POST" });
    state.applicantResults = 0;
    renderApplicantProgress(status);
    if (status.running) pollApplicants();
  } catch (err) {
    $("#applicants-btn").disabled = false;
    alert(err.message);
  }
});

$("#applicants-progress").addEventListener("click", async (e) => {
  const stop = e.target.closest("[data-act=stop-applicants]");
  if (!stop) return;
  stop.disabled = true;
  stop.textContent = "Stopping…";
  await api("/api/applicants/stop", { method: "POST" }).catch((err) => alert(err.message));
  pollApplicants();
});

async function pollApplicants() {
  clearTimeout(state.applicantPolling);
  const since = state.applicantResults || 0;
  const status = await api(`/api/applicants/status?since=${since}`).catch(() => null);
  if (!status) {
    if (state.applicantsRunning) state.applicantPolling = setTimeout(pollApplicants, 3000);
    return;
  }
  if (status.results_total < since) {
    state.applicantResults = 0; // a new update started since the last check
    return pollApplicants();
  }
  status.results.forEach(showApplicantCount);
  state.applicantResults = status.results_total;
  const wasRunning = state.applicantsRunning;
  renderApplicantProgress(status);
  if (status.running) state.applicantPolling = setTimeout(pollApplicants, 2000);
  else if (wasRunning) applyFilters(); // re-sort and re-filter now that the counts are in
}

// Puts a newly read count on the job and on its card, without re-drawing the list you are reading.
function showApplicantCount(result) {
  const job = state.jobs.find((j) => j.id === result.id);
  if (!job) return;
  Object.assign(job, { applicants: result.applicants, applicants_text: result.applicants_text, applicants_checked: result.applicants_checked });
  const card = document.querySelector(`article.job-card[data-id="${job.id}"]`);
  if (card) updateApplicantChip(card, job);
}

function updateApplicantChip(card, job) {
  const chips = card.querySelector(".chips");
  chips.querySelector(".applicants")?.remove();
  chips.firstElementChild.insertAdjacentHTML("afterend", applicantsChip(job));
}

function renderApplicantProgress(status) {
  const box = $("#applicants-progress");
  state.applicantsRunning = status.running;
  $("#applicants-btn").disabled = status.running;
  $("#applicants-btn").textContent = status.running ? "Updating applicants…" : APPLICANTS_LABEL;
  $("#search-btn").disabled = status.running;
  $("#search-btn").title = status.running ? "Wait for the applicant update to finish, or stop it" : "";
  let html = "";
  if (status.running) {
    const seconds = (Date.now() - new Date(status.started_at)) / 1000;
    const left = status.done >= 2 ? Math.ceil(((seconds / status.done) * (status.total - status.done)) / 60) : null;
    html =
      `<span><b>Updating Naukri applicant counts:</b> ${status.done} of ${status.total}</span>` +
      `<progress max="${status.total}" value="${status.done}"></progress>` +
      `<span class="muted">${status.updated} updated${left ? ` · about ${left} min left` : ""}</span>` +
      `<button type="button" class="btn small danger" data-act="stop-applicants"${status.stopping ? " disabled" : ""}>${status.stopping ? "Stopping…" : "Stop"}</button>`;
  } else if (status.nothing_to_do) {
    html = `<span>All Naukri jobs in Jobs and Saved already have an applicant count checked in the last day.</span>`;
  } else if (status.finished_at) {
    const time = new Date(status.finished_at).toLocaleTimeString();
    const extra = [
      status.no_count ? `${status.no_count} without a count on Naukri` : "",
      status.failed ? `${status.failed} could not be read` : "",
      status.done < status.total ? `${status.total - status.done} not checked` : "",
    ].filter(Boolean);
    html =
      `<span><b>Applicant counts ${status.stopped ? "stopped" : "updated"} at ${esc(time)}:</b> ${status.updated} of ${status.total} jobs updated</span>` +
      (extra.length ? `<span class="muted">${esc(extra.join(" · "))}</span>` : "") +
      (status.error ? `<span class="pill error">${esc(status.error)}</span>` : "");
  }
  box.innerHTML = html;
  box.hidden = !html || !["new", "saved"].includes(state.view);
}

restoreFilters();
(async () => {
  try {
    await loadCatalog();
    state.titlesPicker = createPicker($("#titles-picker"), {
      placeholder: "Pick or type job titles",
      groups: titleGroups,
      allOptions: () => state.allTitles,
      onChange: () => {
        state.skillsPicker?.refresh();
        saveProfile();
      },
    });
    state.skillsPicker = createPicker($("#skills-picker"), {
      placeholder: "Pick or type skills",
      groups: skillGroups,
      allOptions: () => state.allSkills,
      onChange: saveProfile,
      actions: [{ label: "Tick all for my titles", pick: () => (skillGroups().length > 1 ? skillGroups()[0].options : []) }],
    });
    state.cityList = (await api("/api/cities")).map((c) => c.name);
    state.citiesPicker = createPicker($("#cities-picker"), {
      placeholder: "All of India (pick cities or Remote)",
      groups: () => [
        { name: "Work from home", options: ["Remote"] },
        { name: "Cities", options: state.cityList },
      ],
      allOptions: () => ["Remote", ...state.cityList],
      onChange: () => {
        renderCityNote();
        saveProfile();
      },
    });
    await loadSettings();
    await loadJobs();
  } catch (err) {
    $("#result-count").textContent = err.message;
  }
  pollStatus();
  pollApplicants(); // picks up an applicant update still running from before a reload, or the last one's summary
})();
