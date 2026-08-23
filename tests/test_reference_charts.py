"""Reference-chart regression tests.

Expected values live in tests/reference_charts/fixtures.json and were derived
from the core modules after scripts/crosscheck_*.py verified them against
PyJHora (independent oracle, dev-only). These tests lock that behavior.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from core import charts, dasha, ephemeris as ep, panchang
from core.ashtakavarga import build_ashtakavarga
from core.shadbala import build_shadbala

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
        "get_current_transits"}


def test_server_tool_error_paths():
    import server as srv_mod
    result = srv_mod.get_natal_chart(
        "not-a-date", "Asia/Kolkata", 28.6, 77.2)
    assert "error" in result and result["error"]["type"] == "ValueError"
