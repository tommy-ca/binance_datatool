#!/usr/bin/env python3
"""
Performance benchmark for OpenTelemetry logging overhead.

This benchmark measures:
1. CPU overhead of OpenTelemetry logging vs standard logging
2. Memory consumption patterns
3. Throughput comparison
4. Latency impact on crypto operations
5. Sampling effectiveness

Target: <2% CPU overhead as specified in requirements.
"""

import time
import logging
import threading
import statistics
import psutil
import gc
from typing import List, Dict, Tuple
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

# Standard logging setup
standard_logger = logging.getLogger("benchmark.standard")
standard_logger.setLevel(logging.DEBUG)
standard_handler = logging.StreamHandler()
standard_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
standard_logger.addHandler(standard_handler)

# OpenTelemetry logging setup
from crypto_lakehouse.core.logging_adapter import (
    get_crypto_logger,
    setup_crypto_logging,
    crypto_operation_logging
)
from crypto_lakehouse.core.otel_logging import (
    LogSamplingConfig,
    crypto_logging_context
)

# Setup OTel logging with production-like settings
setup_crypto_logging(
    service_name="performance-benchmark",
    environment="benchmark",
    sampling_config=LogSamplingConfig(
        error_warn_rate=1.0,
        info_rate=0.1,  # Production sampling
        debug_rate=0.01,
        crypto_operation_rate=0.5,
        high_frequency_rate=0.001
    )
)

otel_logger = get_crypto_logger("benchmark.otel")


class PerformanceMetrics:
    """Collect and analyze performance metrics."""
    
    def __init__(self):
        self.measurements: List[Dict] = []
        self.process = psutil.Process()
    
    def record_measurement(
        self,
        test_name: str,
        duration_ms: float,
        cpu_percent: float,
        memory_mb: float,
        log_count: int,
        logger_type: str
    ):
        """Record a performance measurement."""
        self.measurements.append({
            'test_name': test_name,
            'duration_ms': duration_ms,
            'cpu_percent': cpu_percent,
            'memory_mb': memory_mb,
            'log_count': log_count,
            'logger_type': logger_type,
            'logs_per_second': log_count / (duration_ms / 1000) if duration_ms > 0 else 0,
            'ms_per_log': duration_ms / log_count if log_count > 0 else 0
        })
    
    def get_overhead_analysis(self) -> Dict:
        """Analyze overhead between standard and OpenTelemetry logging."""
        standard_measurements = [m for m in self.measurements if m['logger_type'] == 'standard']
        otel_measurements = [m for m in self.measurements if m['logger_type'] == 'otel']
        
        if not standard_measurements or not otel_measurements:
            return {"error": "Insufficient measurements for comparison"}
        
        # Group by test name for comparison
        comparisons = {}
        
        for test_name in set(m['test_name'] for m in self.measurements):
            standard_data = [m for m in standard_measurements if m['test_name'] == test_name]
            otel_data = [m for m in otel_measurements if m['test_name'] == test_name]
            
            if standard_data and otel_data:
                # Calculate averages
                std_duration = statistics.mean(m['duration_ms'] for m in standard_data)
                otel_duration = statistics.mean(m['duration_ms'] for m in otel_data)
                
                std_cpu = statistics.mean(m['cpu_percent'] for m in standard_data)
                otel_cpu = statistics.mean(m['cpu_percent'] for m in otel_data)
                
                std_memory = statistics.mean(m['memory_mb'] for m in standard_data)
                otel_memory = statistics.mean(m['memory_mb'] for m in otel_data)
                
                std_throughput = statistics.mean(m['logs_per_second'] for m in standard_data)
                otel_throughput = statistics.mean(m['logs_per_second'] for m in otel_data)
                
                # Calculate overhead percentages
                duration_overhead = ((otel_duration - std_duration) / std_duration) * 100
                cpu_overhead = ((otel_cpu - std_cpu) / max(std_cpu, 1.0)) * 100
                memory_overhead = ((otel_memory - std_memory) / max(std_memory, 1.0)) * 100
                throughput_impact = ((std_throughput - otel_throughput) / max(std_throughput, 1.0)) * 100
                
                comparisons[test_name] = {
                    'standard': {
                        'duration_ms': std_duration,
                        'cpu_percent': std_cpu,
                        'memory_mb': std_memory,
                        'throughput': std_throughput
                    },
                    'otel': {
                        'duration_ms': otel_duration,
                        'cpu_percent': otel_cpu,
                        'memory_mb': otel_memory,
                        'throughput': otel_throughput
                    },
                    'overhead': {
                        'duration_percent': duration_overhead,
                        'cpu_percent': cpu_overhead,
                        'memory_percent': memory_overhead,
                        'throughput_impact_percent': throughput_impact
                    }
                }
        
        return comparisons
    
    def print_summary(self):
        """Print performance summary."""
        analysis = self.get_overhead_analysis()
        
        print("\n" + "=" * 80)
        print("OPENTELEMETRY LOGGING PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)
        
        if "error" in analysis:
            print(f"❌ Analysis error: {analysis['error']}")
            return
        
        total_cpu_overhead = 0
        test_count = 0
        
        for test_name, data in analysis.items():
            print(f"\n📊 Test: {test_name}")
            print("-" * 40)
            
            std = data['standard']
            otel = data['otel']
            overhead = data['overhead']
            
            print(f"Duration:    {std['duration_ms']:.2f}ms → {otel['duration_ms']:.2f}ms ({overhead['duration_percent']:+.2f}%)")
            print(f"CPU:         {std['cpu_percent']:.2f}% → {otel['cpu_percent']:.2f}% ({overhead['cpu_percent']:+.2f}%)")
            print(f"Memory:      {std['memory_mb']:.1f}MB → {otel['memory_mb']:.1f}MB ({overhead['memory_percent']:+.2f}%)")
            print(f"Throughput:  {std['throughput']:.0f} → {otel['throughput']:.0f} logs/sec ({overhead['throughput_impact_percent']:+.2f}%)")
            
            # Color coding for CPU overhead
            cpu_overhead_val = overhead['cpu_percent']
            if cpu_overhead_val <= 2.0:
                status = "✅ PASS"
            elif cpu_overhead_val <= 5.0:
                status = "⚠️  WARN"
            else:
                status = "❌ FAIL"
            
            print(f"CPU Status:  {status} (Target: <2% overhead)")
            
            total_cpu_overhead += cpu_overhead_val
            test_count += 1
        
        # Overall summary
        avg_cpu_overhead = total_cpu_overhead / test_count if test_count > 0 else 0
        
        print("\n" + "=" * 80)
        print("OVERALL PERFORMANCE SUMMARY")
        print("=" * 80)
        print(f"Average CPU Overhead: {avg_cpu_overhead:.2f}%")
        
        if avg_cpu_overhead <= 2.0:
            print("✅ BENCHMARK PASSED: CPU overhead within target (<2%)")
        elif avg_cpu_overhead <= 5.0:
            print("⚠️  BENCHMARK WARNING: CPU overhead elevated but acceptable")
        else:
            print("❌ BENCHMARK FAILED: CPU overhead exceeds acceptable limits")
        
        print(f"Tests completed: {test_count}")
        print(f"Total measurements: {len(self.measurements)}")


@contextmanager
def performance_measurement(metrics: PerformanceMetrics, test_name: str, logger_type: str):
    """Context manager for performance measurement."""
    # Force garbage collection before measurement
    gc.collect()
    
    # Capture initial state
    initial_cpu = psutil.cpu_percent(interval=0.1)
    initial_memory = metrics.process.memory_info().rss / 1024 / 1024  # MB
    start_time = time.perf_counter()
    
    try:
        yield
    finally:
        # Capture final state
        end_time = time.perf_counter()
        final_cpu = psutil.cpu_percent(interval=0.1)
        final_memory = metrics.process.memory_info().rss / 1024 / 1024  # MB
        
        duration_ms = (end_time - start_time) * 1000
        avg_cpu = (initial_cpu + final_cpu) / 2
        avg_memory = (initial_memory + final_memory) / 2
        
        # This will be set by the calling function
        log_count = getattr(performance_measurement, '_log_count', 1)
        
        metrics.record_measurement(
            test_name=test_name,
            duration_ms=duration_ms,
            cpu_percent=avg_cpu,
            memory_mb=avg_memory,
            log_count=log_count,
            logger_type=logger_type
        )


def benchmark_basic_logging(metrics: PerformanceMetrics, iterations: int = 1000):
    """Benchmark basic logging operations."""
    print(f"\n🔄 Running basic logging benchmark ({iterations:,} iterations)...")
    
    # Test standard logging
    for _ in range(3):  # Multiple runs for statistical significance
        with performance_measurement(metrics, "basic_logging", "standard"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                standard_logger.info(f"Standard log message {i}")
    
    # Test OpenTelemetry logging
    for _ in range(3):
        with performance_measurement(metrics, "basic_logging", "otel"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                otel_logger.info(f"OpenTelemetry log message {i}")


def benchmark_crypto_context_logging(metrics: PerformanceMetrics, iterations: int = 500):
    """Benchmark crypto-specific context logging."""
    print(f"\n🔄 Running crypto context benchmark ({iterations:,} iterations)...")
    
    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "BNBUSDT"]
    
    # Test standard logging with manual context
    for _ in range(3):
        with performance_measurement(metrics, "crypto_context", "standard"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                symbol = symbols[i % len(symbols)]
                standard_logger.info(f"Processing {symbol} - operation {i}")
    
    # Test OpenTelemetry logging with automatic context
    for _ in range(3):
        with performance_measurement(metrics, "crypto_context", "otel"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                symbol = symbols[i % len(symbols)]
                with crypto_logging_context(
                    market="binance",
                    symbol=symbol,
                    operation="benchmark_test",
                    data_type="klines"
                ):
                    otel_logger.info(f"Processing {symbol} - operation {i}")


def benchmark_high_frequency_logging(metrics: PerformanceMetrics, iterations: int = 10000):
    """Benchmark high-frequency logging (tests sampling effectiveness)."""
    print(f"\n🔄 Running high-frequency benchmark ({iterations:,} iterations)...")
    
    # Test standard logging
    for _ in range(3):
        with performance_measurement(metrics, "high_frequency", "standard"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                standard_logger.debug(f"High freq operation {i}")
    
    # Test OpenTelemetry logging with heavy sampling
    for _ in range(3):
        with performance_measurement(metrics, "high_frequency", "otel"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                otel_logger.debug(f"High freq operation {i}", 
                                extra={'crypto_operation': 'high_frequency'})


def benchmark_concurrent_logging(metrics: PerformanceMetrics, threads: int = 10, iterations_per_thread: int = 100):
    """Benchmark concurrent logging performance."""
    print(f"\n🔄 Running concurrent benchmark ({threads} threads, {iterations_per_thread:,} each)...")
    
    def standard_worker(thread_id: int):
        for i in range(iterations_per_thread):
            standard_logger.info(f"Thread {thread_id} - operation {i}")
    
    def otel_worker(thread_id: int):
        for i in range(iterations_per_thread):
            with crypto_logging_context(
                operation=f"thread_{thread_id}",
                symbol=f"SYM{thread_id % 5}"
            ):
                otel_logger.info(f"Thread {thread_id} - operation {i}")
    
    total_logs = threads * iterations_per_thread
    
    # Test standard logging concurrency
    for _ in range(3):
        with performance_measurement(metrics, "concurrent", "standard"):
            performance_measurement._log_count = total_logs
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(standard_worker, i) for i in range(threads)]
                for future in futures:
                    future.result()
    
    # Test OpenTelemetry logging concurrency
    for _ in range(3):
        with performance_measurement(metrics, "concurrent", "otel"):
            performance_measurement._log_count = total_logs
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(otel_worker, i) for i in range(threads)]
                for future in futures:
                    future.result()


def benchmark_structured_logging(metrics: PerformanceMetrics, iterations: int = 500):
    """Benchmark structured logging with complex data."""
    print(f"\n🔄 Running structured logging benchmark ({iterations:,} iterations)...")
    
    # Test standard logging with string formatting
    for _ in range(3):
        with performance_measurement(metrics, "structured", "standard"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                standard_logger.info(
                    f"Trade executed: symbol=BTCUSDT, price=45000.50, quantity=0.001, "
                    f"side=BUY, order_id={i}, timestamp={time.time()}"
                )
    
    # Test OpenTelemetry logging with structured data
    for _ in range(3):
        with performance_measurement(metrics, "structured", "otel"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                otel_logger.log_ingestion_event(
                    symbol="BTCUSDT",
                    records_count=100,
                    data_size_bytes=5000,
                    duration_ms=50.0,
                    market="binance",
                    timeframe="1m"
                )


def benchmark_error_logging(metrics: PerformanceMetrics, iterations: int = 200):
    """Benchmark error logging with exception handling."""
    print(f"\n🔄 Running error logging benchmark ({iterations:,} iterations)...")
    
    # Test standard error logging
    for _ in range(3):
        with performance_measurement(metrics, "error_logging", "standard"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                try:
                    raise ValueError(f"Test error {i}")
                except ValueError as e:
                    standard_logger.error(f"Error occurred: {e}", exc_info=True)
    
    # Test OpenTelemetry error logging
    for _ in range(3):
        with performance_measurement(metrics, "error_logging", "otel"):
            performance_measurement._log_count = iterations
            for i in range(iterations):
                try:
                    raise ValueError(f"Test error {i}")
                except ValueError as e:
                    with crypto_logging_context(operation="error_test", symbol="TESTUSDT"):
                        otel_logger.error(f"Error occurred: {e}", exc_info=True)


def main():
    """Run comprehensive performance benchmarks."""
    print("🚀 OpenTelemetry Logging Performance Benchmark")
    print("Target: <2% CPU overhead")
    print("=" * 80)
    
    metrics = PerformanceMetrics()
    
    try:
        # Run all benchmarks
        benchmark_basic_logging(metrics, iterations=1000)
        benchmark_crypto_context_logging(metrics, iterations=500)
        benchmark_high_frequency_logging(metrics, iterations=5000)  # Reduced for CI
        benchmark_concurrent_logging(metrics, threads=5, iterations_per_thread=50)  # Reduced for CI
        benchmark_structured_logging(metrics, iterations=300)
        benchmark_error_logging(metrics, iterations=100)
        
        # Print results
        metrics.print_summary()
        
        # Check if benchmarks passed
        analysis = metrics.get_overhead_analysis()
        if analysis and "error" not in analysis:
            total_cpu_overhead = sum(
                data['overhead']['cpu_percent'] 
                for data in analysis.values()
            ) / len(analysis)
            
            if total_cpu_overhead <= 2.0:
                print("\n🎉 PERFORMANCE REQUIREMENTS MET!")
                return 0
            else:
                print(f"\n⚠️  Performance overhead higher than target: {total_cpu_overhead:.2f}%")
                return 1
        else:
            print("\n❌ Benchmark analysis failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Benchmark failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())