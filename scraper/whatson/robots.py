"""robots.txt rules, matched as RFC 9309 says.

Python's urllib.robotparser treats "*" in paths literally and applies rules in file
order, so it gets rules like "Allow: /p/*" + "Disallow: /" wrong. Here the most
specific (longest) matching rule wins, "*" matches any characters and "$" anchors
the end; on a tie, Allow wins.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

PRODUCT_TOKEN = "whatson-bot"


class Robots:
    def __init__(self, text: str, product: str = PRODUCT_TOKEN) -> None:
        groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[bool, str]] = []
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            field, value = (part.strip() for part in line.split(":", 1))
            field = field.lower()
            if field == "user-agent":
                if rules:  # a user-agent after rules starts a new group
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
            elif field in ("allow", "disallow") and agents:
                if value:  # an empty Disallow allows everything
                    rules.append((field == "allow", value))
        if agents:
            groups.append((agents, rules))

        product = product.lower()
        mine = [r for a, r in groups if any(x != "*" and x in product for x in a)]
        chosen = mine or [r for a, r in groups if "*" in a]
        self.rules = [rule for group in chosen for rule in group]

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        if path == "/robots.txt":
            return True
        best: tuple[int, bool] | None = None  # (pattern length, allow)
        for allow, pattern in self.rules:
            if _pattern(pattern).match(path):
                candidate = (len(pattern), allow)
                if best is None or candidate > best:
                    best = candidate
        return best is None or best[1]


def _pattern(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = re.escape(pattern.rstrip("$")).replace(r"\*", ".*")
    return re.compile(body + ("$" if anchored else ""))
