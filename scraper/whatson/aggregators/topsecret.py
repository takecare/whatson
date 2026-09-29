from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.models import Event
from whatson.parsing import at, parse_price, parse_time
from whatson.registry import register

AJAX = "https://thetopsecretcomedyclub.co.uk/wp-admin/admin-ajax.php"


@register
class TopSecretComedyClub(BaseAggregator):
    """The listing page only shows a few days and its pagination links are broken, so
    ask the endpoint the page's own date picker uses, one day at a time."""

    venue_id = "topsecret"
    days_ahead = 60

    def fetch_events(self) -> Iterator[Event]:
        for offset in range(self.days_ahead):
            day = self.today + timedelta(days=offset)
            html = self.http.post_text(
                AJAX, {"action": "jw_events_by_date_v2", "date": day.isoformat()}
            )
            for li in BeautifulSoup(html, "lxml").select("li.event--item"):
                event = self._parse_item(li, day)
                if event:
                    yield event

    def _parse_item(self, li, day: date) -> Event | None:
        heading = li.select_one(".event--details h3")
        if heading is None:
            return None
        venue_span = heading.select_one(".venue")
        space = text_of(venue_span) or None
        if venue_span is not None:
            venue_span.extract()

        starts = next(
            (text_of(s) for s in li.select(".event--time span") if "start" in text_of(s).lower()),
            text_of(li.select_one(".event--time")),
        )
        price_min, price_max = parse_price(text_of(li.select_one(".event--price")))
        more = li.select_one(".event--ctas a.-alt")
        book = li.select_one(".event--ctas a.btn--icon")
        sold_out = text_of(li.select_one(".sold-out")).lower() == "sold out" or (
            text_of(book).lower() == "sold out"
        )

        return self.event(
            title=text_of(heading),
            url=urljoin(self.venue.url, more["href"]) if more else self.venue.url,
            booking_url=book["href"] if book and book.get("href") else None,
            category="Comedy",
            start=at(day, parse_time(starts)),
            space=space,
            price_min=price_min,
            price_max=price_max,
            sold_out=sold_out,
        )
