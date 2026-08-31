# OpenJyotish — agent instructions

## Python environment (user preference)
Always work in the conda env for Python tasks. If missing, recreate it:
`conda env create -f environment.yml`
Run all Python/pytest commands via: `conda run -n openjyotish python ...`
Never use system pip/python directly; never use uv venvs here.

## Project
Deterministic Vedic astrology MCP server.
Stack locked for v1: pyswisseph (Swiss Ephemeris, AGPL), logic built direct on it,
whole-sign houses, Lahiri ayanamsha default. Every tool response must include an
explicit `conventions_used` block.

## Server framework notes
- `mcp>=2.0.0` uses the new `MCPServer` API (`from mcp.server.mcpserver import MCPServer`,
  `@server.tool()` decorator, `server.run("stdio")`). There is NO
  `mcp.server.fastmcp.FastMCP` in 2.x.
- Dev-only oracle PyJHora lives in the env; never import it from openjyotish.core/ or openjyotish.server (production package paths). It may only be used in the dev-only oracle scripts under scripts/.
