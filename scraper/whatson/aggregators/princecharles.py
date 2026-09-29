from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import at, parse_dates, parse_time
from whatson.registry import register


@register
class PrinceCharlesCinema(BaseAggregator):
    """The whole programme is one server-rendered page: each film with its showtimes
    grouped under day headings ("Tuesday 29th September"). One event per film, with
    every showtime as a performance. Prices aren't listed.
    """

    venue_id = "princecharles"

    def fetch_events(self) -> Iterator[Event]:
        soup = self.get_html(self.venue.url)
        for film in soup.select(".jacro-event"):
            event = self._parse_film(film)
            if event:
                yield event

    def _parse_film(self, film) -> Event | None:
        link = film.select_one("a.liveeventtitle[href]")
        if link is None:
            return None
        performances: list[datetime] = []
        sold_out: list[bool] = []
        formats: set[str] = set()
        for group in film.select(".performance-list-items"):
            day = None
            for child in group.find_all(["div", "li"], recursive=False):
                if "heading" in child.get("class", []):
                    days = parse_dates(text_of(child), self.today)
                    day = days[0] if days else None
                elif child.name == "li" and day is not None:
                    t = parse_time(text_of(child.select_one(".time")))
                    if t is None:
                        continue
                    performances.append(at(day, t))  # type: ignore[arg-type]
                    button = child.select_one("a")
                    sold_out.append(bool(button and "sold" in " ".join(button.get("class", []))))
                    formats.update(text_of(tag) for tag in child.select(".movietag .tag"))
        if not performances:
            return None

        details = [text_of(s) for s in film.select(".running-time span")]
        img = film.select_one(".film_img img[src]")
        summary = text_of(film.select_one(".jacro-formatted-text"))
        if formats:
            summary = f"{', '.join(sorted(formats))}. {summary}".strip()
        return self.event(
            title=text_of(link),
            url=link["href"],
            category="Film",
            start=min(performances),
            performances=performances,
            sold_out=all(sold_out),
            image_url=img["src"] if img else None,
            summary=summary or " · ".join(details) or None,
        )
