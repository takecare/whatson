from __future__ import annotations

import html
import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import parse_date_range, parse_dates
from whatson.registry import register

log = logging.getLogger(__name__)

API = "https://www.saatchigallery.com/wp-json/wp/v2/exhibitions"
PAGES = 3
PER_PAGE = 30
FIELDS = "id,date,link,title,aioseo_head_json.description,_links,_embedded"
# Only look up the page of undated posts published this recently; older ones are past.
DETAIL_WINDOW_DAYS = 120


@register
class SaatchiGallery(BaseAggregator):
    """The What's On page is rendered by JavaScript, but WordPress exposes the
    exhibitions over its REST API. The dates only appear in the SEO description:
    "Saatchi Gallery » TITLE 11 November 2026 - 5 May 2027 » blurb".
    """

    venue_id = "saatchi"

    def fetch_events(self) -> Iterator[Event]:
        for page in range(1, PAGES + 1):
            try:
                posts = self.get_json(
                    API,
                    {
                        "per_page": PER_PAGE,
                        "page": page,
                        "_embed": "wp:featuredmedia",
                        "_fields": FIELDS,
                    },
                )
            except FetchError:
                if page == 1:
                    raise
                break  # WordPress answers 400 past the last page
            if not posts:
                break
            for post in posts:
                for event in self._parse_post(post):
                    if event.last_day() >= self.today:
                        yield event

    def _parse_post(self, post: dict[str, Any]) -> list[Event]:
        title = html.unescape(post["title"]["rendered"]).strip()
        description = html.unescape((post.get("aioseo_head_json") or {}).get("description") or "")
        parts = [p.strip() for p in description.split("»")]
        if len(parts) < 2:
            return []
        when = parts[1]
        if when.lower().startswith(title.lower()):
            when = when[len(title) :]
        published = date.fromisoformat(post["date"][:10])
        if not parse_dates(when, published) and (self.today - published).days < DETAIL_WINDOW_DAYS:
            when = self._dates_from_page(post["link"])
        try:
            start, end, dates = parse_date_range(when, ref=published)
        except ValueError:
            log.info("saatchi: no dates for %r", title)
            return []

        common = {
            "title": title,
            "url": post["link"],
            "category": "Nightlife" if title.lower().startswith("lates") else "Exhibition",
            "tags": ["Art"],
            "summary": " ".join(parts[2:]) or None,
            "image_url": _image(post),
        }
        if dates:
            # Separate evenings ("27 November, 4 December"): one event per date.
            return [self.event(start=d, **common) for d in dates]
        return [self.event(start=start, end=end, **common)]

    def _dates_from_page(self, url: str) -> str:
        """Some posts leave the dates out of the description; the page shows them in
        a sub-heading."""
        try:
            soup = self.get_html(url)
        except FetchError:
            return ""
        for h in soup.select("h2.sub-heading-2x"):
            if parse_dates(text_of(h), self.today):
                return text_of(h)
        return ""


def _image(post: dict[str, Any]) -> str | None:
    media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
    if not media or not isinstance(media[0], dict):
        return None
    sizes = (media[0].get("media_details") or {}).get("sizes") or {}
    for size in ("medium_large", "medium", "full"):
        if size in sizes:
            return sizes[size].get("source_url")
    return media[0].get("source_url")
