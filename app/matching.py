"""Free keyword-based match score between a job and the profile typed in the app."""
import re
from functools import lru_cache

FILLER_WORDS = {"and", "of", "the", "for", "in", "a", "an", "to", "with"}


def split_terms(text):
    """'Data Analyst, MIS Analyst' -> ['Data Analyst', 'MIS Analyst']"""
    return [t.strip() for t in re.split(r"[,;\n]", text or "") if t.strip()]


def _words(text):
    return [w for w in re.split(r"[^a-z0-9+#.]+", (text or "").lower()) if w and w not in FILLER_WORDS]


@lru_cache(maxsize=4096)  # room for the whole skill catalogue (about 800 terms), or it recompiles them every time
def _term_pattern(term):
    # "Power BI" also matches "PowerBI" / "power-bi"; symbols like C++ or .NET are kept literal.
    parts = [re.escape(p) for p in term.lower().split()]
    return re.compile(r"(?<![a-z0-9])" + r"[\s\-_/]*".join(parts) + r"(?![a-z0-9])")


def mentions(text, term):
    """True when the text uses the term, allowing 'PowerBI', 'power-bi' and 'Power BI' to match each other."""
    return bool(term) and bool(_term_pattern(term).search((text or "").lower()))


def find_terms(text, terms):
    """The terms out of `terms` that the text mentions, in the order given."""
    lowered = (text or "").lower()
    # A term's first word always appears as written, so terms without it are skipped before the slower pattern.
    return [t for t in terms if t.split() and t.lower().split()[0] in lowered and _term_pattern(t).search(lowered)]


def title_score(job_title, titles):
    """1.0 when every word of one of the wanted titles is in the job title, otherwise the best partial share."""
    job_title = (job_title or "").lower()
    job_words = set(_words(job_title))
    best = 0.0
    for wanted in titles:
        if _term_pattern(wanted).search(job_title):
            return 1.0
        words = _words(wanted)
        if words:
            best = max(best, sum(1 for w in words if w in job_words) / len(words))
    return best


def score_job(title, description, titles, skills):
    """Returns (score 0-100, matched skills). Title counts 40%, skills 60%."""
    text = f"{title or ''}\n{description or ''}".lower()
    matched = [s for s in skills if _term_pattern(s).search(text)]
    t_score = title_score(title, titles) if titles else 0.0
    s_score = len(matched) / len(skills) if skills else 0.0
    if titles and skills:
        score = 40 * t_score + 60 * s_score
    elif titles:
        score = 100 * t_score
    elif skills:
        score = 100 * s_score
    else:
        score = 0
    return round(score), matched
