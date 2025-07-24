"""OpenTelemetry-compliant metrics for crypto lakehouse workflows."""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
from contextlib import contextmanager

from opentelemetry import metrics
from opentelemetry.metrics import Counter, Histogram, UpDownCounter

from .otel_config import get_meter
from ..metrics import MetricsCollector as LegacyMetricsCollector  # Backward compatibility

logger = logging.getLogger(__name__)


class CryptoLakehouseMetrics:
    """OpenTelemetry-compliant metrics for crypto lakehouse operations."""
    
    def __init__(self, meter: Optional[metrics.Meter] = None):
        self.meter = meter or get_meter("crypto_lakehouse")
        self._initialize_instruments()
        
    def _initialize_instruments(self):
        """Initialize OpenTelemetry metric instruments."""
        
        # Data ingestion metrics
        self.records_ingested = self.meter.create_counter(
            name="crypto_lakehouse.data.records_ingested_total",
            description="Total number of crypto data records ingested",
            unit="records"
        )
        
        self.data_bytes_ingested = self.meter.create_counter(
            name="crypto_lakehouse.data.bytes_ingested_total",
            description="Total bytes of crypto data ingested",
            unit="bytes"
        )
        
        # Processing performance metrics
        self.processing_duration = self.meter.create_histogram(
            name="crypto_lakehouse.processing.duration_ms",
            description="Time taken to process crypto data",
            unit="ms"
        )
        
        self.batch_processing_duration = self.meter.create_histogram(
            name="crypto_lakehouse.batch.processing_duration_ms",
            description="Batch processing duration",
            unit="ms"
        )
        
        # Storage efficiency metrics
        self.storage_size = self.meter.create_up_down_counter(
            name="crypto_lakehouse.storage.size_bytes",
            description="Current size of stored crypto data",
            unit="bytes"
        )
        
        self.file_count = self.meter.create_up_down_counter(
            name="crypto_lakehouse.storage.files_total",
            description="Total number of stored files",
            unit="files"
        )
        
        # Workflow execution metrics
        self.workflow_executions = self.meter.create_counter(
            name="crypto_lakehouse.workflow.executions_total",
            description="Total workflow executions",
            unit="executions"
        )
        
        self.workflow_duration = self.meter.create_histogram(
            name="crypto_lakehouse.workflow.duration_ms",
            description="Workflow execution duration",
            unit="ms"
        )
        
        # Error tracking metrics
        self.errors_total = self.meter.create_counter(
            name="crypto_lakehouse.errors_total",
            description="Total number of errors by type",
            unit="errors"
        )
        
        # API and network metrics
        self.api_requests = self.meter.create_counter(
            name="crypto_lakehouse.api.requests_total",
            description="Total API requests to crypto exchanges",
            unit="requests"
        )
        
        self.api_response_duration = self.meter.create_histogram(
            name="crypto_lakehouse.api.response_duration_ms",
            description="API response time",
            unit="ms"
        )
        
        # Resource utilization metrics
        self.active_connections = self.meter.create_up_down_counter(
            name="crypto_lakehouse.connections.active",
            description="Number of active connections",
            unit="connections"
        )
        
        self.queue_size = self.meter.create_up_down_counter(
            name="crypto_lakehouse.queue.size",
            description="Current queue size",
            unit="items"
        )
        
    def record_data_ingestion(
        self,
        records_count: int,
        data_size_bytes: int,
        market: str = "binance",
        data_type: str = "klines",
        symbol: str = "BTCUSDT",
        timeframe: str = "1m"
    ):
        """Record data ingestion metrics with crypto-specific attributes."""
        attributes = {
            "market": market,
            "data_type": data_type,
            "symbol": symbol,
            "timeframe": timeframe,
            "operation": "ingestion"
        }
        
        self.records_ingested.add(records_count, attributes)
        self.data_bytes_ingested.add(data_size_bytes, attributes)
        
        logger.debug(f"Recorded ingestion: {records_count} records, {data_size_bytes} bytes for {symbol}")
    
    @contextmanager
    def measure_processing_duration(
        self,
        operation: str,
        data_type: str = "klines",
        symbol: str = "BTCUSDT"
    ):
        """Context manager to measure processing duration."""
        start_time = time.time()
        attributes = {
            "operation": operation,
            "data_type": data_type,
            "symbol": symbol
        }
        
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.processing_duration.record(duration_ms, attributes)
            logger.debug(f"Processing {operation} took {duration_ms:.2f}ms")
    
    @contextmanager
    def measure_workflow_duration(
        self,
        workflow_name: str,
        workflow_type: str = "batch"
    ):
        """Context manager to measure workflow execution duration."""
        start_time = time.time()
        attributes = {
            "workflow_name": workflow_name,
            "workflow_type": workflow_type
        }
        
        try:
            self.workflow_executions.add(1, attributes)
            yield
        except Exception as e:
            self.record_error("workflow_execution", str(e), workflow_name=workflow_name)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.workflow_duration.record(duration_ms, attributes)
            logger.info(f"Workflow {workflow_name} completed in {duration_ms:.2f}ms")
    
    def record_error(
        self,
        error_type: str,
        error_message: str,
        operation: Optional[str] = None,
        workflow_name: Optional[str] = None
    ):
        """Record error occurrence with context."""
        attributes = {
            "error_type": error_type,
            "operation": operation or "unknown",
            "workflow_name": workflow_name or "unknown"
        }
        
        self.errors_total.add(1, attributes)
        logger.error(f"Error recorded: {error_type} - {error_message}")
    
    def record_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int = 200,
        duration_ms: float = 0.0,
        market: str = "binance"
    ):
        """Record API request metrics."""
        attributes = {
            "endpoint": endpoint,
            "method": method,
            "status_code": str(status_code),
            "market": market
        }
        
        self.api_requests.add(1, attributes)
        if duration_ms > 0:
            self.api_response_duration.record(duration_ms, attributes)
    
    def update_storage_metrics(
        self,
        size_change_bytes: int,
        file_count_change: int = 0,
        storage_type: str = "parquet",
        data_tier: str = "bronze"
    ):
        """Update storage utilization metrics."""
        attributes = {
            "storage_type": storage_type,
            "data_tier": data_tier
        }
        
        if size_change_bytes != 0:
            self.storage_size.add(size_change_bytes, attributes)
        if file_count_change != 0:
            self.file_count.add(file_count_change, attributes)
    
    def update_resource_metrics(
        self,
        active_connections_delta: int = 0,
        queue_size_delta: int = 0,
        component: str = "workflow"
    ):
        """Update resource utilization metrics."""
        attributes = {"component": component}
        
        if active_connections_delta != 0:
            self.active_connections.add(active_connections_delta, attributes)
        if queue_size_delta != 0:
            self.queue_size.add(queue_size_delta, attributes)


class BackwardCompatibleMetricsCollector:
    """Backward-compatible wrapper that combines legacy and OpenTelemetry metrics."""
    
    def __init__(self, enable_otel: bool = True):
        self.enable_otel = enable_otel
        self.legacy_collector = LegacyMetricsCollector()
        
        if enable_otel:
            try:
                self.otel_metrics = CryptoLakehouseMetrics()
                logger.info("OpenTelemetry metrics enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenTelemetry metrics: {e}")
                self.otel_metrics = None
                self.enable_otel = False
        else:
            self.otel_metrics = None
        
        self.start_times: Dict[str, float] = {}
    
    def start_workflow(self, workflow_name: str):
        """Start metrics collection for a workflow (legacy compatible)."""
        self.legacy_collector.start_workflow(workflow_name)
        self.start_times[workflow_name] = time.time()
        
        if self.otel_metrics:
            # The actual workflow duration will be recorded when end_workflow is called
            pass
    
    def end_workflow(self, workflow_name: Optional[str] = None):
        """End metrics collection (legacy compatible)."""
        self.legacy_collector.end_workflow()
        
        if workflow_name and self.otel_metrics and workflow_name in self.start_times:
            duration_ms = (time.time() - self.start_times[workflow_name]) * 1000
            attributes = {"workflow_name": workflow_name, "workflow_type": "batch"}
            self.otel_metrics.workflow_duration.record(duration_ms, attributes)
            self.otel_metrics.workflow_executions.add(1, attributes)
            del self.start_times[workflow_name]
    
    def record_event(self, event: str, **kwargs):
        """Record an event (legacy compatible with OTel enhancement)."""
        self.legacy_collector.record_event(event)
        
        if self.otel_metrics:
            # Parse event for structured metrics
            if "ingested" in event.lower():
                # Try to extract ingestion metrics from event string
                try:
                    records_count = kwargs.get("records_count", 1)
                    data_size = kwargs.get("data_size_bytes", 0)
                    market = kwargs.get("market", "binance")
                    data_type = kwargs.get("data_type", "klines")
                    symbol = kwargs.get("symbol", "BTCUSDT")
                    timeframe = kwargs.get("timeframe", "1m")
                    
                    self.otel_metrics.record_data_ingestion(
                        records_count, data_size, market, data_type, symbol, timeframe
                    )
                except Exception as e:
                    logger.debug(f"Failed to parse ingestion event for OTel: {e}")
    
    def record_error(self, error: str, **kwargs):
        """Record an error (legacy compatible with OTel enhancement)."""
        self.legacy_collector.record_error(error)
        
        if self.otel_metrics:
            error_type = kwargs.get("error_type", "general")
            operation = kwargs.get("operation")
            workflow_name = kwargs.get("workflow_name")
            
            self.otel_metrics.record_error(error_type, error, operation, workflow_name)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics (legacy compatible)."""
        legacy_metrics = self.legacy_collector.get_metrics()
        
        if self.otel_metrics:
            legacy_metrics["otel_enabled"] = True
            legacy_metrics["otel_metrics_active"] = True
        else:
            legacy_metrics["otel_enabled"] = False
            
        return legacy_metrics


# Convenience function for easy adoption
def get_metrics_collector(enable_otel: bool = True) -> BackwardCompatibleMetricsCollector:
    """Get a metrics collector with optional OpenTelemetry support."""
    return BackwardCompatibleMetricsCollector(enable_otel=enable_otel)


# Global metrics instance for easy access
_global_metrics: Optional[CryptoLakehouseMetrics] = None


def get_global_metrics() -> CryptoLakehouseMetrics:
    """Get global OpenTelemetry metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = CryptoLakehouseMetrics()
    return _global_metrics