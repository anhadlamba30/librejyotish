# OpenJyotish

Deterministic Vedic (Jyotish) astrology computations exposed as an
[Model Context Protocol](https://modelcontextprotocol.io) (MCP) server.

Layer 1 only: pure computation, no interpretation. Every number comes from
Swiss Ephemeris via [pyswisseph](https://pypi.org/project/pyswisseph/); the
calling LLM is responsible for synthesis and communication only — it never
computes or guesses astronomy.

## Conventions

Locked for v1 and reported in every response's `conventions_used` block:

- **Zodiac:** sidereal, **Lahiri (Chitrapaksha)** ayanamsha by default
- **Houses:** whole-sign from the Lagna sign
- **Dasha:** Vimshottari, year = 365.25 days
- **Nodes:** true by default (`node_type: "mean"` available)
- **Positions:** apparent by default (`true_positions: true` for true positions)
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
| `geocode_location` | place string + optional `country` | offline gazetteer lookup → latitude/longitude/IANA-timezone candidates (use the top hit's numbers as the `latitude`/`longitude` inputs above) |

All tools are stateless: JSON-style arguments in, structured dict out. Errors
come back as `{"error": {"type", "message"}}` payloads. Every response includes
an explicit `conventions_used` block.

## Setup

Requires Python ≥ 3.11.

**Quickstart (recommended) — no clone needed:**

```bash
uvx openjyotish --version      # prints 0.1.0
uvx openjyotish                # runs the MCP server over stdio
# or install permanently:
uv tool install openjyotish
openjyotish --version
```

`uvx` fetches the wheel from PyPI (once) and runs it isolated — no conda
setup, no ephemeris download. The wheel bundles the Swiss Ephemeris
`sepl_18.se1`/`semo_18.se1` (1800–2399, AGPL) and the GeoNames gazetteer
(`cities.csv`, CC-BY) so startup is instant and offline.

**From source (development):**

```bash
conda env create -f environment.yml   # or your own venv with the two deps
conda run -n openjyotish python -m openjyotish.server   # or python server.py (shim)
# alternative without conda after `pip install -e .`:
pip install -e .
openjyotish --version
openjyotish
```

Ephemeris and gazetteer are bundled in `openjyotish/data/` inside the wheel
under AGPL (Swiss Ephemeris dual-licensed AGPL/commercial; this project
distributes the `.se1` files under AGPL and carries the license forward).
If the files are absent, the server falls back to the built-in Moshier model
and warns loudly, reporting the source in `ephemeris_source` — but the wheel
ships them, so this only matters for stripped installs.

To rebuild the gazetteer from GeoNames or refresh the `.se1` files:

```bash
conda run -n openjyotish python scripts/build_gazetteer.py
conda run -n openjyotish python scripts/download_ephe.py  # refreshes openjyotish/data/ephe/
```

**MCP client config:**

With `uvx` (recommended — no path needed):

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

From source / conda:

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

## Validation

- `scripts/crosscheck_*.py` compare every module against
  [PyJHora](https://github.com/naturalstupid/PyJHora) as an independent oracle
  (dev-only dependency). All vargas, dasha boundaries, panchang elements,
  Ashtakavarga tables, and the exactly-comparable Shadbala components match;
  known PyJHora defects in paksha/dig/cheshta/hora/ayana handling follow canon
  instead (see module docstrings).
- `tests/reference_charts/fixtures.json` pins four reference charts (1947,
  1994, 2000, 2026 Delhi); `pytest` replays them end-to-end:

```bash
conda run -n openjyotish python -m pytest tests/ -q
```

## Scope notes

- No interpretive rules, no predictions — a v2 rules corpus is planned on top.
- Parashari baseline only in v1 (no KP/Jaimini/Nadi).
- Stateless: nothing is stored or tracked.

## License

AGPL-3.0-or-later. Swiss Ephemeris is AGPL/commercial dual-licensed; this
project uses it under the AGPL and carries the license forward. Hosting the
MCP server as a network service triggers AGPL's network clause (source
disclosure to users of the service).

Data attributions: Swiss Ephemeris `.se1` files © Astrodienst / Alois
Treindl (AGPL); GeoNames `cities.csv` © GeoNames (CC BY 4.0) — see
`openjyotish/data/gazetteer/README.md`.
