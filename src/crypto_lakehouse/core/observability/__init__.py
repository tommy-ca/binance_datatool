"""
Unified Observability Module for Crypto Lakehouse Platform.

This module consolidates all OpenTelemetry functionality including metrics, logging, 
and tracing into a unified interface following specs-driven development methodology.

Consolidates functionality from:
- unified_observability.py
- otel_config.py  
- otel_metrics.py
- otel_logging.py
- otel_tracing.py
- auto_instrumentation.py
- manual_instrumentation.py
- context_propagation.py
- performance_monitoring.py
"""

# Unified public interface for observability
from .config import (
    ObservabilityConfig,
    create_observability_resource,
    get_observability_config
)

from .metrics import (
    CryptoLakehouseMetrics,
    BackwardCompatibleMetricsCollector,
    setup_crypto_metrics
)

from .logging import (
    OpenTelemetryLoggingConfig,
    CryptoContextInjector,
    setup_otel_logging,
    crypto_logging_context,
    log_crypto_operation
)

from .tracing import (
    CryptoTracerProvider,
    setup_crypto_tracing,
    crypto_span,
    trace_crypto_operation
)

from .unified import (
    ObservabilityComponents,
    observability_context,
    setup_unified_observability,
    get_observability_components
)

# Backward compatibility exports
from .unified import observability_context as unified_observability_context

__all__ = [
    # Configuration
    "ObservabilityConfig",
    "create_observability_resource", 
    "get_observability_config",
    
    # Metrics
    "CryptoLakehouseMetrics",
    "BackwardCompatibleMetricsCollector", 
    "setup_crypto_metrics",
    
    # Logging
    "OpenTelemetryLoggingConfig",
    "CryptoContextInjector",
    "setup_otel_logging",
    "crypto_logging_context",
    "log_crypto_operation",
    
    # Tracing
    "CryptoTracerProvider",
    "setup_crypto_tracing", 
    "crypto_span",
    "trace_crypto_operation",
    
    # Unified Interface
    "ObservabilityComponents",
    "observability_context",
    "setup_unified_observability",
    "get_observability_components",
    
    # Backward Compatibility
    "unified_observability_context",
]