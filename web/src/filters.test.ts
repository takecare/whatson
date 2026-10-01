import { describe, expect, it } from "vitest";
import { dayOf, presetRange, timeOf } from "./dates";
import { DEFAULT_FILTERS, type Filters, applyFilters, filtersFromQuery, filtersToQuery } from "./filters";
import type { Venue, WhatsOnEvent } from "./types";

const NOW = "2026-09-29"; // a Tuesday

const venue = (id: string, area: string, tags: string[]): Venue => ({
  id, name: id, url: "", address: "", city: "London", area, lat: 0, lng: 0, tags,
});
const VENUES = new Map([
  ["comedy", venue("comedy", "Covent Garden", ["Comedy"])],
  ["gallery", venue("gallery", "Chelsea", ["Art", "Exhibition"])],
  ["cinema", venue("cinema", "Soho", ["Film"])],
]);

const ev = (over: Partial<WhatsOnEvent>): WhatsOnEvent => ({
  id: over.title ?? "x", venue_id: "comedy", title: "x", url: "", tags: [], start: NOW,
  performances: [], currency: "GBP", sold_out: false, ...over,
});

const EVENTS = [
  ev({ title: "Late show", start: "2026-09-29T21:00:00+01:00", tags: ["Comedy"], price_min: 15 }),
  ev({ title: "Early show", start: "2026-09-29T18:00:00+01:00", tags: ["Comedy"], price_min: 1, sold_out: true }),
  ev({ title: "Next week", start: "2026-10-06T20:00:00+01:00", tags: ["Comedy"], price_min: 0 }),
  ev({ title: "Big exhibition", venue_id: "gallery", start: "2026-11-11", end: "2027-05-05", tags: [] }),
  ev({
    title: "Film", venue_id: "cinema", start: "2026-10-02T14:00:00+01:00", tags: ["Film"], price_min: 12,
    performances: ["2026-10-02T21:00:00+01:00", "2026-10-02T14:00:00+01:00", "2026-10-03T18:00:00+01:00"],
  }),
];

const run = (over: Partial<Filters> = {}) => applyFilters(EVENTS, VENUES, { ...DEFAULT_FILTERS, ...over }, NOW);
const titles = (r: ReturnType<typeof run>) => [
  ...r.days.flatMap((d) => d.items.map((i) => i.event.title)),
  ...r.runs.map((x) => x.event.title),
];

describe("dates", () => {
  it("uses London time", () => {
    expect(dayOf("2026-09-29T23:30:00Z")).toBe("2026-09-30"); // 00:30 BST
    expect(timeOf("2026-12-01T19:30:00Z")).toBe("19:30"); // GMT
    expect(timeOf("2026-12-01")).toBeNull();
  });

  it("computes the weekend", () => {
    expect(presetRange("weekend", "2026-09-29")).toEqual(["2026-10-02", "2026-10-04"]); // Tue
    expect(presetRange("weekend", "2026-10-03")).toEqual(["2026-10-03", "2026-10-04"]); // Sat
    expect(presetRange("weekend", "2026-10-04")).toEqual(["2026-10-04", "2026-10-04"]); // Sun
  });
});

describe("applyFilters", () => {
  it("groups by day, sorted by time, and lists runs separately", () => {
    const r = run();
    expect(r.days.map((d) => d.day)).toEqual(["2026-09-29", "2026-10-02", "2026-10-03", "2026-10-06"]);
    expect(r.days[0].items.map((i) => i.event.title)).toEqual(["Early show", "Late show"]);
    expect(r.days[1].items[0].times).toEqual(["14:00", "21:00"]);
    expect(r.runs.map((x) => x.event.title)).toEqual(["Big exhibition"]);
    expect(r.count).toBe(5);
  });

  it("filters by date range, including runs that overlap it", () => {
    expect(titles(run({ when: "today" }))).toEqual(["Early show", "Late show"]);
    expect(titles(run({ when: "weekend" }))).toEqual(["Film", "Film"]);
    expect(titles(run({ when: "custom", from: "2026-12-01", to: "2026-12-02" }))).toEqual(["Big exhibition"]);
  });

  it("filters by tags, falling back to venue tags", () => {
    expect(titles(run({ tags: ["Exhibition"] }))).toEqual(["Big exhibition"]);
    expect(titles(run({ tags: ["Film", "Exhibition"] })).sort()).toEqual(["Big exhibition", "Film", "Film"]);
    expect(titles(run({ tags: ["Film", "Exhibition"], tagMode: "all" }))).toEqual([]);
  });

  it("filters by price", () => {
    expect(titles(run({ freeOnly: true }))).toEqual(["Next week"]);
    expect(titles(run({ maxPrice: 10, includeUnknownPrice: false }))).toEqual(["Early show", "Next week"]);
    expect(titles(run({ maxPrice: 10 }))).toContain("Big exhibition");
  });

  it("filters by sold out, area, venue and text", () => {
    expect(titles(run({ hideSoldOut: true, when: "today" }))).toEqual(["Late show"]);
    expect(titles(run({ areas: ["Chelsea"] }))).toEqual(["Big exhibition"]);
    expect(titles(run({ venues: ["cinema"] }))).toEqual(["Film", "Film"]);
    expect(titles(run({ q: "late SHOW" }))).toEqual(["Late show"]);
    expect(titles(run({ q: "soho" }))).toEqual(["Film", "Film"]);
  });
});

describe("exclusions", () => {
  it("leaves out excluded tags, using venue tags as a fallback", () => {
    expect(titles(run({ excludeTags: ["Comedy"] })).sort()).toEqual(["Big exhibition", "Film", "Film"]);
    expect(titles(run({ excludeTags: ["Art"] }))).not.toContain("Big exhibition"); // a venue tag
  });

  it("combines with included tags", () => {
    expect(titles(run({ tags: ["Comedy", "Film"], excludeTags: ["Film"] })).sort()).toEqual([
      "Early show", "Late show", "Next week",
    ]);
  });

  it("leaves out excluded venues and areas", () => {
    expect(titles(run({ excludeVenues: ["comedy", "cinema"] }))).toEqual(["Big exhibition"]);
    expect(titles(run({ excludeAreas: ["Covent Garden", "Chelsea"] }))).toEqual(["Film", "Film"]);
  });
});

describe("URL state", () => {
  it("writes exclusions with a leading minus", () => {
    const f: Filters = { ...DEFAULT_FILTERS, tags: ["Theatre"], excludeTags: ["Comedy"], excludeVenues: ["o2arena"] };
    expect(decodeURIComponent(filtersToQuery(f))).toBe("?tags=Theatre,-Comedy&venue=-o2arena");
    expect(filtersFromQuery(filtersToQuery(f))).toEqual(f);
    expect(filtersFromQuery("?area=-Soho,-").excludeAreas).toEqual(["Soho"]);
  });


  it("round-trips", () => {
    const f: Filters = {
      ...DEFAULT_FILTERS, q: "jazz", when: "custom", from: "2026-10-01", to: "2026-10-05",
      tags: ["Music", "Jazz"], tagMode: "all", maxPrice: 20, hideSoldOut: true, areas: ["Soho"],
    };
    expect(filtersFromQuery(filtersToQuery(f))).toEqual(f);
    expect(filtersToQuery(DEFAULT_FILTERS)).toBe("");
    expect(filtersFromQuery("?when=weekend").when).toBe("weekend");
    expect(filtersFromQuery("?max=abc").maxPrice).toBeNull();
  });
});
