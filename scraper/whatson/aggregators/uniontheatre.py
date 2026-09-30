from __future__ import annotations

from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register


@register
class UnionTheatre(BaseAggregator):
    """WordPress listing of show thumbnails: title, dates ("3 October 2026 -
    18 October 2026"), image and a Savoy booking link. No times or prices."""

    venue_id = "uniontheatre"

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select(".thumbnail"):
            title = text_of(card.select_one(".caption h2"))
            link = card.select_one("a[href*='/show/']")
            if not title or link is None:
                continue
            try:
                start, end, _ = parse_date_range(text_of(card.select_one(".dates")), self.today)
            except ValueError:
                continue
            book = card.select_one("a[href*='savoysystems']")
            yield self.event(
                title=title,
                url=link["href"],
                booking_url=book["href"] if book else None,
                category="Theatre",
                tags=["Theatre"],
                start=start,
                end=end,
                image_url=image_src(card.select_one("img")),
            )
