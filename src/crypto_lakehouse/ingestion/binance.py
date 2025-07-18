"""Binance data ingestion implementation."""

import aiohttp
import asyncio
from typing import List, Optional, AsyncGenerator, Dict, Any
from datetime import datetime, timezone
import logging
from decimal import Decimal
import gzip
from pathlib import Path

from .base import BaseIngestor, BulkIngestor, IncrementalIngestor
from ..core.models import (
    DataType, TradeType, Interval, ContractType,
    KlineData, FundingRateData, LiquidationData
)
from ..core.config import Settings

logger = logging.getLogger(__name__)


class BinanceIngestor(BaseIngestor):
    """Main Binance data ingestor that combines bulk and incremental ingestion."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.bulk_ingestor = BinanceBulkIngestor(settings)
        self.incremental_ingestor = BinanceIncrementalIngestor(settings)
        self.binance_config = settings.binance
    
    async def get_available_symbols(
        self, 
        trade_type: TradeType, 
        **kwargs
    ) -> List[str]:
        """Get available symbols from Binance."""
        return await self.incremental_ingestor.get_available_symbols(trade_type, **kwargs)
    
    async def ingest_klines(
        self,
        symbols: List[str],
        interval: Interval,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-line data using bulk and incremental methods."""
        
        # Use bulk ingestion for historical data (older than 30 days)
        bulk_cutoff = datetime.now(timezone.utc).replace(day=1)  # Start of current month
        
        if start_date and start_date < bulk_cutoff:
            # Bulk ingestion for historical data
            bulk_end = min(end_date or bulk_cutoff, bulk_cutoff)
            
            async for kline in self.bulk_ingestor.ingest_klines(
                symbols, interval, trade_type, start_date, bulk_end, **kwargs
            ):
                yield kline
        
        # Use incremental ingestion for recent data
        if not end_date or end_date > bulk_cutoff:
            incremental_start = max(start_date or bulk_cutoff, bulk_cutoff)
            
            async for kline in self.incremental_ingestor.ingest_klines(
                symbols, interval, trade_type, incremental_start, end_date, **kwargs
            ):
                yield kline
    
    async def ingest_funding_rates(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[FundingRateData, None]:
        """Ingest funding rate data."""
        if trade_type == TradeType.SPOT:
            raise ValueError("Funding rates not available for spot trading")
        
        # Similar hybrid approach for funding rates
        bulk_cutoff = datetime.now(timezone.utc).replace(day=1)
        
        if start_date and start_date < bulk_cutoff:
            bulk_end = min(end_date or bulk_cutoff, bulk_cutoff)
            
            async for funding in self.bulk_ingestor.ingest_funding_rates(
                symbols, trade_type, start_date, bulk_end, **kwargs
            ):
                yield funding
        
        if not end_date or end_date > bulk_cutoff:
            incremental_start = max(start_date or bulk_cutoff, bulk_cutoff)
            
            async for funding in self.incremental_ingestor.ingest_funding_rates(
                symbols, trade_type, incremental_start, end_date, **kwargs
            ):
                yield funding
    
    async def ingest_liquidations(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[LiquidationData, None]:
        """Ingest liquidation data."""
        if trade_type == TradeType.SPOT:
            raise ValueError("Liquidations not available for spot trading")
        
        # Liquidations are only available via bulk ingestion
        async for liquidation in self.bulk_ingestor.ingest_liquidations(
            symbols, trade_type, start_date, end_date, **kwargs
        ):
            yield liquidation


class BinanceBulkIngestor(BulkIngestor):
    """Binance bulk data ingestion from AWS S3 archives."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.base_url = settings.binance.aws_base_url
    
    async def get_available_symbols(
        self, 
        trade_type: TradeType, 
        **kwargs
    ) -> List[str]:
        """Get symbols from exchange info API."""
        try:
            async with aiohttp.ClientSession() as session:
                if trade_type == TradeType.SPOT:
                    url = f"{self.settings.binance.api_base_url}/api/v3/exchangeInfo"
                elif trade_type == TradeType.UM_FUTURES:
                    url = f"{self.settings.binance.api_base_url}/fapi/v1/exchangeInfo"
                elif trade_type == TradeType.CM_FUTURES:
                    url = f"{self.settings.binance.api_base_url}/dapi/v1/exchangeInfo"
                else:
                    raise ValueError(f"Unknown trade type: {trade_type}")
                
                async with session.get(url) as response:
                    data = await response.json()
                    
                    symbols = []
                    for symbol_info in data.get('symbols', []):
                        if symbol_info.get('status') == 'TRADING':
                            symbols.append(symbol_info['symbol'])
                    
                    return symbols
        
        except Exception as e:
            logger.error(f"Failed to fetch available symbols: {e}")
            return []
    
    async def list_available_files(
        self,
        symbol: str,
        data_type: DataType,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[str]:
        """List available files in Binance S3."""
        try:
            # Build URL pattern based on data type and trade type
            if data_type == DataType.KLINES:
                if trade_type == TradeType.SPOT:
                    base_path = f"data/spot/daily/klines/{symbol}/1m"
                elif trade_type == TradeType.UM_FUTURES:
                    base_path = f"data/futures/um/daily/klines/{symbol}/1m"
                elif trade_type == TradeType.CM_FUTURES:
                    base_path = f"data/futures/cm/daily/klines/{symbol}/1m"
            elif data_type == DataType.FUNDING_RATES:
                if trade_type == TradeType.UM_FUTURES:
                    base_path = f"data/futures/um/daily/fundingRate/{symbol}"
                elif trade_type == TradeType.CM_FUTURES:
                    base_path = f"data/futures/cm/daily/fundingRate/{symbol}"
            elif data_type == DataType.LIQUIDATIONS:
                if trade_type == TradeType.UM_FUTURES:
                    base_path = f"data/futures/um/daily/liquidationSnapshot/{symbol}"
                elif trade_type == TradeType.CM_FUTURES:
                    base_path = f"data/futures/cm/daily/liquidationSnapshot/{symbol}"
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
            
            # Generate date range
            files = []
            current_date = start_date or datetime(2017, 8, 17)  # Binance start date
            end = end_date or datetime.now()
            
            while current_date <= end:
                date_str = current_date.strftime("%Y-%m-%d")
                file_url = f"{self.base_url}/{base_path}/{symbol}-1m-{date_str}.zip"
                files.append(file_url)
                current_date += timedelta(days=1)
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list available files: {e}")
            return []
    
    async def download_file(self, file_url: str, local_path: str) -> bool:
        """Download file from Binance S3."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(local_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        logger.info(f"Downloaded {file_url} to {local_path}")
                        return True
                    else:
                        logger.warning(f"File not found: {file_url} (status: {response.status})")
                        return False
        
        except Exception as e:
            logger.error(f"Failed to download {file_url}: {e}")
            return False
    
    async def ingest_klines(
        self,
        symbols: List[str],
        interval: Interval,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-line data from bulk files."""
        for symbol in symbols:
            files = await self.list_available_files(
                symbol, DataType.KLINES, trade_type, start_date, end_date
            )
            
            for file_url in files:
                try:
                    # Download and parse file
                    async for kline in self._parse_kline_file(file_url, symbol):
                        yield kline
                        
                except Exception as e:
                    logger.error(f"Failed to process file {file_url}: {e}")
    
    async def ingest_funding_rates(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[FundingRateData, None]:
        """Ingest funding rate data from bulk files."""
        for symbol in symbols:
            files = await self.list_available_files(
                symbol, DataType.FUNDING_RATES, trade_type, start_date, end_date
            )
            
            for file_url in files:
                try:
                    async for funding in self._parse_funding_file(file_url, symbol):
                        yield funding
                        
                except Exception as e:
                    logger.error(f"Failed to process file {file_url}: {e}")
    
    async def ingest_liquidations(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[LiquidationData, None]:
        """Ingest liquidation data from bulk files."""
        for symbol in symbols:
            files = await self.list_available_files(
                symbol, DataType.LIQUIDATIONS, trade_type, start_date, end_date
            )
            
            for file_url in files:
                try:
                    async for liquidation in self._parse_liquidation_file(file_url, symbol):
                        yield liquidation
                        
                except Exception as e:
                    logger.error(f"Failed to process file {file_url}: {e}")
    
    async def _parse_kline_file(self, file_url: str, symbol: str) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from CSV file."""
        # Implementation would download, extract, and parse CSV data
        # For now, return empty generator
        return
        yield  # Make this a generator
    
    async def _parse_funding_file(self, file_url: str, symbol: str) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from CSV file."""
        return
        yield
    
    async def _parse_liquidation_file(self, file_url: str, symbol: str) -> AsyncGenerator[LiquidationData, None]:
        """Parse liquidation data from CSV file."""
        return
        yield


class BinanceIncrementalIngestor(IncrementalIngestor):
    """Binance incremental data ingestion via REST API."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_base = settings.binance.api_base_url
        self.rate_limit = settings.binance.rate_limit_requests_per_minute
    
    async def get_available_symbols(
        self, 
        trade_type: TradeType, 
        **kwargs
    ) -> List[str]:
        """Get symbols via API."""
        # Reuse bulk ingestor implementation
        bulk = BinanceBulkIngestor(self.settings)
        return await bulk.get_available_symbols(trade_type, **kwargs)
    
    async def get_latest_data_timestamp(
        self,
        symbol: str,
        data_type: DataType,
        trade_type: TradeType
    ) -> Optional[datetime]:
        """Get latest available data timestamp."""
        try:
            async with aiohttp.ClientSession() as session:
                if data_type == DataType.KLINES:
                    if trade_type == TradeType.SPOT:
                        url = f"{self.api_base}/api/v3/klines"
                    elif trade_type == TradeType.UM_FUTURES:
                        url = f"{self.api_base}/fapi/v1/klines"
                    elif trade_type == TradeType.CM_FUTURES:
                        url = f"{self.api_base}/dapi/v1/klines"
                    
                    params = {"symbol": symbol, "interval": "1m", "limit": 1}
                    
                    async with session.get(url, params=params) as response:
                        data = await response.json()
                        if data:
                            # Last close time
                            return datetime.fromtimestamp(data[0][6] / 1000, tz=timezone.utc)
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get latest timestamp: {e}")
            return None
    
    async def fetch_recent_data(
        self,
        symbol: str,
        data_type: DataType,
        trade_type: TradeType,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch recent data via API."""
        try:
            async with aiohttp.ClientSession() as session:
                if data_type == DataType.KLINES:
                    return await self._fetch_klines_api(
                        session, symbol, trade_type, since, limit
                    )
                elif data_type == DataType.FUNDING_RATES:
                    return await self._fetch_funding_api(
                        session, symbol, trade_type, since, limit
                    )
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Failed to fetch recent data: {e}")
            return []
    
    async def ingest_klines(
        self,
        symbols: List[str],
        interval: Interval,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-lines via API."""
        for symbol in symbols:
            try:
                data = await self.fetch_recent_data(
                    symbol, DataType.KLINES, trade_type, start_date
                )
                
                for kline_data in data:
                    yield self._parse_kline_data(kline_data, symbol)
                    
            except Exception as e:
                logger.error(f"Failed to ingest klines for {symbol}: {e}")
    
    async def ingest_funding_rates(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[FundingRateData, None]:
        """Ingest funding rates via API."""
        for symbol in symbols:
            try:
                data = await self.fetch_recent_data(
                    symbol, DataType.FUNDING_RATES, trade_type, start_date
                )
                
                for funding_data in data:
                    yield self._parse_funding_data(funding_data, symbol)
                    
            except Exception as e:
                logger.error(f"Failed to ingest funding rates for {symbol}: {e}")
    
    async def ingest_liquidations(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs
    ) -> AsyncGenerator[LiquidationData, None]:
        """Liquidations not available via REST API."""
        return
        yield
    
    async def _fetch_klines_api(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        trade_type: TradeType,
        since: Optional[datetime],
        limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Fetch K-lines from API."""
        if trade_type == TradeType.SPOT:
            url = f"{self.api_base}/api/v3/klines"
        elif trade_type == TradeType.UM_FUTURES:
            url = f"{self.api_base}/fapi/v1/klines"
        elif trade_type == TradeType.CM_FUTURES:
            url = f"{self.api_base}/dapi/v1/klines"
        
        params = {
            "symbol": symbol,
            "interval": "1m",
            "limit": limit or 1000
        }
        
        if since:
            params["startTime"] = int(since.timestamp() * 1000)
        
        async with session.get(url, params=params) as response:
            return await response.json()
    
    async def _fetch_funding_api(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        trade_type: TradeType,
        since: Optional[datetime],
        limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Fetch funding rates from API."""
        if trade_type == TradeType.UM_FUTURES:
            url = f"{self.api_base}/fapi/v1/fundingRate"
        elif trade_type == TradeType.CM_FUTURES:
            url = f"{self.api_base}/dapi/v1/fundingRate"
        else:
            return []
        
        params = {
            "symbol": symbol,
            "limit": limit or 1000
        }
        
        if since:
            params["startTime"] = int(since.timestamp() * 1000)
        
        async with session.get(url, params=params) as response:
            return await response.json()
    
    def _parse_kline_data(self, data: List, symbol: str) -> KlineData:
        """Parse API K-line data to KlineData model."""
        return KlineData(
            symbol=symbol,
            open_time=datetime.fromtimestamp(data[0] / 1000, tz=timezone.utc),
            close_time=datetime.fromtimestamp(data[6] / 1000, tz=timezone.utc),
            open_price=Decimal(data[1]),
            high_price=Decimal(data[2]),
            low_price=Decimal(data[3]),
            close_price=Decimal(data[4]),
            volume=Decimal(data[5]),
            quote_asset_volume=Decimal(data[7]),
            number_of_trades=int(data[8]),
            taker_buy_base_asset_volume=Decimal(data[9]),
            taker_buy_quote_asset_volume=Decimal(data[10])
        )
    
    def _parse_funding_data(self, data: Dict, symbol: str) -> FundingRateData:
        """Parse API funding rate data to FundingRateData model."""
        return FundingRateData(
            symbol=symbol,
            funding_time=datetime.fromtimestamp(data['fundingTime'] / 1000, tz=timezone.utc),
            funding_rate=Decimal(data['fundingRate']),
            mark_price=Decimal(data.get('markPrice', 0))
        )