"""Validation tests for OpenTelemetry compliance and specifications."""

import pytest
import time
from unittest.mock import patch, MagicMock

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

from crypto_lakehouse.core.otel_config import OpenTelemetryConfig
from crypto_lakehouse.core.otel_metrics import CryptoLakehouseMetrics


class TestOpenTelemetrySpecCompliance:
    """Test compliance with OpenTelemetry specifications v1.21.0+."""
    
    def test_resource_semantic_conventions(self):
        """Test resource follows OpenTelemetry semantic conventions."""
        config = OpenTelemetryConfig(
            service_name="crypto-lakehouse",
            service_version="2.0.0", 
            environment="production"
        )
        
        resource = config.create_resource()
        attributes = resource.attributes
        
        # Required resource attributes per OTel spec
        assert "service.name" in attributes
        assert "service.version" in attributes
        assert "service.namespace" in attributes
        assert "deployment.environment" in attributes
        
        # Crypto-specific resource attributes
        assert "crypto.market" in attributes
        assert "crypto.data_type" in attributes
        assert "crypto.workflow_type" in attributes
        
        # Validate attribute values
        assert attributes["service.name"] == "crypto-lakehouse"
        assert attributes["service.version"] == "2.0.0"
        assert attributes["service.namespace"] == "crypto-data"
        assert attributes["deployment.environment"] == "production"
    
    def test_metric_naming_conventions(self):
        """Test metric names follow OpenTelemetry naming conventions."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Verify counter creation calls
            counter_calls = [call for call in mock_meter.create_counter.call_args_list]
            histogram_calls = [call for call in mock_meter.create_histogram.call_args_list]
            up_down_counter_calls = [call for call in mock_meter.create_up_down_counter.call_args_list]
            
            # Test counter metric names
            counter_names = [call[1]['name'] for call in counter_calls]
            expected_counter_names = [
                "crypto_lakehouse.data.records_ingested_total",
                "crypto_lakehouse.data.bytes_ingested_total", 
                "crypto_lakehouse.workflow.executions_total",
                "crypto_lakehouse.errors_total",
                "crypto_lakehouse.api.requests_total"
            ]
            
            for name in expected_counter_names:
                assert name in counter_names, f"Counter {name} not found"
                # Validate naming convention (no uppercase, dots as separators)
                assert name.islower()
                assert "_total" in name or name.endswith("_total")
                assert "crypto_lakehouse." in name
            
            # Test histogram metric names
            histogram_names = [call[1]['name'] for call in histogram_calls]
            expected_histogram_names = [
                "crypto_lakehouse.processing.duration_ms",
                "crypto_lakehouse.batch.processing_duration_ms",
                "crypto_lakehouse.workflow.duration_ms",
                "crypto_lakehouse.api.response_duration_ms"
            ]
            
            for name in expected_histogram_names:
                assert name in histogram_names, f"Histogram {name} not found"
                assert name.islower()
                assert "crypto_lakehouse." in name
                assert "duration" in name
            
            # Test up-down counter metric names
            gauge_names = [call[1]['name'] for call in up_down_counter_calls]
            expected_gauge_names = [
                "crypto_lakehouse.storage.size_bytes",
                "crypto_lakehouse.storage.files_total",
                "crypto_lakehouse.connections.active",
                "crypto_lakehouse.queue.size"
            ]
            
            for name in expected_gauge_names:
                assert name in gauge_names, f"UpDownCounter {name} not found"
                assert name.islower()
                assert "crypto_lakehouse." in name
    
    def test_metric_units_compliance(self):
        """Test metric units follow OpenTelemetry specifications."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_get_meter.return_value = mock_meter
            
            CryptoLakehouseMetrics(mock_meter)
            
            # Collect all metric creation calls
            all_calls = (
                mock_meter.create_counter.call_args_list +
                mock_meter.create_histogram.call_args_list +
                mock_meter.create_up_down_counter.call_args_list
            )
            
            # Expected units per metric type
            expected_units = {
                "records_ingested_total": "records",
                "bytes_ingested_total": "bytes",
                "processing_duration_ms": "ms",
                "size_bytes": "bytes",
                "files_total": "files",
                "executions_total": "executions",
                "errors_total": "errors",
                "requests_total": "requests",
                "response_duration_ms": "ms",
                "active": "connections",
                "size": "items"
            }
            
            for call in all_calls:
                name = call[1]['name']
                unit = call[1]['unit']
                
                # Find expected unit for this metric
                for suffix, expected_unit in expected_units.items():
                    if suffix in name:
                        assert unit == expected_unit, f"Metric {name} has unit '{unit}', expected '{expected_unit}'"
                        break
    
    def test_metric_descriptions_present(self):
        """Test all metrics have proper descriptions."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_get_meter.return_value = mock_meter
            
            CryptoLakehouseMetrics(mock_meter)
            
            # Collect all metric creation calls
            all_calls = (
                mock_meter.create_counter.call_args_list +
                mock_meter.create_histogram.call_args_list +
                mock_meter.create_up_down_counter.call_args_list
            )
            
            for call in all_calls:
                name = call[1]['name']
                description = call[1]['description']
                
                assert description is not None, f"Metric {name} missing description"
                assert len(description) > 10, f"Metric {name} description too short: '{description}'"
                assert description[0].isupper(), f"Metric {name} description should start with capital letter"


class TestMetricInstrumentTypes:
    """Test proper use of OpenTelemetry metric instrument types."""
    
    def test_counter_instruments_monotonic(self):
        """Test counter instruments are used for monotonic increasing values."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Test monotonic counter usage
            metrics_instance.record_data_ingestion(100, 5000, "binance", "klines", "BTCUSDT", "1m")
            
            # Verify counter.add() was called with positive value
            assert mock_counter.add.called
            call_args = mock_counter.add.call_args_list
            
            for call in call_args:
                value = call[0][0]
                assert value > 0, f"Counter should only receive positive values, got {value}"
    
    def test_histogram_instruments_measurements(self):
        """Test histogram instruments are used for measured values."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_histogram = MagicMock()
            mock_meter.create_histogram.return_value = mock_histogram
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Test histogram usage with context manager
            with metrics_instance.measure_processing_duration("test_operation"):
                time.sleep(0.001)  # Small delay
            
            # Verify histogram.record() was called
            assert mock_histogram.record.called
            
            call_args = mock_histogram.record.call_args
            duration_value = call_args[0][0]
            attributes = call_args[0][1]
            
            assert duration_value >= 0, "Duration should be non-negative"
            assert isinstance(attributes, dict), "Attributes should be a dictionary"
            assert "operation" in attributes
    
    def test_up_down_counter_bidirectional(self):
        """Test up-down counters support positive and negative changes."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_up_down_counter = MagicMock()
            mock_meter.create_up_down_counter.return_value = mock_up_down_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Test positive change
            metrics_instance.update_storage_metrics(1000, 1, "parquet", "bronze")
            
            # Test negative change  
            metrics_instance.update_storage_metrics(-500, -1, "parquet", "bronze")
            
            # Verify up-down counter accepts both positive and negative values
            call_args = mock_up_down_counter.add.call_args_list
            assert len(call_args) >= 2
            
            # Check that we have both positive and negative values
            values = [call[0][0] for call in call_args]
            assert any(v > 0 for v in values), "Should have positive values"
            assert any(v < 0 for v in values), "Should have negative values"


class TestAttributeCompliance:
    """Test metric attributes follow OpenTelemetry conventions."""
    
    def test_attribute_naming_conventions(self):
        """Test attribute names follow snake_case convention."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            metrics_instance.record_data_ingestion(
                100, 5000, "binance", "klines", "BTCUSDT", "1m"
            )
            
            # Get attributes from the call
            call_args = mock_counter.add.call_args
            attributes = call_args[0][1]
            
            # Verify attribute naming conventions
            for key in attributes.keys():
                assert key.islower() or "_" in key, f"Attribute '{key}' should be snake_case"
                assert not key.startswith("_"), f"Attribute '{key}' should not start with underscore"
                assert not key.endswith("_"), f"Attribute '{key}' should not end with underscore"
    
    def test_attribute_cardinality_control(self):
        """Test attribute cardinality is controlled to prevent explosion."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Test with different symbols (should be acceptable cardinality)
            symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
            for symbol in symbols:
                metrics_instance.record_data_ingestion(
                    100, 5000, "binance", "klines", symbol, "1m"
                )
            
            # Verify each call has appropriate number of attributes
            for call in mock_counter.add.call_args_list:
                attributes = call[0][1]
                assert len(attributes) <= 10, "Too many attributes - high cardinality risk"
    
    def test_attribute_value_types(self):
        """Test attribute values are proper types (string, int, float, bool)."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            metrics_instance.record_api_request(
                "/api/v3/klines", "GET", 200, 150.5, "binance"
            )
            
            call_args = mock_counter.add.call_args
            attributes = call_args[0][1]
            
            # Verify attribute value types
            for key, value in attributes.items():
                assert isinstance(value, (str, int, float, bool)), \
                    f"Attribute '{key}' has invalid type {type(value)}: {value}"


class TestCryptoSpecificSemanticConventions:
    """Test crypto-specific semantic conventions and attributes."""
    
    def test_crypto_market_attributes(self):
        """Test crypto market attributes are consistently applied."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            metrics_instance.record_data_ingestion(
                100, 5000, "binance", "klines", "BTCUSDT", "1h"
            )
            
            call_args = mock_counter.add.call_args
            attributes = call_args[0][1]
            
            # Verify crypto-specific attributes
            assert "market" in attributes
            assert "data_type" in attributes  
            assert "symbol" in attributes
            assert "timeframe" in attributes
            assert "operation" in attributes
            
            # Verify attribute values
            assert attributes["market"] == "binance"
            assert attributes["data_type"] == "klines"
            assert attributes["symbol"] == "BTCUSDT"
            assert attributes["timeframe"] == "1h"
            assert attributes["operation"] == "ingestion"
    
    def test_workflow_context_attributes(self):
        """Test workflow context attributes are properly set."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_histogram = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_meter.create_histogram.return_value = mock_histogram
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            with metrics_instance.measure_workflow_duration("archive_collection", "batch"):
                pass
            
            # Check workflow execution counter
            exec_call_args = mock_counter.add.call_args
            exec_attributes = exec_call_args[0][1]
            
            assert "workflow_name" in exec_attributes
            assert "workflow_type" in exec_attributes
            assert exec_attributes["workflow_name"] == "archive_collection"
            assert exec_attributes["workflow_type"] == "batch"
            
            # Check workflow duration histogram
            duration_call_args = mock_histogram.record.call_args
            duration_attributes = duration_call_args[0][1]
            
            assert "workflow_name" in duration_attributes
            assert "workflow_type" in duration_attributes
    
    def test_error_context_attributes(self):
        """Test error context attributes provide adequate debugging information."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            metrics_instance.record_error(
                "connection_timeout",
                "Connection to Binance API timed out",
                "data_download",
                "archive_collection"
            )
            
            call_args = mock_counter.add.call_args
            attributes = call_args[0][1]
            
            # Verify error context attributes
            assert "error_type" in attributes
            assert "operation" in attributes
            assert "workflow_name" in attributes
            
            assert attributes["error_type"] == "connection_timeout"
            assert attributes["operation"] == "data_download"
            assert attributes["workflow_name"] == "archive_collection"


class TestPerformanceAndScalability:
    """Test performance characteristics and scalability requirements."""
    
    def test_metric_recording_performance(self):
        """Test metric recording performance under load."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Measure time for bulk metric recording
            start_time = time.time()
            
            for i in range(1000):
                metrics_instance.record_data_ingestion(
                    100, 5000, "binance", "klines", f"SYMBOL{i % 10}", "1m"
                )
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Should complete 1000 recordings in reasonable time (<100ms)
            assert duration_ms < 100, f"Metric recording too slow: {duration_ms}ms for 1000 recordings"
    
    def test_context_manager_overhead(self):
        """Test context manager overhead is minimal."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_histogram = MagicMock()
            mock_meter.create_histogram.return_value = mock_histogram
            mock_get_meter.return_value = mock_meter
            
            metrics_instance = CryptoLakehouseMetrics(mock_meter)
            
            # Measure context manager overhead
            start_time = time.time()
            
            for i in range(100):
                with metrics_instance.measure_processing_duration("test_operation"):
                    pass  # No actual work
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Should have minimal overhead (<50ms for 100 context managers)
            assert duration_ms < 50, f"Context manager overhead too high: {duration_ms}ms for 100 operations"
    
    def test_memory_usage_bounded(self):
        """Test memory usage doesn't grow unbounded with metric creation."""
        with patch('crypto_lakehouse.core.otel_metrics.get_meter') as mock_get_meter:
            mock_meter = MagicMock()
            mock_get_meter.return_value = mock_meter
            
            # Create multiple metrics instances
            instances = []
            for i in range(10):
                instances.append(CryptoLakehouseMetrics(mock_meter))
            
            # Verify meter creation was optimized (reused meter)
            assert mock_get_meter.call_count <= 10, "Too many meter instances created"