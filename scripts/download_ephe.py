"""Fetch Swiss Ephemeris data files into data/ephe/.

The Moshier fallback is built into pyswisseph, but the project is committed to
not silently degrading precision: if `data/ephe/` has no ephemeris files the
server warns loudly (see core/ephemeris.py). This script installs the standard
high-precision set, covering years 1800-2399:

- sepl_18.se1  (planet positions, t<1826 pol, t>1826 eph)
- semo_18.se1  (moon positions)

Files are downloaded once at setup and are gitignored (data/ephe/*).

Source: the aloistr/swisseph mirror on GitHub raw. The upstream Swiss
Ephemeris licensing (dual: commercial / free) restricts redistribution of the
`.se1` ephemeris files themselves, which is why they are not committed to this
repository.

Usage::
    conda run -n openjyotish python scripts/download_ephe.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

FILES = {
    "sepl_18.se1": "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/sepl_18.se1",
    "semo_18.se1": "https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/semo_18.se1",
}

EPHE_DIR = Path(__file__).resolve().parent.parent / "data" / "ephe"


def _fetch(url: str, dest: Path, timeout: int) -> int:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        with dest.open("wb") as out:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
    return dest.stat().st_size


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--timeout", type=int, default=120, help="per-file network timeout (s)")
    args = ap.parse_args()

    EPHE_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = EPHE_DIR / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"present: {dest}")
            continue
        print(f"net: downloading {name} ...", file=sys.stderr)
        n = _fetch(url, dest, args.timeout)
        print(f"wrote {n} bytes -> {dest}")
        if n == 0:
            dest.unlink()
            sys.exit(f"download of {name} produced an empty file; aborting")


if __name__ == "__main__":
    main()