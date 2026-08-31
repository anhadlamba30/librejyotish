"""Smoke test: boots the server package and exercises each tool.

Catches restructure regressions (import paths, bundled data, entry point).
Runs via `conda run -n openjyotish python -m pytest tests/test_smoke.py`.
"""

import subprocess
import sys


def test_package_version_matches_server():
    import openjyotish
    import openjyotish.server as srv

    assert openjyotish.__version__ == "0.1.1"
    assert srv.server.version == openjyotish.__version__


def test_cli_version_flag():
    result = subprocess.run(
        [sys.executable, "-m", "openjyotish.server", "--version"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0
    assert "0.1.1" in result.stdout


def test_bundled_data_available():
    from openjyotish.core import ephemeris as ep
    from openjyotish.core import geocode as gc
    # Ephemeris data files are bundled in the wheel
    assert ep.init_ephemeris() == "swiss_ephemeris_data_files"
    assert ep.EPHE_PATH.exists()
    assert (ep.EPHE_PATH / "sepl_18.se1").exists()
    # Gazetteer is bundled
    assert gc.GAZETTEER.exists()
    assert gc.GAZETTEER.stat().st_size > 1_000_000


def test_all_tools_smoke():
    import openjyotish.server as srv

    birth = dict(datetime_local="1994-03-21T14:32:00", latitude=19.997, longitude=73.79, timezone="Asia/Kolkata")

    # Each tool should return a dict with conventions_used or candidates, no error
    r1 = srv.get_natal_chart(**birth)
    assert "error" not in r1
    assert "conventions_used" in r1
    assert r1["ephemeris_source"] == "swiss_ephemeris_data_files"

    r2 = srv.get_divisional_chart(**birth, division="D9")
    assert "error" not in r2

    r3 = srv.get_vimshottari_dasha(**birth, levels=1)
    assert "error" not in r3

    r4 = srv.get_panchang(date_local="1994-03-21", latitude=19.997, longitude=73.79, timezone="Asia/Kolkata")
    assert "error" not in r4

    r5 = srv.get_ashtakavarga(**birth)
    assert "error" not in r5

    r6 = srv.get_shadbala(**birth)
    assert "error" not in r6

    r7 = srv.get_current_transits(**birth, as_of_datetime_local="2026-01-01T12:00:00")
    assert "error" not in r7

    r8 = srv.get_eclipses(**birth, as_of_datetime_local="2026-01-01T12:00:00", count=2)
    assert "error" not in r8

    r9 = srv.geocode_location("Nashik, India")
    assert "error" not in r9
    assert r9["resolved"]


def test_entry_point_importable():
    # console_scripts entry point `openjyotish = openjyotish.server:main` must be importable
    from importlib.metadata import entry_points

    eps = entry_points(group="console_scripts") if hasattr(entry_points, "__call__") else entry_points()
    # entry_points API differs across Python versions; just check import works
    import openjyotish.server as srv
    assert callable(srv.main)
