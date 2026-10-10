from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime, time, timedelta
from typing import Any

from bs4 import BeautifulSoup

from whatson import LONDON
from whatson.aggregators.base import BaseAggregator
from whatson.models import Event
from whatson.registry import register

BASE = "https://www.rbo.org.uk"
_STATE = re.compile(r"window\.__REACT_QUERY_DEHYDRATED_STATE__\s*=\s*")
# The site's tags (by title), and ours.
TAGS = {
    "Opera and music": ["Opera"],
    "Ballet and dance": ["Dance"],
    "Tours": ["Tours"],
    "Workshops and activities": ["Workshop"],
    "Family events": ["Family"],
    "Family Friendly": ["Family"],
    "Talks and insights": ["Talks"],
    "Festivals": ["Festival"],
    "Audio Described": ["Audio Described"],
    "BSL Interpreted": ["Signed"],
    "Captioned": ["Captioned"],
    "Relaxed Performance": ["Relaxed"],
}
# Not at the Royal Opera House: cinema screenings, the Thurrock workshops, streams.
ELSEWHERE = {"Cinema", "Thurrock", "Online only"}
OFFSITE_TAGS = {"Cinema broadcasts", "Livestreams online", "TV and radio broadcasts"}
# Performances the public can't book, or not in Covent Garden.
SKIP_PERFORMANCES = {"schools-matinee", "thurrock"}
_TOUR = re.compile(r"\btours?\b", re.I)
_MUSIC = re.compile(r"\b(recitals?|concerts?|live at lunch)\b", re.I)


def _plain(html: str | None) -> str:
    return " ".join(BeautifulSoup(html or "", "lxml").get_text(" ").split())


def _london(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(LONDON)


@register
class RoyalOperaHouse(BaseAggregator):
    """Royal Ballet and Opera's What's On page embeds its whole programme as JSON
    (React Query's dehydrated state; every ``?page=`` carries the same data): each
    production or event with its performances, locations and tags. Event pages sit
    under /events/, which robots.txt disallows, so only the listing is read."""

    venue_id = "rbo"

    def fetch_events(self) -> Iterator[Event]:
        html = self.http.get_text(self.venue.url)
        m = _STATE.search(html)
        if not m:
            raise ValueError("no programme data in the page")
        state, _ = json.JSONDecoder().raw_decode(html, m.end())
        data = next(
            q["state"]["data"]["events"]
            for q in state["queries"]
            if q.get("queryKey") == ["eventsPage"]
        )
        tags = {t["id"]: t["title"] for t in data.get("tags", [])}
        places = {loc["id"]: loc["title"] for loc in data.get("locations", [])}
        items = data.get("events", [])
        # A series ("Opera on the Terrace") is listed once as a whole and once per date.
        cards = {e["slug"] for e in items if e.get("sourceType") == "prismic-only-event-card"}
        for item in items:
            if item.get("sourceType") == "prismic-only-event-detail" and item.get("slug") in cards:
                continue
            event = self._event(item, tags, places)
            if event:
                yield event

    def _event(
        self, item: dict[str, Any], tags: dict[str, str], places: dict[str, str]
    ) -> Event | None:
        if item.get("isCancelled") or item.get("isHiddenFromTicketsAndEvents"):
            return None
        title = _plain(item.get("title"))
        where = [places.get(i, "") for i in item.get("locations") or []]
        site_tags = [tags.get(t, "") for t in item.get("tags") or []]
        page = item.get("productionPageUrl") or ""
        if not title or "mode=cinema" in page:
            return None
        if where and all(w in ELSEWHERE for w in where):
            return None
        if not where and OFFSITE_TAGS & set(site_tags):
            return None

        performances = sorted(
            _london(p["date"])
            for p in item.get("performances") or []
            if p.get("date") and p.get("performanceType") not in SKIP_PERFORMANCES
        )
        start: datetime | Any
        end = None
        if performances:
            start = performances[0]
        elif item.get("startTime"):
            # Events without performances give a start and end time instead. Whole
            # days run from midnight to midnight: 11 Jun 00:00 to 25 Jun 00:00 is 11–24 June.
            first = _london(item["startTime"])
            last = _london(item["endTime"]) if item.get("endTime") else first
            last_day = (
                (last - timedelta(microseconds=1)).date()
                if last > first and last.time() == time(0)
                else last.date()
            )
            if first.date() == last_day:
                start = first.date() if first.time() == time(0) else first
            else:
                start, end = first.date(), last_day
        elif item.get("performances"):
            return None  # only schools or Thurrock performances
        else:
            return None  # part of a programme, listed without dates

        our_tags: list[str] = []
        for t in site_tags:
            our_tags += [x for x in TAGS.get(t, []) if x not in our_tags]
        if not our_tags and _TOUR.search(title):
            our_tags = ["Tours"]
        elif not our_tags and _MUSIC.search(title):
            our_tags = ["Music"]
        main = [
            t for t in our_tags if t not in ("Audio Described", "Signed", "Captioned", "Relaxed")
        ]

        if page:
            url = BASE + page
        elif item.get("sourceType") == "prismic-only-event-card":
            url = self.venue.url  # these cards have no page of their own
        else:
            url = f"{BASE}/tickets-and-events/{item['slug']}-details"
        image = (item.get("imageResult") or item.get("imageTray") or {}).get("desktopPath")
        spaces = [w for w in where if w and w != "Royal Opera House"]
        return self.event(
            title=title,
            url=url,
            category=main[0] if main else None,
            tags=our_tags,
            start=start,
            end=end,
            performances=performances,
            space=", ".join(spaces) or None,
            image_url=image,
            summary=_plain(item.get("description") or item.get("carouselDescription")) or None,
        )
