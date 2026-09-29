# What's On

One filterable page for the What's On listings of London venues: theatre, comedy,
music, film and exhibitions. Filter by tag, date, price, area and venue.

Site: https://takecare.github.io/whatson/

## How it works

```
GitHub Actions (hourly check, scrapes every SCRAPE_INTERVAL_HOURS)
  scraper/ (Python) ── one aggregator per venue ──► events.json, venues.json, status.json
      │                                                   │
      └─ commits the JSON to the `data` branch            └─ web/ (static site) filters it
                                                             in the browser → GitHub Pages
```

- **`scraper/`** — a Python package. Each venue has an aggregator in
  `whatson/aggregators/` that turns the venue's site into `Event`s. If a venue
  fails, the previous run's events for it are kept and the failure shows on the
  site's Sources table.
- **`web/`** — a static TypeScript site (Vite, no framework). It loads the JSON and
  does all filtering client-side; filter state lives in the URL, so filtered views
  can be shared.
- **`data` branch** — the latest JSON, one commit per scrape.

## Setup (once)

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Settings → General → Default branch: `main`.** Scheduled workflows only run on
   the default branch.
3. **Actions → Scrape and deploy → Run workflow** to collect the first listings and
   publish the site. After that it runs by itself.

### Configuration (Settings → Secrets and variables → Actions → Variables)

| Variable | Default | What it does |
|---|---|---|
| `SCRAPE_INTERVAL_HOURS` | `24` | Hours between scrapes. The workflow checks hourly and scrapes once this much time has passed since the last scrape. `0` pauses scheduled scraping. |
| `SCRAPE_RUNS_ON` | `"ubuntu-latest"` | Where the scrape job runs, as JSON. Set to `["self-hosted","whatson"]` to use a self-hosted runner (see PLAN.md §4). Deleting it moves back to GitHub's machines. |

**Actions → Venue access check** fetches each venue's page once and reports whether
the runner can reach it or gets blocked by bot protection.

## Local development

Requires [uv](https://docs.astral.sh/uv/) and Node 22.

```sh
# Collect events into the site's data folder (--cache speeds up repeat runs)
cd scraper
uv run whatson scrape --out ../web/public/data --cache /tmp/whatson-cache
uv run whatson scrape --out ../web/public/data --venue saatchi   # one venue only
uv run whatson list            # venues and whether they have an aggregator
uv run whatson access-check --all

# Tests and lint
uv run pytest && uv run ruff check . && uv run ruff format --check .

# Site
cd ../web
npm install
npm run dev        # http://localhost:5173
npm test && npm run build
```

## Adding a venue

1. Add the venue to `scraper/whatson/venues.yaml` (id, name, What's On URL, address,
   area, coordinates, tags). Tags must be in `scraper/whatson/taxonomy.py`.
2. Add `scraper/whatson/aggregators/<venue>.py`: subclass `BaseAggregator`, set
   `venue_id`, decorate with `@register`, and implement `fetch_events()`, yielding
   `self.event(...)`. Use `self.get_html` / `self.get_json` / `self.http.post_text`
   so requests are rate-limited, retried and checked against robots.txt. Helpers in
   `whatson/parsing.py` handle free-text dates, times and prices.
3. Import the module in `scraper/whatson/aggregators/__init__.py`.
4. Save a copy of the pages it reads under `scraper/tests/fixtures/<venue>/` and add
   a test to `scraper/tests/test_aggregators.py` (see the existing ones; tests never
   touch the network).
5. Try it: `uv run whatson scrape --out ../web/public/data --venue <id>`.

Look for an API or feed before parsing HTML: WordPress sites often expose
`/wp-json/`, and pages that load listings with JavaScript usually call an endpoint
you can use directly.

## Venues

| Venue | Status |
|---|---|
| The Top Secret Comedy Club | ✅ collected (per-day endpoint used by their date picker) |
| Union Chapel | ✅ collected (listing + event pages; no prices published) |
| Saatchi Gallery | ✅ collected (WordPress REST API) |
| Barbican | planned |
| Prince Charles Cinema | planned |
| Royal Albert Hall | postponed: blocked by bot protection (Incapsula) |
| Southwark Playhouse | postponed: blocked by bot protection (SiteGround captcha) |

Listings are collected from each venue's public website with an identifying
User-Agent, at most one request per second per site, respecting robots.txt. Every
listing links back to the venue for details and booking.
