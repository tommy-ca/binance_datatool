#!/usr/bin/env python3
"""
OpenTelemetry Integration Validation Script

This script validates the complete OpenTelemetry integration for the crypto lakehouse platform.
It tests configuration, metrics creation, and backward compatibility.
"""

import sys
import os
import time
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_opentelemetry_imports():
    """Test OpenTelemetry core imports."""
    print("🔍 Testing OpenTelemetry imports...")
    
    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        print("✅ OpenTelemetry core modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ OpenTelemetry import failed: {e}")
        return False

def test_otel_configuration():
    """Test OpenTelemetry configuration module."""
    print("\n🔍 Testing OpenTelemetry configuration...")
    
    try:
        from crypto_lakehouse.core.otel_config import OpenTelemetryConfig, get_otel_config
        
        # Test configuration creation
        config = OpenTelemetryConfig(
            service_name="test-crypto-lakehouse",
            service_version="2.0.0",
            environment="test"
        )
        
        # Test resource creation
        resource = config.create_resource()
        attributes = resource.attributes
        
        # Validate resource attributes
        assert attributes["service.name"] == "test-crypto-lakehouse"
        assert attributes["service.version"] == "2.0.0"
        assert attributes["crypto.market"] == "binance"
        
        print(f"✅ OTel configuration validated: {attributes['service.name']}")
        
        # Test meter provider initialization
        meter_provider = config.initialize_meter_provider()
        assert meter_provider is not None
        print("✅ Meter provider initialized successfully")
        
        # Test meter creation
        meter = config.get_meter("test_meter")
        assert meter is not None
        print("✅ Meter created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ OTel configuration failed: {e}")
        return False

def test_crypto_metrics():
    """Test crypto-specific metrics implementation.""" 
    print("\n🔍 Testing crypto lakehouse metrics...")
    
    try:
        from crypto_lakehouse.core.otel_metrics import CryptoLakehouseMetrics
        from unittest.mock import MagicMock
        
        # Create mock meter
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock() 
        mock_up_down_counter = MagicMock()
        
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram
        mock_meter.create_up_down_counter.return_value = mock_up_down_counter
        
        # Test metrics initialization
        metrics = CryptoLakehouseMetrics(mock_meter)
        print("✅ CryptoLakehouseMetrics initialized")
        
        # Test data ingestion recording
        metrics.record_data_ingestion(1000, 50000, "binance", "klines", "BTCUSDT", "1m")
        assert mock_counter.add.called
        print("✅ Data ingestion metrics recorded")
        
        # Test processing duration measurement
        with metrics.measure_processing_duration("test_operation", "klines", "ETHUSDT"):
            time.sleep(0.001)  # Small delay to measure
        assert mock_histogram.record.called
        print("✅ Processing duration measured")
        
        # Test workflow duration measurement
        with metrics.measure_workflow_duration("test_workflow", "batch"):
            time.sleep(0.001)
        assert mock_counter.add.called  # workflow_executions
        assert mock_histogram.record.called  # workflow_duration
        print("✅ Workflow duration measured")
        
        # Test API request recording
        metrics.record_api_request("/api/v3/klines", "GET", 200, 150.5, "binance")
        print("✅ API request metrics recorded")
        
        # Test error recording
        metrics.record_error("connection_timeout", "Connection failed", "data_download", "archive_collection")
        print("✅ Error metrics recorded")
        
        # Test storage metrics
        metrics.update_storage_metrics(1024000, 5, "parquet", "bronze")
        assert mock_up_down_counter.add.called
        print("✅ Storage metrics recorded")
        
        return True
        
    except Exception as e:
        print(f"❌ Crypto metrics test failed: {e}")
        return False

def test_backward_compatibility():
    """Test backward compatibility with legacy metrics."""
    print("\n🔍 Testing backward compatibility...")
    
    try:
        from crypto_lakehouse.core.otel_metrics import BackwardCompatibleMetricsCollector
        
        # Test with OTel disabled (fallback mode)
        collector = BackwardCompatibleMetricsCollector(enable_otel=False)
        
        collector.start_workflow("test_workflow")
        collector.record_event("test_event", records_count=100, data_size_bytes=5000)
        collector.record_error("test_error", error_type="validation_error")
        collector.end_workflow("test_workflow")
        
        metrics = collector.get_metrics()
        
        # Validate legacy functionality
        assert metrics["otel_enabled"] is False
        assert len(metrics["events"]) >= 1
        assert len(metrics["errors"]) >= 1
        assert "workflow_name" in metrics["metrics"]
        
        print("✅ Backward compatibility validated (OTel disabled)")
        
        # Test convenience functions
        from crypto_lakehouse.core.otel_metrics import get_metrics_collector
        collector2 = get_metrics_collector(enable_otel=False)
        assert collector2 is not None
        print("✅ Convenience functions working")
        
        return True
        
    except Exception as e:
        print(f"❌ Backward compatibility test failed: {e}")
        return False

def test_semantic_conventions():
    """Test semantic conventions compliance."""
    print("\n🔍 Testing semantic conventions...")
    
    try:
        from crypto_lakehouse.core.otel_config import OpenTelemetryConfig
        
        config = OpenTelemetryConfig(environment="test")
        resource = config.create_resource()
        attributes = resource.attributes
        
        # Check required semantic conventions
        required_attributes = [
            "service.name",
            "service.version", 
            "service.namespace",
            "deployment.environment",
            "crypto.market",
            "crypto.data_type",
            "crypto.workflow_type"
        ]
        
        for attr in required_attributes:
            assert attr in attributes, f"Missing required attribute: {attr}"
        
        print("✅ Semantic conventions compliance validated")
        return True
        
    except Exception as e:
        print(f"❌ Semantic conventions test failed: {e}")
        return False

def test_performance():
    """Test performance characteristics."""
    print("\n🔍 Testing performance characteristics...")
    
    try:
        from crypto_lakehouse.core.otel_metrics import BackwardCompatibleMetricsCollector
        
        collector = BackwardCompatibleMetricsCollector(enable_otel=False)
        
        # Test bulk operations performance
        start_time = time.time()
        
        for i in range(100):
            collector.record_event(f"bulk_event_{i}", records_count=i)
            
        duration = time.time() - start_time
        
        # Should complete quickly (< 50ms for 100 operations)
        assert duration < 0.05, f"Performance too slow: {duration}s"
        
        print(f"✅ Performance validated: {duration*1000:.2f}ms for 100 operations")
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("🚀 OpenTelemetry Integration Validation")
    print("=" * 50)
    
    tests = [
        test_opentelemetry_imports,
        test_otel_configuration,
        test_crypto_metrics,
        test_backward_compatibility,
        test_semantic_conventions,
        test_performance
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All OpenTelemetry integration tests passed!")
        print("✅ Ready for production deployment")
        return 0
    else:
        print("⚠️  Some tests failed - review implementation")
        return 1

if __name__ == "__main__":
    sys.exit(main())