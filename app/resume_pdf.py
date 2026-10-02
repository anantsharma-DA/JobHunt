"""Prints the approved resume to an ATS-safe PDF, using the Edge browser that is already on the computer.

Three designs (Modern, Classic, Compact), all one column with ordinary headings, real text and no tables or images:
the layout parsers read most reliably. Links to your portfolio and projects stay clickable.
"""
import html
import re
import threading
from datetime import date
from pathlib import Path

from app import db, normalize

RESUME_DIR = db.DB_PATH.parent / "resumes"
_lock = threading.Lock()  # one browser print at a time

# Every tailored resume fills one A4 page, never more. JobHunt measures the resume and picks the largest text size
# and spacing that still fit, between the tightest layout that reads comfortably (9.5pt) and the most generous one
# that still looks like a professional resume (11.5pt). Longer than the tightest, the wording itself has to be cut.
A4_MM = (210, 297)
PX_PER_MM = 96 / 25.4
FILL_TARGET = 0.97  # share of the page to fill; the rest is a safety margin so it never spills onto a second page


def level_for(t):
    """Layout for t from -1 (tightest) through 0 (normal) to +1 (largest text), and on to +2 for a short resume:
    past +1 the text stays at 11.5pt and only the space between lines and sections grows, so the page is still full."""
    if t > 1:
        u = min(t, 2) - 1
        return {"t": round(t, 3), "font": 11.5, "line": round(1.45 + 0.1 * u, 3), "gap": round(1.75 + 1.5 * u, 3),
                "margin": (15, 16)}

    def mix(tight, normal, roomy):
        return normal + (normal - tight) * t if t < 0 else normal + (roomy - normal) * t

    return {"t": round(t, 3), "font": round(mix(9.5, 10.5, 11.5), 2), "line": round(mix(1.2, 1.34, 1.45), 3),
            "gap": round(mix(0.55, 1.0, 1.75), 3), "margin": (round(mix(9, 13, 15), 1), round(mix(11, 14, 16), 1))}


NORMAL = level_for(0)


class PdfError(RuntimeError):
    """A problem worded for you (Edge or Playwright missing)."""


class TooLong(Exception):
    """The resume doesn't fit on one page even in the tightest layout. `over` is its length as a share of a page."""

    def __init__(self, over):
        super().__init__(f"The resume is about {round((over - 1) * 100)}% longer than one page.")
        self.over = over


NAVY = "#1F3A5F"
# Three looks, all ATS-safe: one column, standard headings, real text in reading order, no tables, text boxes,
# icons, pictures or page headers. Colour and lines are ignored by ATS software; they only help a person reading it.
DESIGNS = {
    "modern": {"label": "Modern", "font": 'Calibri, Carlito, "Segoe UI", Arial, sans-serif', "accent": NAVY},
    # Not Cambria: Edge writes its spaces so that PDF readers (and ATS software) see tabs between the words.
    "classic": {"label": "Classic", "font": 'Georgia, "Times New Roman", serif', "accent": "#222222"},
    "compact": {"label": "Compact", "font": '"Segoe UI", Calibri, Carlito, Arial, sans-serif', "accent": NAVY},
}
DEFAULT_DESIGN = "modern"


def page_css(level, design=DEFAULT_DESIGN):
    f, g = level["font"], level["gap"]
    d = DESIGNS.get(design) or DESIGNS[DEFAULT_DESIGN]
    accent = d["accent"]
    css = f"""
@page {{ size: A4; margin: {level['margin'][0]}mm {level['margin'][1]}mm; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: {d['font']}; font-size: {f}pt; line-height: {level['line']}; color: #1a1a1a; }}
header {{ margin: 0 0 {8 * g}pt; }}
h1 {{ font-size: {f + 9.5}pt; line-height: 1.1; margin: 0 0 {2 * g}pt; color: {accent}; letter-spacing: 0.3pt; }}
.headline {{ font-size: {f + 0.5}pt; margin: 0 0 {2 * g}pt; color: #333; }}
.contact {{ font-size: {f - 0.8}pt; margin: 0; color: #444; }}
.contact a {{ color: {accent}; text-decoration: none; }}
.ci {{ white-space: nowrap; }}
h2 {{ font-size: {f + 0.3}pt; text-transform: uppercase; letter-spacing: 0.9pt; color: {accent};
     margin: {10 * g}pt 0 {4 * g}pt; padding-bottom: {1.5 * g}pt; border-bottom: 1pt solid {accent}; }}
p {{ margin: 0 0 {4 * g}pt; }}
ul {{ margin: {2 * g}pt 0 {5 * g}pt; padding-left: 14pt; }}
li {{ margin: 0 0 {1.8 * g}pt; }}
.entry {{ margin-bottom: {6 * g}pt; }}
.entry > .row + .row {{ margin-top: {0.6 * g}pt; }}
.row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10pt; }}
.row > .dates {{ white-space: nowrap; color: #555; font-size: {f - 0.5}pt; }}
.org {{ font-weight: bold; color: #111; }}
.place {{ font-weight: normal; color: #555; }}
.title {{ font-style: italic; color: #333; }}
.skills-line {{ margin: 0 0 {2.5 * g}pt; padding-left: 1.4em; text-indent: -1.4em; }}  /* wrapped lines indent */
.skills-line b {{ color: #111; }}
a {{ color: {accent}; text-decoration: none; }}
"""
    if design == "classic":
        css += f"""
header {{ text-align: center; border-bottom: 1.2pt solid #222; padding-bottom: {6 * g}pt; }}
body {{ font-variant-numeric: lining-nums; }}  /* Georgia's default numbers dip below the line */
h1 {{ color: #111; font-size: {f + 10}pt; letter-spacing: 1pt; }}
.contact a {{ color: #111; text-decoration: underline; }}
h2 {{ text-transform: none; font-variant: small-caps; font-size: {f + 1.5}pt; letter-spacing: 1pt; color: #111;
     border-bottom: 0.6pt solid #222; }}
a {{ color: #111; text-decoration: underline; }}
.title {{ color: #222; }}
"""
    elif design == "compact":
        css += f"""
header {{ border-bottom: 2.5pt solid {accent}; padding-bottom: {4 * g}pt; margin-bottom: {6 * g}pt; }}
h1 {{ color: #111; text-transform: uppercase; font-size: {f + 10}pt; letter-spacing: 1.2pt; margin-bottom: {1 * g}pt; }}
.headline {{ font-weight: 600; color: {accent}; margin-bottom: {1 * g}pt; }}
/* The bar sits in the margin, so heading text lines up with the text below it. */
h2 {{ border-bottom: 0; border-left: 3pt solid {accent}; padding: 0 0 0 5pt; margin: {8 * g}pt 0 {3.5 * g}pt -8pt;
     color: #111; letter-spacing: 0.7pt; }}
.entry {{ margin-bottom: {5 * g}pt; }}
ul {{ margin: {1.5 * g}pt 0 {3 * g}pt; }}
.title {{ font-style: normal; font-weight: 600; color: {accent}; }}
"""
    return css


def _esc(value):
    return html.escape(str(value or "").strip())


def _link(url, label):
    url = normalize.safe_url(url)
    return f'<a href="{_esc(url)}">{_esc(label)}</a>' if url else _esc(label)


def _bullets(items):
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in items) + "</ul>"


def _dates(start, end):
    return " – ".join(_esc(x) for x in (start, end) if x)


def _row(left, right=""):
    """One line with text on the left and (optionally) dates on the right. In the PDF's text, and so to an ATS, it
    reads as one line: left text, then the dates."""
    return f"<div class='row'><span>{left}</span>{f'<span class=dates>{right}</span>' if right else ''}</div>"


def _job(entry):
    """A job: the company (with the whole time there), then each title held there with its dates, then the bullets."""
    positions = entry.get("positions") or []
    start = entry.get("start") or (positions[-1]["start"] if positions else "")
    end = entry.get("end") or (positions[0]["end"] if positions else "")
    place = f" <span class=place>· {_esc(entry['location'])}</span>" if entry.get("location") else ""
    lines = [_row(f"<span class=org>{_esc(entry.get('company'))}</span>{place}", _dates(start, end))]
    if positions:
        lines += [_row(f"<span class=title>{_esc(p['title'])}</span>", _dates(p.get("start"), p.get("end")))
                  for p in positions]
    elif entry.get("role"):
        lines.append(_row(f"<span class=title>{_esc(entry['role'])}</span>"))
    return f"<div class='entry'>{''.join(lines)}{_bullets(entry.get('bullets'))}</div>"


def build_html(profile, draft, level=NORMAL, design=DEFAULT_DESIGN):
    """The finished resume as a one-column page: facts from your profile, wording from the approved draft."""
    contact = profile.get("contact", {})
    bits = [contact.get("location"), contact.get("phone"), contact.get("email")]
    # Each item (city, phone, email, link) wraps as a whole: a line break never leaves "·" and a lone email behind.
    line = " · ".join(f"<span class=ci>{_esc(b)}</span>" for b in bits if b)
    links = " · ".join(f"<span class=ci>{_link(link['url'], link.get('label') or link['url'])}</span>"
                       for link in profile.get("links", []))
    header = [f"<h1>{_esc(contact.get('name'))}</h1>"]
    if contact.get("title"):
        header.append(f"<p class='headline'>{_esc(contact['title'])}</p>")
    header.append(f"<p class='contact'>{line}{' · ' + links if links else ''}</p>")
    parts = [f"<header>{''.join(header)}</header>"]  # a normal page element, not a PDF page header ATS may skip

    if draft.get("summary"):
        parts.append(f"<h2>Summary</h2><p>{_esc(draft['summary'])}</p>")

    if draft.get("skills"):
        parts.append("<h2>Skills</h2>")
        for group in draft["skills"]:
            items = ", ".join(_esc(item) for item in group.get("items", []))
            parts.append(f"<p class='skills-line'><b>{_esc(group.get('group') or 'Skills')}:</b> {items}</p>")

    if draft.get("experience"):
        parts.append("<h2>Work Experience</h2>" + "".join(_job(entry) for entry in draft["experience"]))

    if draft.get("projects"):
        parts.append("<h2>Projects</h2>")
        for entry in draft["projects"]:
            name = _link(entry.get("link"), entry.get("name")) if entry.get("link") else _esc(entry.get("name"))
            parts.append(f"<div class='entry'>{_row(f'<span class=org>{name}</span>')}{_bullets(entry.get('bullets'))}</div>")

    if profile.get("education"):
        parts.append("<h2>Education</h2>")
        for entry in profile["education"]:
            school = " · ".join(_esc(x) for x in (entry.get("school"), entry.get("details")) if x)
            left = f"<span class=org>{_esc(entry.get('degree'))}</span>{f' <span class=place>· {school}</span>' if school else ''}"
            parts.append(f"<div class='entry'>{_row(left, _esc(entry.get('year')))}</div>")

    if profile.get("certifications"):
        parts.append("<h2>Certifications</h2><ul>" + "".join(
            f"<li>{_esc(' · '.join(x for x in (c.get('name'), c.get('issuer'), c.get('year')) if x))}</li>"
            for c in profile["certifications"]) + "</ul>")

    title = _esc(contact.get("name") or "Resume")
    # The page Edge prints may not run scripts or load anything; its only style is the inline one below.
    policy = "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">"
    return (f"<!doctype html><html><head><meta charset='utf-8'>{policy}<title>{title}</title>"
            f"<style>{page_css(level, design)}</style></head><body>{''.join(parts)}</body></html>")


def _safe_name(*parts):
    slug = "-".join(re.sub(r"[^A-Za-z0-9]+", "-", str(p or "")).strip("-") for p in parts if p)
    return (re.sub(r"-{2,}", "-", slug).strip("-") or "resume")[:90]


def _print_one_page(profile, draft, design=DEFAULT_DESIGN):
    """Prints the resume filling one page, in the most generous layout that fits. Returns (PDF bytes, layout used).

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
            page.emulate_media(media="print")

            def fill(t):
                """How much of the printable page the resume takes at layout t (1.0 = exactly full)."""
                level = level_for(t)
                page.set_content(build_html(profile, draft, level, design), wait_until="load")
                top, side = level["margin"]
                page.set_viewport_size({"width": round((A4_MM[0] - 2 * side) * PX_PER_MM), "height": 900})
                height = page.evaluate("() => document.body.getBoundingClientRect().height")
                return height / ((A4_MM[1] - 2 * top) * PX_PER_MM)

            tightest = fill(-1)
            if tightest > 1:
                raise TooLong(tightest)
            # The most generous layout that still fits (text size and spacing grow together, then only spacing).
            if fill(2) <= FILL_TARGET:
                best = 2.0
            else:
                low, high = -1.0, 2.0
                for _ in range(8):
                    middle = (low + high) / 2
                    if fill(middle) <= FILL_TARGET:
                        low = middle
                    else:
                        high = middle
                best = low
            # Print, and confirm it really is one page (the printed layout can differ by a line or so).
            while True:
                level = level_for(best)
                page.set_content(build_html(profile, draft, level, design), wait_until="load")
                top, side = level["margin"]
                data = page.pdf(format="A4", print_background=False, margin={
                    "top": f"{top}mm", "bottom": f"{top}mm", "left": f"{side}mm", "right": f"{side}mm"})
                if _page_count(data) == 1:
                    return data, level
                if best <= -1:
                    raise TooLong(1.02)
                best = max(-1.0, best - 0.1)
        finally:
            browser.close()


def _page_count(data):
    from io import BytesIO

    from pypdf import PdfReader

    return len(PdfReader(BytesIO(data)).pages)


def fits(profile, draft, design=DEFAULT_DESIGN):
    """{"fits": True/False, "over": share of a page (1.2 = 20% too long)} without saving anything."""
    try:
        _print_one_page(profile, draft, design)
        return {"fits": True, "over": 1.0}
    except TooLong as exc:
        return {"fits": False, "over": exc.over}


def write_pdf(profile, draft, job, design=DEFAULT_DESIGN):
    """Prints the resume on one page and returns {path, name, layout, pages, text, links}.

    Raises TooLong if it can't fit on one page, or RuntimeError with a readable message. Nothing is saved then.
    """
    data, level = _print_one_page(profile, draft, design)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    name = _safe_name(profile.get("contact", {}).get("name"), job.get("company"), job.get("title"),
                      date.today().isoformat()) + ".pdf"
    path = RESUME_DIR / name
    path.write_bytes(data)
    # layout 1 = normal size or larger (spacing widened to fill the page), 2 = tightened to fit
    return {"path": str(path), "name": name, "layout": 1 if level["t"] >= 0 else 2, "font": level["font"],
            "design": design, **read_back(path)}


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
