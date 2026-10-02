import { type Day, dayHeading, shortDate, timeOf } from "./dates";
import { h } from "./dom";
import type { Occurrence, Results, Run } from "./filters";
import type { Data, Venue, WhatsOnEvent } from "./types";

const PAGE_SIZE = 150;
/** Runs shown before "Show more": 4 on wide screens, 3 on phones. */
const runsPreview = () => (window.matchMedia("(max-width: 860px)").matches ? 3 : 4);

export function priceLabel(e: WhatsOnEvent): string | null {
  const { price_min: min, price_max: max } = e;
  if (min === undefined || min === null) return null;
  const fmt = (n: number) => (n === 0 ? "Free" : `£${Number.isInteger(n) ? n : n.toFixed(2)}`);
  if (max === undefined || max === null || max === min) return fmt(min);
  return `${fmt(min)}–${fmt(max)}`;
}

function card(e: WhatsOnEvent, venue: Venue | undefined, when: string | null, whenLabel: string) {
  const price = priceLabel(e);
  const place = [venue?.name ?? e.venue_id, e.space, venue?.area].filter(Boolean).join(" · ");
  return h(
    "article",
    { class: `card${e.sold_out ? " is-sold-out" : ""}` },
    h("div", { class: "card-when", "aria-label": whenLabel }, when ?? "All day"),
    h(
      "div",
      { class: "card-body" },
      h("h3", {}, h("a", { href: e.url, target: "_blank", rel: "noopener" }, e.title)),
      h("p", { class: "card-place" }, place),
      e.summary ? h("p", { class: "card-summary" }, e.summary) : null,
      h(
        "div",
        { class: "card-tags" },
        e.sold_out ? h("span", { class: "pill pill-soldout" }, "Sold out") : null,
        h("span", { class: `pill pill-price${price ? "" : " is-unknown"}` }, price ?? "Price TBC"),
        ...e.tags.map((t) => h("span", { class: "pill" }, t)),
        e.booking_url && !e.sold_out
          ? h("a", { class: "book", href: e.booking_url, target: "_blank", rel: "noopener" }, "Book")
          : null,
      ),
    ),
    e.image_url
      ? h("img", {
          class: "card-image",
          src: e.image_url,
          alt: "",
          loading: "lazy",
          decoding: "async",
          referrerpolicy: "no-referrer",
          onerror: ((ev: Event) => (ev.target as HTMLElement).remove()) as EventListener,
        })
      : null,
  );
}

function occurrenceCard(o: Occurrence, data: Data) {
  const when = o.times.length ? o.times.join(", ") : null;
  return card(o.event, data.venues.get(o.event.venue_id), when, when ?? "All day");
}

function runCard(r: Run, data: Data) {
  const range = `${shortDate(r.from)} – ${shortDate(r.to)}`;
  const t = timeOf(r.event.start);
  return card(r.event, data.venues.get(r.event.venue_id), range + (t ? ` · ${t}` : ""), range);
}

export function renderResults(
  main: HTMLElement,
  results: Results,
  data: Data,
  now: Day,
  onReset: () => void,
): void {
  main.replaceChildren();
  const total = results.count;
  main.append(
    h(
      "div",
      { class: "results-head" },
      h("p", { class: "results-count", role: "status" }, `${total} ${total === 1 ? "event" : "events"}`),
    ),
  );

  if (!results.days.length && !results.runs.length) {
    main.append(
      h(
        "div",
        { class: "empty" },
        h("p", {}, "Nothing matches these filters."),
        h("button", { class: "button", type: "button", onclick: onReset }, "Clear filters"),
      ),
    );
    return;
  }

  if (results.runs.length) {
    const list = h("div", { class: "cards" });
    const preview = runsPreview();
    const more = results.runs.length - preview;
    results.runs.slice(0, preview).forEach((r) => list.append(runCard(r, data)));
    const section = h(
      "section",
      { class: "day runs" },
      h("h2", { class: "day-heading" }, "On over several days", h("small", {}, `${results.runs.length}`)),
      list,
    );
    if (more > 0) {
      const button = h("button", { class: "button subtle runs-more", type: "button" }, `Show ${more} more`);
      button.addEventListener("click", () => {
        results.runs.slice(preview).forEach((r) => list.append(runCard(r, data)));
        button.remove();
      });
      section.append(button);
    }
    main.append(section);
  }

  // Render day sections in pages so thousands of events don't block the page.
  let dayIndex = 0;
  let itemIndex = 0;
  const more = h("button", { class: "button subtle more", type: "button" }, "Show more");
  const renderPage = () => {
    let budget = PAGE_SIZE;
    while (dayIndex < results.days.length && budget > 0) {
      const { day, items } = results.days[dayIndex];
      let section = main.querySelector<HTMLElement>(`section[data-day="${day}"]`);
      if (!section) {
        section = h(
          "section",
          { class: "day", "data-day": day },
          h("h2", { class: "day-heading" }, dayHeading(day, now), h("small", {}, shortDate(day))),
          h("div", { class: "cards" }),
        );
        main.insertBefore(section, more.isConnected ? more : null);
      }
      const list = section.querySelector(".cards")!;
      while (itemIndex < items.length && budget > 0) {
        list.append(occurrenceCard(items[itemIndex], data));
        itemIndex++;
        budget--;
      }
      if (itemIndex >= items.length) {
        dayIndex++;
        itemIndex = 0;
      }
    }
    if (dayIndex >= results.days.length) more.remove();
  };
  more.addEventListener("click", renderPage);
  main.append(more);
  renderPage();
}

const relative = new Intl.RelativeTimeFormat("en-GB", { numeric: "auto" });

export function ago(iso: string, now = Date.now()): string {
  const minutes = Math.round((new Date(iso).getTime() - now) / 60000);
  if (Math.abs(minutes) < 60) return relative.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) return relative.format(hours, "hour");
  return relative.format(Math.round(hours / 24), "day");
}

export function renderSources(container: HTMLElement, count: HTMLElement, updated: HTMLElement, data: Data): void {
  updated.textContent = data.generatedAt ? `Last updated ${ago(data.generatedAt)}.` : "";
  // The table starts collapsed, so the heading says whether anything is failing.
  const failing = data.sources.filter((s) => !s.ok).length;
  const venues = data.venues.size;
  count.textContent = `${venues} ${venues === 1 ? "venue" : "venues"}${failing ? ` · ${failing} failing` : ""}`;
  count.classList.toggle("err", failing > 0);
  const rows = [...data.venues.values()].map((v) => {
    const s = data.sources.find((x) => x.venue_id === v.id);
    const state = !s
      ? h("span", { class: "status" }, "Not collected yet")
      : s.ok
        ? h("span", { class: "status ok" }, "OK")
        : h(
            "span",
            { class: "status err", title: s.error ?? "" },
            s.stale && s.last_success ? `Failing · showing data from ${ago(s.last_success)}` : "Failing",
          );
    return h(
      "tr",
      {},
      h("td", {}, h("a", { href: v.url, target: "_blank", rel: "noopener" }, v.name)),
      h("td", {}, v.area ?? v.city),
      h("td", { class: "num" }, s ? String(s.event_count) : "–"),
      h("td", {}, state),
    );
  });
  container.replaceChildren(
    h(
      "table",
      { class: "sources" },
      h("thead", {}, h("tr", {}, h("th", {}, "Venue"), h("th", {}, "Area"), h("th", { class: "num" }, "Events"), h("th", {}, "Status"))),
      h("tbody", {}, rows),
    ),
  );
}
