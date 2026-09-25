"""Runs one search across the selected sources, one thread per source, and stores the results."""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests

from app import db, errors, matching, normalize
from app.sources import SearchCancelled, ats, boards, company_boards, naukri

_lock = threading.Lock()
_stop = threading.Event()
_status = {"running": False, "cancelling": False, "cancelled": False, "started_at": None, "finished_at": None, "sources": {}}


def status():
    with _lock:
        return copy.deepcopy(_status)


def _update(source, **fields):
    with _lock:
        _status["sources"][source].update(fields)


def _add_counts(source, count, new, skipped=0):
    with _lock:
        entry = _status["sources"][source]
        entry["count"] += count
        entry["new"] += new
        entry["skipped"] = entry.get("skipped", 0) + skipped


COMPANY_SEARCH_SITES = {"indeed": ("indeed",), "linkedin": ("linkedin",), "both": ("indeed", "linkedin")}


def _tag_titles(raw, titles):
    """The searched title(s) a job belongs to, used by the Job titles filter and the match score.

    Board and Naukri results know the title that was searched. Company feeds return every matching job at
    once, so those are tagged with each searched title the job title fully matches.
    """
    if raw.get("search_title"):
        return [raw["search_title"]]
    matched = [t for t in titles if matching.title_score(raw.get("title"), [t]) >= 1.0]
    return matched or titles[:1]


def _save(source, raws, titles, keep=None):
    count = new = skipped = 0
    for raw in raws:
        raw["search_titles"] = _tag_titles(raw, titles)
        job = normalize.build_job(raw)
        if job is None:
            continue
        if keep is not None and not keep(job):
            skipped += 1  # clearly outside the chosen cities
            continue
        count += 1
        new += db.upsert_job(job)
    _add_counts(source, count, new, skipped)


CITY_SEARCH_LIMIT = 3  # up to this many cities are searched one by one; with more, all of India is searched and filtered


def search_plan(settings):
    """Where to search, from the chosen cities (and "Remote").

    No cities: all of India, as before. 1-3 cities: each city separately, plus a remote-only search if Remote is
    ticked. 4 or more: all of India once. Whenever places are chosen, jobs clearly elsewhere are dropped.
    """
    chosen = [c.strip() for c in settings.get("search_cities") or [] if c.strip()]
    remote = any(c.lower() == "remote" for c in chosen)
    cities = list(dict.fromkeys(normalize.canonical_city(c) for c in chosen if c.lower() != "remote"))
    if (not cities and not remote) or len(cities) > CITY_SEARCH_LIMIT:
        places = [{"kind": "india"}]
    else:
        places = [{"kind": "city", "name": c, "state": normalize.CITY_STATES.get(c)} for c in cities]
        if remote:
            places.append({"kind": "remote"})
    return {"places": places, "cities": cities, "remote": remote, "keep": _place_filter(cities, remote)}


def _place_filter(cities, remote):
    """Keeps jobs in the chosen cities, remote jobs if Remote is ticked, and jobs whose listing names no city
    (unless it names a state none of the chosen cities is in). None when no places were chosen."""
    if not cities and not remote:
        return None
    wanted = {c.lower() for c in cities}
    states = [normalize.CITY_STATES.get(c) for c in cities]
    wanted_states = {s.lower() for s in states} if all(states) else None  # None: a typed city's state is unknown

    def keep(job):
        listed = [c for c in job["cities"] if c != "Remote"]
        if any(c.lower() in wanted for c in listed):
            return True
        if job["work_mode"] == "Remote":
            return remote
        if listed or not cities:
            return False  # listed only in other cities, or only Remote was chosen
        found = normalize.find_states(job["location"])
        return not found or wanted_states is None or bool(found & wanted_states)

    return keep


def start(settings):
    """Starts a background search. Returns False if one is already running."""
    with _lock:
        if _status["running"]:
            return False
        _stop.clear()
        _status.update(
            running=True,
            cancelling=False,
            cancelled=False,
            started_at=datetime.now().isoformat(timespec="seconds"),
            finished_at=None,
            sources={s: {"state": "pending", "count": 0, "new": 0, "skipped": 0, "message": ""} for s in settings["sources"]},
        )
    threading.Thread(target=_run, args=(settings,), daemon=True).start()
    return True


def cancel():
    """Asks the running search to stop. Each source stops at its next page; jobs already found are kept."""
    with _lock:
        if not _status["running"]:
            return False
        _status["cancelling"] = True
    _stop.set()
    return True


def _run(settings):
    titles = matching.split_terms(settings["titles"])
    plan = search_plan(settings)
    try:
        with ThreadPoolExecutor(max_workers=len(settings["sources"])) as pool:
            for source in settings["sources"]:
                pool.submit(_run_source, source, titles, settings, plan)
    finally:
        with _lock:
            _status.update(
                running=False,
                cancelling=False,
                cancelled=_stop.is_set(),
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )


def _run_source(source, titles, settings, plan):
    if _stop.is_set():
        _update(source, state="cancelled", message="not started")
        return
    _update(source, state="running", message="starting…")
    try:
        if source == "companies":
            _run_companies(titles, settings, plan)
            return
        if source == "naukri":
            searcher = naukri.search
        else:
            def searcher(*args, **kwargs):
                return boards.search_site(source, *args, **kwargs)
        errors = searcher(
            titles, settings["minutes_old"], settings["results_wanted"],
            on_batch=lambda raws: _save(source, raws, titles, plan["keep"]),
            on_progress=lambda message: _update(source, message=message),
            should_stop=_stop.is_set,
            places=plan["places"],
        )
        found = status()["sources"][source]["count"]
        if _stop.is_set():
            _update(source, state="cancelled", message="")
        elif errors and not found:
            _update(source, state="error", message=boards.friendly_error(errors[-1]))
        else:
            _update(source, state="done", message=f"some searches failed: {boards.friendly_error(errors[-1])}" if errors else "")
    except SearchCancelled:
        _update(source, state="cancelled", message="")
    except Exception as exc:
        _update(source, state="error", message=boards.friendly_error(f"{exc.__class__.__name__}: {exc}"))


def fetch_company_jobs(company, titles, settings, should_stop=lambda: False):
    """Raw jobs for one company from its hiring platform, or an Indeed + LinkedIn search when the platform is not supported."""
    link = company.get("feed_url") or company["careers_url"]  # feed_url: platform found behind a custom careers page
    if ats.detect_platform(link)["platform"] == "boards":
        sites = COMPANY_SEARCH_SITES.get(settings.get("company_search_sites"), ("indeed",))
        raws, errors = company_boards.search_company(company["name"], titles, settings["minutes_old"], should_stop, sites)
        if errors and not raws:
            raise ats.SourceError(boards.friendly_error(errors[-1]))
        return raws
    return ats.fetch_company(company["name"], link, titles, settings["minutes_old"], settings["request_delay"], should_stop)


def _run_companies(titles, settings, plan):
    companies = [c for c in db.list_companies() if c["enabled"]]
    if not companies:
        _update("companies", state="done", message="no companies added yet (Companies tab)")
        return
    failed = []
    for i, company in enumerate(companies, 1):
        if _stop.is_set():
            _update("companies", state="cancelled", message=f"stopped after {i - 1} of {len(companies)} companies")
            return
        _update("companies", message=f"{company['name']} ({i}/{len(companies)})")
        try:
            _save("companies", fetch_company_jobs(company, titles, settings, _stop.is_set), titles, plan["keep"])
        except SearchCancelled:
            _update("companies", state="cancelled", message=f"stopped during {company['name']}")
            return
        except ats.SourceError as exc:  # written by JobHunt, safe to show
            failed.append(f"{company['name']}: {exc}")
        except requests.RequestException as exc:
            failed.append(f"{company['name']}: {errors.network(exc, company['name'])}")
        except Exception as exc:
            failed.append(f"{company['name']}: {errors.hidden(exc, company['name'], short=True)}")
    message = f"{len(companies)} companies"
    if failed:
        message += f", {len(failed)} failed: " + "; ".join(failed[:3]) + ("…" if len(failed) > 3 else "")
    _update("companies", state="done", message=message)
