from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator, next_data
from whatson.models import Event
from whatson.registry import register

CATEGORIES = {"theatre": ["Theatre"], "nightlife": ["Nightlife", "Music"]}
# Sanity image references look like "image-<id>-<width>x<height>-<ext>".
_IMAGE_REF = re.compile(r"image-(\w+)-(\d+x\d+)-(\w+)")
_SANITY = re.compile(r"cdn\.sanity\.io/images/(\w+)/(\w+)/")


@register
class YardTheatre(BaseAggregator):
    """A Next.js site: the What's On page's data lists every show with its category,
    run (ISO start and end), times and a Sanity image reference."""

    venue_id = "yard"

    def fetch_events(self) -> Iterator[Event]:
        html = self.http.get_text(self.venue.url)
        listing = next_data(html, '{"events":[') or {}
        sanity = _SANITY.search(html)
        for item in listing.get("events", []):
            event = self._event(item, sanity)
            if event:
                yield event

    def _event(self, item: dict[str, Any], sanity: re.Match[str] | None) -> Event | None:
        duration = item.get("duration") or {}
        if not item.get("title") or not item.get("slug") or not duration.get("start"):
            return None
        start = _london(duration["start"])
        end = _london(duration.get("end") or duration["start"])
        tags = CATEGORIES.get((item.get("categorySlug") or "").lower(), ["Theatre"])
        image = None
        ref = _IMAGE_REF.fullmatch(
            ((item.get("coverImage") or {}).get("asset") or {}).get("_ref", "")
        )
        if ref and sanity:
            project, dataset = sanity.groups()
            image = (
                f"https://cdn.sanity.io/images/{project}/{dataset}/"
                f"{ref[1]}-{ref[2]}.{ref[3]}?w=800&auto=format"
            )
        one_day = start.date() == end.date()
        return self.event(
            title=item["title"].strip(),
            url=f"https://www.theyardtheatre.co.uk/events/{item['slug']}",
            category=tags[0],
            tags=tags,
            # A single performance keeps its time; a run is shown by its dates.
            start=start if one_day else start.date(),
            end=None if one_day else end.date(),
            image_url=image,
            summary=item.get("byline") or _times(item),
        )


def _times(item: dict[str, Any]) -> str | None:
    """Performance times from the ticket blocks, e.g. "Times: 2:30pm & 7:00pm"."""
    tickets = (item.get("ticketing") or {}).get("tickets") or []
    times = [t["times"].strip() for t in tickets if (t.get("times") or "").strip()]
    return f"Times: {'; '.join(dict.fromkeys(times))}" if times else None


def _london(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LONDON)
