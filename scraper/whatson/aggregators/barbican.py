from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import parse_dates, parse_price
from whatson.registry import register

log = logging.getLogger(__name__)

# Barbican's categories mapped onto our tags; the first tag is the main category.
CATEGORIES = {
    "cinema": ["Film"],
    "classical music": ["Classical", "Music"],
    "contemporary music": ["Music"],
    "theatre & dance": ["Theatre", "Dance"],
    "art & design": ["Art"],
    "talks & events": ["Talks"],
    "tours & public spaces": ["Tours"],
    "take part": ["Workshop"],
    "family": ["Family"],
}


@dataclass
class _Listing:
    url: str
    title: str
    tags: list[str] = field(default_factory=list)
    image_url: str | None = None
    summary: str | None = None
    days: set[date] = field(default_factory=set)


@register
class Barbican(BaseAggregator):
    """The What's On page is a day-by-day calendar, paginated with ?page=N, about 15
    entries a page. It gives each event's link, categories, image and blurb. Each
    event's own page gives the first and last performance (machine-readable), the
    hall and the standard price; individual showtimes are loaded by JavaScript, so
    events on several days become runs.
    """

    venue_id = "barbican"
    days_ahead = 180
    max_pages = 60

    def fetch_events(self) -> Iterator[Event]:
        for listing in self._listings().values():
            try:
                event = self._event(listing)
            except FetchError as e:
                log.warning("barbican: skipping %s: %s", listing.url, e)
                continue
            if event:
                yield event

    def _listings(self) -> dict[str, _Listing]:
        listings: dict[str, _Listing] = {}
        horizon = self.today + timedelta(days=self.days_ahead)
        for page in range(self.max_pages):
            soup = self.get_html(self.venue.url, {"page": page} if page else None)
            rows = soup.select(".views-row")
            if not rows:
                break
            last_day = None
            for row in rows:
                link = row.select_one("a.search-listing__link[href]")
                title = text_of(row.select_one(".listing-title"))
                if not link or not title:
                    continue
                url = urljoin(self.venue.url, link["href"])
                item = listings.get(url)
                if item is None:
                    tags = [
                        t
                        for label in row.select(".tag__plain")
                        for t in CATEGORIES.get(text_of(label).lower(), [])
                    ]
                    img = row.select_one(".search-listing__image img[src]")
                    item = listings[url] = _Listing(
                        url=url,
                        title=title,
                        tags=list(dict.fromkeys(tags)),
                        image_url=urljoin(self.venue.url, img["src"]) if img else None,
                        summary=text_of(row.select_one(".search-listing__intro")) or None,
                    )
                days = parse_dates(row.get("data-day", ""), self.today)
                if days:
                    item.days.add(days[0])
                    last_day = days[0]
            if last_day and last_day > horizon:
                break
        return listings

    def _event(self, listing: _Listing) -> Event | None:
        soup = self.get_html(listing.url)
        byline = soup.select_one(".event-byline")
        times = [
            datetime.fromisoformat(t["datetime"].replace("Z", "+00:00")).astimezone(LONDON)
            for t in (byline.select("time[datetime]") if byline else [])
        ]
        if times:
            first, last = min(times), max(times)
        elif listing.days:
            first, last = min(listing.days), max(listing.days)
        else:
            return None

        start: date | datetime
        end: date | None
        if _day(first) == _day(last):
            start, end = first, None
        else:
            # Several performances whose individual times we don't know: a run.
            start, end = _day(first), _day(last)

        price_min, price_max = _price(soup)

        tags = list(listing.tags)
        if end and "Art" in tags:
            tags.append("Exhibition")
        return self.event(
            title=listing.title,
            url=listing.url,
            category=tags[0] if tags else None,
            tags=tags,
            start=start,
            end=end,
            space=_space(text_of(byline.select_one(".event-byline__venue"))) if byline else None,
            price_min=price_min,
            price_max=price_max,
            image_url=listing.image_url,
            summary=listing.summary,
        )


def _price(soup) -> tuple[float | None, float | None]:
    """The standard ticket price, including the transaction fee.

    Prices look like "From £19 (£15 + £4 transaction fee)", "£15.50 (...)" or
    "Pay What You Can £0 | £3 | £6"; other rows (members, Young Barbican) are
    discounts and ignored.
    """
    items = soup.select(".ticket-prices .accordion-item")
    if not items:
        return None, None
    item = next(
        (i for i in items if text_of(i).lower().startswith("standard")),
        items[0],
    )
    value = re.sub(r"\(.*?\)", "", text_of(item))  # drop "(£15 + £4 transaction fee)"
    amounts = [float(a) for a in re.findall(r"£\s*(\d+(?:\.\d{1,2})?)", value)]
    if not amounts:
        return parse_price(value)  # "Free", or nothing
    if "|" in value or re.search(r"£[\d.]+\s*(?:–|-|to)\s*£", value):
        return min(amounts), max(amounts)
    return amounts[0], amounts[0]


# The byline sometimes shortens hall names.
SPACES = {
    "hall": "Barbican Hall",
    "theatre": "Barbican Theatre",
    "cinemas": "Barbican Cinemas",
    "milton court": "Milton Court Concert Hall",
}


def _space(name: str) -> str | None:
    return SPACES.get(name.lower(), name) or None


def _day(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d
