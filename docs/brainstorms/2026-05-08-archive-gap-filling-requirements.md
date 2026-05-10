---
date: 2026-05-08
topic: archive-gap-filling
---

# Archive Gap Filling via REST/WS API

## Problem Frame
The Binance public archive (data.binance.vision) has a ~1-2 day delay for recent data and may not cover every data type for every symbol. The exchange clients (now SDK-backed) can fetch live data via REST API. This feature connects the two: when archive data is missing or incomplete, use the REST API to fill gaps.

## Requirements
- R1. Gap detection: Scan local archive and detect missing date ranges per symbol/data type/interval
- R2. Data type to REST API mapping: Map each archive data type to its SDK REST method
- R3. Gap filling: Fetch missing data from REST API and store alongside archive data
- R4. Storage format: Store filled data as CSV (matches Binance's ZIP contents) for downstream consumption
- R5. CLI command: Add `gap-fill` CLI command (or extend `download --fill-gaps`)
- R6. Verify support: Update verify workflow to acknowledge filled data
- R7. All market types: Support spot, um, cm

## Data Types Matrix

| Trade Type | Archive Data Type | REST API SDK Method | Interval Required | Notes |
|------------|------------------|--------------------|-------------------|-------|
| Spot | klines | `rest_api.klines()` | ✅ Yes | Already have ExchangeClient.fetch_ohlcv |
| Spot | aggTrades | `rest_api.agg_trades()` | ❌ No | Timestamp-based |
| Spot | trades | `rest_api.historical_trades()` | ❌ No | Timestamp-based |
| UM | klines | `rest_api.kline_candlestick_data()` | ✅ Yes | Already wired |
| UM | aggTrades | `rest_api.compressed_aggregate_trades_list()` | ❌ No | Timestamp-based |
| UM | fundingRate | `rest_api.get_funding_rate_history()` | ❌ No | Timestamp-based |
| CM | klines | `rest_api.kline_candlestick_data()` | ✅ Yes | Already wired |
| CM | aggTrades | `rest_api.compressed_aggregate_trades_list()` | ❌ No | Timestamp-based |
| CM | fundingRate | `rest_api.get_funding_rate_history_of_perpetual_futures()` | ❌ No | Timestamp-based |

## Success Criteria
- Gap detection correctly identifies missing dates across spot/um/cm data types
- REST API fetches fill all detectable gaps
- Filled data is stored in a verifiable format
- CLI command completes without errors

## Key Decisions
- **CSV format**: Store as CSV matching Binance ZIP content format (not re-zipping)
- **Sidecar checksum**: Generate SHA256 for each filled CSV file
- **Separate subdirectory**: `_filled/` alongside archive files for clear separation
- **No REST API for trades**: Public REST trades endpoint has limited history; archive is primary source
- **No WS for filling**: WebSocket is real-time only, not suitable for historical gap filling

## Scope Boundaries
- **In scope**: Gap detection, REST API fill for klines/aggTrades/fundingRate
- **Post-MVP**: Real-time streaming fill, gap healing automation
- **Out of scope**: Book depth, book ticker gap filling (archive-only data types)
