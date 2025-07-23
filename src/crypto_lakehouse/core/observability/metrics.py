"""
Consolidated Metrics Module.

Consolidates metrics functionality from:
- otel_metrics.py
- metrics.py (core metrics)
- unified_observability.py (metrics aspects)
"""

import time
import logging
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

from .config import ObservabilityConfig, get_observability_config, create_observability_resource

logger = logging.getLogger(__name__)


class CryptoLakehouseMetrics:
    """Comprehensive metrics collection for crypto lakehouse workflows."""
    
    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self.config = config or get_observability_config()
        self._meter: Optional[metrics.Meter] = None
        self._counters: Dict[str, metrics.Counter] = {}
        self._histograms: Dict[str, metrics.Histogram] = {}
        self._gauges: Dict[str, metrics.UpDownCounter] = {}
        
    def _get_meter(self) -> metrics.Meter:
        """Get or create OpenTelemetry meter."""
        if self._meter is None:
            self._meter = metrics.get_meter(
                name="crypto_lakehouse_metrics",
                version=self.config.service_version
            )
        return self._meter
    
    def _get_counter(self, name: str, description: str = "") -> metrics.Counter:
        """Get or create a counter metric."""
        if name not in self._counters:
            self._counters[name] = self._get_meter().create_counter(
                name=name,
                description=description,
                unit="1"
            )
        return self._counters[name]
    
    def _get_histogram(self, name: str, description: str = "", unit: str = "ms") -> metrics.Histogram:
        """Get or create a histogram metric."""
        if name not in self._histograms:
            self._histograms[name] = self._get_meter().create_histogram(
                name=name,
                description=description,
                unit=unit
            )
        return self._histograms[name]
    
    def _get_gauge(self, name: str, description: str = "", unit: str = "1"):
        """Get or create a gauge metric (using UpDownCounter as alternative)."""
        if name not in self._gauges:
            # Use UpDownCounter as OpenTelemetry doesn't have direct Gauge in Python SDK
            self._gauges[name] = self._get_meter().create_up_down_counter(
                name=name,
                description=description,
                unit=unit
            )
        return self._gauges[name]
    
    # Workflow Metrics
    def record_workflow_start(self, workflow_type: str, **attributes):
        """Record workflow start event."""
        counter = self._get_counter(
            "crypto_workflow_started_total",
            "Total number of crypto workflows started"
        )
        counter.add(1, {"workflow_type": workflow_type, **attributes})
    
    def record_workflow_completion(self, workflow_type: str, duration_ms: float, **attributes):
        """Record workflow completion."""
        # Completion counter
        counter = self._get_counter(
            "crypto_workflow_completed_total", 
            "Total number of crypto workflows completed"
        )
        counter.add(1, {"workflow_type": workflow_type, **attributes})
        
        # Duration histogram
        histogram = self._get_histogram(
            "crypto_workflow_duration_ms",
            "Crypto workflow execution duration in milliseconds"
        )
        histogram.record(duration_ms, {"workflow_type": workflow_type, **attributes})
    
    def record_workflow_error(self, workflow_type: str, error_type: str, **attributes):
        """Record workflow error."""
        counter = self._get_counter(
            "crypto_workflow_errors_total",
            "Total number of crypto workflow errors"
        )
        counter.add(1, {
            "workflow_type": workflow_type,
            "error_type": error_type,
            **attributes
        })
    
    # Data Processing Metrics
    def record_data_processed(self, data_type: str, bytes_processed: int, records_count: int, **attributes):
        """Record data processing metrics."""
        # Bytes processed
        counter = self._get_counter(
            "crypto_data_bytes_processed_total",
            "Total bytes of crypto data processed"
        )
        counter.add(bytes_processed, {"data_type": data_type, **attributes})
        
        # Records processed
        counter = self._get_counter(
            "crypto_data_records_processed_total",
            "Total records of crypto data processed"
        )
        counter.add(records_count, {"data_type": data_type, **attributes})
    
    def record_download_metrics(self, source: str, success: bool, file_size: int, duration_ms: float, **attributes):
        """Record file download metrics."""
        # Download counter
        counter = self._get_counter(
            "crypto_downloads_total",
            "Total number of crypto data downloads"
        )
        counter.add(1, {
            "source": source,
            "success": str(success).lower(),
            **attributes
        })
        
        if success:
            # File size histogram
            histogram = self._get_histogram(
                "crypto_download_size_bytes",
                "Size of downloaded crypto data files in bytes",
                unit="bytes"
            )
            histogram.record(file_size, {"source": source, **attributes})
            
            # Download duration
            histogram = self._get_histogram(
                "crypto_download_duration_ms", 
                "Crypto data download duration in milliseconds"
            )
            histogram.record(duration_ms, {"source": source, **attributes})
    
    # Performance Metrics
    def record_performance_metric(self, metric_name: str, value: float, unit: str = "1", **attributes):
        """Record custom performance metric."""
        histogram = self._get_histogram(
            f"crypto_performance_{metric_name}",
            f"Crypto lakehouse performance metric: {metric_name}",
            unit=unit
        )
        histogram.record(value, attributes)
    
    def set_gauge_value(self, metric_name: str, value: float, **attributes):
        """Set gauge metric value (using add for UpDownCounter)."""
        gauge = self._get_gauge(f"crypto_{metric_name}")
        # For UpDownCounter, we use add() instead of set()
        # Note: This is a simplified implementation - proper gauge support would need more logic
        gauge.add(value, attributes)
    
    @contextmanager
    def timed_operation(self, operation_name: str, **attributes):
        """Context manager for timing operations."""
        start_time = time.time()
        try:
            yield
            # Record success
            duration_ms = (time.time() - start_time) * 1000
            histogram = self._get_histogram(
                f"crypto_operation_duration_ms",
                "Duration of crypto operations in milliseconds"
            )
            histogram.record(duration_ms, {
                "operation": operation_name,
                "status": "success",
                **attributes
            })
        except Exception as e:
            # Record error
            duration_ms = (time.time() - start_time) * 1000
            histogram = self._get_histogram(
                f"crypto_operation_duration_ms",
                "Duration of crypto operations in milliseconds"
            )
            histogram.record(duration_ms, {
                "operation": operation_name,
                "status": "error",
                "error_type": type(e).__name__,
                **attributes
            })
            raise


class BackwardCompatibleMetricsCollector:
    """Backward compatible metrics collector interface."""
    
    def __init__(self, config: Optional[ObservabilityConfig] = None):
        self._crypto_metrics = CryptoLakehouseMetrics(config)
        self._events: List[Dict[str, Any]] = []
        self._errors: List[str] = []
        
    def record_event(self, event_name: str, **attributes):
        """Record an event (backward compatible)."""
        self._events.append({"event": event_name, "attributes": attributes})
        
        # Map to OpenTelemetry metrics
        counter = self._crypto_metrics._get_counter(
            f"crypto_events_total",
            "Total number of crypto events"
        )
        counter.add(1, {"event_name": event_name, **attributes})
    
    def record_error(self, error_message: str, **attributes):
        """Record an error (backward compatible)."""
        self._errors.append(error_message)
        
        # Map to OpenTelemetry metrics
        counter = self._crypto_metrics._get_counter(
            f"crypto_errors_total", 
            "Total number of crypto errors"
        )
        counter.add(1, {"error_message": error_message, **attributes})
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics (backward compatible)."""
        return {
            "events": self._events,
            "errors": self._errors,
            "event_count": len(self._events),
            "error_count": len(self._errors)
        }
    
    def reset(self):
        """Reset collected metrics."""
        self._events.clear()
        self._errors.clear()


def setup_crypto_metrics(config: Optional[ObservabilityConfig] = None) -> CryptoLakehouseMetrics:
    """Setup and configure crypto lakehouse metrics."""
    config = config or get_observability_config()
    
    # Create resource
    resource = create_observability_resource(config)
    
    # Create metric readers
    readers = []
    
    # Console exporter for development
    if config.console_exporter:
        console_reader = PeriodicExportingMetricReader(
            exporter=ConsoleMetricExporter(),
            export_interval_millis=config.metric_export_interval * 1000
        )
        readers.append(console_reader)
    
    # OTLP exporter for production
    if config.otlp_endpoint:
        otlp_reader = PeriodicExportingMetricReader(
            exporter=OTLPMetricExporter(endpoint=config.otlp_endpoint),
            export_interval_millis=config.metric_export_interval * 1000
        )
        readers.append(otlp_reader)
    
    # Create and set meter provider
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=readers
    )
    metrics.set_meter_provider(meter_provider)
    
    # Create metrics instance
    crypto_metrics = CryptoLakehouseMetrics(config)
    
    logger.info(f"Crypto metrics initialized with {len(readers)} exporters")
    return crypto_metrics


# Global metrics instance
_global_metrics: Optional[CryptoLakehouseMetrics] = None


def get_crypto_metrics() -> CryptoLakehouseMetrics:
    """Get or create global crypto metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = setup_crypto_metrics()
    return _global_metrics