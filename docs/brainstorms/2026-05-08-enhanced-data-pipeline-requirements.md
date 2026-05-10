---
date: 2026-05-08
topic: enhanced-gap-fill-lineage-health
---

# Enhanced Gap Filling with Lineage, Health Check, and Data Sink

## Problem Frame
The current GapFillWorkflow requires manual start/end times. To be production-ready, it needs:
1. Auto-detection of gaps by scanning local archive
2. Lineage recording for every gap-fill operation
3. Health check to monitor data completeness and freshness
4. A clear plan for transforming normalized data into a queryable lake (Iceberg/DuckDB)

## Requirements

### R1: Auto Gap Detection
- Scan local archive directory for `.zip` and `.filled.csv` files
- Parse dates from filenames (`BTCUSDT-1h-YYYY-MM-DD.zip`)
- Determine min/max dates and identify missing date ranges
- Work across klines, aggTrades, fundingRate

### R2: Gap-Fill Lineage
- Record lineage event for each gap-fill operation
- Fields: symbol, data_type, interval, date_range, row_count, source (REST API)
- Use existing LineageTracker (export to JSON)

### R3: Health Check
- **Completeness**: Are all dates present for each symbol/data_type/interval?
- **Freshness**: When was the latest data ingested?
- **Integrity**: Do checksums verify for both `.zip` and `.filled.csv` files?
- Output: structured report with per-symbol health

### R4: Transform / Sink (Plan)
- Transform archive CSV data to columnar format (Parquet)
- Normalize schemas across data types and trade types
- Sink to DuckDB (local) and/or Iceberg (catalog)
- Support incremental loads (only new/changed data)

## Key Decisions
- **Single pass for gap detection**: Scan once, fill all gaps
- **Polars for transform**: Already available, ideal for columnar processing
- **DuckDB first**: Local analytics, then Iceberg for catalog-driven lakehouse
- **Lineage as JSON events**: File-based, no separate database needed

## Scope Boundaries
- Phase 1: Gap detection + lineage + health check (this sprint)
- Phase 2: Transform/normalize/load to DuckDB (next sprint)
- Phase 3: Iceberg catalog integration (future)
