"""Turns raw job records from every source into one consistent shape."""
import html
import math
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from app.cities import CITIES

CITY_ALIASES = {
    "Bengaluru": ["bengaluru", "bangalore"],
    "Hyderabad": ["hyderabad", "secunderabad"],
    "Pune": ["pune"],
    "Mumbai": ["mumbai", "bombay"],
    "Navi Mumbai": ["navi mumbai"],
    "Thane": ["thane"],
    "Delhi": ["new delhi", "delhi"],
    "Gurugram": ["gurugram", "gurgaon"],
    "Noida": ["noida"],
    "Faridabad": ["faridabad"],
    "Ghaziabad": ["ghaziabad"],
    "Chennai": ["chennai", "madras"],
    "Kolkata": ["kolkata", "calcutta"],
    "Ahmedabad": ["ahmedabad"],
    "Gandhinagar": ["gandhinagar"],
    "Vadodara": ["vadodara", "baroda"],
    "Surat": ["surat"],
    "Jaipur": ["jaipur"],
    "Indore": ["indore"],
    "Bhopal": ["bhopal"],
    "Lucknow": ["lucknow"],
    "Chandigarh": ["chandigarh"],
    "Mohali": ["mohali"],
    "Kochi": ["kochi", "cochin"],
    "Thiruvananthapuram": ["thiruvananthapuram", "trivandrum"],
    "Coimbatore": ["coimbatore"],
    "Mysuru": ["mysuru", "mysore"],
    "Mangaluru": ["mangaluru", "mangalore"],
    "Visakhapatnam": ["visakhapatnam", "vizag"],
    "Vijayawada": ["vijayawada"],
    "Nagpur": ["nagpur"],
    "Nashik": ["nashik"],
    "Bhubaneswar": ["bhubaneswar"],
    "Patna": ["patna"],
    "Ranchi": ["ranchi"],
    "Guwahati": ["guwahati"],
    "Dehradun": ["dehradun"],
    "Udaipur": ["udaipur"],
    "Jodhpur": ["jodhpur"],
    "Madurai": ["madurai"],
    "Goa": ["goa", "panaji"],
}
# Cities offered in the search box (app/cities.py) are recognised in job locations too.
for _name, _state, _aliases in CITIES:
    CITY_ALIASES.setdefault(_name, _aliases)
CITY_STATES = {name: state for name, state, _ in CITIES}

_CITY_PATTERNS = [
    (city, re.compile(r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])"))
    for city, aliases in CITY_ALIASES.items()
    for alias in aliases
]
_INDIA_RE = re.compile(r"(?<![a-z])(india|indian)(?![a-z])")
_REMOTE_RE = re.compile(r"(?<![a-z])(remote|work from home|work-from-home|wfh|anywhere)(?![a-z])")
_HYBRID_RE = re.compile(r"(?<![a-z])hybrid(?![a-z])")
_ONSITE_RE = re.compile(r"(?<![a-z])(on-?site|in-?office|work from office|wfo)(?![a-z])")
_NOT_A_CITY_RE = re.compile(r"(?i)^(india|remote|anywhere|work from home|wfh|hybrid|on-?site|multiple locations|various|\d+\s+locations?|.{1,3})$")
INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur",
    "meghalaya", "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana",
    "tripura", "uttar pradesh", "uttarakhand", "west bengal", "jammu and kashmir", "delhi ncr", "ncr",
}
_STATE_PATTERNS = [
    (state, re.compile(r"(?<![a-z])" + re.escape(state) + r"(?![a-z])"))
    for state in sorted(INDIAN_STATES | {"delhi", "chandigarh", "puducherry"}, key=len, reverse=True)
]


def find_states(text):
    """Lower-case state names mentioned in a location, e.g. 'Rajasthan, India' -> {'rajasthan'}."""
    text = (text or "").lower()
    return {state for state, pattern in _STATE_PATTERNS if pattern.search(text)}


def canonical_city(name):
    """'bangalore' -> 'Bengaluru'; cities that aren't in the list keep the typed name."""
    name = (name or "").strip()
    for city in CITY_STATES:
        if city.lower() == name.lower():
            return city
    found = find_cities(name)
    return found[0] if found else name


def clean(value):
    """None for missing values, including pandas NaN and blank strings."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def safe_url(value):
    """The link if it is a plain http(s) web address, otherwise None.

    Links come from job sites and imported files and end up in the page. Any other kind (javascript:, data:, file:)
    could run code or open local files when clicked, so it is dropped. Links with a user name or password are dropped
    too, since they can disguise where they really go.
    """
    value = clean(value)
    if value is None:
        return None
    text = str(value).strip().replace(" ", "%20")
    if len(text) > 2048 or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in text):
        return None
    try:
        parts = urlparse(text)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            return None
        if not re.fullmatch(r"[\w.\-:]+", parts.hostname) or "%" in parts.hostname:
            return None  # e.g. "http://exa mple.com/"
        parts.port  # raises ValueError for junk such as "https://javascript:alert(1)"
    except ValueError:
        return None
    return text


def to_float(value):
    value = clean(value)
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def strip_html(text):
    text = clean(text)
    if text is None:
        return None
    text = html.unescape(str(text))
    text = re.sub(r"(?i)<\s*br\s*/?>|</\s*(p|div|h\d|tr)\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*li[^>]*>", "\n• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def find_cities(text):
    text = (text or "").lower()
    hits = []
    for city, pattern in _CITY_PATTERNS:
        m = pattern.search(text)
        if m and city not in [c for c, _ in hits]:
            hits.append((city, m.start()))
    return [c for c, _ in sorted(hits, key=lambda h: h[1])]


def is_india(text):
    text = (text or "").lower()
    return bool(_INDIA_RE.search(text)) or bool(find_cities(text))


def cities_for(location, work_mode):
    found = find_cities(location)
    if not found and location:
        first = str(location).split(",")[0].strip()
        if first and not _NOT_A_CITY_RE.match(first) and first.lower() not in INDIAN_STATES:
            found = [first.title()]
    if work_mode == "Remote" and "Remote" not in found:
        found.append("Remote")
    return found


def work_mode(is_remote, *texts):
    joined = " ".join(str(t) for t in texts if clean(t)).lower()
    if _HYBRID_RE.search(joined):
        return "Hybrid"
    if is_remote is True or _REMOTE_RE.search(joined):
        return "Remote"
    if _ONSITE_RE.search(joined):
        return "On-site"
    return "Not specified"


_JOB_TYPE_WORDS = [
    ("intern", "Internship"),
    ("contract", "Contract"),
    ("freelance", "Contract"),
    ("temp", "Temporary"),
    ("part", "Part-time"),
    ("full", "Full-time"),
    ("permanent", "Full-time"),
    ("regular", "Full-time"),
]


def job_types(*values):
    labels = []
    for value in values:
        value = clean(value)
        if value is None:
            continue
        items = value if isinstance(value, (list, tuple)) else re.split(r"[,/|]", str(value))
        for item in items:
            word = str(getattr(item, "value", item)).lower().replace(" ", "").replace("-", "")
            for key, label in _JOB_TYPE_WORDS:
                if key in word and label not in labels:
                    labels.append(label)
                    break
    return labels or ["Not specified"]


_INTERVAL_MULTIPLIER = {"yearly": 1, "monthly": 12, "weekly": 52, "daily": 260, "hourly": 2080}


def interval_name(text):
    text = (str(clean(text) or "yearly")).lower()
    for name, keys in (("hourly", ("hour",)), ("daily", ("day", "daily")), ("weekly", ("week",)),
                       ("monthly", ("month",)), ("yearly", ("year", "annual", "annum"))):
        if any(k in text for k in keys):
            return name
    return "yearly"


def salary(min_amount, max_amount, interval, currency):
    """Returns (min_lpa, max_lpa, display_text). LPA values are None when not disclosed or not in INR."""
    lo, hi = to_float(min_amount), to_float(max_amount)
    if lo is None and hi is None:
        return None, None, None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    currency = (str(clean(currency) or "INR")).upper().strip()
    period = interval_name(interval)
    if currency not in ("INR", "RS", "RS.", "₹"):
        amounts = "–".join(f"{v:,.0f}" for v in (lo, hi) if v is not None)
        return None, None, f"{currency} {amounts} / {period}"
    mult = _INTERVAL_MULTIPLIER[period]
    lo_lpa = round(lo * mult / 100000, 2) if lo is not None else None
    hi_lpa = round(hi * mult / 100000, 2) if hi is not None else None
    top = hi_lpa if hi_lpa is not None else lo_lpa
    if top is None or top < 0.1 or top > 1000:
        return None, None, None
    return lo_lpa, hi_lpa, None


_PERIOD = r"(?:\s*(?:/|per|a|an)\s*(year|annum|month|week|day|hour))?"
_RUPEE_RANGE_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)\s*(?:\\?[-–—]|to)\s*₹?\s?([\d,]+(?:\.\d+)?)" + _PERIOD, re.I)
_LPA_RANGE_RE = re.compile(r"(\d{1,2}(?:\.\d{1,2})?)\s*(?:\\?[-–—]|to)\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:lpa|lakhs?|lacs?)\b", re.I)
_RUPEE_SINGLE_RE = re.compile(r"(?:pay|salary|stipend|ctc)\s*:?\s*(?:up to\s*)?₹\s?([\d,]+(?:\.\d+)?)" + _PERIOD, re.I)


def salary_from_text(text):
    """Pay stated inside a description, e.g. 'Pay: ₹3,05,482 - ₹13,11,523 per year' or '6-9 LPA'.
    Returns (min_rupees, max_rupees, interval)."""
    text = clean(text)
    if text is None:
        return None, None, None
    m = _RUPEE_RANGE_RE.search(text)
    if m:
        lo, hi = to_float(m.group(1)), to_float(m.group(2))
        return lo, hi, m.group(3) or ("monthly" if hi and hi < 200000 else "yearly")
    m = _LPA_RANGE_RE.search(text)
    if m:
        return float(m.group(1)) * 100000, float(m.group(2)) * 100000, "yearly"
    m = _RUPEE_SINGLE_RE.search(text)
    if m:
        value = to_float(m.group(1))
        return value, value, m.group(2) or ("monthly" if value and value < 200000 else "yearly")
    return None, None, None


_NUM = r"(\d{1,2}(?:\.\d)?)"
_YRS = r"\s*\+?\s*(?:years?|yrs?)\b"
_EXP_RANGE_RE = re.compile(_NUM + r"\s*\+?\s*(?:-|–|—|to)\s*" + _NUM + _YRS, re.I)
_EXP_MIN_RE = re.compile(
    r"(?:minimum|min\.?|at\s+least)\s*(?:of\s*)?" + _NUM + _YRS
    + r"|" + _NUM + r"\s*\+\s*(?:years?|yrs?)\b"
    + r"|" + _NUM + r"\s*(?:years?|yrs?)\s*(?:of\s+)?(?:[a-z/&-]+\s+){0,3}?experience",
    re.I,
)


def experience(*texts):
    """Returns (min_years, max_years) from the first text that mentions experience."""
    for text in texts:
        text = clean(text)
        if text is None:
            continue
        text = str(text)
        m = _EXP_RANGE_RE.search(text)
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo <= hi <= 40:
                return lo, hi
        m = _EXP_MIN_RE.search(text)
        if m:
            lo = float(next(g for g in m.groups() if g is not None))
            if lo <= 40:
                return lo, None
    return None, None


def parse_date(value):
    """Accepts date/datetime, ISO strings and epoch milliseconds. Returns 'YYYY-MM-DD' or None."""
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).date().isoformat()
    text = str(value).strip()
    if text.isdigit():
        return parse_date(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        m = re.match(r"\d{4}-\d{2}-\d{2}", text)
        return m.group(0) if m else None


def relative_posted(text):
    """Workday style 'Posted 3 Days Ago' / 'Posted Today' / 'Posted 30+ Days Ago'."""
    text = (clean(text) or "").lower()
    today = date.today()
    if "today" in text:
        return today.isoformat()
    if "yesterday" in text:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*day", text)
    return (today - timedelta(days=int(m.group(1)))).isoformat() if m else None


def _exact_time(value):
    """The posting moment when a source gives one (ISO timestamp or epoch ms); None for date-only values."""
    value = clean(value)
    if value is None or (isinstance(value, date) and not isinstance(value, datetime)):
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)):
        moment = datetime.fromtimestamp(value / 1000 if value > 1e11 else value, tz=timezone.utc)
    else:
        text = str(value).strip()
        if text.isdigit():
            return _exact_time(int(text))
        if not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", text):
            return None
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return moment if moment.tzinfo else moment.astimezone()


def is_recent(posted, minutes_old):
    """True when a job falls inside the "posted within" window.

    Exact posting times are compared to the minute. Date-only values pass when their day is inside
    the window, because the source doesn't say more.
    """
    if not minutes_old:
        return True
    moment = _exact_time(posted)
    if moment is not None:
        return moment >= datetime.now(timezone.utc) - timedelta(minutes=minutes_old)
    day = parse_date(posted)
    if day is None:
        return True
    return day >= (datetime.now() - timedelta(minutes=minutes_old)).date().isoformat()


_COMPANY_SUFFIX_RE = re.compile(r"\b(private|pvt|limited|ltd|llp|inc|incorporated|corp|corporation|co|india)\b")


def slug(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def company_key(name):
    return re.sub(r"\s+", " ", _COMPANY_SUFFIX_RE.sub(" ", slug(name))).strip()


def dedupe_key(title, company, cities):
    return f"{slug(title)}|{company_key(company)}|{','.join(sorted(c.lower() for c in cities))}"


def applicants(value):
    """A site's applicant wording -> (number for sorting, text to show), or (None, None).

    "Over 200 applicants" -> (200, "Over 200 applicants"); "Applicants: 100+" -> (100, "Over 100 applicants");
    "Be among the first 25 applicants" -> (0, "Fewer than 25 applicants").
    """
    text = clean(value)
    if text is None:
        return None, None
    text = " ".join(str(text).split())
    m = re.search(r"(?i)first\s+([\d,]+)\s+applicants", text)
    if m:
        return 0, f"Fewer than {m.group(1)} applicants"
    m = re.search(r"(?i)(over\s+)?([\d,]+)(\+?)\s*applicants?\b", text)
    if m:
        count, more = int(m.group(2).replace(",", "")), bool(m.group(1) or m.group(3))
    else:
        m = re.search(r"(?i)applicants?\s*:?\s*([\d,]+)(\+?)", text)
        if not m:
            return None, None
        count, more = int(m.group(1).replace(",", "")), bool(m.group(2))
    return count, f"{'Over ' if more else ''}{count:,} applicant{'' if count == 1 and not more else 's'}"


def _applicant_fields(value):
    count, text = applicants(value)
    return {
        "applicants": count,
        "applicants_text": text,
        "applicants_checked": datetime.now().isoformat(timespec="minutes") if text else None,
    }


def _rating_fields(raw):
    """Company rating (out of 5), its review count and a link to the reviews, when the source gives them."""
    rating = to_float(raw.get("company_rating"))
    reviews = to_float(raw.get("company_reviews"))
    if rating is None or not 0 < rating <= 5:
        return {"company_rating": None, "company_reviews": None, "company_rating_url": None}
    return {
        "company_rating": round(rating, 1),
        "company_reviews": int(reviews) if reviews is not None else None,
        "company_rating_url": safe_url(raw.get("company_rating_url")),
    }


def build_job(raw):
    """raw -> row ready for db.upsert_job. See sources/*.py for the raw keys."""
    title = clean(raw.get("title"))
    if not title:
        return None
    location = clean(raw.get("location")) or ""
    mode = work_mode(raw.get("is_remote"), raw.get("workplace"), title, location)
    cities = cities_for(location, mode)
    if not [c for c in cities if c != "Remote"]:
        cities = find_cities(title) + cities  # e.g. "Data Analyst: Hyderabad" listed only as "Telangana, India"
    sal_min, sal_max, sal_text = salary(raw.get("min_amount"), raw.get("max_amount"), raw.get("interval"), raw.get("currency"))
    description = clean(raw.get("description"))
    if sal_min is None and sal_max is None and not sal_text:
        # Indeed and LinkedIn often state pay only in the description
        lo, hi, period = salary_from_text(description)
        sal_min, sal_max, sal_text = salary(lo, hi, period, "INR")
    exp_min, exp_max = experience(raw.get("experience_text"), description)
    company = clean(raw.get("company")) or "Unknown company"
    return {
        "dedupe_key": dedupe_key(title, company, cities),
        "title": str(title).strip(),
        "company": str(company).strip(),
        "location": str(location).strip(),
        "cities": cities,
        "work_mode": mode,
        "job_types": job_types(raw.get("job_type")),
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_text": sal_text,
        "exp_min": exp_min,
        "exp_max": exp_max,
        "date_posted": parse_date(raw.get("date_posted")),
        "description": description,
        "skills_listed": clean(raw.get("skills")),
        "search_titles": list(raw.get("search_titles") or []),
        **_applicant_fields(raw.get("applicants")),
        **_rating_fields(raw),
        "source": {
            "site": raw["site"],
            "url": safe_url(raw.get("job_url")),
            "direct": safe_url(raw.get("apply_url")),
        },
    }
