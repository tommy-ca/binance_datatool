"""
Funding rate data processor for Silver layer transformation.

This module processes raw funding rate data from the Bronze zone, applying cleaning,
validation, and enrichment for storage in the Silver zone.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl

from ..core.models import DataZone
from .base import BaseProcessor

logger = logging.getLogger(__name__)


class FundingRateProcessor(BaseProcessor):
    """
    Processor for funding rate data transformation.
    
    Transforms raw funding rate data from Bronze zone into clean, validated, and enriched
    data for Silver zone storage with derived metrics and historical analysis.
    """
    
    def get_required_columns(self) -> List[str]:
        """Get required columns for funding rate processing."""
        return [
            "symbol",
            "funding_time",
            "funding_rate",
            "mark_price"
        ]
    
    def validate_input(self, data: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate input funding rate data structure and quality.
        
        Args:
            data: Input funding rate data
            
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
            
            # Validate numeric columns
            numeric_columns = ["funding_rate", "mark_price"]
            numeric_validation = self.validate_numeric_columns(data, numeric_columns)
            
            if not numeric_validation["valid"]:
                validation_report["valid"] = False
                validation_report["issues"].extend(numeric_validation["issues"])
            
            validation_report["data_quality"] = numeric_validation["statistics"]
            
            # Check funding rate ranges (typical range is -0.75% to +0.75%)
            if "funding_rate" in data.columns:
                extreme_rates = data.filter(
                    (pl.col("funding_rate") > 0.0075) | (pl.col("funding_rate") < -0.0075)
                ).height
                
                if extreme_rates > 0:
                    validation_report["issues"].append(f"Extreme funding rates detected: {extreme_rates} records")
            
            # Check mark price validity
            if "mark_price" in data.columns:
                invalid_prices = data.filter(pl.col("mark_price") <= 0).height
                if invalid_prices > 0:
                    validation_report["valid"] = False
                    validation_report["issues"].append(f"Invalid mark prices (<=0): {invalid_prices} records")
            
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
        Process funding rate data from Bronze to Silver zone.
        
        Args:
            data: Input funding rate data
            source_zone: Source zone (typically BRONZE)
            target_zone: Target zone (typically SILVER)
            **kwargs: Additional processing parameters
            
        Returns:
            Processed funding rate data with enrichments
        """
        try:
            self.logger.info(f"Processing {len(data)} funding rate records from {source_zone} to {target_zone}")
            
            # Step 1: Validate input data
            validation_report = self.validate_input(data)
            if not validation_report["valid"]:
                raise ValueError(f"Input validation failed: {validation_report['issues']}")
            
            # Step 2: Clean data
            cleaned_data = self.clean_data(data)
            
            # Step 3: Deduplicate based on symbol and funding_time
            deduplicated_data = self.deduplicate_data(
                cleaned_data, 
                ["symbol", "funding_time"]
            )
            
            # Step 4: Sort by timestamp
            sorted_data = self.sort_by_timestamp(deduplicated_data, "funding_time")
            
            # Step 5: Add derived metrics
            enriched_data = self._add_derived_metrics(sorted_data)
            
            # Step 6: Add statistical indicators
            statistical_data = self._add_statistical_indicators(enriched_data)
            
            # Step 7: Add processing metadata
            final_data = self.add_processing_metadata(statistical_data)
            
            # Step 8: Final validation
            final_validation = self._validate_processed_data(final_data)
            if not final_validation["valid"]:
                self.logger.warning(f"Processed data validation issues: {final_validation['issues']}")
            
            self.logger.info(f"Successfully processed {len(final_data)} funding rate records")
            return final_data
            
        except Exception as e:
            self.logger.error(f"Funding rate processing failed: {e}")
            raise
    
    def _add_derived_metrics(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add derived metrics to funding rate data.
        
        Args:
            data: Input funding rate data
            
        Returns:
            Data with derived metrics added
        """
        try:
            return data.with_columns([
                # Convert funding rate to basis points (1% = 100 bps)
                (pl.col("funding_rate") * 10000).alias("funding_rate_bps"),
                
                # Annualized funding rate (funding occurs every 8 hours)
                (pl.col("funding_rate") * 365 * 3 * 100).alias("annualized_funding_pct"),
                
                # Funding rate category
                pl.when(pl.col("funding_rate") > 0.001)
                .then(pl.lit("high_positive"))
                .when(pl.col("funding_rate") > 0)
                .then(pl.lit("positive"))
                .when(pl.col("funding_rate") < -0.001)
                .then(pl.lit("high_negative"))
                .when(pl.col("funding_rate") < 0)
                .then(pl.lit("negative"))
                .otherwise(pl.lit("neutral"))
                .alias("funding_category"),
                
                # Absolute funding rate for volatility analysis
                pl.col("funding_rate").abs().alias("funding_rate_abs"),
                
                # Extract date components for time-based analysis
                pl.col("funding_time").dt.year().alias("year"),
                pl.col("funding_time").dt.month().alias("month"),
                pl.col("funding_time").dt.day().alias("day"),
                pl.col("funding_time").dt.hour().alias("hour"),
                pl.col("funding_time").dt.weekday().alias("weekday"),
                
                # Time-based categories
                pl.when(pl.col("funding_time").dt.hour().is_in([0, 8, 16]))
                .then(pl.lit("standard_funding"))
                .otherwise(pl.lit("off_schedule"))
                .alias("funding_schedule"),
                
                # Market regime indicator based on funding rate magnitude
                pl.when(pl.col("funding_rate").abs() > 0.005)
                .then(pl.lit("extreme"))
                .when(pl.col("funding_rate").abs() > 0.002)
                .then(pl.lit("high"))
                .when(pl.col("funding_rate").abs() > 0.0005)
                .then(pl.lit("normal"))
                .otherwise(pl.lit("low"))
                .alias("market_regime")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to add derived metrics: {e}")
            raise
    
    def _add_statistical_indicators(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add statistical indicators to funding rate data.
        
        Args:
            data: Input funding rate data
            
        Returns:
            Data with statistical indicators added
        """
        try:
            # Sort by symbol and time for proper calculation
            sorted_data = data.sort(["symbol", "funding_time"])
            
            return sorted_data.with_columns([
                # Rolling averages of funding rates
                pl.col("funding_rate").rolling_mean(window_size=7).over("symbol").alias("funding_rate_ma_7"),
                pl.col("funding_rate").rolling_mean(window_size=30).over("symbol").alias("funding_rate_ma_30"),
                pl.col("funding_rate").rolling_mean(window_size=90).over("symbol").alias("funding_rate_ma_90"),
                
                # Rolling standard deviation (volatility of funding rates)
                pl.col("funding_rate").rolling_std(window_size=30).over("symbol").alias("funding_volatility_30"),
                
                # Rolling min/max for range analysis
                pl.col("funding_rate").rolling_min(window_size=30).over("symbol").alias("funding_rate_min_30"),
                pl.col("funding_rate").rolling_max(window_size=30).over("symbol").alias("funding_rate_max_30"),
                
                # Mark price moving averages
                pl.col("mark_price").rolling_mean(window_size=7).over("symbol").alias("mark_price_ma_7"),
                pl.col("mark_price").rolling_mean(window_size=30).over("symbol").alias("mark_price_ma_30"),
                
                # Mark price volatility
                pl.col("mark_price").rolling_std(window_size=30).over("symbol").alias("mark_price_volatility_30"),
                
                # Funding rate change from previous period
                (pl.col("funding_rate") - pl.col("funding_rate").shift(1, fill_value=0))
                .over("symbol")
                .alias("funding_rate_change"),
                
                # Cumulative funding over periods
                pl.col("funding_rate").cumsum().over("symbol").alias("cumulative_funding"),
                
                # Percentile rankings within symbol
                pl.col("funding_rate").rank(method="average").over("symbol").alias("funding_rate_rank"),
                
            ]).with_columns([
                # Derived indicators from rolling calculations
                (pl.col("funding_rate_max_30") - pl.col("funding_rate_min_30")).alias("funding_rate_range_30"),
                
                # Z-score for funding rate (standardized)
                ((pl.col("funding_rate") - pl.col("funding_rate_ma_30")) / pl.col("funding_volatility_30"))
                .alias("funding_rate_zscore"),
                
                # Relative position in recent range
                ((pl.col("funding_rate") - pl.col("funding_rate_min_30")) / 
                 (pl.col("funding_rate_max_30") - pl.col("funding_rate_min_30")))
                .alias("funding_rate_position"),
                
                # Mark price momentum
                ((pl.col("mark_price") - pl.col("mark_price_ma_7")) / pl.col("mark_price_ma_7"))
                .alias("mark_price_momentum")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to add statistical indicators: {e}")
            # Return original data if indicator calculation fails
            return data
    
    def _validate_processed_data(self, data: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate the final processed funding rate data.
        
        Args:
            data: Processed funding rate data
            
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
                "funding_rate_bps", "annualized_funding_pct", "funding_category",
                "processed_at", "processor_name"
            ]
            
            missing_columns = [col for col in required_final_columns if col not in data.columns]
            if missing_columns:
                validation_report["issues"].append(f"Missing processed columns: {missing_columns}")
            
            # Check for null values in critical derived columns
            critical_derived = ["funding_rate_bps", "annualized_funding_pct", "funding_category"]
            for col in critical_derived:
                if col in data.columns:
                    null_count = data[col].null_count()
                    if null_count > 0:
                        validation_report["issues"].append(f"Null values in derived column {col}: {null_count}")
            
            # Validate derived calculations
            if "funding_rate_bps" in data.columns and "funding_rate" in data.columns:
                # Check that basis points conversion is correct
                incorrect_conversions = data.filter(
                    pl.col("funding_rate_bps") != (pl.col("funding_rate") * 10000)
                ).height
                
                if incorrect_conversions > 0:
                    validation_report["issues"].append(f"Incorrect basis points conversion: {incorrect_conversions}")
            
            # Calculate processing metrics
            validation_report["metrics"] = {
                "total_records": len(data),
                "columns_count": len(data.columns),
                "symbols_count": data["symbol"].n_unique() if "symbol" in data.columns else 0,
                "date_range": {
                    "min_time": data["funding_time"].min() if "funding_time" in data.columns else None,
                    "max_time": data["funding_time"].max() if "funding_time" in data.columns else None
                },
                "funding_rate_stats": {
                    "min": data["funding_rate"].min() if "funding_rate" in data.columns else None,
                    "max": data["funding_rate"].max() if "funding_rate" in data.columns else None,
                    "mean": data["funding_rate"].mean() if "funding_rate" in data.columns else None,
                    "std": data["funding_rate"].std() if "funding_rate" in data.columns else None
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