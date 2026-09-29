from __future__ import annotations

import html
import logging
import re
from collections.abc import Iterator
from typing import Any

from whatson.aggregators.base import BaseAggregator, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.parsing import at, parse_date_range, parse_time
from whatson.registry import register

log = logging.getLogger(__name__)

API = "https://southwarkparkgalleries.org/wp-json/wp/v2/posts"
CURRENT, UPCOMING = 5, 4
# WordPress category ids mapped onto our tags.
CATEGORIES = {
    9: ["Exhibition", "Art"],  # Exhibitions
    11: ["Talks"],  # Events
    3: ["Workshop"],  # Learning
    1670: ["Workshop", "Family"],  # Current Workshops
    1839: ["Art"],  # Public Art
}


@register
class SouthwarkParkGalleries(BaseAggregator):
    """WordPress. The REST API lists what's on through two categories, "Current"
    and "Upcoming"; each post's page header gives the dates ("15 August – 1 November
    2026"), the gallery (Lake Gallery // Dilston Gallery) and, for talks, a time.
    """

    venue_id = "southwarkparkgalleries"

    def fetch_events(self) -> Iterator[Event]:
        posts = self.get_json(
            API,
            {
                "categories": f"{CURRENT},{UPCOMING}",
                "per_page": 50,
                "_embed": "wp:featuredmedia",
                "_fields": "id,link,title,excerpt,categories,_links,_embedded",
            },
        )
        for post in posts:
            try:
                event = self._parse_post(post)
            except FetchError as e:
                log.warning("southwarkparkgalleries: skipping %s: %s", post.get("link"), e)
                continue
            if event:
                yield event

    def _parse_post(self, post: dict[str, Any]) -> Event | None:
        page = self.get_html(post["link"])
        header = page.select_one(".post-header") or page
        time_line = ""
        for span in header.select(".post-text-column > span"):
            if text_of(span.find("strong")).lower().startswith("time"):
                time_line = text_of(span).split(":", 1)[-1]
        # The dates are usually in .event-date; workshop series put them in the title
        # ("Green Shoots! 17 May - 25 October 2026") and talks only give a time line
        # ("Time: Friday 16 October, 4-5pm").
        event_date = text_of(header.select_one(".event-date"))
        for when in (event_date, text_of(header.find("h1")), time_line):
            try:
                start, end, separate = parse_date_range(when, self.today)
                break
            except ValueError:
                continue
        else:
            return None  # e.g. "July 2025 - July 2026" or a permanent work
        if separate:
            start, end = separate[0], separate[-1]
        time = parse_time(time_line)

        tags: list[str] = []
        for category in post.get("categories", []):
            tags += [t for t in CATEGORIES.get(category, []) if t not in tags]
        spaces = [text_of(s) for s in header.select(".event-category span")]
        excerpt = html.unescape(re.sub(r"<[^>]+>", " ", post["excerpt"]["rendered"]))
        return self.event(
            title=html.unescape(post["title"]["rendered"]).strip(),
            url=post["link"],
            category=tags[0] if tags else None,
            tags=tags,
            start=start if end else at(start, time),
            end=end,
            space=" & ".join(spaces) or None,
            image_url=_image(post),
            summary=excerpt.strip() or None,
        )


def _image(post: dict[str, Any]) -> str | None:
    media = (post.get("_embedded") or {}).get("wp:featuredmedia") or []
    if not media or not isinstance(media[0], dict):
        return None
    sizes = (media[0].get("media_details") or {}).get("sizes") or {}
    for size in ("medium_large", "large", "medium", "full"):
        if size in sizes:
            return sizes[size].get("source_url")
    return media[0].get("source_url")
