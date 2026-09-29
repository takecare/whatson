from __future__ import annotations

import html
import re
from collections.abc import Iterator
from datetime import date, datetime, time
from typing import Any

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator
from whatson.models import Event
from whatson.registry import register

WIDGET = "d24ece57-4cf0-4357-a18a-5f40f33590a9"
BOOT = "https://core.service.elfsight.com/p/boot/"


@register
class SJQ(BaseAggregator):
    """The programme page (Squarespace) shows an Elfsight event-calendar widget. The
    widget loads its events from Elfsight's public boot endpoint as JSON, which is
    what we read: name, start/end date and time, cover image and ticket link. Past
    events are included there, so they're filtered out by the runner."""

    venue_id = "sjq"

    def fetch_events(self) -> Iterator[Event]:
        data = self.get_json(BOOT, {"page": self.venue.url, "w": WIDGET})
        settings = data["data"]["widgets"][WIDGET]["data"]["settings"]
        for item in settings.get("events", []):
            event = self._parse(item)
            if event:
                yield event

    def _parse(self, item: dict[str, Any]) -> Event | None:
        start = _when(item.get("start"))
        if start is None or not item.get("name"):
            return None
        end = _when(item.get("end"))
        link = next(
            (a["link"]["value"] for a in item.get("actions") or [] if a.get("type") == "link"),
            None,
        )
        description = re.sub(r"<[^>]+>", " ", html.unescape(item.get("description") or ""))
        # Club nights end after midnight: that's a late night, not a two-day event.
        late_night = isinstance(end, datetime) and _day(end) > _day(start) and end.hour < 8
        several_days = end is not None and not late_night and _day(end) > _day(start)
        return self.event(
            title=html.unescape(item["name"]).strip(),
            url=link or self.venue.url,
            booking_url=link,
            category="Music",
            tags=["Music", "Nightlife"] if late_night else ["Music"],
            start=start,
            end=end if several_days else None,
            image_url=(item.get("coverImage") or {}).get("url"),
            summary=" ".join(description.split()) or None,
        )


def _when(value: dict[str, Any] | None) -> date | datetime | None:
    if not value or not value.get("date"):
        return None
    day = date.fromisoformat(value["date"])
    if value.get("type") == "datetime" and value.get("time"):
        hour, minute = (int(x) for x in value["time"].split(":")[:2])
        return datetime.combine(day, time(hour, minute), tzinfo=LONDON)
    return day


def _day(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d
