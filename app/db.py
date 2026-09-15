"""SQLite storage for jobs, statuses, companies and settings."""
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

# JOBHUNT_DB lets a test run use its own database instead of your real results.
DB_PATH = Path(os.environ.get("JOBHUNT_DB") or Path(__file__).resolve().parent.parent / "data" / "jobhunt.db")

DEFAULT_SETTINGS = {
    "titles": "",
    "skills": "",
    "minutes_old": 10080,
    "sources": ["linkedin", "indeed", "naukri", "companies"],
    "search_cities": [],  # empty = all of India; may include "Remote"
    "results_wanted": 100,
    "request_delay": 1.0,
    # Companies without a supported careers link are searched by name on: "indeed", "linkedin" or "both".
    "company_search_sites": "indeed",
}

STATUSES = ("new", "saved", "applied", "hidden")

# Apply button prefers the company's own page, then the job boards.
SITE_PRIORITY = ["company", "naukri", "indeed", "linkedin"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT,
    cities TEXT NOT NULL DEFAULT '[]',
    work_mode TEXT,
    job_types TEXT NOT NULL DEFAULT '[]',
    salary_min REAL,
    salary_max REAL,
    salary_text TEXT,
    exp_min REAL,
    exp_max REAL,
    date_posted TEXT,
    description TEXT,
    skills_listed TEXT,
    sources TEXT NOT NULL DEFAULT '[]',
    search_titles TEXT NOT NULL DEFAULT '[]',
    applicants INTEGER,
    applicants_text TEXT,
    applicants_checked TEXT,
    company_rating REAL,
    company_reviews INTEGER,
    company_rating_url TEXT,
    apply_url TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    careers_url TEXT,
    feed_url TEXT,
    check_note TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_lock = threading.RLock()
_conn = None

_JOB_FIELDS = ["title", "company", "location", "cities", "work_mode", "job_types", "salary_min", "salary_max",
               "salary_text", "exp_min", "exp_max", "date_posted", "description", "skills_listed",
               "applicants", "applicants_text", "applicants_checked",
               "company_rating", "company_reviews", "company_rating_url"]
_JSON_FIELDS = ("cities", "job_types", "sources", "search_titles")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    global _conn
    with _lock:
        if _conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
            # Databases created before the careers-page platform finder lack these columns.
            columns = {r[1] for r in _conn.execute("PRAGMA table_info(companies)")}
            for column in ("feed_url", "check_note"):
                if column not in columns:
                    _conn.execute(f"ALTER TABLE companies ADD COLUMN {column} TEXT")
            # ...and jobs saved before the Job titles filter have no record of the title they were searched for.
            job_columns = {r[1] for r in _conn.execute("PRAGMA table_info(jobs)")}
            if "search_titles" not in job_columns:
                _conn.execute("ALTER TABLE jobs ADD COLUMN search_titles TEXT NOT NULL DEFAULT '[]'")
            # ...nor applicant counts or company ratings.
            for column, kind in (("applicants", "INTEGER"), ("applicants_text", "TEXT"), ("applicants_checked", "TEXT"),
                                 ("company_rating", "REAL"), ("company_reviews", "INTEGER"), ("company_rating_url", "TEXT")):
                if column not in job_columns:
                    _conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {kind}")
            _conn.commit()
        return _conn


def _row_to_job(row):
    job = dict(row)
    for field in _JSON_FIELDS:
        job[field] = json.loads(job[field] or "[]")
    return job


def _apply_url(sources):
    for site in SITE_PRIORITY:
        for src in sources:
            if src["site"] == site and src.get("direct"):
                return src["direct"]
    for site in SITE_PRIORITY:
        for src in sources:
            if src["site"] == site and src.get("url"):
                return src["url"]
    return None


def _merge_titles(old, new):
    """Adds search titles not already recorded (ignoring case), keeping the first spelling seen."""
    merged = list(old)
    for title in new:
        if title.lower() not in {t.lower() for t in merged}:
            merged.append(title)
    return merged


def upsert_job(job):
    """Inserts a job or merges it into the stored copy. Keeps status and first_seen. Returns True if new."""
    conn = connect()
    now = _now()
    with _lock:
        row = conn.execute("SELECT * FROM jobs WHERE dedupe_key = ?", (job["dedupe_key"],)).fetchone()
        if row is None:
            sources = [job["source"]]
            values = {f: job.get(f) for f in _JOB_FIELDS}
            values.update(dedupe_key=job["dedupe_key"], sources=sources, apply_url=_apply_url(sources),
                          search_titles=_merge_titles([], job.get("search_titles") or []), first_seen=now, last_seen=now)
            for field in _JSON_FIELDS:
                values[field] = json.dumps(values[field])
            cols = ", ".join(values)
            conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
            conn.commit()
            return True

        old = _row_to_job(row)
        sources = [s for s in old["sources"] if s["site"] != job["source"]["site"]] + [job["source"]]
        values = {}
        for field in _JOB_FIELDS:
            new_value = job.get(field)
            if field == "description":
                values[field] = new_value if len(new_value or "") > len(old[field] or "") else old[field]
            elif field in ("cities", "job_types"):
                values[field] = new_value if new_value and new_value != ["Not specified"] else old[field]
            elif field == "work_mode":
                values[field] = new_value if new_value != "Not specified" else old[field]
            else:
                values[field] = new_value if new_value is not None else old[field]
        values.update(sources=sources, apply_url=_apply_url(sources), last_seen=now,
                      search_titles=_merge_titles(old["search_titles"], job.get("search_titles") or []))
        for field in _JSON_FIELDS:
            values[field] = json.dumps(values[field])
        assignments = ", ".join(f"{k} = ?" for k in values)
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", [*values.values(), old["id"]])
        conn.commit()
        return False


def list_jobs():
    with _lock:
        rows = connect().execute("SELECT * FROM jobs").fetchall()
    return [_row_to_job(r) for r in rows]


def get_job(job_id):
    with _lock:
        row = connect().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def set_status(job_id, status):
    with _lock:
        cur = connect().execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        connect().commit()
    return cur.rowcount > 0


def set_applicants(job_id, count, text, checked):
    with _lock:
        cur = connect().execute("UPDATE jobs SET applicants = ?, applicants_text = ?, applicants_checked = ? WHERE id = ?",
                                (count, text, checked, job_id))
        connect().commit()
    return cur.rowcount > 0


def clear_new_jobs():
    """Removes results you never acted on. Saved, applied and hidden jobs stay."""
    with _lock:
        cur = connect().execute("DELETE FROM jobs WHERE status = 'new'")
        connect().commit()
    return cur.rowcount


def list_companies():
    with _lock:
        rows = connect().execute("SELECT * FROM companies ORDER BY name COLLATE NOCASE").fetchall()
    return [dict(r) for r in rows]


def add_company(name, careers_url, feed_url=None, check_note=None):
    with _lock:
        cur = connect().execute(
            "INSERT INTO companies (name, careers_url, feed_url, check_note, enabled, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (name, careers_url, feed_url, check_note, _now()))
        connect().commit()
    return cur.lastrowid


def update_company(company_id, **fields):
    allowed = {k: v for k, v in fields.items() if k in ("name", "careers_url", "feed_url", "check_note", "enabled")}
    if not allowed:
        return False
    with _lock:
        cur = connect().execute(f"UPDATE companies SET {', '.join(f'{k} = ?' for k in allowed)} WHERE id = ?",
                                [*allowed.values(), company_id])
        connect().commit()
    return cur.rowcount > 0


def delete_company(company_id):
    with _lock:
        cur = connect().execute("DELETE FROM companies WHERE id = ?", (company_id,))
        connect().commit()
    return cur.rowcount > 0


def get_settings():
    with _lock:
        rows = connect().execute("SELECT key, value FROM settings").fetchall()
    stored = {r["key"]: json.loads(r["value"]) for r in rows}
    if "minutes_old" not in stored and "hours_old" in stored:
        stored["minutes_old"] = stored["hours_old"] * 60  # saved before the minutes slider existed
    settings = dict(DEFAULT_SETTINGS)
    settings.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
    return settings


def save_settings(values):
    with _lock:
        conn = connect()
        for key, value in values.items():
            if key in DEFAULT_SETTINGS:
                conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                             (key, json.dumps(value)))
        conn.commit()
    return get_settings()
