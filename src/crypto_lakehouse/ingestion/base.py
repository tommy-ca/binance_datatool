"""Base classes for data ingestion."""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.config import Settings
from ..core.models import (
    DataIngestionTask,
    DataType,
    FundingRateData,
    Interval,
    KlineData,
    LiquidationData,
    TradeType,
)

logger = logging.getLogger(__name__)


class BaseIngestor(ABC):
    """Abstract base class for data ingestors."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def get_available_symbols(self, trade_type: TradeType, **kwargs) -> List[str]:
        """Get list of available trading symbols."""
        pass

    @abstractmethod
    async def ingest_klines(
        self,
        symbols: List[str],
        interval: Interval,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-line data."""
        pass

    @abstractmethod
    async def ingest_funding_rates(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[FundingRateData, None]:
        """Ingest funding rate data."""
        pass

    @abstractmethod
    async def ingest_liquidations(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[LiquidationData, None]:
        """Ingest liquidation data."""
        pass

    async def validate_task(self, task: DataIngestionTask) -> bool:
        """Validate ingestion task parameters."""
        try:
            # Check if symbols are available
            available_symbols = await self.get_available_symbols(task.trade_type)

            invalid_symbols = set(task.symbols) - set(available_symbols)
            if invalid_symbols:
                self.logger.warning(f"Invalid symbols: {invalid_symbols}")
                return False

            # Validate date range
            if task.start_date and task.end_date:
                if task.start_date >= task.end_date:
                    self.logger.error("Start date must be before end date")
                    return False

            # Data type specific validations
            if task.data_type == DataType.KLINES and not task.interval:
                self.logger.error("Interval required for K-line data")
                return False

            if task.data_type == DataType.FUNDING_RATES and task.trade_type == TradeType.SPOT:
                self.logger.error("Funding rates not available for spot trading")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Task validation failed: {e}")
            return False

    async def get_data_availability(
        self, symbol: str, data_type: DataType, trade_type: TradeType
    ) -> Dict[str, Any]:
        """Get data availability information for a symbol."""
        return {
            "symbol": symbol,
            "data_type": data_type,
            "trade_type": trade_type,
            "available": True,  # Override in subclasses
            "start_date": None,
            "end_date": None,
            "intervals": [],
        }


class BulkIngestor(BaseIngestor):
    """Base class for bulk data ingestion (e.g., from S3 archives)."""

    @abstractmethod
    async def list_available_files(
        self,
        symbol: str,
        data_type: DataType,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[str]:
        """List available data files for bulk ingestion."""
        pass

    @abstractmethod
    async def download_file(self, file_url: str, local_path: str) -> bool:
        """Download a single data file."""
        pass


class IncrementalIngestor(BaseIngestor):
    """Base class for incremental data ingestion (e.g., REST APIs)."""

    @abstractmethod
    async def get_latest_data_timestamp(
        self, symbol: str, data_type: DataType, trade_type: TradeType
    ) -> Optional[datetime]:
        """Get timestamp of latest available data."""
        pass

    @abstractmethod
    async def fetch_recent_data(
        self,
        symbol: str,
        data_type: DataType,
        trade_type: TradeType,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent data via API."""
        pass
