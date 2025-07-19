"""
Base processor class for data transformation between lakehouse zones.

This module provides the abstract base class and common functionality for all
data processors in the cryptocurrency lakehouse platform.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl

from ..core.config import Settings
from ..core.models import DataType, DataZone, Exchange, TradeType

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """
    Abstract base class for data processors.
    
    Data processors are responsible for transforming data between different zones
    in the lakehouse architecture (Bronze -> Silver -> Gold).
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the processor with configuration settings.
        
        Args:
            settings: Configuration settings for the processor
        """
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def process(
        self, 
        data: pl.DataFrame, 
        source_zone: DataZone, 
        target_zone: DataZone,
        **kwargs
    ) -> pl.DataFrame:
        """
        Process data from source zone to target zone format.
        
        Args:
            data: Input data to process
            source_zone: Source lakehouse zone (e.g., BRONZE)
            target_zone: Target lakehouse zone (e.g., SILVER)
            **kwargs: Additional processing parameters
            
        Returns:
            Processed data ready for target zone
        """
        pass
    
    @abstractmethod
    def validate_input(self, data: pl.DataFrame) -> Dict[str, Any]:
        """
        Validate input data structure and quality.
        
        Args:
            data: Input data to validate
            
        Returns:
            Validation report with status and issues
        """
        pass
    
    @abstractmethod
    def get_required_columns(self) -> List[str]:
        """
        Get list of required columns for this processor.
        
        Returns:
            List of required column names
        """
        pass
    
    def clean_data(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Perform common data cleaning operations.
        
        Args:
            data: Input data to clean
            
        Returns:
            Cleaned data
        """
        try:
            # Remove completely null rows
            cleaned_data = data.filter(~pl.all_horizontal(pl.all().is_null()))
            
            # Log cleaning statistics
            original_count = len(data)
            cleaned_count = len(cleaned_data)
            
            if original_count != cleaned_count:
                self.logger.info(f"Removed {original_count - cleaned_count} null rows")
            
            return cleaned_data
            
        except Exception as e:
            self.logger.error(f"Data cleaning failed: {e}")
            raise
    
    def add_processing_metadata(self, data: pl.DataFrame) -> pl.DataFrame:
        """
        Add processing metadata to the data.
        
        Args:
            data: Input data
            
        Returns:
            Data with processing metadata added
        """
        try:
            current_time = datetime.now()
            
            return data.with_columns([
                pl.lit(current_time).alias("processed_at"),
                pl.lit(self.__class__.__name__).alias("processor_name"),
                pl.lit("2.0.0").alias("processor_version")
            ])
            
        except Exception as e:
            self.logger.error(f"Failed to add processing metadata: {e}")
            raise
    
    def deduplicate_data(self, data: pl.DataFrame, key_columns: List[str]) -> pl.DataFrame:
        """
        Remove duplicate records based on key columns.
        
        Args:
            data: Input data
            key_columns: Columns to use for deduplication
            
        Returns:
            Deduplicated data
        """
        try:
            # Check if key columns exist
            missing_columns = [col for col in key_columns if col not in data.columns]
            if missing_columns:
                self.logger.warning(f"Key columns not found: {missing_columns}")
                return data
            
            original_count = len(data)
            deduplicated_data = data.unique(subset=key_columns, keep="last")
            deduplicated_count = len(deduplicated_data)
            
            if original_count != deduplicated_count:
                self.logger.info(f"Removed {original_count - deduplicated_count} duplicate records")
            
            return deduplicated_data
            
        except Exception as e:
            self.logger.error(f"Deduplication failed: {e}")
            raise
    
    def validate_numeric_columns(self, data: pl.DataFrame, numeric_columns: List[str]) -> Dict[str, Any]:
        """
        Validate numeric columns for reasonable values.
        
        Args:
            data: Input data
            numeric_columns: List of numeric columns to validate
            
        Returns:
            Validation report
        """
        validation_report = {
            "valid": True,
            "issues": [],
            "statistics": {}
        }
        
        try:
            for col in numeric_columns:
                if col in data.columns:
                    # Check for negative values where they shouldn't exist
                    if col in ["volume", "quote_asset_volume", "number_of_trades"]:
                        negative_count = data.filter(pl.col(col) < 0).height
                        if negative_count > 0:
                            validation_report["valid"] = False
                            validation_report["issues"].append(f"Negative values in {col}: {negative_count}")
                    
                    # Check for extremely large values (possible data corruption)
                    if col.endswith("_price"):
                        max_value = data[col].max()
                        if max_value and max_value > 1000000:  # Arbitrary large value threshold
                            validation_report["issues"].append(f"Extremely large price in {col}: {max_value}")
                    
                    # Collect statistics
                    validation_report["statistics"][col] = {
                        "min": data[col].min(),
                        "max": data[col].max(),
                        "mean": data[col].mean(),
                        "null_count": data[col].null_count()
                    }
            
            return validation_report
            
        except Exception as e:
            self.logger.error(f"Numeric validation failed: {e}")
            validation_report["valid"] = False
            validation_report["issues"].append(f"Validation error: {e}")
            return validation_report
    
    def sort_by_timestamp(self, data: pl.DataFrame, timestamp_column: str) -> pl.DataFrame:
        """
        Sort data by timestamp column.
        
        Args:
            data: Input data
            timestamp_column: Name of timestamp column
            
        Returns:
            Sorted data
        """
        try:
            if timestamp_column in data.columns:
                return data.sort(timestamp_column)
            else:
                self.logger.warning(f"Timestamp column not found: {timestamp_column}")
                return data
                
        except Exception as e:
            self.logger.error(f"Sorting failed: {e}")
            raise
    
    def calculate_processing_metrics(self, input_data: pl.DataFrame, output_data: pl.DataFrame) -> Dict[str, Any]:
        """
        Calculate metrics about the processing operation.
        
        Args:
            input_data: Original input data
            output_data: Processed output data
            
        Returns:
            Processing metrics
        """
        return {
            "input_records": len(input_data),
            "output_records": len(output_data),
            "records_change": len(output_data) - len(input_data),
            "processing_efficiency": len(output_data) / len(input_data) if len(input_data) > 0 else 0,
            "input_columns": len(input_data.columns),
            "output_columns": len(output_data.columns),
            "columns_added": len(output_data.columns) - len(input_data.columns)
        }