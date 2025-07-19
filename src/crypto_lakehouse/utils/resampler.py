"""
Data resampling utilities for converting between different timeframes.

This module provides functionality to resample cryptocurrency data from
base intervals (e.g., 1m) to higher timeframes (e.g., 5m, 1h, 1d).
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Literal

import polars as pl
from pydantic import BaseModel, Field, validator

from ..core.models import KlineData

logger = logging.getLogger(__name__)

# Timeframe conversion mapping
TIMEFRAME_MAPPING = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
    "3d": "3d",
    "1w": "1w",
    "1M": "1mo",
}

# Supported resampling rules
SUPPORTED_TIMEFRAMES = list(TIMEFRAME_MAPPING.keys())


class ResamplingConfig(BaseModel):
    """Configuration for data resampling operations."""

    source_timeframe: str = Field(..., description="Source timeframe (e.g., '1m')")
    target_timeframe: str = Field(..., description="Target timeframe (e.g., '5m', '1h', '1d')")
    aggregation_method: Literal["ohlcv", "mean", "sum"] = Field(
        default="ohlcv", description="Aggregation method to use"
    )
    include_volume: bool = Field(default=True, description="Include volume data")
    include_trades: bool = Field(default=True, description="Include trade count data")
    validate_completeness: bool = Field(default=True, description="Validate data completeness")

    @validator("source_timeframe", "target_timeframe")
    def validate_timeframes(cls, v):
        if v not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {v}. Must be one of {SUPPORTED_TIMEFRAMES}")
        return v

    @validator("target_timeframe")
    def validate_target_greater_than_source(cls, v, values):
        if "source_timeframe" in values:
            source = values["source_timeframe"]
            # Simple validation - could be more sophisticated
            if source == v:
                raise ValueError("Target timeframe must be different from source timeframe")
        return v


class ResamplingResult(BaseModel):
    """Result of a resampling operation."""

    symbol: str
    source_timeframe: str
    target_timeframe: str
    source_records: int
    target_records: int
    start_time: datetime
    end_time: datetime
    completeness_ratio: float = Field(description="Ratio of complete periods")
    processing_time_ms: int


class DataResampler:
    """
    High-performance data resampler for cryptocurrency market data.

    Converts K-line data from base intervals to higher timeframes using
    proper OHLCV aggregation rules.
    """

    def __init__(self, config: ResamplingConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.DataResampler")

    def resample_klines(self, data: List[KlineData], symbol: str) -> ResamplingResult:
        """
        Resample K-line data to target timeframe.

        Args:
            data: List of K-line data records
            symbol: Trading symbol

        Returns:
            ResamplingResult with resampled data and metadata
        """
        start_time = datetime.now()

        if not data:
            raise ValueError("No data provided for resampling")

        # Convert to Polars DataFrame
        df = self._to_polars_df(data)

        # Perform resampling
        resampled_df = self._resample_ohlcv(df)

        # Convert back to KlineData objects
        resampled_data = self._from_polars_df(resampled_df, symbol)

        # Calculate metrics
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        completeness_ratio = self._calculate_completeness(df, resampled_df)

        return ResamplingResult(
            symbol=symbol,
            source_timeframe=self.config.source_timeframe,
            target_timeframe=self.config.target_timeframe,
            source_records=len(data),
            target_records=len(resampled_data),
            start_time=data[0].open_time,
            end_time=data[-1].close_time,
            completeness_ratio=completeness_ratio,
            processing_time_ms=processing_time,
        )

    def _to_polars_df(self, data: List[KlineData]) -> pl.DataFrame:
        """Convert KlineData list to Polars DataFrame."""
        records = []
        for kline in data:
            records.append(
                {
                    "open_time": kline.open_time,
                    "close_time": kline.close_time,
                    "open_price": float(kline.open_price),
                    "high_price": float(kline.high_price),
                    "low_price": float(kline.low_price),
                    "close_price": float(kline.close_price),
                    "volume": float(kline.volume),
                    "quote_asset_volume": float(kline.quote_asset_volume),
                    "number_of_trades": kline.number_of_trades,
                    "taker_buy_base_asset_volume": float(kline.taker_buy_base_asset_volume),
                    "taker_buy_quote_asset_volume": float(kline.taker_buy_quote_asset_volume),
                }
            )

        return pl.DataFrame(records)

    def _resample_ohlcv(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Resample OHLCV data using proper aggregation rules.

        - Open: First value in period
        - High: Maximum value in period
        - Low: Minimum value in period
        - Close: Last value in period
        - Volume: Sum of volumes in period
        """
        # Set up time grouping
        time_expr = pl.col("open_time").dt.truncate(TIMEFRAME_MAPPING[self.config.target_timeframe])

        # Perform aggregation
        agg_exprs = [
            pl.col("open_price").first().alias("open_price"),
            pl.col("high_price").max().alias("high_price"),
            pl.col("low_price").min().alias("low_price"),
            pl.col("close_price").last().alias("close_price"),
            time_expr.alias("open_time"),
        ]

        if self.config.include_volume:
            agg_exprs.extend(
                [
                    pl.col("volume").sum().alias("volume"),
                    pl.col("quote_asset_volume").sum().alias("quote_asset_volume"),
                    pl.col("taker_buy_base_asset_volume")
                    .sum()
                    .alias("taker_buy_base_asset_volume"),
                    pl.col("taker_buy_quote_asset_volume")
                    .sum()
                    .alias("taker_buy_quote_asset_volume"),
                ]
            )

        if self.config.include_trades:
            agg_exprs.append(pl.col("number_of_trades").sum().alias("number_of_trades"))

        # Group by time period and aggregate
        resampled = df.group_by(time_expr).agg(agg_exprs).sort("open_time")

        # Calculate close_time based on target timeframe
        resampled = resampled.with_columns([self._calculate_close_time().alias("close_time")])

        return resampled

    def _calculate_close_time(self) -> pl.Expr:
        """Calculate close time based on target timeframe."""
        timeframe = self.config.target_timeframe

        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            return pl.col("open_time") + pl.duration(minutes=minutes) - pl.duration(milliseconds=1)
        elif timeframe.endswith("h"):
            hours = int(timeframe[:-1])
            return pl.col("open_time") + pl.duration(hours=hours) - pl.duration(milliseconds=1)
        elif timeframe.endswith("d"):
            days = int(timeframe[:-1])
            return pl.col("open_time") + pl.duration(days=days) - pl.duration(milliseconds=1)
        elif timeframe.endswith("w"):
            weeks = int(timeframe[:-1])
            return pl.col("open_time") + pl.duration(weeks=weeks) - pl.duration(milliseconds=1)
        elif timeframe.endswith("M"):
            # Monthly - approximate with 30 days
            months = int(timeframe[:-1])
            return pl.col("open_time") + pl.duration(days=30 * months) - pl.duration(milliseconds=1)
        else:
            raise ValueError(f"Unsupported timeframe format: {timeframe}")

    def _from_polars_df(self, df: pl.DataFrame, symbol: str) -> List[KlineData]:
        """Convert Polars DataFrame back to KlineData list."""
        klines = []

        for row in df.iter_rows(named=True):
            kline = KlineData(
                symbol=symbol,
                open_time=row["open_time"],
                close_time=row["close_time"],
                open_price=Decimal(str(row["open_price"])),
                high_price=Decimal(str(row["high_price"])),
                low_price=Decimal(str(row["low_price"])),
                close_price=Decimal(str(row["close_price"])),
                volume=Decimal(str(row.get("volume", 0))),
                quote_asset_volume=Decimal(str(row.get("quote_asset_volume", 0))),
                number_of_trades=row.get("number_of_trades", 0),
                taker_buy_base_asset_volume=Decimal(str(row.get("taker_buy_base_asset_volume", 0))),
                taker_buy_quote_asset_volume=Decimal(
                    str(row.get("taker_buy_quote_asset_volume", 0))
                ),
            )
            klines.append(kline)

        return klines

    def _calculate_completeness(self, source_df: pl.DataFrame, target_df: pl.DataFrame) -> float:
        """Calculate data completeness ratio."""
        if not self.config.validate_completeness:
            return 1.0

        # Get time range
        start_time = source_df.select(pl.col("open_time").min()).item()
        end_time = source_df.select(pl.col("open_time").max()).item()

        # Calculate expected periods
        expected_periods = self._calculate_expected_periods(start_time, end_time)
        actual_periods = len(target_df)

        return min(actual_periods / expected_periods, 1.0) if expected_periods > 0 else 0.0

    def _calculate_expected_periods(self, start_time: datetime, end_time: datetime) -> int:
        """Calculate expected number of periods for the timeframe."""
        time_delta = end_time - start_time
        timeframe = self.config.target_timeframe

        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            return int(time_delta.total_seconds() / (60 * minutes))
        elif timeframe.endswith("h"):
            hours = int(timeframe[:-1])
            return int(time_delta.total_seconds() / (3600 * hours))
        elif timeframe.endswith("d"):
            days = int(timeframe[:-1])
            return int(time_delta.days / days)
        elif timeframe.endswith("w"):
            weeks = int(timeframe[:-1])
            return int(time_delta.days / (7 * weeks))
        elif timeframe.endswith("M"):
            months = int(timeframe[:-1])
            return int(time_delta.days / (30 * months))  # Approximate
        else:
            return 0


def resample_data(
    data: List[KlineData], symbol: str, source_timeframe: str, target_timeframe: str, **kwargs
) -> ResamplingResult:
    """
    Convenience function to resample data.

    Args:
        data: List of K-line data
        symbol: Trading symbol
        source_timeframe: Source timeframe
        target_timeframe: Target timeframe
        **kwargs: Additional configuration options

    Returns:
        ResamplingResult with resampled data and metadata
    """
    config = ResamplingConfig(
        source_timeframe=source_timeframe, target_timeframe=target_timeframe, **kwargs
    )

    resampler = DataResampler(config)
    return resampler.resample_klines(data, symbol)


def get_supported_timeframes() -> List[str]:
    """Get list of supported timeframes."""
    return SUPPORTED_TIMEFRAMES.copy()


def validate_timeframe_conversion(source: str, target: str) -> bool:
    """
    Validate that a timeframe conversion is valid.

    Args:
        source: Source timeframe
        target: Target timeframe

    Returns:
        True if conversion is valid, False otherwise
    """
    if source not in SUPPORTED_TIMEFRAMES or target not in SUPPORTED_TIMEFRAMES:
        return False

    # Add logic to validate that target is higher than source
    # This is a simplified check - could be more sophisticated
    return source != target
