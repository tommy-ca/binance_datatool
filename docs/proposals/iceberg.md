## Iceberg Catalog Design

### Namespace
- **Namespace**: `binance` (Hadoop catalog: `{warehouse}/iceberg/binance/`)

### Tables
| Table | Partition By | Sort Order | Compress |
|-------|-------------|------------|----------|
| `klines` | `symbol, interval` | `symbol, interval, ts_event` | zstd |
| `aggTrades` | `symbol` | `symbol, ts_event` | zstd |
| `fundingRate` | `symbol` | `symbol, ts_event` | zstd |

The `ts_event` column is BIGINT epoch ms (not TIMESTAMP). A `ts_date DATE`
column is populated at DuckLake ingest time via `CAST(epoch_ms(ts_event) AS DATE)`,
enabling DuckLake's native DATE partition transforms for efficient date pruning.

## Type Mapping: DuckDB/DuckLake ↔ Parquet

All DuckDB column types map cleanly to Parquet physical types:

| DuckDB | Parquet Physical | Arrow/Iceberg Logical | Used In |
|--------|-----------------|----------------------|---------|
| `BIGINT` | `int64` | `long` | `ts_event`, `ts_recv`, `trade_count`, `ingested_at` |
| `DOUBLE` | `double` | `double` | `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `taker_buy_*` |
| `VARCHAR` | `large_string` (UTF8) | `string` | `source`, `exchange`, `trade_type`, `symbol`, `interval`, `data_type` |
| `DATE` | `date32` | `date` | `ts_date` (computed at DuckLake ingest, not in Parquet Silver files) |
| `BOOLEAN` | `bool` | `boolean` | `is_leverage`, `is_stable_pair` (symbols table only) |

No type conversion needed — DuckDB reads Parquet directly with zero-copy type matching.
| `venues` | Unpartitioned | — | zstd |
| `symbols` | Unpartitioned | `trade_type, symbol` | zstd |

### Table Properties
```json
{
    "write.format.default": "parquet",
    "write.parquet.compression-codec": "zstd",
    "write.parquet.compression-level": "9",
    "commit.retry.num-retries": "3",
    "history.expire.max-snapshot-age-ms": "2592000000"
}
```
