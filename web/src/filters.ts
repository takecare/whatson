import { type Day, type Preset, PRESETS, dayOf, presetRange, timeOf } from "./dates";
import type { Venue, WhatsOnEvent } from "./types";

export interface Filters {
  q: string;
  /** A preset date range, or "custom" to use from/to. */
  when: Preset | "custom";
  from: Day | null;
  to: Day | null;
  tags: string[];
  tagMode: "any" | "all";
  /** Upper bound on the cheapest ticket; null means no limit. */
  maxPrice: number | null;
  freeOnly: boolean;
  includeUnknownPrice: boolean;
  hideSoldOut: boolean;
  areas: string[];
  venues: string[];
}

export const DEFAULT_FILTERS: Filters = {
  q: "",
  when: "all",
  from: null,
  to: null,
  tags: [],
  tagMode: "any",
  maxPrice: null,
  freeOnly: false,
  includeUnknownPrice: true,
  hideSoldOut: false,
  areas: [],
  venues: [],
};

/** An event on one particular day, with that day's showtimes. */
export interface Occurrence {
  kind: "day";
  day: Day;
  times: string[];
  event: WhatsOnEvent;
}

/** An event running over several days (exhibition, theatre run). */
export interface Run {
  kind: "run";
  from: Day;
  to: Day;
  event: WhatsOnEvent;
}

export interface Results {
  days: { day: Day; items: Occurrence[] }[];
  runs: Run[];
  /** Number of distinct events matched. */
  count: number;
}

export function dateRange(f: Filters, now: Day): [Day, Day | null] {
  if (f.when !== "custom") return presetRange(f.when, now);
  const from = f.from && f.from > now ? f.from : now;
  return [from, f.to];
}

/** Tags used for filtering: the event's own, or the venue's when it has none. */
export function effectiveTags(e: WhatsOnEvent, venue: Venue | undefined): string[] {
  return e.tags.length ? e.tags : (venue?.tags ?? []);
}

function matchesNonDate(e: WhatsOnEvent, venue: Venue | undefined, f: Filters): boolean {
  if (f.hideSoldOut && e.sold_out) return false;
  if (f.venues.length && !f.venues.includes(e.venue_id)) return false;
  if (f.areas.length && !(venue?.area && f.areas.includes(venue.area))) return false;

  if (f.tags.length) {
    const tags = effectiveTags(e, venue);
    const hit = f.tagMode === "all" ? f.tags.every((t) => tags.includes(t)) : f.tags.some((t) => tags.includes(t));
    if (!hit) return false;
  }

  if (e.price_min === undefined || e.price_min === null) {
    if (!f.includeUnknownPrice || f.freeOnly) return false;
  } else {
    if (f.freeOnly && e.price_min !== 0) return false;
    if (f.maxPrice !== null && e.price_min > f.maxPrice) return false;
  }

  if (f.q.trim()) {
    const haystack = [e.title, e.summary, e.space, venue?.name, venue?.area, ...e.tags]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (!f.q.toLowerCase().trim().split(/\s+/).every((w) => haystack.includes(w))) return false;
  }
  return true;
}

export function applyFilters(
  events: WhatsOnEvent[],
  venues: Map<string, Venue>,
  f: Filters,
  now: Day,
): Results {
  const [from, to] = dateRange(f, now);
  const inRange = (d: Day) => d >= from && (to === null || d <= to);
  const byDay = new Map<Day, Occurrence[]>();
  const runs: Run[] = [];
  const matched = new Set<string>();

  for (const e of events) {
    const venue = venues.get(e.venue_id);
    if (!matchesNonDate(e, venue, f)) continue;

    if (e.performances.length) {
      const times = new Map<Day, string[]>();
      for (const p of e.performances) {
        const d = dayOf(p);
        if (!inRange(d)) continue;
        const list = times.get(d) ?? [];
        const t = timeOf(p);
        if (t) list.push(t);
        times.set(d, list);
      }
      for (const [d, ts] of times) {
        push(byDay, d, { kind: "day", day: d, times: ts.sort(), event: e });
        matched.add(e.id);
      }
      continue;
    }

    const start = dayOf(e.start);
    const end = e.end ? dayOf(e.end) : start;
    if (end > start) {
      if (start <= (to ?? end) && end >= from) {
        runs.push({ kind: "run", from: start, to: end, event: e });
        matched.add(e.id);
      }
    } else if (inRange(start)) {
      const t = timeOf(e.start);
      push(byDay, start, { kind: "day", day: start, times: t ? [t] : [], event: e });
      matched.add(e.id);
    }
  }

  const days = [...byDay.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([day, items]) => ({
      day,
      items: items.sort((a, b) => (a.times[0] ?? "99").localeCompare(b.times[0] ?? "99") || a.event.title.localeCompare(b.event.title)),
    }));
  runs.sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to));
  return { days, runs, count: matched.size };
}

function push<K, V>(map: Map<K, V[]>, key: K, value: V) {
  const list = map.get(key);
  if (list) list.push(value);
  else map.set(key, [value]);
}

// URL state ---------------------------------------------------------------------

const PRESET_IDS = new Set<string>(PRESETS.map((p) => p.id));

export function filtersFromQuery(search: string): Filters {
  const p = new URLSearchParams(search);
  const list = (key: string) => (p.get(key) ? p.get(key)!.split(",").filter(Boolean) : []);
  const day = (key: string) => (/^\d{4}-\d{2}-\d{2}$/.test(p.get(key) ?? "") ? p.get(key) : null);
  const when = p.get("when") ?? "";
  const from = day("from");
  const to = day("to");
  const max = Number(p.get("max"));
  return {
    q: p.get("q") ?? "",
    when: PRESET_IDS.has(when) ? (when as Preset) : from || to ? "custom" : "all",
    from,
    to,
    tags: list("tags"),
    tagMode: p.get("mode") === "all" ? "all" : "any",
    maxPrice: p.has("max") && Number.isFinite(max) && max >= 0 ? max : null,
    freeOnly: p.get("free") === "1",
    includeUnknownPrice: p.get("unknown") !== "0",
    hideSoldOut: p.get("soldout") === "0",
    areas: list("area"),
    venues: list("venue"),
  };
}

export function filtersToQuery(f: Filters): string {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.when === "custom") {
    if (f.from) p.set("from", f.from);
    if (f.to) p.set("to", f.to);
  } else if (f.when !== "all") {
    p.set("when", f.when);
  }
  if (f.tags.length) p.set("tags", f.tags.join(","));
  if (f.tagMode === "all") p.set("mode", "all");
  if (f.maxPrice !== null) p.set("max", String(f.maxPrice));
  if (f.freeOnly) p.set("free", "1");
  if (!f.includeUnknownPrice) p.set("unknown", "0");
  if (f.hideSoldOut) p.set("soldout", "0");
  if (f.areas.length) p.set("area", f.areas.join(","));
  if (f.venues.length) p.set("venue", f.venues.join(","));
  const s = p.toString();
  return s ? `?${s}` : "";
}
