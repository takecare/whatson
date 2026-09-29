from __future__ import annotations

import html
import json
import re
from collections.abc import Iterator
from datetime import date, datetime, time
from typing import Any

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator
from whatson.models import Event
from whatson.registry import register

# Performance flags that map onto our accessibility tags.
FLAGS = {"RS": "Relaxed", "HoH": "Captioned"}


@register
class RioCinema(BaseAggregator):
    """The What's On page (Savoy's Rio.dll ticketing) embeds the whole programme as
    JSON: `var Events = {"Events": [...]}`, each film with its performances (date,
    time, screen, sold out, accessibility flags). One event per film. No prices."""

    venue_id = "rio"

    def fetch_events(self) -> Iterator[Event]:
        page = self.http.get_text(self.venue.url)
        marker = page.find("var Events =")
        if marker < 0:
            raise ValueError("no 'var Events' data on the page")
        data, _ = json.JSONDecoder().raw_decode(page[marker + len("var Events =") :].lstrip())
        for film in data.get("Events", []):
            event = self._parse_film(film)
            if event:
                yield event

    def _parse_film(self, film: dict[str, Any]) -> Event | None:
        performances: list[datetime] = []
        sold_out: list[bool] = []
        tags: set[str] = set()
        for perf in film.get("Performances", []):
            try:
                day = date.fromisoformat(perf["StartDate"])
                hhmm = perf["StartTime"].zfill(4)
                at_time = time(int(hhmm[:2]), int(hhmm[2:]))
            except (KeyError, ValueError):
                continue
            performances.append(datetime.combine(day, at_time, tzinfo=LONDON))
            sold_out.append(perf.get("IsSoldOut") == "Y")
            tags.update(tag for flag, tag in FLAGS.items() if perf.get(flag) == "Y")
        if not performances:
            return None
        synopsis = re.sub(r"<[^>]+>", " ", html.unescape(film.get("Synopsis") or ""))
        return self.event(
            title=html.unescape(film.get("Title", "")).strip(),
            url=film.get("URL") or self.venue.url,
            category="Film",
            tags=sorted(tags),
            start=min(performances),
            performances=performances,
            sold_out=all(sold_out),
            image_url=film.get("ImageURL") or None,
            summary=synopsis.strip() or None,
        )
