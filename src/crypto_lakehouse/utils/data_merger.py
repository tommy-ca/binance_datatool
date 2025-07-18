"""
Data merger for combining bulk and incremental data sources.

This module provides intelligent data merging capabilities with overlap detection,
deduplication, and conflict resolution for the crypto data lakehouse.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple, Set
from enum import Enum
import hashlib

import polars as pl
from pydantic import BaseModel, Field, validator

from ..core.models import KlineData, FundingRateData, DataType

logger = logging.getLogger(__name__)


class MergeStrategy(str, Enum):
    """Strategies for merging overlapping data."""
    
    BULK_PRIORITY = "bulk_priority"          # Prefer bulk data over incremental
    INCREMENTAL_PRIORITY = "incremental_priority"  # Prefer incremental over bulk
    LATEST_TIMESTAMP = "latest_timestamp"    # Use data with latest timestamp
    DATA_QUALITY = "data_quality"           # Use data with better quality metrics
    MANUAL = "manual"                       # Manual conflict resolution required


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    
    SKIP = "skip"                           # Skip conflicting records
    OVERWRITE = "overwrite"                 # Overwrite with new data
    MERGE = "merge"                         # Merge fields intelligently
    FAIL = "fail"                           # Fail on conflicts


class MergeConfig(BaseModel):
    """Configuration for data merging operations."""
    
    merge_strategy: MergeStrategy = Field(
        default=MergeStrategy.BULK_PRIORITY,
        description="Strategy for handling overlapping data"
    )
    conflict_resolution: ConflictResolution = Field(
        default=ConflictResolution.OVERWRITE,
        description="How to resolve data conflicts"
    )
    tolerance_ms: int = Field(
        default=1000,
        description="Tolerance in milliseconds for timestamp matching"
    )
    enable_deduplication: bool = Field(
        default=True,
        description="Enable automatic deduplication"
    )
    enable_validation: bool = Field(
        default=True,
        description="Enable data quality validation"
    )
    max_gap_minutes: int = Field(
        default=60,
        description="Maximum gap in minutes to consider for merging"
    )
    
    @validator("tolerance_ms")
    def validate_tolerance(cls, v):
        if v < 0:
            raise ValueError("Tolerance must be non-negative")
        return v


class MergeResult(BaseModel):
    """Result of a data merge operation."""
    
    symbol: str
    data_type: DataType
    total_input_records: int
    bulk_records: int
    incremental_records: int
    merged_records: int
    duplicates_removed: int
    conflicts_resolved: int
    gaps_detected: int
    merge_strategy_used: MergeStrategy
    processing_time_ms: int
    quality_score: float = Field(description="Data quality score 0-1")
    
    
class DataOverlap(BaseModel):
    """Information about data overlap between sources."""
    
    start_time: datetime
    end_time: datetime
    bulk_records: int
    incremental_records: int
    overlap_type: str  # "complete", "partial", "none"
    conflict_count: int


class DataMerger:
    """
    Intelligent data merger for combining bulk and incremental data sources.
    
    Handles overlapping data, deduplication, and conflict resolution with
    configurable strategies for different data quality requirements.
    """
    
    def __init__(self, config: MergeConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.DataMerger")
        
    def merge_kline_data(
        self,
        bulk_data: List[KlineData],
        incremental_data: List[KlineData],
        symbol: str
    ) -> MergeResult:
        """
        Merge K-line data from bulk and incremental sources.
        
        Args:
            bulk_data: K-line data from bulk source
            incremental_data: K-line data from incremental source
            symbol: Trading symbol
            
        Returns:
            MergeResult with merged data and statistics
        """
        start_time = datetime.now()
        
        # Convert to DataFrames for efficient processing
        bulk_df = self._klines_to_df(bulk_data, "bulk")
        incremental_df = self._klines_to_df(incremental_data, "incremental")
        
        # Detect overlaps
        overlap_info = self._detect_overlaps(bulk_df, incremental_df)
        
        # Merge data based on strategy
        merged_df = self._merge_dataframes(bulk_df, incremental_df, overlap_info)
        
        # Apply deduplication if enabled
        if self.config.enable_deduplication:
            merged_df, duplicates_removed = self._deduplicate_data(merged_df)
        else:
            duplicates_removed = 0
        
        # Validate data quality if enabled
        if self.config.enable_validation:
            merged_df, quality_score = self._validate_data_quality(merged_df)
        else:
            quality_score = 1.0
        
        # Calculate processing time
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return MergeResult(
            symbol=symbol,
            data_type=DataType.KLINE,
            total_input_records=len(bulk_data) + len(incremental_data),
            bulk_records=len(bulk_data),
            incremental_records=len(incremental_data),
            merged_records=len(merged_df),
            duplicates_removed=duplicates_removed,
            conflicts_resolved=overlap_info.conflict_count,
            gaps_detected=self._count_gaps(merged_df),
            merge_strategy_used=self.config.merge_strategy,
            processing_time_ms=processing_time,
            quality_score=quality_score
        )
    
    def merge_funding_rate_data(
        self,
        bulk_data: List[FundingRateData],
        incremental_data: List[FundingRateData],
        symbol: str
    ) -> MergeResult:
        """
        Merge funding rate data from bulk and incremental sources.
        
        Args:
            bulk_data: Funding rate data from bulk source
            incremental_data: Funding rate data from incremental source
            symbol: Trading symbol
            
        Returns:
            MergeResult with merged data and statistics
        """
        start_time = datetime.now()
        
        # Convert to DataFrames
        bulk_df = self._funding_rates_to_df(bulk_data, "bulk")
        incremental_df = self._funding_rates_to_df(incremental_data, "incremental")
        
        # Detect overlaps
        overlap_info = self._detect_overlaps(bulk_df, incremental_df)
        
        # Merge data
        merged_df = self._merge_dataframes(bulk_df, incremental_df, overlap_info)
        
        # Apply deduplication
        if self.config.enable_deduplication:
            merged_df, duplicates_removed = self._deduplicate_data(merged_df)
        else:
            duplicates_removed = 0
        
        # Validate data quality
        if self.config.enable_validation:
            merged_df, quality_score = self._validate_data_quality(merged_df)
        else:
            quality_score = 1.0
        
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        return MergeResult(
            symbol=symbol,
            data_type=DataType.FUNDING_RATE,
            total_input_records=len(bulk_data) + len(incremental_data),
            bulk_records=len(bulk_data),
            incremental_records=len(incremental_data),
            merged_records=len(merged_df),
            duplicates_removed=duplicates_removed,
            conflicts_resolved=overlap_info.conflict_count,
            gaps_detected=self._count_gaps(merged_df),
            merge_strategy_used=self.config.merge_strategy,
            processing_time_ms=processing_time,
            quality_score=quality_score
        )
    
    def _klines_to_df(self, klines: List[KlineData], source: str) -> pl.DataFrame:
        """Convert K-line data to Polars DataFrame."""
        if not klines:
            return pl.DataFrame()
        
        records = []
        for kline in klines:
            records.append({
                "symbol": kline.symbol,
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
                "source": source,
                "record_hash": self._calculate_record_hash(kline)
            })
        
        return pl.DataFrame(records)
    
    def _funding_rates_to_df(self, funding_rates: List[FundingRateData], source: str) -> pl.DataFrame:
        """Convert funding rate data to Polars DataFrame."""
        if not funding_rates:
            return pl.DataFrame()
        
        records = []
        for rate in funding_rates:
            records.append({
                "symbol": rate.symbol,
                "funding_time": rate.funding_time,
                "funding_rate": float(rate.funding_rate),
                "mark_price": float(rate.mark_price),
                "source": source,
                "record_hash": self._calculate_funding_rate_hash(rate)
            })
        
        return pl.DataFrame(records)
    
    def _detect_overlaps(self, bulk_df: pl.DataFrame, incremental_df: pl.DataFrame) -> DataOverlap:
        """Detect overlapping data between bulk and incremental sources."""
        if bulk_df.is_empty() or incremental_df.is_empty():
            return DataOverlap(
                start_time=datetime.min,
                end_time=datetime.min,
                bulk_records=len(bulk_df),
                incremental_records=len(incremental_df),
                overlap_type="none",
                conflict_count=0
            )
        
        # Get time ranges
        bulk_start = bulk_df.select(pl.col("open_time").min()).item()
        bulk_end = bulk_df.select(pl.col("open_time").max()).item()
        inc_start = incremental_df.select(pl.col("open_time").min()).item()
        inc_end = incremental_df.select(pl.col("open_time").max()).item()
        
        # Determine overlap
        overlap_start = max(bulk_start, inc_start)
        overlap_end = min(bulk_end, inc_end)
        
        if overlap_start <= overlap_end:
            # Filter to overlap period
            bulk_overlap = bulk_df.filter(
                (pl.col("open_time") >= overlap_start) & 
                (pl.col("open_time") <= overlap_end)
            )
            inc_overlap = incremental_df.filter(
                (pl.col("open_time") >= overlap_start) & 
                (pl.col("open_time") <= overlap_end)
            )
            
            # Count potential conflicts
            conflict_count = self._count_conflicts(bulk_overlap, inc_overlap)
            
            if bulk_start <= inc_start <= bulk_end and bulk_start <= inc_end <= bulk_end:
                overlap_type = "complete"
            else:
                overlap_type = "partial"
        else:
            overlap_type = "none"
            conflict_count = 0
        
        return DataOverlap(
            start_time=overlap_start,
            end_time=overlap_end,
            bulk_records=len(bulk_df),
            incremental_records=len(incremental_df),
            overlap_type=overlap_type,
            conflict_count=conflict_count
        )
    
    def _merge_dataframes(
        self, 
        bulk_df: pl.DataFrame, 
        incremental_df: pl.DataFrame, 
        overlap_info: DataOverlap
    ) -> pl.DataFrame:
        """Merge DataFrames based on configured strategy."""
        if bulk_df.is_empty():
            return incremental_df
        if incremental_df.is_empty():
            return bulk_df
        
        # Combine all data
        combined_df = pl.concat([bulk_df, incremental_df])
        
        # Apply merge strategy
        if self.config.merge_strategy == MergeStrategy.BULK_PRIORITY:
            # Keep bulk data, fill gaps with incremental
            merged_df = self._merge_bulk_priority(bulk_df, incremental_df)
        elif self.config.merge_strategy == MergeStrategy.INCREMENTAL_PRIORITY:
            # Keep incremental data, fill gaps with bulk
            merged_df = self._merge_incremental_priority(bulk_df, incremental_df)
        elif self.config.merge_strategy == MergeStrategy.LATEST_TIMESTAMP:
            # Use most recent data
            merged_df = self._merge_latest_timestamp(combined_df)
        elif self.config.merge_strategy == MergeStrategy.DATA_QUALITY:
            # Use best quality data
            merged_df = self._merge_data_quality(combined_df)
        else:
            # Default to bulk priority
            merged_df = self._merge_bulk_priority(bulk_df, incremental_df)
        
        # Sort by timestamp
        if "open_time" in merged_df.columns:
            merged_df = merged_df.sort("open_time")
        elif "funding_time" in merged_df.columns:
            merged_df = merged_df.sort("funding_time")
        
        return merged_df
    
    def _merge_bulk_priority(self, bulk_df: pl.DataFrame, incremental_df: pl.DataFrame) -> pl.DataFrame:
        """Merge with bulk data priority."""
        # Start with bulk data
        merged_df = bulk_df.clone()
        
        # Add incremental data for timestamps not in bulk
        time_col = "open_time" if "open_time" in bulk_df.columns else "funding_time"
        
        if not incremental_df.is_empty():
            bulk_times = set(bulk_df.select(time_col).to_series())
            incremental_new = incremental_df.filter(
                ~pl.col(time_col).is_in(bulk_times)
            )
            
            if not incremental_new.is_empty():
                merged_df = pl.concat([merged_df, incremental_new])
        
        return merged_df
    
    def _merge_incremental_priority(self, bulk_df: pl.DataFrame, incremental_df: pl.DataFrame) -> pl.DataFrame:
        """Merge with incremental data priority."""
        # Start with incremental data
        merged_df = incremental_df.clone()
        
        # Add bulk data for timestamps not in incremental
        time_col = "open_time" if "open_time" in incremental_df.columns else "funding_time"
        
        if not bulk_df.is_empty():
            inc_times = set(incremental_df.select(time_col).to_series())
            bulk_new = bulk_df.filter(
                ~pl.col(time_col).is_in(inc_times)
            )
            
            if not bulk_new.is_empty():
                merged_df = pl.concat([merged_df, bulk_new])
        
        return merged_df
    
    def _merge_latest_timestamp(self, combined_df: pl.DataFrame) -> pl.DataFrame:
        """Merge keeping latest timestamp for each record."""
        time_col = "open_time" if "open_time" in combined_df.columns else "funding_time"
        
        # Group by timestamp and keep latest
        return combined_df.group_by(time_col).agg(pl.all().last())
    
    def _merge_data_quality(self, combined_df: pl.DataFrame) -> pl.DataFrame:
        """Merge based on data quality metrics."""
        # Simple quality scoring based on completeness
        quality_scored = combined_df.with_columns([
            pl.when(pl.col("source") == "bulk")
            .then(0.8)  # Bulk data gets 0.8 quality score
            .otherwise(0.9)  # Incremental gets 0.9 (assumed more recent)
            .alias("quality_score")
        ])
        
        time_col = "open_time" if "open_time" in combined_df.columns else "funding_time"
        
        # Group by timestamp and keep highest quality
        return quality_scored.group_by(time_col).agg(
            pl.all().sort_by("quality_score", descending=True).first()
        )
    
    def _deduplicate_data(self, df: pl.DataFrame) -> Tuple[pl.DataFrame, int]:
        """Remove duplicate records based on hash."""
        if df.is_empty():
            return df, 0
        
        original_count = len(df)
        deduplicated = df.unique(subset=["record_hash"])
        duplicates_removed = original_count - len(deduplicated)
        
        return deduplicated, duplicates_removed
    
    def _validate_data_quality(self, df: pl.DataFrame) -> Tuple[pl.DataFrame, float]:
        """Validate data quality and return quality score."""
        if df.is_empty():
            return df, 1.0
        
        # Calculate quality score based on various metrics
        quality_score = 1.0
        
        # Check for missing values
        if "open_price" in df.columns:
            null_count = df.null_count().sum_horizontal().sum()
            total_cells = len(df) * len(df.columns)
            quality_score *= (1 - null_count / total_cells) if total_cells > 0 else 1.0
        
        # Check for unrealistic values
        if "volume" in df.columns:
            negative_volume = df.filter(pl.col("volume") < 0).shape[0]
            quality_score *= (1 - negative_volume / len(df)) if len(df) > 0 else 1.0
        
        # Additional quality checks can be added here
        
        return df, max(quality_score, 0.0)
    
    def _count_conflicts(self, bulk_df: pl.DataFrame, incremental_df: pl.DataFrame) -> int:
        """Count potential conflicts between bulk and incremental data."""
        if bulk_df.is_empty() or incremental_df.is_empty():
            return 0
        
        time_col = "open_time" if "open_time" in bulk_df.columns else "funding_time"
        
        # Find overlapping timestamps
        bulk_times = set(bulk_df.select(time_col).to_series())
        inc_times = set(incremental_df.select(time_col).to_series())
        
        return len(bulk_times.intersection(inc_times))
    
    def _count_gaps(self, df: pl.DataFrame) -> int:
        """Count gaps in the merged data."""
        if df.is_empty():
            return 0
        
        time_col = "open_time" if "open_time" in df.columns else "funding_time"
        
        # Simple gap detection - count missing consecutive periods
        # This is a simplified implementation
        sorted_df = df.sort(time_col)
        times = sorted_df.select(time_col).to_series()
        
        gaps = 0
        for i in range(1, len(times)):
            time_diff = (times[i] - times[i-1]).total_seconds() / 60  # minutes
            if time_diff > self.config.max_gap_minutes:
                gaps += 1
        
        return gaps
    
    def _calculate_record_hash(self, kline: KlineData) -> str:
        """Calculate hash for K-line record."""
        content = f"{kline.symbol}_{kline.open_time}_{kline.open_price}_{kline.close_price}_{kline.volume}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _calculate_funding_rate_hash(self, rate: FundingRateData) -> str:
        """Calculate hash for funding rate record."""
        content = f"{rate.symbol}_{rate.funding_time}_{rate.funding_rate}_{rate.mark_price}"
        return hashlib.md5(content.encode()).hexdigest()


def merge_data(
    bulk_data: List[Any],
    incremental_data: List[Any],
    symbol: str,
    data_type: DataType,
    config: Optional[MergeConfig] = None
) -> MergeResult:
    """
    Convenience function to merge data.
    
    Args:
        bulk_data: Data from bulk source
        incremental_data: Data from incremental source
        symbol: Trading symbol
        data_type: Type of data being merged
        config: Optional merge configuration
        
    Returns:
        MergeResult with merged data and statistics
    """
    if config is None:
        config = MergeConfig()
    
    merger = DataMerger(config)
    
    if data_type == DataType.KLINE:
        return merger.merge_kline_data(bulk_data, incremental_data, symbol)
    elif data_type == DataType.FUNDING_RATE:
        return merger.merge_funding_rate_data(bulk_data, incremental_data, symbol)
    else:
        raise ValueError(f"Unsupported data type: {data_type}")


def get_merge_strategies() -> List[MergeStrategy]:
    """Get list of available merge strategies."""
    return list(MergeStrategy)