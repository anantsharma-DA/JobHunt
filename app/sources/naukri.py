"""Naukri through a real Microsoft Edge window.

Naukri refuses plain requests (reCAPTCHA) and hidden browsers (Access Denied), so the app opens its normal
search pages in Edge, positioned off-screen, and reads the job data those pages load.
"""
import json
import math
import random
import re
import threading
from urllib.parse import parse_qs, quote, urlparse

from app import errors, normalize

PAGE_SIZE = 20
MAX_PAGES_PER_TITLE = 25
EDGE_ARGS = ["--disable-blink-features=AutomationControlled", "--window-position=-2400,-2400", "--window-size=1280,900"]


def _job_age_days(minutes_old):
    """Naukri only offers 1, 3, 7, 15 or 30 days; jobs outside a shorter window are dropped by date later."""
    if not minutes_old:
        return None
    days = math.ceil(minutes_old / 1440)
    return next((d for d in (1, 3, 7, 15, 30) if days <= d), 30)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def search_url(title, page=1, minutes_old=None, place=None):
    """Naukri search page for all of India, one city ({"kind": "city", "name": ...}) or remote jobs ({"kind": "remote"})."""
    kind = (place or {}).get("kind", "india")
    city = place["name"] if kind == "city" else None
    path = f"{_slug(title)}-jobs" + (f"-in-{_slug(city)}" if city else "") + (f"-{page}" if page > 1 else "")
    # The city comes from the "-in-<city>" part of the address. Adding "l=<city>" makes Naukri drop the keyword and
    # date filters on page 2 onwards, so it is left out.
    url = f"https://www.naukri.com/{path}?k={quote(title)}"
    days = _job_age_days(minutes_old)
    if days:
        url += f"&jobAge={days}"
    if kind == "remote":
        url += "&wfhType=2"  # Naukri's "Remote" work mode filter
    return url


def parse_salary(label):
    """'2.5-3 Lacs PA' -> (250000, 300000, 'yearly'). Returns (None, None, None) when not disclosed."""
    label = (label or "").strip()
    m = re.match(r"([\d.,]+)\s*(?:-|to)?\s*([\d.,]+)?\s*(lacs?|lakhs?|lpa|cr|crores?)?", label, re.I)
    if not m or "not disclosed" in label.lower():
        return None, None, None
    unit = (m.group(3) or "").lower()
    mult = 1e7 if unit.startswith("cr") else 1e5 if unit else 1
    lo = normalize.to_float(m.group(1))
    hi = normalize.to_float(m.group(2))
    interval = "monthly" if re.search(r"\b(pm|p\.m\.|per month|month)\b", label, re.I) else "yearly"
    return (lo * mult if lo is not None else None), (hi * mult if hi is not None else None), interval


def _placeholder(job, kind):
    return next((p.get("label") for p in job.get("placeholders") or [] if p.get("type") == kind), None)


def _date_posted(job):
    label = (job.get("footerPlaceholderLabel") or "").lower()
    if re.search(r"just now|few hours|hour", label):
        return normalize.relative_posted("today")
    return normalize.relative_posted(label) or normalize.parse_date(job.get("createdDate"))


def to_raw(job):
    lo, hi, interval = parse_salary(_placeholder(job, "salary"))
    location = _placeholder(job, "location") or "India"
    return {
        "site": "naukri",
        "title": job.get("title"),
        "company": job.get("companyName"),
        "location": location,
        "workplace": location,
        "job_type": job.get("jobType"),
        "description": normalize.strip_html(job.get("jobDescription")),
        "job_url": f"https://www.naukri.com{job['jdURL']}" if job.get("jdURL") else None,
        "apply_url": None,
        "date_posted": _date_posted(job),
        "min_amount": lo,
        "max_amount": hi,
        "currency": "INR",
        "interval": interval,
        "skills": job.get("tagsAndSkills"),
        "experience_text": job.get("experienceText") or _placeholder(job, "experience"),
        # Naukri shows the company's AmbitionBox rating in its search results.
        "company_rating": (job.get("ambitionBoxData") or {}).get("AggregateRating"),
        "company_reviews": (job.get("ambitionBoxData") or {}).get("ReviewsCount"),
        "company_rating_url": (job.get("ambitionBoxData") or {}).get("Url"),
    }


def _load_results(page, url, page_no):
    """Opens one search page. Returns (search JSON, error message)."""
    from playwright.sync_api import Error as PlaywrightError

    captured = {}

    def on_response(resp):
        if "/jobapi/v3/search" not in resp.url or "status" in captured:
            return
        if parse_qs(urlparse(resp.url).query).get("pageNo", ["1"])[0] != str(page_no):
            return  # a response for another page, e.g. Naukri reloading page 1 after an error
        try:
            body = resp.text()
        except Exception:
            return  # body already gone because the page moved on; wait for the next response
        if resp.status == 200:
            try:
                captured["data"] = json.loads(body)
            except ValueError:
                return  # empty or partial body; wait for the next response
        else:
            captured["text"] = body
        captured["status"] = resp.status

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        for _ in range(40):
            if "status" in captured:
                break
            page.wait_for_timeout(500)
        title = page.title()
    except PlaywrightError as exc:
        return None, _load_problem(exc, "page")
    finally:
        page.remove_listener("response", on_response)
    if title.lower().startswith("access denied"):
        return None, "Naukri denied access for now. Try again later"
    if "status" not in captured:
        return None, "Naukri did not return any search results"
    if captured["status"] == 400 and "page number" in captured.get("text", "").lower():
        # Naukri's job total is only an estimate. Asking past its real last page returns
        # 400 "Requested page number doesn't exists", which just means there are no more results.
        return {"jobDetails": [], "noOfJobs": 0}, None
    if captured["status"] != 200:
        return None, f"Naukri search failed (status {captured['status']})"
    return captured["data"], None


def search(titles, minutes_old, results_wanted, on_batch, on_progress, should_stop=lambda: False, places=None):
    """Same contract as boards.search_site: calls on_batch(raw_jobs) per page, returns error messages."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ["Playwright is not installed. Run: .venv\\Scripts\\python -m pip install playwright"]

    errors = []
    pages_per_title = min(MAX_PAGES_PER_TITLE, math.ceil(results_wanted / PAGE_SIZE))
    with sync_playwright() as p:
        on_progress("opening Microsoft Edge…")
        try:
            browser = p.chromium.launch(channel="msedge", headless=False, args=EDGE_ARGS)
        except Exception as exc:
            return [_edge_problem(exc)]
        try:
            page = browser.new_context(locale="en-IN", viewport={"width": 1280, "height": 900}).new_page()
            runs = [(title, place) for title in titles for place in places or [{"kind": "india"}]]
            for i, (title, place) in enumerate(runs, 1):
                where = {"city": f" · {place.get('name')}", "remote": " · Remote"}.get(place["kind"], "")
                for page_no in range(1, pages_per_title + 1):
                    if should_stop():
                        return errors
                    on_progress(f"{title}{where} · page {page_no}/{pages_per_title} (search {i}/{len(runs)})")
                    data, error = _load_results(page, search_url(title, page_no, minutes_old, place), page_no)
                    if error:
                        errors.append(error)
                        break
                    jobs = data.get("jobDetails") or []
                    raws = [{**to_raw(j), "search_title": title} for j in jobs if j.get("title")]
                    if place["kind"] == "remote":
                        for raw in raws:
                            raw["is_remote"] = True  # found with Naukri's own Remote filter
                    on_batch([r for r in raws if normalize.is_recent(r["date_posted"], minutes_old)])
                    if len(jobs) < PAGE_SIZE or page_no * PAGE_SIZE >= (data.get("noOfJobs") or 0):
                        break
                    page.wait_for_timeout(random.randint(1500, 3000))
        finally:
            browser.close()
    return errors


_detail_lock = threading.Lock()  # one Naukri job page at a time


def _find_key(data, key):
    """First value stored under key anywhere inside nested JSON."""
    if isinstance(data, dict):
        if key in data:
            return data[key]
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    for child in children:
        found = _find_key(child, key)
        if found is not None:
            return found
    return None


NOT_NAUKRI = "not a Naukri job link, so it was not opened"
DENIED = "Naukri denied access for now. Try again later"
NO_COUNT = "Naukri doesn't show an applicant count for this job"


def _is_naukri_url(url):
    parts = urlparse(url or "")
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "naukri.com" or host.endswith(".naukri.com"))


def _read_applicants(page, job_url):
    """Loads one job page in an open Edge tab and reads how many people applied.

    Naukri's search results don't include this; the job page's own data does (applyCount).
    Returns (applicant wording or None, error message or None); the error is DENIED or NO_COUNT for those cases.
    """
    from playwright.sync_api import Error as PlaywrightError

    captured = {}

    def on_response(resp):
        if "/jobapi/v4/job/" in resp.url and "data" not in captured:
            try:
                captured["data"] = resp.json()
            except Exception:
                pass

    page.on("response", on_response)
    try:
        page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
        for _ in range(30):
            if "data" in captured:
                break
            page.wait_for_timeout(500)
        if page.title().lower().startswith("access denied"):
            return None, DENIED
        count = _find_key(captured.get("data"), "applyCount")
        if count is not None:
            return f"{count} applicants", None
        m = re.search(r"Applicants?:?\s*([\d,]+\+?)", page.inner_text("body"))
    except PlaywrightError as exc:
        return None, _load_problem(exc, "job page")
    finally:
        page.remove_listener("response", on_response)
    if m:
        return f"Applicants: {m.group(1)}", None
    return None, NO_COUNT


def _load_problem(exc, what):
    """Why a Naukri page failed, in plain words; Playwright's own text (addresses, internals) goes to the log only."""
    if "timeout" in exc.__class__.__name__.lower() or "timeout" in str(exc).lower()[:200]:
        return f"{what} took too long to load; try again later"
    return f"{what} did not load ({errors.hidden(exc, 'Naukri ' + what, short=True)})"


def _edge_problem(exc):
    errors.hidden(exc, "Opening Microsoft Edge")
    return "could not open Microsoft Edge; check that it is installed and up to date"


def _open_page(p):
    """Off-screen Edge window with one tab. Returns (browser, page, error message)."""
    try:
        browser = p.chromium.launch(channel="msedge", headless=False, args=EDGE_ARGS)
    except Exception as exc:
        return None, None, _edge_problem(exc)
    return browser, browser.new_context(locale="en-IN", viewport={"width": 1280, "height": 900}).new_page(), None


def fetch_applicants(job_url):
    """Opens one Naukri job page in off-screen Edge. Returns (applicant wording or None, error message or None)."""
    if not _is_naukri_url(job_url):
        return None, NOT_NAUKRI  # never point the browser anywhere else
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "Playwright is not installed"

    with _detail_lock, sync_playwright() as p:
        browser, page, error = _open_page(p)
        if error:
            return None, error
        try:
            return _read_applicants(page, job_url)
        finally:
            browser.close()


def fetch_applicants_many(jobs, on_result, should_stop=lambda: False):
    """Reads applicant counts for many Naukri jobs, one after another in a single off-screen Edge window.

    jobs: [(job_id, job_url)]. Calls on_result(job_id, wording, error) after each job.
    Returns the error that ended the run early (Edge missing, Naukri denying access), or None.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright is not installed"

    with _detail_lock, sync_playwright() as p:
        browser, page, error = _open_page(p)
        if error:
            return error
        try:
            for i, (job_id, job_url) in enumerate(jobs):
                if should_stop():
                    return None
                if not _is_naukri_url(job_url):
                    on_result(job_id, None, NOT_NAUKRI)
                    continue
                if i:
                    page.wait_for_timeout(random.randint(1000, 2000))  # a short pause between pages, like a person reading
                wording, error = _read_applicants(page, job_url)
                on_result(job_id, wording, error)
                if error == DENIED:
                    return DENIED
        finally:
            browser.close()
    return None
