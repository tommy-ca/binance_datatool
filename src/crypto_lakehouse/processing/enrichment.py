"""
Enrichment processor for adding derived metrics and advanced analytics.

This module provides additional enrichment capabilities for data in the Silver zone,
adding market indicators, cross-asset correlations, and advanced derived metrics.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl

from ..core.models import DataZone, DataType
from .base import BaseProcessor

logger = logging.getLogger(__name__)


class EnrichmentProcessor(BaseProcessor):
    """
    Processor for data enrichment and advanced analytics.
    
    Adds market indicators, cross-asset correlations, and advanced derived metrics
    to existing Silver zone data for Gold zone storage.
    """
    
    def get_required_columns(self) -> List[str]:
        """Get required columns for enrichment processing."""
        return [
            "symbol",
            "processed_at"  # Must be already processed data
        ]
    
    def validate_input(self, data: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate input data for enrichment processing.
        
        Args:
            data: Input data (typically from Silver zone)
            
        Returns:
            Validation report with status and issues
        """
        validation_report = {
            "valid": True,
            "issues": [],
            "record_count": len(data),
            "column_check": {},
            "data_quality": {}
        }
        
        try:
            # Check minimum required columns
            required_columns = self.get_required_columns()
            missing_columns = [col for col in required_columns if col not in data.columns]
            
            if missing_columns:
                validation_report["valid"] = False
                validation_report["issues"].append(f"Missing required columns: {missing_columns}")
            
            for col in required_columns:
                validation_report["column_check"][col] = col in data.columns
            
            # Check if data appears to be already processed (has processor metadata)
            if "processor_name" not in data.columns:
                validation_report["issues"].append("Data does not appear to be pre-processed (missing processor_name)")
            
            # Check data recency
            if "processed_at" in data.columns:
                latest_processing = data["processed_at"].max()
                if latest_processing:
                    age_hours = (datetime.now() - latest_processing).total_seconds() / 3600
                    validation_report["data_quality"]["data_age_hours"] = age_hours
                    
                    if age_hours > 24:
                        validation_report["issues"].append(f"Data is {age_hours:.1f} hours old")
            
            return validation_report
            
        except Exception as e:
            self.logger.error(f"Input validation failed: {e}")
            validation_report["valid"] = False
            validation_report["issues"].append(f"Validation error: {e}")
            return validation_report
    
    async def process(
        self, 
        data: pl.DataFrame, 
        source_zone: DataZone, 
        target_zone: DataZone,
        data_type: Optional[DataType] = None,
        **kwargs
    ) -> pl.DataFrame:
        """
        Process data for enrichment.
        
        Args:
            data: Input data (typically from Silver zone)
            source_zone: Source zone (typically SILVER)
            target_zone: Target zone (typically GOLD)
            data_type: Type of data being processed
            **kwargs: Additional processing parameters
            
        Returns:
            Enriched data ready for Gold zone
        """
        try:
            self.logger.info(f"Enriching {len(data)} records from {source_zone} to {target_zone}")
            
            # Step 1: Validate input data
            validation_report = self.validate_input(data)
            if not validation_report["valid"]:
                self.logger.warning(f"Input validation issues: {validation_report['issues']}")
            
            # Step 2: Determine enrichment strategy based on data type
            if data_type == DataType.KLINES or "close_price" in data.columns:
                enriched_data = self._enrich_kline_data(data)
            elif data_type == DataType.FUNDING_RATES or "funding_rate" in data.columns:
                enriched_data = self._enrich_funding_data(data)
            else:
                # Generic enrichment for unknown data types
                enriched_data = self._enrich_generic_data(data)
            
            # Step 3: Add cross-asset analytics if multiple symbols present
            if "symbol" in enriched_data.columns and enriched_data["symbol"].n_unique() > 1:
                cross_asset_data = self._add_cross_asset_analytics(enriched_data)
            else:
                cross_asset_data = enriched_data
            
            # Step 4: Add market regime indicators
            regime_data = self._add_market_regime_indicators(cross_asset_data)
            
            # Step 5: Add processing metadata
            final_data = self.add_processing_metadata(regime_data)
            
            self.logger.info(f"Successfully enriched {len(final_data)} records")
            return final_data
            
        except Exception as e:
            self.logger.error(f"Enrichment processing failed: {e}")
            raise
    
    def _enrich_kline_data(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add enrichment specific to kline data.
        
        Args:
            data: Kline data
            
        Returns:
            Enriched kline data
        """
        try:
            return data.with_columns([
                # Advanced volatility metrics
                pl.col("price_volatility_14").rolling_mean(window_size=7).over("symbol").alias("volatility_trend"),
                
                # Price momentum indicators
                pl.when(pl.col("sma_7") > pl.col("sma_14"))
                .then(pl.lit("bullish"))
                .when(pl.col("sma_7") < pl.col("sma_14"))
                .then(pl.lit("bearish"))
                .otherwise(pl.lit("neutral"))
                .alias("trend_direction"),
                
                # Volume profile analysis
                (pl.col("volume") / pl.col("volume_ma_14")).alias("volume_ratio"),
                
                pl.when(pl.col("volume") > pl.col("volume_ma_14") * 1.5)
                .then(pl.lit("high_volume"))
                .when(pl.col("volume") > pl.col("volume_ma_14"))
                .then(pl.lit("above_average"))
                .when(pl.col("volume") < pl.col("volume_ma_14") * 0.5)
                .then(pl.lit("low_volume"))
                .otherwise(pl.lit("normal"))
                .alias("volume_profile"),
                
                # RSI-based signals
                pl.when(pl.col("rsi_14") > 70)
                .then(pl.lit("overbought"))
                .when(pl.col("rsi_14") < 30)
                .then(pl.lit("oversold"))
                .otherwise(pl.lit("neutral"))
                .alias("rsi_signal"),
                
                # Support/Resistance levels (simplified)
                pl.col("low_price").rolling_min(window_size=50).over("symbol").alias("support_level_50"),
                pl.col("high_price").rolling_max(window_size=50).over("symbol").alias("resistance_level_50"),
                
                # Market microstructure
                pl.when(pl.col("candle_type") == "bullish")
                .then(1)
                .otherwise(-1)
                .rolling_mean(window_size=20).over("symbol")
                .alias("bullish_momentum_20"),
                
                # Efficiency ratio (price change vs volatility)
                (pl.col("price_change").abs() / pl.col("price_range")).alias("efficiency_ratio")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to enrich kline data: {e}")
            return data
    
    def _enrich_funding_data(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add enrichment specific to funding rate data.
        
        Args:
            data: Funding rate data
            
        Returns:
            Enriched funding rate data
        """
        try:
            return data.with_columns([
                # Funding rate momentum
                pl.when(pl.col("funding_rate_change") > 0)
                .then(pl.lit("increasing"))
                .when(pl.col("funding_rate_change") < 0)
                .then(pl.lit("decreasing"))
                .otherwise(pl.lit("stable"))
                .alias("funding_momentum"),
                
                # Extreme funding events
                pl.when(pl.col("funding_rate").abs() > 0.01)
                .then(pl.lit("extreme_event"))
                .when(pl.col("funding_rate").abs() > 0.005)
                .then(pl.lit("significant_event"))
                .otherwise(pl.lit("normal"))
                .alias("funding_event_type"),
                
                # Funding rate percentile within recent history
                pl.col("funding_rate")
                .rank(method="average")
                .over("symbol")
                .truediv(pl.count().over("symbol"))
                .alias("funding_percentile"),
                
                # Mark price vs funding correlation indicator
                pl.when((pl.col("funding_rate") > 0) & (pl.col("mark_price_momentum") > 0))
                .then(pl.lit("aligned_bullish"))
                .when((pl.col("funding_rate") < 0) & (pl.col("mark_price_momentum") < 0))
                .then(pl.lit("aligned_bearish"))
                .when((pl.col("funding_rate") > 0) & (pl.col("mark_price_momentum") < 0))
                .then(pl.lit("contrarian_signal"))
                .when((pl.col("funding_rate") < 0) & (pl.col("mark_price_momentum") > 0))
                .then(pl.lit("contrarian_signal"))
                .otherwise(pl.lit("neutral"))
                .alias("funding_price_alignment"),
                
                # Funding volatility regime
                pl.when(pl.col("funding_volatility_30") > pl.col("funding_volatility_30").quantile(0.8).over("symbol"))
                .then(pl.lit("high_volatility"))
                .when(pl.col("funding_volatility_30") < pl.col("funding_volatility_30").quantile(0.2).over("symbol"))
                .then(pl.lit("low_volatility"))
                .otherwise(pl.lit("normal_volatility"))
                .alias("funding_volatility_regime")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to enrich funding data: {e}")
            return data
    
    def _enrich_generic_data(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add generic enrichment for unknown data types.
        
        Args:
            data: Generic data
            
        Returns:
            Enriched data with generic metrics
        """
        try:
            enriched_columns = []
            
            # Add timestamp-based features if timestamp column exists
            timestamp_cols = [col for col in data.columns if "time" in col.lower()]
            if timestamp_cols:
                timestamp_col = timestamp_cols[0]
                enriched_columns.extend([
                    pl.col(timestamp_col).dt.hour().alias("hour_of_day"),
                    pl.col(timestamp_col).dt.weekday().alias("day_of_week"),
                    pl.col(timestamp_col).dt.day().alias("day_of_month")
                ])
            
            # Add record age
            enriched_columns.append(
                (datetime.now() - pl.col("processed_at")).dt.total_seconds().truediv(3600).alias("record_age_hours")
            )
            
            return data.with_columns(enriched_columns) if enriched_columns else data
            
        except Exception as e:
            self.logger.error(f"Failed to add generic enrichment: {e}")
            return data
    
    def _add_cross_asset_analytics(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add cross-asset analytics for multi-symbol data.
        
        Args:
            data: Data with multiple symbols
            
        Returns:
            Data with cross-asset analytics
        """
        try:
            # Identify numeric columns for correlation analysis
            numeric_cols = [col for col in data.columns if data[col].dtype in [pl.Float32, pl.Float64, pl.Int32, pl.Int64]]
            
            if not numeric_cols:
                return data
            
            # Add relative performance metrics if price data available
            price_cols = [col for col in numeric_cols if "price" in col.lower()]
            if price_cols:
                price_col = price_cols[0]  # Use first price column
                
                # Calculate market-relative performance
                market_avg = data.group_by("processed_at").agg(
                    pl.col(price_col).mean().alias("market_avg_price")
                )
                
                data_with_market = data.join(market_avg, on="processed_at", how="left")
                
                return data_with_market.with_columns([
                    (pl.col(price_col) / pl.col("market_avg_price")).alias("relative_performance"),
                    pl.when(pl.col(price_col) > pl.col("market_avg_price"))
                    .then(pl.lit("outperforming"))
                    .otherwise(pl.lit("underperforming"))
                    .alias("performance_category")
                ])
            
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to add cross-asset analytics: {e}")
            return data
    
    def _add_market_regime_indicators(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add market regime indicators based on multiple metrics.
        
        Args:
            data: Input data
            
        Returns:
            Data with market regime indicators
        """
        try:
            regime_columns = []
            
            # Volatility regime
            vol_cols = [col for col in data.columns if "volatility" in col.lower()]
            if vol_cols:
                vol_col = vol_cols[0]
                regime_columns.append(
                    pl.when(pl.col(vol_col) > pl.col(vol_col).quantile(0.8))
                    .then(pl.lit("high_volatility"))
                    .when(pl.col(vol_col) < pl.col(vol_col).quantile(0.2))
                    .then(pl.lit("low_volatility"))
                    .otherwise(pl.lit("normal_volatility"))
                    .alias("volatility_regime")
                )
            
            # Volume regime
            vol_ratio_cols = [col for col in data.columns if "volume" in col.lower() and "ratio" in col.lower()]
            if vol_ratio_cols:
                vol_ratio_col = vol_ratio_cols[0]
                regime_columns.append(
                    pl.when(pl.col(vol_ratio_col) > 2.0)
                    .then(pl.lit("high_volume"))
                    .when(pl.col(vol_ratio_col) < 0.5)
                    .then(pl.lit("low_volume"))
                    .otherwise(pl.lit("normal_volume"))
                    .alias("volume_regime")
                )
            
            # Overall market regime composite
            if len(regime_columns) >= 2:
                regime_columns.append(
                    pl.when((pl.col("volatility_regime") == "high_volatility") & 
                           (pl.col("volume_regime") == "high_volume"))
                    .then(pl.lit("stress"))
                    .when((pl.col("volatility_regime") == "low_volatility") & 
                          (pl.col("volume_regime") == "low_volume"))
                    .then(pl.lit("calm"))
                    .otherwise(pl.lit("mixed"))
                    .alias("market_regime")
                )
            
            return data.with_columns(regime_columns) if regime_columns else data
            
        except Exception as e:
            self.logger.error(f"Failed to add market regime indicators: {e}")
            return data