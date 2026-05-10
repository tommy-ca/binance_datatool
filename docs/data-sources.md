# Data Sources & Pipeline Architecture

## Source Layers

The binance-datatool pipeline ingests from three data source layers, ordered by
completeness and latency:

| Layer | Source | Latency | Coverage | Access Method |
|-------|--------|---------|----------|---------------|
| **Layer 1: Archive** | `data.binance.vision` (S3) | ~1-2 days behind real-time | 2017+ historical, daily/monthly ZIPs | `archive/` module (`aiohttp` S3) |
| **Layer 2: REST API** | `api.binance.com` / `fapi` / `dapi` | Real-time (REST) | Current + recent history up to 1000 bars | `exchange/` module via official SDK |
| **Layer 3: WS Stream** | `stream.binance.com` / `fstream` / `dstream` | Real-time (continuous) | Live ticks since connection start | `exchange/` module via official SDK |

### Pipeline Flow

```
Layer 1: Archive ───────────────────────────────────────────────┐
  data.binance.vision (S3)                                       │
  │  download ZIP → extract CSV                                  │
  │  verify checksum                                              │
  └── Bronze (raw ZIPs + CSVs) ──────────────────────────────────┤
                                                                  │
Layer 2: REST API ───────────────────────────────────────────────┤
  api/binance.com                                                 │
  │  gap-fill: fetch missing date ranges                          │
  │  refresh-metadata: exchange_info, symbols                     │
  └── Bronze (filled CSVs) ──────────────────────────────────────┤
                                                                  │
Layer 3: WS Stream ──────────────────────────────────────────────┤
  stream.binance.com                                              │
  │  real-time: streaming funding rate, trades, klines            │
  │  captures fields not available in archive/REST                │
  └── StreamBuffer (in-memory, flushed periodically) ────────────┤
                                                                  │
                              Sink (Polars transform) ←──────────┤
                              │  read all Bronze sources           │
                              │  normalize to Silver schemas       │
                              │  add metadata (exchange, ts_recv)  │
                              │  INSERT INTO DuckLake native table │
                              ▼                                    │
                    DuckLake v1.0 (native tables, ACID,            │
                    partitioning, snapshots)                       │
                    DuckDB manages Parquet files internally        │
```

## Field-to-Source Matrix

### klines (19 columns)

| Silver Field | Archive | REST API | WS Stream | Notes |
|---|---|---|---|---|
| `ts_event` | ✅ `open_time` | ✅ `[0]` | ✅ `kline.t` | Primary from archive |
| `ts_recv` | — | — | ✅ | Set at ingest time |
| `open` | ✅ `open` | ✅ `[1]` | ✅ `kline.o` | |
| `high` | ✅ `high` | ✅ `[2]` | ✅ `kline.h` | |
| `low` | ✅ `low` | ✅ `[3]` | ✅ `kline.l` | |
| `close` | ✅ `close` | ✅ `[4]` | ✅ `kline.c` | |
| `volume` | ✅ `volume` | ✅ `[5]` | ✅ `kline.v` | |
| `quote_volume` | ✅ `quote_volume` | ✅ `[7]` | ✅ `kline.q` | |
| `trade_count` | ✅ `count` | ✅ `[8]` | ✅ `kline.n` | |
| `taker_buy_volume` | ✅ `taker_buy_volume` | ✅ `[9]` | ✅ `kline.V` | |
| `taker_buy_quote_volume` | ✅ `taker_buy_quote_volume` | ✅ `[10]` | ✅ `kline.Q` | |
| `source` | — | — | — | Set by pipeline: "archive"/"api_filled"/"ws_stream" |
| `exchange` | — | — | — | Derived from trade_type |
| `trade_type` | — | — | — | From directory path / client config |
| `symbol` | ✅ filename | ✅ param | ✅ `kline.s` | |
| `interval` | ✅ filename | ✅ param | ✅ `kline.i` | |
| `data_type` | — | — | — | Set by pipeline to "klines" |
| `ingested_at` | — | — | — | Set at ingest time |
| `ts_date` | — | — | — | Computed: `CAST(epoch_ms(ts_event) AS DATE)` |

### aggTrades / trades (16 columns)

| Silver Field | Archive | REST API | WS Stream |
|---|---|---|---|
| `ts_event` | ✅ `transact_time` | ✅ `T` | ✅ `trade.T` |
| `ts_recv` | — | — | — |
| `price` | ✅ `price` | ✅ `p` | ✅ `trade.p` |
| `size` | ✅ `quantity` | ✅ `q` | ✅ `trade.q` |
| `side` | — | ✅ `m` (is_buyer_maker) | — |
| `trade_id` | ✅ `agg_trade_id` | ✅ `a` (agg_trade_id) | ✅ `trade.t` |
| `is_buyer_maker` | ✅ (direct) | ✅ `m` | ✅ `trade.m` |
| `agg_trade_id` | ✅ `agg_trade_id` | ✅ `a` | — |
| `rtype` | — | — | — |
| `source` | — | — | — |
| `exchange` | — | — | — |
| `trade_type` | — | — | — |
| `symbol` | ✅ filename | ✅ param | ✅ `trade.s` |
| `data_type` | — | — | — |
| `ingested_at` | — | — | — |
| `ts_date` | — | — | — |

### fundingRate (12 columns, can expand to 16 with WS)

| Silver Field | Archive | REST API | WS Stream (mark_price_stream) |
|---|---|---|---|
| `ts_event` | ✅ `funding_time` | ✅ `fundingTime` | ✅ `markPrice.T` (event time) |
| `ts_recv` | — | — | — |
| `funding_rate` | ✅ | ✅ | ✅ `markPrice.r` |
| `mark_price` | ✅ | ✅ | ✅ `markPrice.p` (mark price) |
| `funding_timestamp` | ✅ (same as ts_event) | ✅ (same) | ✅ `markPrice.T` |
| `index_price` | ❌ | ❌ | ✅ `markPrice.i` |
| `predicted_funding_rate` | ❌ | ❌ | ✅ `markPrice.R` |
| `last_price` | ❌ | ❌ | ✅ `24hrTicker.c` (from ticker stream) |
| `open_interest` | ❌ | ❌ | ⏳ contract_info or ticker |
| `source` | — | — | — |
| `exchange` | — | — | — |
| `trade_type` | — | — | — |
| `symbol` | ✅ | ✅ | ✅ |
| `data_type` | — | — | — |
| `ingested_at` | — | — | — |
| `ts_date` | — | — | — |

## Source Coverage Summary

| Data Type | Archive Fields | REST Extras | WS Extras | Total Silver |
|---|---|---|---|---|
| `klines` | 10/10 OHLCV fields | — | — | 19 (with metadata) |
| `aggTrades` | 7/7 archive fields | — | — | 16 (with metadata) |
| `fundingRate` | 4/4 archive fields | — | **4 more** (index_price, predicted_funding_rate, last_price, open_interest) | 12 (+4 = 16 with WS) |

## CLI Commands by Source Layer

```bash
# Layer 1: Archive
binance-datatool download spot --type klines --interval 1h BTCUSDT
binance-datatool verify spot --type klines --interval 1h BTCUSDT

# Layer 2: REST API
binance-datatool gap-fill spot --auto-detect --symbol BTCUSDT --type klines --interval 1h
binance-datatool refresh-metadata spot --from-api --catalog /path/to/lake

# Layer 3: WS Streaming (Phase 8 — planned, not implemented)
# See docs/proposals/ for the streaming relay design

# All Layers: Sink
binance-datatool sink spot --type klines --interval 1h --target parquet --catalog /path/to/lake BTCUSDT
```
