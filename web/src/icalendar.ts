// "Add to calendar": an .ics file (Apple Calendar, Outlook) or a Google Calendar link.

import { type Day, addDays, dayOf, isAllDay, today } from "./dates";
import type { Venue, WhatsOnEvent } from "./types";

/** What gets added: one timed showing, or an all-day span (a run, or a day without times). */
export type Slot = { start: string } | { from: Day; to: Day };

/** Showings don't say how long they last; assume this. */
const DEFAULT_HOURS = 2;

/** The slots a card can offer: that day's showings, or the rest of the run as all-day dates. */
export function slotsFor(
  e: WhatsOnEvent,
  day: Day | null,
  run: { from: Day; to: Day } | null,
  now: Day = today(),
): Slot[] {
  if (run) return [{ from: run.from > now ? run.from : now, to: run.to }];
  const starts = e.performances.length ? e.performances : [e.start];
  const timed = starts.filter((s) => !isAllDay(s) && (!day || dayOf(s) === day)).sort();
  if (timed.length) return timed.map((start) => ({ start }));
  const d = day ?? dayOf(e.start);
  return [{ from: d, to: d }];
}

/** "20261003T180000Z" */
function utcStamp(d: Date): string {
  return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}
const compactDay = (day: Day) => day.replace(/-/g, "");

/** Start and end in calendar notation: UTC times, or dates with an exclusive end. */
function bounds(e: WhatsOnEvent, slot: Slot): { allDay: boolean; start: string; end: string } {
  if ("from" in slot) return { allDay: true, start: compactDay(slot.from), end: compactDay(addDays(slot.to, 1)) };
  const start = new Date(slot.start);
  let end = new Date(start.getTime() + DEFAULT_HOURS * 3600_000);
  // A one-off event's own end time, when it has one later the same day.
  if (!e.performances.length && e.end && !isAllDay(e.end)) {
    const own = new Date(e.end);
    if (own > start && dayOf(e.end) === dayOf(slot.start)) end = own;
  }
  return { allDay: false, start: utcStamp(start), end: utcStamp(end) };
}

export function location(e: WhatsOnEvent, venue: Venue | undefined): string {
  return [venue?.name, e.space, venue?.address].filter(Boolean).join(", ");
}

function description(e: WhatsOnEvent): string {
  return [e.summary, e.url].filter(Boolean).join("\n\n");
}

/** Escapes a TEXT value (RFC 5545 §3.3.11). */
function escapeText(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

/** Folds a content line at 75 octets (RFC 5545 §3.1), without splitting characters. */
function fold(line: string): string {
  const encoder = new TextEncoder();
  const parts: string[] = [];
  let current = "";
  let size = 0;
  for (const ch of line) {
    const n = encoder.encode(ch).length;
    if (size + n > (parts.length ? 74 : 75)) {
      parts.push(current);
      current = "";
      size = 0;
    }
    current += ch;
    size += n;
  }
  parts.push(current);
  return parts.join("\r\n ");
}

export function toICS(e: WhatsOnEvent, venue: Venue | undefined, slot: Slot, now = new Date()): string {
  const b = bounds(e, slot);
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//whatson//What's On London//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${e.id}-${b.start}@whatson`,
    `DTSTAMP:${utcStamp(now)}`,
    b.allDay ? `DTSTART;VALUE=DATE:${b.start}` : `DTSTART:${b.start}`,
    b.allDay ? `DTEND;VALUE=DATE:${b.end}` : `DTEND:${b.end}`,
    `SUMMARY:${escapeText(e.title)}`,
    `LOCATION:${escapeText(location(e, venue))}`,
    `DESCRIPTION:${escapeText(description(e))}`,
    `URL:${e.url}`,
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  return `${lines.map(fold).join("\r\n")}\r\n`;
}

/** Google Calendar's "create event" page, filled in. */
export function googleCalendarUrl(e: WhatsOnEvent, venue: Venue | undefined, slot: Slot): string {
  const b = bounds(e, slot);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: e.title,
    dates: `${b.start}/${b.end}`,
    details: description(e),
    location: location(e, venue),
  });
  return `https://calendar.google.com/calendar/render?${params}`;
}

/** A file name for the .ics: "the-shining-2026-10-02.ics". */
export function icsFileName(e: WhatsOnEvent, slot: Slot): string {
  const slug = e.title.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50);
  const day = "from" in slot ? slot.from : dayOf(slot.start);
  return `${slug || "event"}-${day}.ics`;
}
