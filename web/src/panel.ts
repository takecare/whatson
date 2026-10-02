import { type Day, PRESETS } from "./dates";
import { h } from "./dom";
import { DEFAULT_FILTERS, type Filters, type WhenPreset, effectiveTags, isCustom } from "./filters";
import type { Data } from "./types";

const PRICE_STEPS = [5, 10, 15, 20, 30, 40, 50, 75, 100];

/** Builds the filter controls once; `sync` pushes a Filters value back into them. */
export function buildPanel(
  container: HTMLElement,
  data: Data,
  now: () => Day,
  get: () => Filters,
  set: (f: Filters) => void,
): { sync: () => void } {
  const update = (patch: Partial<Filters>) => set({ ...get(), ...patch });
  const without = <T>(list: T[], value: T) => list.filter((v) => v !== value);
  // Each tag, area and venue cycles: off → included → excluded → off.
  const cycle = (key: "tags" | "areas" | "venues", value: string) => {
    const excludeKey = EXCLUDE[key];
    const f = get();
    const included = f[key];
    const excluded = f[excludeKey];
    if (included.includes(value)) {
      update({ [key]: without(included, value), [excludeKey]: [...excluded, value] });
    } else if (excluded.includes(value)) {
      update({ [excludeKey]: without(excluded, value) });
    } else {
      update({ [key]: [...included, value] });
    }
  };
  const stateOf = (key: "tags" | "areas" | "venues", value: string): State => {
    const f = get();
    return f[key].includes(value) ? "included" : f[EXCLUDE[key]].includes(value) ? "excluded" : "off";
  };

  // Counts per tag, area and venue across all upcoming events.
  const tagCounts = new Map<string, number>();
  const venueCounts = new Map<string, number>();
  for (const e of data.events) {
    for (const t of effectiveTags(e, data.venues.get(e.venue_id))) tagCounts.set(t, (tagCounts.get(t) ?? 0) + 1);
    venueCounts.set(e.venue_id, (venueCounts.get(e.venue_id) ?? 0) + 1);
  }
  const areaCounts = new Map<string, number>();
  for (const v of data.venues.values()) {
    if (v.area) areaCounts.set(v.area, (areaCounts.get(v.area) ?? 0) + (venueCounts.get(v.id) ?? 0));
  }
  const byName = (a: [string, number], b: [string, number]) => a[0].localeCompare(b[0]);

  // When ------------------------------------------------------------------------
  // Presets combine (Today + Tomorrow shows both); "All upcoming" clears them, and
  // choosing a date or range replaces them.
  const pickPreset = (id: string) => {
    if (id === "all") return update({ when: [], from: null, to: null });
    const preset = id as WhenPreset;
    const when = get().when;
    update({ when: when.includes(preset) ? without(when, preset) : [...when, preset], from: null, to: null });
  };
  const presetButtons = PRESETS.map((p) =>
    h("button", { type: "button", class: "chip chip-when", "data-value": p.id, onclick: () => pickPreset(p.id) }, p.label),
  );
  const fromInput = h("input", { type: "date", "aria-label": "From" });
  const toInput = h("input", { type: "date", "aria-label": "To" });
  const onDate = () => {
    const from = fromInput.value || null;
    // One date picked: just that day, until a "to" date is chosen.
    const to = toInput.value || (from && !get().to ? from : null);
    update({ when: [], from, to: to && from && to < from ? from : to });
  };
  fromInput.addEventListener("change", onDate);
  toInput.addEventListener("change", onDate);

  // What -------------------------------------------------------------------------
  const tagButtons = [...tagCounts.entries()].sort(byName).map(([tag, n]) =>
    h(
      "button",
      { type: "button", class: "chip", "data-value": tag, onclick: () => cycle("tags", tag) },
      tag,
      h("span", { class: "visually-hidden" }),
      h("span", { class: "count" }, String(n)),
    ),
  );
  const tagMode = h(
    "select",
    { "aria-label": "Tag matching", onchange: (ev: Event) => update({ tagMode: (ev.target as HTMLSelectElement).value as "any" | "all" }) },
    h("option", { value: "any" }, "any selected tag"),
    h("option", { value: "all" }, "all selected tags"),
  );

  // Price ------------------------------------------------------------------------
  const priceRange = h("input", {
    type: "range",
    min: 0,
    max: PRICE_STEPS.length,
    step: 1,
    "aria-label": "Maximum price",
  });
  const priceOut = h("output", { class: "price-out" });
  priceRange.addEventListener("input", () => {
    const i = Number(priceRange.value);
    update({ maxPrice: i >= PRICE_STEPS.length ? null : PRICE_STEPS[i] });
  });
  const check = (label: string, key: "freeOnly" | "includeUnknownPrice" | "hideSoldOut") => {
    const input = h("input", { type: "checkbox", onchange: (ev: Event) => update({ [key]: (ev.target as HTMLInputElement).checked }) });
    return { input, el: h("label", { class: "check" }, input, label) };
  };
  const free = check("Free only", "freeOnly");
  const unknown = check("Include events without a price", "includeUnknownPrice");
  const soldOut = check("Hide sold-out events", "hideSoldOut");

  // Where ------------------------------------------------------------------------
  const areaButtons = [...areaCounts.entries()].sort(byName).map(([area, n]) =>
    h(
      "button",
      { type: "button", class: "chip", "data-value": area, onclick: () => cycle("areas", area) },
      area,
      h("span", { class: "visually-hidden" }),
      h("span", { class: "count" }, String(n)),
    ),
  );
  const venueChecks = [...data.venues.values()]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((v) => {
      const input = h("input", {
        type: "checkbox",
        value: v.id,
        onchange: () => cycle("venues", v.id),
      });
      const el = h(
        "label",
        { class: "check" },
        input,
        v.name,
        h("span", { class: "visually-hidden" }),
        h("span", { class: "count" }, String(venueCounts.get(v.id) ?? 0)),
      );
      return { input, el };
    });

  const reset = h("button", { type: "button", class: "button subtle", onclick: () => set({ ...DEFAULT_FILTERS, q: get().q }) }, "Reset filters");

  container.replaceChildren(
    group("When", h("div", { class: "chips" }, presetButtons), h("div", { class: "date-inputs" }, fromInput, h("span", {}, "to"), toInput)),
    h("p", { class: "hint" }, "Click a tag, area or venue once to show only those, again to hide them, and a third time to clear."),
    group("What", h("div", { class: "chips" }, tagButtons), h("label", { class: "inline" }, "Match ", tagMode)),
    group("Price", h("div", { class: "price" }, priceRange, priceOut), free.el, unknown.el, soldOut.el),
    group("Where", h("div", { class: "chips" }, areaButtons)),
    group("Venues", h("div", { class: "venue-list" }, venueChecks.map((c) => c.el))),
    reset,
  );

  const press = (buttons: HTMLElement[], selected: (v: string) => boolean) =>
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(selected(b.dataset.value!))));
  // Three-state chips: aria-pressed "true" (included), "mixed" (excluded) or "false".
  const pressCycle = (buttons: HTMLElement[], key: "tags" | "areas") =>
    buttons.forEach((b) => {
      const value = b.dataset.value!;
      const state = stateOf(key, value);
      b.setAttribute("aria-pressed", PRESSED[state]);
      b.title = HINTS[state];
      b.querySelector(".visually-hidden")!.textContent = state === "excluded" ? " (hidden)" : "";
    });

  return {
    sync() {
      const f = get();
      const custom = isCustom(f);
      press(presetButtons, (v) => (v === "all" ? !custom && !f.when.length : !custom && f.when.includes(v as WhenPreset)));
      fromInput.value = f.from ?? "";
      toInput.value = f.to ?? "";
      fromInput.min = toInput.min = now();
      pressCycle(tagButtons, "tags");
      tagMode.value = f.tagMode;
      const step = f.maxPrice === null ? PRICE_STEPS.length : PRICE_STEPS.findIndex((p) => p >= f.maxPrice!);
      priceRange.value = String(step === -1 ? PRICE_STEPS.length : step);
      priceOut.textContent = f.maxPrice === null ? "Any price" : `Up to £${f.maxPrice}`;
      free.input.checked = f.freeOnly;
      unknown.input.checked = f.includeUnknownPrice;
      soldOut.input.checked = f.hideSoldOut;
      pressCycle(areaButtons, "areas");
      venueChecks.forEach(({ input, el }) => {
        // An excluded venue shows as an indeterminate checkbox: [-].
        const state = stateOf("venues", input.value);
        input.checked = state === "included";
        input.indeterminate = state === "excluded";
        el.classList.toggle("is-excluded", state === "excluded");
        el.querySelector(".visually-hidden")!.textContent = state === "excluded" ? " (hidden)" : "";
        el.title = HINTS[state];
      });
    },
  };
}

type State = "off" | "included" | "excluded";

const EXCLUDE = { tags: "excludeTags", areas: "excludeAreas", venues: "excludeVenues" } as const;
const PRESSED: Record<State, string> = { off: "false", included: "true", excluded: "mixed" };
const HINTS: Record<State, string> = {
  off: "Click to show only these",
  included: "Shown · click again to hide",
  excluded: "Hidden · click again to clear",
};

function group(title: string, ...children: HTMLElement[]) {
  return h("fieldset", { class: "group" }, h("legend", {}, title), ...children);
}

/** How many filters differ from the defaults (shown on the mobile Filters button). */
export function activeCount(f: Filters): number {
  let n = 0;
  if (f.when.length || isCustom(f)) n++;
  n += f.tags.length + f.areas.length + f.venues.length;
  n += f.excludeTags.length + f.excludeAreas.length + f.excludeVenues.length;
  if (f.maxPrice !== null || f.freeOnly || !f.includeUnknownPrice) n++;
  if (f.hideSoldOut) n++;
  return n;
}
