"""Build the bundled gazetteer used by the `geocode_location` tool.

Downloads GeoNames `cities1000` (populated places with population >= 1000) and
reduces it to `data/gazetteer/cities.csv`: populated places with population >=
20,000, keeping the columns needed for offline geocoding (name, asciiname,
alternatenames, latitude, longitude, country, admin1, population, IANA
timezone).

GeoNames data is licensed CC-BY; see data/gazetteer/README.md for attribution.

Usage::
    conda run -n openjyotish python scripts/build_gazetteer.py

Offline rebuilds can reuse a previously downloaded `cities1000.zip` via
`--zip path/to/cities1000.zip`.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://download.geonames.org/export/dump/cities1000.zip"
MIN_POPULATION = 20_000

OUT = Path(__file__).resolve().parent.parent / "data" / "gazetteer" / "cities.csv"

COLUMNS = [
    "name",
    "asciiname",
    "alternatenames",
    "latitude",
    "longitude",
    "country_code",
    "admin1_code",
    "population",
    "timezone",
]


def _fetch(zip_path: str | None) -> list[str]:
    if zip_path:
        with zipfile.ZipFile(zip_path) as z:
            name = next(n for n in z.namelist() if n.endswith("cities1000.txt"))
            return z.read(name).decode("utf-8").splitlines()
    print(f"net: downloading {URL}", file=sys.stderr)
    raw = urllib.request.urlopen(URL, timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.endswith("cities1000.txt"))
        return z.read(name).decode("utf-8").splitlines()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", help="reuse a local cities1000.zip instead of downloading")
    args = ap.parse_args()

    rows = _fetch(args.zip)
    out = []
    for line in rows:
        f = line.split("\t")
        if len(f) < 18:
            continue
        if f[6].strip() != "P":  # feature class: populated place
            continue
        try:
            pop = int(f[14])
        except ValueError:
            continue
        if pop < MIN_POPULATION:
            continue
        out.append([f[1], f[2], f[3], f[4], f[5], f[8], f[10], str(pop), f[17]])

    out.sort(key=lambda r: (r[5], r[0].casefold()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        w.writerows(out)
    print(f"wrote {len(out)} rows -> {OUT}")
    print(f"{OUT.stat().st_size / 1024:.1f} KiB")


if __name__ == "__main__":
    main()