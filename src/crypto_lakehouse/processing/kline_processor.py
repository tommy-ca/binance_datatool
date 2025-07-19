"""
Kline (candlestick) data processor for Silver layer transformation.

This module processes raw kline data from the Bronze zone, applying cleaning,
validation, enrichment, and technical indicators for storage in the Silver zone.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl

from ..core.models import DataZone
from .base import BaseProcessor

logger = logging.getLogger(__name__)


class KlineProcessor(BaseProcessor):
    """
    Processor for candlestick (kline) data transformation.
    
    Transforms raw kline data from Bronze zone into clean, validated, and enriched
    data for Silver zone storage with technical indicators and derived metrics.
    """
    
    def get_required_columns(self) -> List[str]:
        """Get required columns for kline processing."""
        return [
            "symbol",
            "open_time", 
            "close_time",
            "open_price",
            "high_price", 
            "low_price",
            "close_price",
            "volume",
            "quote_asset_volume",
            "number_of_trades"
        ]
    
    def validate_input(self, data: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate input kline data structure and quality.
        
        Args:
            data: Input kline data
            
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
            # Check required columns
            required_columns = self.get_required_columns()
            missing_columns = [col for col in required_columns if col not in data.columns]
            
            if missing_columns:
                validation_report["valid"] = False
                validation_report["issues"].append(f"Missing required columns: {missing_columns}")
            
            for col in required_columns:
                validation_report["column_check"][col] = col in data.columns
            
            # Validate numeric price columns
            price_columns = ["open_price", "high_price", "low_price", "close_price"]
            numeric_validation = self.validate_numeric_columns(data, price_columns + ["volume", "quote_asset_volume"])
            
            if not numeric_validation["valid"]:
                validation_report["valid"] = False
                validation_report["issues"].extend(numeric_validation["issues"])
            
            validation_report["data_quality"] = numeric_validation["statistics"]
            
            # Check for logical price relationships (high >= low, etc.)
            if all(col in data.columns for col in price_columns):
                invalid_hloc = data.filter(
                    (pl.col("high_price") < pl.col("low_price")) |
                    (pl.col("open_price") < 0) |
                    (pl.col("close_price") < 0)
                ).height
                
                if invalid_hloc > 0:
                    validation_report["valid"] = False
                    validation_report["issues"].append(f"Invalid HLOC relationships: {invalid_hloc} records")
            
            # Check timestamp ordering
            if "open_time" in data.columns and "close_time" in data.columns:
                invalid_times = data.filter(pl.col("close_time") <= pl.col("open_time")).height
                if invalid_times > 0:
                    validation_report["valid"] = False
                    validation_report["issues"].append(f"Invalid timestamp ordering: {invalid_times} records")
            
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
        **kwargs
    ) -> pl.DataFrame:
        """
        Process kline data from Bronze to Silver zone.
        
        Args:
            data: Input kline data
            source_zone: Source zone (typically BRONZE)
            target_zone: Target zone (typically SILVER)
            **kwargs: Additional processing parameters
            
        Returns:
            Processed kline data with enrichments
        """
        try:
            self.logger.info(f"Processing {len(data)} kline records from {source_zone} to {target_zone}")
            
            # Step 1: Validate input data
            validation_report = self.validate_input(data)
            if not validation_report["valid"]:
                raise ValueError(f"Input validation failed: {validation_report['issues']}")
            
            # Step 2: Clean data
            cleaned_data = self.clean_data(data)
            
            # Step 3: Deduplicate based on symbol and open_time
            deduplicated_data = self.deduplicate_data(
                cleaned_data, 
                ["symbol", "open_time"]
            )
            
            # Step 4: Sort by timestamp
            sorted_data = self.sort_by_timestamp(deduplicated_data, "open_time")
            
            # Step 5: Add derived columns
            enriched_data = self._add_derived_metrics(sorted_data)
            
            # Step 6: Add technical indicators
            technical_data = self._add_technical_indicators(enriched_data)
            
            # Step 7: Add processing metadata
            final_data = self.add_processing_metadata(technical_data)
            
            # Step 8: Final validation
            final_validation = self._validate_processed_data(final_data)
            if not final_validation["valid"]:
                self.logger.warning(f"Processed data validation issues: {final_validation['issues']}")
            
            self.logger.info(f"Successfully processed {len(final_data)} kline records")
            return final_data
            
        except Exception as e:
            self.logger.error(f"Kline processing failed: {e}")
            raise
    
    def _add_derived_metrics(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add derived metrics to kline data.
        
        Args:
            data: Input kline data
            
        Returns:
            Data with derived metrics added
        """
        try:
            return data.with_columns([
                # Price-based metrics
                (pl.col("high_price") - pl.col("low_price")).alias("price_range"),
                (pl.col("close_price") - pl.col("open_price")).alias("price_change"),
                ((pl.col("close_price") - pl.col("open_price")) / pl.col("open_price") * 100).alias("price_change_pct"),
                
                # Volume-based metrics
                (pl.col("quote_asset_volume") / pl.col("volume")).alias("avg_price"),
                (pl.col("volume") / pl.col("number_of_trades")).alias("avg_trade_size"),
                
                # Time-based metrics
                (pl.col("close_time") - pl.col("open_time")).dt.total_milliseconds().alias("duration_ms"),
                
                # Volatility metrics
                ((pl.col("high_price") - pl.col("low_price")) / pl.col("open_price") * 100).alias("volatility_pct"),
                
                # Body and wick metrics for candlestick analysis
                pl.when(pl.col("close_price") >= pl.col("open_price"))
                .then(pl.col("close_price") - pl.col("open_price"))
                .otherwise(pl.col("open_price") - pl.col("close_price"))
                .alias("body_size"),
                
                pl.when(pl.col("close_price") >= pl.col("open_price"))
                .then(pl.lit("bullish"))
                .otherwise(pl.lit("bearish"))
                .alias("candle_type"),
                
                # Upper and lower wicks
                pl.when(pl.col("close_price") >= pl.col("open_price"))
                .then(pl.col("high_price") - pl.col("close_price"))
                .otherwise(pl.col("high_price") - pl.col("open_price"))
                .alias("upper_wick"),
                
                pl.when(pl.col("close_price") >= pl.col("open_price"))
                .then(pl.col("open_price") - pl.col("low_price"))
                .otherwise(pl.col("close_price") - pl.col("low_price"))
                .alias("lower_wick")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to add derived metrics: {e}")
            raise
    
    def _add_technical_indicators(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add technical indicators to kline data.
        
        Args:
            data: Input kline data
            
        Returns:
            Data with technical indicators added
        """
        try:
            # Sort by symbol and time for proper indicator calculation
            sorted_data = data.sort(["symbol", "open_time"])
            
            # Add moving averages and other indicators
            return sorted_data.with_columns([
                # Simple Moving Averages
                pl.col("close_price").rolling_mean(window_size=7).over("symbol").alias("sma_7"),
                pl.col("close_price").rolling_mean(window_size=14).over("symbol").alias("sma_14"),
                pl.col("close_price").rolling_mean(window_size=30).over("symbol").alias("sma_30"),
                
                # Volume Moving Average
                pl.col("volume").rolling_mean(window_size=14).over("symbol").alias("volume_ma_14"),
                
                # Price volatility (rolling standard deviation)
                pl.col("close_price").rolling_std(window_size=14).over("symbol").alias("price_volatility_14"),
                
                # Volume-weighted average price (VWAP) approximation
                ((pl.col("high_price") + pl.col("low_price") + pl.col("close_price")) / 3 * pl.col("volume"))
                .rolling_sum(window_size=14).over("symbol")
                .truediv(pl.col("volume").rolling_sum(window_size=14).over("symbol"))
                .alias("vwap_14"),
                
                # Relative Strength Index (RSI) components
                pl.col("price_change")
                .map_elements(lambda x: max(x, 0), return_dtype=pl.Float64)
                .rolling_mean(window_size=14).over("symbol")
                .alias("avg_gain_14"),
                
                pl.col("price_change")
                .map_elements(lambda x: abs(min(x, 0)), return_dtype=pl.Float64)
                .rolling_mean(window_size=14).over("symbol")
                .alias("avg_loss_14"),
            ]).with_columns([
                # Calculate RSI
                pl.when(pl.col("avg_loss_14") == 0)
                .then(100)
                .otherwise(100 - (100 / (1 + pl.col("avg_gain_14") / pl.col("avg_loss_14"))))
                .alias("rsi_14")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to add technical indicators: {e}")
            # Return original data if indicator calculation fails
            return data
    
    def _validate_processed_data(self, data: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate the final processed data.
        
        Args:
            data: Processed kline data
            
        Returns:
            Validation report
        """
        validation_report = {
            "valid": True,
            "issues": [],
            "metrics": {}
        }
        
        try:
            # Check for required columns after processing
            required_final_columns = self.get_required_columns() + [
                "price_range", "price_change", "price_change_pct", 
                "processed_at", "processor_name"
            ]
            
            missing_columns = [col for col in required_final_columns if col not in data.columns]
            if missing_columns:
                validation_report["issues"].append(f"Missing processed columns: {missing_columns}")
            
            # Check for null values in critical derived columns
            critical_derived = ["price_range", "price_change", "avg_price"]
            for col in critical_derived:
                if col in data.columns:
                    null_count = data[col].null_count()
                    if null_count > 0:
                        validation_report["issues"].append(f"Null values in derived column {col}: {null_count}")
            
            # Calculate processing metrics
            validation_report["metrics"] = {
                "total_records": len(data),
                "columns_count": len(data.columns),
                "symbols_count": data["symbol"].n_unique() if "symbol" in data.columns else 0,
                "date_range": {
                    "min_time": data["open_time"].min() if "open_time" in data.columns else None,
                    "max_time": data["open_time"].max() if "open_time" in data.columns else None
                }
            }
            
            # Mark as invalid if there are issues
            if validation_report["issues"]:
                validation_report["valid"] = False
            
            return validation_report
            
        except Exception as e:
            self.logger.error(f"Final validation failed: {e}")
            validation_report["valid"] = False
            validation_report["issues"].append(f"Validation error: {e}")
            return validation_report