# What's On — aggregator plan

A static website that combines "What's On" listings from London/UK venues into one
filterable view (tags, dates, price, location, text search).

## 1. Architecture

```
          (GitHub Actions, cron ~daily)                         (GitHub Pages)
┌───────────────────────────────────────────────┐        ┌──────────────────────────┐
│ scraper (Python)                              │        │ web (static, TypeScript) │
│  venues.yaml ─► registry ─► Aggregator per    │  JSON  │  loads events.json and   │
│  venue ─► [Event] ─► normalise/dedupe/validate├───────►│  venues.json, filters    │
│  ─► data/events.json, venues.json, status.json│        │  everything client-side  │
└───────────────────────────────────────────────┘        └──────────────────────────┘
```

- **No backend.** Scraping happens at build time on a schedule; the site is plain
  static files, so GitHub Pages is enough. Scraping from the browser is not an
  option (CORS, bot protection, speed).
- **Client-side filtering.** A few thousand events is a few hundred KB of JSON —
  fine to load once and filter in memory. If it grows, shard by month.
- **Failure isolation.** Each aggregator runs independently. If one fails, the
  build keeps that venue's last-known-good events and records the failure in
  `status.json` (shown on a small "sources" page), instead of failing the deploy.
- **Data history.** The workflow commits generated JSON to a `data` branch. That
  gives diffs, a last-known-good fallback, and keeps the scheduled workflow from
  being auto-disabled for inactivity.

## 2. Data model (`scraper/whatson/models.py`, pydantic)

```python
class Venue:
    id: str                    # "barbican"
    name: str
    url: str                   # what's-on page
    address: str
    city: str                  # "London"
    area: str | None           # "City of London", "Soho", "Islington"...
    lat: float; lng: float
    tags: list[Tag]            # ["Theatre", "Music", "Film", ...]

class Event:
    id: str                    # stable hash(venue_id, source_url or title+start)
    venue_id: str
    title: str
    url: str                   # booking/detail page on the venue site
    category: Tag | None       # main type: "Comedy", "Film", "Exhibition"...
    tags: list[Tag]            # event tags (merged with venue tags at query time)
    start: date | datetime
    end: date | datetime | None          # runs / exhibitions span a range
    performances: list[datetime] = []    # e.g. every PCC screening of one film
    space: str | None          # sub-location: "Barbican Hall", "23 Kingsway"
    price_min: Decimal | None  # None = unknown; 0 = free
    price_max: Decimal | None
    currency: str = "GBP"
    sold_out: bool = False
    image_url: str | None
    summary: str | None        # short excerpt only
    scraped_at: datetime
```

Notes from the example venues that shaped this:
- Theatre runs and exhibitions (Saatchi) span weeks → `start`/`end`, and the
  date filter matches on *overlap* with the selected range, not on start date.
- Cinemas list many screenings of one film → one `Event` per film with
  `performances`, rather than hundreds of near-duplicate cards.
- Top Secret Comedy Club runs two sites (Drury Lane, Kingsway), Barbican has many
  halls → optional `space`.
- **Tags** come from a controlled vocabulary (`taxonomy.py`: Theatre, Comedy,
  Music, Classical, Film, Art, Exhibition, Talks, Family, Dance, ...). Each
  aggregator maps the venue's own genre labels onto it, so filters stay coherent.

## 3. Aggregators (`scraper/whatson/aggregators/`)

```python
class BaseAggregator(ABC):
    venue: Venue
    def __init__(self, http: HttpClient): ...
    @abstractmethod
    def fetch_events(self) -> Iterable[Event]: ...

    # shared helpers
    def get_html(self, url) -> Selector          # cached, retried, rate-limited
    def get_json(self, url) -> Any
    def json_ld_events(self, html) -> list[dict] # schema.org Event, when present
    def parse_price(self, text) -> (min, max)    # "£12.50–£30", "Free", "£1"
    def parse_when(self, text, tz="Europe/London")
```

- Subclasses register via a `@register("venue-id")` decorator; `venues.yaml`
  holds venue metadata (name, address, coordinates, tags).
- Two fetch strategies behind the same interface: `httpx` (default) and a
  `BrowserAggregator` using Playwright for JS-rendered or challenge-protected sites.
- Politeness: identifiable User-Agent, respect robots.txt, ≤1 req/s per host,
  run ~daily, link out to the venue for booking, keep only a short summary and
  hotlink images rather than copying them.

### What the example venues look like (probed 2026-09-28)

| Venue | What I found | Approach | Difficulty |
|---|---|---|---|
| Top Secret Comedy Club | WordPress, list is server-rendered with date, site, times, price, sold-out | parse list HTML | Easy |
| Union Chapel | Server-rendered list with title + date; filters for genre/type | list HTML + detail pages for price/time | Easy |
| Saatchi Gallery | List is JS-rendered, but WP REST exposes an `exhibitions` post type | `/wp-json/wp/v2/exhibitions` | Easy |
| Prince Charles Cinema | Whole programme server-rendered (~1.8 MB), format tags (35mm, 70mm, Sing-along) | parse one page, group screenings per film | Medium |
| Barbican | Drupal, event links server-rendered, infinite scroll via `?page=N` | paginate list, then detail pages | Medium |
| Southwark Playhouse | SiteGround captcha (HTTP 202 + `sgcaptcha` redirect) for non-browser clients | Playwright; may still be blocked | Hard |
| Royal Albert Hall | HTTP 403 from Incapsula bot protection | Playwright, or look for a feed/partner API; may need deferring | Hard |

GitHub Actions runners use datacenter IPs, which bot protection blocks more
readily. If that bites, fallback: run the scraper somewhere else (home machine /
small VPS) and push the JSON; the site doesn't change.

## 4. Web frontend (`web/`)

Vite + TypeScript, lightweight (Preact or vanilla), no server.

- **Filters**
  - Tags: multi-select chips (venue tags ∪ event tags), with an any/all toggle
  - Dates: range calendar with quick picks (Today, This weekend, Next 7 days, This month)
  - Price: range slider + "Free only" + "Hide sold out" + "Include unknown price"
  - Location: city → area chips, venue multi-select, optional "near me" (distance from venue coordinates)
  - Text search over title/summary/venue
- **Views:** list grouped by day (default), and later a map.
- Filter state lives in the URL query string, so filtered views are shareable.
- Cards show title, venue/space, date(s), price range, tags, sold-out badge, link out.
- Mobile-first, light/dark theme, "last updated" + per-source status.

## 5. Repository layout

```
scraper/
  pyproject.toml                  # uv, ruff, pytest
  whatson/
    models.py  taxonomy.py  http.py  registry.py  cli.py
    venues.yaml
    aggregators/base.py  topsecret.py  unionchapel.py  saatchi.py  ...
  tests/
    fixtures/<venue>/*.html|json  # saved pages → offline parser tests
    test_<venue>.py
web/
  index.html  src/...  vite.config.ts
.github/workflows/
  ci.yml                          # lint + tests (scraper and web) on PRs
  scrape-and-deploy.yml           # cron + manual: scrape → build → deploy Pages
```

## 6. Execution phases

1. **Scaffold** — Python package (uv, ruff, pytest), Vite app, CI workflow, README.
2. **Core** — models, taxonomy, HTTP client (cache/retry/rate-limit), `BaseAggregator`,
   registry, CLI (`whatson scrape [--venue X] --out data/`), JSON schema for output.
3. **First venues end-to-end** — Top Secret, Union Chapel, Saatchi, each with
   fixture-based tests.
4. **Frontend MVP** — load JSON, tags/date/price/location/search filters, URL state.
5. **Deploy** — scheduled scrape → `data` branch → build → GitHub Pages; status page.
6. **More venues** — Prince Charles Cinema, Barbican.
7. **Hard venues** — Playwright-based Southwark Playhouse, then Royal Albert Hall
   (investigate; defer if blocked).
8. **Hardening** — dedupe, drop past events, schema validation, a script to refresh
   fixtures, alert (issue/comment) when a source fails N runs in a row.
9. **Later** — map view, "add to calendar" (.ics), favourites (localStorage),
   more UK cities, CONTRIBUTING guide on adding a venue.

## 7. Open questions

1. Python for scrapers + TypeScript for the site (recommended), or all TypeScript?
2. Is the repo public? GitHub Pages on a free plan needs a public repo.
3. Is a daily refresh enough?
4. OK to defer Royal Albert Hall / Southwark Playhouse if bot protection blocks them?
