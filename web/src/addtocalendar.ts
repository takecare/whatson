import { dayOf, shortDate, timeOf } from "./dates";
import { showDialog } from "./dialog";
import { h } from "./dom";
import { type Slot, googleCalendarUrl, icsFileName, toICS } from "./icalendar";
import type { Venue, WhatsOnEvent } from "./types";

// iPhones and iPads add an .ics to Calendar when they open it, but only save it to
// Files when it's downloaded. iPads report themselves as Macs, hence the touch check.
const isIOS = () =>
  /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

const slotLabel = (slot: Slot) =>
  "from" in slot
    ? slot.from === slot.to
      ? shortDate(slot.from)
      : `${shortDate(slot.from)} – ${shortDate(slot.to)} (all day)`
    : `${shortDate(dayOf(slot.start))}, ${timeOf(slot.start)}`;

/** The "add to calendar" menu: Apple/Outlook (.ics) or Google Calendar. */
export function openAddToCalendar(anchor: HTMLElement, e: WhatsOnEvent, venue: Venue | undefined, slots: Slot[]): void {
  let slot = slots[0];
  const when = h("p", { class: "addcal-when" });
  const ics = h("a", { class: "addcal-option" }, "Apple Calendar / Outlook", h("small", {}, ".ics file"));
  const google = h("a", { class: "addcal-option", target: "_blank", rel: "noopener" }, "Google Calendar", h("small", {}, "opens Google"));
  const times =
    slots.length > 1
      ? h(
          "div",
          { class: "addcal-times", role: "group", "aria-label": "Showing" },
          slots.map((s) =>
            h("button", { type: "button", class: "chip chip-when", onclick: () => pick(s) }, "start" in s ? (timeOf(s.start) ?? "") : ""),
          ),
        )
      : null;
  const pick = (s: Slot) => {
    slot = s;
    when.textContent = slotLabel(s);
    const data = `data:text/calendar;charset=utf-8,${encodeURIComponent(toICS(e, venue, s))}`;
    ics.href = data;
    if (isIOS()) ics.removeAttribute("download");
    else ics.download = icsFileName(e, s);
    google.href = googleCalendarUrl(e, venue, s);
    times?.querySelectorAll("button").forEach((b, i) => b.setAttribute("aria-pressed", String(slots[i] === s)));
  };

  const dialog = h(
    "dialog",
    { class: "popover addcal", "aria-labelledby": "addcal-title" },
    h(
      "div",
      { class: "popover-head" },
      h("h2", { class: "popover-title", id: "addcal-title" }, "Add to calendar"),
      h("button", { type: "button", class: "popover-close", "aria-label": "Close" }, "×"),
    ),
    h("p", { class: "addcal-event" }, e.title),
    when,
    times,
    h("div", { class: "addcal-options" }, ics, google),
  );
  pick(slot);
  const close = showDialog(anchor, dialog);
  dialog.querySelector(".popover-close")!.addEventListener("click", () => close());
  // Close once an option has been followed (after the browser has acted on it).
  for (const option of [ics, google]) option.addEventListener("click", () => setTimeout(close, 0));
  (times?.querySelector("button") ?? ics).focus({ preventScroll: true });
}

const SVG = "http://www.w3.org/2000/svg";

/** A calendar with a plus, drawn inline so it follows the text colour. */
export function calendarIcon(): SVGSVGElement {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  for (const d of ["M4 6.5h16v13.5H4z", "M4 10.5h16", "M8.5 4v4M15.5 4v4", "M12 13v5M9.5 15.5h5"]) {
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", d);
    svg.append(path);
  }
  return svg;
}
