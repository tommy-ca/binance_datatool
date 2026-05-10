---
title: Wire Archive with REST/WS API for Gap Filling
type: feat
status: active
date: 2026-05-08
origin: docs/brainstorms/2026-05-08-archive-gap-filling-requirements.md
---

# Wire Archive with REST/WS API for Gap Filling

## Overview

Enable the archive module to fill gaps in local data using the SDK-backed Binance REST API. For each trade type (spot, um, cm), detect missing date ranges and fetch them via REST API, storing results alongside archive data.

## Problem Frame

The Binance public archive (data.binance.vision) has a ~1-2 day delay and only provides data for listed symbols. The SDK-backed exchange clients can fetch live data via REST API. This feature bridges the gap: detect missing data and fill it from the REST API.

## Requirements Trace

- R1. Gap detection: Scan local archive for existing files, detect missing date ranges
- R2. Data type mapping: Map archive data types (klines, aggTrades, fundingRate) to SDK REST methods
- R3. Gap filling: Fetch missing data from REST API using SDK clients
- R4. Storage: Save filled data as CSV with checksum in `_filled/` subdirectory
- R5. CLI: Add `gap-fill` command
- R6. All markets: Support spot, um, cm

## Scope Boundaries

- **In scope**: klines, aggTrades for spot/um/cm; fundingRate for um/cm
- **Out of scope**: trades (REST history limited), book depth/ticker (archive only), WebSocket filling

## Context & Research

### Data Type to REST API Mapping

| Archive Data Type | Spot SDK | UM SDK | CM SDK |
|-------------------|----------|--------|--------|
| klines | `rest_api.klines()` | `rest_api.kline_candlestick_data()` | `rest_api.kline_candlestick_data()` |
| aggTrades | `rest_api.agg_trades()` | `rest_api.compressed_aggregate_trades_list()` | `rest_api.compressed_aggregate_trades_list()` |
| fundingRate | N/A | `rest_api.get_funding_rate_history()` | `rest_api.get_funding_rate_history_of_perpetual_futures()` |

### Archive CSV Format (Binance)
Inside each ZIP file, Binance stores CSV files like:
```
BTCUSDT-1m-2026-05-08.csv  →  open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore
```

### Key Technical Decisions
- Extend ExchangeClient protocol with `fetch_agg_trades()` across all market types
- Add `fetch_funding_rate()` to UM/CM REST clients only
- Use existing `fetch_ohlcv` for klines gap filling (no change needed)
- Store filled data as CSV with SHA256 sidecar

## Implementation Units

- [ ] **Unit 1: Extend ExchangeClient protocol with aggTrades**

**Goal:** Add `fetch_agg_trades()` to ExchangeClient protocol and implement on all REST clients.

**Files:**
- Modify: `src/binance_datatool/exchange/client.py`
- Modify: `src/binance_datatool/exchange/binance_rest.py`
- Test: `tests/test_exchange.py`

**Approach:**
- Add to ExchangeClient protocol: `fetch_agg_trades(symbol, since, until, limit) -> list[dict]`
- Implement on BinanceSpotRestClient using `rest_api.agg_trades()`
- Implement on BinanceUmRestClient using `rest_api.compressed_aggregate_trades_list()`
- Implement on BinanceCmRestClient using `rest_api.compressed_aggregate_trades_list()`

---

- [ ] **Unit 2: Add fetch_funding_rate to futures REST clients**

**Goal:** Add funding rate fetching for UM and CM futures.

**Files:**
- Modify: `src/binance_datatool/exchange/client.py`
- Modify: `src/binance_datatool/exchange/binance_rest.py`
- Test: `tests/test_exchange.py`

**Approach:**
- Add to ExchangeClient protocol: `fetch_funding_rate(symbol, since, until, limit) -> list[dict]`
- Implement on BinanceUmRestClient using `rest_api.get_funding_rate_history()`
- Implement on BinanceCmRestClient using `rest_api.get_funding_rate_history_of_perpetual_futures()`
- Spot client raises NotImplementedError

---

- [ ] **Unit 3: Create GapFillWorkflow**

**Goal:** Workflow that detects gaps and fills them via REST API.

**Files:**
- Create: `src/binance_datatool/workflow/gap_fill.py`
- Create: `tests/test_gap_fill.py`

**Approach:**
1. Accept: symbols, trade_type, data_type, interval, start_time, end_time
2. For each symbol:
   - Scan local archive for existing files
   - Determine date gaps in [start_time, end_time]
   - For each gap:
     - If klines: use ExchangeClient.fetch_ohlcv
     - If aggTrades: use ExchangeClient.fetch_agg_trades
     - If fundingRate: use ExchangeClient.fetch_funding_rate
   - Save as CSV in `archive_home/.../_filled/`
   - Create SHA256 checksum
3. Return summary: files_filled, files_failed, date_range

---

- [ ] **Unit 4: Add CLI gap-fill command**

**Goal:** CLI entry point for gap filling.

**Files:**
- Modify: `src/binance_datatool/cli/__init__.py` or `cli/archive.py`
- Modify: `src/binance_datatool/cli/archive.py`

**Approach:**
- Add `gap-fill` subcommand to archive group
- Parameters: symbols, trade_type, data_type, interval, start, end, archive-home
- Construct GapFillWorkflow and run

---

- [ ] **Unit 5: Update docs**

**Files:**
- Modify: `docs/requirements.md`
- Modify: `docs/data-flows.md` (if exists)
- Modify: `AGENTS.md`

**Approach:**
- Add gap-filling section to requirements
- Add data flow diagram
- Update AGENTS.md with gap-fill command

---
**Status**: Complete — implementation merged to main on 2026-05-10.
