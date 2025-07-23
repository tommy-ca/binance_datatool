"""Performance monitoring and resource-aware tracing for crypto operations."""

import logging
import time
import threading
import psutil
from typing import Dict, Any, Optional, List, Tuple
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum

from opentelemetry import trace
from opentelemetry.trace import Span

logger = logging.getLogger(__name__)


class PerformanceThreshold(Enum):
    """Performance threshold levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ResourceUsage:
    """Resource usage snapshot."""
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_io_sent_mb: float = 0.0
    network_io_recv_mb: float = 0.0
    active_threads: int = 0


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    duration_ms: float = 0.0
    cpu_usage_delta: float = 0.0
    memory_usage_delta_mb: float = 0.0
    throughput_records_per_sec: float = 0.0
    throughput_mbps: float = 0.0
    error_rate: float = 0.0
    resource_efficiency_score: float = 0.0


class ResourceMonitor:
    """Monitors system resources for performance-aware tracing."""
    
    def __init__(
        self,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 85.0,
        sampling_interval: float = 1.0,
        history_size: int = 100
    ):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.sampling_interval = sampling_interval
        self.history_size = history_size
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._resource_history: List[ResourceUsage] = []
        self._current_usage = ResourceUsage()
        
        # Initialize psutil objects for efficiency
        self._process = psutil.Process()
        self._initial_disk_io = psutil.disk_io_counters()
        self._initial_net_io = psutil.net_io_counters()
        
    def start_monitoring(self):
        """Start resource monitoring in background thread."""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Resource monitoring started")
        
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Resource monitoring stopped")
        
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                usage = self._collect_resource_usage()
                
                with self._lock:
                    self._current_usage = usage
                    self._resource_history.append(usage)
                    
                    # Keep only recent history
                    if len(self._resource_history) > self.history_size:
                        self._resource_history = self._resource_history[-self.history_size:]
                        
                time.sleep(self.sampling_interval)
                
            except Exception as e:
                logger.warning(f"Error in resource monitoring: {e}")
                time.sleep(self.sampling_interval)
    
    def _collect_resource_usage(self) -> ResourceUsage:
        """Collect current resource usage."""
        usage = ResourceUsage()
        
        try:
            # CPU usage
            usage.cpu_percent = self._process.cpu_percent()
            
            # Memory usage
            memory_info = self._process.memory_info()
            usage.memory_mb = memory_info.rss / 1024 / 1024
            usage.memory_percent = self._process.memory_percent()
            
            # Disk I/O
            current_disk_io = psutil.disk_io_counters()
            if current_disk_io and self._initial_disk_io:
                usage.disk_io_read_mb = (current_disk_io.read_bytes - self._initial_disk_io.read_bytes) / 1024 / 1024
                usage.disk_io_write_mb = (current_disk_io.write_bytes - self._initial_disk_io.write_bytes) / 1024 / 1024
            
            # Network I/O
            current_net_io = psutil.net_io_counters()
            if current_net_io and self._initial_net_io:
                usage.network_io_sent_mb = (current_net_io.bytes_sent - self._initial_net_io.bytes_sent) / 1024 / 1024
                usage.network_io_recv_mb = (current_net_io.bytes_recv - self._initial_net_io.bytes_recv) / 1024 / 1024
            
            # Thread count
            usage.active_threads = self._process.num_threads()
            
        except Exception as e:
            logger.debug(f"Error collecting resource usage: {e}")
            
        return usage
    
    def get_current_usage(self) -> ResourceUsage:
        """Get current resource usage."""
        with self._lock:
            return self._current_usage
    
    def get_usage_history(self, duration_seconds: Optional[float] = None) -> List[ResourceUsage]:
        """Get resource usage history."""
        with self._lock:
            if duration_seconds is None:
                return self._resource_history.copy()
            
            cutoff_time = time.time() - duration_seconds
            return [usage for usage in self._resource_history if usage.timestamp >= cutoff_time]
    
    def is_high_load(self) -> bool:
        """Check if system is under high load."""
        usage = self.get_current_usage()
        return (usage.cpu_percent > self.cpu_threshold or 
                usage.memory_percent > self.memory_threshold)
    
    def get_load_factor(self) -> float:
        """Get load factor (0.0 = no load, 1.0 = at threshold, >1.0 = over threshold)."""
        usage = self.get_current_usage()
        
        cpu_factor = usage.cpu_percent / self.cpu_threshold
        memory_factor = usage.memory_percent / self.memory_threshold
        
        return max(cpu_factor, memory_factor)
    
    def calculate_performance_threshold(self) -> PerformanceThreshold:
        """Calculate current performance threshold level."""
        load_factor = self.get_load_factor()
        
        if load_factor < 0.5:
            return PerformanceThreshold.LOW
        elif load_factor < 0.75:
            return PerformanceThreshold.MEDIUM
        elif load_factor < 1.0:
            return PerformanceThreshold.HIGH
        else:
            return PerformanceThreshold.CRITICAL


class PerformanceAwareSpanManager:
    """Span manager with performance monitoring integration."""
    
    def __init__(self, resource_monitor: Optional[ResourceMonitor] = None):
        self.resource_monitor = resource_monitor or ResourceMonitor()
        self.tracer = trace.get_tracer("performance_aware")
        
        # Start monitoring if not already started
        if not self.resource_monitor._monitoring:
            self.resource_monitor.start_monitoring()
    
    @contextmanager
    def performance_aware_span(
        self,
        span_name: str,
        auto_adjust_sampling: bool = True,
        record_resource_usage: bool = True,
        performance_budget_ms: Optional[float] = None,
        **span_attributes
    ):
        """Create a performance-aware span with resource monitoring."""
        # Check if we should skip or adjust tracing based on system load
        if auto_adjust_sampling:
            threshold = self.resource_monitor.calculate_performance_threshold()
            
            # Skip tracing for non-critical operations under high load
            if (threshold == PerformanceThreshold.CRITICAL and 
                span_attributes.get("crypto.priority", "normal") != "high"):
                
                # Create a no-op span context
                yield NoOpSpanContext()
                return
        
        # Collect baseline resource usage
        start_usage = self.resource_monitor.get_current_usage() if record_resource_usage else None
        start_time = time.time()
        
        # Add performance attributes
        attributes = {
            "performance.monitoring_enabled": record_resource_usage,
            "performance.auto_sampling": auto_adjust_sampling,
            "performance.threshold": self.resource_monitor.calculate_performance_threshold().value
        }
        attributes.update(span_attributes)
        
        if performance_budget_ms:
            attributes["performance.budget_ms"] = performance_budget_ms
        
        with self.tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield PerformanceSpanContext(
                    span, 
                    self.resource_monitor,
                    start_usage,
                    start_time,
                    performance_budget_ms
                )
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
                
            finally:
                # Record final performance metrics
                if record_resource_usage and start_usage:
                    self._record_performance_metrics(span, start_usage, start_time)
    
    def _record_performance_metrics(
        self, 
        span: Span, 
        start_usage: ResourceUsage, 
        start_time: float
    ):
        """Record performance metrics on span completion."""
        end_usage = self.resource_monitor.get_current_usage()
        duration_ms = (time.time() - start_time) * 1000
        
        # Calculate resource usage deltas
        cpu_delta = max(0, end_usage.cpu_percent - start_usage.cpu_percent)
        memory_delta_mb = end_usage.memory_mb - start_usage.memory_mb
        
        # Record metrics as span attributes
        span.set_attribute("performance.duration_ms", duration_ms)
        span.set_attribute("performance.cpu_usage_delta", cpu_delta)
        span.set_attribute("performance.memory_usage_delta_mb", memory_delta_mb)
        span.set_attribute("performance.start_memory_mb", start_usage.memory_mb)
        span.set_attribute("performance.end_memory_mb", end_usage.memory_mb)
        span.set_attribute("performance.start_cpu_percent", start_usage.cpu_percent)
        span.set_attribute("performance.end_cpu_percent", end_usage.cpu_percent)
        
        # Calculate efficiency score (lower is better)
        efficiency_score = self._calculate_efficiency_score(duration_ms, cpu_delta, memory_delta_mb)
        span.set_attribute("performance.efficiency_score", efficiency_score)
        
        # Add performance event
        span.add_event("performance.metrics_recorded", {
            "duration_ms": duration_ms,
            "cpu_delta": cpu_delta,
            "memory_delta_mb": memory_delta_mb,
            "efficiency_score": efficiency_score
        })
    
    def _calculate_efficiency_score(
        self, 
        duration_ms: float, 
        cpu_delta: float, 
        memory_delta_mb: float
    ) -> float:
        """Calculate efficiency score based on resource usage."""
        # Normalize metrics (these are rough heuristics)
        duration_score = min(duration_ms / 1000, 10)  # Cap at 10 seconds
        cpu_score = cpu_delta / 100  # Normalize CPU percentage
        memory_score = max(0, memory_delta_mb) / 100  # Normalize memory MB
        
        # Weighted combination (lower is better)
        efficiency_score = (duration_score * 0.4 + 
                          cpu_score * 0.3 + 
                          memory_score * 0.3)
        
        return round(efficiency_score, 3)


class PerformanceSpanContext:
    """Context for performance-aware spans."""
    
    def __init__(
        self,
        span: Span,
        resource_monitor: ResourceMonitor,
        start_usage: Optional[ResourceUsage],
        start_time: float,
        performance_budget_ms: Optional[float] = None
    ):
        self.span = span
        self.resource_monitor = resource_monitor
        self.start_usage = start_usage
        self.start_time = start_time
        self.performance_budget_ms = performance_budget_ms
        
    def check_performance_budget(self) -> bool:
        """Check if operation is within performance budget."""
        if not self.performance_budget_ms:
            return True
            
        elapsed_ms = (time.time() - self.start_time) * 1000
        within_budget = elapsed_ms <= self.performance_budget_ms
        
        if not within_budget:
            self.span.add_event("performance.budget_exceeded", {
                "elapsed_ms": elapsed_ms,
                "budget_ms": self.performance_budget_ms,
                "overage_ms": elapsed_ms - self.performance_budget_ms
            })
            
        return within_budget
    
    def record_throughput(self, records_processed: int, bytes_processed: int = 0):
        """Record throughput metrics."""
        elapsed_s = time.time() - self.start_time
        
        if elapsed_s > 0:
            records_per_sec = records_processed / elapsed_s
            self.span.set_attribute("performance.throughput_records_per_sec", records_per_sec)
            
            if bytes_processed > 0:
                mbps = (bytes_processed / 1024 / 1024) / elapsed_s
                self.span.set_attribute("performance.throughput_mbps", mbps)
    
    def add_performance_checkpoint(self, checkpoint_name: str):
        """Add a performance checkpoint."""
        elapsed_ms = (time.time() - self.start_time) * 1000
        current_usage = self.resource_monitor.get_current_usage()
        
        checkpoint_data = {
            "elapsed_ms": elapsed_ms,
            "cpu_percent": current_usage.cpu_percent,
            "memory_mb": current_usage.memory_mb
        }
        
        if self.start_usage:
            checkpoint_data.update({
                "cpu_delta": current_usage.cpu_percent - self.start_usage.cpu_percent,
                "memory_delta_mb": current_usage.memory_mb - self.start_usage.memory_mb
            })
        
        self.span.add_event(f"performance.checkpoint.{checkpoint_name}", checkpoint_data)
    
    def set_performance_attribute(self, key: str, value: Any):
        """Set a performance-related attribute."""
        self.span.set_attribute(f"performance.{key}", value)


class NoOpSpanContext:
    """No-op span context for high-load situations."""
    
    def check_performance_budget(self) -> bool:
        return True
    
    def record_throughput(self, records_processed: int, bytes_processed: int = 0):
        pass
    
    def add_performance_checkpoint(self, checkpoint_name: str):
        pass
    
    def set_performance_attribute(self, key: str, value: Any):
        pass


# Global instances
_resource_monitor: Optional[ResourceMonitor] = None
_performance_span_manager: Optional[PerformanceAwareSpanManager] = None


def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
        _resource_monitor.start_monitoring()
    return _resource_monitor


def get_performance_span_manager() -> PerformanceAwareSpanManager:
    """Get global performance-aware span manager."""
    global _performance_span_manager
    if _performance_span_manager is None:
        _performance_span_manager = PerformanceAwareSpanManager(get_resource_monitor())
    return _performance_span_manager


# Convenience functions
@contextmanager
def performance_aware_operation(
    operation_name: str,
    performance_budget_ms: Optional[float] = None,
    auto_adjust_sampling: bool = True,
    **attributes
):
    """Context manager for performance-aware operations."""
    manager = get_performance_span_manager()
    
    with manager.performance_aware_span(
        span_name=operation_name,
        performance_budget_ms=performance_budget_ms,
        auto_adjust_sampling=auto_adjust_sampling,
        **attributes
    ) as context:
        yield context


def check_system_health() -> Dict[str, Any]:
    """Check current system health and performance status."""
    monitor = get_resource_monitor()
    current_usage = monitor.get_current_usage()
    
    return {
        "timestamp": time.time(),
        "cpu_percent": current_usage.cpu_percent,
        "memory_mb": current_usage.memory_mb,
        "memory_percent": current_usage.memory_percent,
        "load_factor": monitor.get_load_factor(),
        "performance_threshold": monitor.calculate_performance_threshold().value,
        "high_load": monitor.is_high_load(),
        "active_threads": current_usage.active_threads
    }