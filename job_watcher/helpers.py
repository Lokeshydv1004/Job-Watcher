"""Shared text, date, and job-normalization helpers."""

import html
import re
from datetime import datetime, timezone

import requests

from .settings import HEADERS, TIMEOUT

def phrase_regex(phrases):
    """
    Whole-word, case-insensitive regex from a list of phrases.
    Returns None if the list is empty.
    """
    phrases = [
        p.strip()
        for p in phrases
        if isinstance(p, str) and p.strip()
    ]

    if not phrases:
        return None

    return re.compile(
        r"\b(" + "|".join(re.escape(p) for p in phrases) + r")\b",
        re.I
    )

def location_regex(phrases):
    """
    Locations match as substrings.
    Example:
        'india' matches 'Bengaluru, India'
    """
    phrases = [
        p.strip()
        for p in phrases
        if isinstance(p, str) and p.strip()
    ]

    if not phrases:
        return None

    return re.compile(
        "|".join(re.escape(p) for p in phrases),
        re.I
    )

def strip_html(text):
    """
    Convert HTML into clean plain text.
    """
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)

    return re.sub(r"\s+", " ", text).strip()

def parse_date(value):
    """
    Handles:
        - ISO strings
        - epoch milliseconds
        - epoch seconds

    Returns timezone-aware UTC datetime or None.
    """

    try:
        if isinstance(value, (int, float)):
            # Detect milliseconds vs seconds
            if value > 10_000_000_000:
                return datetime.fromtimestamp(
                    value / 1000,
                    tz=timezone.utc
                )

            return datetime.fromtimestamp(
                value,
                tz=timezone.utc
            )

        if isinstance(value, str) and value.strip():
            value = value.strip()

            # ISO date
            dt = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt

    except (ValueError, TypeError, OSError, OverflowError):
        pass

    return None

def make_job(
    title="",
    location="",
    url="",
    description="",
    date=None
):
    """
    Normalize every ATS result into the same structure.
    """
    return {
        "title": title or "",
        "location": location or "",
        "url": url or "",
        "description": description or "",
        "date": date,
    }

def get_json(url, **kwargs):
    """
    GET JSON helper.
    """
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        **kwargs
    )

    response.raise_for_status()

    return response.json()

def get_html(url, **kwargs):
    """
    GET HTML helper.
    """
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        **kwargs
    )

    response.raise_for_status()

    return response.text

RANGE_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*"
    r"(?:-|–|—|to)\s*"
    r"\d{1,2}\s*\+?\s*"
    r"(?:years|yrs)",
    re.I
)

SINGLE_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:years|yrs)",
    re.I
)

FRESHER_RE = re.compile(
    r"\b("
    r"freshers?"
    r"|entry[- ]level"
    r"|new grad(?:uate)?s?"
    r"|recent graduates?"
    r"|graduate engineer"
    r"|campus hire"
    r")\b",
    re.I
)

def extract_required_years(text):
    """
    Best-effort estimate of minimum required experience.

    Looks for experience patterns such as:
        2 years experience
        2+ years experience
        2-4 years experience

    Returns:
        int
        None if experience is not stated.
    """

    text = text or ""

    found = []

    for rx, group in (
        (RANGE_RE, 1),
        (SINGLE_RE, 1),
    ):
        for match in rx.finditer(text):

            context = text[
                max(0, match.start() - 100):
                match.end() + 100
            ].lower()

            if "experience" in context:
                found.append(
                    int(match.group(group))
                )

    if found:
        return min(found)

    if FRESHER_RE.search(text):
        return 0

    return None
