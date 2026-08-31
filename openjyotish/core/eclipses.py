"""Solar and lunar eclipse search with exact times and the sidereal eclipse point.

Layer 1 only: raw computed events, no interpretation. For a lunar eclipse the
point is the Moon's sidereal longitude at greatest eclipse; for a solar eclipse
it is the Sun's. All times come back in UT *and* the requested local timezone.
When a natal chart is supplied by the caller, the eclipse point's whole-sign
house from the natal Lagna and from the natal Moon is computed so readers can
place the event on a chart — mirroring get_current_transits.

Type conventions used here, calibrated against published eclipse data:

- Lunar eclipse type is derived from the *umbral magnitude* returned by
  `swe.lun_eclipse_how` (umbral >= 1 -> total, > 0 -> partial, == 0 -> the
  event is penumbral), because SWE's own return flag mislabels a clearly
  partial event (2025-09-07, umbral magnitude ~0.09) as total.
- Solar eclipse type is read from SWE's return flag bits
  (ECL_TOTAL/ECL_ANNULAR/ECL_PARTIAL), which match published classifications
  for every 2025-2028 solar eclipse checked.
"""

from __future__ import annotations

from datetime import date

import swisseph as swe

from . import ephemeris as ep

# SWE return-flag bits in this pyswisseph build (differ from the C header!):
#   ECL_TOTAL=4   ECL_ANNULAR=8   ECL_PARTIAL=16   ECL_ANNULAR_TOTAL=32   ECL_PENUMBRAL=64
_ECL_TOTAL = swe.ECL_TOTAL
_ECL_ANNULAR = swe.ECL_ANNULAR
_ECL_PARTIAL = swe.ECL_PARTIAL
_ECL_ANNULAR_TOTAL = swe.ECL_ANNULAR_TOTAL

# Contact-time slots inside SWE's tret tuple. "greatest" is always present;
# the others are 0 when the phase does not occur.
_LUNAR_CONTACT_SLOTS = [
    ("penumbral_begin", 6),
    ("partial_begin", 2),
    ("greatest", 0),
    ("partial_end", 3),
    ("penumbral_end", 7),
    ("totality_begin", 4),
    ("totality_end", 5),
]
_SOLAR_CONTACT_SLOTS = [
    ("partial_begin", 2),
    ("greatest", 0),
    ("partial_end", 3),
    ("totality_begin", 4),
    ("totality_end", 5),
]


def _solar_type(flags: int) -> str:
    if flags & _ECL_ANNULAR_TOTAL:
        return "annular_total"
    if flags & _ECL_ANNULAR and flags & _ECL_TOTAL:
        return "annular_total"
    if flags & _ECL_TOTAL:
        return "total"
    if flags & _ECL_ANNULAR:
        return "annular"
    if flags & _ECL_PARTIAL:
        return "partial"
    return "unknown"


def _lunar_type(umbral_mag: float) -> str:
    if umbral_mag >= 1.0:
        return "total"
    if umbral_mag > 0.0:
        return "partial"
    return "penumbral"


def _contacts(tret, slots: list) -> dict:
    out = {}
    for name, idx in slots:
        jd = tret[idx]
        if jd and jd > 0:
            out[name] = round(jd, 8)
    return out


def _point(pmax_jd: float, kind: str, ayanamsha: str, node_type: str,
           true_positions: bool) -> dict:
    """Sidereal eclipse point: Sun for solar, Moon for lunar. Strips the
    positional nakshatra fields that are only meaningful for moving bodies'
    internal bookkeeping (matches natal chart output style)."""
    body = "Sun" if kind == "solar" else "Moon"
    pos = ep.planet_positions(pmax_jd, ayanamsha=ayanamsha, node_type=node_type,
                              true_positions=true_positions)[body]
    lon = pos["longitude"]
    nks = ep.nakshatra_of(lon)
    nks.pop("index_zero_based", None)
    nks.pop("fraction_elapsed", None)
    return {
        "body": body,
        "longitude": round(lon, 6),
        "sign": ep.sign_of(lon)["name"],
        "degree_in_sign": round(ep.sign_of(lon)["degree_in_sign"], 6),
        "degree_in_sign_dms": ep.dms(ep.sign_of(lon)["degree_in_sign"]),
        "nakshatra": nks,
    }


def _lunar_event(pmax_jd, tret, flags, tz_name, ayanamsha, node_type, true_positions):
    # `how` requires a geopos tuple; magnitude/saros are geographic-position
    # independent, so pass a neutral reference (0°E, 0°N, sea level).
    ret, attr = swe.lun_eclipse_how(pmax_jd, (0.0, 0.0, 0.0), flags)
    umbral_mag = attr[0]
    penumbral_mag = attr[1]
    saros_series = int(attr[9]) if attr[9] and attr[9] != -99999999 else None
    saros_member = int(attr[10]) if attr[10] and attr[10] != -99999999 else None
    return {
        "kind": "lunar",
        "type": _lunar_type(umbral_mag),
        "julian_day_ut_greatest": round(pmax_jd, 8),
        "greatest_ut": ep.jd_to_datetime_utc(pmax_jd).isoformat(),
        "greatest_local": ep.jd_to_local(pmax_jd, tz_name).isoformat(),
        "contacts_ut": _contacts(tret, _LUNAR_CONTACT_SLOTS),
        "contacts_local": {
            name: ep.jd_to_local(jd, tz_name).isoformat()
            for name, jd in _contacts(tret, _LUNAR_CONTACT_SLOTS).items()
        },
        "magnitudes": {
            "umbral": round(umbral_mag, 6),
            "penumbral": round(penumbral_mag, 6),
        },
        "saros": {"series": saros_series, "member": saros_member},
        "point": _point(pmax_jd, "lunar", ayanamsha, node_type, true_positions),
    }


def _solar_event(pmax_jd, tret, retflag, flags, tz_name, ayanamsha, node_type,
                 true_positions):
    contacts = _contacts(tret, _SOLAR_CONTACT_SLOTS)
    return {
        "kind": "solar",
        "type": _solar_type(retflag),
        "julian_day_ut_greatest": round(pmax_jd, 8),
        "greatest_ut": ep.jd_to_datetime_utc(pmax_jd).isoformat(),
        "greatest_local": ep.jd_to_local(pmax_jd, tz_name).isoformat(),
        "contacts_ut": contacts,
        "contacts_local": {
            name: ep.jd_to_local(jd, tz_name).isoformat()
            for name, jd in contacts.items()
        },
        "point": _point(pmax_jd, "solar", ayanamsha, node_type, true_positions),
    }


def next_eclipses(
    start_local,
    tz_name: str,
    ayanamsha: str = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
    count: int = 4,
) -> dict:
    """The next `count` solar/lunar eclipses at or after `start_local`.

    Pure computation; `latitude`/`longitude` are not needed because eclipse
    times and the sidereal point are global phenomena (the location of the
    requester affects only local visibility of the contact times, which is
    not part of this Layer-1 scope).
    """
    if not 1 <= count <= 20:
        raise ValueError("count must be between 1 and 20")
    aya_key, _, _ = ep.resolve_ayanamsha(ayanamsha)
    flags = ep.flags(true_positions)
    jd = ep.to_jd(start_local, tz_name)
    events = []
    while len(events) < count:
        try:
            lret, ltret = swe.lun_eclipse_when(jd, flags)
        except swe.Error:
            ltret = None
        try:
            sret, stret = swe.sol_eclipse_when_glob(jd, flags)
        except swe.Error:
            stret = None
        lmax = ltret[0] if ltret else None
        smax = stret[0] if stret else None
        if lmax is None and smax is None:
            break  # unreachable for any realistic jd; defensive
        if lmax is not None and (smax is None or lmax < smax):
            events.append(_lunar_event(lmax, ltret, flags, tz_name, aya_key,
                                       node_type, true_positions))
            jd = lmax + 0.001
        else:
            events.append(_solar_event(smax, stret, sret, flags, tz_name, aya_key,
                                       node_type, true_positions))
            jd = smax + 0.001
    return {"events": events}


def eclipses_on_date(
    local_date,
    tz_name: str,
    ayanamsha: str = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
) -> dict:
    """Any eclipse whose greatest moment falls on `local_date` (a civil day in
    the given timezone). Used for day-level queries (e.g. 'was there an eclipse
    on this panchang day?'). Returns {"events": [...]} with at most one entry."""
    start = _dt_for_date(local_date, tz_name)
    # Search from the day's 00:00 up to the next day's 23:59:59.
    from datetime import datetime, timedelta

    window_end_jd = ep.to_jd(start + timedelta(days=1, seconds=-1), tz_name)
    result = next_eclipses(start, tz_name, ayanamsha, node_type, true_positions, count=1)
    events = []
    for ev in result["events"]:
        if ev["julian_day_ut_greatest"] <= window_end_jd:
            events.append(ev)
    return {"events": events}


def _dt_for_date(local_date, tz_name):
    from datetime import datetime

    if hasattr(local_date, "hour"):
        return local_date
    d = local_date if isinstance(local_date, date) else date.fromisoformat(str(local_date))
    return datetime(d.year, d.month, d.day, 0, 0, 0)