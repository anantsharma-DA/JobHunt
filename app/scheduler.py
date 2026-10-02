"""Things JobHunt does on its own while it is running: reminders for your applications, and the daily auto-search.

- Every few minutes it checks for follow-ups and interviews that are due and sends each reminder once.
- At the time you set (on the days you set) it searches your saved job titles, cities and sites for jobs posted in the
  last day, then tells you how many are new and how many are strong matches.
- Optionally, Windows Task Scheduler starts JobHunt at that time (run.bat --auto), so the search happens even when
  JobHunt isn't open. Started that way, JobHunt searches, notifies you, then closes itself.
"""
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from app import applicant_update, db, errors, matching, notify, search, tracker

TASK_NAME = "JobHunt Daily Search"
RUN_BAT = Path(__file__).resolve().parent.parent / "run.bat"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
CHECK_EVERY = 30          # seconds between checks
REMINDERS_EVERY = 300     # seconds between reminder checks
LATE_LIMIT = 60           # minutes after the set time that a missed auto-search still runs (JobHunt was busy/just opened)
SEARCH_TIMEOUT = 45 * 60  # seconds an auto-search may take before JobHunt stops waiting for it

_lock = threading.Lock()
_state = {"running": False, "last_reminders": 0.0}


def start():
    """Starts the background checks (once). Automated tests switch this off with JOBHUNT_SCHEDULER=off."""
    if os.environ.get("JOBHUNT_SCHEDULER") == "off":
        return
    threading.Thread(target=_loop, daemon=True, name="jobhunt-scheduler").start()
    if os.environ.get("JOBHUNT_AUTORUN") == "1":
        threading.Thread(target=_autorun, daemon=True, name="jobhunt-autorun").start()


def _loop():
    while True:
        try:
            now = datetime.now()
            if time.monotonic() - _state["last_reminders"] >= REMINDERS_EVERY:
                _state["last_reminders"] = time.monotonic()
                send_reminders(now)
            # Started by Windows just for the search, _autorun does it (once) and then closes JobHunt.
            if not _autorun_mode() and is_due(db.get_settings(), now):
                run_autosearch()
        except Exception as exc:  # a failed check must never stop the next ones
            errors.hidden(exc, "Background check")
        time.sleep(CHECK_EVERY)


# ---------- Reminders ----------

def send_reminders(now=None):
    """Sends each due reminder once (if notifications are on). Returns the reminders sent."""
    settings = db.get_settings()
    items = tracker.due_items(db.list_jobs(), db.list_applications(), settings["followup_days"], now)
    sent = []
    apps = db.list_applications()
    for item in items:
        if item["key"] in ((apps.get(item["job_id"]) or {}).get("notified") or []):
            continue
        if settings["notify_on"]:
            title = {"followup": "Time to follow up", "no_reply": "Still no reply", "interview": "Interview reminder"}[item["kind"]]
            notify.send(f"JobHunt: {title}", item["text"])
        tracker.mark_notified(item["job_id"], item["key"])  # also when notifications are off, so they don't pile up later
        sent.append(item)
    return sent


# ---------- Daily auto-search ----------

def is_due(settings, now):
    """True when today's auto-search should run now: switched on, a chosen day, the time has come (within the hour),
    and it hasn't run today."""
    if not settings.get("autosearch_on") or DAYS[now.weekday()] not in (settings.get("autosearch_days") or []):
        return False
    if settings.get("autosearch_last") == now.date().isoformat():
        return False
    try:
        hour, minute = (int(x) for x in settings.get("autosearch_time", "09:00").split(":"))
    except ValueError:
        return False
    planned = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return planned <= now <= planned + timedelta(minutes=LATE_LIMIT)


def run_autosearch(wait=True):
    """Searches for jobs posted in the last day with your saved titles, cities and sites, then notifies you.

    Returns what was found, or {"skipped": reason}. Only one runs at a time; it waits for a search you started.
    """
    with _lock:
        if _state["running"]:
            return {"skipped": "an auto-search is already running"}
        _state["running"] = True
    try:
        return _autosearch(wait)
    finally:
        with _lock:
            _state["running"] = False


def _autosearch(wait):
    settings = db.get_settings()
    today = datetime.now().date().isoformat()
    if search.status()["running"] or applicant_update.is_running():
        return {"skipped": "another search or applicant update is running; it will try again shortly"}
    db.save_settings({"autosearch_last": today})
    titles = matching.split_terms(settings["titles"])
    if not titles or not settings["sources"]:
        result = {"at": datetime.now().isoformat(timespec="minutes"), "skipped": "no job titles or sites saved"}
        db.save_settings({"autosearch_result": result})
        if settings["notify_on"]:
            notify.send("JobHunt: daily search skipped", "Pick your job titles and sites on the Jobs tab first.")
        return result
    started = datetime.now().isoformat(timespec="seconds")
    if not search.start({**settings, "minutes_old": 24 * 60}):
        return {"skipped": "a search is already running"}
    if not wait:
        return {"started": started}
    deadline = time.monotonic() + SEARCH_TIMEOUT
    while search.status()["running"] and time.monotonic() < deadline:
        time.sleep(5)
    return summarise(settings, started)


def summarise(settings, started):
    """Counts jobs first seen since `started`, and the strong matches among them, then notifies you."""
    titles, skills = matching.split_terms(settings["titles"]), matching.split_terms(settings["skills"])
    new = [j for j in db.list_jobs() if (j.get("first_seen") or "") >= started and j["status"] == "new"]
    scored = []
    for job in new:
        text = f"{job.get('description') or ''}\n{job.get('skills_listed') or ''}"
        score, _ = matching.score_job(job["title"], text, job["search_titles"] or titles, skills)
        scored.append((score, job))
    strong = sorted([(s, j) for s, j in scored if s >= settings["autosearch_min_match"]], key=lambda sj: -sj[0])
    result = {"at": datetime.now().isoformat(timespec="minutes"), "new": len(new), "strong": len(strong),
              "min_match": settings["autosearch_min_match"],
              "top": [f"{j['title']} at {j['company']} ({s}%)" for s, j in strong[:3]]}
    db.save_settings({"autosearch_result": result})
    if settings["notify_on"]:
        if new:
            text = f"{len(new)} new jobs, {len(strong)} strong matches ({settings['autosearch_min_match']}%+)."
            if strong:
                text += " Top: " + "; ".join(result["top"])
        else:
            text = "No new jobs today for your titles and cities."
        notify.send("JobHunt: daily search done", text, launch=notify.OPEN_APP if not _autorun_mode() else _run_bat_uri())
    return result


def _autorun_mode():
    return os.environ.get("JOBHUNT_AUTORUN") == "1"


def _run_bat_uri():
    """Started by Windows just for the search, JobHunt closes afterwards, so the notification opens run.bat."""
    return RUN_BAT.as_uri()


def _autorun():
    """run.bat --auto: wait for the server, search, notify, then close JobHunt."""
    time.sleep(3)
    try:
        run_autosearch()
    except Exception as exc:
        errors.hidden(exc, "Daily auto-search")
    finally:
        time.sleep(2)
        try:
            if db._conn is not None:
                db._conn.close()
        finally:
            os._exit(0)


# ---------- Windows Task Scheduler ----------

def task_args(time_text, days, bat=RUN_BAT):
    """The schtasks command that starts JobHunt for the daily search: your Windows user, the chosen days and time.

    Given as a list (no shell), after the time and days have been checked, so nothing can be injected.
    """
    hour, minute = (int(x) for x in time_text.split(":"))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("time")
    chosen = [d for d in DAYS if d in days]
    if not chosen:
        raise ValueError("days")
    return ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", f'"{bat}" --auto', "/SC", "WEEKLY",
            "/D", ",".join(d.upper() for d in chosen), "/ST", f"{hour:02d}:{minute:02d}", "/F"]


def _schtasks(args):
    return subprocess.run(args, capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def task_exists():
    if sys.platform != "win32":
        return False
    try:
        return _schtasks(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def set_task(enabled, settings):
    """Creates (or updates) or removes the Windows task. Returns (ok, message)."""
    if sys.platform != "win32":
        return False, "Starting JobHunt automatically needs Windows."
    try:
        if enabled:
            result = _schtasks(task_args(settings["autosearch_time"], settings["autosearch_days"]))
        elif task_exists():
            result = _schtasks(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        else:
            return True, "Windows won't start JobHunt automatically."
    except ValueError:
        return False, "Pick a time and at least one day first."
    except (OSError, subprocess.SubprocessError) as exc:
        errors.hidden(exc, "Windows Task Scheduler")
        return False, "Windows Task Scheduler couldn't be reached."
    if result.returncode != 0:
        errors.log.warning("schtasks failed: %s", result.stderr.decode("utf-8", "replace")[:300])
        return False, "Windows didn't accept the scheduled task. Try again, or leave this switched off."
    if enabled:
        days = ", ".join(d.capitalize() for d in DAYS if d in settings["autosearch_days"])
        return True, f"Windows will start JobHunt at {settings['autosearch_time']} on {days} for the daily search."
    return True, "Windows won't start JobHunt automatically any more."
