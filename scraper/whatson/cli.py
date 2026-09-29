"""Command line: `whatson scrape`, `whatson access-check`, `whatson list`."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from whatson.http import HttpClient
from whatson.registry import load_aggregators, load_venues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="whatson")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scrape", help="collect events and write events/venues/status JSON")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--previous", type=Path, help="previous output, reused for failing venues")
    p.add_argument("--venue", action="append", help="only scrape this venue (repeatable)")
    p.add_argument("--cache", type=Path, help="cache responses here (for development)")
    p.add_argument("--min-interval", type=float, default=1.0, help="seconds between requests")

    p = sub.add_parser("access-check", help="report the HTTP status of every venue page")
    p.add_argument("--all", action="store_true", help="include venues without an aggregator")

    sub.add_parser("list", help="list venues and whether they have an aggregator")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.command == "scrape":
        from whatson.runner import scrape

        with HttpClient(min_interval=args.min_interval, cache_dir=args.cache) as http:
            statuses = scrape(http, args.out, args.previous, args.venue)
        failed = [s.venue_id for s in statuses if not s.ok]
        print(
            f"{len(statuses) - len(failed)}/{len(statuses)} venues ok"
            + (f"; failing: {', '.join(failed)}" if failed else "")
        )
        return 0

    if args.command == "access-check":
        return access_check(include_all=args.all)

    if args.command == "list":
        aggregators = load_aggregators()
        for v in load_venues().values():
            state = "ok" if v.id in aggregators else "no aggregator"
            print(f"{v.id:20} {'enabled' if v.enabled else 'disabled':9} {state:14} {v.url}")
        return 0
    return 1


def access_check(include_all: bool) -> int:
    """Fetch each venue's page once and print a Markdown table (also to the job summary)."""
    aggregators = load_aggregators()
    rows = ["| Venue | URL | HTTP | Size |", "|---|---|---|---|"]
    with HttpClient(retries=1) as http:
        for v in load_venues().values():
            if not include_all and v.id not in aggregators:
                continue
            try:
                code, body = http.probe(v.url)
                challenge = _challenge(body)
                if challenge:
                    result = f"{code} ❌ blocked ({challenge})"
                else:
                    result = str(code) + (" ✅" if code == 200 else " ❌")
                size = len(body)
            except Exception as e:
                result, size = f"{type(e).__name__} ❌", 0
            rows.append(f"| {v.name} | {v.url} | {result} | {size:,} B |")
    table = "\n".join(rows)
    print(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("## Venue access check\n\n" + table + "\n")
    return 0


# Markers of bot-protection pages, which are often served with HTTP 200.
CHALLENGE_MARKERS = {
    b"_Incapsula_Resource": "Incapsula",
    b"sgcaptcha": "SiteGround captcha",
    b"cf-challenge": "Cloudflare",
    b"Attention Required! | Cloudflare": "Cloudflare",
    b"Just a moment...": "Cloudflare",
    b"captcha-delivery.com": "DataDome",
}


def _challenge(body: bytes) -> str | None:
    head = body[:20_000]
    return next((name for marker, name in CHALLENGE_MARKERS.items() if marker in head), None)


if __name__ == "__main__":
    sys.exit(main())
