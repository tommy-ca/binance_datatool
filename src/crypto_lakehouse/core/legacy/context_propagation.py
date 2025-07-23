"""Context propagation and baggage management for distributed crypto operations."""

import logging
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager

from opentelemetry import trace, baggage, context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagators.b3 import B3MultiFormat, B3SingleFormat
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.propagate import set_global_textmap, composite

logger = logging.getLogger(__name__)


class CryptoContextPropagator:
    """Enhanced context propagator for crypto workflow operations."""
    
    def __init__(self):
        self.propagators = {
            "w3c": TraceContextTextMapPropagator(),
            "baggage": W3CBaggagePropagator(),
            "b3_multi": B3MultiFormat(),
            "b3_single": B3SingleFormat(),
            "jaeger": JaegerPropagator()
        }
        
        # Setup composite propagator with crypto-optimized configuration
        self.composite_propagator = composite.CompositeHTTPPropagator([
            self.propagators["w3c"],      # W3C Trace Context (primary)
            self.propagators["baggage"],  # W3C Baggage
            self.propagators["b3_multi"]  # B3 for Zipkin compatibility
        ])
        
        # Set as global propagator
        set_global_textmap(self.composite_propagator)
        
    def inject_crypto_context(
        self,
        carrier: Dict[str, str],
        crypto_workflow_id: Optional[str] = None,
        market: Optional[str] = None,
        processing_stage: Optional[str] = None,
        priority: Optional[str] = None,
        custom_baggage: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Inject crypto-specific context into carrier headers."""
        # Set crypto-specific baggage
        ctx = context.get_current()
        
        if crypto_workflow_id:
            ctx = baggage.set_baggage("crypto.workflow_id", crypto_workflow_id, ctx)
            
        if market:
            ctx = baggage.set_baggage("crypto.market", market, ctx)
            
        if processing_stage:
            ctx = baggage.set_baggage("crypto.processing_stage", processing_stage, ctx)
            
        if priority:
            ctx = baggage.set_baggage("crypto.priority", priority, ctx)
            
        # Add custom baggage
        if custom_baggage:
            for key, value in custom_baggage.items():
                # Ensure crypto namespace for custom baggage
                baggage_key = f"crypto.{key}" if not key.startswith("crypto.") else key
                ctx = baggage.set_baggage(baggage_key, value, ctx)
        
        # Use context to inject headers
        with context.use_context(ctx):
            self.composite_propagator.inject(carrier)
            
        return carrier
    
    def extract_crypto_context(self, carrier: Dict[str, str]) -> Dict[str, Any]:
        """Extract crypto-specific context from carrier headers."""
        # Extract context using composite propagator
        ctx = self.composite_propagator.extract(carrier)
        
        crypto_context = {}
        
        # Extract baggage with crypto namespace
        with context.use_context(ctx):
            crypto_baggage_keys = [
                "crypto.workflow_id",
                "crypto.market", 
                "crypto.processing_stage",
                "crypto.priority",
                "crypto.data_type",
                "crypto.symbol",
                "crypto.timeframe"
            ]
            
            for key in crypto_baggage_keys:
                value = baggage.get_baggage(key)
                if value:
                    crypto_context[key] = value
            
            # Extract trace context
            span_context = trace.get_current_span(ctx).get_span_context()
            if span_context.is_valid:
                crypto_context["trace_id"] = format(span_context.trace_id, "032x")
                crypto_context["span_id"] = format(span_context.span_id, "016x")
                crypto_context["trace_flags"] = span_context.trace_flags
                
        return crypto_context
    
    def create_workflow_context(
        self,
        workflow_id: str,
        workflow_name: str,
        market: str = "binance",
        data_types: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        priority: str = "normal"
    ) -> context.Context:
        """Create a context with crypto workflow baggage."""
        ctx = context.get_current()
        
        # Core workflow context
        ctx = baggage.set_baggage("crypto.workflow_id", workflow_id, ctx)
        ctx = baggage.set_baggage("crypto.workflow_name", workflow_name, ctx)
        ctx = baggage.set_baggage("crypto.market", market, ctx)
        ctx = baggage.set_baggage("crypto.priority", priority, ctx)
        
        # Optional context
        if data_types:
            ctx = baggage.set_baggage("crypto.data_types", ",".join(data_types), ctx)
            
        if symbols:
            ctx = baggage.set_baggage("crypto.symbols", ",".join(symbols), ctx)
            
        return ctx
    
    def create_processing_context(
        self,
        processing_stage: str,
        data_type: str = "klines",
        symbol: str = "BTCUSDT",
        record_count: Optional[int] = None,
        parent_context: Optional[context.Context] = None
    ) -> context.Context:
        """Create a context for data processing operations."""
        ctx = parent_context or context.get_current()
        
        # Processing-specific context
        ctx = baggage.set_baggage("crypto.processing_stage", processing_stage, ctx)
        ctx = baggage.set_baggage("crypto.data_type", data_type, ctx)
        ctx = baggage.set_baggage("crypto.symbol", symbol, ctx)
        
        if record_count is not None:
            ctx = baggage.set_baggage("crypto.record_count", str(record_count), ctx)
            
        return ctx
    
    def create_api_context(
        self,
        api_endpoint: str,
        market: str = "binance",
        api_type: str = "rest",
        rate_limit_info: Optional[Dict[str, Any]] = None,
        parent_context: Optional[context.Context] = None
    ) -> context.Context:
        """Create a context for API operations."""
        ctx = parent_context or context.get_current()
        
        # API-specific context
        ctx = baggage.set_baggage("crypto.api_endpoint", api_endpoint, ctx)
        ctx = baggage.set_baggage("crypto.market", market, ctx)
        ctx = baggage.set_baggage("crypto.api_type", api_type, ctx)
        
        # Rate limiting context
        if rate_limit_info:
            for key, value in rate_limit_info.items():
                baggage_key = f"crypto.rate_limit.{key}"
                ctx = baggage.set_baggage(baggage_key, str(value), ctx)
                
        return ctx
    
    @contextmanager
    def crypto_context(
        self,
        workflow_id: Optional[str] = None,
        market: Optional[str] = None,
        processing_stage: Optional[str] = None,
        **baggage_items
    ):
        """Context manager for crypto operations with automatic baggage management."""
        ctx = context.get_current()
        
        # Set crypto baggage
        if workflow_id:
            ctx = baggage.set_baggage("crypto.workflow_id", workflow_id, ctx)
        if market:
            ctx = baggage.set_baggage("crypto.market", market, ctx)
        if processing_stage:
            ctx = baggage.set_baggage("crypto.processing_stage", processing_stage, ctx)
            
        # Set additional baggage items
        for key, value in baggage_items.items():
            baggage_key = f"crypto.{key}" if not key.startswith("crypto.") else key
            ctx = baggage.set_baggage(baggage_key, str(value), ctx)
        
        # Use the context
        token = context.attach(ctx)
        try:
            yield CryptoBaggageAccessor(ctx)
        finally:
            context.detach(token)


class CryptoBaggageAccessor:
    """Helper class for accessing crypto baggage within context."""
    
    def __init__(self, ctx: context.Context):
        self.context = ctx
        
    def get_workflow_id(self) -> Optional[str]:
        """Get workflow ID from baggage."""
        with context.use_context(self.context):
            return baggage.get_baggage("crypto.workflow_id")
    
    def get_market(self) -> Optional[str]:
        """Get market from baggage."""
        with context.use_context(self.context):
            return baggage.get_baggage("crypto.market")
    
    def get_processing_stage(self) -> Optional[str]:
        """Get processing stage from baggage."""
        with context.use_context(self.context):
            return baggage.get_baggage("crypto.processing_stage")
    
    def get_data_type(self) -> Optional[str]:
        """Get data type from baggage."""
        with context.use_context(self.context):
            return baggage.get_baggage("crypto.data_type")
    
    def get_symbol(self) -> Optional[str]:
        """Get symbol from baggage."""
        with context.use_context(self.context):
            return baggage.get_baggage("crypto.symbol")
    
    def get_priority(self) -> Optional[str]:
        """Get priority from baggage."""
        with context.use_context(self.context):
            return baggage.get_baggage("crypto.priority")
    
    def get_custom_baggage(self, key: str) -> Optional[str]:
        """Get custom baggage item."""
        with context.use_context(self.context):
            return baggage.get_baggage(key)
    
    def get_all_crypto_baggage(self) -> Dict[str, str]:
        """Get all crypto-related baggage items."""
        crypto_baggage = {}
        
        with context.use_context(self.context):
            # Get all baggage and filter for crypto keys
            all_baggage = baggage.get_all()
            
            for key, value in all_baggage.items():
                if key.startswith("crypto."):
                    crypto_baggage[key] = value
                    
        return crypto_baggage


class DistributedTracingHelper:
    """Helper for distributed tracing across crypto workflow components."""
    
    def __init__(self):
        self.propagator = CryptoContextPropagator()
        
    def create_http_headers_for_downstream(
        self,
        workflow_id: Optional[str] = None,
        market: Optional[str] = None,
        processing_stage: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Create HTTP headers for downstream service calls."""
        headers = custom_headers.copy() if custom_headers else {}
        
        # Inject current trace context and crypto baggage
        self.propagator.inject_crypto_context(
            carrier=headers,
            crypto_workflow_id=workflow_id,
            market=market,
            processing_stage=processing_stage
        )
        
        return headers
    
    def extract_context_from_http_headers(
        self, 
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Extract context from incoming HTTP headers."""
        return self.propagator.extract_crypto_context(headers)
    
    def propagate_to_prefect_context(
        self,
        flow_run_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Propagate crypto context to Prefect flow run context."""
        context_data = {}
        
        # Get current crypto baggage
        accessor = CryptoBaggageAccessor(context.get_current())
        crypto_baggage = accessor.get_all_crypto_baggage()
        
        # Add to Prefect context
        context_data.update(crypto_baggage)
        
        # Add trace information
        current_span = trace.get_current_span()
        if current_span.is_recording():
            span_context = current_span.get_span_context()
            context_data.update({
                "trace_id": format(span_context.trace_id, "032x"),
                "span_id": format(span_context.span_id, "016x"),
                "trace_flags": span_context.trace_flags
            })
        
        return context_data
    
    def restore_from_prefect_context(
        self,
        flow_run_context: Dict[str, Any]
    ) -> context.Context:
        """Restore crypto context from Prefect flow run context."""
        ctx = context.get_current()
        
        # Restore crypto baggage
        for key, value in flow_run_context.items():
            if key.startswith("crypto."):
                ctx = baggage.set_baggage(key, value, ctx)
        
        return ctx


# Global instances
_crypto_propagator: Optional[CryptoContextPropagator] = None
_distributed_helper: Optional[DistributedTracingHelper] = None


def get_crypto_propagator() -> CryptoContextPropagator:
    """Get global crypto context propagator."""
    global _crypto_propagator
    if _crypto_propagator is None:
        _crypto_propagator = CryptoContextPropagator()
    return _crypto_propagator


def get_distributed_tracing_helper() -> DistributedTracingHelper:
    """Get global distributed tracing helper."""
    global _distributed_helper
    if _distributed_helper is None:
        _distributed_helper = DistributedTracingHelper()
    return _distributed_helper


# Convenience functions
def create_crypto_headers(
    workflow_id: Optional[str] = None,
    market: Optional[str] = None,
    processing_stage: Optional[str] = None,
    **kwargs
) -> Dict[str, str]:
    """Create HTTP headers with crypto context (convenience function)."""
    helper = get_distributed_tracing_helper()
    return helper.create_http_headers_for_downstream(
        workflow_id=workflow_id,
        market=market,
        processing_stage=processing_stage,
        **kwargs
    )


def extract_crypto_headers(headers: Dict[str, str]) -> Dict[str, Any]:
    """Extract crypto context from HTTP headers (convenience function)."""
    helper = get_distributed_tracing_helper()
    return helper.extract_context_from_http_headers(headers)


@contextmanager
def crypto_workflow_context(
    workflow_id: str,
    workflow_name: str,
    market: str = "binance",
    **kwargs
):
    """Context manager for crypto workflow operations."""
    propagator = get_crypto_propagator()
    
    ctx = propagator.create_workflow_context(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        market=market,
        **kwargs
    )
    
    token = context.attach(ctx)
    try:
        yield CryptoBaggageAccessor(ctx)
    finally:
        context.detach(token)


@contextmanager  
def crypto_processing_context(
    processing_stage: str,
    data_type: str = "klines",
    symbol: str = "BTCUSDT",
    **kwargs
):
    """Context manager for crypto data processing operations."""
    propagator = get_crypto_propagator()
    
    ctx = propagator.create_processing_context(
        processing_stage=processing_stage,
        data_type=data_type,
        symbol=symbol,
        **kwargs
    )
    
    token = context.attach(ctx)
    try:
        yield CryptoBaggageAccessor(ctx)
    finally:
        context.detach(token)