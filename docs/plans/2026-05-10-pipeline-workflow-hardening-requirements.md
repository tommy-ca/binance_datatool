---
date: 2026-05-10
topic: pipeline-workflow-hardening
---

# Pipeline Workflow Hardening

## Problem Frame
The Prefect pipeline (`historical_pipeline`, `bulk_backfill`) was built incrementally across multiple phases. A comprehensive audit found 50+ issues spanning resource leaks, result propagation bugs, silent failure masking, race conditions, concurrency guard gaps, deployment registration dead code, and zero test coverage for sink/catalog/health modules.

## Requirements

**R1. Fix result propagation bugs** — `download_archive` checks wrong attribute (`to_download` vs `downloaded`), `health_flow` returns `missing_dates=0` always, and `prepare_symbol` discards download/verify return values.

**R2. Fix resource leaks** — `_route_to_dlq` skips `con.close()` on exception. Use `try/finally` everywhere.

**R3. Fix configuration masking** — Replace `DataType._value2member_map_` private API with `try/except ValueError` so unknown data types raise instead of silently defaulting to `klines`.

**R4. Isolate per-symbol failures** — `historical_pipeline` aborts entirely when one symbol fails in `prepare_symbol.map()`. Wrap each symbol in `try/except` and collect partial results so N-1 symbols complete.

**R5. Fix deployment registration** — `__main__.serve()` blocks on first `.serve()` call; second cron deployment is dead code. Use `serve_multiple()` or `serve(flows=[...])`.

**R6. Add test coverage** — Zero tests exist for `sink.py`, `catalog.py`, `health_check.py`. Add unit tests for at least the DuckLake ingestion path and anomaly detection.

**R7. Guard metadata writes** — `refresh_metadata_flow` writes to `venues`/`symbols` without the `ducklake-writer` concurrency guard, risking races with `sink_silver`.

## Success Criteria
- All lint/format/tests pass (existing 249 + new tests)
- `download_archive` returns correct count of downloaded files
- `health_flow` returns accurate `missing_dates` from anomaly report
- Unknown data type raises `ValueError` instead of silently switching to `klines`
- A single symbol failure does not abort the pipeline for other symbols
- Both cron deployments register via `serve_multiple()`

## Scope Boundaries
- **Out of scope**: Python 3.14+ `asyncio.run()` thread safety (requires structural refactor in follow-up)
- **Out of scope**: SQL injection hardening in `health_check.py` (CLI-only tool, parameterized queries deferred)
- **Out of scope**: `sink.py` substring symbol path parsing (requires sym ordering fix — tracked separately)
- **Out of scope**: missing docs/ updated with the above data and code flows. separate commit.

## Key Decisions
- Use `try/except ValueError` for DataType construction (Pythonic, no private API, matches dataskew best practices)
- Use `prefect.serve()` for deployment registration (Prefect 3.x native API, non-blocking)
- Use `future.result(raise_on_failure=False)` + `future.state.is_completed()` for Prefect-native error isolation (instead of `try/except`)
- Use `zip(sym_list, futures, strict=True)` to pair inputs with futures so the symbol is known even on failure
- Remove nested `ThreadPoolTaskRunner` from `bulk_backfill` — subflow delegates to `historical_pipeline` which owns the parallelism
- Use Prefect `concurrency` context manager for DuckDB write serialization
- `refresh_metadata_flow` also uses `ducklake-writer` concurrency guard to prevent races with `sink_silver`
- `download_flow`/`verify_flow` use `.map()` with `ThreadPoolTaskRunner(4)` for parallel multi-symbol downloads
- Use `asyncio.run()` inside sync tasks for async bridging (Prefect 3.x recommended pattern; safe on Python 3.14 per testing)
- In-task task calls (`prepare_symbol` calling sub-tasks) create properly tracked `TaskRun` objects via the full task engine — Prefect-native and correct
- Use `_route_to_dlq` with proper `try/finally` and warning log when catalog absent (no silent error dropping)
- `health_check.py` outlier exception logged as warning instead of bare `except Exception: pass`
- `sink.py` `_parse_symbol_from_path` uses `path.name.startswith(f"{sym}-")` instead of substring matching (fixes order-dependent bug)
- `bulk_backfill` accepts `max_symbols` parameter (no hardcoded `[:10]`)

## Dependencies / Assumptions
- Python 3.11 — `asyncio.run()` from threads is safe; Python 3.14 upgrade will require changes
- Prefect 3.7+ — `serve_multiple()` confirmed available; `concurrency` context managers stable
