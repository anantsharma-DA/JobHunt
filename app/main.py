"""JobHunt web app: serves the page and the JSON API. Start with run.bat."""
import collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from app import applicant_update, company_import, db, matching, normalize, search
from app.cities import CITIES
from app.sources import ats, naukri

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
SEARCH_SOURCES = ("linkedin", "indeed", "naukri", "companies")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TITLES = 20

# JobHunt only runs on this computer. The browser must reach it by one of these names; any other Host (for example
# an attacker's domain re-pointed at 127.0.0.1, "DNS rebinding") is refused, so other websites can't read its data.
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# static/app.js sends this header on every change. A page on another website can't add a custom header to a request
# here without a CORS approval this app never gives, so it can't clear jobs, import companies or start searches.
CSRF_HEADER = "x-jobhunt"
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
        "font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}

db.connect()
# No /docs, /redoc or /openapi.json: the page doesn't need them, and they would list every action the API offers.
app = FastAPI(title="JobHunt", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _refuse(status, message):
    return JSONResponse({"detail": message}, status_code=status, headers=SECURITY_HEADERS)


@app.middleware("http")
async def protect_local_app(request: Request, call_next):
    """Keeps other websites open in the same browser from reading or changing JobHunt, and adds security headers."""
    host_header = request.headers.get("host", "")
    if "@" in host_header or urlparse(f"//{host_header}").hostname not in ALLOWED_HOSTS:
        return _refuse(400, "JobHunt only answers on localhost.")
    if request.method not in SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc.lower() != host_header.lower():
            return _refuse(403, "Request from another website refused.")
        if request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            return _refuse(403, "Request from another website refused.")
        if request.headers.get(CSRF_HEADER) != "1":
            return _refuse(403, "Request refused: it did not come from the JobHunt page.")
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        # Browsers (Opera especially) otherwise keep old copies of app.js/styles.css after the app is updated.
        response.headers["Cache-Control"] = "no-cache"
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    # Version the asset links by file time so every browser fetches the new file after an update.
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for name in ("styles.css", "app.js"):
        version = int((STATIC_DIR / name).stat().st_mtime)
        html = html.replace(f'"/static/{name}"', f'"/static/{name}?v={version}"')
    return HTMLResponse(html)


# ---------- Input limits ----------

SourceName = Annotated[str, StringConstraints(max_length=20)]
CityName = Annotated[str, StringConstraints(max_length=60)]


# ---------- Search ----------

class SearchRequest(BaseModel):
    titles: str = Field(max_length=2000)
    skills: str = Field("", max_length=4000)
    minutes_old: int = Field(10080, ge=5, le=30 * 24 * 60)
    sources: list[SourceName] = Field(max_length=10)
    search_cities: list[CityName] = Field(default_factory=list, max_length=50)


@app.post("/api/search")
def start_search(req: SearchRequest):
    titles = matching.split_terms(req.titles)
    if not titles:
        raise HTTPException(400, "Enter at least one job title.")
    if len(titles) > MAX_TITLES:
        raise HTTPException(400, f"Pick at most {MAX_TITLES} job titles per search.")
    sources = [s for s in req.sources if s in SEARCH_SOURCES]
    if not sources:
        raise HTTPException(400, "Tick at least one site to search on.")
    if applicant_update.is_running():
        raise HTTPException(409, "Applicant counts are being updated. Wait for that to finish, or press Stop.")
    settings = db.save_settings({"titles": req.titles, "skills": req.skills, "minutes_old": req.minutes_old, "sources": sources,
                                 "search_cities": req.search_cities})
    if not search.start(settings):
        raise HTTPException(409, "A search is already running. Wait for it to finish.")
    return search.status()


@app.get("/api/search/status")
def search_status():
    return search.status()


@app.post("/api/search/cancel")
def cancel_search():
    return {"cancelling": search.cancel()}


@app.get("/api/cities")
def list_cities():
    return [{"name": name, "state": state} for name, state, _ in CITIES]


# ---------- Jobs ----------

RATING_FIELDS = ("company_rating", "company_reviews", "company_rating_url")


def _company_ratings(jobs):
    """Best-known rating per company (the one with the most reviews), keyed by normalised company name.

    Only Naukri gives ratings, but they describe the company, so the same company's jobs from other sites show them too.
    """
    best = {}
    for job in jobs:
        if job["company_rating"] is None:
            continue
        key = normalize.company_key(job["company"])
        if not key or key == "unknown company":
            continue
        if key not in best or (job["company_reviews"] or 0) > (best[key]["company_reviews"] or 0):
            best[key] = {field: job[field] for field in RATING_FIELDS}
    return best


@app.get("/api/jobs")
def list_jobs():
    settings = db.get_settings()
    titles = matching.split_terms(settings["titles"])
    skills = matching.split_terms(settings["skills"])
    rows = db.list_jobs()
    ratings = _company_ratings(rows)
    jobs = []
    for job in rows:
        if job["company_rating"] is None:
            job.update(ratings.get(normalize.company_key(job["company"]), {}))
        text = f"{job.pop('description') or ''}\n{job.pop('skills_listed') or ''}"
        # Score the title against the search that found the job, so older jobs keep their score after a new search.
        score, matched = matching.score_job(job["title"], text, job["search_titles"] or titles, skills)
        job.pop("dedupe_key")
        # Jobs saved by older versions weren't link-checked; only http(s) links ever reach the page.
        job["apply_url"] = normalize.safe_url(job["apply_url"])
        job["company_rating_url"] = normalize.safe_url(job["company_rating_url"])
        job["sources"] = [{**s, "url": normalize.safe_url(s.get("url")), "direct": normalize.safe_url(s.get("direct"))}
                          for s in job["sources"]]
        job.update(
            match_score=score,
            matched_skills=matched,
            missing_skills=[s for s in skills if s not in matched],
            skills_total=len(skills),
        )
        jobs.append(job)
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return {"description": job["description"], "skills_listed": job["skills_listed"]}


class StatusUpdate(BaseModel):
    status: str = Field(max_length=20)


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: int, body: StatusUpdate):
    if body.status not in db.STATUSES:
        raise HTTPException(400, f"Status must be one of: {', '.join(db.STATUSES)}")
    if not db.set_status(job_id, body.status):
        raise HTTPException(404, "Job not found.")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/applicants")
def fetch_job_applicants(job_id: int):
    """Reads the applicant count of a Naukri job (Naukri's search results don't include it). Takes a few seconds."""
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    naukri_url = applicant_update.naukri_url(job)
    if not naukri_url:
        raise HTTPException(400, "Applicant counts are fetched on request only for Naukri jobs.")
    if applicant_update.is_running():
        return {"applicants": job["applicants"], "applicants_text": job["applicants_text"], "applicants_checked": job["applicants_checked"],
                "error": "Update Applicants (Naukri) is running; counts appear on the job cards as they are read"}
    wording, error = naukri.fetch_applicants(naukri_url)
    if error:
        return {"applicants": job["applicants"], "applicants_text": job["applicants_text"],
                "applicants_checked": job["applicants_checked"], "error": error}
    count, text = normalize.applicants(wording)
    checked = datetime.now().isoformat(timespec="minutes")
    db.set_applicants(job_id, count, text, checked)
    return {"applicants": count, "applicants_text": text, "applicants_checked": checked, "error": None}


@app.post("/api/jobs/clear")
def clear_jobs():
    return {"deleted": db.clear_new_jobs()}


# ---------- Update Applicants (Naukri) ----------

@app.post("/api/applicants/update")
def start_applicant_update():
    """Reads applicant counts for Naukri jobs in Jobs and Saved that have none, or one older than a day."""
    if search.status()["running"]:
        raise HTTPException(409, "A search is running. Update applicants after it finishes.")
    if applicant_update.start() is None:
        raise HTTPException(409, "Applicant counts are already being updated.")
    return applicant_update.status()


@app.get("/api/applicants/status")
def applicant_update_status(since: int = Query(0, ge=0)):
    return applicant_update.status(since)


@app.post("/api/applicants/stop")
def stop_applicant_update():
    return {"stopping": applicant_update.stop()}


# ---------- Companies ----------

BOARD_SEARCH_LABELS = {"indeed": "Indeed search", "linkedin": "LinkedIn search", "both": "Indeed + LinkedIn search"}


def _platform_label(platform):
    if platform == "boards":
        return BOARD_SEARCH_LABELS.get(db.get_settings()["company_search_sites"], "Indeed search")
    return ats.PLATFORM_LABELS[platform]


def _company_out(company):
    platform = ats.detect_platform(company.get("feed_url") or company["careers_url"])["platform"]
    return {**company, "careers_url": normalize.safe_url(company["careers_url"]), "enabled": bool(company["enabled"]),
            "platform": platform, "platform_label": _platform_label(platform)}


def _clean_url(url):
    """A careers link typed or imported by the user. Adds https:// if missing; anything but a web address is refused."""
    url = (url or "").strip()
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    safe = normalize.safe_url(url)
    if safe is None:
        raise HTTPException(400, "The careers link must be a normal web address (http:// or https://).")
    return safe


def _check_link(url):
    """For a careers link not on a supported platform, looks inside the page for one. Returns (feed_url, note)."""
    if not url:
        return None, "no careers link, so job sites are searched by company name"
    if ats.detect_platform(url)["platform"] != "boards":
        return None, None
    feed, note = ats.find_platform_in_page(url)
    return (feed, note) if feed else (None, f"{note}, so job sites are searched by company name")


def _import_rows(rows, problems):
    existing = {c["name"].strip().lower() for c in db.list_companies()}
    seen, to_add, skipped_existing, skipped_repeats = set(), [], [], []
    for row in rows:
        key = row["name"].lower()
        if key in existing:
            skipped_existing.append(row["name"])
        elif key in seen:
            skipped_repeats.append(f"row {row['row']}: {row['name']}")
        else:
            seen.add(key)
            to_add.append(row)
    with ThreadPoolExecutor(max_workers=8) as pool:
        checks = list(pool.map(lambda r: _check_link(r["careers_url"]), to_add))
    platforms = collections.Counter()
    for row, (feed, note) in zip(to_add, checks):
        db.add_company(row["name"], row["careers_url"], feed, note)
        platforms[_platform_label(ats.detect_platform(feed or row["careers_url"])["platform"])] += 1
    return {
        "added": len(to_add),
        "platforms": dict(platforms),
        "found_on_page": sum(1 for feed, _ in checks if feed),
        "skipped_existing": skipped_existing,
        "skipped_duplicates": skipped_repeats,
        "problems": problems,
    }


class CompanyIn(BaseModel):
    name: str = Field(max_length=200)
    careers_url: str = Field("", max_length=2048)


class CompanyPatch(BaseModel):
    name: str | None = Field(None, max_length=200)
    careers_url: str | None = Field(None, max_length=2048)
    enabled: bool | None = None


@app.get("/api/companies")
def list_companies():
    return [_company_out(c) for c in db.list_companies()]


@app.post("/api/companies")
def add_company(body: CompanyIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Enter the company name.")
    if any(c["name"].strip().lower() == name.lower() for c in db.list_companies()):
        raise HTTPException(400, f"{name} is already in your list.")
    url = _clean_url(body.careers_url)
    feed, note = _check_link(url)
    company_id = db.add_company(name, url, feed, note)
    return next(_company_out(c) for c in db.list_companies() if c["id"] == company_id)


@app.patch("/api/companies/{company_id}")
def update_company(company_id: int, body: CompanyPatch):
    fields = body.model_dump(exclude_none=True)
    if "enabled" in fields:
        fields["enabled"] = int(fields["enabled"])
    if "name" in fields:
        fields["name"] = fields["name"].strip()
        if not fields["name"]:
            raise HTTPException(400, "Enter the company name.")
    if "careers_url" in fields:
        # A changed link gets the same checks as a new one, and a fresh look for the platform behind it.
        fields["careers_url"] = _clean_url(fields["careers_url"])
        fields["feed_url"], fields["check_note"] = _check_link(fields["careers_url"])
    if not db.update_company(company_id, **fields):
        raise HTTPException(404, "Company not found.")
    return {"ok": True}


@app.delete("/api/companies/{company_id}")
def delete_company(company_id: int):
    if not db.delete_company(company_id):
        raise HTTPException(404, "Company not found.")
    return {"ok": True}


@app.post("/api/companies/import")
async def import_companies(request: Request, filename: str = Query("", max_length=255)):
    """Body is the raw uploaded file (CSV or .xlsx); the file name tells which. Read with a size cap."""
    too_large = HTTPException(413, "The file is larger than 5 MB.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise too_large
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_UPLOAD_BYTES:
            raise too_large
    if not data:
        raise HTTPException(400, "The file is empty.")
    try:
        rows, problems = company_import.parse_companies(filename, bytes(data))
    except company_import.FileProblem as exc:
        raise HTTPException(400, str(exc)) from exc
    if not rows:
        raise HTTPException(400, "No companies found. The file needs a column of company names, with careers links in the next column.")
    if len(rows) > 2000:
        raise HTTPException(400, "The file has more than 2,000 companies. Split it into smaller files.")
    return await run_in_threadpool(_import_rows, rows, problems)


@app.get("/api/companies/template.csv")
def companies_template():
    text = (
        "Company name,Careers link\n"
        "Rubrik,https://boards.greenhouse.io/rubrik\n"
        "NVIDIA,https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite\n"
        "Infosys,\n"
    )
    return Response(text, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="jobhunt-companies-template.csv"'})


@app.post("/api/companies/{company_id}/test")
def test_company(company_id: int):
    company = next((c for c in db.list_companies() if c["id"] == company_id), None)
    if company is None:
        raise HTTPException(404, "Company not found.")
    settings = db.get_settings()
    if company["careers_url"] and not company.get("feed_url"):
        # Look behind the careers page again; the site may have changed since it was added.
        feed, note = _check_link(company["careers_url"])
        if note is not None:
            db.update_company(company_id, feed_url=feed, check_note=note)
            company.update(feed_url=feed, check_note=note)
    out = _company_out(company)
    try:
        raws = search.fetch_company_jobs(company, matching.split_terms(settings["titles"]), settings)
    except Exception as exc:
        return {"count": 0, "error": str(exc), "platform_label": out["platform_label"], "check_note": out["check_note"]}
    return {"count": len(raws), "error": None, "platform_label": out["platform_label"], "check_note": out["check_note"]}


# ---------- Settings ----------

class SettingsIn(BaseModel):
    titles: str | None = Field(None, max_length=2000)
    skills: str | None = Field(None, max_length=4000)
    minutes_old: int | None = Field(None, ge=5, le=30 * 24 * 60)
    sources: list[Literal["linkedin", "indeed", "naukri", "companies"]] | None = Field(None, max_length=4)
    results_wanted: int | None = Field(None, ge=10, le=500)
    request_delay: float | None = Field(None, ge=0, le=10)
    company_search_sites: Literal["indeed", "linkedin", "both"] | None = None
    search_cities: list[CityName] | None = Field(None, max_length=50)


@app.get("/api/settings")
def get_settings():
    return db.get_settings()


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    return db.save_settings(body.model_dump(exclude_none=True))
