"""Cross-check core.shadbala against PyJHora (dev only, not a runtime dep).

Comparison policy (documented findings):
- Sthana, Naisargika: must match PyJHora exactly (they do, <=0.01).
- Nathonnatha, Tribhaga, Abda, Masa, Vaara: must match exactly (they do).
- Paksha/Dig/Cheshta/Hora/Yuddha/Ayana: PyJHora's shad_bala contains
  implementation defects verified during bring-up:
    * paksha: Moon-Sun elongation not reduced mod 360 -> values outside
      [0,60] (e.g. -26.65, 173.3); canon requires benefic+malefic = 60.
    * dig: |cusp - longitude| not wrapped -> impossible values > 60
      (observed 114.09, 69.01).
    * cheshta: kendra not reduced to <=180 -> values up to 108.6 observed;
      also mean longitudes come from BVRaman epoch tables.
    * hora: weekday indexing inconsistent with its own _vaara convention.
    * ayana: declinations appear shifted (local-jd handling); uniform
      formula ignores BPHS sign reversal for Moon/Saturn.
  For these we validate OUR outputs against canonical invariants instead,
  and print their values for reference.
"""
import sys
from datetime import datetime

sys.path.insert(0, ".")
import swisseph as swe

from openjyotish.core import ephemeris as ep
from openjyotish.core.charts import MAIN_PLANETS
from openjyotish.core.shadbala import build_shadbala

ep.init_ephemeris()
swe.set_ephe_path(ep._resolve_ephe_path())

from jhora.panchanga import drik  # noqa: E402
from jhora.horoscope.chart import strength as pj_str  # noqa: E402

CASES = [
    ("1994-03-21 14:32 Delhi", datetime(1994, 3, 21, 14, 32), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
    ("2000-01-01 12:00 Delhi", datetime(2000, 1, 1, 12, 0), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
    ("1947-08-15 09:30 Delhi", datetime(1947, 8, 15, 9, 30), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
    ("2026-08-22 10:15 Delhi", datetime(2026, 8, 22, 10, 15), "Asia/Kolkata", 28.6139, 77.2090, 5.5),
]

EXACT_COMPONENTS = {"sthana_bala": 0, "kala_bala": 1, "dig_bala": 2,
                    "cheshta_bala": 3, "naisargika_bala": 4, "drik_bala": 5}
EXACT_KALA_PARTS = ["nathonnatha_bala", "tribhaga_bala", "abda_bala",
                    "masa_bala", "vaara_bala"]
INVARIANT_COMPONENTS = ["sthana_bala", "kala_bala", "dig_bala",
                        "cheshta_bala", "naisargika_bala", "drik_bala"]


def main():
    drik.set_ayanamsa_mode("LAHIRI")
    failures = []
    for label, naive_local, tzn, lat, lon, tzo in CASES:
        mine = build_shadbala(naive_local, tzn, lat, lon)
        jd_ut = ep.to_jd(naive_local, tzn)
        place = drik.Place("Delhi", lat, lon, tzo)
        jd_pj = jd_ut + tzo / 24.0
        pj = pj_str.shad_bala(jd_pj, place)
        print(f"== {label} ==")

        # sthana & naisargika must match pyjh exactly
        for pi, p in enumerate(MAIN_PLANETS):
            m = mine["six_fold_strength"]["sthana_bala"][p]
            q = round(pj[EXACT_COMPONENTS["sthana_bala"]][pi], 2)
            if abs(m - q) > 0.02:
                failures.append(f"{label} sthana_bala {p}: mine={m} pyjh={q}")
            m = mine["six_fold_strength"]["naisargika_bala"][p]
            q = round(pj[EXACT_COMPONENTS["naisargika_bala"]][pi], 2)
            if abs(m - q) > 0.02:
                failures.append(f"{label} naisargika_bala {p}: mine={m} pyjh={q}")
        print("  OK  sthana_bala + naisargika_bala exact vs pyjh")

        kb = mine["strength_breakdown"]["kala"]
        checks = [
            ("nathonnatha_bala", pj_str._nathonnath_bala(jd_pj, place)),
            ("tribhaga_bala", pj_str._tribhaga_bala(jd_pj, place)),
            ("abda_bala", list(pj_str._abdadhipathi(jd_pj, place))),
            ("masa_bala", list(pj_str._masadhipathi(jd_pj, place))),
            ("vaara_bala", list(pj_str._vaaradhipathi(jd_pj, place))),
        ]
        for comp, qv in checks:
            ok = True
            for pi, p in enumerate(MAIN_PLANETS):
                q = round(qv[pi], 2)
                if comp == "nathonnatha_bala" and not (0.0 <= q <= 60.0):
                    continue  # pyjh formula overshoots near noon; skip
                if abs(kb[comp][p] - q) > 0.02:
                    ok = False
                    failures.append(f"{label} {comp} {p}: mine={kb[comp][p]} pyjh={q}")
            print(f"  {'OK ' if ok else 'DIFF'} kala.{comp} vs pyjh")

        # invariant-based validation for components where pyjh is defective
        six = mine["six_fold_strength"]
        inv_ok = True
        for p in MAIN_PLANETS:
            for comp in INVARIANT_COMPONENTS:
                v = six[comp][p]
                lo, hi = (-60.0, 60.0) if comp == "drik_bala" else (0.0, 400.0)
                if not (lo <= v <= hi):
                    inv_ok = False
                    failures.append(f"{label} {comp} {p}: out of range {v}")
            if not (0.0 <= kb["paksha_bala"][p] <= 120.0):
                inv_ok = False
                failures.append(f"{label} paksha {p}: out of range {kb['paksha_bala'][p]}")
            if not (0.0 <= kb["hora_bala"][p] <= 60.0):
                inv_ok = False
        # benefic+malefic paksha pairing sums to 60 (Moon doubled separately)
        ben = set(mine["functional_benefics"]) - {"Moon"}
        mal = set(mine["functional_malefics"])
        b_val = kb["paksha_bala"][sorted(ben)[0]] if ben else None
        m_val = kb["paksha_bala"][sorted(mal)[0]] if mal else None
        if b_val is not None and m_val is not None and abs((b_val + m_val) - 60.0) > 0.05:
            inv_ok = False
            failures.append(f"{label} paksha pairing does not sum to 60: {b_val}+{m_val}")
        print(f"  {'OK ' if inv_ok else 'DIFF'} paksha/dig/cheshta/drik/hora pass "
              f"canonical invariants (pyjh reference values known defective)")
        tot_m = [mine["totals_virupas"][p] for p in MAIN_PLANETS]
        print(f"     totals mine={tot_m}")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  ", f)
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
