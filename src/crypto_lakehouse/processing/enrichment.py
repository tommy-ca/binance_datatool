"""Data enrichment module for advanced feature engineering."""

import polars as pl
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import numpy as np

from .base import BaseProcessor
from ..core.models import DataZone, DataType
from ..core.config import Settings

logger = logging.getLogger(__name__)


class DataEnrichment(BaseProcessor):
    """Advanced data enrichment for Gold zone transformations."""
    
    async def process(
        self,
        data: pl.DataFrame,
        source_zone: DataZone,
        target_zone: DataZone,
        **kwargs
    ) -> pl.DataFrame:
        """Enrich data from Silver to Gold zone."""
        try:
            # Apply various enrichment strategies
            enriched = data
            
            if "close_price" in data.columns:
                enriched = await self._add_technical_indicators(enriched)
                enriched = await self._add_market_microstructure(enriched)
            
            if "funding_rate" in data.columns:
                enriched = await self._add_funding_insights(enriched)
            
            # Add cross-asset features if multiple symbols
            if len(data["symbol"].unique()) > 1:
                enriched = await self._add_cross_asset_features(enriched)
            
            # Add processing metadata
            enriched = await self.add_processing_metadata(
                enriched,
                datetime.now(),
                source_zone,
                target_zone
            )
            
            logger.info(f"Successfully enriched {len(enriched)} records")
            return enriched
            
        except Exception as e:
            logger.error(f"Data enrichment failed: {e}")
            raise
    
    def get_schema(self, zone: DataZone) -> pl.Schema:
        """Get schema for enriched data."""
        return pl.Schema({
            # Base schema will be inherited from input data
            # Additional enrichment columns will be added dynamically
        })
    
    async def _add_technical_indicators(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add comprehensive technical indicators."""
        try:
            enhanced = data
            
            # Moving averages
            for window in [5, 10, 20, 50, 200]:
                enhanced = enhanced.with_columns([
                    pl.col("close_price").rolling_mean(window_size=window).over("symbol").alias(f"sma_{window}"),
                    pl.col("close_price").ewm_mean(span=window).over("symbol").alias(f"ema_{window}")
                ])
            
            # RSI (Relative Strength Index)
            enhanced = await self._calculate_rsi(enhanced)
            
            # MACD (Moving Average Convergence Divergence)
            enhanced = await self._calculate_macd(enhanced)
            
            # Bollinger Bands
            enhanced = await self._calculate_bollinger_bands(enhanced)
            
            # Stochastic Oscillator
            enhanced = await self._calculate_stochastic(enhanced)
            
            # Average True Range (ATR)
            enhanced = await self._calculate_atr(enhanced)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Failed to add technical indicators: {e}")
            return data
    
    async def _calculate_rsi(self, data: pl.DataFrame, period: int = 14) -> pl.DataFrame:
        """Calculate Relative Strength Index."""
        try:
            enhanced = data.with_columns([
                # Price changes
                (pl.col("close_price") - pl.col("close_price").shift(1)).over("symbol").alias("price_delta")
            ])
            
            # Separate gains and losses
            enhanced = enhanced.with_columns([
                pl.when(pl.col("price_delta") > 0).then(pl.col("price_delta")).otherwise(0).alias("gain"),
                pl.when(pl.col("price_delta") < 0).then(-pl.col("price_delta")).otherwise(0).alias("loss")
            ])
            
            # Calculate average gains and losses
            enhanced = enhanced.with_columns([
                pl.col("gain").rolling_mean(window_size=period).over("symbol").alias("avg_gain"),
                pl.col("loss").rolling_mean(window_size=period).over("symbol").alias("avg_loss")
            ])
            
            # Calculate RSI
            enhanced = enhanced.with_columns([
                (100 - (100 / (1 + (pl.col("avg_gain") / pl.col("avg_loss"))))).alias("rsi")
            ])
            
            # Clean up temporary columns
            enhanced = enhanced.drop(["price_delta", "gain", "loss", "avg_gain", "avg_loss"])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"RSI calculation failed: {e}")
            return data
    
    async def _calculate_macd(self, data: pl.DataFrame) -> pl.DataFrame:
        """Calculate MACD indicator."""
        try:
            enhanced = data.with_columns([
                # MACD line
                (
                    pl.col("close_price").ewm_mean(span=12).over("symbol") - 
                    pl.col("close_price").ewm_mean(span=26).over("symbol")
                ).alias("macd"),
                
                # Signal line (9-period EMA of MACD)
                pl.col("close_price").ewm_mean(span=12).over("symbol").alias("temp_ema12"),
                pl.col("close_price").ewm_mean(span=26).over("symbol").alias("temp_ema26")
            ])
            
            enhanced = enhanced.with_columns([
                (pl.col("temp_ema12") - pl.col("temp_ema26")).alias("macd")
            ])
            
            enhanced = enhanced.with_columns([
                pl.col("macd").ewm_mean(span=9).over("symbol").alias("macd_signal")
            ])
            
            # MACD histogram
            enhanced = enhanced.with_columns([
                (pl.col("macd") - pl.col("macd_signal")).alias("macd_histogram")
            ])
            
            # Clean up
            enhanced = enhanced.drop(["temp_ema12", "temp_ema26"])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"MACD calculation failed: {e}")
            return data
    
    async def _calculate_bollinger_bands(self, data: pl.DataFrame, period: int = 20, std_dev: float = 2.0) -> pl.DataFrame:
        """Calculate Bollinger Bands."""
        try:
            enhanced = data.with_columns([
                pl.col("close_price").rolling_mean(window_size=period).over("symbol").alias("bb_middle"),
                pl.col("close_price").rolling_std(window_size=period).over("symbol").alias("bb_std")
            ])
            
            enhanced = enhanced.with_columns([
                (pl.col("bb_middle") + std_dev * pl.col("bb_std")).alias("bb_upper"),
                (pl.col("bb_middle") - std_dev * pl.col("bb_std")).alias("bb_lower"),
                
                # Bollinger Band width and position
                (pl.col("bb_std") * 2 * std_dev).alias("bb_width"),
                (
                    (pl.col("close_price") - pl.col("bb_lower")) / 
                    (pl.col("bb_upper") - pl.col("bb_lower"))
                ).alias("bb_position")
            ])
            
            # Clean up
            enhanced = enhanced.drop(["bb_std"])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Bollinger Bands calculation failed: {e}")
            return data
    
    async def _calculate_stochastic(self, data: pl.DataFrame, k_period: int = 14, d_period: int = 3) -> pl.DataFrame:
        """Calculate Stochastic Oscillator."""
        try:
            enhanced = data.with_columns([
                # Highest high and lowest low over period
                pl.col("high_price").rolling_max(window_size=k_period).over("symbol").alias("highest_high"),
                pl.col("low_price").rolling_min(window_size=k_period).over("symbol").alias("lowest_low")
            ])
            
            enhanced = enhanced.with_columns([
                # %K
                (
                    (pl.col("close_price") - pl.col("lowest_low")) / 
                    (pl.col("highest_high") - pl.col("lowest_low")) * 100
                ).alias("stoch_k")
            ])
            
            enhanced = enhanced.with_columns([
                # %D (moving average of %K)
                pl.col("stoch_k").rolling_mean(window_size=d_period).over("symbol").alias("stoch_d")
            ])
            
            # Clean up
            enhanced = enhanced.drop(["highest_high", "lowest_low"])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Stochastic calculation failed: {e}")
            return data
    
    async def _calculate_atr(self, data: pl.DataFrame, period: int = 14) -> pl.DataFrame:
        """Calculate Average True Range."""
        try:
            enhanced = data.with_columns([
                # True Range components
                (pl.col("high_price") - pl.col("low_price")).alias("hl_diff"),
                (pl.col("high_price") - pl.col("close_price").shift(1)).abs().over("symbol").alias("hc_diff"),
                (pl.col("low_price") - pl.col("close_price").shift(1)).abs().over("symbol").alias("lc_diff")
            ])
            
            # True Range is the maximum of the three differences
            enhanced = enhanced.with_columns([
                pl.max_horizontal(["hl_diff", "hc_diff", "lc_diff"]).alias("true_range")
            ])
            
            # ATR is the moving average of True Range
            enhanced = enhanced.with_columns([
                pl.col("true_range").rolling_mean(window_size=period).over("symbol").alias("atr")
            ])
            
            # Clean up
            enhanced = enhanced.drop(["hl_diff", "hc_diff", "lc_diff", "true_range"])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"ATR calculation failed: {e}")
            return data
    
    async def _add_market_microstructure(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add market microstructure features."""
        try:
            enhanced = data.with_columns([
                # Spread (high - low)
                (pl.col("high_price") - pl.col("low_price")).alias("spread"),
                
                # Body size (close - open)
                (pl.col("close_price") - pl.col("open_price")).alias("body_size"),
                
                # Upper shadow
                (pl.col("high_price") - pl.max_horizontal(["open_price", "close_price"])).alias("upper_shadow"),
                
                # Lower shadow  
                (pl.min_horizontal(["open_price", "close_price"]) - pl.col("low_price")).alias("lower_shadow"),
                
                # Buy pressure ratio
                (
                    pl.col("taker_buy_base_asset_volume") / pl.col("volume")
                ).alias("buy_pressure_ratio"),
                
                # Quote volume ratio
                (
                    pl.col("quote_asset_volume") / pl.col("volume")
                ).alias("quote_volume_ratio")
            ])
            
            # Candlestick pattern recognition
            enhanced = enhanced.with_columns([
                # Doji pattern (small body relative to spread)
                (
                    pl.col("body_size").abs() / pl.col("spread") < 0.1
                ).alias("is_doji"),
                
                # Hammer pattern
                (
                    (pl.col("lower_shadow") > 2 * pl.col("body_size").abs()) &
                    (pl.col("upper_shadow") < pl.col("body_size").abs())
                ).alias("is_hammer"),
                
                # Shooting star pattern
                (
                    (pl.col("upper_shadow") > 2 * pl.col("body_size").abs()) &
                    (pl.col("lower_shadow") < pl.col("body_size").abs())
                ).alias("is_shooting_star")
            ])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Market microstructure features failed: {e}")
            return data
    
    async def _add_funding_insights(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add funding rate insights and derivatives."""
        try:
            enhanced = data.with_columns([
                # Funding rate momentum
                (
                    pl.col("funding_rate") - pl.col("funding_rate").shift(1)
                ).over("symbol").alias("funding_momentum"),
                
                # Funding rate acceleration
                (
                    (pl.col("funding_rate") - pl.col("funding_rate").shift(1)) -
                    (pl.col("funding_rate").shift(1) - pl.col("funding_rate").shift(2))
                ).over("symbol").alias("funding_acceleration"),
                
                # Funding rate percentile ranking
                pl.col("funding_rate").rank(method="average").over("symbol").alias("funding_rank"),
                
                # Extreme funding rate indicator
                (
                    (pl.col("funding_rate") > 0.001) |  # > 0.1%
                    (pl.col("funding_rate") < -0.001)   # < -0.1%
                ).alias("extreme_funding"),
                
                # Funding rate regime change
                (
                    (pl.col("funding_rate") > 0) != (pl.col("funding_rate").shift(1) > 0)
                ).over("symbol").alias("funding_regime_change")
            ])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Funding insights failed: {e}")
            return data
    
    async def _add_cross_asset_features(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add cross-asset correlation and spread features."""
        try:
            # This is a simplified implementation
            # In practice, you'd want more sophisticated correlation calculations
            
            enhanced = data
            
            if "close_price" in data.columns:
                # Market-wide features (across all symbols)
                enhanced = enhanced.with_columns([
                    # Market average price change
                    pl.col("returns").mean().over("open_time").alias("market_avg_return"),
                    
                    # Symbol correlation with market
                    pl.corr("returns", "market_avg_return").over("symbol").alias("market_correlation"),
                    
                    # Relative strength vs market
                    (
                        pl.col("returns") - pl.col("market_avg_return")
                    ).alias("relative_strength")
                ])
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Cross-asset features failed: {e}")
            return data