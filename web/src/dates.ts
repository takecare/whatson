// Every date on the site is shown in London time, whatever the viewer's timezone.

const TZ = "Europe/London";

const dayFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});
const timeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ,
  hour: "2-digit",
  minute: "2-digit",
});

/** A day as "YYYY-MM-DD". Strings compare correctly with < and >. */
export type Day = string;

export function isAllDay(iso: string): boolean {
  return iso.length === 10;
}

/** The London calendar day of an ISO date or datetime. */
export function dayOf(iso: string | Date): Day {
  if (typeof iso === "string" && isAllDay(iso)) return iso;
  return dayFormat.format(typeof iso === "string" ? new Date(iso) : iso);
}

/** "19:30" in London time, or null for all-day dates. */
export function timeOf(iso: string): string | null {
  return isAllDay(iso) ? null : timeFormat.format(new Date(iso));
}

export function today(now: Date = new Date()): Day {
  return dayOf(now);
}

export function addDays(day: Day, n: number): Day {
  const d = new Date(`${day}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

/** 0 = Sunday … 6 = Saturday. */
export function weekday(day: Day): number {
  return new Date(`${day}T12:00:00Z`).getUTCDay();
}

export type Preset = "today" | "tomorrow" | "weekend" | "week" | "month" | "all";

export const PRESETS: { id: Preset; label: string }[] = [
  { id: "all", label: "All upcoming" },
  { id: "today", label: "Today" },
  { id: "tomorrow", label: "Tomorrow" },
  { id: "weekend", label: "This weekend" },
  { id: "week", label: "Next 7 days" },
  { id: "month", label: "Next 30 days" },
];

/** The [from, to] days a preset covers; `to` is null for "all upcoming". */
export function presetRange(preset: Preset, now: Day): [Day, Day | null] {
  switch (preset) {
    case "today":
      return [now, now];
    case "tomorrow":
      return [addDays(now, 1), addDays(now, 1)];
    case "weekend": {
      const wd = weekday(now);
      if (wd === 0) return [now, now]; // Sunday: just today
      const friday = wd === 6 ? addDays(now, -1) : addDays(now, 5 - wd);
      const from = friday < now ? now : friday;
      return [from, addDays(friday, 2)];
    }
    case "week":
      return [now, addDays(now, 6)];
    case "month":
      return [now, addDays(now, 29)];
    case "all":
      return [now, null];
  }
}

const longDay = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "UTC",
});
const shortDay = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** "Today", "Tomorrow" or "Saturday 3 October". */
export function dayHeading(day: Day, now: Day): string {
  if (day === now) return "Today";
  if (day === addDays(now, 1)) return "Tomorrow";
  return longDay.format(new Date(`${day}T12:00:00Z`));
}

/** "3 Oct 2026". */
export function shortDate(day: Day): string {
  return shortDay.format(new Date(`${day}T12:00:00Z`));
}
