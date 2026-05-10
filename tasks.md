# Tasks

## Legend

| Prefix | Meaning |
|--------|---------|
| `[FR]` | Functional Requirement — user-facing feature or behavior |
| `[NFR]` | Non-Functional Requirement — quality, performance, maintainability |
| `[B]` | Bug — incorrect behavior |
| `[D]` | Documentation — docs, specs, agent files |
| `[T]` | Test — test coverage |
| `[C]` | Chore — tooling, config, CI |

Status: `⏳` pending, `🔄` in progress, `✅` done, `❌` cancelled

---

## Phase 1: Foundation (COMPLETE)

| Status | ID | Type | Description |
|--------|----|------|-------------|
| ✅ | 1.1 | FR | CLI: list-symbols, list-files, download, verify commands |
| ✅ | 1.2 | FR | aria2 download integration with resumable downloads |
| ✅ | 1.3 | FR | SHA256 checksum verification |
| ✅ | 1.4 | FR | Symbol filtering (quote asset, contract type, exclude stables/leverage) |
| ✅ | 1.5 | NFR | Pre-commit hooks (ruff, format, uv-lock, ty, trailing-whitespace, end-of-file, yaml) |
| ✅ | 1.6 | NFR | uv-native toolchain (no pip, uv pip, or global python3) |
| ✅ | 1.7 | D | AGENTS.md with all patterns, task graph, known issues |

## Phase 2: Exchange SDK Migration (COMPLETE)

| Status | ID | Type | Description |
|--------|----|------|-------------|
| ✅ | 2.1 | FR | Official Binance SDK integration (spot, um, cm) |
| ✅ | 2.2 | FR | ExchangeClient protocol with backward-compat aliases |
| ✅ | 2.3 | FR | REST: fetch_ohlcv, fetch_agg_trades, fetch_funding_rate |
| ✅ | 2.4 | FR | WS stream relay (async generator via asyncio.Queue) |
| ✅ | 2.5 | NFR | Optional CCXT integration for multi-exchange |

## Phase 3: Data Pipeline (COMPLETE)

| Status | ID | Type | Description |
|--------|----|------|-------------|
| ✅ | 3.1 | FR | Bronze→Silver transform via Polars (klines, aggTrades, trades, fundingRate) |
| ✅ | 3.2 | FR | DuckLake v1.0 native table ingestion with partitioning |
| ✅ | 3.3 | FR | Zero-copy DuckDB INSERT (all type casting in Polars) |
| ✅ | 3.4 | FR | Microsecond timestamp normalization (archive ms + μs → μs) |
| ✅ | 3.5 | FR | Monthly archive support for fundingRate |
| ✅ | 3.6 | FR | Dead letter queue for failed sink records |
| ✅ | 3.7 | NFR | concurrency guard for DuckDB writes |

## Phase 4: Gap Fill & Health (COMPLETE)

| Status | ID | Type | Description |
|--------|----|------|-------------|
| ✅ | 4.1 | FR | Gap detection from archive filenames |
| ✅ | 4.2 | FR | REST API backfill with CSV + checksum output |
| ✅ | 4.3 | FR | Lineage tracking for fill events |
| ✅ | 4.4 | FR | DuckLake anomaly detection (null prices, duplicates, outliers) |
| ✅ | 4.5 | FR | Per-rtype health filtering (aggTrades + trades share table) |
| ✅ | 4.6 | NFR | Per-symbol error isolation (Prefect raise_on_failure=False) |

## Phase 5: Prefect Orchestration (COMPLETE)

| Status | ID | Type | Description |
|--------|----|------|-------------|
| ✅ | 5.1 | FR | historical_pipeline (metadata→download→verify→fill→sink→health) |
| ✅ | 5.2 | FR | bulk_backfill with auto-discovery |
| ✅ | 5.3 | FR | Cron deployments via prefect.serve() |
| ✅ | 5.4 | NFR | Configurable ThreadPoolTaskRunner via PREFECT_MAX_WORKERS |
| ✅ | 5.5 | NFR | pydantic-settings with .env support |
| ✅ | 5.6 | D | Task dependency graph documented in AGENTS.md |

## Phase 6: Test Infrastructure (COMPLETE)

| Status | ID | Type | Description |
|--------|----|------|-------------|
| ✅ | 6.1 | T | 31 tests for health_check + sink modules |
| ✅ | 6.2 | T | SampleArchive generator for offline testing |
| ✅ | 6.3 | T | Real Binance archive fixtures (6 zips + checksums + manifest) |
| ✅ | 6.4 | T | Parametrized trade type fixtures (spot/um/cm) |
| ✅ | 6.5 | T | Pre-commit hooks (ruff, format, ty, trailing-whitespace, end-of-file) |

---

## Pending Items (FR over NFR)

### FR-1: CLI reference docs missing 4 commands
- **Type**: D
- **Status**: ✅ Done
- **Files**: `docs/reference/cli/README.md`
- **Fix**: Added gap-fill, health, sink, refresh-metadata to app structure tree and reference table

### FR-2: docs/requirements.md Phase 5 OKX/Bybit aspirational
- **Type**: D
- **Status**: ✅ Done
- **Files**: `docs/requirements.md`
- **Fix**: Changed to ❌ with note "not implemented"

### FR-3: docs/requirements.md Phase 2 `--source` flag stale
- **Type**: D
- **Status**: ✅ Done
- **Files**: `docs/requirements.md` line 697
- **Fix**: Changed to ❌ with explanation

### FR-4: docs/data-sources.md WS stream commands referenced
- **Type**: D
- **Status**: ✅ Done
- **Files**: `docs/data-sources.md`
- **Fix**: Replaced with "Phase 8 — planned, not implemented"

### FR-5: Iceberg catalog aspirational content in silver-layer-spec.md
- **Type**: D
- **Status**: ✅ Done
- **Files**: `docs/silver-layer-spec.md`, `docs/requirements.md`
- **Fix**: Moved to `docs/proposals/iceberg.md`, replaced with brief note

---

### NFR-1: ts_event/ts_recv/ingested_at type docs wrong (ms → μs)
- **Type**: D
- **Status**: ✅ Done
- **Files**: `AGENTS.md`, `docs/silver-layer-spec.md`, `docs/data-sources.md`
- **Fix**: s/INT64 ms/INT64 μs/g across all three files. Added missing `exchange` column to AGENTS.md schema table

### NFR-2: sink.py `_scan_bronze_files` ignores lookback_days
- **Type**: NFR
- **Files**: `src/binance_datatool/workflow/sink.py` line 172
- **Issue**: Scans all files regardless of date window
- **Fix**: Add optional lookback_days parameter

### NFR-3: sink.py split transform() and load()
- **Type**: NFR
- **Files**: `src/binance_datatool/workflow/sink.py` lines 485-575
- **Issue**: `transform()` conflates transform + DuckDB write
- **Fix**: Split into `transform()` returning DataFrame and `load()` doing DuckDB write

### NFR-4: health_check.py optimize outlier query
- **Type**: NFR
- **Files**: `src/binance_datatool/workflow/health_check.py` line 333
- **Issue**: Window function STDDEV scans entire partition per row
- **Fix**: Use scalar subqueries for AVG/STDDEV

### NFR-5: catalog.py `ingest_dataframe` silent exception swallow
- **Type**: NFR
- **Files**: `src/binance_datatool/workflow/catalog.py` lines 295-296
- **Issue**: `except Exception: logger.warning` swallows all errors
- **Fix**: Re-raise after logging

### NFR-6: catalog.py missing dedup on INSERT
- **Type**: NFR
- **Files**: `src/binance_datatool/workflow/catalog.py` line 293
- **Issue**: `INSERT INTO` is plain append — pipeline re-run creates duplicates
- **Fix**: Add `DELETE FROM {table} WHERE symbol=? AND ts_date IN (...)` before INSERT

### NFR-7: prefect_flows.py health_flow re-attaches DuckLake per symbol
- **Type**: NFR
- **Files**: `src/binance_datatool/workflow/prefect_flows.py` lines 498-500
- **Issue**: New DuckDB connection + attach per symbol in loop
- **Fix**: Pass connection from caller

### NFR-8: test_sink.py only tests `_parse_symbol_from_path`
- **Type**: T
- **Files**: `tests/test_sink.py`
- **Issue**: Core sink transform + load completely untested
- **Fix**: Add tests for `_bronze_kline_to_silver`, `_read_zip_csv`, `_add_silver_metadata`, `ingest_dataframe`

### NFR-9: `tests/unit/`, `tests/integration/`, `tests/fixture_metrics/`, `tests/streaming_lakehouse/` orphaned
- **Type**: C
- **Files**: Empty test directories
- **Issue**: Dead directories with only `__pycache__/` — no test source files
- **Fix**: Remove empty dirs or populate with actual tests

### NFR-10: `test_adapter_binance.py` duplicates `FakeArchiveClient`
- **Type**: T
- **Files**: `tests/test_adapter_binance.py:12`, `tests/conftest.py:21`
- **Issue**: `FakeBinanceArchiveClient` is nearly identical to `FakeArchiveClient`
- **Fix**: Consolidate into conftest.py or `tests/fakes.py`
