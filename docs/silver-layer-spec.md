# Silver Layer: Normalized Data Schemas

## Overview

The **Silver layer** is the transform/normalization stage of the medallion architecture.
It converts raw archive data (Bronze) into clean, queryable, standardized schemas suitable
for analytics, gap detection, health checks, and downstream ML pipelines.

## Design Principles

- **Normalized across trade types**: Spot, UM, CM share a unified schema per data type
- **Normalized across sources**: Archive ZIP, API-filled, and WS-filled data use the same schema
- **Industry-standard field names**: Follows Databento DBN (`ts_event`, `price`, `size`),
  tardis.dev (timestamp-based), and Binance archive naming conventions
- **Self-describing**: Metadata columns (`source`, `trade_type`, `data_type`, `symbol`,
  `interval`, `ingested_at`) make each row fully contextual without external catalog lookups
- **Type-safe**: All numeric fields are numeric (Float64), timestamps are Int64 epoch ms

## Iceberg Catalog Table Naming

```
{catalog}/{trade_type}/{data_type}/date={YYYY-MM-DD}/{file}.parquet
```

| Catalog Path | Description | Partitioning |
|---|---|---|
| `{catalog}/spot/klines/date=N/spot_klines.parquet` | Spot klines | `date` |
| `{catalog}/um/klines/date=N/um_klines.parquet` | UM klines | `date` |
| `{catalog}/cm/klines/date=N/cm_klines.parquet` | CM klines | `date` |
| `{catalog}/spot/aggTrades/date=N/spot_aggTrades.parquet` | Spot aggregated trades | `date` |
| `{catalog}/um/fundingRate/date=N/um_fundingRate.parquet` | UM funding rate | `date` |
| `{catalog}/venues.parquet` | Venue metadata | None |
| `{catalog}/symbols.parquet` | Symbol metadata | None |

## Metadata Tables

### venues (catalog-level)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `venue` | UTF8 | Auto | `"binance_spot"`, `"binance_um"`, `"binance_cm"` |
| `trade_type` | UTF8 | Auto | `"spot"`, `"um"`, `"cm"` |
| `exchange` | UTF8 | Auto | `"binance"` |
| `source` | UTF8 | Auto | `"archive"` or `"api"` |
| `symbol_count` | INT64 | Derived | Number of symbols (populated after refresh) |
| `data_types` | UTF8 | Auto | Comma-separated available data types |
| `fetched_at` | INT64 (ms) | Auto | When metadata was fetched |

### symbols (catalog-level)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `symbol` | UTF8 | Archive/API | Trading pair (e.g. `"BTCUSDT"`) |
| `trade_type` | UTF8 | Auto | `"spot"`, `"um"`, `"cm"` |
| `exchange` | UTF8 | Auto | `"binance"` |
| `base_asset` | UTF8 | Archive/API | Base asset (e.g. `"BTC"`) |
| `quote_asset` | UTF8 | Archive/API | Quote asset (e.g. `"USDT"`) |
| `contract_type` | UTF8 | API | `"perpetual"`, `"delivery"`, or empty |
| `is_leverage` | BOOL | Archive | Leveraged token flag |
| `is_stable_pair` | BOOL | Archive | Stablecoin pair flag |
| `source` | UTF8 | Auto | `"archive"` or `"api"` |
| `status` | UTF8 | API | `"trading"`, `"break"`, etc. |
| `fetched_at` | INT64 (ms) | Auto | When metadata was fetched |

## Silver Layer Schemas

### silver_klines (unified OHLCV)

Unifies spot/um/cm klines from all sources (archive, API, WS).

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `ts_event` | INT64 (ms) | DBN | Event timestamp, epoch ms (aligned to interval start) |
| `open` | FLOAT64 | tardis.dev | Open price |
| `high` | FLOAT64 | tardis.dev | High price |
| `low` | FLOAT64 | tardis.dev | Low price |
| `close` | FLOAT64 | tardis.dev | Close price |
| `volume` | FLOAT64 | tardis.dev | Volume (base asset) |
| `quote_volume` | FLOAT64 | Binance | Quote asset volume |
| `trade_count` | INT64 | Binance | Number of trades |
| `taker_buy_volume` | FLOAT64 | Binance | Taker buy base volume |
| `taker_buy_quote_volume` | FLOAT64 | Binance | Taker buy quote volume |
| `source` | UTF8 | Metadata | `"archive"`, `"api_filled"`, or `"ws_stream"` |
| `trade_type` | UTF8 | Metadata | `"spot"`, `"um"`, `"cm"` |
| `symbol` | UTF8 | Metadata | Trading pair (e.g. `"BTCUSDT"`) |
| `interval` | UTF8 | Metadata | Kline interval (e.g. `"1h"`, `"1m"`) |
| `data_type` | UTF8 | Metadata | Always `"klines"` |
| `ingested_at` | INT64 (ms) | Metadata | When this record was ingested |

### silver_trades (unified raw/aggregated trades)

Unifies trades, aggTrades from all trade types.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `ts_event` | INT64 (ms) | DBN | Trade timestamp, epoch ms |
| `price` | FLOAT64 | tardis.dev | Trade price |
| `size` | FLOAT64 | tardis.dev | Trade size (base asset) |
| `side` | UTF8 | tardis.dev | `"buy"`, `"sell"`, or `null` (aggTrades use is_buyer_maker) |
| `trade_id` | INT64 | Binance | Unique trade ID |
| `agg_trade_id` | INT64 | Binance | Aggregated trade ID (aggTrades only) |
| `is_buyer_maker` | INT8 | Binance | 1 if buyer is maker, 0 otherwise |
| `source` | UTF8 | Metadata | Data source classification |
| `trade_type` | UTF8 | Metadata | `"spot"`, `"um"`, `"cm"` |
| `symbol` | UTF8 | Metadata | Trading pair |
| `data_type` | UTF8 | Metadata | `"trades"` or `"aggTrades"` |
| `ingested_at` | INT64 (ms) | Metadata | Ingestion timestamp |

### silver_funding_rate

Perpetual futures funding rates (um/cm only).

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `ts_event` | INT64 (ms) | DBN | Funding time, epoch ms |
| `funding_rate` | FLOAT64 | tardis.dev | Funding rate (e.g. 0.0001 = 0.01%) |
| `mark_price` | FLOAT64 | Binance | Mark price at funding time |
| `source` | UTF8 | Metadata | Data source |
| `trade_type` | UTF8 | Metadata | `"um"`, `"cm"` |
| `symbol` | UTF8 | Metadata | Trading pair |
| `data_type` | UTF8 | Metadata | Always `"fundingRate"` |
| `ingested_at` | INT64 (ms) | Metadata | Ingestion timestamp |

## Bronze → Silver Mapping

```
Bronze Klines (Binance archive CSV)          Silver Klines
─────────────────────────────                 ─────────────
open_time                → ts_event
open (str → float)       → open
high (str → float)       → high
low (str → float)        → low
close (str → float)      → close
volume (str → float)     → volume
quote_volume (str → float) → quote_volume
count                    → trade_count
taker_buy_volume         → taker_buy_volume
taker_buy_quote_volume   → taker_buy_quote_volume
(literal "0")            → ignore (dropped)
-                        → source = "archive"
-                        → trade_type (from directory path)
-                        → symbol (from directory path)
-                        → interval (from directory path)
-                        → data_type = "klines"
-                        → ingested_at = now()
```

## Data Flow: Archive → Silver Pipeline

```
Archive (local ZIPs + filled CSVs)
  │
  ├── ArchiveListSymbolsWorkflow (list-symbols)
  │     → symbols metadata (symbols.parquet)
  │
  ├── SinkWorkflow (sink)
  │     → read ZIP CSVs + filled CSVs
  │     → Bronze → Silver transform (normalize, cast, add metadata)
  │     → write partitioned Parquet: {catalog}/{type}/{data_type}/date=N/*.parquet
  │     → DuckDB: CREATE OR REPLACE TABLE {type}_{data_type}
  │
  └── MetadataWorkflow (refresh-metadata)
        → venues.parquet (3 venues: spot, um, cm)
        → symbols.parquet (all symbols per trade type)
        → Optionally from REST API: richer metadata (status, contract type)
```

## Commands

```bash
# Transform Bronz to Silver Parquet
binance-datatool sink spot --type klines --interval 1h --target parquet --catalog /path/to/lake BTCUSDT

# Load into DuckDB as well
binance-datatool sink spot --type klines --interval 1h --target all --duckdb /path/to/db.duckdb BTCUSDT

# Refresh metadata from archive
binance-datatool refresh-metadata spot --catalog /path/to/lake

# Refresh metadata from REST API (richer data)
binance-datatool refresh-metadata um --from-api --catalog /path/to/lake
```

## Catalog Directory Structure

```
{archive_home}/../lake/
├── venues.parquet           # Venue metadata (3 rows)
├── symbols.parquet          # Symbol metadata (all trade types)
├── spot/
│   └── klines/
│       └── date=2026-05-08/
│           └── spot_klines.parquet
├── um/
│   └── klines/
│       └── date=2026-05-08/
│           └── um_klines.parquet
└── cm/
    └── klines/
        └── date=2026-05-08/
            └── cm_klines.parquet
```

## Gap-Fill and Health Check on Silver

### Gap Detection (Silver-aware)
- Scan Silver layer for missing dates per `(trade_type, data_type, symbol, interval)`
- Query Parquet for date range coverage
- Fetch missing data from REST API → normalize → append to Silver

### Health Check (Silver-aware)
- **Completeness**: Silver has all expected dates?
- **Freshness**: Latest Silver record within max_stale window?
- **Integrity**: Silver schema conforms to contract? No null prices? Valid timestamps?
- **Consistency**: Cross-reference counts between Bronze and Silver?