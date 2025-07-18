"""Base data processing classes."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import polars as pl
import logging
from datetime import datetime

from ..core.models import DataZone, DataType, TradeType, Exchange
from ..core.config import Settings

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """Abstract base class for data processors."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def process(
        self,
        data: pl.DataFrame,
        source_zone: DataZone,
        target_zone: DataZone,
        **kwargs
    ) -> pl.DataFrame:
        """Process data from source to target zone."""
        pass
    
    @abstractmethod
    def get_schema(self, zone: DataZone) -> pl.Schema:
        """Get expected schema for the data in a specific zone."""
        pass
    
    def validate_schema(self, data: pl.DataFrame, expected_schema: pl.Schema) -> bool:
        """Validate DataFrame schema against expected schema."""
        try:
            data_columns = set(data.columns)
            expected_columns = set(expected_schema.keys())
            
            missing_columns = expected_columns - data_columns
            if missing_columns:
                self.logger.error(f"Missing required columns: {missing_columns}")
                return False
            
            # Check data types for key columns
            for col_name, expected_type in expected_schema.items():
                if col_name in data.columns:
                    actual_type = data[col_name].dtype
                    if not self._is_compatible_type(actual_type, expected_type):
                        self.logger.warning(
                            f"Column {col_name} type mismatch: {actual_type} vs {expected_type}"
                        )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Schema validation failed: {e}")
            return False
    
    def _is_compatible_type(self, actual: pl.DataType, expected: pl.DataType) -> bool:
        """Check if data types are compatible."""
        # Simplified type compatibility check
        if actual == expected:
            return True
        
        # Allow some flexibility for numeric types
        numeric_types = {pl.Int32, pl.Int64, pl.Float32, pl.Float64}
        if actual in numeric_types and expected in numeric_types:
            return True
        
        return False
    
    async def add_processing_metadata(
        self, 
        data: pl.DataFrame, 
        processing_time: datetime,
        source_zone: DataZone,
        target_zone: DataZone
    ) -> pl.DataFrame:
        """Add metadata columns for tracking data lineage."""
        return data.with_columns([
            pl.lit(processing_time).alias("_processed_at"),
            pl.lit(source_zone.value).alias("_source_zone"),
            pl.lit(target_zone.value).alias("_target_zone"),
            pl.lit("2.0.0").alias("_processor_version")
        ])
    
    async def validate_data_quality(self, data: pl.DataFrame) -> Dict[str, Any]:
        """Perform basic data quality checks."""
        try:
            quality_report = {
                "total_rows": data.shape[0],
                "total_columns": data.shape[1],
                "null_counts": {},
                "duplicate_rows": 0,
                "data_types": {},
                "quality_score": 1.0
            }
            
            # Count nulls per column
            for col in data.columns:
                null_count = data[col].null_count()
                quality_report["null_counts"][col] = null_count
                quality_report["data_types"][col] = str(data[col].dtype)
            
            # Count duplicate rows
            quality_report["duplicate_rows"] = data.shape[0] - data.unique().shape[0]
            
            # Calculate quality score (simple heuristic)
            total_nulls = sum(quality_report["null_counts"].values())
            total_cells = data.shape[0] * data.shape[1]
            
            if total_cells > 0:
                null_ratio = total_nulls / total_cells
                duplicate_ratio = quality_report["duplicate_rows"] / data.shape[0]
                quality_report["quality_score"] = max(0, 1.0 - null_ratio - duplicate_ratio)
            
            return quality_report
            
        except Exception as e:
            self.logger.error(f"Data quality validation failed: {e}")
            return {"error": str(e), "quality_score": 0.0}


class BatchProcessor(BaseProcessor):
    """Base class for batch data processing."""
    
    async def process_in_batches(
        self,
        data: pl.DataFrame,
        batch_size: Optional[int] = None,
        **kwargs
    ) -> pl.DataFrame:
        """Process large datasets in batches."""
        if batch_size is None:
            batch_size = self.settings.processing.batch_size
        
        if data.shape[0] <= batch_size:
            return await self.process(data, **kwargs)
        
        results = []
        total_rows = data.shape[0]
        
        for i in range(0, total_rows, batch_size):
            batch = data.slice(i, batch_size)
            self.logger.info(f"Processing batch {i//batch_size + 1}/{(total_rows + batch_size - 1)//batch_size}")
            
            processed_batch = await self.process(batch, **kwargs)
            results.append(processed_batch)
        
        return pl.concat(results)


class StreamProcessor(BaseProcessor):
    """Base class for streaming data processing."""
    
    async def process_stream(
        self,
        data_stream,
        **kwargs
    ):
        """Process streaming data."""
        # Implementation depends on streaming framework
        raise NotImplementedError("Streaming processing not implemented yet")