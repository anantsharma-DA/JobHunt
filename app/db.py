"""SQLite storage for jobs, statuses, companies and settings."""
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app import secret_store

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
    "theme": "light",  # "light" or "dark"; saved here so every browser opens the page in the mode you chose
    # AI services for resume tailoring, tried in this order when one is busy, out of credit or switched off.
    # Each key lives in `secrets` as ai_key_<provider>.
    "ai_chain": [{"provider": name, "models": [], "enabled": True}
                 for name in ("openrouter", "nvidia", "gemini", "openai", "claude")],
    # Tailoring keeps trying (up to tailor_rounds rounds) until the resume reaches these scores. 0 = no target.
    "ats_target": 0,
    "human_target": 0,
    "tailor_rounds": 3,
    # Web searches for interview questions, counted so the free limits are never exceeded.
    "search_usage": {"gemini_day": "", "gemini_count": 0, "tavily_month": "", "tavily_count": 0},
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
-- Kept apart from settings so the API key is never sent back to the page with the ordinary settings.
CREATE TABLE IF NOT EXISTS secrets (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Your resume details, as one JSON record (there is only ever one).
CREATE TABLE IF NOT EXISTS resume_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
-- One tailored resume per job: the approved wording, the PDF made from it and its ATS report.
CREATE TABLE IF NOT EXISTS tailored_resumes (
    job_id INTEGER PRIMARY KEY,
    data TEXT NOT NULL DEFAULT '{}',
    pdf_path TEXT,
    ats_score INTEGER,
    model TEXT,
    created_at TEXT NOT NULL
);
-- Interview questions found on the web, saved per "company|job title" or per job title, so opening them again is free.
CREATE TABLE IF NOT EXISTS interview_qa (
    scope TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
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
            # Deleted or replaced data (an old API key, a removed resume) is overwritten with zeros, not left in the file.
            _conn.execute("PRAGMA secure_delete = ON")
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
            _migrate_ai_chain(_conn)
            _encrypt_old_secrets(_conn)
        return _conn


def _migrate_ai_chain(conn):
    """Moves the first version's single AI service and key onto the per-service list."""
    stored = {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM settings").fetchall()}
    old_provider = stored.get("ai_provider")
    if "ai_chain" in stored or not old_provider:
        return
    order = [old_provider] + [step["provider"] for step in DEFAULT_SETTINGS["ai_chain"] if step["provider"] != old_provider]
    chain = [{"provider": name, "models": stored.get("ai_models") or [] if name == old_provider else [], "enabled": True}
             for name in order]
    conn.execute("INSERT INTO settings (key, value) VALUES ('ai_chain', ?)", (json.dumps(chain),))
    old_key = conn.execute("SELECT value FROM secrets WHERE key = 'ai_key'").fetchone()
    if old_key:
        conn.execute("INSERT INTO secrets (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                     (f"ai_key_{old_provider}", old_key["value"]))
        conn.execute("DELETE FROM secrets WHERE key = 'ai_key'")
    conn.execute("DELETE FROM settings WHERE key IN ('ai_provider', 'ai_models')")
    conn.commit()


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


# ---------- AI keys ----------

def get_secret(name):
    """One API key: from its environment variable if set, otherwise the saved one, decrypted. "" if there is none."""
    env = secret_store.from_env(name)
    if env:
        return env
    with _lock:
        row = connect().execute("SELECT value FROM secrets WHERE key = ?", (name,)).fetchone()
    return secret_store.unprotect(row["value"]) if row else ""


def secret_source(name):
    """Where a key comes from: "env" (environment variable), "saved" (encrypted in this database) or None."""
    if secret_store.from_env(name):
        return "env"
    return "saved" if get_secret(name) else None


def set_secret(name, value):
    """Saves (encrypted) or clears one API key. Kept out of get_settings() so it never reaches the page."""
    stored = secret_store.protect(value) if value else ""
    with _lock:
        conn = connect()
        if stored:
            conn.execute("INSERT INTO secrets (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                         (name, stored))
        else:
            conn.execute("DELETE FROM secrets WHERE key = ?", (name,))
        conn.commit()


def _encrypt_old_secrets(conn):
    """Keys saved before encryption existed are encrypted in place, then the file is rebuilt (VACUUM) so no readable
    copy of them is left in its unused space."""
    if not secret_store.AVAILABLE:
        return
    rows = [r for r in conn.execute("SELECT key, value FROM secrets").fetchall() if not secret_store.is_protected(r["value"])]
    if not rows:
        return
    for row in rows:
        conn.execute("UPDATE secrets SET value = ? WHERE key = ?", (secret_store.protect(row["value"]), row["key"]))
    conn.commit()
    conn.execute("VACUUM")


# ---------- Resume ----------

def get_resume():
    with _lock:
        row = connect().execute("SELECT data, updated_at FROM resume_profile WHERE id = 1").fetchone()
    if row is None:
        return None
    return {**json.loads(row["data"]), "updated_at": row["updated_at"]}


def save_resume(profile):
    data = json.dumps({k: v for k, v in profile.items() if k != "updated_at"})
    with _lock:
        conn = connect()
        conn.execute("INSERT INTO resume_profile (id, data, updated_at) VALUES (1, ?, ?) "
                     "ON CONFLICT(id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at", (data, _now()))
        conn.commit()
    return get_resume()


def get_tailored(job_id):
    with _lock:
        row = connect().execute("SELECT * FROM tailored_resumes WHERE job_id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    return {**dict(row), "data": json.loads(row["data"] or "{}")}


def save_tailored(job_id, data, pdf_path=None, ats_score=None, model=None):
    with _lock:
        conn = connect()
        conn.execute("INSERT INTO tailored_resumes (job_id, data, pdf_path, ats_score, model, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET data = excluded.data, "
                     "pdf_path = excluded.pdf_path, ats_score = excluded.ats_score, model = excluded.model, "
                     "created_at = excluded.created_at",
                     (job_id, json.dumps(data), pdf_path, ats_score, model, _now()))
        conn.commit()
    return get_tailored(job_id)


def get_interview_qa(scope):
    with _lock:
        row = connect().execute("SELECT data, created_at FROM interview_qa WHERE scope = ?", (scope,)).fetchone()
    return {**json.loads(row["data"]), "saved_at": row["created_at"]} if row else None


def list_interview_qa():
    with _lock:
        rows = connect().execute("SELECT data, created_at FROM interview_qa").fetchall()
    return [{**json.loads(r["data"]), "saved_at": r["created_at"]} for r in rows]


def save_interview_qa(scope, data):
    with _lock:
        conn = connect()
        conn.execute("INSERT INTO interview_qa (scope, data, created_at) VALUES (?, ?, ?) ON CONFLICT(scope) DO UPDATE "
                     "SET data = excluded.data, created_at = excluded.created_at", (scope, json.dumps(data), _now()))
        conn.commit()
    return get_interview_qa(scope)


def delete_tailored(job_id):
    with _lock:
        conn = connect()
        conn.execute("DELETE FROM tailored_resumes WHERE job_id = ?", (job_id,))
        conn.commit()


def list_tailored():
    """Every tailored resume, newest first, with its job's title and company (None if the job was since removed)."""
    with _lock:
        rows = connect().execute(
            "SELECT t.job_id, t.pdf_path, t.ats_score, t.model, t.created_at, t.data, j.title, j.company "
            "FROM tailored_resumes t LEFT JOIN jobs j ON j.id = t.job_id ORDER BY t.created_at DESC").fetchall()
    return [{**dict(r), "data": json.loads(r["data"] or "{}")} for r in rows]


def tailored_by_job():
    """{job id: what was made for it}, so the Jobs list can show which jobs already have a tailored resume."""
    with _lock:
        rows = connect().execute("SELECT job_id, pdf_path, ats_score, model, created_at FROM tailored_resumes").fetchall()
    return {r["job_id"]: dict(r) for r in rows}
