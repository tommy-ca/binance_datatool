---
name: binance-datatool-migration
description: ZIP to Parquet to Iceberg migration for binance-datatool. Use when the user asks to migrate bronze ZIP files to Parquet, register files in an Iceberg catalog, convert archive data to columnar format, or set up a data lake table.
---

# Data Lake Migration

Migrate Binance archive ZIP files to Parquet and register them in an Apache Iceberg catalog for SQL querying.

## Overview

The migration workflow converts Binance's ZIP/CSV format to compressed Parquet files and registers them in an Iceberg table:

```
Bronze ZIP → CSV extraction → Parquet (zstd) → Iceberg table registration
```

## Quick Start

### 1. Create an Iceberg Catalog

```python
from binance_datatool.archive.catalog import IcebergCatalog

catalog = IcebergCatalog(
    name="binance",
    warehouse="/data/warehouse",
    uri="/data/warehouse/catalog.db",
)
```

### 2. Define Schema and Partition

```python
from binance_datatool.common.partition import PartitionField, PartitionSpec, PartitionTransformType

schema = {
    "symbol": str,
    "open_time": int,
    "open": float,
    "high": float,
    "low": float,
    "close": float,
    "volume": float,
    "close_time": int,
    "quote_asset_volume": float,
    "num_trades": int,
    "taker_buy_base_asset_volume": float,
    "taker_buy_quote_asset_volume": float,
}

partition_spec = PartitionSpec(fields=[
    PartitionField(source_column="symbol"),
    PartitionField(
        source_column="open_time",
        transform=PartitionTransformType.DAY,
        name="open_time_day",
    ),
])
```

### 3. Migrate Files

```python
from pathlib import Path
from binance_datatool.workflow.migrate import migrate_files
from binance_datatool.common.enums import DataType

zip_paths = [
    Path("/data/lakehouse/bronze/binance/spot/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01-01.zip"),
    Path("/data/lakehouse/bronze/binance/spot/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01-02.zip"),
]

result = migrate_files(
    zip_paths=zip_paths,
    catalog=catalog,
    table_identifier="binance.spot_klines",
    warehouse_table_dir=Path("/data/warehouse/binance/spot_klines"),
    schema=schema,
    partition_spec=partition_spec,
    identifier_fields=["symbol", "open_time"],
    data_type=DataType.klines,
)

print(f"Migrated: {result.migrated}")
print(f"Failed: {result.failed}")
print(f"Total rows: {result.total_rows}")
print(f"Batch ID: {result.batch_id}")
```

## API Reference

### `migrate_files()`

Main migration orchestrator.

```python
def migrate_files(
    zip_paths: list[Path],
    catalog: IcebergCatalog,
    table_identifier: str,
    warehouse_table_dir: Path,
    schema: dict[str, type],
    lineage: LineageTracker | None = None,
    dry_run: bool = False,
    partition_spec: PartitionSpec | None = None,
    identifier_fields: list[str] | None = None,
    data_type: DataType = DataType.klines,
) -> MigrationSummary
```

**Args:**
- `zip_paths` — List of ZIP files to migrate
- `catalog` — Iceberg catalog for table registration
- `table_identifier` — Fully-qualified table name (e.g., `"binance.spot_klines"`)
- `warehouse_table_dir` — Directory for Parquet output
- `schema` — Column name to Python type mapping
- `lineage` — Optional LineageTracker
- `dry_run` — Preview without writing
- `partition_spec` — Optional partitioning
- `identifier_fields` — Primary key columns
- `data_type` — Dataset type for CSV parsing

**Returns:** `MigrationSummary` with `migrated`, `skipped`, `failed`, `total_rows`, `batch_id`

### `extract_zip_to_parquet()`

Extract a single ZIP to Parquet.

```python
def extract_zip_to_parquet(
    zip_path: Path,
    output_dir: Path,
    data_type: DataType = DataType.klines,
) -> tuple[Path, int]
```

**Returns:** `(parquet_path, row_count)`

**Raises:** `ValueError` if ZIP has 0 or >1 CSV files

## Schema Mapping

Python types map to Iceberg types automatically:

| Python | Iceberg |
|--------|---------|
| `str` | `StringType` |
| `int` | `LongType` |
| `float` | `DoubleType` |
| `bool` | `BooleanType` |
| `datetime` | `TimestampType` |

## Partition Transforms

| Transform | Description | Example |
|-----------|-------------|---------|
| `IDENTITY` | Use column as-is | `symbol` |
| `DAY` | Partition by day | `open_time` → daily partitions |
| `HOUR` | Partition by hour | `trade_time` → hourly partitions |
| `BUCKET(N)` | Hash into N buckets | `symbol` → `bucket(32, symbol)` |
| `TRUNCATE(W)` | Truncate to W chars | `symbol` → first W characters |

## Klines CSV → Parquet Mapping

Binance klines CSV has 12 columns (no header):

```
Column 0  → open_time
Column 1  → open
Column 2  → high
Column 3  → low
Column 4  → close
Column 5  → volume
Column 6  → close_time
Column 7  → quote_asset_volume
Column 8  → num_trades
Column 9  → taker_buy_base_asset_volume
Column 10 → taker_buy_quote_asset_volume
```

Other data types (aggTrades, trades, etc.) are read without column names.

## File Naming

Parquet files are named with a directory hash suffix to avoid collisions:

```
Input:  /dir_a/BTCUSDT-1d-2024-01-01.zip
Output: /warehouse/BTCUSDT-1d-2024-01-01_a1b2c3d4.parquet

Input:  /dir_b/BTCUSDT-1d-2024-01-01.zip
Output: /warehouse/BTCUSDT-1d-2024-01-01_e5f6g7h8.parquet
```

## Iceberg Catalog Operations

```python
from binance_datatool.archive.catalog import IcebergCatalog

catalog = IcebergCatalog(name="default", warehouse="/data/wh", uri="/data/wh/catalog.db")

# Create table
catalog.create_table(
    identifier="binance.klines",
    schema={"symbol": str, "open_time": int, "close": float},
    partition_spec=PartitionSpec(fields=[PartitionField(source_column="symbol")]),
    identifier_fields=["symbol", "open_time"],
)

# Check existence
if catalog.table_exists("binance.klines"):
    print("Table exists")

# Load and query
table = catalog.load_table("binance.klines")
scan = table.scan()
data = scan.to_arrow()

# List tables
print(catalog.list_tables("binance"))

# Add files
catalog.add_files("binance.klines", ["/data/output/file1.parquet", "/data/output/file2.parquet"])

# Drop table
catalog.drop_table("binance.klines")
```

## Lineage Events

Migration records these lineage events:

| Event Type | When | Metadata |
|------------|------|----------|
| `TRANSFORMED` | ZIP converted to Parquet | `source_file`, `target_file`, `row_count`, `batch_id` |
| `LOADED` | Parquet registered in catalog | `table`, `file_count`, `total_rows`, `symbols`, `batch_id` |
| `REJECTED` | Migration or registration failed | `file_path`, `error_detail`, `batch_id` |

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `ValueError: Expected exactly 1 CSV` | ZIP has 0 or multiple CSVs | Verify archive format |
| `TableAlreadyExistsError` | Concurrent table creation | Handled automatically (TOCTOU-safe) |
| `NoSuchTableError` | Table doesn't exist for add_files | Call migrate_files which creates table |
| Catalog registration failure | Schema mismatch or corrupt Parquet | Check schema matches CSV structure |

## For DataOps Pipelines

```python
from pathlib import Path
import asyncio

async def migrate_symbol(symbol: str, catalog: IcebergCatalog):
    """Migrate all daily klines for a symbol."""
    bronze_dir = Path(f"/data/lakehouse/bronze/binance/spot/klines/{symbol}/1d")
    zip_files = sorted(bronze_dir.glob("*.zip"))
    
    return migrate_files(
        zip_paths=zip_files,
        catalog=catalog,
        table_identifier="binance.spot_klines",
        warehouse_table_dir=Path("/data/warehouse/binance/spot_klines"),
        schema=KLINES_SCHEMA,
        data_type=DataType.klines,
    )

# Batch migrate multiple symbols
for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
    result = asyncio.run(migrate_symbol(symbol, catalog))
    print(f"{symbol}: {result.migrated} migrated, {result.failed} failed")
```

## Testing

```bash
# Run migration tests
uv run pytest tests/test_migrate.py -v

# Run catalog tests
uv run pytest tests/test_catalog.py -v
```
