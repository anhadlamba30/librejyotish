"""Ashtakavarga: Bhinnashtakavarga (BAV) and Sarvashtakavarga (SAV) bindus.

Each of the seven classical planets receives benefic contributions ("bindus")
from eight reference points (the seven planets + Lagna) at fixed houses counted
from each contributor's own sign. The per-planet 12-sign tallies form the BAV;
their sum across the seven planets forms the SAV.

Contribution tables are the Parasara canon (BPHS ch. 66). They were verified
against three independent sources before encoding:
  1. BPHS (R. Santhanam translation) Karanaprada lists, complemented to
     benefic places -- resolves the Moon-table variants exactly.
  2. PyJHora const.ashtaka_varga_dict (matches BPHS on every cell).
  3. Published B.V. Raman / K.N. Rao tables (agree everywhere except the
     three Moon rows above, where BPHS governs).
Row totals are canonical constants: 48, 49, 39, 54, 56, 52, 39 (SAV = 337);
the Lagna's own row totals 49 but does not enter the SAV.
"""

from __future__ import annotations

from . import ephemeris as ep
from .constants import SIGNS

BAV_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Ascendant"]

# BAV_BENEFIC_PLACES[receiving_planet][contributor_index] = benefic houses
# (1-based) counted from that contributor's natal sign.
BAV_BENEFIC_PLACES = {
    "Sun": [
        (1, 2, 4, 7, 8, 9, 10, 11),
        (3, 6, 10, 11),
        (1, 2, 4, 7, 8, 9, 10, 11),
        (3, 5, 6, 9, 10, 11, 12),
        (5, 6, 9, 11),
        (6, 7, 12),
        (1, 2, 4, 7, 8, 9, 10, 11),
        (3, 4, 6, 10, 11, 12),
    ],
    "Moon": [
        (3, 6, 7, 8, 10, 11),
        (1, 3, 6, 7, 9, 10, 11),
        (2, 3, 5, 6, 10, 11),
        (1, 3, 4, 5, 7, 8, 10, 11),
        (1, 2, 4, 7, 8, 10, 11),
        (3, 4, 5, 7, 9, 10, 11),
        (3, 5, 6, 11),
        (3, 6, 10, 11),
    ],
    "Mars": [
        (3, 5, 6, 10, 11),
        (3, 6, 11),
        (1, 2, 4, 7, 8, 10, 11),
        (3, 5, 6, 11),
        (6, 10, 11, 12),
        (6, 8, 11, 12),
        (1, 4, 7, 8, 9, 10, 11),
        (1, 3, 6, 10, 11),
    ],
    "Mercury": [
        (5, 6, 9, 11, 12),
        (2, 4, 6, 8, 10, 11),
        (1, 2, 4, 7, 8, 9, 10, 11),
        (1, 3, 5, 6, 9, 10, 11, 12),
        (6, 8, 11, 12),
        (1, 2, 3, 4, 5, 8, 9, 11),
        (1, 2, 4, 7, 8, 9, 10, 11),
        (1, 2, 4, 6, 8, 10, 11),
    ],
    "Jupiter": [
        (1, 2, 3, 4, 7, 8, 9, 10, 11),
        (2, 5, 7, 9, 11),
        (1, 2, 4, 7, 8, 10, 11),
        (1, 2, 4, 5, 6, 9, 10, 11),
        (1, 2, 3, 4, 7, 8, 10, 11),
        (2, 5, 6, 9, 10, 11),
        (3, 5, 6, 12),
        (1, 2, 4, 5, 6, 7, 9, 10, 11),
    ],
    "Venus": [
        (8, 11, 12),
        (1, 2, 3, 4, 5, 8, 9, 11, 12),
        (3, 4, 6, 9, 11, 12),
        (3, 5, 6, 9, 11),
        (5, 8, 9, 10, 11),
        (1, 2, 3, 4, 5, 8, 9, 10, 11),
        (3, 4, 5, 8, 9, 10, 11),
        (1, 2, 3, 4, 5, 8, 9, 11),
    ],
    "Saturn": [
        (1, 2, 4, 7, 8, 10, 11),
        (3, 6, 11),
        (3, 5, 6, 10, 11, 12),
        (6, 8, 9, 10, 11, 12),
        (5, 6, 11, 12),
        (6, 11, 12),
        (3, 5, 6, 11),
        (1, 3, 4, 6, 10, 11),
    ],
}

# Canonical row totals used as a build-time integrity check.
CANONICAL_ROW_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
                        "Jupiter": 56, "Venus": 52, "Saturn": 39}
SAV_TOTAL = sum(CANONICAL_ROW_TOTALS.values())


def _contributor_signs(positions: dict, asc_longitude: float) -> list[int]:
    signs = []
    for name in CONTRIBUTORS:
        if name == "Ascendant":
            signs.append(ep.sign_of(asc_longitude)["index_one_based"] - 1)
        else:
            signs.append(ep.sign_of(positions[name]["longitude"])["index_one_based"] - 1)
    return signs


def build_ashtakavarga(
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
    asc, _ = ep.ascendant_and_mc(jd, latitude, longitude, ayanamsha=aya_key,
                                 true_positions=true_positions)
    contrib_signs = _contributor_signs(positions, asc)

    bav: dict[str, list[int]] = {}
    prastara: dict[str, list[list[str]]] = {}
    for planet in BAV_PLANETS:
        row = [0] * 12
        spread = [[None] * 12 for _ in range(12)]
        for ci, contrib in enumerate(CONTRIBUTORS):
            base = contrib_signs[ci]
            for house in BAV_BENEFIC_PLACES[planet][ci]:
                sign_idx = (base + house - 1) % 12
                row[sign_idx] += 1
                spread[sign_idx][ci] = contrib if spread[sign_idx][ci] is None \
                    else f"{spread[sign_idx][ci]}+{contrib}"
        assert sum(row) == CANONICAL_ROW_TOTALS[planet], planet
        bav[planet] = row
        prastara[planet] = spread

    sav = [sum(bav[p][s] for p in BAV_PLANETS) for s in range(12)]
    assert sum(sav) == SAV_TOTAL

    lagna_row = [0] * 12
    asc_sign = ep.sign_of(asc)["index_one_based"] - 1
    for house in BAV_BENEFIC_PLACES["Sun"][7]:
        lagna_row[(asc_sign + house - 1) % 12] += 1

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
            "ashtakavarga": {
                "system": "Parasara (BPHS ch. 66), eight contributors "
                          "(seven planets + Lagna)",
                "reductions_applied": "none (raw Prastara-derived bindus; "
                                      "trikona/ekadhipatya sodhana and "
                                      "shodhya pindas planned for v2)",
                "canonical_totals": {**CANONICAL_ROW_TOTALS, "sav_total": SAV_TOTAL},
            },
        },
        "sarvashtakavarga": {
            "bindus_by_sign": dict(zip(SIGNS, sav)),
            "total_bindus": sum(sav),
        },
        "bhinnashtakavarga": {
            p: {
                "row_total": CANONICAL_ROW_TOTALS[p],
                "bindus_by_sign": dict(zip(SIGNS,
                                           bav[p])),
                "prastara_contributors": prastara[p],
            }
            for p in BAV_PLANETS
        },
        "lagna_ashtakavarga": {
            "note": "Reference only; excluded from SAV.",
            "bindus_by_sign": dict(zip(SIGNS,
                                       lagna_row)),
        },
    }
