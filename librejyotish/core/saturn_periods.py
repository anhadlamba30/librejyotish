"""Saturn transit periods measured from the natal Moon (Layer 1: raw dates only).

Covers the classical Moon-relative Saturn transits:
- Sade Sati: Saturn in the 12th (rising), 1st (peak) and 2nd (setting)
  whole-sign from the natal Moon sign (~7.5 years per cycle).
- Dhaiya (small panoti): Saturn in the 4th (Ardhashtama, also called Kantaka
  Shani) and the 8th (Ashtama Shani) from the natal Moon (~2.5 years each).

Conventions (surfaced in every response's conventions_used block):
- Reference point is the natal Moon sign only. Lagna-relative readings and
  the 10th-from-Moon Kantaka variant belong to other lineages and are NOT
  reported here.
- Period boundaries are whole-sign sidereal ingress instants of Saturn,
  refined by bisection to ~30 minutes. Retrograde re-entries are listed as
  separate contiguous spans (phases genuinely interleave, e.g. a peak span
  can resume after a setting span starts) — spans are never merged.
- No favorable/unfavorable judgment is attached; dasha context decides what
  a transit can deliver, and dashas live in get_vimshottari_dasha.
"""

from __future__ import annotations

import datetime as _dt

import swisseph as swe

from . import charts, ephemeris as ep
from .constants import SIGNS, normalize_deg

DAY = 1.0
YEAR_DAYS = 365.25  # same civil-year convention as the dasha module
REFINE_TOLERANCE_JD = 0.5 / 24.0  # ~30 minutes

SATURN_PERIOD_CONVENTIONS = (
    "Moon-relative whole-sign Saturn transits: Sade Sati = Saturn in 12th "
    "(rising) / 1st (peak) / 2nd (setting) from natal Moon; Dhaiya = 4th "
    "(Ardhashtama/Kantaka) / 8th (Ashtama). 10th-from-Moon Kantaka and "
    "Lagna-relative variants not reported. Ingress instants refined to "
    "~30 min; retrograde re-entries listed as separate spans."
)


def _category_for(house_from_moon: int) -> str | None:
    return {
        12: "sade_sati_rising",
        1: "sade_sati_peak",
        2: "sade_sati_setting",
        4: "dhaiya_4th",
        8: "dhaiya_8th",
    }.get(house_from_moon)


def saturn_longitude(jd: float, ayanamsha: str | None = "lahiri",
                     true_positions: bool = False) -> float:
    """Sidereal Saturn longitude at JD (UT)."""
    ep.require_coverage(jd)
    _key, mode, _ = ep.resolve_ayanamsha(ayanamsha)
    swe.set_sid_mode(mode)
    pos, retflag = swe.calc_ut(jd, swe.SATURN, ep.flags(true_positions))
    ep.check_swiss_flag(retflag, jd)
    return normalize_deg(pos[0])


def saturn_sign(jd: float, ayanamsha: str | None = "lahiri",
                true_positions: bool = False) -> int:
    """Whole-sign index (0..11) of sidereal Saturn at JD (UT)."""
    return int(saturn_longitude(jd, ayanamsha, true_positions) // 30)


def _refine_ingress(jd_lo: float, jd_hi: float, sign_lo: int,
                    ayanamsha: str | None, true_positions: bool) -> float:
    """Bisect a same-sign -> new-sign day bracket to ~30-minute precision."""
    while jd_hi - jd_lo > REFINE_TOLERANCE_JD:
        mid = (jd_lo + jd_hi) / 2.0
        if saturn_sign(mid, ayanamsha, true_positions) == sign_lo:
            jd_lo = mid
        else:
            jd_hi = mid
    return jd_hi


def find_saturn_ingresses(jd_start: float, jd_end: float,
                          ayanamsha: str | None = "lahiri",
                          true_positions: bool = False) -> list[tuple[float, int]]:
    """All (ingress_jd_ut, new_sign_index) with jd_start < ingress <= jd_end."""
    ep.require_coverage(jd_start, label="window start")
    ep.require_coverage(jd_end - 1e-9, label="window end")
    ingresses: list[tuple[float, int]] = []
    prev_jd = jd_start
    prev_sign = saturn_sign(prev_jd, ayanamsha, true_positions)
    jd = jd_start + DAY
    while jd < jd_end:
        sign = saturn_sign(jd, ayanamsha, true_positions)
        if sign != prev_sign:
            refined = _refine_ingress(prev_jd, jd, prev_sign, ayanamsha, true_positions)
            ingresses.append((refined, sign))
            prev_sign = sign
            prev_jd = refined
        else:
            prev_jd = jd
        jd = prev_jd + DAY
        # Guard the tail so the last bracket never overshoots the window.
        if jd > jd_end:
            break
    return ingresses


def build_saturn_periods(
    naive_local,
    tz_name: str,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    true_positions: bool = False,
    reference_local=None,
    lookback_years: float = 2.0,
    lookahead_years: float = 30.0,
) -> dict:
    """Saturn periods around a reference moment for a birth chart.

    Scans [reference - lookback, reference + lookahead] for sidereal Saturn
    sign ingresses and classifies each contiguous span from the natal Moon.
    """
    for label, value in (("lookback_years", lookback_years),
                         ("lookahead_years", lookahead_years)):
        if not 0 <= float(value) <= 120:
            raise ValueError(f"{label} must be within [0, 120] years")
    lookback_years = float(lookback_years)
    lookahead_years = float(lookahead_years)

    jd_birth = ep.to_jd(naive_local, tz_name)
    source = ep.ephemeris_source()
    aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)
    natal = charts.build_natal_chart(naive_local, tz_name, latitude, longitude,
                                     aya_key, true_positions=true_positions)
    moon_lon = next(p["longitude"] for p in natal["planets"] if p["name"] == "Moon")
    moon_sign = int(normalize_deg(moon_lon) // 30)

    ref_jd = ep.to_jd(reference_local, tz_name)
    jd_start = ref_jd - lookback_years * YEAR_DAYS
    jd_end = ref_jd + lookahead_years * YEAR_DAYS
    # Clamp the scan to the bundled ephemeris coverage instead of failing it.
    jd_start = max(jd_start, ep.EPHEMERIS_MIN_JD)
    jd_end = min(jd_end, ep.EPHEMERIS_MAX_JD - 1e-6)
    if jd_end <= jd_start:
        raise ValueError("scan window is empty after ephemeris-range clamping")

    ingresses = find_saturn_ingresses(jd_start, jd_end, aya_key, true_positions)

    spans: list[dict] = []
    span_sign = saturn_sign(jd_start, aya_key, true_positions)
    span_start = jd_start
    span_clipped_start = True
    for ing_jd, new_sign in ingresses:
        spans.append((span_sign, span_start, ing_jd, span_clipped_start, False))
        span_sign, span_start, span_clipped_start = new_sign, ing_jd, False
    spans.append((span_sign, span_start, jd_end, span_clipped_start, True))

    periods = []
    for sign, start, end, clipped_start, clipped_end in spans:
        house = (sign - moon_sign) % 12 + 1
        category = _category_for(house)
        if category is None:
            continue
        periods.append({
            "category": category,
            "saturn_sign": SIGNS[sign],
            "house_from_natal_moon": house,
            "start_local": ep.jd_to_local(start, tz_name).isoformat(),
            "end_local": ep.jd_to_local(end, tz_name).isoformat(),
            "clipped_start": clipped_start,
            "clipped_end": clipped_end,
        })

    ref_sign = saturn_sign(ref_jd, aya_key, true_positions)
    ref_house = (ref_sign - moon_sign) % 12 + 1
    ref_category = _category_for(ref_house)
    current_period = None
    if ref_category is not None:
        now = ep.jd_to_local(ref_jd, tz_name)
        for p in periods:
            start = _dt.datetime.fromisoformat(p["start_local"])
            end = _dt.datetime.fromisoformat(p["end_local"])
            if start <= now < end:
                current_period = p
                break

    return {
        "input": {
            "birth_datetime_local": naive_local.isoformat(),
            "timezone": tz_name,
            "latitude": latitude,
            "longitude": longitude,
            "reference_local": ep.jd_to_local(ref_jd, tz_name).isoformat(),
            "lookback_years": lookback_years,
            "lookahead_years": lookahead_years,
            "window_start_local": ep.jd_to_local(jd_start, tz_name).isoformat(),
            "window_end_local": ep.jd_to_local(jd_end, tz_name).isoformat(),
        },
        "julian_day_ut_birth": round(jd_birth, 8),
        "julian_day_ut_reference": round(ref_jd, 8),
        "ephemeris_source": source,
        "conventions_used": {
            "zodiac": "sidereal",
            "ayanamsha": {"key": aya_key, "name": aya_label,
                           "value_degrees": round(ep.ayanamsha_value(ref_jd, aya_key), 6)},
            "position_type": "true" if true_positions else "apparent",
            "reference_point": {
                "key": "natal_moon_sign",
                "name": ("All houses counted whole-sign from the natal Moon sign "
                         f"({SIGNS[moon_sign]}); Lagna-relative variants not included"),
            },
            "categories": SATURN_PERIOD_CONVENTIONS,
            "interpretation": "none — raw transit date ranges only",
        },
        "natal_moon_sign": SIGNS[moon_sign],
        "current_status": {
            "reference_local": ep.jd_to_local(ref_jd, tz_name).isoformat(),
            "saturn_sign": SIGNS[ref_sign],
            "house_from_natal_moon": ref_house,
            "category": ref_category or "none",
            "current_period": current_period,
        },
        "periods": periods,
    }
