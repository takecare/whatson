from datetime import date, time

import pytest

from whatson.parsing import parse_date_range, parse_dates, parse_price, parse_time

REF = date(2026, 9, 29)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("28th September 2026", [date(2026, 9, 28)]),
        ("Wed 30 Sep 2026", [date(2026, 9, 30)]),
        ("Wednesday 30th September 2026", [date(2026, 9, 30)]),
        ("2026-09-30 00:00:00", [date(2026, 9, 30)]),
        ("Starts 6:00PM on 3 October", [date(2026, 10, 3)]),
        # No year: the next occurrence that isn't long past.
        ("14 February", [date(2027, 2, 14)]),
        ("1 September", [date(2026, 9, 1)]),
    ],
)
def test_parse_dates(text, expected):
    assert parse_dates(text, REF) == expected


@pytest.mark.parametrize(
    ("text", "start", "end", "dates"),
    [
        ("11 November 2026 - 5 May 2027", date(2026, 11, 11), date(2027, 5, 5), []),
        ("3 - 11 October", date(2026, 10, 3), date(2026, 10, 11), []),
        ("Wed 7 - Thu 8 Oct", date(2026, 10, 7), date(2026, 10, 8), []),
        ("Mon 28 Sep - Sat 3 Oct", date(2026, 9, 28), date(2026, 10, 3), []),
        ("18 – 19 September", date(2026, 9, 18), date(2026, 9, 19), []),
        ("3 October - 5 November 2026", date(2026, 10, 3), date(2026, 11, 5), []),
        ("30 December - 5 January 2027", date(2026, 12, 30), date(2027, 1, 5), []),
        ("12 December - 3 January", date(2026, 12, 12), date(2027, 1, 3), []),
        (
            "27 November, 4 December, 11 December",
            date(2026, 11, 27),
            date(2026, 12, 11),
            [date(2026, 11, 27), date(2026, 12, 4), date(2026, 12, 11)],
        ),
        ("Until 5 October", date(2026, 10, 5), None, []),
    ],
)
def test_parse_date_range(text, start, end, dates):
    assert parse_date_range(text, REF) == (start, end, dates)


def test_parse_date_range_without_dates():
    with pytest.raises(ValueError):
        parse_date_range("Every Monday and Thursday", REF)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Starts: 6:00PM", time(18, 0)),
        ("Doors 7pm", time(19, 0)),
        ("Start 7.30pm", time(19, 30)),
        ("12:15am", time(0, 15)),
        ("19:30", time(19, 30)),
        ("Friday 16 October, 4-5pm", time(16, 0)),
        ("10am-1pm", time(10, 0)),
        ("11-1pm", time(11, 0)),
        ("TBC", None),
    ],
)
def test_parse_time(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("£15", (15.0, 15.0)),
        ("£12.50 – £30", (12.5, 30.0)),
        ("£1 Concessions: FREE", (0.0, 1.0)),
        ("Free", (0.0, 0.0)),
        ("Tickets available soon", (None, None)),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected
