"""Typed mock interviews from your saved interview questions: you type an answer, your AI service scores it out of 10
and says what worked, what to improve and how a better answer could go, using only your resume facts. Every attempt
is kept, so you can see your scores improve and retry the weak ones."""
import json
import uuid

from app import ai, db, interview, resume

RULES = """You are an interview coach helping one person prepare for a job interview in India. You get one interview
question, the person's typed answer, their resume, and sometimes an answer reported on the web for reference.

Score the typed answer from 0 to 10 for how well it would land in a real interview: it answers what was asked, is
specific (examples, tools, results from their own work), is structured (for example situation, action, result), and
is the right length to say aloud (about 1-2 minutes).

Rules you must follow:
1. The better answer may only use facts from the resume: never invent employers, projects, numbers, tools, results
   or certificates. Where a strong answer needs something the resume doesn't show, say so in "improve" instead.
2. The reported answer is only a hint about what interviewers look for; don't copy facts from it into the better
   answer unless the resume has them.
3. Be direct and kind. At most 3 strengths and at most 4 things to improve, each one short sentence.
4. An empty or off-topic answer scores 0-2.

Answer with only this JSON:
{"score": 0, "strengths": [""], "improve": [""], "better_answer": "about 120-180 words, first person"}"""
SCHEMA = resume._object(score={"type": "integer"}, strengths=resume._TEXTS, improve=resume._TEXTS,
                        better_answer=resume._STRING)
WEAK_SCORE = 6       # an answer scored below this is "weak" (Retry weak ones)
HISTORY_SHOWN = 10   # attempts per question sent to the page
MODES = ("each", "end")  # feedback after each question, or for all of them at the end
SESSIONS_SHOWN = 50


class PracticeError(Exception):
    """Something the user should see, already worded for them."""


def _saved(title, company):
    saved = interview.saved_for(title, company or None)
    if not saved or not saved.get("questions"):
        raise PracticeError("There are no saved questions for this yet. Find some first.")
    return saved


def session(title, company=""):
    """The saved questions for a job title (or company + title), each with your earlier attempts, newest last.
    Each opening of Practise is a new session, so its answers can later be compared with earlier sessions."""
    saved = _saved(title, company)
    scope = interview.scope_for(title, company or None)
    attempts = {}
    for row in db.list_practice(scope):
        attempts.setdefault(row["question"], []).append(
            {"score": row["score"], "at": row["created_at"], "answer": row["answer"], "feedback": row["feedback"]})
    return {
        "session_id": uuid.uuid4().hex,
        "title": saved["title"], "company": saved.get("company") or "", "weak_below": WEAK_SCORE,
        "questions": [{"question": q["question"], "reference": q.get("answer") or "",
                       "attempts": attempts.get(q["question"], [])[-HISTORY_SHOWN:]} for q in saved["questions"]],
    }


def _lines(value, limit):
    """At most `limit` feedback lines, each shortened at the end of a sentence, never mid-word."""
    items = value if isinstance(value, list) else [value] if value else []
    return [interview.fit(" ".join(str(item).split()), 500) for item in items if str(item).strip()][:limit]


def answer(title, company, question, typed, profile, steps, session_id=None, mode=None):
    """Scores one typed answer, keeps the attempt (with its session), and returns the feedback."""
    saved = _saved(title, company)
    match = next((q for q in saved["questions"] if q["question"] == question), None)
    if match is None:
        raise PracticeError("That question isn't in your saved questions any more. Reopen the practice window.")
    typed = (typed or "").strip()
    if not typed:
        raise PracticeError("Type your answer first.")
    if not resume.profile_is_usable(profile):
        raise PracticeError("Fill in the Resume tab first, so the feedback can use your own experience.")
    role = f"{saved['title']}" + (f" at {saved['company']}" if saved.get("company") else "")
    brief = [f"The job: {role}", f"Interview question: {question}"]
    if match.get("answer"):
        brief.append(f"An answer reported on the web (reference only): {match['answer'][:1500]}")
    brief += [f"The person's typed answer:\n{typed}", "The person's resume as JSON:\n" + json.dumps(profile, ensure_ascii=False)]
    data, model = ai.chat_json([{"role": "system", "content": RULES}, {"role": "user", "content": "\n\n".join(brief)}],
                               steps, schema=SCHEMA, max_tokens=1500, timeout=90)
    try:
        score = max(0, min(10, int(data.get("score"))))
    except (TypeError, ValueError) as exc:
        raise ai.AIError("The AI didn't give a score. Try again, or pick another model on the Settings tab.") from exc
    better = " ".join(str(data.get("better_answer") or "").split())[:2000]
    # The better answer may repeat the question's and the job's words; only claims about you must be in your details.
    known = {**profile, "about_this_question": f"{question} {role}"}
    flags = resume.verify(known, {"summary": better, "skills": [], "experience": [], "projects": []})
    feedback = {"strengths": _lines(data.get("strengths"), 3), "improve": _lines(data.get("improve"), 4),
                "better_answer": better, "flags": sorted({t for f in flags for t in f["terms"]}), "model": model}
    scope = interview.scope_for(title, company or None)
    db.add_practice(scope, question, typed[:4000], score, feedback, session_id or None,
                    mode if mode in MODES else None)
    return {"score": score, **feedback}


def _average(scores):
    scores = [s for s in scores if s is not None]
    return round(sum(scores) / len(scores), 1) if scores else None


def sessions(title, company=""):
    """Earlier practice sessions for a job title (or company + title), newest first, each with its answers, scores,
    average and the change in average from the session before it. Attempts saved before sessions existed are
    grouped by day."""
    scope = interview.scope_for(title, company or None)
    groups = {}
    for row in db.list_practice(scope):  # oldest first
        key = row.get("session_id") or f"day:{row['created_at'][:10]}"
        group = groups.setdefault(key, {"id": key, "mode": row.get("mode"), "started": row["created_at"],
                                        "ended": row["created_at"], "attempts": []})
        group["ended"] = row["created_at"]
        group["attempts"].append({"question": row["question"], "answer": row["answer"], "score": row["score"],
                                  "at": row["created_at"], "feedback": row["feedback"]})
    out, previous = [], None
    for group in sorted(groups.values(), key=lambda g: g["started"]):
        group["average"] = _average([a["score"] for a in group["attempts"]])
        group["answered"] = len(group["attempts"])
        group["change"] = (round(group["average"] - previous, 1)
                           if group["average"] is not None and previous is not None else None)
        if group["average"] is not None:
            previous = group["average"]
        out.append(group)
    out.reverse()
    return {"title": title, "company": company or "", "weak_below": WEAK_SCORE, "sessions": out[:SESSIONS_SHOWN]}
