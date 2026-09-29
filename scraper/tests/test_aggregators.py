from datetime import date, datetime

from conftest import FakeFetcher

from whatson import LONDON
from whatson.aggregators.barbican import Barbican
from whatson.aggregators.saatchi import API as SAATCHI_API
from whatson.aggregators.saatchi import SaatchiGallery
from whatson.aggregators.topsecret import AJAX as TOPSECRET_AJAX
from whatson.aggregators.topsecret import TopSecretComedyClub
from whatson.aggregators.unionchapel import UnionChapel
from whatson.registry import load_aggregators


def test_every_enabled_venue_has_an_aggregator(venues):
    aggregators = load_aggregators()
    missing = [v.id for v in venues.values() if v.enabled and v.id not in aggregators]
    assert not missing


def test_topsecret(venues):
    http = FakeFetcher(
        {
            f"{TOPSECRET_AJAX}|2026-09-29": "topsecret/2026-09-29.html",
            f"{TOPSECRET_AJAX}|2026-10-31": "topsecret/2026-10-31.html",
        }
    )
    agg = TopSecretComedyClub(venues["topsecret"], http, today=date(2026, 9, 29))
    agg.days_ahead = 1
    events = list(agg.fetch_events())

    assert len(events) == 4
    first = events[0]
    assert first.title == "Tim Renkow: Work In Progress"
    assert first.start == datetime(2026, 9, 29, 18, 0, tzinfo=LONDON)
    assert first.space == "170 Drury Lane (ground floor)"
    assert (first.price_min, first.price_max) == (1.0, 1.0)
    assert first.category == "Comedy"
    assert first.url.startswith("https://thetopsecretcomedyclub.co.uk/events-listings/")
    assert first.booking_url and first.booking_url.startswith("https://fixr.co/")

    agg.today = date(2026, 10, 31)
    halloween = list(agg.fetch_events())
    assert sum(e.sold_out for e in halloween) == 1
    assert all(e.start.date() == date(2026, 10, 31) for e in halloween)


def test_unionchapel(venues):
    detail = "https://unionchapel.org.uk/venue/whats-on/deva-premal-miten-live-in-london-2026"
    http = FakeFetcher(
        {
            venues["unionchapel"].url: "unionchapel/whats-on.html",
            detail: "unionchapel/deva-premal-miten-live-in-london-2026.html",
        }
    )
    events = list(UnionChapel(venues["unionchapel"], http, today=date(2026, 9, 29)).fetch_events())

    assert len(events) == 109
    deva = next(e for e in events if e.url == detail)
    assert deva.title == "Deva Premal & Miten | Live in London 2026"
    assert deva.start == datetime(2026, 9, 30, 19, 0, tzinfo=LONDON)  # from the detail page
    assert deva.category == "Music"
    assert deva.image_url and deva.image_url.endswith("(1).jpg")
    assert deva.booking_url and "gigantic.com" in deva.booking_url
    assert deva.summary

    # Other detail pages aren't in the fixtures: those events keep their date only.
    others = [e for e in events if e.url != detail]
    assert all(isinstance(e.start, date) and not isinstance(e.start, datetime) for e in others)
    assert sum(e.sold_out for e in events) == 1
    assert {e.category for e in events} == {"Music", "Workshop"}


def test_saatchi(venues):
    http = FakeFetcher({f"{SAATCHI_API}|page=1": "saatchi/exhibitions-page1.json"})
    agg = SaatchiGallery(venues["saatchi"], http, today=date(2026, 9, 29))
    events = list(agg.fetch_events())

    by_title = {}
    for e in events:
        by_title.setdefault(e.title, []).append(e)
    streets = by_title["BEYOND THE STREETS"][0]
    assert (streets.start, streets.end) == (date(2026, 11, 11), date(2027, 5, 5))
    assert streets.category == "Exhibition"
    assert streets.image_url

    lates = by_title["LATES: BEYOND THE STREETS"]
    assert [e.start for e in lates] == [date(2026, 11, 27), date(2026, 12, 4), date(2026, 12, 11)]
    assert all(e.category == "Nightlife" and e.end is None for e in lates)

    # Exhibitions that ended before today are dropped.
    assert all(e.last_day() >= date(2026, 9, 29) for e in events)


def test_barbican(venues):
    base = "https://www.barbican.org.uk/whats-on/2026/event/"
    http = FakeFetcher(
        {
            venues["barbican"].url: "barbican/whats-on.html",
            f"{venues['barbican'].url}?page=1": "barbican/whats-on-page1.html",
            **{
                base + slug: f"barbican/{slug}.html"
                for slug in (
                    "1765-times-of-transition",
                    "sense-and-sensibility",
                    "pam-tanowitz-dance-pastoral",
                )
            },
        }
    )
    agg = Barbican(venues["barbican"], http, today=date(2026, 9, 29))
    agg.max_pages = 2
    events = {e.url.rsplit("/", 1)[1]: e for e in agg.fetch_events()}

    # Only events whose page is in the fixtures come out; the rest are skipped.
    assert set(events) == {
        "1765-times-of-transition",
        "sense-and-sensibility",
        "pam-tanowitz-dance-pastoral",
    }

    concert = events["1765-times-of-transition"]
    assert concert.start == datetime(2026, 10, 1, 19, 30, tzinfo=LONDON)
    assert concert.end is None
    assert concert.space == "Milton Court Concert Hall"
    assert (concert.price_min, concert.price_max) == (19.0, 19.0)  # "From £19 (£15 + £4 fee)"
    assert concert.category == "Classical" and "Music" in concert.tags
    assert concert.image_url and concert.image_url.startswith("https://www.barbican.org.uk/")
    assert concert.summary

    film = events["sense-and-sensibility"]  # shown daily: a run, dates only
    assert (film.start, film.end) == (date(2026, 9, 25), date(2026, 10, 1))
    assert film.category == "Film" and film.space == "Barbican Cinemas"
    assert film.price_min == 15.5

    dance = events["pam-tanowitz-dance-pastoral"]
    assert (dance.start, dance.end) == (date(2026, 10, 1), date(2026, 10, 3))
    assert set(dance.tags) == {"Theatre", "Dance"}
    assert dance.space == "Barbican Theatre"


def test_barbican_prices():
    from bs4 import BeautifulSoup
    from conftest import FIXTURES

    from whatson.aggregators.barbican import _price

    page = BeautifulSoup(
        (FIXTURES / "barbican/bsl-architectural-tour-with-martin-glover.html").read_text(), "lxml"
    )
    assert _price(page) == (0.0, 12.0)  # "Pay What You Can £0 | £3 | … | £12"
    assert _price(BeautifulSoup("<p>No prices here</p>", "lxml")) == (None, None)
