#!/usr/bin/env python3
"""
Production-optimized performance benchmark.

This benchmark tests the production configuration with:
- No console logging 
- OTLP export only
- Optimized sampling
- Minimal overhead configuration
"""

import time
import logging
import statistics
import psutil
import gc
from typing import List, Dict
from contextlib import contextmanager

# Setup production-like logging configuration
import os
os.environ['ENABLE_CONSOLE_EXPORT'] = 'false'
os.environ['ENABLE_LEGACY_LOGGING'] = 'false'  # Disable for production test

# Standard logging setup (minimal)
logging.basicConfig(level=logging.CRITICAL)  # Suppress most standard logs
standard_logger = logging.getLogger("production.standard")
standard_logger.setLevel(logging.INFO)

# OpenTelemetry production setup
from crypto_lakehouse.core.logging_adapter import (
    get_crypto_logger,
    setup_crypto_logging
)
from crypto_lakehouse.core.otel_logging import LogSamplingConfig

# Production sampling configuration
production_sampling = LogSamplingConfig(
    error_warn_rate=1.0,      # Always log errors
    info_rate=0.01,           # Very low info sampling (1%)
    debug_rate=0.001,         # Minimal debug sampling (0.1%) 
    crypto_operation_rate=0.05,  # Low crypto operation sampling
    high_frequency_rate=0.0001   # Extremely low high-frequency sampling
)

setup_crypto_logging(
    service_name="production-benchmark",
    environment="production",
    sampling_config=production_sampling
)

otel_logger = get_crypto_logger("production.otel", enable_legacy=False)


class ProductionMetrics:
    """Lightweight metrics collection for production testing."""
    
    def __init__(self):
        self.measurements = []
        self.process = psutil.Process()
    
    @contextmanager
    def measure(self, test_name: str, logger_type: str, log_count: int):
        """Lightweight performance measurement."""
        gc.collect()
        
        # Quick CPU measurement
        cpu_start = psutil.cpu_percent(interval=None)
        memory_start = self.process.memory_info().rss / 1024 / 1024
        start_time = time.perf_counter()
        
        yield
        
        end_time = time.perf_counter()
        cpu_end = psutil.cpu_percent(interval=None)
        memory_end = self.process.memory_info().rss / 1024 / 1024
        
        duration_ms = (end_time - start_time) * 1000
        avg_cpu = (cpu_start + cpu_end) / 2
        
        self.measurements.append({
            'test': test_name,
            'type': logger_type,
            'duration_ms': duration_ms,
            'cpu_percent': avg_cpu,
            'memory_mb': memory_end,
            'logs': log_count,
            'logs_per_ms': log_count / duration_ms if duration_ms > 0 else 0
        })
    
    def analyze(self):
        """Analyze production performance."""
        standard_measurements = [m for m in self.measurements if m['type'] == 'standard']
        otel_measurements = [m for m in self.measurements if m['type'] == 'otel']
        
        results = {}
        
        for test_name in set(m['test'] for m in self.measurements):
            std_data = [m for m in standard_measurements if m['test'] == test_name]
            otel_data = [m for m in otel_measurements if m['test'] == test_name]
            
            if std_data and otel_data:
                std_avg_duration = statistics.mean(m['duration_ms'] for m in std_data)
                otel_avg_duration = statistics.mean(m['duration_ms'] for m in otel_data)
                
                std_avg_cpu = statistics.mean(m['cpu_percent'] for m in std_data)
                otel_avg_cpu = statistics.mean(m['cpu_percent'] for m in otel_data)
                
                cpu_overhead = ((otel_avg_cpu - std_avg_cpu) / max(std_avg_cpu, 0.1)) * 100
                duration_overhead = ((otel_avg_duration - std_avg_duration) / std_avg_duration) * 100
                
                results[test_name] = {
                    'cpu_overhead_percent': cpu_overhead,
                    'duration_overhead_percent': duration_overhead,
                    'std_cpu': std_avg_cpu,
                    'otel_cpu': otel_avg_cpu,
                    'std_duration': std_avg_duration,
                    'otel_duration': otel_avg_duration
                }
        
        return results


def production_basic_test(metrics: ProductionMetrics):
    """Test basic production logging."""
    print("Testing basic production logging...")
    
    iterations = 1000
    
    # Standard logging
    for run in range(5):
        with metrics.measure("basic", "standard", iterations):
            for i in range(iterations):
                standard_logger.info(f"Operation {i}")
    
    # OpenTelemetry logging
    for run in range(5):
        with metrics.measure("basic", "otel", iterations):
            for i in range(iterations):
                otel_logger.info(f"Operation {i}")


def production_crypto_test(metrics: ProductionMetrics):
    """Test crypto operations in production."""
    print("Testing crypto operations...")
    
    iterations = 500
    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
    
    # Standard logging
    for run in range(5):
        with metrics.measure("crypto", "standard", iterations):
            for i in range(iterations):
                symbol = symbols[i % len(symbols)]
                standard_logger.info(f"Processing {symbol}")
    
    # OpenTelemetry logging
    for run in range(5):
        with metrics.measure("crypto", "otel", iterations):
            for i in range(iterations):
                symbol = symbols[i % len(symbols)]
                otel_logger.log_ingestion_event(
                    symbol=symbol,
                    records_count=100,
                    data_size_bytes=5000,
                    duration_ms=10.0
                )


def production_high_frequency_test(metrics: ProductionMetrics):
    """Test high-frequency operations (heavy sampling)."""
    print("Testing high-frequency operations...")
    
    iterations = 10000
    
    # Standard logging
    for run in range(3):
        with metrics.measure("high_freq", "standard", iterations):
            for i in range(iterations):
                standard_logger.debug(f"High freq {i}")
    
    # OpenTelemetry logging (will be heavily sampled)
    for run in range(3):
        with metrics.measure("high_freq", "otel", iterations):
            for i in range(iterations):
                otel_logger.debug(f"High freq {i}", 
                                extra={'crypto_operation': 'high_frequency'})


def main():
    """Run production benchmark."""
    print("🚀 Production OpenTelemetry Logging Benchmark")
    print("Configuration: OTLP-only, aggressive sampling, minimal overhead")
    print("=" * 70)
    
    metrics = ProductionMetrics()
    
    try:
        production_basic_test(metrics)
        production_crypto_test(metrics)
        production_high_frequency_test(metrics)
        
        # Analyze results
        results = metrics.analyze()
        
        print("\n" + "=" * 70)
        print("PRODUCTION BENCHMARK RESULTS")
        print("=" * 70)
        
        total_cpu_overhead = 0
        test_count = 0
        
        for test_name, data in results.items():
            cpu_overhead = data['cpu_overhead_percent']
            duration_overhead = data['duration_overhead_percent']
            
            print(f"\n📊 {test_name.upper()} TEST:")
            print(f"  CPU:      {data['std_cpu']:.2f}% → {data['otel_cpu']:.2f}% ({cpu_overhead:+.2f}%)")
            print(f"  Duration: {data['std_duration']:.2f}ms → {data['otel_duration']:.2f}ms ({duration_overhead:+.2f}%)")
            
            if cpu_overhead <= 2.0:
                status = "✅ PASS"
            elif cpu_overhead <= 5.0:
                status = "⚠️  WARN"
            else:
                status = "❌ FAIL"
            
            print(f"  Status:   {status}")
            
            total_cpu_overhead += cpu_overhead
            test_count += 1
        
        avg_cpu_overhead = total_cpu_overhead / test_count if test_count > 0 else 0
        
        print(f"\n" + "=" * 70)
        print(f"AVERAGE CPU OVERHEAD: {avg_cpu_overhead:.2f}%")
        
        if avg_cpu_overhead <= 2.0:
            print("✅ PRODUCTION BENCHMARK PASSED")
            print("OpenTelemetry logging meets <2% CPU overhead requirement")
            return 0
        elif avg_cpu_overhead <= 5.0:
            print("⚠️  PRODUCTION BENCHMARK WARNING")
            print("CPU overhead slightly elevated but may be acceptable")
            return 0
        else:
            print("❌ PRODUCTION BENCHMARK FAILED") 
            print("CPU overhead exceeds acceptable limits")
            return 1
            
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())