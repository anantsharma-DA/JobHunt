"""LinkedIn and Indeed through JobSpy's site scrapers.

The scrapers are called directly (not via jobspy.scrape_jobs) so results skip JobSpy's pandas step
and each site's log messages can be captured and shown in the app.
"""
import logging
import math
import random
import re
import threading
import time
from datetime import date

import jobspy.indeed as indeed_module
import jobspy.linkedin as linkedin_module
from jobspy.model import Country, ScraperInput, Site

from app import normalize

class _LinkedIn(linkedin_module.LinkedIn):
    """JobSpy reads the posting date only from "job-search-card__listdate". LinkedIn marks listings from the
    last day "job-search-card__listdate--new" instead, which would leave the newest jobs undated."""

    def _process_job(self, job_card, job_id, full_descr):
        post = super()._process_job(job_card, job_id, full_descr)
        if post is not None and post.date_posted is None:
            tag = job_card.find("time", class_="job-search-card__listdate--new")
            if tag is not None and tag.get("datetime"):
                try:
                    post.date_posted = date.fromisoformat(tag["datetime"])
                except ValueError:
                    pass
        return post

    def _get_job_details(self, job_id):
        self._details_job_id = job_id
        return super()._get_job_details(job_id)

    def _parse_job_url_direct(self, soup):
        # JobSpy calls this with the job page it has already downloaded, which also shows the applicant count.
        caption = soup.find(class_=lambda c: c and "num-applicants__caption" in c)
        if caption is not None:
            with _applicants_lock:
                _linkedin_applicants[f"li-{self._details_job_id}"] = caption.get_text(" ", strip=True)
        return super()._parse_job_url_direct(soup)


_linkedin_applicants = {}  # "li-<job id>" -> e.g. "Over 200 applicants"
_applicants_lock = threading.Lock()


def _pop_applicants(post_id):
    with _applicants_lock:
        return _linkedin_applicants.pop(post_id, None)


class _Indeed(indeed_module.Indeed):
    """JobSpy's Indeed scraper sends its requests with HTTPS certificate checks switched off (verify=False), which would
    let anyone on the same network (e.g. public Wi-Fi) tamper with the results. This switches the checks back on."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        send = self.session.request

        def verified(method, url, **options):
            options["verify"] = True
            return send(method, url, **options)

        self.session.request = verified


SCRAPERS = {
    "linkedin": (_LinkedIn, Site.LINKEDIN, linkedin_module.log),
    "indeed": (_Indeed, Site.INDEED, indeed_module.log),
}

INDEED_STATE_CODES = {
    "AP": "Andhra Pradesh", "AS": "Assam", "BR": "Bihar", "CH": "Chandigarh", "CT": "Chhattisgarh", "DL": "Delhi",
    "GA": "Goa", "GJ": "Gujarat", "HR": "Haryana", "HP": "Himachal Pradesh", "JK": "Jammu and Kashmir",
    "JH": "Jharkhand", "KA": "Karnataka", "KL": "Kerala", "MP": "Madhya Pradesh", "MH": "Maharashtra",
    "OR": "Odisha", "OD": "Odisha", "PB": "Punjab", "RJ": "Rajasthan", "TN": "Tamil Nadu", "TS": "Telangana",
    "TG": "Telangana", "UP": "Uttar Pradesh", "UK": "Uttarakhand", "UT": "Uttarakhand", "WB": "West Bengal",
}


class _LogCapture(logging.Handler):
    """Collects a scraper's errors and forwards its page-by-page progress."""

    def __init__(self, on_progress):
        super().__init__(logging.INFO)
        self.on_progress = on_progress
        self.errors = []

    def emit(self, record):
        message = record.getMessage()
        if record.levelno >= logging.ERROR or "status code" in message:
            self.errors.append(message)
        elif message.lower().startswith(("search page", "scraping page")) and self.on_progress:
            # JobSpy's own "page 2 / 1" counter is wrong when fewer results than a page are wanted
            self.on_progress(re.sub(r"(?i)(?:search|scraping) page:?\s*(\d+)\s*/\s*\d+.*", r"page \1", message))


def friendly_error(message):
    text = str(message)
    if "429" in text:
        return "blocked for now (too many requests). Try again in 30–60 minutes"
    if "403" in text:
        return "the site refused the request (403). Try again later"
    return text if len(text) <= 160 else text[:157] + "…"


def run_scraper(site, scraper_input, on_progress=None):
    """Returns (JobPost list, error messages)."""
    scraper_class, _, logger = SCRAPERS[site]
    for handler in logger.handlers:
        if not isinstance(handler, _LogCapture):
            handler.setLevel(logging.WARNING)  # keep the run.bat window readable
    logger.setLevel(logging.INFO)
    capture = _LogCapture(on_progress)
    logger.addHandler(capture)
    try:
        posts = scraper_class().scrape(scraper_input).jobs
    except Exception as exc:  # a scraper failing on one search should not stop the others
        return [], [*capture.errors, f"{exc.__class__.__name__}: {exc}"]
    finally:
        logger.removeHandler(capture)
    return posts, capture.errors


def add_linkedin_details(post):
    """Fills description, job type and the external apply link for a LinkedIn post found without details."""
    scraper = _LinkedIn()
    scraper.scraper_input = ScraperInput(site_type=[Site.LINKEDIN])
    details = scraper._get_job_details(post.id.removeprefix("li-"))
    post.description = details.get("description") or post.description
    post.job_url_direct = details.get("job_url_direct") or post.job_url_direct
    post.job_type = details.get("job_type") or post.job_type
    return post


def post_to_raw(site, post):
    pay = post.compensation
    loc = post.location
    if site == "indeed" and loc and str(loc.country or "").upper() == "IN":
        # Indeed gives codes ("KA, IN") and often no city
        state = INDEED_STATE_CODES.get((loc.state or "").upper(), loc.state)
        location = ", ".join(x for x in (loc.city, state, "India") if x)
    else:
        location = loc.display_location() if loc else ""
        location = re.sub(r"(^|,\s*)IN$", r"\1India", location)
    return {
        "site": site,
        "title": post.title,
        "company": post.company_name,
        "location": location or "India",
        "is_remote": post.is_remote,
        "workplace": post.work_from_home_type,
        "job_type": [jt.value[0] for jt in post.job_type or []],
        "description": post.description,
        "job_url": post.job_url,
        "apply_url": post.job_url_direct,
        "date_posted": post.date_posted,
        "min_amount": pay.min_amount if pay else None,
        "max_amount": pay.max_amount if pay else None,
        "currency": pay.currency if pay else None,
        "interval": pay.interval.value if pay and pay.interval else None,
        "skills": ", ".join(s.strip() for s in post.skills) if post.skills else None,
        "experience_text": post.experience_range,
        "applicants": _pop_applicants(post.id) if site == "linkedin" else None,
    }


LINKEDIN_PAGE = 10  # LinkedIn's guest search returns 10 jobs per request


class _PreciseHours(float):
    """JobSpy only accepts whole hours. LinkedIn multiplies them by 3600 to build its "posted within"
    filter, so this returns whole seconds from that multiplication and windows under an hour work."""

    def __mul__(self, other):
        return int(round(float(self) * other))


def set_posted_within(scraper_input, site, minutes_old):
    if not minutes_old:
        return
    if site == "linkedin":
        scraper_input.hours_old = _PreciseHours(minutes_old / 60)
    else:
        scraper_input.hours_old = max(1, math.ceil(minutes_old / 60))  # Indeed filters by whole hours


def _pause(seconds, should_stop):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not should_stop():
        time.sleep(0.25)


def _runs(site, titles, places):
    """(title, location, remote, label) for every search this site needs.

    places come from search.search_plan: all of India, single cities, and/or remote-only.
    """
    runs = []
    for title in titles:
        for place in places or [{"kind": "india"}]:
            if place["kind"] == "india":
                runs.append((title, "India", False, title))
                if site == "indeed":
                    # Indeed's India search by location can miss jobs listed only as "Remote", so search those separately.
                    runs.append((title, None, True, f"{title} (remote)"))
            elif place["kind"] == "remote":
                runs.append((title, "India" if site == "linkedin" else None, True, f"{title} · Remote"))
            else:
                # LinkedIn understands "Jaipur, Rajasthan, India"; Indeed (already set to India) wants "Jaipur, Rajasthan".
                parts = [place["name"], place.get("state")] + (["India"] if site == "linkedin" else [])
                runs.append((title, ", ".join(p for p in parts if p), False, f"{title} · {place['name']}"))
    return runs


def search_site(site, titles, minutes_old, results_wanted, on_batch, on_progress, should_stop=lambda: False, places=None):
    """Searches one job board for every title and place. Calls on_batch(raw_jobs) after each fetch. Returns errors.

    LinkedIn is fetched one results page per call, so a cancelled search stops within seconds.
    """
    _, site_enum, _ = SCRAPERS[site]
    runs = _runs(site, titles, places)
    chunk = LINKEDIN_PAGE if site == "linkedin" else results_wanted
    pages = math.ceil(results_wanted / chunk)
    errors = []
    for i, (title, location, remote, label) in enumerate(runs, 1):
        for page_no in range(1, pages + 1):
            if should_stop():
                return errors
            offset = (page_no - 1) * chunk
            wanted = min(chunk, results_wanted - offset)
            on_progress(f"{label} · search {i}/{len(runs)}" + (f" · page {page_no}/{pages}" if pages > 1 else ""))
            scraper_input = ScraperInput(
                site_type=[site_enum],
                search_term=title,
                location=location,
                country=Country.INDIA,
                distance=50 if location in (None, "India") else 25,
                is_remote=remote,
                results_wanted=wanted,
                offset=offset,
                linkedin_fetch_description=True,
            )
            if not (remote and site == "indeed"):
                # Indeed ignores the remote filter when a date filter is set, so its remote results are date-filtered below.
                set_posted_within(scraper_input, site, minutes_old)
            progress = None if pages > 1 else (lambda m, label=label: on_progress(f"{label} · {m}"))
            posts, run_errors = run_scraper(site, scraper_input, progress)
            errors += run_errors
            raws = [{**post_to_raw(site, p), "search_title": title} for p in posts]
            if remote:
                # These came from the site's own remote filter; LinkedIn still lists them under a city.
                for raw in raws:
                    raw["is_remote"] = True
            if remote:
                raws = [r for r in raws if normalize.is_recent(r["date_posted"], minutes_old)]
            on_batch(raws)
            if site == "linkedin" and any("429" in e for e in run_errors):
                return errors  # LinkedIn has blocked us; more searches now only extend the block
            if len(posts) < wanted:
                break  # no more results for this title
            if site == "linkedin":
                _pause(random.uniform(2, 4), should_stop)
    return errors
