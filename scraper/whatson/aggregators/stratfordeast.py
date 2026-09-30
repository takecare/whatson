from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import at, parse_date_range, parse_dates, parse_price, parse_time
from whatson.registry import register

log = logging.getLogger(__name__)

# Genres as the "You may also like" cards give them ("Panto, On Stage").
GENRES = {
    "drama": ["Theatre"],
    "musical": ["Theatre"],
    "panto": ["Theatre", "Family"],
    "family": ["Family"],
    "comedy": ["Comedy"],
    "dance": ["Dance"],
    "music": ["Music"],
    "concert": ["Music"],
}
ACCESS = [
    (re.compile(r"\bBSL\b|signed", re.I), "Signed"),
    (re.compile(r"captioned", re.I), "Captioned"),
    (re.compile(r"audio[- ]described", re.I), "Audio Described"),
    (re.compile(r"relaxed", re.I), "Relaxed"),
]
_COMEDY = re.compile(r"\b(stand-up|comedian|comedy special)\b", re.I)
# "Fri 02 Oct - Reggae Revival - 9pm-12am"
_BAR_EVENT = re.compile(r"^(\w{3}\s+\d{1,2}\s+\w{3,9})\s*-\s*(.+?)\s*-\s*(\d.*)$")
BAR_EVENTS = "bar-events"


@register
class StratfordEast(BaseAggregator):
    """Theatre Royal Stratford East. The listing links to each show's page, which
    lists every performance (date, time, price range, access notes). Genres only
    appear on the "You may also like" cards, so they're gathered across the show
    pages. The free bar nights are lines of text on their own page."""

    venue_id = "stratfordeast"

    def fetch_events(self) -> Iterator[Event]:
        listing = self.get_html(self.venue.url)
        pages: dict[str, tuple[BeautifulSoup, BeautifulSoup]] = {}
        genres: dict[str, str] = {}
        for card in listing.select("li.Exhib"):
            link = card.select_one("h2 a[href]")
            if link is None:
                continue
            url = urljoin(self.venue.url, link["href"])
            try:
                page = self.get_html(url)
            except FetchError as e:
                log.warning("stratfordeast: skipping %s: %s", url, e)
                continue
            pages[url] = (card, page)
            for like in page.select(".LikeText_Box"):
                other = like.select_one("h2 a[href]")
                if other:
                    genres[urljoin(url, other["href"])] = text_of(like.select_one("strong"))
        for url, (card, page) in pages.items():
            if url.rstrip("/").endswith(BAR_EVENTS):
                yield from self._bar_events(url, page)
            else:
                event = self._show(url, card, page, genres.get(url, ""))
                if event:
                    yield event

    def _show(self, url: str, card, page: BeautifulSoup, genre: str) -> Event | None:
        performances: list[datetime] = []
        prices: list[float] = []
        access: list[str] = []
        # The schedule is in the page twice (mobile and desktop layouts).
        for row in page.select("#schedules .mobileTicket li"):
            days = parse_dates(text_of(row.select_one(".DateSpan")), self.today)
            t = parse_time(text_of(row.select_one(".TimeSpan")))
            if not days or t is None:
                continue
            performances.append(at(days[0], t))  # type: ignore[arg-type]
            prices += [
                p for p in parse_price(text_of(row.select_one(".PriceSpan"))) if p is not None
            ]
            notes = text_of(row.select_one(".Accesibility"))
            access += [
                tag for pattern, tag in ACCESS if pattern.search(notes) and tag not in access
            ]
        title = text_of(page.select_one(".DetailBanner h2")) or text_of(card.select_one("h2"))
        tags: list[str] = []
        for word in re.split(r"[,/]", genre.lower()):
            tags += [t for t in GENRES.get(word.strip(), []) if t not in tags]
        if not tags:  # some shows only say "On Stage"
            about = text_of(page.select_one("#Details_in"))
            tags = ["Comedy"] if _COMEDY.search(about) else ["Theatre"]
        tags += access
        if performances:
            start, end = min(performances), None
        else:
            try:
                start, end, _ = parse_date_range(
                    text_of(card.select_one(".postDate_l")), self.today
                )
            except ValueError:
                return None
        description = page.select_one("meta[name=description]")
        src = image_src(card.select_one("img"))
        return self.event(
            title=title,
            url=url,
            booking_url=f"{url}#schedules",
            category=tags[0],
            tags=tags,
            start=start,
            end=end,
            performances=sorted(performances),
            price_min=min(prices) if prices else None,
            price_max=max(prices) if prices else None,
            image_url=urljoin(url, src) if src else None,
            summary=" ".join(description.get("content", "").split()) or None
            if description
            else None,
        )

    def _bar_events(self, url: str, page: BeautifulSoup) -> Iterator[Event]:
        details = page.select_one("#Details_in")
        if details is None:
            return
        for line in details.get_text("\n").splitlines():
            m = _BAR_EVENT.match(" ".join(line.split()))
            if not m:
                continue
            days = parse_dates(m[1], self.today)
            if not days:
                continue
            yield self.event(
                title=m[2],
                url=url,
                category="Nightlife",
                tags=["Nightlife", "Music"],
                start=at(days[0], parse_time(m[3])),
                price_min=0.0,
                summary="Free, in the Stratford East bar.",
            )
