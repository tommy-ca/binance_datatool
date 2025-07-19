"""
Base workflow framework for the crypto lakehouse platform.

This module defines the core abstractions and interfaces that all workflows
must implement, providing a consistent architecture across the platform.
"""

import abc
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable

from .config import WorkflowConfig
from .metrics import MetricsCollector, WorkflowMetrics
from .exceptions import WorkflowError, ConfigurationError


logger = logging.getLogger(__name__)


class BaseWorkflow(abc.ABC):
    """
    Abstract base class for all lakehouse workflows.
    
    Provides the foundational architecture patterns including:
    - Configuration management and validation
    - Metrics collection and monitoring  
    - Error handling and resilience
    - Lifecycle management (setup, execute, cleanup)
    - Resource management and dependency injection
    """
    
    def __init__(self, config: WorkflowConfig, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize workflow with configuration and optional metrics collector.
        
        Args:
            config: Validated workflow configuration
            metrics_collector: Optional metrics collector for monitoring
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._execution_state = "initialized"
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        
        # Validate configuration on initialization
        self._validate_configuration()
        
        # Setup workflow-specific logging
        self._setup_logging()
        
        # Initialize metrics tracking
        self.metrics.start_workflow(self.__class__.__name__)
    
    @abc.abstractmethod
    def _validate_configuration(self) -> None:
        """
        Validate workflow-specific configuration requirements.
        
        Must be implemented by subclasses to define their configuration schema.
        Should raise ConfigurationError for invalid configurations.
        """
        pass
    
    @abc.abstractmethod
    def _setup_workflow(self) -> None:
        """
        Setup workflow-specific resources and dependencies.
        
        Called before execute() to prepare workflow for execution.
        Should handle resource allocation, dependency injection, etc.
        """
        pass
    
    @abc.abstractmethod
    def _execute_workflow(self) -> Dict[str, Any]:
        """
        Execute the main workflow logic.
        
        Must be implemented by subclasses to define their core functionality.
        Should return a dictionary with execution results and metadata.
        """
        pass
    
    @abc.abstractmethod
    def _cleanup_workflow(self) -> None:
        """
        Cleanup workflow resources and finalize execution.
        
        Called after execute() to handle resource cleanup, finalization, etc.
        Should be implemented to ensure proper resource management.
        """
        pass
    
    def execute(self) -> WorkflowMetrics:
        """
        Execute the complete workflow lifecycle.
        
        Orchestrates the full workflow execution including setup, execution,
        metrics collection, error handling, and cleanup.
        
        Returns:
            WorkflowMetrics object with execution results and metadata
        """
        self.logger.info(f"Starting workflow execution: {self.__class__.__name__}")
        self._execution_state = "running"
        self._start_time = datetime.now()
        
        try:
            # Phase 1: Setup
            self.logger.debug("Setting up workflow")
            self._setup_workflow()
            self.metrics.record_event("workflow_setup_completed")
            
            # Phase 2: Execute
            self.logger.debug("Executing workflow")
            results = self._execute_workflow()
            self.metrics.record_event("workflow_execution_completed")
            
            # Phase 3: Cleanup
            self.logger.debug("Cleaning up workflow")
            self._cleanup_workflow()
            self.metrics.record_event("workflow_cleanup_completed")
            
            self._execution_state = "completed"
            self.logger.info("Workflow execution completed successfully")
            
        except Exception as e:
            self._execution_state = "failed"
            self.logger.error(f"Workflow execution failed: {e}")
            self.metrics.record_error(str(e))
            raise WorkflowError(f"Workflow execution failed: {e}") from e
        
        finally:
            self._end_time = datetime.now()
            self.metrics.end_workflow()
        
        # Generate final metrics
        return self._generate_metrics(results if self._execution_state == "completed" else {})
    
    def _setup_logging(self) -> None:
        """Setup workflow-specific logging configuration."""
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Add workflow-specific context to logger
        self.logger = logging.LoggerAdapter(self.logger, {
            'workflow': self.__class__.__name__,
            'config_id': self.config.get('id', 'unknown')
        })
    
    def _generate_metrics(self, results: Dict[str, Any]) -> WorkflowMetrics:
        """
        Generate comprehensive workflow metrics.
        
        Args:
            results: Workflow execution results
            
        Returns:
            WorkflowMetrics object with complete execution metadata
        """
        duration = None
        if self._start_time and self._end_time:
            duration = (self._end_time - self._start_time).total_seconds()
        
        return WorkflowMetrics(
            workflow_name=self.__class__.__name__,
            execution_state=self._execution_state,
            start_time=self._start_time,
            end_time=self._end_time,
            duration=duration,
            results=results,
            metrics_data=self.metrics.get_metrics(),
            config_snapshot=self.config.to_dict()
        )
    
    @property
    def execution_state(self) -> str:
        """Get current workflow execution state."""
        return self._execution_state
    
    @property
    def is_running(self) -> bool:
        """Check if workflow is currently running."""
        return self._execution_state == "running"
    
    @property
    def is_completed(self) -> bool:
        """Check if workflow completed successfully."""
        return self._execution_state == "completed"
    
    @property
    def is_failed(self) -> bool:
        """Check if workflow failed."""
        return self._execution_state == "failed"


class WorkflowExecutor:
    """
    High-level workflow execution orchestrator.
    
    Provides utilities for executing workflows with advanced features like:
    - Parallel workflow execution
    - Workflow dependency management
    - Resource pooling and management
    - Centralized metrics collection
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize workflow executor.
        
        Args:
            max_workers: Maximum number of concurrent workflows
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics = MetricsCollector()
        self.logger = logging.getLogger(__name__)
    
    def execute_workflow(self, workflow: BaseWorkflow) -> WorkflowMetrics:
        """
        Execute a single workflow.
        
        Args:
            workflow: Configured workflow instance to execute
            
        Returns:
            WorkflowMetrics with execution results
        """
        self.logger.info(f"Executing workflow: {workflow.__class__.__name__}")
        return workflow.execute()
    
    def execute_workflows_parallel(self, workflows: List[BaseWorkflow]) -> List[WorkflowMetrics]:
        """
        Execute multiple workflows in parallel.
        
        Args:
            workflows: List of configured workflow instances
            
        Returns:
            List of WorkflowMetrics for each executed workflow
        """
        self.logger.info(f"Executing {len(workflows)} workflows in parallel")
        
        results = []
        future_to_workflow = {}
        
        # Submit all workflows for execution
        for workflow in workflows:
            future = self.executor.submit(workflow.execute)
            future_to_workflow[future] = workflow
        
        # Collect results as they complete
        for future in as_completed(future_to_workflow):
            workflow = future_to_workflow[future]
            try:
                result = future.result()
                results.append(result)
                self.logger.info(f"Workflow {workflow.__class__.__name__} completed successfully")
            except Exception as e:
                self.logger.error(f"Workflow {workflow.__class__.__name__} failed: {e}")
                # Create error metrics for failed workflow
                error_metrics = WorkflowMetrics(
                    workflow_name=workflow.__class__.__name__,
                    execution_state="failed", 
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    duration=0,
                    results={},
                    metrics_data={"error": str(e)},
                    config_snapshot=workflow.config.to_dict()
                )
                results.append(error_metrics)
        
        return results
    
    def shutdown(self):
        """Shutdown the executor and cleanup resources."""
        self.logger.info("Shutting down workflow executor")
        self.executor.shutdown(wait=True)