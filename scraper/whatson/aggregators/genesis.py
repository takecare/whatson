from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import urljoin

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.models import Event
from whatson.parsing import at, parse_dates, parse_time
from whatson.registry import register

# Events are mostly screenings with a Q&A or intro; a few aren't films at all.
KEYWORDS = [
    (re.compile(r"\b(q&a|q & a|in conversation|intro by)\b", re.I), "Talks"),
    (re.compile(r"\bpoetry\b", re.I), "Talks"),
    (re.compile(r"\bwrestling\b", re.I), "Sport"),
    (re.compile(r"\bcomedy\b", re.I), "Comedy"),
]
_NOT_FILM = re.compile(r"\b(poetry|slam|wrestling)\b", re.I)


@register
class GenesisCinema(BaseAggregator):
    """The events page (Admit One's cinema site) lists special events, each with its
    performances: date ("Thu 08 Oct", no year), time and booking link."""

    venue_id = "genesis"

    def fetch_events(self) -> Iterator[Event]:
        page = self.get_html(self.venue.url)
        for block in page.select("div.bg-white"):
            links = block.select("h2 a[href]")
            if len(links) != 1:  # not an event, or a wrapper around several
                continue
            link = links[0]
            performances: list[datetime] = []
            booking = None
            for book in block.select("a[href*='admit-one']"):
                when = [text_of(p) for p in book.parent.find_all("p", recursive=False)]
                days = parse_dates(when[0], self.today) if when else []
                t = parse_time(when[1]) if len(when) > 1 else None
                if days and t:
                    performances.append(at(days[0], t))  # type: ignore[arg-type]
                    booking = booking or book["href"]
            if not performances:
                continue
            title = text_of(link)
            tags = [] if _NOT_FILM.search(title) else ["Film"]
            tags += [tag for pattern, tag in KEYWORDS if pattern.search(title) and tag not in tags]
            src = image_src(block.select_one("img"))
            yield self.event(
                title=title,
                url=urljoin(self.venue.url, link["href"]),
                booking_url=booking,
                category=tags[0],
                tags=tags,
                start=min(performances),
                performances=sorted(performances),
                image_url=urljoin(self.venue.url, src) if src else None,
            )
