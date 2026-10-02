"""Your resume details, importing an old resume, and tailoring it to one job.

The AI may only choose, reorder and rephrase what you typed. Everything it writes is checked back against your own
details here, and anything new is flagged so you can accept or drop it before it reaches the PDF.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

from app import ai, matching, normalize

CATALOG_PATH = Path(__file__).resolve().parent.parent / "static" / "job_catalog.json"
MAX_IMPORT_BYTES = 5 * 1024 * 1024  # a saved HTML resume carries its pictures inside it, so it can be a few MB
MAX_PROFILE_BYTES = 200 * 1024

# Words that mean nothing on their own, so they are never treated as a skill or a claim.
COMMON_WORDS = set("""a an and the of for to in on at by with from as is are was were be been being this that these those
it its into over under across per via using use used work worked working team teams role roles job jobs company companies
new more most other others than then so such very also may can will would should could my our your their his her they we
i you he she who which what when where why how all any both each few own same not no nor only just about after before
during while between through against above below up down out off again further once here there years year month months
experience skills project projects client clients customer customers business data report reports reporting process
processes manage managed management support supported supporting develop developed developing build built building
create created creating improve improved improving increase increased reduce reduced deliver delivered lead led
ensure ensured provide provided maintain maintained analyse analysed analyze analyzed prepare prepared daily weekly
monthly quarterly annual india remote hybrid onsite full time part contract intern internship""".split())

SECTION_LIMITS = {"links": 12, "skills": 12, "skill_items": 40, "experience": 20, "bullets": 25,
                  "projects": 20, "education": 10, "certifications": 25, "positions": 8}


class ResumeError(Exception):
    """Something to show the user, already worded for them."""


# ---------- The profile you type in ----------

def empty_profile():
    return {
        "contact": {"name": "", "title": "", "email": "", "phone": "", "location": ""},
        "links": [],
        "summary": "",
        "skills": [],
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "answers": {"notice_period": "", "current_ctc": "", "expected_ctc": "", "total_experience": "",
                    "preferred_locations": ""},
    }


_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _text(value, limit=300):
    """One line of text: invisible control characters removed, spaces tidied, cut to the limit."""
    return " ".join(_CONTROL.sub("", str(value or "")).split())[:limit]


def _lines(value, limit, item_limit=500):
    """A list of short texts, however the AI or the form sent them."""
    if isinstance(value, str):
        value = [line for line in value.splitlines()]
    if not isinstance(value, list):
        return []
    out = [_text(item, item_limit) for item in value if isinstance(item, (str, int, float))]
    return [item for item in out if item][:limit]


def _entries(value, fields, limit, bullet_field="bullets"):
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        entry = {field: _text(item.get(field), 200) for field in fields}
        if bullet_field:
            entry[bullet_field] = _lines(item.get(bullet_field), SECTION_LIMITS["bullets"])
        if any(entry.get(field) for field in fields):
            out.append(entry)
    return out


EXPERIENCE_FIELDS = ("company", "role", "start", "end", "location")
# "Title (Jul 2025 – Present)" inside a role line that lists several promotions, separated by ";".
_ROLE_WITH_DATES = re.compile(r"^\s*(?P<title>.+?)\s*\((?P<start>[^()]+?)\s*[–—-]\s*(?P<end>[^()]+?)\)\s*$")


def split_roles(role):
    """Promotions typed into one role line ("A (Jun 2025 – Present); B (Jun 2024 – May 2025)") as separate positions,
    newest first as written. Parts without dates (for example a line cut off when it was saved) are left out."""
    parts = [part for part in str(role or "").split(";") if part.strip()]
    found = [m for m in (_ROLE_WITH_DATES.match(part) for part in parts) if m]
    return [{"title": _text(m["title"], 150), "start": _text(m["start"], 40), "end": _text(m["end"], 40)}
            for m in found]


def _positions(value):
    """The titles held at one company (promotions), newest first, each with its own dates."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:50]:
        if isinstance(item, dict) and _text(item.get("title"), 150):
            out.append({"title": _text(item.get("title"), 150), "start": _text(item.get("start"), 40),
                        "end": _text(item.get("end"), 40)})
    return out[:SECTION_LIMITS["positions"]]


def _experience(value):
    """Jobs, each with its facts, bullet points and (for promotions) the positions held there."""
    if not isinstance(value, list):
        return []
    out = []
    for item in value[:SECTION_LIMITS["experience"]]:
        if not isinstance(item, dict):
            continue
        entry = {field: _text(item.get(field), 200) for field in EXPERIENCE_FIELDS}
        entry["bullets"] = _lines(item.get("bullets"), SECTION_LIMITS["bullets"])
        entry["positions"] = _positions(item.get("positions"))
        if not entry["positions"]:
            parsed = split_roles(item.get("role"))
            if len(parsed) >= 2:  # several promotions typed into one line: give each its own line
                entry["positions"], entry["role"] = parsed, parsed[0]["title"]
        if entry["positions"] and not entry["role"]:
            entry["role"] = entry["positions"][0]["title"]
        if any(entry[field] for field in EXPERIENCE_FIELDS) or entry["positions"]:
            out.append(entry)
    return out


def clean_profile(raw):
    """Whatever arrives (typed in, or built by the AI from an old resume) becomes a safe, size-limited profile."""
    if not isinstance(raw, dict):
        raise ResumeError("The resume details could not be read.")
    if len(json.dumps(raw)) > MAX_PROFILE_BYTES:
        raise ResumeError("These resume details are too large. Shorten the longest sections and save again.")
    profile = empty_profile()
    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    profile["contact"] = {field: _text(contact.get(field), 150) for field in profile["contact"]}
    profile["summary"] = _text(raw.get("summary"), 2000)

    links = raw.get("links") if isinstance(raw.get("links"), list) else []
    for link in links[:SECTION_LIMITS["links"]]:
        if not isinstance(link, dict):
            continue
        url = normalize.safe_url(link.get("url"))
        if url:  # a resume link that isn't a normal web address would be dead in the PDF anyway
            profile["links"].append({"label": _text(link.get("label"), 60) or url, "url": url})

    skills = raw.get("skills") if isinstance(raw.get("skills"), list) else []
    for group in skills[:SECTION_LIMITS["skills"]]:
        if isinstance(group, str):
            group = {"group": "Skills", "items": [group]}
        if not isinstance(group, dict):
            continue
        items = _lines(group.get("items"), SECTION_LIMITS["skill_items"], 80)
        if items:
            profile["skills"].append({"group": _text(group.get("group"), 60) or "Skills", "items": items})

    profile["experience"] = _experience(raw.get("experience"))
    profile["projects"] = _entries(raw.get("projects"), ("name", "link"), SECTION_LIMITS["projects"])
    for project in profile["projects"]:
        project["link"] = normalize.safe_url(project["link"]) or ""
    profile["education"] = _entries(raw.get("education"), ("school", "degree", "year", "details"),
                                    SECTION_LIMITS["education"], bullet_field=None)
    profile["certifications"] = _entries(raw.get("certifications"), ("name", "issuer", "year"),
                                         SECTION_LIMITS["certifications"], bullet_field=None)
    answers = raw.get("answers") if isinstance(raw.get("answers"), dict) else {}
    profile["answers"] = {field: _text(answers.get(field), 150) for field in profile["answers"]}
    return profile


def profile_is_usable(profile):
    """Enough to tailor with: a name and at least one job or project with something written under it."""
    if not profile:
        return False
    has_history = any(e.get("bullets") for e in profile.get("experience", []) + profile.get("projects", []))
    return bool(profile.get("contact", {}).get("name")) and (has_history or bool(profile.get("summary")))


# ---------- Importing an old resume ----------

# File signatures ("magic bytes"): what a file really is, whatever its name says.
_SIGNATURES = ((b"%PDF-", "a PDF"), (b"PK\x03\x04", "a Word or zip file"), (b"\xd0\xcf\x11\xe0", "an old Office file"),
               (b"MZ", "a program"), (b"\x7fELF", "a program"), (b"\x89PNG", "a picture"), (b"\xff\xd8\xff", "a picture"),
               (b"GIF8", "a picture"), (b"Rar!", "an archive"), (b"7z\xbc\xaf", "an archive"))


def _really_is(data):
    head = data[:8]
    return next((kind for magic, kind in _SIGNATURES if head.startswith(magic)), None)


def extract_text(filename, data):
    """Plain text out of a resume file you already have (PDF, HTML, Markdown or text).

    The file is untrusted: it is only read in memory (never saved, opened or run), its content must match its name
    (a real PDF, or real text), and only its text is kept.
    """
    if len(data) > MAX_IMPORT_BYTES:
        raise ResumeError("That file is larger than 5 MB.")
    name = (filename or "").lower()
    kind = _really_is(data)
    if name.endswith(".pdf") and b"%PDF-" not in data[:1024]:
        raise ResumeError("That file is named .pdf but isn't a PDF. Upload the real PDF, or paste your resume text.")
    if not name.endswith(".pdf") and (kind or b"\x00" in data[:65536]):
        raise ResumeError(f"That file is {kind or 'not plain text'}, not a text, Markdown or HTML file. Upload a PDF, "
                          "HTML, Markdown or text file, or paste your resume text.")
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ResumeError("PDF support isn't installed. Close JobHunt and double-click run.bat.") from exc
        import io

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ResumeError("That PDF is password-protected. Save an unprotected copy and try again.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:10])
        except ResumeError:
            raise
        except Exception as exc:
            raise ResumeError("That PDF could not be read. Try the Word, HTML or text version.") from exc
        if len(text.split()) < 40:
            raise ResumeError("That PDF seems to be a scan (no text inside). Paste your resume text instead.")
        return text
    for suffix, is_html in ((".html", True), (".htm", True), (".md", False), (".txt", False), (".markdown", False)):
        if name.endswith(suffix):
            try:
                raw = data.decode("utf-8")
            except UnicodeDecodeError:
                raw = data.decode("cp1252", errors="replace")
            if is_html:
                # A resume saved as HTML carries styling, scripts, pictures and fonts inside it. None of that is
                # resume text, and it would otherwise drown the real content.
                raw = re.sub(r"(?is)<(script|style|svg|head|noscript)[^>]*>.*?</\1\s*>", " ", raw)
                raw = re.sub(r"data:[^\"')\s]{100,}", "", raw)
                raw = normalize.strip_html(raw) or ""
            if len(raw.split()) < 40:
                raise ResumeError("There is almost no text in that file; it may be a picture, or a page that draws "
                                  "itself with scripts. Use the PDF version, or paste your resume text instead.")
            return raw
    raise ResumeError("Upload a PDF, HTML, Markdown or text file, or paste your resume text.")


IMPORT_RULES = """You convert a resume into JSON. Copy the facts exactly as written; never invent, guess or improve
anything. If something is missing, leave it empty. Keep dates exactly as the resume writes them.
If the person held several titles at one company (promotions), list each in "positions", newest first, with its own
dates; put the latest title in "role" and the whole time at the company in "start" and "end". With one title, leave
"positions" empty.

Answer with only this JSON:
{"contact": {"name": "", "title": "", "email": "", "phone": "", "location": ""},
 "links": [{"label": "", "url": ""}],
 "summary": "",
 "skills": [{"group": "", "items": [""]}],
 "experience": [{"company": "", "role": "", "start": "", "end": "", "location": "", "bullets": [""],
                 "positions": [{"title": "", "start": "", "end": ""}]}],
 "projects": [{"name": "", "link": "", "bullets": [""]}],
 "education": [{"school": "", "degree": "", "year": "", "details": ""}],
 "certifications": [{"name": "", "issuer": "", "year": ""}]}"""


def import_from_text(text, steps):
    """Turns resume text into profile fields with the AI. You check and correct the result afterwards."""
    text = (text or "").strip()
    if len(text.split()) < 40:
        raise ResumeError("There isn't enough text to read a resume from. Paste the whole resume.")
    messages = [{"role": "system", "content": IMPORT_RULES},
                {"role": "user", "content": f"Resume text:\n\n{text[:20000]}"}]
    data, model = ai.chat_json(messages, steps, temperature=0, schema=IMPORT_SCHEMA)
    return clean_profile(data), model


# ---------- What the job is asking for ----------

@lru_cache(maxsize=1)
def catalog_skills():
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    skills = {skill for category in catalog.get("categories", []) for title in category.get("titles", [])
              for skill in title.get("skills", [])}
    return tuple(sorted(skills, key=len, reverse=True))


_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,29}")
_NUMBER = re.compile(r"\d[\d,.]*%?")
# "We are hiring a Data Analyst" doesn't make Hiring a skill the job wants.
_BOILERPLATE = re.compile(r"(?i)\b(?:we\s+are|we're|is|are|now|currently)\s+hiring\b|\bhiring\s+(?:a|an|for|now)\b")


def job_keywords(job, limit=25):
    """What this job asks for, most important first: known skills it names, then its own repeated terms."""
    text = "\n".join(str(job.get(field) or "") for field in ("title", "description", "skills_listed"))
    text = _BOILERPLATE.sub(" ", text)
    found = matching.find_terms(text, catalog_skills())
    keywords = list(dict.fromkeys(found))
    counts = {}
    for word in _WORD.findall(text):
        if word.isupper() and 2 <= len(word) <= 6 or (word[:1].isupper() and word.lower() not in COMMON_WORDS):
            if word.lower() not in COMMON_WORDS and not any(matching.mentions(k, word) for k in keywords):
                counts[word] = counts.get(word, 0) + 1
    extra = [word for word, count in sorted(counts.items(), key=lambda kv: -kv[1]) if count >= 3]
    return (keywords + extra)[:limit]


# ---------- Tailoring ----------

TAILOR_RULES = """You tailor one person's resume to one job advert. You may only reuse what the resume already says.

Rules you must follow:
1. Never invent employers, job titles, dates, numbers, percentages, tools, skills or certificates.
2. Never add a skill just because the job asks for it. If it is not in the resume, leave it out.
3. Keep every company name and role exactly as the resume writes them, and keep their order.
4. You may drop bullets that don't matter for this job, reorder them, and rewrite the wording of a bullet so it uses
   the job advert's own words for things the person has actually done.
5. Keep bullets short (one line each, at most about 28 words) and start them with what the person did.
6. Put the strongest matching skills first, but only skills already in the resume.
7. The resume MUST fit on ONE A4 page: about 450-550 words in total across summary, skills and bullets. Usually that
   is 4-5 bullets for the latest job, 2-3 for older ones and at most 2 projects with 1-2 bullets each. Leave out
   what matters least for this job rather than going over.

Answer with only this JSON:
{"summary": "2-3 sentences, first person implied, no 'I'",
 "skills": [{"group": "", "items": [""]}],
 "experience": [{"company": "", "role": "", "bullets": [""]}],
 "projects": [{"name": "", "bullets": [""]}],
 "left_out": ["short reason for anything from the resume you did not use"]}"""


def _job_brief(job, keywords):
    parts = [f"Job title: {job.get('title')}", f"Company: {job.get('company')}",
             f"Location: {job.get('location') or 'India'}"]
    if keywords:
        parts.append("Important words from this advert: " + ", ".join(keywords))
    description = (job.get("description") or "").strip()
    parts.append("Job description:\n" + (description[:8000] if description else "(the site gave no description)"))
    return "\n".join(parts)


RESTORED_BULLETS = 2


def clean_draft(draft, profile):
    """Keeps the AI's wording but the profile's facts: companies, roles, dates and links always come from you."""
    if not isinstance(draft, dict):
        raise ResumeError("The AI did not send a usable resume. Try another model.")
    by_company = {e["company"].lower(): e for e in profile["experience"] if e.get("company")}
    by_project = {p["name"].lower(): p for p in profile["projects"] if p.get("name")}
    out = {"summary": _text(draft.get("summary"), 900), "skills": [], "experience": [], "projects": [],
           "left_out": _lines(draft.get("left_out"), 10, 200), "unknown_entries": []}

    for group in (draft.get("skills") if isinstance(draft.get("skills"), list) else [])[:SECTION_LIMITS["skills"]]:
        if not isinstance(group, dict):
            continue
        items = _lines(group.get("items"), SECTION_LIMITS["skill_items"], 80)
        if items:
            out["skills"].append({"group": _text(group.get("group"), 60) or "Skills", "items": items})

    for entry in (draft.get("experience") if isinstance(draft.get("experience"), list) else []):
        if not isinstance(entry, dict):
            continue
        original = by_company.get(_text(entry.get("company"), 200).lower())
        if original is None:
            out["unknown_entries"].append(_text(entry.get("company"), 120))
            continue  # an employer that isn't in your details never reaches the resume
        out["experience"].append({**original, "bullets": _lines(entry.get("bullets"), SECTION_LIMITS["bullets"])})

    for entry in (draft.get("projects") if isinstance(draft.get("projects"), list) else []):
        if not isinstance(entry, dict):
            continue
        original = by_project.get(_text(entry.get("name"), 200).lower())
        if original is None:
            out["unknown_entries"].append(_text(entry.get("name"), 120))
            continue
        out["projects"].append({**original, "bullets": _lines(entry.get("bullets"), SECTION_LIMITS["bullets"])})

    # A job you held is never silently dropped (a gap would raise questions); it stays with its first bullets only,
    # so the resume still fits on one page.
    for entry in profile["experience"]:
        if entry.get("company") and not any(e["company"] == entry["company"] for e in out["experience"]):
            out["experience"].append({**entry, "bullets": list(entry.get("bullets") or [])[:RESTORED_BULLETS]})
    out["experience"].sort(key=lambda e: [x.get("company") for x in profile["experience"]].index(e.get("company"))
                           if e.get("company") in [x.get("company") for x in profile["experience"]] else 99)
    return out


# ---------- Checking the AI didn't make anything up ----------

def profile_text(profile):
    return json.dumps(profile, ensure_ascii=False)


def _vocabulary(text):
    words = {word.lower().rstrip(".-/") for word in _WORD.findall(text)}
    return words | {n.replace(",", "") for n in _NUMBER.findall(text)}


def draft_text(draft, profile):
    """Everything the finished resume would say, as plain text."""
    parts = [profile["contact"].get(f, "") for f in ("name", "title", "email", "phone", "location")]
    parts += [link.get("label", "") for link in profile.get("links", [])]
    parts.append(draft.get("summary", ""))
    for group in draft.get("skills", []):
        parts.append(group.get("group", ""))
        parts.extend(group.get("items", []))
    for entry in draft.get("experience", []) + draft.get("projects", []):
        parts += [entry.get("company", ""), entry.get("role", ""), entry.get("name", "")]
        parts += [position["title"] for position in entry.get("positions") or [] if position["title"] != entry.get("role")]
        parts.extend(entry.get("bullets", []))
    for entry in profile.get("education", []):
        parts += [entry.get("school", ""), entry.get("degree", ""), entry.get("year", "")]
    for entry in profile.get("certifications", []):
        parts += [entry.get("name", ""), entry.get("issuer", ""), entry.get("year", "")]
    return "\n".join(p for p in parts if p)


def verify(profile, draft, keywords=()):
    """Every claim in the draft must already exist in your details. Returns the ones that don't."""
    source = profile_text(profile)
    known = _vocabulary(source)
    # The advert's skills your details don't mention, including two-word ones like "Supply Chain".
    unclaimed = [k for k in keywords if not matching.mentions(source, k)]
    flags = []

    def scan(where, text):
        numbers = [n.replace(",", "") for n in _NUMBER.findall(text)]
        new_numbers = [n for n in numbers if n not in known and n.strip("%.") not in known]
        new_terms = []
        for match in _WORD.finditer(text):
            word = match.group().rstrip(".-/")  # "Python." at the end of a sentence is still Python
            low = word.lower()
            if low in known or low in COMMON_WORDS or len(low) < 3:
                continue
            before = text[:match.start()].rstrip()
            starts_sentence = not before or before[-1] in ".!?;:•"
            # A capital letter only suggests a name or tool mid-sentence; "Skilled in …" is just a sentence start.
            named = word[:1].isupper() and not starts_sentence
            special = word.isupper() or any(c.isdigit() for c in word) or any(c.isupper() for c in word[1:])
            if named or special or any(matching.mentions(word, k) for k in keywords):
                new_terms.append(word)
        new_terms += [k for k in unclaimed if matching.mentions(text, k) and not any(matching.mentions(k, t) for t in new_terms)]
        if new_numbers or new_terms:
            flags.append({
                "where": where,
                "text": text,
                "terms": sorted(set(new_numbers + new_terms)),
                "why": "number not in your details" if new_numbers else "not in your details",
            })

    if draft.get("summary"):
        scan("Summary", draft["summary"])
    for group in draft.get("skills", []):
        for item in group.get("items", []):
            scan(f"Skills · {group.get('group', '')}", item)
    for entry in draft.get("experience", []):
        for i, bullet in enumerate(entry.get("bullets", []), 1):
            scan(f"{entry.get('company', '')} · bullet {i}", bullet)
    for entry in draft.get("projects", []):
        for i, bullet in enumerate(entry.get("bullets", []), 1):
            scan(f"{entry.get('name', '')} · bullet {i}", bullet)
    for name in draft.get("unknown_entries", []):
        flags.append({"where": "Dropped", "text": name, "terms": [name],
                      "why": "the AI invented this employer or project, so it was left out"})
    return flags


# ---------- ATS report ----------

MIN_WORDS = 350
ONE_PAGE_WORDS = 650  # about what one A4 page holds at the PDF's sizes, with contact details and education

def ats_report(profile, draft, keywords, pdf_text=None):
    """An estimate of how well this resume answers the advert and how easily software can read it."""
    text = draft_text(draft, profile)
    matched = matching.find_terms(text, keywords) if keywords else []
    coverage = len(matched) / len(keywords) if keywords else 0.0
    words = len(text.split())
    bullets = [b for e in draft.get("experience", []) + draft.get("projects", []) for b in e.get("bullets", [])]
    stuffed = [k for k in matched if len(matching.find_terms(text, [k])) and text.lower().count(k.lower()) > 6]

    checks = [
        {"name": "Email and phone number", "ok": bool(profile["contact"].get("email") and profile["contact"].get("phone")),
         "detail": "ATS software looks for both."},
        {"name": "Summary, skills and experience sections", "ok": bool(draft.get("summary") and draft.get("skills") and draft.get("experience")),
         "detail": "Standard headings are what parsers expect."},
        {"name": "Bullet points that stay on one line", "ok": bool(bullets) and all(len(b.split()) <= 32 for b in bullets),
         "detail": f"{len(bullets)} bullets; long ones get cut off."},
        {"name": f"Length between {MIN_WORDS} and {ONE_PAGE_WORDS} words", "ok": MIN_WORDS <= words <= ONE_PAGE_WORDS,
         "detail": f"{words} words; more than about {ONE_PAGE_WORDS} won't fit on one page."},
        {"name": "Working links", "ok": all(normalize.safe_url(link["url"]) for link in profile.get("links", [])),
         "detail": f"{len(profile.get('links', []))} links."},
        {"name": "No keyword stuffing", "ok": not stuffed, "detail": ", ".join(stuffed) or "No word is repeated too often."},
        {"name": "Education or certificates listed", "ok": bool(profile.get("education") or profile.get("certifications")),
         "detail": "Many filters ask for a qualification."},
    ]
    if pdf_text is not None:
        readable = matching.find_terms(pdf_text, keywords) if keywords else []
        checks.append({"name": "The PDF reads back correctly",
                       "ok": bool(pdf_text.strip()) and len(readable) >= len(matched) - 1
                       and bool(profile["contact"].get("email", "") in pdf_text),
                       "detail": f"{len(readable)} of {len(keywords)} keywords survive when the PDF's text is extracted."})

    passed = sum(1 for c in checks if c["ok"])
    score = round(60 * coverage + 40 * (passed / len(checks)))
    return {
        "score": score,
        "coverage": round(coverage * 100),
        "matched": matched,
        "missing": [k for k in keywords if k not in matched],
        "checks": checks,
        "words": words,
        "note": "An estimate from this job's wording, not an official ATS score.",
    }


def tailor_messages(job, profile, keywords):
    return [{"role": "system", "content": TAILOR_RULES},
            {"role": "user", "content": _job_brief(job, keywords) + "\n\nThe person's resume as JSON:\n"
             + json.dumps(profile, ensure_ascii=False)}]


def tailor(job, profile, steps):
    """Asks the AI to tailor your resume to one job, then checks the result. No file is written yet."""
    if not profile_is_usable(profile):
        raise ResumeError("Fill in the Resume tab first (at least your name and one job or project).")
    keywords = job_keywords(job)
    data, model = ai.chat_json(tailor_messages(job, profile, keywords), steps, schema=TAILOR_SCHEMA)
    draft = clean_draft(data, profile)
    flags = verify(profile, draft, keywords)
    return {"draft": draft, "flags": flags, "keywords": keywords, "model": model,
            "ats": ats_report(profile, draft, keywords)}


COVER_RULES = """You write a short job application note (90-130 words) for the person whose resume is given.
Use only facts from the resume. Never invent numbers, tools, employers or skills. Plain text, no greeting line
placeholders like [Name], no markdown. Mention the role and two or three things from the resume that fit the advert.
Reply with only the note itself: no introduction ("Here is…", "Based on the resume…"), no title, no closing remarks."""

# What models put around the note: "Based on the provided resume, here is a job application note for …:",
# a "**Job Application Note**" title, "Subject: …", and "Let me know if …" at the end.
_NOTE_INTRO = re.compile(r"(?i)^\s*(?:based on|here is|here's|here are|sure|certainly|of course|below is|okay|ok)\b"
                         r"(?=[^:\n]{0,250}\b(?:resume|note|letter|application|request|details|information|cv)\b)"
                         r"[^:\n]{0,250}(?::|\.(?=\s*\n)|\n)\s*")
_NOTE_TITLE = re.compile(r"(?i)^\s*(?:#{1,6}\s*|\*\*|__)?\s*(?:(?:job\s+)?application\s+note|cover\s+(?:note|letter)|"
                         r"subject\s*:[^\n*]*|re\s*:[^\n*]*)\s*(?:\*\*|__)?\s*:?\s*")
_NOTE_BOLD_TITLE = re.compile(r"^\s*(?:\*\*|__)[^*_\n]{1,80}(?:\*\*|__)\s*:?\s*")
# Only on a line of its own at the end: "Please let me know a good time to talk." inside the note stays.
_NOTE_OUTRO = re.compile(r"(?i)\n\s*(?:let me know|feel free to|i hope this|hope this helps|note:)[^\n]*\s*$")


def clean_note(text):
    """Only the note: no AI introduction, title, closing remark or markdown. Works on saved notes too, which were
    stored on one line."""
    text = str(text or "").strip()
    for _ in range(3):  # an introduction can be followed by a title, which can be followed by another one
        before = text
        text = _NOTE_INTRO.sub("", text, count=1)
        text = _NOTE_TITLE.sub("", text, count=1)
        text = _NOTE_BOLD_TITLE.sub("", text, count=1)
        if text == before:
            break
    text = _NOTE_OUTRO.sub("", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)  # **bold** and __bold__
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    return " ".join(text.replace("**", "").split())


def cover_note(job, profile, steps):
    messages = [{"role": "system", "content": COVER_RULES},
                {"role": "user", "content": _job_brief(job, job_keywords(job, 12))
                 + "\n\nThe person's resume as JSON:\n" + json.dumps(profile, ensure_ascii=False)}]
    text, model = ai.chat(messages, steps, max_tokens=600)
    note = clean_note(text)[:1500]
    return {"note": note, "model": model,
            "flags": verify(profile, {"summary": note, "skills": [], "experience": [], "projects": []}, job_keywords(job, 12))}


def apply_answers(profile):
    """The details application forms ask for, ready to copy."""
    contact, answers = profile.get("contact", {}), profile.get("answers", {})
    fields = [("Full name", contact.get("name")), ("Email", contact.get("email")), ("Phone", contact.get("phone")),
              ("Current location", contact.get("location")), ("Total experience", answers.get("total_experience")),
              ("Notice period", answers.get("notice_period")), ("Current CTC", answers.get("current_ctc")),
              ("Expected CTC", answers.get("expected_ctc")), ("Preferred locations", answers.get("preferred_locations"))]
    out = [{"label": label, "value": value} for label, value in fields if value]
    out += [{"label": link["label"], "value": link["url"]} for link in profile.get("links", [])]
    return out


# ---------- JSON shapes, enforced by services that support it (Claude) ----------

_TEXTS = {"type": "array", "items": {"type": "string"}}


def _object(**properties):
    return {"type": "object", "additionalProperties": False, "required": list(properties), "properties": properties}


_STRING = {"type": "string"}
TAILOR_SCHEMA = _object(
    summary=_STRING,
    skills={"type": "array", "items": _object(group=_STRING, items=_TEXTS)},
    experience={"type": "array", "items": _object(company=_STRING, role=_STRING, bullets=_TEXTS)},
    projects={"type": "array", "items": _object(name=_STRING, bullets=_TEXTS)},
    left_out=_TEXTS,
)
IMPORT_SCHEMA = _object(
    contact=_object(name=_STRING, title=_STRING, email=_STRING, phone=_STRING, location=_STRING),
    links={"type": "array", "items": _object(label=_STRING, url=_STRING)},
    summary=_STRING,
    skills={"type": "array", "items": _object(group=_STRING, items=_TEXTS)},
    experience={"type": "array", "items": _object(
        company=_STRING, role=_STRING, start=_STRING, end=_STRING, location=_STRING, bullets=_TEXTS,
        positions={"type": "array", "items": _object(title=_STRING, start=_STRING, end=_STRING)})},
    projects={"type": "array", "items": _object(name=_STRING, link=_STRING, bullets=_TEXTS)},
    education={"type": "array", "items": _object(school=_STRING, degree=_STRING, year=_STRING, details=_STRING)},
    certifications={"type": "array", "items": _object(name=_STRING, issuer=_STRING, year=_STRING)},
)


# ---------- How human it sounds ----------

# Stock phrases that make a resume read as machine-written. Some are fine once in a human resume, so each costs a
# little rather than failing the text outright.
AI_PHRASES = (
    "spearheaded", "leveraged", "leveraging", "utilized", "utilizing", "results-driven", "results driven", "dynamic",
    "passionate", "proven track record", "synergy", "synergies", "cutting-edge", "cutting edge", "seamless",
    "seamlessly", "robust", "delve", "delved", "orchestrated", "pivotal", "meticulous", "meticulously", "adept at",
    "tapestry", "fostering", "fostered", "empowered", "harnessed", "harnessing", "innovative", "detail-oriented",
    "self-starter", "go-getter", "thought leader", "best-in-class", "world-class", "strategic thinker",
    "team player", "hard-working", "hardworking", "in today's", "ever-evolving", "fast-paced", "a testament to",
    "showcasing", "showcased", "navigating", "landscape", "realm", "unwavering", "commitment to excellence",
    "impactful", "drive growth", "value-added", "holistic", "streamlined", "streamlining", "elevate", "elevated",
    "transformative", "game-changer", "keen eye", "wealth of experience", "extensive experience",
)


def _sentences(texts):
    out = []
    for text in texts:
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.split()) >= 3]
    return out


def style_check(texts):
    """A quick, consistent read of how machine-written the text sounds. Returns score 0-100 and what to change."""
    joined = " ".join(t for t in texts if t)
    low = joined.lower()
    found = [p for p in AI_PHRASES if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", low)]
    penalty, notes = min(48, 8 * len(found)), []
    sentences = _sentences(texts)
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) >= 4:
        mean = sum(lengths) / len(lengths)
        spread = (sum((n - mean) ** 2 for n in lengths) / len(lengths)) ** 0.5 / mean if mean else 0
        if spread < 0.2:
            penalty += 15
            notes.append("every line is about the same length; vary them")
        elif spread < 0.3:
            penalty += 7
    openers = {}
    for sentence in sentences:
        first = sentence.split()[0].lower()
        openers[first] = openers.get(first, 0) + 1
    repeated = [word for word, count in openers.items() if count > 2]
    if repeated:
        penalty += min(15, 5 * sum(openers[w] - 2 for w in repeated))
        notes.append(f"too many lines start with: {', '.join(repeated)}")
    dashes = joined.count("—")
    if dashes > 1:
        penalty += min(12, 3 * (dashes - 1))
        notes.append("fewer long dashes (—)")
    return {"score": max(0, 100 - penalty), "phrases": found, "notes": notes}


REVIEW_RULES = """You are a strict editor who knows how AI-written resumes read. Rate how much the text sounds like a
real person wrote it, from 0 (clearly machine-written) to 100 (clearly a person). Resumes are terse by nature: judge
word choice, stock phrases, empty claims and rhythm, not grammar. Plain, specific lines with real tools and numbers
sound human. Quote up to 8 exact phrases from the text that sound generated (a low score must be backed by quotes),
and give one short tip.
Answer with only this JSON: {"score": <whole number from 0 to 100>, "phrases": ["<exact quote>"], "tip": "<one sentence>"}"""
REVIEW_SCHEMA = _object(score={"type": "integer"}, phrases=_TEXTS, tip=_STRING)


def draft_texts(draft):
    """The parts of a tailored resume the AI wrote: the summary and the bullet points."""
    return [draft.get("summary", "")] + [b for e in draft.get("experience", []) + draft.get("projects", [])
                                         for b in e.get("bullets", [])]


def human_score(draft, reviewer_steps):
    """How much the tailored wording sounds like a person: the built-in style check averaged with an AI reviewer.

    The reviewer is always the same model (the first usable one), so scores are comparable between rounds.
    """
    texts = draft_texts(draft)
    style = style_check(texts)
    review = None
    if reviewer_steps:
        joined = " ".join(texts)
        try:
            data, model = ai.chat_json([{"role": "system", "content": REVIEW_RULES},
                                        {"role": "user", "content": "\n".join(t for t in texts if t)}],
                                       reviewer_steps, temperature=0, max_tokens=800, schema=REVIEW_SCHEMA)
            review = {"score": max(0, min(100, int(data.get("score")))),
                      "phrases": [p for p in data.get("phrases") or [] if isinstance(p, str) and p.strip()
                                  and p.strip().lower() in joined.lower()][:8],
                      "tip": str(data.get("tip") or "")[:200], "model": model}
            if review["score"] < 50 and not review["phrases"]:
                review = None  # a harsh score with nothing quoted from the text is a model misfiring, not a judgement
        except (ai.AIError, TypeError, ValueError):
            review = None  # the built-in check still gives a score
    score = round((style["score"] + review["score"]) / 2) if review else style["score"]
    phrases = list(dict.fromkeys(style["phrases"] + (review["phrases"] if review else [])))
    return {"score": score, "style_score": style["score"], "reviewer_score": review["score"] if review else None,
            "reviewer": review["model"] if review else None, "phrases": phrases,
            "notes": style["notes"] + ([review["tip"]] if review and review["tip"] else []),
            "note": "An estimate of how natural the wording reads, not a real AI detector."}


# ---------- Reaching an ATS target honestly ----------

CEILING_BLOCKERS = {
    "Email and phone number": "Add your email and phone number on the Resume tab.",
    "Working links": "Fix the links on the Resume tab (they must start with http:// or https://).",
    "Education or certificates listed": "Add your education or a certificate on the Resume tab.",
    "Summary, skills and experience sections": "Add a summary, some skills and at least one job on the Resume tab.",
}


def ats_ceiling(profile, keywords):
    """The best ATS score possible without claiming anything new.

    Keyword match counts only the advert's words already in your details. The format checks count only what a rewrite
    can fix: a resume can always be cut to length or have its bullets shortened, but it can't grow past what your
    details contain, or gain an email address that isn't there.
    """
    have = matching.find_terms(profile_text(profile), keywords) if keywords else []
    coverage = len(have) / len(keywords) if keywords else 1.0
    full = {"summary": profile.get("summary") or "x", "skills": profile.get("skills", []),
            "experience": profile.get("experience", []), "projects": profile.get("projects", [])}
    report = ats_report(profile, full, keywords)
    passed, blockers = 0, []
    for check in report["checks"]:
        name, ok = check["name"], check["ok"]
        if name.startswith("Length"):
            ok = report["words"] >= MIN_WORDS  # longer can be trimmed; shorter can't be padded honestly
            if not ok:
                blockers.append(f"Your resume details come to about {report['words']} words; a full one-page resume is "
                                f"{MIN_WORDS} to {ONE_PAGE_WORDS}. Add more on the Resume tab (bullet points, a project, "
                                "certificates).")
        elif name in ("Bullet points that stay on one line", "No keyword stuffing"):
            ok = True  # a rewrite can fix these
        elif not ok and name in CEILING_BLOCKERS:
            blockers.append(CEILING_BLOCKERS[name])
        passed += ok
    best = round(60 * coverage + 40 * passed / len(report["checks"]))
    return {"best_score": best, "have": have, "missing": [k for k in keywords if k not in have], "blockers": blockers}


def add_skills(profile, skills):
    """Adds skills you confirmed you have to your details, in a group of their own that is easy to edit later."""
    text = profile_text(profile)
    new = [s for s in dict.fromkeys(_text(x, 80) for x in skills or []) if s and not matching.mentions(text, s)]
    if new:
        group = next((g for g in profile["skills"] if g["group"] == "Also skilled in"), None)
        if group is None:
            profile["skills"].append({"group": "Also skilled in", "items": new})
        else:
            group["items"] += new
    return clean_profile(profile), new


REVISE_RULES = TAILOR_RULES + """

You are improving an earlier version of this tailored resume. Everything must stay true to the person's resume.
Work in the feedback you are given: use the listed keywords only where the resume shows the person really has
that skill or did that work, and rewrite the listed phrases in plain, specific wording (real tools, numbers and
results from the resume, no buzzwords, varied sentence length)."""


def shorten(job, profile, draft, keywords, over, steps):
    """Asks the AI to cut a resume that runs past one page, keeping what matters most for this job.

    `over` is its length as a share of a page (1.25 = a quarter too long). Returns (shortened draft, model).
    """
    words = len(draft_text(draft, profile).split())
    target = max(MIN_WORDS, int(words / over * 0.93))  # a little under the limit, so it really fits
    feedback = (f"This version runs to about {round(over * 100)}% of one A4 page and the resume must fit on ONE page. "
                f"It has about {words} words; bring it down to about {target}. Remove the bullets and projects that "
                "matter least for this job first, then shorten long bullets and the summary. Keep every job (an older "
                "one can go down to one bullet), its company name and role, and the strongest matches for the advert. "
                "Do not add anything new.")
    data, model = ai.chat_json(revise_messages(job, profile, draft, keywords, feedback), steps, schema=TAILOR_SCHEMA)
    return clean_draft(data, profile), model


def revise_messages(job, profile, draft, keywords, feedback):
    current = json.loads(json.dumps({k: draft.get(k) for k in ("summary", "skills", "experience", "projects")}))
    for entry in current["experience"] or []:  # a copy: the draft itself keeps its dates
        for field in ("start", "end", "location", "positions"):
            entry.pop(field, None)
    return [{"role": "system", "content": REVISE_RULES},
            {"role": "user", "content": _job_brief(job, keywords)
             + "\n\nThe person's resume as JSON:\n" + json.dumps(profile, ensure_ascii=False)
             + "\n\nThe earlier version:\n" + json.dumps(current, ensure_ascii=False)
             + "\n\nFeedback:\n" + feedback}]
