from __future__ import annotations

import logging
import re
from collections.abc import Iterator

from bs4 import BeautifulSoup

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.aggregators.excel import is_trade
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import at, parse_date_range, parse_price, parse_time
from whatson.registry import register

log = logging.getLogger(__name__)

_BG_URL = re.compile(r"url\([\"']?([^\"')]+)")
# No categories on the site; recognised from the title and intro.
KEYWORDS = [
    (re.compile(r"\bfestival\b", re.I), "Festival"),
    (re.compile(r"\b(workout|training|fitness|run club)\b", re.I), "Sport"),
    (re.compile(r"\b(christmas party|cirque|circus|club night)\b", re.I), "Nightlife"),
    (re.compile(r"\b(show|expo|exhibition|fair)\b", re.I), "Exhibition"),
]


@register
class TobaccoDock(BaseAggregator):
    """A hire venue: its What's On cards link to event pages with dates, space,
    "Prices from", times and a ticket link. Like ExCeL, much of the calendar is
    business conferences, which are left out using ExCeL's trade-show check."""

    venue_id = "tobaccodock"

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select("a.event-card[href]"):
            url = card["href"]
            try:
                page = self.get_html(url)
            except FetchError as e:
                log.warning("tobaccodock: skipping %s: %s", url, e)
                continue
            event = self._event(url, card, page)
            if event:
                yield event

    def _event(self, url: str, card, page: BeautifulSoup) -> Event | None:
        title = text_of(page.select_one(".event-summary-banner__title")) or text_of(
            card.select_one(".event-card__title")
        )
        details = {
            text_of(b.select_one(".details-list__title")).rstrip("?:").lower(): b.select_one(
                ".details-list__content"
            )
            for b in page.select(".details-list__block")
        }
        intro = " ".join(
            text_of(x)
            for x in page.select(".event-summary-banner__intro, .event-summary-banner__description")
        )
        if not title or is_trade(title, f"{intro} {text_of(details.get('the event'))}"):
            return None
        try:
            start, end, _ = parse_date_range(text_of(details.get("when")), self.today)
        except ValueError:
            return None
        if end is None:
            # One day: the schedule gives its opening time ("18:00 - 21:00").
            start = at(start, parse_time(text_of(page.select_one(".event-schedule__time"))))
        # "Dock Gallery, Tobacco Dock" names a space; "Wapping Lane Entrance" only a door.
        where = text_of(details.get("where")).split(",")[0].strip()
        space = (
            where
            if where and "tobacco dock" not in where.lower() and "entrance" not in where.lower()
            else None
        )
        price_min, _ = parse_price(text_of(details.get("tickets")))
        text = f"{title} {intro}"
        tags = [tag for pattern, tag in KEYWORDS if pattern.search(text)][:2]
        book = page.select_one("a.event-booking__btn[href]")
        bg = card.select_one(".event-card__bg")
        image = _BG_URL.search(bg.get("data-bg", "")) if bg else None
        return self.event(
            title=title,
            url=url,
            booking_url=book["href"] if book else None,
            category=tags[0] if tags else None,
            tags=tags,
            start=start,
            end=end,
            space=space,
            price_min=price_min,  # "Prices from": the cheapest
            image_url=image.group(1) if image else None,
            summary=intro or None,
        )
