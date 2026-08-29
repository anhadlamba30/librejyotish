"""Natal chart and divisional (varga) chart computation.

Whole-sign houses throughout: house N of a body = ((its sign - lagna sign)
mod 12) + 1. Divisional mappings follow Traditional Parasara (BPHS) rules;
each varga's rule is documented inline next to its implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import ephemeris as ep
from core.constants import (
    COMBUSTION_ORBS,
    COMBUSTION_ORBS_RETRO,
    EXALTATION_DEGREE,
    MOOLATRIKONA_RANGE,
    PLANET_RELATIONS,
    SIGN_ELEMENTS,
    SIGN_LORDS,
    SIGNS,
    nakshatra_index,
    normalize_deg,
)

MAIN_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
ALL_GRAHAS = MAIN_PLANETS + ["Rahu", "Ketu"]

# ---------------------------------------------------------------------------
# Varga engine
# ---------------------------------------------------------------------------


def _movable_fixed_dual(sign: int) -> str:
    """Chara/sthira/dwiswabhava classification of a sign index."""
    return ("movable", "fixed", "dual")[sign % 3]


def _navamsha_base(sign: int) -> int:
    """Navamsha counting seed: fire->Aries(0), water->Cancer(3),
    air->Libra(6), earth->Capricorn(9)."""
    return {"fire": 0, "water": 3, "air": 6, "earth": 9}[SIGN_ELEMENTS[sign]]


def _bhamsha_base(sign: int) -> int:
    """Bhamsha (D27) counting seed: fire->Aries(0), earth->Cancer(3),
    air->Libra(6), water->Capricorn(9). Note earth/water are swapped
    relative to the Navamsha seeds."""
    return {"fire": 0, "earth": 3, "air": 6, "water": 9}[SIGN_ELEMENTS[sign]]


# Each rule maps (sign_index, part_index) -> varga sign index.
# part_index runs 0..divisions-1 within the rasi sign.

def _d1(s: int, k: int) -> int:
    return s

def _d2(s: int, k: int) -> int:
    # Hora (Parasara): only Leo (Sun) and Cancer (Moon). Odd signs: 1st half
    # Leo, 2nd half Cancer. Even signs reversed.
    sun_hora = 4
    moon_hora = 3
    first_half_is_sun = (s % 2 == 0 and k == 0) or (s % 2 == 1 and k == 1)
    return sun_hora if first_half_is_sun else moon_hora

def _d3(s: int, k: int) -> int:
    # Drekkana: parts fall in same / 5th / 9th sign.
    return (s + 4 * k) % 12

def _d4(s: int, k: int) -> int:
    # Chaturthamsha: same / 4th / 7th / 10th.
    return (s + 3 * k) % 12

def _d7(s: int, k: int) -> int:
    # Saptamsha: odd signs count from themselves, even from the 7th.
    return (s + k) % 12 if s % 2 == 0 else (s + 6 + k) % 12

def _d9(s: int, k: int) -> int:
    # Navamsha: fire signs from Aries, water from Cancer, air from Libra,
    # earth from Capricorn (equivalent to movable/fixed/dual rule).
    return (_navamsha_base(s) + k) % 12

def _d10(s: int, k: int) -> int:
    # Dashamsha: odd from itself, even from the 9th.
    return (s + k) % 12 if s % 2 == 0 else (s + 8 + k) % 12

def _d12(s: int, k: int) -> int:
    # Dwadashamsha: always from the sign itself.
    return (s + k) % 12

def _d16(s: int, k: int) -> int:
    # Shodashamsha: movable from Aries, fixed from Leo, dual from Sagittarius.
    mfd = _movable_fixed_dual(s)
    base = {"movable": 0, "fixed": 4, "dual": 8}[mfd]
    return (base + k) % 12

def _d20(s: int, k: int) -> int:
    # Vimshamsha: movable from Aries, dual from Leo, fixed from Sagittarius.
    mfd = _movable_fixed_dual(s)
    base = {"movable": 0, "dual": 4, "fixed": 8}[mfd]
    return (base + k) % 12

def _d24(s: int, k: int) -> int:
    # Chaturvimshamsha: odd from Leo, even from Cancer.
    return (4 + k) % 12 if s % 2 == 0 else (3 + k) % 12

def _d27(s: int, k: int) -> int:
    # Bhamsha/Nakshatramsha: fire from Aries, earth from Cancer, air from
    # Libra, water from Capricorn.
    return (_bhamsha_base(s) + k) % 12

def _d40(s: int, k: int) -> int:
    # Khavedamsha: odd from Aries, even from Libra.
    return k % 12 if s % 2 == 0 else (6 + k) % 12

def _d45(s: int, k: int) -> int:
    # Akshavedamsha: movable from Aries, fixed from Leo, dual from Sagittarius.
    mfd = _movable_fixed_dual(s)
    base = {"movable": 0, "fixed": 4, "dual": 8}[mfd]
    return (base + k) % 12

def _d60(s: int, k: int) -> int:
    # Shashtiamsha (Parasara): counted from the sign itself.
    return (s + k) % 12


TRIMSAMSA_ODD = [(0.0, 5.0, 0), (5.0, 10.0, 10), (10.0, 18.0, 8), (18.0, 25.0, 2), (25.0, 30.0, 6)]
TRIMSAMSA_EVEN = [(0.0, 5.0, 1), (5.0, 12.0, 5), (12.0, 20.0, 11), (20.0, 25.0, 9), (25.0, 30.0, 7)]


@dataclass(frozen=True)
class VargaSpec:
    code: str
    name: str
    divisions: int
    sign_for_part: object  # callable(sign_index, part_index) -> sign_index
    significations: str


SUPPORTED_VARGAS: dict[str, VargaSpec] = {
    spec.code: spec
    for spec in [
        VargaSpec("D1", "Rashi", 1, _d1, "body, overall life"),
        VargaSpec("D2", "Hora", 2, _d2, "wealth"),
        VargaSpec("D3", "Drekkana", 3, _d3, "siblings, courage"),
        VargaSpec("D4", "Chaturthamsha", 4, _d4, "fortune, property"),
        VargaSpec("D7", "Saptamsha", 7, _d7, "children, progeny"),
        VargaSpec("D9", "Navamsha", 9, _d9, "marriage, inner self"),
        VargaSpec("D10", "Dashamsha", 10, _d10, "career, public life"),
        VargaSpec("D12", "Dwadashamsha", 12, _d12, "parents"),
        VargaSpec("D16", "Shodashamsha", 16, _d16, "vehicles, comforts"),
        VargaSpec("D20", "Vimshamsha", 20, _d20, "spiritual practice"),
        VargaSpec("D24", "Chaturvimshamsha", 24, _d24, "learning, education"),
        VargaSpec("D27", "Bhamsha (Nakshatramsha)", 27, _d27, "strengths, weaknesses"),
        VargaSpec("D30", "Trimshamsha", 30, None, "evils, misfortunes"),  # special-cased
        VargaSpec("D40", "Khavedamsha", 40, _d40, "maternal legacy"),
        VargaSpec("D45", "Akshavedamsha", 45, _d45, "paternal legacy"),
        VargaSpec("D60", "Shashtiamsha", 60, _d60, "past-life karma"),
    ]
}


def varga_sign(spec: VargaSpec, sidereal_longitude: float) -> tuple[int, float]:
    """Return (varga_sign_index, degree_within_varga_sign) for a longitude."""
    lon = normalize_deg(sidereal_longitude)
    s = int(lon // 30.0)
    deg_in_sign = lon - s * 30.0
    if spec.code == "D30":
        # Trimshamsha uses unequal classical partitions owned by the five
        # non-luminary planets.
        table = TRIMSAMSA_ODD if s % 2 == 0 else TRIMSAMSA_EVEN
        target = next(rasi for lo, hi, rasi in table if lo <= deg_in_sign <= hi)
    else:
        part = min(int(deg_in_sign // (30.0 / spec.divisions)), spec.divisions - 1)
        target = spec.sign_for_part(s, part)
    d_long = (deg_in_sign * spec.divisions) % 30.0
    return target, d_long


def resolve_varga(code: str) -> VargaSpec:
    key = code.upper().replace("-", "").replace("_", "")
    if key not in SUPPORTED_VARGAS:
        raise ValueError(
            f"Unsupported division '{code}'. Supported: {sorted(SUPPORTED_VARGAS)}"
        )
    return SUPPORTED_VARGAS[key]


# ---------------------------------------------------------------------------
# Natal chart
# ---------------------------------------------------------------------------


def house_from_lagna(body_lon: float, anchor_lon: float) -> int:
    """Whole-sign house: (body sign index - anchor sign index) mod 12 + 1.

    `anchor_lon` is usually the natal Lagna, but the same rule measures from
    any anchor (natal Moon for Chandra-lagna placements, etc.).
    """
    return (int(normalize_deg(body_lon) // 30) - int(normalize_deg(anchor_lon) // 30)) % 12 + 1


def _house_from_lagna(body_lon: float, lagna_lon: float) -> int:
    return house_from_lagna(body_lon, lagna_lon)


def combustion_of(planet: str, planets: dict) -> bool:
    """True when a planet falls within its combustion orb of the Sun."""
    if planet == "Sun":
        return False
    sep = abs(normalize_deg(planets[planet]["longitude"] - planets["Sun"]["longitude"] + 180) - 180)
    orb_key = planet
    orb = COMBUSTION_ORBS.get(orb_key)
    if planet in COMBUSTION_ORBS_RETRO and planets[planet]["retrograde"]:
        orb = COMBUSTION_ORBS_RETRO[planet]
    return orb is not None and sep <= orb


def dignity_of(planet: str, lon: float) -> str:
    """Sign-based classical dignity, including degree-sensitive moolatrikona."""
    si = int(normalize_deg(lon) // 30)
    sign_name = SIGNS[si]
    lord = SIGN_LORDS[si]
    lo, hi = MOOLATRIKONA_RANGE.get(planet, (-1.0, -1.0))
    if lo >= 0 and lo <= normalize_deg(lon) < hi:
        return "moolatrikona"
    if planet in EXALTATION_DEGREE and si == int(EXALTATION_DEGREE[planet] // 30):
        return "exalted"
    if planet in EXALTATION_DEGREE and si == int((EXALTATION_DEGREE[planet] + 180) // 30):
        return "debilitated"
    if lord == planet:
        return "own"
    rel = PLANET_RELATIONS.get(planet)
    if rel:
        if lord in rel["friends"]:
            return "friendly"
        if lord in rel["enemies"]:
            return "enemy"
        return "neutral"
    # Nodes have no classical sign-relations; report dispositor instead.
    return f"dispositor:{lord}"


def build_natal_chart(
    naive_local,
    tz_name: str,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
) -> dict:
    jd = ep.to_jd(naive_local, tz_name)
    source = ep.ephemeris_source()
    aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)
    positions = ep.planet_positions(jd, ayanamsha=aya_key, node_type=node_type,
                                    true_positions=true_positions)
    asc, mc = ep.ascendant_and_mc(jd, latitude, longitude, ayanamsha=aya_key,
                                  true_positions=true_positions)

    planets_out = []
    for name in ALL_GRAHAS:
        p = positions[name]
        entry = {
            "name": name,
            "longitude": round(p["longitude"], 6),
            "speed_deg_per_day": round(p["speed"], 6),
            "retrograde": p["retrograde"],
            "sign": ep.sign_of(p["longitude"])["name"],
            "degree_in_sign": round(ep.sign_of(p["longitude"])["degree_in_sign"], 6),
            "degree_in_sign_dms": ep.dms(ep.sign_of(p["longitude"])["degree_in_sign"]),
            "nakshatra": ep.nakshatra_of(p["longitude"]),
            "house_from_lagna": _house_from_lagna(p["longitude"], asc),
            "combustion": combustion_of(name, positions),
            "dignity": dignity_of(name, p["longitude"]),
        }
        entry["nakshatra"].pop("index_zero_based", None)
        entry["nakshatra"].pop("fraction_elapsed", None)
        planets_out.append(entry)

    return {
        "input": {
            "datetime_local": naive_local.isoformat(),
            "timezone": tz_name,
            "latitude": latitude,
            "longitude": longitude,
        },
        "julian_day_ut": round(jd, 8),
        "ephemeris_source": source,
        "conventions_used": {
            "zodiac": "sidereal",
            "ayanamsha": {"key": aya_key, "name": aya_label, "value_degrees": round(ep.ayanamsha_value(jd, aya_key), 6)},
            "node_type": node_type,
            "position_type": "true" if true_positions else "apparent",
            "house_system": {
                "key": "whole_sign",
                "name": "Whole-sign houses from Lagna sign",
            },
            "dignity_basis": "sign-based with degree-specific moolatrikona",
            "combustion_orbs_degrees": {
                **COMBUSTION_ORBS,
                **{"mercury_retro": COMBUSTION_ORBS_RETRO["Mercury"],
                   "venus_retro": COMBUSTION_ORBS_RETRO["Venus"]},
            },
        },
        "ascendant": {
            "longitude": round(asc, 6),
            "sign": ep.sign_of(asc)["name"],
            "degree_in_sign": round(ep.sign_of(asc)["degree_in_sign"], 6),
            "degree_in_sign_dms": ep.dms(ep.sign_of(asc)["degree_in_sign"]),
            "nakshatra": ep.nakshatra_of(asc),
        },
        "midheaven_sidereal": {
            "longitude": round(mc, 6),
            "sign": ep.sign_of(mc)["name"],
            "note": "MC provided for reference; whole-sign houses are measured from Lagna only.",
        },
        "planets": planets_out,
    }


# ---------------------------------------------------------------------------
# Divisional charts
# ---------------------------------------------------------------------------


def build_divisional_chart(
    naive_local,
    tz_name: str,
    latitude: float,
    longitude: float,
    division: str,
    ayanamsha: str | None = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
) -> dict:
    spec = resolve_varga(division)
    natal = build_natal_chart(naive_local, tz_name, latitude, longitude, ayanamsha,
                              node_type, true_positions)
    lagna_varga_sign, _ = varga_sign(spec, natal["ascendant"]["longitude"])

    bodies = []
    for body in natal["planets"]:
        vs, vd = varga_sign(spec, body["longitude"])
        bodies.append({
            "name": body["name"],
            "varga_sign_index": vs + 1,
            "varga_sign": SIGNS[vs],
            "degree_in_varga_sign": round(vd, 6),
            "house_from_varga_lagna": (vs - lagna_varga_sign) % 12 + 1,
        })

    return {
        "division": spec.code,
        "division_name": spec.name,
        "significations": spec.significations,
        "input": natal["input"],
        "julian_day_ut": natal["julian_day_ut"],
        "ephemeris_source": natal["ephemeris_source"],
        "conventions_used": {
            **natal["conventions_used"],
            "varga_rule": (
                "Traditional Parasara (BPHS); Trimshamsha uses unequal "
                "classical Mars/Saturn/Jupiter/Mercury/Venus partitions."
                if spec.code == "D30" else "Traditional Parasara (BPHS)"
            ),
            "houses_in_varga": "whole-sign from the varga position of the natal Lagna",
        },
        "lagna": {
            "varga_sign_index": lagna_varga_sign + 1,
            "varga_sign": SIGNS[lagna_varga_sign],
        },
        "bodies": bodies,
    }
