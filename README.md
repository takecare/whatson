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

Status: ✅ collected · 🔜 planned (reachable, approach known) · ⏸️ postponed
(blocked by bot protection). "Blocked" means the venue's site refuses
our requests; `whatson access-check --all` (or the **Venue access check** workflow)
shows the current state.

| Venue | Status | Why / how |
|---|---|---|
| The Top Secret Comedy Club | ✅ Collected | Asks the per-day endpoint their date picker uses; the listing's own page links are broken. |
| Union Chapel | ✅ Collected | Listing page plus each event's page for the start time. They don't publish prices. |
| Saatchi Gallery | ✅ Collected | WordPress REST API; dates come from each exhibition's description. |
| Barbican | ✅ Collected | Day-by-day listing pages (`?page=N`, about six months ahead) plus each event's page for the first and last performance, hall and standard price. Showtimes load with JavaScript, so events on several days (films, runs) show as date ranges. About 6 minutes per run. |
| Prince Charles Cinema | 🔜 Planned | The whole programme is on one large page; screenings are grouped into one event per film. |
| Southbank Centre | 🔜 Planned | Listing is in the page (titles, date ranges, categories). Its WordPress API is behind a Cloudflare challenge, so it has to be the HTML. |
| Sadler's Wells | 🔜 Planned | Listing is in the page with date ranges and which theatre (Sadler's Wells, Peacock, Lilian Baylis Studio). The Peacock is in Holborn, so it may become its own venue. |
| The O2 arena | 🔜 Planned | Listing is in the page, with some schema.org event data; same site and layout as indigo, so one aggregator can serve both. |
| indigo at The O2 | 🔜 Planned | As The O2 arena. |
| Wilton's Music Hall | 🔜 Planned | Listing is in the page with dates, times and prices; WordPress also exposes a `whatson` post type. |
| Southwark Park Galleries | 🔜 Planned | WordPress REST API (exhibitions category); dates are in each post's text. |
| Troxy | ⏸️ Postponed | Cloudflare blocks the scraper's Python HTTP client by its TLS fingerprint (plain `curl` gets through). We don't work around blocks a venue has chosen; retry from the self-hosted runner or look for a feed. |
| Whitechapel Gallery | ⏸️ Postponed | Same as Troxy: the Python client gets 403 while `curl` gets the page. |
| Rich Mix | ⏸️ Postponed | Cloudflare challenge page for every client we tried. |
| EartH Hackney | ⏸️ Postponed | SiteGround captcha for every client we tried. |
| Royal Albert Hall | ⏸️ Postponed | Incapsula bot protection. |
| Southwark Playhouse | ⏸️ Postponed | SiteGround captcha. |

Postponed venues are worth retrying from the self-hosted runner (a home IP) and
checking for a ticketing-platform feed before giving up on them.

Listings are collected from each venue's public website with an identifying
User-Agent, at most one request per second per site, respecting robots.txt. Every
listing links back to the venue for details and booking.
