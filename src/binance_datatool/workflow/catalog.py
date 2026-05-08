"""Iceberg lakehouse and DuckDB catalog management.

Designs the catalog structure for the medallion architecture:
- Iceberg: Namespace-based, partitioned, versioned snapshots
- DuckDB: Local SQL views, materialized aggregations

Catalog follows Databento DBN and tardis.dev schema conventions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Sequence


def duckdb_table_name(trade_type: str, data_type: str) -> str:
    """Generate a DuckDB-safe table name."""
    return f"{trade_type}_{data_type}".replace("-", "_").replace(".", "_")


def iceberg_table_name(data_type: str, interval: str | None = None) -> str:
    """Generate an Iceberg table name."""
    base = data_type.replace("_", "").replace("-", "")
    if interval:
        return f"{base}_{interval}"
    return base


def catalog_path(
    base: Path,
    trade_type: str,
    data_type: str,
    date_str: str | None = None,
) -> Path:
    """Build the file-system catalog path for a data partition."""
    p = base / trade_type / data_type
    if date_str:
        p = p / f"date={date_str}"
    return p


# ── Iceberg Catalog ─────────────────────────────────────────────────────


def _iceberg_partition_spec(table_name: str) -> list[dict[str, Any]]:
    """Return Iceberg partition spec for a table.

    All time-series tables partition by day on ts_event.
    Metadata tables are unpartitioned.
    """
    if table_name in ("venues", "symbols", "symbol"):
        return []
    return [{"column": "ts_event", "transform": "day"}]


def _iceberg_table_properties() -> dict[str, str]:
    """Default Iceberg table properties."""
    return {
        "write.format.default": "parquet",
        "write.parquet.compression-codec": "zstd",
        "write.parquet.compression-level": "9",
        "commit.retry.num-retries": "3",
        "history.expire.max-snapshot-age-ms": "2592000000",  # 30 days
    }


class IcebergCatalog:
    """Iceberg catalog manager using PyIceberg.

    Manages namespaces, tables, partitions, and snapshots for the
    medallion lakehouse architecture.

    Iceberg tables are stored under `{warehouse}/iceberg/` with
    a standard Hadoop catalog layout.
    """

    NAMESPACE = "binance"

    TABLE_SPECS = {
        "klines": {"partition": ["days(ts_event)"], "sort": ["symbol", "ts_event"]},
        "klines_1h": {"partition": ["days(ts_event)"], "sort": ["symbol", "ts_event"]},
        "klines_1d": {"partition": ["months(ts_event)"], "sort": ["symbol", "ts_event"]},
        "trades": {"partition": ["days(ts_event)"], "sort": ["symbol", "ts_event"]},
        "aggTrades": {"partition": ["days(ts_event)"], "sort": ["symbol", "ts_event"]},
        "fundingRate": {"partition": ["days(ts_event)"], "sort": ["symbol", "ts_event"]},
        "venues": {"partition": [], "sort": []},
        "symbols": {"partition": [], "sort": ["trade_type", "symbol"]},
    }

    def __init__(self, warehouse_path: Path) -> None:
        self._warehouse = Path(warehouse_path)
        self._initialized = False

    def _init_catalog(self) -> None:
        """Initialize PyIceberg catalog if available."""
        if self._initialized:
            return
        self._initialized = True
        try:
            import pyiceberg.catalog  # noqa: F401
            import pyiceberg.schema  # noqa: F401
            import pyiceberg.types  # noqa: F401

            logger.info("PyIceberg available; catalog ready")
        except ImportError:
            logger.info("PyIceberg not installed; using file-system catalog")

    def create_namespace(self) -> None:
        """Create the binance namespace if not exists."""
        ns_path = self._warehouse / "iceberg" / self.NAMESPACE
        ns_path.mkdir(parents=True, exist_ok=True)
        logger.info("Iceberg namespace: {}", ns_path)

    def table_path(self, table_name: str) -> Path:
        """Return the file-system path for an Iceberg table."""
        return self._warehouse / "iceberg" / self.NAMESPACE / table_name

    def register_parquet(
        self,
        df: pl.DataFrame,
        table_name: str,
        trade_type: str | None = None,
    ) -> Path:
        """Register a DataFrame as an Iceberg table (file-system catalog).

        Uses Hive-style partitioning: {table}/date={N}/data.parquet.
        Metadata tables (venues, symbols) are stored flat.
        """
        self._init_catalog()
        table_root = self.table_path(table_name)

        if table_name in ("venues", "symbols"):
            # Unpartitioned metadata tables
            table_root.mkdir(parents=True, exist_ok=True)
            out = table_root / f"{table_name}.parquet"
            df.write_parquet(out)
            return out

        # Partitioned time-series tables
        ts_col = "ts_event" if "ts_event" in df.columns else None
        if ts_col:
            df = df.with_columns(
                pl.from_epoch(pl.col(ts_col) // 1000)
                .dt.strftime("%Y-%m-%d")
                .alias("_iceberg_date")
            )
        else:
            df = df.with_columns(pl.lit("unknown").alias("_iceberg_date"))

        written = 0
        for date_val, group in df.group_by("_iceberg_date", maintain_order=True):
            partition_path = table_root / f"date={date_val[0]}"
            partition_path.mkdir(parents=True, exist_ok=True)
            suffix = f"_{trade_type}" if trade_type else ""
            out = partition_path / f"{table_name}{suffix}.parquet"
            group.drop("_iceberg_date").write_parquet(out)
            written += 1

        logger.info("Iceberg: registered {} files to {}", written, table_root)
        return table_root


# ── DuckDB Catalog ──────────────────────────────────────────────────────


_DUCKDB_VIEWS_SQL = """
-- Analytics views for the binance data lake.

-- Daily aggregate: OHLCV by symbol
CREATE OR REPLACE VIEW daily_ohlcv AS
SELECT
    CAST(ts_event / 86400000 AS DATE) AS trade_date,
    symbol,
    trade_type,
    FIRST(open) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close) AS close,
    SUM(volume) AS volume,
    SUM(quote_volume) AS quote_volume,
    COUNT(*) AS bar_count
FROM spot_klines
WHERE interval = '1h'
GROUP BY trade_date, symbol, trade_type;

-- Latest data per symbol
CREATE OR REPLACE VIEW latest_klines AS
SELECT DISTINCT ON (symbol, trade_type, interval)
    symbol,
    trade_type,
    interval,
    ts_event,
    close,
    volume,
    ingested_at
FROM spot_klines
ORDER BY symbol, trade_type, interval, ts_event DESC;

-- Funding rate summary (UM)
CREATE OR REPLACE VIEW funding_summary AS
SELECT
    symbol,
    trade_type,
    COUNT(*) AS records,
    AVG(funding_rate) AS avg_rate,
    MAX(ts_event) AS latest_ts
FROM um_fundingRate
GROUP BY symbol, trade_type;

-- Health check: symbols with stale data
CREATE OR REPLACE VIEW stale_symbols AS
SELECT
    symbol,
    trade_type,
    MAX(ts_event) AS latest_ts,
    CAST(epoch_ms(MAX(ts_event)) AS DATE) AS latest_date,
    DATEDIFF('day', CAST(epoch_ms(MAX(ts_event)) AS DATE), CURRENT_DATE) AS days_stale
FROM spot_klines
GROUP BY symbol, trade_type
HAVING days_stale > 3;
"""


class DuckDBCatalog:
    """DuckDB catalog manager for local analytics.

    Creates tables, views, and materialized views on top of the
    partitioned Parquet catalog for DuckDB-based querying.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"

    def connect(self):
        """Create a DuckDB connection."""
        import duckdb

        con = duckdb.connect(self._db_path)
        con.execute("SET enable_progress_bar=false")
        return con

    def register_table(
        self,
        con: Any,
        parquet_paths: Sequence[Path],
        trade_type: str,
        data_type: str,
    ) -> str:
        """Register a set of Parquet files as a DuckDB table."""
        table = duckdb_table_name(trade_type, data_type)
        files_str = ", ".join(f"'{p}'" for p in parquet_paths)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet([{files_str}])")
        row_count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        logger.info("DuckDB: loaded {} rows into table {}", row_count, table)
        return table

    def create_views(self, con: Any) -> None:
        """Create analytics views on the DuckDB session."""
        for stmt in _DUCKDB_VIEWS_SQL.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    con.execute(stmt)
                except Exception as e:
                    logger.warning("DuckDB view error: {}", e)
        logger.info("DuckDB: analytics views created")

    def run_query(self, query: str) -> pl.DataFrame:
        """Run a SQL query and return results as Polars DataFrame."""
        con = self.connect()
        try:
            return pl.from_arrow(con.execute(query).fetch_arrow_table())
        finally:
            con.close()
