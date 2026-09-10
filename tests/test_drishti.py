"""Graha-drishti unit tests: offsets, symmetry labels, node modes, transits."""

from datetime import datetime

import pytest

from librejyotish.core import charts, ephemeris as ep
from librejyotish.core.drishti import (
    graha_drishti,
    offsets_for,
    transit_to_natal_aspects,
)

ep.init_ephemeris()


def test_all_planets_aspect_seventh():
    signs = {"Sun": 0, "Moon": 6, "Mars": 1, "Mercury": 2, "Jupiter": 3,
             "Venus": 4, "Saturn": 5, "Rahu": 6, "Ketu": 0}
    # Sun in Aries(0) -> Moon in Libra(6): offset 6 == 7th
    res = graha_drishti(signs)
    assert {"target": "Moon", "type": "7th"} in res["Sun"]["casts"]
    assert {"caster": "Sun", "type": "7th"} in res["Moon"]["receives"]


def test_special_aspects_mars_jupiter_saturn():
    # Caster at Aries(0): Mars hits Cancer(3, 4th), Libra(6, 7th),
    # Scorpio(7, 8th); Jupiter hits Leo(4, 5th), Libra(6, 7th),
    # Sagittarius(8, 9th); Saturn hits Gemini(2, 3rd), Libra(6, 7th),
    # Capricorn(9, 10th).
    signs = {"Mars": 0, "Jupiter": 0, "Saturn": 0, "Sun": 2, "Moon": 3,
             "Mercury": 4, "Venus": 6, "Rahu": 7, "Ketu": 8}
    res = graha_drishti(signs)
    assert {"target": "Moon", "type": "4th"} in res["Mars"]["casts"]
    assert {"target": "Venus", "type": "7th"} in res["Mars"]["casts"]
    assert {"target": "Rahu", "type": "8th"} in res["Mars"]["casts"]
    assert {"target": "Mercury", "type": "5th"} in res["Jupiter"]["casts"]
    assert {"target": "Ketu", "type": "9th"} in res["Jupiter"]["casts"]
    assert {"target": "Sun", "type": "3rd"} in res["Saturn"]["casts"]
    # Saturn's 10th needs a target at offset 9 (nothing there in this
    # fixture) — check it separately.
    res2 = graha_drishti({"Saturn": 0, "Sun": 9})
    assert res2["Saturn"]["casts"] == [{"target": "Sun", "type": "10th"}]
    # Non-special planets cast 7th only (Sun at 2 -> Ketu at 8 is offset 6).
    assert res["Sun"]["casts"] == [{"target": "Ketu", "type": "7th"}]


def test_mutual_aspect_labels_match():
    # Mars in Aries(0), Saturn in Libra(6): mutual 7th both ways.
    res = graha_drishti({"Mars": 0, "Saturn": 6})
    assert {"target": "Saturn", "type": "7th"} in res["Mars"]["casts"]
    assert {"target": "Mars", "type": "7th"} in res["Saturn"]["casts"]


def test_nodes_default_seventh_only():
    assert offsets_for("Rahu") == (6,)
    assert offsets_for("Ketu") == (6,)
    assert offsets_for("Rahu", nodes="jupiter_like") == (4, 6, 8)
    assert offsets_for("Rahu", nodes="none") == ()
    with pytest.raises(ValueError):
        offsets_for("Rahu", nodes="bogus")


def test_casts_receives_symmetry_counts():
    signs = {"Sun": 0, "Moon": 0, "Mars": 6, "Mercury": 6, "Jupiter": 9,
             "Venus": 3, "Saturn": 3, "Rahu": 6, "Ketu": 0}
    res = graha_drishti(signs)
    total_casts = sum(len(v["casts"]) for v in res.values())
    total_receives = sum(len(v["receives"]) for v in res.values())
    assert total_casts == total_receives
    # Every receives entry has a matching casts entry with same type
    for target, v in res.items():
        for r in v["receives"]:
            assert {"target": target, "type": r["type"]} in res[r["caster"]]["casts"]


def test_transit_to_natal_direction():
    # Transit Jupiter in Aries(0) aspects natal Moon in Leo(4) as 5th.
    out = transit_to_natal_aspects({"Jupiter": 0}, {"Moon": 4, "Sun": 5})
    assert out["Jupiter"] == [{"target": "Moon", "type": "5th"}]


def test_natal_chart_carries_aspects_and_conventions():
    natal = charts.build_natal_chart(
        datetime(1994, 3, 21, 14, 30), "Asia/Kolkata", 19.99, 73.79)
    assert "graha_drishti" in natal["conventions_used"]
    for p in natal["planets"]:
        assert "aspects" in p
        assert sorted(p["aspects"]) == ["casts", "receives"]
    # Cross-check one planet against the pure function (plus house enrichment)
    signs = {p["name"]: int(p["longitude"] // 30) for p in natal["planets"]}
    houses = {p["name"]: p["house_from_lagna"] for p in natal["planets"]}
    expect = graha_drishti(signs)
    for c in expect["Jupiter"]["casts"]:
        c["target_house_from_lagna"] = houses[c["target"]]
    by_name = {p["name"]: p for p in natal["planets"]}
    assert by_name["Jupiter"]["aspects"] == expect["Jupiter"]


def test_divisional_chart_carries_aspects():
    dc = charts.build_divisional_chart(
        datetime(1994, 3, 21, 14, 30), "Asia/Kolkata", 19.99, 73.79, "D9")
    assert "graha_drishti" in dc["conventions_used"]
    for b in dc["bodies"]:
        assert "aspects" in b
    signs = {b["name"]: b["varga_sign_index"] - 1 for b in dc["bodies"]}
    houses = {b["name"]: b["house_from_varga_lagna"] for b in dc["bodies"]}
    expect = graha_drishti(signs)
    for c in expect["Saturn"]["casts"]:
        c["target_house_from_varga_lagna"] = houses[c["target"]]
    by_name = {b["name"]: b for b in dc["bodies"]}
    assert by_name["Saturn"]["aspects"] == expect["Saturn"]


def test_transit_tool_carries_aspects_natal():
    import server as srv_mod
    r = srv_mod.get_current_transits(
        "1994-03-21T14:30:00", 19.99, 73.79, "Asia/Kolkata",
        as_of_datetime_local="2026-01-01T12:00:00")
    assert "error" not in r
    assert "graha_drishti" in r["conventions_used"]
    for t in r["transits"]:
        assert "aspects_natal" in t
        for h in t["aspects_natal"]:
            assert set(h) == {"target", "type", "target_house_from_lagna"}
