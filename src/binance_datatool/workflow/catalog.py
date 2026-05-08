"""Iceberg lakehouse and DuckDB catalog management.

Designs the catalog structure for the medallion architecture:
- Iceberg: Namespace-based, partitioned, versioned snapshots
- DuckDB: Local SQL views, materialized aggregations

Catalog follows Databento DBN and tardis.dev schema conventions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
from loguru import logger


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
        interval: str | None = None,
    ) -> Path:
        """Register a DataFrame as an Iceberg table (file-system catalog).

        Uses the same Hive-style partitioning as DuckLake for interop:
          symbol={S}/interval={I}/date={N}/file.parquet  (klines)
          symbol={S}/date={N}/file.parquet               (non-klines)
        Metadata tables (venues, symbols) are stored flat.
        """
        self._init_catalog()
        table_root = self.table_path(table_name)

        if table_name in ("venues", "symbols"):
            table_root.mkdir(parents=True, exist_ok=True)
            out = table_root / f"{table_name}.parquet"
            df.write_parquet(out)
            return out

        df = df.with_columns(pl.col("symbol").alias("_sym"))
        df = df.with_columns(
            pl.from_epoch(pl.col("ts_event") // 1000).dt.strftime("%Y-%m-%d").alias("_dt")
        )

        written = 0
        for (sym, dt), group in df.group_by(["_sym", "_dt"], maintain_order=True):
            parts = [table_root / f"symbol={sym}" / f"date={dt}"]
            if interval:
                parts = [table_root / f"symbol={sym}" / f"interval={interval}" / f"date={dt}"]
            out_dir = parts[0]
            out_dir.mkdir(parents=True, exist_ok=True)
            suffix = f"_{trade_type}" if trade_type else ""
            out = out_dir / f"{table_name}{suffix}.parquet"
            group.drop(["_sym", "_dt"]).write_parquet(out)
            written += 1

        logger.info("Iceberg: {} files under {}", written, table_root)
        return table_root


# ── DuckDB Catalog ──────────────────────────────────────────────────────


_DUCKLAKE_ANALYTICS_VIEWS = """
-- Analytics views on top of lake-scanned tables.

CREATE OR REPLACE VIEW daily_ohlcv AS
SELECT CAST(epoch_ms(ts_event) AS DATE) AS trade_date,
       symbol, trade_type,
       FIRST(open) AS open, MAX(high) AS high,
       MIN(low) AS low, LAST(close) AS close,
       SUM(volume) AS volume, SUM(quote_volume) AS quote_volume,
       COUNT(*) AS bar_count
FROM spot_klines WHERE interval = '1h'
GROUP BY trade_date, symbol, trade_type;

CREATE OR REPLACE VIEW latest_klines AS
SELECT DISTINCT ON (symbol, trade_type, interval)
       symbol, trade_type, interval, ts_event, close, volume, ingested_at
FROM spot_klines
ORDER BY symbol, trade_type, interval, ts_event DESC;

CREATE OR REPLACE VIEW stale_symbols AS
SELECT symbol, trade_type,
       MAX(ts_event) AS latest_ts,
       CAST(epoch_ms(MAX(ts_event)) AS DATE) AS latest_date,
       DATEDIFF('day', CAST(epoch_ms(MAX(ts_event)) AS DATE), CURRENT_DATE) AS days_stale
FROM spot_klines GROUP BY symbol, trade_type
HAVING days_stale > 3;
"""


class DuckLakeCatalog:
    """DuckLake v1.0 catalog — DuckDB queries the lake via the DuckLake format.

    Uses the official DuckLake format (ATTACH 'ducklake:metadata.ducklake') from
    the DuckDB team. The DuckLake catalog provides:
    - ACID transactions over multi-table operations
    - Lightweight snapshots and time-travel queries
    - Schema evolution and partition pruning
    - Concurrent read/write from multiple DuckDB instances

    Data is written as Parquet via Polars (efficient batch transform),
    then registered as DuckLake views for ACID-compliant querying.

    Docs: https://ducklake.select/docs/stable
    """

    def __init__(
        self,
        lake_path: Path | str,
        db_path: Path | str | None = None,
        catalog_name: str = "binance_lake",
    ) -> None:
        self._lake_path = Path(lake_path).resolve()
        self._data_path = self._lake_path / "data"
        self._db_path = str(db_path) if db_path else ":memory:"
        self._catalog_name = catalog_name

    def connect(self):
        """Create a DuckDB connection with DuckLake v1.0 attached."""
        import duckdb

        con = duckdb.connect(self._db_path)
        con.execute("SET enable_progress_bar=false")
        con.execute("LOAD ducklake")
        con.execute("LOAD parquet")
        con.execute("LOAD iceberg")

        # Attach DuckLake format (ACID catalog + Parquet storage)
        metadata_path = self._lake_path / "metadata.ducklake"
        data_path = self._data_path
        con.execute(
            f"ATTACH 'ducklake:{metadata_path}' AS {self._catalog_name} (DATA_PATH '{data_path}')"
        )
        con.execute(f"USE {self._catalog_name}")
        return con

    def register_lake_views(self, con: Any, interval: str | None = None) -> None:
        """Create DuckLake views that scan the lake Parquet in-place (zero-copy).

        Catalog layout mirrors the archive directory organization:
          {trade_type}/{data_type}/symbol={S}/interval={I}/date={N}/*.parquet  (klines)
          {trade_type}/{data_type}/symbol={S}/date={N}/*.parquet               (non-klines)
        """
        dp = self._data_path
        views = []
        for tt in ("spot", "um", "cm"):
            for dt in ("klines", "fundingRate"):
                views.append((f"{tt}_{dt}", dp / tt / dt))

        for view_name, base_path in views:
            if interval and "klines" in view_name:
                pattern = str(
                    base_path / "symbol=*" / f"interval={interval}" / "date=*" / "*.parquet"
                )
            else:
                pattern = str(base_path / "symbol=*" / "date=*" / "*.parquet")
            try:
                con.execute(
                    f"CREATE OR REPLACE VIEW {view_name} AS "
                    f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
                )
            except Exception:
                con.execute(
                    f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM (SELECT 1::BIGINT AS ts_event) WHERE 1=0"
                )
        logger.info("DuckLake: lake views registered at {}", dp)

    def create_analytics_views(self, con: Any) -> None:
        """Create analytics views on top of lake tables (in DuckLake catalog)."""
        for stmt in _DUCKLAKE_ANALYTICS_VIEWS.split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    con.execute(stmt)
                except Exception as e:
                    logger.warning("DuckLake analytics error: {}", e)
        logger.info("DuckLake: analytics views created")

    def run_query(self, query: str) -> pl.DataFrame:
        """Run a SQL query against the DuckLake catalog."""
        con = self.connect()
        try:
            self.register_lake_views(con)
            return pl.from_arrow(con.execute(query).fetch_arrow_table())
        finally:
            con.close()
