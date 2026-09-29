from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import yaml

from whatson.models import Venue

if TYPE_CHECKING:
    from whatson.aggregators.base import BaseAggregator

VENUES_FILE = Path(__file__).with_name("venues.yaml")

AGGREGATORS: dict[str, type[BaseAggregator]] = {}

A = TypeVar("A", bound="type[BaseAggregator]")


def register(cls: A) -> A:
    """Class decorator: make an aggregator available under its ``venue_id``."""
    if cls.venue_id in AGGREGATORS:
        raise ValueError(f"duplicate aggregator for venue {cls.venue_id!r}")
    AGGREGATORS[cls.venue_id] = cls
    return cls


def load_venues(path: Path = VENUES_FILE) -> dict[str, Venue]:
    raw = yaml.safe_load(path.read_text())
    return {v["id"]: Venue(**v) for v in raw["venues"]}


def load_aggregators() -> dict[str, type[BaseAggregator]]:
    import whatson.aggregators  # noqa: F401  (importing registers every aggregator)

    return AGGREGATORS
