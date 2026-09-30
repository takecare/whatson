from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urljoin

from whatson.aggregators.base import BaseAggregator, largest, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register

# The Young Vic's own spaces; the listing also has streams ("NT at Home") and
# productions elsewhere, which are skipped.
SPACES = {"main house": "Main House", "the maria theatre": "The Maria", "the clare": "The Clare"}
HERE = {*SPACES, "young vic"}


@register
class YoungVic(BaseAggregator):
    """One listing page of cards: title, run (sometimes as <time datetime>), space
    and image. The banner repeats a show that's also in the list."""

    venue_id = "youngvic"

    def fetch_events(self) -> Iterator[Event]:
        seen: set[str] = set()
        for card in self.get_html(self.venue.url).select(".c-event-card"):
            link = card.select_one("a.c-event-card__cover-link[href]")
            title = text_of(card.select_one(".c-event-card__title"))
            where = text_of(card.select_one(".c-event-card__event-venue"))
            if link is None or not title or where.lower() not in HERE:
                continue
            url = urljoin(self.venue.url, link["href"])
            if url in seen:
                continue
            try:
                start, end, _ = parse_date_range(
                    text_of(card.select_one(".c-event-card__time")), self.today
                )
            except ValueError:
                continue
            seen.add(url)
            img = card.select_one("img")
            image = largest(img.get("srcset", "")) if img else None
            yield self.event(
                title=title,
                url=url,
                category="Theatre",
                tags=["Theatre"],
                start=start,
                end=end,
                space=SPACES.get(where.lower()),
                image_url=urljoin(self.venue.url, image) if image else None,
            )
