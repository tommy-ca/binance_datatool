---
name: binance-datatool-bronze
description: Bronze layer operations for binance-datatool. Use when the user asks to ingest data into bronze, verify bronze files, list bronze files, scan bronze status, or export bronze lineage. Covers the raw data storage layer with immutability guarantees.
---

# Bronze Layer Operations

The bronze layer stores raw upstream data unchanged with checksums and lineage tracking.

## Directory Structure

```
lakehouse/
└── bronze/
    └── {source}/
        └── {market_type}/
            └── {data_type}/
                └── {symbol}/
                    └── {interval}/
                        ├── BTCUSDT-1d-2024-01-01.zip
                        └── BTCUSDT-1d-2024-01-01.zip.CHECKSUM
```

## Commands

### ingest

Download raw files from source into the bronze layer.

```bash
binance-datatool bronze ingest \
  {spot|um|cm} \
  SYMBOL [SYMBOL ...] \
  --type {klines|aggTrades|trades|bookDepth|bookTicker|fundingRate} \
  [--interval 1m|5m|15m|1h|4h|1d|...] \
  [--source binance|coinbase] \
  [--lakehouse /data/lakehouse] \
  [--dry-run]
```

**Examples:**

```bash
# Ingest BTCUSDT klines
binance-datatool bronze ingest spot BTCUSDT --type klines --interval 1d

# Ingest multiple symbols
binance-datatool bronze ingest um BTCUSDT ETHUSDT --type fundingRate

# Dry run
binance-datatool bronze ingest spot BTCUSDT --type klines --interval 1d --dry-run

# With custom lakehouse
binance-datatool bronze ingest spot BTCUSDT --type klines --interval 1d --lakehouse /data/lakehouse
```

**Immutability:** Raises `FileExistsError` if a bronze file already exists. Use `--dry-run` to preview.

### verify

Verify bronze files against SHA256 checksums.

```bash
binance-datatool bronze verify \
  {spot|um|cm} \
  SYMBOL [SYMBOL ...] \
  --type {klines|aggTrades|trades|bookDepth|bookTicker|fundingRate} \
  [--interval ...] \
  [--source binance] \
  [--lakehouse /data/lakehouse] \
  [--dry-run]
```

**Examples:**

```bash
binance-datatool bronze verify spot BTCUSDT --type klines --interval 1d
```

**Statuses:**
- `verified` — checksum matches
- `verification_failed` — checksum mismatch or missing file

### list

List files in the bronze layer.

```bash
binance-datatool bronze list \
  {spot|um|cm} \
  SYMBOL [SYMBOL ...] \
  --type {klines|aggTrades|trades|bookDepth|bookTicker|fundingRate} \
  [--interval ...] \
  [--source binance] \
  [--lakehouse /data/lakehouse] \
  [--long]
```

**Examples:**

```bash
# Simple list
binance-datatool bronze list spot BTCUSDT --type klines --interval 1d

# With size and checksum
binance-datatool bronze list spot BTCUSDT --type klines --interval 1d --long
```

### scan

Scan bronze files by status.

```bash
binance-datatool bronze scan \
  {spot|um|cm} \
  SYMBOL [SYMBOL ...] \
  --type {klines|aggTrades|trades|bookDepth|bookTicker|fundingRate} \
  [--interval ...] \
  [--source binance] \
  [--lakehouse /data/lakehouse] \
  [--status needs_verify|verified|failed|ready_for_silver]
```

**Examples:**

```bash
# Show status counts for all files
binance-datatool bronze scan spot BTCUSDT --type klines --interval 1d

# List only files needing verification
binance-datatool bronze scan spot BTCUSDT --type klines --interval 1d --status needs_verify
```

**Statuses:**
- `needs_verify` — ZIP exists but no CHECKSUM file
- `verified` — ZIP + CHECKSUM, checksum matches
- `failed` — ZIP + CHECKSUM, checksum mismatch
- `ready_for_silver` — ZIP + CHECKSUM, not yet processed to silver

### lineage

Export bronze lineage events.

```bash
binance-datatool bronze lineage \
  [--lakehouse /data/lakehouse] \
  [--format jsonl]
```

**Examples:**

```bash
binance-datatool bronze lineage --lakehouse /data/lakehouse
```

**Output:** JSONL format with one event per line.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `BINANCE_DATATOOL_LAKEHOUSE` | Default lakehouse root directory |

## Lakehouse Resolution Order

1. `--lakehouse` CLI flag
2. `BINANCE_DATATOOL_LAKEHOUSE` environment variable
3. Error if neither is set

## Lineage Events

The bronze layer records these lineage event types:

| Event Type | When | Metadata |
|------------|------|----------|
| `DOWNLOADED` | File ingested | `file_path`, `file_checksum`, `file_size`, `ingested_at`, `batch_id` |
| `VERIFIED` | Checksum matches | `file_path`, `file_checksum` |
| `VERIFICATION_FAILED` | Checksum mismatch | `file_path`, `error_detail` |

**Query lineage:**

```python
from binance_datatool.lineage import LineageTracker

tracker = LineageTracker()
tracker.load("/data/lakehouse/bronze/lineage.jsonl")

# Query by symbol
events = tracker.query(source="binance", symbol="BTCUSDT")

# Query by event type
downloads = tracker.query(source="binance", event_type=LineageEventType.DOWNLOADED)
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `LakehouseNotConfiguredError` | No lakehouse configured | Set `BINANCE_DATATOOL_LAKEHOUSE` or use `--lakehouse` |
| `FileExistsError` | Bronze file already exists | Bronze is append-only; delete manually if needed |
| `ValueError: interval required` | Kline data without interval | Add `--interval 1d` |

## For Programmatic Use

```python
from binance_datatool.workflow import BronzeIngestWorkflow, BronzeVerifyWorkflow
from binance_datatool.lineage import LineageTracker
from binance_datatool.source_registry import SourceRegistry
from binance_datatool.common.enums import TradeType, DataType

# Ingest
adapter = SourceRegistry.get("binance")
workflow = BronzeIngestWorkflow(
    adapter=adapter,
    trade_type=TradeType.spot,
    data_type=DataType.klines,
    symbols=["BTCUSDT"],
    interval="1d",
    lineage=LineageTracker(),
)
result = await workflow.run()
print(f"Ingested: {result.files_ingested}, Failed: {result.failed_symbols}")

# Verify
verify = BronzeVerifyWorkflow(
    trade_type=TradeType.spot,
    data_type=DataType.klines,
    symbols=["BTCUSDT"],
    interval="1d",
    lineage=LineageTracker(),
)
result = await verify.run()
print(f"Verified: {result.verified}, Failed: {result.failed}")
```
