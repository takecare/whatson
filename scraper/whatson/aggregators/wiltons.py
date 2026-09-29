from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import at, parse_date_range, parse_price, parse_time
from whatson.registry import register

MAX_PAGES = 30
PER_PAGE = 12

# Wilton's genres mapped onto our tags; the first is the main category.
GENRES = {
    "comedy": ["Comedy"],
    "film": ["Film"],
    "new writing": ["Theatre"],
    "theatre": ["Theatre"],
    "musical theatre": ["Theatre", "Music"],
    "music": ["Music"],
    "music hall": ["Theatre", "Music"],
    "cabaret": ["Theatre", "Nightlife"],
    "opera": ["Opera", "Music"],
    "family": ["Family"],
    "magic": ["Theatre", "Family"],
    "heritage tour": ["Tours"],
}
_GENRE = re.compile(r'whatson-event-vanue-link"[^>]*>([^<]+)<')


@register
class WiltonsMusicHall(BaseAggregator):
    """WordPress listing, 12 shows a page, paginated with ?event-page=N (the theme's
    /page/N/ links just repeat page one). Each card has
    the date(s) and time ("Mon 28 Sep - Sat 3 Oct, 7:45pm") and an availability
    badge; the price and genre are in HTML comments inside the card."""

    venue_id = "wiltons"

    def fetch_events(self) -> Iterator[Event]:
        for page in range(1, MAX_PAGES + 1):
            soup = self.get_html(self.venue.url, {"event-page": page} if page > 1 else None)
            cards = soup.select("li.WhatsonItem")
            if not cards:
                break
            for card in cards:
                yield from self._parse_card(card)
            if len(cards) < PER_PAGE:
                break

    def _parse_card(self, card) -> list[Event]:
        link = card.select_one(".WhatsonItemTitle h3 a[href]")
        when = text_of(card.select_one(".EV_ListDate"))
        if link is None or not when:
            return []
        dates_text, _, time_text = when.partition(",")
        try:
            start, end, separate = parse_date_range(dates_text, self.today)
        except ValueError:
            return []
        time = parse_time(time_text)

        comments = " ".join(str(c) for c in card.find_all(string=lambda s: isinstance(s, Comment)))
        genre = _GENRE.search(comments)
        tags = GENRES.get(genre.group(1).strip().lower(), []) if genre else []
        price_text = BeautifulSoup(comments, "lxml").get_text(" ")
        full = price_text.split("full price", 1)[0] if "full price" in price_text else price_text
        price_min, price_max = parse_price(full.split("Running time", 1)[0])

        img = card.select_one(".whatson-event-listing-img-area img[src]")
        availability = card.select_one("[class*=availability_]")
        classes = " ".join(availability.get("class", [])) if availability else ""
        url = link["href"].rstrip("/") + "/"
        common = {
            "title": text_of(link),
            "url": url,
            "booking_url": url + "#Tickets_in",
            "category": tags[0] if tags else None,
            "tags": tags,
            "price_min": price_min,
            "price_max": price_max,
            "sold_out": "availability_SoldOut" in classes,
            "image_url": urljoin(self.venue.url, img["src"]) if img else None,
        }
        if separate:  # "Sat 24 Oct & Sat 31 Oct, 5pm": one event per date
            return [self.event(start=at(d, time), **common) for d in separate]
        if end:  # a run ("Mon 28 Sep - Sat 3 Oct") keeps its dates
            return [self.event(start=start, end=end, **common)]
        return [self.event(start=at(start, time), **common)]
