"""Interview questions found on the web, for one company and role, or for a role in general.

Gemini searches Google itself ("grounding") and says which web page supports each line it writes, which is what
lets JobHunt show a real source for every question. When Gemini is unavailable or at its free daily limit, Tavily
finds the pages and the user's AI models pull the questions out of the pages' own text. Every question is kept only
if a source backs it, and results are saved so opening them again costs nothing.
"""
import difflib
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app import ai, db, normalize
from app.sources import ats

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Free Google Search grounding exists only on the 2.5 models (about 500 a day), and Google no longer offers those to new
# keys. Newer models ground searches only on keys with billing switched on (5,000 free a month there). Keys that can do
# neither get "not available" or "quota" answers, and JobHunt then uses Tavily for the rest of the day.
GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-lite-latest")
GEMINI_DAILY_CAP = 500
TAVILY_URL = "https://api.tavily.com/search"
TAVILY_MONTHLY_CAP = 1000
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
EXTRACT_MAX = 8  # pages read in one Extract request
MAX_QUESTIONS = 30
# Each search of the same title (or company + title) uses the next wording, so it reaches different pages.
# Candidates' own write-ups ("interview experience") name the questions a company actually asked.
ROLE_QUERIES = (
    "{title} interview questions asked candidates India",
    "{title} technical interview questions and answers",
    "{title} scenario based interview questions with answers",
    "{title} interview questions for experienced professionals",
    "{title} interview questions for freshers",
    "{title} HR and managerial round interview questions",
)
COMPANY_QUERIES = (
    "{company} {title} interview experience questions asked",
    "{company} {title} interview questions and answers",
    "{company} {title} technical round interview questions",
    "{company} interview experience {title} rounds",
    "{company} {title} HR round interview questions",
)
ENOUGH_EXACT = 15  # questions from pages about the exact role before near-match pages are left out
# Words that name the level or kind of job rather than its field; a page needn't repeat them to be about the role.
_ROLE_WORDS = {"engineer", "engineers", "analyst", "developer", "manager", "specialist", "executive", "associate",
               "consultant", "lead", "senior", "junior", "sr", "jr", "intern", "trainee", "officer", "assistant",
               "head", "principal", "staff", "i", "ii", "iii", "and", "of", "the", "for", "in", "&"}
TIMEOUT = 120


class SearchError(Exception):
    """Shown to the user as it is."""


def scope_for(title, company=None):
    return f"{(company or '').strip().lower()}|{title.strip().lower()}"


# ---------- Free-limit counters ----------

def usage():
    u = dict(db.get_settings()["search_usage"])
    today, month = date.today().isoformat(), date.today().isoformat()[:7]
    return {"gemini_today": u.get("gemini_count", 0) if u.get("gemini_day") == today else 0,
            "gemini_cap": GEMINI_DAILY_CAP,
            "gemini_unavailable": u.get("gemini_blocked_day") == today,
            "tavily_month": u.get("tavily_count", 0) if u.get("tavily_month") == month else 0,
            "tavily_cap": TAVILY_MONTHLY_CAP}


def _count(service):
    u = dict(db.get_settings()["search_usage"])
    today, month = date.today().isoformat(), date.today().isoformat()[:7]
    if service == "gemini":
        u["gemini_count"] = (u.get("gemini_count", 0) if u.get("gemini_day") == today else 0) + 1
        u["gemini_day"] = today
    else:
        u["tavily_count"] = (u.get("tavily_count", 0) if u.get("tavily_month") == month else 0) + 1
        u["tavily_month"] = month
    db.save_settings({"search_usage": u})


# ---------- Text helpers ----------

def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())).strip()


def _site(url, fallback=""):
    host = (urlparse(url or "").hostname or fallback or "").lower()
    return host[4:] if host.startswith("www.") else host


def _found_in(question, text):
    """True when most of the question's words are really on the page (the AI didn't make it up)."""
    words = [w for w in _norm(question).split() if len(w) > 3]
    if not words:
        return False
    page = set(_norm(text).split())
    return sum(1 for w in words if w in page) / len(words) >= 0.7


def _parse_qa(text):
    """'Q: …' / 'A: …' lines -> [{question, answer}]."""
    items, current = [], None
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*•0123456789. ").strip()
        if re.match(r"(?i)^q\s*[:.)-]", line):
            current = {"question": re.sub(r"(?i)^q\s*[:.)-]\s*", "", line).strip(), "answer": None}
            if current["question"]:
                items.append(current)
        elif re.match(r"(?i)^a\s*[:.)-]", line) and current is not None:
            answer = re.sub(r"(?i)^a\s*[:.)-]\s*", "", line).strip()
            if answer and answer.lower().strip(".") not in ("none", "n/a", "not given", "no answer"):
                current["answer"] = answer
    return items


# ---------- Gemini with Google Search ----------

GOOGLE_REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)


def _resolve(uri):
    """Gemini's source links go through a Google redirect; follow it once to show the real page.

    Only Google's own redirect service is ever contacted here, never a link taken from the model's text.
    """
    parts = urlparse(uri or "")
    if parts.scheme != "https" or (parts.hostname or "").lower() not in GOOGLE_REDIRECT_HOSTS:
        return normalize.safe_url(uri) or ""
    try:
        resp = requests.get(uri, allow_redirects=False, timeout=15, stream=True)
        resp.close()
        target = resp.headers.get("location")
        return normalize.safe_url(target) or uri
    except requests.RequestException:
        return uri


def _gemini_prompt(title, company, known=()):
    where = f"at {company} " if company else ""
    skip = ("\n\nThese were found in earlier searches; look for different ones and leave these out:\n"
            + "\n".join(f"- {q}" for q in list(known)[:40])) if known else ""
    return (
        f"Search the web for interview questions that real candidates reported being asked {where}for the "
        f"\"{title}\" role, preferably in India. Look at interview-experience pages such as Glassdoor, AmbitionBox, "
        f"GeeksforGeeks, Naukri Code360, Reddit, InterviewBit and candidates' blogs.\n\n"
        f"List up to {MAX_QUESTIONS} different questions candidates reported. Write each as:\n"
        f"Q: <the question as the page states it>\n"
        f"A: <the answer the page gives, or: none>\n\n"
        f"Only include questions you actually found on the pages. Do not invent or rephrase them into new questions."
        f"{skip}"
    )


def _mark_gemini_unavailable():
    u = dict(db.get_settings()["search_usage"])
    u["gemini_blocked_day"] = date.today().isoformat()
    db.save_settings({"search_usage": u})


def _gemini_search(title, company, key, known=()):
    last_error, refused = None, 0
    for model in GEMINI_MODELS:
        try:
            resp = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key},
                                 json={"contents": [{"parts": [{"text": _gemini_prompt(title, company, known)}]}],
                                       "tools": [{"google_search": {}}]}, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last_error = f"could not reach Gemini ({exc.__class__.__name__})"
            continue
        if resp.status_code in (401, 403):
            raise SearchError("Gemini did not accept its API key. Check the Gemini card on the Settings tab.")
        if resp.status_code in (404, 429):
            refused += 1  # "no longer available to new users", or no search quota on this key
            last_error = ("Google doesn't offer free web search on this Gemini key (it needs an older key or billing "
                          "switched on)")
            continue
        if resp.status_code >= 400:
            last_error = f"Gemini failed (HTTP {resp.status_code})"
            continue
        _count("gemini")
        candidate = (resp.json().get("candidates") or [{}])[0]
        text = "".join(part.get("text", "") for part in (candidate.get("content") or {}).get("parts", []))
        meta = candidate.get("groundingMetadata") or {}
        return text, meta, model
    if refused == len(GEMINI_MODELS):
        _mark_gemini_unavailable()  # don't spend a request on this again today; Tavily takes over
    raise SearchError(last_error or "Gemini did not answer")


def _from_gemini(title, company, key, known=()):
    text, meta, model = _gemini_search(title, company, key, known)
    chunks = [c.get("web") or {} for c in meta.get("groundingChunks") or []]
    links = {}  # chunk index -> {"url", "site"}, redirects resolved once each
    items = _parse_qa(text)
    for support in meta.get("groundingSupports") or []:
        segment = _norm((support.get("segment") or {}).get("text"))
        if not segment:
            continue
        for item in items:
            question, answer = _norm(item["question"]), _norm(item.get("answer"))
            if segment in question or question in segment or (answer and (segment in answer or answer in segment)):
                for index in support.get("groundingChunkIndices") or []:
                    if index < len(chunks) and index not in links:
                        web = chunks[index]
                        url = _resolve(web.get("uri", "")) if web.get("uri") else ""
                        links[index] = {"url": normalize.safe_url(url) or "", "site": _site(url, web.get("title"))}
                    if index in links:
                        item.setdefault("sources", [])
                        if links[index] not in item["sources"]:
                            item["sources"].append(links[index])
    # A question no web page backs is not shown, nor one a forum writer asked about themself.
    kept = [i for i in items if i.get("sources") and not bad_question(i["question"])]
    for item in kept:
        item["answer_source"] = "source" if item.get("answer") else None
    queries = [{"query": q, "url": f"https://www.google.com/search?q={quote_plus(q)}"}
               for q in meta.get("webSearchQueries") or []]
    return kept, f"Gemini ({model}) with Google Search", queries


# ---------- Tavily + the user's AI models ----------

EXTRACT_RULES = """You pull interview questions out of web pages. Use only the page texts given. For each question a
candidate reports being asked, copy it as written on the page, add the answer only if that page gives one, and give
the URL of the page it came from. Never invent questions or answers.
Answer with only this JSON: {"items": [{"question": "", "answer": "", "url": ""}]}"""

EXTRACT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["question", "answer", "url"],
        "properties": {"question": {"type": "string"}, "answer": {"type": "string"}, "url": {"type": "string"}}}}},
}


# A question on a page: a capitalised sentence ending in "?", optionally numbered ("Q3.", "12)", "-").
# A closing quote and a "(SQL round)" note after the "?" belong to the question, not to its answer.
_QUESTION = re.compile(r"(?<=[\n.!?:])[ \t]*(?:>[ \t]*)?"
                       r"(?:(?:Q|Question)\s*\d*\s*[.:)\-]\s*|\d{1,3}\s*[.)]\s*|[^\w\s.!?]{1,3}\s*)?[“\"‘']?"
                       r"(?P<q>[A-Z][^?.!:\n]{10,220}\?)(?:[ \t]*[”\"’'])?(?:[ \t]*\([^()\n]{1,40}\))?")
# Page furniture that also ends in "?": sign-up prompts, course adverts, navigation.
_NOT_INTERVIEW = re.compile(r"(?i)\b(course|enrol|enroll|sign ?up|subscribe|cookie|newsletter|contact us|learn more|click|"
                            r"download|free trial|webinar|want to|looking for|ready to|why choose|need help|have any questions|"
                            r"our program|bootcamp|placement|salary of|how much does|paid fairly|interview experience|"
                            r"rate your|how was your|got a question|are you ready|dream job|get hired|"
                            r"interview process)\b")
# Forum posts ("Am I aiming for the right CTC?") ask about the writer; interview questions ask about you.
# Also "What are the tools I used…?" and "Explain the blockers I got…": the writer asking about themself. "Type I
# error" and "I and II" are statistics, not a person.
_FIRST_PERSON = re.compile(r"^(?:Am|Should|Can|Could|Do|Did|Will|Would|Shall|Must|Have|Was|Is it ok (?:for|if)) I\b"
                           r"|\b(?:do|am|should|can|could|will|would|did|shall) I\b|\b(?:my|I'm|I've|I am)\b"
                           r"|(?<![Tt]ype )(?<![Pp]hase )(?<![Ll]evel )\bI\b(?!/)(?!\s*(?:and|&|or|vs\.?)\s*II\b)(?![-\s]*errors?\b)")
# Tavily writes each picture on a page as "Image 13" or "Image 25: BFSI Logo", glued to the menu text around it.
_IMAGE = re.compile(r"Image\s*\d+\s*:?")
# Page furniture between a question and the next one ("Add your answer", "Share", "1 Comment", "View answers (4)").
_FURNITURE = re.compile(r"(?i)\b(?:add your answer|share|read more|view (?:all|answers?)|show more|comments?|reply|upvotes?|"
                        r"likes?|follow|log ?in|sign ?in|rate your|anonymous|was asked|posted on|explore more|advertisement|"
                        r"sponsored|trending|difficulty level|icon\w*|menu|arrow|avatar|communities)\b")
# Practice quizzes next to real interview questions ("Here's your problem of the day", "Skill covered: …").
_QUIZ = re.compile(r"(?i)problem of the day|skill covered|practice (?:question|problem)|choose the correct|take the quiz|poll\b")
# "asked in Accenture" above a question: the site listing another company's questions next to this one's.
_ASKED_IN = re.compile(r"(?i)\basked (?:in|at|by)\s+(.{2,80})$")
_ANSWER_LEAD = re.compile(r"(?i)^(?:answer|ans|a)\s*[:.\-]\s*")
# A section heading run into the question on pages without line breaks ("TCS Data Analyst Interview Questions What is …").
_HEADING = re.compile(r"(?i)^.*\binterview questions?\b\s*[:\-–]?\s*(?=[A-Z])")
# Text after a question that is really the next list item or a heading, not an answer to it.
_NOT_ANSWER = re.compile(r"^(?:\d{1,3}\s*[.)]\s|Q\s*\d*\s*[.:]|Describe|Explain|Write|Tell me|Walk me|Give|Given|Define|"
                         r"Compare|Discuss|Design|Implement|What |How |Why |Which )|(?i:\binterview questions?\b)|[-:–]$")
# A real question asks something; forum and news titles ("TCS reaching out to ex-employees?") often don't.
_ASKS = re.compile(r"(?i)\b(?:what|how|why|when|where|which|who|whom|whose|can|could|do|does|did|is|are|was|were|have|has|"
                   r"will|would|should|explain|describe|tell|walk|difference)\b")
# Where the next question starts inside an answer's text: "… sample. 3. Define structured data.", "> 3. “Walk me …",
# "Q4. What …". Numbered points that are part of the answer ("1. Descriptive 2. Diagnostic") don't start with one of
# these words, so they stay.
_NEXT_ITEM = re.compile(r"(?:^|\s)(?:>\s*)?(?:Q(?:uestion)?\s*\d{1,3}\s*[.:)\-]|\d{1,3}\s*[.)])\s*[“\"‘']?\s*"
                        r"(?=(?:What|How|Why|Which|When|Where|Who|Describe|Explain|Define|Write|Tell|Walk|Give|Given|"
                        r"Compare|Discuss|Design|Implement|Can|Could|Do|Does|Is|Are|List|Name|Differentiate|"
                        r"Distinguish|State|Mention|Have|Suppose|Imagine)\b)")
# A quoted list of other questions ("> 3. “Walk me …”") or text that starts in the middle of something.
_ANSWER_START_JUNK = re.compile(r"^[\s”\"’'>)\]:;,.\-–—]+")
# Page furniture glued to the end of an answer: "… pipelines Answered by", "… Read more", "View 3 more answers".
_ANSWER_TAIL = re.compile(r"(?i)\s*\b(?:answered by|asked by|read more|read full answer|view (?:full |all |\d+ more )?answers?|"
                          r"show more|see more|continue reading|was this (?:answer )?helpful|helpful\s*\?|upvote|"
                          r"report this|add (?:your )?answer)\b[^.!?]{0,40}$")
# A site's shortened preview: "… extraction, transformation, and loading....", "… requiring…".
_CUT_OFF = re.compile(r"(?:\.{3,}|…)\s*$")
ANSWER_CAP = 1500  # characters; longer answers end at the last full sentence that fits
MAX_PER_PAGE = 25
# Raised when the way pages are read changes, so results saved by an older reader (with menu text as "answers")
# are searched again instead of being shown.
READER = 3


def _clean_question(question):
    """Drop a heading or an emoji/bullet list marker that ended up in front of the question."""
    marks = [i for i, ch in enumerate(question) if unicodedata.category(ch) == "So" or ch in "•▪►|"]
    if marks:
        question = question[marks[-1] + 1:].strip()
    return _HEADING.sub("", question)


def _page_text(text):
    """The page's text with Tavily's picture markers turned into line breaks, so menus fall apart into short lines."""
    return _IMAGE.sub("\n", text or "")


def _junk_line(line):
    """A line of page furniture: no lowercase at all ("AMBITIONBOX COMMUNITIES", "0"), or a short button/label line."""
    if not re.search(r"[a-z]", line):
        return True
    return len(line.split()) <= 8 and bool(_FURNITURE.search(line))


def bad_question(question):
    """A forum writer asking about themself, or a fragment of a sentence that quotes a question
    ('Answers questions such as "What happened?') rather than a question of its own."""
    if _FIRST_PERSON.search(question):
        return True
    return question.count("“") != question.count("”") or question.count('"') % 2 == 1


def cut_off(answer):
    """True when an answer is a site's shortened preview ("… and loading....") rather than the whole answer."""
    return bool(answer) and bool(_CUT_OFF.search(answer))


def _drop_heading_tail(text):
    """Drops a section heading left at the end ("… large enough sample. Statistical and Mathematical Concepts")."""
    end = max(text.rfind(". "), text.rfind("? "), text.rfind("! "))
    if end <= 0:
        return text
    tail = text[end + 2:].split()
    if tail and len(tail) <= 8 and sum(w[:1].isupper() or not w[:1].isalpha() for w in tail) >= len(tail) * 0.75 \
            and not re.search(r"[.!?:)”\"]$", tail[-1]):
        return text[:end + 1]
    return text


def fit(text, limit=ANSWER_CAP):
    """At most `limit` characters, ending at a full sentence (or at least a whole word), never mid-word.
    Also used for practice feedback lines."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > limit // 3 else cut.rsplit(" ", 1)[0]


def tidy_answer(answer):
    """An answer cleaned of what a page glues around it: a stray quote or the rest of a question list in front, the
    next numbered question and furniture ("Answered by", "Read more") after. None when nothing usable is left.
    Used on new answers and to repair saved ones."""
    answer = _ANSWER_START_JUNK.sub("", " ".join(str(answer or "").split()))
    answer = _ANSWER_LEAD.sub("", answer)
    if answer.startswith("("):  # "(Python/statistics round) > 3. …": a note on the question before, not an answer
        answer = _ANSWER_START_JUNK.sub("", re.sub(r"^\([^()]{1,40}\)", "", answer))
    nxt = _NEXT_ITEM.search(answer)
    if nxt:
        if nxt.start() == 0:
            return None  # it is the next question
        answer = _drop_heading_tail(answer[:nxt.start()].rstrip())
    answer = _ANSWER_TAIL.sub("", answer).strip()
    answer = fit(answer)
    words = answer.split()
    if len(answer) < 40 or _NOT_ANSWER.search(answer) or not answer[:1].isalnum():
        return None
    if sum(w[:1].islower() for w in words) < len(words) * 0.4:
        return None  # mostly Capitalised Words: a menu or a list of links, not a sentence
    return answer


def _answer_text(chunk):
    """The answer written under a question: the prose lines that follow it, up to the first line of page furniture
    or the next numbered question.

    Returns None when what follows isn't an answer (a menu, a forum post's header, the next list item).
    """
    kept = []
    for line in _ANSWER_LEAD.sub("", _ANSWER_START_JUNK.sub("", chunk or "")).split("\n"):
        line = line.strip()
        if not line:
            continue
        if _junk_line(line) or (kept and line.startswith(">")):
            break  # furniture, or a quoted list of other questions
        kept.append(line)
    return tidy_answer(" ".join(kept))


def _other_company(asked_in, company):
    """True when a site labels a question as asked in a different company from the one searched for."""
    theirs, ours = normalize.company_key(asked_in), normalize.company_key(company or "")
    if not company or not theirs or not ours:
        return False
    initials = "".join(w[0] for w in ours.split())
    return not (theirs == ours or theirs in ours or ours in theirs or theirs == initials)


def _questions_from_page(url, text, company=None, answers=True):
    """Interview questions written on the page, each with the page's own answer when one follows it.

    Read straight from the page's text, so nothing can be invented; the AI is only needed when a page has none.
    `answers=False` for a search preview, whose text after a question is a cut-off fragment, not an answer.
    """
    text = "\n" + _page_text(text)[:60000]
    found, seen = [], set()
    matches = list(_QUESTION.finditer(text))
    for i, match in enumerate(matches):
        question = _clean_question(" ".join(match.group("q").split()))
        if (not question[:1].isupper() or not 5 <= len(question.split()) <= 40 or _NOT_INTERVIEW.search(question)
                or bad_question(question) or not _ASKS.search(question)):
            continue
        above = [line.strip() for line in text[max(0, match.start() - 200):match.start()].split("\n") if line.strip()]
        asked_in = _ASKED_IN.search(above[-1]) if above else None
        if asked_in and _other_company(asked_in.group(1), company):
            continue
        if any(_QUIZ.search(line) for line in above[-3:]):
            continue
        key = _norm(question)
        if key in seen:
            continue
        seen.add(key)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        answer = _answer_text(text[match.end():min(end, match.end() + 4000)]) if answers else None
        found.append({"question": question, "answer": answer, "answer_source": "source" if answer else None,
                      "sources": [{"url": url, "site": _site(url)}]})
        if len(found) >= MAX_PER_PAGE:
            break
    return found


FULL_TEXT = 1500  # characters; less than this is only a search preview


def _read_empty_pages(pages, key):
    """Tavily's search sends many pages without their text (only a 2-line preview). They are read in two free-or-cheap
    ways: one Tavily Extract request (1 credit), then JobHunt opening the rest itself. Tested live 2026-09-25: Extract
    reads Credosystemz only sometimes and never Glassdoor or AmbitionBox, while a plain visit reads those two."""
    _extract([p for p in pages if len(p["text"]) < FULL_TEXT], key, "basic")
    empty = [p for p in pages if len(p["text"]) < FULL_TEXT]
    if empty:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(_read_directly, empty))


def _extract(pages, key, depth):
    """Tavily Extract for up to EXTRACT_MAX pages. Basic costs 1 credit per 5 pages read, advanced 2."""
    pages = pages[:EXTRACT_MAX]
    if not pages or usage()["tavily_month"] >= TAVILY_MONTHLY_CAP:
        return
    try:
        resp = requests.post(TAVILY_EXTRACT_URL, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT, json={
            "urls": [p["url"] for p in pages], "extract_depth": depth, "format": "text", "timeout": 30})
    except requests.RequestException:
        return
    if resp.status_code >= 400:
        return
    results = resp.json().get("results") or []
    for _ in range((2 if depth == "advanced" else 1) if results else 0):
        _count("tavily")  # nothing read costs nothing
    by_url = {p["url"]: p for p in pages}
    for result in results:
        page = by_url.get(normalize.safe_url(result.get("url")))
        text = (result.get("raw_content") or "").strip()
        if page is not None and len(text) > len(page["text"]):
            page["text"] = text


def _read_directly(page):
    """Opens the page like a browser would (public addresses only, at most 2 MB) and keeps its visible text."""
    html_text = _open(page["url"])
    if html_text is None:
        return
    text = _visible_text(html_text)[1]
    if len(text) >= FULL_TEXT and len(text) > len(page["text"]):
        page["text"] = text


def _stems(words):
    return [w[:5] if len(w) > 5 else w for w in words]


def _about_role(page, title):
    """True when the page's title, address or preview names every field word of the job title.

    "Data Science Engineer" needs "data" and "scien…" (science, scientist); role words like engineer or analyst are
    left out, since a "Data Scientist" page fits a "Data Science Engineer" search.
    """
    words = [w for w in re.findall(r"[a-z0-9+#]+", title.lower()) if w not in _ROLE_WORDS]
    where = " ".join((page["title"], page["url"].replace("-", " ").replace("_", " "), page["snippet"])).lower()
    return all(re.search(r"(?<![a-z0-9])" + re.escape(stem), where) for stem in _stems(words))


def _mentions_company(text, company):
    """True when the page names the company, by name or initials ("TCS" for Tata Consultancy Services)."""
    names = {normalize.company_key(company)}
    words = [w for w in normalize.slug(company).split() if w not in ("and", "of", "the")]
    if len(words) > 1:
        names.add("".join(w[0] for w in words))
    low = normalize.slug(text)
    return any(re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", low) for n in names if n)


def _questions_from(pages, company):
    # Only a page's own text can hold answers; after a question in a search preview comes a cut-off fragment.
    return _take_turns([_questions_from_page(p["url"], p["body"], company, answers=bool(p["text"])) for p in pages])


def _take_turns(lists):
    """Questions from several pages, one from each page in turn, so the first 30 aren't all from one long list."""
    out = []
    for i in range(max((len(items) for items in lists), default=0)):
        out.extend(items[i] for items in lists if i < len(items))
    return out


def _query(title, company, round_no):
    """The search wording for this search of a title (or company + title): a different angle each time, so that
    searching again finds other pages instead of the same eight."""
    variants = COMPANY_QUERIES if company else ROLE_QUERIES
    return variants[round_no % len(variants)].format(title=title, company=company)


def _from_tavily(title, company, key, steps, round_no=0, seen=None):
    """`seen`: pages read by earlier searches of this title; they are skipped (and this search's pages added)."""
    if usage()["tavily_month"] >= TAVILY_MONTHLY_CAP:
        raise SearchError(f"Tavily's {TAVILY_MONTHLY_CAP} free credits for this month are used up.")
    seen = set() if seen is None else seen
    query = _query(title, company, round_no)
    try:
        resp = requests.post(TAVILY_URL, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT, json={
            "query": query, "search_depth": "basic", "max_results": 12 if seen else 8, "include_raw_content": "text",
            "country": "india"})
    except requests.RequestException as exc:
        raise SearchError(f"Could not reach Tavily ({exc.__class__.__name__}).") from exc
    if resp.status_code in (401, 403):
        raise SearchError("Tavily did not accept its API key. Check it on the Settings tab.")
    if resp.status_code == 429 or resp.status_code == 432:
        raise SearchError("Tavily's free searches are used up for now.")
    if resp.status_code >= 400:
        raise SearchError(f"Tavily failed (HTTP {resp.status_code}).")
    _count("tavily")
    pages = []
    for result in resp.json().get("results") or []:
        url = normalize.safe_url(result.get("url"))
        snippet = (result.get("content") or "").strip()
        if url and url not in seen and (result.get("raw_content") or snippet):
            pages.append({"url": url, "title": (result.get("title") or "").strip(), "snippet": snippet,
                          "text": (result.get("raw_content") or "").strip()})
    pages = pages[:8]  # the extra results asked for only stand in for pages already read
    seen.update(p["url"] for p in pages)
    searches = [{"query": query, "url": f"https://www.google.com/search?q={quote_plus(query)}"}]
    _read_empty_pages(pages, key)
    for page in pages:
        page["body"] = page["text"] or page["snippet"]  # a page nobody could read still has its search preview
    if company:
        pages = [p for p in pages if _mentions_company(" ".join((p["title"], p["url"], p["snippet"], p["text"])), company)]
    if not pages:
        return [], "Tavily", searches

    # Pages about this exact role come first. If they are still only previews, Tavily's stronger reader (2 credits)
    # tries them. Near matches (a "Data Engineer" list for a "Data Science Engineer" search) only top the list up.
    exact = [p for p in pages if _about_role(p, title)]
    near = [p for p in pages if p not in exact]
    kept = _questions_from(exact, company)
    unread = [p for p in exact if len(p["text"]) < FULL_TEXT]
    if len(kept) < ENOUGH_EXACT and unread:
        _extract(unread, key, "advanced")
        for page in unread:
            page["body"] = page["text"] or page["snippet"]
        kept = _questions_from(exact, company)
    if len(kept) < ENOUGH_EXACT:
        kept += _questions_from(near, company)[:ENOUGH_EXACT - len(kept)]
    if len(kept) >= 5:
        return kept, "Tavily (questions read straight from the pages)", searches

    # Pages that describe questions in prose instead of listing them: the AI picks them out, and each one is then
    # checked against the page's full text so nothing invented gets through. Menus are left out of what it reads.
    def readable(text):
        return "\n".join(line.strip() for line in _page_text(text).split("\n") if line.strip() and not _junk_line(line.strip()))

    brief = "\n\n".join(f"PAGE {i + 1} — {p['url']}\n{p['snippet']}\n{readable(p['body'])[:3500]}" for i, p in enumerate(pages))
    try:
        data, model = ai.chat_json([{"role": "system", "content": EXTRACT_RULES}, {"role": "user", "content": brief}],
                                   steps, schema=EXTRACT_SCHEMA, max_tokens=6000)
    except ai.AIError:
        return kept, "Tavily", searches
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        question = " ".join(str(item.get("question") or "").split())[:400]
        homes = [p["url"] for p in pages if question and _found_in(question, p["body"])]
        if not homes or bad_question(question) or _NOT_INTERVIEW.search(question):
            continue  # on none of the pages (the AI made it up), or not an interview question
        answer = _answer_text(str(item.get("answer") or ""))
        kept.append({"question": question, "answer": answer, "answer_source": "source" if answer else None,
                     "sources": [{"url": url, "site": _site(url)} for url in homes]})
    return kept, f"Tavily + {model}", searches


# ---------- Merging, verifying, answering ----------

def merge(items):
    """Joins the same question found on several sites; 2 or more different sites makes it "verified"."""
    merged = []
    for item in items:
        match = _twin(item, merged)
        if match is None:
            merged.append({**item, "sources": list(item.get("sources") or [])})
            continue
        _absorb(match, item)
    for m in merged:
        _count_sites(m)
    merged.sort(key=lambda m: (not m["verified"], -len(m["sites"])))
    return merged[:MAX_QUESTIONS]


def _twin(item, questions):
    """The question in `questions` that asks the same thing as `item`, worded almost the same, or None."""
    key = _norm(item["question"])
    return next((q for q in questions if difflib.SequenceMatcher(None, _norm(q["question"]), key).ratio() >= 0.85), None)


def _better_answer(new, old):
    """True when `new` should replace `old`: there was none, or `old` is only an AI draft or a cut-off preview and
    `new` is a whole answer from a page."""
    if not new.get("answer"):
        return False
    if not old.get("answer"):
        return True
    if new.get("answer_source") != "source":
        return False
    return old.get("answer_source") != "source" or (cut_off(old["answer"]) and not cut_off(new["answer"]))


def _absorb(match, item):
    """Adds `item`'s sources (and its answer, when it is better) to the same question found before."""
    for source in item.get("sources") or []:
        if source not in match["sources"]:
            match["sources"].append(source)
    if _better_answer(item, match):
        match["answer"], match["answer_source"] = item["answer"], item.get("answer_source")


# Links next to a question that lead to its whole answer.
_MORE_LINK = re.compile(r"(?i)\b(?:read more|read full|view (?:full |all )?answers?|see (?:the )?answers?|show (?:more|answer)|"
                        r"more answers?|full answer|continue reading)\b")
FULL_ANSWER_PAGES = 12  # pages opened per search (or per saved set being repaired) to finish cut-off answers


def _visible_text(html_text):
    """(parsed page, its visible text one line per block), without scripts, menus and footers."""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
        tag.decompose()
    return soup, "\n".join(line.strip() for line in soup.get_text("\n").split("\n") if line.strip())


def _whole_answer_on(url, text, question):
    """The question's answer as read from this page's text, if the page has it whole."""
    for item in _questions_from_page(url, text):
        if item.get("answer") and not cut_off(item["answer"]) and \
                difflib.SequenceMatcher(None, _norm(item["question"]), _norm(question)).ratio() >= 0.85:
            return item["answer"]
    return None


def _open(url):
    """The page's HTML, opened like a browser would (public addresses only, at most 2 MB), or None."""
    try:
        _, status, html_text = ats._get_public_page(url, 20)
    except (ats.SourceError, requests.RequestException):
        return None
    return html_text if status == 200 else None


def full_answer(question, url):
    """The whole answer to a question whose page showed only a preview ("… and loading...."). Opens the page, and
    then the link beside the question that leads to its full answer (the question itself, "Read more", "View
    answer"), on the same site only. None when neither has it."""
    html_text = _open(url)
    if html_text is None:
        return None
    soup, text = _visible_text(html_text)
    answer = _whole_answer_on(url, text, question)
    if answer:
        return answer
    key = _norm(question)
    spot = None
    for tag in soup.find_all(["a", "h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "strong", "b", "div", "li"]):
        own = _norm(tag.get_text(" "))
        if own and len(own) <= len(key) * 1.5 and difflib.SequenceMatcher(None, own, key).ratio() >= 0.85:
            spot = tag
            break
    if spot is None:
        return None
    links, node = [], spot
    for _ in range(6):  # the question's own link first, then "Read more" links in ever larger boxes around it
        if node is None:
            break
        anchors = [node] if node.name == "a" else []
        anchors += node.find_all("a", href=True) if hasattr(node, "find_all") else []
        for a in anchors:
            href = a.get("href")
            label = " ".join(a.get_text(" ").split())
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            if a is spot or _MORE_LINK.search(label) or (label and _norm(label) == key):
                link = normalize.safe_url(urljoin(url, href))
                if link and link != url and _site(link) == _site(url) and link not in links:
                    links.append(link)
        if links:
            break
        node = node.parent
    for link in links[:2]:
        page = _open(link)
        if page is not None:
            answer = _whole_answer_on(link, _visible_text(page)[1], question)
            if answer:
                return answer
    return None


def _finish_cut_off(questions):
    """Replaces site previews that stop mid-answer with the whole answer from the source page; when no page has
    it, the preview is removed so an AI draft (clearly labelled) takes its place."""
    todo = [q for q in questions if q.get("answer_source") == "source" and cut_off(q.get("answer"))]

    def finish(question):
        for source in (question.get("sources") or [])[:2]:
            whole = full_answer(question["question"], source.get("url"))
            if whole:
                return whole
        return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        for question, whole in zip(todo[:FULL_ANSWER_PAGES], pool.map(finish, todo[:FULL_ANSWER_PAGES])):
            question["answer"] = whole
            question["answer_source"] = "source" if whole else None
    for question in todo[FULL_ANSWER_PAGES:]:
        question["answer"], question["answer_source"] = None, None


def _count_sites(question):
    question["sites"] = sorted({s["site"] for s in question["sources"] if s.get("site")})
    question["verified"] = len(question["sites"]) >= 2


ANSWER_RULES = """You help a job seeker prepare answers to interview questions. For each numbered question write a
short, natural model answer (2-4 sentences) the candidate could give. For questions about the candidate's own
experience, use only facts from their resume JSON; if the resume doesn't cover it, give a short structure to fill in
instead of inventing anything. Answer EVERY question: one entry per question number, in order.
Answer with only this JSON: {"answers": [{"n": 1, "answer": "..."}, {"n": 2, "answer": "..."}]}"""
ANSWER_BATCH = 8
ANSWER_PARALLEL = 4  # free NVIDIA/OpenRouter keys handled 3-4 requests at once in the model tests
ANSWER_TIMEOUT = 60  # seconds a model may stay silent before the next one is tried (one stalled for 3 minutes live)

ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["answers"],
    "properties": {"answers": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["n", "answer"],
        "properties": {"n": {"type": "integer"}, "answer": {"type": "string"}}}}},
}


def draft_answers(questions, title, profile, steps):
    """Fills in answers the sources didn't give, labelled as AI-drafted. Returns (model used, problem)."""
    missing = [q for q in questions if not q.get("answer")]
    if not missing:
        return None, None
    if not ai.usable_steps(steps):
        return None, "add an AI model on the Settings tab to get drafted answers"
    resume_json = json.dumps(profile or {}, ensure_ascii=False)

    def one_batch(batch):
        listing = "\n".join(f"{n}. {q['question']}" for n, q in enumerate(batch, 1))
        content = (f"Role: {title}\n\n{len(batch)} questions, answer all {len(batch)}:\n{listing}\n\n"
                   f"The candidate's resume as JSON:\n{resume_json}")
        data, model = ai.chat_json([{"role": "system", "content": ANSWER_RULES}, {"role": "user", "content": content}],
                                   steps, schema=ANSWER_SCHEMA, max_tokens=6000, timeout=ANSWER_TIMEOUT)
        for entry in data.get("answers") or []:
            try:
                question = batch[int(entry.get("n")) - 1]
            except (TypeError, ValueError, IndexError):
                continue
            answer = " ".join(str(entry.get("answer") or "").split())[:1500]
            if answer:
                question["answer"], question["answer_source"] = answer, "ai"
        return model

    model, problem = None, None
    # Small batches written at the same time, and one more try for any a model skipped: free models often answer
    # only the first few, and a stalled model is left after ANSWER_TIMEOUT seconds for the next one.
    started = time.monotonic()
    for attempt in range(2):
        if attempt and time.monotonic() - started > ANSWER_TIMEOUT * 1.5:
            break  # the first pass was slow; leave the rest unanswered rather than keep you waiting
        todo = [q for q in missing if not q.get("answer")]
        batches = [todo[start:start + ANSWER_BATCH] for start in range(0, len(todo), ANSWER_BATCH)]
        with ThreadPoolExecutor(max_workers=ANSWER_PARALLEL) as pool:
            for future in [pool.submit(one_batch, batch) for batch in batches]:
                try:
                    model = future.result() or model
                except ai.AIError as exc:
                    problem = f"answers could not be drafted: {exc}"
        if problem or all(q.get("answer") for q in missing):
            break
    return model, (problem if model is None else None)


def saved_for(title, company=None):
    """What is saved for a title (or company + title), or None. Results from an older page reader don't count."""
    saved = db.get_interview_qa(scope_for(title, company))
    return saved if saved and saved.get("reader") == READER else None


def all_saved():
    """Every saved set of questions: {"titles": [...] for job-title searches, "companies": [...] for company ones}."""
    out = {"titles": [], "companies": []}
    for row in db.list_interview_qa():
        if row.get("reader") != READER or not row.get("questions"):
            continue
        entry = {"title": row["title"], "company": row.get("company"), "questions": row["questions"],
                 "saved_at": row["saved_at"], "searches": row.get("searches", 1)}
        out["companies" if row.get("company") else "titles"].append(entry)
    for group in out.values():
        group.sort(key=lambda e: ((e["company"] or "").lower(), e["title"].lower()))
    return out


# Raised when the answer checks change, so saved questions are cleaned again (in place, without a new search).
CLEANER = 1
OLD_ANSWER_CAP = 600  # where readers before CLEANER 1 cut answers off


def repair_saved(steps, profile):
    """Cleans questions saved before the current answer checks: drops questions the writer asked about themself
    ("What are the tools I used…"), trims answers glued to the next question or to page furniture, replaces cut-off
    previews with the whole answer from the source page, and has the AI draft (labelled) what is still missing.
    The questions keep their wording, so practice history stays with them, and the saved date doesn't change.
    Returns the number of saved sets cleaned."""
    cleaned = 0
    for row in db.list_interview_qa():
        if row.get("reader") != READER or row.get("cleaned") == CLEANER:
            continue
        scope = row.pop("scope", None) or scope_for(row["title"], row.get("company"))
        row.pop("saved_at", None)
        before = json.dumps(row, sort_keys=True)
        questions = []
        for question in row.get("questions") or []:
            if bad_question(question.get("question") or ""):
                continue
            if question.get("answer_source") == "source" and question.get("answer"):
                raw = question["answer"]
                # Earlier readers stopped every answer at 600 characters, often mid-sentence ("… requiring ").
                capped = len(raw) >= OLD_ANSWER_CAP - 1 and not re.search(r"[.!?)”\"]\s*$", raw)
                was_cut = cut_off(raw) or capped
                tidy = tidy_answer(raw)
                if tidy and capped:
                    end = max(tidy.rfind(". "), tidy.rfind("? "), tidy.rfind("! "), tidy.rfind("."))
                    if end > len(tidy) // 3:
                        question["_sentences"] = tidy[:end + 1]  # the whole sentences, if no page has the rest
                if tidy and was_cut and not cut_off(tidy):
                    tidy += "…"  # still only a preview; the mark makes the whole answer be looked for below
                question["answer"] = tidy
                question["answer_source"] = "source" if tidy else None
            questions.append(question)
        _finish_cut_off(questions)
        for question in questions:
            sentences = question.pop("_sentences", None)
            if sentences and not question.get("answer"):
                question["answer"], question["answer_source"] = sentences, "source"
        problem = None
        try:
            model, problem = draft_answers(questions, row["title"], profile, steps)
        except Exception as exc:  # the AI may be busy; the questions are still saved cleaned, without those answers
            model, problem = None, f"answers could not be drafted: {exc}"
        row.update(questions=questions, cleaned=CLEANER, answers_by=model or row.get("answers_by"),
                   answers_problem=problem)
        with db._lock:  # a search of the same set may have saved meanwhile; then this is left for the next start
            current = db.get_interview_qa(scope) or {}
            current.pop("saved_at", None)
            if json.dumps(current, sort_keys=True) != before:
                continue
            db.save_interview_qa(scope, row, keep_date=True)
        cleaned += 1
    return cleaned


def find(title, company, steps, profile, refresh=False):
    """Interview questions for a role (and company).

    Without refresh, what is saved comes back as it is. A search (refresh, or nothing saved yet) keeps everything saved
    and adds only questions not saved before: it uses new search wording, skips pages already read, and drops
    repeats. The reply lists the new questions first, marked "new", then the saved ones; `new_count` may be 0.
    """
    title = " ".join((title or "").split())[:120]
    company = " ".join((company or "").split())[:120] or None
    if not title:
        raise SearchError("Pick a job title first.")
    scope = scope_for(title, company)
    saved = saved_for(title, company)
    if saved and saved["questions"] and not refresh:
        return {**saved, "from_saved": True, "new_count": None}

    gemini_key, tavily_key = db.get_secret("ai_key_gemini"), db.get_secret("tavily_key")
    if not gemini_key and not tavily_key:
        raise SearchError("Add a free Gemini key (Settings tab, Gemini card) or a Tavily key to search the web.")
    old = (saved or {}).get("questions") or []
    round_no = (saved or {}).get("searches", 1 if saved else 0)
    seen = set((saved or {}).get("read_pages") or [])
    problems, items, searched_with, queries, searched = [], [], None, [], False
    current = usage()
    if gemini_key and not current["gemini_unavailable"] and current["gemini_today"] < GEMINI_DAILY_CAP:
        try:
            items, searched_with, queries = _from_gemini(title, company, gemini_key, [q["question"] for q in old])
            searched = True
        except SearchError as exc:
            problems.append(str(exc))
    if not items and tavily_key:
        try:
            items, searched_with, queries = _from_tavily(title, company, tavily_key, steps, round_no, seen)
            searched = True
        except (SearchError, ai.AIError) as exc:
            problems.append(str(exc))
    if not searched:
        # Nothing could search at all. (A search that worked but found nothing is not an error; it is said below.)
        raise SearchError("; ".join(problems) if problems else "No web search is set up.")

    new = []
    for question in merge(items):
        twin = _twin(question, old)
        if twin is None:
            new.append(question)
        else:  # asked again on another site: it may now be verified, but it isn't new
            _absorb(twin, question)
            _count_sites(twin)
    _finish_cut_off(new)
    answer_model, answer_problem = draft_answers(new, title, profile, steps)
    today = date.today().isoformat()
    for question in new:
        question["found_on"] = today

    hint = "Try the job title without the company, or Search again later." if company else "Try a more common job title."
    if new:
        note = ""
    elif old:
        note = (f"0 new questions found: the pages this search reached had only questions already saved here. "
                f"Search again later; each search looks from a different angle.")
    else:
        note = f"0 questions found: the search worked, but the pages it found didn't list interview questions. {hint}"
    data = {"reader": READER, "cleaned": (saved or {}).get("cleaned") if old else CLEANER,
            "title": title, "company": company, "questions": old + new,
            "searched_with": searched_with, "google_searches": ((saved or {}).get("google_searches") or []) + queries,
            "answers_by": answer_model or (saved or {}).get("answers_by"), "answers_problem": answer_problem,
            "searches": round_no + 1, "read_pages": sorted(seen)[-400:]}
    stored = db.save_interview_qa(scope, data)
    if not old and not new:
        # No questions to keep, but the searching is remembered, so the next try uses other wording and other pages.
        stored["saved_at"] = None
    flagged = [{**q, "new": True} for q in new] + old
    return {**stored, "questions": flagged, "new_count": len(new), "note": note, "from_saved": False}
