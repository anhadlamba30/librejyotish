"""Dev-only cross-check of LibreJyotish Vimshottari math against PyJHora.

Patches PyJHora to Lahiri ayanamsha / 365.25-day year so both engines share
identical conventions, then compares raw Julian-day period boundaries (bypassing
PyJHora's display formatting, which applies its own offsets).

Requires pip install PyJHora (dev-only; not used by the server).
Run: conda run -n librejyotish python scripts/crosscheck_dasha.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import swisseph as swe

from librejyotish.core import dasha as od
from librejyotish.core import ephemeris as ep

ep.init_ephemeris()  # point both engines at data/ephe Swiss files
swe.set_ephe_path(ep._resolve_ephe_path())

import jhora.const as jc

jc.sidereal_year = 365.25

from jhora.panchanga import drik
from jhora.horoscope.dhasa.graha import vimsottari as pjv

drik.set_ayanamsa_mode("LAHIRI")
pjv.year_duration = 365.25

DT = datetime(1994, 3, 21, 14, 32)
LAT, LON, TZ = 28.6139, 77.2090, "Asia/Kolkata"
TZ_OFF = 5.5  # PyJHora expects LOCAL julian day = JD_UT + tz_off/24

LORD_NAMES = {0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury", 4: "Jupiter",
              5: "Venus", 6: "Saturn", 7: "Rahu", 8: "Ketu"}
LORD_IDS = {v: k for k, v in LORD_NAMES.items()}


def main() -> None:
    place = drik.Place("Delhi", LAT, LON, TZ_OFF)
    jd_ut = ep.to_jd(DT, TZ)
    jd_pj = jd_ut + TZ_OFF / 24.0

    mds = rebuild_raw()["mahadashas"]
    natal_lord = mds[0]["lord"]

    total_bad = 0

    print("== Full natal-mahadasha start ==")
    lord_id, pj_start = pjv.vimsottari_dasha_start_date(jd_pj, place)
    delta_min = abs((pj_start - TZ_OFF / 24.0) - mds[0]["_start_jd"]) * 1440
    total_bad += delta_min >= 1e-3
    print(f"  {'OK ' if delta_min < 1e-3 else 'DIFF'} {LORD_NAMES[lord_id]} ({delta_min:.6f} min)")

    print("== Mahadasha boundaries ==")
    md_pj = pjv.vimsottari_mahadasa(jd_pj, place)
    for lord_id, pj_local in md_pj.items():
        lord = LORD_NAMES[lord_id]
        mine = next(e["_start_jd"] for e in mds if e["lord"] == lord)
        delta_min = abs((pj_local - TZ_OFF / 24.0) - mine) * 1440
        total_bad += delta_min >= 1e-3
        print(f"  {'OK ' if delta_min < 1e-3 else 'DIFF'} {lord:8s} ({delta_min:.6f} min)")

    print("== Antardasha boundaries (all 9 mahadashas x 9 bhukthis) ==")
    bad_ad = 0
    checked_ad = 0
    for md in mds:
        md_lord_id = LORD_IDS[md["lord"]]
        pj_md_start_local = md_pj[md_lord_id]
        bhuktis = pjv._vimsottari_bhukti(md_lord_id, pj_md_start_local)
        for sub in md["sub_periods"]:
            pj_ut = bhuktis[LORD_IDS[sub["lord"]]] - TZ_OFF / 24.0
            delta_min = abs(pj_ut - sub["_start_jd"]) * 1440
            checked_ad += 1
            if delta_min >= 1e-3:
                bad_ad += 1
                print(f"  DIFF {md['lord']}>{sub['lord']:8s} ({delta_min:.6f} min)")
    print(f"  {checked_ad - bad_ad}/{checked_ad} OK")

    print("== Pratyantardasha boundaries (natal MD > first 3 ADs x 9) ==")
    bad_pd = 0
    checked_pd = 0
    md0 = mds[0]
    md_lord_id = LORD_IDS[md0["lord"]]
    bhuktis = pjv._vimsottari_bhukti(md_lord_id, md_pj[md_lord_id])
    for sub in md0["sub_periods"][:3]:
        antaras = pjv._vimsottari_antara(md_lord_id, LORD_IDS[sub["lord"]],
                                         bhuktis[LORD_IDS[sub["lord"]]])
        for pd in sub["sub_periods"]:
            pj_ut = antaras[LORD_IDS[pd["lord"]]] - TZ_OFF / 24.0
            delta_min = abs(pj_ut - pd["_start_jd"]) * 1440
            checked_pd += 1
            if delta_min >= 1e-3:
                bad_pd += 1
                print(f"  DIFF {md0['lord']}>{sub['lord']}>{pd['lord']:8s} ({delta_min:.6f} min)")
    print(f"  {checked_pd - bad_pd}/{checked_pd} OK")

    total_bad += bad_ad + bad_pd
    print(f"\nTOTAL FAILURES: {total_bad}")


def rebuild_raw() -> dict:
    """Re-run the builder keeping private JD fields (absolute-window mode)."""
    jd = ep.to_jd(DT, TZ)
    positions = ep.planet_positions(jd, true_positions=True)
    _, fraction = od._nakshatra_fraction(positions["Moon"]["longitude"])
    starting_lord = ep.nakshatra_of(positions["Moon"]["longitude"])["lord"]
    balance_years = od.VIMSHOTTARI_YEARS[starting_lord] * (1.0 - fraction)

    first_full_days = od.VIMSHOTTARI_YEARS[starting_lord] * od.YEAR_DAYS
    cursor = jd + balance_years * od.YEAR_DAYS - first_full_days
    mds = []
    for lord in od._sequence_from(starting_lord):
        full = od.VIMSHOTTARI_YEARS[lord] * od.YEAR_DAYS
        mds.append(od._add_period(lord, cursor, full, 2, TZ))
        cursor += full
    return {"mahadashas": mds}


if __name__ == "__main__":
    main()
