---
date: 2026-05-10
topic: pipeline-architecture
---

# Pipeline Architecture Design

## Overview

The `binance_datatool` pipeline ingests historical market data from Binance
(Archive S3 + REST API), transforms it to a normalized Silver schema, and
persists it in DuckLake v1.0 native tables. Orchestration is handled by
Prefect 3.x flows and tasks.

## Pipeline Stages

```
historical_pipeline (ThreadPoolTaskRunner, max_workers=4)
  │
  ├── 0: refresh_metadata_flow (subflow, sequential)
  │       → saves venues + symbols tables in DuckLake
  │
  ├── 1: prepare_symbol.map() (parallel fan-out)
  │     └── per symbol: download_archive → verify_archive → fill_gaps
  │         • download: ArchiveDownloadWorkflow via asyncio.run()
  │         • verify: ArchiveVerifyWorkflow (sync)
  │         • fill: GapFillWorkflow via asyncio.run()
  │
  ├── 2: sink_silver() (sequential, concurrency guard)
  │     └── per symbol: SinkWorkflow.transform()
  │         • Polars: read ZIP CSVs + filled CSVs
  │         • Bronze→Silver transform (ts_event, ts_recv)
  │         • DuckLake INSERT (partitioned by trade_type/symbol/interval/ts_date)
  │
  └── 3: health_flow() (sequential subflows)
        └── per symbol: check_ducklake_anomalies()
            • null prices, zero volumes, duplicate timestamps
            • date gaps, Z-score outlier detection
```

## Prefect-Native Patterns

### Error Isolation

Use `result(raise_on_failure=False)` + `state.is_completed()` instead of
`try/except` to handle per-symbol failures without aborting the batch:

```python
for sym, future in zip(sym_list, prep_futures, strict=True):
    meta = future.result(raise_on_failure=False)
    if future.state.is_completed():
        rows = sink_silver(tt, sym, ...)
        results[sym] = {"rows_sunk": rows, "gaps_filled": meta["gaps"]}
    else:
        results[sym] = {"rows_sunk": 0, "gaps_filled": 0, "error": str(meta)}
```

This is the Prefect-native idiom (per `prefect.futures.PrefectFuture.result()`
docs). The `zip(strict=True)` pair ensures the symbol is known even when the
task's return value is an exception.

### Concurrency Control

DuckDB does not support concurrent writers. Use Prefect's `concurrency`
context manager with `occupy=1` to serialize writes:

```python
from prefect.concurrency.sync import concurrency

with concurrency("ducklake-writer", occupy=1):
    stats = workflow.transform(...)
```

This serializes across task runs within the same Prefect process. For
cross-process serialization, a Prefect global concurrency limit via
`prefect concurrency-limit create ducklake-writer 1` is needed.

### Async Bridging

Prefect 3.x does not support calling async tasks from sync flows. Sync tasks
use `asyncio.run()` to bridge to async workflows:

```python
@task
def download_archive(...) -> int:
    import asyncio
    wf = ArchiveDownloadWorkflow(...)
    result = asyncio.run(wf.run())
    return result.downloaded
```

This is the recommended pattern per Prefect 3.x migration docs.

### Serving Deployments

Use `prefect.serve()` with `flow.to_deployment()` to serve multiple cron
deployments in a single process:

```python
from prefect import serve

serve(
    historical_pipeline.to_deployment(name="daily-backfill", cron="0 6 * * *"),
    refresh_metadata_flow.to_deployment(name="hourly-metadata", cron="0 * * * *"),
)
```

This replaces the legacy blocking `.serve()` pattern and registers both
deployments.

## Resource Management

### DuckDB Connections
Every `connect()` must be paired with a `close()` in `finally`. The
`_route_to_dlq` function is the canonical example of this pattern:

```python
con = None
try:
    con = duckdb.connect(path)
    ...
except Exception as e:
    _log.warning("failed: %s", e)
finally:
    if con is not None:
        con.close()
```

### DataType Configuration
Use `try/except ValueError` instead of private `_value2member_map_`:

```python
try:
    dt = DataType(data_type)
except ValueError:
    dt = DataType.klines
```

### StrEnum Pattern
All enum classes use `enum.StrEnum` (Python 3.11+) instead of the legacy
`(str, Enum)` pattern. This eliminates the UP042 lint warning and provides
native string comparison, `.value` access, and `__members__` introspection:

```python
from enum import StrEnum

class TradeType(StrEnum):
    spot = "spot"
    um = "um"
```

### SQL Injection Prevention
All DuckDB queries in `health_check.py` use parameterized queries (`?`
placeholders) for user-supplied values. Table/column names use an
identifier sanitizer (`_sanitize_identifier`) that strips non-alphanumeric
characters:

```python
tn = _sanitize_identifier(table_name)  # safe for f-string
result = con.execute(
    f"SELECT COUNT(*) FROM {tn} WHERE symbol = ?", [symbol]
).fetchone()[0]
```

## Task Fan-Out Design

### Parallel (Stage 1)
`prepare_symbol.map()` fans out to N symbols concurrently via
`ThreadPoolTaskRunner(max_workers=4)`. Each symbol runs three sub-tasks
sequentially: download → verify → fill_gaps. The sub-tasks do NOT touch
DuckDB, so no concurrency guard is needed.

### Sequential (Stage 2)
`sink_silver()` runs per-symbol sequentially because DuckDB only supports one
writer at a time. The `ducklake-writer` concurrency guard enforces this even
if sink is called concurrently from other flow runs.

### Sequential (Stage 3)
`health_flow()` runs per-symbol sequentially. DuckDB reads are fast
(milliseconds), so parallelizing adds complexity without meaningful benefit.

## Symbol-to-Future Mapping

```
zip(sym_list, futures, strict=True)
```

This cleanly pairs each symbol with its corresponding PrefectFuture. Even when
a task raises, the symbol is still known — no need to extract it from the
failed task's return value.

## Nested Flows

`bulk_backfill` does NOT declare a task runner — it delegates entirely to
`historical_pipeline` which owns the `ThreadPoolTaskRunner`. This avoids
non-deterministic nested runner behavior.

## Metadata Concurrency Guard

`refresh_metadata_flow` writes to `venues` and `symbols` tables in DuckLake.
It uses the same `ducklake-writer` concurrency guard as `sink_silver` to
prevent races when both run as separate deployments (daily backfill at 06:00
and hourly metadata at 00:00).

```python
from prefect.concurrency.sync import concurrency

with concurrency("ducklake-writer", occupy=1):
    wf.save_venues(wf.refresh_venues())
    ...
    wf.save_symbols(syms)
```

## Task-to-Task Calls in Prefect

In Prefect 3.x, calling a `@task` from within another `@task` creates a
properly tracked sub-task run with its own `TaskRun` object, state machine
(Pending → Running → Completed), and event emission. The sub-tasks do NOT
execute as plain function calls — they go through the full task engine.

However, sub-tasks called via `Task.__call__()` (not `.submit()`) run
sequentially in the same thread. True parallelism requires `.map()` at the
flow level, which submits each item to the `ThreadPoolExecutor`.

## Asyncio Bridge

Prefect 3.x tasks use `asyncio.run()` to bridge from sync tasks to async
workflow classes like `ArchiveDownloadWorkflow` and `GapFillWorkflow`. This
is safe on all Python 3.x versions including 3.14 — `asyncio.run()` explicitly
creates a new event loop via `Runner` and does not depend on the main thread's
event loop.

## DLQ Pattern

The Dead Letter Queue (`_route_to_dlq`) records sink failures to a DuckDB
`dlq` table. It uses parameterized queries (`?` placeholders) for safety and
proper `try/finally` for connection cleanup. If the DuckLake catalog has not
been initialized (`metadata.ducklake` missing), errors are logged as a warning
rather than silently dropped.
