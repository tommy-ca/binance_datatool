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

## Data Sources

The pipeline ingests from three source layers. See `docs/data-sources.md` for
the complete field-to-source mapping matrix.

| Layer | Source | Latency | CLI |
|-------|--------|---------|-----|
| **Archive** | data.binance.vision (S3) | ~1-2 days | `download`, `verify` |
| **REST API** | api.binance.com via SDK | real-time | `gap-fill`, `refresh-metadata` |
| **WS Stream** | stream.binance.com via SDK | real-time continuous | `stream` (Phase 8) |

## Data Pipeline Architecture

```
Archive (S3) → Download → Verify
                    ↓
GapFillWorkflow (--auto-detect)
  ├── detect_gaps() → parse dates from filenames
  └── run() → fetch via SDK REST → save as CSV + .CHECKSUM
                    ↓
LineageTracker.record(FILLED)
                    ↓
HealthCheckWorkflow
  ├── completeness (date coverage)
  ├── freshness (staleness check)
  └── integrity (SHA256 verification)
                    ↓
SinkWorkflow (binance-datatool sink)
  ├── Polars: read ZIP CSVs + filled CSVs
  ├── normalize to Silver schemas (ts_event, ts_recv)
  ├── write partitioned Parquet (self-describing paths)
  └── DuckLake v1.0 native tables (ACID, snapshots)
```

## CLI Commands Reference

### archive commands
```bash
binance-datatool list-symbols spot --freq daily --type klines --quote USDT
binance-datatool list-files --symbols BTCUSDT --trade-type spot --type klines --interval 1d
binance-datatool download --symbols BTCUSDT --trade-type spot --type klines --interval 1d --dry-run
binance-datatool verify --symbols BTCUSDT --trade-type spot --type klines --interval 1d
```

### gap-fill command (REST API backfill)
```bash
# Auto-detect gaps and fill (uses REST API via SDK)
binance-datatool gap-fill spot --auto-detect --symbol BTCUSDT --type klines --interval 1h --lookback 30
# Manual time range
binance-datatool gap-fill spot --symbol BTCUSDT --type klines --interval 1h --start-time 1700000000000 --end-time 1700088000000
```

### health command (data quality monitoring)
```bash
# Check completeness, freshness, integrity
binance-datatool health spot --type klines --interval 1h BTCUSDT --max-stale 3
```

### sink command (transform to Parquet/DuckDB)
```bash
# Transform archive data to partitioned Parquet
binance-datatool sink spot --type klines --interval 1h --target parquet --catalog /path/to/lake BTCUSDT
# Load into DuckDB as well
binance-datatool sink spot --type klines --interval 1h --target all --duckdb /path/to/db.duckdb BTCUSDT
```

### refresh-metadata (venue/symbol tables)
```bash
# From archive (symbols discovered via S3 listing)
binance-datatool refresh-metadata spot --catalog /path/to/lake
# From REST API (richer metadata: status, contract type)
binance-datatool refresh-metadata um --from-api --catalog /path/to/lake
# Register as DuckLake native tables:
binance-datatool refresh-metadata spot --catalog /path/to/lake --duckdb /path/to/db.duckdb
```

## Key Design Patterns

- **SinkWorkflow**: Polars-based transform + Parquet write + DuckDB load
- **GapFillWorkflow**: Auto-detect gaps via `_scan_existing_dates()` → `_fetch_data()` → `_save_filled()`
- **HealthCheckWorkflow**: Scans local archive for completeness (missing dates), freshness (staleness), integrity (checksums)
- **Lineage**: Every data operation records `LineageEvent` via `LineageTracker` (exportable to JSON)
- **DuckLake catalog**: Uses official DuckLake v1.0 format (`ATTACH 'ducklake:metadata.ducklake'`). Lake views scan Parquet in-place via `read_parquet()` — zero copy, no data duplication.

## Silver Layer (Transform/Normalize)

The Silver layer normalizes Bronze archive data into unified schemas following
Databento DBN and tardis.dev conventions.

### Silver Schema (klines)
| Silver Column | Bronze Source | Type | Description |
|--------------|---------------|------|-------------|
| `ts_event` | `open_time` | INT64 ms | Event timestamp (DBN convention) |
| `ts_recv` | Auto | INT64 ms | Receive timestamp (DBN convention) |
| `open` | CSV column | FLOAT64 | Open price |
| `high` | CSV column | FLOAT64 | High price |
| `low` | CSV column | FLOAT64 | Low price |
| `close` | CSV column | FLOAT64 | Close price |
| `volume` | CSV column | FLOAT64 | Base volume |
| `quote_volume` | CSV column | FLOAT64 | Quote volume |
| `trade_count` | `count` | INT64 | Number of trades |
| `taker_buy_volume` | CSV column | FLOAT64 | Maker buy volume |
| `taker_buy_quote_volume` | CSV column | FLOAT64 | Maker buy quote volume |
| `source` | Auto | UTF8 | `"archive"`, `"api_filled"`, `"ws_stream"` |
| `trade_type` | Auto | UTF8 | `"spot"`, `"um"`, `"cm"` |
| `symbol` | Auto | UTF8 | e.g. `"BTCUSDT"` |
| `interval` | Auto | UTF8 | e.g. `"1h"` |
| `data_type` | Auto | UTF8 | `"klines"` |
| `ingested_at` | Auto | INT64 ms | Ingestion timestamp |

### DuckLake Catalog Path (self-describing)
```
data/exchange=binance-spot/data-type=klines/symbol=BTCUSDT/interval=1h/date=2026-05-08/data.parquet
```

Partition levels (all Hive-style):
| Level | Example | Purpose |
|-------|---------|---------|
| `exchange` | `binance-spot`, `binance-perps-um`, `binance-perps-cm` | Venue + market type |
| `data-type` | `klines`, `aggTrades`, `fundingRate` | Dataset type |
| `symbol` | `BTCUSDT` | Trading pair |
| `interval` | `1h`, `1m` (klines only) | Bar size |
| `date` | `2026-05-08` | Temporal partition |

The file is always `data.parquet` — no redundancy with path components.

### Metadata Tables
```
{lake}/metadata/venues.parquet     — Venue metadata (3 venues)
{lake}/metadata/symbols.parquet    — Symbol metadata (all symbols per trade type)
```

### Silver Spec
See `docs/silver-layer-spec.md` for full schema definitions for klines, trades,
aggTrades, and funding rate across all trade types.

### Populate Metadata from Archive/API
```bash
# From archive (symbols discovered via S3 listing)
binance-datatool refresh-metadata spot --catalog /path/to/lake

# From REST API (richer metadata: status, contract type)
binance-datatool refresh-metadata um --from-api --catalog /path/to/lake
```

## Repository Boundaries
- `temp/` is git-ignored and may contain temporary or non-public materials.
- Do not treat `temp/` as part of the public package surface or public project documentation.
- Keep checked-in guidance focused on the package and stable workflows, not on transient working files.
