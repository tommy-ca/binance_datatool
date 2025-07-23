"""OpenTelemetry tracing configuration for crypto lakehouse workflows."""

import os
import logging
import time
import resource
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Union, Callable
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
    SpanExportResult
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagate import set_global_textmap, composite
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
from opentelemetry.sdk.trace.sampling import (
    TraceIdRatioBased,
    ParentBased,
    Sampler,
    SamplingResult
)

logger = logging.getLogger(__name__)


class AdaptiveSampler(Sampler):
    """Adaptive sampler that adjusts sampling rates based on system load and operation type."""
    
    def __init__(
        self,
        default_ratio: float = 0.1,
        workflow_ratio: float = 1.0,
        api_ratio: float = 0.3,
        storage_ratio: float = 0.2,
        max_cpu_threshold: float = 80.0,
        max_memory_threshold: float = 85.0
    ):
        self.default_ratio = default_ratio
        self.workflow_ratio = workflow_ratio
        self.api_ratio = api_ratio
        self.storage_ratio = storage_ratio
        self.max_cpu_threshold = max_cpu_threshold
        self.max_memory_threshold = max_memory_threshold
        self._lock = threading.Lock()
        self._last_resource_check = 0
        self._current_load_factor = 1.0
        
    def _get_system_load_factor(self) -> float:
        """Calculate system load factor to adjust sampling."""
        current_time = time.time()
        
        # Check system resources every 10 seconds
        if current_time - self._last_resource_check < 10:
            return self._current_load_factor
            
        try:
            # Get memory usage
            memory_info = resource.getrusage(resource.RUSAGE_SELF)
            memory_usage_mb = memory_info.ru_maxrss / 1024  # Convert to MB
            
            # Estimate CPU usage (simplified)
            cpu_time = memory_info.ru_utime + memory_info.ru_stime
            
            # Calculate load factor (simplified heuristic)
            if memory_usage_mb > 500:  # 500MB threshold
                load_factor = 0.5  # Reduce sampling by 50%
            elif memory_usage_mb > 300:  # 300MB threshold
                load_factor = 0.7  # Reduce sampling by 30%
            else:
                load_factor = 1.0  # Normal sampling
                
            with self._lock:
                self._current_load_factor = load_factor
                self._last_resource_check = current_time
                
            return load_factor
            
        except Exception as e:
            logger.warning(f"Failed to get system load: {e}")
            return 1.0
    
    def _get_operation_ratio(self, span_name: str, attributes: Dict[str, Any]) -> float:
        """Get sampling ratio based on operation type."""
        span_name_lower = span_name.lower()
        
        # Crypto workflow operations - always sample
        if "workflow" in span_name_lower or attributes.get("crypto.operation_type") == "workflow":
            return self.workflow_ratio
            
        # API operations - medium sampling
        if "api" in span_name_lower or "request" in span_name_lower:
            return self.api_ratio
            
        # Storage operations - low-medium sampling
        if "storage" in span_name_lower or "s3" in span_name_lower or "minio" in span_name_lower:
            return self.storage_ratio
            
        # Data ingestion - adjust based on volume
        if "ingest" in span_name_lower or attributes.get("crypto.operation_type") == "ingestion":
            record_count = attributes.get("crypto.record_count", 0)
            if record_count > 10000:
                return 0.05  # 5% for high-volume ingestion
            elif record_count > 1000:
                return 0.1   # 10% for medium-volume
            else:
                return 0.3   # 30% for low-volume
                
        return self.default_ratio
    
    def should_sample(
        self,
        parent_context: Optional[trace.Context],
        trace_id: int,
        name: str,
        kind: trace.SpanKind = None,
        attributes: Dict[str, Any] = None,
        links: List[trace.Link] = None,
        trace_state: Optional[trace.TraceState] = None,
    ) -> SamplingResult:
        """Determine if span should be sampled."""
        attributes = attributes or {}
        
        # Always sample errors and high-priority operations
        if attributes.get("error") or attributes.get("crypto.priority") == "high":
            return SamplingResult(
                decision=trace.sampling.Decision.RECORD_AND_SAMPLE,
                attributes={"sampler.type": "adaptive", "sampler.reason": "high_priority"}
            )
        
        # Get base sampling ratio for operation type
        base_ratio = self._get_operation_ratio(name, attributes)
        
        # Adjust for system load
        load_factor = self._get_system_load_factor()
        final_ratio = base_ratio * load_factor
        
        # Use TraceIdRatioBased for actual sampling decision
        ratio_sampler = TraceIdRatioBased(final_ratio)
        result = ratio_sampler.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )
        
        # Add adaptive sampler metadata
        if result.attributes:
            result.attributes.update({
                "sampler.type": "adaptive",
                "sampler.base_ratio": base_ratio,
                "sampler.load_factor": load_factor,
                "sampler.final_ratio": final_ratio
            })
        
        return result
    
    def get_description(self) -> str:
        return f"AdaptiveSampler(default={self.default_ratio})"


class CryptoTracingConfig:
    """OpenTelemetry tracing configuration for crypto lakehouse workflows."""
    
    def __init__(
        self,
        service_name: str = "crypto-lakehouse",
        service_version: str = "2.0.0",
        environment: str = "local",
        enable_console_export: bool = True,
        enable_auto_instrumentation: bool = True
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.enable_console_export = enable_console_export
        self.enable_auto_instrumentation = enable_auto_instrumentation
        
        self._tracer_provider: Optional[TracerProvider] = None
        self._tracer: Optional[trace.Tracer] = None
        self._initialized = False
        
    def create_resource(self) -> Resource:
        """Create OpenTelemetry resource with crypto-specific attributes."""
        resource_attributes = {
            ResourceAttributes.SERVICE_NAME: self.service_name,
            ResourceAttributes.SERVICE_VERSION: self.service_version,
            ResourceAttributes.SERVICE_NAMESPACE: "crypto-data",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
            
            # Crypto-specific attributes
            "crypto.market": "binance",
            "crypto.data_type": "archive",
            "crypto.workflow_type": "batch_processing",
            "crypto.component": "lakehouse",
            
            # Performance attributes
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
            "telemetry.sdk.version": "1.35.0"
        }
        
        # Add Kubernetes attributes if available
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            resource_attributes.update({
                ResourceAttributes.K8S_CLUSTER_NAME: os.getenv("K8S_CLUSTER_NAME", "local-dev"),
                ResourceAttributes.K8S_NAMESPACE_NAME: os.getenv("K8S_NAMESPACE", "crypto-lakehouse"),
                ResourceAttributes.K8S_POD_NAME: os.getenv("K8S_POD_NAME", "unknown"),
                ResourceAttributes.K8S_DEPLOYMENT_NAME: os.getenv("K8S_DEPLOYMENT_NAME", "crypto-lakehouse")
            })
            
        # Add container attributes
        if os.getenv("HOSTNAME"):
            resource_attributes[ResourceAttributes.CONTAINER_NAME] = os.getenv("HOSTNAME")
            
        return Resource.create(resource_attributes)
    
    def create_span_processors(self) -> List[BatchSpanProcessor]:
        """Create span processors for different export destinations."""
        processors = []
        
        # Console exporter for development
        if self.enable_console_export and self.environment in ["local", "development"]:
            console_processor = BatchSpanProcessor(
                span_exporter=ConsoleSpanExporter(),
                max_queue_size=2048,
                max_export_batch_size=512,
                export_timeout_millis=5000,
                schedule_delay_millis=1000
            )
            processors.append(console_processor)
            logger.info("Console span exporter configured")
        
        # OTLP exporter for OpenObserve
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.observability:4317")
        )
        
        try:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=True,  # Use TLS in production
                timeout=10,
                compression="gzip",
                headers={"X-Source": "crypto-lakehouse"}
            )
            
            otlp_processor = BatchSpanProcessor(
                span_exporter=otlp_exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                export_timeout_millis=30000,  # 30 seconds for network operations
                schedule_delay_millis=5000    # 5 seconds batch delay
            )
            processors.append(otlp_processor)
            logger.info(f"OTLP span exporter configured for {otlp_endpoint}")
            
        except Exception as e:
            logger.warning(f"Failed to configure OTLP span exporter: {e}")
        
        return processors
    
    def create_sampler(self) -> Sampler:
        """Create adaptive sampler for crypto operations."""
        adaptive_sampler = AdaptiveSampler(
            default_ratio=0.1,      # 10% default
            workflow_ratio=1.0,     # 100% for workflows
            api_ratio=0.3,          # 30% for API calls
            storage_ratio=0.2       # 20% for storage operations
        )
        
        # Use parent-based sampling to maintain trace consistency
        return ParentBased(root=adaptive_sampler)
    
    def setup_context_propagation(self):
        """Setup W3C Trace Context and Baggage propagation."""
        propagator = composite.CompositeHTTPPropagator([
            TraceContextTextMapPropagator(),  # W3C Trace Context
            W3CBaggagePropagator()           # W3C Baggage
        ])
        set_global_textmap(propagator)
        logger.info("Context propagation configured (W3C Trace Context + Baggage)")
    
    def setup_auto_instrumentation(self):
        """Setup automatic instrumentation for common libraries."""
        if not self.enable_auto_instrumentation:
            return
            
        try:
            # HTTP requests instrumentation
            RequestsInstrumentor().instrument(
                span_callback=self._enrich_http_span,
                excluded_urls="health,metrics"
            )
            logger.info("Requests instrumentation enabled")
            
            # Async HTTP client instrumentation
            AioHttpClientInstrumentor().instrument(
                span_callback=self._enrich_aiohttp_span
            )
            logger.info("AioHTTP client instrumentation enabled")
            
            # AWS SDK instrumentation
            try:
                Boto3SQSInstrumentor().instrument()
                logger.info("Boto3 SQS instrumentation enabled")
            except Exception as e:
                logger.warning(f"Failed to instrument Boto3: {e}")
                
        except Exception as e:
            logger.warning(f"Failed to setup auto-instrumentation: {e}")
    
    def _enrich_http_span(self, span: Span, request, response=None):
        """Enrich HTTP spans with crypto-specific attributes."""
        if not span or not request:
            return
            
        url = getattr(request, 'url', str(request))
        
        # Add crypto-specific attributes for Binance API calls
        if "binance" in url.lower():
            span.set_attribute("crypto.market", "binance")
            span.set_attribute("crypto.api_type", "rest")
            
            # Extract data type from URL
            if "klines" in url:
                span.set_attribute("crypto.data_type", "klines")
            elif "trades" in url:
                span.set_attribute("crypto.data_type", "trades")
            elif "depth" in url:
                span.set_attribute("crypto.data_type", "order_book")
            elif "ticker" in url:
                span.set_attribute("crypto.data_type", "ticker")
                
        # Add response attributes
        if response:
            content_length = getattr(response, 'content_length', 0) or len(getattr(response, 'content', b''))
            if content_length:
                span.set_attribute("http.response.body.size", content_length)
    
    def _enrich_aiohttp_span(self, span: Span, params: Dict[str, Any]):
        """Enrich aioHTTP spans with crypto-specific attributes."""
        if not span:
            return
            
        url = params.get('url', '')
        
        # Add crypto market detection
        if "binance" in url.lower():
            span.set_attribute("crypto.market", "binance")
            span.set_attribute("crypto.api_type", "rest_async")
    
    def initialize_tracer_provider(self) -> TracerProvider:
        """Initialize OpenTelemetry tracer provider."""
        if self._tracer_provider is not None:
            return self._tracer_provider
            
        resource = self.create_resource()
        span_processors = self.create_span_processors()
        sampler = self.create_sampler()
        
        self._tracer_provider = TracerProvider(
            resource=resource,
            sampler=sampler
        )
        
        # Add span processors
        for processor in span_processors:
            self._tracer_provider.add_span_processor(processor)
        
        # Set global tracer provider
        trace.set_tracer_provider(self._tracer_provider)
        
        # Setup context propagation
        self.setup_context_propagation()
        
        # Setup auto-instrumentation
        self.setup_auto_instrumentation()
        
        self._initialized = True
        logger.info(f"OpenTelemetry tracer provider initialized for {self.service_name}")
        return self._tracer_provider
    
    def get_tracer(self, name: str = "crypto_lakehouse") -> trace.Tracer:
        """Get OpenTelemetry tracer instance."""
        if self._tracer is None:
            if not self._initialized:
                self.initialize_tracer_provider()
                
            self._tracer = trace.get_tracer(
                name,
                version=self.service_version,
                schema_url="https://opentelemetry.io/schemas/1.26.0"
            )
            
        return self._tracer
    
    def shutdown(self, timeout_millis: int = 30000):
        """Shutdown OpenTelemetry tracer provider."""
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
            logger.info("OpenTelemetry tracer provider shutdown complete")


# Global configuration instance
_tracing_config: Optional[CryptoTracingConfig] = None


def get_tracing_config(
    service_name: str = "crypto-lakehouse",
    service_version: str = "2.0.0",
    environment: Optional[str] = None,
    enable_console_export: Optional[bool] = None,
    enable_auto_instrumentation: Optional[bool] = None
) -> CryptoTracingConfig:
    """Get or create global OpenTelemetry tracing configuration."""
    global _tracing_config
    
    if _tracing_config is None:
        env = environment or os.getenv("ENVIRONMENT", "local")
        console_export = enable_console_export if enable_console_export is not None else (env == "local")
        auto_instr = enable_auto_instrumentation if enable_auto_instrumentation is not None else True
        
        _tracing_config = CryptoTracingConfig(
            service_name=service_name,
            service_version=service_version,
            environment=env,
            enable_console_export=console_export,
            enable_auto_instrumentation=auto_instr
        )
        _tracing_config.initialize_tracer_provider()
        
    return _tracing_config


def get_tracer(name: str = "crypto_lakehouse") -> trace.Tracer:
    """Get OpenTelemetry tracer instance (convenience function)."""
    config = get_tracing_config()
    return config.get_tracer(name)


# Convenience functions for span creation
def create_span(
    name: str,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None
) -> trace.Span:
    """Create a new span with crypto-specific attributes."""
    tracer = get_tracer()
    span = tracer.start_span(name, kind=kind, attributes=attributes or {})
    return span


@contextmanager
def trace_operation(
    operation_name: str,
    operation_type: str = "internal",
    crypto_attributes: Optional[Dict[str, Any]] = None
):
    """Context manager for tracing crypto operations."""
    tracer = get_tracer()
    attributes = {
        "crypto.operation_type": operation_type,
        "operation.name": operation_name
    }
    
    if crypto_attributes:
        attributes.update(crypto_attributes)
    
    with tracer.start_as_current_span(operation_name, attributes=attributes) as span:
        start_time = time.time()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("duration_ms", duration_ms)


def trace_crypto_workflow(
    workflow_name: str,
    workflow_type: str = "batch",
    market: str = "binance",
    data_type: str = "klines"
):
    """Decorator for tracing crypto workflow functions."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attributes = {
                "crypto.operation_type": "workflow",
                "crypto.workflow_name": workflow_name,
                "crypto.workflow_type": workflow_type,
                "crypto.market": market,
                "crypto.data_type": data_type
            }
            
            with trace_operation(f"workflow.{workflow_name}", "workflow", attributes):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def trace_crypto_api_call(
    api_type: str = "rest",
    market: str = "binance"
):
    """Decorator for tracing crypto API calls."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attributes = {
                "crypto.operation_type": "api_call",
                "crypto.api_type": api_type,
                "crypto.market": market
            }
            
            with trace_operation(f"api.{func.__name__}", "api_call", attributes):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def trace_storage_operation(
    storage_type: str = "s3",
    operation: str = "read"
):
    """Decorator for tracing storage operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attributes = {
                "crypto.operation_type": "storage",
                "storage.type": storage_type,
                "storage.operation": operation
            }
            
            with trace_operation(f"storage.{operation}", "storage", attributes):
                return func(*args, **kwargs)
        return wrapper
    return decorator