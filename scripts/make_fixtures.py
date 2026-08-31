"""Regenerate tests/reference_charts/fixtures.json from the verified core modules.

The values in this fixture were established correct by scripts/crosscheck_*.py
against PyJHora (independent oracle). Running this script re-derives them; any
unintended change to core math will show up as a test failure.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openjyotish.core import charts, dasha, ephemeris as ep, panchang
from openjyotish.core.ashtakavarga import build_ashtakavarga
from openjyotish.core.shadbala import build_shadbala

CASES = [
    ("case_1994_delhi", "1994-03-21T14:32:00", "Asia/Kolkata", 28.6139, 77.2090,
     "2026-08-22T10:15:00"),
    ("case_2000_delhi", "2000-01-01T12:00:00", "Asia/Kolkata", 28.6139, 77.2090,
     "2026-08-22T10:15:00"),
    ("case_1947_delhi", "1947-08-15T09:30:00", "Asia/Kolkata", 28.6139, 77.2090,
     None),
    ("case_2026_delhi", "2026-08-22T10:15:00", "Asia/Kolkata", 28.6139, 77.2090,
     None),
]

DIVISIONS = ["D2", "D3", "D4", "D7", "D9", "D10", "D12", "D16",
             "D20", "D24", "D27", "D30", "D40", "D45", "D60"]


def build_case(label, iso_local, tz_name, lat, lon, ref_iso):
    naive = datetime.fromisoformat(iso_local)
    out = {"input": {"datetime_local": iso_local, "timezone": tz_name,
                     "latitude": lat, "longitude": lon}}

    natal = charts.build_natal_chart(naive, tz_name, lat, lon)
    out["natal"] = {
        "julian_day_ut": round(natal["julian_day_ut"], 6),
        "ascendant_longitude": round(natal["ascendant"]["longitude"], 4),
        "ascendant_sign": natal["ascendant"]["sign"],
        "planets": {
            p["name"]: {
                "longitude": round(p["longitude"], 4),
                "sign": p["sign"],
                "house_from_lagna": p["house_from_lagna"],
                "retrograde": p["retrograde"],
            } for p in natal["planets"]
        },
    }

    out["divisions"] = {}
    for div in DIVISIONS:
        dc = charts.build_divisional_chart(naive, tz_name, lat, lon, div)
        out["divisions"][div] = {
            "lagna_varga_sign_index": dc["lagna"]["varga_sign_index"],
            **{b["name"]: b["varga_sign_index"] for b in dc["bodies"]},
        }

    tree = dasha.build_vimshottari_dasha(
        naive, tz_name, lat, lon,
        reference_local=datetime.fromisoformat(ref_iso) if ref_iso else None)
    md_out = []
    for md in tree["mahadashas"]:
        entry = {"lord": md["lord"],
                 "start_local": md["start_local"][:19],
                 "end_local": md["end_local"][:19],
                 "first_antardasha_lord": md["sub_periods"][0]["lord"],
                 "last_antardasha_lord": md["sub_periods"][-1]["lord"]}
        first_pd = md["sub_periods"][0]["sub_periods"]
        entry["first_pratyantardasha_lord"] = (
            first_pd[0]["lord"] if first_pd else None)
        md_out.append(entry)
    out["dasha_mahadashas"] = md_out

    if ref_iso is not None:
        cur = tree.get("current_periods")
        if cur:
            out["dasha_current_at_reference"] = [
                {"level": c["level"], "lord": c["lord"]} for c in cur["chain"]]

    d = naive.date()
    pc = panchang.build_panchang(d, tz_name, lat, lon)
    out["panchang"] = {
        "tithi_name": pc["tithi"]["name"],
        "tithi_index_one_based": pc["tithi"]["index_one_based"],
        "vara": pc["vara"]["name"],
        "nakshatra_name": pc["nakshatra"]["name"],
        "nakshatra_pada": pc["nakshatra"]["pada"],
        "yoga_name": pc["yoga"]["name"],
        "karana_name": pc["karana"]["name"],
        "sunrise": pc["sunrise"][:16],
        "sunset": pc["sunset"][:16],
    }

    av = build_ashtakavarga(naive, tz_name, lat, lon)
    out["ashtakavarga"] = {
        planet: row["bindus_by_sign"]
        for planet, row in av["bhinnashtakavarga"].items()
    }
    out["sarvashtakavarga_totals"] = av["sarvashtakavarga"]["bindus_by_sign"]

    sb = build_shadbala(naive, tz_name, lat, lon)
    six = sb["six_fold_strength"]
    kb = sb["strength_breakdown"]["kala"]
    out["shadbala"] = {
        p: {
            "sthana_bala": round(six["sthana_bala"][p], 2),
            "naisargika_bala": round(six["naisargika_bala"][p], 2),
            "nathonnatha_bala": round(kb["nathonnatha_bala"][p], 2),
            "tribhaga_bala": round(kb["tribhaga_bala"][p], 2),
            "abda_bala": round(kb["abda_bala"][p], 2),
            "masa_bala": round(kb["masa_bala"][p], 2),
            "vaara_bala": round(kb["vaara_bala"][p], 2),
        } for p in six["sthana_bala"]
    }
    return out


def main():
    ep.init_ephemeris()
    fixtures = {label: build_case(label, iso, tz, lat, lon, ref)
                for label, iso, tz, lat, lon, ref in CASES}
    dest = ROOT / "tests" / "reference_charts" / "fixtures.json"
    dest.write_text(json.dumps(fixtures, indent=2) + "\n")
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
