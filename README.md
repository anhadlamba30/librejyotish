<p align="center">
  <img src="https://raw.githubusercontent.com/anhadlamba30/openjyotish/master/assets/logo.png" width="180" alt="OpenJyotish logo">
</p>

<h1 align="center">OpenJyotish</h1>

<p align="center">
  Deterministic Vedic astrology calculations as an MCP server
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-2.0-blue" alt="MCP"></a>
  <a href="https://github.com/anhadlamba30/openjyotish/blob/master/LICENSE"><img src="https://img.shields.io/github/license/anhadlamba30/openjyotish" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <!-- PyPI badges — uncomment after first publish
  <a href="https://pypi.org/project/openjyotish/"><img src="https://img.shields.io/pypi/v/openjyotish" alt="PyPI"></a>
  <a href="https://pypi.org/project/openjyotish/"><img src="https://img.shields.io/pypi/pyversions/openjyotish" alt="PyPI Python"></a>
  -->
</p>

<p align="center">
  Open-source and free. Sidereal positions, houses, dashas and panchang, computed from Swiss Ephemeris.
</p>

---

## 30-second quickstart

**Add to Claude Desktop** — `Settings → Developer → Edit Config` → `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "openjyotish": {
      "command": "uvx",
      "args": ["openjyotish"]
    }
  }
}
```

`uvx` fetches the wheel from PyPI once and runs isolated; the wheel bundles Swiss Ephemeris `sepl_18.se1`/`semo_18.se1` (1800–2399, AGPL) and GeoNames `cities.csv` (CC-BY), so startup is instant and offline. Restart Claude — a tools icon (hammer/wrench) appears at the bottom of the chat input. Click it to confirm the server's tools are loaded, then ask:

> “I was born 1994-03-21 14:32 in Nashik, India — what’s my Lagna, nakshatra, D9 and current Mahadasha?”

This resolves through `geocode_location` → `get_natal_chart` → `get_divisional_chart(D9)` → `get_vimshottari_dasha`, and the assistant answers in plain language, citing `conventions_used`.

Or install the CLI directly:

```bash
uvx openjyotish --version      # prints 0.1.0
uvx openjyotish                # runs the MCP server over stdio
# or install permanently:
uv tool install openjyotish
openjyotish --version
```

---

## Conventions

Reported in every response’s `conventions_used` block so you know exactly what was assumed:

- **Zodiac:** sidereal, **Lahiri (Chitrapaksha)** ayanamsha by default
- **Houses:** whole-sign from the Lagna sign
- **Dasha:** Vimshottari
- **Nodes:** true by default
- **Positions:** apparent by default
- **Varas, tithis, etc.:** sunrise-anchored civil day

## Tools

| Tool | Input | Output |
| --- | --- | --- |
| `get_natal_chart` | birth datetime + location | ascendant, planets with sign/nakshatra/house, retrograde & combustion flags, dignities |
| `get_divisional_chart` | + `division` (`D1`–`D60`) | varga sign & house per body (Parashara rules incl. classical Trimshamsha) |
| `get_vimshottari_dasha` | birth input (+ optional reference moment) | mahadasha → antardasha → pratyantardasha tree, current chain annotated |
| `get_panchang` | date + location | tithi, vara, nakshatra/pada, yoga, karana, sunrise/sunset |
| `get_ashtakavarga` | birth input | Bhinnashtakavarga per planet (with prastara), Sarvashtakavarga totals |
| `get_shadbala` | birth input | six-fold strength: sthana, dig, kala, cheshta, naisargika, drik; virupas/rupas vs required |
| `get_current_transits` | birth input + optional as-of moment | transit positions with house from natal Lagna and natal Moon (raw positions only) |
| `get_eclipses` | birth input + optional as-of moment + `count` | next solar/lunar eclipses: exact event times, type, eclipse point (sidereal sign/nakshatra) and its house from natal Lagna & Moon |
| `geocode_location` | place string + optional `country` | offline gazetteer lookup → latitude/longitude/IANA-timezone candidates (use the top hit’s numbers as the `latitude`/`longitude` inputs above) |

All tools are stateless: JSON in, structured dict out. Errors are `{"error": {"type", "message"}}`. Every response includes an explicit `conventions_used` block.

---

## Setup alternatives

**From source (development):**

```bash
conda env create -f environment.yml   # or your own venv with the two deps
conda run -n openjyotish python -m openjyotish.server   # or python server.py (shim)
# after pip install -e .:
pip install -e .
openjyotish --version
openjyotish
```

Ephemeris and gazetteer live in `openjyotish/data/` inside the wheel under AGPL (Swiss Ephemeris dual-licensed AGPL/commercial; this project distributes the `.se1` files under AGPL). If files are absent, the server falls back to the built-in Moshier model and warns loudly, reporting the source in `ephemeris_source`.

To rebuild the gazetteer or refresh `.se1` files:

```bash
conda run -n openjyotish python scripts/build_gazetteer.py
conda run -n openjyotish python scripts/download_ephe.py  # refreshes openjyotish/data/ephe/
```

**MCP client config — from source / conda:**

```json
{
  "mcpServers": {
    "openjyotish": {
      "command": "conda",
      "args": ["run", "-n", "openjyotish", "python", "-m", "openjyotish.server"]
    }
  }
}
```

Legacy `python /path/to/server.py` still works via a shim at the repo root.

---

## Validation

- `scripts/crosscheck_*.py` compare every module against [PyJHora](https://github.com/naturalstupid/PyJHora) as an independent oracle (dev-only). All vargas, dasha boundaries, panchang elements, Ashtakavarga tables, and the exactly-comparable Shadbala components match; known PyJHora defects in paksha/dig/cheshta/hora/ayana handling follow canon instead (see module docstrings).
- `tests/reference_charts/fixtures.json` pins four reference charts (1947, 1994, 2000, 2026 Delhi); `pytest` replays them end-to-end:

```bash
conda run -n openjyotish python -m pytest tests/ -q
```

---

## Acknowledgments

- **Swiss Ephemeris** — [Astrodienst / pyswisseph](https://pypi.org/project/pyswisseph/): the astronomical engine behind every calculation.
- **PyJHora** — [naturalstupid/PyJHora](https://github.com/naturalstupid/PyJHora): independent reference used to validate the Vedic math (dev-only, not imported in production).
- **GeoNames** — [GeoNames](https://www.geonames.org): city data powering the offline `geocode_location` gazetteer.

## License

AGPL-3.0-or-later. Swiss Ephemeris is AGPL/commercial dual-licensed; this project uses it under the AGPL and carries the license forward. Hosting the MCP server as a network service triggers AGPL’s network clause (source disclosure to users of the service).

Data attributions: Swiss Ephemeris `.se1` files © Astrodienst / Alois Treindl (AGPL); GeoNames `cities.csv` © GeoNames (CC BY 4.0) — see `openjyotish/data/gazetteer/README.md`.
