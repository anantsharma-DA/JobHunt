"""Warnings on a job, worked out on this computer with no AI and no web access: likely scams, likely ghost jobs
(listings that stay up or keep being reposted without real hiring), and how soon the advert wants you to join.

These are signs, not proof: each warning lists the reasons it found, so you can judge for yourself.
"""
import re
from datetime import date

# ---------- Scams ----------
# Each rule: (weight, reason shown to you, pattern). 3 = a strong sign on its own, 2 = a clear sign, 1 = weak alone.
_MONEY = r"(?:rs\.?|inr|₹)\s*[\d,]+"
_SCAM_RULES = [
    (3, "asks you to pay a fee or deposit",
     re.compile(r"(?i)\b(?:registration|processing|training|security|joining|kit|onboarding|verification|document(?:ation)?)"
                r"\s+(?:fees?|charges?|deposit|amount)\b|\brefundable\s+(?:fees?|deposit|amount)\b|\bpay\s+" + _MONEY
                + r"|\bdeposit\s+(?:of\s+)?" + _MONEY)),
    (3, "promises easy money (per-day earnings, tasks, typing or investment)",
     re.compile(r"(?i)\bearn\s+(?:up\s*to\s+)?" + _MONEY + r"\s*(?:per|/|a|an|in\s+a)\s*(?:day|hour|week)\b|\b(?:daily|weekly)"
                r"\s+payouts?\b|\b(?:like|rate|review)\s+(?:youtube\s+)?(?:videos|products|hotels|apps)\b|\btask[- ]based\s+"
                r"(?:income|earning|job)|\b(?:crypto|forex|trading)\s+(?:task|income|earning)|\bcopy[- ]paste\s+work\b")),
    (2, "asks you to apply or talk only on WhatsApp or Telegram",
     re.compile(r"(?i)\b(?:apply|send\s+(?:your\s+)?(?:cv|resume)|contact|message|ping|dm|reach)\b[^.\n]{0,40}?"
                r"\b(?:on|via|through|at)\s+(?:whats\s*app|telegram)\b|\b(?:whats\s*app|telegram)\s+(?:only|me|us\s+(?:your|at))")),
    (2, "the recruiter uses a personal email address",
     re.compile(r"(?i)\b[\w.+-]+@(?:gmail|yahoo|outlook|hotmail|rediffmail|ymail)\.(?:com|co\.in|in)\b")),
    (2, "promises a job with no interview",
     re.compile(r"(?i)\bno\s+interview\b|\bwithout\s+(?:any\s+)?interview\b|\b(?:direct|instant|spot)\s+(?:joining|offer\s+letter)\b"
                r"|\boffer\s+letter\s+(?:in|within)\s+\d+\s*(?:hours?|hrs?)\b")),
]
# Phrases that mention a fee only to say there isn't one.
_NO_FEE = re.compile(r"(?i)\b(?:no|never|not|free\s+of|without)\b[^.\n]{0,30}\b(?:fees?|charges?|deposit|money|payment)\b")
_UNNAMED = {"", "confidential", "unknown company", "company confidential", "hiring", "urgent", "undisclosed", "n/a", "na"}


def scam_check(job, text):
    """{"level": "low"|"medium"|"high", "reasons": [...]} for one job. `text` is its description and listed skills."""
    reasons, score, strong, clear = [], 0, 0, 0
    text = text or ""
    for weight, reason, pattern in _SCAM_RULES:
        match = pattern.search(text)
        if not match:
            continue
        if weight == 3 and "fee" in reason and _NO_FEE.search(text[max(0, match.start() - 40):match.end() + 10]):
            continue  # "no registration fee" is the opposite of a warning
        reasons.append(reason)
        score += weight
        strong += weight == 3
        clear += weight == 2
    top, experience = job.get("salary_max") or job.get("salary_min"), job.get("exp_min")
    if top is not None and experience is not None and experience <= 1:
        if top >= 25:
            reasons.append(f"pays up to ₹{top:g} LPA for {experience:g}–1 years' experience, far above normal")
            score += 3
            strong += 1
        elif top >= 12:
            reasons.append(f"pays up to ₹{top:g} LPA for {experience:g}–1 years' experience, unusually high")
            score += 2
            clear += 1
    if (job.get("company") or "").strip().lower() in _UNNAMED:
        reasons.append("the company isn't named")
        score += 1
    if text.strip() and len(text.split()) < 40:
        reasons.append("the advert is only a few lines long")
        score += 1
    # High needs a strong sign, two clear ones, or a lot together; weak signs alone (a short advert, no company name)
    # never make a job look dangerous.
    level = "high" if strong or clear >= 2 or score >= 4 else "medium" if score >= 2 and (clear or score >= 3) else "low"
    return {"level": level, "reasons": reasons}


# ---------- Ghost jobs ----------

def _day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def ghost_check(job, history, ghost_days=45, ghost_reposts=3, today=None):
    """{"likely": bool, "reasons": [...], "first_seen", "reposts"} for one job.

    `history` is what JobHunt remembers about this company + title across all searches (kept even after you clear the
    Jobs tab): when it first appeared, and how often its posting date jumped forward (a repost).
    """
    today = today or date.today()
    history = history or {}
    known = [d for d in (_day(history.get("first_posted")), _day(history.get("first_seen")), _day(job.get("date_posted")),
                         _day(job.get("first_seen"))) if d]
    first = min(known) if known else None
    age = (today - first).days if first else 0
    reposts = int(history.get("repost_count") or 0)
    reasons = []
    if first and age >= ghost_days:
        reasons.append(f"first seen {first.strftime('%d %b %Y')}, {age} days ago")
    if reposts >= ghost_reposts:
        reasons.append(f"reposted {reposts} times")
    if first and age >= 30 and (job.get("applicants") or 0) >= 200:
        reasons.append("still open after 30+ days with 200+ applicants")
    return {"likely": bool(reasons), "reasons": reasons, "first_seen": first.isoformat() if first else None,
            "reposts": reposts}


# ---------- Notice period ----------
_IMMEDIATE = re.compile(r"(?i)\bimmediate\s+(?:joiners?|joinees?|joining|starters?|availability)\b|\bjoin(?:ing)?\s+immediately\b"
                        r"|\bcan\s+join\s+immediately\b|\bnotice\s+period\s*[:\-]?\s*(?:immediate|0\s*days?|nil|none)\b")
# "notice period of 30 days", "join within 15 days", "notice up to 2 months", "15-30 days notice"
_NOTICE_NEAR = re.compile(r"(?i)(?:notice(?:\s+period)?|join(?:ing)?\s+within|can\s+join\s+(?:in|within))[^.\n]{0,40}")
_NOTICE_BEFORE = re.compile(r"(?i)(\d{1,3})\s*(?:[-–to]+\s*(\d{1,3})\s*)?(days?|weeks?|months?)\s+(?:of\s+)?notice")
_AMOUNT = re.compile(r"(?i)(\d{1,3})\s*(?:[-–]|to)?\s*(\d{1,3})?\s*(days?|weeks?|months?)")
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}


def _to_days(number, unit):
    return int(number) * _UNIT_DAYS[unit.lower().rstrip("s")]


def notice_need(text):
    """How soon the advert wants you to join: {"text", "max_days"}, or None if it doesn't say."""
    text = text or ""
    if _IMMEDIATE.search(text):
        return {"text": "Immediate joiner", "max_days": 0}
    days = []
    for near in _NOTICE_NEAR.finditer(text):
        for m in _AMOUNT.finditer(near.group(0)):
            days.append(_to_days(m.group(2) or m.group(1), m.group(3)))
    for m in _NOTICE_BEFORE.finditer(text):
        days.append(_to_days(m.group(2) or m.group(1), m.group(3)))
    days = [d for d in days if 0 < d <= 180]
    if not days:
        return None
    most = max(days)
    return {"text": f"Notice up to {most} days", "max_days": most}


def notice_days(answer):
    """Your notice period from the Resume tab ("30 days", "2 months", "Immediate", "serving, 15 days left") in days,
    or None if it can't be read."""
    text = (answer or "").strip().lower()
    if not text:
        return None
    if re.search(r"\b(?:immediate|immediately|none|nil|0)\b", text):
        return 0
    m = re.search(r"(\d{1,3})\s*(days?|weeks?|months?)", text)
    if m:
        return _to_days(m.group(1), m.group(2))
    m = re.fullmatch(r"(\d{1,3})", text)
    return int(m.group(1)) if m else None


# ---------- A second opinion from the AI (only when you press "Check with AI") ----------

AI_RULES = """You check one job advert for signs of recruitment fraud, the way an experienced Indian recruiter would.
Common frauds in India: asking the candidate for any payment (registration, training, kit, security deposit,
document verification), job offers without an interview, recruiters using personal Gmail/Yahoo addresses or only
WhatsApp/Telegram, unrealistic pay for the experience, easy-money tasks (liking videos, rating products, typing),
impersonating a well-known company, and pressure to decide or pay quickly.
Judge only from the advert given. Most adverts are genuine: say "low" unless there are real warning signs.
Answer with only this JSON: {"risk": "low" | "medium" | "high", "reasons": ["short reason", ...]}"""

AI_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["risk", "reasons"],
    "properties": {"risk": {"type": "string", "enum": ["low", "medium", "high"]},
                   "reasons": {"type": "array", "items": {"type": "string"}}},
}


def ai_brief(job):
    """The advert as the AI sees it: what a candidate would see, nothing about you."""
    pay = job.get("salary_text") or (f"{job.get('salary_min')}–{job.get('salary_max')} LPA"
                                      if job.get("salary_min") or job.get("salary_max") else "not stated")
    experience = f"{job.get('exp_min')}–{job.get('exp_max')} years" if job.get("exp_min") is not None else "not stated"
    return (f"Job title: {job.get('title')}\nCompany: {job.get('company') or 'not named'}\nLocation: {job.get('location')}\n"
            f"Pay: {pay}\nExperience asked: {experience}\n\nAdvert:\n{(job.get('description') or '(no description)')[:6000]}")


# ---------- Applying twice ----------

def history_key(title, company):
    """The same role at the same company, however a site words the city or salary: used for reposts and 'already
    applied'."""
    from app import normalize

    return f"{normalize.company_key(company or '')}|{normalize.slug(title or '')}"
