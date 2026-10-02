"""Tailoring that keeps going until the resume reaches your ATS and human-sounding targets.

Round 1: every ticked model writes a version at the same time and the best is kept. Later rounds: the best version's
model gets specific feedback (keywords it could still use honestly, phrases that sound generated) and rewrites it.
It stops when both targets are met or the rounds run out, and keeps the best version either way. Honest versions
always beat ones with invented claims.

Stop ends the run at once: the page is freed straight away, nothing from the stopped run is saved, and the resume
tailored earlier for the same job stays exactly as it was. Model calls already sent finish in the background and
are thrown away.
"""
import copy
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime

from app import ai, db, errors, resume

PARALLEL = 4  # models writing at once in round 1; free services allow little more
STOP_CHECK = 0.5  # seconds between looks at the Stop button while models are writing

_lock = threading.Lock()
_stop = threading.Event()  # the current run's; each run gets its own, so a new run can't un-stop an old one
_run_id = 0
_status = {"running": False, "stopping": False, "stopped": False, "job_id": None, "round": 0, "rounds": 0,
           "targets": {}, "phase": "", "log": [], "result": None, "error": None, "started_at": None,
           "finished_at": None}


class _Stopped(Exception):
    """The run was stopped; its work is thrown away."""


def status():
    with _lock:
        return copy.deepcopy(_status)


def is_running():
    with _lock:
        return _status["running"]


def stop():
    """Ends the run now. Its result is discarded, so the earlier tailored resume for the job is left untouched."""
    with _lock:
        if not _status["running"]:
            return False
        _stop.set()
        _status.update(running=False, stopping=False, stopped=True, result=None, phase="",
                       finished_at=datetime.now().isoformat(timespec="seconds"))
    return True


def _update(run_id, **fields):
    """Changes the status, unless this run has been stopped or replaced by a newer one."""
    with _lock:
        if run_id != _run_id or _status["stopped"]:
            raise _Stopped()
        _status.update(fields)


def _log(run_id, entry):
    with _lock:
        if run_id != _run_id or _status["stopped"]:
            raise _Stopped()
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
    global _stop, _run_id
    with _lock:
        if _status["running"]:
            return None
        _stop = threading.Event()
        _run_id += 1
        run_id, stopped = _run_id, _stop
        _status.update(running=True, stopping=False, stopped=False, job_id=job["id"], round=0, rounds=rounds,
                       targets=targets, phase="starting…", log=[], result=None, error=None,
                       started_at=datetime.now().isoformat(timespec="seconds"), finished_at=None)
    threading.Thread(target=_run, args=(run_id, stopped, job, profile, steps, targets, rounds, keywords),
                     daemon=True).start()
    return status()


def _check(stopped):
    if stopped.is_set():
        raise _Stopped()


def _first_round(stopped, job, profile, keywords, writer_steps, messages):
    """Every model writes a version at the same time. Stop is looked at while they write, not only after."""
    candidates, failed = [], []
    pool = ThreadPoolExecutor(max_workers=PARALLEL)
    try:
        futures = {pool.submit(_write, job, profile, keywords, step, messages): step for step in writer_steps}
        pending = set(futures)
        while pending:
            _check(stopped)
            done, pending = wait(pending, timeout=STOP_CHECK, return_when=FIRST_COMPLETED)
            for future in done:
                try:
                    candidates.append(future.result())
                except (ai.AIError, resume.ResumeError) as exc:
                    failed.append(f"{futures[future]['models'][0]}: {exc}")
        _check(stopped)
    finally:
        # On Stop, calls not yet sent are cancelled; ones already sent finish in the background and are ignored.
        pool.shutdown(wait=False, cancel_futures=True)
    return candidates, failed


def _run(run_id, stopped, job, profile, steps, targets, rounds, keywords):
    best = None
    try:
        writer_steps, review_steps = writers(steps), reviewer(steps)
        _update(run_id, round=1, phase=f"{len(writer_steps)} models are each writing a version…")
        messages = resume.tailor_messages(job, profile, keywords)
        candidates, failed = _first_round(stopped, job, profile, keywords, writer_steps, messages)
        if not candidates:
            raise ai.AIError("No model could write a version: " + "; ".join(failed[:4]))
        candidates.sort(key=lambda c: (c["honest"], c["ats"]["score"]), reverse=True)
        _update(run_id, phase="checking how human the best versions sound…")
        for candidate in candidates[:3]:
            _check(stopped)
            _score_human(candidate, review_steps, targets)
        _check(stopped)
        scored = [c for c in candidates[:3] if c.get("human")] or candidates[:1]
        best = max(scored, key=lambda c: _rank(c, targets))
        _log(run_id, {**_summary(1, best, f"best of {len(candidates)} versions"
                                          + (f"; {len(failed)} models failed" if failed else "")),
                      "tried": [_summary(1, c) for c in candidates[:6]]})

        for round_no in range(2, rounds + 1):
            if _meets(best, targets):
                break
            _check(stopped)
            _update(run_id, round=round_no, phase=f"{best['model']} is improving its version…")
            messages = resume.revise_messages(job, profile, best["draft"], keywords,
                                              _feedback(best, targets, keywords, profile))
            try:
                new = _write(job, profile, keywords, best["step"], messages)
            except (ai.AIError, resume.ResumeError):
                _check(stopped)
                try:  # the best model is busy now; the others take the revision, in your order
                    new = _write(job, profile, keywords, best["step"], messages, fallback_steps=ai.usable_steps(steps))
                except (ai.AIError, resume.ResumeError) as exc:
                    _log(run_id, {"round": round_no, "note": f"no model could revise it: {exc}"})
                    break
            _check(stopped)
            _score_human(new, review_steps, targets)
            _check(stopped)
            improved = _rank(new, targets) > _rank(best, targets)
            _log(run_id, _summary(round_no, new, "better, kept" if improved else "not better, earlier version kept"))
            if improved:
                best = new
        _check(stopped)
    except _Stopped:
        return  # stop() already freed the page; nothing from this run is kept
    except Exception as exc:  # anything unexpected is reported, and the page stops waiting
        best = None if stopped.is_set() else best
        try:
            _update(run_id, error=str(exc) if isinstance(exc, (ai.AIError, resume.ResumeError))
                    else errors.hidden(exc, "Tailoring"))
        except _Stopped:
            return
    _finish(run_id, stopped, job, best, keywords, targets)


def _finish(run_id, stopped, job, best, keywords, targets):
    """Saves the best version and frees the page, but only for a run that is still current and wasn't stopped:
    the check and the save happen under the lock, so Stop pressed at the last moment still wins."""
    with _lock:
        if run_id != _run_id or stopped.is_set() or _status["stopped"]:
            return
        result = None
        if best is not None:
            result = {"draft": best["draft"], "flags": best["flags"], "ats": best["ats"], "human": best["human"],
                      "model": best["model"], "keywords": keywords, "met": _meets(best, targets), "targets": targets}
            previous = db.get_tailored(job["id"]) or {}
            db.save_tailored(job["id"], {**(previous.get("data") or {}), "draft": best["draft"], "keywords": keywords,
                                         "human": best["human"]},
                             pdf_path=previous.get("pdf_path"), ats_score=previous.get("ats_score"), model=best["model"])
        _status.update(running=False, stopping=False, stopped=False, result=result, phase="",
                       finished_at=datetime.now().isoformat(timespec="seconds"))
