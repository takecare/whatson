from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urljoin

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.models import Event
from whatson.parsing import at, parse_date_range, parse_price, parse_time
from whatson.registry import register

MAX_PAGES = 20


@register
class CafeOto(BaseAggregator):
    """Server-rendered listing, 12 a page, paginated with ?page=N (infinite scroll;
    past the last page the site answers 404, so we follow its own next-page link).
    Each card has the date and time ("Wednesday 30 September 2026, 7.30pm", or a
    run like "28–29 September 2026"), door/advance/DICE prices and a members' price.
    """

    venue_id = "cafeoto"

    def fetch_events(self) -> Iterator[Event]:
        params: dict[str, str] | None = None
        for _ in range(MAX_PAGES):
            soup = self.get_html(self.venue.url, params)
            for card in soup.select(".each-activity"):
                event = self._parse_card(card)
                if event:
                    yield event
            # The infinite-scroll trigger links to the next page; past the end it's gone.
            nxt = soup.select_one('#iscroll_other a[href^="?page="]')
            if nxt is None:
                break
            params = {"page": nxt["href"].split("=", 1)[1]}

    def _parse_card(self, card) -> Event | None:
        headers = card.select(".each-header")
        link = card.select_one(".each-header a[href]")
        if len(headers) < 2 or link is None:
            return None
        dates_text, _, time_text = text_of(headers[0]).partition(",")
        try:
            start, end, _ = parse_date_range(dates_text, self.today)
        except ValueError:
            return None

        prefix = text_of(headers[1].select_one(".prefix"))
        suffix = text_of(headers[1].select_one(".suffix"))
        title = " ".join(p for p in (prefix, text_of(link)) if p)
        price_box = card.select_one(".each-price")
        prices = (price_box.select_one(".member_price") or price_box) if price_box else None
        # Door, advance and DICE prices; the members' price is a discount.
        public = [
            text_of(span)
            for span in (prices.find_all("span", recursive=False) if prices else [])
            if "member" not in text_of(span).lower()
        ]
        price_min, price_max = parse_price(" ".join(public))
        url = urljoin(self.venue.url, link["href"])
        return self.event(
            title=title,
            url=url,
            category="Music",
            start=start if end else at(start, parse_time(time_text)),
            end=end,
            price_min=price_min,
            price_max=price_max,
            sold_out="sold out" in text_of(price_box).lower(),
            image_url=image_src(card.select_one(".each-image img")),
            summary=suffix or None,
        )
