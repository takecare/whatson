from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import at, parse_date_range, parse_time
from whatson.registry import register

log = logging.getLogger(__name__)

# Art-form filters we list, mapped onto our tags. (Accessible, online and
# young-people filters overlap these and are skipped.)
ARTFORMS = {
    "art-exhibitions": ["Art", "Exhibition"],
    "classical-music": ["Classical", "Music"],
    "gigs": ["Music"],
    "comedy": ["Comedy"],
    "performance-dance": ["Dance", "Theatre"],
    "literature-poetry": ["Talks"],
    "talks-debates": ["Talks"],
    "family": ["Family"],
    "courses-workshops": ["Workshop"],
    "tours-activities": ["Tours"],
}
# The card's main art form ("pill"), mapped onto tags; the first is the category.
PRIMARY_TAGS = {
    "art & exhibitions": ["Exhibition", "Art"],
    "classical music": ["Classical", "Music"],
    "gigs": ["Music"],
    "comedy": ["Comedy"],
    "performance & dance": ["Dance", "Theatre"],
    "literature & poetry": ["Talks"],
    "talks & debates": ["Talks"],
    "family": ["Family"],
    "courses & workshops": ["Workshop"],
    "tours & activities": ["Tours"],
}
_WIDTH = re.compile(r"(\S+)\s+640w")


@dataclass
class _Card:
    card: Any
    tags: list[str] = field(default_factory=list)


@register
class SouthbankCentre(BaseAggregator):
    """Every listing's first page is open, but page 2 onwards sits behind a Cloudflare
    challenge, which we don't try to get past. So we read first pages only:

    - one per art form (/whats-on/?artform-filter=gigs), which also tells us each
      event's art forms, and
    - one per day for the next ``days_ahead`` days (?start-date=…&end-date=…).

    A day page holds 12 events; on busy days (weekends) anything past the first 12
    is missed unless an art-form page listed it. Cards give the date(s), time, space
    and whether it's free.
    """

    venue_id = "southbankcentre"
    days_ahead = 90

    def fetch_events(self) -> Iterator[Event]:
        cards: dict[str, _Card] = {}
        pages = [({"artform-filter": a}, tags) for a, tags in ARTFORMS.items()]
        for offset in range(self.days_ahead):
            day = (self.today + timedelta(days=offset)).isoformat()
            pages.append(({"start-date": day, "end-date": day}, []))

        fetched = 0
        for params, tags in pages:
            try:
                soup = self.get_html(self.venue.url, params)
            except FetchError as e:
                log.warning("southbankcentre: skipping %s: %s", params, e)
                continue
            fetched += 1
            for card in soup.select(".c-event-card"):
                link = card.select_one("a.c-event-card__cover-link[href]")
                if not link:
                    continue
                entry = cards.setdefault(link["href"], _Card(card))
                entry.tags += [t for t in tags if t not in entry.tags]
        if not fetched:
            raise FetchError("no listing page could be fetched")
        for url, entry in cards.items():
            yield from self._parse_card(url, entry)

    def _parse_card(self, url: str, entry: _Card) -> list[Event]:
        card = entry.card
        title = text_of(card.select_one(".c-event-card__title"))
        when = text_of(card.select_one(".c-event-card__daterange"))
        if not title or not when:
            return []
        dates_text, _, time_text = when.partition(",")
        try:
            start, end, separate = parse_date_range(dates_text, self.today)
        except ValueError:
            return []
        time = parse_time(time_text)

        pill = text_of(card.select_one(".c-event-card__primary-artform")).lower()
        tags = list(dict.fromkeys([*PRIMARY_TAGS.get(pill, []), *entry.tags]))
        free = "free" in text_of(card.select_one(".c-event-card__label")).lower()
        img = card.select_one(".c-event-card__fig img")
        image = None
        if img:
            srcset = _WIDTH.search(img.get("data-srcset", ""))
            image = srcset.group(1) if srcset else img.get("src")
        common = {
            "title": title,
            "url": url,
            "category": tags[0] if tags else None,
            "tags": tags,
            "space": text_of(card.select_one(".c-event-card__location")) or None,
            "price_min": 0.0 if free else None,
            "image_url": image,
            "summary": text_of(card.select_one(".c-event-card__listing-details")) or None,
        }
        if separate:  # "Tue 29 Sep & Wed 30 Sep 2026": one event per date
            return [self.event(start=at(d, time), **common) for d in separate]
        if end:
            return [self.event(start=start, end=end, **common)]
        return [self.event(start=at(start, time), **common)]
