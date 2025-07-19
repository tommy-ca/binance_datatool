"""Data models for crypto lakehouse workflows."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class ArchiveMetadata:
    """Metadata for archive data files."""
    symbol: str
    market: str
    data_type: str
    interval: Optional[str]
    date: str
    file_size: int
    checksum: Optional[str] = None


@dataclass 
class CollectionResult:
    """Result of a data collection operation."""
    success: bool
    files_collected: int
    total_size: int
    errors: list
    metadata: Dict[str, Any]