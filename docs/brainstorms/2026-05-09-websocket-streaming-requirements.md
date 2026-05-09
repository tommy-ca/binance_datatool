---
date: 2026-05-09
topic: websocket-streaming-pipeline
---

# Real-Time WebSocket Streaming Pipeline

## Problem
The current pipeline captures historical data from Binance archive + REST API.
Four funding rate fields cannot be captured historically — they require
real-time WebSocket subscription:

- `predicted_funding_rate` (markPrice stream)
- `open_interest` (contractInfo stream)
- `last_price` (ticker stream)
- `index_price` (markPrice stream)

## Available SDK WS Methods

| Field | SDK WS Method | Stream Type |
|-------|--------------|-------------|
| `funding_rate` | `mark_price_stream(symbol)` | continuous |
| `mark_price` | `mark_price_stream(symbol)` | continuous |
| `index_price` | `mark_price_stream(symbol)` | continuous |
| `predicted_funding_rate` | `mark_price_stream(symbol)` | continuous |
| `last_price` | `individual_symbol_ticker_streams(symbol)` | event-based |
| `open_interest` | `contract_info_stream()` (or ticker) | periodic snapshot |

All SDK WS methods return `RequestStreamHandle` with `.on("message", callback)`.

## Architecture

```
WebSocket Stream (wss://fstream.binance.com)
  ↓ mark_price_stream("BTCUSDT")
  ↓ individual_symbol_ticker_streams("BTCUSDT")
  ↓ contract_info_stream()
  │
  ├── EventProcessor
  │     ↓ parse → SilverFundingRate
  │     ↓ map fields to tardis.dev naming
  │
  ├── [Optional] TimeSeriesBuffer
  │     ↓ micro-batch every N seconds
  │
  └── SilverSink
        ↓ append to DuckLake fundingRate table
        ↓ or write to Parquet via Polars
```

## Requirements
- R1. Extend WS clients with `stream_funding_rate()` — equivalent of RestClient.fetch_funding_rate()
  but from WebSocket mark_price stream
- R2. Capture all 4 extra fields: predicted_funding_rate, index_price,
  last_price, open_interest
- R3. Persist streamed data to Silver layer (DuckLake fundingRate table)
- R4. Support incremental backfill: fill gaps between latest Silver record and current time
- R5. All trade types: spot (ticker only), um, cm

## Data Flow
```
Real-time WS → asyncio.Queue → batch collector → DuckLake INSERT
                            ↓
              LineageTracker.record(STREAMED)
                            ↓
              HealthCheckWorkflow detects freshness
```

## Scope Boundaries
- **In scope**: Funding rate fields from WS mark_price + ticker streams
- **Out of scope**: Full order book streaming, trade streaming,
  kline streaming (already supported), multi-exchange WS

## Next Steps
1. Extend ExchangeClient protocol: add `stream_funding_rate()` method
2. Implement on BinanceUmWsClient and BinanceCmWsClient using
   `mark_price_stream()` + `ticker_streams()`
3. Create StreamPipeline: subscribes, receives, batches, persists
4. Wire to CLI: `binance-datatool stream funding-rate`
5. Update DuckLake schema to include all 4 tardis.dev fields
