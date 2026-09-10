"""Parashari graha drishti (planetary aspects): whole-sign, no orbs.

Distinct from the degree-based sphuta drishti used internally by Shadbala
(`core/shadbala.py::_drishti_value`, which yields virupa strengths for
Drik bala). Graha drishti here is boolean: a planet aspects another iff
the target sits in one of the caster's aspect signs.

Classical basis: BPHS — every graha aspects the 7th from itself;
Mars additionally 4th and 8th; Jupiter 5th and 9th; Saturn 3rd and 10th.
Counting is inclusive-forward from the caster's own sign.

Nodes convention: Rahu/Ketu aspect the 7th only by default
(`nodes="seventh_only"`), the most common Parashari baseline. Other
schools give nodes Jupiter-like (5/7/9) or no aspects at all; pass
`nodes="jupiter_like"` or `nodes="none"` to select those explicitly.
The active convention is always echoed in each response's
`conventions_used` block so readers know what was assumed.
"""

from __future__ import annotations

# Zero-based sign offsets from the caster's sign index.
# offset 6 == 7th house, offset 3 == 4th house, etc.
_OFFSET_TO_HOUSE_LABEL = {
    2: "3rd",
    3: "4th",
    4: "5th",
    6: "7th",
    7: "8th",
    8: "9th",
    9: "10th",
}

_BASE_OFFSETS: dict[str, tuple[int, ...]] = {
    "Sun": (6,),
    "Moon": (6,),
    "Mercury": (6,),
    "Venus": (6,),
    "Mars": (3, 6, 7),
    "Jupiter": (4, 6, 8),
    "Saturn": (2, 6, 9),
}

_NODE_MODES = ("seventh_only", "jupiter_like", "none")


def offsets_for(planet: str, nodes: str = "seventh_only") -> tuple[int, ...]:
    """Aspect offsets (zero-based) cast by `planet` under the node convention."""
    if planet in ("Rahu", "Ketu"):
        if nodes not in _NODE_MODES:
            raise ValueError(
                f"nodes must be one of {list(_NODE_MODES)}, got {nodes!r}")
        if nodes == "none":
            return ()
        if nodes == "jupiter_like":
            return (4, 6, 8)
        return (6,)
    try:
        return _BASE_OFFSETS[planet]
    except KeyError:
        raise ValueError(f"unknown planet {planet!r}") from None


def graha_drishti(signs: dict[str, int],
                  nodes: str = "seventh_only") -> dict[str, dict]:
    """Compute whole-sign graha drishti for planets given as {name: sign_index}.

    Returns {planet: {"casts": [{"target": name, "type": "7th"|...}],
    "receives": [{"caster": name, "type": ...}]}}. Both lists are sorted by
    planet name for determinism. `type` is the house counted inclusively
    from the caster (so a "7th" entry in A.casts matches a "7th" entry in
    B.receives when mutual).
    """
    names = list(signs)
    for n, s in signs.items():
        if n not in _BASE_OFFSETS and n not in ("Rahu", "Ketu"):
            raise ValueError(f"unknown planet {n!r}")
        if not isinstance(s, int) or not 0 <= s <= 11:
            raise ValueError(f"sign index for {n!r} must be int 0..11, got {s!r}")
    casts: dict[str, list[dict]] = {n: [] for n in names}
    receives: dict[str, list[dict]] = {n: [] for n in names}
    for caster in names:
        for offset in offsets_for(caster, nodes=nodes):
            label = _OFFSET_TO_HOUSE_LABEL[offset]
            for target in names:
                if target == caster:
                    continue
                if (signs[target] - signs[caster]) % 12 == offset:
                    casts[caster].append({"target": target, "type": label})
                    receives[target].append({"caster": caster, "type": label})
    for n in names:
        casts[n].sort(key=lambda e: e["target"])
        receives[n].sort(key=lambda e: e["caster"])
    return {n: {"casts": casts[n], "receives": receives[n]} for n in names}


def transit_to_natal_aspects(transit_signs: dict[str, int],
                             natal_signs: dict[str, int],
                             nodes: str = "seventh_only") -> dict[str, list[dict]]:
    """For each transiting planet, which natal planets it aspects.

    Offset is measured forward from the *transit* sign to the *natal* sign:
    `(natal_sign - transit_sign) % 12 in offsets_for(transit_planet)`.
    Returns {transit_name: [{"target": natal_name, "type": "7th"|...}]},
    sorted by target name.
    """
    out: dict[str, list[dict]] = {}
    for tname, tsign in transit_signs.items():
        hits = []
        for offset in offsets_for(tname, nodes=nodes):
            for nname, nsign in natal_signs.items():
                if (nsign - tsign) % 12 == offset:
                    hits.append({"target": nname,
                                 "type": _OFFSET_TO_HOUSE_LABEL[offset]})
        hits.sort(key=lambda e: e["target"])
        out[tname] = hits
    return out


Drishti_CONVENTIONS = {
    "system": "Parashari graha drishti (whole-sign, no orbs)",
    "special_aspects": {"Mars": ["4th", "8th"], "Jupiter": ["5th", "9th"],
                        "Saturn": ["3rd", "10th"]},
    "universal_aspect": "7th (all grahas)",
    "nodes": "Rahu/Ketu 7th only (most common Parashari baseline; "
             "other schools use Jupiter-like 5/7/9 or none)",
    "excluded": "partial-strength fractions, Rashi (Jaimini) drishti, "
                "sphuta-drishti virupas (see get_shadbala drik bala)",
}
