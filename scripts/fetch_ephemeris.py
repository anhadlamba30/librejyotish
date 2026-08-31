"""Download Swiss Ephemeris data files into data/ephe (one-time setup).

Files cover years 1800-2400 CE which comfortably exceeds any practical chart.
Without these files LibreJyotish transparently falls back to the built-in
Moshier ephemeris (sub-arcsecond accuracy for this era, no downloads needed).

Run: conda run -n librejyotish python scripts/fetch_ephemeris.py
"""

import sys
import urllib.request
from pathlib import Path

EPHE_DIR = Path(__file__).resolve().parent.parent / "data" / "ephe"

BASE_URLS = [
    "https://www.astro.com/ftp/swisseph/ephe/",
    "https://github.com/aloistr/swisseph/raw/master/ephe/",
]

FILES = [
    "sepl_18.se1",  # Sun..Pluto, 1800-2400
    "semo_18.se1",  # Moon, Mars..Pluto refined, 1800-2400
]


def fetch(name: str) -> bool:
    dest = EPHE_DIR / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  {name}: already present")
        return True
    for base in BASE_URLS:
        url = base + name
        try:
            print(f"  {name}: downloading {url} ...")
            with urllib.request.urlopen(url, timeout=60) as resp:
                dest.write_bytes(resp.read())
            print(f"  {name}: saved ({dest.stat().st_size} bytes)")
            return True
        except Exception as exc:  # noqa: BLE001 - try next mirror
            print(f"    failed: {exc}")
    return False


def main() -> int:
    EPHE_DIR.mkdir(parents=True, exist_ok=True)
    ok = all(fetch(name) for name in FILES)
    print("ephemeris files ready" if ok else "some downloads failed; "
          "LibreJyotish will use the built-in Moshier fallback")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
