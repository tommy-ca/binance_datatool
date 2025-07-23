"""Integration tests for OpenTelemetry tracing functionality."""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from typing import Dict, Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from crypto_lakehouse.core import (
    initialize_crypto_observability,
    get_unified_sdk,
    get_workflow_tracer,
    get_manual_span_manager,
    crypto_workflow_context,
    crypto_processing_context,
    performance_aware_operation,
    create_crypto_headers,
    extract_crypto_headers,
    trace_crypto_workflow,
    manual_trace_binance_api
)
from crypto_lakehouse.core.unified_otel import UnifiedOpenTelemetrySDK
from crypto_lakehouse.core.crypto_workflow_tracing import CryptoWorkflowTracer


class TestOpenTelemetryIntegration:
    """Test suite for OpenTelemetry integration."""
    
    @pytest.fixture(autouse=True)
    def setup_otel(self):
        """Setup OpenTelemetry for testing."""
        # Initialize with test configuration
        self.sdk = UnifiedOpenTelemetrySDK(
            service_name="crypto-lakehouse-test",
            service_version="1.0.0-test",
            environment="test",
            enable_auto_instrumentation=True,
            enable_performance_monitoring=True,
            enable_console_exports=False  # Disable console output for tests
        )
        
        # Initialize the SDK
        self.components = self.sdk.initialize()
        
        yield
        
        # Cleanup
        self.sdk.shutdown()
    
    def test_unified_sdk_initialization(self):
        """Test unified SDK initialization."""
        assert self.sdk._initialized
        assert len(self.components) > 0
        
        # Check required components
        required_components = [
            "metrics_config",
            "tracing_config", 
            "otel_metrics",
            "tracer",
            "workflow_tracer",
            "context_propagator",
            "manual_span_manager"
        ]
        
        for component in required_components:
            assert component in self.components
            assert self.components[component] is not None
    
    def test_health_status(self):
        """Test SDK health status reporting."""
        health = self.sdk.get_health_status()
        
        assert health["status"] in ["healthy", "degraded"]
        assert health["service_name"] == "crypto-lakehouse-test"
        assert health["initialized"] is True
        assert "components" in health
        
        # All components should have status
        for component_name, component_health in health["components"].items():
            assert "status" in component_health
    
    def test_workflow_tracing(self):
        """Test end-to-end workflow tracing."""
        workflow_tracer = get_workflow_tracer()
        
        with workflow_tracer.trace_workflow_execution(
            workflow_name="test_archive_collection",
            workflow_type="batch",
            market="binance",
            symbols=["BTCUSDT", "ETHUSDT"],
            data_types=["klines"]
        ) as context:
            
            # Simulate workflow stages
            with context.start_stage("data_download", symbol="BTCUSDT", data_type="klines"):
                time.sleep(0.01)  # Simulate work
                
            with context.start_stage("data_validation", symbol="BTCUSDT"):
                time.sleep(0.01)  # Simulate work
                
            context.add_workflow_event("workflow_checkpoint", {"progress": 50})
            
            with context.start_stage("data_storage", storage_type="s3"):
                time.sleep(0.01)  # Simulate work
        
        # Verify workflow executed without errors
        assert context.workflow_id is not None
        assert context._stage_count == 3
    
    def test_api_tracing(self):
        """Test API interaction tracing."""
        workflow_tracer = get_workflow_tracer()
        
        with workflow_tracer.trace_api_interaction(
            api_endpoint="https://api.binance.com/api/v3/klines",
            method="GET",
            market="binance",
            request_params={"symbol": "BTCUSDT", "interval": "1m", "limit": 1000}
        ) as context:
            
            # Simulate API response
            context.set_processing_metric("response_size_bytes", 50000)
            context.add_processing_event("api_response_received", {
                "status_code": 200,
                "record_count": 1000
            })
    
    def test_data_processing_tracing(self):
        """Test data processing stage tracing."""
        workflow_tracer = get_workflow_tracer()
        
        with workflow_tracer.trace_data_processing_stage(
            stage_name="kline_parsing",
            data_type="klines",
            symbol="BTCUSDT",
            record_count=1000,
            data_size_bytes=50000
        ) as context:
            
            # Simulate processing
            time.sleep(0.02)
            
            context.record_data_stats(1000, 50000)
            context.set_processing_metric("parsing_rate", 50000)  # records per second
    
    def test_storage_operation_tracing(self):
        """Test storage operation tracing."""
        workflow_tracer = get_workflow_tracer()
        
        with workflow_tracer.trace_storage_operation(
            operation="upload",
            storage_type="s3",
            file_path="bronze/binance/klines/BTCUSDT/2025/01/20/data.parquet",
            file_size_bytes=1024000,
            storage_tier="bronze"
        ) as context:
            
            # Simulate storage operation
            time.sleep(0.01)
            
            context.set_file_details(file_count=1, total_size_bytes=1024000)
            context.add_storage_event("upload_completed", {"transfer_rate": "100MB/s"})
    
    @pytest.mark.asyncio
    async def test_async_operation_tracing(self):
        """Test async operation tracing."""
        workflow_tracer = get_workflow_tracer()
        
        async with workflow_tracer.trace_async_operation(
            operation_name="async_data_download",
            operation_type="async_api_call",
            symbol="BTCUSDT",
            data_type="klines"
        ) as context:
            
            # Simulate async work
            await asyncio.sleep(0.01)
            
            context.add_async_event("download_started")
            await asyncio.sleep(0.01)
            context.add_async_event("download_completed", {"bytes_downloaded": 100000})
    
    def test_manual_instrumentation(self):
        """Test manual span creation."""
        manager = get_manual_span_manager()
        
        with manager.create_span(
            "test_manual_span",
            trace.SpanKind.INTERNAL,
            {"operation": "test", "component": "manual"}
        ) as context:
            
            context.add_event("test_event", {"data": "test"})
            context.set_attribute("test.attribute", "value")
    
    def test_binance_api_manual_span(self):
        """Test Binance API manual span creation."""
        manager = get_manual_span_manager()
        
        with manager.binance_api_span(
            endpoint="https://api.binance.com/api/v3/ticker/24hr",
            method="GET",
            symbol="BTCUSDT",
            data_type="ticker",
            request_params={"symbol": "BTCUSDT"}
        ) as context:
            
            # Simulate API call
            context.set_request_details(
                params={"symbol": "BTCUSDT"},
                headers={"User-Agent": "crypto-lakehouse"}
            )
            
            context.set_response_details(
                status_code=200,
                response_size_bytes=500,
                response_time_ms=150,
                rate_limit_headers={"x-ratelimit-remaining": "1199"}
            )
    
    def test_s3_storage_manual_span(self):
        """Test S3 storage manual span creation."""
        manager = get_manual_span_manager()
        
        with manager.s3_storage_span(
            operation="put_object",
            bucket="crypto-data-lake",
            key="bronze/binance/klines/BTCUSDT/2025/01/20/data.parquet",
            file_size_bytes=1024000,
            storage_class="STANDARD"
        ) as context:
            
            context.set_upload_details(
                file_count=1,
                total_size_bytes=1024000,
                encryption="AES256"
            )
            
            context.calculate_throughput(1024000)
    
    def test_context_propagation(self):
        """Test context propagation with baggage."""
        with crypto_workflow_context(
            workflow_id="test-workflow-123",
            workflow_name="archive_collection",
            market="binance",
            data_types=["klines", "trades"]
        ) as baggage_accessor:
            
            # Test baggage access
            assert baggage_accessor.get_workflow_id() == "test-workflow-123"
            assert baggage_accessor.get_market() == "binance"
            
            # Test HTTP header creation
            headers = create_crypto_headers(
                workflow_id="test-workflow-123",
                market="binance",
                processing_stage="data_ingestion"
            )
            
            assert isinstance(headers, dict)
            assert len(headers) > 0
            
            # Test header extraction
            extracted_context = extract_crypto_headers(headers)
            assert isinstance(extracted_context, dict)
    
    def test_processing_context_propagation(self):
        """Test processing context propagation."""
        with crypto_processing_context(
            processing_stage="data_transformation",
            data_type="klines",
            symbol="BTCUSDT",
            record_count=1000
        ) as baggage_accessor:
            
            assert baggage_accessor.get_processing_stage() == "data_transformation"
            assert baggage_accessor.get_data_type() == "klines"
            assert baggage_accessor.get_symbol() == "BTCUSDT"
    
    def test_performance_aware_operation(self):
        """Test performance-aware operation tracing."""
        with performance_aware_operation(
            operation_name="test_performance_operation",
            performance_budget_ms=1000,
            auto_adjust_sampling=True,
            crypto_priority="high"
        ) as context:
            
            # Simulate work
            time.sleep(0.01)
            
            # Check performance budget
            within_budget = context.check_performance_budget()
            assert within_budget is True
            
            # Record throughput
            context.record_throughput(records_processed=1000, bytes_processed=50000)
            
            # Add performance checkpoint
            context.add_performance_checkpoint("midpoint")
    
    def test_decorator_workflow_tracing(self):
        """Test workflow tracing decorator."""
        
        @trace_crypto_workflow(
            workflow_name="test_decorator_workflow",
            workflow_type="batch",
            market="binance"
        )
        def test_workflow_function(context, data):
            """Test workflow function."""
            context.add_workflow_event("function_started")
            time.sleep(0.01)
            context.set_workflow_attribute("data_count", len(data))
            return {"processed": len(data)}
        
        result = test_workflow_function([1, 2, 3, 4, 5])
        assert result["processed"] == 5
    
    def test_decorator_api_tracing(self):
        """Test API tracing decorator."""
        
        @manual_trace_binance_api(
            endpoint="https://api.binance.com/api/v3/klines",
            method="GET",
            extract_symbol=True
        )
        def fetch_klines(context, symbol="BTCUSDT", interval="1m", limit=100):
            """Test API function."""
            context.set_request_details(
                params={"symbol": symbol, "interval": interval, "limit": limit},
                headers={"User-Agent": "test"}
            )
            
            # Simulate successful response
            context.set_response_details(
                status_code=200,
                response_size_bytes=5000,
                response_time_ms=200
            )
            
            return [{"symbol": symbol, "count": limit}]
        
        result = fetch_klines(symbol="ETHUSDT", interval="5m", limit=500)
        assert result[0]["symbol"] == "ETHUSDT"
        assert result[0]["count"] == 500
    
    def test_error_handling_and_span_status(self):
        """Test error handling and span status setting."""
        workflow_tracer = get_workflow_tracer()
        
        with pytest.raises(ValueError):
            with workflow_tracer.trace_workflow_execution(
                workflow_name="test_error_workflow",
                workflow_type="batch"
            ) as context:
                
                context.add_workflow_event("error_about_to_occur")
                raise ValueError("Test error for span status")
    
    def test_span_attributes_and_events(self):
        """Test comprehensive span attributes and events."""
        workflow_tracer = get_workflow_tracer()
        
        with workflow_tracer.trace_data_processing_stage(
            stage_name="comprehensive_test",
            data_type="klines",
            symbol="BTCUSDT",
            record_count=5000,
            data_size_bytes=250000
        ) as context:
            
            # Add various events
            context.add_processing_event("stage_started", {"config": "test"})
            context.add_processing_event("data_loaded", {"source": "binance"})
            context.add_processing_event("validation_passed", {"errors": 0})
            context.add_processing_event("transformation_applied", {"rules": 5})
            
            # Set various metrics
            context.set_processing_metric("validation_rate", 99.9)
            context.set_processing_metric("transformation_rate", 100.0)
            context.set_processing_metric("memory_efficiency", 85.5)
            
            # Record final stats
            context.record_data_stats(record_count=5000, data_size_bytes=250000)
    
    def test_concurrent_tracing(self):
        """Test concurrent tracing operations."""
        import concurrent.futures
        import threading
        
        def concurrent_operation(operation_id: int):
            """Concurrent operation for testing."""
            workflow_tracer = get_workflow_tracer()
            
            with workflow_tracer.trace_workflow_execution(
                workflow_name=f"concurrent_workflow_{operation_id}",
                workflow_type="concurrent"
            ) as context:
                
                context.add_workflow_event("concurrent_start", {"thread_id": threading.get_ident()})
                time.sleep(0.01)  # Simulate work
                context.set_workflow_attribute("operation_id", operation_id)
                
                return f"completed_{operation_id}"
        
        # Run multiple concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(concurrent_operation, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        assert len(results) == 5
        assert all("completed_" in result for result in results)
    
    def test_sampling_behavior(self):
        """Test adaptive sampling behavior."""
        from crypto_lakehouse.core.otel_tracing import AdaptiveSampler
        
        sampler = AdaptiveSampler(
            default_ratio=0.1,
            workflow_ratio=1.0,
            api_ratio=0.3
        )
        
        # Test workflow sampling (should always sample)
        result = sampler.should_sample(
            parent_context=None,
            trace_id=12345,
            name="workflow.test",
            attributes={"crypto.operation_type": "workflow"}
        )
        assert result.decision == trace.sampling.Decision.RECORD_AND_SAMPLE
        
        # Test high-priority sampling
        result = sampler.should_sample(
            parent_context=None,
            trace_id=12346,
            name="api.test",
            attributes={"crypto.priority": "high"}
        )
        assert result.decision == trace.sampling.Decision.RECORD_AND_SAMPLE


class TestObservabilityConvenienceFunctions:
    """Test convenience functions for observability."""
    
    def test_initialize_crypto_observability(self):
        """Test convenience initialization function."""
        components = initialize_crypto_observability(
            service_name="test-service",
            service_version="1.0.0",
            environment="test"
        )
        
        assert isinstance(components, dict)
        assert len(components) > 0
        
        # Cleanup
        from crypto_lakehouse.core import shutdown_observability
        shutdown_observability()
    
    def test_observability_health_check(self):
        """Test observability health check."""
        # Initialize first
        initialize_crypto_observability(service_name="health-test")
        
        from crypto_lakehouse.core import get_observability_health
        health = get_observability_health()
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "not_initialized"]
        
        # Cleanup
        from crypto_lakehouse.core import shutdown_observability
        shutdown_observability()


@pytest.mark.integration
class TestEndToEndWorkflow:
    """End-to-end integration tests simulating real crypto workflows."""
    
    def test_complete_archive_collection_workflow(self):
        """Test complete archive collection workflow with tracing."""
        # Initialize observability
        components = initialize_crypto_observability(
            service_name="archive-collection-test",
            environment="test"
        )
        
        workflow_tracer = components["workflow_tracer"]
        
        # Simulate complete workflow
        with workflow_tracer.trace_workflow_execution(
            workflow_name="binance_archive_collection",
            workflow_type="batch",
            market="binance",
            symbols=["BTCUSDT", "ETHUSDT"],
            data_types=["klines", "trades"],
            date_range="2025-01-20"
        ) as workflow_context:
            
            # Stage 1: Market data discovery
            with workflow_context.start_stage(
                "market_discovery",
                data_type="exchange_info"
            ) as discovery_context:
                discovery_context.add_processing_event("symbols_discovered", {"count": 2})
                time.sleep(0.005)
            
            # Stage 2: API data collection
            for symbol in ["BTCUSDT", "ETHUSDT"]:
                with workflow_context.start_stage(
                    f"api_collection_{symbol}",
                    symbol=symbol,
                    data_type="klines"
                ) as api_context:
                    
                    # Simulate API calls with manual spans
                    manager = components["manual_span_manager"]
                    
                    with manager.binance_api_span(
                        endpoint=f"https://api.binance.com/api/v3/klines",
                        method="GET",
                        symbol=symbol,
                        data_type="klines"
                    ) as api_span:
                        api_span.set_response_details(200, 50000, 150)
                        time.sleep(0.01)
                    
                    api_context.record_data_stats(1000, 50000)
            
            # Stage 3: Data processing and validation
            with workflow_context.start_stage(
                "data_processing",
                data_type="klines"
            ) as processing_context:
                
                # Use performance-aware operation
                with performance_aware_operation(
                    "kline_validation_and_transformation",
                    performance_budget_ms=5000
                ) as perf_context:
                    
                    perf_context.record_throughput(2000, 100000)
                    time.sleep(0.02)
                
                processing_context.record_data_stats(2000, 100000)
            
            # Stage 4: Storage operations
            with workflow_context.start_stage(
                "storage_operations",
                storage_type="s3"
            ) as storage_context:
                
                # Simulate S3 uploads
                manager = components["manual_span_manager"]
                
                with manager.s3_storage_span(
                    operation="put_object",
                    bucket="crypto-data-lake",
                    key="bronze/binance/klines/batch_2025-01-20.parquet",
                    file_size_bytes=100000
                ) as s3_span:
                    s3_span.set_upload_details(1, 100000, "AES256")
                    time.sleep(0.01)
                
                storage_context.set_file_details(1, 100000)
            
            # Workflow completion
            workflow_context.add_workflow_event("workflow_completed", {
                "total_records": 2000,
                "total_size_bytes": 100000,
                "symbols_processed": 2
            })
        
        # Verify workflow completed successfully
        assert workflow_context.workflow_id is not None
        assert workflow_context._stage_count == 5  # 1 discovery + 2 collection + 1 processing + 1 storage
        
        # Cleanup
        from crypto_lakehouse.core import shutdown_observability
        shutdown_observability()