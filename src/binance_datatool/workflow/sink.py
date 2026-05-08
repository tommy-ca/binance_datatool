"""Transform and load archive data to Parquet/DuckDB/Iceberg.

Reads raw archive data (ZIP CSVs and filled CSVs), normalizes schemas,
writes partitioned Parquet files, and loads into DuckDB for analytics.
"""

from __future__ import annotations

import csv
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import polars as pl
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from binance_datatool.common import DataType, TradeType

_DEFAULT_CATALOG_PATH = "data/lake"


@dataclass
class SinkStats:
    """Statistics from a sink operation."""

    parquet_files: int = 0
    row_count: int = 0
    symbols: int = 0
    errors: list[str] = field(default_factory=list)


_SCHEMA_KLINE = {
    "open_time": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "close_time": pl.Int64,
    "quote_volume": pl.Float64,
    "count": pl.Int64,
    "taker_buy_volume": pl.Float64,
    "taker_buy_quote_volume": pl.Float64,
    "ignore": pl.Utf8,
}

_SCHEMA_AGGR_TRADES = {
    "agg_trade_id": pl.Int64,
    "price": pl.Float64,
    "quantity": pl.Float64,
    "first_trade_id": pl.Int64,
    "last_trade_id": pl.Int64,
    "transact_time": pl.Int64,
    "is_buyer_maker": pl.Int8,
}

_SCHEMA_FUNDING_RATE = {
    "symbol": pl.Utf8,
    "funding_time": pl.Int64,
    "funding_rate": pl.Float64,
    "mark_price": pl.Float64,
}


def _schema_for(data_type: str) -> dict[str, pl.DataType]:
    if data_type == "klines":
        return dict(_SCHEMA_KLINE)
    if data_type == "aggTrades":
        return dict(_SCHEMA_AGGR_TRADES)
    if data_type == "fundingRate":
        return dict(_SCHEMA_FUNDING_RATE)
    msg = f"Unknown data type: {data_type}"
    raise ValueError(msg)


def _scan_files(
    archive_home: Path,
    trade_type: TradeType,
    data_type: str,
    symbols: Sequence[str],
    interval: str | None = None,
) -> list[Path]:
    """Scan archive for all CSV files (both ZIP entries and filled CSVs)."""
    files: list[Path] = []
    for symbol in symbols:
        base = archive_home / "data" / trade_type.s3_path / "daily" / data_type / symbol
        if interval:
            base = base / interval
        if not base.exists():
            continue
        for entry in sorted(base.iterdir()):
            if entry.suffix in (".zip", ".csv"):
                files.append(entry)
            elif entry.is_dir() and entry.name == "_filled":
                for f in sorted(entry.iterdir()):
                    if f.suffix == ".csv":
                        files.append(f)
    return files


def _parse_csv_line(line: str) -> list[str]:
    """Parse a single CSV line, handling quoted fields."""
    return next(csv.reader([line]))


def _read_zip_csv(path: Path) -> pl.DataFrame:
    """Read CSV content from a Binance archive ZIP file."""
    with zipfile.ZipFile(path) as z:
        csv_files = [n for n in z.namelist() if n.endswith(".csv")]
        if not csv_files:
            return pl.DataFrame()
        with z.open(csv_files[0]) as f:
            content = f.read().decode("utf-8")
    lines = content.strip().split("\n")
    if len(lines) < 2:
        return pl.DataFrame()
    header = _parse_csv_line(lines[0])
    rows = [_parse_csv_line(line) for line in lines[1:]]
    return pl.DataFrame(rows, schema=header, orient="row")


def _read_filled_csv(path: Path) -> pl.DataFrame:
    """Read a filled CSV file."""
    content = path.read_text().strip()
    lines = content.split("\n")
    if len(lines) < 2:
        return pl.DataFrame()
    header = _parse_csv_line(lines[0])
    rows = [_parse_csv_line(line) for line in lines[1:]]
    return pl.DataFrame(rows, schema=header, orient="row")


def _cast_schema(df: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Cast DataFrame columns to the target schema types."""
    casts = {}
    for col, dtype in schema.items():
        if col in df.columns:
            try:
                casts[col] = pl.col(col).cast(dtype)
            except Exception:
                casts[col] = pl.col(col).cast(pl.Utf8).cast(dtype)
    return df.with_columns(**casts)


def _add_metadata(
    df: pl.DataFrame,
    trade_type: str,
    data_type: str,
    symbol: str,
) -> pl.DataFrame:
    """Add source metadata columns."""
    return df.with_columns(
        pl.lit(trade_type).alias("trade_type"),
        pl.lit(data_type).alias("data_type"),
        pl.lit(symbol).alias("symbol"),
    )


class SinkWorkflow:
    """Transform archive data to Parquet and load into DuckDB/Iceberg."""

    def __init__(
        self,
        archive_home: Path,
        catalog_path: Path | None = None,
        duckdb_path: Path | None = None,
    ) -> None:
        self._archive_home = Path(archive_home)
        self._catalog_path = catalog_path or Path(_DEFAULT_CATALOG_PATH)
        self._duckdb_path = duckdb_path

    def transform(
        self,
        trade_type: TradeType,
        data_type: DataType,
        symbols: Sequence[str],
        interval: str | None = None,
        target: Literal["parquet", "duckdb", "all"] = "all",
    ) -> SinkStats:
        """Transform archive data for given symbols and load to target."""
        stats = SinkStats()
        schema = _schema_for(data_type.value)
        data_type_str = data_type.value
        trade_type_str = trade_type.value

        files = _scan_files(self._archive_home, trade_type, data_type_str, symbols, interval)
        if not files:
            logger.warning("No data files found for {}/{}", trade_type_str, data_type_str)
            return stats

        seen_symbols: set[str] = set()
        all_dfs: list[pl.DataFrame] = []

        for path in files:
            try:
                df = _read_zip_csv(path) if path.suffix == ".zip" else _read_filled_csv(path)

                if df.is_empty():
                    continue

                symbol = _parse_symbol_from_path(path, symbols)
                if symbol is None:
                    continue

                seen_symbols.add(symbol)
                df = _cast_schema(df, schema)
                df = _add_metadata(df, trade_type_str, data_type_str, symbol)
                all_dfs.append(df)
                stats.row_count += len(df)

            except Exception as e:
                logger.error("Failed to read {}: {}", path, e)
                stats.errors.append(f"{path.name}: {e}")

        if not all_dfs:
            return stats

        combined = pl.concat(all_dfs)

        if target in ("parquet", "all"):
            stats.parquet_files = self._write_parquet(combined, trade_type_str, data_type_str)

        if target in ("duckdb", "all") and self._duckdb_path:
            self._load_duckdb(combined, trade_type_str, data_type_str)

        stats.symbols = len(seen_symbols)
        return stats

    def _write_parquet(
        self,
        df: pl.DataFrame,
        trade_type: str,
        data_type: str,
    ) -> int:
        """Write DataFrame to partitioned Parquet files."""
        base = self._catalog_path / trade_type / data_type
        base.mkdir(parents=True, exist_ok=True)

        # Determine partition column
        if "open_time" in df.columns:
            df = df.with_columns(pl.from_epoch(pl.col("open_time") // 1000).alias("_date"))
            partition_col = pl.col("_date").dt.strftime("%Y-%m-%d").alias("date")
            df = df.with_columns(partition_col)
        elif "transact_time" in df.columns:
            df = df.with_columns(pl.from_epoch(pl.col("transact_time") // 1000).alias("_date"))
            partition_col = pl.col("_date").dt.strftime("%Y-%m-%d").alias("date")
            df = df.with_columns(partition_col)
        else:
            df = df.with_columns(pl.lit("unknown").alias("date"))

        file_count = 0
        for date_val, group in df.group_by("date", maintain_order=True):
            out_path = base / date_val[0] / f"{trade_type}_{data_type}.parquet"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            group.drop("_date").write_parquet(out_path)
            file_count += 1

        logger.info("Wrote {} parquet files to {}", file_count, base)
        return file_count

    def _load_duckdb(self, df: pl.DataFrame, trade_type: str, data_type: str) -> None:
        """Load DataFrame into DuckDB."""
        import duckdb

        table_name = f"{trade_type}_{data_type}".replace("-", "_")
        db_path = str(self._duckdb_path) if self._duckdb_path else ":memory:"

        con = duckdb.connect(db_path)
        try:
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")
            row_count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            logger.info("Loaded {} rows into DuckDB table {}", row_count, table_name)
        finally:
            con.close()


def _parse_symbol_from_path(path: Path, known_symbols: Sequence[str]) -> str | None:
    """Extract symbol from a path like .../BTCUSDT/1h/BTCUSDT-1h-2026-01-01.zip."""
    for sym in known_symbols:
        if sym in path.name or sym in str(path):
            return sym
    return None
