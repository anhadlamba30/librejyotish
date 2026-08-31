"""Dev-only cross-check of LibreJyotish varga rules against PyJHora.

Requires: pip install PyJHora (dev dependency, NOT used by the server).
Run: conda run -n librejyotish python scripts/crosscheck_vargas.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from librejyotish.core import charts as ch
from librejyotish.core import ephemeris as ep
from jhora.horoscope.chart import charts as pj

DT = datetime(1994, 3, 21, 14, 32)
LAT, LON, TZ = 28.6139, 77.2090, "Asia/Kolkata"

BODIES = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

PJ_CALLS = {
    "D2": lambda pp: pj.hora_chart(pp, 2),
    "D3": lambda pp: pj.drekkana_chart(pp, 1),
    "D4": lambda pp: pj.chaturthamsa_chart(pp, 1),
    "D7": lambda pp: pj.saptamsa_chart(pp, 1),
    "D9": lambda pp: pj.navamsa_chart(pp, 1),
    "D10": lambda pp: pj.dasamsa_chart(pp, 1),
    "D12": lambda pp: pj.dwadasamsa_chart(pp, 1),
    "D16": lambda pp: pj.shodasamsa_chart(pp, 1),
    "D20": lambda pp: pj.vimsamsa_chart(pp, 1),
    "D24": lambda pp: pj.chaturvimsamsa_chart(pp, 1),
    "D27": lambda pp: pj.nakshatramsa_chart(pp, 1),
    "D30": lambda pp: pj.trimsamsa_chart(pp, 1),
    "D40": lambda pp: pj.khavedamsa_chart(pp, 1),
    "D45": lambda pp: pj.akshavedamsa_chart(pp, 1),
    "D60": lambda pp: pj.shashtyamsa_chart(pp, 1),
}


def main() -> None:
    jd = ep.to_jd(DT, TZ)
    pos = ep.planet_positions(jd)
    asc, _mc = ep.ascendant_and_mc(jd, LAT, LON)

    lons = {"L": asc, **{name: pos[name]["longitude"] for name in BODIES}}
    pp = [
        [i, (int(lon // 30), round(lon % 30, 6))]
        for i, lon in enumerate(lons.values())
    ]

    total_mismatch = 0
    for code, call in PJ_CALLS.items():
        spec = ch.resolve_varga(code)
        mine = {name: ch.varga_sign(spec, lon) for name, lon in lons.items()}
        theirs = {
            (list(lons)[entry[0]]): (entry[1][0], entry[1][1])
            for entry in call(pp)
        }
        bad = [
            f"{name}: mine={mine[name][0]}/{round(mine[name][1],4)} "
            f"pyjh={theirs[name][0]}/{round(theirs[name][1],4)}"
            for name in lons
            if mine[name][0] != theirs[name][0]
            or abs(mine[name][1] - theirs[name][1]) > 1e-4
        ]
        status = "OK " if not bad else "DIFF"
        print(f"{code:>4} {status} ({len(bad)} mismatches)")
        for line in bad:
            print("      ", line)
        total_mismatch += len(bad)

    print("TOTAL MISMATCHES:", total_mismatch)


if __name__ == "__main__":
    main()
