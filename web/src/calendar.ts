import { type Day, addDays, weekday } from "./dates";
import { showDialog } from "./dialog";
import { h } from "./dom";

const monthTitle = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const dayLabel = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const asDate = (day: Day) => new Date(`${day}T12:00:00Z`);
/** "2026-10" of a day. */
const monthOf = (day: Day) => day.slice(0, 7);
/** The first day of the month `n` months after `month` ("2026-10"). */
function shiftMonth(month: string, n: number): Day {
  const d = new Date(`${month}-01T12:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + n);
  return d.toISOString().slice(0, 10);
}

/** The days of a month as a Monday-first grid, with nulls before the 1st. */
export function monthGrid(month: string): (Day | null)[] {
  const first = `${month}-01`;
  const cells: (Day | null)[] = Array((weekday(first) + 6) % 7).fill(null);
  for (let d = first; monthOf(d) === month; d = addDays(d, 1)) cells.push(d);
  return cells;
}

/**
 * A month calendar in a modal dialog, our own rather than the browser's date input,
 * whose pickers behave differently on every phone. Only days in `days` (the days
 * with events) can be picked.
 */
export function openCalendar(anchor: HTMLElement, now: Day, days: Set<Day>, onPick: (day: Day) => void): void {
  const sorted = [...days].filter((d) => d >= now).sort();
  const firstMonth = monthOf(sorted[0] ?? now);
  const lastMonth = monthOf(sorted[sorted.length - 1] ?? now);
  let month = firstMonth;

  const title = h("h2", { class: "calendar-title", id: "calendar-title" });
  const prev = h("button", { type: "button", class: "calendar-nav", "aria-label": "Previous month" }, "‹");
  const next = h("button", { type: "button", class: "calendar-nav", "aria-label": "Next month" }, "›");
  const grid = h("div", { class: "calendar-grid", role: "group", "aria-labelledby": "calendar-title" });
  const dialog = h(
    "dialog",
    { class: "popover calendar", "aria-labelledby": "calendar-title" },
    h(
      "div",
      { class: "calendar-head" },
      prev,
      title,
      next,
      h("button", { type: "button", class: "calendar-close", "aria-label": "Close" }, "×"),
    ),
    h("div", { class: "calendar-weekdays", "aria-hidden": "true" }, WEEKDAYS.map((w) => h("span", {}, w))),
    grid,
    h("p", { class: "calendar-note" }, sorted.length ? "Days with events are in bold." : "No upcoming events with these filters."),
  );

  const show = () => {
    title.textContent = monthTitle.format(asDate(`${month}-01`));
    prev.disabled = month <= firstMonth;
    next.disabled = month >= lastMonth;
    grid.replaceChildren(
      ...monthGrid(month).map((day) => {
        if (!day) return h("span", {});
        const has = days.has(day) && day >= now;
        return h(
          "button",
          {
            type: "button",
            class: `calendar-day${has ? " has-events" : ""}${day === now ? " is-today" : ""}`,
            "data-day": day,
            "aria-label": dayLabel.format(asDate(day)) + (has ? "" : ", no events"),
            disabled: !has,
          },
          String(Number(day.slice(8))),
        );
      }),
    );
  };
  prev.addEventListener("click", () => {
    month = monthOf(shiftMonth(month, -1));
    show();
  });
  next.addEventListener("click", () => {
    month = monthOf(shiftMonth(month, 1));
    show();
  });
  dialog.querySelector(".calendar-close")!.addEventListener("click", () => close());
  grid.addEventListener("click", (ev) => {
    const day = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-day]")?.dataset.day;
    if (!day) return;
    close();
    onPick(day);
  });

  show();
  const close = showDialog(anchor, dialog);
  // Focus the first pickable day without scrolling the page.
  dialog.querySelector<HTMLButtonElement>(".calendar-day:not(:disabled)")?.focus({ preventScroll: true });
}
