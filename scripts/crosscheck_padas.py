"""Dev-only cross-check of LibreJyotish Arudha Padas against PyJHora.

Parity is checked under a SHARED convention: jhora's Scorpio/Aquarius dual
lordship is forced to Mars/Saturn (our Parashara single-lord scheme) via its
dhasa-calculation overrides. Any remaining mismatch is a real rule bug.

Requires: PyJHora in the env (dev dependency, NOT used by the server).
Run: conda run -n librejyotish python scripts/crosscheck_padas.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jhora import const
from jhora.horoscope.chart import arudhas as pj_arudhas

from librejyotish.core import ephemeris as ep
from librejyotish.core import jaimini as jm
from librejyotish.core.constants import SIGNS

SIGNS_INDEX = {name: i for i, name in enumerate(SIGNS)}

# Force jhora onto our Parashara single-lord convention for this comparison.
const.scorpio_owner_for_dhasa_calculations = const.MARS_ID
const.aquarius_owner_for_dhasa_calculations = const.SATURN_ID

BODIES = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

CHARTS = [
    # (datetime_local, lat, lon, tz, label) — mirrors tests/reference_charts
    (datetime(1947, 8, 15, 0, 0), 28.6139, 77.2090, "Asia/Kolkata", "1947 Delhi"),
    (datetime(1994, 3, 21, 14, 32), 19.9975, 73.7898, "Asia/Kolkata", "1994 Nashik"),
    (datetime(2000, 1, 1, 12, 0), 40.7128, -74.0060, "America/New_York", "2000 NYC"),
    (datetime(2026, 9, 27, 8, 0), 51.5074, -0.1278, "Europe/London", "2026 London"),
    (datetime(1988, 6, 14, 9, 20), 40.7128, -74.0060, "America/New_York", "1988 NYC"),
    (datetime(1991, 11, 2, 18, 45), 51.5074, -0.1278, "Europe/London", "1991 London"),
]


def main() -> None:
    total = 0
    for dt, lat, lon, tz, label in CHARTS:
        jd = ep.to_jd(dt, tz)
        pos = ep.planet_positions(jd)
        asc, _mc = ep.ascendant_and_mc(jd, lat, lon)

        lons = {"L": asc, **{b: pos[b]["longitude"] for b in BODIES}}
        # jhora planet labels: 'L' for Lagna, 0..8 for Sun..Ketu.
        pp = [["L", (int(asc // 30) % 12, round(asc % 30, 6))]]
        pp += [[i, (int(pos[b]["longitude"] // 30) % 12,
                     round(pos[b]["longitude"] % 30, 6))]
               for i, b in enumerate(BODIES)]
        theirs = pj_arudhas.bhava_arudhas_from_planet_positions(pp)

        lagna = int(asc // 30) % 12
        signs = {b: int(pos[b]["longitude"] // 30) % 12 for b in BODIES}
        mine = jm.all_arudha_padas(lagna, signs)

        bad = []
        for i, entry in enumerate(mine):
            mine_idx = SIGNS_INDEX[entry["pada_sign"]]
            if mine_idx != theirs[i] % 12:
                bad.append(f"{entry['pada']}: mine={entry['pada_sign']} pyjh={theirs[i]}")
        status = "OK " if not bad else "DIFF"
        print(f"{label:>14} {status} ({len(bad)} mismatches)")
        for line in bad:
            print("      ", line)
        total += len(bad)

    print("TOTAL MISMATCHES:", total)


if __name__ == "__main__":
    main()
