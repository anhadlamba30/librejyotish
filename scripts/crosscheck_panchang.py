"""Dev-only cross-check of OpenJyotish panchanga against PyJHora.

Requires pip install PyJHora (dev-only). 
Run: conda run -n openjyotish python scripts/crosscheck_panchang.py
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import swisseph as swe

from core import ephemeris as ep
from core import panchang as op

ep.init_ephemeris()
swe.set_ephe_path(ep._resolve_ephe_path())

import jhora.const as jc
from jhora.panchanga import drik

drik.set_ayanamsa_mode("LAHIRI")

LAT, LON, TZ_NAME = 28.6139, 77.2090, "Asia/Kolkata"
TZ_OFF = 5.5


def pyjhora_sunrise(y, m, d):
    place = drik.Place("Delhi", LAT, LON, TZ_OFF)
    jd_local = ep.to_jd(__import__("datetime").datetime(y, m, d), TZ_NAME) + TZ_OFF / 24.0
    res = drik.sunrise(jd_local, place)
    return res


def main() -> None:
    cases = [
        (1994, 3, 21),
        (2026, 8, 22),
        (2000, 1, 1),
        (1947, 8, 15),
    ]
    for (y, m, d) in cases:
        mine = op.build_panchang(date(y, m, d), TZ_NAME, LAT, LON)
        jd_anchor_ut = mine["julian_day_ut_at_anchor"]
        # PyJHora at my anchor moment (local-jd space)
        jd_pj = jd_anchor_ut + TZ_OFF / 24.0
        place = drik.Place("Delhi", LAT, LON, TZ_OFF)

        tithi_idx = int(drik.tithi(jd_pj, place)[0])
        nak_no = int(drik.nakshatra(jd_pj, place)[0])  # 1..27, Ashwini=1
        yoga_idx = int(drik.yogam(jd_pj, place)[0])
        # drik.karana()'s convenience wrapper misclassifies morning anchors
        # via its display formatter; derive karana from their raw positions.
        moon = drik.sidereal_longitude(jd_anchor_ut, jc._MOON)
        sun = drik.sidereal_longitude(jd_anchor_ut, jc._SUN)
        karana_idx = int(((moon - sun) % 360) // 6) + 1
        vaara = int(drik.vaara(jd_pj, place, show_vedic_day=False))  # 0=Sunday

        print(f"== {y}-{m:02d}-{d:02d} ==")
        checks = [
            ("tithi", mine["tithi"]["index_one_based"], tithi_idx),
            ("nakshatra", mine["nakshatra"]["name"], op.NAKSHATRAS[nak_no - 1]),
            ("yoga", mine["yoga"]["index_one_based"], yoga_idx),
            ("karana", mine["karana"]["index_one_based"], karana_idx),
            ("vara", mine["vara"]["name"], op.VARAS[vaara]),
        ]
        for label, a, b in checks:
            ok = str(a) == str(b)
            print(f"  {'OK ' if ok else 'DIFF'} {label:10s} mine={a!r} pyjh={b!r}")
        sr = pyjhora_sunrise(y, m, d)
        print(f"  sunrise: mine={mine['sunrise']} pyjh={sr[1]}")


if __name__ == "__main__":
    main()
