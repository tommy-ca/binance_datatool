"""Base workflow orchestration classes."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from prefect import task

from ..core.config import Settings
from ..core.models import DataIngestionTask, IngestionMetadata

logger = logging.getLogger(__name__)


class BaseWorkflow(ABC):
    """Abstract base class for data workflows."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the workflow."""
        pass

    @abstractmethod
    def get_flow_config(self) -> Dict[str, Any]:
        """Get Prefect flow configuration."""
        pass


@task(retries=3, retry_delay_seconds=60)
async def validate_task_parameters(task: DataIngestionTask) -> bool:
    """Validate ingestion task parameters."""
    try:
        # Basic validation
        if not task.symbols:
            raise ValueError("No symbols provided")

        if task.start_date and task.end_date:
            if task.start_date >= task.end_date:
                raise ValueError("Start date must be before end date")

        # Future: Add exchange-specific validation
        return True

    except Exception as e:
        logger.error(f"Task validation failed: {e}")
        raise


@task(retries=3, retry_delay_seconds=60)
async def create_metadata_record(task: DataIngestionTask) -> IngestionMetadata:
    """Create initial metadata record for tracking."""
    return IngestionMetadata(
        task_id=f"{task.exchange}_{task.data_type}_{int(datetime.now().timestamp())}",
        status="started",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@task(retries=3, retry_delay_seconds=60)
async def update_metadata_record(
    metadata: IngestionMetadata, status: str, **updates
) -> IngestionMetadata:
    """Update metadata record with progress."""
    metadata.status = status
    metadata.updated_at = datetime.now()

    for key, value in updates.items():
        if hasattr(metadata, key):
            setattr(metadata, key, value)

    return metadata


@task(retries=2, retry_delay_seconds=30)
async def cleanup_temp_files(file_paths: List[str]) -> bool:
    """Clean up temporary files after processing."""
    import os

    try:
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up temporary file: {file_path}")
        return True
    except Exception as e:
        logger.warning(f"Failed to cleanup some temporary files: {e}")
        return False


@task(retries=3, retry_delay_seconds=60)
async def send_notification(
    message: str, level: str = "info", webhook_url: Optional[str] = None
) -> bool:
    """Send workflow status notification."""
    try:
        if webhook_url:
            # Future: Implement webhook notification
            pass

        logger.log(getattr(logging, level.upper()), f"Workflow notification: {message}")
        return True

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


class WorkflowRegistry:
    """Registry for managing available workflows."""

    _workflows: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register workflow classes."""

        def decorator(workflow_class):
            cls._workflows[name] = workflow_class
            return workflow_class

        return decorator

    @classmethod
    def get_workflow(cls, name: str, settings: Settings) -> BaseWorkflow:
        """Get workflow instance by name."""
        if name not in cls._workflows:
            raise ValueError(f"Unknown workflow: {name}")

        return cls._workflows[name](settings)

    @classmethod
    def list_workflows(cls) -> List[str]:
        """List all registered workflows."""
        return list(cls._workflows.keys())
