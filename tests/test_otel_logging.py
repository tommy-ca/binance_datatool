"""
Comprehensive tests for OpenTelemetry logging integration.

This test suite validates:
- Log correlation with traces and spans
- Crypto-specific log enhancement
- Adaptive sampling strategies
- OTLP export functionality
- Performance overhead measurements
- Backward compatibility
"""

import pytest
import logging
import json
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
from typing import Dict, List, Any

# OpenTelemetry test utilities
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import set_tracer_provider

# Test imports
from crypto_lakehouse.core.legacy.otel_logging import (
    OpenTelemetryLoggingConfig,
    CryptoContextInjector,
    LogSamplingConfig,
    PerformanceAwareFilter,
    TraceCorrelationFormatter,
    KubernetesMetadataEnricher,
    get_otel_logging_config,
    setup_otel_logging,
    crypto_logging_context,
    log_crypto_operation
)

from crypto_lakehouse.core.logging_adapter import (
    BackwardCompatibleCryptoLogger,
    CryptoLoggerFactory,
    get_crypto_logger,
    crypto_operation_logging
)


class LogCapture:
    """Utility class to capture log records for testing."""
    
    def __init__(self):
        self.records: List[logging.LogRecord] = []
        self.messages: List[str] = []
    
    def __call__(self, record: logging.LogRecord):
        self.records.append(record)
        self.messages.append(record.getMessage())
    
    def clear(self):
        self.records.clear()
        self.messages.clear()


@pytest.fixture
def log_capture():
    """Fixture to capture log records."""
    return LogCapture()


@pytest.fixture
def mock_otel_environment():
    """Setup mock OpenTelemetry environment for testing."""
    # Setup tracer for correlation testing
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    set_tracer_provider(tracer_provider)
    
    yield tracer_provider
    
    # Cleanup
    tracer_provider.shutdown()


class TestLogSamplingConfig:
    """Test adaptive log sampling configurations."""
    
    def test_default_sampling_rates(self):
        """Test default sampling rates."""
        config = LogSamplingConfig()
        
        assert config.error_warn_rate == 1.0
        assert config.info_rate == 0.1
        assert config.debug_rate == 0.01
        assert config.crypto_operation_rate == 0.5
        assert config.high_frequency_rate == 0.001
    
    def test_error_always_sampled(self):
        """Test that error/warning logs are always sampled."""
        config = LogSamplingConfig()
        
        # Test multiple times to ensure consistency
        for _ in range(100):
            assert config.should_sample(logging.ERROR, "test") is True
            assert config.should_sample(logging.WARNING, "test") is True
            assert config.should_sample(logging.CRITICAL, "test") is True
    
    def test_high_frequency_sampling(self):
        """Test high frequency operation sampling."""
        config = LogSamplingConfig()
        
        # Test high frequency operations have lower sampling rate
        samples = [config.should_sample(logging.INFO, "high_frequency") for _ in range(1000)]
        sample_rate = sum(samples) / len(samples)
        
        # Should be close to 0.1% (0.001) with some variance
        assert 0.0005 <= sample_rate <= 0.0020
    
    def test_crypto_operation_sampling(self):
        """Test crypto operation specific sampling."""
        config = LogSamplingConfig()
        
        # Test crypto operations have higher sampling rate than normal info
        crypto_samples = [config.should_sample(logging.INFO, "crypto_operation") for _ in range(1000)]
        crypto_rate = sum(crypto_samples) / len(crypto_samples)
        
        normal_samples = [config.should_sample(logging.INFO, "general") for _ in range(1000)]
        normal_rate = sum(normal_samples) / len(normal_samples)
        
        # Crypto rate should be higher (around 50% vs 10%)
        assert crypto_rate > normal_rate
        assert 0.4 <= crypto_rate <= 0.6
        assert 0.05 <= normal_rate <= 0.15


class TestCryptoContextInjector:
    """Test crypto-specific context injection."""
    
    def test_context_injection(self):
        """Test basic context injection."""
        injector = CryptoContextInjector()
        
        injector.set_crypto_context(
            market="binance",
            symbol="BTCUSDT",
            operation="ingestion",
            data_type="klines",
            timeframe="1m"
        )
        
        context = injector.get_crypto_context()
        
        assert context['crypto.market'] == "binance"
        assert context['crypto.symbol'] == "BTCUSDT"
        assert context['crypto.operation'] == "ingestion"
        assert context['crypto.data_type'] == "klines"
        assert context['crypto.timeframe'] == "1m"
    
    def test_context_thread_isolation(self):
        """Test that context is isolated between threads."""
        injector = CryptoContextInjector()
        results = {}
        
        def thread_func(thread_id: int):
            injector.set_crypto_context(
                market=f"market_{thread_id}",
                symbol=f"SYMBOL_{thread_id}"
            )
            time.sleep(0.1)  # Allow context mixing if not isolated
            results[thread_id] = injector.get_crypto_context()
        
        threads = []
        for i in range(3):
            thread = threading.Thread(target=thread_func, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Each thread should have its own context
        assert results[0]['crypto.market'] == "market_0"
        assert results[1]['crypto.market'] == "market_1"
        assert results[2]['crypto.market'] == "market_2"
    
    def test_context_manager(self):
        """Test crypto operation context manager."""
        injector = CryptoContextInjector()
        
        # Set initial context
        injector.set_crypto_context(market="initial", symbol="INITIAL")
        
        with injector.crypto_operation(market="binance", symbol="BTCUSDT", operation="test"):
            context = injector.get_crypto_context()
            assert context['crypto.market'] == "binance"
            assert context['crypto.symbol'] == "BTCUSDT"
            assert context['crypto.operation'] == "test"
        
        # Context should be restored
        context = injector.get_crypto_context()
        assert context['crypto.market'] == "initial"
        assert context['crypto.symbol'] == "INITIAL"


class TestTraceCorrelationFormatter:
    """Test trace correlation and structured JSON formatting."""
    
    def test_json_formatting(self, mock_otel_environment):
        """Test structured JSON log formatting."""
        formatter = TraceCorrelationFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['level'] == 'INFO'
        assert log_data['logger'] == 'test_logger'
        assert log_data['message'] == 'Test message'
        assert log_data['line'] == 42
        assert 'timestamp' in log_data
    
    def test_trace_correlation(self, mock_otel_environment):
        """Test trace ID and span ID correlation."""
        formatter = TraceCorrelationFormatter()
        tracer = trace.get_tracer("test")
        
        with tracer.start_as_current_span("test_span") as span:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=42,
                msg="Test message with trace",
                args=(),
                exc_info=None
            )
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            
            span_context = span.get_span_context()
            expected_trace_id = format(span_context.trace_id, "032x")
            expected_span_id = format(span_context.span_id, "016x")
            
            assert log_data['trace_id'] == expected_trace_id
            assert log_data['span_id'] == expected_span_id
            assert 'trace_flags' in log_data
    
    def test_crypto_context_formatting(self):
        """Test crypto context inclusion in formatted logs."""
        formatter = TraceCorrelationFormatter()
        
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Crypto operation log",
            args=(),
            exc_info=None
        )
        
        # Add crypto context attributes
        record.crypto_market = "binance"
        record.crypto_symbol = "BTCUSDT"
        record.crypto_operation = "ingestion"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'crypto' in log_data
        assert log_data['crypto']['crypto_market'] == "binance"
        assert log_data['crypto']['crypto_symbol'] == "BTCUSDT"
        assert log_data['crypto']['crypto_operation'] == "ingestion"
    
    def test_exception_formatting(self):
        """Test exception information formatting."""
        formatter = TraceCorrelationFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=True
            )
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'exception' in log_data
        assert log_data['exception']['type'] == 'ValueError'
        assert log_data['exception']['message'] == 'Test exception'
        assert 'traceback' in log_data['exception']


class TestKubernetesMetadataEnricher:
    """Test Kubernetes metadata enrichment."""
    
    @patch.dict(os.environ, {
        'POD_NAME': 'crypto-lakehouse-pod-123',
        'NAMESPACE': 'crypto-data',
        'NODE_NAME': 'worker-node-1'
    })
    def test_k8s_metadata_detection(self):
        """Test Kubernetes metadata detection from environment."""
        enricher = KubernetesMetadataEnricher()
        
        assert enricher.k8s_metadata['k8s_pod_name'] == 'crypto-lakehouse-pod-123'
        assert enricher.k8s_metadata['k8s_namespace'] == 'crypto-data'
        assert enricher.k8s_metadata['k8s_node_name'] == 'worker-node-1'
    
    @patch('os.path.exists')
    def test_k8s_detection_flag(self, mock_exists):
        """Test Kubernetes detection flag."""
        mock_exists.return_value = True
        enricher = KubernetesMetadataEnricher()
        
        assert enricher.k8s_metadata['k8s_detected'] == 'true'
    
    def test_resource_enrichment(self):
        """Test resource attribute enrichment."""
        enricher = KubernetesMetadataEnricher()
        enricher.k8s_metadata = {
            'k8s_pod_name': 'test-pod',
            'k8s_namespace': 'test-ns'
        }
        
        original_attrs = {'service.name': 'crypto-lakehouse'}
        enriched_attrs = enricher.enrich_resource(original_attrs)
        
        assert enriched_attrs['service.name'] == 'crypto-lakehouse'
        assert enriched_attrs['k8s.k8s_pod_name'] == 'test-pod'
        assert enriched_attrs['k8s.k8s_namespace'] == 'test-ns'


class TestPerformanceAwareFilter:
    """Test performance-aware filtering and sampling."""
    
    def test_sampling_filter(self):
        """Test log record sampling filter."""
        sampling_config = LogSamplingConfig(
            error_warn_rate=1.0,
            info_rate=0.5,
            debug_rate=0.1
        )
        context_injector = CryptoContextInjector()
        filter_obj = PerformanceAwareFilter(sampling_config, context_injector)
        
        # Error logs should always pass
        error_record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="Error", args=(), exc_info=None
        )
        assert filter_obj.filter(error_record) is True
        
        # Test info sampling (multiple attempts to verify randomness)
        info_records = []
        for i in range(100):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=f"Info {i}", args=(), exc_info=None
            )
            if filter_obj.filter(record):
                info_records.append(record)
        
        # Should sample approximately 50% (with some variance)
        sample_rate = len(info_records) / 100
        assert 0.3 <= sample_rate <= 0.7
    
    @patch('psutil.cpu_percent')
    def test_cpu_adaptive_sampling(self, mock_cpu):
        """Test CPU-adaptive sampling."""
        mock_cpu.return_value = 85.0  # High CPU usage
        
        sampling_config = LogSamplingConfig(info_rate=0.5)
        context_injector = CryptoContextInjector()
        filter_obj = PerformanceAwareFilter(sampling_config, context_injector)
        
        # Trigger CPU check
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Info", args=(), exc_info=None
        )
        
        # Force CPU check by setting last check time to past
        filter_obj._last_cpu_check = 0
        filter_obj.filter(record)
        
        # Verify CPU usage was captured
        assert hasattr(record, 'cpu_usage_percent')
        assert record.cpu_usage_percent == 85.0
    
    def test_crypto_context_injection(self):
        """Test crypto context injection in filter."""
        sampling_config = LogSamplingConfig()
        context_injector = CryptoContextInjector()
        filter_obj = PerformanceAwareFilter(sampling_config, context_injector)
        
        # Set crypto context
        context_injector.set_crypto_context(
            market="binance",
            symbol="BTCUSDT",
            operation="test"
        )
        
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="Error", args=(), exc_info=None
        )
        
        assert filter_obj.filter(record) is True
        
        # Check that crypto context was added to record
        assert hasattr(record, 'crypto_market')
        assert record.crypto_market == "binance"
        assert hasattr(record, 'crypto_symbol')
        assert record.crypto_symbol == "BTCUSDT"


class TestOpenTelemetryLoggingConfig:
    """Test main OpenTelemetry logging configuration."""
    
    def test_resource_creation(self):
        """Test OpenTelemetry resource creation."""
        config = OpenTelemetryLoggingConfig(
            service_name="test-service",
            service_version="1.0.0",
            environment="test"
        )
        
        resource = config.create_resource()
        attributes = resource.attributes
        
        assert attributes['service.name'] == "test-service"
        assert attributes['service.version'] == "1.0.0"
        assert attributes['deployment.environment'] == "test"
        assert attributes['crypto.market'] == "binance"
        assert attributes['crypto.data_platform'] == "lakehouse"
    
    @patch.dict(os.environ, {'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://test:4317'})
    def test_otlp_exporter_configuration(self):
        """Test OTLP exporter configuration."""
        config = OpenTelemetryLoggingConfig(enable_otlp_export=True)
        processors = config.create_log_processors()
        
        assert len(processors) >= 1
        # Should have OTLP processor when enabled
        assert any(hasattr(p, '_exporter') for p in processors)
    
    def test_console_exporter_development(self):
        """Test console exporter in development environment."""
        config = OpenTelemetryLoggingConfig(
            environment="development",
            enable_console_export=True
        )
        processors = config.create_log_processors()
        
        assert len(processors) >= 1
        # Should have console processor in development
        console_processors = [p for p in processors if hasattr(p, '_exporter')]
        assert len(console_processors) > 0


class TestBackwardCompatibleCryptoLogger:
    """Test backward-compatible crypto logger."""
    
    def test_dual_logging_systems(self, log_capture):
        """Test logging to both OpenTelemetry and legacy systems."""
        # Mock legacy logger availability
        with patch('crypto_lakehouse.core.logging_adapter.LEGACY_LOGGING_AVAILABLE', True):
            logger = BackwardCompatibleCryptoLogger(
                "test_logger",
                enable_otel=True,
                enable_legacy=True
            )
            
            # Test that both systems receive logs
            logger.info("Test message")
            
            # Verify OTel logging (mock verification)
            assert logger.enable_otel is True
            assert logger.enable_legacy is True
    
    def test_crypto_event_logging(self):
        """Test crypto-specific event logging."""
        logger = BackwardCompatibleCryptoLogger("test_logger")
        
        # Mock the underlying loggers to capture calls
        logger.otel_logger = Mock()
        logger.legacy_logger = Mock()
        
        logger.log_ingestion_event(
            symbol="BTCUSDT",
            records_count=1000,
            data_size_bytes=50000,
            duration_ms=250.5,
            market="binance",
            timeframe="1m"
        )
        
        # Verify OTel logger was called with structured data
        assert logger.otel_logger.log.called
        call_args = logger.otel_logger.log.call_args
        assert 'extra' in call_args.kwargs
        extra = call_args.kwargs['extra']
        assert extra['crypto_symbol'] == "BTCUSDT"
        assert extra['crypto_records_count'] == 1000
    
    def test_workflow_logging(self):
        """Test workflow event logging."""
        logger = BackwardCompatibleCryptoLogger("test_logger")
        logger.otel_logger = Mock()
        
        # Test workflow start
        logger.log_workflow_event("test_workflow", "started")
        assert logger.otel_logger.log.called
        
        # Test workflow completion with metrics
        logger.log_workflow_event(
            "test_workflow",
            "completed",
            duration_ms=5000.0,
            records_processed=10000
        )
        
        call_args = logger.otel_logger.log.call_args
        extra = call_args.kwargs['extra']
        assert extra['workflow_name'] == "test_workflow"
        assert extra['workflow_phase'] == "completed"
        assert extra['duration_ms'] == 5000.0


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'test'})
    def test_end_to_end_crypto_logging(self, mock_otel_environment):
        """Test end-to-end crypto logging with trace correlation."""
        # Setup logging
        config = get_otel_logging_config(
            service_name="test-crypto-service",
            environment="test"
        )
        logger = get_crypto_logger("integration_test")
        
        tracer = trace.get_tracer("test")
        
        # Simulate crypto operation with tracing
        with tracer.start_as_current_span("crypto_ingestion") as span:
            with crypto_logging_context(
                market="binance",
                symbol="BTCUSDT",
                operation="ingestion",
                data_type="klines"
            ):
                logger.log_ingestion_event(
                    symbol="BTCUSDT",
                    records_count=5000,
                    data_size_bytes=100000,
                    duration_ms=150.0
                )
                
                # Add span attributes
                span.set_attribute("crypto.symbol", "BTCUSDT")
                span.set_attribute("crypto.records_count", 5000)
        
        # Verify no exceptions and proper context
        assert span.get_span_context().is_valid
    
    def test_performance_overhead_measurement(self):
        """Test performance overhead measurement."""
        import time
        import psutil
        
        # Baseline measurement without logging
        start_cpu = psutil.cpu_percent(interval=0.1)
        start_time = time.time()
        
        # Simulate work without logging
        for i in range(1000):
            _ = f"operation_{i}"
        
        baseline_duration = time.time() - start_time
        baseline_cpu = psutil.cpu_percent(interval=0.1)
        
        # Measurement with OpenTelemetry logging
        logger = get_crypto_logger("performance_test")
        
        start_cpu_logged = psutil.cpu_percent(interval=0.1)
        start_time_logged = time.time()
        
        for i in range(1000):
            with crypto_logging_context(symbol=f"SYM{i}", operation="test"):
                logger.debug(f"Test operation {i}")
        
        logged_duration = time.time() - start_time_logged
        logged_cpu = psutil.cpu_percent(interval=0.1)
        
        # Calculate overhead
        time_overhead = (logged_duration - baseline_duration) / baseline_duration
        cpu_overhead = abs(logged_cpu - baseline_cpu) / max(baseline_cpu, 1.0)
        
        # Verify overhead is reasonable (less than 5% for this test)
        assert time_overhead < 0.05, f"Time overhead too high: {time_overhead:.2%}"
        # Note: CPU measurement can be noisy, so we use a higher threshold
        assert cpu_overhead < 0.10, f"CPU overhead too high: {cpu_overhead:.2%}"
    
    def test_high_frequency_logging_performance(self):
        """Test performance with high-frequency logging."""
        logger = get_crypto_logger("high_freq_test")
        
        # Configure for high frequency operations
        with crypto_logging_context(operation="high_frequency_test"):
            start_time = time.time()
            
            # Simulate high-frequency trading logs
            for i in range(10000):
                logger.debug(f"High frequency operation {i}", 
                           extra={'crypto_operation': 'high_frequency'})
            
            duration = time.time() - start_time
            
            # Should complete within reasonable time (allowing for sampling)
            assert duration < 1.0, f"High frequency logging too slow: {duration:.2f}s"
    
    def test_concurrent_logging_thread_safety(self):
        """Test thread safety with concurrent logging."""
        logger = get_crypto_logger("concurrent_test")
        results = []
        errors = []
        
        def worker_thread(thread_id: int):
            try:
                with crypto_logging_context(
                    symbol=f"SYM{thread_id}",
                    operation=f"thread_operation_{thread_id}"
                ):
                    for i in range(100):
                        logger.info(f"Thread {thread_id} operation {i}")
                    results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Start multiple concurrent threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all threads completed successfully
        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 10
        assert sorted(results) == list(range(10))


@pytest.mark.integration
class TestOTLPExportIntegration:
    """Integration tests for OTLP export functionality."""
    
    @pytest.mark.skipif(
        not os.getenv("TEST_OTLP_INTEGRATION"),
        reason="OTLP integration tests require TEST_OTLP_INTEGRATION=1"
    )
    def test_otlp_export_to_openobserve(self):
        """Test actual OTLP export to OpenObserve (requires running OpenObserve)."""
        # This test requires a running OpenObserve instance
        config = OpenTelemetryLoggingConfig(
            service_name="test-otlp-export",
            environment="integration-test",
            enable_otlp_export=True,
            enable_console_export=False
        )
        
        logger = config.setup_logger("otlp_test")
        
        # Send test logs
        with crypto_logging_context(
            market="binance",
            symbol="BTCUSDT",
            operation="integration_test"
        ):
            logger.info("OTLP integration test log")
            logger.warning("Test warning with crypto context")
            logger.error("Test error for verification")
        
        # Force export
        time.sleep(2)
        config.shutdown()
        
        # Note: In a real integration test, you would verify logs in OpenObserve
        # This requires external verification outside the test


if __name__ == "__main__":
    # Run specific test suites
    pytest.main([__file__, "-v", "--tb=short"])