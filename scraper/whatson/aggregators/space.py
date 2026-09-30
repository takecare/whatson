from __future__ import annotations

import re
from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register

_BG_URL = re.compile(r"url\([\"']?([^\"')]+)")
# The site's categories only say "In Person" or "Online", so tag from the title and
# blurb. Anything else is theatre, the venue's main programme.
TITLE_KEYWORDS = [
    (re.compile(r"\b(comedy|laughs|stand-up)\b", re.I), ["Comedy"]),
    (re.compile(r"\bfestival\b", re.I), ["Festival", "Theatre"]),
]
TEXT_KEYWORDS = [
    (re.compile(r"\bclub night\b", re.I), ["Music", "Nightlife"]),
    (re.compile(r"\b(recitals?|piano|concerts?|symphonic|the music of)\b", re.I), ["Music"]),
    (re.compile(r"\b(screening|film)\b", re.I), ["Film"]),
]


@register
class TheSpace(BaseAggregator):
    """WordPress listing of cards with title, dates ("1 Oct - 4 Oct", no year), blurb
    and image. Event pages add nothing machine-readable (booking is embedded)."""

    venue_id = "space"

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select(".event-item"):
            title = text_of(card.select_one(".title"))
            link = card.select_one(".event-links a[href]")
            try:
                start, end, _ = parse_date_range(
                    text_of(card.select_one(".event-date")), self.today
                )
            except ValueError:
                continue
            if not title or link is None:
                continue
            blurb = " ".join(text_of(p) for p in card.select(".event-item-info > p")).strip()
            tags: list[str] = []
            for patterns, text in ((TITLE_KEYWORDS, title), (TEXT_KEYWORDS, f"{title} {blurb}")):
                for pattern, keyword_tags in patterns:
                    if pattern.search(text):
                        tags += [t for t in keyword_tags if t not in tags]
            tags = tags or ["Theatre"]
            image = card.select_one(".event-item-image")
            bg = _BG_URL.search(image.get("style", "")) if image else None
            book = card.select_one(".event-links a.filled[href]")
            yield self.event(
                title=title,
                url=link["href"],
                booking_url=book["href"] if book else None,
                category=tags[0],
                tags=tags,
                start=start,
                end=end,
                image_url=bg.group(1) if bg else None,
                summary=blurb or None,
            )
