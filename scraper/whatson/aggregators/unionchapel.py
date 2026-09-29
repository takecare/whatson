from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import time

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import at, parse_dates, parse_price, parse_time
from whatson.registry import register

log = logging.getLogger(__name__)

# Their "Event type" filter labels (read from the page) mapped onto our taxonomy.
EVENT_TYPES = {"theatre": "Theatre", "concert": "Music", "workshop": "Workshop"}
ACCESS_CLASSES = {
    "cat-signed": "Signed",
    "cat-relaxed": "Relaxed",
    "cat-audio-described": "Audio Described",
}
Price = tuple[float | None, float | None]
_BG_URL = re.compile(r"url\((?:\"(.*?)\"|'(.*?)'|([^)]*))\)")


@register
class UnionChapel(BaseAggregator):
    """Server-rendered card grid; the start time and blurb come from each event's page."""

    venue_id = "unionchapel"
    fetch_details = True

    def fetch_events(self) -> Iterator[Event]:
        soup = self.get_html(self.venue.url)
        type_classes = {
            a["data-filter-value"].lstrip("."): EVENT_TYPES.get(text_of(a).lower())
            for a in soup.select('[data-filter-group="event"] a[data-filter-value^=".cla-"]')
        }
        for card in soup.select("#items .item[data-chron]"):
            event = self._parse_card(card, type_classes)
            if event:
                yield event

    def _parse_card(self, card, type_classes: dict[str, str | None]) -> Event | None:
        dates = parse_dates(card.get("data-chron", ""), self.today)
        link = card.select_one("a.btn-info") or card.select_one("a[href]")
        title_el = card.select_one(".card-inner .card-title") or card.select_one(".card-title")
        if not dates or link is None or title_el is None:
            return None
        classes = card.get("class", [])
        tags = [ACCESS_CLASSES[c] for c in classes if c in ACCESS_CLASSES]
        category = next((type_classes[c] for c in classes if type_classes.get(c)), "Music")
        top = text_of(card.select_one(".card-top"))
        book = card.select_one("a.btn-primary")
        image = card.select_one(".card-image")
        image_match = _BG_URL.search(image.get("style", "")) if image else None

        url = link["href"]
        start_time, summary, price = self._details(url)
        return self.event(
            title=text_of(title_el),
            url=url,
            booking_url=book["href"] if book else None,
            category=category,
            tags=tags,
            start=at(dates[0], start_time),
            sold_out=top.upper() == "SOLD OUT",
            image_url=next((g for g in image_match.groups() if g), None) if image_match else None,
            summary=summary or (top if top and top.upper() != "SOLD OUT" else None),
            price_min=price[0],
            price_max=price[1],
        )

    def _details(self, url: str) -> tuple[time | None, str | None, Price]:
        if not self.fetch_details:
            return None, None, (None, None)
        try:
            soup = self.get_html(url)
        except FetchError as e:
            log.warning("unionchapel: no details for %s: %s", url, e)
            return None, None, (None, None)
        info = soup.select_one("aside .pl-4")
        start = None
        if info:
            lines = [text_of(p) for p in info.find_all("p")]
            start_line = next((ln for ln in lines if ln.lower().startswith("start")), "")
            start = parse_time(start_line) or parse_time(
                next((ln for ln in lines if ln.lower().startswith("doors")), "")
            )
        body = [text_of(p) for p in soup.select(".pt-4 p")]
        summary = next((b for b in body if len(b) > 60), None)
        price_line = next((b for b in body if "£" in b and "ticket" in b.lower()), "")
        return start, summary, parse_price(price_line)
