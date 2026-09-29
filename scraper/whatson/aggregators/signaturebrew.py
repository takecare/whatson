from __future__ import annotations

import re
from collections.abc import Iterator
from typing import ClassVar

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import at, parse_dates, parse_time
from whatson.registry import register

_BG_URL = re.compile(r"url\([\"']?([^\"')]+)")
# The listing's category field is almost always empty, so tag from the title.
KEYWORDS = [
    (re.compile(r"\bquiz\b", re.I), ["Nightlife"]),
    (re.compile(r"\b(uefa|premier league|world cup|f1|rugby|six nations)\b", re.I), ["Sport"]),
    (re.compile(r"\bcomedy\b", re.I), ["Comedy"]),
    (re.compile(r"\bjazz\b", re.I), ["Jazz", "Music"]),
]


class SignatureBrew(BaseAggregator):
    """One Webflow page lists events at both taprooms; each card names its venue
    ("Signature Brew Haggerston"), date ("Tuesday, September 29, 2026"), time and a
    ticket link (Tixr). Each of our venues keeps its own taproom's events."""

    taproom: ClassVar[str]

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select(".cal-container"):
            if text_of(card.select_one(".venuename")).lower() != self.taproom.lower():
                continue
            days = parse_dates(text_of(card.select_one(".dates .date")), self.today)
            title = text_of(card.select_one(".b-show"))
            if not days or not title:
                continue
            tags: list[str] = []
            for pattern, keyword_tags in KEYWORDS:
                if pattern.search(title):
                    tags += [t for t in keyword_tags if t not in tags]
            tickets = card.select_one("a.button[href]")
            poster = _BG_URL.search((card.select_one(".poster") or {}).get("style", ""))
            yield self.event(
                title=title.removesuffix("| London").strip(),
                url=tickets["href"] if tickets else self.venue.url,
                booking_url=tickets["href"] if tickets else None,
                category=tags[0] if tags else "Music",
                tags=tags or ["Music"],
                start=at(days[0], parse_time(text_of(card.select_one(".time")))),
                image_url=poster.group(1) if poster else None,
            )


@register
class SignatureBrewHaggerston(SignatureBrew):
    venue_id = "signaturebrew-haggerston"
    taproom = "Signature Brew Haggerston"


@register
class SignatureBrewBlackhorseRoad(SignatureBrew):
    venue_id = "signaturebrew-blackhorse"
    taproom = "Signature Brew Blackhorse Road"
