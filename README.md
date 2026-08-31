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
  <a href="https://pypi.org/project/openjyotish/"><img src="https://img.shields.io/pypi/v/openjyotish" alt="PyPI"></a>
  <a href="https://pypi.org/project/openjyotish/"><img src="https://img.shields.io/pypi/pyversions/openjyotish" alt="PyPI Python"></a>
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

Restart Claude — a tools icon (hammer/wrench) appears at the bottom of the chat input. Click it to confirm the server's tools are loaded. Then head to [Example prompts](#example-prompts) for things to try.

## Example prompts

Once the tools are connected, paste any of these straight into Claude. Each one resolves through the server’s tools:

**Natal reading.**

> “I was born 1994-03-21 14:32 in Nashik, India. Tell me my Lagna, nakshatra, D9, and current Mahadasha — and what they mean in plain language.”

Resolves via `geocode_location` → `get_natal_chart` → `get_divisional_chart(D9)` → `get_vimshottari_dasha`.

**Comparing people / synastry.**

> “Compare the charts of these three: A born 1988-06-14 09:20 in New York, B born 1991-11-02 18:45 in London, C born 1985-02-27 05:10 in Sydney. What do the Moon signs and D9s have in common?”

A single `batch` call runs all three charts plus divisional charts at once, with per-chart results kept separate.

**Auspicious-timing screening.**

> “I’m picking a date to launch. Give me the next three auspicious windows this year from the panchang.”

`get_panchang` across candidate dates — or one `batch` over a week of dates to compare at a glance.

**Eclipse hitting your Moon.**

> “Show me the eclipse that will land on my natal Moon, and when.”

`get_natal_chart` (for the Moon’s house) → `get_eclipses`.

**Strength of a planet.**

> “Where in my chart is Saturn strongest for me as a writer?”

`get_natal_chart` → `get_shadbala`, then let the model explain the `rupas` vs. required-strength comparison.

**Life-arc timing.**

> “Walk me through the big timing cycles in my life for the next 20 years.”

`get_vimshottari_dasha` with `levels=4` and a date-range filter.

> Every answer carries a `conventions_used` block (sidereal/Lahiri, whole-sign houses, Vimshottari). Ask the model to “quote the `conventions_used`” if you want the exact assumptions stated back to you.

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
| `batch` | list of `{tool, arguments}` | run many charts/panchang/geocodes in one call — result per op, order preserved, one failure never discards the rest |

All tools are stateless: JSON in, structured dict out. Errors are `{"error": {"type", "message"}}`. Every response includes an explicit `conventions_used` block.

`batch` is the answer to "can't I just loop client-side?": a 20-chart comparison costs **one** model round-trip instead of 20, and a single bad input fails as an `error` entry without discarding the other 19 results — so you keep the deterministic server-side shared state (ephemeris files, gazetteer, ayanamsha resolution) and avoid N round trips of your own.

---

## Setup alternatives

**Install the CLI directly (any machine):**

```bash
uvx openjyotish --version      # prints 0.1.1
uvx openjyotish                # runs the MCP server over stdio
# or install permanently:
uv tool install openjyotish
openjyotish --version
```

**How the `uvx` install works.** `uvx` fetches the wheel from PyPI once and runs isolated; the wheel bundles Swiss Ephemeris `sepl_18.se1`/`semo_18.se1` (1800–2399, AGPL) and GeoNames `cities.csv` (CC-BY), so startup is instant and offline — no separate download step, no network at query time.

A full first-claude query resolves through `geocode_location` → `get_natal_chart` → `get_divisional_chart(D9)` → `get_vimshottari_dasha`, and the assistant answers in plain language, citing `conventions_used`.

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
