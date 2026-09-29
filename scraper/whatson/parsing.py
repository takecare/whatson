"""Parsing helpers for the free-text dates, times and prices venue pages use."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from whatson import LONDON

MONTHS = {
    name: i
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sept", "sep"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}

_MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
_DATE_TOKEN = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+({_MONTH_RE})[a-z]*\.?)?(?:,?\s+(\d{{4}}))?\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_WEEKDAY = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?"
# What may stand between a bare day number and the next date: "3 - 11 Oct",
# "Wed 7 - Thu 8 Oct", "3, 4 & 5 Oct".
_JOINER = re.compile(
    rf"\s*(?:-|–|—|,|&|\band\b|\bto\b|\buntil\b)\s*(?:{_WEEKDAY}\s+)?", re.IGNORECASE
)
_RANGE_SEP = re.compile(r"\s*(?:-|–|—|\bto\b|\buntil\b)\s*", re.IGNORECASE)
_TIME = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b|\b(\d{1,2})[:.](\d{2})\b", re.I)
_TIME_RANGE = re.compile(
    r"\b(\d{1,2})(?:[:.](\d{2}))?\s*[-–]\s*(\d{1,2})(?:[:.]\d{2})?\s*(am|pm)\b", re.I
)
_PRICE = re.compile(r"£\s*(\d+(?:[.,]\d{1,2})?)")


def _infer_year(month: int, day: int, ref: date) -> date:
    """Pick the year for a date given without one: the closest that isn't long past."""
    d = date(ref.year, month, day)
    if d < ref - timedelta(days=90):
        d = date(ref.year + 1, month, day)
    return d


def parse_dates(text: str, ref: date | None = None) -> list[date]:
    """All dates mentioned in ``text``, filling in missing months/years.

    Handles "28th September 2026", "Wed 30 Sep 2026", "3 - 11 October" (the month is
    borrowed from the following date) and dates without a year (inferred from ``ref``).
    """
    ref = ref or date.today()
    iso = [date(int(y), int(m), int(d)) for y, m, d in _ISO_DATE.findall(text)]
    if iso:
        return iso

    tokens: list[list[int | None]] = []
    spans: list[tuple[int, int]] = []
    for m in _DATE_TOKEN.finditer(text):
        day, month, year = m.groups()
        tokens.append(
            [int(day), MONTHS[month.lower()] if month else None, int(year) if year else None]
        )
        spans.append(m.span())
    # A bare number ("3" in "3 - 11 October") borrows the month of the next date, but
    # only when nothing but a separator stands between them.
    for i in range(len(tokens) - 2, -1, -1):
        between = text[spans[i][1] : spans[i + 1][0]]
        if not _JOINER.fullmatch(between):
            continue
        if tokens[i][1] is None:
            tokens[i][1] = tokens[i + 1][1]
        if tokens[i][2] is None and tokens[i][1] == tokens[i + 1][1]:
            tokens[i][2] = tokens[i + 1][2]
    out: list[date] = []
    for i, (day, month, year) in enumerate(tokens):
        if month is None or day is None or not 1 <= day <= 31:
            continue
        try:
            if year is not None:
                d = date(year, month, day)
            elif out:
                d = date(out[-1].year, month, day)
                if d < out[-1]:
                    d = date(out[-1].year + 1, month, day)
            else:
                # Year only known from a later token: "30 December - 5 January 2027".
                later = next((t[2] for t in tokens[i + 1 :] if t[2]), None)
                if later is not None:
                    d = date(later, month, day)
                    if tokens[-1][1] is not None and month > tokens[-1][1]:
                        d = date(later - 1, month, day)
                else:
                    d = _infer_year(month, day, ref)
        except ValueError:
            continue
        out.append(d)
    return out


def parse_date_range(text: str, ref: date | None = None) -> tuple[date, date | None, list[date]]:
    """Parse a run ("3 - 11 October") or a list of dates ("27 Nov, 4 Dec").

    Returns (start, end, dates). ``end`` is set for runs; ``dates`` lists every date
    for a comma-separated list. Raises ValueError when no date is found.
    """
    dates = parse_dates(text, ref)
    if not dates:
        raise ValueError(f"no date in {text!r}")
    if len(dates) == 2 and _RANGE_SEP.search(text):
        start, end = dates
        return start, (end if end != start else None), []
    if len(dates) > 1:
        return min(dates), max(dates), sorted(dates)
    return dates[0], None, []


def parse_time(text: str) -> time | None:
    """First time of day in ``text``: "6:00PM", "7pm", "7.30pm", "19:30", or the start
    of a range like "4-5pm" (4pm, not 5pm)."""
    r = _TIME_RANGE.search(text)
    if r:
        hour, minute, end_hour, meridiem = int(r[1]), int(r[2] or 0), int(r[3]), r[4].lower()
        if hour <= 12 and minute <= 59:
            if meridiem == "pm" and hour <= end_hour and hour != 12:
                hour += 12  # "4-5pm" → 16:00 ("11-1pm" stays 11:00)
            return time(hour % 24, minute)
    m = _TIME.search(text)
    if not m:
        return None
    if m.group(3):
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        hour = hour % 12 + (12 if m.group(3).lower() == "pm" else 0)
    else:
        hour, minute = int(m.group(4)), int(m.group(5))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def at(day: date, t: time | None) -> date | datetime:
    """Combine a date and optional time into a London-local datetime (or keep the date)."""
    return datetime.combine(day, t, tzinfo=LONDON) if t else day


def parse_price(text: str) -> tuple[float | None, float | None]:
    """(min, max) of the £ amounts in ``text``; "free" counts as 0. (None, None) if none."""
    amounts = [float(a.replace(",", ".")) for a in _PRICE.findall(text)]
    if re.search(r"\bfree\b", text, re.IGNORECASE):
        amounts.append(0.0)
    if not amounts:
        return None, None
    return min(amounts), max(amounts)
