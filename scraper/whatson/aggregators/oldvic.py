from __future__ import annotations

import logging
from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import parse_date_range, parse_price
from whatson.registry import register

log = logging.getLogger(__name__)

# The listing's access icons, by their tooltip.
ACCESS = {
    "audio described": "Audio Described",
    "bsl interpreted": "Signed",
    "captioned": "Captioned",
    "relaxed": "Relaxed",
}


@register
class OldVic(BaseAggregator):
    """The stage listing is a handful of poster cards (title and access icons); each
    show's page gives its run, ticket prices and booking link."""

    venue_id = "oldvic"

    def fetch_events(self) -> Iterator[Event]:
        for card in self.get_html(self.venue.url).select("a.poster-card[href]"):
            url = card["href"]
            try:
                page = self.get_html(url)
            except FetchError as e:
                log.warning("oldvic: skipping %s: %s", url, e)
                continue
            try:
                start, end, _ = parse_date_range(
                    text_of(page.select_one(".event-hero-right__dates")), self.today
                )
            except ValueError:
                continue
            info = {
                text_of(seg.select_one(".essential-information__segment-header")).lower(): seg
                for seg in page.select(".essential-information__wrapper > div")
            }
            tickets = info.get("tickets")
            price_min, price_max = parse_price(text_of(tickets)) if tickets else (None, None)
            access = [text_of(t).lower() for t in card.select(".accessibility .text-small")]
            book = page.select_one("a.event-hero-right__button[href]")
            description = page.select_one("meta[name=description]")
            yield self.event(
                title=text_of(page.select_one(".event-hero-right__heading"))
                or text_of(card.select_one(".sr-only")),
                url=url,
                booking_url=book["href"] if book else None,
                category="Theatre",
                tags=["Theatre", *(ACCESS[a] for a in access if a in ACCESS)],
                start=start,
                end=end,
                price_min=price_min,
                price_max=price_max,
                image_url=image_src(page.select_one(".hero img")),
                summary=description.get("content") if description else None,
            )
