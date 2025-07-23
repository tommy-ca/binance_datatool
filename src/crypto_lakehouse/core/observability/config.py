"""
Unified Observability Configuration Module.

Consolidates configuration functionality from:
- otel_config.py
- unified_observability.py (configuration aspects)
"""

import os
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityConfig:
    """Unified configuration for all observability components."""
    
    # Service Information
    service_name: str = "crypto-lakehouse"
    service_version: str = "2.0.0"
    environment: str = "local"
    
    # Export Configuration
    otlp_endpoint: Optional[str] = None
    console_exporter: bool = True
    
    # Sampling Configuration
    trace_sampling_ratio: float = 1.0
    metric_export_interval: int = 60
    log_export_interval: int = 30
    
    # Crypto-specific Configuration
    crypto_market: str = "binance"
    crypto_data_type: str = "archive"
    crypto_workflow_type: str = "batch_processing"
    
    # Performance Configuration
    batch_timeout: int = 5000
    max_export_batch_size: int = 512
    
    @classmethod
    def from_environment(cls) -> "ObservabilityConfig":
        """Create configuration from environment variables."""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "crypto-lakehouse"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "2.0.0"),
            environment=os.getenv("OTEL_ENVIRONMENT", "local"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            console_exporter=os.getenv("OTEL_CONSOLE_EXPORTER", "true").lower() == "true",
            trace_sampling_ratio=float(os.getenv("OTEL_TRACE_SAMPLING_RATIO", "1.0")),
            metric_export_interval=int(os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60")),
            log_export_interval=int(os.getenv("OTEL_LOG_EXPORT_INTERVAL", "30")),
            crypto_market=os.getenv("CRYPTO_MARKET", "binance"),
            crypto_data_type=os.getenv("CRYPTO_DATA_TYPE", "archive"),
            crypto_workflow_type=os.getenv("CRYPTO_WORKFLOW_TYPE", "batch_processing"),
            batch_timeout=int(os.getenv("OTEL_BATCH_TIMEOUT", "5000")),
            max_export_batch_size=int(os.getenv("OTEL_MAX_EXPORT_BATCH_SIZE", "512"))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "otlp_endpoint": self.otlp_endpoint,
            "console_exporter": self.console_exporter,
            "trace_sampling_ratio": self.trace_sampling_ratio,
            "metric_export_interval": self.metric_export_interval,
            "log_export_interval": self.log_export_interval,
            "crypto_market": self.crypto_market,
            "crypto_data_type": self.crypto_data_type,
            "crypto_workflow_type": self.crypto_workflow_type,
            "batch_timeout": self.batch_timeout,
            "max_export_batch_size": self.max_export_batch_size
        }


def create_observability_resource(config: ObservabilityConfig) -> Resource:
    """Create OpenTelemetry resource with crypto lakehouse context."""
    resource_attributes = {
        ResourceAttributes.SERVICE_NAME: config.service_name,
        ResourceAttributes.SERVICE_VERSION: config.service_version,
        ResourceAttributes.SERVICE_NAMESPACE: "crypto-data",
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: config.environment,
        # Crypto-specific attributes
        "crypto.market": config.crypto_market,
        "crypto.data_type": config.crypto_data_type,
        "crypto.workflow_type": config.crypto_workflow_type
    }
    
    # Add environment-specific attributes
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        resource_attributes[ResourceAttributes.K8S_CLUSTER_NAME] = "local-dev"
    
    # Add hostname if available
    hostname = os.getenv("HOSTNAME") or os.getenv("COMPUTERNAME")
    if hostname:
        resource_attributes[ResourceAttributes.HOST_NAME] = hostname
        
    return Resource.create(resource_attributes)


# Global configuration instance
_global_config: Optional[ObservabilityConfig] = None


def get_observability_config() -> ObservabilityConfig:
    """Get or create global observability configuration."""
    global _global_config
    if _global_config is None:
        _global_config = ObservabilityConfig.from_environment()
    return _global_config


def set_observability_config(config: ObservabilityConfig) -> None:
    """Set global observability configuration."""
    global _global_config
    _global_config = config