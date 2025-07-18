"""Funding rate data processor for Bronze to Silver transformation."""

import polars as pl
from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from .base import BaseProcessor
from ..core.models import DataZone
from ..core.config import Settings

logger = logging.getLogger(__name__)


class FundingRateProcessor(BaseProcessor):
    """Processor for funding rate data."""
    
    async def process(
        self,
        data: pl.DataFrame,
        source_zone: DataZone,
        target_zone: DataZone,
        **kwargs
    ) -> pl.DataFrame:
        """Process funding rate data from Bronze to Silver zone."""
        try:
            # Validate input schema
            expected_schema = self.get_schema(source_zone)
            if not self.validate_schema(data, expected_schema):
                raise ValueError("Input data schema validation failed")
            
            # Sort by symbol and timestamp
            processed_data = data.sort(["symbol", "funding_time"])
            
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
            
            logger.info(f"Successfully processed {len(processed_data)} funding rate records")
            return processed_data
            
        except Exception as e:
            logger.error(f"Funding rate processing failed: {e}")
            raise
    
    def get_schema(self, zone: DataZone) -> pl.Schema:
        """Get expected schema for funding rate data."""
        
        bronze_schema = pl.Schema({
            "symbol": pl.Utf8,
            "funding_time": pl.Datetime,
            "funding_rate": pl.Float64,
            "mark_price": pl.Float64
        })
        
        silver_schema = bronze_schema.copy()
        silver_schema.update({
            # Enhanced features
            "funding_rate_bps": pl.Float64,  # Basis points
            "annualized_rate": pl.Float64,
            "rate_change": pl.Float64,
            "rate_change_percent": pl.Float64,
            "rolling_avg_7d": pl.Float64,
            "rolling_avg_30d": pl.Float64,
            "volatility_7d": pl.Float64,
            "cumulative_funding": pl.Float64,
            
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
        """Clean and validate funding rate data."""
        cleaned = data
        
        # Remove rows with null funding times or symbols
        cleaned = cleaned.filter(
            pl.col("symbol").is_not_null() &
            pl.col("funding_time").is_not_null()
        )
        
        # Fill null funding rates with 0
        cleaned = cleaned.with_columns([
            pl.col("funding_rate").fill_null(0.0),
            pl.col("mark_price").fill_null(0.0)
        ])
        
        # Remove extreme outliers (funding rates outside reasonable bounds)
        # Typical funding rates are between -0.75% and +0.75% (8-hour periods)
        cleaned = cleaned.filter(
            (pl.col("funding_rate") >= -0.0075) &
            (pl.col("funding_rate") <= 0.0075)
        )
        
        # Remove duplicate records
        cleaned = cleaned.unique(subset=["symbol", "funding_time"])
        
        rows_removed = len(data) - len(cleaned)
        if rows_removed > 0:
            logger.info(f"Cleaned funding rate data: removed {rows_removed} invalid records")
        
        return cleaned
    
    async def _add_features(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add computed features to funding rate data."""
        enhanced = data.with_columns([
            # Convert to basis points (1% = 100 bps)
            (pl.col("funding_rate") * 10000).alias("funding_rate_bps"),
            
            # Annualized rate (funding occurs every 8 hours, so 3 times per day)
            (pl.col("funding_rate") * 365 * 3).alias("annualized_rate"),
            
            # Rate changes
            (
                pl.col("funding_rate") - pl.col("funding_rate").shift(1)
            ).over("symbol").alias("rate_change"),
            
            (
                (pl.col("funding_rate") / pl.col("funding_rate").shift(1) - 1) * 100
            ).over("symbol").alias("rate_change_percent"),
        ])
        
        # Add rolling averages and volatility
        enhanced = enhanced.with_columns([
            # 7-day rolling average (about 21 funding periods)
            pl.col("funding_rate").rolling_mean(window_size=21).over("symbol").alias("rolling_avg_7d"),
            
            # 30-day rolling average (about 90 funding periods)
            pl.col("funding_rate").rolling_mean(window_size=90).over("symbol").alias("rolling_avg_30d"),
            
            # 7-day volatility
            pl.col("funding_rate").rolling_std(window_size=21).over("symbol").alias("volatility_7d"),
            
            # Cumulative funding (running sum)
            pl.col("funding_rate").cumsum().over("symbol").alias("cumulative_funding")
        ])
        
        # Handle edge cases
        enhanced = enhanced.with_columns([
            pl.col("rate_change").fill_null(0.0),
            pl.col("rate_change_percent").fill_null(0.0),
            pl.col("rolling_avg_7d").fill_null(pl.col("funding_rate")),
            pl.col("rolling_avg_30d").fill_null(pl.col("funding_rate")),
            pl.col("volatility_7d").fill_null(0.0)
        ])
        
        # Replace infinite values
        numeric_cols = ["rate_change_percent", "annualized_rate"]
        for col in numeric_cols:
            enhanced = enhanced.with_columns([
                pl.when(pl.col(col).is_infinite()).then(None).otherwise(pl.col(col)).alias(col)
            ])
            enhanced = enhanced.with_columns([
                pl.col(col).fill_null(0.0)
            ])
        
        logger.info("Added enhanced features to funding rate data")
        return enhanced
    
    async def calculate_funding_statistics(
        self, 
        data: pl.DataFrame,
        window_days: int = 30
    ) -> pl.DataFrame:
        """Calculate additional funding rate statistics."""
        window_periods = window_days * 3  # 3 funding periods per day
        
        stats = data.with_columns([
            # Min/Max rates in period
            pl.col("funding_rate").rolling_min(window_size=window_periods).over("symbol").alias(f"min_rate_{window_days}d"),
            pl.col("funding_rate").rolling_max(window_size=window_periods).over("symbol").alias(f"max_rate_{window_days}d"),
            
            # Percentiles
            pl.col("funding_rate").rolling_quantile(quantile=0.25, window_size=window_periods).over("symbol").alias(f"p25_rate_{window_days}d"),
            pl.col("funding_rate").rolling_quantile(quantile=0.75, window_size=window_periods).over("symbol").alias(f"p75_rate_{window_days}d"),
            
            # Count of positive/negative rates
            (pl.col("funding_rate") > 0).cast(pl.Int32).rolling_sum(window_size=window_periods).over("symbol").alias(f"positive_count_{window_days}d"),
            (pl.col("funding_rate") < 0).cast(pl.Int32).rolling_sum(window_size=window_periods).over("symbol").alias(f"negative_count_{window_days}d"),
        ])
        
        # Calculate rate regime (predominantly positive, negative, or neutral)
        stats = stats.with_columns([
            pl.when(pl.col(f"positive_count_{window_days}d") > window_periods * 0.6)
            .then(pl.lit("positive"))
            .when(pl.col(f"negative_count_{window_days}d") > window_periods * 0.6)
            .then(pl.lit("negative"))
            .otherwise(pl.lit("neutral"))
            .alias(f"rate_regime_{window_days}d")
        ])
        
        return stats