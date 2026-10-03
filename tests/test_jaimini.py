"""Tests for core/jaimini.py: Arudha Padas, Chara Karakas, Karakamsha.

Pada-rule pins come from the published SJVC Bhava Arudha worked example
(Virgo lagna / Mercury in Pisces -> AL in Gemini); the oracle cross-check
against jhora lives in scripts/crosscheck_padas.py (dev-only).
Runs via `conda run -n librejyotish python -m pytest tests/test_jaimini.py`.
"""

from datetime import datetime

import pytest

from librejyotish.core import charts, ephemeris as ep
from librejyotish.core import jaimini as jm
from librejyotish.core.constants import SIGNS

NASHIK = dict(naive_local=datetime(1994, 3, 21, 14, 32), tz_name="Asia/Kolkata",
              latitude=19.9975, longitude=73.7898)


def test_sjvc_example_lagna_pada():
    # Virgo lagna (5), Mercury in Pisces (11): count 7, raw Virgo -> exception.
    calc = jm.arudha_pada(5, 11)
    assert calc["count"] == 7
    assert calc["raw_sign_index"] == 5
    assert calc["exception_applied"] is True
    assert calc["pada_sign_index"] == 2  # Gemini


def test_lord_in_own_house_goes_tenth():
    # 8th house Aries (0), Mars in Aries (0): raw Aries -> 10th therefrom.
    calc = jm.arudha_pada(0, 0)
    assert calc["pada_sign_index"] == 9  # Capricorn
    assert calc["exception_applied"] is True


def test_lord_in_seventh_goes_tenth_from_house():
    # Lord in 7th (count 7): raw falls on the house itself -> 10th therefrom.
    calc = jm.arudha_pada(3, 9)
    assert calc["raw_sign_index"] == 3
    assert calc["pada_sign_index"] == 0  # (3 + 9) % 12


def test_pada_never_in_first_or_seventh_exhaustive():
    for house in range(12):
        for lord in range(12):
            pada = jm.arudha_pada(house, lord)["pada_sign_index"]
            assert (pada - house) % 12 not in (0, 6), (house, lord)


def test_lord_in_fourth_owns_pada():
    # count 4 -> raw in 7th -> exception lands back on the lord's own sign.
    for house in range(12):
        lord = (house + 3) % 12
        calc = jm.arudha_pada(house, lord)
        assert calc["exception_applied"] is True
        assert calc["pada_sign_index"] == lord


def test_seven_karaka_order():
    lons = {"Sun": 10.0, "Moon": 46.5, "Mars": 300.1, "Mercury": 165.9,
            "Jupiter": 100.2, "Venus": 350.0, "Saturn": 200.7, "Rahu": 80.0,
            "Ketu": 260.0}
    table = jm.chara_karakas(lons, "seven")
    order = [k["planet"] for k in table["karakas"]]
    degs = {p: lons[p] % 30 for p in jm.KARAKA_PLANETS_7}
    expect = sorted(degs, key=lambda p: -degs[p])
    assert order == expect
    assert table["karakas"][0]["role"] == "Atmakaraka"
    assert table["karakas"][-1]["role"] == "Darakaraka"
    assert table["warnings"] == []


def test_eight_karaka_rahu_reversed():
    # Rahu at 5 deg in-sign ranks as 25 (backwards count).
    lons = {"Sun": 10.0, "Moon": 46.5, "Mars": 300.1, "Mercury": 165.0,
            "Jupiter": 100.0, "Venus": 350.0, "Saturn": 200.0,
            "Rahu": 35.0, "Ketu": 215.0}  # Rahu 5 deg in Aries -> 25.0
    table = jm.chara_karakas(lons, "eight")
    rahu = next(k for k in table["karakas"] if k["planet"] == "Rahu")
    assert rahu["degree_in_sign"] == pytest.approx(25.0)
    assert rahu["role"] == "Atmakaraka"  # 25.0 beats everything else here
    assert rahu["signifies"] == "soul, self"
    assert len(table["karakas"]) == 8
    assert "roles" not in table  # roles live on each entry, not as a separate array
    assert [k["role"] for k in table["karakas"]] == jm.EIGHT_KARAKA_ROLES
    assert next(k for k in table["karakas"] if k["role"] == "Pitrukaraka")["signifies"] == "father"


def test_karaka_tie_warns():
    lons = {"Sun": 10.0, "Moon": 10.0 + 1.0 / 7200.0, "Mars": 300.1,
            "Mercury": 166.0, "Jupiter": 101.0, "Venus": 351.0,
            "Saturn": 202.0, "Rahu": 80.0, "Ketu": 260.0}
    table = jm.chara_karakas(lons, "seven")
    assert len(table["warnings"]) == 1
    assert "Sun" in table["warnings"][0] and "Moon" in table["warnings"][0]


def test_bad_scheme_raises():
    with pytest.raises(ValueError):
        jm.chara_karakas({"Sun": 10.0}, "nine")


def test_build_jaimini_end_to_end():
    result = jm.build_jaimini(**NASHIK)
    assert result["ephemeris_source"] == "swiss_ephemeris_data_files"
    assert len(result["arudha_padas"]) == 12
    assert result["arudha_lagna"]["pada"] == "A1"
    assert result["arudha_lagna"] == result["arudha_padas"][0]
    assert result["upapada"]["pada"] == "A12"
    assert result["upapada"] == result["arudha_padas"][11]
    assert result["upapada"]["signifies"] == "marriage and committed union"
    assert result["arudha_padas"][9]["signifies"] == "career, public deeds and reputation"
    # Result-first field order: placement fields lead each pada entry.
    assert list(result["arudha_padas"][0])[:5] == [
        "pada", "name", "signifies", "pada_sign", "pada_house_from_lagna"]
    # Pada houses are whole-sign from the Lagna sign.
    lagna_idx = SIGNS.index(result["lagna_sign"])
    for entry in result["arudha_padas"]:
        assert entry["pada_house_from_lagna"] == (SIGNS.index(entry["pada_sign"]) - lagna_idx) % 12 + 1
    # Karakamsha Swamsha equals the AK's D9 sign via the shared varga engine.
    jd = ep.to_jd(NASHIK["naive_local"], NASHIK["tz_name"])
    pos = ep.planet_positions(jd)
    spec = charts.resolve_varga("D9")
    for scheme in ("seven", "eight"):
        ak = result["karakamsha"][scheme]["atmakaraka"]
        swamsha, _ = charts.varga_sign(spec, pos[ak]["longitude"])
        assert result["karakamsha"][scheme]["swamsha_sign"] == SIGNS[swamsha]
    assert "lord_scheme" in result["conventions_used"]
    assert "arudha_rule" in result["conventions_used"]
