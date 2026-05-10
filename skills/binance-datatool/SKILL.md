---
name: binance-datatool
description: |
  Manage and query Binance historical market data from data.binance.vision.
  List symbols, browse archive files, download klines/trades/funding rates with
  aria2, verify SHA256 checksums. Trigger Prefect data pipelines for automated
  backfilling and DuckDB ingestion. Use when the user mentions Binance historical
  data, klines, candlestick data, trade data, funding rates, data.binance.vision,
  or crypto data pipeline orchestration. Do not use for Binance REST API
  real-time data or WebSocket streaming.
---

# binance-datatool

CLI for Binance historical market data + Prefect pipeline orchestration.

## Quick Start

```bash
# List USDT symbols, download 3 days of 1h klines, verify
binance-datatool -v list-symbols spot --quote USDT --exclude-stables > syms.txt
binance-datatool -v download spot --type klines --interval 1h < syms.txt
binance-datatool -v verify spot --type klines --interval 1h < syms.txt

# Or run the full Prefect pipeline (same thing, automated)
uv run python3 -c "
from binance_datatool.workflow.prefect_flows import historical_pipeline
r = historical_pipeline(trade_type='spot', symbols=['BTCUSDT'],
                        data_type='klines', interval='1h', lookback_days=3)
print(r)
"
```

## CLI Commands

All commands accept `-v` (INFO-level stderr) and `--archive-home PATH`.

### list-symbols
`binance-datatool -v list-symbols (spot|um|cm) [--quote USDT] [--exclude-stables]`

`binance-datatool -v list-files (spot|um|cm) [SYMBOLS...] [--type klines] [--interval 1h]`

`binance-datatool -v download (spot|um|cm) [SYMBOLS...] [--type klines] [--interval 1h] [--dry-run]`

`binance-datatool -v verify (spot|um|cm) [SYMBOLS...] [--type klines] [--interval 1h]`

Verifies SHA256 checksums. Exit 0 = all pass, 2 = partial failure.

## Prefect Workflows

Full pipeline orchestration at `src/binance_datatool/workflow/prefect_flows.py`.

**Available flows:**

| Flow | Purpose | Parallelism |
|------|---------|-------------|
| `historical_pipeline` | Full ETL: metadata→download→verify→fill→sink→health | `prepare_symbol.map()` via `PREFECT_MAX_WORKERS` |
| `bulk_backfill` | Auto-discover + historical_pipeline | Delegates to historical_pipeline |
| `download_flow` | Multi-symbol archive download | `download_archive.map()` |
| `verify_flow` | Multi-symbol checksum verification | `verify_archive.map()` |
| `sink_flow` | Bronze→Silver→DuckDB ingestion | Sequential (DuckDB constraint) |
| `health_flow` | DuckLake anomaly detection | Sequential |
| `refresh_metadata_flow` | Venue/symbol metadata refresh | Sequential |

**Task graph:**
```
historical_pipeline
  ├── refresh_metadata_flow        (subflow, sequential)
  ├── prepare_symbol.map()         (parallel fan-out per symbol)
  │     └── download → verify → fill_gaps
  ├── sink_silver()                (sequential, ducklake-writer guard)
  └── health_flow()                (sequential, per-symbol)
```

**Run via Python API:**
```python
from binance_datatool.workflow.prefect_flows import historical_pipeline, bulk_backfill

# Single symbol
result = historical_pipeline(trade_type='spot', symbols=['BTCUSDT'],
                             data_type='klines', interval='1h', lookback_days=3)

# Multi-symbol batch
result = bulk_backfill(trade_type='spot', symbols=['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
                       data_type='klines', interval='1h', lookback_days=3)
```

## Data Types

| Type | Archive | REST API | Table | Needs interval |
|------|---------|----------|-------|----------------|
| klines | daily zips | ✓ | `klines` | Yes (1m/1h/1d) |
| aggTrades | daily zips | ✓ | `aggTrades` | No |
| trades | daily zips | ✓ | `aggTrades` (shared) | No |
| fundingRate | monthly zips | ✓ | `fundingRate` | No |

Pipeline sink handlers exist for these 4 types. Types like `bookDepth`, `bookTicker`,
`indexPriceKlines`, `markPriceKlines`, `premiumIndexKlines`, `metrics`, `liquidationSnapshot`
exist in the archive but have no Silver transform yet.

## Archive Structure (data.binance.vision)

```
data/
├── spot/daily/     klines(13 intv)  aggTrades(6376f)  trades(6376f)
├── spot/monthly/   klines(16 intv)  aggTrades(210f)   trades(210f)
├── futures/um/daily/  9 data types,  833 symbols, 6376 files/sym
├── futures/um/monthly/ 8 data types, 833 symbols
├── futures/cm/daily/  10 data types, 267 symbols (USD_PERP naming)
├── futures/cm/monthly/ 8 data types, 267 symbols
└── option/daily/  BVOLIndex(2 syms)  EOHSummary(5 syms)
```

File naming: `{symbol}-{dataType}-{date}.zip` + `.CHECKSUM` companion.
Klines add interval subdirectory: `{symbol}/{interval}/{symbol}-{interval}-{date}.zip`.

## Configuration

Settings via environment variables or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PREFECT_MAX_WORKERS` | 8 | Thread pool workers |
| `ARCHIVE_HOME` | `~/.binance-datatool/archive` | Local archive root |
| `CATALOG_PATH` | `ARCHIVE_HOME/../lake` | DuckLake catalog root |
| `DEFAULT_LOOKBACK_DAYS` | 30 | Pipeline lookback window |

## Best Practices

- **Always pass `-v`** — output is nearly silent at default WARNING level.
- **Dry-run before download** — `download --dry-run` to preview.
- **Frequency matters** — fundingRate requires `--freq monthly`.
- **Type names are camelCase** — `fundingRate`, `aggTrades`, not `funding_rate`.
- **Exit code 2** means partial failure — check stderr for details.
- **Stdin composition** — `list-symbols | download` when no positional args given.
- **Workflows prefer Python API** — flows accept same params as CLI but add parallelism.
- **Serve deployments** — `uv run python -m binance_datatool.workflow.prefect_flows serve` for cron.
