from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import date
from typing import Any, ClassVar

from bs4 import BeautifulSoup

from whatson.http import Fetcher
from whatson.models import Event, Venue


class BaseAggregator(ABC):
    """Collects the events of one venue.

    Subclasses set ``venue_id`` (matching an entry in venues.yaml), are registered with
    ``@register``, and implement ``fetch_events``. All network access goes through
    ``self.http`` so tests can replay saved pages.
    """

    venue_id: ClassVar[str]
    min_interval: ClassVar[float | None] = None
    """Seconds between requests to this venue's site, for sites that rate-limit."""

    def __init__(self, venue: Venue, http: Fetcher, today: date | None = None) -> None:
        self.venue = venue
        self.http = http
        self.today = today or date.today()
        throttle = getattr(http, "throttle", None)
        if self.min_interval and throttle:
            throttle(venue.url, self.min_interval)

    @abstractmethod
    def fetch_events(self) -> Iterable[Event]: ...

    # Helpers shared by aggregators -------------------------------------------------

    def event(self, **fields: Any) -> Event:
        """Build an Event for this venue."""
        return Event(venue_id=self.venue.id, **fields)

    def get_html(self, url: str, params: dict[str, Any] | None = None) -> BeautifulSoup:
        return BeautifulSoup(self.http.get_text(url, params), "lxml")

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self.http.get_json(url, params)

    @staticmethod
    def json_ld(soup: BeautifulSoup, type_: str | None = "Event") -> list[dict[str, Any]]:
        """schema.org objects of ``type_`` embedded as JSON-LD, if the page has any.
        With ``type_=None``, every object whose type ends in "Event" (MusicEvent, ...)."""
        found: list[dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for n in node:
                    walk(n)
            elif isinstance(node, dict):
                t = node.get("@type")
                types = t if isinstance(t, list) else [t]
                if any(
                    isinstance(x, str) and (x == type_ if type_ else x.endswith("Event"))
                    for x in types
                ):
                    found.append(node)
                walk(node.get("@graph"))

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                walk(json.loads(tag.string or ""))
            except json.JSONDecodeError:
                continue
        return found


def text_of(node: Any) -> str:
    """Whitespace-normalised text of a BeautifulSoup node (empty string for None)."""
    return " ".join(node.get_text(" ").split()) if node is not None else ""
