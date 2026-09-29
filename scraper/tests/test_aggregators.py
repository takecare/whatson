from datetime import date, datetime

from conftest import FakeFetcher

from whatson import LONDON
from whatson.aggregators.barbican import Barbican
from whatson.aggregators.princecharles import PrinceCharlesCinema
from whatson.aggregators.saatchi import API as SAATCHI_API
from whatson.aggregators.saatchi import SaatchiGallery
from whatson.aggregators.sadlerswells import (
    PeacockTheatre,
    SadlersWellsClerkenwell,
    SadlersWellsEast,
)
from whatson.aggregators.southbank import SouthbankCentre
from whatson.aggregators.southwarkparkgalleries import API as SPG_API
from whatson.aggregators.southwarkparkgalleries import SouthwarkParkGalleries
from whatson.aggregators.theo2 import AJAX, RSS, Indigo, O2Arena
from whatson.aggregators.topsecret import AJAX as TOPSECRET_AJAX
from whatson.aggregators.topsecret import TopSecretComedyClub
from whatson.aggregators.unionchapel import UnionChapel
from whatson.aggregators.wiltons import WiltonsMusicHall
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


def test_princecharles(venues):
    http = FakeFetcher({venues["princecharles"].url: "princecharles/whats-on.html"})
    agg = PrinceCharlesCinema(venues["princecharles"], http, today=date(2026, 9, 29))
    events = {e.title: e for e in agg.fetch_events()}

    assert len(events) == 9
    fallen = events["Fallen Angels"]
    assert fallen.category == "Film"
    assert fallen.performances == [
        datetime(2026, 9, 29, 15, 15, tzinfo=LONDON),
        datetime(2026, 11, 8, 17, 30, tzinfo=LONDON),
        datetime(2026, 11, 23, 12, 30, tzinfo=LONDON),
    ]
    assert fallen.start == fallen.performances[0]
    assert fallen.summary and fallen.summary.startswith("4K. ")
    assert fallen.image_url and fallen.url.startswith("https://princecharlescinema.com/film/")
    assert fallen.price_min is None  # not on the listing

    # Sold out only when every showing is.
    assert events["Silence"].sold_out and events["Teen Wolf"].sold_out
    assert not events["Barry Lyndon"].sold_out
    assert len(events["In The Mood For Love"].performances) == 14


def test_theo2(venues):
    arena = venues["o2arena"]
    http = FakeFetcher(
        {
            RSS: "theo2/rss.xml",
            arena.url: "theo2/the-o2-arena.html",
            f"{AJAX.format(offset=24)}?category=0&venue=1&team=0&exclude=&per_page=24"
            "&came_from_page=event-list-page": "theo2/events_ajax-24.json",
        }
    )
    agg = O2Arena(arena, http, today=date(2026, 9, 29))
    agg.max_pages = 2
    listed = list(agg.fetch_events())
    events = {e.title: e for e in listed}

    assert len(listed) == 100  # the arena's 102 feed items, minus 2 cancelled
    assert "Brandi Carlile" not in events and "Brandi Carlile | Cancelled" not in events
    niall = events["Niall Horan"]  # two nights: a run
    assert (niall.start, niall.end) == (date(2026, 10, 2), date(2026, 10, 3))
    assert niall.tags == ["Music"]
    assert niall.summary == "Plus special guest Flowerovlove"  # the card's tagline
    assert niall.image_url and niall.booking_url and "axs.com" in niall.booking_url
    bailey = events["Bill Bailey : Vaudevillean"]
    assert bailey.start == datetime(2026, 11, 22, 18, 0, tzinfo=LONDON)
    assert bailey.category == "Comedy"
    assert events["Dubois vs Wardley 2"].category == "Sport"
    # The two listing pages hold 48 cards, one of them for a cancelled event.
    assert sum(1 for e in listed if e.image_url) == 47


def test_o2_venues_share_one_feed_request(venues):
    http = FakeFetcher({RSS: "theo2/rss.xml"})
    today = date(2026, 9, 29)
    list(O2Arena(venues["o2arena"], http, today).fetch_events())
    list(Indigo(venues["indigo"], http, today).fetch_events())
    assert http.requested.count(RSS) == 1


def test_indigo_without_listing(venues):
    # If the listing pages fail, events still come from the feed, just without images.
    http = FakeFetcher({RSS: "theo2/rss.xml"})
    agg = Indigo(venues["indigo"], http, today=date(2026, 9, 29))
    listed = list(agg.fetch_events())
    events = {e.title: e for e in listed}
    assert len(listed) == 52  # 57 feed items, 5 cancelled
    assert not any(t.endswith("Cancelled") for t in events)
    assert events["Wahala Comedy Clash"].category == "Comedy"
    assert events["Wahala Comedy Clash"].summary  # from the feed's description
    assert not any(e.image_url for e in listed)


def test_wiltons(venues):
    url = venues["wiltons"].url
    http = FakeFetcher(
        {
            url: "wiltons/whats-on.html",
            f"{url}?event-page=2": "wiltons/whats-on-page2.html",
            f"{url}?event-page=3": "wiltons/whats-on-page3.html",
        }
    )
    listed = list(WiltonsMusicHall(venues["wiltons"], http, today=date(2026, 9, 29)).fetch_events())
    events = {e.title: e for e in listed}

    assert len(listed) == 30  # 28 cards; two "History Tours" cards list two dates each
    tim = events["Tim Key: Loganberry"]  # "Mon 28 Sep - Sat 3 Oct, 7:45pm"
    assert (tim.start, tim.end) == (date(2026, 9, 28), date(2026, 10, 3))
    assert (tim.price_min, tim.price_max) == (12.0, 26.0)  # full price, not concessions
    assert tim.category == "Comedy" and tim.image_url
    film = events["The Cabinet of Dr Caligari (1920) with live score"]
    assert film.start == datetime(2026, 10, 6, 19, 0, tzinfo=LONDON)
    assert film.category == "Film"
    incendiary = events["INCENDIARY – Samuel Pepys in Words and Music"]  # "Wed 7 - Thu 8 Oct"
    assert (incendiary.start, incendiary.end) == (date(2026, 10, 7), date(2026, 10, 8))
    assert events["Stewart Lee’s Pea Green Boat"].sold_out
    tours = sorted(e.start for e in listed if e.title == "History Tours")
    assert tours[:2] == [
        datetime(2026, 10, 24, 17, 0, tzinfo=LONDON),
        datetime(2026, 10, 31, 17, 0, tzinfo=LONDON),
    ]
    assert http.requested[-1] == f"{url}?event-page=3"  # stops at the first short page


def test_southbank(venues):
    url = venues["southbankcentre"].url
    http = FakeFetcher(
        {
            f"{url}?artform-filter=gigs": "southbank/gigs.html",
            f"{url}?start-date=2026-10-02&end-date=2026-10-02": "southbank/day-2026-10-02.html",
        }
    )
    agg = SouthbankCentre(venues["southbankcentre"], http, today=date(2026, 10, 2))
    agg.days_ahead = 1
    listed = list(agg.fetch_events())
    events = {e.title: e for e in listed}

    # 12 gig cards + 11 day cards, 3 of them on both pages; other art forms are skipped.
    assert len(listed) == 20
    orii = events["ORII Presents feat. BXKS"]
    assert orii.start == datetime(2026, 10, 2, 19, 30, tzinfo=LONDON)  # "7.30pm"
    assert orii.space == "Purcell Room" and orii.category == "Music"
    assert orii.price_min is None and orii.image_url
    assert events["futuretense x DOTWAVNOTWAVE"].price_min == 0.0  # "Tickets Free"
    kapoor = events["Anish Kapoor"]
    assert (kapoor.start, kapoor.end) == (date(2026, 6, 16), date(2026, 10, 18))
    assert kapoor.category == "Exhibition" and "Art" in kapoor.tags
    # The literature event on the gigs page keeps its own category but gains Music.
    tice = events["Tice Cin: Safe Spaces"]
    assert tice.category == "Talks" and "Music" in tice.tags
    assert events["Playing with Fire"].end == date(2027, 1, 3)


def test_sadlerswells_stages(venues):
    base = "https://www.sadlerswells.com/whats-on/"
    routes = {base: "sadlerswells/page1.html"}
    routes |= {f"{base}page/{n}/": f"sadlerswells/page{n}.html" for n in range(2, 6)}
    today = date(2026, 9, 29)

    def run(cls, venue_id):
        return list(cls(venues[venue_id], FakeFetcher(routes), today).fetch_events())

    clerkenwell = run(SadlersWellsClerkenwell, "sadlerswells")
    peacock = run(PeacockTheatre, "peacock")
    east = run(SadlersWellsEast, "sadlerswellseast")

    assert (len(clerkenwell), len(peacock), len(east)) == (28, 3, 15)
    # Page one repeats highlights; each event appears once.
    assert len({e.url for e in clerkenwell}) == len(clerkenwell)
    assert {e.space for e in clerkenwell} == {"Sadler's Wells Theatre", "Lilian Baylis Studio"}
    snowman = next(e for e in peacock if e.title == "The Snowman")
    assert (snowman.start, snowman.end) == (date(2026, 11, 21), date(2027, 1, 3))
    assert snowman.space is None and snowman.image_url and "640" in snowman.image_url
    rhythm = next(e for e in clerkenwell if e.title == "English National Ballet - Rhythm Riot")
    assert (rhythm.start, rhythm.end) == (date(2026, 9, 30), date(2026, 10, 3))


def test_southwarkparkgalleries(venues):
    fixtures = "southwarkparkgalleries"
    base = "https://southwarkparkgalleries.org/"
    routes = {f"{SPG_API}|page=1": f"{fixtures}/posts.json"}
    for slug in (
        "danfong-wang-the-sparkle-the-blossom-and-the-milky-land",
        "green-shoots-free-creative-family-workshops-2026",
        "in-conversation-isabel-nolan-with-judith-carlton",
    ):
        routes[f"{base}{slug}/"] = f"{fixtures}/{slug}.html"
    venue = venues["southwarkparkgalleries"]
    agg = SouthwarkParkGalleries(venue, FakeFetcher(routes), date(2026, 9, 29))
    events = {e.title: e for e in agg.fetch_events()}

    # Posts whose page isn't in the fixtures are skipped.
    assert set(events) == {
        "The Sparkle, The Blossom and The Milky Land",
        "Green Shoots! Family Workshops",
        "In Conversation with Isabel Nolan",
    }
    sparkle = events["The Sparkle, The Blossom and The Milky Land"]
    assert (sparkle.start, sparkle.end) == (date(2026, 8, 15), date(2026, 11, 1))
    assert sparkle.category == "Exhibition" and sparkle.space == "Lake Gallery"
    assert sparkle.image_url and sparkle.summary
    shoots = events["Green Shoots! Family Workshops"]  # dates from the title line
    assert (shoots.start, shoots.end) == (date(2026, 5, 17), date(2026, 10, 25))
    assert set(shoots.tags) == {"Workshop", "Family"}
    talk = events["In Conversation with Isabel Nolan"]  # "Time: Friday 16 October, 4-5pm"
    assert talk.start == datetime(2026, 10, 16, 16, 0, tzinfo=LONDON)
    assert talk.category == "Talks"
