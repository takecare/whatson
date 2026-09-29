import json
from datetime import date

from conftest import FakeFetcher

from whatson.aggregators.saatchi import API as SAATCHI_API
from whatson.runner import scrape

TODAY = date(2026, 9, 29)


def _read(path):
    return json.loads(path.read_text())


def test_scrape_writes_outputs_and_isolates_failures(tmp_path):
    # Only Saatchi has fixtures; the other venues fail with FetchError.
    http = FakeFetcher({f"{SAATCHI_API}|page=1": "saatchi/exhibitions-page1.json"})
    statuses = {s.venue_id: s for s in scrape(http, tmp_path, today=TODAY)}

    assert statuses["saatchi"].ok and statuses["saatchi"].event_count > 0
    assert not statuses["topsecret"].ok and "FetchError" in statuses["topsecret"].error

    events = _read(tmp_path / "events.json")["events"]
    assert events and {e["venue_id"] for e in events} == {"saatchi"}
    starts = [e["start"] for e in events]
    assert starts == sorted(starts)
    assert {v["id"] for v in _read(tmp_path / "venues.json")["venues"]} >= {"saatchi", "topsecret"}
    assert len(_read(tmp_path / "status.json")["sources"]) == len(statuses)


def test_failed_venue_keeps_previous_events(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    http = FakeFetcher({f"{SAATCHI_API}|page=1": "saatchi/exhibitions-page1.json"})
    scrape(http, first, today=TODAY)

    # Next run: Saatchi is down.
    statuses = {s.venue_id: s for s in scrape(FakeFetcher({}), second, first, today=TODAY)}

    saatchi = statuses["saatchi"]
    assert not saatchi.ok and saatchi.stale and saatchi.event_count > 0
    assert saatchi.last_success is not None
    kept = [e for e in _read(second / "events.json")["events"] if e["venue_id"] == "saatchi"]
    assert len(kept) == saatchi.event_count


def test_only_flag_carries_other_venues_over(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    http = FakeFetcher({f"{SAATCHI_API}|page=1": "saatchi/exhibitions-page1.json"})
    scrape(http, first, today=TODAY)

    statuses = scrape(FakeFetcher({}), second, first, only=["topsecret"], today=TODAY)
    saatchi = next(s for s in statuses if s.venue_id == "saatchi")
    assert saatchi.ok  # untouched status from the first run
    assert any(e["venue_id"] == "saatchi" for e in _read(second / "events.json")["events"])
