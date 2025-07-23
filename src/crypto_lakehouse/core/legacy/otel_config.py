"""OpenTelemetry configuration for crypto lakehouse observability."""

import os
import logging
from typing import Optional, Dict, Any

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

logger = logging.getLogger(__name__)


class OpenTelemetryConfig:
    """OpenTelemetry configuration for crypto lakehouse metrics."""
    
    def __init__(
        self,
        service_name: str = "crypto-lakehouse",
        service_version: str = "2.0.0",
        environment: str = "local"
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self._meter_provider: Optional[MeterProvider] = None
        self._meter: Optional[metrics.Meter] = None
        
    def create_resource(self) -> Resource:
        """Create OpenTelemetry resource with crypto lakehouse context."""
        resource_attributes = {
            ResourceAttributes.SERVICE_NAME: self.service_name,
            ResourceAttributes.SERVICE_VERSION: self.service_version,
            ResourceAttributes.SERVICE_NAMESPACE: "crypto-data",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: self.environment,
            # Crypto-specific attributes
            "crypto.market": "binance",
            "crypto.data_type": "archive",
            "crypto.workflow_type": "batch_processing"
        }
        
        # Add environment-specific attributes
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            resource_attributes[ResourceAttributes.K8S_CLUSTER_NAME] = "local-dev"
            
        return Resource.create(resource_attributes)
    
    def create_metric_readers(self) -> list:
        """Create metric readers for different export destinations."""
        readers = []
        
        # Console exporter for development
        if self.environment in ["local", "development"]:
            console_reader = PeriodicExportingMetricReader(
                exporter=ConsoleMetricExporter(),
                export_interval_millis=30000,  # 30 seconds
                export_timeout_millis=5000     # 5 seconds
            )
            readers.append(console_reader)
        
        # OTLP exporter for OpenObserve (existing infrastructure)
        otlp_endpoint = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", 
            "http://otel-collector.observability:4317"
        )
        
        try:
            otlp_exporter = OTLPMetricExporter(
                endpoint=otlp_endpoint,
                insecure=True,  # Use TLS in production
                timeout=10
            )
            
            otlp_reader = PeriodicExportingMetricReader(
                exporter=otlp_exporter,
                export_interval_millis=15000,  # 15 seconds for crypto data
                export_timeout_millis=10000    # 10 seconds
            )
            readers.append(otlp_reader)
            logger.info(f"OTLP exporter configured for {otlp_endpoint}")
            
        except Exception as e:
            logger.warning(f"Failed to configure OTLP exporter: {e}")
        
        return readers
    
    def initialize_meter_provider(self) -> MeterProvider:
        """Initialize OpenTelemetry meter provider."""
        if self._meter_provider is not None:
            return self._meter_provider
            
        resource = self.create_resource()
        metric_readers = self.create_metric_readers()
        
        self._meter_provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers
        )
        
        # Set global meter provider
        metrics.set_meter_provider(self._meter_provider)
        
        logger.info(f"OpenTelemetry meter provider initialized for {self.service_name}")
        return self._meter_provider
    
    def get_meter(self, name: str = "crypto_lakehouse") -> metrics.Meter:
        """Get OpenTelemetry meter instance."""
        if self._meter is None:
            if self._meter_provider is None:
                self.initialize_meter_provider()
                
            self._meter = metrics.get_meter(
                name,
                version=self.service_version,
                schema_url="https://opentelemetry.io/schemas/1.21.0"
            )
            
        return self._meter
    
    def shutdown(self):
        """Shutdown OpenTelemetry meter provider."""
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
            logger.info("OpenTelemetry meter provider shutdown complete")


# Global configuration instance
_otel_config: Optional[OpenTelemetryConfig] = None


def get_otel_config(
    service_name: str = "crypto-lakehouse",
    service_version: str = "2.0.0",
    environment: Optional[str] = None
) -> OpenTelemetryConfig:
    """Get or create global OpenTelemetry configuration."""
    global _otel_config
    
    if _otel_config is None:
        env = environment or os.getenv("ENVIRONMENT", "local")
        _otel_config = OpenTelemetryConfig(
            service_name=service_name,
            service_version=service_version,
            environment=env
        )
        _otel_config.initialize_meter_provider()
        
    return _otel_config


def get_meter(name: str = "crypto_lakehouse") -> metrics.Meter:
    """Get OpenTelemetry meter instance (convenience function)."""
    config = get_otel_config()
    return config.get_meter(name)