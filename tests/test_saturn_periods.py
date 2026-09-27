"""Tests for core/saturn_periods.py: ingress scan and Moon-relative phases.

Ingress pins use widely published sidereal (Lahiri) Saturn ingresses with a
+/-1.5 day tolerance for calculator/bisection differences:
- Capricorn 2020-01-24, Aquarius 2022-04-29, Pisces 2025-03-29, Aries 2027-06-03.
Runs via `conda run -n librejyotish python -m pytest tests/test_saturn_periods.py`.
"""

from datetime import datetime, timedelta

from librejyotish.core import ephemeris as ep
from librejyotish.core import saturn_periods as sp

TOL = timedelta(days=1.5)

NASHIK_BIRTH = dict(naive_local=datetime(1994, 3, 21, 14, 32),
                    tz_name="Asia/Kolkata", latitude=19.9975, longitude=73.7898)
# 1994-03-21 Nashik natal Moon is in Gemini.


def _ingress_near(year: int, month: int, day: int, want_sign: str) -> float:
    anchor = ep.to_jd(datetime(year, month, day, 12, 0), "Asia/Kolkata")
    ingresses = sp.find_saturn_ingresses(anchor - 20, anchor + 20)
    hits = [jd for jd, sign in ingresses
            if ep.sign_of(sp.saturn_longitude(jd))["name"] == want_sign
            and abs(jd - anchor) < 20]
    assert hits, f"no ingress into {want_sign} near {year}-{month}-{day}"
    return hits[0]


def _jd_to_utc(jd: float) -> datetime:
    return ep.jd_to_datetime_utc(jd).replace(tzinfo=None)


def test_ingress_capricorn_2020():
    jd = _ingress_near(2020, 1, 24, "Capricorn")
    assert abs(_jd_to_utc(jd) - datetime(2020, 1, 24, 12)) < TOL


def test_ingress_aquarius_2022():
    jd = _ingress_near(2022, 4, 29, "Aquarius")
    assert abs(_jd_to_utc(jd) - datetime(2022, 4, 29, 12)) < TOL


def test_ingress_pisces_2025():
    jd = _ingress_near(2025, 3, 29, "Pisces")
    assert abs(_jd_to_utc(jd) - datetime(2025, 3, 29, 12)) < TOL


def test_ingress_aries_2027():
    jd = _ingress_near(2027, 6, 3, "Aries")
    assert abs(_jd_to_utc(jd) - datetime(2027, 6, 3, 12)) < TOL


def test_gemini_moon_peak_and_current_status():
    result = sp.build_saturn_periods(
        **NASHIK_BIRTH, reference_local=datetime(2033, 6, 1, 12, 0),
        lookback_years=1, lookahead_years=3)
    assert result["natal_moon_sign"] == "Gemini"
    assert result["current_status"]["category"] == "sade_sati_peak"
    assert result["current_status"]["saturn_sign"] == "Gemini"
    assert result["current_status"]["current_period"] is not None
    assert result["current_status"]["current_period"]["category"] == "sade_sati_peak"


def test_retrograde_split_spans_listed_separately():
    # Saturn's 2022 Aquarius ingress was followed by a retrograde dip back
    # into Capricorn: the 8th-from-Gemini-Moon Dhaiya must appear twice.
    result = sp.build_saturn_periods(
        **NASHIK_BIRTH, reference_local=datetime(2021, 6, 1, 12, 0),
        lookback_years=2, lookahead_years=3)
    eighths = [p for p in result["periods"]
               if p["category"] == "dhaiya_8th" and p["saturn_sign"] == "Capricorn"]
    assert len(eighths) == 2
    assert eighths[0]["end_local"][:10] == "2022-04-29"
    assert eighths[1]["start_local"][:10] == "2022-07-12"


def test_periods_sorted_and_disjoint():
    result = sp.build_saturn_periods(
        **NASHIK_BIRTH, reference_local=datetime(2026, 1, 1, 12, 0),
        lookback_years=6, lookahead_years=8)
    starts = [p["start_local"] for p in result["periods"]]
    assert starts == sorted(starts)
    for first, second in zip(result["periods"], result["periods"][1:]):
        assert first["end_local"] <= second["start_local"]


def test_tenth_from_moon_not_reported():
    # Saturn in Pisces is 10th from Gemini Moon: present in transits but with
    # no Saturn-period category (Kantaka-10th is out of scope for v1).
    result = sp.build_saturn_periods(
        **NASHIK_BIRTH, reference_local=datetime(2026, 1, 1, 12, 0),
        lookback_years=0, lookahead_years=1)
    assert result["current_status"]["category"] == "none"
    assert result["current_status"]["house_from_natal_moon"] == 10


def test_bad_window_raises():
    import pytest
    with pytest.raises(ValueError):
        sp.build_saturn_periods(**NASHIK_BIRTH,
                                reference_local=datetime(2026, 1, 1, 12, 0),
                                lookback_years=200, lookahead_years=1)
