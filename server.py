"""OpenJyotish MCP server — deterministic Vedic astrology computations.

Layer 1 only: every number is computed here (Swiss Ephemeris, sidereal zodiac,
Lahiri ayanamsha by default, whole-sign houses). The calling LLM does synthesis
and communication only. Every response carries an explicit conventions_used block.
"""

import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

# Make `core` importable regardless of the current working directory (the MCP
# client spawns us from an arbitrary cwd). server.py lives at the repo root,
# alongside the core/ package, so add its own directory to sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import charts, dasha, eclipses, ephemeris as ep, geocode, panchang

server = MCPServer(
    name="openjyotish",
    version="0.1.0",
    title="OpenJyotish",
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


def _common_inputs(datetime_local: str, timezone: str, latitude: float,
                   longitude: float, ayanamsha: str | None):
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be within [-90, 90]")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must be within [-180, 180]")
    return (
        _parse_datetime(datetime_local),
        _validate_tz(timezone),
        float(latitude),
        float(longitude),
        ayanamsha,
    )


def _error(tool: str, exc: Exception) -> dict:
    return {"error": {"tool": tool, "type": type(exc).__name__, "message": str(exc)}}


@server.tool()
def get_natal_chart(datetime_local: str, timezone: str, latitude: float,
                    longitude: float, ayanamsha: str = "lahiri",
                    node_type: str = "true", true_positions: bool = False) -> dict:
    """Sidereal natal chart: ascendant, planetary longitudes/signs/nakshatras/
    whole-sign houses, retrograde and combustion flags, dignities.

    datetime_local: ISO-8601 naive local birth datetime, e.g. '1994-03-21T14:32:00'.
    timezone: IANA zone name, e.g. 'Asia/Kolkata'. ayanamsha: 'lahiri' (default).
    node_type: 'true' or 'mean'. true_positions: true for true-position planets.
    """
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        if node_type not in ("true", "mean"):
            raise ValueError("node_type must be 'true' or 'mean'")
        return charts.build_natal_chart(naive_local, tz_name, lat, lon, aya,
                                        node_type=node_type,
                                        true_positions=true_positions)
    except (ValueError, TypeError) as exc:
        return _error("get_natal_chart", exc)


@server.tool()
def get_divisional_chart(datetime_local: str, timezone: str, latitude: float,
                         longitude: float, division: str,
                         ayanamsha: str = "lahiri", node_type: str = "true",
                         true_positions: bool = False) -> dict:
    """Divisional (varga) chart D1..D60 for the same birth input, e.g. division='D9'.

    Returns each body's varga sign and house counted whole-sign from the varga Lagna.
    """
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        return charts.build_divisional_chart(naive_local, tz_name, lat, lon,
                                             division.upper(), aya,
                                             node_type=node_type,
                                             true_positions=true_positions)
    except (ValueError, TypeError) as exc:
        return _error("get_divisional_chart", exc)


@server.tool()
def get_vimshottari_dasha(datetime_local: str, timezone: str, latitude: float,
                          longitude: float, reference_datetime_local: str | None = None,
                          ayanamsha: str = "lahiri", node_type: str = "true",
                          true_positions: bool = False) -> dict:
    """Full Vimshottari dasha tree: mahadasha -> antardasha -> pratyantardasha
    with start/end dates. If reference_datetime_local is given, each level is
    annotated with the period running at that moment.
    """
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        ref = None
        if reference_datetime_local is not None:
            ref = _parse_datetime(reference_datetime_local, "reference_datetime_local")
        return dasha.build_vimshottari_dasha(naive_local, tz_name, lat, lon, aya,
                                             node_type=node_type,
                                             true_positions=true_positions,
                                             include_pratyantardasha=True,
                                             reference_local=ref)
    except (ValueError, TypeError) as exc:
        return _error("get_vimshottari_dasha", exc)


@server.tool()
def get_panchang(date_local: str, timezone: str, latitude: float,
                 longitude: float, ayanamsha: str = "lahiri",
                 true_positions: bool = False) -> dict:
    """Panchang for a civil date at a location: tithi, vara, nakshatra, yoga,
    karana, sunrise/sunset.

    date_local: ISO date string 'YYYY-MM-DD' (civil day in the given timezone).
    """
    try:
        _validate_tz(timezone)
        try:
            d = date.fromisoformat(date_local.strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"date_local must be 'YYYY-MM-DD': {exc}") from exc
        return panchang.build_panchang(d, timezone, float(latitude), float(longitude),
                                       ayanamsha, true_positions=true_positions)
    except (ValueError, TypeError) as exc:
        return _error("get_panchang", exc)


@server.tool()
def get_ashtakavarga(datetime_local: str, timezone: str, latitude: float,
                     longitude: float, ayanamsha: str = "lahiri",
                     node_type: str = "true", true_positions: bool = False) -> dict:
    """Ashtakavarga bindu tables: Bhinnashtakavarga per planet plus
    Sarvashtakavarga totals across the 12 signs."""
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        from core.ashtakavarga import build_ashtakavarga
        return build_ashtakavarga(naive_local, tz_name, lat, lon, aya,
                                  node_type=node_type, true_positions=true_positions)
    except (ValueError, TypeError) as exc:
        return _error("get_ashtakavarga", exc)


@server.tool()
def get_shadbala(datetime_local: str, timezone: str, latitude: float,
                 longitude: float, ayanamsha: str = "lahiri",
                 node_type: str = "true", true_positions: bool = False) -> dict:
    """Shadbala six-fold strength per planet (sthana, dig, kala, cheshta,
    naisargika, drik) with component breakdowns, totals in virupas and rupas,
    and required-strength comparison."""
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
        from core.shadbala import build_shadbala
        return build_shadbala(naive_local, tz_name, lat, lon, aya,
                              node_type=node_type, true_positions=true_positions)
    except (ValueError, TypeError) as exc:
        return _error("get_shadbala", exc)


@server.tool()
def get_current_transits(datetime_local: str, timezone: str, latitude: float,
                         longitude: float, as_of_datetime_local: str | None = None,
                         ayanamsha: str = "lahiri", node_type: str = "true",
                         true_positions: bool = False) -> dict:
    """Current planetary transits measured against the natal chart: each planet's
    sidereal position plus house from natal Lagna and from natal Moon (Chandra
    lagna), raw positions only — no favorable/unfavorable judgment.

    as_of_datetime_local defaults to now in `timezone`.
    """
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
            datetime_local, timezone, latitude, longitude, ayanamsha)
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
def get_eclipses(datetime_local: str, timezone: str, latitude: float,
                 longitude: float, as_of_datetime_local: str | None = None,
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
    """
    try:
        naive_local, tz_name, lat, lon, aya = _common_inputs(
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


if __name__ == "__main__":
    server.run("stdio")
