"""
Core framework components for the crypto lakehouse platform.

This module provides the foundational classes, utilities, and interfaces
that enable the lakehouse architecture patterns throughout the platform.

REFACTORING NOTICE:
OpenTelemetry functionality has been consolidated into the observability submodule.
Use 'from crypto_lakehouse.core.observability import ...' for new code.
"""

from .base import BaseWorkflow
from .config import WorkflowConfig
from .metrics import MetricsCollector, WorkflowMetrics
from .utils import setup_logging, get_timestamp, format_file_size, create_directory_structure
from .exceptions import LakehouseException, ConfigurationError, WorkflowError, ValidationError

# Unified Observability Interface (New)
from .observability import (
    observability_context,
    setup_unified_observability,
    ObservabilityComponents,
    CryptoLakehouseMetrics,
    BackwardCompatibleMetricsCollector
)

__all__ = [
    # Base Framework
    "BaseWorkflow",
    
    # Configuration Management  
    "WorkflowConfig",
    "ValidationError",
    
    # Metrics and Monitoring
    "MetricsCollector", 
    "WorkflowMetrics",
    
    # Utilities
    "setup_logging",
    "get_timestamp", 
    "format_file_size",
    "create_directory_structure",
    
    # Exceptions
    "LakehouseException",
    "ConfigurationError",
    "WorkflowError",
    
    # Unified Observability (New)
    "observability_context",
    "setup_unified_observability", 
    "ObservabilityComponents",
    "CryptoLakehouseMetrics",
    "BackwardCompatibleMetricsCollector",
]


# Backward compatibility for deprecated imports
def __getattr__(name: str):
    """Provide backward compatibility for deprecated imports."""
    import warnings
    
    # Map old imports to new observability module
    observability_mapping = {
        "OpenTelemetryLoggingConfig": "observability.OpenTelemetryLoggingConfig",
        "CryptoContextInjector": "observability.CryptoContextInjector",
        "setup_otel_logging": "observability.setup_otel_logging", 
        "crypto_logging_context": "observability.crypto_logging_context",
        "log_crypto_operation": "observability.log_crypto_operation",
        "unified_observability_context": "observability.observability_context",
    }
    
    if name in observability_mapping:
        warnings.warn(
            f"{name} is deprecated. Use 'from crypto_lakehouse.core.observability import {name.split('.')[-1]}' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Import from observability module
        from . import observability
        return getattr(observability, name.split('.')[-1])
    
    # Handle other deprecated imports
    if name in ["BackwardCompatibleCryptoLogger", "CryptoLoggerFactory", "get_crypto_logger"]:
        warnings.warn(
            f"{name} is deprecated. Use unified observability interface instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Return a placeholder or redirect to new implementation
        return BackwardCompatibleMetricsCollector
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")