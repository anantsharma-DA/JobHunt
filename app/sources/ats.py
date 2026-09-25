"""Reads careers sites hosted on common hiring platforms through their free public job feeds."""
import collections
import html
import ipaddress
import re
import socket
import time
from urllib.parse import unquote, urljoin, urlparse

import requests

from app import errors, matching, normalize
from app.sources import SearchCancelled

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 40
WORKDAY_PAGES_PER_TITLE = 5
MAX_DETAIL_FETCHES = 80

PLATFORM_LABELS = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
    "smartrecruiters": "SmartRecruiters",
    "workday": "Workday",
    "boards": "Indeed + LinkedIn search",
}

_PATTERNS = [
    ("greenhouse", re.compile(r"greenhouse\.io/.*[?&]for=(?P<token>[\w-]+)", re.I)),
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board/?)?(?P<token>[\w-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/(?P<token>[\w-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?P<eu>eu\.)?lever\.co/(?P<site>[\w.-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/(?P<board>[^/?#]+)", re.I)),
    ("smartrecruiters", re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/(?P<company>[^/?#]+)", re.I)),
    ("workday", re.compile(r"(?P<tenant>[\w-]+)\.(?P<wd>wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?(?P<site>[^/?#]+)", re.I)),
]


class SourceError(Exception):
    pass


def detect_platform(url):
    for platform, pattern in _PATTERNS:
        m = pattern.search(url or "")
        if m:
            return {"platform": platform, **{k: v for k, v in m.groupdict().items()}}
    return {"platform": "boards"}


_LINK_RE = re.compile(r"""https?://[^\s"'<>()\\]+""", re.I)
_NOT_A_BOARD = {"embed", "js", "job_board", "jobs", "wday", "api", "v1", "static", "assets", "careers"}


def _feed_url(params):
    platform = params["platform"]
    if platform == "greenhouse":
        return f"https://boards.greenhouse.io/{params['token']}"
    if platform == "lever":
        return f"https://jobs.{'eu.' if params.get('eu') else ''}lever.co/{params['site']}"
    if platform == "ashby":
        return f"https://jobs.ashbyhq.com/{params['board']}"
    if platform == "smartrecruiters":
        return f"https://jobs.smartrecruiters.com/{params['company']}"
    return f"https://{params['tenant']}.{params['wd']}.myworkdayjobs.com/{params['site']}"


MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5


def is_public_web_address(url):
    """True only for http(s) links whose host resolves to public internet addresses.

    Careers links come from the user or from imported files. Without this check, a link such as http://192.168.1.1/
    or http://169.254.169.254/ would make JobHunt fetch pages from this computer or the local network
    (server-side request forgery).
    """
    parts = urlparse(url or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        addresses = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError, ValueError):
        return False
    return bool(addresses) and all(ipaddress.ip_address(info[4][0].split("%")[0]).is_global for info in addresses)


def _get_public_page(url, timeout):
    """GETs a careers page, following redirects only to public addresses and reading at most MAX_PAGE_BYTES.
    Returns (final url, status code, page text)."""
    for _ in range(MAX_REDIRECTS + 1):
        if not is_public_web_address(url):
            raise SourceError("careers link points to a local or private network address, so it was not opened")
        resp = requests.get(url, headers={**HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"},
                            timeout=timeout, allow_redirects=False, stream=True)
        try:
            if resp.is_redirect and resp.headers.get("location"):
                url = urljoin(url, resp.headers["location"])
                continue
            chunks, size = [], 0
            for chunk in resp.iter_content(chunk_size=65536):
                chunks.append(chunk)
                size += len(chunk)
                if size >= MAX_PAGE_BYTES:
                    break
            body = b"".join(chunks)[:MAX_PAGE_BYTES]
            return url, resp.status_code, body.decode(resp.encoding or "utf-8", errors="replace")
        finally:
            resp.close()
    raise SourceError("careers page redirected too many times")


def find_platform_in_page(url, timeout=15):
    """Opens a careers page that isn't itself on a supported platform and looks inside it, and at where it
    redirects, for a link to one. Returns (feed_url or None, note)."""
    try:
        final_url, status, page = _get_public_page(url, timeout)
    except SourceError as exc:
        return None, str(exc)
    except requests.RequestException as exc:
        return None, f"careers page could not be opened: {errors.network(exc, 'Careers page')}"
    text = html.unescape(page.replace("\\/", "/"))
    counts = collections.Counter()
    for link in [final_url, *_LINK_RE.findall(text)]:
        params = detect_platform(unquote(link))
        if params["platform"] == "boards":
            continue
        board = next(v for k, v in params.items() if k in ("token", "site", "board", "company"))
        if board.lower() in _NOT_A_BOARD:
            continue
        counts[_feed_url(params)] += 1
    if not counts:
        if status >= 400:
            return None, f"careers page returned HTTP {status}"
        return None, "no supported hiring platform found on the careers page"
    feed = counts.most_common(1)[0][0]
    return feed, f"{PLATFORM_LABELS[detect_platform(feed)['platform']]} found behind the careers page"


class _Fetcher:
    def __init__(self, company, titles, minutes_old, delay, should_stop):
        self.company = company
        self.should_stop = should_stop
        self.titles = titles
        self.minutes_old = minutes_old
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.details_fetched = 0

    def request(self, method, url, **kwargs):
        host = url.split("/")[2]
        for attempt in (1, 2):
            if self.should_stop():
                raise SearchCancelled()
            time.sleep(self.delay)
            try:
                resp = self.session.request(method, url, timeout=TIMEOUT, **kwargs)
                break
            except requests.Timeout as exc:
                if attempt == 2:
                    raise SourceError(f"{host} did not respond in time, try again later") from exc
            except requests.RequestException as exc:
                raise SourceError(f"could not reach {host} ({exc.__class__.__name__})") from exc
        if resp.status_code == 404:
            raise SourceError("careers board not found, check the careers URL")
        if resp.status_code >= 400:
            raise SourceError(f"HTTP {resp.status_code} from {url.split('/')[2]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise SourceError("unexpected response (not JSON)") from exc

    def wanted_title(self, title):
        return not self.titles or matching.title_score(title, self.titles) >= 1.0

    def raw(self, **fields):
        return {"site": "company", "company": self.company, **fields}

    def keep(self, raw, location_text):
        return normalize.is_india(location_text) and normalize.is_recent(raw.get("date_posted"), self.minutes_old)


def _greenhouse(f, p):
    data = f.request("GET", f"https://boards-api.greenhouse.io/v1/boards/{p['token']}/jobs", params={"content": "true"})
    for j in data.get("jobs") or []:
        if not f.wanted_title(j.get("title")):
            continue
        location = (j.get("location") or {}).get("name") or ""
        offices = [o.get("location") or o.get("name") or "" for o in j.get("offices") or []]
        raw = f.raw(
            title=j.get("title"),
            location=location,
            description=normalize.strip_html(j.get("content")),
            job_url=j.get("absolute_url"),
            apply_url=j.get("absolute_url"),
            date_posted=j.get("first_published") or j.get("updated_at"),
        )
        if f.keep(raw, ", ".join([location, *offices])):
            yield raw


def _lever(f, p):
    host = "api.eu.lever.co" if p.get("eu") else "api.lever.co"
    data = f.request("GET", f"https://{host}/v0/postings/{p['site']}", params={"mode": "json"})
    for j in data if isinstance(data, list) else []:
        if not f.wanted_title(j.get("text")):
            continue
        cats = j.get("categories") or {}
        locations = [cats.get("location") or "", *(cats.get("allLocations") or [])]
        parts = [j.get("descriptionPlain") or ""]
        for block in j.get("lists") or []:
            parts.append(f"{block.get('text', '')}\n{normalize.strip_html(block.get('content')) or ''}")
        parts.append(j.get("additionalPlain") or "")
        pay = j.get("salaryRange") or {}
        workplace = j.get("workplaceType") or ""
        raw = f.raw(
            title=j.get("text"),
            location=", ".join(l for l in locations if l),
            is_remote=workplace == "remote",
            workplace=workplace,
            job_type=cats.get("commitment"),
            description="\n\n".join(x for x in parts if x).strip(),
            job_url=j.get("hostedUrl"),
            apply_url=j.get("applyUrl") or j.get("hostedUrl"),
            date_posted=j.get("createdAt"),
            min_amount=pay.get("min"),
            max_amount=pay.get("max"),
            currency=pay.get("currency"),
            interval=pay.get("interval"),
        )
        location_text = ", ".join(locations) + (" india" if j.get("country") == "IN" else "")
        if f.keep(raw, location_text):
            yield raw


def _ashby(f, p):
    data = f.request("GET", f"https://api.ashbyhq.com/posting-api/job-board/{p['board']}",
                     params={"includeCompensation": "true"})
    for j in data.get("jobs") or []:
        if j.get("isListed") is False or not f.wanted_title(j.get("title")):
            continue
        locations = [j.get("location") or "", *[s.get("location") or "" for s in j.get("secondaryLocations") or []]]
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or ""
        pay = {}
        for comp in (j.get("compensation") or {}).get("summaryComponents") or []:
            if comp.get("compensationType") == "Salary":
                pay = comp
                break
        workplace = j.get("workplaceType") or ""
        raw = f.raw(
            title=j.get("title"),
            location=", ".join(l for l in locations if l),
            is_remote=bool(j.get("isRemote")) or workplace.lower() == "remote",
            workplace=workplace,
            job_type=j.get("employmentType"),
            description=j.get("descriptionPlain") or normalize.strip_html(j.get("descriptionHtml")),
            job_url=j.get("jobUrl"),
            apply_url=j.get("applyUrl") or j.get("jobUrl"),
            date_posted=j.get("publishedAt"),
            min_amount=pay.get("minValue"),
            max_amount=pay.get("maxValue"),
            currency=pay.get("currencyCode"),
            interval=pay.get("interval"),
        )
        if f.keep(raw, ", ".join([*locations, country])):
            yield raw


def _smartrecruiters(f, p):
    base = f"https://api.smartrecruiters.com/v1/companies/{p['company']}/postings"
    seen = set()
    for query in f.titles or [""]:
        offset = 0
        while offset < 1000:
            data = f.request("GET", base, params={"limit": 100, "offset": offset, "q": query})
            content = data.get("content") or []
            for j in content:
                if j.get("id") in seen or not f.wanted_title(j.get("name")):
                    continue
                seen.add(j.get("id"))
                loc = j.get("location") or {}
                location_text = loc.get("fullLocation") or ", ".join(
                    x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
                if str(loc.get("country", "")).lower() == "in" and not normalize.is_india(location_text):
                    location_text += ", India"
                date_posted = normalize.parse_date(j.get("releasedDate"))
                if not normalize.is_india(location_text) or not normalize.is_recent(j.get("releasedDate"), f.minutes_old):
                    continue
                detail = {}
                if f.details_fetched < MAX_DETAIL_FETCHES:
                    f.details_fetched += 1
                    detail = f.request("GET", f"{base}/{j['id']}")
                sections = ((detail.get("jobAd") or {}).get("sections") or {}).values()
                description = "\n\n".join(
                    f"{s.get('title', '')}\n{normalize.strip_html(s.get('text')) or ''}" for s in sections if isinstance(s, dict))
                url = detail.get("postingUrl") or f"https://jobs.smartrecruiters.com/{p['company']}/{j['id']}"
                yield f.raw(
                    title=j.get("name"),
                    location=location_text,
                    is_remote=bool(loc.get("remote")),
                    workplace="hybrid" if loc.get("hybrid") else "",
                    job_type=(j.get("typeOfEmployment") or {}).get("label"),
                    description=description.strip() or None,
                    job_url=url,
                    apply_url=detail.get("applyUrl") or url,
                    date_posted=date_posted,
                )
            offset += 100
            if not content or offset >= (data.get("totalFound") or 0):
                break


def _workday(f, p):
    base = f"https://{p['tenant']}.{p['wd']}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{p['tenant']}/{p['site']}"
    seen = set()
    for query in f.titles or [""]:
        total = None
        for page in range(WORKDAY_PAGES_PER_TITLE):
            offset = page * 20
            data = f.request("POST", f"{api}/jobs",
                             json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": query})
            postings = data.get("jobPostings") or []
            if total is None:
                total = data.get("total") or 0  # Workday only reports the total on the first page
            for jp in postings:
                path = jp.get("externalPath")
                if not path or path in seen or not f.wanted_title(jp.get("title")):
                    continue
                seen.add(path)
                where = f"{jp.get('locationsText') or ''} {path.replace('-', ' ')}"
                if not normalize.is_india(where) and not re.search(r"\d+\s+locations", where, re.I):
                    continue  # one location and it is outside India: skip the detail request
                posted = normalize.relative_posted(jp.get("postedOn"))
                if not normalize.is_recent(posted, f.minutes_old) or f.details_fetched >= MAX_DETAIL_FETCHES:
                    continue
                f.details_fetched += 1
                info = f.request("GET", f"{api}{path}").get("jobPostingInfo") or {}
                locations = [info.get("location") or jp.get("locationsText") or "", *(info.get("additionalLocations") or [])]
                country = (info.get("country") or {}).get("descriptor") or ""
                url = info.get("externalUrl") or f"{base}/{p['site']}{path}"
                raw = f.raw(
                    title=info.get("title") or jp.get("title"),
                    location=", ".join(l for l in locations if l) or country,
                    workplace=info.get("remoteType") or "",
                    job_type=info.get("timeType"),
                    description=normalize.strip_html(info.get("jobDescription")),
                    job_url=url,
                    apply_url=url,
                    date_posted=info.get("startDate") or posted,
                )
                if normalize.is_india(", ".join([*locations, country])):
                    yield raw
            if len(postings) < 20 or offset + 20 >= total:
                break


_FETCHERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "smartrecruiters": _smartrecruiters,
    "workday": _workday,
}


def fetch_company(company, careers_url, titles, minutes_old, delay=1.0, should_stop=lambda: False):
    """Returns raw India jobs matching the titles from a company's hiring-platform feed."""
    params = detect_platform(careers_url)
    fetch = _FETCHERS.get(params["platform"])
    if fetch is None:
        raise SourceError("careers URL is not on a supported platform")
    return list(fetch(_Fetcher(company, titles, minutes_old, delay, should_stop), params))
