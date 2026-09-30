from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import urljoin

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register

log = logging.getLogger(__name__)

GENRES = {
    "drama": ["Theatre"],
    "musical": ["Theatre"],
    "drag": ["Theatre"],
    "cabaret": ["Theatre"],
    "pantomime": ["Theatre", "Family"],
    "comedy": ["Comedy"],
}
# The stage links among the genres; "Main House Later" is a late slot in the Main House.
STAGES = {"main house": "Main House", "main house later": "Main House", "4below": "4Below"}
_ADULTS = re.compile(r"\badults?\b", re.I)


@register
class KingsHeadTheatre(BaseAggregator):
    """The listing gives each show's run, genres and stage; each show's page has a
    JSON-LD Event for every performance."""

    venue_id = "kingshead"

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select(".listItemWrapper"):
            link = card.select_one("a.desc[href]")
            title = text_of(card.select_one(".title"))
            if link is None or not title:
                continue
            url = urljoin(self.venue.url, link["href"])
            labels = [text_of(a).lower() for a in card.select("a.genres__link")]
            tags: list[str] = []
            for label in labels:
                tags += [t for t in GENRES.get(label, []) if t not in tags]
            if _ADULTS.search(title) and "Family" in tags:
                tags.remove("Family")  # the adults-only panto
            tags = tags or ["Theatre"]
            space = next((STAGES[x] for x in labels if x in STAGES), None)
            performances = self._performances(url)
            if performances:
                start, end = performances[0], None
            else:
                dates = " - ".join(
                    text_of(card.select_one(f".top-date .{part}")) for part in ("start", "end")
                )
                try:
                    start, end, _ = parse_date_range(dates.strip(" -"), self.today)
                except ValueError:
                    continue
            yield self.event(
                title=title,
                url=url,
                category=tags[0],
                tags=tags,
                start=start,
                end=end,
                performances=performances,
                space=space,
                image_url=image_src(card.select_one(".thumb img")),
                summary=text_of(card.select_one(".tagline")) or None,
            )

    def _performances(self, url: str) -> list[datetime]:
        try:
            page = self.get_html(url)
        except FetchError as e:
            log.warning("kingshead: no performances for %s: %s", url, e)
            return []
        times = set()
        for event in self.json_ld(page):
            try:
                times.add(datetime.fromisoformat(event["startDate"]).astimezone(LONDON))
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(times)
