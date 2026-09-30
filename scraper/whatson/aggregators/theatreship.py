from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator
from whatson.models import Event
from whatson.registry import register

# The What's On section is filled in by the page's script from this Firestore
# document, which we read through Firestore's REST API instead.
DOC = "https://firestore.googleapis.com/v1/projects/theatreship/databases/(default)/documents/eventsCache/latest"
# No categories: gigs and folk sessions are the norm, so tag from the text.
_FILM = re.compile(r"\b(cinema|screenings?|films?|national theatre live)\b", re.I)
_TALK = re.compile(r"\b(q&a|book launch|in conversation)\b", re.I)
_FREE = re.compile(r"\bfree\b", re.I)


def plain(value: dict[str, Any]) -> Any:
    """A Firestore REST value ({"stringValue": ...}, {"mapValue": ...}) as plain data."""
    if "mapValue" in value:
        return {k: plain(v) for k, v in value["mapValue"].get("fields", {}).items()}
    if "arrayValue" in value:
        return [plain(v) for v in value["arrayValue"].get("values", [])]
    return next(iter(value.values()), None)


@register
class Theatreship(BaseAggregator):
    """A ship moored at Canary Wharf. Its events are a list in a public Firestore
    document: title, date and time, description, image and booking links
    (Eventbrite, DICE)."""

    venue_id = "theatreship"

    def fetch_events(self) -> Iterator[Event]:
        fields = self.get_json(DOC).get("fields", {})
        for item in plain(fields.get("eventsList", {"arrayValue": {}})):
            event = self._event(item)
            if event:
                yield event

    def _event(self, item: dict[str, Any]) -> Event | None:
        title, when = (item.get("title") or "").strip(), item.get("date")
        links = [link for link in item.get("links") or [] if link.get("url")]
        if not title or not when or not links:
            return None
        start = datetime.fromisoformat(when)
        # Eventbrite dates are local time without an offset; DICE ones carry one.
        start = start.replace(tzinfo=LONDON) if start.tzinfo is None else start.astimezone(LONDON)
        description = " ".join((item.get("description") or "").replace("*", "").split())
        text = f"{title} {description}"
        tags = ["Film"] if _FILM.search(text) else ["Music"]
        if _TALK.search(text):
            tags.append("Talks")
        return self.event(
            title=title,
            url=links[0]["url"],
            booking_url=links[0]["url"],
            category=tags[0],
            tags=tags,
            start=start,
            price_min=0.0 if _FREE.search(title) else None,
            image_url=item.get("image") or None,
            summary=description or None,
        )
