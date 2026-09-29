from __future__ import annotations

from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register

# Category pages (/whats-on/<slug>) mapped onto our tags.
CATEGORIES = {
    "art-design": ["Art", "Exhibition"],
    "music": ["Music"],
    "events": ["Talks"],
    "history": ["Tours"],
}


@register
class TrinityBuoyWharf(BaseAggregator):
    """A short server-rendered list; each category has its own page, which gives the
    tags. Permanent works ("Open year round") aren't events and are skipped."""

    venue_id = "trinitybuoywharf"

    def fetch_events(self) -> Iterator[Event]:
        tags: dict[str, list[str]] = {}
        for slug, category_tags in CATEGORIES.items():
            try:
                page = self.get_html(f"{self.venue.url}/{slug}")
            except FetchError:
                continue  # tags are a nice-to-have
            for entry in page.select("a.listing-entry[href]"):
                known = tags.setdefault(entry["href"], [])
                known += [t for t in category_tags if t not in known]

        for entry in self.get_html(self.venue.url).select("a.listing-entry[href]"):
            try:
                start, end, _ = parse_date_range(
                    text_of(entry.select_one(".listing-entry__subtext")), self.today
                )
            except ValueError:
                continue  # "Open year round"
            event_tags = tags.get(entry["href"], [])
            yield self.event(
                title=text_of(entry.select_one(".listing-entry__title")),
                url=entry["href"],
                category=event_tags[0] if event_tags else None,
                tags=event_tags,
                start=start,
                end=end,
                image_url=image_src(entry.select_one("img")),
            )
