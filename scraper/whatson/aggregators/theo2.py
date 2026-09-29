from __future__ import annotations

import html
import json
import logging
import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any, ClassVar
from weakref import WeakKeyDictionary

from bs4 import BeautifulSoup

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.registry import register

log = logging.getLogger(__name__)

RSS = "https://www.theo2.co.uk/events/rss"
AJAX = "https://www.theo2.co.uk/events/events_ajax/{offset}"
PER_PAGE = 24

# The feed's event types mapped onto our tags ("Entertainment" gets none).
MUSIC = ("Pop", "Rock", "World", "Hip Hop", "Dance", "R&B", "Country", "Indie", "K Pop",
         "Soul", "Reggae", "Afrobeats")  # fmt: skip
TYPES = {
    **{t.lower(): ["Music"] for t in MUSIC},
    "classical": ["Classical", "Music"],
    "comedy": ["Comedy"],
    "sport": ["Sport"],
    "family": ["Family"],
}
_FEEDS: WeakKeyDictionary[Any, str] = WeakKeyDictionary()

# Suffixes added to titles of events that aren't going ahead here.
_NOT_ON = re.compile(r"\s*\|\s*(cancelled|postponed|venue change|rescheduled)\s*$", re.I)


class TheO2(BaseAggregator):
    """The O2's venues share one site. Its RSS feed (/events/rss) lists every event
    at every venue with start and end times and an event type. The venue's listing
    pages add what the feed lacks: image, tagline, ticket link and sold-out state.
    They show 24 events; "Load more" asks /events/events_ajax/{offset} for the next
    24 (a JSON string of the same HTML).
    """

    o2_venue: ClassVar[int]
    max_pages = 20
    min_interval = 3.0  # the site answers 406 for a while if asked quickly

    def fetch_events(self) -> Iterator[Event]:
        # The feed first: it's the one request we can't do without, and the site
        # starts answering 406 after a handful of requests. Both venues read the same
        # feed, so it's fetched once per HTTP client (i.e. once per run).
        if self.http not in _FEEDS:
            _FEEDS[self.http] = self.http.get_text(RSS)
        feed = BeautifulSoup(_FEEDS[self.http], "xml")
        cards = self._cards()
        for item in feed.find_all("item"):
            if text_of(item.find("location")).lower() != self.venue.name.lower():
                continue
            event = self._parse_item(item, cards)
            if event:
                yield event

    def _parse_item(self, item: Any, cards: dict[str, Any]) -> Event | None:
        title = text_of(item.find("title"))
        url = text_of(item.find("link"))
        if not title or not url or _NOT_ON.search(title):
            return None
        try:
            first = _london(text_of(item.find("startdate")))
            last = _london(text_of(item.find("enddate")) or text_of(item.find("startdate")))
        except ValueError:
            return None
        tags = [t for ty in item.find_all("type") for t in TYPES.get(text_of(ty).lower(), [])]
        tags = list(dict.fromkeys(tags))

        card = cards.get(url)
        summary = text_of(card.select_one(".tagline")) if card else ""
        if not summary:
            description = BeautifulSoup(html.unescape(text_of(item.find("description"))), "lxml")
            summary = text_of(description.find("p")) or text_of(description)
        buttons = ""
        if card:
            buttons = " ".join(" ".join(a.get("class", [])) for a in card.select(".buttons a"))
        tickets = card.select_one(".buttons a.tickets[href]") if card else None
        img = card.select_one(".thumb img[src]") if card else None

        several_days = last.date() > first.date()
        return self.event(
            title=title,
            url=url,
            booking_url=tickets["href"] if tickets else None,
            category=tags[0] if tags else None,
            tags=tags,
            # A run of nights: we only know the first and last, so show the dates.
            start=first.date() if several_days else first,
            end=last.date() if several_days else None,
            sold_out="soldout" in buttons.replace("-", "").replace("_", "").lower(),
            image_url=img["src"] if img else None,
            summary=summary or None,
        )

    def _cards(self) -> dict[str, Any]:
        """Listing cards by event URL. Optional: without them events just lack images."""
        cards: dict[str, Any] = {}

        def add(page_html: str) -> int:
            found = 0
            for card in BeautifulSoup(page_html, "lxml").select(".eventItem"):
                link = card.select_one("h3.title a[href]")
                if link:
                    cards.setdefault(link["href"], card)
                    found += 1
            return found

        try:
            if add(self.http.get_text(self.venue.url)) < PER_PAGE:
                return cards
            for page in range(1, self.max_pages):
                params = {
                    "category": 0,
                    "venue": self.o2_venue,
                    "team": 0,
                    "exclude": "",
                    "per_page": PER_PAGE,
                    "came_from_page": "event-list-page",
                }
                raw = self.http.get_text(AJAX.format(offset=page * PER_PAGE), params)
                try:
                    page_html = json.loads(raw)
                except json.JSONDecodeError:
                    page_html = raw
                if add(page_html) < PER_PAGE:
                    break
        except FetchError as e:
            log.warning("%s: listing incomplete (%s); some events lack images", self.venue_id, e)
        return cards


def _london(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LONDON)


@register
class O2Arena(TheO2):
    venue_id = "o2arena"
    o2_venue = 1


@register
class Indigo(TheO2):
    venue_id = "indigo"
    o2_venue = 2
