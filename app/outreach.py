"""The Referral button: a short referral request to someone at the company and a note to the recruiter, written by
your AI service from your saved resume details only, and checked like a tailored resume."""
import json
from urllib.parse import quote

from app import ai, resume

RULES = """You write two short messages for one person applying to one job, using only facts from their resume.
1. "referral": a LinkedIn message (60-90 words) to someone who works at the company, asking whether they would be
   willing to refer the person for this role. Polite and specific: name the role and one or two things from the
   resume that fit the advert. Make it easy to say no.
2. "recruiter": a note (60-90 words) to the recruiter or hiring manager for this role: interest in the role, two or
   three facts from the resume that fit the advert, and an offer to share the resume.
Never invent numbers, tools, employers, skills, dates or a job ID. No placeholders like [Name]: start with "Hi,".
Plain text, no markdown, no subject line, and sign off with the person's first name.
Answer with only this JSON: {"referral": "", "recruiter": ""}"""
SCHEMA = resume._object(referral=resume._STRING, recruiter=resume._STRING)
MAX_CHARS = 1500


def people_search_url(company):
    """LinkedIn's own people search for the company, opened in your browser (JobHunt reads nothing from it)."""
    return f"https://www.linkedin.com/search/results/people/?keywords={quote(company or '')}"


def write(job, profile, steps):
    """Both messages, each checked against your details. Returns {"referral", "recruiter", "flags", "model"}."""
    if not resume.profile_is_usable(profile):
        raise resume.ResumeError("Fill in the Resume tab first (at least your name and one job or project).")
    keywords = resume.job_keywords(job, 12)
    messages = [{"role": "system", "content": RULES},
                {"role": "user", "content": resume._job_brief(job, keywords)
                 + "\n\nThe person's resume as JSON:\n" + json.dumps(profile, ensure_ascii=False)}]
    data, model = ai.chat_json(messages, steps, schema=SCHEMA, max_tokens=1200, timeout=90)
    out = {"model": model, "flags": {}}
    # The messages may name the job, the company and LinkedIn; only claims about you must come from your details.
    known = {**profile, "about_this_job": f"{job.get('title')} {job.get('company')} {job.get('location') or ''} "
                                          "LinkedIn Hiring Manager Recruiter HR Team Regards Thanks"}
    for kind in ("referral", "recruiter"):
        text = " ".join(str(data.get(kind) or "").split())[:MAX_CHARS]
        if not text:
            raise ai.AIError("The AI didn't write both messages. Try again, or pick another model on the Settings tab.")
        out[kind] = text
        found = resume.verify(known, {"summary": text, "skills": [], "experience": [], "projects": []}, keywords)
        out["flags"][kind] = sorted({term for flag in found for term in flag["terms"]})
    return out
