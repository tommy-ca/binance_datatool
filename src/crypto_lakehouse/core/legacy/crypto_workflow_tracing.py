"""Crypto workflow instrumentation for comprehensive tracing."""

import logging
import time
import asyncio
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, Dict, Any, List, Callable, Union, AsyncGenerator
from functools import wraps

from opentelemetry import trace, baggage
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.semconv.trace import SpanAttributes

from .otel_tracing import get_tracer, trace_operation

logger = logging.getLogger(__name__)


class CryptoWorkflowTracer:
    """Enhanced tracer for crypto workflow operations with comprehensive instrumentation."""
    
    def __init__(self, tracer_name: str = "crypto_workflow"):
        self.tracer = get_tracer(tracer_name)
        self._active_workflows: Dict[str, Span] = {}
        
    @contextmanager
    def trace_workflow_execution(
        self,
        workflow_name: str,
        workflow_type: str = "batch",
        market: str = "binance",
        symbols: Optional[List[str]] = None,
        data_types: Optional[List[str]] = None,
        **kwargs
    ):
        """Trace complete workflow execution with comprehensive context."""
        workflow_id = f"{workflow_name}_{int(time.time())}"
        
        attributes = {
            "crypto.operation_type": "workflow_execution",
            "crypto.workflow_name": workflow_name,
            "crypto.workflow_type": workflow_type,
            "crypto.workflow_id": workflow_id,
            "crypto.market": market,
            "crypto.symbols": ",".join(symbols) if symbols else "ALL",
            "crypto.data_types": ",".join(data_types) if data_types else "ALL",
            "workflow.start_time": time.time(),
        }
        
        # Add custom attributes
        for key, value in kwargs.items():
            if key.startswith("crypto.") or key.startswith("workflow."):
                attributes[key] = value
        
        # Set baggage for distributed context
        token = baggage.set_baggage("crypto.workflow_id", workflow_id)
        token = baggage.set_baggage("crypto.market", market, token)
        
        span_name = f"workflow.{workflow_name}"
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            self._active_workflows[workflow_id] = span
            
            # Record workflow start
            span.add_event("workflow.started", {
                "workflow.id": workflow_id,
                "workflow.configuration": str(kwargs)
            })
            
            start_time = time.time()
            
            try:
                yield WorkflowContext(workflow_id, span, self)
                span.set_status(Status(StatusCode.OK))
                span.add_event("workflow.completed")
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.add_event("workflow.failed", {
                    "error.type": type(e).__name__,
                    "error.message": str(e)
                })
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("workflow.duration_ms", duration_ms)
                span.set_attribute("workflow.end_time", time.time())
                
                if workflow_id in self._active_workflows:
                    del self._active_workflows[workflow_id]
    
    @contextmanager
    def trace_data_processing_stage(
        self,
        stage_name: str,
        data_type: str = "klines",
        symbol: str = "BTCUSDT",
        record_count: Optional[int] = None,
        data_size_bytes: Optional[int] = None,
        **kwargs
    ):
        """Trace data processing stages with performance metrics."""
        attributes = {
            "crypto.operation_type": "data_processing",
            "crypto.processing_stage": stage_name,
            "crypto.data_type": data_type,
            "crypto.symbol": symbol,
            "processing.start_time": time.time(),
        }
        
        if record_count is not None:
            attributes["crypto.record_count"] = record_count
        if data_size_bytes is not None:
            attributes["crypto.data_size_bytes"] = data_size_bytes
            
        # Add custom attributes
        for key, value in kwargs.items():
            if key.startswith("crypto.") or key.startswith("processing."):
                attributes[key] = value
        
        span_name = f"processing.{stage_name}"
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            start_time = time.time()
            start_memory = self._get_memory_usage()
            
            span.add_event("processing.stage.started", {
                "stage.name": stage_name,
                "data.type": data_type,
                "data.symbol": symbol
            })
            
            try:
                yield ProcessingContext(span, self)
                span.set_status(Status(StatusCode.OK))
                span.add_event("processing.stage.completed")
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.add_event("processing.stage.failed", {
                    "error.type": type(e).__name__,
                    "error.message": str(e)
                })
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                end_memory = self._get_memory_usage()
                memory_delta = end_memory - start_memory
                
                span.set_attribute("processing.duration_ms", duration_ms)
                span.set_attribute("processing.memory_delta_bytes", memory_delta)
                span.set_attribute("processing.end_time", time.time())
                
                # Calculate throughput if record count is available
                if record_count and duration_ms > 0:
                    throughput = record_count / (duration_ms / 1000)
                    span.set_attribute("processing.throughput_records_per_sec", throughput)
    
    @contextmanager
    def trace_api_interaction(
        self,
        api_endpoint: str,
        method: str = "GET",
        market: str = "binance",
        request_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Trace API interactions with comprehensive request/response details."""
        attributes = {
            "crypto.operation_type": "api_interaction",
            "crypto.market": market,
            "http.method": method,
            "http.url": api_endpoint,
            SpanAttributes.HTTP_METHOD: method,
            SpanAttributes.HTTP_URL: api_endpoint,
            "api.start_time": time.time(),
        }
        
        if request_params:
            # Sanitize sensitive parameters
            safe_params = self._sanitize_params(request_params)
            attributes["api.request.params"] = str(safe_params)
            attributes["api.request.param_count"] = len(safe_params)
        
        # Add custom attributes
        for key, value in kwargs.items():
            if key.startswith("api.") or key.startswith("http."):
                attributes[key] = value
        
        span_name = f"api.{market}.{method.lower()}"
        
        with self.tracer.start_as_current_span(
            span_name, 
            kind=trace.SpanKind.CLIENT,
            attributes=attributes
        ) as span:
            start_time = time.time()
            
            span.add_event("api.request.started", {
                "api.endpoint": api_endpoint,
                "api.method": method,
                "api.market": market
            })
            
            try:
                yield ApiContext(span, self)
                span.set_status(Status(StatusCode.OK))
                span.add_event("api.request.completed")
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.add_event("api.request.failed", {
                    "error.type": type(e).__name__,
                    "error.message": str(e)
                })
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("api.duration_ms", duration_ms)
                span.set_attribute("api.end_time", time.time())
    
    @contextmanager
    def trace_storage_operation(
        self,
        operation: str,
        storage_type: str = "s3",
        file_path: str = "",
        file_size_bytes: Optional[int] = None,
        storage_tier: str = "bronze",
        **kwargs
    ):
        """Trace storage operations with file and performance details."""
        attributes = {
            "crypto.operation_type": "storage_operation",
            "storage.operation": operation,
            "storage.type": storage_type,
            "storage.tier": storage_tier,
            "storage.file_path": file_path,
            "storage.start_time": time.time(),
        }
        
        if file_size_bytes is not None:
            attributes["storage.file_size_bytes"] = file_size_bytes
            attributes["storage.file_size_category"] = self._categorize_file_size(file_size_bytes)
        
        # Add custom attributes
        for key, value in kwargs.items():
            if key.startswith("storage."):
                attributes[key] = value
        
        span_name = f"storage.{operation}"
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            start_time = time.time()
            
            span.add_event("storage.operation.started", {
                "storage.operation": operation,
                "storage.type": storage_type,
                "storage.path": file_path
            })
            
            try:
                yield StorageContext(span, self)
                span.set_status(Status(StatusCode.OK))
                span.add_event("storage.operation.completed")
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.add_event("storage.operation.failed", {
                    "error.type": type(e).__name__,
                    "error.message": str(e)
                })
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("storage.duration_ms", duration_ms)
                span.set_attribute("storage.end_time", time.time())
                
                # Calculate throughput if file size is available
                if file_size_bytes and duration_ms > 0:
                    throughput_mbps = (file_size_bytes / 1024 / 1024) / (duration_ms / 1000)
                    span.set_attribute("storage.throughput_mbps", throughput_mbps)
    
    @asynccontextmanager
    async def trace_async_operation(
        self,
        operation_name: str,
        operation_type: str = "async_task",
        **attributes
    ):
        """Trace asynchronous operations with proper context propagation."""
        span_attributes = {
            "crypto.operation_type": operation_type,
            "async.operation_name": operation_name,
            "async.start_time": time.time(),
        }
        span_attributes.update(attributes)
        
        span_name = f"async.{operation_name}"
        
        with self.tracer.start_as_current_span(span_name, attributes=span_attributes) as span:
            start_time = time.time()
            
            span.add_event("async.operation.started", {
                "operation.name": operation_name,
                "operation.type": operation_type
            })
            
            try:
                yield AsyncOperationContext(span, self)
                span.set_status(Status(StatusCode.OK))
                span.add_event("async.operation.completed")
                
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.add_event("async.operation.failed", {
                    "error.type": type(e).__name__,
                    "error.message": str(e)
                })
                raise
                
            finally:
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("async.duration_ms", duration_ms)
                span.set_attribute("async.end_time", time.time())
    
    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return 0
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive parameters for tracing."""
        sensitive_keys = {"api_key", "secret", "password", "token", "signature"}
        sanitized = {}
        
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
                
        return sanitized
    
    def _categorize_file_size(self, size_bytes: int) -> str:
        """Categorize file size for metrics."""
        if size_bytes < 1024 * 1024:  # < 1MB
            return "small"
        elif size_bytes < 100 * 1024 * 1024:  # < 100MB
            return "medium"
        elif size_bytes < 1024 * 1024 * 1024:  # < 1GB
            return "large"
        else:
            return "xlarge"


class WorkflowContext:
    """Context object for workflow tracing operations."""
    
    def __init__(self, workflow_id: str, span: Span, tracer: CryptoWorkflowTracer):
        self.workflow_id = workflow_id
        self.span = span
        self.tracer = tracer
        self._stage_count = 0
        
    def add_workflow_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the workflow span."""
        self.span.add_event(f"workflow.{event_name}", attributes or {})
        
    def set_workflow_attribute(self, key: str, value: Any):
        """Set an attribute on the workflow span."""
        self.span.set_attribute(key, value)
        
    def start_stage(self, stage_name: str, **kwargs):
        """Start a new processing stage within the workflow."""
        self._stage_count += 1
        return self.tracer.trace_data_processing_stage(
            stage_name=f"{stage_name}_{self._stage_count}",
            **kwargs
        )


class ProcessingContext:
    """Context object for data processing operations."""
    
    def __init__(self, span: Span, tracer: CryptoWorkflowTracer):
        self.span = span
        self.tracer = tracer
        
    def add_processing_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the processing span."""
        self.span.add_event(f"processing.{event_name}", attributes or {})
        
    def set_processing_metric(self, metric_name: str, value: Union[int, float]):
        """Set a processing metric attribute."""
        self.span.set_attribute(f"processing.{metric_name}", value)
        
    def record_data_stats(self, record_count: int, data_size_bytes: int):
        """Record data processing statistics."""
        self.span.set_attribute("crypto.record_count", record_count)
        self.span.set_attribute("crypto.data_size_bytes", data_size_bytes)
        self.add_processing_event("data_stats_recorded", {
            "record_count": record_count,
            "data_size_bytes": data_size_bytes
        })


class ApiContext:
    """Context object for API interaction tracing."""
    
    def __init__(self, span: Span, tracer: CryptoWorkflowTracer):
        self.span = span
        self.tracer = tracer
        
    def set_response_details(
        self,
        status_code: int,
        response_size_bytes: Optional[int] = None,
        content_type: Optional[str] = None
    ):
        """Set API response details."""
        self.span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status_code)
        if response_size_bytes is not None:
            self.span.set_attribute("http.response.size", response_size_bytes)
        if content_type:
            self.span.set_attribute("http.response.content_type", content_type)
            
    def add_api_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the API span."""
        self.span.add_event(f"api.{event_name}", attributes or {})


class StorageContext:
    """Context object for storage operation tracing."""
    
    def __init__(self, span: Span, tracer: CryptoWorkflowTracer):
        self.span = span
        self.tracer = tracer
        
    def set_file_details(self, file_count: int, total_size_bytes: int):
        """Set file operation details."""
        self.span.set_attribute("storage.file_count", file_count)
        self.span.set_attribute("storage.total_size_bytes", total_size_bytes)
        
    def add_storage_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the storage span."""
        self.span.add_event(f"storage.{event_name}", attributes or {})


class AsyncOperationContext:
    """Context object for async operation tracing."""
    
    def __init__(self, span: Span, tracer: CryptoWorkflowTracer):
        self.span = span
        self.tracer = tracer
        
    def add_async_event(self, event_name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the async span."""
        self.span.add_event(f"async.{event_name}", attributes or {})
        
    def set_async_attribute(self, key: str, value: Any):
        """Set an attribute on the async span."""
        self.span.set_attribute(key, value)


# Global tracer instance
_workflow_tracer: Optional[CryptoWorkflowTracer] = None


def get_workflow_tracer() -> CryptoWorkflowTracer:
    """Get global crypto workflow tracer instance."""
    global _workflow_tracer
    if _workflow_tracer is None:
        _workflow_tracer = CryptoWorkflowTracer()
    return _workflow_tracer


# Convenience functions for common tracing patterns
def trace_crypto_workflow(
    workflow_name: str,
    workflow_type: str = "batch",
    market: str = "binance",
    **kwargs
):
    """Decorator for tracing crypto workflow functions with comprehensive instrumentation."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **func_kwargs):
            tracer = get_workflow_tracer()
            with tracer.trace_workflow_execution(
                workflow_name=workflow_name,
                workflow_type=workflow_type,
                market=market,
                **kwargs
            ) as context:
                return func(context, *args, **func_kwargs)
                
        @wraps(func)
        async def async_wrapper(*args, **func_kwargs):
            tracer = get_workflow_tracer()
            with tracer.trace_workflow_execution(
                workflow_name=workflow_name,
                workflow_type=workflow_type,
                market=market,
                **kwargs
            ) as context:
                return await func(context, *args, **func_kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator


def trace_data_processing(
    stage_name: str,
    data_type: str = "klines",
    **kwargs
):
    """Decorator for tracing data processing stages."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **func_kwargs):
            tracer = get_workflow_tracer()
            with tracer.trace_data_processing_stage(
                stage_name=stage_name,
                data_type=data_type,
                **kwargs
            ) as context:
                return func(context, *args, **func_kwargs)
                
        @wraps(func)
        async def async_wrapper(*args, **func_kwargs):
            tracer = get_workflow_tracer()
            with tracer.trace_data_processing_stage(
                stage_name=stage_name,
                data_type=data_type,
                **kwargs
            ) as context:
                return await func(context, *args, **func_kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator