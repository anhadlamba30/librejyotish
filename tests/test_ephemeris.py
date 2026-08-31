"""Ephemeris node-retrograde tests.

Nodes (Rahu/Ketu) are always retrograde; their instantaneous speed is a
numerical derivative that can go positive near a station. Regression test for
the bug where Rahu was wrongly reported non-retrograde at those instants.
"""

from datetime import datetime

import pytest

from librejyotish.core import ephemeris as ep

ep.init_ephemeris()

# Dates spanning Rahu stations (raw TRUE_NODE speed may cross zero here).
STATION_DATES = [
    "2026-08-30",
    "2026-09-06",
    "2026-09-15",
    "2026-10-15",
    "2027-01-15",
    "2027-03-01",
]


@pytest.mark.parametrize("d", STATION_DATES)
def test_rahu_always_retrograde_across_stations(d):
    jd = ep.to_jd(datetime.fromisoformat(d + "T12:00"), "UTC")
    p = ep.planet_positions(jd)
    assert p["Rahu"]["retrograde"] is True
    assert p["Ketu"]["retrograde"] is True


def test_nodes_opposite_and_share_speed():
    jd = ep.to_jd(datetime.fromisoformat("2026-09-06T12:00"), "UTC")
    p = ep.planet_positions(jd)
    assert ep.normalize_deg(p["Ketu"]["longitude"]) == pytest.approx(
        ep.normalize_deg(p["Rahu"]["longitude"] + 180.0), abs=1e-9)
    assert p["Ketu"]["speed"] == pytest.approx(p["Rahu"]["speed"])
