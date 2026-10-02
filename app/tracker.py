"""Your applications after you press Apply: the stage each one is at on the Applied board, its dates, notes and the
recruiter's details, and the reminders that are due (follow-ups and interviews)."""
from datetime import date, datetime, timedelta

from app import db

STAGES = ("applied", "followed_up", "interview", "offer", "rejected", "no_reply")
LABELS = {"applied": "Applied", "followed_up": "Followed up", "interview": "Interview", "offer": "Offer",
          "rejected": "Rejected", "no_reply": "No reply"}


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _moment(value):
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def _stage_since(app):
    """The day the application reached its current stage."""
    for step in reversed(app.get("history") or []):
        if step.get("stage") == app["stage"]:
            return _day(step.get("on"))
    return _day(app.get("applied_on"))


def view(job, app, followup_days):
    """One application as the page shows it: its stage, dates, and when the next follow-up is due."""
    app = dict(app or {})
    stage = app.get("stage") or "applied"
    applied_on = app.get("applied_on") or (job.get("applied_at") or "")[:10] or None
    out = {"job_id": job["id"], "stage": stage, "applied_on": applied_on, "followup_on": app.get("followup_on"),
           "interview_at": app.get("interview_at"), "notes": app.get("notes") or "", "contact_name": app.get("contact_name") or "",
           "contact_email": app.get("contact_email") or "", "contact_phone": app.get("contact_phone") or "",
           "history": app.get("history") or [], "notified": app.get("notified") or []}
    due = None
    if stage == "applied" and (out["followup_on"] or applied_on):
        due = _day(out["followup_on"]) or _day(applied_on) + timedelta(days=followup_days)
    elif stage == "followed_up":
        since = _stage_since({**out, "stage": stage})
        due = _day(out["followup_on"]) or (since + timedelta(days=followup_days) if since else None)
    out["followup_due"] = due.isoformat() if due else None
    return out


def update(job, changes, followup_days):
    """Saves what you changed on an application. A new stage is recorded with the day it happened."""
    current = db.get_application(job["id"]) or {}
    record = dict(changes)  # a None here means you cleared that date
    stage = record.get("stage")
    if stage and stage not in STAGES:
        raise ValueError("Unknown stage.")
    history = list(current.get("history") or [])
    if not current:
        record.setdefault("applied_on", (job.get("applied_at") or "")[:10] or None)
        history.append({"stage": "applied", "on": record["applied_on"] or date.today().isoformat()})
    if stage and stage != (current.get("stage") or "applied"):
        history.append({"stage": stage, "on": date.today().isoformat()})
        record.setdefault("followup_on", None)  # a new stage starts its own follow-up clock, unless you set a date
    record["history"] = history[-40:]
    return view(job, db.save_application(job["id"], record), followup_days)


def due_items(jobs, apps, followup_days, now=None):
    """Reminders that are due for jobs on the Applied board, newest first. Each has a key, so it's notified once."""
    now = now or datetime.now()
    today = now.date()
    items = []
    for job in jobs:
        if job.get("status") != "applied":
            continue
        app = view(job, apps.get(job["id"]), followup_days)
        name = f"{job['title']} at {job['company']}"
        due = _day(app["followup_due"])
        if due and due <= today:
            if app["stage"] == "applied":
                text = f"Follow up on {name}: you applied {(today - _day(app['applied_on'])).days} days ago." if app["applied_on"] \
                    else f"Follow up on {name}."
                items.append({"job_id": job["id"], "kind": "followup", "key": f"followup:{due}", "due": due.isoformat(), "text": text})
            else:
                items.append({"job_id": job["id"], "kind": "no_reply", "key": f"no_reply:{due}", "due": due.isoformat(),
                              "text": f"No reply yet from {name}. Follow up again, or mark it No reply."})
        interview = _moment(app["interview_at"])
        if interview and app["stage"] in ("applied", "followed_up", "interview") and now <= interview:
            left = interview - now
            when = interview.strftime("%d %b, %I:%M %p").lstrip("0")
            if left <= timedelta(hours=2):
                items.append({"job_id": job["id"], "kind": "interview", "key": f"interview-2h:{app['interview_at']}",
                              "due": app["interview_at"], "text": f"Interview soon: {name}, {when}."})
            elif left <= timedelta(hours=24):
                day = "today" if interview.date() == today else "tomorrow"
                items.append({"job_id": job["id"], "kind": "interview", "key": f"interview-24h:{app['interview_at']}",
                              "due": app["interview_at"], "text": f"Interview {day}: {name}, {when}."})
    items.sort(key=lambda i: i["due"])
    return items


def mark_notified(job_id, key):
    app = db.get_application(job_id) or {}
    notified = (app.get("notified") or [])[-30:] + [key]
    db.save_application(job_id, {"notified": notified})
