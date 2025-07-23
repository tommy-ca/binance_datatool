"""
Unified OpenTelemetry Observability Configuration
Complete integration of metrics, logging, and tracing for crypto lakehouse workflows.
"""

import os
import logging
import time
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager
from dataclasses import dataclass

# OpenTelemetry Core
from opentelemetry import metrics, trace, baggage, context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider

# Resource Detection
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.sdk.environment_variables import OTEL_RESOURCE_ATTRIBUTES

# Instrumentation
from opentelemetry.instrumentation.auto_instrumentation import sitecustomize

# Local imports
from .otel_config import OpenTelemetryConfig
from .otel_metrics import CryptoLakehouseMetrics, BackwardCompatibleMetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityComponents:
    """Container for all observability components."""
    
    # Providers
    meter_provider: MeterProvider
    tracer_provider: TracerProvider
    logger_provider: LoggerProvider
    
    # Instruments
    crypto_metrics: CryptoLakehouseMetrics
    metrics_collector: BackwardCompatibleMetricsCollector
    
    # Resources
    resource: Resource
    
    # Configuration
    config: OpenTelemetryConfig
    
    # Health status
    initialized: bool = False
    auto_instrumentation_enabled: bool = False


class UnifiedObservabilityManager:
    """
    Unified manager for all OpenTelemetry observability components.
    Provides single point of configuration for metrics, logging, and tracing.
    """
    
    def __init__(
        self,
        service_name: str = "crypto-lakehouse",
        service_version: str = "2.0.0",
        environment: Optional[str] = None,
        enable_auto_instrumentation: bool = True
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment or os.getenv("ENVIRONMENT", "local")
        self.enable_auto_instrumentation = enable_auto_instrumentation
        
        self.components: Optional[ObservabilityComponents] = None
        self._initialized = False
        
        # Performance tracking
        self._init_start_time = time.time()
        self._performance_metrics = {}
    
    def initialize(self) -> ObservabilityComponents:
        """Initialize all observability components."""
        if self._initialized:
            return self.components
        
        logger.info(f"Initializing unified observability for {self.service_name}")
        
        try:
            # Create base configuration
            config = OpenTelemetryConfig(
                service_name=self.service_name,
                service_version=self.service_version,
                environment=self.environment
            )
            
            # Create resource with enhanced attributes
            resource = self._create_enhanced_resource(config)
            
            # Initialize providers
            meter_provider = self._initialize_metrics(resource, config)
            tracer_provider = self._initialize_tracing(resource, config)
            logger_provider = self._initialize_logging(resource, config)
            
            # Create crypto-specific instruments
            crypto_metrics = CryptoLakehouseMetrics()
            metrics_collector = BackwardCompatibleMetricsCollector(enable_otel=True)
            
            # Enable auto-instrumentation if requested
            auto_instrumentation_enabled = False
            if self.enable_auto_instrumentation:
                auto_instrumentation_enabled = self._enable_auto_instrumentation()
            
            # Create components container
            self.components = ObservabilityComponents(
                meter_provider=meter_provider,
                tracer_provider=tracer_provider,
                logger_provider=logger_provider,
                crypto_metrics=crypto_metrics,
                metrics_collector=metrics_collector,
                resource=resource,
                config=config,
                initialized=True,
                auto_instrumentation_enabled=auto_instrumentation_enabled
            )
            
            self._initialized = True
            self._track_initialization_performance()
            
            logger.info("Unified observability initialization complete")
            return self.components
            
        except Exception as e:
            logger.error(f"Failed to initialize observability: {e}")
            raise
    
    def _create_enhanced_resource(self, config: OpenTelemetryConfig) -> Resource:
        """Create resource with enhanced crypto-specific attributes."""
        
        # Start with base resource
        base_resource = config.create_resource()
        
        # Add enhanced attributes
        enhanced_attributes = {
            # Crypto-specific
            "crypto.platform_type": "data_lakehouse",
            "crypto.observability_version": "2.0.0",
            "crypto.supported_markets": "binance,coinbase,kraken",
            "crypto.data_types": "klines,trades,funding_rates,order_books",
            
            # Infrastructure
            "infrastructure.type": "kubernetes",
            "infrastructure.orchestrator": "prefect",
            "infrastructure.storage": "minio_s3_compatible",
            
            # Observability
            "observability.framework": "opentelemetry",
            "observability.version": "1.35.0",
            "observability.pillars": "metrics,logging,tracing",
            
            # Performance
            "performance.target_overhead": "5_percent",
            "performance.optimization": "adaptive_sampling",
        }
        
        # Merge with base resource
        return Resource.create(
            {**base_resource.attributes, **enhanced_attributes}
        )
    
    def _initialize_metrics(self, resource: Resource, config: OpenTelemetryConfig) -> MeterProvider:
        """Initialize metrics provider with enhanced configuration."""
        try:
            # Create metric readers
            metric_readers = config.create_metric_readers()
            
            # Create meter provider
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=metric_readers
            )
            
            # Set global meter provider
            metrics.set_meter_provider(meter_provider)
            
            logger.info("Metrics provider initialized")
            return meter_provider
            
        except Exception as e:
            logger.error(f"Failed to initialize metrics: {e}")
            raise
    
    def _initialize_tracing(self, resource: Resource, config: OpenTelemetryConfig) -> TracerProvider:
        """Initialize tracing provider with enhanced configuration."""
        try:
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.sampling import (
                TraceIdRatioBased,
                ParentBased
            )
            
            # Create span exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.observability:4317"),
                insecure=True,
                timeout=10
            )
            
            # Create span processor
            span_processor = BatchSpanProcessor(
                span_exporter=otlp_exporter,
                max_queue_size=2048,
                export_timeout_millis=30000,
                schedule_delay_millis=5000,
                max_export_batch_size=512
            )
            
            # Create adaptive sampler
            if self.environment == "production":
                sampler = TraceIdRatioBased(0.1)  # 10% in production
            else:
                sampler = TraceIdRatioBased(0.3)  # 30% in development
            
            # Create tracer provider
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=ParentBased(root=sampler)
            )
            
            # Add span processor
            tracer_provider.add_span_processor(span_processor)
            
            # Set global tracer provider
            trace.set_tracer_provider(tracer_provider)
            
            logger.info("Tracing provider initialized")
            return tracer_provider
            
        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}")
            raise
    
    def _initialize_logging(self, resource: Resource, config: OpenTelemetryConfig) -> LoggerProvider:
        """Initialize logging provider with enhanced configuration."""
        try:
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
            
            # Create log exporter
            otlp_log_exporter = OTLPLogExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.observability:4317"),
                insecure=True,
                timeout=10
            )
            
            # Create log processor
            log_processor = BatchLogRecordProcessor(
                exporter=otlp_log_exporter,
                max_queue_size=2048,
                export_timeout_millis=5000,
                schedule_delay_millis=10000,
                max_export_batch_size=512
            )
            
            # Create logger provider
            logger_provider = LoggerProvider(resource=resource)
            logger_provider.add_log_record_processor(log_processor)
            
            # Set global logger provider
            set_logger_provider(logger_provider)
            
            logger.info("Logging provider initialized")
            return logger_provider
            
        except Exception as e:
            logger.error(f"Failed to initialize logging: {e}")
            raise
    
    def _enable_auto_instrumentation(self) -> bool:
        """Enable automatic instrumentation for common libraries."""
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
            from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
            from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            
            # Instrument HTTP clients
            RequestsInstrumentor().instrument()
            AioHttpClientInstrumentor().instrument()
            
            # Instrument AWS services
            try:
                Boto3SQSInstrumentor().instrument()
            except Exception:
                logger.debug("Boto3 instrumentation not available")
            
            # Instrument databases
            try:
                Psycopg2Instrumentor().instrument()
            except Exception:
                logger.debug("PostgreSQL instrumentation not available")
            
            try:
                RedisInstrumentor().instrument()
            except Exception:
                logger.debug("Redis instrumentation not available")
            
            try:
                SQLAlchemyInstrumentor().instrument()
            except Exception:
                logger.debug("SQLAlchemy instrumentation not available")
            
            logger.info("Auto-instrumentation enabled successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to enable auto-instrumentation: {e}")
            return False
    
    def _track_initialization_performance(self):
        """Track initialization performance metrics."""
        init_duration = time.time() - self._init_start_time
        
        self._performance_metrics = {
            "initialization_duration_ms": init_duration * 1000,
            "components_initialized": 3,  # metrics, logging, tracing
            "auto_instrumentation_enabled": self.components.auto_instrumentation_enabled,
            "initialization_timestamp": time.time()
        }
        
        # Record initialization metric if available
        if self.components and self.components.crypto_metrics:
            try:
                self.components.crypto_metrics.record_initialization_metric(
                    "observability_initialization",
                    init_duration * 1000,
                    {
                        "service": self.service_name,
                        "environment": self.environment,
                        "components": "metrics,logging,tracing"
                    }
                )
            except Exception:
                pass  # Don't fail initialization due to metric recording
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get initialization performance metrics."""
        return self._performance_metrics.copy()
    
    def create_crypto_context(
        self,
        workflow_name: str,
        market: str = "binance",
        data_type: str = "klines",
        symbols: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Create crypto-specific context for correlation across observability pillars."""
        
        context = {
            "crypto.workflow_name": workflow_name,
            "crypto.market": market,
            "crypto.data_type": data_type,
            "crypto.timestamp": str(int(time.time())),
        }
        
        if symbols:
            context["crypto.symbols"] = ",".join(symbols[:5])  # Limit to 5 symbols
            context["crypto.symbol_count"] = str(len(symbols))
        
        return context
    
    @contextmanager
    def observability_context(
        self,
        workflow_name: str,
        market: str = "binance",
        data_type: str = "klines",
        symbols: Optional[List[str]] = None,
        record_metrics: bool = True
    ):
        """
        Context manager that provides unified observability context across
        metrics, logging, and tracing.
        """
        
        if not self._initialized:
            self.initialize()
        
        # Create crypto context
        crypto_context = self.create_crypto_context(workflow_name, market, data_type, symbols)
        
        # Start workflow metrics
        if record_metrics and self.components.metrics_collector:
            self.components.metrics_collector.start_workflow(workflow_name)
        
        # Create trace span
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span(
            f"crypto_workflow_{workflow_name}",
            attributes={
                **crypto_context,
                "workflow.type": "crypto_data_processing",
                "workflow.framework": "crypto_lakehouse"
            }
        ) as span:
            
            # Set baggage for context propagation
            token1 = context.attach(baggage.set_baggage("crypto.workflow_name", workflow_name))
            token2 = context.attach(baggage.set_baggage("crypto.market", market))
            
            try:
                # Yield context with all observability components
                yield {
                    "span": span,
                    "context": crypto_context,
                    "metrics": self.components.crypto_metrics,
                    "metrics_collector": self.components.metrics_collector,
                    "tracer": tracer
                }
                
                # Mark successful completion
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as e:
                # Record error in all observability pillars
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                
                if record_metrics and self.components.crypto_metrics:
                    self.components.crypto_metrics.record_error(
                        "workflow_execution_error",
                        str(e),
                        operation=workflow_name,
                        workflow_name=workflow_name
                    )
                
                raise
            
            finally:
                # Detach baggage context
                context.detach(token2)
                context.detach(token1)
                
                # End workflow metrics
                if record_metrics and self.components.metrics_collector:
                    self.components.metrics_collector.end_workflow(workflow_name)
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check of all observability components."""
        
        health = {
            "status": "healthy",
            "timestamp": time.time(),
            "components": {},
            "performance": self.get_performance_metrics()
        }
        
        if not self._initialized:
            health["status"] = "not_initialized"
            return health
        
        # Check each component
        try:
            # Metrics health
            if self.components.meter_provider:
                health["components"]["metrics"] = "healthy"
            else:
                health["components"]["metrics"] = "unhealthy"
                health["status"] = "degraded"
            
            # Tracing health
            if self.components.tracer_provider:
                health["components"]["tracing"] = "healthy"
            else:
                health["components"]["tracing"] = "unhealthy"
                health["status"] = "degraded"
            
            # Logging health
            if self.components.logger_provider:
                health["components"]["logging"] = "healthy"
            else:
                health["components"]["logging"] = "unhealthy"
                health["status"] = "degraded"
            
            # Auto-instrumentation status
            health["components"]["auto_instrumentation"] = (
                "enabled" if self.components.auto_instrumentation_enabled else "disabled"
            )
            
        except Exception as e:
            health["status"] = "error"
            health["error"] = str(e)
        
        return health
    
    def shutdown(self):
        """Gracefully shutdown all observability components."""
        logger.info("Shutting down unified observability")
        
        if self.components:
            try:
                # Shutdown providers
                if hasattr(self.components.meter_provider, 'shutdown'):
                    self.components.meter_provider.shutdown()
                
                if hasattr(self.components.tracer_provider, 'shutdown'):
                    self.components.tracer_provider.shutdown()
                
                if hasattr(self.components.logger_provider, 'shutdown'):
                    self.components.logger_provider.shutdown()
                
                logger.info("Observability shutdown complete")
                
            except Exception as e:
                logger.error(f"Error during observability shutdown: {e}")
        
        self._initialized = False
        self.components = None


# Global instance for easy access
_global_observability_manager: Optional[UnifiedObservabilityManager] = None


def initialize_crypto_observability(
    service_name: str = "crypto-lakehouse",
    service_version: str = "2.0.0",
    environment: Optional[str] = None,
    enable_auto_instrumentation: bool = True
) -> ObservabilityComponents:
    """
    Initialize global crypto observability with unified configuration.
    
    Returns ObservabilityComponents for immediate use.
    """
    global _global_observability_manager
    
    if _global_observability_manager is None:
        _global_observability_manager = UnifiedObservabilityManager(
            service_name=service_name,
            service_version=service_version,
            environment=environment,
            enable_auto_instrumentation=enable_auto_instrumentation
        )
    
    return _global_observability_manager.initialize()


def get_observability_manager() -> Optional[UnifiedObservabilityManager]:
    """Get the global observability manager instance."""
    return _global_observability_manager


def observability_context(
    workflow_name: str,
    market: str = "binance",
    data_type: str = "klines",
    symbols: Optional[List[str]] = None,
    record_metrics: bool = True
):
    """
    Convenience function for unified observability context.
    
    Usage:
        with observability_context("daily_collection", "binance", ["BTCUSDT"]) as ctx:
            # Your workflow code here
            ctx["metrics"].record_data_ingestion(1000, 50000, "binance", "klines", "BTCUSDT", "1m")
            ctx["span"].add_event("Data processing started")
    """
    
    # Initialize if needed
    if _global_observability_manager is None:
        initialize_crypto_observability()
    
    return _global_observability_manager.observability_context(
        workflow_name=workflow_name,
        market=market,
        data_type=data_type,
        symbols=symbols,
        record_metrics=record_metrics
    )