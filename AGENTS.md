# LibreJyotish — agent instructions

## Python environment (user preference)
Always work in the conda env for Python tasks. If missing, recreate it:
`conda env create -f environment.yml`
Run all Python/pytest commands via: `conda run -n librejyotish python ...`
Never use system pip/python directly; never use uv venvs here.
(CI uses pip on a clean runner instead — local stays conda, CI uses pip.)

## Project
Deterministic Vedic astrology MCP server.

Layer 1 only: every number is computed here (Swiss Ephemeris, sidereal
zodiac, Lahiri ayanamsha by default, whole-sign houses). The calling LLM
does synthesis and interpretation only — never attach favorable/unfavorable
judgments, remedies, or predictions to a response. Raw results, no verdicts.

Every tool response must include an explicit `conventions_used` block.
Every tool is stateless (JSON in, structured dict out) and reports errors
as `{"error": {"type", "message"}}`. Keep responses bounded so a model
can't blow up its own context (default shallow levels, date-windowed deep
queries, clamped with a warning when unfiltered).

## Locked canon decisions (do not re-litigate without user approval)
- Whole-sign houses from Lagna; Lahiri ayanamsha and apparent positions by default.
- Parashara single house lords (Mars rules Scorpio, Saturn rules Aquarius) —
  the Jaimini stronger-lord (Ketu/Rahu) evaluation is a documented lineage
  variant and is NOT applied.
- Saturn periods are natal-Moon-relative only (Sade Sati 12th/1st/2nd, Dhaiya
  4th/8th). Lagna-relative readings and the 10th-from-Moon Kantaka are out
  of scope.
- Ephemeris coverage is 1800–2399 (bundled `.se1` files); outside that range
  raise `EphemerisRangeError`, never silently degrade to Moshier theory.

## Adding a tool (all steps, every time)
New canon math first: research the classical rule, its lineage variants and
exceptions before coding; record the chosen convention in `conventions_used`;
cross-check against the `jhora` oracle where one exists.
Then, in order:
1. Pure computation in a new `librejyotish/core/<name>.py` (no I/O, no MCP).
2. Thin `@server.tool()` wrapper in `librejyotish/server.py` with strict
   ISO-8601 input parsing via the shared `_common_inputs` helpers.
3. Register in `_BATCHABLE` and the `batch` docstring list.
4. Unit tests under `tests/` (hand-verified pins + invariant sweeps, never
   oracle output copied blindly) plus a `scripts/crosscheck_*.py` oracle
   script for rule math (dev-only: `jhora` must never be imported from
   production paths).
5. README tools-table row, smoke coverage in `tests/test_smoke.py`, and the
   registry set in `tests/test_reference_charts.py`.

## LLM-facing response shape
The consumer is a model, not a human — shape responses so the most likely
misreading is impossible:
- Result-first field order: the answer (`pada_sign`, `pada_house_from_lagna`)
  before the derivation (`house`, `lord`, `count`, `raw_sign`).
- Placement vs source must be unmistakable: `house` is the SOURCE a factor
  derives from, never its location. Say so in the tool description.
- Static definitional labels (`signifies`) on domain terms (padas, karakas,
  vargas) — same status as varga significations, not interpretation.
- No duplicated arrays that restate per-entry fields.

## Server framework notes
- `mcp>=2.0.0` uses the new `MCPServer` API (`from mcp.server.mcpserver import MCPServer`,
  `@server.tool()` decorator, `server.run("stdio")`). There is NO
  `mcp.server.fastmcp.FastMCP` in 2.x.
- Dev-only oracle PyJHora lives in the env; never import it from librejyotish.core/ or librejyotish.server (production package paths). It may only be used in the dev-only oracle scripts under scripts/.

## Releases and working-tree discipline
- Version lives in 5 places: `pyproject.toml`, `librejyotish/__init__.py`,
  the `server.py` fallback, the README `--version` line, `tests/test_smoke.py`.
- Releases ship ONLY via `v*` tags (`git tag vX.Y.Z && git push origin vX.Y.Z`);
  the tag must equal the package version (the workflow enforces this).
  Never publish to PyPI by hand — trusted publishing handles auth, no tokens.
- CI (`ci.yml`) runs pytest on every push/PR; `master` merges must be green.
- Never commit, push, tag, or publish without the user's explicit approval
  in the current session.
