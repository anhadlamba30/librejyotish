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
- **MCP framework:** official `mcp` Python SDK
- **Astronomical core:** `pyswisseph` (Swiss Ephemeris bindings) — industry standard precision
  - *Licensing note:* Swiss Ephemeris is AGPL/commercial dual-licensed. Since this project is fully open-source and free, AGPL is compatible — but it does mean the repo must carry AGPL forward. Alternative: use a Skyfield + JPL DE421-based approach (as `jyotishganit` does) to allow a more permissive license, at the cost of some historical/far-future date range coverage. **Decision needed before v1 lock — flagging for your input.**
- **Higher-level chart/dasha logic:** build directly on `pyswisseph`, or fork/wrap an existing permissively-licensed library (`jyotishganit`, `dashaflow`, `PyJHora`) rather than reimplementing dasha/varga math from scratch. Recommendation: start by wrapping one of these, benchmark against known reference charts, replace pieces only if discrepancies found.
- **Packaging:** pip-installable, ephemeris data bundled or auto-downloaded once on first run (cached locally after).

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
│   ├── ephemeris.py        # swisseph wrapper, ayanamsha handling
│   ├── charts.py            # natal + divisional chart logic
│   ├── dasha.py              # vimshottari dasha tree
│   ├── panchang.py
│   ├── ashtakavarga.py
│   └── shadbala.py
├── tests/
│   └── reference_charts/    # known-correct test fixtures
├── data/
│   └── ephe/                 # bundled or downloaded ephemeris files
├── LICENSE                    # AGPL (pending stack decision, see §4)
└── README.md
```

## 8. Open Decisions Before Build

1. **Swiss Ephemeris (AGPL, more precise/wider range) vs. Skyfield+JPL DE421 (permissive license, narrower range).**
2. **Library to wrap first** — `jyotishganit`, `dashaflow`, or `PyJHora` — for fastest path to a working v1.
3. **House system default** — whole-sign is standard for Vedic, but confirm before locking as the unannounced default.

## 9. Roadmap

- **v1 (this spec):** pure computation, ships as a usable MCP server on its own.
- **v2:** community-reviewed interpretive rules corpus (gochara, common yogas, dasha-lord significations) as a separate, clearly-sourced YAML dataset — additive, doesn't change v1's contract.
- **v3+:** possible additional systems (Jaimini, KP) as opt-in modules once core is stable.
