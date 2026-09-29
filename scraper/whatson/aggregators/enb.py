from __future__ import annotations

from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import load_venues, register


@register
class EnglishNationalBallet(BaseAggregator):
    """A touring company, not a venue: its What's On page lists productions with
    where and when they play. We keep the London ones, with the theatre as the
    space, and skip those at venues we already collect (e.g. Sadler's Wells) so
    they aren't listed twice."""

    venue_id = "enb"

    def fetch_events(self) -> Iterator[Event]:
        collected = [
            v.name.lower() for v in load_venues().values() if v.enabled and v.id != self.venue_id
        ]
        for card in self.get_html(self.venue.url).select(".card--performance"):
            where = text_of(card.select_one(".card__meta-item--location"))
            if "london" not in where.lower():
                continue
            if any(name in where.lower() for name in collected):
                continue
            try:
                start, end, _ = parse_date_range(
                    text_of(card.select_one(".card__meta-item--date")), self.today
                )
            except ValueError:
                continue
            link = card.select_one("a[href]")
            yield self.event(
                title=text_of(card.select_one(".card__title")),
                url=link["href"] if link else self.venue.url,
                category="Dance",
                start=start,
                end=end,
                space=where.removesuffix(", London").strip(),
                image_url=image_src(card.select_one("img")),
            )
