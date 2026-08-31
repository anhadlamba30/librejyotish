"""Shim for backwards compatibility: `python server.py` at repo root.

The canonical server lives at `openjyotish.server`; this wrapper delegates
so existing `conda run -n openjyotish python server.py` invocations keep working.
"""

# Re-export everything so `import server` still exposes tool functions for tests.
from openjyotish.server import (  # noqa: F401
    batch,
    geocode_location,
    get_ashtakavarga,
    get_current_transits,
    get_divisional_chart,
    get_eclipses,
    get_natal_chart,
    get_panchang,
    get_shadbala,
    get_vimshottari_dasha,
    main,
    server,
)

__all__ = [
    "server",
    "main",
    "batch",
    "get_natal_chart",
    "get_divisional_chart",
    "get_vimshottari_dasha",
    "get_panchang",
    "get_ashtakavarga",
    "get_shadbala",
    "get_current_transits",
    "get_eclipses",
    "geocode_location",
]

if __name__ == "__main__":
    main()
