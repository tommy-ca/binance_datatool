"""Binance data ingestion implementation with s5cmd and ccxt integration."""

import logging
import tempfile
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import ccxt.pro as ccxt

from ..core.config import Settings
from ..core.models import (
    DataType,
    FundingRateData,
    Interval,
    KlineData,
    LiquidationData,
    TradeType,
)
from .base import BaseIngestor, BulkIngestor, IncrementalIngestor
from .bulk_downloader import BinanceDataParser, S5cmdDownloader

logger = logging.getLogger(__name__)


class BinanceIngestor(BaseIngestor):
    """Main Binance data ingestor that combines bulk and incremental ingestion."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.bulk_ingestor = BinanceBulkIngestor(settings)
        self.incremental_ingestor = BinanceIncrementalIngestor(settings)
        self.binance_config = settings.binance

    async def get_available_symbols(self, trade_type: TradeType, **kwargs) -> List[str]:
        """Get available symbols from Binance."""
        return await self.incremental_ingestor.get_available_symbols(trade_type, **kwargs)

    async def ingest_klines(
        self,
        symbols: List[str],
        interval: Interval,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-line data using bulk and incremental methods."""

        # Use bulk ingestion for historical data (older than 30 days)
        bulk_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        if start_date and start_date < bulk_cutoff:
            # Bulk ingestion for historical data
            bulk_end = min(end_date or bulk_cutoff, bulk_cutoff)

            logger.info(f"Using bulk ingestion for {start_date} to {bulk_end}")
            async for kline in self.bulk_ingestor.ingest_klines(
                symbols, interval, trade_type, start_date, bulk_end, **kwargs
            ):
                yield kline

        # Use incremental ingestion for recent data
        if not end_date or end_date > bulk_cutoff:
            incremental_start = max(start_date or bulk_cutoff, bulk_cutoff)

            logger.info(
                f"Using incremental ingestion for {incremental_start} to {end_date or 'now'}"
            )
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
        **kwargs,
    ) -> AsyncGenerator[FundingRateData, None]:
        """Ingest funding rate data."""
        if trade_type == TradeType.SPOT:
            raise ValueError("Funding rates not available for spot trading")

        # Similar hybrid approach for funding rates
        bulk_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

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
        **kwargs,
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
    """Binance bulk data ingestion from AWS S3 archives using s5cmd."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.base_url = settings.binance.aws_base_url
        self.downloader = S5cmdDownloader(settings)
        self.parser = BinanceDataParser(settings)

    async def get_available_symbols(self, trade_type: TradeType, **kwargs) -> List[str]:
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
                    for symbol_info in data.get("symbols", []):
                        if symbol_info.get("status") == "TRADING":
                            symbols.append(symbol_info["symbol"])

                    logger.info(f"Found {len(symbols)} active symbols for {trade_type}")
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
        end_date: Optional[datetime] = None,
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

                if data_type == DataType.KLINES:
                    file_url = f"{self.base_url}/{base_path}/{symbol}-1m-{date_str}.zip"
                elif data_type == DataType.FUNDING_RATES:
                    file_url = f"{self.base_url}/{base_path}/{symbol}-fundingRate-{date_str}.zip"
                elif data_type == DataType.LIQUIDATIONS:
                    file_url = (
                        f"{self.base_url}/{base_path}/{symbol}-liquidationSnapshot-{date_str}.zip"
                    )

                files.append(file_url)
                current_date += timedelta(days=1)

            logger.info(f"Generated {len(files)} file URLs for {symbol} {data_type}")
            return files

        except Exception as e:
            logger.error(f"Failed to list available files: {e}")
            return []

    async def download_file(self, file_url: str, local_path: str) -> bool:
        """Download file from Binance S3."""
        try:
            local_dir = Path(local_path).parent
            files = await self.downloader.download_files_bulk([file_url], local_dir)
            return len(files) > 0
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
        **kwargs,
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-line data from bulk files using s5cmd."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for symbol in symbols:
                try:
                    # Get list of files to download
                    file_urls = await self.list_available_files(
                        symbol, DataType.KLINES, trade_type, start_date, end_date
                    )

                    if not file_urls:
                        logger.warning(f"No files found for {symbol}")
                        continue

                    # Download files in bulk
                    logger.info(f"Downloading {len(file_urls)} files for {symbol}")
                    downloaded_files = await self.downloader.download_files_bulk(
                        file_urls, temp_path, max_concurrent=10
                    )

                    # Parse each downloaded file
                    for file_path in downloaded_files:
                        logger.info(f"Parsing file: {file_path}")
                        async for kline in self.parser.parse_kline_file(file_path, symbol):
                            yield kline

                except Exception as e:
                    logger.error(f"Failed to ingest klines for {symbol}: {e}")

    async def ingest_funding_rates(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[FundingRateData, None]:
        """Ingest funding rate data from bulk files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            for symbol in symbols:
                try:
                    file_urls = await self.list_available_files(
                        symbol, DataType.FUNDING_RATES, trade_type, start_date, end_date
                    )

                    if not file_urls:
                        continue

                    downloaded_files = await self.downloader.download_files_bulk(
                        file_urls, temp_path, max_concurrent=10
                    )

                    for file_path in downloaded_files:
                        async for funding in self.parser.parse_funding_file(file_path, symbol):
                            yield funding

                except Exception as e:
                    logger.error(f"Failed to ingest funding rates for {symbol}: {e}")

    async def ingest_liquidations(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[LiquidationData, None]:
        """Ingest liquidation data from bulk files."""
        # Placeholder - liquidation parsing would be similar to funding rates
        return
        yield


class BinanceIncrementalIngestor(IncrementalIngestor):
    """Binance incremental data ingestion via ccxt unified API."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.api_base = settings.binance.api_base_url
        self.rate_limit = settings.binance.rate_limit_requests_per_minute
        self._exchange = None

    async def _get_exchange(self) -> ccxt.binance:
        """Get or create ccxt exchange instance."""
        if self._exchange is None:
            config = {
                "apiKey": self.settings.binance.api_key,
                "secret": self.settings.binance.api_secret,
                "timeout": 30000,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},  # Will be overridden as needed
            }

            if self.settings.binance.api_key and self.settings.binance.api_secret:
                self._exchange = ccxt.binance(config)
            else:
                # Use public API only
                self._exchange = ccxt.binance({"enableRateLimit": True})

        return self._exchange

    async def get_available_symbols(self, trade_type: TradeType, **kwargs) -> List[str]:
        """Get symbols via ccxt unified API."""
        try:
            exchange = await self._get_exchange()

            # Set market type
            if trade_type == TradeType.SPOT:
                exchange.options["defaultType"] = "spot"
            elif trade_type == TradeType.UM_FUTURES:
                exchange.options["defaultType"] = "future"
            elif trade_type == TradeType.CM_FUTURES:
                exchange.options["defaultType"] = "delivery"

            # Load markets
            markets = await exchange.load_markets()

            # Filter active symbols
            symbols = [symbol for symbol, market in markets.items() if market.get("active", True)]

            logger.info(f"Found {len(symbols)} active symbols via ccxt")
            return symbols

        except Exception as e:
            logger.error(f"Failed to get symbols via ccxt: {e}")
            return []

    async def get_latest_data_timestamp(
        self, symbol: str, data_type: DataType, trade_type: TradeType
    ) -> Optional[datetime]:
        """Get latest available data timestamp."""
        try:
            exchange = await self._get_exchange()

            if data_type == DataType.KLINES:
                # Get latest kline
                ohlcvs = await exchange.fetch_ohlcv(symbol, "1m", limit=1)
                if ohlcvs:
                    return datetime.fromtimestamp(ohlcvs[0][0] / 1000, tz=timezone.utc)

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
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch recent data via ccxt unified API."""
        try:
            exchange = await self._get_exchange()

            if data_type == DataType.KLINES:
                since_ts = int(since.timestamp() * 1000) if since else None
                ohlcvs = await exchange.fetch_ohlcv(
                    symbol, "1m", since=since_ts, limit=limit or 1000
                )
                return ohlcvs
            elif data_type == DataType.FUNDING_RATES:
                # ccxt doesn't have unified funding rate endpoint
                # Fall back to direct API call
                return await self._fetch_funding_api_direct(symbol, since, limit)
            else:
                return []

        except Exception as e:
            logger.error(f"Failed to fetch recent data via ccxt: {e}")
            return []

    async def _fetch_funding_api_direct(
        self, symbol: str, since: Optional[datetime], limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Fetch funding rates using direct API call."""
        try:
            url = f"{self.api_base}/fapi/v1/fundingRate"
            params = {"symbol": symbol, "limit": limit or 1000}

            if since:
                params["startTime"] = int(since.timestamp() * 1000)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    return await response.json()

        except Exception as e:
            logger.error(f"Failed to fetch funding rates directly: {e}")
            return []

    async def ingest_klines(
        self,
        symbols: List[str],
        interval: Interval,
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> AsyncGenerator[KlineData, None]:
        """Ingest K-lines via ccxt unified API."""
        for symbol in symbols:
            try:
                data = await self.fetch_recent_data(
                    symbol, DataType.KLINES, trade_type, start_date, 1000
                )

                for ohlcv in data:
                    yield self._parse_ohlcv_data(ohlcv, symbol)

            except Exception as e:
                logger.error(f"Failed to ingest klines for {symbol}: {e}")

    async def ingest_funding_rates(
        self,
        symbols: List[str],
        trade_type: TradeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
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
        **kwargs,
    ) -> AsyncGenerator[LiquidationData, None]:
        """Liquidations not available via REST API."""
        return
        yield

    def _parse_ohlcv_data(self, ohlcv: List, symbol: str) -> KlineData:
        """Parse ccxt OHLCV data to KlineData model."""
        # ccxt OHLCV format: [timestamp, open, high, low, close, volume]
        timestamp = ohlcv[0] / 1000

        return KlineData(
            symbol=symbol,
            open_time=datetime.fromtimestamp(timestamp, tz=timezone.utc),
            close_time=datetime.fromtimestamp(timestamp + 60, tz=timezone.utc),  # 1m later
            open_price=Decimal(str(ohlcv[1])),
            high_price=Decimal(str(ohlcv[2])),
            low_price=Decimal(str(ohlcv[3])),
            close_price=Decimal(str(ohlcv[4])),
            volume=Decimal(str(ohlcv[5])),
            quote_asset_volume=Decimal("0"),  # Not available in basic OHLCV
            number_of_trades=0,  # Not available in basic OHLCV
            taker_buy_base_asset_volume=Decimal("0"),
            taker_buy_quote_asset_volume=Decimal("0"),
        )

    def _parse_funding_data(self, data: Dict, symbol: str) -> FundingRateData:
        """Parse API funding rate data to FundingRateData model."""
        return FundingRateData(
            symbol=symbol,
            funding_time=datetime.fromtimestamp(data["fundingTime"] / 1000, tz=timezone.utc),
            funding_rate=Decimal(data["fundingRate"]),
            mark_price=Decimal(data.get("markPrice", 0)),
        )
