"""JobHunt web app: serves the page and the JSON API. Start with run.bat."""
import collections
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import (ai, applicant_update, company_import, db, errors, guard, interview, matching, normalize, resume,
                 resume_pdf, search, secret_store, tailor_run)
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

SECURITY_HEADERS["X-Permitted-Cross-Domain-Policies"] = "none"

db.connect()
# No /docs, /redoc or /openapi.json: the page doesn't need them, and they would list every action the API offers.
app = FastAPI(title="JobHunt", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _refuse(status, message):
    return JSONResponse({"detail": message}, status_code=status, headers=SECURITY_HEADERS)


# ---------- Errors: helpful messages, never internals ----------

@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    """Messages JobHunt wrote (HTTPException) are shown; a 5xx never shows anything but the plain message."""
    detail = exc.detail if exc.status_code < 500 and isinstance(exc.detail, str) else errors.GENERIC
    return JSONResponse({"detail": detail}, status_code=exc.status_code, headers={**SECURITY_HEADERS, **(exc.headers or {})})


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, exc: RequestValidationError):
    """Invalid input is refused with what was wrong, without repeating back what was sent."""
    problems = []
    for error in exc.errors()[:3]:
        where = ".".join(str(part) for part in error.get("loc", ())[1:]) or "request"
        message = ("contains characters that aren't allowed" if error.get("type") == "string_pattern_mismatch"
                   else error.get("msg", "not valid"))
        problems.append(f"{where}: {message}")
    return _refuse(422, "Some of the information sent isn't valid (" + "; ".join(problems) + ").")


@app.exception_handler(guard.TooLarge)
async def too_large(request: Request, exc: guard.TooLarge):
    return _refuse(413, "That is too much data to send at once.")


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    """Anything unexpected: you see only the plain message. (uvicorn prints the full error in the run.bat window.)"""
    return _refuse(500, errors.GENERIC)


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


# Outermost layer: only this computer, size limits, rate limits and a cap on slow jobs (see guard.py).
app.add_middleware(guard.Guard, headers=SECURITY_HEADERS)


@app.get("/")
def index():
    # Version the asset links by file time so every browser fetches the new file after an update.
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for name in ("styles.css", "app.js", "resume.js"):
        version = int((STATIC_DIR / name).stat().st_mtime)
        html = html.replace(f'"/static/{name}"', f'"/static/{name}?v={version}"')
    if db.get_settings()["theme"] == "dark":
        # Set before the page is drawn, so a dark page never flashes white while it loads.
        html = html.replace('<html lang="en">', '<html lang="en" data-theme="dark">', 1)
        html = html.replace('<meta name="color-scheme" content="light">', '<meta name="color-scheme" content="dark">', 1)
    return HTMLResponse(html)


# ---------- Input limits ----------
# Every value from the page is checked here, on the server: its type, length or range, format and allowed values.
# Anything else is refused (422) before the app acts on it, and unknown fields are refused too.

MAX_ID = 2**31 - 1
Id = Annotated[int, PathParam(ge=1, le=MAX_ID)]
# Printable text: tabs and line breaks are fine, other control characters (NUL, escape codes) are not.
_PRINTABLE = r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]*$"


Text60 = Annotated[str, StringConstraints(max_length=60, pattern=_PRINTABLE)]
Text80 = Annotated[str, StringConstraints(max_length=80, pattern=_PRINTABLE)]
Text120 = Annotated[str, StringConstraints(max_length=120, pattern=_PRINTABLE)]
Text200 = Annotated[str, StringConstraints(max_length=200, pattern=_PRINTABLE)]
Text2000 = Annotated[str, StringConstraints(max_length=2000, pattern=_PRINTABLE)]
Text2048 = Annotated[str, StringConstraints(max_length=2048, pattern=_PRINTABLE)]
Text4000 = Annotated[str, StringConstraints(max_length=4000, pattern=_PRINTABLE)]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


# API keys go into request headers, so they may only hold visible characters: no spaces, line breaks or control codes.
ApiKey = Annotated[str, BeforeValidator(_strip), StringConstraints(max_length=300, pattern=r"^[\x21-\x7E]*$")]
Provider = Literal["openrouter", "nvidia", "gemini", "openai", "claude"]
ModelName = Annotated[str, StringConstraints(max_length=140, pattern=r"^[A-Za-z0-9._:/@+\-]*$")]
SourceName = Annotated[str, StringConstraints(max_length=20, pattern=r"^[a-z]*$")]
CityName = Text60
FILE_NAME = r"^[^\x00-\x1F\x7F/\\:*?\"<>|]*$"  # a plain file name: no folders, no characters Windows forbids


class Strict(BaseModel):
    """Refuses fields the page never sends, instead of silently ignoring them."""
    model_config = ConfigDict(extra="forbid")


# ---------- Search ----------

class SearchRequest(Strict):
    titles: Text2000
    skills: Text4000 = ""
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
    tailored = db.tailored_by_job()  # which jobs already have a resume made for them
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
            tailored=tailored.get(job["id"]),
        )
        jobs.append(job)
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: Id):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return {"description": job["description"], "skills_listed": job["skills_listed"]}


class StatusUpdate(Strict):
    status: Literal["new", "saved", "applied", "hidden"]


@app.patch("/api/jobs/{job_id}")
def update_job(job_id: Id, body: StatusUpdate):
    if body.status not in db.STATUSES:
        raise HTTPException(400, f"Status must be one of: {', '.join(db.STATUSES)}")
    if not db.set_status(job_id, body.status):
        raise HTTPException(404, "Job not found.")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/applicants")
def fetch_job_applicants(job_id: Id):
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
def applicant_update_status(since: int = Query(0, ge=0, le=10**9)):
    return applicant_update.status(since)


@app.post("/api/applicants/stop")
def stop_applicant_update():
    return {"stopping": applicant_update.stop()}


# ---------- AI service ----------

class AIStepIn(Strict):
    provider: Provider
    models: list[ModelName] = Field(default_factory=list, max_length=ai.MAX_MODELS)
    enabled: bool = True


class AISettingsIn(Strict):
    """The services in the order they should be tried, plus any keys you just typed."""
    chain: list[AIStepIn] = Field(default_factory=list, max_length=8)
    # One key per service: "" forgets that service's key, and a service left out keeps the key already saved.
    keys: dict[Provider, ApiKey] = Field(default_factory=dict, max_length=5)


def _key_name(provider):
    return f"ai_key_{provider}"


def _ai_chain():
    """Your saved order, plus any service added to JobHunt since you last saved it (such as Claude), at the end."""
    chain = [step for step in db.get_settings()["ai_chain"] if step.get("provider") in ai.PROVIDERS]
    named = {step["provider"] for step in chain}
    return chain + [{"provider": name, "models": [], "enabled": True} for name in ai.PROVIDERS if name not in named]


def _ai_steps():
    """The saved services in your order, each with its key, ready for the AI client."""
    return [{**step, "key": db.get_secret(_key_name(step["provider"]))} for step in _ai_chain()]


def _key_state(name):
    """What the page may know about a key: whether there is one, a masked hint, and where it comes from. Never the key."""
    key, source = db.get_secret(name), db.secret_source(name)
    hint = ai.mask(key)
    if source == "env":
        hint += f" (from the {secret_store.ENV_NAMES[name]} environment variable)"
    return {"has_key": bool(key), "key_hint": hint, "key_source": source}


def _ai_state():
    """What the Settings tab shows. Keys never come back, only a hint that one is saved."""
    described = {p["name"]: p for p in ai.provider_list()}
    chain = []
    for step in _ai_chain():
        name = _key_name(step["provider"])
        chain.append({**described.get(step["provider"], {}), **step, **_key_state(name)})
    return {"chain": chain, "ready": [step["provider"] for step in ai.usable_steps(_ai_steps())]}


@app.get("/api/ai")
def get_ai_settings():
    return _ai_state()


@app.put("/api/ai")
def put_ai_settings(body: AISettingsIn):
    chosen = [step.model_dump() for step in body.chain]
    named = {step["provider"] for step in chosen}
    # Services you didn't send stay in the list, switched off at the end, so their keys and models are not lost.
    chain = chosen + [{"provider": name, "models": [], "enabled": True} for name in ai.PROVIDERS if name not in named]
    db.save_settings({"ai_chain": chain})
    for provider, key in body.keys.items():
        if provider in ai.PROVIDERS:
            db.set_secret(_key_name(provider), key.strip())
    return _ai_state()


@app.get("/api/ai/models")
def list_ai_models(provider: Literal["", "openrouter", "nvidia", "gemini", "openai", "claude"] = Query("")):
    provider = provider or db.get_settings()["ai_chain"][0]["provider"]
    try:
        return {"provider": provider, "models": ai.list_models(provider, db.get_secret(_key_name(provider)))}
    except ai.AIError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/ai/test")
def test_ai():
    try:
        return ai.test_chain(_ai_steps())
    except ai.AIError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------- Your resume details ----------

@app.get("/api/resume")
def get_resume():
    profile = db.get_resume() or resume.empty_profile()
    return {"profile": profile, "usable": resume.profile_is_usable(profile)}


@app.put("/api/resume")
def put_resume(body: dict):
    try:
        profile = db.save_resume(resume.clean_profile(body))
    except resume.ResumeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"profile": profile, "usable": resume.profile_is_usable(profile)}


@app.post("/api/resume/import")
async def import_resume(request: Request, filename: str = Query("", max_length=255, pattern=FILE_NAME)):
    """Body is your existing resume file (PDF/HTML/Markdown/text). The AI fills in the fields; you then check them."""
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > resume.MAX_IMPORT_BYTES:
            raise HTTPException(413, "That file is larger than 5 MB.")
    if not data:
        raise HTTPException(400, "The file is empty.")
    try:
        text = resume.extract_text(filename or "pasted.txt", bytes(data))
        profile, model = await run_in_threadpool(resume.import_from_text, text, _ai_steps())
    except (resume.ResumeError, ai.AIError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"profile": profile, "model": model}


# ---------- Tailoring a resume to one job ----------

class ResumeDraftIn(Strict):
    draft: dict
    accept_flags: bool = False  # you have seen the flagged wording and want it anyway


def _job_or_404(job_id):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return job


@app.get("/api/jobs/{job_id}/tailor")
def saved_tailoring(job_id: Id):
    """What was tailored for this job earlier, so reopening it doesn't spend another AI request."""
    row = db.get_tailored(job_id) or {}
    draft = (row.get("data") or {}).get("draft")
    if not draft:
        return {"draft": None}  # nothing tailored yet; the page then asks the AI
    profile = db.get_resume() or resume.empty_profile()
    keywords = (row["data"].get("keywords")) or resume.job_keywords(_job_or_404(job_id))
    return {"draft": draft, "flags": resume.verify(profile, draft, keywords), "keywords": keywords,
            "ats": row["data"].get("ats") or resume.ats_report(profile, draft, keywords),
            "human": row["data"].get("human") or resume.human_score(draft, []),
            "model": row.get("model"), "created_at": row.get("created_at")}


@app.post("/api/jobs/{job_id}/tailor")
def tailor_for_job(job_id: Id):
    """Asks the AI to fit your resume to this job. Nothing is written to a file yet; you review it first."""
    job = _job_or_404(job_id)
    try:
        result = resume.tailor(job, db.get_resume(), _ai_steps())
    except (resume.ResumeError, ai.AIError) as exc:
        raise HTTPException(400, str(exc)) from exc
    previous = db.get_tailored(job_id) or {}
    db.save_tailored(job_id, {**(previous.get("data") or {}), "draft": result["draft"], "keywords": result["keywords"]},
                     pdf_path=previous.get("pdf_path"), ats_score=previous.get("ats_score"), model=result["model"])
    return result


@app.post("/api/jobs/{job_id}/resume")
def make_resume_pdf(job_id: Id, body: ResumeDraftIn):
    """Checks the approved wording once more, then prints the PDF."""
    job = _job_or_404(job_id)
    profile = db.get_resume()
    if not resume.profile_is_usable(profile):
        raise HTTPException(400, "Fill in the Resume tab first (at least your name and one job or project).")
    try:
        draft = resume.clean_draft(body.draft, profile)
        keywords = resume.job_keywords(job)
        flags = resume.verify(profile, draft, keywords)
        if flags and not body.accept_flags:
            return {"needs_review": True, "flags": flags, "draft": draft}
        made = resume_pdf.write_pdf(profile, draft, job)
    except resume_pdf.TooLong as exc:
        return _shorten_to_one_page(job, profile, draft, keywords, exc.over)
    except resume.ResumeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except resume_pdf.PdfError as exc:
        raise HTTPException(400, str(exc)) from exc
    report = resume.ats_report(profile, draft, keywords, pdf_text=made["text"])
    previous = db.get_tailored(job_id) or {}
    db.save_tailored(job_id, {**(previous.get("data") or {}), "draft": draft, "keywords": keywords, "ats": report},
                     pdf_path=made["path"], ats_score=report["score"], model=previous.get("model"))
    return {"needs_review": False, "file": made["name"], "pages": made["pages"], "layout": made["layout"],
            "links": made["links"], "ats": report}


SHORTEN_TRIES = 2


def _shorten_to_one_page(job, profile, draft, keywords, over):
    """Every tailored resume is one page. When the wording runs over even in the tightest layout, the AI cuts it
    until it fits; nothing is printed yet, so you check the shorter wording before pressing Make PDF again."""
    before = round((over - 1) * 100)
    check, model = {"fits": False, "over": over}, None
    for _ in range(SHORTEN_TRIES):
        try:
            draft, model = resume.shorten(job, profile, draft, keywords, check["over"], _ai_steps())
            check = resume_pdf.fits(profile, draft)
        except (ai.AIError, resume.ResumeError) as exc:
            raise HTTPException(400, f"This resume is about {before}% longer than one page, and the AI couldn't "
                                     f"shorten it: {exc} Remove a few bullets yourself, then press Make PDF.") from exc
        except resume_pdf.PdfError as exc:
            raise HTTPException(400, str(exc)) from exc
        if check["fits"]:
            break
    previous = db.get_tailored(job["id"]) or {}
    db.save_tailored(job["id"], {**(previous.get("data") or {}), "draft": draft, "keywords": keywords},
                     pdf_path=previous.get("pdf_path"), ats_score=previous.get("ats_score"), model=model)
    return {"needs_review": True, "shortened": True, "fits": check["fits"], "was_over": before,
            "still_over": 0 if check["fits"] else round((check["over"] - 1) * 100), "model": model,
            "draft": draft, "flags": resume.verify(profile, draft, keywords),
            "ats": resume.ats_report(profile, draft, keywords)}


def _resume_file(row):
    """The PDF made for a tailored resume, only if it still exists inside the resumes folder."""
    path = Path(row["pdf_path"]) if row.get("pdf_path") else None
    if path is None or not path.is_file() or resume_pdf.RESUME_DIR.resolve() not in path.resolve().parents:
        return None
    return path


@app.get("/api/tailored")
def tailored_resumes():
    """Every resume tailored so far, for the list on the Resume tab."""
    out = []
    for row in db.list_tailored():
        if not row["data"].get("draft") and not row.get("pdf_path"):
            continue  # only a cover note was written for this job
        path = _resume_file(row)
        out.append({"job_id": row["job_id"], "title": row.get("title"), "company": row.get("company"),
                    "job_exists": row.get("title") is not None, "file": path.name if path else None,
                    "ats_score": row.get("ats_score") if path else None, "model": row.get("model"),
                    "created_at": row.get("created_at")})
    return {"resumes": out, "folder": str(resume_pdf.RESUME_DIR)}


@app.delete("/api/jobs/{job_id}/tailored")
def delete_tailored_resume(job_id: Id):
    """Removes a tailored resume: its saved wording, cover note and PDF file (only ever a file in the resumes folder)."""
    run = tailor_run.status()
    if run.get("running") and run.get("job_id") == job_id:
        raise HTTPException(409, "This resume is still being tailored. Press Stop first.")
    row = db.get_tailored(job_id)
    if row is None:
        raise HTTPException(404, "There is no tailored resume for this job.")
    path = _resume_file(row)
    if path is not None:
        try:
            path.unlink()
        except OSError as exc:
            raise HTTPException(409, "The PDF is open in another program. Close it and try again.") from exc
    db.delete_tailored(job_id)
    return {"deleted": True, "file": path.name if path else None}


@app.get("/api/jobs/{job_id}/resume/file")
def download_resume(job_id: Id, download: bool = False):
    path = _resume_file(db.get_tailored(job_id) or {})
    if path is None:
        raise HTTPException(404, "No resume has been made for this job yet.")
    # The page's own policy would stop the browser's PDF viewer, so this file gets its own, narrower one.
    return FileResponse(path, media_type="application/pdf", filename=path.name,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Content-Security-Policy": "default-src 'none'; object-src 'self'; frame-ancestors 'none'"})


@app.post("/api/jobs/{job_id}/cover-note")
def make_cover_note(job_id: Id):
    job = _job_or_404(job_id)
    profile = db.get_resume()
    if not resume.profile_is_usable(profile):
        raise HTTPException(400, "Fill in the Resume tab first (at least your name and one job or project).")
    try:
        result = resume.cover_note(job, profile, _ai_steps())
    except (resume.ResumeError, ai.AIError) as exc:
        raise HTTPException(400, str(exc)) from exc
    previous = db.get_tailored(job_id) or {}
    db.save_tailored(job_id, {**(previous.get("data") or {}), "cover_note": result["note"]},
                     pdf_path=previous.get("pdf_path"), ats_score=previous.get("ats_score"), model=result["model"])
    return result


@app.get("/api/jobs/{job_id}/apply-pack")
def apply_pack(job_id: Id):
    """Everything to have ready before you press Apply: the tailored resume, your standard answers and the note."""
    job = _job_or_404(job_id)
    profile = db.get_resume() or resume.empty_profile()
    row = db.get_tailored(job_id) or {}
    data = row.get("data") or {}
    return {
        "apply_url": normalize.safe_url(job.get("apply_url")) or None, "status": job.get("status"),
        "answers": resume.apply_answers(profile),
        "resume": {"file": Path(row["pdf_path"]).name if row.get("pdf_path") else None,
                   "ats_score": row.get("ats_score"), "created_at": row.get("created_at"),
                   "folder": str(resume_pdf.RESUME_DIR)},
        "cover_note": data.get("cover_note", ""),
        "has_draft": bool(data.get("draft")),
        "profile_ready": resume.profile_is_usable(profile),
    }


# ---------- Tailoring until the score targets are met ----------

class TailorRunIn(Strict):
    check_ceiling: bool = True  # False: you've seen which advert keywords are missing and want to go ahead anyway


@app.post("/api/jobs/{job_id}/tailor-run")
def start_tailor_run(job_id: Id, body: TailorRunIn):
    """Tailors in rounds, in the background, until the ATS and human-sounding targets on the Settings tab are met."""
    job = _job_or_404(job_id)
    settings = db.get_settings()
    targets = {"ats": settings["ats_target"] or 0, "human": settings["human_target"] or 0}
    if tailor_run.is_running():
        raise HTTPException(409, "A resume is already being tailored. Wait for it to finish, or press Stop.")
    try:
        result = tailor_run.start(job, db.get_resume(), _ai_steps(), targets, settings["tailor_rounds"],
                                  body.check_ceiling)
    except (resume.ResumeError, ai.AIError) as exc:
        raise HTTPException(400, str(exc)) from exc
    if result is None:
        raise HTTPException(409, "A resume is already being tailored. Wait for it to finish, or press Stop.")
    return result


@app.get("/api/tailor-run/status")
def tailor_run_status():
    return tailor_run.status()


@app.post("/api/tailor-run/stop")
def stop_tailor_run():
    return {"stopping": tailor_run.stop()}


class SkillsIn(Strict):
    skills: list[Text80] = Field(max_length=40)


@app.post("/api/resume/skills")
def add_resume_skills(body: SkillsIn):
    """Adds skills you confirmed you really have (from an advert's missing keywords) to your resume details."""
    profile = db.get_resume()
    if not profile:
        raise HTTPException(400, "Fill in the Resume tab first.")
    updated, added = resume.add_skills(profile, body.skills)
    db.save_resume(updated)
    return {"added": added}


# ---------- Interview questions from the web ----------

class InterviewIn(Strict):
    title: Text120
    company: Text120 = ""
    refresh: bool = False


class RefreshIn(Strict):
    refresh: bool = False


def _interview(title, company, refresh):
    try:
        return interview.find(title, company, _ai_steps(), db.get_resume(), refresh)
    except interview.SearchError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/interview/search")
def interview_search(body: InterviewIn):
    """Questions for a job title (and company, if given). Saved results come back unless refresh is set."""
    return _interview(body.title, body.company, body.refresh)


@app.post("/api/jobs/{job_id}/interview")
def job_interview(job_id: Id, body: RefreshIn):
    """Questions this job's company asked for this role."""
    job = _job_or_404(job_id)
    return _interview(job["title"], job["company"] or "", body.refresh)


@app.get("/api/interview/saved")
def interview_saved():
    """Every question saved so far: by job title (Interview Questions tab) and by company (Frequently Asked Questions)."""
    return interview.all_saved()


def _interview_settings():
    tavily = _key_state("tavily_key")
    return {"usage": interview.usage(), "tavily_hint": tavily["key_hint"], "has_tavily": tavily["has_key"],
            "has_gemini": bool(db.get_secret(_key_name("gemini")))}


@app.get("/api/interview/settings")
def get_interview_settings():
    return _interview_settings()


class TavilyIn(Strict):
    key: ApiKey  # "" forgets the saved key


@app.put("/api/interview/settings")
def put_interview_settings(body: TavilyIn):
    db.set_secret("tavily_key", body.key.strip())
    return _interview_settings()


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


class CompanyIn(Strict):
    name: Text200
    careers_url: Text2048 = ""


class CompanyPatch(Strict):
    name: Text200 | None = None
    careers_url: Text2048 | None = None
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
def update_company(company_id: Id, body: CompanyPatch):
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
def delete_company(company_id: Id):
    if not db.delete_company(company_id):
        raise HTTPException(404, "Company not found.")
    return {"ok": True}


@app.post("/api/companies/import")
async def import_companies(request: Request, filename: str = Query("", max_length=255, pattern=FILE_NAME)):
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
def test_company(company_id: Id):
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
    except Exception as exc:  # JobHunt's own messages are shown; a library's text only goes to the run.bat window
        error = str(exc) if isinstance(exc, ats.SourceError) else errors.hidden(exc, f"Testing {company['name']}")
        return {"count": 0, "error": error, "platform_label": out["platform_label"], "check_note": out["check_note"]}
    return {"count": len(raws), "error": None, "platform_label": out["platform_label"], "check_note": out["check_note"]}


# ---------- Settings ----------

class SettingsIn(Strict):
    titles: Text2000 | None = None
    skills: Text4000 | None = None
    minutes_old: int | None = Field(None, ge=5, le=30 * 24 * 60)
    sources: list[Literal["linkedin", "indeed", "naukri", "companies"]] | None = Field(None, max_length=4)
    results_wanted: int | None = Field(None, ge=10, le=500)
    request_delay: float | None = Field(None, ge=0, le=10)
    company_search_sites: Literal["indeed", "linkedin", "both"] | None = None
    search_cities: list[CityName] | None = Field(None, max_length=50)
    theme: Literal["light", "dark"] | None = None
    ats_target: int | None = Field(None, ge=0, le=100)  # 0 = no target
    human_target: int | None = Field(None, ge=0, le=100)
    tailor_rounds: int | None = Field(None, ge=1, le=10)


@app.get("/api/settings")
def get_settings():
    return db.get_settings()


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    return db.save_settings(body.model_dump(exclude_none=True))
