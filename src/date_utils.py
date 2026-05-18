import re
from datetime import datetime, timezone

_URL_DATE_PATTERNS = (
    re.compile(r"/(20\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$)"),
    re.compile(r"/(20\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?:/|$)"),
    re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"),
)

_CONTENT_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?!\d)"),
    re.compile(
        r"\b("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?"
        r")\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?,\s*(20\d{2})\b",
        re.IGNORECASE,
    ),
)

_BYLINE_CONTENT_DATE_PATTERNS = (
    re.compile(
        r"\b("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?"
        r")\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?,\s*(20\d{2})"
        r"\s*(?:[-|]|&nbsp;| )*\s*(?:by[: ]|author[: ])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:published|posted|updated|date)\s*[:\-]?\s*("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?"
        r")\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?,\s*(20\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:published|posted|updated|date)\s*[:\-]?\s*(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])",
        re.IGNORECASE,
    ),
)

_MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def parse_published_date(value: str | None) -> datetime | None:
    """Parse common published_date formats into an aware UTC datetime."""
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")

    # Some providers return timestamps without timezone; assume UTC.
    if "T" in text and "+" not in text and not text.endswith("Z"):
        candidates.append(text + "+00:00")

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d",):
        try:
            dt = datetime.strptime(text[:10], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def extract_date_from_url(url: str | None) -> datetime | None:
    if not url:
        return None

    for pattern in _URL_DATE_PATTERNS:
        match = pattern.search(url)
        if not match:
            continue
        year, month, day = match.groups()
        try:
            return datetime(
                int(year), int(month), int(day), tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def extract_date_from_content(text: str | None, max_chars: int = 500) -> datetime | None:
    if not text:
        return None

    snippet = text[:max_chars]
    byline_date = _extract_date_from_patterns(snippet, _BYLINE_CONTENT_DATE_PATTERNS)
    if byline_date is not None:
        return byline_date

    lines = [line.strip() for line in snippet.splitlines() if line.strip()]
    for line in lines[:8]:
        line_date = _extract_date_from_patterns(line, _CONTENT_DATE_PATTERNS)
        if line_date is not None:
            return line_date

    return _extract_date_from_patterns(snippet, _CONTENT_DATE_PATTERNS)


def _extract_date_from_patterns(text: str, patterns: tuple[re.Pattern, ...]) -> datetime | None:
    if not text:
        return None

    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue

        groups = match.groups()
        try:
            if len(groups) == 3 and groups[0].isdigit():
                year, month, day = groups
                return datetime(
                    int(year), int(month), int(day), tzinfo=timezone.utc
                )

            month_name, day, year = groups
            month = _MONTH_MAP[month_name.lower()]
            return datetime(int(year), month, int(day), tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue

    return None


def resolve_article_date(article: dict, max_content_chars: int = 500) -> tuple[datetime | None, str]:
    published_dt = parse_published_date(article.get("published_date"))
    if published_dt is not None:
        return published_dt, "published_date"

    url_dt = extract_date_from_url(article.get("url", ""))
    if url_dt is not None:
        return url_dt, "url"

    content_dt = extract_date_from_content(article.get("content", ""), max_chars=max_content_chars)
    if content_dt is not None:
        return content_dt, "content"

    return None, "unknown"
