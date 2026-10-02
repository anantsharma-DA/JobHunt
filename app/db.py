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
    "resume_design": "modern",  # the look of tailored resume PDFs: "modern", "classic" or "compact"
    # Fewer new questions than this in one search shows "Only found N questions" (0 = no message).
    "faq_min_questions": 10,  # Frequently Asked Questions on a job (company searches)
    "iq_min_questions": 10,   # Interview Questions tab (job-title searches)
    # Warnings on job cards (Settings → Warnings).
    "warn_scam": True,
    "warn_ghost": True,
    "ghost_days": 45,     # open this long (first seen, or first posted) makes a possible ghost job
    "ghost_reposts": 3,   # reposted this many times makes a possible ghost job
    # Applied board reminders and the daily auto-search (Settings → Reminders and daily auto-search).
    "followup_days": 7,           # remind you to follow up this many days after applying (and after following up)
    "notify_on": True,            # Windows notifications for reminders and auto-search results
    "autosearch_on": False,
    "autosearch_time": "09:00",
    "autosearch_days": ["mon", "tue", "wed", "thu", "fri"],
    "autosearch_min_match": 70,   # a new job at or above this match % counts as a strong match
    "autosearch_windows": False,  # Windows Task Scheduler starts JobHunt at that time
    "autosearch_last": "",        # the day the auto-search last ran
    "autosearch_result": {},      # what it found then
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
-- What JobHunt remembers about a role at a company across all searches, kept even when the Jobs tab is cleared, so
-- listings that stay up for months or keep being reposted can be recognised (possible ghost jobs).
CREATE TABLE IF NOT EXISTS job_history (
    key TEXT PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    first_posted TEXT,
    last_posted TEXT,
    repost_count INTEGER NOT NULL DEFAULT 0,
    times_seen INTEGER NOT NULL DEFAULT 1
);
-- Your progress on each job you applied to: its stage on the Applied board, dates, notes and the recruiter's details.
CREATE TABLE IF NOT EXISTS applications (
    job_id INTEGER PRIMARY KEY,
    stage TEXT NOT NULL DEFAULT 'applied',
    applied_on TEXT,
    followup_on TEXT,
    interview_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT '',
    contact_phone TEXT NOT NULL DEFAULT '',
    history TEXT NOT NULL DEFAULT '[]',
    notified TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);
-- Referral request and recruiter note written for a job (Referral button).
CREATE TABLE IF NOT EXISTS outreach (
    job_id INTEGER PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Every typed practice answer to a saved interview question, with the AI's feedback and score.
CREATE TABLE IF NOT EXISTS practice_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    score INTEGER,
    feedback TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS practice_by_scope ON practice_attempts (scope);
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
            if "roles" not in columns:  # the roles you tagged a company with ("Data Analyst"), for filtering
                _conn.execute("ALTER TABLE companies ADD COLUMN roles TEXT NOT NULL DEFAULT '[]'")
            # ...and jobs saved before the Job titles filter have no record of the title they were searched for.
            job_columns = {r[1] for r in _conn.execute("PRAGMA table_info(jobs)")}
            if "search_titles" not in job_columns:
                _conn.execute("ALTER TABLE jobs ADD COLUMN search_titles TEXT NOT NULL DEFAULT '[]'")
            # ...nor applicant counts or company ratings.
            for column, kind in (("applicants", "INTEGER"), ("applicants_text", "TEXT"), ("applicants_checked", "TEXT"),
                                 ("company_rating", "REAL"), ("company_reviews", "INTEGER"), ("company_rating_url", "TEXT")):
                if column not in job_columns:
                    _conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} {kind}")
            # ...nor the day you applied, or an AI scam check.
            for column in ("applied_at", "scam_ai"):
                if column not in job_columns:
                    _conn.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
            # Practice attempts saved before sessions have no session or feedback mode.
            practice_columns = {r[1] for r in _conn.execute("PRAGMA table_info(practice_attempts)")}
            for column in ("session_id", "mode"):
                if column not in practice_columns:
                    _conn.execute(f"ALTER TABLE practice_attempts ADD COLUMN {column} TEXT")
            _conn.commit()
            _seed_history(_conn)
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
            _record_history(conn, job, now)
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
        _record_history(conn, job, now)
        conn.commit()
        return False


REPOST_GAP_DAYS = 7  # a posting date that jumps forward by at least this much is counted as a repost


def _record_history(conn, job, now):
    """Notes one sighting of a role at a company: when it was first seen and posted, and whether it was reposted."""
    from app import job_warnings

    key = job_warnings.history_key(job.get("title"), job.get("company"))
    today, posted = now[:10], job.get("date_posted")
    row = conn.execute("SELECT * FROM job_history WHERE key = ?", (key,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO job_history (key, first_seen, last_seen, first_posted, last_posted) VALUES (?, ?, ?, ?, ?)",
                     (key, today, today, posted, posted))
        return
    reposts, last_posted, first_posted = row["repost_count"], row["last_posted"], row["first_posted"]
    if posted and last_posted and posted > last_posted:
        try:
            gap = (datetime.fromisoformat(posted) - datetime.fromisoformat(last_posted)).days
        except ValueError:
            gap = 0
        if gap >= REPOST_GAP_DAYS:
            reposts += 1
    conn.execute("UPDATE job_history SET last_seen = ?, first_posted = ?, last_posted = ?, repost_count = ?, "
                 "times_seen = times_seen + ? WHERE key = ?",
                 (today, min(x for x in (first_posted, posted) if x) if (first_posted or posted) else None,
                  max(x for x in (last_posted, posted) if x) if (last_posted or posted) else None,
                  reposts, 0 if row["last_seen"] == today else 1, key))


def _seed_history(conn):
    """Starts the history from the jobs already saved, the first time it exists."""
    if conn.execute("SELECT 1 FROM job_history LIMIT 1").fetchone():
        return
    for row in conn.execute("SELECT title, company, date_posted, first_seen FROM jobs").fetchall():
        _record_history(conn, {"title": row["title"], "company": row["company"], "date_posted": row["date_posted"]},
                        (row["first_seen"] or _now())[:19])
    conn.commit()


def job_histories():
    """{history key: what is remembered about that role at that company}."""
    with _lock:
        rows = connect().execute("SELECT * FROM job_history").fetchall()
    return {r["key"]: dict(r) for r in rows}


_APPLICATION_FIELDS = ("stage", "applied_on", "followup_on", "interview_at", "notes", "contact_name", "contact_email",
                       "contact_phone", "history", "notified")


def _application(row):
    return {**dict(row), "history": json.loads(row["history"] or "[]"), "notified": json.loads(row["notified"] or "[]")}


def get_application(job_id):
    with _lock:
        row = connect().execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
    return _application(row) if row else None


def list_applications():
    """{job id: your progress on that application}."""
    with _lock:
        rows = connect().execute("SELECT * FROM applications").fetchall()
    return {r["job_id"]: _application(r) for r in rows}


def save_application(job_id, fields):
    """Creates or updates one application; only the known fields are stored."""
    values = {k: (json.dumps(v) if k in ("history", "notified") else v) for k, v in fields.items() if k in _APPLICATION_FIELDS}
    values["updated_at"] = _now()
    with _lock:
        conn = connect()
        exists = conn.execute("SELECT 1 FROM applications WHERE job_id = ?", (job_id,)).fetchone()
        if exists:
            conn.execute(f"UPDATE applications SET {', '.join(f'{k} = ?' for k in values)} WHERE job_id = ?",
                         [*values.values(), job_id])
        else:
            columns = ["job_id", *values]
            conn.execute(f"INSERT INTO applications ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                         [job_id, *values.values()])
        conn.commit()
    return get_application(job_id)


def set_scam_ai(job_id, data):
    with _lock:
        cur = connect().execute("UPDATE jobs SET scam_ai = ? WHERE id = ?", (json.dumps(data), job_id))
        connect().commit()
    return cur.rowcount > 0


def list_jobs():
    with _lock:
        rows = connect().execute("SELECT * FROM jobs").fetchall()
    return [_row_to_job(r) for r in rows]


def get_job(job_id):
    with _lock:
        row = connect().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def set_status(job_id, status):
    """Moves a job to a tab. The first time it becomes Applied, the day is kept (for "already applied" and statistics)."""
    with _lock:
        cur = connect().execute("UPDATE jobs SET status = ?, applied_at = CASE WHEN ? = 'applied' AND applied_at IS NULL "
                                "THEN ? ELSE applied_at END WHERE id = ?", (status, status, _now(), job_id))
        connect().commit()
    return cur.rowcount > 0


def set_applicants(job_id, count, text, checked):
    with _lock:
        cur = connect().execute("UPDATE jobs SET applicants = ?, applicants_text = ?, applicants_checked = ? WHERE id = ?",
                                (count, text, checked, job_id))
        connect().commit()
    return cur.rowcount > 0


# ---------- Clearing data (Settings → Clear data) ----------

# What can be cleared, each one a checkbox on the Settings tab.
CLEAR_PARTS = ("new", "saved", "applied", "hidden", "history", "resume", "tailored", "companies",
               "qa_titles", "qa_companies", "practice")
_TITLE_SCOPES = "scope LIKE '|%'"      # interview questions saved for a job title (Interview Questions tab)
_COMPANY_SCOPES = "scope NOT LIKE '|%'"  # ...and for a company's job (Frequently Asked Questions)


def _question_count(where):
    rows = connect().execute(f"SELECT data FROM interview_qa WHERE {where}").fetchall()
    return sum(len(json.loads(r["data"]).get("questions") or []) for r in rows), len(rows)


def data_counts():
    """How much each part holds, for the Clear data checkboxes."""
    with _lock:
        conn = connect()
        statuses = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")}
        one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
        titles, title_groups = _question_count(_TITLE_SCOPES)
        companies, company_groups = _question_count(_COMPANY_SCOPES)
        return {
            **{status: statuses.get(status, 0) for status in STATUSES},
            "history": one("SELECT COUNT(*) FROM job_history"),
            "resume": one("SELECT COUNT(*) FROM resume_profile"),
            "tailored": one("SELECT COUNT(*) FROM tailored_resumes"),
            "companies": one("SELECT COUNT(*) FROM companies"),
            "qa_titles": titles, "qa_title_groups": title_groups,
            "qa_companies": companies, "qa_company_groups": company_groups,
            "practice": one("SELECT COUNT(*) FROM practice_attempts"),
        }


def tailored_files(parts):
    """The PDF paths that clearing these parts would remove: every tailored resume, or those of the jobs removed."""
    statuses = [p for p in parts if p in STATUSES]
    with _lock:
        if "tailored" in parts:
            rows = connect().execute("SELECT pdf_path FROM tailored_resumes").fetchall()
        elif statuses:
            rows = connect().execute(
                f"SELECT pdf_path FROM tailored_resumes WHERE job_id IN (SELECT id FROM jobs WHERE status IN "
                f"({', '.join('?' * len(statuses))}))", statuses).fetchall()
        else:
            rows = []
    return [r["pdf_path"] for r in rows if r["pdf_path"]]


def clear_data(parts):
    """Deletes the chosen parts in one go. Removing jobs also removes everything attached to them: their tracker
    details, referral messages and tailored resumes (the PDF files are deleted by the caller). Returns what was
    removed, per part."""
    parts = [p for p in CLEAR_PARTS if p in parts]
    removed = {}
    with _lock:
        conn = connect()
        statuses = [p for p in parts if p in STATUSES]
        if statuses:
            marks = ", ".join("?" * len(statuses))
            ids = [r["id"] for r in conn.execute(f"SELECT id FROM jobs WHERE status IN ({marks})", statuses)]
            for start in range(0, len(ids), 500):  # SQLite limits how many values one statement takes
                chunk = ids[start:start + 500]
                id_marks = ", ".join("?" * len(chunk))
                for table in ("applications", "outreach", "tailored_resumes"):
                    conn.execute(f"DELETE FROM {table} WHERE job_id IN ({id_marks})", chunk)
            for status in statuses:
                removed[status] = conn.execute("DELETE FROM jobs WHERE status = ?", (status,)).rowcount
        simple = {"history": "DELETE FROM job_history", "resume": "DELETE FROM resume_profile",
                  "tailored": "DELETE FROM tailored_resumes", "companies": "DELETE FROM companies",
                  "qa_titles": f"DELETE FROM interview_qa WHERE {_TITLE_SCOPES}",
                  "qa_companies": f"DELETE FROM interview_qa WHERE {_COMPANY_SCOPES}",
                  "practice": "DELETE FROM practice_attempts"}
        for part in parts:
            if part in simple:
                removed[part] = conn.execute(simple[part]).rowcount
        conn.commit()
    return removed


def list_companies():
    with _lock:
        rows = connect().execute("SELECT * FROM companies ORDER BY name COLLATE NOCASE").fetchall()
    return [{**dict(r), "roles": json.loads(r["roles"] or "[]")} for r in rows]


def add_company(name, careers_url, feed_url=None, check_note=None, roles=()):
    with _lock:
        cur = connect().execute(
            "INSERT INTO companies (name, careers_url, feed_url, check_note, enabled, created_at, roles) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)", (name, careers_url, feed_url, check_note, _now(), json.dumps(list(roles))))
        connect().commit()
    return cur.lastrowid


def update_company(company_id, **fields):
    allowed = {k: v for k, v in fields.items() if k in ("name", "careers_url", "feed_url", "check_note", "enabled", "roles")}
    if "roles" in allowed:
        allowed["roles"] = json.dumps(list(allowed["roles"]))
    if not allowed:
        return False
    with _lock:
        cur = connect().execute(f"UPDATE companies SET {', '.join(f'{k} = ?' for k in allowed)} WHERE id = ?",
                                [*allowed.values(), company_id])
        connect().commit()
    return cur.rowcount > 0


def set_companies_enabled(company_ids, enabled):
    """Ticks or unticks "In search" for many companies at once. Returns how many changed."""
    ids = list(company_ids)
    if not ids:
        return 0
    with _lock:
        cur = connect().execute(f"UPDATE companies SET enabled = ? WHERE id IN ({', '.join('?' * len(ids))})",
                                [int(enabled), *ids])
        connect().commit()
    return cur.rowcount


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
        rows = connect().execute("SELECT scope, data, created_at FROM interview_qa").fetchall()
    return [{**json.loads(r["data"]), "saved_at": r["created_at"], "scope": r["scope"]} for r in rows]


def save_interview_qa(scope, data, keep_date=False):
    """`keep_date`: a repair of what is saved, not a new search, so the "last searched" date stays."""
    with _lock:
        conn = connect()
        if keep_date:
            conn.execute("UPDATE interview_qa SET data = ? WHERE scope = ?", (json.dumps(data), scope))
            conn.commit()
            return get_interview_qa(scope)
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


# ---------- Referral messages and interview practice ----------

def get_outreach(job_id):
    with _lock:
        row = connect().execute("SELECT data, created_at FROM outreach WHERE job_id = ?", (job_id,)).fetchone()
    return {**json.loads(row["data"]), "created_at": row["created_at"]} if row else None


def save_outreach(job_id, data):
    with _lock:
        conn = connect()
        conn.execute("INSERT INTO outreach (job_id, data, created_at) VALUES (?, ?, ?) ON CONFLICT(job_id) DO UPDATE "
                     "SET data = excluded.data, created_at = excluded.created_at", (job_id, json.dumps(data), _now()))
        conn.commit()
    return get_outreach(job_id)


def add_practice(scope, question, answer, score, feedback, session_id=None, mode=None):
    with _lock:
        conn = connect()
        cur = conn.execute("INSERT INTO practice_attempts (scope, question, answer, score, feedback, created_at, "
                           "session_id, mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (scope, question, answer, score, json.dumps(feedback), _now(), session_id, mode))
        conn.commit()
    return cur.lastrowid


def list_practice(scope=None):
    """Practice attempts, oldest first: for one set of saved questions, or all of them."""
    query = "SELECT * FROM practice_attempts" + (" WHERE scope = ?" if scope else "") + " ORDER BY id"
    with _lock:
        rows = connect().execute(query, (scope,) if scope else ()).fetchall()
    return [{**dict(r), "feedback": json.loads(r["feedback"] or "{}")} for r in rows]
