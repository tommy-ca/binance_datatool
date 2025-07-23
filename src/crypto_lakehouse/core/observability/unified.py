"""
Unified Observability Interface.

Consolidates the main observability context and components from:
- unified_observability.py
"""

import time
import logging
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager
from dataclasses import dataclass

from opentelemetry import metrics, trace, baggage, context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider

from .config import ObservabilityConfig, get_observability_config, create_observability_resource
from .metrics import CryptoLakehouseMetrics, BackwardCompatibleMetricsCollector, setup_crypto_metrics

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
    config: ObservabilityConfig


@contextmanager
def observability_context(
    operation_name: str,
    workflow_type: str = "unknown",
    **context_attributes
):
    """
    Unified observability context manager providing metrics, logging, and tracing.
    
    This replaces the unified_observability_context from the original implementation.
    """
    config = get_observability_config()
    
    # Get or create crypto metrics
    crypto_metrics = CryptoLakehouseMetrics(config)
    
    # Start timing
    start_time = time.time()
    
    # Create context with baggage
    ctx = baggage.set_baggage("operation.name", operation_name)
    ctx = baggage.set_baggage("workflow.type", workflow_type, context=ctx)
    
    for key, value in context_attributes.items():
        ctx = baggage.set_baggage(f"custom.{key}", str(value), context=ctx)
    
    # Attach context
    token = context.attach(ctx)
    
    try:
        # Record workflow start
        crypto_metrics.record_workflow_start(
            workflow_type=workflow_type,
            operation=operation_name,
            **context_attributes
        )
        
        logger.info(f"Starting operation: {operation_name}", extra={
            "operation": operation_name,
            "workflow_type": workflow_type,
            **context_attributes
        })
        
        yield {
            "metrics": crypto_metrics,
            "context": ctx,
            "operation_name": operation_name,
            "workflow_type": workflow_type,
            **context_attributes
        }
        
        # Record successful completion
        duration_ms = (time.time() - start_time) * 1000
        crypto_metrics.record_workflow_completion(
            workflow_type=workflow_type,
            duration_ms=duration_ms,
            operation=operation_name,
            **context_attributes
        )
        
        logger.info(f"Completed operation: {operation_name}", extra={
            "operation": operation_name,
            "workflow_type": workflow_type,
            "duration_ms": duration_ms,
            "status": "success",
            **context_attributes
        })
        
    except Exception as e:
        # Record error
        duration_ms = (time.time() - start_time) * 1000
        error_type = type(e).__name__
        
        crypto_metrics.record_workflow_error(
            workflow_type=workflow_type,
            error_type=error_type,
            operation=operation_name,
            **context_attributes
        )
        
        logger.error(f"Operation failed: {operation_name}", extra={
            "operation": operation_name,
            "workflow_type": workflow_type,
            "duration_ms": duration_ms,
            "status": "error",
            "error_type": error_type,
            "error_message": str(e),
            **context_attributes
        }, exc_info=True)
        
        raise
    finally:
        # Detach context
        context.detach(token)


def setup_unified_observability(config: Optional[ObservabilityConfig] = None) -> ObservabilityComponents:
    """Setup unified observability with all components."""
    config = config or get_observability_config()
    
    # Create resource
    resource = create_observability_resource(config)
    
    # Setup metrics
    crypto_metrics = setup_crypto_metrics(config)
    metrics_collector = BackwardCompatibleMetricsCollector(config)
    
    # Get providers (these should be set by individual setup functions)
    meter_provider = metrics.get_meter_provider()
    tracer_provider = trace.get_tracer_provider()
    
    # Create a basic logger provider for now
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    
    components = ObservabilityComponents(
        meter_provider=meter_provider,
        tracer_provider=tracer_provider,
        logger_provider=logger_provider,
        crypto_metrics=crypto_metrics,
        metrics_collector=metrics_collector,
        resource=resource,
        config=config
    )
    
    logger.info("Unified observability components initialized")
    return components


# Global components instance
_global_components: Optional[ObservabilityComponents] = None


def get_observability_components() -> ObservabilityComponents:
    """Get or create global observability components."""
    global _global_components
    if _global_components is None:
        _global_components = setup_unified_observability()
    return _global_components


# Backward compatibility alias
unified_observability_context = observability_context