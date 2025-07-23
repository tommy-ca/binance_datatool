"""
OpenTelemetry Logging SDK Integration for Crypto Lakehouse.

This module provides comprehensive OpenTelemetry logging integration with:
- OTLP export to OpenObserve
- Structured JSON logging with trace correlation
- Crypto-specific log enhancement and context injection
- Adaptive log sampling strategies
- Backward compatibility with existing logging systems
- Kubernetes metadata enrichment
- Performance-optimized BatchLogRecordProcessor
"""

import os
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from contextlib import contextmanager
from dataclasses import dataclass

# OpenTelemetry Logging SDK imports
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

# Trace correlation imports
from opentelemetry import trace
from opentelemetry.trace import SpanContext
from opentelemetry.baggage import get_baggage, set_baggage
from opentelemetry.semconv.trace import SpanAttributes

# Performance and sampling
import random
import psutil
import time

logger = logging.getLogger(__name__)


@dataclass
class LogSamplingConfig:
    """Configuration for adaptive log sampling."""
    error_warn_rate: float = 1.0      # Always sample error/warn logs
    info_rate: float = 0.1             # 10% sampling for info logs
    debug_rate: float = 0.01           # 1% sampling for debug logs
    crypto_operation_rate: float = 0.5  # 50% sampling for crypto operations
    high_frequency_rate: float = 0.001  # 0.1% for high-frequency operations
    
    def should_sample(self, level: int, operation_type: str = "general") -> bool:
        """Determine if a log record should be sampled."""
        if level >= logging.ERROR:
            return random.random() < self.error_warn_rate
        elif level >= logging.WARNING:
            return random.random() < self.error_warn_rate
        elif level >= logging.INFO:
            if "high_frequency" in operation_type:
                return random.random() < self.high_frequency_rate
            elif "crypto" in operation_type:
                return random.random() < self.crypto_operation_rate
            return random.random() < self.info_rate
        else:  # DEBUG
            return random.random() < self.debug_rate


class CryptoContextInjector:
    """Inject crypto-specific context into log records."""
    
    def __init__(self):
        self._thread_local = threading.local()
    
    def set_crypto_context(
        self,
        market: str = None,
        symbol: str = None,
        operation: str = None,
        data_type: str = None,
        timeframe: str = None,
        workflow_id: str = None
    ):
        """Set crypto context for current thread."""
        if not hasattr(self._thread_local, 'crypto_context'):
            self._thread_local.crypto_context = {}
        
        context = self._thread_local.crypto_context
        if market:
            context['crypto.market'] = market
        if symbol:
            context['crypto.symbol'] = symbol
        if operation:
            context['crypto.operation'] = operation
        if data_type:
            context['crypto.data_type'] = data_type
        if timeframe:
            context['crypto.timeframe'] = timeframe
        if workflow_id:
            context['crypto.workflow_id'] = workflow_id
    
    def get_crypto_context(self) -> Dict[str, Any]:
        """Get current crypto context."""
        if hasattr(self._thread_local, 'crypto_context'):
            return self._thread_local.crypto_context.copy()
        return {}
    
    def clear_crypto_context(self):
        """Clear crypto context for current thread."""
        if hasattr(self._thread_local, 'crypto_context'):
            self._thread_local.crypto_context.clear()
    
    @contextmanager
    def crypto_operation(
        self,
        market: str = "binance",
        symbol: str = None,
        operation: str = None,
        data_type: str = None,
        timeframe: str = None,
        workflow_id: str = None
    ):
        """Context manager for crypto operations."""
        # Store original context
        original_context = self.get_crypto_context()
        
        try:
            # Set new context
            self.set_crypto_context(
                market=market,
                symbol=symbol,
                operation=operation,
                data_type=data_type,
                timeframe=timeframe,
                workflow_id=workflow_id
            )
            yield
        finally:
            # Restore original context
            self._thread_local.crypto_context = original_context


class PerformanceAwareFilter(logging.Filter):
    """Filter that adds performance context and sampling."""
    
    def __init__(self, sampling_config: LogSamplingConfig, context_injector: CryptoContextInjector):
        super().__init__()
        self.sampling_config = sampling_config
        self.context_injector = context_injector
        self._last_cpu_check = 0
        self._cpu_usage = 0
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records with sampling and performance awareness."""
        # Update CPU usage periodically (every 5 seconds)
        current_time = time.time()
        if current_time - self._last_cpu_check > 5:
            try:
                self._cpu_usage = psutil.cpu_percent(interval=None)
                self._last_cpu_check = current_time
            except Exception:
                pass
        
        # Adaptive sampling based on CPU usage
        operation_type = "general"
        if hasattr(record, 'crypto_operation'):
            operation_type = getattr(record, 'crypto_operation', 'general')
        
        # Reduce sampling when CPU usage is high
        if self._cpu_usage > 80:
            adjusted_config = LogSamplingConfig(
                error_warn_rate=self.sampling_config.error_warn_rate,
                info_rate=self.sampling_config.info_rate * 0.5,
                debug_rate=self.sampling_config.debug_rate * 0.1,
                crypto_operation_rate=self.sampling_config.crypto_operation_rate * 0.3,
                high_frequency_rate=self.sampling_config.high_frequency_rate * 0.1
            )
        else:
            adjusted_config = self.sampling_config
        
        # Apply sampling
        if not adjusted_config.should_sample(record.levelno, operation_type):
            return False
        
        # Add performance context
        record.cpu_usage_percent = self._cpu_usage
        record.timestamp_ns = int(time.time() * 1_000_000_000)
        
        # Add crypto context
        crypto_context = self.context_injector.get_crypto_context()
        for key, value in crypto_context.items():
            setattr(record, key.replace('.', '_'), value)
        
        return True


class TraceCorrelationFormatter(logging.Formatter):
    """Formatter that adds trace correlation and structured JSON output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with trace correlation and crypto context."""
        # Get current span context
        current_span = trace.get_current_span()
        span_context = current_span.get_span_context() if current_span else None
        
        # Base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "process": record.process
        }
        
        # Add trace correlation
        if span_context and span_context.is_valid:
            log_entry.update({
                "trace_id": format(span_context.trace_id, "032x"),
                "span_id": format(span_context.span_id, "016x"),
                "trace_flags": span_context.trace_flags
            })
        
        # Add baggage context
        baggage = get_baggage()
        if baggage:
            log_entry["baggage"] = dict(baggage)
        
        # Add crypto-specific context
        crypto_attributes = {}
        for attr_name in dir(record):
            if attr_name.startswith('crypto_'):
                crypto_attributes[attr_name] = getattr(record, attr_name)
        
        if crypto_attributes:
            log_entry["crypto"] = crypto_attributes
        
        # Add performance context
        if hasattr(record, 'cpu_usage_percent'):
            log_entry["performance"] = {
                "cpu_usage_percent": record.cpu_usage_percent,
                "timestamp_ns": getattr(record, 'timestamp_ns', 0)
            }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Add extra attributes
        extra_attrs = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'message', 'exc_info',
                'exc_text', 'stack_info'
            } and not key.startswith('crypto_') and not key.startswith('performance'):
                extra_attrs[key] = value
        
        if extra_attrs:
            log_entry["extra"] = extra_attrs
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))


class KubernetesMetadataEnricher:
    """Enrich logs with Kubernetes metadata."""
    
    def __init__(self):
        self.k8s_metadata = self._detect_kubernetes_metadata()
    
    def _detect_kubernetes_metadata(self) -> Dict[str, str]:
        """Detect Kubernetes metadata from environment."""
        metadata = {}
        
        # Standard Kubernetes environment variables
        k8s_env_vars = {
            'K8S_NAMESPACE': 'NAMESPACE',
            'K8S_POD_NAME': 'POD_NAME',
            'K8S_POD_IP': 'POD_IP',
            'K8S_NODE_NAME': 'NODE_NAME',
            'K8S_SERVICE_ACCOUNT': 'SERVICE_ACCOUNT',
            'K8S_CLUSTER_NAME': 'CLUSTER_NAME'
        }
        
        for k8s_key, env_var in k8s_env_vars.items():
            value = os.getenv(env_var)
            if value:
                metadata[k8s_key.lower()] = value
        
        # Detect if running in Kubernetes
        if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
            metadata['k8s_detected'] = 'true'
        
        return metadata
    
    def enrich_resource(self, resource_attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich resource attributes with Kubernetes metadata."""
        enriched = resource_attrs.copy()
        
        for key, value in self.k8s_metadata.items():
            enriched[f"k8s.{key}"] = value
        
        return enriched


class OpenTelemetryLoggingConfig:
    """Main OpenTelemetry logging configuration class."""
    
    def __init__(
        self,
        service_name: str = "crypto-lakehouse",
        service_version: str = "2.0.0",
        environment: str = "local",
        enable_console_export: bool = None,
        enable_otlp_export: bool = True,
        sampling_config: LogSamplingConfig = None,
        batch_export_timeout: int = 30000,
        max_export_batch_size: int = 512
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.enable_console_export = enable_console_export or (environment in ["local", "development"])
        self.enable_otlp_export = enable_otlp_export
        self.sampling_config = sampling_config or LogSamplingConfig()
        self.batch_export_timeout = batch_export_timeout
        self.max_export_batch_size = max_export_batch_size
        
        self.context_injector = CryptoContextInjector()
        self.k8s_enricher = KubernetesMetadataEnricher()
        self._logger_provider: Optional[LoggerProvider] = None
        self._otel_handler: Optional[LoggingHandler] = None
    
    def create_resource(self) -> Resource:
        """Create OpenTelemetry resource with crypto and K8s context."""
        resource_attributes = {
            ResourceAttributes.SERVICE_NAME: self.service_name,
            ResourceAttributes.SERVICE_VERSION: self.service_version,
            ResourceAttributes.SERVICE_NAMESPACE: "crypto-data",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
            
            # Crypto-specific attributes
            "crypto.market": "binance",
            "crypto.data_platform": "lakehouse",
            "crypto.processing_type": "batch",
            
            # Application context
            "application.type": "data_processing",
            "application.framework": "polars_prefect",
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
            "telemetry.sdk.version": "1.21.0"
        }
        
        # Add Kubernetes metadata
        resource_attributes = self.k8s_enricher.enrich_resource(resource_attributes)
        
        return Resource.create(resource_attributes)
    
    def create_log_processors(self) -> List:
        """Create log record processors for different export destinations."""
        processors = []
        
        # Console exporter for development
        if self.enable_console_export:
            console_processor = BatchLogRecordProcessor(
                ConsoleLogExporter(),
                max_export_batch_size=self.max_export_batch_size,
                export_timeout_millis=self.batch_export_timeout,
                schedule_delay_millis=5000  # 5 seconds for console
            )
            processors.append(console_processor)
        
        # OTLP exporter for OpenObserve
        if self.enable_otlp_export:
            otlp_endpoint = os.getenv(
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.observability:4317")
            )
            
            try:
                otlp_exporter = OTLPLogExporter(
                    endpoint=otlp_endpoint,
                    insecure=True,  # Use TLS in production
                    timeout=10,
                    headers=self._get_otlp_headers()
                )
                
                otlp_processor = BatchLogRecordProcessor(
                    otlp_exporter,
                    max_export_batch_size=self.max_export_batch_size,
                    export_timeout_millis=self.batch_export_timeout,
                    schedule_delay_millis=1000  # 1 second for OTLP
                )
                processors.append(otlp_processor)
                logger.info(f"OTLP log exporter configured for {otlp_endpoint}")
                
            except Exception as e:
                logger.warning(f"Failed to configure OTLP log exporter: {e}")
        
        return processors
    
    def _get_otlp_headers(self) -> Dict[str, str]:
        """Get OTLP headers for authentication."""
        headers = {}
        
        # OpenObserve authentication
        auth_token = os.getenv("OPENOBSERVE_AUTH_TOKEN")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        # Basic auth for OpenObserve
        username = os.getenv("OPENOBSERVE_USERNAME", "root")
        password = os.getenv("OPENOBSERVE_PASSWORD", "Complexpass#123")
        if username and password:
            import base64
            auth_string = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {auth_string}"
        
        return headers
    
    def initialize_logger_provider(self) -> LoggerProvider:
        """Initialize OpenTelemetry logger provider."""
        if self._logger_provider is not None:
            return self._logger_provider
        
        resource = self.create_resource()
        processors = self.create_log_processors()
        
        self._logger_provider = LoggerProvider(
            resource=resource,
            multi_log_record_processor=processors[0] if len(processors) == 1 else None
        )
        
        # Add multiple processors if needed
        if len(processors) > 1:
            for processor in processors:
                self._logger_provider.add_log_record_processor(processor)
        
        # Set global logger provider
        set_logger_provider(self._logger_provider)
        
        logger.info(f"OpenTelemetry logger provider initialized for {self.service_name}")
        return self._logger_provider
    
    def get_otel_handler(self) -> LoggingHandler:
        """Get OpenTelemetry logging handler."""
        if self._otel_handler is None:
            if self._logger_provider is None:
                self.initialize_logger_provider()
            
            self._otel_handler = LoggingHandler(
                level=logging.NOTSET,
                logger_provider=self._logger_provider
            )
            
            # Add performance filter and correlation formatter
            perf_filter = PerformanceAwareFilter(self.sampling_config, self.context_injector)
            self._otel_handler.addFilter(perf_filter)
            
            # Set structured formatter
            structured_formatter = TraceCorrelationFormatter()
            self._otel_handler.setFormatter(structured_formatter)
        
        return self._otel_handler
    
    def setup_root_logger(self, level: int = logging.INFO):
        """Setup root logger with OpenTelemetry integration."""
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Remove existing handlers to avoid duplication
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add OpenTelemetry handler
        otel_handler = self.get_otel_handler()
        root_logger.addHandler(otel_handler)
        
        logger.info("Root logger configured with OpenTelemetry integration")
    
    def setup_logger(self, name: str, level: int = logging.INFO) -> logging.Logger:
        """Setup specific logger with OpenTelemetry integration."""
        target_logger = logging.getLogger(name)
        target_logger.setLevel(level)
        
        # Add OpenTelemetry handler if not present
        otel_handler = self.get_otel_handler()
        if otel_handler not in target_logger.handlers:
            target_logger.addHandler(otel_handler)
        
        return target_logger
    
    def shutdown(self):
        """Shutdown OpenTelemetry logging."""
        if self._logger_provider is not None:
            self._logger_provider.shutdown()
            logger.info("OpenTelemetry logging shutdown complete")


# Global configuration instance
_otel_logging_config: Optional[OpenTelemetryLoggingConfig] = None


def get_otel_logging_config(
    service_name: str = "crypto-lakehouse",
    service_version: str = "2.0.0",
    environment: Optional[str] = None,
    **kwargs
) -> OpenTelemetryLoggingConfig:
    """Get or create global OpenTelemetry logging configuration."""
    global _otel_logging_config
    
    if _otel_logging_config is None:
        env = environment or os.getenv("ENVIRONMENT", "local")
        _otel_logging_config = OpenTelemetryLoggingConfig(
            service_name=service_name,
            service_version=service_version,
            environment=env,
            **kwargs
        )
        _otel_logging_config.initialize_logger_provider()
    
    return _otel_logging_config


def setup_otel_logging(
    logger_name: Optional[str] = None,
    level: int = logging.INFO,
    **config_kwargs
) -> logging.Logger:
    """Convenience function to setup OpenTelemetry logging."""
    config = get_otel_logging_config(**config_kwargs)
    
    if logger_name is None:
        config.setup_root_logger(level)
        return logging.getLogger()
    else:
        return config.setup_logger(logger_name, level)


def get_crypto_context_injector() -> CryptoContextInjector:
    """Get the global crypto context injector."""
    config = get_otel_logging_config()
    return config.context_injector


# Convenience decorators and context managers
@contextmanager
def crypto_logging_context(
    market: str = "binance",
    symbol: str = None,
    operation: str = None,
    data_type: str = None,
    timeframe: str = None,
    workflow_id: str = None
):
    """Context manager for crypto logging operations."""
    injector = get_crypto_context_injector()
    with injector.crypto_operation(
        market=market,
        symbol=symbol,
        operation=operation,
        data_type=data_type,
        timeframe=timeframe,
        workflow_id=workflow_id
    ):
        yield


def log_crypto_operation(func):
    """Decorator to automatically log crypto operations."""
    def wrapper(*args, **kwargs):
        operation_name = f"{func.__module__}.{func.__name__}"
        
        # Extract crypto context from kwargs
        crypto_context = {}
        for key in ['market', 'symbol', 'operation', 'data_type', 'timeframe', 'workflow_id']:
            if key in kwargs:
                crypto_context[key] = kwargs[key]
        
        with crypto_logging_context(operation=operation_name, **crypto_context):
            logger.info(f"Starting crypto operation: {operation_name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed crypto operation: {operation_name}")
                return result
            except Exception as e:
                logger.error(f"Failed crypto operation: {operation_name}", exc_info=True)
                raise
    
    return wrapper