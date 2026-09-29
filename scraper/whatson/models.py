from __future__ import annotations

import hashlib
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from whatson.taxonomy import normalise_tag


def _normalise_tags(tags: list[str]) -> list[str]:
    return sorted({normalise_tag(t) for t in tags})


class Venue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    url: str
    """The venue's What's On page."""
    address: str
    city: str
    area: str | None = None
    """Neighbourhood used by the location filter, e.g. "Soho" or "Islington"."""
    lat: float
    lng: float
    tags: list[str] = Field(default_factory=list)
    """What the venue generally hosts. Events without tags of their own inherit these."""
    enabled: bool = True

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, v: list[str]) -> list[str]:
        return _normalise_tags(v)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    """Stable id; derived from venue, url and start when left empty."""
    venue_id: str
    title: str
    url: str
    """Detail page on the venue's site."""
    booking_url: str | None = None
    category: str | None = None
    """Main type, e.g. "Comedy". Always included in ``tags`` too."""
    tags: list[str] = Field(default_factory=list)
    start: date | datetime
    end: date | datetime | None = None
    """End of a run (theatre run, exhibition). None for one-off events."""
    performances: list[datetime] = Field(default_factory=list)
    """Individual showtimes, e.g. every screening of one film."""
    space: str | None = None
    """Sub-location within the venue: a hall, a room or a second site."""
    price_min: float | None = None
    """None means unknown; 0 means free."""
    price_max: float | None = None
    currency: str = "GBP"
    sold_out: bool = False
    image_url: str | None = None
    summary: str | None = None

    @field_validator("title", "summary", "space")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = " ".join(v.split())
        return v or None

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str | None) -> str | None:
        return normalise_tag(v) if v else None

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, v: list[str]) -> list[str]:
        return _normalise_tags(v)

    @model_validator(mode="after")
    def _finish(self) -> Event:
        if self.category and self.category not in self.tags:
            self.tags = sorted([*self.tags, self.category])
        if self.performances:
            self.performances = sorted(set(self.performances))
        if self.price_min is not None and self.price_max is None:
            self.price_max = self.price_min
        if self.summary and len(self.summary) > 300:
            self.summary = self.summary[:297].rsplit(" ", 1)[0] + "…"
        if not self.id:
            key = f"{self.venue_id}|{self.url}|{self.start.isoformat()}"
            self.id = hashlib.sha1(key.encode()).hexdigest()[:12]
        return self

    def last_day(self) -> date:
        """The last day this event is on, used to drop past events."""
        candidates = [self.start, *(self.performances or [])]
        if self.end:
            candidates.append(self.end)
        return max(_as_date(c) for c in candidates)


def _as_date(d: date | datetime) -> date:
    return d.date() if isinstance(d, datetime) else d


class SourceStatus(BaseModel):
    venue_id: str
    ok: bool
    event_count: int
    error: str | None = None
    duration_s: float | None = None
    last_success: datetime | None = None
    stale: bool = False
    """True when the events shown are carried over from an earlier successful run."""
