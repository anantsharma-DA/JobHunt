"use strict";
// The Insights tab (your applications, salary with the CTC to in-hand calculator, skill gaps), the Referral window
// and the typed mock interview (Practise). Uses the helpers in app.js ($, esc, api, safeUrl, shortDate) and
// resume.js (copyText, resumeState).

const insightState = { view: "applications", loaded: {}, handTimer: null, outreachJob: null, practice: null };

function rupees(value) {
  const whole = Math.round(value);
  return `${whole < 0 ? "−" : ""}₹${Math.abs(whole).toLocaleString("en-IN")}`;
}

function matchesWord(text, word) {
  return new RegExp(`(^|[^a-z])${word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z]|$)`).test(text);
}

function unlockIfNoOverlay() {
  if (!$$(".overlay").some((o) => !o.hidden)) document.body.classList.remove("locked");
}

function showOverlay(id) {
  $(id).hidden = false;
  document.body.classList.add("locked");
}

/* ---------- Tab and its three sections ---------- */
function showInsightView(view) {
  insightState.view = view;
  $$("[data-insight-view]").forEach((b) => {
    const on = b.dataset.insightView === view;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", String(on));
  });
  $$(".insight-view").forEach((el) => (el.hidden = el.id !== `insight-${view}`));
  loadInsight(view);
}

function loadInsight(view) {
  if (view === "applications") return loadApplicationStats();
  if (view === "salary") return loadSalary();
  return loadSkillGaps();
}

$$("[data-insight-view]").forEach((b) => b.addEventListener("click", () => showInsightView(b.dataset.insightView)));
$$(".tab[data-tab=insights]").forEach((tab) => tab.addEventListener("click", () => loadInsight(insightState.view)));

/* ---------- Your applications ---------- */
function weeksChart(weeks) {
  const width = 640, height = 190, top = 18, bottom = 34, gap = 10;
  const bar = (width - gap * (weeks.length + 1)) / weeks.length;
  const most = Math.max(1, ...weeks.map((w) => w.count));
  const bars = weeks.map((w, i) => {
    const x = gap + i * (bar + gap);
    const h = Math.round(((height - top - bottom) * w.count) / most);
    const y = height - bottom - h;
    const label = new Date(`${w.start}T00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
    return `<g><title>Week of ${esc(label)}: ${w.count} application${w.count === 1 ? "" : "s"}</title>
      <rect class="chart-bar${w.count ? "" : " empty"}" x="${x.toFixed(1)}" y="${w.count ? y : height - bottom - 2}" width="${bar.toFixed(1)}" height="${w.count ? h : 2}" rx="3"></rect>
      ${w.count ? `<text class="chart-value" x="${(x + bar / 2).toFixed(1)}" y="${y - 5}" text-anchor="middle">${w.count}</text>` : ""}
      <text class="chart-label" x="${(x + bar / 2).toFixed(1)}" y="${height - bottom + 16}" text-anchor="middle">${esc(label)}</text></g>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Applications per week, last 12 weeks">${bars}</svg>`;
}

function funnelHtml(d) {
  const steps = [["Applied", d.total], ["Any reply", d.replied], ["Interview", d.interviews], ["Offer", d.offers]];
  return `<div class="funnel">${steps.map(([label, n]) => `
    <div class="funnel-row"><span class="funnel-label">${label}</span>
      <svg class="funnel-bar" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
        <rect class="funnel-track" x="0" y="0" width="100" height="10" rx="2"></rect>
        <rect class="funnel-fill" x="0" y="0" width="${d.total ? Math.max(n ? 1.5 : 0, (100 * n) / d.total).toFixed(1) : 0}" height="10" rx="2"></rect></svg>
      <b>${n}</b><span class="hint">${d.total ? `${Math.round((100 * n) / d.total)}%` : ""}</span></div>`).join("")}</div>`;
}

// One table: a heading row for each group, and the same columns throughout, so every number lines up.
function repliesTable(d) {
  const groups = [["By site you applied on", d.by_site], ["By match %", d.by_band],
                  ["Tailored resume or not", d.by_tailored], ["By resume design", d.by_design]].filter(([, rows]) => rows.length);
  const bodies = groups.map(([title, rows]) => `<tbody>
    <tr class="rate-group"><th colspan="4" scope="colgroup">${esc(title)}</th></tr>
    ${rows.map((r) => `<tr><td>${esc(r.label)}</td><td>${r.applied}</td><td>${r.replied}</td>
      <td><span class="rate-cell"><svg class="rate-bar" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true">
        <rect class="funnel-track" x="0" y="0" width="100" height="8" rx="2"></rect>
        <rect class="funnel-fill" x="0" y="0" width="${r.rate}" height="8" rx="2"></rect></svg><b>${r.rate}%</b></span></td></tr>`).join("")}
  </tbody>`).join("");
  return `<div class="rate-card"><table class="rate-table">
      <colgroup><col class="col-group"><col class="col-num"><col class="col-num"><col class="col-rate"></colgroup>
      <thead><tr><th scope="col">Group</th><th scope="col">Applied</th><th scope="col">Replies</th><th scope="col">Reply rate</th></tr></thead>
      ${bodies}</table>
    <p class="hint rate-note">Small numbers can mislead: a few more replies change these a lot.</p></div>`;
}

async function loadApplicationStats() {
  const box = $("#insight-applications");
  box.innerHTML = `<p class="hint">Working it out…</p>`;
  let d;
  try {
    d = await api("/api/insights/applications");
  } catch (err) {
    box.innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
    return;
  }
  if (!d.total) {
    box.innerHTML = `<p class="empty">No applications yet. Jobs appear here when you press <b>Apply</b> on them.</p>`;
    return;
  }
  const tile = (value, label, sub = "") => `<div class="stat"><b>${value}</b><span>${label}</span>${sub ? `<small>${sub}</small>` : ""}</div>`;
  box.innerHTML = `
    <div class="stat-row">
      ${tile(d.total, "applications")}
      ${tile(`${d.reply_rate}%`, "reply rate", `${d.replied} of ${d.total} replied`)}
      ${tile(d.interviews, "interviews")}
      ${tile(d.offers, "offers")}
    </div>
    <p class="hint">A reply is an interview, an offer or a rejection (set the stage on the <b>Applied</b> board).
      Recent applications may still get one.</p>
    <h3 class="insight-head">Applications per week</h3>
    ${weeksChart(d.weeks)}
    ${d.undated ? `<p class="hint">${d.undated} application${d.undated === 1 ? " has" : "s have"} no date (applied before JobHunt kept dates); set it in the Tracker panel on the Applied board.</p>` : ""}
    <h3 class="insight-head">From applying to an offer</h3>
    ${funnelHtml(d)}
    <h3 class="insight-head">What gets replies</h3>
    ${repliesTable(d)}`;
}

/* ---------- Salary ---------- */
function fillSelect(select, options, allLabel, current) {
  select.innerHTML = `<option value="">${esc(allLabel)}</option>`
    + options.filter(([, n]) => n).map(([value, n]) => `<option value="${esc(value)}">${esc(value)} (${n})</option>`).join("");
  select.value = options.some(([v, n]) => v === current && n) ? current : "";
}

function rangeChart(stats, expected) {
  const low = Math.min(stats.min, expected ?? stats.min), high = Math.max(stats.max, expected ?? stats.max);
  const span = high - low || 1;
  // Drawn at its real proportions (640 × 64), so the "you" label is never stretched.
  const x = (v) => (32 + (576 * (v - low)) / span).toFixed(1);
  const marker = expected != null
    ? `<line class="range-you" x1="${x(expected)}" x2="${x(expected)}" y1="6" y2="42"></line>
       <text class="range-you-label" x="${x(expected)}" y="58" text-anchor="middle">you ${expected}</text>` : "";
  return `<svg class="range-chart" viewBox="0 0 640 64" role="img"
      aria-label="Pay from ${stats.min} to ${stats.max} LPA, middle half ${stats.p25} to ${stats.p75}">
    <line class="range-line" x1="${x(stats.min)}" x2="${x(stats.max)}" y1="24" y2="24"></line>
    <rect class="range-box" x="${x(stats.p25)}" y="12" width="${(x(stats.p75) - x(stats.p25)).toFixed(1)}" height="24" rx="4"></rect>
    <line class="range-mid" x1="${x(stats.median)}" x2="${x(stats.median)}" y1="12" y2="36"></line>${marker}</svg>`;
}

async function loadSalary() {
  const title = $("#sal-title").value, city = $("#sal-city").value, exp = $("#sal-exp").value;
  const params = new URLSearchParams({ title, city, exp });
  let d;
  try {
    d = await api(`/api/insights/salary?${params}`);
  } catch (err) {
    $("#sal-result").innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
    return;
  }
  fillSelect($("#sal-title"), d.titles, "All job titles", title);
  fillSelect($("#sal-city"), d.cities, "All cities", city);
  fillSelect($("#sal-exp"), d.exps.map(([band, n]) => [band, n]), "Any experience", exp);
  $$("#sal-exp option").forEach((o) => o.value && (o.textContent = o.textContent.replace(o.value, `${o.value} years`)));
  if (!d.stats) {
    $("#sal-result").innerHTML = `<p class="hint">Only ${d.count} job${d.count === 1 ? "" : "s"} here show${d.count === 1 ? "s" : ""} pay
      (at least ${d.min_jobs} are needed). ${d.with_pay} of your ${d.total_jobs} jobs show pay; widen the choices above or search more.</p>`;
  } else {
    const s = d.stats;
    const you = d.expected != null
      ? `<p>Your expected CTC (${d.expected} LPA, from the Resume tab) is <b>${esc(d.position)}</b>.</p>`
      : `<p class="hint">Add your expected CTC on the Resume tab to see where it sits.</p>`;
    $("#sal-result").innerHTML = `
      <div class="stat-row">
        <div class="stat"><b>${s.p25}</b><span>LPA · lower quarter</span></div>
        <div class="stat"><b>${s.median}</b><span>LPA · median</span></div>
        <div class="stat"><b>${s.p75}</b><span>LPA · upper quarter</span></div>
      </div>
      ${rangeChart(s, d.expected)}
      <p class="hint">From ${d.count} jobs showing pay (${s.min}–${s.max} LPA). Half of them pay between ${s.p25} and ${s.p75} LPA.</p>
      ${you}`;
  }
  if (!insightState.loaded.hand) {
    insightState.loaded.hand = true;
    $("#h-state").innerHTML = `<option value="">Pick your state</option>`
      + d.states.map((st) => `<option value="${esc(st.name)}" data-tax="${st.tax}">${esc(st.name)}</option>`).join("")
      + `<option value="other">Other (type the amount)</option>`;
    // Your state from the location on the Resume tab: a state name, or a city from JobHunt's city list.
    const [profile, cities] = await Promise.all([api("/api/resume").then((r) => r.profile).catch(() => null),
                                                 api("/api/cities").catch(() => [])]);
    const where = `${profile?.contact?.location || ""}`.toLowerCase();
    const city = cities.find((c) => c.state && matchesWord(where, c.name.toLowerCase()));
    const state = d.states.find((st) => where.includes(st.name.toLowerCase()))
      || (city ? d.states.find((st) => st.name === city.state) : null);
    if (state) {
      $("#h-state").value = state.name;
      $("#h-pt").value = state.tax;
    }
    if (d.expected != null) $("#h-ctc").value = d.expected;
    updateInHand();
  }
}

["#sal-title", "#sal-city", "#sal-exp"].forEach((sel) => $(sel).addEventListener("change", loadSalary));

$("#h-state").addEventListener("change", () => {
  const option = $("#h-state").selectedOptions[0];
  if (option && option.dataset.tax != null && option.value !== "other") $("#h-pt").value = option.dataset.tax;
  updateInHand();
});
$("#hand-form").addEventListener("input", () => {
  clearTimeout(insightState.handTimer);
  insightState.handTimer = setTimeout(updateInHand, 250);
});
$("#hand-form").addEventListener("submit", (e) => e.preventDefault());

async function updateInHand() {
  const typed = Number($("#h-ctc").value);
  // 1,000 or more can't be lakhs a year (that would be ₹10 crore): it was typed in rupees, e.g. 600000 for 6 lakh.
  const inRupees = typed >= 1000;
  const lakhs = inRupees ? typed / 100000 : typed;
  const box = $("#hand-result");
  if (!lakhs || lakhs <= 0) {
    box.innerHTML = `<p class="hint">Type a CTC to see the monthly in-hand pay.</p>`;
    return;
  }
  const clamp = (sel, lo, hi, fallback) => Math.max(lo, Math.min(hi, Number($(sel).value) || fallback));
  try {
    const r = await api("/api/insights/in-hand", { method: "POST", body: {
      ctc: Math.round(Math.min(lakhs, 1000) * 100000), variable_pct: clamp("#h-variable", 0, 60, 0),
      basic_pct: clamp("#h-basic", 20, 80, 50), pf_capped: $("#h-pf").value === "capped",
      employer_pf_in_ctc: $("#h-epf").checked, gratuity_in_ctc: $("#h-gratuity").checked,
      professional_tax: Math.round(clamp("#h-pt", 0, 2500, 0)) } });
    box.innerHTML = `
      ${inRupees ? `<p class="hand-note">Read as ${rupees(typed)} a year (${+lakhs.toFixed(2)} lakh).</p>` : ""}
      <p class="hand-headline">About <b>${rupees(r.monthly)}</b> a month in hand</p>
      ${r.variable_after_tax ? `<p class="hint">Plus variable pay of about ${rupees(r.variable_after_tax)} after tax, when it is paid.</p>` : ""}
      <table class="hand-table"><thead><tr><th></th><th>A month</th><th>A year</th></tr></thead>
        <tbody>${r.rows.map((row) => `<tr class="${row.label.startsWith("In hand") || row.label.startsWith("Gross") ? "sum" : ""}">
          <td>${esc(row.label)}</td><td>${rupees(row.month)}</td><td>${rupees(row.year)}</td></tr>`).join("")}</tbody></table>
      <p class="hint">Income tax for the year, variable pay included: ${rupees(r.tax_year)}. ${rupees(r.pf_saved)} a year goes into
        your PF account (yours and your employer's share). An estimate: your payslip may differ (allowances, meal cards, NPS).</p>`;
  } catch (err) {
    box.innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
  }
}

/* ---------- Skill gaps ---------- */
function learnLinks(skill) {
  const q = encodeURIComponent(skill);
  return `<a href="https://www.youtube.com/results?search_query=${q}+tutorial+for+beginners" target="_blank" rel="noopener noreferrer">YouTube</a>
    · <a href="https://www.google.com/search?q=learn+${q}+free+course" target="_blank" rel="noopener noreferrer">Free courses</a>`;
}

async function loadSkillGaps() {
  const box = $("#insight-skills");
  box.innerHTML = `<p class="hint">Reading your jobs…</p>`;
  let d;
  try {
    d = await api("/api/insights/skills");
  } catch (err) {
    box.innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
    return;
  }
  const intro = `<p class="hint">Skills asked for by the ${d.jobs} job${d.jobs === 1 ? "" : "s"} with ${d.min_match}%+ match found in the
    last ${d.days} days (Hidden jobs left out) that your Resume tab doesn't mention, most asked first.</p>`;
  if (!d.has_profile) {
    box.innerHTML = `${intro}<p class="empty">Fill in the Resume tab first, so JobHunt knows which skills you already have.</p>`;
    return;
  }
  if (!d.skills.length) {
    box.innerHTML = `${intro}<p class="empty">${d.jobs ? "No gaps: your resume mentions every skill these jobs ask for." : "No matching jobs from the last 30 days yet. Search on the Jobs tab first."}</p>`;
    return;
  }
  box.innerHTML = `${intro}
    <ol class="gap-list">${d.skills.map((s) => `<li class="gap">
      <label class="gap-skill"><input type="checkbox" value="${esc(s.skill)}"> <b>${esc(s.skill)}</b></label>
      <span class="gap-count" title="${esc(s.examples.join("\n"))}">asked by ${s.jobs} job${s.jobs === 1 ? "" : "s"} (${s.share}%)</span>
      <svg class="gap-bar" viewBox="0 0 100 8" preserveAspectRatio="none" aria-hidden="true"><rect class="funnel-track" x="0" y="0" width="100" height="8" rx="2"></rect>
        <rect class="funnel-fill" x="0" y="0" width="${Math.max(2, s.share)}" height="8" rx="2"></rect></svg>
      <span class="gap-learn">${learnLinks(s.skill)}</span></li>`).join("")}</ol>
    <div class="pack-row"><button type="button" id="gap-add" class="btn primary">I have these: add to my Resume tab</button>
      <span class="hint">Tick only skills you really have; they go on your tailored resumes.</span></div>
    <p id="gap-status" class="hint"></p>`;
}

$("#insight-skills").addEventListener("click", async (e) => {
  if (!e.target.closest("#gap-add")) return;
  const skills = $$("#insight-skills .gap input:checked").map((cb) => cb.value).slice(0, 40);
  if (!skills.length) return alert("Tick the skills you have first.");
  try {
    const r = await api("/api/resume/skills", { method: "POST", body: { skills } });
    resumeState.profile = null; // the Resume tab reloads with them
    await loadSkillGaps();
    $("#gap-status").textContent = r.added.length ? `Added to your Resume tab: ${r.added.join(", ")}.` : "Those were already on your Resume tab.";
  } catch (err) {
    alert(err.message);
  }
});

/* ---------- Referral helper ---------- */
function outreachHtml(job, d) {
  const people = safeUrl(d.people_url);
  const block = (kind, title, hint) => {
    const flags = (d.flags || {})[kind] || [];
    return `<div class="outreach-block"><div class="pack-row"><b>${title}</b>
        <button type="button" class="btn small" data-copy-outreach="${kind}">Copy</button></div>
      <p class="hint">${hint}</p>
      <textarea id="outreach-${kind}" rows="6" placeholder="Press Write with AI.">${esc(d[kind] || "")}</textarea>
      ${flags.length ? `<p class="flag-why">Not in your saved details, check before sending: ${flags.map(esc).join(", ")}</p>` : ""}</div>`;
  };
  return `<p class="hint">JobHunt writes the messages from your saved details only; you send them yourself.</p>
    <div class="pack-row">${people ? `<a class="btn small" href="${esc(people)}" target="_blank" rel="noopener noreferrer">Find people at ${esc(job.company)} on LinkedIn</a>` : ""}
      <span class="hint">Opens LinkedIn's own search in your browser. Look for alumni of your college, people in the same team, or a recruiter.</span></div>
    ${block("referral", "Referral request", "For someone who works there: ask whether they would refer you.")}
    ${block("recruiter", "Note to the recruiter", "For the recruiter or hiring manager: LinkedIn message or email.")}
    ${d.model ? `<p class="hint">Written by ${esc(d.model)}${d.created_at ? ` · ${esc(shortDate(d.created_at))}` : ""}.</p>` : ""}`;
}

async function openOutreach(job) {
  insightState.outreachJob = job;
  $("#outreach-title").textContent = `Referral · ${job.title} · ${job.company}`;
  $("#outreach-status").textContent = "";
  $("#outreach-body").innerHTML = `<p class="hint">Loading…</p>`;
  showOverlay("#outreach-overlay");
  try {
    const d = await api(`/api/jobs/${job.id}/outreach`);
    $("#outreach-body").innerHTML = outreachHtml(job, d);
    $("#outreach-write").textContent = d.referral ? "Write again" : "Write with AI";
  } catch (err) {
    $("#outreach-body").innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
  }
}

function closeOutreach() {
  $("#outreach-overlay").hidden = true;
  insightState.outreachJob = null;
  unlockIfNoOverlay();
}

$("#outreach-close").addEventListener("click", closeOutreach);

$("#outreach-write").addEventListener("click", async () => {
  const job = insightState.outreachJob;
  const button = $("#outreach-write");
  button.disabled = true;
  $("#outreach-status").textContent = "Writing… (up to a minute)";
  try {
    const d = await api(`/api/jobs/${job.id}/outreach`, { method: "POST" });
    $("#outreach-body").innerHTML = outreachHtml(job, d);
    const flagged = Object.values(d.flags || {}).some((f) => f.length);
    $("#outreach-status").textContent = flagged ? "Written. Check the highlighted words before sending." : "Written. Nothing in it is outside your saved details.";
    button.textContent = "Write again";
  } catch (err) {
    $("#outreach-status").textContent = err.message;
  } finally {
    button.disabled = false;
  }
});

$("#outreach-body").addEventListener("click", (e) => {
  const copy = e.target.closest("[data-copy-outreach]");
  if (copy) copyText($(`#outreach-${copy.dataset.copyOutreach}`).value, copy);
});

$("#job-list").addEventListener("click", (e) => {
  const button = e.target.closest("[data-act=outreach]");
  if (!button) return;
  const job = state.jobs.find((j) => String(j.id) === button.closest("article.job-card").dataset.id);
  if (job) openOutreach(job);
});

/* ---------- Mock interview (typing) ---------- */
function lastScore(q) {
  return q.attempts.length ? q.attempts[q.attempts.length - 1].score : null;
}

function shuffle(items) {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  return items;
}

// A new random order every time; "weak only" keeps those whose latest score is below the weak mark.
function practiceOrder(questions, weakOnly, weakBelow) {
  const chosen = questions.map((q, i) => i)
    .filter((i) => !weakOnly || (lastScore(questions[i]) != null && lastScore(questions[i]) < weakBelow));
  return shuffle(chosen);
}

function hasWeak(p) {
  return p.session.questions.some((q) => lastScore(q) != null && lastScore(q) < p.session.weak_below);
}

// Which buttons show under the practice window; the rest are hidden.
function practiceButtons(shown = []) {
  for (const name of ["send", "save", "all", "skip", "next"]) $(`#practice-${name}`).hidden = !shown.includes(name);
  $("#practice-send").disabled = false;
  $("#practice-save").disabled = false;
  $("#practice-all").disabled = false;
}

function renderModeChoice() {
  const p = insightState.practice;
  practiceButtons();
  $("#practice-status").textContent = "";
  $("#practice-body").innerHTML = `<p class="hint">${p.queue.length} question${p.queue.length === 1 ? "" : "s"}${
      p.weakOnly ? " (weak ones)" : ""}, in a random order.</p>
    <h3 class="practice-q">How do you want feedback?</h3>
    <div class="mode-choice">
      <button type="button" class="btn mode-card" data-mode="each"><b>After each question</b>
        <span>Answer one, get its score and feedback, then go to the next.</span></button>
      <button type="button" class="btn mode-card" data-mode="end"><b>At the end</b>
        <span>Answer every question first, like a real interview, then get feedback for all of them at once.</span></button>
    </div>`;
}

function historyHtml(q) {
  if (!q.attempts.length) return `<p class="hint">First try at this question.</p>`;
  const scores = q.attempts.map((a) => `<span class="score-chip ${a.score >= 8 ? "good" : a.score >= 6 ? "mid" : "low"}"
    title="${esc(shortDate(a.at))}">${a.score}</span>`).join("→");
  return `<p class="hint practice-history">Your scores so far: ${scores}</p>`;
}

function finalSummaryHtml(p) {
  const scored = p.session.questions.filter((q) => q.attempts.length);
  const average = scored.length ? (scored.reduce((n, q) => n + lastScore(q), 0) / scored.length).toFixed(1) : null;
  const weak = scored.filter((q) => lastScore(q) < p.session.weak_below).length;
  $("#practice-weak").disabled = !weak;
  return `<p class="hand-headline">${p.weakOnly ? "Weak ones done." : "That's every question."}</p>
    <p>${average != null ? `Average of your latest scores: <b>${average}/10</b>. ` : ""}${weak ? `${weak} still below ${p.session.weak_below}: press <b>Retry weak ones</b>.` : "None below " + p.session.weak_below + " — well done."}</p>`;
}

function renderPracticeQuestion() {
  const p = insightState.practice;
  const body = $("#practice-body");
  $("#practice-status").textContent = "";
  if (p.pos >= p.queue.length) {
    if (p.mode === "end" && p.pending.some((a) => !a.result)) return renderEndReady();
    practiceButtons();
    body.innerHTML = finalSummaryHtml(p);
    return;
  }
  const q = p.session.questions[p.queue[p.pos]];
  practiceButtons(p.mode === "end" ? ["save", "skip"] : ["send", "skip"]);
  body.innerHTML = `<p class="hint">Question ${p.pos + 1} of ${p.queue.length}${p.weakOnly ? " (weak ones)" : ""}${
      p.mode === "end" ? ` · feedback at the end · ${p.pending.length} answered so far` : ""}</p>
    <h3 class="practice-q">${esc(q.question)}</h3>
    ${historyHtml(q)}
    <label class="field"><span>Your answer (type it as you would say it)</span>
      <textarea id="practice-answer" rows="8" maxlength="4000"></textarea></label>
    <div id="practice-feedback" aria-live="polite"></div>`;
  $("#practice-answer").focus();
}

/* "At the end" mode: answers are kept here until "Get feedback for all" scores them. */
function renderEndReady() {
  const p = insightState.practice;
  const waiting = p.pending.filter((a) => !a.result).length;
  practiceButtons(["all"]);
  $("#practice-body").innerHTML = `<p class="hand-headline">All questions done.</p>
    <p>You answered <b>${p.pending.length}</b> of ${p.queue.length}. Press <b>Get feedback for all</b> to score
      ${waiting === 1 ? "it" : `all ${waiting}`} (each takes a few seconds; up to a minute or two in all).</p>`;
}

async function scoreOne(p, item) {
  const q = p.session.questions[item.i];
  for (let tries = 0; ; tries++) {
    try {
      return await api("/api/practice/answer", { method: "POST", body: {
        title: p.title, company: p.company, question: q.question, answer: item.typed,
        session_id: p.session.session_id, mode: p.mode } });
    } catch (err) {
      if (err.status !== 429 || tries >= 4 || insightState.practice !== p) throw err;
      $("#practice-status").textContent = `Waiting ${err.retryAfter || 15} seconds: too many AI requests at once…`;
      await new Promise((resolve) => setTimeout(resolve, (err.retryAfter || 15) * 1000));
    }
  }
}

async function scoreAll() {
  const p = insightState.practice;
  const todo = p.pending.filter((a) => !a.result);
  if (!todo.length) return renderEndResults();
  p.scoring = true;
  practiceButtons();
  let done = 0;
  const show = () => ($("#practice-status").textContent = `Getting feedback… ${done} of ${todo.length} scored`);
  show();
  $("#practice-body").innerHTML = `<p class="hint"><span class="spinner small"></span> Scoring your answers, two at a time…</p>`;
  const queue = [...todo];
  const worker = async () => {
    while (queue.length && insightState.practice === p) {
      const item = queue.shift();
      try {
        item.result = await scoreOne(p, item);
        item.error = null;
        p.session.questions[item.i].attempts.push({ score: item.result.score, at: new Date().toISOString(),
                                                    answer: item.typed, feedback: item.result });
      } catch (err) {
        item.error = err.message;
      }
      done += 1;
      if (insightState.practice === p) show();
    }
  };
  await Promise.all([worker(), worker()]);
  p.scoring = false;
  if (insightState.practice === p) renderEndResults();
}

function renderEndResults() {
  const p = insightState.practice;
  const scored = p.pending.filter((a) => a.result);
  const failed = p.pending.filter((a) => !a.result);
  const average = scored.length ? (scored.reduce((n, a) => n + a.result.score, 0) / scored.length).toFixed(1) : null;
  practiceButtons();
  $("#practice-status").textContent = failed.length ? `${failed.length} could not be scored; press Try again on them.` : "";
  const items = p.pending.map((a, n) => {
    const q = p.session.questions[a.i];
    const result = a.result ? feedbackHtml(a.result, q)
      : `<p class="import-result err">${esc(a.error || "Not scored yet.")}</p>
         <button type="button" class="btn small" data-rescore="${n}">Try again</button>`;
    return `<li class="end-result"><h3 class="practice-q">${esc(q.question)}</h3>
      <details class="practice-ref"><summary>Your answer</summary><p>${esc(a.typed)}</p></details>${result}</li>`;
  }).join("");
  $("#practice-body").innerHTML = `${finalSummaryHtml(p)}
    ${average != null ? `<p>This session: <b>${average}/10</b> average over ${scored.length} answer${scored.length === 1 ? "" : "s"}.</p>` : ""}
    <ol class="end-results">${items}</ol>`;
}

function practiceDirty() {
  const p = insightState.practice;
  return !!p && (p.scoring || p.pending.some((a) => !a.result));
}

function feedbackHtml(r, q) {
  const list = (items) => items.length ? `<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<p class="hint">–</p>`;
  const level = r.score >= 8 ? "good" : r.score >= 6 ? "mid" : "low";
  return `<div class="feedback">
    <p class="feedback-score"><span class="score-chip big ${level}">${r.score}/10</span></p>
    <div class="feedback-grid"><div><h4>What worked</h4>${list(r.strengths)}</div><div><h4>What to improve</h4>${list(r.improve)}</div></div>
    ${r.better_answer ? `<h4>A stronger answer, from your resume</h4><p class="better-answer">${esc(r.better_answer)}</p>
      <button type="button" class="btn small" data-copy="${esc(r.better_answer)}">Copy</button>` : ""}
    ${r.flags.length ? `<p class="flag-why">Not in your saved details, don't say it unless it's true: ${r.flags.map(esc).join(", ")}</p>` : ""}
    ${q.reference ? `<details class="practice-ref"><summary>Answer reported on the web</summary><p>${esc(q.reference)}</p></details>` : ""}
    <p class="hint">Feedback by ${esc(r.model)}.</p></div>`;
}

async function openPractice(title, company = "") {
  insightState.practice = null;
  $("#practice-title").textContent = `Practice · ${company ? `${company} · ` : ""}${title}`;
  $("#practice-body").innerHTML = `<p class="hint">Loading your saved questions…</p>`;
  $("#practice-status").textContent = "";
  practiceButtons();
  showOverlay("#practice-overlay");
  try {
    const session = await api(`/api/practice?${new URLSearchParams({ title, company })}`);
    insightState.practice = { session, title, company, mode: null, weakOnly: false, pos: 0, pending: [], scoring: false,
                              queue: practiceOrder(session.questions, false, session.weak_below) };
    $("#practice-weak").disabled = !hasWeak(insightState.practice);
    renderModeChoice();
  } catch (err) {
    $("#practice-body").innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
    $("#practice-weak").disabled = true;
  }
}

function closePractice() {
  if (practiceDirty()) {
    const p = insightState.practice;
    const waiting = p.pending.filter((a) => !a.result).length;
    const why = p.scoring ? "Your answers are still being scored." : `${waiting} typed answer${waiting === 1 ? " hasn't" : "s haven't"} been scored yet and will be lost.`;
    if (!confirm(`${why} Close anyway?`)) return;
  }
  $("#practice-overlay").hidden = true;
  insightState.practice = null;
  unlockIfNoOverlay();
}

$("#practice-close").addEventListener("click", closePractice);

$("#practice-send").addEventListener("click", async () => {
  const p = insightState.practice;
  if (!p) return;
  const q = p.session.questions[p.queue[p.pos]];
  const typed = $("#practice-answer").value.trim();
  if (!typed) return alert("Type your answer first.");
  $("#practice-send").disabled = true;
  $("#practice-skip").hidden = true;
  $("#practice-status").textContent = "Getting feedback… (up to a minute)";
  try {
    const r = await scoreOne(p, { i: p.queue[p.pos], typed });
    if (insightState.practice !== p) return;
    q.attempts.push({ score: r.score, at: new Date().toISOString(), answer: typed, feedback: r });
    $("#practice-feedback").innerHTML = feedbackHtml(r, q);
    $("#practice-status").textContent = "";
    practiceButtons(["next"]);
    $("#practice-weak").disabled = !hasWeak(p);
  } catch (err) {
    $("#practice-status").textContent = err.message;
    $("#practice-send").disabled = false;
    $("#practice-skip").hidden = false;
  }
});

$("#practice-save").addEventListener("click", () => {
  const p = insightState.practice;
  if (!p) return;
  const typed = $("#practice-answer").value.trim();
  if (!typed) return alert("Type your answer first, or press Skip.");
  p.pending.push({ i: p.queue[p.pos], typed, result: null, error: null });
  nextPractice();
});

$("#practice-all").addEventListener("click", () => insightState.practice && scoreAll());

function nextPractice() {
  insightState.practice.pos += 1;
  renderPracticeQuestion();
}

$("#practice-skip").addEventListener("click", () => insightState.practice && nextPractice());
$("#practice-next").addEventListener("click", () => insightState.practice && nextPractice());
$("#practice-weak").addEventListener("click", () => {
  const p = insightState.practice;
  if (!p || p.scoring) return;
  if (p.pending.some((a) => !a.result) && !confirm("Your unscored answers will be lost. Retry weak ones anyway?")) return;
  Object.assign(p, { weakOnly: true, pos: 0, pending: [], queue: practiceOrder(p.session.questions, true, p.session.weak_below) });
  if (p.mode) renderPracticeQuestion();
  else renderModeChoice();
});
$("#practice-body").addEventListener("click", async (e) => {
  const copy = e.target.closest("[data-copy]");
  if (copy) return copyText(copy.dataset.copy, copy);
  const p = insightState.practice;
  if (!p) return;
  const mode = e.target.closest("[data-mode]");
  if (mode) {
    p.mode = mode.dataset.mode;
    return renderPracticeQuestion();
  }
  const again = e.target.closest("[data-rescore]");
  if (again && !p.scoring) {
    const item = p.pending[Number(again.dataset.rescore)];
    if (item) {
      item.error = null;
      await scoreAll();
    }
  }
});

for (const box of ["#saved-titles", "#saved-companies"]) {
  $(box).addEventListener("click", (e) => {
    const button = e.target.closest("[data-practise]");
    if (button) openPractice(button.dataset.title, button.dataset.company || "");
    const old = e.target.closest("[data-sessions]");
    if (old) openSessions(old.dataset.title, old.dataset.company || "");
  });
}

/* ---------- Old practice sessions: each opening of Practise, to see the improvement ---------- */
function scoreChip(score, big = false) {
  if (score == null) return `<span class="score-chip">–</span>`;
  const level = score >= 8 ? "good" : score >= 6 ? "mid" : "low";
  return `<span class="score-chip ${level}${big ? " big" : ""}">${score}</span>`;
}

function changeHtml(change) {
  if (change == null) return `<span class="hint">first session</span>`;
  if (change > 0) return `<span class="trend up">▲ +${change}</span>`;
  if (change < 0) return `<span class="trend down">▼ ${change}</span>`;
  return `<span class="trend">no change</span>`;
}

function sessionHtml(s, open) {
  const when = new Date(s.started).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
  const label = s.id.startsWith("day:")
    ? `${esc(new Date(s.started).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }))} <span class="hint">(before sessions were kept)</span>`
    : esc(when);
  const mode = s.mode === "end" ? "feedback at the end" : s.mode === "each" ? "feedback after each" : "";
  const list = (items) => (items || []).length ? `<ul>${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<p class="hint">–</p>`;
  const attempts = s.attempts.map((a) => {
    const f = a.feedback || {};
    return `<li class="session-attempt"><p class="session-q">${scoreChip(a.score)} <b>${esc(a.question)}</b></p>
      <details class="practice-ref"><summary>Your answer and the feedback</summary>
        <p>${esc(a.answer)}</p>
        <div class="feedback-grid"><div><h4>What worked</h4>${list(f.strengths)}</div><div><h4>What to improve</h4>${list(f.improve)}</div></div>
        ${f.better_answer ? `<h4>A stronger answer, from your resume</h4><p class="better-answer">${esc(f.better_answer)}</p>` : ""}
      </details></li>`;
  }).join("");
  return `<details class="saved-qa session"${open ? " open" : ""}><summary><b>${label}</b>
      <span class="hint">· ${s.answered} answer${s.answered === 1 ? "" : "s"}${mode ? ` · ${mode}` : ""} · average</span>
      ${s.average != null ? scoreChip(s.average) : "–"} ${changeHtml(s.change)}</summary>
    <ol class="qa-list">${attempts}</ol></details>`;
}

async function openSessions(title, company = "") {
  $("#sessions-title").textContent = `Old Practise Sessions · ${company ? `${company} · ` : ""}${title}`;
  $("#sessions-body").innerHTML = `<p class="hint">Loading your earlier sessions…</p>`;
  showOverlay("#sessions-overlay");
  try {
    const d = await api(`/api/practice/sessions?${new URLSearchParams({ title, company })}`);
    if (!d.sessions.length) {
      $("#sessions-body").innerHTML = `<p class="hint">No practice yet for this. Press <b>Practise</b> to start your first session.</p>`;
      return;
    }
    const trend = [...d.sessions].reverse().filter((s) => s.average != null).map((s) => scoreChip(s.average)).join("→");
    const latest = d.sessions.find((s) => s.average != null);
    $("#sessions-body").innerHTML = `<p class="practice-history">${d.sessions.length} session${d.sessions.length === 1 ? "" : "s"}, newest first.
        ${trend ? ` Average per session, oldest to newest: ${trend}` : ""}</p>
      ${latest ? `<p class="hint">Latest average ${latest.average}/10. Scores of ${d.weak_below} and up are not weak.</p>` : ""}
      ${d.sessions.map((s, n) => sessionHtml(s, n === 0)).join("")}`;
  } catch (err) {
    $("#sessions-body").innerHTML = `<p class="import-result err">${esc(err.message)}</p>`;
  }
}

$("#sessions-close").addEventListener("click", () => {
  $("#sessions-overlay").hidden = true;
  unlockIfNoOverlay();
});
$("#qa-practise").addEventListener("click", () => {
  const job = resumeState.qaJob;
  if (job) openPractice(job.title, job.company || "");
});

