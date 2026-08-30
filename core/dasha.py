"""Vimshottari dasha computation: mahadasha -> antardasha -> pratyantardasha.

Conventions (surfaced in every response's conventions_used block):
- 120-year cycle anchored to the Moon's natal nakshatra lord.
- One Vimshottari year = 365.25 days (solar), the most widely used convention.
- Period math runs in continuous UT from the birth moment; boundary dates are
  rendered in the caller's timezone without re-deriving through wall-clock
  round-trips (DST-safe).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core import ephemeris as ep
from core.constants import (
    VIMSHOTTARI_SEQUENCE,
    VIMSHOTTARI_YEARS,
    normalize_deg,
)

YEAR_DAYS = 365.25
CYCLE_YEARS = sum(VIMSHOTTARI_YEARS.values())  # == 120

_LEVEL_LABELS = ["mahadasha", "antardasha", "pratyantardasha", "sookshma"]


def _nakshatra_fraction(moon_longitude: float) -> tuple[int, float]:
    """(nakshatra_index_zero_based, fraction_of_nakshatra_elapsed)."""
    span = 360.0 / 27.0
    lon = normalize_deg(moon_longitude)
    idx = int(lon // span)
    return idx, (lon - idx * span) / span


def _sequence_from(lord: str) -> list[str]:
    """The nine Vimshottari lords in order starting at `lord`."""
    start = VIMSHOTTARI_SEQUENCE.index(lord)
    return [VIMSHOTTARI_SEQUENCE[(start + i) % 9] for i in range(9)]


def _add_period(lord: str, start_jd: float, days: float, depth: int, tz_name: str) -> dict:
    entry = {
        "lord": lord,
        "_start_jd": start_jd,
        "_end_jd": start_jd + days,
        "start_local": ep.jd_to_local(start_jd, tz_name).isoformat(),
        "end_local": ep.jd_to_local(start_jd + days, tz_name).isoformat(),
    }
    if depth > 0:
        cursor = start_jd
        subs = []
        for sub_lord in _sequence_from(lord):
            sub_days = days * VIMSHOTTARI_YEARS[sub_lord] / CYCLE_YEARS
            subs.append(_add_period(sub_lord, cursor, sub_days, depth - 1, tz_name))
            cursor += sub_days
        entry["sub_periods"] = subs
    return entry


def find_current_period(tree: dict, reference_local: datetime, tz_name: str) -> dict | None:
    """Deepest active period chain at a reference moment, from a built tree."""
    ref_jd = ep.to_jd(reference_local.replace(tzinfo=None), tz_name)

    def bounds(period: dict) -> tuple[float, float]:
        if "_start_jd" in period:
            return period["_start_jd"], period["_end_jd"]
        start = datetime.fromisoformat(period["start_local"])
        end = datetime.fromisoformat(period["end_local"])
        return (start.timestamp() / 86400.0 + 2440587.5,
                end.timestamp() / 86400.0 + 2440587.5)

    def walk(periods: list) -> list[dict]:
        for p in periods:
            start_jd, end_jd = bounds(p)
            if start_jd <= ref_jd < end_jd:
                deeper = walk(p.get("sub_periods", []))
                return [p] + deeper
        return []

    chain = walk(tree["mahadashas"])
    if not chain:
        return None
    return {
        "reference_local": reference_local.isoformat() if reference_local.tzinfo is None
        else reference_local.isoformat(),
        "chain": [
            {
                "level": _LEVEL_LABELS[level],
                "lord": period["lord"],
                "start_local": period["start_local"],
                "end_local": period["end_local"],
            }
            for level, period in enumerate(chain)
        ],
        "path": " > ".join(p["lord"] for p in chain),
    }


def _strip_internal(node):
    """Remove private JD bookkeeping keys recursively."""
    if isinstance(node, dict):
        return {
            k: _strip_internal(v)
            for k, v in node.items()
            if not k.startswith("_")
        }
    if isinstance(node, list):
        return [_strip_internal(v) for v in node]
    return node


def _filter_periods_by_date(periods: list, start_date: datetime | None,
                            end_date: datetime | None, tz_name: str) -> list:
    """Filter periods to those overlapping with [start_date, end_date]."""
    start_jd = ep.to_jd(start_date, tz_name) if start_date else None
    end_jd = ep.to_jd(end_date, tz_name) if end_date else None

    def overlaps(p: dict) -> bool:
        s = p["_start_jd"]
        e = p["_end_jd"]
        if start_jd is not None and e <= start_jd:
            return False
        if end_jd is not None and s >= end_jd:
            return False
        return True

    filtered = []
    for p in periods:
        if overlaps(p):
            new_p = dict(p)
            if "sub_periods" in new_p:
                new_p["sub_periods"] = _filter_periods_by_date(
                    new_p["sub_periods"], start_date, end_date, tz_name)
            filtered.append(new_p)
    return filtered


def build_vimshottari_dasha(
    naive_local: datetime,
    tz_name: str,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
    levels: int = 3,
    reference_local: datetime | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    """Vimshottari tree from the natal Moon, plus optional current chain.

    `levels` controls nesting depth: 1 = mahadasha only, 2 = + antardasha,
    3 = + pratyantardasha, 4 = + sookshma. Lower levels shrink the response for
    callers that only need the coarse periods.

    Periods are emitted as their full absolute windows (a period running at
    birth shows its complete span, including time before birth); the entries
    running at birth additionally carry a `running_at_birth` marker.
    """
    if levels not in (1, 2, 3, 4):
        raise ValueError("levels must be one of 1 (mahadasha), 2 (+antardasha), "
                         "3 (+pratyantardasha), 4 (+sookshma)")
    aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)
    jd = ep.to_jd(naive_local, tz_name)
    positions = ep.planet_positions(jd, ayanamsha=aya_key, node_type=node_type,
                                    true_positions=true_positions)
    moon_lon = positions["Moon"]["longitude"]
    naks_idx, fraction = _nakshatra_fraction(moon_lon)
    starting_lord = ep.nakshatra_of(moon_lon)["lord"]

    balance_years = VIMSHOTTARI_YEARS[starting_lord] * (1.0 - fraction)
    md_depth = levels - 1

    # Absolute start of the mahadasha currently running at birth:
    # it began (full_years - balance_years) before the birth moment.
    first_full_days = VIMSHOTTARI_YEARS[starting_lord] * YEAR_DAYS
    first_start_jd = jd + balance_years * YEAR_DAYS - first_full_days

    mahadashas: list[dict] = []
    cursor = first_start_jd
    for lord in _sequence_from(starting_lord):
        full_days = VIMSHOTTARI_YEARS[lord] * YEAR_DAYS
        entry = _add_period(lord, cursor, full_days, md_depth, tz_name)
        if cursor <= jd < cursor + full_days:
            entry["running_at_birth"] = True
            entry["balance_at_birth"] = {
                "years": round(balance_years, 6),
                "note": (
                    f"{lord} mahadasha was already running at birth "
                    f"({fraction:.4%} of {starting_lord}'s nakshatra had "
                    f"elapsed; {balance_years:.4f} years remain)"
                ),
            }
        mahadashas.append(entry)
        cursor += full_days

    tree: dict = {
        "input": {
            "datetime_local": naive_local.isoformat(),
            "timezone": tz_name,
            "latitude": latitude,
            "longitude": longitude,
        },
        "julian_day_ut": round(jd, 8),
        "ephemeris_source": ep.ephemeris_source(),
        "natal_moon": {
            "longitude": round(moon_lon, 6),
            "nakshatra_index_one_based": naks_idx + 1,
            "fraction_elapsed": round(fraction, 8),
        },
        "conventions_used": {
            "dasha_system": "Vimshottari",
            "dasha_seed": "Moon's natal nakshatra lord",
            "year_length_days": YEAR_DAYS,
            "sub_period_rule": (
                "antardasha/pratyantardasha always use full proportional "
                "lengths of their parent period; only periods running at "
                "birth appear truncated in effect"
            ),
            "ayanamsha": {"key": aya_key, "name": aya_label, "value_degrees": round(ep.ayanamsha_value(jd, aya_key), 6)},
            "node_type": node_type,
            "position_type": "true" if true_positions else "apparent",
            "boundary_rendering": f"ISO-8601 local time ({tz_name})",
        },
        "mahadashas": mahadashas,
    }

    if reference_local is not None:
        tree["current_periods"] = find_current_period(tree, reference_local, tz_name)

    if start_date is not None or end_date is not None:
        tree["mahadashas"] = _filter_periods_by_date(tree["mahadashas"], start_date, end_date, tz_name)

    return _strip_internal(tree)
