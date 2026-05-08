---
name: binance-datatool-ccxt
description: Use CCXT and CCXT Pro for live exchange API access, gap filling, and real-time WebSocket streaming. Use when the user asks to fetch live klines, fill gaps via exchange API, stream real-time data, use CCXT, connect to Binance/Bybit/OKX API, or replace EnhancedBinanceAdapter.
---

# CCXT Integration for Gap Filling Pipelines

Use CCXT (REST) and CCXT Pro (WebSocket) for live exchange data access.

## Overview

The Exchange Layer provides live market data access via CCXT:

1. **CCXTExchangeClient**: REST API for historical gap filling
2. **CCXTProExchangeClient**: WebSocket for real-time streaming
3. **KlineSeriesGapDetector**: Pure gap detection (no I/O)
4. **GapFillWorkflow**: Orchestrates detect → fetch → store

## Prerequisites

```bash
# Install with exchange support
uv pip install binance-datatool[exchange]

# Or with uv sync
uv sync --extra exchange
```

## Quick Start: Fill Gaps

```python
import asyncio
from binance_datatool.exchange import create_client
from binance_datatool.gap import KlineSeriesGapDetector
from binance_datatool.workflow import GapFillWorkflow

async def fill_btc_gaps():
    # 1. Create CCXT client for Binance
    client = create_client("binance")

    # 2. Load existing klines from bronze
    existing_klines = load_from_bronze("BTCUSDT", "1h")

    # 3. Detect gaps
    detector = KlineSeriesGapDetector()
    gaps = detector.detect(existing_klines, "1h", "BTCUSDT")

    if not gaps:
        print("No gaps found")
        return

    # 4. Fill gaps
    workflow = GapFillWorkflow(client, detector)
    result = await workflow.fill_gaps("BTCUSDT", "1h", gaps)

    print(f"Gaps detected: {result.gaps_detected}")
    print(f"Gaps filled: {result.gaps_filled}")
    print(f"Klines fetched: {result.klines_fetched}")

    # 5. Close client
    await client.close()

asyncio.run(fill_btc_gaps())
```

## CCXT REST Client

### Fetch OHLCV

```python
from binance_datatool.exchange import CCXTExchangeClient

async def fetch_klines():
    client = CCXTExchangeClient("binance")

    # Fetch 100 hourly candles starting from timestamp
    klines = await client.fetch_ohlcv(
        symbol="BTC/USDT",      # CCXT uses slash format
        interval="1h",
        since=1704067200000,    # milliseconds
        limit=100,
    )

    for kline in klines:
        print(f"{kline.open_time}: O={kline.open} H={kline.high} L={kline.low} C={kline.close}")

    await client.close()
```

### Auto-Pagination

CCXT handles pagination automatically:

```python
# This fetches ALL klines in the range, paginating as needed
all_klines = await client.fetch_ohlcv(
    symbol="BTC/USDT",
    interval="1h",
    since=1704067200000,
    until=1706745600000,    # CCXT Pro only; for REST, use limit
)
```

**Note**: For large ranges, fetch in chunks to avoid rate limits:

```python
# Manual chunking for fine-grained control
chunk_size = 1000  # candles
start = 1704067200000
end = 1706745600000
interval_ms = 3600 * 1000

all_klines = []
current = start

while current < end:
    klines = await client.fetch_ohlcv(
        "BTC/USDT", "1h", since=current, limit=chunk_size
    )
    if not klines:
        break
    all_klines.extend(klines)
    current = klines[-1].close_time + 1
```

## CCXT Pro WebSocket

### Stream Real-Time Klines

```python
from binance_datatool.exchange import CCXTProExchangeClient

async def stream_klines():
    client = CCXTProExchangeClient("binance")

    async for kline in client.watch_ohlcv("BTC/USDT", "1m"):
        print(f"Live: O={kline.open} C={kline.close} V={kline.volume}")

        # Stop after N candles
        if some_condition:
            break

    await client.close()
```

### Stream to Bronze

```python
from binance_datatool.workflow import StreamToBronzeWorkflow

async def stream_to_bronze():
    workflow = StreamToBronzeWorkflow(
        exchange_client=CCXTProExchangeClient("binance"),
        symbol="BTC/USDT",
        interval="1m",
        buffer_size=100,      # flush every 100 candles
        buffer_timeout=60,    # or every 60 seconds
        bronze_dir="/data/lakehouse/bronze",
    )

    # Runs until interrupted
    await workflow.run()
```

## Gap Detection

### Detect Kline Gaps

```python
from binance_datatool.gap import KlineSeriesGapDetector
from binance_datatool.models import KlineData

def detect_gaps(klines: list[KlineData]) -> list[GapInfo]:
    detector = KlineSeriesGapDetector()
    gaps = detector.detect(klines, "1h", "BTCUSDT")

    for gap in gaps:
        print(f"Gap: {gap.start_time} to {gap.end_time}")
        print(f"  Missing: {gap.expected_candles} candles")

    return gaps
```

### Detect Archive Gaps

```python
from pathlib import Path
from binance_datatool.gap import ArchiveGapDetector

def detect_archive_gaps(archive_dir: Path) -> list[GapInfo]:
    detector = ArchiveGapDetector()

    files = sorted(archive_dir.glob("*.zip"))
    gaps = detector.detect(files, "daily", "BTCUSDT")

    for gap in gaps:
        print(f"Missing: {gap.start_time.date()}")

    return gaps
```

## Multi-Exchange Support

### Supported Exchanges

| Exchange | ID | REST | WebSocket | Notes |
|----------|-----|------|-----------|-------|
| Binance Spot | `binance` | ✅ | ✅ | CCXT Certified |
| Binance USD-M | `binanceusdm` | ✅ | ✅ | Futures |
| Binance COIN-M | `binancecoinm` | ✅ | ✅ | Futures |
| Bybit | `bybit` | ✅ | ✅ | CCXT Certified |
| OKX | `okx` | ✅ | ✅ | CCXT Certified |
| Coinbase | `coinbase` | ✅ | ⏳ | Via existing adapter |

### Use Different Exchange

```python
# Bybit
client = create_client("bybit")
klines = await client.fetch_ohlcv("BTC/USDT", "1h")

# OKX
client = create_client("okx")
klines = await client.fetch_ohlcv("BTC/USDT", "1h")

# Binance Futures
client = create_client("binanceusdm")
klines = await client.fetch_ohlcv("BTC/USDT", "1h")
```

## Symbol Format

CCXT uses `BASE/QUOTE` format (with slash):

| Binance Archive | CCXT Format |
|-----------------|-------------|
| BTCUSDT | BTC/USDT |
| ETHBTC | ETH/BTC |
| SOLUSDT | SOL/USDT |

**Conversion**:
```python
def binance_to_ccxt(symbol: str) -> str:
    """Convert BTCUSDT → BTC/USDT."""
    # Find quote asset (USDT, BTC, ETH, etc.)
    for quote in ["USDT", "BTC", "ETH", "BNB", "FDUSD", "USDC"]:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            return f"{base}/{quote}"
    return symbol  # Fallback
```

## Rate Limiting

CCXT handles rate limits automatically:

```python
# This is the default — no manual rate limit code needed
client = CCXTExchangeClient("binance")  # enableRateLimit=True by default

# If you need to override (not recommended):
client = CCXTExchangeClient("binance", enable_rate_limit=True, rate_limit=100)
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `NetworkError` | Connection timeout | CCXT auto-retry 3x |
| `ExchangeError` | Invalid symbol | Check symbol format (BTC/USDT) |
| `RateLimitExceeded` | Too many requests | CCXT auto-backoff; increase interval |
| `NotSupported` | Interval not supported | Use valid CCXT timeframe |
| `AuthenticationError` | API key required | Only public endpoints supported |

## Testing

### Mock CCXT for Unit Tests

```python
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_ccxt_client():
    exchange = MagicMock()
    exchange.fetch_ohlcv = AsyncMock(return_value=[
        [1704067200000, "42000", "43000", "41000", "42500", "100.5"],
    ])
    exchange.id = "binance"
    return exchange

async def test_fill_gaps(mock_ccxt_client):
    client = CCXTExchangeClient(mock_ccxt_client)
    klines = await client.fetch_ohlcv("BTC/USDT", "1h")
    assert len(klines) == 1
```

### Integration Test (Real Exchange)

```python
@pytest.mark.integration
@pytest.mark.ccxt
async def test_real_binance_fetch():
    """Test with real Binance via CCXT (read-only)."""
    client = CCXTExchangeClient("binance")
    klines = await client.fetch_ohlcv("BTC/USDT", "1h", limit=10)
    assert len(klines) <= 10
    assert klines[0].open_time > 0
    await client.close()
```

## CLI Commands (Phase 6)

```bash
# Detect gaps in archive
binance-datatool gap detect BTCUSDT --interval 1h --start 2024-01-01 --end 2024-01-31

# Fill gaps via CCXT
binance-datatool gap fill BTCUSDT --interval 1h --exchange binance

# Show gap status
binance-datatool gap status BTCUSDT --interval 1h

# Stream real-time to bronze
binance-datatool stream BTCUSDT --interval 1m --exchange binance --buffer-size 100
```

## Migration from EnhancedBinanceAdapter

| Old (EnhancedBinanceAdapter) | New (CCXT) |
|------------------------------|------------|
| `fetch_klines()` | `CCXTExchangeClient.fetch_ohlcv()` |
| `fetch_all_klines()` | `fetch_ohlcv()` with auto-pagination |
| `detect_gaps()` | `KlineSeriesGapDetector.detect()` |
| `fill_gaps()` | `GapFillWorkflow.fill_gaps()` |
| `stream_klines_ws()` | `CCXTProExchangeClient.watch_ohlcv()` |
| Manual rate limiting | CCXT automatic |
| Manual retry logic | CCXT automatic |
| Binance only | 100+ exchanges |

## Architecture

```
┌─────────────────────────────────────────┐
│         GapFillWorkflow                 │
│  (orchestrator: detect → fetch → store) │
└─────────────┬───────────────────────────┘
              │
    ┌─────────┼─────────┐
    │         │         │
    ▼         ▼         ▼
┌──────┐ ┌────────┐ ┌──────────┐
│CCXT  │ │ Gap    │ │ KlineStore│
│Client│ │Detector│ │ (Protocol)│
└──────┘ └────────┘ └──────────┘
```

---

For archive downloads, see [SKILL.md](SKILL.md).
For bronze layer, see [bronze.md](bronze.md).
For migration workflows, see [migration.md](migration.md).
