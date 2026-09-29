from __future__ import annotations

from collections.abc import Iterator

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.models import Event
from whatson.parsing import at, parse_dates, parse_time
from whatson.registry import register

MAX_PAGES = 20


@register
class CourtyardTheatre(BaseAggregator):
    """WordPress page of cards, paginated with ?event_page=N. Each card has the title,
    "October 1, 2026, 7:00 PM" and a See Tickets link. No categories or prices."""

    venue_id = "courtyard"

    def fetch_events(self) -> Iterator[Event]:
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            soup = self.get_html(self.venue.url, {"event_page": page} if page > 1 else None)
            cards = soup.select(".card")
            new = 0
            for card in cards:
                link = card.select_one("a[href]")
                if link is None or link["href"] in seen:
                    continue
                seen.add(link["href"])
                new += 1
                event = self._parse_card(card, link["href"])
                if event:
                    yield event
            last_page = not soup.select_one(f'a[href*="event_page={page + 1}"]')
            if not new or last_page:
                break

    def _parse_card(self, card, url: str) -> Event | None:
        when = next((text_of(p) for p in card.select("p") if p.select_one(".fa-calendar-alt")), "")
        dates = parse_dates(when, self.today)
        title = text_of(card.select_one(".card-title"))
        if not dates or not title:
            return None
        return self.event(
            title=title,
            url=url,
            booking_url=url,
            start=at(dates[0], parse_time(when.split(",")[-1])),
            image_url=image_src(card.select_one("img")),
        )
