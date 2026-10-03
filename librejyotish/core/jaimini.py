"""Jaimini padas and chara karakas (Layer 1: computation only, no interpretation).

Contents
- Arudha padas A1..A12 (Bhava Padas): the reflected image of each house.
  A1 is the Arudha Lagna (AL); A12 is the Upapada Lagna (UL).
- Chara karakas in both the 7-karaka (Parashara) and 8-karaka (Jaimini)
  schemes, ranked by degree-in-sign.
- Karakamsha/Swamsha: the Atmakaraka's Navamsha (D9) sign, read both as a
  point (Swamsha) and as a lagna over the rasi chart (Karakamsha).

Conventions (surfaced in every response's conventions_used block):
- Pada rule (BPHS 29): count the lord's whole-sign distance from its house,
  project the same count forward from the lord. When the raw pada falls in
  the 1st or 7th from its house, the 10th sign therefrom is the pada instead.
  The two classical sub-clauses (same-house -> 10th therefrom; 7th -> 4th
  from the original house) are algebraically identical to this unified rule,
  as is the "lord in the 4th owns the pada outright" corollary — so a single
  code path covers all cases.
- Lord scheme is Parashara single lords (Mars for Scorpio, Saturn for
  Aquarius, per SIGN_LORDS). The Jaimini stronger-lord evaluation
  (Mars/Ketu, Saturn/Rahu) is a documented lineage variant and is NOT applied.
- Karaka ranking uses full-precision degree-in-sign; Rahu in the 8-scheme is
  counted backwards (30 - degree_in_sign, since Rahu moves counter-zodiacally)
  and Ketu is excluded. Near-ties (< 1 arcsecond apart) are reported, not
  resolved by fiat.
- Swamsha = the Atmakaraka's D9 sign (the point); Karakamsha = that sign
  used as a lagna over the D1 (rasi) placements (the chart).
"""

from __future__ import annotations

from . import charts, ephemeris as ep
from .constants import SIGNS, SIGN_LORDS, normalize_deg

# Traditional names per Bhava Pada (A1..A12).
PADA_NAMES = [
    "Arudha Lagna",   # A1
    "Dhana Pada",      # A2
    "Vikrama Pada",    # A3 (Bhratru Pada)
    "Matru Pada",      # A4 (Sukha Pada)
    "Mantra Pada",     # A5 (Putra Pada)
    "Roga Pada",       # A6 (Satru Pada)
    "Dara Pada",       # A7 (Kalatra Pada)
    "Marana Pada",     # A8
    "Pitru Pada",      # A9
    "Karma Pada",      # A10
    "Labha Pada",      # A11
    "Upapada",         # A12 (Vyaya Pada)
]

# Static definitional glosses per pada (what the pada reflects outwardly).
# Same status as varga `significations`: labels, not interpretive judgment.
PADA_SIGNIFIES = [
    "public image, worldly status, how the self appears",
    "wealth, assets and family resources as seen outwardly",
    "courage, initiative, siblings",
    "mother, home, comforts and property",
    "children, intellect, counsel and devotion",
    "disease, enemies, litigation and service",
    "spouse and partners, romance, business partnerships",
    "longevity, crises and hidden matters",
    "father, dharma, fortune and mentors",
    "career, public deeds and reputation",
    "gains, networks and elder siblings",
    "marriage and committed union",
]

# Static definitional glosses per karaka role.
KARAKA_SIGNIFIES = {
    "Atmakaraka": "soul, self",
    "Amatyakaraka": "career, advisor",
    "Bhratrukaraka": "siblings",
    "Matrukaraka": "mother",
    "Pitrukaraka": "father",
    "Putrakaraka": "children",
    "Gnatikaraka": "rivals, strife",
    "Darakaraka": "spouse",
}

KARAKA_PLANETS_7 = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]

SEVEN_KARAKA_ROLES = [
    "Atmakaraka", "Amatyakaraka", "Bhratrukaraka", "Matrukaraka",
    "Putrakaraka", "Gnatikaraka", "Darakaraka",
]

# 8-karaka (Sanjay Rath / K.N. Rao reading): Rahu joins ranked backwards and
# Pitrukaraka takes slot 5, splitting the parental significators.
EIGHT_KARAKA_ROLES = [
    "Atmakaraka", "Amatyakaraka", "Bhratrukaraka", "Matrukaraka",
    "Pitrukaraka", "Putrakaraka", "Gnatikaraka", "Darakaraka",
]

#: Degree gap below which two karaka candidates are flagged as tied (1 arcsecond).
TIE_TOLERANCE_DEG = 1.0 / 3600.0

ARUDHA_CONVENTIONS = (
    "BPHS Pada rule: count lord's whole-sign distance from its house, "
    "project forward from the lord; raw pada in 1st/7th from its house -> "
    "10th therefrom. Parashara single lords (Mars/Scorpio, Saturn/Aquarius); "
    "Jaimini stronger-lord variant not applied."
)

KARAKA_CONVENTIONS = (
    "Ranked by full-precision degree-in-sign (Sun..Saturn); 8-scheme adds "
    "Rahu counted backwards (30 - degree) and inserts Pitrukaraka at slot 5; "
    "Ketu excluded. Near-ties (< 1 arcsecond) reported, not resolved."
)


def arudha_pada(house_sign: int, lord_sign: int) -> dict:
    """Arudha pada sign index (0..11) for a house/lord sign pair.

    Both inputs are whole-sign indices (0 = Aries). Returns the pada index
    plus the intermediate values so callers (and tests) can audit the rule.
    """
    house_sign %= 12
    lord_sign %= 12
    count = (lord_sign - house_sign) % 12 + 1
    raw = (lord_sign + count - 1) % 12
    if (raw - house_sign) % 12 in (0, 6):
        # Raw pada in the 1st or 7th from its house: take the 10th therefrom.
        return {
            "pada_sign_index": (raw + 9) % 12,
            "count": count,
            "raw_sign_index": raw,
            "exception_applied": True,
        }
    return {
        "pada_sign_index": raw,
        "count": count,
        "raw_sign_index": raw,
        "exception_applied": False,
    }


def all_arudha_padas(lagna_sign: int, graha_signs: dict[str, int]) -> list[dict]:
    """All twelve Bhava Padas for a chart.

    `lagna_sign` is the ascendant's sign index; `graha_signs` maps planet
    name -> sign index (whole-sign). House i (1-indexed) sits at
    (lagna + i - 1) % 12 and is ruled by the Parashara lord of that sign.
    """
    lagna_sign %= 12
    padas = []
    for house in range(1, 13):
        house_sign = (lagna_sign + house - 1) % 12
        lord = SIGN_LORDS[house_sign]
        lord_sign = graha_signs[lord] % 12
        calc = arudha_pada(house_sign, lord_sign)
        pada = calc["pada_sign_index"]
        # Result-first field order: where the pada lands, then how it was derived.
        padas.append({
            "pada": f"A{house}",
            "name": PADA_NAMES[house - 1],
            "signifies": PADA_SIGNIFIES[house - 1],
            "pada_sign": SIGNS[pada],
            "pada_house_from_lagna": (pada - lagna_sign) % 12 + 1,
            "house": house,
            "house_sign": SIGNS[house_sign],
            "lord": lord,
            "lord_sign": SIGNS[lord_sign],
            "count": calc["count"],
            "raw_sign": SIGNS[calc["raw_sign_index"]],
            "exception_applied": calc["exception_applied"],
        })
    return padas


def chara_karakas(longitudes: dict[str, float], scheme: str = "seven") -> dict:
    """Chara karaka ranking for one scheme ('seven' or 'eight').

    `longitudes` maps planet name -> sidereal longitude (degrees). Returns
    the ordered role list with ranking degrees and any near-tie warnings.
    """
    scheme = scheme.lower()
    if scheme == "seven":
        roles = SEVEN_KARAKA_ROLES
        candidates = [(p, normalize_deg(longitudes[p]) % 30.0) for p in KARAKA_PLANETS_7]
    elif scheme == "eight":
        roles = EIGHT_KARAKA_ROLES
        candidates = [(p, normalize_deg(longitudes[p]) % 30.0) for p in KARAKA_PLANETS_7]
        rahu_deg = 30.0 - (normalize_deg(longitudes["Rahu"]) % 30.0)
        # A Rahu at exactly 0 deg in-sign reads as a full 30 (highest rank).
        candidates.append(("Rahu", rahu_deg if rahu_deg > 0 else 30.0))
    else:
        raise ValueError(f"scheme must be 'seven' or 'eight', got '{scheme}'")

    # Stable sort, highest degree first; planet order breaks exact ties.
    order = {p: i for i, p in enumerate(KARAKA_PLANETS_7 + ["Rahu"])}
    ranked = sorted(candidates, key=lambda c: (-c[1], order[c[0]]))

    warnings: list[str] = []
    for (p1, d1), (p2, d2) in zip(ranked, ranked[1:]):
        if abs(d1 - d2) < TIE_TOLERANCE_DEG:
            warnings.append(
                f"{p1} ({d1:.6f}\u00b0) and {p2} ({d2:.6f}\u00b0) are within "
                f"1 arcsecond — their {roles[ranked.index((p1, d1))]} / "
                f"{roles[ranked.index((p2, d2))]} order is exact-longitude "
                f"sensitive; some lineages substitute Sthira karakas on ties."
            )

    return {
        "scheme": scheme,
        "karakas": [
            {"role": role, "planet": planet,
             "signifies": KARAKA_SIGNIFIES[role],
             "degree_in_sign": round(deg, 6)}
            for (planet, deg), role in zip(ranked, roles)
        ],
        "warnings": warnings,
    }


def karakamsha(atmakaraka_longitude: float, graha_signs: dict[str, int]) -> dict:
    """Karakamsha reading for one Atmakaraka longitude.

    Returns the Swamsha (AK's D9 sign) and every graha's whole-sign house
    counted from it (the Karakamsha chart over D1 placements).
    """
    spec = charts.resolve_varga("D9")
    swamsha, _ = charts.varga_sign(spec, atmakaraka_longitude)
    return {
        "swamsha_sign": SIGNS[swamsha],
        "houses_from_karakamsha": {
            name: (sign - swamsha) % 12 + 1 for name, sign in graha_signs.items()
        },
    }


def build_jaimini(
    naive_local,
    tz_name: str,
    latitude: float,
    longitude: float,
    ayanamsha: str | None = "lahiri",
    node_type: str = "true",
    true_positions: bool = False,
) -> dict:
    """Full Jaimini factor set for a birth moment/place (see module docstring)."""
    jd = ep.to_jd(naive_local, tz_name)
    source = ep.ephemeris_source()
    aya_key, _, aya_label = ep.resolve_ayanamsha(ayanamsha)
    positions = ep.planet_positions(jd, ayanamsha=aya_key, node_type=node_type,
                                    true_positions=true_positions)
    asc, _mc = ep.ascendant_and_mc(jd, latitude, longitude, ayanamsha=aya_key,
                                   true_positions=true_positions)

    lagna_sign = int(normalize_deg(asc) // 30)
    graha_signs = {
        name: int(normalize_deg(positions[name]["longitude"]) // 30)
        for name in charts.ALL_GRAHAS
    }
    padas = all_arudha_padas(lagna_sign, graha_signs)

    longitudes = {name: positions[name]["longitude"] for name in charts.ALL_GRAHAS}
    seven = chara_karakas(longitudes, "seven")
    eight = chara_karakas(longitudes, "eight")

    karakamsha_out = {}
    for scheme_name, table in (("seven", seven), ("eight", eight)):
        ak_planet = table["karakas"][0]["planet"]
        k = karakamsha(longitudes[ak_planet], graha_signs)
        karakamsha_out[scheme_name] = {"atmakaraka": ak_planet, **k}

    warnings: list[str] = []
    for table in (seven, eight):
        warnings.extend(table["warnings"])

    upapada = next(p for p in padas if p["pada"] == "A12")
    arudha_lagna = next(p for p in padas if p["pada"] == "A1")

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
            "ayanamsha": {"key": aya_key, "name": aya_label,
                           "value_degrees": round(ep.ayanamsha_value(jd, aya_key), 6)},
            "node_type": node_type,
            "position_type": "true" if true_positions else "apparent",
            "lord_scheme": {
                "key": "parashara",
                "name": ("Single lords (Mars rules Scorpio, Saturn rules Aquarius); "
                         "Jaimini stronger-lord evaluation with Ketu/Rahu not applied"),
            },
            "arudha_rule": ARUDHA_CONVENTIONS,
            "karaka_rule": KARAKA_CONVENTIONS,
            "swamsha_vs_karakamsha": ("Swamsha = the Atmakaraka's D9 sign (the point); "
                                      "Karakamsha = that sign used as lagna over D1 signs (the chart)"),
            "interpretation": "none — raw padas/karakas only",
        },
        "warnings": warnings,
        "lagna_sign": SIGNS[lagna_sign],
        "moon_sign": SIGNS[graha_signs["Moon"]],
        "arudha_lagna": arudha_lagna,
        "upapada": upapada,
        "arudha_padas": padas,
        "chara_karakas": {"seven": seven, "eight": eight},
        "karakamsha": karakamsha_out,
    }
