"""LibreJyotish MCP server — deterministic Vedic astrology computations.

Layer 1 only: every number is computed here (Swiss Ephemeris, sidereal zodiac,
Lahiri ayanamsha by default, whole-sign houses). The calling LLM does synthesis
and communication only. Every response carries an explicit conventions_used block.
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

try:
    from librejyotish import __version__ as _pkg_version
except ImportError:
    _pkg_version = "0.1.1"

from librejyotish.core import charts, dasha, eclipses, ephemeris as ep, geocode, panchang

server = MCPServer(
    name="librejyotish",
    version=_pkg_version,
    title="LibreJyotish",
    description=(
        "Deterministic Vedic (Jyotish) astrology calculations: natal and divisional "
        "charts, Vimshottari dasha, panchang, Ashtakavarga, Shadbala, transits."
    ),
    instructions=(
        "All outputs are sidereal (Lahiri ayanamsha unless overridden) with whole-sign "
        "houses. Every response includes a conventions_used block — quote it when citing "
        "results. All numbers are computed from Swiss Ephemeris; never recompute or "
        "round-trip them yourself. Interpretation is your job; this server only computes."
    ),
)

EPHEMERIS_INIT = ep.init_ephemeris()


def _parse_datetime(value: str, field: str = "datetime") -> datetime:
    """Parse a strict ISO-8601 naive local datetime string (e.g. '1994-03-21T14:32:00').

    Only the 'T'-separated ISO form is accepted; space-separated, slash-delimited,
    and 12-hour formats are rejected so malformed input fails loudly instead of
    being silently misinterpreted.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be an ISO-8601 local datetime string like "
            f"'1994-03-21T14:32:00' (naive, interpreted in the given timezone)"
        )
    value = value.strip()
    if "T" not in value:
        raise ValueError(
            f"{field} must use 'T' to separate the date and time, e.g. "
            f"'1994-03-21T14:32:00' — got {value!r} (space-separated, slash, or "
            f"12-hour AM/PM forms are not accepted)"
        )
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field} must be an ISO-8601 local datetime string like "
            f"'1994-03-21T14:32:00' (naive, interpreted in the given timezone): {exc}"
        ) from exc
    if dt.tzinfo is not None:
        raise ValueError(f"{field} must be naive local time; give the timezone separately")
    return dt


def _validate_tz(tz_name: str) -> str:
    try:
        ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError(f"unknown timezone {tz_name!r}: {exc}") from exc
    return tz_name


def _parse_date(value: str, field: str = "date") -> datetime:
    """Parse a strict ISO-8601 civil date (e.g. '2025-01-01') as a naive local
    midnight datetime. Slash and other ambiguous formats are rejected loudly."""
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be an ISO-8601 date string like '2025-01-01'"
        )
    value = value.strip()
    try:
        d = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{field} must be an ISO-8601 date string like '2025-01-01' "
            f"(slash and 12-hour forms are not accepted): {exc}"
        ) from exc
    return datetime(d.year, d.month, d.day)


def _resolve_timezone(timezone: str | None, latitude: float,
                      longitude: float) -> tuple[str, list[str]]:
    """Return (tz_name, warnings). Derives timezone from coords when omitted and
    cross-checks against the gazetteer-derived zone when explicitly supplied.
    """
    warnings: list[str] = []
    nearest = geocode.nearest_place(latitude, longitude)
    derived = nearest["timezone"]
    if nearest["distance_km"] > 250:
        warnings.append(
            f"the nearest populated place to these coordinates is "
            f"{nearest['place']}, {nearest['country_code']} at "
            f"{nearest['distance_km']} km away — the given lat/lon may be wrong "
            f"(dropped digit, transposed sign, or open water). Please confirm."
        )
    if timezone is None:
        warnings.append(
            f"timezone auto-derived from the nearest gazetteer city as "
            f"{derived!r} ({nearest['place']}, {nearest['distance_km']} km away); "
            f"pass `timezone` explicitly to override."
        )
        return derived, warnings
    tz_name = _validate_tz(timezone)
    if derived and derived != tz_name:
        warnings.append(
            f"supplied timezone {tz_name!r} does not match the gazetteer-derived "
            f"zone {derived!r} for these coordinates; the clock time is read in "
            f"{tz_name!r} but houses are computed at the given lat/lon."
        )
    return tz_name, warnings


def _common_inputs(datetime_local: str, timezone: str | None, latitude: float,
                   longitude: float, ayanamsha: str | None):
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be within [-90, 90]")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must be within [-180, 180]")
    tz_name, tz_warnings = _resolve_timezone(timezone, float(latitude), float(longitude))
    return (
        _parse_datetime(datetime_local),
        tz_name,
        float(latitude),
        float(longitude),
        ayanamsha,
        tz_warnings,
    )


def _error(tool: str, exc: Exception) -> dict:
    return {"error": {"tool": tool, "type": type(exc).__name__, "message": str(exc)}}


@server.tool()
def get_natal_chart(datetime_local: str, latitude: float, longitude: float,
                    timezone: str | None = None, ayanamsha: str = "lahiri",
                    node_type: str = "true", true_positions: bool = False) -> dict:
    """Sidereal natal chart: ascendant, planetary longitudes/signs/nakshatras/
    whole-sign houses, retrograde and combustion flags, dignities.

    datetime_local: ISO-8601 naive local birth datetime, e.g. '1994-03-21T14:32:00'.
    timezone: IANA zone name, e.g. 'Asia/Kolkata'; when omitted it is derived
      from the coordinates. ayanamsha: 'lahiri' (default).
    node_type: 'true' or 'mean' — true node is the physically oscillating lunar
      node; mean node is its smoothed average. Jyotish most commonly uses 'true'.
    true_positions: false (default) = apparent geocentric positions (refraction
      and light-time corrected, the standard for astrology); true = geometric
      positions without those corrections. Leave false unless you know you need
      the geometric values.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        if node_type not in ("true", "mean"):
            raise ValueError("node_type must be 'true' or 'mean'")
        result = charts.build_natal_chart(naive_local, tz_name, lat, lon, aya,
                                          node_type=node_type,
                                          true_positions=true_positions)
        if tz_warnings:
            result["warnings"] = tz_warnings
        return result
    except (ValueError, TypeError) as exc:
        return _error("get_natal_chart", exc)


@server.tool()
def get_divisional_chart(datetime_local: str, latitude: float, longitude: float,
                         division: str, timezone: str | None = None,
                         ayanamsha: str = "lahiri", node_type: str = "true",
                         true_positions: bool = False) -> dict:
    """Divisional (varga) chart D1..D60 for the same birth input, e.g. division='D9'.

    Returns each body's varga sign and house counted whole-sign from the varga Lagna.
    node_type: 'true' or 'mean' (see get_natal_chart). true_positions: false
      (default) = apparent positions; true = geometric.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        result = charts.build_divisional_chart(naive_local, tz_name, lat, lon,
                                               division.upper(), aya,
                                               node_type=node_type,
                                               true_positions=true_positions)
        if tz_warnings:
            result["warnings"] = tz_warnings
        return result
    except (ValueError, TypeError) as exc:
        return _error("get_divisional_chart", exc)


@server.tool()
def get_vimshottari_dasha(datetime_local: str, latitude: float, longitude: float,
                          timezone: str | None = None,
                          reference_datetime_local: str | None = None,
                          start_date: str | None = None,
                          end_date: str | None = None,
                          levels: int = 3, ayanamsha: str = "lahiri",
                          node_type: str = "true",
                          true_positions: bool = False) -> dict:
    """Vimshottari dasha tree: mahadasha -> antardasha -> pratyantardasha (and
    optionally sookshma) with start/end dates. If reference_datetime_local is
    given, `current_periods` reports the chain running at that moment.

    levels: 1 = mahadasha only, 2 = + antardasha, 3 = + pratyantardasha,
      4 = + sookshma. Lower levels shrink the response.
    start_date, end_date: optional ISO-8601 date strings (e.g. '2025-01-01')
      to filter the returned periods to those overlapping the range.
    node_type: 'true' or 'mean' (see get_natal_chart). true_positions: false
      (default) = apparent positions; true = geometric.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        ref = None
        if reference_datetime_local is not None:
            ref = _parse_datetime(reference_datetime_local, "reference_datetime_local")
        start = _parse_date(start_date, "start_date") if start_date else None
        end = _parse_date(end_date, "end_date") if end_date else None
        result = dasha.build_vimshottari_dasha(naive_local, tz_name, lat, lon, aya,
                                               node_type=node_type,
                                               true_positions=true_positions,
                                               levels=levels,
                                               reference_local=ref,
                                               start_date=start,
                                               end_date=end)
        if tz_warnings:
            result["warnings"] = tz_warnings
        return result
    except (ValueError, TypeError) as exc:
        return _error("get_vimshottari_dasha", exc)


@server.tool()
def get_panchang(date_local: str, latitude: float, longitude: float,
                 timezone: str | None = None, ayanamsha: str = "lahiri",
                 true_positions: bool = False) -> dict:
    """Panchang for a civil date at a location: tithi, vara, nakshatra, yoga,
    karana, sunrise/sunset.

    date_local: ISO date string 'YYYY-MM-DD' (civil day in the given timezone).
    timezone: IANA zone name; when omitted it is derived from the coordinates.
    true_positions: false (default) = apparent positions; true = geometric.
    """
    try:
        tz_name, tz_warnings = _resolve_timezone(timezone, float(latitude), float(longitude))
        try:
            d = date.fromisoformat(date_local.strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"date_local must be 'YYYY-MM-DD': {exc}") from exc
        result = panchang.build_panchang(d, tz_name, float(latitude), float(longitude),
                                         ayanamsha, true_positions=true_positions)
        result_warnings = list(result.get("warnings") or [])
        result_warnings.extend(w for w in tz_warnings if w not in result_warnings)
        result["warnings"] = result_warnings
        return result
    except (ValueError, TypeError) as exc:
        return _error("get_panchang", exc)


@server.tool()
def get_ashtakavarga(datetime_local: str, latitude: float, longitude: float,
                     timezone: str | None = None,
                     ayanamsha: str = "lahiri",
                     node_type: str = "true", true_positions: bool = False) -> dict:
    """Ashtakavarga bindu tables: Bhinnashtakavarga per planet plus
    Sarvashtakavarga totals across the 12 signs.
    node_type: 'true' or 'mean' (see get_natal_chart). true_positions: false
      (default) = apparent positions; true = geometric.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        from librejyotish.core.ashtakavarga import build_ashtakavarga
        result = build_ashtakavarga(naive_local, tz_name, lat, lon, aya,
                                    node_type=node_type, true_positions=true_positions)
        if tz_warnings:
            result["warnings"] = tz_warnings
        return result
    except (ValueError, TypeError) as exc:
        return _error("get_ashtakavarga", exc)


@server.tool()
def get_shadbala(datetime_local: str, latitude: float, longitude: float,
                 timezone: str | None = None,
                 ayanamsha: str = "lahiri",
                 node_type: str = "true", true_positions: bool = False) -> dict:
    """Shadbala six-fold strength per planet (sthana, dig, kala, cheshta,
    naisargika, drik) with component breakdowns, totals in virupas and rupas,
    and required-strength comparison.
    node_type: 'true' or 'mean' (see get_natal_chart). true_positions: false
      (default) = apparent positions; true = geometric.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        from librejyotish.core.shadbala import build_shadbala
        result = build_shadbala(naive_local, tz_name, lat, lon, aya,
                                node_type=node_type, true_positions=true_positions)
        if tz_warnings:
            result["warnings"] = tz_warnings
        return result
    except (ValueError, TypeError) as exc:
        return _error("get_shadbala", exc)


@server.tool()
def get_current_transits(datetime_local: str, latitude: float, longitude: float,
                         timezone: str | None = None,
                         as_of_datetime_local: str | None = None,
                         ayanamsha: str = "lahiri", node_type: str = "true",
                         true_positions: bool = False) -> dict:
    """Current planetary transits measured against the natal chart: each planet's
    sidereal position plus house from natal Lagna and from natal Moon (Chandra
    lagna), raw positions only — no favorable/unfavorable judgment.

    as_of_datetime_local defaults to now in `timezone`.
    timezone: IANA zone name; when omitted it is derived from the coordinates.
    node_type: 'true' or 'mean' (see get_natal_chart). true_positions: false
      (default) = apparent positions; true = geometric.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        if as_of_datetime_local is None:
            as_of_naive = datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
        else:
            as_of_naive = _parse_datetime(as_of_datetime_local, "as_of_datetime_local")

        warnings = list(tz_warnings)
        if as_of_naive < naive_local:
            warnings.append(
                "as_of is before the birth datetime; transit house positions are "
                "still computed but predate the native's birth."
            )
        elif (as_of_naive - naive_local) <= timedelta(days=45):
            warnings.append(
                "as_of is within ~45 days of the birth datetime; if you intended a "
                "current-date transit you may have passed the birth input as the "
                "as_of date. Confirm as_of_datetime_local is the date you want."
            )

        natal = charts.build_natal_chart(naive_local, tz_name, lat, lon, aya,
                                         node_type=node_type,
                                         true_positions=true_positions)
        lagna_lon = natal["ascendant"]["longitude"]
        moon_lon = next(
            p["longitude"] for p in natal["planets"] if p["name"] == "Moon")

        as_of_jd = ep.to_jd(as_of_naive, tz_name)
        transit_positions = ep.planet_positions(as_of_jd, ayanamsha=aya,
                                                node_type=node_type,
                                                true_positions=true_positions)
        aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)

        bodies = []
        for name in charts.ALL_GRAHAS:
            t = transit_positions[name]
            sign_info = ep.sign_of(t["longitude"])
            bodies.append({
                "name": name,
                "longitude": round(t["longitude"], 6),
                "sign": sign_info["name"],
                "degree_in_sign": round(sign_info["degree_in_sign"], 6),
                "nakshatra": ep.nakshatra_of(t["longitude"]),
                "speed_deg_per_day": round(t["speed"], 6),
                "retrograde": t["retrograde"],
                "house_from_natal_lagna": charts.house_from_lagna(
                    t["longitude"], lagna_lon),
                "house_from_natal_moon": charts.house_from_lagna(
                    t["longitude"], moon_lon),
            })

        return {
            "input": {
                "birth_datetime_local": naive_local.isoformat(),
                "timezone": tz_name,
                "latitude": lat,
                "longitude": lon,
                "as_of_local": as_of_naive.isoformat(),
                "as_of_is_default_now": as_of_datetime_local is None,
            },
            "warnings": warnings,
            "julian_day_ut_as_of": round(as_of_jd, 8),
            "ephemeris_source": ep.ephemeris_source(),
            "conventions_used": {
                "zodiac": "sidereal",
                "ayanamsha": {"key": aya_key, "name": aya_label,
                              "value_degrees": round(ep.ayanamsha_value(as_of_jd, aya_key), 6)},
                "node_type": node_type,
                "position_type": "true" if true_positions else "apparent",
                "house_system": {
                    "key": "whole_sign",
                    "name": ("Whole-sign houses: transit house = transit sign counted "
                             "from natal Lagna sign / natal Moon sign"),
                },
                "natal_reference": {
                    "lagna_sign": ep.sign_of(lagna_lon)["name"],
                    "moon_sign": ep.sign_of(moon_lon)["name"],
                },
                "interpretation": "none — raw gochara positions only (v2 rules corpus)",
            },
            "transits": bodies,
        }
    except (ValueError, TypeError) as exc:
        return _error("get_current_transits", exc)


@server.tool()
def get_eclipses(datetime_local: str, latitude: float, longitude: float,
                 timezone: str | None = None,
                 as_of_datetime_local: str | None = None,
                 count: int = 4, ayanamsha: str = "lahiri",
                 node_type: str = "true", true_positions: bool = False) -> dict:
    """Next solar/lunar eclipses with exact event times and the sidereal
    eclipse point.

    The eclipse point is the Moon's longitude for a lunar eclipse and the Sun's
    for a solar one. When the birth chart is supplied (datetime_local, timezone,
    latitude, longitude), each event also reports the point's whole-sign house
    from the natal Lagna and from the natal Moon (Chandra lagna).

    as_of_datetime_local defaults to now in `timezone`; count: 1-20. The birth
    latitude/longitude anchor the natal houses only — eclipses are global events.
    timezone: IANA zone name; when omitted it is derived from the coordinates.
    node_type: 'true' or 'mean' (see get_natal_chart). true_positions: false
      (default) = apparent positions; true = geometric.
    """
    try:
        naive_local, tz_name, lat, lon, aya, tz_warnings = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        if not 1 <= int(count) <= 20:
            raise ValueError("count must be between 1 and 20")
        count = int(count)
        if as_of_datetime_local is None:
            as_of_naive = datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
        else:
            as_of_naive = _parse_datetime(as_of_datetime_local, "as_of_datetime_local")

        natal = charts.build_natal_chart(naive_local, tz_name, lat, lon, aya,
                                         node_type=node_type,
                                         true_positions=true_positions)
        lagna_lon = natal["ascendant"]["longitude"]
        moon_lon = next(
            p["longitude"] for p in natal["planets"] if p["name"] == "Moon")

        result = eclipses.next_eclipses(as_of_naive, tz_name, ayanamsha=aya,
                                        count=count, node_type=node_type,
                                        true_positions=true_positions)
        as_of_jd = ep.to_jd(as_of_naive, tz_name)
        aya_key, _, aya_label = ep.resolve_ayanamsha(aya)

        for ev in result["events"]:
            lon_ev = ev["point"]["longitude"]
            ev["house_from_natal_lagna"] = charts.house_from_lagna(lon_ev, lagna_lon)
            ev["house_from_natal_moon"] = charts.house_from_lagna(lon_ev, moon_lon)

        return {
            "input": {
                "birth_datetime_local": naive_local.isoformat(),
                "timezone": tz_name,
                "birth_latitude": lat,
                "birth_longitude": lon,
                "as_of_local": as_of_naive.isoformat(),
                "as_of_is_default_now": as_of_datetime_local is None,
                "count_requested": count,
            },
            "warnings": tz_warnings,
            "julian_day_ut_as_of": round(as_of_jd, 8),
            "ephemeris_source": ep.ephemeris_source(),
            "conventions_used": {
                "zodiac": "sidereal",
                "ayanamsha": {"key": aya_key, "name": aya_label,
                              "value_degrees": round(ep.ayanamsha_value(as_of_jd, aya_key), 6)},
                "node_type": node_type,
                "position_type": "true" if true_positions else "apparent",
                "event_times": "overall-first contact, maximum (greatest), last "
                             "contact — UT plus local time",
                "eclipse_types": {
                    "solar": "from SWE sol_eclipse_when_glob return flag "
                             "(total/annular/partial/annular-total)",
                    "lunar": "from SWE lun_eclipse_how umbral magnitude "
                             "(>=1 total, >0 partial, else penumbral)",
                },
                "house_system": {
                    "key": "whole_sign",
                    "name": "eclipse point house = point sign counted from natal "
                            "Lagna sign / natal Moon sign",
                },
                "natal_reference": {
                    "lagna_sign": ep.sign_of(lagna_lon)["name"],
                    "moon_sign": ep.sign_of(moon_lon)["name"],
                },
                "interpretation": "none — raw eclipse geometry only",
            },
            **result,
        }
    except (ValueError, TypeError) as exc:
        return _error("get_eclipses", exc)


@server.tool()
def geocode_location(place: str, country: str | None = None,
                     limit: int = 5) -> dict:
    """Offline place-string lookup for use with the computation tools.

    Resolves a place like 'Nashik, India' into candidate latitude/longitude/
    IANA-timezone tuples. The computation tools expect numeric latitude and
    longitude; pass the top candidate's values to them.

    Matching is deterministic (exact name -> asciiname -> alternate name ->
    prefix), ranked by population, against the bundled GeoNames-derived
    gazetteer of cities >= 20k population. `ambiguous: true` means the string
    does not uniquely resolve — confirm the intended place with the user.
    """
    try:
        result = geocode.geocode(place if isinstance(place, str) else None,
                                 country=country, limit=limit)
        result["conventions_used"] = {
            "data_source": "GeoNames cities1000 (CC-BY) reduced to populated "
                           "places >= 20k population; strictly offline — no network",
            "attribution": "GeoNames data is licensed under Creative Commons "
                           "Attribution 4.0; see data/gazetteer/README.md",
            "resolution": "deterministic tiered matching, population-ranked; "
                          "not an astronomical computation",
        }
        return result
    except (ValueError, TypeError) as exc:
        return _error("geocode_location", exc)


_BATCHABLE = {
    "get_natal_chart": get_natal_chart,
    "get_divisional_chart": get_divisional_chart,
    "get_vimshottari_dasha": get_vimshottari_dasha,
    "get_panchang": get_panchang,
    "get_ashtakavarga": get_ashtakavarga,
    "get_shadbala": get_shadbala,
    "get_current_transits": get_current_transits,
    "get_eclipses": get_eclipses,
    "geocode_location": geocode_location,
}


@server.tool()
def batch(operations: list[dict]) -> dict:
    """Run multiple chart/panchang/geocode operations in a single call.

    Use this for comparative work — multiple people's charts in one turn, or
    screening a date range — instead of sequential single calls.

    operations: a list of {"tool": <name>, "arguments": {<param>: value}}.
    Supported tool names: get_natal_chart, get_divisional_chart,
      get_vimshottari_dasha, get_panchang, get_ashtakavarga, get_shadbala,
      get_current_transits, get_eclipses, geocode_location. Each `arguments`
      dict is the same set of parameters that tool normally takes.

    Every result is the same structured dict that tool would return alone. A
    failing operation becomes {"error": {...}} rather than aborting the batch,
    so a single bad input never discards the other results. Response order
    matches the input order.
    """
    if not isinstance(operations, list) or not operations:
        raise ValueError("operations must be a non-empty list of {tool, arguments} dicts")
    if len(operations) > 50:
        raise ValueError("operations accepts at most 50 items in one call")
    results = []
    for op in operations:
        if not isinstance(op, dict) or "tool" not in op:
            results.append(_error("batch",
                                  ValueError("each operation must be a {tool, arguments} dict")))
            continue
        name = op["tool"]
        fn = _BATCHABLE.get(name)
        if fn is None:
            results.append(_error("batch",
                                  ValueError(
                                      f"unknown tool {name!r}; supported: "
                                      f"{', '.join(sorted(_BATCHABLE))}")))
            continue
        args = op.get("arguments") or {}
        try:
            results.append(fn(**args))
        except (TypeError, ValueError) as exc:
            results.append(_error("batch", exc))
    return {"count": len(results), "results": results}


def main() -> None:
    """Entry point for `librejyotish` console script."""
    parser = argparse.ArgumentParser(description="LibreJyotish MCP server")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args, _unknown = parser.parse_known_args()
    if args.version:
        print(_pkg_version)
        return
    server.run("stdio")


if __name__ == "__main__":
    main()
