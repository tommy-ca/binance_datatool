"""
Core framework components for the crypto lakehouse platform.

This module provides the foundational classes, utilities, and interfaces
that enable the lakehouse architecture patterns throughout the platform.

REFACTORING NOTICE:
OpenTelemetry functionality has been consolidated into the observability submodule.
Use 'from crypto_lakehouse.core.observability import ...' for new code.
"""

from .base import BaseWorkflow
from .config import WorkflowConfig, Config, S3Config, StorageConfig, Settings, TradeType, DataZone, LegacyWorkflowConfig
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
    "Config",
    "S3Config", 
    "StorageConfig",
    "Settings",
    "TradeType",
    "DataZone", 
    "LegacyWorkflowConfig",
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
    
    # Map old imports to new observability module and legacy modules
    observability_mapping = {
        "OpenTelemetryLoggingConfig": "observability.OpenTelemetryLoggingConfig",
        "CryptoContextInjector": "observability.CryptoContextInjector",
        "setup_otel_logging": "observability.setup_otel_logging", 
        "crypto_logging_context": "observability.crypto_logging_context",
        "log_crypto_operation": "observability.log_crypto_operation",
        "unified_observability_context": "observability.observability_context",
    }
    
    # Map legacy OTEL imports to legacy module
    legacy_otel_mapping = {
        "OpenTelemetryConfig": "legacy.otel_config.OpenTelemetryConfig",
        "get_otel_config": "legacy.otel_config.get_otel_config",
        "get_meter": "legacy.otel_config.get_meter",
        "initialize_crypto_observability": "legacy.unified_observability.initialize_crypto_observability",
        "unified_observability": "legacy.unified_observability",
        "otel_config": "legacy.otel_config",
        "otel_logging": "legacy.otel_logging",
        "otel_tracing": "legacy.otel_tracing",
        "otel_metrics": "legacy.otel_metrics",
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
    
    # Handle legacy OTEL imports
    if name in legacy_otel_mapping:
        warnings.warn(
            f"{name} is deprecated. Use new observability interface instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Import from legacy module
        module_path = legacy_otel_mapping[name]
        if '.' in module_path:
            module_name, attr_name = module_path.rsplit('.', 1)
            try:
                from . import legacy
                module = getattr(legacy, module_name.split('.')[-1])
                return getattr(module, attr_name)
            except (ImportError, AttributeError):
                # Fallback to mock implementation
                return BackwardCompatibleMetricsCollector
        else:
            try:
                from . import legacy
                return getattr(legacy, name)
            except (ImportError, AttributeError):
                return BackwardCompatibleMetricsCollector
    
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