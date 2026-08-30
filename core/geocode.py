"""Offline, deterministic place-string resolution for the computation tools.

The astronomical modules take numeric latitude/longitude; this module bridges
the gap from human place strings ("Nashik, India") to those numbers using the
bundled GeoNames-derived gazetteer (data/gazetteer/cities.csv). No network is
ever contacted at query time.

Resolution is deterministic: exact name -> exact asciiname -> exact
alternatename -> word-prefix on name/asciiname, within the highest matching
tier sorted by population, then name. Callers should treat a non-exact match
or an `ambiguous: true` result as a prompt to confirm with the user rather
than guessing.
"""

from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path

GAZETTEER = Path(__file__).resolve().parent.parent / "data" / "gazetteer" / "cities.csv"

_COUNTRY_CODE_REMAP = None  # reserved; country codes used as-is


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _fold(text: str) -> str:
    return _ascii(text).casefold().strip()


@lru_cache(maxsize=1)
def _load() -> list[dict]:
    """Rows of the bundled gazetteer, cached for the process lifetime."""
    if not GAZETTEER.is_file():
        raise FileNotFoundError(
            f"bundled gazetteer missing at {GAZETTEER}; run "
            "`scripts/build_gazetteer.py` to create it"
        )
    rows = []
    with GAZETTEER.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row["population"] = int(row["population"] or 0)
            row["latitude"] = float(row["latitude"])
            row["longitude"] = float(row["longitude"])
            rows.append(row)
    return rows


def _split_query(query: str) -> tuple[str, str | None]:
    """Split 'Nashik, India' into (place, country_code_hint_or_None)."""
    parts = [p.strip() for p in query.split(",") if p.strip()]
    if not parts:
        raise ValueError("place must be a non-empty string")
    place = parts[0]
    valid_countries = frozenset(r["country_code"] for r in _load())
    hint = None
    for part in parts[1:]:
        code = part.upper().strip()
        if code in valid_countries:
            hint = code  # last country-like token wins ("Nashik, MH, India")
    return place, hint


def _search(q: str, rows: list[dict], country_code: str | None,
            limit: int) -> dict:
    """Run the deterministic tiered search against an optionally filtered rowws."""
    tiers = [  # (tier_name, predicate(row) -> bool)
        ("exact_name", lambda r, q=q: _fold(r["name"]) == q),
        ("exact_ascii", lambda r, q=q: _fold(r["asciiname"]) == q),
        ("exact_alias", lambda r, q=q: q in (_fold(a) for a in r["alternatenames"].split(","))),
        ("prefix_name", lambda r, q=q: _fold(r["name"]).startswith(q) or _fold(r["asciiname"]).startswith(q)),
    ]

    pool_rows = rows
    if country_code:
        pool_rows = [r for r in rows if r["country_code"] == country_code]

    matched_tier = None
    candidates: list[dict] = []
    for tier_name, pred in tiers:
        pool = [r for r in pool_rows if pred(r)]
        if pool:
            matched_tier = tier_name
            pool.sort(key=lambda r: (-r["population"], _fold(r["name"])))
            candidates = pool[:limit]
            break

    if not candidates:
        return {
            "query": {"raw": None, "place": None, "country_code": country_code or None},
            "resolved": False,
            "ambiguous": False,
            "matched_tier": None,
            "note": f"no match in the bundled gazetteer (cities >= 20k population)",
            "candidates": [],
        }

    top = candidates[0]
    exact_unique = matched_tier in ("exact_name", "exact_ascii") and len(candidates) == 1
    same_place_alias = len(candidates) > 1 and all(
        _fold(c["asciiname"]) == _fold(top["asciiname"])
        and c.get("admin1_code") == top.get("admin1_code")
        and c.get("country_code") == top.get("country_code")
        for c in candidates)
    ambiguous = not (exact_unique or same_place_alias) or (matched_tier == "prefix_name")

    return {
        "query": {"raw": None, "place": None, "country_code": country_code or None},
        "resolved": True,
        "ambiguous": ambiguous,
        "matched_tier": matched_tier,
        "note": (
            "deterministic offline ranking (exact name -> asciiname -> alias -> "
            "prefix), ties broken by population. Confirm with the user before use "
            "when ambiguous."
            if ambiguous else "unambiguous exact match against the bundled gazetteer"
        ),
        "candidates": [
            {
                "name": c["name"],
                "country_code": c["country_code"],
                "admin1_code": c["admin1_code"],
                "latitude": c["latitude"],
                "longitude": c["longitude"],
                "timezone": c["timezone"],
                "population": c["population"],
            }
            for c in candidates
        ],
    }


def nearest_timezone(latitude: float, longitude: float) -> str:
    """Best-effort IANA timezone for a lat/lon, from the nearest gazetteer city.

    This maps a *point* to the nearest bundled city's zone. IANA zones are
    region polygons, not points, so near timezone borders this can pick the
    wrong side. Treat the result as a hint that a caller may override.
    """
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise ValueError("latitude/longitude out of range")
    rows = _load()
    best = None
    best_d2 = float("inf")
    for r in rows:
        # Equirectangular-ish approximation: scale longitude by cos(lat).
        dx = (r["longitude"] - longitude) * (3.141592653589793 / 180.0)
        dy = (r["latitude"] - latitude) * (3.141592653589793 / 180.0)
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best = r["timezone"]
    return best


def geocode(query: str, country: str | None = None, limit: int = 5) -> dict:
    """Resolve a place string against the bundled gazetteer.

    Returns a structured result with ranked candidates, the matching tier used
    for the top hit, and an `ambiguous` flag that should prompt user
    confirmation before the numbers are used.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("place must be a non-empty string")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")

    place, hint = _split_query(query)
    country_code = (country or hint or "").strip().upper()
    q = _fold(place)

    result = _search(q, rows := _load(), country_code, limit)
    if result["resolved"]:
        result["query"] = {
            "raw": query, "place": place, "country_code": country_code or None,
        }
        return result
    # A country code that happens to be a real ISO code (e.g. MH =
    # Marshall Islands) can be a region abbreviation. Re-run without the
    # country filter and surface the ambiguity instead of failing.
    if country_code:
        retried = _search(q, rows, None, limit)
        if retried["resolved"]:
            retried["query"] = {
                "raw": query, "place": place, "country_code": country_code or None,
                "country_filter": f"applied then dropped (no matches in {country_code})",
            }
            retried["ambiguous"] = True
            retried["note"] = (
                f"no match under country filter {country_code!r}; "
                "resolved without the filter — confirm the region with the user."
            )
            return retried
    return result