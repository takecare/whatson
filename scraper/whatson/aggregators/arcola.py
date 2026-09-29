from __future__ import annotations

from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.models import Event
from whatson.parsing import parse_date_range
from whatson.registry import register


@register
class ArcolaTheatre(BaseAggregator):
    """Server-rendered list of shows (the "all shows" view is the same list, filtered
    in the browser). Cards give the run, the studio and a one-line blurb."""

    venue_id = "arcola"

    def fetch_events(self) -> Iterator[Event]:
        for item in self.get_html(self.venue.url).select("li.listing-item"):
            link = item.select_one("a.card__fill-link[href]") or item.select_one("a[href]")
            dates = item.select_one(".card__dates")
            if link is None or dates is None:
                continue
            for hidden in item.select(".sr-only"):
                hidden.decompose()  # "Venue", "Date" labels for screen readers
            try:
                start, end, _ = parse_date_range(text_of(dates), self.today)
            except ValueError:
                continue
            url = link["href"]
            yield self.event(
                title=text_of(item.select_one(".card__heading")),
                url=url,
                booking_url=url.rstrip("/") + "/#event-booking",
                category="Theatre",
                start=start,
                end=end,
                space=text_of(item.select_one(".card__venue")) or None,
                image_url=image_src(item.select_one(".card__image img")),
                summary=text_of(item.select_one(".type-body-l")) or None,
            )
