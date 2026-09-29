"""Runs aggregators, merges with the previous run and writes the JSON the site reads."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from whatson.http import Fetcher
from whatson.models import Event, SourceStatus, Venue
from whatson.registry import load_aggregators, load_venues

log = logging.getLogger(__name__)

EVENTS_FILE = "events.json"
VENUES_FILE = "venues.json"
STATUS_FILE = "status.json"

_events_adapter = TypeAdapter(list[Event])


@dataclass
class Previous:
    events: dict[str, list[Event]]
    status: dict[str, SourceStatus]

    @classmethod
    def load(cls, directory: Path | None) -> Previous:
        events: dict[str, list[Event]] = {}
        status: dict[str, SourceStatus] = {}
        if not directory:
            return cls(events, status)
        try:
            raw = json.loads((directory / EVENTS_FILE).read_text())
            for e in _events_adapter.validate_python(raw["events"]):
                events.setdefault(e.venue_id, []).append(e)
        except (OSError, KeyError, ValueError, ValidationError) as e:
            log.info("no usable previous events in %s: %s", directory, e)
        try:
            raw = json.loads((directory / STATUS_FILE).read_text())
            for s in raw["sources"]:
                status[s["venue_id"]] = SourceStatus(**s)
        except (OSError, KeyError, ValueError, ValidationError) as e:
            log.info("no usable previous status in %s: %s", directory, e)
        return cls(events, status)


def run_one(venue: Venue, http: Fetcher, today: date) -> list[Event]:
    aggregator = load_aggregators()[venue.id](venue, http, today)
    events: dict[str, Event] = {}
    for event in aggregator.fetch_events():
        if event.last_day() >= today:
            events.setdefault(event.id, event)
    return list(events.values())


def scrape(
    http: Fetcher,
    out_dir: Path,
    previous_dir: Path | None = None,
    only: list[str] | None = None,
    today: date | None = None,
) -> list[SourceStatus]:
    today = today or date.today()
    now = datetime.now(UTC).replace(microsecond=0)
    venues = load_venues()
    aggregators = load_aggregators()
    previous = Previous.load(previous_dir)

    all_events: list[Event] = []
    statuses: list[SourceStatus] = []
    for venue in venues.values():
        if not venue.enabled or venue.id not in aggregators:
            continue
        prev_status = previous.status.get(venue.id)
        prev_events = [e for e in previous.events.get(venue.id, []) if e.last_day() >= today]
        if only and venue.id not in only:
            # Not scraped this time: carry the previous results over untouched.
            all_events.extend(prev_events)
            if prev_status:
                statuses.append(prev_status)
            continue

        started = time.monotonic()
        error: str | None = None
        try:
            events = run_one(venue, http, today)
            if not events and prev_events:
                error = "returned no events (previously had some); keeping previous data"
        except Exception as e:  # one broken venue must not break the others
            log.exception("%s failed", venue.id)
            error = f"{type(e).__name__}: {e}"
            events = []
        duration = round(time.monotonic() - started, 1)

        if error:
            all_events.extend(prev_events)
            statuses.append(
                SourceStatus(
                    venue_id=venue.id,
                    ok=False,
                    event_count=len(prev_events),
                    error=error[:500],
                    duration_s=duration,
                    last_success=prev_status.last_success if prev_status else None,
                    stale=bool(prev_events),
                )
            )
        else:
            all_events.extend(events)
            statuses.append(
                SourceStatus(
                    venue_id=venue.id,
                    ok=True,
                    event_count=len(events),
                    duration_s=duration,
                    last_success=now,
                )
            )
        log.info(
            "%s: %s events in %.1fs%s",
            venue.id,
            statuses[-1].event_count,
            duration,
            f" (error: {error})" if error else "",
        )

    all_events.sort(key=lambda e: (_sort_key(e), e.title))
    write_outputs(out_dir, now, venues, all_events, statuses)
    return statuses


def _sort_key(e: Event) -> str:
    return e.start.isoformat() if isinstance(e.start, datetime) else f"{e.start.isoformat()}T00"


def write_outputs(
    out_dir: Path,
    now: datetime,
    venues: dict[str, Venue],
    events: list[Event],
    statuses: list[SourceStatus],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = now.isoformat()
    _dump(
        out_dir / EVENTS_FILE,
        generated,
        "events",
        [e.model_dump(mode="json", exclude_none=True) for e in events],
    )
    _dump(
        out_dir / VENUES_FILE,
        generated,
        "venues",
        [v.model_dump(mode="json", exclude={"enabled"}) for v in venues.values() if v.enabled],
    )
    _dump(
        out_dir / STATUS_FILE, generated, "sources", [s.model_dump(mode="json") for s in statuses]
    )


def _dump(path: Path, generated_at: str, key: str, items: list[dict]) -> None:
    """Write {"generated_at": ..., key: [...]} with one item per line, for readable diffs."""
    lines = ",\n".join(json.dumps(i, ensure_ascii=False, separators=(",", ":")) for i in items)
    path.write_text(f'{{"generated_at":"{generated_at}","{key}":[\n{lines}\n]}}\n')
