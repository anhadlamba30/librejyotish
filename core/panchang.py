"""Panchanga: the five limbs of the Vedic day.

All five elements are evaluated at a single anchor moment — local sunrise for
the requested date (falling back to local noon in polar cases where the sun
does not rise) — and that convention is reported in every response.
Sunrise/sunset use the Hindu convention (upper limb of the solar disc
crossing the true horizon, refraction included).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from core import ephemeris as ep
from core.constants import (
    END_TITHIS,
    MOVABLE_KARANAS,
    NAKSHATRAS,
    PAKSHAS,
    TITHIS,
    VARAS,
    YOGAS,
    normalize_deg,
)

KARANA_SPAN_DEG = 6.0


def _moon_sun_separation(jd: float, ayanamsha: str, true_positions: bool) -> tuple[float, float]:
    pos = ep.planet_positions(jd, ayanamsha=ayanamsha, true_positions=true_positions)
    moon = pos["Moon"]["longitude"]
    sun = pos["Sun"]["longitude"]
    return normalize_deg(moon - sun), normalize_deg(moon + sun)


def tithi_of(separation: float) -> dict:
    idx = int(separation // 12.0)          # 0..29
    paksha = PAKSHAS[0] if idx < 15 else PAKSHAS[1]
    within = idx % 15                       # 0..14
    if within == 14:
        name = END_TITHIS[0] if paksha == "Shukla" else END_TITHIS[1]
        number = 15
    else:
        number = within + 1
        name = TITHIS[within]
    return {
        "index_one_based": idx + 1,
        "number": number,
        "paksha": paksha,
        "name": f"{paksha} {name}",
    }


def yoga_of(sum_longitude: float) -> dict:
    span = 360.0 / 27.0
    idx = int(normalize_deg(sum_longitude) // span)
    return {"index_one_based": idx + 1, "name": YOGAS[idx]}


def karana_of(separation: float) -> dict:
    k = int(separation // KARANA_SPAN_DEG) + 1   # 1..60
    if k == 1:
        name = "Kimstughna"
    elif k <= 57:
        name = MOVABLE_KARANAS[(k - 2) % 7]
    elif k == 58:
        name = "Shakuni"
    elif k == 59:
        name = "Chatushpada"
    else:
        name = "Naga"
    return {"index_one_based": k, "name": name}


def vara_of(anchor_local: datetime) -> dict:
    # Weekday of the anchor (sunrise) date: the Jyotish day runs
    # sunrise -> next sunrise. Python's Monday=0 maps onto the
    # Sunday-first VARAS table via +1 mod 7.
    return {
        "name": VARAS[(anchor_local.weekday() + 1) % 7],
        "note": "weekday of the sunrise-anchored date; Jyotish vara runs sunrise to sunrise",
    }


def build_panchang(
    local_date: date,
    tz_name: str,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    true_positions: bool = False,
) -> dict:
    aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)
    tz = ZoneInfo(tz_name)

    riseset = ep.sunrise_sunset(local_date, tz_name, latitude, longitude)
    if riseset["sunrise"] is not None:
        anchor = datetime.fromisoformat(riseset["sunrise"])
        anchor_label = "sunrise"
    else:
        anchor = datetime(local_date.year, local_date.month, local_date.day, 12, tzinfo=tz)
        anchor_label = "local_noon"

    jd_anchor = ep.to_jd(anchor.replace(tzinfo=None), tz_name)
    sep, total = _moon_sun_separation(jd_anchor, aya_key, true_positions)
    moon_lon = ep.planet_positions(jd_anchor, ayanamsha=aya_key,
                                   true_positions=true_positions)["Moon"]["longitude"]
    nak = ep.nakshatra_of(moon_lon)

    return {
        "input": {
            "date": local_date.isoformat(),
            "timezone": tz_name,
            "latitude": latitude,
            "longitude": longitude,
        },
        "julian_day_ut_at_anchor": round(jd_anchor, 8),
        "ephemeris_source": ep.ephemeris_source(),
        "conventions_used": {
            "zodiac": "sidereal",
            "ayanamsha": {"key": aya_key, "name": aya_label,
                          "value_degrees": round(ep.ayanamsha_value(jd_anchor, aya_key), 6)},
            "position_type": "true" if true_positions else "apparent",
            "evaluation_anchor": (
                f"panchangangas computed at {anchor_label} on the requested date "
                f"({anchor.isoformat()}); each element changes later in the day"
            ),
            "sunrise_sunset_convention": (
                "upper limb of Sun's disc crossing the horizon, refraction included"
            ),
            "vara_convention": "civil weekday of the sunrise date",
        },
        "tithi": tithi_of(sep),
        "vara": vara_of(anchor),
        "nakshatra": {
            "name": nak["name"],
            "lord": nak["lord"],
            "pada": nak["pada"],
        },
        "yoga": yoga_of(total),
        "karana": karana_of(sep),
        "sunrise": riseset["sunrise"],
        "sunset": riseset["sunset"],
    }
