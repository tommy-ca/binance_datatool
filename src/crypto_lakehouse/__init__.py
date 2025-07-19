"""
Crypto Lakehouse - Unified Data Platform for Cryptocurrency Analytics

A comprehensive data lakehouse solution for cryptocurrency data ingestion, processing,
and analytics. Provides standardized workflows, data models, and infrastructure
for handling multi-market cryptocurrency data from various sources.

Architecture:
- Modular workflow framework with dependency injection
- Event-driven processing for scalable data operations  
- Unified configuration management and validation
- Comprehensive metrics collection and monitoring
- Extensible plugin architecture for custom data sources

Key Features:
- Multi-source data integration (REST API, WebSocket, Archive)
- Matrix-driven collection strategies
- Parallel processing with resource management
- Schema validation and data quality assurance
- Performance optimization and caching
- Cloud storage integration capabilities

Usage:
    from crypto_lakehouse.workflows import ArchiveCollectionWorkflow
    from crypto_lakehouse.core import WorkflowConfig
    
    config = WorkflowConfig.from_file("config.json")
    workflow = ArchiveCollectionWorkflow(config)
    results = workflow.execute()
"""

__version__ = "1.0.0"
__author__ = "Crypto Lakehouse Team"
__description__ = "Unified cryptocurrency data lakehouse platform"

# Core exports
from .core.base import BaseWorkflow
from .core.config import WorkflowConfig
from .core.metrics import MetricsCollector, WorkflowMetrics
from .core.exceptions import ValidationError

# Workflow exports
from .workflows.archive_collection import ArchiveCollectionWorkflow

__all__ = [
    # Core Framework
    "BaseWorkflow",
    "WorkflowConfig", 
    "MetricsCollector",
    "WorkflowMetrics",
    "ValidationError",
    
    # Workflows
    "ArchiveCollectionWorkflow",
    
    # Package Info
    "__version__",
    "__author__",
    "__description__"
]