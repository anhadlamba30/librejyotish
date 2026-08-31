"""Reference-chart regression tests.

Expected values live in tests/reference_charts/fixtures.json and were derived
from the core modules after scripts/crosscheck_*.py verified them against
PyJHora (independent oracle, dev-only). These tests lock that behavior.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from librejyotish.core import charts, dasha, ephemeris as ep, panchang
from librejyotish.core.ashtakavarga import build_ashtakavarga
from librejyotish.core.shadbala import build_shadbala

FIXTURES = json.loads(
    (Path(__file__).parent / "reference_charts" / "fixtures.json").read_text())

LONGITUDE_TOL = 0.0002
BALA_TOL = 0.02

ep.init_ephemeris()


def _naive(case):
    inp = case["input"]
    return (datetime.fromisoformat(inp["datetime_local"]), inp["timezone"],
            inp["latitude"], inp["longitude"])


@pytest.mark.parametrize("label", sorted(FIXTURES))
def test_natal_chart(label):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    natal = charts.build_natal_chart(naive, tz, lat, lon)
    exp = case["natal"]
    assert natal["julian_day_ut"] == pytest.approx(exp["julian_day_ut"], abs=1e-6)
    assert natal["ascendant"]["longitude"] == pytest.approx(
        exp["ascendant_longitude"], abs=LONGITUDE_TOL)
    assert natal["ascendant"]["sign"] == exp["ascendant_sign"]
    for p in natal["planets"]:
        want = exp["planets"][p["name"]]
        assert p["longitude"] == pytest.approx(want["longitude"], abs=LONGITUDE_TOL), p["name"]
        assert p["sign"] == want["sign"]
        assert p["house_from_lagna"] == want["house_from_lagna"]
        assert p["retrograde"] == want["retrograde"]


@pytest.mark.parametrize("label", sorted(FIXTURES))
@pytest.mark.parametrize("division", ["D2", "D3", "D4", "D7", "D9", "D10",
                                      "D12", "D16", "D20", "D24", "D27",
                                      "D30", "D40", "D45", "D60"])
def test_divisional_charts(label, division):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    dc = charts.build_divisional_chart(naive, tz, lat, lon, division)
    exp = case["divisions"][division]
    assert dc["lagna"]["varga_sign_index"] == exp["lagna_varga_sign_index"]
    for body in dc["bodies"]:
        assert body["varga_sign_index"] == exp[body["name"]], (
            f"{label} {division} {body['name']}")


@pytest.mark.parametrize("label", sorted(FIXTURES))
def test_vimshottari_mahadashas(label):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    tree = dasha.build_vimshottari_dasha(naive, tz, lat, lon)
    mds = tree["mahadashas"]
    exp = case["dasha_mahadashas"]
    assert len(mds) == len(exp) == 9
    for got, want in zip(mds, exp):
        assert got["lord"] == want["lord"]
        assert got["start_local"][:19] == want["start_local"]
        assert got["end_local"][:19] == want["end_local"]
        subs = got["sub_periods"]
        assert subs[0]["lord"] == want["first_antardasha_lord"]
        assert subs[-1]["lord"] == want["last_antardasha_lord"]
        first_pd = subs[0]["sub_periods"]
        assert (first_pd[0]["lord"] if first_pd else None) == want[
            "first_pratyantardasha_lord"]


@pytest.mark.parametrize("label", [l for l in sorted(FIXTURES)
                                   if FIXTURES[l].get("dasha_current_at_reference")])
def test_dasha_current_period(label):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    tree = dasha.build_vimshottari_dasha(naive, tz, lat, lon)
    cur = dasha.find_current_period(tree, datetime(2026, 8, 22, 10, 15), tz)
    chain = [{"level": c["level"], "lord": c["lord"]} for c in cur["chain"]]
    assert chain == case["dasha_current_at_reference"]


def test_dasha_levels_control_depth():
    naive, tz, lat, lon = _naive(FIXTURES[next(iter(FIXTURES))])
    md0 = dasha.build_vimshottari_dasha(naive, tz, lat, lon, levels=1)["mahadashas"]
    assert all("sub_periods" not in m for m in md0)
    md1 = dasha.build_vimshottari_dasha(naive, tz, lat, lon, levels=2)["mahadashas"]
    assert all("sub_periods" in m for m in md1)
    assert all("sub_periods" not in a for m in md1 for a in m["sub_periods"])
    md2 = dasha.build_vimshottari_dasha(naive, tz, lat, lon, levels=3)["mahadashas"]
    assert all("sub_periods" in a for m in md2 for a in m["sub_periods"])


def test_dasha_invalid_levels_rejected():
    naive, tz, lat, lon = _naive(FIXTURES[next(iter(FIXTURES))])
    with pytest.raises(ValueError):
        dasha.build_vimshottari_dasha(naive, tz, lat, lon, levels=9)


def test_server_dasha_levels_via_tool():
    import server as srv_mod
    r = srv_mod.get_vimshottari_dasha(
        "1994-03-21T14:30:00", 19.99, 73.79, "Asia/Kolkata", levels=1)
    assert "error" not in r
    assert all("sub_periods" not in m for m in r["mahadashas"])
    rbad = srv_mod.get_vimshottari_dasha(
        "1994-03-21T14:30:00", 19.99, 73.79, "Asia/Kolkata", levels=0)
    assert "error" in rbad and rbad["error"]["type"] == "ValueError"


@pytest.mark.parametrize("label", sorted(FIXTURES))
def test_panchang(label):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    pc = panchang.build_panchang(naive.date(), tz, lat, lon)
    exp = case["panchang"]
    assert pc["tithi"]["name"] == exp["tithi_name"]
    assert pc["tithi"]["index_one_based"] == exp["tithi_index_one_based"]
    assert pc["vara"]["name"] == exp["vara"]
    assert pc["nakshatra"]["name"] == exp["nakshatra_name"]
    assert pc["nakshatra"]["pada"] == exp["nakshatra_pada"]
    assert pc["yoga"]["name"] == exp["yoga_name"]
    assert pc["karana"]["name"] == exp["karana_name"]
    assert pc["sunrise"][:16] == exp["sunrise"]
    assert pc["sunset"][:16] == exp["sunset"]


@pytest.mark.parametrize("label", sorted(FIXTURES))
def test_ashtakavarga(label):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    av = build_ashtakavarga(naive, tz, lat, lon)
    for planet, bindus in case["ashtakavarga"].items():
        assert av["bhinnashtakavarga"][planet]["bindus_by_sign"] == bindus
    sav = av["sarvashtakavarga"]["bindus_by_sign"]
    assert sav == case["sarvashtakavarga_totals"]
    assert sum(sav.values()) == 337


@pytest.mark.parametrize("label", sorted(FIXTURES))
def test_shadbala_verified_components(label):
    case = FIXTURES[label]
    naive, tz, lat, lon = _naive(case)
    sb = build_shadbala(naive, tz, lat, lon)
    six = sb["six_fold_strength"]
    kb = sb["strength_breakdown"]["kala"]
    parts = {"sthana_bala": six["sthana_bala"],
             "naisargika_bala": six["naisargika_bala"],
             "nathonnatha_bala": kb["nathonnatha_bala"],
             "tribhaga_bala": kb["tribhaga_bala"],
             "abda_bala": kb["abda_bala"],
             "masa_bala": kb["masa_bala"],
             "vaara_bala": kb["vaara_bala"]}
    for planet, want in case["shadbala"].items():
        for part, table in parts.items():
            assert table[planet] == pytest.approx(want[part], abs=BALA_TOL), (
                f"{label} {planet} {part}")


def test_server_registers_all_tools():
    import asyncio

    import server as srv_mod
    tools = asyncio.run(srv_mod.server.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "get_natal_chart", "get_divisional_chart", "get_vimshottari_dasha",
        "get_panchang", "get_ashtakavarga", "get_shadbala",
        "get_current_transits", "get_eclipses", "geocode_location", "batch"}


def test_server_tool_error_paths():
    import server as srv_mod
    result = srv_mod.get_natal_chart(
        "not-a-date", 28.6, 77.2, "Asia/Kolkata")
    assert "error" in result and result["error"]["type"] == "ValueError"


def test_server_timezone_derived_when_omitted():
    import server as srv_mod
    # No timezone -> derived from coords (Nashik -> Asia/Kolkata).
    r = srv_mod.get_natal_chart("1994-03-21T14:30:00", 19.99727, 73.79096)
    assert "error" not in r
    assert r["input"]["timezone"] == "Asia/Kolkata"
    assert any("auto-derived" in w for w in r["warnings"])


def test_server_timezone_match_no_warning():
    import server as srv_mod
    r = srv_mod.get_natal_chart(
        "1994-03-21T14:30:00", 19.99727, 73.79096, "Asia/Kolkata")
    assert "error" not in r
    assert r.get("warnings") is None


def test_server_timezone_mismatch_warns():
    import server as srv_mod
    # NYC coords declared as Asia/Kolkata -> mismatch warning, still computed.
    r = srv_mod.get_natal_chart("1994-03-21T14:30:00", 40.71, -74.0, "Asia/Kolkata")
    assert "error" not in r
    assert any("does not match" in w for w in r["warnings"])


def test_server_strict_datetime_rejects_space_separator():
    import server as srv_mod
    r = srv_mod.get_natal_chart("1994-03-21 14:30:00", 19.99, 73.79, "Asia/Kolkata")
    assert "error" in r
    assert "T" in r["error"]["message"]


def test_server_start_date_accepts_date_only():
    import server as srv_mod
    r = srv_mod.get_vimshottari_dasha(
        "1994-03-21T14:30:00", 19.99, 73.79, "Asia/Kolkata",
        levels=1, start_date="2000-01-01")
    assert "error" not in r


def test_server_panchang_flag_sunset_before_sunrise():
    import server as srv_mod
    # Mumbai coords + a wildly wrong timezone produce sunset before sunrise.
    r = srv_mod.get_panchang(
        "2025-06-21", 19.0, 72.8, timezone="America/New_York")
    assert "error" not in r
    assert any("not after sunrise" in w for w in r.get("warnings", []))


def test_server_batch_dispatches():
    import server as srv_mod
    r = srv_mod.batch([
        {"tool": "get_natal_chart", "arguments": {
            "datetime_local": "1994-03-21T14:30:00",
            "latitude": 19.99, "longitude": 73.79, "timezone": "Asia/Kolkata"}},
        {"tool": "does_not_exist", "arguments": {}},
        {"tool": "geocode_location", "arguments": {"place": "Nashik, India", "limit": 1}},
    ])
    assert r["count"] == 3
    assert "error" not in r["results"][0]
    assert "error" in r["results"][1]
    assert r["results"][2]["resolved"]
