---
name: binance-datatool-data-ops
description: DataOps workflows for binance-datatool: validate data against contracts, track lineage, and ensure data quality. Use when the user asks to validate data, check data quality, track data provenance, or record data lineage events.
---

# DataOps Workflows

Data validation, contract enforcement, and lineage tracking for binance-datatool.

## Data Contracts

Data contracts define schema, validation rules, and quality checks for datasets.

### Built-in Contracts

```python
from binance_datatool.models import (
    DataContract,
    ContractRegistry,
    DataSource,
    MarketType,
    DataType,
    BINANCE_SPOT_KLINES_CONTRACT,
    BINANCE_UM_KLINES_CONTRACT,
)

# Get a registered contract
contract = ContractRegistry.get(DataSource.BINANCE, MarketType.SPOT, DataType.KLINES)
```

### Pre-built Contracts

| Contract | Source | Market | Data Type |
|----------|--------|--------|-----------|
| `BINANCE_SPOT_KLINES_CONTRACT` | Binance | Spot | Klines |
| `BINANCE_UM_KLINES_CONTRACT` | Binance | USD-M Futures | Klines |

### Contract Schema (Spot Klines)

```python
{
    "open_time": int,
    "open": Decimal,
    "high": Decimal,
    "low": Decimal,
    "close": Decimal,
    "volume": Decimal,
    "close_time": int,
    "quote_volume": Decimal,
    "num_trades": int,
    "taker_buy_volume": Decimal,
    "taker_buy_quote_volume": Decimal,
}
```

### Contract Validators

Built-in validators check:
- `open > 0`, `close > 0` (positive prices)
- `high >= low` (price ordering)
- `volume >= 0`, `quote_volume >= 0` (non-negative volumes)
- `close_time > open_time` (time ordering)

## Validation Workflow

### Step 1: Load Data

```python
from decimal import Decimal

# From CSV/JSON file
import json
with open("data.json") as f:
    data = json.load(f)  # list[dict]

# Or from polars DataFrame
import polars as pl
df = pl.read_csv("data.csv")
data = df.to_dicts()
```

### Step 2: Validate Against Contract

```python
from binance_datatool.models import ContractRegistry, DataSource, MarketType, DataType

contract = ContractRegistry.get(DataSource.BINANCE, MarketType.SPOT, DataType.KLINES)
result = contract.validate(data)

if result.passed:
    print(f"✓ {result.row_count} rows valid")
else:
    print(f"✗ {result.error_count} errors found")
    for error in result.errors[:5]:  # Show first 5
        print(f"  Row {error.row_index}: {error.column} - {error.reason}")
```

### Step 3: Handle Validation Results

```python
from binance_datatool.models import ValidationResult

def process_validation(result: ValidationResult):
    if result.passed:
        # Data is valid — proceed to storage
        return True
    else:
        # Log errors for investigation
        for error in result.errors:
            if error.row_index is not None:
                print(f"Row {error.row_index}: {error.reason}")
            else:
                print(f"Schema error: {error.reason}")
        return False
```

## Lineage Tracking

Record data provenance events for audit trails and debugging.

### Recording Events

```python
from datetime import datetime
from binance_datatool.lineage import LineageTracker
from binance_datatool.models import LineageEvent, LineageEventType

tracker = LineageTracker()

# Record download event
tracker.record(LineageEvent(
    source="binance",
    symbol="BTCUSDT",
    date="2024-01-01",
    event_type=LineageEventType.DOWNLOADED,
    timestamp=datetime.now(),
    message="Downloaded 1d klines",
    metadata={"file": "BTCUSDT-1d-2024-01-01.zip", "size_bytes": 1234567},
))

# Record validation event
tracker.record(LineageEvent(
    source="binance",
    symbol="BTCUSDT",
    date="2024-01-01",
    event_type=LineageEventType.VALIDATED,
    timestamp=datetime.now(),
    message="Validation passed",
    metadata={"row_count": 1440, "error_count": 0},
))
```

### Querying Lineage

```python
# All events for a symbol
events = tracker.query(symbol="BTCUSDT")

# All download events
downloads = tracker.query(event_type=LineageEventType.DOWNLOADED)

# Events in date range
from datetime import datetime
events = tracker.query(
    source="binance",
    date_range=(datetime(2024, 1, 1), datetime(2024, 12, 31)),
)

# Most recent event for a symbol
latest = tracker.get_latest(source="binance", symbol="BTCUSDT")
```

### Exporting Lineage

```python
# JSON array
json_str = tracker.export(format="json")

# JSON Lines (one event per line)
jsonl_str = tracker.export(format="jsonl")

# CSV
csv_str = tracker.export(format="csv")
```

### Lineage Statistics

```python
stats = tracker.stats()
# {
#     "total_events": 100,
#     "by_event_type": {"downloaded": 50, "validated": 45, "verification_failed": 5},
#     "by_source": {"binance": 100},
#     "by_symbol": ["BTCUSDT", "ETHUSDT"],
#     "unique_symbols": 2
# }
```

## Full DataOps Pipeline

```python
from binance_datatool.lineage import LineageTracker
from binance_datatool.models import (
    ContractRegistry, DataSource, MarketType, DataType,
    LineageEvent, LineageEventType,
)
from datetime import datetime

tracker = LineageTracker()
contract = ContractRegistry.get(DataSource.BINANCE, MarketType.SPOT, DataType.KLINES)

def ingest_partition(symbol: str, date: str, data: list[dict]):
    # 1. Record download
    tracker.record(LineageEvent(
        source="binance",
        symbol=symbol,
        date=date,
        event_type=LineageEventType.DOWNLOADED,
        timestamp=datetime.now(),
        metadata={"row_count": len(data)},
    ))

    # 2. Validate
    result = contract.validate(data)

    # 3. Record validation
    tracker.record(LineageEvent(
        source="binance",
        symbol=symbol,
        date=date,
        event_type=LineageEventType.VALIDATED if result.passed else LineageEventType.VALIDATION_FAILED,
        timestamp=datetime.now(),
        metadata={"row_count": result.row_count, "error_count": result.error_count},
    ))

    # 4. Proceed or reject
    if result.passed:
        # write_to_lakehouse(data, symbol, date)
        tracker.record(LineageEvent(
            source="binance",
            symbol=symbol,
            date=date,
            event_type=LineageEventType.LOADED,
            timestamp=datetime.now(),
        ))
        return True
    else:
        # log errors, alert
        return False
```

## Data Quality Checklist

- [ ] Schema matches expected columns and types
- [ ] No NULL values in key columns
- [ ] Prices are positive
- [ ] Volumes are non-negative
- [ ] High >= Low for each candle
- [ ] Close time > Open time
- [ ] No duplicate rows (by primary key)
- [ ] Lineage event recorded for each partition

## Error Modes

| Error | Cause | Solution |
|-------|-------|----------|
| `ValidationError: key column 'X' not found in schema` | Key col not in schema dict | Add column to schema or remove from key_cols |
| `DataContract.schema must not be empty` | Empty schema | Define at least one column |
| `Cannot normalize data of type X` | Unsupported data type | Convert to list[dict], pandas DataFrame, or polars DataFrame |

## Pydantic Models

```python
from binance_datatool.models import (
    DataContract,         # Schema + validation rules
    ValidationResult,     # Validation output (passed, errors, row_count)
    ValidationError,      # Single error (row_index, column, reason)
    LineageEvent,         # Provenance event (frozen)
    LineageEventType,     # Event type enum
)
```

---

For CLI usage, see [SKILL.md](SKILL.md).
For gap detection and healing, see [gap-healing.md](gap-healing.md).
