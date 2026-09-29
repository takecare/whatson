import { type Day, PRESETS } from "./dates";
import { h } from "./dom";
import { DEFAULT_FILTERS, type Filters, dateRange, effectiveTags } from "./filters";
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
  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

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
  const presetButtons = PRESETS.map((p) =>
    h("button", { type: "button", class: "chip", "data-value": p.id, onclick: () => update({ when: p.id }) }, p.label),
  );
  const fromInput = h("input", { type: "date", "aria-label": "From" });
  const toInput = h("input", { type: "date", "aria-label": "To" });
  const onDate = () =>
    update({ when: "custom", from: fromInput.value || null, to: toInput.value || null });
  fromInput.addEventListener("change", onDate);
  toInput.addEventListener("change", onDate);

  // What -------------------------------------------------------------------------
  const tagButtons = [...tagCounts.entries()].sort(byName).map(([tag, n]) =>
    h(
      "button",
      { type: "button", class: "chip", "data-value": tag, onclick: () => update({ tags: toggle(get().tags, tag) }) },
      tag,
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
      { type: "button", class: "chip", "data-value": area, onclick: () => update({ areas: toggle(get().areas, area) }) },
      area,
      h("span", { class: "count" }, String(n)),
    ),
  );
  const venueChecks = [...data.venues.values()]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((v) => {
      const input = h("input", {
        type: "checkbox",
        value: v.id,
        onchange: () => update({ venues: toggle(get().venues, v.id) }),
      });
      return { input, el: h("label", { class: "check" }, input, v.name, h("span", { class: "count" }, String(venueCounts.get(v.id) ?? 0))) };
    });

  const reset = h("button", { type: "button", class: "button subtle", onclick: () => set({ ...DEFAULT_FILTERS, q: get().q }) }, "Reset filters");

  container.replaceChildren(
    group("When", h("div", { class: "chips" }, presetButtons), h("div", { class: "date-inputs" }, fromInput, h("span", {}, "to"), toInput)),
    group("What", h("div", { class: "chips" }, tagButtons), h("label", { class: "inline" }, "Match ", tagMode)),
    group("Price", h("div", { class: "price" }, priceRange, priceOut), free.el, unknown.el, soldOut.el),
    group("Where", h("div", { class: "chips" }, areaButtons)),
    group("Venues", h("div", { class: "venue-list" }, venueChecks.map((c) => c.el))),
    reset,
  );

  const press = (buttons: HTMLElement[], selected: (v: string) => boolean) =>
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(selected(b.dataset.value!))));

  return {
    sync() {
      const f = get();
      press(presetButtons, (v) => v === f.when);
      const [from, to] = dateRange(f, now());
      fromInput.value = from;
      toInput.value = to ?? "";
      fromInput.min = toInput.min = now();
      press(tagButtons, (v) => f.tags.includes(v));
      tagMode.value = f.tagMode;
      const step = f.maxPrice === null ? PRICE_STEPS.length : PRICE_STEPS.findIndex((p) => p >= f.maxPrice!);
      priceRange.value = String(step === -1 ? PRICE_STEPS.length : step);
      priceOut.textContent = f.maxPrice === null ? "Any price" : `Up to £${f.maxPrice}`;
      free.input.checked = f.freeOnly;
      unknown.input.checked = f.includeUnknownPrice;
      soldOut.input.checked = f.hideSoldOut;
      press(areaButtons, (v) => f.areas.includes(v));
      venueChecks.forEach((c) => (c.input.checked = f.venues.includes(c.input.value)));
    },
  };
}

function group(title: string, ...children: HTMLElement[]) {
  return h("fieldset", { class: "group" }, h("legend", {}, title), ...children);
}

/** How many filters differ from the defaults (shown on the mobile Filters button). */
export function activeCount(f: Filters): number {
  let n = 0;
  if (f.when !== "all") n++;
  n += f.tags.length + f.areas.length + f.venues.length;
  if (f.maxPrice !== null || f.freeOnly || !f.includeUnknownPrice) n++;
  if (f.hideSoldOut) n++;
  return n;
}
