from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whatson.http import FetchError
from whatson.registry import load_venues

FIXTURES = Path(__file__).parent / "fixtures"


class FakeFetcher:
    """Serves saved pages instead of hitting the network.

    ``routes`` maps a key to a fixture path (relative to tests/fixtures). The key is the
    URL for GETs, or "URL|value" for POSTs, where value is the first form field that
    isn't "action". Unknown keys raise FetchError, like a failed request would.
    """

    def __init__(self, routes: dict[str, str]) -> None:
        self.routes = routes
        self.requested: list[str] = []

    def _load(self, key: str) -> str:
        self.requested.append(key)
        if key not in self.routes:
            raise FetchError(f"no fixture for {key}")
        return (FIXTURES / self.routes[key]).read_text()

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        return self._load(url)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        page = (params or {}).get("page", 1)
        return json.loads(self._load(f"{url}|page={page}"))

    def post_text(self, url: str, data: dict[str, str]) -> str:
        value = next(v for k, v in data.items() if k != "action")
        return self._load(f"{url}|{value}")


@pytest.fixture
def venues():
    return load_venues()
