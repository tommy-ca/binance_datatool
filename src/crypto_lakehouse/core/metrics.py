"""Metrics collection for crypto lakehouse workflows."""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class WorkflowMetrics:
    """Workflow execution metrics."""
    workflow_name: str
    execution_state: str
    start_time: Optional[datetime]
    end_time: Optional[datetime] 
    duration: Optional[float]
    results: Dict[str, Any]
    metrics_data: Dict[str, Any]
    config_snapshot: Dict[str, Any]


class MetricsCollector:
    """Collects and manages workflow metrics."""
    
    def __init__(self):
        self.metrics = {}
        self.events = []
        self.errors = []
        
    def start_workflow(self, workflow_name: str):
        """Start metrics collection for a workflow."""
        self.metrics['workflow_name'] = workflow_name
        self.metrics['start_time'] = time.time()
        
    def end_workflow(self):
        """End metrics collection."""
        self.metrics['end_time'] = time.time()
        
    def record_event(self, event: str):
        """Record an event."""
        self.events.append({'event': event, 'timestamp': time.time()})
        
    def record_error(self, error: str):
        """Record an error."""
        self.errors.append({'error': error, 'timestamp': time.time()})
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        return {
            'metrics': self.metrics,
            'events': self.events,
            'errors': self.errors
        }