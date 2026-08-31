"""Eclipse computation tests.

Expected values are the published NASA/calendar events for these dates:
solar eclipses must reproduce their published type (total/annular/partial),
and lunar magnitudes must match published umbral values within tolerance.
"""

from datetime import datetime

import pytest

from librejyotish.core import eclipses
from librejyotish.core.ephemeris import init_ephemeris

init_ephemeris()


def _first(dt, tz="Asia/Kolkata", count=1):
    return eclipses.next_eclipses(dt, tz, count=count)["events"][0]


def test_2026_august_window():
    events = eclipses.next_eclipses(
        datetime(2026, 8, 1, 0), "Asia/Kolkata", count=2)["events"]
    assert events[0]["kind"] == "solar"
    assert events[0]["type"] == "total"
    assert events[0]["greatest_ut"].startswith("2026-08-12")
    assert events[1]["kind"] == "lunar"
    assert events[1]["type"] == "partial"
    assert events[1]["greatest_ut"].startswith("2026-08-28")
    assert events[1]["greatest_local"].startswith("2026-08-28T09:42")
    assert events[1]["magnitudes"]["umbral"] == pytest.approx(0.93, abs=0.01)
    assert events[1]["saros"]["series"] == 138
    assert events[1]["saros"]["member"] == 29


def test_lunar_eclipse_point_is_moon():
    ev = _first(datetime(2026, 8, 25, 0))
    assert ev["kind"] == "lunar"
    assert ev["point"]["body"] == "Moon"
    # Sidereal Moon ~10.6° Aquarius (Shatabhisha) at the Aug 28 2026 maximum.
    assert ev["point"]["sign"] == "Aquarius"
    assert ev["point"]["nakshatra"]["name"] == "Shatabhisha"


def test_solar_types_match_published():
    # 2023-10-14 annular, 2024-04-08 total, 2019-01-06 partial.
    assert _first(datetime(2023, 10, 10, 0))["type"] == "annular"
    assert _first(datetime(2024, 4, 3, 0))["type"] == "total"
    assert _first(datetime(2019, 1, 1, 0))["type"] == "partial"


def test_eclipses_on_date():
    res = eclipses.eclipses_on_date(datetime(2026, 8, 28).date(), "Asia/Kolkata")
    ev_list = res["events"]
    assert len(ev_list) == 1
    assert ev_list[0]["kind"] == "lunar"
    assert ev_list[0]["type"] == "partial"


def test_count_obeys_limit():
    events = eclipses.next_eclipses(
        datetime(2026, 8, 1, 0), "Asia/Kolkata", count=6)["events"]
    assert len(events) == 6
    assert events[0]["greatest_ut"] < events[-1]["greatest_ut"]


def test_server_get_eclipses_houses():
    import server as srv_mod
    r = srv_mod.get_eclipses(
        "2002-03-10T06:30:00", 19.9975, 73.79096, "Asia/Kolkata",
        as_of_datetime_local="2026-08-01T00:00:00", count=1)
    assert "error" not in r
    assert r["ephemeris_source"] == "swiss_ephemeris_data_files"
    assert r["conventions_used"]["natal_reference"]["lagna_sign"] == "Aquarius"
    ev = r["events"][0]
    assert ev["kind"] == "solar" and ev["type"] == "total"
    # Sun 25.8° Cancer = 6 whole-sign houses from Aquarius Lagna.
    assert ev["house_from_natal_lagna"] == 6
    # and 7 from Capricorn Moon.
    assert ev["house_from_natal_moon"] == 7