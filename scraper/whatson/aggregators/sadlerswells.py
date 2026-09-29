from __future__ import annotations

import re
from collections.abc import Iterator
from typing import ClassVar

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register

LISTING = "https://www.sadlerswells.com/whats-on/"
MAX_PAGES = 20
_WIDTH = re.compile(r"(\S+)\s+640w")


class SadlersWells(BaseAggregator):
    """Sadler's Wells runs several stages from one listing (/whats-on/page/N/, 12 a
    page after a highlights strip on page one). Each card is marked with its stage
    (class "u-venue-peacock-theatre"), so each of our venues keeps its own stages.
    Cards give the date or run, not times or prices.
    """

    stages: ClassVar[dict[str, str]]
    """Card venue class -> space name, for the stages that belong to this venue."""

    def fetch_events(self) -> Iterator[Event]:
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            url = LISTING if page == 1 else f"{LISTING}page/{page}/"
            cards = self.get_html(url).select(".c-event-card")
            if not cards:
                break
            for card in cards:
                link = card.select_one("a.c-event-card__cover-link[href]")
                if not link or link["href"] in seen:
                    continue
                seen.add(link["href"])
                classes = card.get("class", [])
                space = next((self.stages[c] for c in classes if c in self.stages), None)
                if space is None:
                    continue  # another venue's stage
                event = self._parse_card(card, link["href"], space)
                if event:
                    yield event

    def _parse_card(self, card, url: str, space: str) -> Event | None:
        title = text_of(card.select_one(".c-event-card__title"))
        try:
            start, end, _ = parse_date_range(
                text_of(card.select_one(".c-event-card__daterange")), self.today
            )
        except ValueError:
            return None
        img = card.select_one("img")
        image = None
        if img:
            srcset = _WIDTH.search(img.get("data-srcset", ""))
            image = srcset.group(1) if srcset else img.get("src")
        return self.event(
            title=title,
            url=url,
            booking_url=url + "#book",
            start=start,
            end=end,
            space=space if len(self.stages) > 1 else None,
            image_url=image,
        )


@register
class SadlersWellsClerkenwell(SadlersWells):
    venue_id = "sadlerswells"
    stages = {
        "u-venue-sadlers-wells-theatre": "Sadler's Wells Theatre",
        "u-venue-lilian-baylis-studio": "Lilian Baylis Studio",
    }


@register
class PeacockTheatre(SadlersWells):
    venue_id = "peacock"
    stages = {"u-venue-peacock-theatre": "Peacock Theatre"}


@register
class SadlersWellsEast(SadlersWells):
    venue_id = "sadlerswellseast"
    stages = {"u-venue-sadlers-wells-east": "Sadler's Wells East"}
