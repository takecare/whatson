// Shapes of the JSON written by the scraper (scraper/whatson/runner.py).

export interface WhatsOnEvent {
  id: string;
  venue_id: string;
  title: string;
  url: string;
  booking_url?: string;
  category?: string;
  tags: string[];
  /** "2026-09-30" (all day) or "2026-09-30T19:00:00+01:00". */
  start: string;
  /** End of a run (exhibition, theatre run). */
  end?: string;
  /** Individual showtimes, e.g. every screening of a film. */
  performances: string[];
  space?: string;
  /** Missing means unknown; 0 means free. */
  price_min?: number;
  price_max?: number;
  currency: string;
  sold_out: boolean;
  image_url?: string;
  summary?: string;
}

export interface Venue {
  id: string;
  name: string;
  url: string;
  address: string;
  city: string;
  area: string | null;
  lat: number;
  lng: number;
  tags: string[];
}

export interface SourceStatus {
  venue_id: string;
  ok: boolean;
  event_count: number;
  error: string | null;
  duration_s: number | null;
  last_success: string | null;
  stale: boolean;
}

export interface Data {
  generatedAt: string | null;
  events: WhatsOnEvent[];
  venues: Map<string, Venue>;
  sources: SourceStatus[];
}
