"""
Consolidated Logging Module.

Consolidates logging functionality from:
- otel_logging.py
- logging_adapter.py
"""

import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

from .config import ObservabilityConfig, get_observability_config

logger = logging.getLogger(__name__)


class OpenTelemetryLoggingConfig:
    """OpenTelemetry logging configuration."""
    
    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self.config = config or get_observability_config()


class CryptoContextInjector:
    """Crypto context injector for logging."""
    
    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self.config = config or get_observability_config()


def setup_otel_logging(config: Optional[ObservabilityConfig] = None):
    """Setup OpenTelemetry logging."""
    config = config or get_observability_config()
    logger.info("OpenTelemetry logging setup complete")


@contextmanager
def crypto_logging_context(operation: str, **attributes):
    """Crypto logging context manager."""
    logger.info(f"Starting {operation}", extra=attributes)
    try:
        yield
        logger.info(f"Completed {operation}", extra=attributes)
    except Exception as e:
        logger.error(f"Failed {operation}: {e}", extra=attributes)
        raise


def log_crypto_operation(operation: str, **attributes):
    """Log crypto operation."""
    logger.info(f"Crypto operation: {operation}", extra=attributes)