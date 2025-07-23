"""Unified OpenTelemetry SDK for crypto lakehouse with comprehensive observability."""

import logging
import os
import atexit
from typing import Dict, Any, Optional, List

from .otel_config import get_otel_config
from .otel_metrics import get_global_metrics, BackwardCompatibleMetricsCollector
from .otel_tracing import get_tracing_config, get_tracer
from .auto_instrumentation import initialize_auto_instrumentation, get_auto_instrumentation_manager
from .crypto_workflow_tracing import get_workflow_tracer
from .context_propagation import get_crypto_propagator, get_distributed_tracing_helper
from .manual_instrumentation import get_manual_span_manager
from .performance_monitoring import get_resource_monitor, get_performance_span_manager

logger = logging.getLogger(__name__)


class UnifiedOpenTelemetrySDK:
    """Unified SDK for comprehensive OpenTelemetry integration in crypto lakehouse."""
    
    def __init__(
        self,
        service_name: str = "crypto-lakehouse",
        service_version: str = "2.0.0",
        environment: Optional[str] = None,
        enable_auto_instrumentation: bool = True,
        enable_performance_monitoring: bool = True,
        enable_console_exports: Optional[bool] = None
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment or os.getenv("ENVIRONMENT", "local")
        self.enable_auto_instrumentation = enable_auto_instrumentation
        self.enable_performance_monitoring = enable_performance_monitoring
        self.enable_console_exports = enable_console_exports if enable_console_exports is not None else (self.environment == "local")
        
        self._initialized = False
        self._components: Dict[str, Any] = {}
        
    def initialize(self) -> Dict[str, Any]:
        """Initialize all OpenTelemetry components."""
        if self._initialized:
            logger.warning("OpenTelemetry SDK already initialized")
            return self._components
            
        logger.info(f"Initializing OpenTelemetry SDK for {self.service_name} v{self.service_version}")
        
        try:
            # Initialize core configuration
            self._initialize_core_config()
            
            # Initialize metrics
            self._initialize_metrics()
            
            # Initialize tracing
            self._initialize_tracing()
            
            # Initialize auto-instrumentation
            if self.enable_auto_instrumentation:
                self._initialize_auto_instrumentation()
            
            # Initialize workflow tracing
            self._initialize_workflow_tracing()
            
            # Initialize context propagation
            self._initialize_context_propagation()
            
            # Initialize manual instrumentation
            self._initialize_manual_instrumentation()
            
            # Initialize performance monitoring
            if self.enable_performance_monitoring:
                self._initialize_performance_monitoring()
            
            # Register shutdown handler
            atexit.register(self.shutdown)
            
            self._initialized = True
            logger.info("OpenTelemetry SDK initialization complete")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry SDK: {e}")
            raise
            
        return self._components
    
    def _initialize_core_config(self):
        """Initialize core OpenTelemetry configuration."""
        # Metrics configuration
        metrics_config = get_otel_config(
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment
        )
        self._components["metrics_config"] = metrics_config
        
        # Tracing configuration
        tracing_config = get_tracing_config(
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            enable_console_export=self.enable_console_exports,
            enable_auto_instrumentation=self.enable_auto_instrumentation
        )
        self._components["tracing_config"] = tracing_config
        
        logger.info("Core OpenTelemetry configuration initialized")
    
    def _initialize_metrics(self):
        """Initialize metrics collection."""
        # Get global metrics instance
        otel_metrics = get_global_metrics()
        self._components["otel_metrics"] = otel_metrics
        
        # Get backward-compatible metrics collector
        metrics_collector = BackwardCompatibleMetricsCollector(enable_otel=True)
        self._components["metrics_collector"] = metrics_collector
        
        logger.info("OpenTelemetry metrics initialized")
    
    def _initialize_tracing(self):
        """Initialize distributed tracing."""
        # Get global tracer
        tracer = get_tracer("crypto_lakehouse")
        self._components["tracer"] = tracer
        
        logger.info("OpenTelemetry tracing initialized")
    
    def _initialize_auto_instrumentation(self):
        """Initialize automatic instrumentation."""
        # Configure auto-instrumentation
        auto_instr_config = {
            "requests": {
                "excluded_urls": ["health", "metrics", "ping"]
            },
            "aiohttp": {
                "excluded_urls": ["health", "metrics", "ping"]
            }
        }
        
        # Initialize auto-instrumentation
        manager = initialize_auto_instrumentation(
            enable_requests=True,
            enable_aiohttp=True,
            enable_boto3=True,
            enable_database=True,
            enable_redis=True,
            custom_config=auto_instr_config
        )
        
        self._components["auto_instrumentation"] = manager
        logger.info(f"Auto-instrumentation initialized for: {manager.get_instrumented_modules()}")
    
    def _initialize_workflow_tracing(self):
        """Initialize crypto workflow tracing."""
        workflow_tracer = get_workflow_tracer()
        self._components["workflow_tracer"] = workflow_tracer
        
        logger.info("Crypto workflow tracing initialized")
    
    def _initialize_context_propagation(self):
        """Initialize context propagation."""
        # Context propagator
        propagator = get_crypto_propagator()
        self._components["context_propagator"] = propagator
        
        # Distributed tracing helper
        distributed_helper = get_distributed_tracing_helper()
        self._components["distributed_helper"] = distributed_helper
        
        logger.info("Context propagation initialized")
    
    def _initialize_manual_instrumentation(self):
        """Initialize manual instrumentation."""
        manual_span_manager = get_manual_span_manager()
        self._components["manual_span_manager"] = manual_span_manager
        
        logger.info("Manual instrumentation initialized")
    
    def _initialize_performance_monitoring(self):
        """Initialize performance monitoring."""
        # Resource monitor
        resource_monitor = get_resource_monitor()
        self._components["resource_monitor"] = resource_monitor
        
        # Performance-aware span manager
        performance_span_manager = get_performance_span_manager()
        self._components["performance_span_manager"] = performance_span_manager
        
        logger.info("Performance monitoring initialized")
    
    def get_component(self, component_name: str) -> Any:
        """Get a specific OpenTelemetry component."""
        if not self._initialized:
            raise RuntimeError("OpenTelemetry SDK not initialized. Call initialize() first.")
            
        return self._components.get(component_name)
    
    def get_all_components(self) -> Dict[str, Any]:
        """Get all initialized components."""
        if not self._initialized:
            raise RuntimeError("OpenTelemetry SDK not initialized. Call initialize() first.")
            
        return self._components.copy()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all OpenTelemetry components."""
        if not self._initialized:
            return {"status": "not_initialized", "components": {}}
        
        health_status = {
            "status": "healthy",
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "initialized": self._initialized,
            "components": {}
        }
        
        # Check each component
        for name, component in self._components.items():
            try:
                if name == "auto_instrumentation":
                    health_status["components"][name] = {
                        "status": "healthy",
                        "instrumented_modules": component.get_instrumented_modules()
                    }
                elif name == "resource_monitor":
                    current_usage = component.get_current_usage()
                    health_status["components"][name] = {
                        "status": "healthy",
                        "cpu_percent": current_usage.cpu_percent,
                        "memory_mb": current_usage.memory_mb,
                        "high_load": component.is_high_load()
                    }
                else:
                    health_status["components"][name] = {"status": "healthy"}
                    
            except Exception as e:
                health_status["components"][name] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
        
        return health_status
    
    def shutdown(self, timeout_seconds: int = 30):
        """Shutdown all OpenTelemetry components."""
        if not self._initialized:
            return
            
        logger.info("Shutting down OpenTelemetry SDK")
        
        try:
            # Shutdown tracing
            if "tracing_config" in self._components:
                self._components["tracing_config"].shutdown(timeout_seconds * 1000)
            
            # Shutdown metrics
            if "metrics_config" in self._components:
                self._components["metrics_config"].shutdown()
            
            # Shutdown performance monitoring
            if "resource_monitor" in self._components:
                self._components["resource_monitor"].stop_monitoring()
            
            self._initialized = False
            logger.info("OpenTelemetry SDK shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during OpenTelemetry SDK shutdown: {e}")


# Global SDK instance
_unified_sdk: Optional[UnifiedOpenTelemetrySDK] = None


def get_unified_sdk(
    service_name: str = "crypto-lakehouse",
    service_version: str = "2.0.0",
    environment: Optional[str] = None,
    enable_auto_instrumentation: bool = True,
    enable_performance_monitoring: bool = True,
    enable_console_exports: Optional[bool] = None,
    auto_initialize: bool = True
) -> UnifiedOpenTelemetrySDK:
    """Get or create global unified OpenTelemetry SDK."""
    global _unified_sdk
    
    if _unified_sdk is None:
        _unified_sdk = UnifiedOpenTelemetrySDK(
            service_name=service_name,
            service_version=service_version,
            environment=environment,
            enable_auto_instrumentation=enable_auto_instrumentation,
            enable_performance_monitoring=enable_performance_monitoring,
            enable_console_exports=enable_console_exports
        )
        
        if auto_initialize:
            _unified_sdk.initialize()
    
    return _unified_sdk


def initialize_crypto_observability(
    service_name: str = "crypto-lakehouse",
    service_version: str = "2.0.0",
    environment: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Initialize complete crypto observability stack (convenience function)."""
    sdk = get_unified_sdk(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        **kwargs
    )
    
    components = sdk.get_all_components()
    
    logger.info(f"Crypto observability stack initialized with {len(components)} components")
    return components


def get_observability_health() -> Dict[str, Any]:
    """Get health status of observability stack (convenience function)."""
    if _unified_sdk is None:
        return {"status": "not_initialized"}
        
    return _unified_sdk.get_health_status()


def shutdown_observability(timeout_seconds: int = 30):
    """Shutdown observability stack (convenience function)."""
    if _unified_sdk is not None:
        _unified_sdk.shutdown(timeout_seconds)