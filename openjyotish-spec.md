# OpenJyotish — MCP Server Spec (v1)

**Status:** Draft
**Scope:** Layer 1 only — deterministic Vedic astrology computation. No interpretive/predictive rules, no LLM-in-the-loop logic. That's explicitly out of scope for this version (see "Non-Goals").

---

## 1. Purpose

Give any LLM/agent fast, free, local, and accurate Vedic (Jyotish) astrological calculations — birth charts, divisional charts, dashas, panchang, strength tables — without a paid API and without asking the model to compute or recall astronomy from its own weights (which it will get wrong).

The model is responsible for *synthesis and communication only*. This server is responsible for every number.

## 2. Non-Goals (explicitly out of scope for v1)

- No interpretive rule tables (gochara phalam, argala, yoga-effect narratives, dasha-lord significations). That's a planned v2 "rules corpus" layered on top of this server, built and reviewed separately with community input.
- No natural-language prediction or explanation generation — that's the calling LLM's job.
- No support for multiple competing schools of astrology in v1 (KP system, Jaimini, Nadi). v1 targets mainstream Parashari + standard Vimshottari dasha, the most widely used baseline. Note this explicitly wherever ambiguity could arise (e.g. house system, ayanamsha).
- No user data storage/tracking. Stateless: input in, structured data out.

## 3. Design Principles

1. **Deterministic and auditable.** Every output must be traceable to a specific calculation, not a heuristic or LLM guess.
2. **Local-first.** No network calls at inference time. All ephemeris data bundled or fetched once at install/setup time.
3. **Transparent about defaults.** Ayanamsha (Lahiri by default), house system (whole-sign by default for Vedic), and any other convention must be explicit in every response payload — never silently assumed.
4. **Structured output only.** JSON in, JSON out. No prose, no formatting decisions — that's for the LLM consuming this.
5. **Cite the convention, not the tradition's "meaning."** E.g. return "Saturn in Capricorn, house 10 (whole-sign from Lagna)" — never "Saturn is well placed here."

## 4. Tech Stack (proposed)

- **Language:** Python 3.11+
- **MCP framework:** official `mcp` Python SDK (v2 `MCPServer` API)
- **Astronomical core:** `pyswisseph` (Swiss Ephemeris bindings) — industry standard precision. **Decided:** AGPL path (see §4 decision note). High-precision `.se1` files are fetched once at setup by `scripts/download_ephe.py` into `data/ephe/` (gitignored, not redistributed — Swiss Ephemeris license restricts redistribution); the server falls back to the built-in Moshier model — loudly, via `warnings.warn` + `ephemeris_source` — only if the files are absent. This removes the silent precision fallback that undermines determinism.
- **Higher-level chart/dasha logic:** built directly on `pyswisseph` (no wrapper library); PyJHora is used only as a dev-time oracle in `scripts/crosscheck_*.py` and never imported by `core/` or `server.py`.
- **Geocoding:** bundled offline gazetteer (`data/gazetteer/cities.csv`) + `core/geocode.py`; built by `scripts/build_gazetteer.py` from GeoNames `cities1000`. No network at query time.
- **Packaging:** pip-installable, stateless; ephemeris data downloaded once at setup (see §7 repo layout).

## 5. Tool Definitions (v1)

All tools take a birth/event datetime + location (or a `chart_id` if we add chart caching later — out of scope for now, stateless first).

### 5.1 `get_natal_chart`
**Input:**
```json
{
  "datetime": "1994-03-21T14:32:00",
  "timezone": "Asia/Kolkata",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "ayanamsha": "lahiri"        // optional, default lahiri
}
```
**Output:** Ascendant, all planetary longitudes/signs/nakshatras/houses, retrograde flags, combustion flags. Explicit `ayanamsha_used` and `house_system_used` fields in every response.

### 5.2 `get_divisional_chart`
**Input:** same as above + `division` (e.g. `"D9"`, `"D10"`, `"D60"`)
**Output:** planet-to-sign/house mapping for that varga.

### 5.3 `get_vimshottari_dasha`
**Input:** natal chart input
**Output:** full mahadasha → antardasha → pratyantardasha tree with start/end dates, plus "current period as of [given date]" if a reference date is supplied.

### 5.4 `get_panchang`
**Input:** date + location
**Output:** tithi, vara, nakshatra, yoga, karana, sunrise/sunset.

### 5.5 `get_ashtakavarga`
**Input:** natal chart input
**Output:** Sarvashtakavarga + Bhinnashtakavarga (per-planet) bindu tables.

### 5.6 `get_shadbala`
**Input:** natal chart input
**Output:** six-fold strength breakdown per planet, numeric + normalized score.

### 5.7 `get_current_transits`
**Input:** natal chart input + "as of" date (defaults to now)
**Output:** current planetary positions + their position relative to the natal chart (houses/signs from Lagna and from Moon). **Raw positions only — no favorable/unfavorable judgment (that's v2).**

### 5.8 `get_eclipses`
**Input:** natal chart input + "as of" date (defaults to now) + `count` (1–20, default 4)
**Output:** the next `count` solar/lunar eclipses as global events:
- exact event times — time-of-maximum/greatest and first/last contact — in UT and local time;
- eclipse type: solar from SWE `sol_eclipse_when_glob`'s return flag (total/annular/partial/annular-total); lunar from SWE `lun_eclipse_how`'s umbral magnitude (≥1 total, >0 partial, else penumbral). The lunar return flag is unreliable in current pyswisseph builds and is *not* used;
- lunar umbral/penumbral magnitudes and Saros series/member;
- the sidereal eclipse point — Moon for a lunar eclipse, Sun for a solar one — with sign, degree, and nakshatra, plus its whole-sign house from natal Lagna and from natal Moon.

**Design notes:** a time-window search, distinct from the snapshots returned by `get_current_transits`; the birth lat/long anchor houses only (eclipses are global). A future `get_astrological_events` aggregator is a thin wrapper over this, not a redesign. No eclipse-to-interpretation mapping (that's v2/v3).

### 5.9 `geocode_location` (helper — not astronomical)
**Input:** `place` string (e.g. `"Nashik, India"`), optional `country`, optional `limit`
**Output:** ranked candidate `{name, country_code, admin1_code, latitude, longitude, timezone, population}` tuples, a `matched_tier` (exact name → asciiname → alternate name → prefix) and an `ambiguous` flag.

**Design notes:** offline and deterministic, backed by the committed GeoNames-derived gazetteer (`data/gazetteer/cities.csv`, populated places ≥ 20k population, CC-BY — see `data/gazetteer/README.md`). No network at query time (§3). `ambiguous: true` (alias match, prefix match, or region filter dropped) is the caller's cue to confirm the intended place before feeding the coordinates to the computation tools. The seven computation tools keep their numeric `latitude`/`longitude` contract.

## 6. Non-Functional Requirements

- Every tool response includes a `conventions_used` block (ayanamsha, house system, dasha system) so the calling LLM never has to guess what assumptions were made.
- Validated against a fixed set of reference charts with known-correct outputs from at least two independent sources (e.g. cross-check against astro.com and one Vedic-specific tool) before calling any calculation "done."
- All tools must work fully offline once ephemeris data is present locally.
- Response time target: sub-200ms per tool call on typical hardware (this is pure math, no reason it should be slow).

## 7. Repo Structure (proposed)

```
openjyotish/
├── server.py              # MCP server entrypoint, tool registration
├── core/
│   ├── ephemeris.py       # swisseph wrapper, ayanamsha handling, ephe source detection
│   ├── charts.py          # natal + divisional chart logic, whole-sign house helper
│   ├── dasha.py           # vimshottari dasha tree
│   ├── panchang.py
│   ├── ashtakavarga.py
│   ├── shadbala.py
│   ├── eclipses.py        # sol/lun eclipse search: times, type, point, saros
│   └── geocode.py         # offline gazetteer resolution (helper)
├── scripts/
│   ├── download_ephe.py   # one-time fetch of .se1 files (network only at setup)
│   └── build_gazetteer.py # regenerate data/gazetteer/cities.csv from GeoNames
├── tests/
│   └── reference_charts/  # known-correct test fixtures
├── data/
│   ├── ephe/              # downloaded ephemeris files (gitignored, run download_ephe.py)
│   └── gazetteer/         # committed GeoNames-derived cities.csv + attribution README
├── LICENSE                # AGPL-3.0-or-later
└── README.md
```

## 8. Open Decisions Before Build

1. **Swiss Ephemeris (AGPL, more precise/wider range) vs. Skyfield+JPL DE421 (permissive license, narrower range).** *Resolved:* Swiss Ephemeris (pyswisseph) with the AGPL path; `.se1` files fetched at setup rather than redistributed. *(Open:* whether to offer a later Skyfield backend for permissive-license deployments.)
2. **House system default** — whole-sign is standard for Vedic, and is confirmed as v1's default (see §5.7 conventions; Placidus still used internally for Shadbala's Dig Bana).
3. **Eclipse handling (proposed then accepted):** dedicated `get_eclipses` tool rather than folding into `get_current_transits`; lunar type via umbral magnitude (`lun_eclipse_how`), never the pyswisseph lunar return flag.

## 9. Roadmap

- **v1 (this spec):** pure computation, ships as a usable MCP server on its own.
- **v2:** community-reviewed interpretive rules corpus (gochara, common yogas, dasha-lord significations) as a separate, clearly-sourced YAML dataset — additive, doesn't change v1's contract.
- **v3+:** possible additional systems (Jaimini, KP) as opt-in modules once core is stable.
