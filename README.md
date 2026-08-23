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

All tools are stateless: JSON-style arguments in, structured dict out. Errors
come back as `{"error": {"type", "message"}}` payloads.

## Quickstart

Requires Python ≥ 3.11.

```bash
conda env create -f environment.yml   # or your own venv with the two deps
conda run -n openjyotish python server.py
```

The server speaks MCP over stdio. Example client config:

```json
{
  "mcpServers": {
    "openjyotish": {
      "command": "conda",
      "args": ["run", "-n", "openjyotish", "python", "/path/to/openjyotish/server.py"]
    }
  }
}
```

Ephemeris files (`data/ephe/*.se1`) are bundled; without them the server falls
back to Swiss Ephemeris' built-in Moshier model and says so in
`ephemeris_source`.

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
project uses it under the AGPL and carries the license forward.
