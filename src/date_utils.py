import re
from datetime import datetime, timezone

_URL_DATE_PATTERNS = (
    re.compile(r"/(20\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$)"),
    re.compile(r"/(20\d{2})-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])(?:/|$)"),
    re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)"),
)

_MONTH_NAME = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?"
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

_DATE_WITH_MONTH_NAME = re.compile(
    rf"\b({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})\b",
    re.IGNORECASE,
)
_DATE_WITH_MONTH_NAME_NO_BOUNDARY = re.compile(
    rf"({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})",
    re.IGNORECASE,
)
_DATE_ISO_OR_SLASH = re.compile(
    r"(?<!\d)(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])(?!\d)"
)
_DATE_DAY_MONTH_YEAR = re.compile(
    rf"\b([0-2]?\d|3[01])\s+({_MONTH_NAME})\s+(20\d{{2}})\b",
    re.IGNORECASE,
)
_DATE_PARENTHESES = re.compile(
    rf"\(\s*(20\d{{2}})\s*,\s*({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*\)",
    re.IGNORECASE,
)

_BYLINE_PATTERNS = (
    re.compile(
        rf"({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})\s*[-|]?\s*by\s*:",
        re.IGNORECASE,
    ),
    re.compile(
        rf"({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})\s*[-|]?\s*by\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:published|posted|updated|date)\s*[:\-]?\s*({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:published|posted|updated|date)\s*[:\-]?\s*(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])",
        re.IGNORECASE,
    ),
)

_TITLE_ADJACENT_PATTERN = re.compile(
    rf"(?:^|\n)(?:[^\n]{{0,120}}\n){{0,4}}#\s+[^\n]+\n(?:[^\n]{{0,120}}\n){{0,4}}"
    rf"({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})",
    re.IGNORECASE,
)

_TITLE_ADJACENT_DATE_LABEL_PATTERN = re.compile(
    rf"#\s+[^\n]+\n(?:[^\n]{{0,120}}\n){{0,6}}date\s*:\s*({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})",
    re.IGNORECASE,
)

_LOW_CONFIDENCE_MARKERS = (
    "retrieved ",
    "accessed ",
    "technical paper link",
    "more press releases",
    "related stories",
    "related articles",
    "explore more",
    "read article",
    "learn more",
)


def parse_published_date(value: str | None) -> datetime | None:
    if not value:
        return None

    text = value.strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")

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

    try:
        dt = datetime.strptime(text[:10], "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
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
            return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def extract_date_from_content(text: str | None, max_chars: int = 1600) -> tuple[datetime | None, str, str | None]:
    if not text:
        return None, "low", "empty_content"

    snippet = text[:max_chars]

    byline_date = _extract_date_from_patterns(snippet, _BYLINE_PATTERNS)
    if byline_date is not None:
        return byline_date, "high", None

    title_adjacent_date = _extract_date_from_patterns(
        snippet,
        (_TITLE_ADJACENT_PATTERN, _TITLE_ADJACENT_DATE_LABEL_PATTERN),
    )
    if title_adjacent_date is not None:
        warning = None
        confidence = "high"
        lowered = snippet.lower()
        if "technical paper link" in lowered or "related articles" in lowered or "more press releases" in lowered:
            confidence = "medium"
            warning = "title_adjacent_date_with_sidebar_noise"
        return title_adjacent_date, confidence, warning

    sciencedaily_date = _extract_sciencedaily_date(snippet)
    if sciencedaily_date is not None:
        return sciencedaily_date, "high", None

    if any(marker in snippet.lower() for marker in _LOW_CONFIDENCE_MARKERS):
        return None, "low", "only_low_confidence_date_markers"

    return None, "low", "no_high_confidence_date_found"


def _extract_sciencedaily_date(text: str) -> datetime | None:
    if "sciencedaily" not in text.lower():
        return None

    # ScienceDaily pages often begin with a citation line like:
    # "University of Cambridge. (2026, April 23). Title..."
    match = _DATE_PARENTHESES.search(text[:400])
    if match:
        year, month_name, day = match.groups()
        return _build_month_name_date(month_name, day, year)

    # Fallback to explicit "Date:April 23, 2026" near the main body,
    # while ignoring earlier "Retrieved"/"accessed" dates.
    safe_text = _mask_low_confidence_date_contexts(text)
    match = re.search(
        rf"date\s*:\s*({_MONTH_NAME})\s+([0-2]?\d|3[01])(?:st|nd|rd|th)?\s*,\s*(20\d{{2}})",
        safe_text,
        re.IGNORECASE,
    )
    if match:
        month_name, day, year = match.groups()
        return _build_month_name_date(month_name, day, year)

    return None


def _mask_low_confidence_date_contexts(text: str) -> str:
    masked = text
    for marker in _LOW_CONFIDENCE_MARKERS:
        masked = re.sub(
            rf"{re.escape(marker)}[^\n]{{0,120}}",
            "",
            masked,
            flags=re.IGNORECASE,
        )
    return masked


def _extract_date_from_patterns(text: str, patterns: tuple[re.Pattern, ...]) -> datetime | None:
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue

        groups = match.groups()
        try:
            if len(groups) == 3 and groups[0].isdigit():
                year, month, day = groups
                return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)

            if len(groups) == 3 and groups[1].isdigit() and not groups[0].isdigit():
                month_name, day, year = groups
                return _build_month_name_date(month_name, day, year)

            if len(groups) == 3 and groups[0].isdigit() and not groups[1].isdigit():
                day, month_name, year = groups
                return _build_month_name_date(month_name, day, year)
        except (KeyError, ValueError):
            continue

    return None


def _build_month_name_date(month_name: str, day: str, year: str) -> datetime:
    month = _MONTH_MAP[month_name.lower()]
    return datetime(int(year), month, int(day), tzinfo=timezone.utc)


def resolve_article_date(article: dict, max_content_chars: int = 1600) -> tuple[datetime | None, str, str, str | None]:
    published_dt = parse_published_date(article.get("published_date"))
    if published_dt is not None:
        return published_dt, "published_date", "high", None

    url_dt = extract_date_from_url(article.get("url", ""))
    if url_dt is not None:
        return url_dt, "url", "high", None

    content_dt, confidence, warning = extract_date_from_content(
        article.get("content", ""),
        max_chars=max_content_chars,
    )
    if content_dt is not None:
        return content_dt, "content", confidence, warning

    return None, "unknown", confidence, warning
