from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from datetime import date
from urllib.parse import urljoin

from whatson.aggregators.base import BaseAggregator, image_src, text_of
from whatson.http import FetchError
from whatson.models import Event
from whatson.registry import register

log = logging.getLogger(__name__)

# Most of ExCeL's calendar is trade and B2B shows, which we leave out. The site's
# consumer/trade filter works through /ajax/, which robots.txt disallows, and event
# pages don't state their type, so we judge from the title and the page's intro:
# trade shows talk about professionals and industry, consumer ones about families,
# fans and tickets.
_TRADE = re.compile(
    r"\b(professionals?|industry|industries|trade|b2b|suppliers?|buyers?|procurement|"
    r"business(es)?|conference|congress|summit|expo|sector|clinical|veterinary|dental|"
    r"dentistry|housing|hotels?|interiors|hospitality|infrastructure|enterprise|"
    r"retail(ers)?|manufactur\w*|logistics|decision[- ]makers|c-suite|delegates|"
    r"networking|exhibitors|innovation|technology|tech)\b"
)
_CONSUMER = re.compile(
    r"\b(famil(y|ies)|kids|children|immersive|fans?|cosplay|comic|gaming|anime|weekend|"
    r"book now|tickets?|visitors|fun|festival|live stage|celebrit\w*|meet stars|shopping|"
    r"foodies?|christmas|circus|cirque|horses?|wedding|consumer)\b"
)
_FAMILY = re.compile(r"\b(famil(y|ies)|kids|children)\b")
INTRO_CHARS = 600


def is_trade(title: str, intro: str) -> bool:
    """True when the title and intro read like a trade show. Ties go to consumer."""
    text = f"{title} {intro[:INTRO_CHARS]}".lower()
    return len(_TRADE.findall(text)) > len(_CONSUMER.findall(text))


@register
class ExcelLondon(BaseAggregator):
    """The visitor What's On page lists every event with machine-readable start and
    end dates. Each event's page is read for its intro, to leave out trade shows."""

    venue_id = "excel"

    def fetch_events(self) -> Iterator[Event]:
        for item in self.get_html(self.venue.url).select("a.item[href]"):
            title = text_of(item.select_one(".name"))
            try:
                start = date.fromisoformat(text_of(item.select_one(".date")))
                end = date.fromisoformat(text_of(item.select_one(".date2")))
            except ValueError:
                continue
            url = urljoin(self.venue.url, item["href"])
            try:
                intro = self._intro(url)
            except FetchError as e:
                log.warning("excel: skipping %s: %s", url, e)
                continue
            if is_trade(title, intro):
                continue
            tags = ["Exhibition", "Family"] if _FAMILY.search(intro.lower()) else ["Exhibition"]
            yield self.event(
                title=title,
                url=url,
                category="Exhibition",
                tags=tags,
                start=start,
                end=end if end > start else None,
                image_url=image_src(item.select_one("img")),
                summary=intro[:INTRO_CHARS].strip() or None,
            )

    def _intro(self, url: str) -> str:
        page = self.get_html(url)
        text = text_of(page.select_one("main") or page)
        marker = "Visitor | What’s on"
        at = text.find(marker)
        return text[at + len(marker) :] if at >= 0 else text
