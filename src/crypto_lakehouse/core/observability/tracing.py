"""
Consolidated Tracing Module.

Consolidates tracing functionality from:
- otel_tracing.py
- crypto_workflow_tracing.py
- context_propagation.py
"""

import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from .config import ObservabilityConfig, get_observability_config, create_observability_resource

logger = logging.getLogger(__name__)


class CryptoTracerProvider:
    """Crypto tracer provider."""
    
    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self.config = config or get_observability_config()


def setup_crypto_tracing(config: Optional[ObservabilityConfig] = None):
    """Setup crypto tracing."""
    config = config or get_observability_config()
    
    # Create resource
    resource = create_observability_resource(config)
    
    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    
    logger.info("Crypto tracing setup complete")


@contextmanager
def crypto_span(span_name: str, **attributes):
    """Crypto span context manager."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        try:
            yield span
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def trace_crypto_operation(operation: str, **attributes):
    """Trace crypto operation."""
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(operation, attributes=attributes):
        pass