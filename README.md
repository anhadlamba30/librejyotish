<p align="center">
  <img src="https://raw.githubusercontent.com/anhadlamba30/librejyotish/master/assets/logo.png" width="180" alt="LibreJyotish logo">
</p>

<h1 align="center">LibreJyotish</h1>

<p align="center">
  Deterministic Vedic astrology calculations as an MCP server
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-2.0-blue" alt="MCP"></a>
  <a href="https://github.com/anhadlamba30/librejyotish/blob/master/LICENSE"><img src="https://img.shields.io/github/license/anhadlamba30/librejyotish" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python">
  <a href="https://pypi.org/project/librejyotish/"><img src="https://img.shields.io/pypi/v/librejyotish" alt="PyPI"></a>
  <a href="https://pypi.org/project/librejyotish/"><img src="https://img.shields.io/pypi/pyversions/librejyotish" alt="PyPI Python"></a>
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
    "librejyotish": {
      "command": "uvx",
      "args": ["librejyotish"]
    }
  }
}
```

Restart Claude — a tools icon (hammer/wrench) appears at the bottom of the chat input. Click it to confirm the server's tools are loaded. Then head to [Example prompts](#example-prompts) for things to try.

## Example prompts

Once the tools are connected, paste any of these straight into Claude. Each one resolves through the server’s tools:

**✨ Natal reading.**

> “I was born 1994-03-21 14:32 in Nashik, India. Tell me my Lagna, nakshatra, D9, and current Mahadasha — and what they mean in plain language.”

**💞 Love & compatibility.**

> “How compatible are me and my partner? I’m born 1988-06-14 09:20 in New York, they’re born 1991-11-02 18:45 in London. Compare our Moons, D9 charts, and current dashas for marriage, communication, and long-term fit.”

**📅 Auspicious-timing screening.**

> “I’m picking a date to launch. Give me the next three auspicious windows this year from the panchang.”

**🌑 Eclipse hitting your Moon.**

> “Show me the eclipse that will land on my natal Moon, and when.”

**💪 Strength of a planet.**

> “Where in my chart is Saturn strongest for me as a writer?”

**⏳ Life-arc timing.**

> “Walk me through the big timing cycles in my life for the next 20 years.”


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
| `get_vimshottari_dasha` | birth input; optional `reference_datetime_local` (defaults to now), `start_date`/`end_date` bounds, `levels` | mahadasha → antardasha tree by default (`levels=2`); `current_periods` current chain always included; deeper levels (3/4) only with a date window |
| `get_panchang` | date + location | tithi, vara, nakshatra/pada, yoga, karana, sunrise/sunset |
| `get_ashtakavarga` | birth input | Bhinnashtakavarga per planet (with prastara), Sarvashtakavarga totals |
| `get_shadbala` | birth input | six-fold strength: sthana, dig, kala, cheshta, naisargika, drik; virupas/rupas vs required |
| `get_current_transits` | birth input + optional as-of moment | transit positions with house from natal Lagna and natal Moon (raw positions only) |
| `get_eclipses` | birth input + optional as-of moment + `count` | next solar/lunar eclipses: exact event times, type, eclipse point (sidereal sign/nakshatra) and its house from natal Lagna & Moon |
| `geocode_location` | place string + optional `country` | offline gazetteer lookup → latitude/longitude/IANA-timezone candidates (use the top hit’s numbers as the `latitude`/`longitude` inputs above) |
| `batch` | list of `{tool, arguments}` | run many charts/panchang/geocodes in one call — result per op, order preserved, one failure never discards the rest |

All tools are stateless: JSON in, structured dict out. Errors are `{"error": {"type", "message"}}`. Every response includes an explicit `conventions_used` block.

`batch` is the answer to "can't I just loop client-side?": a 20-chart comparison costs **one** model round-trip instead of 20, and a single bad input fails as an `error` entry without discarding the other 19 results — so you keep the deterministic server-side shared state (ephemeris files, gazetteer, ayanamsha resolution) and avoid N round trips of your own.

### Defensive by default

The server greets a sketchy input with a warning rather than a silently wrong chart. It flags an internally inconsistent date/time/location (e.g. a timezone that doesn't match the coordinates, or coordinates that resolve to a place 500+ km away, producing a sunset before sunrise) and tells you exactly what to fix. Use the top `geocode_location` candidate's numbers and strip stray guesses — the tools will catch the rest.

Dasha responses are bounded so a model can't blow up its own context: `get_vimshottari_dasha` defaults to `levels=2` (mahadasha + antardasha, ~81 periods) and `reference_datetime_local` to now, so the usual "what's running now?" query gets the current chain without asking. A `levels>=3` call with no `start_date`/`end_date` range is clamped to `levels=2` with a warning telling the model how to get the deeper periods — passing a date window around the timeframe you actually need.

### Limitations

- **Gazetteer covers cities ≥ 20k population.** `geocode_location` resolves against a generously-sourced but deliberately-shipped-down GeoNames subset, so obscure small towns and villages won't resolve — and in this domain a lot of birthplaces are villages. If an exact hit isn't found, the tool reports `resolved: false` with the searched string echoed back; treat that as "resolve the coordinates yourself and pass them directly" rather than a bug.
- **Ephemeris spans 1800–2399** (the bundled Swiss Ephemeris `sepl_18.se1`/`semo_18.se1` files). Births outside that range fall back to the built-in Moshier model, which is reported in `ephemeris_source`.

---

## Setup alternatives

**Install the CLI directly (any machine):**

```bash
uvx librejyotish --version      # prints 0.1.2
uvx librejyotish                # runs the MCP server over stdio
# or install permanently:
uv tool install librejyotish
librejyotish --version
```

**How the `uvx` install works.** `uvx` fetches the wheel from PyPI once and runs isolated; the wheel bundles Swiss Ephemeris `sepl_18.se1`/`semo_18.se1` (1800–2399, AGPL) and GeoNames `cities.csv` (CC-BY), so startup is instant and offline — no separate download step, no network at query time.

A full first-claude query resolves through `geocode_location` → `get_natal_chart` → `get_divisional_chart(D9)` → `get_vimshottari_dasha`, and the assistant answers in plain language, citing `conventions_used`.

**From source (development):**

```bash
conda env create -f environment.yml   # or your own venv with the two deps
conda run -n librejyotish python -m librejyotish.server   # or python server.py (shim)
# after pip install -e .:
pip install -e .
librejyotish --version
librejyotish
```

Ephemeris and gazetteer live in `librejyotish/data/` inside the wheel under AGPL (Swiss Ephemeris dual-licensed AGPL/commercial; this project distributes the `.se1` files under AGPL). If files are absent, the server falls back to the built-in Moshier model and warns loudly, reporting the source in `ephemeris_source`.

To rebuild the gazetteer or refresh `.se1` files:

```bash
conda run -n librejyotish python scripts/build_gazetteer.py
conda run -n librejyotish python scripts/download_ephe.py  # refreshes librejyotish/data/ephe/
```

**MCP client config — from source / conda:**

```json
{
  "mcpServers": {
    "librejyotish": {
      "command": "conda",
      "args": ["run", "-n", "librejyotish", "python", "-m", "librejyotish.server"]
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
conda run -n librejyotish python -m pytest tests/ -q
```

---

## Acknowledgments

- **Swiss Ephemeris** — [Astrodienst / pyswisseph](https://pypi.org/project/pyswisseph/): the astronomical engine behind every calculation.
- **PyJHora** — [naturalstupid/PyJHora](https://github.com/naturalstupid/PyJHora): independent reference used to validate the Vedic math (dev-only, not imported in production).
- **GeoNames** — [GeoNames](https://www.geonames.org): city data powering the offline `geocode_location` gazetteer.

## License

AGPL-3.0-or-later. Swiss Ephemeris is AGPL/commercial dual-licensed; this project uses it under the AGPL and carries the license forward. Hosting the MCP server as a network service triggers AGPL’s network clause (source disclosure to users of the service).

Data attributions: Swiss Ephemeris `.se1` files © Astrodienst / Alois Treindl (AGPL); GeoNames `cities.csv` © GeoNames (CC BY 4.0) — see `librejyotish/data/gazetteer/README.md`.
