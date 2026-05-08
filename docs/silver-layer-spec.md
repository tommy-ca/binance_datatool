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

### Klines (unified OHLCV)

Unifies spot/um/cm klines from all sources (archive, API, WS).
Follows DBN (`ts_event`, `ts_recv`) and tardis.dev (price/size volume) conventions.

| Silver Column | Bronze Source | Type | Description |
|--------------|---------------|------|-------------|
| `ts_event` | `open_time` | INT64 ms | Event timestamp (DBN) |
| `ts_recv` | Auto | INT64 ms | Receive timestamp (DBN) |
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

### Trades (unified raw/aggregated)

Unifies trades, aggTrades from all trade types.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `ts_event` | INT64 ms | DBN | Trade timestamp |
| `ts_recv` | INT64 ms | DBN | Receive timestamp |
| `price` | FLOAT64 | tardis.dev | Trade price |
| `size` | FLOAT64 | tardis.dev | Trade size |
| `side` | UTF8 | tardis.dev | `"buy"`, `"sell"`, or null |
| `trade_id` | INT64 | Binance | Unique trade ID |
| `rtype` | UTF8 | Auto | Record type: `"trade"` or `"agg"` |
| `agg_trade_id` | INT64 | Binance | Aggregated trade ID |
| `is_buyer_maker` | INT8 | Binance | 1 if buyer is maker |
| `source` | UTF8 | Meta | Data source |
| `trade_type` | UTF8 | Meta | `"spot"`, `"um"`, `"cm"` |
| `symbol` | UTF8 | Meta | Trading pair |
| `data_type` | UTF8 | Meta | `"trades"` or `"aggTrades"` |
| `ingested_at` | INT64 ms | Meta | Ingestion timestamp |

### Funding Rate

Perpetual futures funding rates (um/cm only).

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| `ts_event` | INT64 ms | DBN | Funding time |
| `ts_recv` | INT64 ms | DBN | Receive timestamp |
| `funding_rate` | FLOAT64 | tardis.dev | Rate (0.0001 = 0.01%) |
| `mark_price` | FLOAT64 | Binance | Mark price |
| `source` | UTF8 | Meta | Data source |
| `trade_type` | UTF8 | Meta | `"um"`, `"cm"` |
| `symbol` | UTF8 | Meta | Trading pair |
| `data_type` | UTF8 | Meta | `"fundingRate"` |
| `ingested_at` | INT64 ms | Meta | Ingestion timestamp |

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

## Iceberg Catalog Design

### Namespace
- **Namespace**: `binance` (Hadoop catalog: `{warehouse}/iceberg/binance/`)

### Tables
| Table | Partition By | Sort Order | Compress |
|-------|-------------|------------|----------|
| `klines` | `days(ts_event)` | `symbol, ts_event` | zstd |
| `klines_1h` | `days(ts_event)` | `symbol, ts_event` | zstd |
| `klines_1d` | `months(ts_event)` | `symbol, ts_event` | zstd |
| `trades` | `days(ts_event)` | `symbol, ts_event` | zstd |
| `aggTrades` | `days(ts_event)` | `symbol, ts_event` | zstd |
| `fundingRate` | `days(ts_event)` | `symbol, ts_event` | zstd |
| `venues` | Unpartitioned | — | zstd |
| `symbols` | Unpartitioned | `trade_type, symbol` | zstd |

### Table Properties
```json
{
    "write.format.default": "parquet",
    "write.parquet.compression-codec": "zstd",
    "write.parquet.compression-level": "9",
    "commit.retry.num-retries": "3",
    "history.expire.max-snapshot-age-ms": "2592000000"
}
```

### Implementation
```python
from binance_datatool.workflow.catalog import IcebergCatalog

catalog = IcebergCatalog(warehouse_path)
catalog.create_namespace()  # Creates binance/iceberg/binance/
catalog.register_parquet(df, "klines", trade_type="spot")
# → iceberg/binance/klines/date=2026-05-08/klines_spot.parquet
```

## DuckLake Catalog Design

DuckLake uses DuckDB's lake extensions to query Parquet files in-place.
No data is copied into DuckDB — views scan the lake directly.

### Lake Views (zero-copy)
| View | Lake Source | Description |
|------|-------------|-------------|
| `spot_klines` | `lake/spot/klines/*/*.parquet` | Spot klines |
| `um_klines` | `lake/um/klines/*/*.parquet` | UM klines |
| `cm_klines` | `lake/cm/klines/*/*.parquet` | CM klines |
| `um_fundingRate` | `lake/um/fundingRate/*/*.parquet` | UM funding rate |
| `cm_fundingRate` | `lake/cm/fundingRate/*/*.parquet` | CM funding rate |

Views use `read_parquet('.../*/*.parquet', union_by_name=true)` to scan
the entire lake directory. DuckDB's Parquet reader handles partition
pruning and projection pushdown automatically.

### Analytics Views
```sql
-- Daily OHLCV aggregation (queries lake in-place)
CREATE OR REPLACE VIEW daily_ohlcv AS
SELECT CAST(ts_event / 86400000 AS DATE) AS trade_date,
       symbol, trade_type,
       FIRST(open) AS open, MAX(high) AS high,
       MIN(low) AS low, LAST(close) AS close,
       SUM(volume) AS volume
FROM spot_klines WHERE interval = '1h'
GROUP BY trade_date, symbol, trade_type;

-- Latest data per symbol
CREATE OR REPLACE VIEW latest_klines AS
SELECT DISTINCT ON (symbol, trade_type, interval)
       symbol, trade_type, interval, ts_event, close, volume, ingested_at
FROM spot_klines
ORDER BY symbol, trade_type, interval, ts_event DESC;

-- Stale symbol detection
CREATE OR REPLACE VIEW stale_symbols AS
SELECT symbol, trade_type,
       MAX(ts_event) AS latest_ts,
       CAST(epoch_ms(MAX(ts_event)) AS DATE) AS latest_date,
       DATEDIFF('day', CAST(epoch_ms(MAX(ts_event)) AS DATE), CURRENT_DATE) AS days_stale
FROM spot_klines GROUP BY symbol, trade_type
HAVING days_stale > 3;
```

### Implementation
```python
from binance_datatool.workflow.catalog import DuckLakeCatalog

catalog = DuckLakeCatalog(lake_path=Path("/path/to/lake"), db_path="/path/to/db.duckdb")
con = catalog.connect()
catalog.register_lake_views(con)       # spot_klines = read_parquet('lake/spot/klines/...')
catalog.create_analytics_views(con)    # daily_ohlcv, latest_klines, stale_symbols
```

## Gap-Fill and Health Check on Silver

### Gap Detection (Silver-aware)
- Scan Silver layer for missing dates per `(trade_type, data_type, symbol, interval)`
- Query Iceberg/DuckDB catalog for date range coverage
- Fetch missing data from REST API → normalize → append to Silver

### Health Check (Silver-aware)
- **Completeness**: Silver has all expected dates?
- **Freshness**: Latest Silver record within max_stale window?
- **Integrity**: Silver schema conforms to contract? No null prices? Valid timestamps?
- **Consistency**: Cross-reference counts between Bronze and Silver?
