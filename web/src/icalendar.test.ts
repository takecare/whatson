import { describe, expect, it } from "vitest";
import { googleCalendarUrl, icsFileName, slotsFor, toICS } from "./icalendar";
import type { Venue, WhatsOnEvent } from "./types";

const venue: Venue = {
  id: "rio", name: "Rio Cinema", url: "", address: "107 Kingsland High Street, London E8 2PB",
  city: "London", area: "Dalston", lat: 0, lng: 0, tags: [],
};
const ev = (over: Partial<WhatsOnEvent>): WhatsOnEvent => ({
  id: "abc123", venue_id: "rio", title: "Film", url: "https://example.org/film", tags: [],
  start: "2026-10-02T18:00:00+01:00", performances: [], currency: "GBP", sold_out: false, ...over,
});
const NOW = new Date("2026-10-01T09:00:00Z");

describe("slotsFor", () => {
  it("offers that day's showings", () => {
    const e = ev({
      performances: ["2026-10-02T20:40:00+01:00", "2026-10-02T18:00:00+01:00", "2026-10-03T18:00:00+01:00"],
    });
    expect(slotsFor(e, "2026-10-02", null)).toEqual([
      { start: "2026-10-02T18:00:00+01:00" },
      { start: "2026-10-02T20:40:00+01:00" },
    ]);
  });

  it("uses all-day dates for runs and for days without a time", () => {
    const run = { from: "2026-10-01", to: "2026-10-24" };
    expect(slotsFor(ev({}), null, run, "2026-09-30")).toEqual([{ from: "2026-10-01", to: "2026-10-24" }]);
    // A run already on is added from today.
    expect(slotsFor(ev({}), null, run, "2026-10-05")).toEqual([{ from: "2026-10-05", to: "2026-10-24" }]);
    expect(slotsFor(ev({ start: "2026-10-05" }), "2026-10-05", null)).toEqual([{ from: "2026-10-05", to: "2026-10-05" }]);
  });
});

describe("toICS", () => {
  it("writes a timed event in UTC, two hours long", () => {
    const ics = toICS(ev({}), venue, { start: "2026-10-02T18:00:00+01:00" }, NOW);
    expect(ics).toContain("DTSTART:20261002T170000Z\r\n");
    expect(ics).toContain("DTEND:20261002T190000Z\r\n");
    expect(ics).toContain("UID:abc123-20261002T170000Z@whatson\r\n");
    expect(ics).toContain("LOCATION:Rio Cinema\\, 107 Kingsland High Street\\, London E8 2PB\r\n");
    expect(ics.startsWith("BEGIN:VCALENDAR\r\n") && ics.endsWith("END:VCALENDAR\r\n")).toBe(true);
  });

  it("uses a one-off event's own end time", () => {
    const e = ev({ end: "2026-10-02T22:30:00+01:00" });
    expect(toICS(e, venue, { start: e.start }, NOW)).toContain("DTEND:20261002T213000Z");
  });

  it("writes all-day dates with an exclusive end", () => {
    const ics = toICS(ev({}), venue, { from: "2026-10-01", to: "2026-10-24" }, NOW);
    expect(ics).toContain("DTSTART;VALUE=DATE:20261001\r\n");
    expect(ics).toContain("DTEND;VALUE=DATE:20261025\r\n");
  });

  it("escapes text and folds long lines", () => {
    const e = ev({ title: "Rock; Roll, and \\ more", summary: "Line one\nline two ".repeat(10) + "é".repeat(40) });
    const ics = toICS(e, venue, { start: e.start }, NOW);
    expect(ics).toContain("SUMMARY:Rock\\; Roll\\, and \\\\ more");
    expect(ics).toContain("Line one\\nline two");
    for (const line of ics.split("\r\n")) expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
  });
});

describe("googleCalendarUrl", () => {
  it("fills in Google's create-event page", () => {
    const url = new URL(googleCalendarUrl(ev({}), venue, { start: "2026-10-02T18:00:00+01:00" }));
    expect(url.origin + url.pathname).toBe("https://calendar.google.com/calendar/render");
    expect(url.searchParams.get("action")).toBe("TEMPLATE");
    expect(url.searchParams.get("dates")).toBe("20261002T170000Z/20261002T190000Z");
    expect(url.searchParams.get("location")).toContain("Rio Cinema");
    const allDay = new URL(googleCalendarUrl(ev({}), venue, { from: "2026-10-01", to: "2026-10-01" }));
    expect(allDay.searchParams.get("dates")).toBe("20261001/20261002");
  });
});

it("names the file after the event and day", () => {
  expect(icsFileName(ev({ title: "The Shining [UK Version]!" }), { start: "2026-10-02T18:00:00+01:00" })).toBe(
    "the-shining-uk-version-2026-10-02.ics",
  );
});
