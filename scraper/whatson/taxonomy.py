"""The controlled vocabulary of tags.

Aggregators map each venue's own genre labels onto these, so the site's tag filter
stays consistent across venues. Add new tags here rather than inventing them in an
aggregator; unknown tags are rejected by the Event model.
"""

TAGS: tuple[str, ...] = (
    "Art",
    "Classical",
    "Comedy",
    "Dance",
    "Exhibition",
    "Family",
    "Festival",
    "Film",
    "Jazz",
    "Music",
    "Nightlife",
    "Opera",
    "Sport",
    "Talks",
    "Theatre",
    "Tours",
    "Workshop",
    # Accessible performances
    "Audio Described",
    "Captioned",
    "Relaxed",
    "Signed",
)

_BY_LOWER = {t.lower(): t for t in TAGS}


def normalise_tag(tag: str) -> str:
    """Return the canonical spelling of ``tag``, or raise ``ValueError``."""
    try:
        return _BY_LOWER[tag.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown tag {tag!r}; add it to whatson/taxonomy.py") from None
