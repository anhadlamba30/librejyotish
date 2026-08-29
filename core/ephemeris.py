"""Swiss Ephemeris wrapper: time conversion, ayanamsha handling, positions.

All functions are pure computation over (datetime, location) inputs — no I/O
beyond reading local ephemeris files if present. The ephemeris source actually
used is always reported so callers can surface it in `conventions_used`.
"""

from __future__ import annotations

import os
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

from core.constants import NAKSHATRAS, NAKSHATRA_LORD_CYCLE, SIGNS, normalize_deg

# Ephemeris files live here when downloaded; absent them we use the built-in
# Moshier ephemeris (no data files needed).
EPHE_PATH = Path(__file__).resolve().parent.parent / "data" / "ephe"

PLANET_BODIES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
}

AYANAMSHAS = {
    "lahiri": ("Lahiri (Chitrapaksha)", swe.SIDM_LAHIRI),
    "raman": ("Raman", swe.SIDM_RAMAN),
    "krishnamurti": ("Krishnamurti", swe.SIDM_KRISHNAMURTI),
    "fagan_bradley": ("Fagan-Bradley", swe.SIDM_FAGAN_BRADLEY),
}

HOUSE_SYSTEMS = {
    "whole_sign": ("Whole-sign houses from Lagna sign", b"W"),
}

_ephemeris_source: str | None = None


def _resolve_ephe_path() -> str:
    return str(EPHE_PATH.resolve())


def init_ephemeris() -> str:
    """Point swisseph at bundled files if available, else Moshier fallback.

    Returns a machine-readable label of the source in use.
    """
    global _ephemeris_source
    ephe_path = _resolve_ephe_path()
    swe.set_ephe_path(ephe_path)
    # sepl.se / sepl_18.se1 presence indicates Swiss Ephemeris files.
    has_files = any(
        name.startswith("sepl") for name in os.listdir(ephe_path)
    ) if os.path.isdir(ephe_path) else False
    _ephemeris_source = (
        "swiss_ephemeris_data_files" if has_files else "moshier_builtin"
    )
    if not has_files:
        warnings.warn(
            "Swiss Ephemeris data files not found in data/ephe/. Falling back to "
            "the less precise built-in Moshier ephemeris. Run "
            "`scripts/download_ephe.py` once to enable full Swiss Ephemeris precision.",
            stacklevel=2,
        )
    return _ephemeris_source


def ephemeris_source() -> str:
    return _ephemeris_source or init_ephemeris()


def _flags(true_positions: bool = False) -> int:
    base = swe.FLG_SPEED | swe.FLG_SIDEREAL
    if _ephemeris_source == "swiss_ephemeris_data_files":
        base |= swe.FLG_SWIEPH
    else:
        base |= swe.FLG_MOSEPH
    if true_positions:
        base |= swe.FLG_TRUEPOS
    return base


def flags(true_positions: bool = False) -> int:
    """Public accessor for the SWE calc flags matching the active source."""
    return _flags(true_positions)


def to_jd(naive_local: datetime, tz_name: str) -> float:
    """Convert a naive local datetime in `tz_name` to Julian Day (UT)."""
    tz = ZoneInfo(tz_name)
    aware = naive_local.replace(tzinfo=tz)
    utc = aware.astimezone(timezone.utc)
    hour = utc.hour + utc.minute / 60 + utc.second / 3600 + utc.microsecond / 3.6e9
    return swe.julday(utc.year, utc.month, utc.day, hour)


def jd_to_datetime_utc(jd: float) -> datetime:
    """Inverse of to_jd on the UTC axis."""
    y, m, d, hour = swe.revjul(jd)
    total_seconds = round(hour * 3600)
    base = datetime(int(y), int(m), int(d), tzinfo=timezone.utc)
    return base + timedelta(seconds=total_seconds)


def jd_to_local(jd: float, tz_name: str) -> datetime:
    """Convert a Julian Day (UT) into an aware datetime in `tz_name`."""
    return jd_to_datetime_utc(jd).astimezone(ZoneInfo(tz_name))


def resolve_ayanamsha(name: str | None) -> tuple[str, int, str]:
    """Return (canonical_name, swe_sid_mode, human_label) for an ayanamsha key."""
    key = (name or "lahiri").lower()
    if key not in AYANAMSHAS:
        raise ValueError(
            f"Unknown ayanamsha '{name}'. Supported: {sorted(AYANAMSHAS)}"
        )
    label, mode = AYANAMSHAS[key]
    return key, mode, label


def ayanamsha_value(jd: float, ayanamsha: str | None = None) -> float:
    """Ayanamsha offset in degrees at JD (UT), with the sid mode set globally."""
    _, mode, _ = resolve_ayanamsha(ayanamsha)
    swe.set_sid_mode(mode)
    return swe.get_ayanamsa_ut(jd)


def planet_positions(
    jd: float,
    ayanamsha: str | None = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
) -> dict:
    """Sidereal longitudes/speeds for Sun..Saturn plus Rahu and Ketu.

    `true_positions=True` requests geometric true positions (SEFLG_TRUEPOS,
    the JHora-school convention); default is apparent positions, which is
    what most software including astro.com reports.

    Returns {planet: {"longitude": deg, "speed": deg/day, "retrograde": bool}}
    """
    key, mode, _ = resolve_ayanamsha(ayanamsha)
    swe.set_sid_mode(mode)
    node_key = node_type.lower()
    if node_key not in ("true", "mean"):
        raise ValueError(f"node_type must be 'true' or 'mean', got '{node_type}'")

    bodies = dict(PLANET_BODIES)
    bodies["Rahu"] = swe.TRUE_NODE if node_key == "true" else swe.MEAN_NODE
    # Ketu is always Rahu + 180 by definition; computed below.

    out: dict = {}
    flags = _flags(true_positions)
    for name, body in bodies.items():
        pos, _rf = swe.calc_ut(jd, body, flags)
        lon, speed = pos[0], pos[3]
        retro = speed < 0 and name != "Ketu"
        out[name] = {
            "longitude": normalize_deg(lon),
            "speed": speed,
            "retrograde": bool(retro),
        }
    rahu = out["Rahu"]
    ketu_speed = rahu["speed"]
    out["Ketu"] = {
        "longitude": normalize_deg(rahu["longitude"] + 180.0),
        "speed": ketu_speed,
        "retrograde": True,  # nodes move counter-zodiacally
    }
    return out


def ascendant_and_mc(
    jd: float,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    house_system: str = "whole_sign",
    true_positions: bool = False,
) -> tuple[float, float]:
    """Sidereal Ascendant and MC longitudes for the given time/place."""
    key, mode, _ = resolve_ayanamsha(ayanamsha)
    swe.set_sid_mode(mode)
    if house_system not in HOUSE_SYSTEMS:
        raise ValueError(
            f"Unsupported house system '{house_system}'. "
            f"Supported: {sorted(HOUSE_SYSTEMS)}"
        )
    _, hsys = HOUSE_SYSTEMS[house_system]
    cusps, ascmc = swe.houses_ex(jd, latitude, longitude, hsys, _flags(true_positions))
    return normalize_deg(ascmc[0]), normalize_deg(ascmc[1])


def bhava_cusps(
    jd: float,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    true_positions: bool = False,
) -> list[float]:
    """Sidereal Placidus house cusps (12 values, house 1 first).

    Used only by Shadbala's Dig Bana, which is defined against actual bhava
    madhya (cusp) longitudes rather than whole-sign houses.
    """
    key, mode, _ = resolve_ayanamsha(ayanamsha)
    swe.set_sid_mode(mode)
    cusps, _ascmc = swe.houses_ex(jd, latitude, longitude, b"P", _flags(true_positions))
    return [normalize_deg(c) for c in cusps[:12]]


def sunrise_sunset(
    local_date: date,
    tz_name: str,
    latitude: float,
    longitude: float,
) -> dict:
    """Sunrise/sunset using the Hindu convention (upper limb, with refraction).

    Returns {"sunrise": iso_or_None, "sunset": iso_or_None} in local time;
    None where the event does not occur (polar day/night).
    """
    jd_start = to_jd(datetime(local_date.year, local_date.month, local_date.day, 0, 0), tz_name)
    geopos = (longitude, latitude, 0.0)
    result = {}
    for label, flag in (
        ("sunrise", swe.CALC_RISE | swe.BIT_HINDU_RISING),
        ("sunset", swe.CALC_SET | swe.BIT_HINDU_RISING),
    ):
        try:
            res, tret = swe.rise_trans(jd_start, swe.SUN, flag, geopos)
            if res >= 0 and tret and tret[0] > 0:
                result[label] = jd_to_datetime_utc(tret[0]).astimezone(
                    ZoneInfo(tz_name)
                ).isoformat()
            else:
                result[label] = None
        except (swe.Error, RuntimeError):
            result[label] = None
    return result


def nakshatra_of(lon: float) -> dict:
    """Nakshatra name/lord/pada for a sidereal longitude."""
    span = 360.0 / 27.0
    idx = int(normalize_deg(lon) // span)
    within = normalize_deg(lon) - idx * span
    pada = int(within // (span / 4.0)) + 1
    lord = NAKSHATRA_LORD_CYCLE[idx % 9]
    return {
        "name": NAKSHATRAS[idx],
        "lord": lord,
        "pada": pada,
        "index_zero_based": idx,
        "fraction_elapsed": within / span,
    }


def sign_of(lon: float) -> dict:
    si = int(normalize_deg(lon) // 30.0)
    return {"index_one_based": si + 1, "name": SIGNS[si], "degree_in_sign": normalize_deg(lon) - si * 30.0}


def dms(deg: float) -> str:
    """Format degrees as D°MM'SS"."""
    deg = normalize_deg(deg)
    d = int(deg)
    minutes_full = (deg - d) * 60
    m = int(minutes_full)
    s = (minutes_full - m) * 60
    return f"{d}\u00b0{m:02d}'{s:04.1f}\""
