"""Prints the approved resume to an ATS-safe PDF, using the Edge browser that is already on the computer.

One column, ordinary headings, real text and no tables or images: the layout parsers read most reliably. Links to
your portfolio and projects stay clickable.
"""
import html
import re
import threading
from datetime import date
from pathlib import Path

from app import db, normalize

RESUME_DIR = db.DB_PATH.parent / "resumes"
_lock = threading.Lock()  # one browser print at a time

# Every tailored resume must fit on one A4 page. These layouts are tried in order until it does; the last one is the
# smallest that still reads comfortably (9.5pt text). Longer than that, the wording itself has to be cut.
FIT_LEVELS = (
    {"font": 10.5, "line": 1.34, "gap": 1.0, "margin": (13, 14)},
    {"font": 10.0, "line": 1.27, "gap": 0.75, "margin": (11, 12)},
    {"font": 9.5, "line": 1.2, "gap": 0.55, "margin": (9, 11)},
)
A4_MM = (210, 297)


class PdfError(RuntimeError):
    """A problem worded for you (Edge or Playwright missing)."""


class TooLong(Exception):
    """The resume doesn't fit on one page even in the tightest layout. `over` is its length as a share of a page."""

    def __init__(self, over):
        super().__init__(f"The resume is about {round((over - 1) * 100)}% longer than one page.")
        self.over = over


def page_css(level):
    f, g = level["font"], level["gap"]
    return f"""
@page {{ size: A4; margin: {level['margin'][0]}mm {level['margin'][1]}mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Calibri, Carlito, Arial, "Segoe UI", sans-serif; font-size: {f}pt;
       line-height: {level['line']}; color: #000; }}
h1 {{ font-size: {f + 6.5}pt; margin: 0 0 {2 * g}pt; letter-spacing: 0.2pt; }}
.role {{ font-size: {f + 0.5}pt; margin: 0 0 {3 * g}pt; }}
.contact {{ font-size: {f - 1}pt; margin: 0 0 {9 * g}pt; }}
.contact a {{ color: #000; }}
h2 {{ font-size: {f}pt; text-transform: uppercase; letter-spacing: 0.6pt; margin: {11 * g}pt 0 {4 * g}pt;
     border-bottom: 0.8pt solid #000; padding-bottom: {2 * g}pt; }}
p {{ margin: 0 0 {4 * g}pt; }}
ul {{ margin: {2 * g}pt 0 {6 * g}pt; padding-left: 15pt; }}
li {{ margin: 0 0 {2 * g}pt; }}
.entry {{ margin-bottom: {6 * g}pt; }}
.entry-head {{ display: block; font-weight: bold; }}
.entry-sub {{ font-size: {f - 1}pt; }}
.skills-line {{ margin: 0 0 {3 * g}pt; }}
a {{ color: #000; text-decoration: underline; }}
"""


def _esc(value):
    return html.escape(str(value or "").strip())


def _link(url, label):
    url = normalize.safe_url(url)
    return f'<a href="{_esc(url)}">{_esc(label)}</a>' if url else _esc(label)


def _bullets(items):
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in items) + "</ul>"


def build_html(profile, draft, level=FIT_LEVELS[0]):
    """The finished resume as a plain one-column page: facts from your profile, wording from the approved draft."""
    contact = profile.get("contact", {})
    bits = [contact.get("location"), contact.get("phone"), contact.get("email")]
    line = " · ".join(_esc(b) for b in bits if b)
    links = " · ".join(_link(link["url"], link.get("label") or link["url"]) for link in profile.get("links", []))
    parts = [f"<h1>{_esc(contact.get('name'))}</h1>"]
    if contact.get("title"):
        parts.append(f"<p class='role'>{_esc(contact['title'])}</p>")
    parts.append(f"<p class='contact'>{line}{' · ' + links if links else ''}</p>")

    if draft.get("summary"):
        parts.append(f"<h2>Summary</h2><p>{_esc(draft['summary'])}</p>")

    if draft.get("skills"):
        parts.append("<h2>Skills</h2>")
        for group in draft["skills"]:
            items = ", ".join(_esc(item) for item in group.get("items", []))
            parts.append(f"<p class='skills-line'><b>{_esc(group.get('group') or 'Skills')}:</b> {items}</p>")

    if draft.get("experience"):
        parts.append("<h2>Work Experience</h2>")
        for entry in draft["experience"]:
            dates = " – ".join(x for x in (entry.get("start"), entry.get("end")) if x)
            sub = " · ".join(x for x in (entry.get("company"), entry.get("location"), dates) if x)
            parts.append(f"<div class='entry'><span class='entry-head'>{_esc(entry.get('role'))}</span>"
                         f"<span class='entry-sub'>{_esc(sub)}</span>{_bullets(entry.get('bullets'))}</div>")

    if draft.get("projects"):
        parts.append("<h2>Projects</h2>")
        for entry in draft["projects"]:
            name = _link(entry.get("link"), entry.get("name")) if entry.get("link") else _esc(entry.get("name"))
            parts.append(f"<div class='entry'><span class='entry-head'>{name}</span>{_bullets(entry.get('bullets'))}</div>")

    if profile.get("education"):
        parts.append("<h2>Education</h2>")
        for entry in profile["education"]:
            sub = " · ".join(_esc(x) for x in (entry.get("school"), entry.get("year"), entry.get("details")) if x)
            parts.append(f"<div class='entry'><span class='entry-head'>{_esc(entry.get('degree'))}</span>"
                         f"<span class='entry-sub'>{sub}</span></div>")

    if profile.get("certifications"):
        parts.append("<h2>Certifications</h2><ul>" + "".join(
            f"<li>{_esc(' · '.join(x for x in (c.get('name'), c.get('issuer'), c.get('year')) if x))}</li>"
            for c in profile["certifications"]) + "</ul>")

    title = _esc(contact.get("name") or "Resume")
    # The page Edge prints may not run scripts or load anything; its only style is the inline one below.
    policy = "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">"
    return f"<!doctype html><html><head><meta charset='utf-8'>{policy}<title>{title}</title><style>{page_css(level)}</style></head>" \
           f"<body>{''.join(parts)}</body></html>"


def _safe_name(*parts):
    slug = "-".join(re.sub(r"[^A-Za-z0-9]+", "-", str(p or "")).strip("-") for p in parts if p)
    return (re.sub(r"-{2,}", "-", slug).strip("-") or "resume")[:90]


def _print_one_page(profile, draft):
    """Prints the resume in the first layout that fits on one page. Returns (PDF bytes, layout number 1-3).

    Raises TooLong when even the tightest layout runs onto a second page, or RuntimeError with a readable message.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PdfError("Playwright is not installed. Close JobHunt and double-click run.bat.") from exc

    with _lock, sync_playwright() as p:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = p.chromium.launch(channel=channel, headless=True) if channel else p.chromium.launch(headless=True)
                break
            except Exception:
                continue
        if browser is None:
            raise PdfError("Microsoft Edge was not found, so the PDF could not be printed.")
        try:
            page = browser.new_page()
            page.route("**/*", lambda route: route.abort())  # printing needs no network; nothing in the resume may reach out
            for number, level in enumerate(FIT_LEVELS, 1):
                page.set_content(build_html(profile, draft, level), wait_until="load")
                top, side = level["margin"]
                data = page.pdf(format="A4", print_background=False, margin={
                    "top": f"{top}mm", "bottom": f"{top}mm", "left": f"{side}mm", "right": f"{side}mm"})
                if _page_count(data) == 1:
                    return data, number
            # Too long even at the smallest size: measure by how much, laid out at the printed width.
            px = 96 / 25.4
            page.set_viewport_size({"width": round((A4_MM[0] - 2 * side) * px), "height": 800})
            height = page.evaluate("() => document.body.scrollHeight")
            raise TooLong(height / ((A4_MM[1] - 2 * top) * px))
        finally:
            browser.close()


def _page_count(data):
    from io import BytesIO

    from pypdf import PdfReader

    return len(PdfReader(BytesIO(data)).pages)


def fits(profile, draft):
    """{"fits": True/False, "over": share of a page (1.2 = 20% too long)} without saving anything."""
    try:
        _print_one_page(profile, draft)
        return {"fits": True, "over": 1.0}
    except TooLong as exc:
        return {"fits": False, "over": exc.over}


def write_pdf(profile, draft, job):
    """Prints the resume on one page and returns {path, name, layout, pages, text, links}.

    Raises TooLong if it can't fit on one page, or RuntimeError with a readable message. Nothing is saved then.
    """
    data, layout = _print_one_page(profile, draft)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_name(profile.get("contact", {}).get("name"), job.get("company"), job.get("title"),
                      date.today().isoformat()) + ".pdf"
    path = RESUME_DIR / name
    path.write_bytes(data)
    return {"path": str(path), "name": name, "layout": layout, **read_back(path)}


def read_back(path):
    """What an ATS would get out of the finished PDF: its text, page count and clickable links."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"pages": 0, "text": "", "links": []}
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    links = []
    for page in reader.pages:
        for annotation in page.get("/Annots") or []:
            try:
                target = annotation.get_object().get("/A", {}).get("/URI")
            except Exception:
                target = None
            if target:
                links.append(str(target))
    return {"pages": len(reader.pages), "text": text, "links": links}
