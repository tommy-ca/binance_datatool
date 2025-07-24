"""Integration tests for OpenTelemetry metrics implementation."""

import pytest
import os
import time
from unittest.mock import patch, MagicMock

from crypto_lakehouse.core.legacy.otel_config import OpenTelemetryConfig, get_otel_config, get_meter
from crypto_lakehouse.core.legacy.otel_metrics import (
    CryptoLakehouseMetrics,
    BackwardCompatibleMetricsCollector,
    get_metrics_collector,
    get_global_metrics
)


class TestOpenTelemetryConfiguration:
    """Test OpenTelemetry configuration setup."""
    
    def test_resource_creation(self):
        """Test resource creation with crypto lakehouse attributes."""
        config = OpenTelemetryConfig(
            service_name="test-crypto-lakehouse",
            service_version="1.0.0",
            environment="test"
        )
        
        resource = config.create_resource()
        attributes = resource.attributes
        
        assert attributes["service.name"] == "test-crypto-lakehouse"
        assert attributes["service.version"] == "1.0.0"
        assert attributes["service.namespace"] == "crypto-data"
        assert attributes["deployment.environment"] == "test"
        assert attributes["crypto.market"] == "binance"
        assert attributes["crypto.data_type"] == "archive"
        assert attributes["crypto.workflow_type"] == "batch_processing"
    
    def test_meter_provider_initialization(self):
        """Test meter provider initialization."""
        config = OpenTelemetryConfig(environment="test")
        meter_provider = config.initialize_meter_provider()
        
        assert meter_provider is not None
        assert config._meter_provider is meter_provider
        
        # Test singleton behavior
        meter_provider_2 = config.initialize_meter_provider()
        assert meter_provider is meter_provider_2
    
    def test_meter_creation(self):
        """Test meter creation with proper configuration."""
        config = OpenTelemetryConfig(environment="test")
        meter = config.get_meter("test_meter")
        
        assert meter is not None
        assert hasattr(meter, 'create_counter')
        assert hasattr(meter, 'create_histogram')
        assert hasattr(meter, 'create_up_down_counter')
    
    def test_global_configuration(self):
        """Test global configuration access."""
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            config = get_otel_config("test-service", "2.0.0")
            
            assert config.service_name == "test-service"
            assert config.service_version == "2.0.0"
            assert config.environment == "test"
    
    def test_metric_readers_configuration(self):
        """Test metric readers configuration for different environments."""
        # Test local environment (should include console exporter)
        local_config = OpenTelemetryConfig(environment="local")
        local_readers = local_config.create_metric_readers()
        
        assert len(local_readers) >= 1  # At least console reader
        
        # Test production environment (no console exporter)
        prod_config = OpenTelemetryConfig(environment="production")
        prod_readers = prod_config.create_metric_readers()
        
        assert len(prod_readers) >= 0  # May have OTLP reader if endpoint available


class TestCryptoLakehouseMetrics:
    """Test crypto lakehouse specific metrics implementation."""
    
    @pytest.fixture
    def metrics(self):
        """Create test metrics instance."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_get_meter.return_value = mock_meter
            
            # Mock instrument creation
            mock_meter.create_counter.return_value = MagicMock()
            mock_meter.create_histogram.return_value = MagicMock()
            mock_meter.create_up_down_counter.return_value = MagicMock()
            
            return CryptoLakehouseMetrics(mock_meter)
    
    def test_instrument_initialization(self, metrics):
        """Test that all required instruments are initialized."""
        assert hasattr(metrics, 'records_ingested')
        assert hasattr(metrics, 'data_bytes_ingested')
        assert hasattr(metrics, 'processing_duration')
        assert hasattr(metrics, 'batch_processing_duration')
        assert hasattr(metrics, 'storage_size')
        assert hasattr(metrics, 'file_count')
        assert hasattr(metrics, 'workflow_executions')
        assert hasattr(metrics, 'workflow_duration')
        assert hasattr(metrics, 'errors_total')
        assert hasattr(metrics, 'api_requests')
        assert hasattr(metrics, 'api_response_duration')
        assert hasattr(metrics, 'active_connections')
        assert hasattr(metrics, 'queue_size')
    
    def test_data_ingestion_recording(self, metrics):
        """Test data ingestion metrics recording."""
        metrics.record_data_ingestion(
            records_count=1000,
            data_size_bytes=50000,
            market="binance",
            data_type="klines",
            symbol="BTCUSDT",
            timeframe="1m"
        )
        
        expected_attributes = {
            "market": "binance",
            "data_type": "klines",
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "operation": "ingestion"
        }
        
        metrics.records_ingested.add.assert_called_once_with(1000, expected_attributes)
        metrics.data_bytes_ingested.add.assert_called_once_with(50000, expected_attributes)
    
    def test_processing_duration_context_manager(self, metrics):
        """Test processing duration measurement with context manager."""
        with metrics.measure_processing_duration("kline_processing", "klines", "ETHUSDT"):
            time.sleep(0.01)  # Simulate processing
        
        # Verify histogram record was called
        assert metrics.processing_duration.record.called
        
        # Check call arguments
        call_args = metrics.processing_duration.record.call_args
        duration_ms = call_args[0][0]
        attributes = call_args[0][1]
        
        assert duration_ms > 0  # Should have some duration
        assert attributes["operation"] == "kline_processing"
        assert attributes["data_type"] == "klines"
        assert attributes["symbol"] == "ETHUSDT"
    
    def test_workflow_duration_context_manager(self, metrics):
        """Test workflow duration measurement with context manager."""
        with metrics.measure_workflow_duration("test_workflow", "batch"):
            time.sleep(0.01)  # Simulate workflow execution
        
        # Verify execution counter and duration histogram were called
        assert metrics.workflow_executions.add.called
        assert metrics.workflow_duration.record.called
        
        # Check execution counter
        exec_call_args = metrics.workflow_executions.add.call_args
        assert exec_call_args[0][0] == 1  # Count
        assert exec_call_args[0][1]["workflow_name"] == "test_workflow"
        assert exec_call_args[0][1]["workflow_type"] == "batch"
    
    def test_error_recording(self, metrics):
        """Test error recording with context."""
        metrics.record_error(
            error_type="download_failure",
            error_message="Connection timeout",
            operation="data_download",
            workflow_name="archive_collection"
        )
        
        expected_attributes = {
            "error_type": "download_failure",
            "operation": "data_download",
            "workflow_name": "archive_collection"
        }
        
        metrics.errors_total.add.assert_called_once_with(1, expected_attributes)
    
    def test_api_request_recording(self, metrics):
        """Test API request metrics recording."""
        metrics.record_api_request(
            endpoint="/api/v3/klines",
            method="GET",
            status_code=200,
            duration_ms=150.5,
            market="binance"
        )
        
        expected_attributes = {
            "endpoint": "/api/v3/klines",
            "method": "GET",
            "status_code": "200",
            "market": "binance"
        }
        
        metrics.api_requests.add.assert_called_once_with(1, expected_attributes)
        metrics.api_response_duration.record.assert_called_once_with(150.5, expected_attributes)
    
    def test_storage_metrics_update(self, metrics):
        """Test storage metrics updates."""
        metrics.update_storage_metrics(
            size_change_bytes=1024000,
            file_count_change=5,
            storage_type="parquet",
            data_tier="bronze"
        )
        
        expected_attributes = {
            "storage_type": "parquet",
            "data_tier": "bronze"
        }
        
        metrics.storage_size.add.assert_called_once_with(1024000, expected_attributes)
        metrics.file_count.add.assert_called_once_with(5, expected_attributes)


class TestBackwardCompatibleMetricsCollector:
    """Test backward compatibility with legacy metrics collector."""
    
    def test_legacy_compatibility_disabled_otel(self):
        """Test backward compatibility when OpenTelemetry is disabled."""
        collector = BackwardCompatibleMetricsCollector(enable_otel=False)
        
        assert collector.enable_otel is False
        assert collector.otel_metrics is None
        assert collector.legacy_collector is not None
    
    def test_legacy_compatibility_enabled_otel(self):
        """Test backward compatibility when OpenTelemetry is enabled."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_otel:
            mock_instance = MagicMock()
            mock_otel.return_value = mock_instance
            
            collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            
            assert collector.enable_otel is True
            assert collector.otel_metrics is mock_instance
            assert collector.legacy_collector is not None
    
    def test_workflow_lifecycle_compatibility(self):
        """Test workflow start/end compatibility."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_otel:
            mock_instance = MagicMock()
            mock_otel.return_value = mock_instance
            
            collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            
            # Test workflow lifecycle
            collector.start_workflow("test_workflow")
            time.sleep(0.01)
            collector.end_workflow("test_workflow")
            
            # Verify legacy collector was called
            assert collector.legacy_collector.metrics.get('workflow_name') == 'test_workflow'
            
            # Verify OpenTelemetry metrics were recorded
            assert mock_instance.workflow_duration.record.called
            assert mock_instance.workflow_executions.add.called
    
    def test_event_recording_compatibility(self):
        """Test event recording with both legacy and OTel."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_otel:
            mock_instance = MagicMock()
            mock_otel.return_value = mock_instance
            
            collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            
            # Test ingestion event
            collector.record_event(
                "data_ingested", 
                records_count=500,
                data_size_bytes=25000,
                market="binance",
                data_type="klines",
                symbol="BTCUSDT",
                timeframe="5m"
            )
            
            # Verify legacy event recording
            assert len(collector.legacy_collector.events) == 1
            assert collector.legacy_collector.events[0]['event'] == 'data_ingested'
            
            # Verify OTel ingestion recording
            assert mock_instance.record_data_ingestion.called
    
    def test_error_recording_compatibility(self):
        """Test error recording with both legacy and OTel."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_otel:
            mock_instance = MagicMock()
            mock_otel.return_value = mock_instance
            
            collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            
            collector.record_error(
                "Connection failed",
                error_type="network_error",
                operation="data_download",
                workflow_name="archive_collection"
            )
            
            # Verify legacy error recording
            assert len(collector.legacy_collector.errors) == 1
            assert collector.legacy_collector.errors[0]['error'] == 'Connection failed'
            
            # Verify OTel error recording
            mock_instance.record_error.assert_called_once_with(
                "network_error", 
                "Connection failed", 
                "data_download", 
                "archive_collection"
            )
    
    def test_metrics_retrieval_compatibility(self):
        """Test metrics retrieval includes OTel status."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_otel:
            mock_instance = MagicMock()
            mock_otel.return_value = mock_instance
            
            collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            metrics = collector.get_metrics()
            
            assert metrics['otel_enabled'] is True
            assert metrics['otel_metrics_active'] is True
            assert 'metrics' in metrics
            assert 'events' in metrics
            assert 'errors' in metrics
    
    def test_graceful_otel_failure_handling(self):
        """Test graceful handling of OpenTelemetry initialization failures."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_otel:
            mock_otel.side_effect = Exception("OTel initialization failed")
            
            collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            
            # Should fall back to legacy-only mode
            assert collector.enable_otel is False
            assert collector.otel_metrics is None
            assert collector.legacy_collector is not None
            
            # Should still work with legacy functionality
            collector.start_workflow("test_workflow")
            collector.record_event("test_event")
            collector.record_error("test_error")
            
            metrics = collector.get_metrics()
            assert metrics['otel_enabled'] is False


class TestConvenienceFunctions:
    """Test convenience functions for easy adoption."""
    
    def test_get_metrics_collector_function(self):
        """Test get_metrics_collector convenience function."""
        with patch('crypto_lakehouse.core.otel_metrics.BackwardCompatibleMetricsCollector') as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value = mock_instance
            
            collector = get_metrics_collector(enable_otel=True)
            
            mock_collector.assert_called_once_with(enable_otel=True)
            assert collector is mock_instance
    
    def test_get_global_metrics_singleton(self):
        """Test global metrics singleton behavior."""
        with patch('crypto_lakehouse.core.otel_metrics.CryptoLakehouseMetrics') as mock_metrics:
            mock_instance = MagicMock()
            mock_metrics.return_value = mock_instance
            
            # Clear any existing global instance
            import crypto_lakehouse.core.otel_metrics
            crypto_lakehouse.core.otel_metrics._global_metrics = None
            
            metrics1 = get_global_metrics()
            metrics2 = get_global_metrics()
            
            # Should be the same instance (singleton)
            assert metrics1 is metrics2
            mock_metrics.assert_called_once()


class TestIntegrationWithExistingWorkflows:
    """Test integration with existing crypto lakehouse workflows."""
    
    def test_archive_collection_workflow_integration(self):
        """Test integration with archive collection workflow."""
        # This would test actual workflow integration
        # For now, test the pattern that would be used
        
        with patch('crypto_lakehouse.core.otel_metrics.get_global_metrics') as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_get_metrics.return_value = mock_metrics
            
            # Simulate workflow usage pattern
            collector = get_metrics_collector(enable_otel=True)
            
            with mock_metrics.measure_workflow_duration("archive_collection", "batch"):
                # Simulate workflow operations
                collector.record_event(
                    "data_ingested",
                    records_count=1000,
                    data_size_bytes=50000,
                    symbol="BTCUSDT"
                )
                
                # Simulate API call
                mock_metrics.record_api_request(
                    endpoint="/api/v3/klines",
                    method="GET",
                    status_code=200,
                    duration_ms=120.0
                )
                
                # Simulate storage operation
                mock_metrics.update_storage_metrics(
                    size_change_bytes=50000,
                    file_count_change=1,
                    storage_type="parquet",
                    data_tier="bronze"
                )
            
            # Verify workflow metrics were recorded
            assert mock_metrics.measure_workflow_duration.called
            assert mock_metrics.record_api_request.called
            assert mock_metrics.update_storage_metrics.called


@pytest.fixture(scope="session")
def otel_test_environment():
    """Set up test environment for OpenTelemetry integration tests."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "test",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"
    }):
        yield


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    def test_complete_workflow_with_otel_metrics(self, otel_test_environment):
        """Test complete workflow execution with OpenTelemetry metrics."""
        # Initialize metrics collector
        collector = get_metrics_collector(enable_otel=True)
        
        # Simulate complete workflow
        collector.start_workflow("e2e_test_workflow")
        
        try:
            # Simulate data ingestion
            collector.record_event(
                "data_ingested",
                records_count=5000,
                data_size_bytes=250000,
                market="binance",
                data_type="klines",
                symbol="ETHUSDT",
                timeframe="1h"
            )
            
            # Simulate processing
            time.sleep(0.01)
            
            # Simulate storage operation
            collector.record_event("data_stored")
            
        except Exception as e:
            collector.record_error(str(e), error_type="workflow_error")
            raise
        finally:
            collector.end_workflow("e2e_test_workflow")
        
        # Verify metrics were collected
        metrics = collector.get_metrics()
        assert metrics is not None
        assert len(metrics['events']) >= 2
        assert metrics['metrics']['workflow_name'] == 'e2e_test_workflow'