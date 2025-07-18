"""Storage factory for creating storage implementations."""

from typing import Union
from ..core.config import Settings
from .base import BaseStorage
from .s3_storage import S3Storage
from .local_storage import LocalStorage


def create_storage(settings: Settings) -> BaseStorage:
    """Create appropriate storage implementation based on configuration."""
    
    if settings.is_cloud_enabled:
        # Use S3 storage for cloud deployments
        return S3Storage(settings)
    else:
        # Use local storage for development
        return LocalStorage(settings)


def create_s3_storage(settings: Settings) -> S3Storage:
    """Create S3 storage implementation."""
    return S3Storage(settings)


def create_local_storage(settings: Settings) -> LocalStorage:
    """Create local storage implementation.""" 
    return LocalStorage(settings)