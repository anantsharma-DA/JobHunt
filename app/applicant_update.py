"""The "Update Applicants (Naukri)" button: reads applicant counts for many Naukri jobs in the background."""
import copy
import threading
from datetime import datetime, timedelta

from app import db, normalize
from app.sources import naukri

STATUSES = ("new", "saved")  # the Jobs and Saved tabs; applied and hidden jobs are skipped
RECHECK_AFTER = timedelta(days=1)  # counts older than this are read again

_lock = threading.Lock()
_stop = threading.Event()
_status = {"running": False, "stopping": False, "stopped": False, "nothing_to_do": False, "total": 0, "done": 0,
           "updated": 0, "no_count": 0, "failed": 0, "last_failure": None, "error": None, "started_at": None,
           "finished_at": None, "results": []}


def naukri_url(job):
    return next((s["url"] for s in job["sources"] if s["site"] == "naukri" and s.get("url")), None)


def _due(job, now):
    """A Naukri job in Jobs or Saved that has never been checked, or was checked more than a day ago."""
    if job["status"] not in STATUSES or not naukri_url(job):
        return False
    try:
        return not job["applicants_checked"] or datetime.fromisoformat(job["applicants_checked"]) <= now - RECHECK_AFTER
    except ValueError:
        return True


def jobs_to_update(now=None):
    now = now or datetime.now()
    jobs = [j for j in db.list_jobs() if _due(j, now)]
    return sorted(jobs, key=lambda j: j["date_posted"] or "", reverse=True)  # newest jobs first


def status(since=0):
    """Progress, plus the counts read since result number `since` so the page can show them without reloading."""
    with _lock:
        out = copy.deepcopy({k: v for k, v in _status.items() if k != "results"})
        out["results"] = copy.deepcopy(_status["results"][since:])
        out["results_total"] = len(_status["results"])
    return out


def is_running():
    with _lock:
        return _status["running"]


def start():
    """Starts updating in the background. Returns the number of jobs to update, or None if already running."""
    jobs = jobs_to_update()
    now = datetime.now().isoformat(timespec="seconds")
    with _lock:
        if _status["running"]:
            return None
        _stop.clear()
        _status.update(running=bool(jobs), stopping=False, stopped=False, nothing_to_do=not jobs, total=len(jobs), done=0,
                       updated=0, no_count=0, failed=0, last_failure=None, error=None, started_at=now,
                       finished_at=None if jobs else now, results=[])
    if jobs:
        threading.Thread(target=_run, args=(jobs,), daemon=True).start()
    return len(jobs)


def stop():
    """Stops after the job page being read now. Counts already read are kept."""
    with _lock:
        if not _status["running"]:
            return False
        _status["stopping"] = True
    _stop.set()
    return True


def _save_result(job_id, wording, error):
    checked = datetime.now().isoformat(timespec="minutes")
    count, text = normalize.applicants(wording)
    if text:
        db.set_applicants(job_id, count, text, checked)
        result = {"id": job_id, "applicants": count, "applicants_text": text, "applicants_checked": checked}
    elif error == naukri.NO_COUNT:
        job = db.get_job(job_id)
        if job:  # remember it was checked, so pressing the button again soon doesn't re-open it; keep any count it had
            db.set_applicants(job_id, job["applicants"], job["applicants_text"], checked)
        result = None
    else:
        result = None
    with _lock:
        _status["done"] += 1
        if result:
            _status["updated"] += 1
            _status["results"].append(result)
        elif error == naukri.NO_COUNT:
            _status["no_count"] += 1
        else:
            _status["failed"] += 1
            _status["last_failure"] = error


def _run(jobs):
    error = None
    try:
        error = naukri.fetch_applicants_many([(j["id"], naukri_url(j)) for j in jobs], _save_result, should_stop=_stop.is_set)
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"
    finally:
        with _lock:
            _status.update(running=False, stopping=False, stopped=_stop.is_set(), error=error,
                           finished_at=datetime.now().isoformat(timespec="seconds"))
