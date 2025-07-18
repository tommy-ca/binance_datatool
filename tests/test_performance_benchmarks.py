"""
Performance benchmark tests for the lakehouse implementation.

These tests measure and compare processing speeds, memory usage, and resource consumption
between the lakehouse implementation and original script workflows.
"""

import pytest
import polars as pl
import numpy as np
import time
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from memory_profiler import profile
import gc

from config import TradeType, N_JOBS
from generate.merge import merge_klines, merge_funding_rates
from generate.kline_gaps import scan_gaps, split_by_gaps, fill_kline_gaps
from generate.resample import polars_calc_resample, resample_kline
from generate.kline import gen_kline, gen_kline_type
from util.ts_manager import TSManager


class PerformanceTracker:
    """Track performance metrics during test execution."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.peak_memory = 0
        self.monitoring = False
        self.monitor_thread = None
        self.memory_samples = []
        
    def start(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.peak_memory = 0
        self.memory_samples = []
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_memory)
        self.monitor_thread.start()
        
    def stop(self):
        """Stop performance monitoring."""
        self.end_time = time.time()
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_memory(self):
        """Monitor memory usage in background thread."""
        process = psutil.Process()
        while self.monitoring:
            try:
                memory_info = process.memory_info()
                current_memory = memory_info.rss
                self.peak_memory = max(self.peak_memory, current_memory)
                self.memory_samples.append(current_memory)
                time.sleep(0.1)
            except:
                break
                
    @property
    def duration(self) -> float:
        """Get execution duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
        
    @property
    def peak_memory_mb(self) -> float:
        """Get peak memory usage in MB."""
        return self.peak_memory / (1024 * 1024)
        
    @property
    def average_memory_mb(self) -> float:
        """Get average memory usage in MB."""
        if self.memory_samples:
            return np.mean(self.memory_samples) / (1024 * 1024)
        return 0.0


class TestDataProcessingPerformance:
    """Test performance of data processing operations."""
    
    @pytest.mark.performance
    @pytest.mark.parametrize("data_size", [1000, 10000, 100000])
    def test_merge_klines_performance(self, test_data_dir, data_generator, data_size):
        """Test K-line merging performance with different data sizes."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"
        
        # Generate test data
        kline_data = data_generator.generate_kline_data(
            symbol=symbol,
            duration_hours=data_size // 60,
            interval_minutes=1
        )
        
        # Setup test environment
        parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        parsed_dir.mkdir(parents=True, exist_ok=True)
        
        ts_manager = TSManager(parsed_dir)
        ts_manager.update(kline_data)
        
        # Benchmark merge operation
        tracker = PerformanceTracker()
        
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            tracker.start()
            result = merge_klines(trade_type, symbol, time_interval, exclude_empty=True)
            tracker.stop()
        
        # Performance assertions
        assert result is not None
        assert tracker.duration > 0
        
        # Performance targets (adjust based on system capabilities)
        if data_size <= 1000:
            assert tracker.duration < 1.0  # Should complete in < 1 second
        elif data_size <= 10000:
            assert tracker.duration < 5.0  # Should complete in < 5 seconds
        else:
            assert tracker.duration < 30.0  # Should complete in < 30 seconds
            
        # Memory usage should be reasonable
        memory_per_row = tracker.peak_memory_mb / data_size
        assert memory_per_row < 0.01  # Less than 10KB per row
        
        # Record metrics for reporting
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"merge_klines_{data_size}"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "rows_processed": data_size,
            "rows_per_second": data_size / tracker.duration if tracker.duration > 0 else 0
        }
    
    @pytest.mark.performance
    @pytest.mark.parametrize("gap_percentage", [0.1, 1.0, 5.0, 10.0])
    def test_gap_detection_performance(self, sample_kline_data, gap_percentage):
        """Test gap detection performance with different gap densities."""
        # Create data with specified gap percentage
        total_rows = sample_kline_data.height
        num_gaps = int(total_rows * gap_percentage / 100)
        
        # Introduce gaps by removing random rows
        np.random.seed(42)
        gap_indices = np.random.choice(total_rows, num_gaps, replace=False)
        
        data_with_gaps = sample_kline_data.with_row_index().filter(
            ~pl.col("index").is_in(gap_indices)
        ).drop("index")
        
        # Benchmark gap detection
        tracker = PerformanceTracker()
        
        tracker.start()
        gaps = scan_gaps(data_with_gaps, min_days=0.1, min_price_chg=0.05)
        tracker.stop()
        
        # Performance assertions
        assert tracker.duration > 0
        assert tracker.duration < 10.0  # Should complete in < 10 seconds
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"gap_detection_{gap_percentage}%"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "rows_processed": data_with_gaps.height,
            "gaps_found": gaps.height,
            "rows_per_second": data_with_gaps.height / tracker.duration if tracker.duration > 0 else 0
        }
    
    @pytest.mark.performance
    @pytest.mark.parametrize("fill_percentage", [1.0, 5.0, 10.0, 20.0])
    def test_gap_filling_performance(self, sample_kline_data, fill_percentage):
        """Test gap filling performance with different fill requirements."""
        # Create data with gaps that need filling
        total_rows = sample_kline_data.height
        num_gaps = int(total_rows * fill_percentage / 100)
        
        # Remove random rows to create gaps
        np.random.seed(42)
        gap_indices = np.random.choice(total_rows, num_gaps, replace=False)
        
        data_with_gaps = sample_kline_data.with_row_index().filter(
            ~pl.col("index").is_in(gap_indices)
        ).drop("index")
        
        # Benchmark gap filling
        tracker = PerformanceTracker()
        
        tracker.start()
        filled_data = fill_kline_gaps(data_with_gaps, "1m")
        tracker.stop()
        
        # Performance assertions
        assert tracker.duration > 0
        assert filled_data.height >= data_with_gaps.height
        
        # Performance should scale reasonably
        if fill_percentage <= 1.0:
            assert tracker.duration < 5.0
        elif fill_percentage <= 5.0:
            assert tracker.duration < 15.0
        else:
            assert tracker.duration < 60.0  # Should complete in < 1 minute
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"gap_filling_{fill_percentage}%"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "rows_input": data_with_gaps.height,
            "rows_output": filled_data.height,
            "rows_filled": filled_data.height - data_with_gaps.height,
            "rows_per_second": filled_data.height / tracker.duration if tracker.duration > 0 else 0
        }
    
    @pytest.mark.performance
    @pytest.mark.parametrize("resample_interval", ["5m", "15m", "1h", "4h", "1d"])
    def test_resampling_performance(self, sample_kline_data, resample_interval):
        """Test resampling performance for different intervals."""
        time_interval = "1m"
        offset = "0m"
        
        # Benchmark resampling
        tracker = PerformanceTracker()
        
        tracker.start()
        resampled = polars_calc_resample(sample_kline_data, time_interval, resample_interval, offset)
        tracker.stop()
        
        # Performance assertions
        assert tracker.duration > 0
        assert not resampled.is_empty()
        assert tracker.duration < 10.0  # Should complete in < 10 seconds
        
        # Calculate compression ratio
        compression_ratio = sample_kline_data.height / resampled.height
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"resampling_{resample_interval}"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "rows_input": sample_kline_data.height,
            "rows_output": resampled.height,
            "compression_ratio": compression_ratio,
            "rows_per_second": sample_kline_data.height / tracker.duration if tracker.duration > 0 else 0
        }


class TestScalabilityBenchmarks:
    """Test scalability with large datasets."""
    
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.parametrize("num_symbols", [1, 10, 50, 100])
    def test_multi_symbol_processing(self, test_data_dir, data_generator, num_symbols):
        """Test processing performance with multiple symbols."""
        trade_type = TradeType.spot
        time_interval = "1m"
        symbols = [f"SYMBOL{i:03d}USDT" for i in range(num_symbols)]
        
        # Generate test data for all symbols
        for symbol in symbols:
            kline_data = data_generator.generate_kline_data(
                symbol=symbol,
                duration_hours=24,
                interval_minutes=1
            )
            
            # Setup test environment
            parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
            parsed_dir.mkdir(parents=True, exist_ok=True)
            
            ts_manager = TSManager(parsed_dir)
            ts_manager.update(kline_data)
        
        # Benchmark multi-symbol processing
        tracker = PerformanceTracker()
        
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            with patch("aws.kline.util.local_list_kline_symbols", return_value=symbols):
                with patch("config.N_JOBS", min(4, num_symbols)):
                    tracker.start()
                    gen_kline_type(
                        trade_type=trade_type,
                        time_interval=time_interval,
                        split_gaps=True,
                        min_days=1,
                        min_price_chg=0.1,
                        with_vwap=True,
                        with_funding_rates=False
                    )
                    tracker.stop()
        
        # Performance assertions
        assert tracker.duration > 0
        
        # Performance should scale sub-linearly due to parallelization
        if num_symbols <= 1:
            assert tracker.duration < 30.0
        elif num_symbols <= 10:
            assert tracker.duration < 120.0  # 2 minutes
        else:
            assert tracker.duration < 600.0  # 10 minutes
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"multi_symbol_{num_symbols}"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "symbols_processed": num_symbols,
            "symbols_per_second": num_symbols / tracker.duration if tracker.duration > 0 else 0,
            "parallel_efficiency": (num_symbols / tracker.duration) / (1 / 30.0) if tracker.duration > 0 else 0
        }
    
    @pytest.mark.performance
    @pytest.mark.slow
    @pytest.mark.parametrize("duration_days", [1, 7, 30, 90])
    def test_large_dataset_processing(self, test_data_dir, data_generator, duration_days):
        """Test processing performance with large time ranges."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"
        
        # Generate large dataset
        kline_data = data_generator.generate_kline_data(
            symbol=symbol,
            duration_hours=duration_days * 24,
            interval_minutes=1
        )
        
        # Setup test environment
        parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        parsed_dir.mkdir(parents=True, exist_ok=True)
        
        ts_manager = TSManager(parsed_dir)
        ts_manager.update(kline_data)
        
        # Benchmark processing
        tracker = PerformanceTracker()
        
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            tracker.start()
            result = gen_kline(
                trade_type=trade_type,
                time_interval=time_interval,
                symbol=symbol,
                split_gaps=True,
                min_days=1,
                min_price_chg=0.1,
                with_vwap=True,
                with_funding_rates=False
            )
            tracker.stop()
        
        # Performance assertions
        assert result == symbol
        assert tracker.duration > 0
        
        # Performance should scale reasonably with data size
        rows_processed = kline_data.height
        processing_rate = rows_processed / tracker.duration if tracker.duration > 0 else 0
        
        # Should maintain reasonable processing rate
        assert processing_rate > 1000  # At least 1000 rows per second
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"large_dataset_{duration_days}d"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "rows_processed": rows_processed,
            "duration_days": duration_days,
            "rows_per_second": processing_rate,
            "memory_per_row_kb": (tracker.peak_memory_mb * 1024) / rows_processed if rows_processed > 0 else 0
        }


class TestMemoryEfficiency:
    """Test memory usage efficiency."""
    
    @pytest.mark.performance
    def test_memory_usage_patterns(self, test_data_dir, data_generator):
        """Test memory usage patterns during processing."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"
        
        # Generate test data
        kline_data = data_generator.generate_kline_data(
            symbol=symbol,
            duration_hours=24,
            interval_minutes=1
        )
        
        # Setup test environment
        parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        parsed_dir.mkdir(parents=True, exist_ok=True)
        
        ts_manager = TSManager(parsed_dir)
        ts_manager.update(kline_data)
        
        # Monitor memory usage throughout processing
        tracker = PerformanceTracker()
        
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            tracker.start()
            
            # Step 1: Merge data
            merged_data = merge_klines(trade_type, symbol, time_interval, exclude_empty=True)
            memory_after_merge = tracker.peak_memory_mb
            
            # Step 2: Scan gaps
            gaps = scan_gaps(merged_data, min_days=0.1, min_price_chg=0.05)
            memory_after_gaps = tracker.peak_memory_mb
            
            # Step 3: Fill gaps
            filled_data = fill_kline_gaps(merged_data, time_interval)
            memory_after_fill = tracker.peak_memory_mb
            
            # Step 4: Resample
            resampled_data = polars_calc_resample(filled_data, "1m", "5m", "0m")
            memory_after_resample = tracker.peak_memory_mb
            
            tracker.stop()
        
        # Memory efficiency assertions
        data_size_mb = (kline_data.height * len(kline_data.columns) * 8) / (1024 * 1024)  # Rough estimate
        
        # Memory usage should be reasonable relative to data size
        assert tracker.peak_memory_mb < data_size_mb * 10  # Less than 10x data size
        
        # Memory should not grow unbounded
        assert memory_after_resample < memory_after_fill * 2  # Should not double
        
        # Record detailed memory metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics["memory_usage_patterns"] = {
            "data_size_mb": data_size_mb,
            "memory_after_merge": memory_after_merge,
            "memory_after_gaps": memory_after_gaps,
            "memory_after_fill": memory_after_fill,
            "memory_after_resample": memory_after_resample,
            "peak_memory_mb": tracker.peak_memory_mb,
            "memory_efficiency": data_size_mb / tracker.peak_memory_mb if tracker.peak_memory_mb > 0 else 0
        }
    
    @pytest.mark.performance
    def test_memory_cleanup(self, test_data_dir, data_generator):
        """Test memory cleanup after processing."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"
        
        # Record baseline memory
        gc.collect()
        baseline_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        
        # Generate and process data
        kline_data = data_generator.generate_kline_data(
            symbol=symbol,
            duration_hours=24,
            interval_minutes=1
        )
        
        # Setup test environment
        parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        parsed_dir.mkdir(parents=True, exist_ok=True)
        
        ts_manager = TSManager(parsed_dir)
        ts_manager.update(kline_data)
        
        # Process data
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            result = gen_kline(
                trade_type=trade_type,
                time_interval=time_interval,
                symbol=symbol,
                split_gaps=True,
                min_days=1,
                min_price_chg=0.1,
                with_vwap=True,
                with_funding_rates=False
            )
        
        # Clean up explicitly
        del kline_data
        del ts_manager
        gc.collect()
        
        # Check memory after cleanup
        final_memory = psutil.Process().memory_info().rss / (1024 * 1024)
        memory_increase = final_memory - baseline_memory
        
        # Memory increase should be minimal after cleanup
        assert memory_increase < 100  # Less than 100MB increase
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics["memory_cleanup"] = {
            "baseline_memory_mb": baseline_memory,
            "final_memory_mb": final_memory,
            "memory_increase_mb": memory_increase,
            "cleanup_efficiency": 1.0 - (memory_increase / 100.0)  # Normalized to 100MB
        }


class TestConcurrencyPerformance:
    """Test concurrent processing performance."""
    
    @pytest.mark.performance
    @pytest.mark.parametrize("num_workers", [1, 2, 4, 8])
    def test_parallel_processing_efficiency(self, test_data_dir, data_generator, num_workers):
        """Test parallel processing efficiency with different worker counts."""
        trade_type = TradeType.spot
        time_interval = "1m"
        symbols = [f"SYMBOL{i:03d}USDT" for i in range(8)]  # Fixed number of symbols
        
        # Generate test data
        for symbol in symbols:
            kline_data = data_generator.generate_kline_data(
                symbol=symbol,
                duration_hours=6,  # Smaller dataset for parallel testing
                interval_minutes=1
            )
            
            parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
            parsed_dir.mkdir(parents=True, exist_ok=True)
            
            ts_manager = TSManager(parsed_dir)
            ts_manager.update(kline_data)
        
        # Benchmark with specific worker count
        tracker = PerformanceTracker()
        
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            with patch("aws.kline.util.local_list_kline_symbols", return_value=symbols):
                with patch("config.N_JOBS", num_workers):
                    tracker.start()
                    gen_kline_type(
                        trade_type=trade_type,
                        time_interval=time_interval,
                        split_gaps=True,
                        min_days=1,
                        min_price_chg=0.1,
                        with_vwap=True,
                        with_funding_rates=False
                    )
                    tracker.stop()
        
        # Performance assertions
        assert tracker.duration > 0
        
        # Record metrics
        pytest.performance_metrics = getattr(pytest, 'performance_metrics', {})
        pytest.performance_metrics[f"parallel_{num_workers}workers"] = {
            "duration": tracker.duration,
            "peak_memory_mb": tracker.peak_memory_mb,
            "num_workers": num_workers,
            "symbols_processed": len(symbols),
            "symbols_per_second": len(symbols) / tracker.duration if tracker.duration > 0 else 0,
            "parallel_efficiency": (len(symbols) / tracker.duration) / num_workers if tracker.duration > 0 else 0
        }


@pytest.fixture(scope="session", autouse=True)
def performance_report_generator():
    """Generate performance report after all tests complete."""
    yield
    
    # Generate performance report
    if hasattr(pytest, 'performance_metrics') and pytest.performance_metrics:
        report_path = Path("performance_report.txt")
        
        with open(report_path, "w") as f:
            f.write("BINANCE DATA TOOL - PERFORMANCE BENCHMARK REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            for test_name, metrics in pytest.performance_metrics.items():
                f.write(f"Test: {test_name}\n")
                f.write("-" * 40 + "\n")
                
                for metric_name, value in metrics.items():
                    if isinstance(value, float):
                        f.write(f"  {metric_name}: {value:.4f}\n")
                    else:
                        f.write(f"  {metric_name}: {value}\n")
                
                f.write("\n")
            
            # Summary statistics
            f.write("PERFORMANCE SUMMARY\n")
            f.write("=" * 30 + "\n")
            
            # Processing rates
            rates = [m.get("rows_per_second", 0) for m in pytest.performance_metrics.values()]
            rates = [r for r in rates if r > 0]
            
            if rates:
                f.write(f"Average processing rate: {np.mean(rates):.2f} rows/second\n")
                f.write(f"Max processing rate: {np.max(rates):.2f} rows/second\n")
                f.write(f"Min processing rate: {np.min(rates):.2f} rows/second\n")
            
            # Memory usage
            memory_usage = [m.get("peak_memory_mb", 0) for m in pytest.performance_metrics.values()]
            memory_usage = [m for m in memory_usage if m > 0]
            
            if memory_usage:
                f.write(f"Average memory usage: {np.mean(memory_usage):.2f} MB\n")
                f.write(f"Max memory usage: {np.max(memory_usage):.2f} MB\n")
                f.write(f"Min memory usage: {np.min(memory_usage):.2f} MB\n")
        
        print(f"Performance report generated: {report_path}")
    else:
        print("No performance metrics collected")