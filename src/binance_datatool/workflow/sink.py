"""Transform archive data to Silver layer (Parquet/DuckDB/Iceberg).

Reads Bronze data (archive ZIP CSVs, filled CSVs), normalizes to Silver
schemas following Databento DBN and tardis.dev conventions, writes
partitioned Parquet, and loads into DuckDB/Iceberg.
"""

from __future__ import annotations

import csv
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import polars as pl
from loguru import logger

from binance_datatool.lineage import LineageEvent, LineageEventType
from binance_datatool.workflow.catalog import DuckLakeCatalog

if TYPE_CHECKING:
    from collections.abc import Sequence

    from binance_datatool.common import DataType, TradeType
    from binance_datatool.lineage import LineageTracker

_DEFAULT_CATALOG_PATH = "data/lake"

# Bronze kline columns as they appear in Binance archive CSV files (no header row)
_BRONZE_KLINE_COLS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]

_BRONZE_AGGT_COLS = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
]

_BRONZE_FUNDING_COLS = [
    "symbol",
    "funding_time",
    "funding_rate",
    "mark_price",
]

_BRONZE_COLS_BY_TYPE = {
    "klines": _BRONZE_KLINE_COLS,
    "aggTrades": _BRONZE_AGGT_COLS,
    "fundingRate": _BRONZE_FUNDING_COLS,
}

# Silver klines columns (normalized, Databento DBN + tardis.dev naming)
_SILVER_KLINE_COLS = [
    "ts_event",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
]

_BRONZE_TO_SILVER_KLINE = {
    "open_time": "ts_event",
    "count": "trade_count",
}

_SILVER_META_COLS = [
    "ts_recv",
    "source",
    "trade_type",
    "symbol",
    "interval",
    "data_type",
    "ingested_at",
]

_FULL_SILVER_KLINE_SCHEMA = {
    "ts_event": pl.Int64,
    "ts_recv": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "quote_volume": pl.Float64,
    "trade_count": pl.Int64,
    "taker_buy_volume": pl.Float64,
    "taker_buy_quote_volume": pl.Float64,
    "source": pl.Utf8,
    "exchange": pl.Utf8,
    "trade_type": pl.Utf8,
    "symbol": pl.Utf8,
    "interval": pl.Utf8,
    "data_type": pl.Utf8,
    "ingested_at": pl.Int64,
}


@dataclass
class SinkStats:
    """Statistics from a sink operation."""

    parquet_files: int = 0
    row_count: int = 0
    symbols: int = 0
    errors: list[str] = field(default_factory=list)


def _scan_bronze_files(
    archive_home: Path,
    trade_type: TradeType,
    data_type: str,
    symbols: Sequence[str],
    interval: str | None = None,
) -> list[Path]:
    """Scan Bronze archive for CSV/ZIP files."""
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
    return next(csv.reader([line]))


def _read_zip_csv(path: Path, bronze_cols: list[str] | None = None) -> pl.DataFrame:
    """Read CSV from a Binance archive ZIP file.

    Binance archive CSVs have no header row — the first line is data.
    Uses the provided ``bronze_cols`` schema, or falls back to the first
    data line for backward compatibility.
    """
    with zipfile.ZipFile(path) as z:
        csv_files = [n for n in z.namelist() if n.endswith(".csv")]
        if not csv_files:
            return pl.DataFrame()
        with z.open(csv_files[0]) as f:
            content = f.read().decode("utf-8")
    lines = content.strip().split("\n")
    if len(lines) < 1:
        return pl.DataFrame()
    schema = bronze_cols or _parse_csv_line(lines[0])
    rows = [_parse_csv_line(line) for line in lines]
    return pl.DataFrame(rows, schema=schema, orient="row")


def _read_filled_csv(path: Path) -> pl.DataFrame:
    """Read a filled CSV file."""
    content = path.read_text().strip()
    lines = content.split("\n")
    if len(lines) < 2:
        return pl.DataFrame()
    header = _parse_csv_line(lines[0])
    rows = [_parse_csv_line(line) for line in lines[1:]]
    return pl.DataFrame(rows, schema=header, orient="row")


def _cast_columns(df: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Cast DataFrame columns to match target schema types."""
    casts = {}
    for col, dtype in schema.items():
        if col in df.columns:
            casts[col] = pl.col(col).cast(dtype, strict=False)
    if casts:
        df = df.with_columns(list(casts.values()))
    return df


def _rename_to_silver(df: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
    """Rename Bronze columns to Silver naming."""
    for old, new in mapping.items():
        if old in df.columns:
            df = df.rename({old: new})
    return df


def _exchange_for(trade_type: str) -> str:
    """Map trade_type to exchange name (tardis.dev convention).

    https://docs.tardis.dev/downloadable-csv-files/data-types
    tardis.dev exchange IDs: binance, binance-futures, binance-delivery
    """
    return {"spot": "binance", "um": "binance-futures", "cm": "binance-delivery"}.get(
        trade_type, "binance"
    )


def _add_silver_metadata(
    df: pl.DataFrame,
    trade_type: str,
    data_type: str,
    symbol: str,
    interval: str | None,
    source: str,
) -> pl.DataFrame:
    """Add Silver metadata columns."""
    now_us = int(time.time() * 1_000_000)
    exchange = _exchange_for(trade_type)
    df = df.with_columns(pl.lit(now_us).alias("ts_recv"))
    return df.with_columns(
        pl.lit(source).alias("source"),
        pl.lit(exchange).alias("exchange"),
        pl.lit(trade_type).alias("trade_type"),
        pl.lit(symbol).alias("symbol"),
        pl.lit(interval or "").alias("interval"),
        pl.lit(data_type).alias("data_type"),
        pl.lit(now_us).alias("ingested_at"),
    )


def _normalize_to_microseconds(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize ts_event to epoch microseconds.

    Binance archive has ms (pre-2024, 13-digit) and μs (2024+, 16-digit).
    Silver layer uses μs for forward compatibility.
    """
    if "ts_event" not in df.columns or len(df) == 0:
        return df
    max_ts = df.select(pl.col("ts_event").cast(pl.Int64, strict=False).max()).item()
    if max_ts is not None and max_ts < 1_000_000_000_000_000:
        df = df.with_columns(
            (pl.col("ts_event").cast(pl.Int64, strict=False) * 1000).alias("ts_event")
        )
    elif max_ts is not None:
        df = df.with_columns(pl.col("ts_event").cast(pl.Int64, strict=False).alias("ts_event"))
    return df


def _bronze_kline_to_silver(df: pl.DataFrame, source: str) -> pl.DataFrame:
    """Transform Bronze klines CSV to Silver schema."""
    df = _rename_to_silver(df, _BRONZE_TO_SILVER_KLINE)
    df = _normalize_to_microseconds(df)
    # Keep only Silver columns that exist in data
    keep = [c for c in _SILVER_KLINE_COLS if c in df.columns]
    df = df.select(keep)
    df = _cast_columns(df, _FULL_SILVER_KLINE_SCHEMA)
    return df


def _bronze_agg_trades_to_silver(df: pl.DataFrame, source: str) -> pl.DataFrame:
    """Transform Bronze aggTrades CSV to Silver trades schema.

    Binance aggTrades archive CSV fields:
      agg_trade_id, price, quantity, first_trade_id,
      last_trade_id, transact_time, is_buyer_maker

    tardis.dev normalized trades: side = liquidity taker.
    Binance is_buyer_maker: 1=buyer is maker → seller is taker → side="sell"
    """
    rename_map = {
        "agg_trade_id": "trade_id",
        "price": "price",
        "quantity": "size",
        "transact_time": "ts_event",
    }
    df = _rename_to_silver(df, rename_map)
    df = _normalize_to_microseconds(df)
    keep = [
        c for c in ["ts_event", "price", "size", "trade_id", "is_buyer_maker"] if c in df.columns
    ]
    df = df.select(keep)
    # Derive tardis.dev side from Binance is_buyer_maker
    # Archive CSV has is_buyer_maker as string "1"/"0"; cast to int first
    # is_buyer_maker=1 → buyer is maker → seller is taker → side="sell"
    # is_buyer_maker=0 → seller is maker → buyer is taker → side="buy"
    df = df.with_columns(pl.col("is_buyer_maker").cast(pl.Int64, strict=False))
    df = df.with_columns(
        pl.when(pl.col("is_buyer_maker") == 1)
        .then(pl.lit("sell"))
        .when(pl.col("is_buyer_maker") == 0)
        .then(pl.lit("buy"))
        .otherwise(pl.lit(None, pl.Utf8))
        .alias("side"),
    )
    # preserve original agg_trade_id (archive has it; renamed to trade_id above)
    df = df.with_columns(pl.col("trade_id").alias("agg_trade_id"))
    return df.with_columns(pl.lit("agg").alias("rtype"))


def _bronze_funding_rate_to_silver(df: pl.DataFrame, source: str) -> pl.DataFrame:
    """Transform Bronze fundingRate CSV to Silver schema.

    Maps Binance archive fundingRate CSV to our Silver schema.
    Binance archive CSV: symbol, funding_time, funding_rate, mark_price
    tardis.dev derivative_ticker: timestamp, funding_timestamp, funding_rate, mark_price, ...
    """
    rename_map = {"funding_time": "ts_event"}
    df = _rename_to_silver(df, rename_map)
    df = _normalize_to_microseconds(df)
    # Map funding_time as both ts_event (for sorting) and funding_timestamp
    keep = [c for c in ["ts_event", "funding_rate", "mark_price"] if c in df.columns]
    df = df.select(keep)
    df = _cast_columns(
        df,
        {
            "ts_event": pl.Int64,
            "funding_rate": pl.Float64,
            "mark_price": pl.Float64,
        },
    )
    # tardis.dev: funding_timestamp is the next funding event time
    # Binance archive: funding_time is the funding event timestamp
    if "ts_event" in df.columns:
        df = df.with_columns(pl.col("ts_event").alias("funding_timestamp"))
    return df


def _bronze_to_silver(
    df: pl.DataFrame,
    data_type: str,
    source: str,
) -> pl.DataFrame:
    """Dispatch Bronze→Silver transform by data type."""
    if data_type == "klines":
        return _bronze_kline_to_silver(df, source)
    if data_type in ("aggTrades", "trades"):
        return _bronze_agg_trades_to_silver(df, source)
    if data_type == "fundingRate":
        return _bronze_funding_rate_to_silver(df, source)
    msg = f"Unknown data type: {data_type}"
    raise ValueError(msg)


def _parse_symbol_from_path(path: Path, known_symbols: Sequence[str]) -> str | None:
    name = path.name
    for sym in known_symbols:
        if name.startswith(f"{sym}-"):
            return sym
    return None


class SinkWorkflow:
    """Transform Bronze archive data to Silver layer (Parquet/DuckDB)."""

    def __init__(
        self,
        archive_home: Path,
        catalog_path: Path | None = None,
        duckdb_path: Path | None = None,
        tracker: LineageTracker | None = None,
    ) -> None:
        self._archive_home = Path(archive_home)
        self._catalog_path = catalog_path or Path(_DEFAULT_CATALOG_PATH)
        self._duckdb_path = duckdb_path
        self._tracker = tracker

    def transform(
        self,
        trade_type: TradeType,
        data_type: DataType,
        symbols: Sequence[str],
        interval: str | None = None,
        target: Literal["parquet", "duckdb", "all"] = "all",
    ) -> SinkStats:
        """Transform Bronze archive data to Silver layer."""
        stats = SinkStats()
        data_type_str = data_type.value
        trade_type_str = trade_type.value

        files = _scan_bronze_files(self._archive_home, trade_type, data_type_str, symbols, interval)
        if not files:
            logger.warning("No Bronze files found for {}/{}", trade_type_str, data_type_str)
            return stats

        seen_symbols: set[str] = set()
        all_dfs: list[pl.DataFrame] = []

        for path in files:
            try:
                source = "api_filled" if "_filled" in str(path.parent) else "archive"
                df = (
                    _read_zip_csv(path, bronze_cols=_BRONZE_COLS_BY_TYPE.get(data_type_str))
                    if path.suffix == ".zip"
                    else _read_filled_csv(path)
                )
                if df.is_empty():
                    continue

                symbol = _parse_symbol_from_path(path, symbols)
                if symbol is None:
                    continue

                seen_symbols.add(symbol)
                silver_df = _bronze_to_silver(df, data_type_str, source)
                silver_df = _add_silver_metadata(
                    silver_df, trade_type_str, data_type_str, symbol, interval, source
                )
                all_dfs.append(silver_df)
                stats.row_count += len(silver_df)

            except Exception as e:
                logger.error("Failed to transform {}: {}", path, e)
                stats.errors.append(f"{path.name}: {e}")

        if not all_dfs:
            return stats

        combined = pl.concat(all_dfs, how="diagonal")

        # DuckLake native ingestion — handles partitioning and file management
        stats.parquet_files = self._write_ducklake(
            combined, trade_type_str, data_type_str, interval
        )

        stats.symbols = len(seen_symbols)

        # Record lineage for each symbol
        if self._tracker:
            now = datetime.now()
            for symbol in seen_symbols:
                self._tracker.record(
                    LineageEvent(
                        source=f"binance_{trade_type_str}",
                        symbol=symbol,
                        event_type=LineageEventType.SUNK,
                        timestamp=now,
                        date=None,
                        message=f"Sunk {data_type_str} data to DuckLake ({len(combined)} total rows)",
                        metadata={
                            "data_type": data_type_str,
                            "trade_type": trade_type_str,
                            "interval": interval or "",
                            "row_count": len(combined),
                            "symbols": list(seen_symbols),
                        },
                    )
                )
            self._tracker.save_ducklake(
                str(self._duckdb_path) if self._duckdb_path else ":memory:",
                str(self._catalog_path) if self._catalog_path else None,
            )

        return stats

    def _write_ducklake(
        self,
        df: pl.DataFrame,
        trade_type: str,
        data_type: str,
        interval: str | None = None,
    ) -> int:
        """Write Silver DataFrame to DuckLake native table.

        DuckLake manages Parquet storage, partitioning, and ACID tracking.
        No manual Hive paths — DuckDB handles file placement.
        """
        table_name = data_type.replace("-", "_")
        catalog = DuckLakeCatalog(
            lake_path=self._catalog_path,
            db_path=self._duckdb_path,
        )
        con = catalog.connect()
        try:
            written = catalog.ingest_dataframe(con, table_name, df)
        finally:
            con.close()
        return written
