"""Base storage interface for the data lakehouse."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
from pathlib import Path
import polars as pl

from ..core.models import DataZone, DataType, TradeType, Exchange


class BaseStorage(ABC):
    """Abstract base class for data lakehouse storage."""
    
    @abstractmethod
    async def write_data(
        self,
        data: pl.DataFrame,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: str,
        partition_date: datetime,
        **kwargs
    ) -> str:
        """Write data to the lakehouse."""
        pass
    
    @abstractmethod
    async def read_data(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbols: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> pl.DataFrame:
        """Read data from the lakehouse."""
        pass
    
    @abstractmethod
    async def list_partitions(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available data partitions."""
        pass
    
    @abstractmethod
    async def delete_partition(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: str,
        partition_date: datetime
    ) -> bool:
        """Delete a specific data partition."""
        pass
    
    @abstractmethod
    async def get_schema(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType
    ) -> Optional[pl.Schema]:
        """Get the schema for a data type."""
        pass
    
    @abstractmethod
    async def optimize_partitions(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Optimize storage partitions (compaction, etc.)."""
        pass
    
    def get_partition_path(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: str,
        partition_date: datetime
    ) -> str:
        """Generate partition path following lakehouse conventions."""
        year = partition_date.year
        month = f"{partition_date.month:02d}"
        day = f"{partition_date.day:02d}"
        
        return f"{zone.value}/{exchange.value}/{trade_type.value}/{data_type.value}/symbol={symbol}/year={year}/month={month}/day={day}"
    
    def get_table_path(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType
    ) -> str:
        """Generate table path for data catalog registration."""
        return f"{zone.value}/{exchange.value}/{trade_type.value}/{data_type.value}"


class DataLakeMetadata(ABC):
    """Abstract interface for data lake metadata management."""
    
    @abstractmethod
    async def register_table(
        self,
        database: str,
        table_name: str,
        schema: pl.Schema,
        location: str,
        partition_columns: List[str],
        **kwargs
    ) -> bool:
        """Register table in data catalog."""
        pass
    
    @abstractmethod
    async def update_partitions(
        self,
        database: str,
        table_name: str,
        partitions: List[Dict[str, Any]]
    ) -> bool:
        """Update partition metadata."""
        pass
    
    @abstractmethod
    async def get_table_info(
        self,
        database: str,
        table_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get table metadata information."""
        pass
    
    @abstractmethod
    async def list_tables(
        self,
        database: str,
        pattern: Optional[str] = None
    ) -> List[str]:
        """List tables in database."""
        pass