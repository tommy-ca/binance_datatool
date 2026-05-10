---
date: 2026-05-09
topic: ducklake-schema-audit-plan
---

# DuckLake Schema Audit: Findings and Resolution Plan

## Issues Found

### I1: `rtype` defined but never produced

**Severity**: Low
**Files affected**: `workflow/sink.py`, `workflow/catalog.py`, `common/types.py`, `docs/silver-layer-spec.md`

**Description**: `SilverTrade` dataclass defines `rtype: str` ("trade" or "agg"),
the docs document it, but neither the Bronze→Silver transform (`_bronze_agg_trades_to_silver`)
nor the DuckLake table definitions include it.

**Fix**: Add `rtype` column to:
1. `_bronze_agg_trades_to_silver()` output → `pl.lit("agg").alias("rtype")`
2. `DuckLakeCatalog.TABLE_DEFS["spot/um/cm_aggTrades"]` → add `rtype VARCHAR`

---

### I2: `is_buyer_maker` type mismatch

**Severity**: Low
**Files affected**: `workflow/catalog.py`, `common/types.py`

**Description**: `SilverTrade` dataclass has `is_buyer_maker: int | None`,
DuckLake table defines it as `TINYINT`. DuckDB TINYINT supports NULL,
but `int | None` is wider than `TINYINT`.

**Fix**: Either change DuckLake to `BIGINT` (wider, matches Python) or change
SilverTrade to use `int` (strict, no None). Prefer `BIGINT` for safety.

---

### I3: Missing `trades` (raw) table definitions

**Severity**: Medium
**Files affected**: `workflow/catalog.py`

**Description**: Only `klines`, `aggTrades`, and `fundingRate` have DuckLake table
definitions. Raw `trades` data type is not supported by DuckLake.

**Fix**: Add `spot/um/cm_trades` TABLE_DEFS when the `trades` data type is
implemented in the pipeline. Deferred to Phase 8.

---

### I4: No type-level check between Silver dataclass and DuckLake table

**Severity**: Low
**Files affected**: `workflow/catalog.py` (new validation method)

**Description**: There is no automated test ensuring `TABLE_DEFS` column types
match `Silver*` dataclass field types. Manual audit required.

**Fix**: Add a `validate_schema()` method to `DuckLakeCatalog` that reads
the `SilverKline`, `SilverTrade`, `SilverFundingRate` dataclasses and
checks they match `TABLE_DEFS` column types.

---

## Resolution

| Issue | Effort | Priority | Action |
|-------|--------|----------|--------|
| I1: rtype missing | 15 min | High | Fix now (docs vs code gap) |
| I2: TINYINT vs BIGINT | 5 min | Low | Change DuckLake to BIGINT |
| I3: trades tables | - | Future | Defer to Phase 8 |
| I4: validation test | 30 min | Medium | Add test in next sprint |

## Next Steps

1. Fix I1 and I2 immediately (this session)
2. Add I4 as a TODO in the test file
3. Defer I3 to Phase 8

---
**Status**: Complete — implementation merged to main on 2026-05-10.
