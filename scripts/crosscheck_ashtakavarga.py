"""Cross-check core.ashtakavarga against PyJHora (dev only, not a runtime dep)."""
import sys
from datetime import datetime

sys.path.insert(0, ".")
import swisseph as swe

from librejyotish.core import ephemeris as ep
from librejyotish.core.ashtakavarga import build_ashtakavarga, BAV_PLANETS
from librejyotish.core.constants import SIGNS

ep.init_ephemeris()
swe.set_ephe_path(ep._resolve_ephe_path())

import jhora.const as jc  # noqa: E402
from jhora.horoscope.chart import ashtakavarga as pj_av  # noqa: E402
import jhora.horoscope.chart.charts as pj_charts  # noqa: E402

# PyJHora planet numbering for chart strings: 0..8 = Sun..Ketu
PJ_NUM = {"Sun": "0", "Moon": "1", "Mars": "2", "Mercury": "3", "Jupiter": "4",
          "Venus": "5", "Saturn": "6", "Rahu": "7", "Ketu": "8"}

CASES = [
    ("1994-03-21 Delhi", datetime(1994, 3, 21, 14, 32), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
    ("2000-01-01 Delhi", datetime(2000, 1, 1, 12, 0), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
    ("1947-08-15 Delhi", datetime(1947, 8, 15, 9, 30), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
    ("2026-08-22 Delhi", datetime(2026, 8, 22, 10, 15), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
]


def main():
    from jhora.panchanga import drik
    drik.set_ayanamsa_mode("LAHIRI")
    total_diff = 0
    for label, naive_local, tzn, lat, lon, tz_off in CASES:
        mine = build_ashtakavarga(naive_local, tzn, lat, lon)
        jd_ut = ep.to_jd(naive_local, tzn)
        place = drik.Place("Delhi", lat, lon, tz_off)
        jd_pj = jd_ut + tz_off / 24.0
        # Build their chart string directly from my natal-chart output
        # (positions already verified identical in prior crosschecks).
        from librejyotish.core.charts import build_natal_chart
        chart = build_natal_chart(naive_local, tzn, lat, lon)
        sign_of_planet = {}
        lst = [""] * 12
        for pl in chart["planets"]:
            si = SIGNS.index(pl["sign"])
            lst[si] = (lst[si] + "/" if lst[si] else "") + PJ_NUM[pl["name"]]
            sign_of_planet[pl["name"]] = si
        lst[SIGNS.index(chart["ascendant"]["sign"])] += (
            "/L" if lst[SIGNS.index(chart["ascendant"]["sign"])] else "L")
        bav_pj, sav_pj, prastara_pj = pj_av.get_ashtaka_varga(lst)
        print(f"== {label} ==")
        for i, p in enumerate(BAV_PLANETS):
            diff = sum(abs(a - b) for a, b in zip(mine["bhinnashtakavarga"][p]["bindus_by_sign"].values(), bav_pj[i]))
            ok = diff == 0
            total_diff += diff
            print(f"  {'OK ' if ok else 'DIFF'} BAV {p:8s} mine={list(mine['bhinnashtakavarga'][p]['bindus_by_sign'].values())} pyjh={bav_pj[i]}")
        sav_mine = list(mine["sarvashtakavarga"]["bindus_by_sign"].values())
        diff = sum(abs(a - b) for a, b in zip(sav_mine, sav_pj))
        total_diff += diff
        print(f"  {'OK ' if diff == 0 else 'DIFF'} SAV       mine={sav_mine} pyjh={sav_pj}")
        print(f"  chart string: {lst}")
    print(f"\nTOTAL ABS DIFF: {total_diff}")
    return total_diff


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
