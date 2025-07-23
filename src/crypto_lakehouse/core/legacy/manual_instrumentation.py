"""Manual instrumentation utilities for crypto-specific operations."""

import logging
import time
import asyncio
from contextlib import contextmanager, asynccontextmanager
from typing import Dict, Any, Optional, List, Callable, Union, Type
from functools import wraps

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.semconv.trace import SpanAttributes

from .otel_tracing import get_tracer
from .context_propagation import get_crypto_propagator, crypto_processing_context

logger = logging.getLogger(__name__)


class ManualSpanManager:
    """Manager for creating and managing manual spans for crypto operations."""
    
    def __init__(self, tracer_name: str = "crypto_manual"):
        self.tracer = get_tracer(tracer_name)
        self.propagator = get_crypto_propagator()
        
    @contextmanager
    def create_span(
        self,
        span_name: str,
        span_kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span: Optional[Span] = None
    ):
        """Create a manual span with crypto-specific enhancements."""
        span_attributes = attributes or {}
        
        # Add default crypto attributes
        span_attributes.update({
            "component": "crypto_lakehouse",
            "span.kind": span_kind.name,
            "instrumentation.library": "manual"
        })
        
        if parent_span:
            ctx = trace.set_span_in_context(parent_span)
        else:
            ctx = None
            
        with self.tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=span_kind,
            attributes=span_attributes
        ) as span:
            try:
                yield ManualSpanContext(span, self)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.record_exception(e)
                raise
    
    @contextmanager
    def binance_api_span(
        self,
        endpoint: str,
        method: str = "GET",
        symbol: Optional[str] = None,
        data_type: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None
    ):
        """Create a span specifically for Binance API calls."""
        span_name = f"binance.api.{method.lower()}"
        
        attributes = {
            "crypto.operation_type": "api_call",
            "crypto.market": "binance",
            "crypto.api_type": "rest",
            "http.method": method,
            "http.url": endpoint,
            SpanAttributes.HTTP_METHOD: method,
            SpanAttributes.HTTP_URL: endpoint
        }
        
        if symbol:
            attributes["crypto.symbol"] = symbol
        if data_type:
            attributes["crypto.data_type"] = data_type
        if request_params:
            # Sanitize sensitive parameters
            safe_params = self._sanitize_params(request_params)
            attributes["api.request.params"] = str(safe_params)
            
        with self.create_span(
            span_name,
            trace.SpanKind.CLIENT,
            attributes
        ) as span_context:
            yield BinanceApiSpanContext(span_context.span, self)
    
    @contextmanager
    def s3_storage_span(
        self,
        operation: str,
        bucket: str,
        key: str,
        file_size_bytes: Optional[int] = None,
        storage_class: Optional[str] = None
    ):
        """Create a span for S3 storage operations."""
        span_name = f"s3.{operation}"
        
        attributes = {
            "crypto.operation_type": "storage",
            "storage.type": "s3",
            "storage.operation": operation,
            "aws.s3.bucket": bucket,
            "aws.s3.key": key
        }
        
        if file_size_bytes is not None:
            attributes["storage.file_size_bytes"] = file_size_bytes
        if storage_class:
            attributes["aws.s3.storage_class"] = storage_class
            
        with self.create_span(
            span_name,
            trace.SpanKind.CLIENT,
            attributes
        ) as span_context:
            yield S3StorageSpanContext(span_context.span, self)
    
    @contextmanager
    def data_processing_span(
        self,
        processor_name: str,
        data_type: str = "klines",
        symbol: str = "BTCUSDT",
        record_count: Optional[int] = None,
        processing_stage: Optional[str] = None
    ):
        """Create a span for data processing operations."""
        span_name = f"processing.{processor_name}"
        
        attributes = {
            "crypto.operation_type": "data_processing",
            "crypto.processor_name": processor_name,
            "crypto.data_type": data_type,
            "crypto.symbol": symbol
        }
        
        if record_count is not None:
            attributes["crypto.record_count"] = record_count
        if processing_stage:
            attributes["crypto.processing_stage"] = processing_stage
            
        with self.create_span(
            span_name,
            trace.SpanKind.INTERNAL,
            attributes
        ) as span_context:
            yield DataProcessingSpanContext(span_context.span, self)
    
    @contextmanager
    def workflow_task_span(
        self,
        task_name: str,
        workflow_name: str,
        task_type: str = "batch",
        dependencies: Optional[List[str]] = None
    ):
        """Create a span for workflow task execution."""
        span_name = f"workflow.task.{task_name}"
        
        attributes = {
            "crypto.operation_type": "workflow_task",
            "crypto.task_name": task_name,
            "crypto.workflow_name": workflow_name,
            "crypto.task_type": task_type
        }
        
        if dependencies:
            attributes["crypto.task_dependencies"] = ",".join(dependencies)
            
        with self.create_span(
            span_name,
            trace.SpanKind.INTERNAL,
            attributes
        ) as span_context:
            yield WorkflowTaskSpanContext(span_context.span, self)
    
    @asynccontextmanager
    async def async_operation_span(
        self,
        operation_name: str,
        operation_type: str = "async_task",
        **attributes
    ):
        """Create a span for async operations."""
        span_name = f"async.{operation_name}"
        
        span_attributes = {
            "crypto.operation_type": operation_type,
            "async.operation_name": operation_name,
            "async.coroutine": True
        }
        span_attributes.update(attributes)
        
        with self.create_span(
            span_name,
            trace.SpanKind.INTERNAL,
            span_attributes
        ) as span_context:
            yield AsyncSpanContext(span_context.span, self)
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive parameters."""
        sensitive_keys = {"api_key", "secret", "password", "token", "signature"}
        sanitized = {}
        
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
                
        return sanitized


class ManualSpanContext:
    """Base context for manual spans."""
    
    def __init__(self, span: Span, manager: ManualSpanManager):
        self.span = span
        self.manager = manager
        self.start_time = time.time()
        
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the span."""
        self.span.add_event(name, attributes or {})
        
    def set_attribute(self, key: str, value: Any):
        """Set an attribute on the span."""
        self.span.set_attribute(key, value)
        
    def set_status(self, status: Status):
        """Set span status."""
        self.span.set_status(status)
        
    def record_exception(self, exception: Exception):
        """Record an exception on the span."""
        self.span.record_exception(exception)
        
    def get_duration_ms(self) -> float:
        """Get current duration in milliseconds."""
        return (time.time() - self.start_time) * 1000


class BinanceApiSpanContext(ManualSpanContext):
    """Context for Binance API spans."""
    
    def set_request_details(self, params: Dict[str, Any], headers: Dict[str, str]):
        """Set API request details."""
        safe_params = self.manager._sanitize_params(params)
        self.set_attribute("api.request.params", str(safe_params))
        self.set_attribute("api.request.param_count", len(params))
        
        # Extract important headers (non-sensitive)
        safe_headers = {k: v for k, v in headers.items() 
                       if k.lower() not in ["authorization", "x-mbx-apikey"]}
        self.set_attribute("api.request.headers", str(safe_headers))
        
    def set_response_details(
        self,
        status_code: int,
        response_size_bytes: int,
        response_time_ms: float,
        rate_limit_headers: Optional[Dict[str, str]] = None
    ):
        """Set API response details."""
        self.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
        self.set_attribute("api.response.size_bytes", response_size_bytes)
        self.set_attribute("api.response.time_ms", response_time_ms)
        
        if rate_limit_headers:
            for header, value in rate_limit_headers.items():
                attr_name = f"api.rate_limit.{header.replace('-', '_').lower()}"
                self.set_attribute(attr_name, value)
                
    def record_api_error(self, error_code: str, error_message: str):
        """Record API-specific error."""
        self.set_attribute("api.error.code", error_code)
        self.set_attribute("api.error.message", error_message)
        self.add_event("api.error", {
            "error_code": error_code,
            "error_message": error_message
        })


class S3StorageSpanContext(ManualSpanContext):
    """Context for S3 storage spans."""
    
    def set_upload_details(self, file_count: int, total_size_bytes: int, encryption: str):
        """Set upload operation details."""
        self.set_attribute("storage.upload.file_count", file_count)
        self.set_attribute("storage.upload.total_size_bytes", total_size_bytes)
        self.set_attribute("storage.encryption", encryption)
        
    def set_download_details(self, file_count: int, total_size_bytes: int):
        """Set download operation details."""
        self.set_attribute("storage.download.file_count", file_count)
        self.set_attribute("storage.download.total_size_bytes", total_size_bytes)
        
    def calculate_throughput(self, bytes_transferred: int):
        """Calculate and set throughput metrics."""
        duration_s = self.get_duration_ms() / 1000
        if duration_s > 0:
            throughput_mbps = (bytes_transferred / 1024 / 1024) / duration_s
            self.set_attribute("storage.throughput_mbps", throughput_mbps)


class DataProcessingSpanContext(ManualSpanContext):
    """Context for data processing spans."""
    
    def set_input_data(self, record_count: int, data_size_bytes: int):
        """Set input data characteristics."""
        self.set_attribute("processing.input.record_count", record_count)
        self.set_attribute("processing.input.size_bytes", data_size_bytes)
        
    def set_output_data(self, record_count: int, data_size_bytes: int):
        """Set output data characteristics."""
        self.set_attribute("processing.output.record_count", record_count)
        self.set_attribute("processing.output.size_bytes", data_size_bytes)
        
    def set_processing_stats(self, memory_usage_mb: float, cpu_usage_percent: float):
        """Set processing resource usage statistics."""
        self.set_attribute("processing.memory_usage_mb", memory_usage_mb)
        self.set_attribute("processing.cpu_usage_percent", cpu_usage_percent)
        
    def calculate_processing_rate(self, records_processed: int):
        """Calculate and set processing rate."""
        duration_s = self.get_duration_ms() / 1000
        if duration_s > 0:
            rate = records_processed / duration_s
            self.set_attribute("processing.rate_records_per_sec", rate)


class WorkflowTaskSpanContext(ManualSpanContext):
    """Context for workflow task spans."""
    
    def set_task_progress(self, completed_steps: int, total_steps: int):
        """Set task progress information."""
        self.set_attribute("task.progress.completed_steps", completed_steps)
        self.set_attribute("task.progress.total_steps", total_steps)
        progress_percent = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        self.set_attribute("task.progress.percent", progress_percent)
        
    def add_task_checkpoint(self, checkpoint_name: str, checkpoint_data: Dict[str, Any]):
        """Add a task checkpoint event."""
        self.add_event(f"task.checkpoint.{checkpoint_name}", checkpoint_data)
        
    def set_task_result(self, success: bool, result_summary: Dict[str, Any]):
        """Set task execution result."""
        self.set_attribute("task.success", success)
        self.set_attribute("task.result", str(result_summary))


class AsyncSpanContext(ManualSpanContext):
    """Context for async operation spans."""
    
    def set_async_details(self, coroutine_name: str, event_loop_id: str):
        """Set async operation details."""
        self.set_attribute("async.coroutine_name", coroutine_name)
        self.set_attribute("async.event_loop_id", event_loop_id)
        
    def add_await_event(self, awaited_operation: str, duration_ms: float):
        """Add an await event."""
        self.add_event("async.await", {
            "awaited_operation": awaited_operation,
            "duration_ms": duration_ms
        })


# Decorator functions for manual instrumentation
def manual_trace_binance_api(
    endpoint: str,
    method: str = "GET",
    extract_symbol: bool = True,
    extract_data_type: bool = True
):
    """Decorator for manual Binance API tracing."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_manual_span_manager()
            
            # Extract symbol and data_type from function parameters if requested
            symbol = None
            data_type = None
            
            if extract_symbol and "symbol" in kwargs:
                symbol = kwargs["symbol"]
            if extract_data_type and "data_type" in kwargs:
                data_type = kwargs["data_type"]
                
            with manager.binance_api_span(
                endpoint=endpoint,
                method=method,
                symbol=symbol,
                data_type=data_type,
                request_params=kwargs
            ) as span_context:
                return func(span_context, *args, **kwargs)
                
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager = get_manual_span_manager()
            
            # Extract symbol and data_type from function parameters if requested
            symbol = None
            data_type = None
            
            if extract_symbol and "symbol" in kwargs:
                symbol = kwargs["symbol"]
            if extract_data_type and "data_type" in kwargs:
                data_type = kwargs["data_type"]
                
            with manager.binance_api_span(
                endpoint=endpoint,
                method=method,
                symbol=symbol,
                data_type=data_type,
                request_params=kwargs
            ) as span_context:
                return await func(span_context, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    return decorator


def manual_trace_data_processing(
    processor_name: str,
    data_type: str = "klines",
    auto_record_stats: bool = True
):
    """Decorator for manual data processing tracing."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_manual_span_manager()
            
            with manager.data_processing_span(
                processor_name=processor_name,
                data_type=data_type,
                symbol=kwargs.get("symbol", "BTCUSDT"),
                record_count=kwargs.get("record_count"),
                processing_stage=kwargs.get("processing_stage")
            ) as span_context:
                result = func(span_context, *args, **kwargs)
                
                # Auto-record processing statistics if enabled
                if auto_record_stats and hasattr(result, "__len__"):
                    span_context.set_output_data(len(result), 0)  # Size calculation would need implementation
                    
                return result
                
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            manager = get_manual_span_manager()
            
            with manager.data_processing_span(
                processor_name=processor_name,
                data_type=data_type,
                symbol=kwargs.get("symbol", "BTCUSDT"),
                record_count=kwargs.get("record_count"),
                processing_stage=kwargs.get("processing_stage")
            ) as span_context:
                result = await func(span_context, *args, **kwargs)
                
                # Auto-record processing statistics if enabled
                if auto_record_stats and hasattr(result, "__len__"):
                    span_context.set_output_data(len(result), 0)  # Size calculation would need implementation
                    
                return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    return decorator


# Global manual span manager
_manual_span_manager: Optional[ManualSpanManager] = None


def get_manual_span_manager() -> ManualSpanManager:
    """Get global manual span manager."""
    global _manual_span_manager
    if _manual_span_manager is None:
        _manual_span_manager = ManualSpanManager()
    return _manual_span_manager