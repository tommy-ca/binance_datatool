"""Export definitions for OpenTelemetry tracing components."""

# OpenTelemetry configuration
from .otel_config import get_otel_config, get_meter
from .otel_metrics import get_global_metrics, get_metrics_collector
from .otel_tracing import get_tracing_config, get_tracer, trace_operation, trace_crypto_workflow
from .auto_instrumentation import initialize_auto_instrumentation, get_auto_instrumentation_manager
from .crypto_workflow_tracing import get_workflow_tracer, trace_crypto_workflow as trace_workflow
from .context_propagation import (
    get_crypto_propagator, 
    crypto_workflow_context, 
    crypto_processing_context,
    create_crypto_headers,
    extract_crypto_headers
)
from .manual_instrumentation import get_manual_span_manager, manual_trace_binance_api
from .performance_monitoring import (
    get_resource_monitor, 
    get_performance_span_manager,
    performance_aware_operation,
    check_system_health
)
from .unified_otel import (
    get_unified_sdk,
    initialize_crypto_observability,
    get_observability_health,
    shutdown_observability
)

# Export list for OpenTelemetry components
OTEL_EXPORTS = [
    # OpenTelemetry configuration
    "get_otel_config",
    "get_meter",
    "get_tracing_config",
    "get_tracer",
    
    # Metrics
    "get_global_metrics",
    "get_metrics_collector",
    
    # Tracing
    "trace_operation",
    "trace_crypto_workflow",
    "get_workflow_tracer",
    "trace_workflow",
    
    # Auto-instrumentation
    "initialize_auto_instrumentation",
    "get_auto_instrumentation_manager",
    
    # Context propagation
    "get_crypto_propagator",
    "crypto_workflow_context",
    "crypto_processing_context",
    "create_crypto_headers",
    "extract_crypto_headers",
    
    # Manual instrumentation
    "get_manual_span_manager",
    "manual_trace_binance_api",
    
    # Performance monitoring
    "get_resource_monitor",
    "get_performance_span_manager",
    "performance_aware_operation",
    "check_system_health",
    
    # Unified SDK
    "get_unified_sdk",
    "initialize_crypto_observability",
    "get_observability_health",
    "shutdown_observability"
]