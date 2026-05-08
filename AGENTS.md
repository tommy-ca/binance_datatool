# AGENTS.md

## Purpose
- This repository hosts the `binance_datatool` Python package.
- Treat checked-in source code, tests, configuration, and public documentation as the source of
  truth for current behavior.
- Keep the repository easy for both human developers and AI agents to navigate.

## Local Instructions
- Before making changes, check whether `.AGENTS.local.md` exists at the repository root.
- If `.AGENTS.local.md` exists, read it and follow it as additional local guidance.
- Public instructions in this file apply to everyone; local instructions add developer-specific context.

## Documentation Navigation
- Read `docs/architecture.md` before making structural or cross-layer changes.
- Read `docs/extending.md` before adding a new command, workflow, enum member, or sub-command group.
- Read `docs/reference/testing.md` before changing tests, fixtures, or test layout conventions.
- Use `docs/reference/README.md` as the entry point for module and CLI reference details.
- Treat checked-in code and tests as higher priority than documentation if they conflict.
- When a change alters behavior, public interfaces, or contributor workflows, update the relevant
  `docs/` promptly after the code change is committed.
- Unless explicitly requested otherwise, do not mix code changes and documentation updates in the
  same commit.
- **Documentation accuracy rule**: If docs describe features not implemented (e.g., Bronze layer, Migration, Skills), either implement them or move docs to `docs/proposals/`. Never maintain false documentation about what the tool can do.
- **Overspec prevention**: Original specs may have promised 34 Pydantic models, Bronze/Silver layers, 5 Skills, etc. The codebase uses `@dataclass` (29 total), not Pydantic. Keep docs aligned with reality (currently 98% accurate).

## Working Model
- Build the project as a modern Python package named `binance_datatool`.
- Use the intended package layout: shared code under `binance_datatool.common`, archive access
  under `binance_datatool.archive`, CLI entrypoints under `binance_datatool.cli`, and business
  workflows under `binance_datatool.workflow.archive`.
- Prefer clear, composable workflows and thin CLI entrypoints.
- Keep the root package minimal. Export only version metadata from `binance_datatool.__init__`.

## Toolchain
- Package and dependency management: `uv`
- Build backend: `hatchling`
- Linting and formatting: `ruff`
- Testing: `pytest`
- Git hooks: `pre-commit`
- External downloader: `aria2`

## Expected Commands
- Environment setup: `uv sync`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Tests: `uv run pytest`
- Targeted tests: `uv run pytest tests/path_to_test.py`
- CLI entrypoint target: `uv run binance-datatool --help`

## Code Standards
- Use written English for code comments, docstrings, logs, CLI text, and developer-facing messages.
- Write clear comments only where they add real value; do not narrate obvious code.
- Use Google-style docstrings for public modules, classes, and functions.
- Use modern Python syntax compatible with Python 3.11, but **MUST NOT** use syntax introduced after 3.11
- Keep Python source line length at 100 characters or less. This limit does not apply to
  Markdown files under `docs/`, where long table rows and wide ASCII diagrams are allowed.
- Keep imports at module top level unless a local import is technically necessary.
- Prefer explicit types and clear names over implicit behavior.
- Prefer small, focused modules with straightforward responsibilities.
- Follow a let-it-crash mindset. Do not add casual fallback logic, silent recovery, or defensive
  branches unless there is a concrete and justified failure mode.
- Replace hand-rolled infrastructure with mature third-party libraries when the design already
  names a standard dependency.

## Architecture Expectations
- Keep CLI modules thin: parse arguments, construct workflows, and present output.
- Put business logic in importable workflow or domain modules, not inside CLI command functions.
- Prefer Polars LazyFrame-based data processing when working with tabular pipelines.
- Preserve a clear separation between shared utilities, archive access, parsing, completion,
  metadata tracking, and holographic kline generation.
- Design commands to be atomic and composable so an agent can inspect state and then choose the
  next step.

## Testing Expectations
- Add or update tests for every meaningful behavior change.
- Prefer the smallest test scope that proves the change.
- Use `pytest` as the test runner and keep tests readable enough for agent-assisted maintenance.
- When adding data-processing behavior, include representative fixtures or focused regression
  coverage.
- Focus tests on functional correctness and observable behavior, not on logging implementation
  details such as how loguru renders or routes messages to stderr.

## Exchange Client SDK Migration

The `exchange/` module uses **official Binance SDK packages** (not hand-rolled `aiohttp`):

| Package | Market | REST Method | WS Method |
|---------|--------|-------------|-----------|
| `binance-sdk-spot` | Spot | `rest_api.klines()` | `connection.kline(symbol, interval)` with `KlineIntervalEnum` |
| `binance-sdk-derivatives-trading-usds-futures` | UM | `rest_api.kline_candlestick_data()` | `connection.kline_candlestick_streams()` |
| `binance-sdk-derivatives-trading-coin-futures` | CM | `rest_api.kline_candlestick_data()` | `connection.kline_candlestick_streams()` |

### Key Design Decisions
- **Async generator interface preserved**: SDK callback-based WS streams are wrapped via `asyncio.Queue` bridge. `ExchangeClient.stream_ohlcv()` still returns `AsyncIterator[KlineData]`.
- **No auth**: `ConfigurationRestAPI(api_key="", api_secret="")` for public market data endpoints only.
- **Archive client intact**: `archive/` module still uses `aiohttp` for S3 access (`data.binance.vision`).
- **Backward compat**: `BinanceRestClient = BinanceSpotRestClient`, `BinanceWsClient = BinanceSpotWsClient`.
- **KlineData.from_binance_api()**: This classmethod on `common/types.py` maps the 12-element Binance kline array to our `KlineData` dataclass.
- **Required dependencies**: SDK packages are required (not optional). CCXT remains optional (`[exchange]` extra).

### SDK Response Format
- REST klines endpoint returns array of 12 elements (same across all market types):
  `[open_time, open, high, low, close, volume, close_time, quote_volume, num_trades, taker_buy_volume, taker_buy_quote_volume, ignore]`
- WS kline stream returns dict with structure `{"k": {"t": ..., "o": ..., ...}}`

## Repository Boundaries
- `temp/` is git-ignored and may contain temporary or non-public materials.
- Do not treat `temp/` as part of the public package surface or public project documentation.
- Keep checked-in guidance focused on the package and stable workflows, not on transient working files.
