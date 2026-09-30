from __future__ import annotations

import re
from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register

_TOUR = re.compile(r"\btour\b", re.I)


def largest(srcset: str) -> str | None:
    """The widest candidate in an ``srcset`` ("url 480w, url 960w")."""
    candidates = []
    for part in srcset.split(","):
        url, _, width = part.strip().rpartition(" ")
        if url and width.endswith("w") and width[:-1].isdigit():
            candidates.append((int(width[:-1]), url))
    return max(candidates)[1] if candidates else None


@register
class Almeida(BaseAggregator):
    """One listing page of cards: title, run, sold-out state and artwork (lazy
    loaded, so the real image is in data-srcset)."""

    venue_id = "almeida"

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select(".c-event-card"):
            link = card.select_one("a.c-event-card__permalink[href]")
            title = text_of(card.select_one(".c-event-card__title"))
            if link is None or not title:
                continue
            try:
                start, end, _ = parse_date_range(
                    text_of(card.select_one(".c-event-card__daterange")), self.today
                )
            except ValueError:
                continue
            buttons = text_of(card.select_one(".c-event-card__buttons")).lower()
            tags = ["Tours"] if _TOUR.search(title) else ["Theatre"]
            img = card.select_one("img")
            yield self.event(
                title=title,
                url=link["href"],
                category=tags[0],
                tags=tags,
                start=start,
                end=end,
                sold_out="sold out" in buttons,
                image_url=largest(img.get("data-srcset", "")) if img else None,
            )
