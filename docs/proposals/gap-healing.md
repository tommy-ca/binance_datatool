---
name: binance-datatool-gap-healing
description: Detect and fill gaps in kline data using composable components. Use when the user asks to find missing data, fill gaps, detect data holes, heal kline data, or backfill missing candles.
---

# Gap Detection & Healing

Detect missing kline data and fill gaps using composable `GapDetector`, `ExchangeClient`, and `KlineStore` components.

> **Note**: The monolithic `EnhancedBinanceAdapter` is deprecated (v0.7.0+) in favor of focused components. See [ccxt.md](ccxt.md) for CCXT-based gap filling.

## Overview

The gap filling pipeline uses three composable components:

1. **GapDetector** (`gap/detector.py`): Pure logic for finding missing candles — no I/O
2. **ExchangeClient** (`exchange/client.py`): Abstract exchange API for fetching data
3. **KlineStore** (`storage/kline_store.py`): Abstract storage for persisting filled data
4. **GapFillWorkflow** (`workflow/gap_fill.py`): Orchestrates detect → fetch → store

## Architecture

```
User / CLI
  │
  ├─→ GapFillWorkflow
  │       │
  │       ├─→ GapDetector.detect(klines) → list[GapInfo]
  │       │
  │       ├─→ for each gap:
  │       │       ExchangeClient.fetch_ohlcv(symbol, since, until)
  │       │       → list[KlineData]
  │       │
  │       └─→ KlineStore.append(klines)
  │
  └─→ FillResult(gaps_filled, klines_fetched, errors)
```

## Gap Detection (Recommended)

### Using KlineSeriesGapDetector (Pure Logic)

```python
from binance_datatool.gap import KlineSeriesGapDetector
from binance_datatool.models import KlineData

def detect_kline_gaps(klines: list[KlineData]) -> list[GapInfo]:
    detector = KlineSeriesGapDetector()
    gaps = detector.detect(klines, interval="1h", symbol="BTCUSDT")

    for gap in gaps:
        print(f"Gap: {gap.start_time} to {gap.end_time}")
        print(f"  Expected candles: {gap.expected_candles}")
        print(f"  Gap size: {gap.gap_size}")

    return gaps
```

**Key difference from old API**: `KlineSeriesGapDetector` is pure logic — no exchange client needed. Pass in any `list[KlineData]` from any source (archive, CCXT, file).

### Using ArchiveGapDetector (File-Based)

```python
from pathlib import Path
from binance_datatool.gap import ArchiveGapDetector

def detect_archive_gaps(archive_dir: Path) -> list[GapInfo]:
    detector = ArchiveGapDetector()
    files = sorted(archive_dir.glob("*.zip"))
    gaps = detector.detect(files, interval="daily", symbol="BTCUSDT")

    for gap in gaps:
        print(f"Missing: {gap.start_time.date()} to {gap.end_time.date()}")

    return gaps
```

## Legacy: EnhancedBinanceAdapter (Deprecated)

> **Deprecation**: `EnhancedBinanceAdapter` is deprecated in v0.7.0+. It delegates internally to the new components but will be removed in v0.9.0.

```python
import warnings
from binance_datatool.adapter.enhanced import EnhancedBinanceAdapter

# DeprecationWarning: EnhancedBinanceAdapter is deprecated...
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    adapter = EnhancedBinanceAdapter()

# These methods still work but delegate to new components:
# - adapter.detect_gaps() → KlineSeriesGapDetector().detect()
# - adapter.detect_archive_gaps() → ArchiveGapDetector().detect()
# - adapter.fill_gaps() → GapFillWorkflow().run()
# - adapter.fetch_klines() → BinanceRestClient().fetch_ohlcv()
# - adapter.stream_klines_ws() → BinanceWsClient().stream_ohlcv()
```

### Migration Path

| Old (Deprecated) | New (Recommended) | Phase |
|------------------|-------------------|-------|
| `EnhancedBinanceAdapter().detect_gaps()` | `KlineSeriesGapDetector().detect()` | 6a |
| `EnhancedBinanceAdapter().detect_archive_gaps()` | `ArchiveGapDetector().detect()` | 6a |
| `EnhancedBinanceAdapter().fill_gaps()` | `GapFillWorkflow().run()` | 6a |
| `EnhancedBinanceAdapter().fetch_klines()` | `BinanceRestClient().fetch_ohlcv()` | 6a |
| `EnhancedBinanceAdapter().stream_klines_ws()` | `BinanceWsClient().stream_ohlcv()` | 6a |
| `EnhancedBinanceAdapter()._save_klines()` | `LocalKlineStore().append()` | 6a |
| Any of the above | `CCXTExchangeClient` equivalents | 6b |

### GapInfo Model

```python
from binance_datatool.models import GapInfo

# GapInfo fields:
#   symbol: str
#   interval: str
#   start_time: datetime
#   end_time: datetime
#   expected_candles: int (ge=0)
#   actual_candles: int (ge=0)
#   gap_size: int (ge=0)
```

## Archive Gap Detection

Detects missing date files in the local archive.

```python
from pathlib import Path
from binance_datatool.adapter.enhanced import EnhancedBinanceAdapter

def detect_archive_gaps():
    adapter = EnhancedBinanceAdapter()

    # List local files
    archive_dir = Path("/path/to/archive/data/spot/daily/klines/BTCUSDT/1d")
    local_files = sorted(archive_dir.glob("*.zip"))

    # Detect gaps
    gaps = adapter.detect_archive_gaps(local_files, "daily", "BTCUSDT")

    for gap in gaps:
        print(f"Missing: {gap.start_time.date()} to {gap.end_time.date()}")
        print(f"  Days missing: {gap.gap_size}")

    return gaps

gaps = detect_archive_gaps()
```

## Gap Filling

Fetches missing klines via REST API and saves them.

```python
async def fill_gaps():
    adapter = EnhancedBinanceAdapter()

    # Detect gaps first
    klines = await adapter.fetch_klines("BTCUSDT", "1h", start, end)
    gaps = adapter.detect_gaps(klines, "1h", "BTCUSDT")

    if not gaps:
        print("No gaps found")
        return

    # Fill gaps
    result = await adapter.fill_gaps(
        symbol="BTCUSDT",
        interval="1h",
        gaps=gaps,
        destination_dir=Path("/path/to/output"),
    )

    print(f"Gaps processed: {result['gaps_processed']}")
    print(f"Gaps filled: {result['gaps_filled']}")
    print(f"Klines fetched: {result['klines_fetched']}")

    if result['errors']:
        print(f"Errors: {result['errors']}")

asyncio.run(fill_gaps())
```

### Fill Result

```python
{
    "symbol": "BTCUSDT",
    "interval": "1h",
    "gaps_processed": 3,
    "gaps_filled": 3,
    "klines_fetched": 72,
    "errors": []
}
```

## Complete Gap Healing Workflow

```python
async def heal_symbol(symbol: str, interval: str, start_ms: int, end_ms: int):
    """Detect and fill all gaps for a symbol/interval range."""
    adapter = EnhancedBinanceAdapter()

    # Step 1: Fetch existing klines
    klines = await adapter.fetch_klines(
        symbol=symbol,
        interval=interval,
        start_time=start_ms,
        end_time=end_ms,
    )

    # Step 2: Detect gaps
    gaps = adapter.detect_gaps(klines, interval, symbol)

    if not gaps:
        return {"status": "complete", "gaps_found": 0}

    # Step 3: Fill gaps
    result = await adapter.fill_gaps(
        symbol=symbol,
        interval=interval,
        gaps=gaps,
    )

    return {
        "status": "healed" if not result["errors"] else "partial",
        "gaps_found": len(gaps),
        "gaps_filled": result["gaps_filled"],
        "klines_fetched": result["klines_fetched"],
        "errors": result["errors"],
    }
```

## Valid Intervals

| Interval | Description |
|----------|-------------|
| `1m` | 1 minute |
| `3m` | 3 minutes |
| `5m` | 5 minutes |
| `15m` | 15 minutes |
| `30m` | 30 minutes |
| `1h` | 1 hour |
| `2h` | 2 hours |
| `4h` | 4 hours |
| `6h` | 6 hours |
| `8h` | 8 hours |
| `12h` | 12 hours |
| `1d` | 1 day |
| `3d` | 3 days |
| `1w` | 1 week |
| `1M` | 1 month |

## KlineData Model

```python
from binance_datatool.models import KlineData

# KlineData fields (prices are strings to preserve precision):
#   open_time: int
#   open: str
#   high: str
#   low: str
#   close: str
#   volume: str
#   close_time: int
#   quote_volume: str
#   num_trades: int
#   taker_buy_volume: str
#   taker_buy_quote_volume: str

# Convert to Decimal when needed:
from decimal import Decimal
price = Decimal(kline.open)
```

## Rate Limits

- REST API: 1200 requests/minute (weight-based)
- Klines endpoint: weight = 10 per request
- Pagination: max 1000 klines per request

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `ValueError: Invalid interval` | Interval not in valid list | Use one of the valid intervals listed above |
| `ValueError: Limit cannot exceed 1000` | Limit > 1000 | Use default limit or set ≤ 1000 |
| `aiohttp.ClientError` | Network failure | Retry with backoff |
| Binance API error (4xx/5xx) | Invalid params or server error | Check symbol, interval, timestamps |

## Testing

```python
# Test gap detection
def test_detect_gaps():
    adapter = EnhancedBinanceAdapter()
    klines = [
        KlineData(open_time=0, open="100", high="105", low="95", close="102",
                  volume="10", close_time=3599999, quote_volume="1000",
                  num_trades=50, taker_buy_volume="5", taker_buy_quote_volume="500"),
        # Gap: next open_time should be 3600000, but we skip to 7200000
        KlineData(open_time=7200000, open="103", high="108", low="100", close="105",
                  volume="12", close_time=7199999, quote_volume="1200",
                  num_trades=60, taker_buy_volume="6", taker_buy_quote_volume="600"),
    ]
    gaps = adapter.detect_gaps(klines, "1h", "TEST")
    assert len(gaps) == 1
    assert gaps[0].gap_size == 1
```

---

For CLI usage, see [SKILL.md](SKILL.md).
For DataOps workflows, see [data-ops.md](data-ops.md).
