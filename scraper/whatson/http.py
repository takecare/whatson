"""HTTP access for aggregators: polite, retried, rate-limited and optionally cached."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)

USER_AGENT = os.environ.get(
    "WHATSON_USER_AGENT",
    "Mozilla/5.0 (compatible; whatson-bot/0.1; +https://github.com/takecare/whatson)",
)


class FetchError(Exception):
    pass


class Fetcher(Protocol):
    """What aggregators need from an HTTP client. Tests pass a fake."""

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str: ...
    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any: ...
    def post_text(self, url: str, data: dict[str, str]) -> str: ...


class HttpClient:
    def __init__(
        self,
        *,
        min_interval: float = 1.0,
        retries: int = 3,
        timeout: float = 30.0,
        cache_dir: Path | None = None,
        respect_robots: bool = True,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en;q=0.9"},
            timeout=timeout,
            follow_redirects=True,
        )
        self._min_interval = min_interval
        self._retries = retries
        self._cache_dir = cache_dir
        self._respect_robots = respect_robots
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        return self._get(url, params).decode("utf-8", errors="replace")

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return json.loads(self._get(url, params))

    def post_text(self, url: str, data: dict[str, str]) -> str:
        """POST form data (e.g. to a WordPress admin-ajax endpoint the page itself uses)."""
        return self._get(url, None, data).decode("utf-8", errors="replace")

    def status(self, url: str) -> tuple[int, int]:
        """Fetch ``url`` without raising; return (status code, body size). For access checks."""
        self._wait(url)
        resp = self._client.get(url)
        return resp.status_code, len(resp.content)

    def _get(
        self, url: str, params: dict[str, Any] | None, data: dict[str, str] | None = None
    ) -> bytes:
        full = str(httpx.URL(url, params=params)) if params else url
        cached = self._cache_path(full + (json.dumps(data, sort_keys=True) if data else ""))
        if cached and cached.exists():
            return cached.read_bytes()
        if not self._allowed(full):
            raise FetchError(f"robots.txt disallows {full}")

        last_error: Exception | None = None
        for attempt in range(self._retries):
            self._wait(full)
            try:
                if data is None:
                    resp = self._client.get(full)
                else:
                    resp = self._client.post(full, data=data)
            except httpx.HTTPError as e:
                last_error = e
            else:
                if resp.status_code == 200:
                    if cached:
                        cached.parent.mkdir(parents=True, exist_ok=True)
                        cached.write_bytes(resp.content)
                    return resp.content
                last_error = FetchError(f"HTTP {resp.status_code} for {full}")
                if resp.status_code < 500 and resp.status_code != 429:
                    break
            log.info("retrying %s after %s", full, last_error)
            time.sleep(2**attempt)
        raise FetchError(str(last_error)) from last_error

    def _wait(self, url: str) -> None:
        host = urlsplit(url).netloc
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request[host] = time.monotonic()

    def _allowed(self, url: str) -> bool:
        if not self._respect_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                resp = self._client.get(f"{origin}/robots.txt")
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser = None  # no robots.txt (or unreadable): allow
            except httpx.HTTPError:
                parser = None
            self._robots[origin] = parser
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    def _cache_path(self, url: str) -> Path | None:
        if not self._cache_dir:
            return None
        return self._cache_dir / hashlib.sha1(url.encode()).hexdigest()
