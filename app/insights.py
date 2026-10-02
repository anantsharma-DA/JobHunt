"""The Insights tab: how your applications are going, what jobs like yours pay (and what a CTC means in hand), and
the skills adverts for your kind of job ask for that your resume doesn't show. All worked out from your own data."""
import json
import re
from datetime import date, datetime, timedelta
from statistics import quantiles

from app import db, matching, resume, tracker

# ---------- Your applications ----------

REPLIED = ("interview", "offer", "rejected")  # any answer from the company, a rejection included
WEEKS = 12
MATCH_BANDS = ((70, "70% and above"), (40, "40–69%"), (0, "Below 40%"))
SITE_NAMES = {"linkedin": "LinkedIn", "indeed": "Indeed", "naukri": "Naukri", "company": "Company site"}


def _reached(app, stages):
    """True when the application is, or once was, at one of these stages."""
    return app["stage"] in stages or any(step.get("stage") in stages for step in app.get("history") or [])


def _apply_site(job):
    """The site the Apply button used: the one whose link is the job's apply link, else the first listed."""
    sources = job.get("sources") or []
    for src in sources:
        if job.get("apply_url") and job["apply_url"] in (src.get("direct"), src.get("url")):
            return src.get("site")
    return sources[0].get("site") if sources else None


def _rate(rows):
    applied = len(rows)
    replied = sum(1 for r in rows if r["replied"])
    return {"applied": applied, "replied": replied, "rate": round(100 * replied / applied) if applied else None}


def _grouped(rows, key, order=None):
    groups = {}
    for row in rows:
        groups.setdefault(row[key], []).append(row)
    names = order or sorted(groups, key=lambda name: -len(groups[name]))
    return [{"label": name, **_rate(groups[name])} for name in names if name in groups]


def applications(jobs, apps, tailored, settings, today=None):
    """Applications per week, the Applied → Interview → Offer funnel, and reply rates by site, resume design, match
    band and whether the resume was tailored."""
    today = today or date.today()
    titles, skills = matching.split_terms(settings["titles"]), matching.split_terms(settings["skills"])
    rows = []
    for job in jobs:
        if job["status"] != "applied":
            continue
        app = tracker.view(job, apps.get(job["id"]), settings["followup_days"])
        made = tailored.get(job["id"])
        score, _ = matching.score_job(job["title"], f"{job.get('description') or ''}\n{job.get('skills_listed') or ''}",
                                      job["search_titles"] or titles, skills)
        rows.append({
            "applied_on": app["applied_on"],
            "replied": _reached(app, REPLIED),
            "interview": _reached(app, ("interview", "offer")),
            "offer": _reached(app, ("offer",)),
            "site": SITE_NAMES.get(_apply_site(job), "Other"),
            "design": ((made.get("design") or "modern").capitalize() + " design") if made and made.get("pdf") else "No tailored PDF",
            "tailored": "Tailored resume" if made and made.get("pdf") else "Not tailored",
            "band": next(label for low, label in MATCH_BANDS if score >= low),
        })
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=WEEKS - 1)  # Monday, 11 weeks before this one
    weeks = [{"start": (start + timedelta(weeks=i)).isoformat(), "count": 0} for i in range(WEEKS)]
    undated = 0
    for row in rows:
        try:
            day = date.fromisoformat(row["applied_on"])
        except (TypeError, ValueError):
            undated += 1
            continue
        index = (day - start).days // 7
        if 0 <= index < WEEKS:
            weeks[index]["count"] += 1
    total = _rate(rows)
    return {
        "total": total["applied"], "replied": total["replied"], "reply_rate": total["rate"],
        "interviews": sum(r["interview"] for r in rows), "offers": sum(r["offer"] for r in rows),
        "weeks": weeks, "undated": undated,
        "by_site": _grouped(rows, "site"),
        "by_design": _grouped(rows, "design"),
        "by_band": _grouped(rows, "band", [label for _, label in MATCH_BANDS]),
        "by_tailored": _grouped(rows, "tailored", ["Tailored resume", "Not tailored"]),
    }


# ---------- Salary: what jobs like yours pay ----------

EXP_BANDS = (("0-2", 0, 2), ("2-5", 2, 5), ("5-8", 5, 8), ("8+", 8, 99))
MIN_JOBS = 3  # fewer jobs than this with pay shown is too few to say what's typical


def _lpa(job):
    """One figure for the job's pay: the middle of its range, or the one end given."""
    low, high = job.get("salary_min"), job.get("salary_max")
    if low is not None and high is not None:
        return (low + high) / 2
    return high if high is not None else low


def _exp_band(job):
    years = job.get("exp_min")
    if years is None:
        return None
    return next((name for name, low, high in EXP_BANDS if low <= years < high), None)


def parse_lpa(text):
    """'9 LPA', '9.5 lakh', '₹9,00,000' or '900000' as lakhs a year; None if there's no number."""
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(text or ""))
    if not match:
        return None
    value = float(match.group().replace(",", ""))
    if value >= 1000:  # written in rupees
        value /= 100000
    return round(value, 2) if value > 0 else None


def salary(jobs, profile, title="", city="", exp=""):
    """Typical pay (25th percentile, median, 75th percentile, in LPA) for the jobs you've found that show pay,
    narrowed by the job title searched, city and experience band, next to your expected CTC."""
    paid = [j for j in jobs if _lpa(j) is not None]
    def fits(job, skip=None):
        return ((skip == "title" or not title or title in (job.get("search_titles") or []))
                and (skip == "city" or not city or city in (job.get("cities") or []))
                and (skip == "exp" or not exp or _exp_band(job) == exp))
    chosen = [j for j in paid if fits(j)]
    values = sorted(_lpa(j) for j in chosen)
    stats = None
    if len(values) >= MIN_JOBS:
        low, mid, high = quantiles(values, n=4, method="inclusive")
        stats = {"p25": round(low, 1), "median": round(mid, 1), "p75": round(high, 1),
                 "min": round(values[0], 1), "max": round(values[-1], 1)}
    expected = parse_lpa(((profile or {}).get("answers") or {}).get("expected_ctc"))
    position = None
    if stats and expected is not None:
        position = ("below the typical range" if expected < stats["p25"] else "above the typical range" if expected > stats["p75"]
                    else "within the typical range")

    def options(field_values):
        counts = {}
        for value in field_values:
            counts[value] = counts.get(value, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        "count": len(values), "min_jobs": MIN_JOBS, "stats": stats, "expected": expected, "position": position,
        "total_jobs": len(jobs), "with_pay": len(paid),
        "titles": options(t for j in paid if fits(j, "title") for t in (j.get("search_titles") or [])),
        "cities": options(c for j in paid if fits(j, "city") for c in (j.get("cities") or [])),
        "exps": [(name, sum(1 for j in paid if fits(j, "exp") and _exp_band(j) == name)) for name, _, _ in EXP_BANDS],
    }


# ---------- CTC to monthly in-hand pay (new tax regime, FY 2026-27) ----------
# Checked 2026-09-27: Budget 2026 left the new-regime slabs, the ₹75,000 standard deduction and the section 87A rebate
# (no tax up to ₹12 lakh of taxable income, with marginal relief just above) unchanged for FY 2026-27.

SLABS = ((400000, 0.0), (800000, 0.05), (1200000, 0.10), (1600000, 0.15), (2000000, 0.20), (2400000, 0.25), (None, 0.30))
STANDARD_DEDUCTION = 75000
REBATE_LIMIT = 1200000
SURCHARGES = ((20000000, 0.25), (10000000, 0.15), (5000000, 0.10))  # above ₹2 crore it stays 25% in the new regime
CESS = 0.04
PF_RATE = 0.12
PF_WAGE_CAP = 15000 * 12  # the PF wage limit: capped PF is 12% of ₹15,000 a month
GRATUITY_RATE = 0.0481
# Professional tax a year at typical salaries (each state's top slab). It varies with pay, so it can be edited.
PROFESSIONAL_TAX = {
    "Rajasthan": 0, "Delhi": 0, "Uttar Pradesh": 0, "Haryana": 0, "Uttarakhand": 0, "Himachal Pradesh": 0,
    "Maharashtra": 2500, "Karnataka": 2400, "Tamil Nadu": 2500, "Telangana": 2400, "Andhra Pradesh": 2400,
    "West Bengal": 2400, "Gujarat": 2400, "Madhya Pradesh": 2500, "Kerala": 2500, "Odisha": 2500,
    "Assam": 2500, "Jharkhand": 2500, "Bihar": 2500, "Punjab": 2400,
}


def _slab_tax(taxable):
    tax, lower = 0.0, 0
    for upper, rate in SLABS:
        if taxable <= lower:
            break
        top = taxable if upper is None else min(taxable, upper)
        tax += (top - lower) * rate
        if upper is None:
            break
        lower = upper
    return tax


def _after_rebate(taxable):
    if taxable <= REBATE_LIMIT:
        return 0.0
    return min(_slab_tax(taxable), taxable - REBATE_LIMIT)  # marginal relief: never more than the income above ₹12 lakh


def _surcharge_rate(taxable):
    return next((rate for threshold, rate in SURCHARGES if taxable > threshold), 0.0)


def income_tax(income):
    """Tax a year on salary income under the new regime: slabs, the 87A rebate with marginal relief, surcharge with
    marginal relief, and 4% cess."""
    taxable = max(0.0, income - STANDARD_DEDUCTION)
    tax = _after_rebate(taxable)
    rate = _surcharge_rate(taxable)
    if rate:
        # Marginal relief: crossing ₹50 lakh / ₹1 crore / ₹2 crore never costs more than the income above it.
        threshold = next(t for t, r in SURCHARGES if taxable > t)
        limit = _after_rebate(threshold) * (1 + _surcharge_rate(threshold)) + (taxable - threshold)
        tax = min(tax * (1 + rate), limit)
    return round(tax * (1 + CESS))


def in_hand(ctc, variable_pct=0.0, basic_pct=50.0, pf_capped=False, employer_pf_in_ctc=True, gratuity_in_ctc=True,
            professional_tax=0):
    """What a yearly CTC (in rupees) pays each month. Variable pay is paid separately (usually once a year), so the
    monthly figure leaves it out; the tax it adds is taken from it."""
    variable = ctc * variable_pct / 100
    fixed = ctc - variable
    basic = fixed * basic_pct / 100
    pf = min(basic, PF_WAGE_CAP) * PF_RATE if pf_capped else basic * PF_RATE
    employer_pf = pf if employer_pf_in_ctc else 0.0
    gratuity = basic * GRATUITY_RATE if gratuity_in_ctc else 0.0
    gross = fixed - employer_pf - gratuity
    tax_fixed = income_tax(gross)
    tax_total = income_tax(gross + variable)
    take_home = gross - pf - professional_tax - tax_fixed
    rows = [("CTC", ctc), ("Variable pay (paid separately)", -variable), ("Employer PF (inside CTC)", -employer_pf),
            ("Gratuity (inside CTC)", -gratuity), ("Gross fixed pay", gross), ("Your PF (12%)", -pf),
            ("Professional tax", -professional_tax), ("Income tax on fixed pay (new regime, incl. 4% cess)", -tax_fixed),
            ("In hand from fixed pay", take_home)]
    return {
        "monthly": round(take_home / 12), "yearly": round(take_home),
        "variable_after_tax": round(variable - (tax_total - tax_fixed)), "tax_year": tax_total,
        "rows": [{"label": label, "year": round(value), "month": round(value / 12)} for label, value in rows
                 if value or label in ("CTC", "Gross fixed pay", "In hand from fixed pay")],
        "pf_saved": round(pf + employer_pf),
    }


# ---------- Skill gaps ----------

GAP_DAYS = 30
GAP_MIN_MATCH = 40  # jobs below this match are too far from what you look for to count
GAP_LIMIT = 30


def _role_names():
    """Job titles from the catalogue: Naukri's skill tags often include them ("data scientist"), and a job title isn't
    a skill you could add to your resume."""
    try:
        catalog = json.loads(resume.CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {t["title"].lower() for category in catalog.get("categories", []) for t in category.get("titles", []) if t.get("title")}


def _listed_skills(job, roles):
    tags = [s.strip() for s in re.split(r"[,;|\n]", job.get("skills_listed") or "") if 1 < len(s.strip()) <= 40]
    return [t for t in tags if t.lower() not in roles and t.lower() not in {s.lower() for s in job.get("search_titles") or []}]


def skill_gaps(jobs, profile, settings, now=None):
    """Skills that jobs you'd apply for (40%+ match, not hidden, found in the last 30 days) ask for and your resume
    details don't mention, most asked first."""
    now = now or datetime.now()
    since = (now - timedelta(days=GAP_DAYS)).isoformat(timespec="seconds")
    titles, skills = matching.split_terms(settings["titles"]), matching.split_terms(settings["skills"])
    have = resume.profile_text(profile) if profile else ""
    chosen = []
    for job in jobs:
        if job["status"] == "hidden" or (job.get("first_seen") or "") < since:
            continue
        text = f"{job.get('description') or ''}\n{job.get('skills_listed') or ''}"
        score, _ = matching.score_job(job["title"], text, job["search_titles"] or titles, skills)
        if score >= GAP_MIN_MATCH:
            chosen.append(job)
    catalog, roles = resume.catalog_skills(), _role_names()
    counts, spelling, examples = {}, {}, {}
    for job in chosen:
        text = "\n".join(str(job.get(f) or "") for f in ("title", "description", "skills_listed"))
        seen = set()
        for skill in matching.find_terms(text, catalog) + _listed_skills(job, roles):
            key = re.sub(r"[\s\-_/]+", " ", skill.lower()).strip()
            if key in seen or any(matching.mentions(other, skill) for other in seen if len(other) > len(key)):
                continue
            seen.add(key)
            counts[key] = counts.get(key, 0) + 1
            spelling.setdefault(key, skill)
            examples.setdefault(key, []).append(f"{job['title']} at {job['company']}")
    def has(skill):  # "Dashboards" is covered by "dashboard" on your resume, and the other way round
        forms = {skill, skill[:-1] if skill.lower().endswith("s") and len(skill) > 3 else skill, skill + "s"}
        return any(matching.mentions(have, form) for form in forms)

    gaps = [key for key in counts if not has(spelling[key])]
    gaps.sort(key=lambda key: (-counts[key], key))
    return {
        "jobs": len(chosen), "days": GAP_DAYS, "min_match": GAP_MIN_MATCH, "has_profile": bool(have),
        "skills": [{"skill": spelling[key], "jobs": counts[key], "share": round(100 * counts[key] / len(chosen)),
                    "examples": examples[key][:3]} for key in gaps[:GAP_LIMIT]],
    }


def application_inputs():
    """What the applications statistics need from the database."""
    tailored = {}
    for row in db.list_tailored():
        tailored[row["job_id"]] = {"design": (row.get("data") or {}).get("design"), "pdf": bool(row.get("pdf_path"))}
    return db.list_jobs(), db.list_applications(), tailored
