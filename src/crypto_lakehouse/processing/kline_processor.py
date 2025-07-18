"""K-line data processor for Bronze to Silver transformation."""

import polars as pl
from typing import Dict, Any
from datetime import datetime
import logging
from decimal import Decimal

from .base import BaseProcessor
from ..core.models import DataZone, DataType
from ..core.config import Settings

logger = logging.getLogger(__name__)


class KlineProcessor(BaseProcessor):
    """Processor for K-line (candlestick) data."""
    
    async def process(
        self,
        data: pl.DataFrame,
        source_zone: DataZone,
        target_zone: DataZone,
        **kwargs
    ) -> pl.DataFrame:
        """Process K-line data from Bronze to Silver zone."""
        try:
            # Validate input schema
            expected_schema = self.get_schema(source_zone)
            if not self.validate_schema(data, expected_schema):
                raise ValueError("Input data schema validation failed")
            
            # Sort by symbol and timestamp
            processed_data = data.sort(["symbol", "open_time"])
            
            # Clean and validate data
            processed_data = await self._clean_data(processed_data)
            
            # Add computed features
            processed_data = await self._add_features(processed_data)
            
            # Add processing metadata
            processed_data = await self.add_processing_metadata(
                processed_data,
                datetime.now(),
                source_zone,
                target_zone
            )
            
            # Validate output schema
            output_schema = self.get_schema(target_zone)
            if not self.validate_schema(processed_data, output_schema):
                logger.warning("Output schema validation failed, but continuing")
            
            logger.info(f"Successfully processed {len(processed_data)} K-line records")
            return processed_data
            
        except Exception as e:
            logger.error(f"K-line processing failed: {e}")
            raise
    
    def get_schema(self, zone: DataZone) -> pl.Schema:
        """Get expected schema for K-line data in different zones."""
        
        bronze_schema = pl.Schema({
            "symbol": pl.Utf8,
            "open_time": pl.Datetime,
            "close_time": pl.Datetime,
            "open_price": pl.Float64,
            "high_price": pl.Float64,
            "low_price": pl.Float64,
            "close_price": pl.Float64,
            "volume": pl.Float64,
            "quote_asset_volume": pl.Float64,
            "number_of_trades": pl.Int64,
            "taker_buy_base_asset_volume": pl.Float64,
            "taker_buy_quote_asset_volume": pl.Float64
        })
        
        silver_schema = bronze_schema.copy()
        silver_schema.update({
            # Enhanced features
            "vwap": pl.Float64,
            "returns": pl.Float64,
            "log_returns": pl.Float64,
            "price_change": pl.Float64,
            "price_change_percent": pl.Float64,
            "volatility": pl.Float64,
            
            # Technical indicators
            "typical_price": pl.Float64,
            "volume_weighted_average": pl.Float64,
            
            # Metadata
            "_processed_at": pl.Datetime,
            "_source_zone": pl.Utf8,
            "_target_zone": pl.Utf8,
            "_processor_version": pl.Utf8
        })
        
        if zone == DataZone.BRONZE:
            return bronze_schema
        elif zone == DataZone.SILVER:
            return silver_schema
        else:
            return bronze_schema
    
    async def _clean_data(self, data: pl.DataFrame) -> pl.DataFrame:
        """Clean and validate K-line data."""
        cleaned = data
        
        # Remove rows with invalid prices (null, zero, negative)
        cleaned = cleaned.filter(
            (pl.col("open_price") > 0) &
            (pl.col("high_price") > 0) &
            (pl.col("low_price") > 0) &
            (pl.col("close_price") > 0) &
            (pl.col("volume") >= 0)
        )
        
        # Validate OHLC relationships
        cleaned = cleaned.filter(
            (pl.col("high_price") >= pl.col("open_price")) &
            (pl.col("high_price") >= pl.col("close_price")) &
            (pl.col("low_price") <= pl.col("open_price")) &
            (pl.col("low_price") <= pl.col("close_price")) &
            (pl.col("high_price") >= pl.col("low_price"))
        )
        
        # Remove duplicate records
        cleaned = cleaned.unique(subset=["symbol", "open_time"])
        
        # Fill any remaining nulls with appropriate values
        cleaned = cleaned.with_columns([
            pl.col("number_of_trades").fill_null(0),
            pl.col("taker_buy_base_asset_volume").fill_null(0),
            pl.col("taker_buy_quote_asset_volume").fill_null(0)
        ])
        
        rows_removed = len(data) - len(cleaned)
        if rows_removed > 0:
            logger.info(f"Cleaned data: removed {rows_removed} invalid records")
        
        return cleaned
    
    async def _add_features(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add computed features to K-line data."""
        enhanced = data.with_columns([
            # Volume Weighted Average Price (VWAP)
            (
                (pl.col("high_price") + pl.col("low_price") + pl.col("close_price")) / 3 * pl.col("volume")
            ).sum().over("symbol") / pl.col("volume").sum().over("symbol").alias("vwap"),
            
            # Price changes
            (pl.col("close_price") - pl.col("open_price")).alias("price_change"),
            (
                (pl.col("close_price") - pl.col("open_price")) / pl.col("open_price") * 100
            ).alias("price_change_percent"),
            
            # Returns (period over period)
            (
                (pl.col("close_price") / pl.col("close_price").shift(1) - 1) * 100
            ).over("symbol").alias("returns"),
            
            # Log returns
            (
                pl.col("close_price").log() - pl.col("close_price").shift(1).log()
            ).over("symbol").alias("log_returns"),
            
            # Typical price
            (
                (pl.col("high_price") + pl.col("low_price") + pl.col("close_price")) / 3
            ).alias("typical_price"),
            
            # Volume weighted average (different from VWAP)
            (
                pl.col("quote_asset_volume") / pl.col("volume")
            ).alias("volume_weighted_average"),
            
        ])
        
        # Calculate volatility (rolling standard deviation of returns)
        enhanced = enhanced.with_columns([
            pl.col("returns").rolling_std(window_size=20, min_periods=1).over("symbol").alias("volatility")
        ])
        
        # Handle edge cases and infinite values
        enhanced = enhanced.with_columns([
            pl.col("vwap").fill_null(pl.col("close_price")),
            pl.col("returns").fill_null(0.0),
            pl.col("log_returns").fill_null(0.0),
            pl.col("volatility").fill_null(0.0)
        ])
        
        # Replace infinite values with nulls then fill
        numeric_cols = ["returns", "log_returns", "price_change_percent", "volatility"]
        for col in numeric_cols:
            enhanced = enhanced.with_columns([
                pl.when(pl.col(col).is_infinite()).then(None).otherwise(pl.col(col)).alias(col)
            ])
            enhanced = enhanced.with_columns([
                pl.col(col).fill_null(0.0)
            ])
        
        logger.info("Added enhanced features to K-line data")
        return enhanced
    
    async def calculate_additional_indicators(
        self, 
        data: pl.DataFrame, 
        indicators: list = None
    ) -> pl.DataFrame:
        """Calculate additional technical indicators."""
        if not indicators:
            indicators = ["sma_20", "ema_20", "bollinger_bands"]
        
        enhanced = data
        
        for indicator in indicators:
            if indicator == "sma_20":
                enhanced = enhanced.with_columns([
                    pl.col("close_price").rolling_mean(window_size=20).over("symbol").alias("sma_20")
                ])
            
            elif indicator == "ema_20":
                # Exponential Moving Average (simplified)
                enhanced = enhanced.with_columns([
                    pl.col("close_price").ewm_mean(span=20).over("symbol").alias("ema_20")
                ])
            
            elif indicator == "bollinger_bands":
                # Bollinger Bands (20-period SMA ± 2 standard deviations)
                enhanced = enhanced.with_columns([
                    pl.col("close_price").rolling_mean(window_size=20).over("symbol").alias("bb_middle"),
                    pl.col("close_price").rolling_std(window_size=20).over("symbol").alias("bb_std")
                ])
                
                enhanced = enhanced.with_columns([
                    (pl.col("bb_middle") + 2 * pl.col("bb_std")).alias("bb_upper"),
                    (pl.col("bb_middle") - 2 * pl.col("bb_std")).alias("bb_lower")
                ])
                
                # Clean up temporary columns
                enhanced = enhanced.drop(["bb_std"])
        
        return enhanced