"""
Comprehensive tests for unified OpenTelemetry observability integration.
Tests metrics, logging, tracing integration and performance characteristics.
"""

import pytest
import time
import os
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from crypto_lakehouse.core.unified_observability import (
    UnifiedObservabilityManager,
    ObservabilityComponents,
    initialize_crypto_observability,
    get_observability_manager,
    observability_context
)


class TestUnifiedObservabilityManager:
    """Test unified observability manager functionality."""
    
    def test_manager_initialization(self):
        """Test observability manager initialization."""
        manager = UnifiedObservabilityManager(
            service_name="test-crypto-lakehouse",
            service_version="1.0.0",
            environment="test"
        )
        
        assert manager.service_name == "test-crypto-lakehouse"
        assert manager.service_version == "1.0.0"
        assert manager.environment == "test"
        assert not manager._initialized
    
    @patch('crypto_lakehouse.core.unified_observability.metrics')
    @patch('crypto_lakehouse.core.unified_observability.trace')
    @patch('crypto_lakehouse.core.unified_observability.set_logger_provider')
    def test_complete_initialization(self, mock_set_logger, mock_trace, mock_metrics):
        """Test complete initialization of all observability components."""
        
        # Mock providers
        mock_meter_provider = MagicMock()
        mock_tracer_provider = MagicMock()
        mock_logger_provider = MagicMock()
        
        with patch('crypto_lakehouse.core.unified_observability.MeterProvider', 
                  return_value=mock_meter_provider):
            with patch('crypto_lakehouse.core.unified_observability.TracerProvider',
                      return_value=mock_tracer_provider):
                with patch('crypto_lakehouse.core.unified_observability.LoggerProvider',
                          return_value=mock_logger_provider):
                    
                    manager = UnifiedObservabilityManager(environment="test")
                    components = manager.initialize()
                    
                    # Verify components are created
                    assert isinstance(components, ObservabilityComponents)
                    assert components.initialized is True
                    assert components.meter_provider is mock_meter_provider
                    assert components.tracer_provider is mock_tracer_provider
                    assert components.logger_provider is mock_logger_provider
                    
                    # Verify global providers are set
                    mock_metrics.set_meter_provider.assert_called_once_with(mock_meter_provider)
                    mock_trace.set_tracer_provider.assert_called_once_with(mock_tracer_provider)
                    mock_set_logger.assert_called_once_with(mock_logger_provider)
    
    def test_enhanced_resource_creation(self):
        """Test enhanced resource creation with crypto-specific attributes."""
        manager = UnifiedObservabilityManager(environment="test")
        
        with patch('crypto_lakehouse.core.unified_observability.OpenTelemetryConfig') as mock_config_class:
            mock_config = MagicMock()
            mock_base_resource = MagicMock()
            mock_base_resource.attributes = {
                "service.name": "test-service",
                "service.version": "1.0.0"
            }
            mock_config.create_resource.return_value = mock_base_resource
            mock_config_class.return_value = mock_config
            
            resource = manager._create_enhanced_resource(mock_config)
            
            # Verify enhanced attributes are added
            expected_attributes = [
                "crypto.platform_type",
                "crypto.observability_version", 
                "crypto.supported_markets",
                "infrastructure.type",
                "observability.framework",
                "performance.target_overhead"
            ]
            
            for attr in expected_attributes:
                assert attr in resource.attributes
    
    def test_crypto_context_creation(self):
        """Test crypto-specific context creation."""
        manager = UnifiedObservabilityManager()
        
        context = manager.create_crypto_context(
            workflow_name="test_workflow",
            market="binance",
            data_type="klines",
            symbols=["BTCUSDT", "ETHUSDT"]
        )
        
        assert context["crypto.workflow_name"] == "test_workflow"
        assert context["crypto.market"] == "binance"
        assert context["crypto.data_type"] == "klines"
        assert context["crypto.symbols"] == "BTCUSDT,ETHUSDT"
        assert context["crypto.symbol_count"] == "2"
        assert "crypto.timestamp" in context
    
    def test_crypto_context_symbol_limiting(self):
        """Test symbol limiting in crypto context."""
        manager = UnifiedObservabilityManager()
        
        symbols = [f"SYMBOL{i}" for i in range(10)]  # 10 symbols
        context = manager.create_crypto_context(
            workflow_name="test",
            symbols=symbols
        )
        
        # Should limit to 5 symbols
        symbol_list = context["crypto.symbols"].split(",")
        assert len(symbol_list) == 5
        assert context["crypto.symbol_count"] == "10"
    
    @patch('crypto_lakehouse.core.unified_observability.UnifiedObservabilityManager.initialize')
    def test_performance_tracking(self, mock_initialize):
        """Test initialization performance tracking."""
        manager = UnifiedObservabilityManager()
        
        # Mock components
        mock_components = MagicMock()
        mock_components.crypto_metrics = MagicMock()
        mock_initialize.return_value = mock_components
        manager.components = mock_components
        
        # Simulate initialization delay
        manager._init_start_time = time.time() - 0.1  # 100ms ago
        manager._track_initialization_performance()
        
        metrics = manager.get_performance_metrics()
        
        assert "initialization_duration_ms" in metrics
        assert metrics["initialization_duration_ms"] >= 100  # At least 100ms
        assert metrics["components_initialized"] == 3
        assert "initialization_timestamp" in metrics
    
    @patch('crypto_lakehouse.core.unified_observability.trace')
    @patch('crypto_lakehouse.core.unified_observability.baggage')
    def test_observability_context_success(self, mock_baggage, mock_trace):
        """Test successful observability context execution."""
        manager = UnifiedObservabilityManager()
        
        # Mock components
        mock_components = MagicMock()
        mock_metrics_collector = MagicMock()
        mock_crypto_metrics = MagicMock()
        mock_components.metrics_collector = mock_metrics_collector
        mock_components.crypto_metrics = mock_crypto_metrics
        manager.components = mock_components
        manager._initialized = True
        
        # Mock tracer and span
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Mock baggage context managers
        mock_baggage.set_baggage.return_value.__enter__ = MagicMock()
        mock_baggage.set_baggage.return_value.__exit__ = MagicMock()
        
        # Test successful execution
        with manager.observability_context("test_workflow", "binance") as ctx:
            assert "span" in ctx
            assert "context" in ctx
            assert "metrics" in ctx
            assert "metrics_collector" in ctx
            assert "tracer" in ctx
        
        # Verify workflow metrics were called
        mock_metrics_collector.start_workflow.assert_called_once_with("test_workflow")
        mock_metrics_collector.end_workflow.assert_called_once_with("test_workflow")
        
        # Verify span status was set to OK
        mock_span.set_status.assert_called()
    
    @patch('crypto_lakehouse.core.unified_observability.trace')
    def test_observability_context_error_handling(self, mock_trace):
        """Test error handling in observability context."""
        manager = UnifiedObservabilityManager()
        
        # Mock components
        mock_components = MagicMock()
        mock_crypto_metrics = MagicMock()
        mock_components.crypto_metrics = mock_crypto_metrics
        manager.components = mock_components
        manager._initialized = True
        
        # Mock tracer and span
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        
        # Test error handling
        test_error = Exception("Test error")
        
        with pytest.raises(Exception):
            with manager.observability_context("test_workflow") as ctx:
                raise test_error
        
        # Verify error was recorded in span
        mock_span.record_exception.assert_called_once_with(test_error)
        mock_span.set_status.assert_called()
        
        # Verify error was recorded in metrics
        mock_crypto_metrics.record_error.assert_called_once()
    
    def test_health_check_healthy(self):
        """Test health check with healthy components."""
        manager = UnifiedObservabilityManager()
        
        # Mock healthy components
        mock_components = MagicMock()
        mock_components.meter_provider = MagicMock()
        mock_components.tracer_provider = MagicMock()
        mock_components.logger_provider = MagicMock()
        mock_components.auto_instrumentation_enabled = True
        
        manager.components = mock_components
        manager._initialized = True
        
        health = manager.health_check()
        
        assert health["status"] == "healthy"
        assert health["components"]["metrics"] == "healthy"
        assert health["components"]["tracing"] == "healthy"
        assert health["components"]["logging"] == "healthy"
        assert health["components"]["auto_instrumentation"] == "enabled"
    
    def test_health_check_not_initialized(self):
        """Test health check when not initialized."""
        manager = UnifiedObservabilityManager()
        
        health = manager.health_check()
        
        assert health["status"] == "not_initialized"
    
    def test_health_check_degraded(self):
        """Test health check with missing components."""
        manager = UnifiedObservabilityManager()
        
        # Mock components with missing tracer
        mock_components = MagicMock()
        mock_components.meter_provider = MagicMock()
        mock_components.tracer_provider = None  # Missing
        mock_components.logger_provider = MagicMock()
        mock_components.auto_instrumentation_enabled = False
        
        manager.components = mock_components
        manager._initialized = True
        
        health = manager.health_check()
        
        assert health["status"] == "degraded"
        assert health["components"]["metrics"] == "healthy"
        assert health["components"]["tracing"] == "unhealthy"
        assert health["components"]["logging"] == "healthy"
        assert health["components"]["auto_instrumentation"] == "disabled"
    
    def test_shutdown(self):
        """Test graceful shutdown of observability components."""
        manager = UnifiedObservabilityManager()
        
        # Mock components with shutdown methods
        mock_components = MagicMock()
        mock_meter_provider = MagicMock()
        mock_tracer_provider = MagicMock()
        mock_logger_provider = MagicMock()
        
        mock_components.meter_provider = mock_meter_provider
        mock_components.tracer_provider = mock_tracer_provider
        mock_components.logger_provider = mock_logger_provider
        
        manager.components = mock_components
        manager._initialized = True
        
        manager.shutdown()
        
        # Verify shutdown was called on all providers
        mock_meter_provider.shutdown.assert_called_once()
        mock_tracer_provider.shutdown.assert_called_once()
        mock_logger_provider.shutdown.assert_called_once()
        
        # Verify manager state is reset
        assert not manager._initialized
        assert manager.components is None


class TestGlobalFunctions:
    """Test global utility functions."""
    
    @patch('crypto_lakehouse.core.unified_observability.UnifiedObservabilityManager')
    def test_initialize_crypto_observability(self, mock_manager_class):
        """Test global initialization function."""
        mock_manager = MagicMock()
        mock_components = MagicMock()
        mock_manager.initialize.return_value = mock_components
        mock_manager_class.return_value = mock_manager
        
        # Clear global state
        import crypto_lakehouse.core.unified_observability
        crypto_lakehouse.core.unified_observability._global_observability_manager = None
        
        components = initialize_crypto_observability(
            service_name="test-service",
            service_version="1.0.0",
            environment="test"
        )
        
        assert components is mock_components
        mock_manager_class.assert_called_once_with(
            service_name="test-service",
            service_version="1.0.0",
            environment="test",
            enable_auto_instrumentation=True
        )
        mock_manager.initialize.assert_called_once()
    
    def test_get_observability_manager(self):
        """Test getting global observability manager."""
        # Clear global state
        import crypto_lakehouse.core.unified_observability
        crypto_lakehouse.core.unified_observability._global_observability_manager = None
        
        # Should return None when not initialized
        manager = get_observability_manager()
        assert manager is None
        
        # Initialize and test again
        initialize_crypto_observability()
        manager = get_observability_manager()
        assert manager is not None
        assert isinstance(manager, UnifiedObservabilityManager)
    
    @patch('crypto_lakehouse.core.unified_observability.initialize_crypto_observability')
    def test_observability_context_function(self, mock_initialize):
        """Test global observability context function."""
        mock_manager = MagicMock()
        mock_components = MagicMock()
        mock_initialize.return_value = mock_components
        
        # Clear global state
        import crypto_lakehouse.core.unified_observability
        crypto_lakehouse.core.unified_observability._global_observability_manager = mock_manager
        
        # Mock context manager
        mock_context_manager = MagicMock()
        mock_manager.observability_context.return_value = mock_context_manager
        
        result = observability_context(
            workflow_name="test_workflow",
            market="binance",
            symbols=["BTCUSDT"]
        )
        
        assert result is mock_context_manager
        mock_manager.observability_context.assert_called_once_with(
            workflow_name="test_workflow",
            market="binance",
            data_type="klines",
            symbols=["BTCUSDT"],
            record_metrics=True
        )


class TestIntegrationScenarios:
    """Test end-to-end integration scenarios."""
    
    @patch.dict(os.environ, {"ENVIRONMENT": "test"})
    def test_complete_workflow_observability(self):
        """Test complete workflow with all observability components."""
        
        # Mock all OpenTelemetry components to avoid actual initialization
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                # Initialize observability
                                components = initialize_crypto_observability(
                                    service_name="integration-test",
                                    environment="test"
                                )
                                
                                assert components is not None
                                assert components.initialized
                                
                                # Test context usage
                                with observability_context(
                                    workflow_name="integration_test",
                                    market="binance",
                                    symbols=["BTCUSDT", "ETHUSDT"]
                                ) as ctx:
                                    
                                    # Verify context contains all expected components
                                    assert "span" in ctx
                                    assert "context" in ctx
                                    assert "metrics" in ctx
                                    assert "metrics_collector" in ctx
                                    assert "tracer" in ctx
                                    
                                    # Verify crypto context
                                    crypto_ctx = ctx["context"]
                                    assert crypto_ctx["crypto.workflow_name"] == "integration_test"
                                    assert crypto_ctx["crypto.market"] == "binance"
                                    assert "BTCUSDT,ETHUSDT" in crypto_ctx["crypto.symbols"]
    
    def test_performance_under_load(self):
        """Test performance characteristics under simulated load."""
        
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                
                                manager = UnifiedObservabilityManager(environment="test")
                                components = manager.initialize()
                                
                                # Measure context creation performance
                                start_time = time.time()
                                
                                for i in range(100):
                                    context = manager.create_crypto_context(
                                        workflow_name=f"test_workflow_{i}",
                                        market="binance",
                                        symbols=[f"SYMBOL{j}" for j in range(5)]
                                    )
                                    assert context is not None
                                
                                duration = time.time() - start_time
                                
                                # Should complete 100 context creations quickly (<100ms)
                                assert duration < 0.1, f"Context creation too slow: {duration}s"
    
    def test_error_resilience(self):
        """Test error handling and resilience."""
        
        # Test initialization failure resilience
        with patch('crypto_lakehouse.core.unified_observability.MeterProvider') as mock_meter:
            mock_meter.side_effect = Exception("Meter initialization failed")
            
            manager = UnifiedObservabilityManager(environment="test")
            
            with pytest.raises(Exception):
                manager.initialize()
            
            # Verify manager state remains clean after failure
            assert not manager._initialized
            assert manager.components is None
    
    def test_auto_instrumentation_fallback(self):
        """Test auto-instrumentation with missing libraries."""
        
        # Mock successful core initialization but failed auto-instrumentation
        with patch('crypto_lakehouse.core.unified_observability.metrics'):
            with patch('crypto_lakehouse.core.unified_observability.trace'):
                with patch('crypto_lakehouse.core.unified_observability.set_logger_provider'):
                    with patch('crypto_lakehouse.core.unified_observability.MeterProvider'):
                        with patch('crypto_lakehouse.core.unified_observability.TracerProvider'):
                            with patch('crypto_lakehouse.core.unified_observability.LoggerProvider'):
                                with patch('crypto_lakehouse.core.unified_observability.RequestsInstrumentor') as mock_requests:
                                    mock_requests.side_effect = ImportError("Library not available")
                                    
                                    manager = UnifiedObservabilityManager(
                                        environment="test",
                                        enable_auto_instrumentation=True
                                    )
                                    components = manager.initialize()
                                    
                                    # Should succeed even with auto-instrumentation failures
                                    assert components.initialized
                                    assert not components.auto_instrumentation_enabled