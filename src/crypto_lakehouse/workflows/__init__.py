"""
Workflow implementations for the crypto lakehouse platform.

This module contains concrete workflow implementations that extend the base
framework to provide specific data collection and processing capabilities.
"""

from .archive_collection import ArchiveCollectionWorkflow

__all__ = [
    "ArchiveCollectionWorkflow"
]