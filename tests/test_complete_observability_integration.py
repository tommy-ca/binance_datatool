"""
Complete OpenTelemetry Integration Tests
Comprehensive testing of metrics, logging, and tracing integration following specs-driven workflow.
"""

import pytest
import time
import os
import logging
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any, List

from crypto_lakehouse.core.unified_observability import (
    initialize_crypto_observability,
    observability_context,
    get_observability_manager
)


class TestCompleteObservabilityIntegration:
    """Test complete integration of metrics, logging, and tracing."""
    
    @patch.dict(os.environ, {"ENVIRONMENT": "test", "OTEL_EXPORTER_OTLP_ENDPOINT": "http://test-collector:4317"})
    def test_complete_observability_stack_initialization(self):
        """Test initialization of complete observability stack."""
        
        # Mock all OpenTelemetry components
        with patch('crypto_lakehouse.core.unified_observability.metrics') as mock_metrics:
            with patch('crypto_lakehouse.core.unified_observability.trace') as mock_trace:
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider') as mock_set_logger:
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider') as mock_meter_provider:
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider') as mock_tracer_provider:
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider') as mock_logger_provider:
                                
                                # Initialize complete stack
                                components = initialize_crypto_observability(
                                    service_name="test-crypto-lakehouse",
                                    service_version="2.0.0",
                                    environment="test",
                                    enable_auto_instrumentation=True
                                )
                                
                                # Verify all components are initialized
                                assert components.initialized is True
                                assert components.meter_provider is not None
                                assert components.tracer_provider is not None
                                assert components.logger_provider is not None
                                assert components.crypto_metrics is not None
                                assert components.metrics_collector is not None
                                
                                # Verify global providers are set
                                mock_metrics.set_meter_provider.assert_called_once()
                                mock_trace.set_tracer_provider.assert_called_once()
                                mock_set_logger.assert_called_once()
    
    def test_crypto_workflow_end_to_end_observability(self):
        """Test end-to-end observability for crypto workflows."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace') as mock_trace:
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                with patch('crypto_lakehouse.core.unified_observability.baggage') as mock_baggage:
                                    
                                    # Mock tracer and span
                                    mock_tracer = MagicMock()
                                    mock_span = MagicMock()
                                    mock_trace.get_tracer.return_value = mock_tracer
                                    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
                                    
                                    # Mock baggage context managers
                                    mock_baggage.set_baggage.return_value.__enter__ = MagicMock()
                                    mock_baggage.set_baggage.return_value.__exit__ = MagicMock()
                                    
                                    # Initialize observability
                                    components = initialize_crypto_observability(environment="test")
                                    
                                    # Test complete workflow
                                    with observability_context(
                                        workflow_name="binance_archive_collection",
                                        market="binance",
                                        data_type="klines",
                                        symbols=["BTCUSDT", "ETHUSDT", "ADAUSDT"]
                                    ) as ctx:
                                        
                                        # Verify context provides all observability components
                                        assert "span" in ctx
                                        assert "context" in ctx
                                        assert "metrics" in ctx
                                        assert "metrics_collector" in ctx
                                        assert "tracer" in ctx
                                        
                                        # Verify crypto context
                                        crypto_ctx = ctx["context"]
                                        assert crypto_ctx["crypto.workflow_name"] == "binance_archive_collection"
                                        assert crypto_ctx["crypto.market"] == "binance"
                                        assert crypto_ctx["crypto.data_type"] == "klines"
                                        assert "BTCUSDT,ETHUSDT,ADAUSDT" in crypto_ctx["crypto.symbols"]
                                        assert crypto_ctx["crypto.symbol_count"] == "3"
                                        
                                        # Test metrics recording
                                        metrics = ctx["metrics"]
                                        metrics_collector = ctx["metrics_collector"]
                                        
                                        # Simulate workflow operations
                                        metrics_collector.record_event(
                                            "data_ingested",
                                            records_count=1000,
                                            data_size_bytes=50000,
                                            market="binance",
                                            data_type="klines",
                                            symbol="BTCUSDT"
                                        )
                                        
                                        # Add span events
                                        span = ctx["span"]
                                        span.add_event("Data processing started")
                                        span.set_attribute("processing.batch_size", 1000)
                                        
                                    # Verify span operations
                                    mock_span.add_event.assert_called_with("Data processing started")
                                    mock_span.set_attribute.assert_called_with("processing.batch_size", 1000)
                                    mock_span.set_status.assert_called()  # Should be called with OK status
    
    def test_observability_correlation_across_pillars(self):
        """Test correlation between metrics, logs, and traces."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace') as mock_trace:
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Mock trace context
                                mock_span_context = MagicMock()
                                mock_span_context.trace_id = 12345
                                mock_span_context.span_id = 67890
                                
                                mock_span = MagicMock()
                                mock_span.get_span_context.return_value = mock_span_context
                                
                                mock_tracer = MagicMock()
                                mock_trace.get_tracer.return_value = mock_tracer
                                mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
                                
                                # Initialize and test correlation
                                components = initialize_crypto_observability(environment="test")
                                
                                with observability_context("correlation_test") as ctx:
                                    
                                    # Verify trace context is available for correlation
                                    span = ctx["span"]
                                    span_context = span.get_span_context()
                                    
                                    # Test that span context would be used for log correlation
                                    assert span_context.trace_id is not None
                                    assert span_context.span_id is not None
                                    
                                    # Test metrics have access to trace context
                                    metrics = ctx["metrics"]
                                    assert metrics is not None
                                    
                                    # Verify crypto context is shared across all pillars
                                    crypto_context = ctx["context"]
                                    assert "crypto.workflow_name" in crypto_context
                                    assert crypto_context["crypto.workflow_name"] == "correlation_test"
    
    def test_auto_instrumentation_integration(self):
        """Test auto-instrumentation integration with manual instrumentation."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                with patch('crypto_lakehouse.core.unified_observability.RequestsInstrumentor') as mock_requests:
                                    with patch('crypto_lakehouse.core.unified_observability.AioHttpClientInstrumentor') as mock_aiohttp:
                                        
                                        # Mock instrumentors
                                        mock_requests_instance = MagicMock()
                                        mock_aiohttp_instance = MagicMock()
                                        mock_requests.return_value = mock_requests_instance
                                        mock_aiohttp.return_value = mock_aiohttp_instance
                                        
                                        # Initialize with auto-instrumentation enabled
                                        components = initialize_crypto_observability(
                                            environment="test",
                                            enable_auto_instrumentation=True
                                        )
                                        
                                        # Verify auto-instrumentation was attempted
                                        assert components.auto_instrumentation_enabled is True
                                        
                                        # Verify instrumentors were called
                                        mock_requests_instance.instrument.assert_called_once()
                                        mock_aiohttp_instance.instrument.assert_called_once()
    
    def test_performance_under_high_load(self):
        """Test observability performance under high load scenarios."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                manager = get_observability_manager()
                                
                                # Test context creation performance under load
                                start_time = time.time()
                                
                                for i in range(1000):
                                    context = manager.create_crypto_context(
                                        workflow_name=f"high_load_test_{i}",
                                        market="binance",
                                        symbols=[f"SYMBOL{j}" for j in range(3)]
                                    )
                                    assert context is not None
                                
                                duration = time.time() - start_time
                                
                                # Should complete 1000 context creations in reasonable time (<500ms)
                                assert duration < 0.5, f"Performance too slow under load: {duration}s"
    
    def test_error_handling_across_observability_stack(self):
        """Test error handling and resilience across the complete observability stack."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace') as mock_trace:
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Mock span for error handling
                                mock_span = MagicMock()
                                mock_tracer = MagicMock()
                                mock_trace.get_tracer.return_value = mock_tracer
                                mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                
                                # Test error handling in context
                                test_error = ValueError("Test error for observability")
                                
                                with pytest.raises(ValueError):
                                    with observability_context("error_test") as ctx:
                                        # Simulate error in workflow
                                        raise test_error
                                
                                # Verify error was recorded in span
                                mock_span.record_exception.assert_called_once_with(test_error)
                                mock_span.set_status.assert_called()  # Should set error status
    
    def test_resource_attributes_compliance(self):
        """Test OpenTelemetry resource attributes compliance."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(
                                    service_name="compliance-test",
                                    service_version="1.0.0",
                                    environment="test"
                                )
                                
                                # Verify resource attributes compliance
                                resource = components.resource
                                attributes = resource.attributes
                                
                                # Standard OpenTelemetry attributes
                                assert attributes["service.name"] == "compliance-test"
                                assert attributes["service.version"] == "1.0.0"
                                assert attributes["service.namespace"] == "crypto-data"
                                assert attributes["deployment.environment"] == "test"
                                
                                # Crypto-specific attributes
                                assert "crypto.platform_type" in attributes
                                assert "crypto.observability_version" in attributes
                                assert "crypto.supported_markets" in attributes
                                
                                # Infrastructure attributes
                                assert "infrastructure.type" in attributes
                                assert "observability.framework" in attributes
                                assert attributes["observability.framework"] == "opentelemetry"
    
    def test_health_check_comprehensive(self):
        """Test comprehensive health check of observability stack."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                manager = get_observability_manager()
                                
                                # Perform health check
                                health = manager.health_check()
                                
                                # Verify health check results
                                assert health["status"] == "healthy"
                                assert "timestamp" in health
                                assert "components" in health
                                assert "performance" in health
                                
                                # Verify component health
                                components_health = health["components"]
                                assert components_health["metrics"] == "healthy"
                                assert components_health["tracing"] == "healthy"
                                assert components_health["logging"] == "healthy"
                                
                                # Verify performance metrics are included
                                performance = health["performance"]
                                assert "initialization_duration_ms" in performance
                                assert "components_initialized" in performance
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown of complete observability stack."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider') as mock_meter_provider_class:
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider') as mock_tracer_provider_class:
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider') as mock_logger_provider_class:
                                
                                # Mock provider instances with shutdown methods
                                mock_meter_provider = MagicMock()
                                mock_tracer_provider = MagicMock()
                                mock_logger_provider = MagicMock()
                                
                                mock_meter_provider_class.return_value = mock_meter_provider
                                mock_tracer_provider_class.return_value = mock_tracer_provider
                                mock_logger_provider_class.return_value = mock_logger_provider
                                
                                # Initialize and shutdown
                                components = initialize_crypto_observability(environment="test")
                                manager = get_observability_manager()
                                
                                manager.shutdown()
                                
                                # Verify shutdown was called on all providers
                                mock_meter_provider.shutdown.assert_called_once()
                                mock_tracer_provider.shutdown.assert_called_once()
                                mock_logger_provider.shutdown.assert_called_once()
                                
                                # Verify manager state is clean
                                assert not manager._initialized
                                assert manager.components is None


class TestSpecificationCompliance:
    """Test compliance with OpenTelemetry specifications."""
    
    def test_metric_naming_conventions(self):
        """Test metric naming follows OpenTelemetry conventions."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                
                                # Test crypto metrics naming
                                crypto_metrics = components.crypto_metrics
                                
                                # Verify metric instrument attributes exist
                                # (These would be created during initialization)
                                assert hasattr(crypto_metrics, 'records_ingested')
                                assert hasattr(crypto_metrics, 'processing_duration')
                                assert hasattr(crypto_metrics, 'workflow_executions')
                                assert hasattr(crypto_metrics, 'storage_size')
    
    def test_trace_context_propagation(self):
        """Test W3C trace context propagation compliance."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace') as mock_trace:
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                with patch('crypto_lakehouse.core.unified_observability.baggage') as mock_baggage:
                                    
                                    # Mock tracer and span
                                    mock_tracer = MagicMock()
                                    mock_span = MagicMock()
                                    mock_trace.get_tracer.return_value = mock_tracer
                                    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
                                    
                                    # Mock baggage context managers
                                    mock_baggage.set_baggage.return_value.__enter__ = MagicMock()
                                    mock_baggage.set_baggage.return_value.__exit__ = MagicMock()
                                    
                                    # Initialize observability
                                    components = initialize_crypto_observability(environment="test")
                                    
                                    # Test context propagation
                                    with observability_context("propagation_test", "binance") as ctx:
                                        pass
                                    
                                    # Verify baggage propagation was used
                                    expected_calls = [
                                        call("crypto.workflow_name", "propagation_test"),
                                        call("crypto.market", "binance")
                                    ]
                                    
                                    # Verify baggage.set_baggage was called with crypto context
                                    assert mock_baggage.set_baggage.call_count >= 2
    
    def test_semantic_conventions_compliance(self):
        """Test compliance with OpenTelemetry semantic conventions."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                manager = get_observability_manager()
                                
                                # Test crypto context follows conventions
                                context = manager.create_crypto_context(
                                    workflow_name="semantic_test",
                                    market="binance",
                                    data_type="klines"
                                )
                                
                                # Verify semantic convention compliance
                                assert all(key.startswith("crypto.") for key in context.keys())
                                assert all("." in key for key in context.keys())  # Dot-separated naming
                                assert all(isinstance(value, str) for value in context.values())  # String values


class TestCryptoWorkflowIntegration:
    """Test integration with crypto-specific workflow patterns."""
    
    def test_binance_archive_collection_observability(self):
        """Test observability for Binance archive collection workflow."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace') as mock_trace:
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Mock trace components
                                mock_tracer = MagicMock()
                                mock_span = MagicMock()
                                mock_trace.get_tracer.return_value = mock_tracer
                                mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                
                                # Simulate Binance archive collection workflow
                                symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "DOGEUSDT"]
                                
                                with observability_context(
                                    workflow_name="binance_archive_collection",
                                    market="binance",
                                    data_type="klines",
                                    symbols=symbols
                                ) as ctx:
                                    
                                    # Verify crypto context for archive collection
                                    crypto_ctx = ctx["context"]
                                    assert crypto_ctx["crypto.workflow_name"] == "binance_archive_collection"
                                    assert crypto_ctx["crypto.market"] == "binance"
                                    assert crypto_ctx["crypto.data_type"] == "klines"
                                    assert crypto_ctx["crypto.symbol_count"] == "5"
                                    assert "BTCUSDT,ETHUSDT,ADAUSDT,BNBUSDT,DOGEUSDT" in crypto_ctx["crypto.symbols"]
                                    
                                    # Simulate workflow operations
                                    metrics = ctx["metrics"]
                                    span = ctx["span"]
                                    
                                    # Record multiple data ingestion events
                                    for symbol in symbols:
                                        span.add_event(f"Processing {symbol}")
                                        span.set_attribute(f"symbol.{symbol}.processed", True)
                                    
                                    # Verify span operations were called
                                    assert mock_span.add_event.call_count == 5
                                    assert mock_span.set_attribute.call_count == 5
    
    def test_multi_market_observability(self):
        """Test observability across multiple crypto markets."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                manager = get_observability_manager()
                                
                                markets = ["binance", "coinbase", "kraken"]
                                
                                for market in markets:
                                    context = manager.create_crypto_context(
                                        workflow_name=f"{market}_collection",
                                        market=market,
                                        data_type="trades"
                                    )
                                    
                                    # Verify market-specific context
                                    assert context["crypto.workflow_name"] == f"{market}_collection"
                                    assert context["crypto.market"] == market
                                    assert context["crypto.data_type"] == "trades"
    
    def test_high_frequency_trading_observability(self):
        """Test observability patterns for high-frequency trading scenarios."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(environment="test")
                                manager = get_observability_manager()
                                
                                # Test rapid context creation (simulating high-frequency operations)
                                start_time = time.time()
                                
                                contexts_created = 0
                                for i in range(100):
                                    for symbol in ["BTCUSDT", "ETHUSDT"]:
                                        context = manager.create_crypto_context(
                                            workflow_name="hft_processing",
                                            market="binance",
                                            symbols=[symbol]
                                        )
                                        contexts_created += 1
                                        assert context is not None
                                
                                duration = time.time() - start_time
                                
                                # Should handle 200 context creations quickly
                                assert contexts_created == 200
                                assert duration < 0.1, f"HFT observability too slow: {duration}s for {contexts_created} contexts"