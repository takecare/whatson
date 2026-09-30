from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from urllib.parse import urljoin

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import at, parse_dates, parse_price, parse_time
from whatson.registry import register

log = logging.getLogger(__name__)

_QUIZ = re.compile(r"\bquiz\b", re.IGNORECASE)


@register
class Lexington(BaseAggregator):
    """One page lists every gig and club night with date and time ("Tue September 29,
    19:00", no year), image and ticket link. Each event's page adds the price line and
    a description."""

    venue_id = "lexington"

    def fetch_events(self) -> Iterator[Event]:
        listing = self.get_html(self.venue.url)
        for item in listing.select(".grid-item, .grid-item-club"):
            when = text_of(item.select_one(".event-date"))
            days = parse_dates(when, self.today)
            title = text_of(item.select_one(".event-title"))
            link = item.select_one("a.link-box[href]")
            if not days or not title or not link:
                continue
            url = urljoin(self.venue.url, link["href"])
            club = "grid-item-club" in item.get("class", [])
            if _QUIZ.search(title):
                tags = ["Nightlife"]
            elif club:
                tags = ["Nightlife", "Music"]
            else:
                tags = ["Music"]
            tickets = item.select_one("a.ticket-box[href]")
            booking = tickets["href"] if tickets and tickets["href"] != "#" else None
            src = image_src(item.select_one("img"))
            price_min = price_max = summary = None
            try:
                page = self.get_html(url)
            except FetchError as e:
                log.warning("lexington: no details for %s: %s", url, e)
            else:
                meta = page.select_one(".event-meta")
                if meta:
                    for strong in meta.select("strong"):
                        strong.decompose()
                    price_min, price_max = parse_price(text_of(meta))
                # Paragraphs: sometimes the running order ("8pm Joe Hicks"), then the blurb.
                paragraphs = [text_of(p) for p in page.select(".text-content > p")]
                summary = " ".join(p for p in paragraphs if p) or None
            yield self.event(
                title=title,
                url=url,
                booking_url=booking,
                category=tags[0],
                tags=tags,
                start=at(days[0], parse_time(when)),
                price_min=price_min,
                price_max=price_max,
                image_url=urljoin(self.venue.url, src) if src else None,
                summary=summary,
            )
