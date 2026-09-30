from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime

from bs4 import BeautifulSoup

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.registry import register

log = logging.getLogger(__name__)

BASE = "https://www.hackneyempire.co.uk/whats-on"
# Category pages, and the tags their events get.
CATEGORIES = {
    "theatre": ["Theatre"],
    "comedy": ["Comedy"],
    "live-music": ["Music"],
    "opera": ["Opera"],
    "podcasts-talks": ["Talks"],
    "family": ["Family"],
    "dance": ["Dance"],
}


@register
class HackneyEmpire(BaseAggregator):
    """Listing pages (``/whats-on/page-N``) of cards with title, ISO start time (two
    for a run), image and link. Events carry no category, so the category pages
    (``/whats-on/category/<slug>``) are read to tag them."""

    venue_id = "hackneyempire"

    def fetch_events(self) -> Iterator[Event]:
        tags: dict[str, list[str]] = {}
        for slug, slug_tags in CATEGORIES.items():
            try:
                pages = list(self._pages(f"{BASE}/category/{slug}"))
            except FetchError as e:  # only tags are lost
                log.warning("hackneyempire: no %s tags: %s", slug, e)
                continue
            for page in pages:
                for url, *_ in _cards(page):
                    tags.setdefault(url, [])
                    tags[url] += [t for t in slug_tags if t not in tags[url]]
        seen: set[str] = set()
        for page in self._pages(BASE):
            for url, title, times, image in _cards(page):
                if url in seen or not times:
                    continue
                seen.add(url)
                event_tags = tags.get(url) or ["Theatre"]
                first, last = times[0], times[-1]
                one_day = first.date() == last.date()
                yield self.event(
                    title=title,
                    url=url,
                    category=event_tags[0],
                    tags=event_tags,
                    start=first if one_day else first.date(),
                    end=None if one_day else last.date(),
                    image_url=image,
                )

    def _pages(self, url: str) -> Iterator[BeautifulSoup]:
        """The first page and each following ``page-N``, while the page links to it.
        (The last page's "next" link wraps round to page 1.)"""
        n = 1
        page = self.get_html(url)
        while True:
            yield page
            n += 1
            if not page.select_one(f'.c-pagination a[href*="/page-{n}"]'):
                return
            page = self.get_html(f"{url}/page-{n}")


def _cards(page: BeautifulSoup) -> Iterator[tuple[str, str, list[datetime], str | None]]:
    """(url, title, start times, image) of each card. The site's markup nests each
    card inside the previous one, so fields are read relative to the card's title."""
    for heading in page.select("h3.c-media__title"):
        card = heading.find_parent(class_="c-media")
        link = card.select_one("a.c-media__faux-link[href]") if card else None
        if link is None:
            continue
        posttitle = heading.find_next_sibling(class_="c-media__posttitle")
        times = []
        for t in posttitle.select("time[datetime]") if posttitle else []:
            try:
                times.append(datetime.fromisoformat(t["datetime"]).astimezone(LONDON))
            except ValueError:
                continue
        yield link["href"], text_of(heading), sorted(times), image_src(card.select_one("img"))
