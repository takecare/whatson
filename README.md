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
  can be shared. It's installable on phones ("Add to home": a web app manifest and
  a network-first service worker, so the last listings also open offline).
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
| `SCRAPE_INTERVAL_HOURS` | `12` | Hours between scrapes (12: twice a day). The workflow checks hourly and scrapes once this much time has passed since the last scrape. `0` pauses scheduled scraping. |
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
| Prince Charles Cinema | ✅ Collected | The whole programme is one page: each film with its showtimes by day, so one event per film with every showing. Format tags (35mm, 70mm, sing-along) go in the summary. Prices aren't listed. |
| The O2 arena | ✅ Collected | The O2's RSS feed (`/events/rss`) gives every event with start/end times and type, in one request; the listing pages (plus their "load more" endpoint) add images, taglines and ticket links. Events on several nights show as date ranges. The site rate-limits (HTTP 406), so requests are spaced 3 s apart. |
| indigo at The O2 | ✅ Collected | Same aggregator as The O2 arena. |
| Wilton's Music Hall | ✅ Collected | Listing pages (`?event-page=N`; the theme's `/page/N/` links repeat page one) give dates, time, availability, and, in HTML comments, full-price range and genre. Runs show as date ranges. |
| Southbank Centre | ✅ Collected (nearly all) | Only the first page of any listing is open; page 2 onwards (and the WordPress API) sit behind a Cloudflare challenge, which we don't get around. So it reads the first page of each art-form filter plus one page per day for 90 days. A page holds 12 events: in a check on 29 Sep 2026 only 2 of 90 days (both Saturdays) had more, so a few events on the busiest days can be missing. Paid prices aren't shown; free events are marked. |
| Sadler's Wells | ✅ Collected | One listing (`/whats-on/page/N/`) covers all their stages; each card names its stage. This venue is the Clerkenwell building (Sadler's Wells Theatre and Lilian Baylis Studio as spaces). Dates or runs only: no times or prices on the cards. Events are tagged Dance via the venue. |
| Peacock Theatre | ✅ Collected | Sadler's Wells' Holborn stage, from the same listing. |
| Sadler's Wells East | ✅ Collected | Sadler's Wells' Stratford stage, from the same listing. |
| Southwark Park Galleries | ✅ Collected | WordPress REST API lists what's on through its "Current" and "Upcoming" categories; each post's page gives dates (or, for workshop series, the title line; for talks, the time line), and which gallery. |
| English National Ballet | ✅ Collected (London only) | A touring company: its What's On page lists productions with where they play. Only London dates are kept, with the theatre as the space; productions at venues we already collect (e.g. Sadler's Wells) are skipped to avoid duplicates. |
| Trinity Buoy Wharf | ✅ Collected | Server-rendered list; its category pages (art & design, music, events, history) give the tags. Permanent works marked "Open year round" aren't events and are skipped. |
| Cafe OTO | ✅ Collected | Server-rendered listing, paged by following its own next-page link (`?page=N`; past the end it answers 404). Cards give date and time, door/advance/DICE prices (members' prices ignored) and sold-out state. |
| Arcola Theatre | ✅ Collected | Server-rendered list of shows with run, studio and blurb (the "all shows" view is the same list, filtered in the browser). No times or prices on the listing. |
| Rio Cinema | ✅ Collected | The What's On page (Savoy's Rio.dll ticketing) embeds the programme as JSON: films with every showtime, screen, sold-out and accessibility flags (relaxed, captioned). One event per film. No prices. |
| Signature Brew Haggerston | ✅ Collected | One Webflow page lists both taprooms' events with date, time and Tixr link. Its category field is almost always empty, so quiz, football screenings and comedy are recognised from the title; everything else is tagged Music. Addresses approximate. |
| Signature Brew Blackhorse Road | ✅ Collected | Same page and aggregator as Haggerston. |
| SJQ | ✅ Collected | The programme page shows an Elfsight calendar widget; we read the JSON the widget itself loads (Elfsight's public boot endpoint): name, date and time, image, ticket link. Club nights running past midnight are tagged Nightlife. |
| The Courtyard Theatre | ✅ Collected | WordPress page of cards (`?event_page=N`) with title, date and time, image and See Tickets link. No categories or prices, so events are tagged Theatre via the venue. |
| ExCeL London | ✅ Collected (consumer events only) | Most of ExCeL's calendar is trade and B2B shows, which are left out. Its consumer/trade filter goes through `/ajax/` (disallowed by robots.txt) and event pages don't state their type, so each event's title and intro are scored for trade wording (professionals, industry, expo…) against consumer wording (families, fans, tickets…). A heuristic: borderline shows can land on either side. |
| The Old Vic | ✅ Collected | The stage listing is a few poster cards (title and access icons); each show's page gives its run, ticket prices (lowest to highest across off-peak and peak) and booking link. No performance times. |
| The Lexington | ✅ Collected | One page lists every gig and club night with date and time (no year; inferred), image and ticket link; each event's page adds the price line and description (about 90 pages, 1.5 minutes). Club nights are tagged Nightlife, the weekly quiz Nightlife only. |
| Genesis Cinema | ✅ Collected (events only) | Its events page (Q&As, double bills, poetry slams) lists each event with its performances: date, time, booking link. The regular film programme (`/whatson/all`) isn't collected. No prices. |
| The Yard Theatre | ✅ Collected | A Next.js site: the What's On page's embedded data lists each show with category, run (ISO start and end) and performance times ("2:30pm & 7:00pm", kept in the summary). Single performances keep their time; runs show as dates. No prices. |
| The Space | ✅ Collected | WordPress listing of cards: title, dates ("1 Oct - 4 Oct"), blurb, image. The site's own categories only say "In Person" or "Online", so comedy, music, club nights and screenings are recognised from the title and blurb; the rest is tagged Theatre. No times or prices (booking is embedded). |
| Stratford East | ✅ Collected | The listing links to each show's page, which lists every performance with time, price range and access notes (BSL, captioned, audio described, relaxed). Genres only appear on the pages' "You may also like" cards, so they're gathered across the show pages. The free bar nights are lines of text on their own page and are listed too (Nightlife). |
| Theatreship | ✅ Collected | The page's script fills in What's On from a public Firestore document; we read that document through Firestore's REST API: title, date and time, description, image and Eventbrite/DICE links. No categories, so screenings are recognised from the text (Film) and the rest is tagged Music; events titled "free" are marked free. |
| Hackney Empire | ✅ Collected | Listing pages (`/whats-on/page-N`; the last page's "next" wraps round to page 1) give title, start time, image and link; runs show as dates. Cards carry no category, so the seven category pages (theatre, comedy, live music, opera, talks, family, dance) are read for tags: 9 requests. Prices are only in the event pages' text and aren't collected. |
| King's Head Theatre | ✅ Collected | The listing gives each show's run, genres and stage (Main House, 4Below); each show's page has a JSON-LD Event per performance, so every performance time is listed. Prices are banded and only described in text, so they aren't collected. |
| Almeida Theatre | ✅ Collected | One listing page of cards: title, run, sold-out state and artwork. Show pages describe prices and access performances only in text, so runs are shown as dates, without times or prices. |
| Young Vic | ✅ Collected | One listing page of cards: title, run, space (Main House, The Maria) and image. NT at Home streams and productions staged elsewhere are skipped. No times or prices on the listing. |
| Union Theatre | ✅ Collected | WordPress listing of show thumbnails: title, dates, image and Savoy booking link. No times or prices. |
| Troxy | ⏸️ Postponed | Cloudflare blocks the scraper's Python HTTP client by its TLS fingerprint (plain `curl` gets through). We don't work around blocks a venue has chosen; retry from the self-hosted runner or look for a feed. |
| Whitechapel Gallery | ⏸️ Postponed | Same as Troxy: the Python client gets 403 while `curl` gets the page. |
| Rich Mix | ⏸️ Postponed | Cloudflare challenge page for every client we tried. |
| EartH Hackney | ⏸️ Postponed | SiteGround captcha for every client we tried. |
| Royal Albert Hall | ⏸️ Postponed | Incapsula bot protection. |
| Southwark Playhouse | ⏸️ Postponed | SiteGround captcha. |
| ATG Tickets (London & West End) | ⏸️ Skipped for now | A ticket seller covering many theatres rather than a venue. Its robots.txt allows `/whats-on/london-west-end/` but blocks AI crawlers site-wide, and the page as linked (`london,london-west-end`) is disallowed. |

Postponed venues are worth retrying from the self-hosted runner (a home IP) and
checking for a ticketing-platform feed before giving up on them.

Listings are collected from each venue's public website with an identifying
User-Agent, at most one request per second per site, respecting robots.txt. Every
listing links back to the venue for details and booking.
