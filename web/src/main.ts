import { openCalendar } from "./calendar";
import { type Day, addDays, dayHeading, today } from "./dates";
import { DEFAULT_FILTERS, type Filters, applyFilters, filtersFromQuery, filtersToQuery } from "./filters";
import { setUpAddToHome } from "./install";
import { activeCount, buildPanel } from "./panel";
import { type ResultsView, renderResults, renderSources } from "./render";
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
  let view: ResultsView = { jumpTo: () => null, days: () => [] };
  const render = () => {
    const results = applyFilters(data.events, data.venues, filters, today());
    view = renderResults(main, results, data, today(), () => setFilters({ ...DEFAULT_FILTERS }));
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

  setUpJump(() => view, today);

  panel.sync();
  render();
  renderSources($("sources"), $("sources-count"), $("updated"), data);
}

/** The Today / Tomorrow / Choose buttons: scroll to a day in the current results. */
function setUpJump(view: () => ResultsView, now: () => Day) {
  const note = $("jump-note");
  let hideNote: number | undefined;
  const say = (text: string) => {
    clearTimeout(hideNote);
    note.textContent = text;
    note.hidden = !text;
    if (text) hideNote = window.setTimeout(() => (note.hidden = true), 4000);
  };
  const jump = (day: Day) => {
    const shown = view().jumpTo(day);
    // "today", "tomorrow" or "Saturday 3 October"
    const name = (d: Day) => dayHeading(d, now()).replace(/^(Today|Tomorrow)$/, (w) => w.toLowerCase());
    if (shown === null) say(`No events from ${name(day)} onwards with these filters.`);
    else if (shown !== day) say(`Nothing on ${name(day)}. Showing ${name(shown)}.`);
    else say("");
  };
  for (const button of document.querySelectorAll<HTMLButtonElement>("[data-jump]")) {
    button.addEventListener("click", () => jump(button.dataset.jump === "tomorrow" ? addDays(now(), 1) : now()));
  }
  const choose = $<HTMLButtonElement>("jump-choose");
  choose.addEventListener("click", () => openCalendar(choose, now(), new Set(view().days()), jump));
}

setUpAddToHome($<HTMLButtonElement>("add-to-home"));
void start();
