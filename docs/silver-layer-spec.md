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
binance.{layer}_{data_type}_{interval_suffix}
```

| Catalog Path | Description | Partitioning |
|---|---|---|
| `binance.silver_klines_1m` | 1-minute klines | `(trade_type, date)` |
| `binance.silver_klines_1h` | 1-hour klines | `(trade_type, date)` |
| `binance.silver_klines_1d` | 1-day klines | `(trade_type, date)` |
| `binance.silver_trades` | Raw trades + aggTrades | `(trade_type, date)` |
| `binance.silver_funding_rate` | Perpetual funding rates | `(trade_type, date)` |
| `binance.gold_daily_ohlcv` | Daily aggregated OHLCV | `(trade_type)` |
| `binance.gold_funding_summary` | Funding rate summaries | `(trade_type)` |

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

## Gap-Fill and Health Check on Silver

### Gap Detection (Silver-aware)
- Scan Silver layer for missing dates per `(trade_type, data_type, symbol, interval)`
- Query Parquet/Iceberg for date range coverage
- Fetch missing data from REST API → normalize → append to Silver

### Health Check (Silver-aware)
- **Completeness**: Silver has all expected dates?
- **Freshness**: Latest Silver record within max_stale window?
- **Integrity**: Silver schema conforms to contract? No null prices? Valid timestamps?
- **Consistency**: Cross-reference counts between Bronze and Silver?
