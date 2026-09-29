import pytest

from whatson.robots import Robots

ELFSIGHT = """
User-agent: *
Allow: /p/*
Disallow: /
"""

WORDPRESS = """
User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
Disallow: /*?add-to-cart=
Disallow: /search$
"""


@pytest.mark.parametrize(
    ("robots", "url", "allowed"),
    [
        # The most specific rule wins, whatever the order in the file.
        (ELFSIGHT, "https://x.test/p/boot/?w=1", True),
        (ELFSIGHT, "https://x.test/other", False),
        (ELFSIGHT, "https://x.test/robots.txt", True),
        (WORDPRESS, "https://x.test/wp-admin/admin-ajax.php", True),
        (WORDPRESS, "https://x.test/wp-admin/options.php", False),
        # "*" is a wildcard; "$" anchors the end.
        (WORDPRESS, "https://x.test/shop/?add-to-cart=12", False),
        (WORDPRESS, "https://x.test/search", False),
        (WORDPRESS, "https://x.test/search/results", True),
        (WORDPRESS, "https://x.test/whats-on/", True),
        # No robots rules: allowed.
        ("", "https://x.test/anything", True),
    ],
)
def test_robots(robots, url, allowed):
    assert Robots(robots).allows(url) is allowed


def test_specific_group_beats_star():
    robots = Robots("User-agent: *\nDisallow: /\n\nUser-agent: whatson-bot\nDisallow: /private\n")
    assert robots.allows("https://x.test/events")
    assert not robots.allows("https://x.test/private/page")


def test_tie_goes_to_allow():
    robots = Robots("User-agent: *\nDisallow: /page\nAllow: /page\n")
    assert robots.allows("https://x.test/page")
