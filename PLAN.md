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
readily. See §4 for how the scrape job moves to a home machine without changing
the site.

## 4. Hosting

The site is static and stays on **GitHub Pages**. Only the scrape job moves.

**Stage A: GitHub-hosted runners (start here).**
`scrape-and-deploy.yml` runs hourly and has four jobs:

1. `plan`: decides whether a scrape is due (`SCRAPE_INTERVAL_HOURS`, default 24).
2. `scrape`: runs the aggregators and uploads the JSON as an artifact.
3. `publish`: commits the JSON to the `data` branch.
4. `deploy`: builds `web/` with that data and deploys to Pages.

Venues that get blocked show as failing in `status.json`, and their last-known-good
data is kept.

**Stage B: self-hosted runner on Proxmox.**
The `scrape` job doesn't hard-code where it runs:

```yaml
scrape:
  runs-on: ${{ fromJSON(vars.SCRAPE_RUNS_ON || '"ubuntu-latest"') }}
```

To move, set the repository variable `SCRAPE_RUNS_ON` to `["self-hosted","whatson"]`.
That needs no code change, and deleting the variable moves the job back to hosted
runners. `publish` and `deploy` stay on hosted runners, so the home box only needs
the runner registration and no deploy permissions. If the home box is offline, the
job waits in the queue (up to 24h) and the site keeps serving the previous data.

Proxmox guest:
- A small **VM** (Debian 12, 2 vCPU, 2–4 GB RAM, 20 GB disk). A VM rather than an
  LXC container gives better isolation, since the guest runs code from the repo, and
  Chromium/Playwright works in it without adjusting container settings.
- The Actions runner is registered at repo level with the label `whatson` and runs
  as a systemd service under an unprivileged user. `infra/proxmox/` holds a setup
  script plus a README covering VM creation, runner install, Playwright deps and
  updates.
- Security for a public repo: jobs with `runs-on: self-hosted` are only triggered by
  `schedule` / `workflow_dispatch` on `main`, never by `pull_request`. Fork PR
  workflows require approval (repo setting). If the network allows, put the VM on
  an isolated VLAN or firewall it off from the rest of the LAN.

**Later, optionally: split by venue.** If only a few venues need a home IP, add
`network: residential` to those entries in `venues.yaml`. A matrix then runs two
scrape jobs (hosted and self-hosted), and a merge step combines their outputs.
Only do this if keeping everything on the home box turns out to be a problem.

## 5. Web frontend (`web/`)

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

## 6. Repository layout

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
infra/proxmox/                    # self-hosted runner VM setup script + README
.github/workflows/
  access-check.yml                # manual: fetch every venue, report HTTP status
  ci.yml                          # lint + tests (scraper and web) on PRs
  scrape-and-deploy.yml           # cron + manual: scrape → build → deploy Pages
```

## 7. Execution phases

Built: 1–5 (with three venues: Top Secret Comedy Club, Union Chapel, Saatchi Gallery).

1. **Scaffold** — Python package (uv, ruff, pytest), Vite app, CI workflow, README,
   and `access-check.yml`, which confirms which venues GitHub-hosted runners can reach.
2. **Core** — models, taxonomy, HTTP client (cache/retry/rate-limit), `BaseAggregator`,
   registry, CLI (`whatson scrape [--venue X] --out data/`), JSON schema for output.
3. **First venues end-to-end** — Top Secret, Union Chapel, Saatchi, each with
   fixture-based tests.
4. **Frontend MVP** — load JSON, tags/date/price/location/search filters, URL state.
5. **Deploy (Stage A)** — scheduled scrape on hosted runners → `data` branch → build
   → GitHub Pages; status page. The `scrape` job gets its runner from `SCRAPE_RUNS_ON`.
6. **More venues** — Prince Charles Cinema, Barbican.
7. **Self-hosted (Stage B)** — `infra/proxmox/` setup script and README; register
   the runner; set `SCRAPE_RUNS_ON`; re-run `access-check.yml` on the home runner.
8. **Hard venues** — Playwright-based Southwark Playhouse, then Royal Albert Hall
   (look for a ticketing-platform feed first; defer if still blocked).
9. **Hardening** — dedupe, drop past events, schema validation, a script to refresh
   fixtures, alert (issue/comment) when a source fails N runs in a row.
10. **Later** — map view, "add to calendar" (.ics), favourites (localStorage),
   more UK cities, CONTRIBUTING guide on adding a venue.

## 8. Decisions

1. Python for scraping; TypeScript (Vite, no framework) for the site.
2. The repo is public (needed for GitHub Pages on a free plan).
3. Scrape daily by default, configurable with the `SCRAPE_INTERVAL_HOURS` repository
   variable: the workflow checks hourly and scrapes once that many hours have passed
   since the last scrape (`0` pauses it).
4. Royal Albert Hall and Southwark Playhouse are postponed (bot protection).
5. Hosting: GitHub-hosted runners first, then a self-hosted runner on Proxmox (§4).
6. Changes are committed straight to `main`, without pull requests.
