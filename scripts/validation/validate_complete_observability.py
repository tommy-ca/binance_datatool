#!/usr/bin/env python3
"""
Complete OpenTelemetry Observability Validation Script

Comprehensive validation of metrics, logging, and tracing integration
following specs-driven workflow requirements.
"""

import sys
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_complete_observability_stack():
    """Test complete OpenTelemetry observability stack initialization."""
    print("🔍 Testing complete observability stack...")
    
    try:
        from crypto_lakehouse.core.unified_observability import initialize_crypto_observability
        
        # Initialize complete stack
        components = initialize_crypto_observability(
            service_name="validation-crypto-lakehouse",
            service_version="2.0.0",
            environment="validation"
        )
        
        # Verify all components are present
        assert components.initialized is True, "Observability not initialized"
        assert components.meter_provider is not None, "Meter provider missing"
        assert components.tracer_provider is not None, "Tracer provider missing"
        assert components.logger_provider is not None, "Logger provider missing"
        assert components.crypto_metrics is not None, "Crypto metrics missing"
        assert components.metrics_collector is not None, "Metrics collector missing"
        
        print("✅ Complete observability stack initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Observability stack initialization failed: {e}")
        return False

def test_unified_observability_context():
    """Test unified observability context for crypto workflows."""
    print("\n🔍 Testing unified observability context...")
    
    try:
        from crypto_lakehouse.core.unified_observability import observability_context
        
        # Test crypto workflow context
        with observability_context(
            workflow_name="validation_workflow",
            market="binance",
            data_type="klines", 
            symbols=["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        ) as ctx:
            
            # Verify context provides all observability components
            required_components = ["span", "context", "metrics", "metrics_collector", "tracer"]
            for component in required_components:
                assert component in ctx, f"Missing component: {component}"
            
            # Verify crypto context
            crypto_ctx = ctx["context"]
            assert crypto_ctx["crypto.workflow_name"] == "validation_workflow"
            assert crypto_ctx["crypto.market"] == "binance"
            assert crypto_ctx["crypto.data_type"] == "klines"
            assert "BTCUSDT,ETHUSDT,ADAUSDT" in crypto_ctx["crypto.symbols"]
            assert crypto_ctx["crypto.symbol_count"] == "3"
            
            # Test metrics recording
            metrics = ctx["metrics"]
            metrics_collector = ctx["metrics_collector"]
            
            # Record validation metrics
            metrics_collector.record_event(
                "validation_data_processed",
                records_count=1000,
                data_size_bytes=50000
            )
            
            # Add span events
            span = ctx["span"]
            span.add_event("Validation processing started")
            span.set_attribute("validation.test_mode", True)
            span.set_attribute("validation.symbols_count", 3)
        
        print("✅ Unified observability context working correctly")
        return True
        
    except Exception as e:
        print(f"❌ Unified observability context failed: {e}")
        return False

def test_metrics_logging_tracing_integration():
    """Test integration between metrics, logging, and tracing."""
    print("\n🔍 Testing metrics, logging, and tracing integration...")
    
    try:
        from crypto_lakehouse.core.unified_observability import (
            observability_context,
            get_observability_manager
        )
        
        manager = get_observability_manager()
        if manager is None:
            from crypto_lakehouse.core.unified_observability import initialize_crypto_observability
            components = initialize_crypto_observability()
            manager = get_observability_manager()
        
        # Test correlated observability
        with observability_context(
            workflow_name="integration_test",
            market="binance",
            symbols=["BTCUSDT"]
        ) as ctx:
            
            # Test all three pillars work together
            metrics = ctx["metrics"]
            span = ctx["span"]
            crypto_context = ctx["context"]
            
            # Metrics recording
            metrics_collector = ctx["metrics_collector"]
            metrics_collector.record_event("integration_event", records_count=500)
            
            # Span operations
            span.add_event("Integration test event")
            span.set_attribute("integration.test_type", "validation")
            
            # Verify crypto context is shared
            assert crypto_context["crypto.workflow_name"] == "integration_test"
            assert crypto_context["crypto.market"] == "binance"
            
            # Test error handling across all pillars
            try:
                raise ValueError("Test error for integration")
            except ValueError as e:
                # This should be handled by the context manager
                span.record_exception(e)
                metrics_collector.record_error(str(e), error_type="validation_error")
        
        print("✅ Metrics, logging, and tracing integration working")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def test_performance_characteristics():
    """Test performance characteristics of complete observability stack."""
    print("\n🔍 Testing performance characteristics...")
    
    try:
        from crypto_lakehouse.core.unified_observability import (
            get_observability_manager,
            observability_context
        )
        
        manager = get_observability_manager()
        if manager is None:
            print("❌ Manager not initialized for performance test")
            return False
        
        # Test context creation performance
        start_time = time.time()
        
        for i in range(100):
            context = manager.create_crypto_context(
                workflow_name=f"perf_test_{i}",
                market="binance",
                symbols=[f"SYMBOL{j}" for j in range(3)]
            )
            assert context is not None
        
        context_creation_duration = time.time() - start_time
        
        # Test observability context performance
        start_time = time.time()
        
        for i in range(10):
            with observability_context(f"perf_workflow_{i}", "binance") as ctx:
                # Simulate minimal work
                ctx["span"].set_attribute("test.iteration", i)
                ctx["metrics_collector"].record_event(f"perf_event_{i}")
        
        context_usage_duration = time.time() - start_time
        
        # Verify performance requirements
        context_creation_per_ms = context_creation_duration * 1000
        context_usage_per_ms = context_usage_duration * 1000
        
        print(f"📊 Context creation: {context_creation_per_ms:.2f}ms for 100 operations")
        print(f"📊 Context usage: {context_usage_per_ms:.2f}ms for 10 workflow contexts")
        
        # Performance requirements: <100ms for 100 context creations, <500ms for 10 workflows
        assert context_creation_per_ms < 100, f"Context creation too slow: {context_creation_per_ms}ms"
        assert context_usage_per_ms < 500, f"Context usage too slow: {context_usage_per_ms}ms"
        
        print("✅ Performance characteristics meet requirements")
        return True
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

def test_health_check_and_monitoring():
    """Test health check and monitoring capabilities."""
    print("\n🔍 Testing health check and monitoring...")
    
    try:
        from crypto_lakehouse.core.unified_observability import get_observability_manager
        
        manager = get_observability_manager()
        if manager is None:
            print("❌ Manager not available for health check")
            return False
        
        # Perform health check
        health = manager.health_check()
        
        # Verify health check structure
        assert "status" in health, "Health status missing"
        assert "timestamp" in health, "Health timestamp missing"
        assert "components" in health, "Components status missing"
        assert "performance" in health, "Performance metrics missing"
        
        # Verify component health
        components = health["components"]
        expected_components = ["metrics", "tracing", "logging"]
        for component in expected_components:
            assert component in components, f"Component {component} missing from health check"
        
        # Verify performance metrics
        performance = health["performance"]
        assert "initialization_duration_ms" in performance, "Initialization duration missing"
        assert "components_initialized" in performance, "Components count missing"
        
        print(f"✅ Health check passed - Status: {health['status']}")
        print(f"📊 Components: {list(components.keys())}")
        print(f"📊 Initialization: {performance.get('initialization_duration_ms', 0):.2f}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_resource_attributes_compliance():
    """Test OpenTelemetry resource attributes compliance."""
    print("\n🔍 Testing resource attributes compliance...")
    
    try:
        from crypto_lakehouse.core.unified_observability import get_observability_manager
        
        manager = get_observability_manager()
        if manager is None:
            print("❌ Manager not available for resource test")
            return False
        
        # Get resource attributes
        resource = manager.components.resource
        attributes = resource.attributes
        
        # Standard OpenTelemetry attributes
        required_standard_attrs = [
            "service.name",
            "service.version", 
            "service.namespace",
            "deployment.environment"
        ]
        
        for attr in required_standard_attrs:
            assert attr in attributes, f"Missing standard attribute: {attr}"
        
        # Crypto-specific attributes
        required_crypto_attrs = [
            "crypto.platform_type",
            "crypto.observability_version",
            "crypto.supported_markets"
        ]
        
        for attr in required_crypto_attrs:
            assert attr in attributes, f"Missing crypto attribute: {attr}"
        
        # Infrastructure attributes
        required_infra_attrs = [
            "infrastructure.type",
            "observability.framework"
        ]
        
        for attr in required_infra_attrs:
            assert attr in attributes, f"Missing infrastructure attribute: {attr}"
        
        print("✅ Resource attributes compliance verified")
        print(f"📊 Total attributes: {len(attributes)}")
        print(f"📊 Service: {attributes.get('service.name', 'unknown')}")
        print(f"📊 Framework: {attributes.get('observability.framework', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Resource attributes test failed: {e}")
        return False

def test_crypto_workflow_scenarios():
    """Test crypto-specific workflow scenarios."""
    print("\n🔍 Testing crypto workflow scenarios...")
    
    try:
        from crypto_lakehouse.core.unified_observability import observability_context
        
        # Test multiple crypto workflow scenarios
        scenarios = [
            {
                "workflow": "binance_archive_collection",
                "market": "binance",
                "data_type": "klines",
                "symbols": ["BTCUSDT", "ETHUSDT"]
            },
            {
                "workflow": "coinbase_streaming",
                "market": "coinbase", 
                "data_type": "trades",
                "symbols": ["BTC-USD", "ETH-USD"]
            },
            {
                "workflow": "funding_rate_collection",
                "market": "binance",
                "data_type": "funding_rates",
                "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
            }
        ]
        
        for scenario in scenarios:
            with observability_context(
                workflow_name=scenario["workflow"],
                market=scenario["market"],
                data_type=scenario["data_type"],
                symbols=scenario["symbols"]
            ) as ctx:
                
                # Verify scenario context
                crypto_ctx = ctx["context"]
                assert crypto_ctx["crypto.workflow_name"] == scenario["workflow"]
                assert crypto_ctx["crypto.market"] == scenario["market"]
                assert crypto_ctx["crypto.data_type"] == scenario["data_type"]
                
                # Simulate scenario-specific operations
                span = ctx["span"]
                metrics_collector = ctx["metrics_collector"]
                
                span.add_event(f"Started {scenario['workflow']}")
                span.set_attribute("scenario.symbols_count", len(scenario["symbols"]))
                
                metrics_collector.record_event(
                    f"{scenario['data_type']}_processed",
                    records_count=len(scenario["symbols"]) * 100
                )
        
        print("✅ Crypto workflow scenarios validated")
        print(f"📊 Scenarios tested: {len(scenarios)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Crypto workflow scenarios failed: {e}")
        return False

def test_graceful_shutdown():
    """Test graceful shutdown of observability stack."""
    print("\n🔍 Testing graceful shutdown...")
    
    try:
        from crypto_lakehouse.core.unified_observability import get_observability_manager
        
        manager = get_observability_manager()
        if manager is None:
            print("❌ Manager not available for shutdown test")
            return False
        
        # Verify manager is initialized
        assert manager._initialized is True, "Manager not initialized before shutdown"
        assert manager.components is not None, "Components not available before shutdown"
        
        # Perform graceful shutdown
        manager.shutdown()
        
        # Verify shutdown state
        assert manager._initialized is False, "Manager still marked as initialized after shutdown"
        assert manager.components is None, "Components not cleared after shutdown"
        
        print("✅ Graceful shutdown completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Graceful shutdown failed: {e}")
        return False

def main():
    """Run complete observability validation."""
    print("🚀 Complete OpenTelemetry Observability Validation")
    print("=" * 60)
    
    # Set test environment
    os.environ["ENVIRONMENT"] = "validation"
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://test-collector:4317"
    
    tests = [
        test_complete_observability_stack,
        test_unified_observability_context,
        test_metrics_logging_tracing_integration,
        test_performance_characteristics,
        test_health_check_and_monitoring,
        test_resource_attributes_compliance,
        test_crypto_workflow_scenarios,
        test_graceful_shutdown
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Validation Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Complete OpenTelemetry observability validation successful!")
        print("✅ Metrics, logging, and tracing integration ready for production")
        print("✅ Crypto lakehouse observability fully compliant")
        print("✅ Performance requirements met")
        print("✅ Specs-driven workflow requirements satisfied")
        return 0
    else:
        print("⚠️  Some validation tests failed")
        print("🔧 Review implementation and address failures")
        return 1

if __name__ == "__main__":
    sys.exit(main())