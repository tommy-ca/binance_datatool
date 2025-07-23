#!/usr/bin/env python3
"""
OpenTelemetry Logging Integration Demo for Crypto Lakehouse.

This example demonstrates:
1. Basic OpenTelemetry logging setup
2. Crypto-specific context injection
3. Trace correlation with logs
4. Performance monitoring
5. Error handling and structured logging
"""

import asyncio
import time
import random
from typing import List

# OpenTelemetry tracing setup
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import set_tracer_provider

# Crypto lakehouse logging
from crypto_lakehouse.core.logging_adapter import (
    get_crypto_logger,
    setup_crypto_logging,
    crypto_operation_logging
)
from crypto_lakehouse.core.otel_logging import (
    LogSamplingConfig,
    crypto_logging_context
)


def setup_demo_environment():
    """Setup OpenTelemetry tracing for demo."""
    # Initialize tracer provider
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(
        BatchSpanProcessor(ConsoleSpanExporter())
    )
    set_tracer_provider(tracer_provider)
    
    # Setup crypto logging with demo configuration
    setup_crypto_logging(
        service_name="crypto-logging-demo",
        environment="demo",
        sampling_config=LogSamplingConfig(
            error_warn_rate=1.0,
            info_rate=0.8,  # Higher sampling for demo
            debug_rate=0.3,
            crypto_operation_rate=1.0  # Sample all crypto operations in demo
        )
    )


def demo_basic_logging():
    """Demonstrate basic crypto logging functionality."""
    print("\n=== Demo 1: Basic Crypto Logging ===")
    
    logger = get_crypto_logger("demo.basic")
    
    # Basic logging levels
    logger.debug("Debug message - typically filtered in production")
    logger.info("Info message - standard operational information")
    logger.warning("Warning message - something needs attention")
    logger.error("Error message - operation failed")
    logger.ok("Success message - operation completed successfully")
    
    print("✅ Basic logging demo completed")


def demo_crypto_context():
    """Demonstrate crypto-specific context injection."""
    print("\n=== Demo 2: Crypto Context Injection ===")
    
    logger = get_crypto_logger("demo.context")
    
    # Manual context injection
    logger.log_ingestion_event(
        symbol="BTCUSDT",
        records_count=5000,
        data_size_bytes=250000,
        duration_ms=150.5,
        market="binance",
        timeframe="1m"
    )
    
    # Using context manager
    with crypto_logging_context(
        market="binance",
        symbol="ETHUSDT",
        operation="processing",
        data_type="klines",
        timeframe="5m"
    ):
        logger.info("Processing klines data with automatic context")
        logger.log_processing_event(
            operation="data_validation",
            symbol="ETHUSDT",
            duration_ms=75.2,
            records_processed=3000,
            success=True
        )
    
    print("✅ Crypto context demo completed")


def demo_trace_correlation():
    """Demonstrate trace correlation with logs."""
    print("\n=== Demo 3: Trace Correlation ===")
    
    logger = get_crypto_logger("demo.tracing")
    tracer = trace.get_tracer("demo")
    
    with tracer.start_as_current_span("crypto_workflow") as span:
        span.set_attribute("crypto.market", "binance")
        span.set_attribute("crypto.operation", "data_ingestion")
        
        logger.info("Starting crypto workflow - this log is correlated with the span")
        
        # Nested span with more detailed operations
        with tracer.start_as_current_span("data_download") as download_span:
            download_span.set_attribute("crypto.symbol", "BTCUSDT")
            download_span.set_attribute("crypto.data_type", "klines")
            
            logger.log_ingestion_event(
                symbol="BTCUSDT",
                records_count=10000,
                data_size_bytes=500000,
                duration_ms=300.0
            )
            
            # Simulate processing time
            time.sleep(0.1)
            
            with tracer.start_as_current_span("data_processing"):
                logger.log_processing_event(
                    operation="data_enrichment",
                    symbol="BTCUSDT",
                    duration_ms=250.0,
                    records_processed=10000,
                    success=True
                )
    
    print("✅ Trace correlation demo completed")


def demo_workflow_logging():
    """Demonstrate comprehensive workflow logging."""
    print("\n=== Demo 4: Workflow Logging ===")
    
    logger = get_crypto_logger("demo.workflow")
    
    # Start workflow
    logger.log_workflow_event("archive_collection", "started")
    
    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT"]
    total_records = 0
    
    try:
        for symbol in symbols:
            with crypto_operation_logging(
                operation="symbol_processing",
                market="binance",
                symbol=symbol,
                data_type="klines",
                logger=logger
            ) as op_logger:
                # Simulate processing
                processing_time = random.uniform(50, 200)
                records_count = random.randint(1000, 5000)
                
                time.sleep(processing_time / 1000)  # Convert to seconds
                
                op_logger.log_ingestion_event(
                    symbol=symbol,
                    records_count=records_count,
                    data_size_bytes=records_count * 50,  # Approximate size
                    duration_ms=processing_time
                )
                
                total_records += records_count
        
        # Workflow completed successfully
        logger.log_workflow_event(
            "archive_collection",
            "completed",
            duration_ms=1000.0,
            records_processed=total_records
        )
        
    except Exception as e:
        logger.log_workflow_event(
            "archive_collection",
            "failed",
            error_message=str(e)
        )
        raise
    
    print("✅ Workflow logging demo completed")


def demo_error_handling():
    """Demonstrate error handling and exception logging."""
    print("\n=== Demo 5: Error Handling ===")
    
    logger = get_crypto_logger("demo.errors")
    
    # Simulate various error scenarios
    with crypto_logging_context(
        market="binance",
        symbol="INVALID_SYMBOL",
        operation="error_demo"
    ):
        try:
            # Simulate API error
            raise ValueError("Invalid symbol format: INVALID_SYMBOL")
        except ValueError as e:
            logger.error(f"API validation error: {e}", exc_info=True)
        
        try:
            # Simulate network error
            raise ConnectionError("Failed to connect to Binance API")
        except ConnectionError as e:
            logger.log_processing_event(
                operation="api_connection",
                symbol="INVALID_SYMBOL",
                success=False,
                error_message=str(e)
            )
        
        try:
            # Simulate data processing error
            data = None
            result = data['price']  # This will raise TypeError
        except (TypeError, KeyError) as e:
            logger.exception("Data processing error occurred")
    
    print("✅ Error handling demo completed")


async def demo_async_operations():
    """Demonstrate logging in async operations."""
    print("\n=== Demo 6: Async Operations ===")
    
    logger = get_crypto_logger("demo.async")
    
    async def fetch_symbol_data(symbol: str) -> dict:
        """Simulate async data fetching."""
        with crypto_logging_context(
            market="binance",
            symbol=symbol,
            operation="async_fetch"
        ):
            logger.info(f"Starting async fetch for {symbol}")
            
            # Simulate async work
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            records_count = random.randint(1000, 5000)
            logger.log_ingestion_event(
                symbol=symbol,
                records_count=records_count,
                data_size_bytes=records_count * 48,
                duration_ms=random.uniform(100, 300)
            )
            
            return {"symbol": symbol, "records": records_count}
    
    # Process multiple symbols concurrently
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
    
    logger.info("Starting concurrent async operations")
    tasks = [fetch_symbol_data(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    
    total_records = sum(result["records"] for result in results)
    logger.info(f"Async operations completed. Total records: {total_records:,}")
    
    print("✅ Async operations demo completed")


def demo_performance_monitoring():
    """Demonstrate performance monitoring and sampling."""
    print("\n=== Demo 7: Performance Monitoring ===")
    
    logger = get_crypto_logger("demo.performance")
    
    # High-frequency operations (will be heavily sampled)
    logger.info("Starting high-frequency operations simulation")
    
    start_time = time.time()
    for i in range(1000):
        # These will be sampled based on configuration
        logger.debug(f"High frequency operation {i}", 
                    extra={'crypto_operation': 'high_frequency'})
    
    duration = (time.time() - start_time) * 1000
    logger.info(f"Completed 1000 high-frequency logs in {duration:.2f}ms")
    
    # Performance-critical operations
    with crypto_logging_context(operation="performance_critical"):
        start = time.time()
        
        # Simulate CPU-intensive work
        for i in range(100000):
            _ = i ** 2
        
        processing_time = (time.time() - start) * 1000
        logger.info(f"CPU-intensive operation completed in {processing_time:.2f}ms")
    
    print("✅ Performance monitoring demo completed")


def main():
    """Run all demo scenarios."""
    print("🚀 OpenTelemetry Crypto Logging Demo")
    print("=" * 50)
    
    # Setup demo environment
    setup_demo_environment()
    
    try:
        # Run synchronous demos
        demo_basic_logging()
        demo_crypto_context()
        demo_trace_correlation()
        demo_workflow_logging()
        demo_error_handling()
        demo_performance_monitoring()
        
        # Run async demo
        asyncio.run(demo_async_operations())
        
        print("\n" + "=" * 50)
        print("✅ All demos completed successfully!")
        print("\nCheck your configured log export destinations (console/OTLP) for structured logs")
        print("Look for trace correlation IDs linking logs to spans")
        print("Notice crypto-specific context in all log entries")
        
    except Exception as e:
        logger = get_crypto_logger("demo.main")
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise
    
    finally:
        # Clean shutdown
        time.sleep(1)  # Allow final logs to export


if __name__ == "__main__":
    main()