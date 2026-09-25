"""Tailoring that keeps going until the resume reaches your ATS and human-sounding targets.

Round 1: every ticked model writes a version at the same time and the best is kept. Later rounds: the best version's
model gets specific feedback (keywords it could still use honestly, phrases that sound generated) and rewrites it.
It stops when both targets are met or the rounds run out, and keeps the best version either way. Honest versions
always beat ones with invented claims.
"""
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app import ai, db, errors, resume

PARALLEL = 4  # models writing at once in round 1; free services allow little more

_lock = threading.Lock()
_stop = threading.Event()
_status = {"running": False, "stopping": False, "stopped": False, "job_id": None, "round": 0, "rounds": 0,
           "targets": {}, "phase": "", "log": [], "result": None, "error": None, "started_at": None,
           "finished_at": None}


def status():
    with _lock:
        return copy.deepcopy(_status)


def is_running():
    with _lock:
        return _status["running"]


def stop():
    with _lock:
        if not _status["running"]:
            return False
        _status["stopping"] = True
    _stop.set()
    return True


def _update(**fields):
    with _lock:
        _status.update(fields)


def _log(entry):
    with _lock:
        _status["log"].append(entry)


def writers(steps):
    """Every ticked model on every usable service, each as its own one-model step, in your order."""
    return [{**step, "models": [model]} for step in ai.usable_steps(steps) for model in step["models"]]


def reviewer(steps):
    """Always the same model judges how human the wording sounds, so scores compare between rounds."""
    usable = ai.usable_steps(steps)
    return [{**usable[0], "models": usable[0]["models"][:1]}] if usable else []


def _write(job, profile, keywords, step, messages, fallback_steps=None):
    """One version from one model (or, when fallback_steps are given, from the first of them that answers)."""
    data, model = ai.chat_json(messages, fallback_steps or [step], schema=resume.TAILOR_SCHEMA)
    draft = resume.clean_draft(data, profile)
    flags = resume.verify(profile, draft, keywords)
    return {"draft": draft, "flags": flags, "honest": not flags, "model": model, "step": step,
            "ats": resume.ats_report(profile, draft, keywords), "human": None}


def _meets(candidate, targets):
    human = (candidate.get("human") or {}).get("score", 0)
    return (candidate["honest"] and (not targets["ats"] or candidate["ats"]["score"] >= targets["ats"])
            and (not targets["human"] or human >= targets["human"]))


def _rank(candidate, targets):
    """Higher is better: honest first, then how close the weaker score is to its target, then the total."""
    ats = candidate["ats"]["score"]
    human = (candidate.get("human") or {}).get("score", 0)
    parts = []
    if targets["ats"]:
        parts.append(min(1.0, ats / targets["ats"]))
    if targets["human"]:
        parts.append(min(1.0, human / targets["human"]))
    return (candidate["honest"], min(parts) if parts else 1.0, ats + human)


def _feedback(candidate, targets, keywords, profile):
    lines = []
    if targets["ats"] and candidate["ats"]["score"] < targets["ats"]:
        supported = set(resume.ats_ceiling(profile, keywords)["have"])
        unused = [k for k in candidate["ats"]["missing"] if k in supported]
        lines.append(f"ATS score is {candidate['ats']['score']}, target {targets['ats']}.")
        if unused:
            lines.append("Keywords from the advert that the resume supports but this version doesn't use yet: "
                         + ", ".join(unused) + ". Work them into the relevant bullets or skills.")
    human = candidate.get("human") or {}
    if targets["human"] and human.get("score", 0) < targets["human"]:
        lines.append(f"Human-sounding score is {human.get('score', 0)}, target {targets['human']}.")
        if human.get("phrases"):
            lines.append("Rewrite these phrases in plain, specific words: " + "; ".join(human["phrases"]) + ".")
        lines += human.get("notes", [])
    if candidate["ats"]["words"] > resume.ONE_PAGE_WORDS:
        lines.append(f"It is {candidate['ats']['words']} words, too long for one page (at most about "
                     f"{resume.ONE_PAGE_WORDS}). Cut the bullets that matter least for this job.")
    if candidate["flags"]:
        lines.append("These parts are not in the resume and must be removed or fixed: "
                     + "; ".join(f"{f['where']}: {', '.join(f['terms'])}" for f in candidate["flags"]) + ".")
    return "\n".join(lines) or "Tighten the wording."


def _score_human(candidate, review_steps, targets):
    # The AI reviewer only runs when there is a human-sounding target; otherwise the free built-in check is enough.
    candidate["human"] = resume.human_score(candidate["draft"], review_steps if targets["human"] else [])


def _summary(round_no, candidate, extra=""):
    human = (candidate.get("human") or {}).get("score")
    return {"round": round_no, "model": candidate["model"], "ats": candidate["ats"]["score"], "human": human,
            "honest": candidate["honest"], "note": extra}


def start(job, profile, steps, targets, rounds, check_ceiling=True):
    """Starts in the background and returns the status. If the ATS target is above what your details can honestly
    reach, returns {"needs_skills": ...} instead, so you can say which missing skills you really have."""
    if not resume.profile_is_usable(profile):
        raise resume.ResumeError("Fill in the Resume tab first (at least your name and one job or project).")
    keywords = resume.job_keywords(job)
    if check_ceiling and targets["ats"]:
        ceiling = resume.ats_ceiling(profile, keywords)
        if ceiling["best_score"] < targets["ats"]:
            return {"running": False, "needs_skills": True, "ceiling": ceiling, "target": targets["ats"]}
    if not writers(steps):
        raise ai.AIError("Add an API key and tick at least one model for one of the AI services on the Settings tab.")
    with _lock:
        if _status["running"]:
            return None
        _stop.clear()
        _status.update(running=True, stopping=False, stopped=False, job_id=job["id"], round=0, rounds=rounds,
                       targets=targets, phase="starting…", log=[], result=None, error=None,
                       started_at=datetime.now().isoformat(timespec="seconds"), finished_at=None)
    threading.Thread(target=_run, args=(job, profile, steps, targets, rounds, keywords), daemon=True).start()
    return status()


def _run(job, profile, steps, targets, rounds, keywords):
    best = None
    try:
        writer_steps, review_steps = writers(steps), reviewer(steps)
        _update(round=1, phase=f"{len(writer_steps)} models are each writing a version…")
        candidates, failed = [], []
        messages = resume.tailor_messages(job, profile, keywords)
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            futures = {pool.submit(_write, job, profile, keywords, step, messages): step for step in writer_steps}
            for future, step in futures.items():
                try:
                    candidates.append(future.result())
                except (ai.AIError, resume.ResumeError) as exc:
                    failed.append(f"{step['models'][0]}: {exc}")
        if not candidates:
            raise ai.AIError("No model could write a version: " + "; ".join(failed[:4]))
        candidates.sort(key=lambda c: (c["honest"], c["ats"]["score"]), reverse=True)
        _update(phase="checking how human the best versions sound…")
        for candidate in candidates[:3]:
            if _stop.is_set():
                break
            _score_human(candidate, review_steps, targets)
        scored = [c for c in candidates[:3] if c.get("human")] or candidates[:1]
        best = max(scored, key=lambda c: _rank(c, targets))
        _log({**_summary(1, best, f"best of {len(candidates)} versions"
                                  + (f"; {len(failed)} models failed" if failed else "")),
              "tried": [_summary(1, c) for c in candidates[:6]]})

        for round_no in range(2, rounds + 1):
            if _meets(best, targets) or _stop.is_set():
                break
            _update(round=round_no, phase=f"{best['model']} is improving its version…")
            messages = resume.revise_messages(job, profile, best["draft"], keywords,
                                              _feedback(best, targets, keywords, profile))
            try:
                new = _write(job, profile, keywords, best["step"], messages)
            except (ai.AIError, resume.ResumeError):
                try:  # the best model is busy now; the others take the revision, in your order
                    new = _write(job, profile, keywords, best["step"], messages, fallback_steps=ai.usable_steps(steps))
                except (ai.AIError, resume.ResumeError) as exc:
                    _log({"round": round_no, "note": f"no model could revise it: {exc}"})
                    break
            _score_human(new, review_steps, targets)
            improved = _rank(new, targets) > _rank(best, targets)
            _log(_summary(round_no, new, "better, kept" if improved else "not better, earlier version kept"))
            if improved:
                best = new
    except Exception as exc:  # anything unexpected is reported, and the page stops waiting
        _update(error=str(exc) if isinstance(exc, (ai.AIError, resume.ResumeError)) else errors.hidden(exc, "Tailoring"))
    finally:
        result = None
        if best is not None:
            result = {"draft": best["draft"], "flags": best["flags"], "ats": best["ats"], "human": best["human"],
                      "model": best["model"], "keywords": keywords, "met": _meets(best, targets), "targets": targets}
            previous = db.get_tailored(job["id"]) or {}
            db.save_tailored(job["id"], {**(previous.get("data") or {}), "draft": best["draft"], "keywords": keywords,
                                         "human": best["human"]},
                             pdf_path=previous.get("pdf_path"), ats_score=previous.get("ats_score"), model=best["model"])
        _update(running=False, stopping=False, stopped=_stop.is_set(), result=result, phase="",
                finished_at=datetime.now().isoformat(timespec="seconds"))
