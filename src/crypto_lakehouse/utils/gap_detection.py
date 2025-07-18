"""Gap detection and handling utilities."""

import polars as pl
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from ..core.models import DataType, TradeType, Interval
from ..core.config import Settings

logger = logging.getLogger(__name__)


class GapDetector:
    """Detects and handles gaps in time series data."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def detect_gaps(
        self, 
        data: pl.DataFrame, 
        interval: Interval,
        time_column: str = "open_time",
        symbol_column: str = "symbol"
    ) -> List[Dict[str, Any]]:
        """
        Detect gaps in time series data.
        
        Args:
            data: DataFrame with time series data
            interval: Expected time interval between records
            time_column: Name of the timestamp column
            symbol_column: Name of the symbol column
            
        Returns:
            List of gap information dictionaries
        """
        try:
            if len(data) == 0:
                return []
            
            # Convert interval to timedelta
            interval_delta = self._interval_to_timedelta(interval)
            
            # Sort data by symbol and time
            sorted_data = data.sort([symbol_column, time_column])
            
            gaps = []
            
            # Group by symbol and detect gaps within each symbol
            for symbol in sorted_data[symbol_column].unique():
                symbol_data = sorted_data.filter(pl.col(symbol_column) == symbol)
                symbol_gaps = self._detect_gaps_for_symbol(
                    symbol_data, symbol, interval_delta, time_column
                )
                gaps.extend(symbol_gaps)
            
            logger.info(f"Detected {len(gaps)} gaps across {len(sorted_data[symbol_column].unique())} symbols")
            return gaps
            
        except Exception as e:
            logger.error(f"Gap detection failed: {e}")
            return []
    
    def _detect_gaps_for_symbol(
        self, 
        data: pl.DataFrame, 
        symbol: str, 
        interval_delta: timedelta,
        time_column: str
    ) -> List[Dict[str, Any]]:
        """Detect gaps for a single symbol."""
        gaps = []
        
        if len(data) < 2:
            return gaps
        
        # Get sorted timestamps
        timestamps = data[time_column].sort().to_list()
        
        for i in range(1, len(timestamps)):
            current_time = timestamps[i]
            previous_time = timestamps[i-1]
            
            # Calculate expected next timestamp
            expected_time = previous_time + interval_delta
            
            # Check if there's a gap
            if current_time > expected_time:
                gap_duration = current_time - expected_time
                missing_periods = int(gap_duration / interval_delta)
                
                if missing_periods > 0:
                    gaps.append({
                        "symbol": symbol,
                        "gap_start": expected_time,
                        "gap_end": current_time,
                        "missing_periods": missing_periods,
                        "gap_duration": gap_duration,
                        "previous_timestamp": previous_time,
                        "next_timestamp": current_time
                    })
        
        return gaps
    
    def _interval_to_timedelta(self, interval: Interval) -> timedelta:
        """Convert Interval enum to timedelta."""
        interval_map = {
            Interval.MIN_1: timedelta(minutes=1),
            Interval.MIN_5: timedelta(minutes=5),
            Interval.MIN_15: timedelta(minutes=15),
            Interval.MIN_30: timedelta(minutes=30),
            Interval.HOUR_1: timedelta(hours=1),
            Interval.HOUR_4: timedelta(hours=4),
            Interval.HOUR_12: timedelta(hours=12),
            Interval.DAY_1: timedelta(days=1),
            Interval.WEEK_1: timedelta(weeks=1),
            Interval.MONTH_1: timedelta(days=30)  # Approximate
        }
        
        return interval_map.get(interval, timedelta(minutes=1))
    
    def generate_missing_timestamps(
        self, 
        gaps: List[Dict[str, Any]], 
        interval: Interval
    ) -> List[Dict[str, Any]]:
        """
        Generate list of missing timestamps that need to be filled.
        
        Args:
            gaps: List of gap information from detect_gaps
            interval: Time interval for missing timestamps
            
        Returns:
            List of missing timestamp info
        """
        missing_timestamps = []
        interval_delta = self._interval_to_timedelta(interval)
        
        for gap in gaps:
            symbol = gap["symbol"]
            current_time = gap["gap_start"]
            end_time = gap["gap_end"]
            
            # Generate all missing timestamps in this gap
            while current_time < end_time:
                missing_timestamps.append({
                    "symbol": symbol,
                    "timestamp": current_time,
                    "gap_info": gap
                })
                current_time += interval_delta
        
        return missing_timestamps
    
    def create_gap_report(self, gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a comprehensive gap analysis report."""
        if not gaps:
            return {
                "total_gaps": 0,
                "total_missing_periods": 0,
                "symbols_affected": 0,
                "gap_summary": []
            }
        
        # Aggregate gap statistics
        total_gaps = len(gaps)
        total_missing_periods = sum(gap["missing_periods"] for gap in gaps)
        symbols_affected = len(set(gap["symbol"] for gap in gaps))
        
        # Create summary by symbol
        symbol_summary = {}
        for gap in gaps:
            symbol = gap["symbol"]
            if symbol not in symbol_summary:
                symbol_summary[symbol] = {
                    "gap_count": 0,
                    "missing_periods": 0,
                    "largest_gap": 0,
                    "total_gap_duration": timedelta(0)
                }
            
            symbol_summary[symbol]["gap_count"] += 1
            symbol_summary[symbol]["missing_periods"] += gap["missing_periods"]
            symbol_summary[symbol]["largest_gap"] = max(
                symbol_summary[symbol]["largest_gap"], 
                gap["missing_periods"]
            )
            symbol_summary[symbol]["total_gap_duration"] += gap["gap_duration"]
        
        return {
            "total_gaps": total_gaps,
            "total_missing_periods": total_missing_periods,
            "symbols_affected": symbols_affected,
            "gap_summary": symbol_summary,
            "largest_gap": max(gap["missing_periods"] for gap in gaps) if gaps else 0,
            "average_gap_size": total_missing_periods / total_gaps if total_gaps > 0 else 0
        }
    
    def validate_data_completeness(
        self, 
        data: pl.DataFrame, 
        expected_start: datetime,
        expected_end: datetime,
        interval: Interval,
        symbol_column: str = "symbol",
        time_column: str = "open_time"
    ) -> Dict[str, Any]:
        """
        Validate data completeness against expected date range.
        
        Args:
            data: DataFrame to validate
            expected_start: Expected start timestamp
            expected_end: Expected end timestamp
            interval: Expected time interval
            symbol_column: Name of symbol column
            time_column: Name of timestamp column
            
        Returns:
            Validation report
        """
        try:
            if len(data) == 0:
                return {
                    "is_complete": False,
                    "completeness_ratio": 0.0,
                    "missing_periods": 0,
                    "symbols_complete": {},
                    "overall_gaps": []
                }
            
            # Calculate expected number of periods
            interval_delta = self._interval_to_timedelta(interval)
            expected_periods = int((expected_end - expected_start) / interval_delta)
            
            # Check completeness by symbol
            symbols_complete = {}
            overall_gaps = []
            
            for symbol in data[symbol_column].unique():
                symbol_data = data.filter(pl.col(symbol_column) == symbol)
                
                # Check if symbol has data for the full range
                symbol_start = symbol_data[time_column].min()
                symbol_end = symbol_data[time_column].max()
                
                # Detect gaps for this symbol
                symbol_gaps = self.detect_gaps(
                    symbol_data, interval, time_column, symbol_column
                )
                
                # Calculate completeness
                actual_periods = len(symbol_data)
                completeness = actual_periods / expected_periods if expected_periods > 0 else 0
                
                symbols_complete[symbol] = {
                    "actual_periods": actual_periods,
                    "expected_periods": expected_periods,
                    "completeness_ratio": completeness,
                    "gaps": len(symbol_gaps),
                    "data_start": symbol_start,
                    "data_end": symbol_end,
                    "covers_expected_range": (
                        symbol_start <= expected_start and 
                        symbol_end >= expected_end
                    )
                }
                
                overall_gaps.extend(symbol_gaps)
            
            # Calculate overall completeness
            total_actual = len(data)
            total_expected = expected_periods * len(data[symbol_column].unique())
            overall_completeness = total_actual / total_expected if total_expected > 0 else 0
            
            return {
                "is_complete": overall_completeness >= 0.95,  # 95% threshold
                "completeness_ratio": overall_completeness,
                "missing_periods": len(overall_gaps),
                "symbols_complete": symbols_complete,
                "overall_gaps": overall_gaps,
                "expected_start": expected_start,
                "expected_end": expected_end,
                "actual_start": data[time_column].min(),
                "actual_end": data[time_column].max()
            }
            
        except Exception as e:
            logger.error(f"Data completeness validation failed: {e}")
            return {
                "is_complete": False,
                "completeness_ratio": 0.0,
                "missing_periods": 0,
                "symbols_complete": {},
                "overall_gaps": [],
                "error": str(e)
            }