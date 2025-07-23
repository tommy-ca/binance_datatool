"""Demo script showcasing comprehensive OpenTelemetry tracing for crypto workflows."""

import asyncio
import time
import logging
from typing import List, Dict, Any

# Import crypto lakehouse tracing components
from crypto_lakehouse.core import (
    initialize_crypto_observability,
    get_workflow_tracer,
    get_manual_span_manager,
    crypto_workflow_context,
    crypto_processing_context,
    performance_aware_operation,
    create_crypto_headers,
    trace_crypto_workflow,
    manual_trace_binance_api,
    check_system_health,
    shutdown_observability
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CryptoTracingDemo:
    """Demo class for crypto workflow tracing."""
    
    def __init__(self):
        # Initialize observability stack
        logger.info("Initializing crypto observability stack...")
        self.components = initialize_crypto_observability(
            service_name="crypto-tracing-demo",
            service_version="1.0.0",
            environment="demo"
        )
        
        self.workflow_tracer = self.components["workflow_tracer"]
        self.manual_span_manager = self.components["manual_span_manager"]
        
        logger.info("Observability stack initialized successfully")
    
    def demo_workflow_tracing(self):
        """Demonstrate comprehensive workflow tracing."""
        logger.info("=== Demo: Workflow Tracing ===")
        
        with self.workflow_tracer.trace_workflow_execution(
            workflow_name="binance_data_collection",
            workflow_type="batch",
            market="binance",
            symbols=["BTCUSDT", "ETHUSDT", "ADAUSDT"],
            data_types=["klines", "trades"],
            collection_date="2025-01-20"
        ) as workflow_context:
            
            logger.info(f"Started workflow: {workflow_context.workflow_id}")
            
            # Stage 1: Market Discovery
            with workflow_context.start_stage(
                "market_discovery",
                data_type="exchange_info"
            ) as discovery_context:
                discovery_context.add_processing_event("discovery_started")
                time.sleep(0.1)  # Simulate API call
                discovery_context.add_processing_event("symbols_discovered", {"count": 3})
                discovery_context.set_processing_metric("discovery_time_ms", 100)
            
            # Stage 2: Data Collection for each symbol
            symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
            for symbol in symbols:
                with workflow_context.start_stage(
                    f"data_collection_{symbol}",
                    symbol=symbol,
                    data_type="klines"
                ) as collection_context:
                    
                    # Simulate data collection
                    self._simulate_binance_api_call(symbol)
                    time.sleep(0.05)
                    
                    collection_context.record_data_stats(
                        record_count=1440,  # 1 day of 1-minute data
                        data_size_bytes=72000  # ~50 bytes per record
                    )
            
            # Stage 3: Data Processing
            with workflow_context.start_stage(
                "data_processing",
                data_type="klines"
            ) as processing_context:
                
                total_records = len(symbols) * 1440
                self._simulate_data_processing(total_records)
                
                processing_context.record_data_stats(
                    record_count=total_records,
                    data_size_bytes=total_records * 50
                )
            
            # Stage 4: Storage Operations
            with workflow_context.start_stage(
                "storage_operations",
                storage_type="s3"
            ) as storage_context:
                
                self._simulate_s3_storage(symbols)
                
                storage_context.set_file_details(
                    file_count=len(symbols),
                    total_size_bytes=len(symbols) * 72000
                )
            
            # Workflow completion
            workflow_context.add_workflow_event("workflow_completed", {
                "symbols_processed": len(symbols),
                "total_records": total_records,
                "success": True
            })
            
            logger.info(f"Completed workflow: {workflow_context.workflow_id}")
    
    def _simulate_binance_api_call(self, symbol: str):
        """Simulate Binance API call with manual tracing."""
        with self.manual_span_manager.binance_api_span(
            endpoint="https://api.binance.com/api/v3/klines",
            method="GET",
            symbol=symbol,
            data_type="klines",
            request_params={"symbol": symbol, "interval": "1m", "limit": 1440}
        ) as api_context:
            
            # Simulate request
            api_context.set_request_details(
                params={"symbol": symbol, "interval": "1m", "limit": 1440},
                headers={"User-Agent": "crypto-tracing-demo"}
            )
            
            # Simulate network delay
            time.sleep(0.02)
            
            # Simulate successful response
            api_context.set_response_details(
                status_code=200,
                response_size_bytes=72000,
                response_time_ms=20,
                rate_limit_headers={
                    "x-ratelimit-remaining": "1199",
                    "x-mbx-used-weight": "1"
                }
            )
    
    def _simulate_data_processing(self, record_count: int):
        """Simulate data processing with performance monitoring."""
        with performance_aware_operation(
            operation_name="kline_data_processing",
            performance_budget_ms=2000,
            crypto_priority="high",
            data_type="klines"
        ) as perf_context:
            
            # Simulate processing steps
            perf_context.add_performance_checkpoint("validation_start")
            time.sleep(0.03)  # Simulate validation
            
            perf_context.add_performance_checkpoint("transformation_start")
            time.sleep(0.05)  # Simulate transformation
            
            perf_context.add_performance_checkpoint("enrichment_start")
            time.sleep(0.02)  # Simulate enrichment
            
            # Record processing metrics
            perf_context.record_throughput(
                records_processed=record_count,
                bytes_processed=record_count * 50
            )
            
            perf_context.set_performance_attribute("processing_steps", 3)
            perf_context.set_performance_attribute("validation_passed", True)
    
    def _simulate_s3_storage(self, symbols: List[str]):
        """Simulate S3 storage operations."""
        for symbol in symbols:
            with self.manual_span_manager.s3_storage_span(
                operation="put_object",
                bucket="crypto-data-lake",
                key=f"bronze/binance/klines/{symbol}/2025/01/20/data.parquet",
                file_size_bytes=72000,
                storage_class="STANDARD"
            ) as s3_context:
                
                # Simulate upload
                time.sleep(0.01)
                
                s3_context.set_upload_details(
                    file_count=1,
                    total_size_bytes=72000,
                    encryption="AES256"
                )
                
                s3_context.calculate_throughput(72000)
    
    def demo_context_propagation(self):
        """Demonstrate context propagation across services."""
        logger.info("=== Demo: Context Propagation ===")
        
        with crypto_workflow_context(
            workflow_id="distributed-demo-123",
            workflow_name="distributed_data_collection",
            market="binance",
            data_types=["klines"]
        ) as baggage_accessor:
            
            logger.info(f"Workflow ID: {baggage_accessor.get_workflow_id()}")
            logger.info(f"Market: {baggage_accessor.get_market()}")
            
            # Create headers for downstream service
            headers = create_crypto_headers(
                workflow_id=baggage_accessor.get_workflow_id(),
                market=baggage_accessor.get_market(),
                processing_stage="api_collection"
            )
            
            logger.info(f"Created headers with {len(headers)} propagation fields")
            
            # Simulate downstream processing
            with crypto_processing_context(
                processing_stage="data_validation",
                data_type="klines",
                symbol="BTCUSDT"
            ) as processing_accessor:
                
                logger.info(f"Processing stage: {processing_accessor.get_processing_stage()}")
                logger.info(f"Data type: {processing_accessor.get_data_type()}")
                logger.info(f"Symbol: {processing_accessor.get_symbol()}")
    
    @trace_crypto_workflow(
        workflow_name="decorated_workflow",
        workflow_type="real_time",
        market="binance"
    )
    def demo_decorator_tracing(self, context, symbols: List[str]):
        """Demonstrate decorator-based tracing."""
        logger.info("=== Demo: Decorator Tracing ===")
        
        context.add_workflow_event("decorator_workflow_started")
        
        for symbol in symbols:
            context.set_workflow_attribute(f"processing_{symbol}", True)
            time.sleep(0.01)  # Simulate processing
        
        context.add_workflow_event("decorator_workflow_completed", {
            "symbols_processed": len(symbols)
        })
        
        return {"status": "success", "symbols": symbols}
    
    @manual_trace_binance_api(
        endpoint="https://api.binance.com/api/v3/ticker/24hr",
        method="GET",
        extract_symbol=True
    )
    def demo_api_decorator(self, context, symbol: str = "BTCUSDT"):
        """Demonstrate API decorator tracing."""
        logger.info(f"=== Demo: API Decorator for {symbol} ===")
        
        # Simulate API request preparation
        context.set_request_details(
            params={"symbol": symbol},
            headers={"User-Agent": "crypto-tracing-demo", "Accept": "application/json"}
        )
        
        # Simulate API call
        time.sleep(0.015)
        
        # Simulate successful response
        context.set_response_details(
            status_code=200,
            response_size_bytes=1024,
            response_time_ms=15
        )
        
        return {
            "symbol": symbol,
            "price": "50000.00",
            "volume": "1000.50"
        }
    
    async def demo_async_tracing(self):
        """Demonstrate async operation tracing."""
        logger.info("=== Demo: Async Tracing ===")
        
        async with self.workflow_tracer.trace_async_operation(
            operation_name="async_multi_symbol_collection",
            operation_type="concurrent_api_calls",
            symbols=["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        ) as async_context:
            
            async_context.add_async_event("async_operation_started")
            
            # Simulate concurrent API calls
            tasks = []
            for symbol in ["BTCUSDT", "ETHUSDT", "ADAUSDT"]:
                task = asyncio.create_task(self._async_api_call(symbol))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            async_context.add_async_event("all_api_calls_completed", {
                "results_count": len(results),
                "total_records": sum(len(result) for result in results)
            })
            
            return results
    
    async def _async_api_call(self, symbol: str):
        """Simulate async API call."""
        await asyncio.sleep(0.02)  # Simulate network delay
        return [{"symbol": symbol, "timestamp": time.time(), "price": "50000.00"}]
    
    def demo_performance_monitoring(self):
        """Demonstrate performance monitoring capabilities."""
        logger.info("=== Demo: Performance Monitoring ===")
        
        # Check system health
        health = check_system_health()
        logger.info(f"System health: {health}")
        
        # Run performance-intensive operation
        with performance_aware_operation(
            operation_name="intensive_data_processing",
            performance_budget_ms=3000,
            auto_adjust_sampling=True,
            crypto_priority="medium"
        ) as perf_context:
            
            # Simulate memory and CPU intensive work
            data = []
            for i in range(100000):
                data.append({"id": i, "value": i * 2, "symbol": "BTCUSDT"})
                
                if i % 25000 == 0:
                    perf_context.add_performance_checkpoint(f"checkpoint_{i}")
            
            # Check if within budget
            within_budget = perf_context.check_performance_budget()
            logger.info(f"Operation within budget: {within_budget}")
            
            # Record final metrics
            perf_context.record_throughput(
                records_processed=len(data),
                bytes_processed=len(data) * 100  # Estimate
            )
    
    def demo_error_handling(self):
        """Demonstrate error handling and span status."""
        logger.info("=== Demo: Error Handling ===")
        
        try:
            with self.workflow_tracer.trace_workflow_execution(
                workflow_name="error_demo_workflow",
                workflow_type="error_test"
            ) as workflow_context:
                
                workflow_context.add_workflow_event("error_simulation_started")
                
                # Simulate an error
                raise ValueError("Simulated error for tracing demonstration")
                
        except ValueError as e:
            logger.error(f"Expected error caught: {e}")
    
    def run_all_demos(self):
        """Run all tracing demonstrations."""
        logger.info("Starting comprehensive OpenTelemetry tracing demo...")
        
        try:
            # Demo 1: Workflow Tracing
            self.demo_workflow_tracing()
            
            # Demo 2: Context Propagation  
            self.demo_context_propagation()
            
            # Demo 3: Decorator Tracing
            result = self.demo_decorator_tracing(["BTCUSDT", "ETHUSDT"])
            logger.info(f"Decorator workflow result: {result}")
            
            # Demo 4: API Decorator
            api_result = self.demo_api_decorator(symbol="ETHUSDT")
            logger.info(f"API decorator result: {api_result}")
            
            # Demo 5: Async Tracing
            async_result = asyncio.run(self.demo_async_tracing())
            logger.info(f"Async tracing result: {len(async_result)} results")
            
            # Demo 6: Performance Monitoring
            self.demo_performance_monitoring()
            
            # Demo 7: Error Handling
            self.demo_error_handling()
            
            logger.info("All demos completed successfully!")
            
        except Exception as e:
            logger.error(f"Demo failed: {e}")
            raise
        finally:
            # Shutdown observability
            logger.info("Shutting down observability stack...")
            shutdown_observability()
            logger.info("Demo complete!")


def main():
    """Main demo function."""
    demo = CryptoTracingDemo()
    demo.run_all_demos()


if __name__ == "__main__":
    main()