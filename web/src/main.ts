import { today } from "./dates";
import { DEFAULT_FILTERS, type Filters, applyFilters, filtersFromQuery, filtersToQuery } from "./filters";
import { activeCount, buildPanel } from "./panel";
import { renderResults, renderSources } from "./render";
import type { Data, SourceStatus, Venue, WhatsOnEvent } from "./types";

async function getJson<T>(name: string): Promise<T | null> {
  try {
    const res = await fetch(`./data/${name}`, { cache: "no-cache" });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

async function loadData(): Promise<Data | null> {
  const [events, venues, status] = await Promise.all([
    getJson<{ generated_at: string; events: WhatsOnEvent[] }>("events.json"),
    getJson<{ venues: Venue[] }>("venues.json"),
    getJson<{ sources: SourceStatus[] }>("status.json"),
  ]);
  if (!events || !venues) return null;
  return {
    generatedAt: events.generated_at,
    events: events.events,
    venues: new Map(venues.venues.map((v) => [v.id, v])),
    sources: status?.sources ?? [],
  };
}

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

async function start() {
  const main = $("results");
  const data = await loadData();
  if (!data) {
    main.innerHTML = "";
    main.append(Object.assign(document.createElement("p"), {
      className: "empty",
      textContent: "No listings yet. They appear after the first scheduled collection run.",
    }));
    return;
  }

  let filters: Filters = filtersFromQuery(location.search);
  const search = $<HTMLInputElement>("q");
  const badge = $("filter-count");
  const aside = $("filters");
  const openButton = $("open-filters");

  const closeButton = $("close-filters");
  const render = () => {
    const results = applyFilters(data.events, data.venues, filters, today());
    renderResults(main, results, data, today(), () => setFilters({ ...DEFAULT_FILTERS }));
    closeButton.textContent = `Show ${results.count} ${results.count === 1 ? "event" : "events"}`;
    const n = activeCount(filters);
    badge.hidden = n === 0;
    badge.textContent = String(n);
  };

  const setFilters = (f: Filters) => {
    filters = f;
    history.replaceState(null, "", location.pathname + filtersToQuery(f) + location.hash);
    if (search.value !== f.q) search.value = f.q;
    panel.sync();
    render();
  };

  const panel = buildPanel($("filter-controls"), data, today, () => filters, setFilters);

  let debounce: number | undefined;
  search.value = filters.q;
  search.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = window.setTimeout(() => setFilters({ ...filters, q: search.value }), 150);
  });

  const setOpen = (open: boolean) => {
    aside.classList.toggle("is-open", open);
    document.body.classList.toggle("has-sheet", open);
    openButton.setAttribute("aria-expanded", String(open));
  };
  openButton.addEventListener("click", () => setOpen(true));
  closeButton.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (e) => e.key === "Escape" && setOpen(false));

  panel.sync();
  render();
  renderSources($("sources"), $("updated"), data);
}

void start();
