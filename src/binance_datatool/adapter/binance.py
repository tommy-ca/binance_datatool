"""Adapter for Binance data archive via data.binance.vision S3 API.

This adapter wraps the ArchiveClient to provide the DataSourceAdapter protocol
interface. It enables integration with the multi-source pipeline framework while
preserving the existing ArchiveClient implementation.

Example:
    ```python
    adapter = BinanceAdapter()
    symbols = await adapter.list_symbols(
        market_type="spot",
        partition="daily",
        data_type="klines"
    )
    ```
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import aiohttp

from binance_datatool.archive.client import ArchiveClient, ArchiveFile
from binance_datatool.common.enums import DataFrequency, DataType, TradeType

from . import FileMetadata

if TYPE_CHECKING:
    pass


class BinanceAdapter:
    """Adapter for Binance data.binance.vision S3 archive.

    Wraps ArchiveClient to provide the DataSourceAdapter protocol interface,
    enabling integration with multi-source data pipelines.
    """

    def __init__(
        self,
        timeout_seconds: int | float = 30,
        trust_env: bool = True,
    ) -> None:
        """Initialize BinanceAdapter.

        Args:
            timeout_seconds: HTTP timeout for S3 requests.
            trust_env: Honor HTTP proxy environment variables.
        """
        self._client = ArchiveClient(
            timeout_seconds=timeout_seconds, trust_env=trust_env
        )

    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return "binance"

    async def list_symbols(
        self, market_type: str, partition: str, data_type: str
    ) -> list[str]:
        """List available symbols for the requested parameters.

        Args:
            market_type: Market segment ("spot", "um", "cm").
            partition: Partition frequency ("daily", "monthly").
            data_type: Dataset type ("klines", "aggTrades", etc.).

        Returns:
            Sorted list of symbol names (e.g., ["BTCUSDT", "ETHUSDT"]).

        Raises:
            ValueError: If parameters are invalid.
            aiohttp.ClientError: If S3 request fails.
        """
        # Validate and convert market_type
        trade_type = self._validate_market_type(market_type)

        # Validate and convert partition
        data_freq = self._validate_partition(partition)

        # Validate and convert data_type
        data_type_enum = self._validate_data_type(data_type)

        # Call ArchiveClient
        return await self._client.list_symbols(trade_type, data_freq, data_type_enum)

    async def list_files(
        self,
        market_type: str,
        partition: str,
        data_type: str,
        symbol: str,
        interval: str | None = None,
    ) -> list[FileMetadata]:
        """List files available for one symbol.

        Args:
            market_type: Market segment ("spot", "um", "cm").
            partition: Partition frequency ("daily", "monthly").
            data_type: Dataset type ("klines", "aggTrades", etc.).
            symbol: Symbol directory name (e.g., "BTCUSDT").
            interval: Kline interval directory (required for klines, else None).

        Returns:
            List of FileMetadata objects for the symbol.

        Raises:
            ValueError: If parameters are invalid.
            aiohttp.ClientError: If S3 request fails.
        """
        # Validate parameters
        trade_type = self._validate_market_type(market_type)
        data_freq = self._validate_partition(partition)
        data_type_enum = self._validate_data_type(data_type)

        # Call ArchiveClient
        archive_files: list[ArchiveFile] = (
            await self._client.list_symbol_files(
                trade_type=trade_type,
                data_freq=data_freq,
                data_type=data_type_enum,
                symbol=symbol,
                interval=interval,
            )
        )

        # Convert to FileMetadata
        result = []
        for f in archive_files:
            # Build URL from S3 key
            url = f"https://data.binance.vision?key={f.key}"
            metadata = FileMetadata(
                key=f.key,
                url=url,
                size=f.size,
                last_modified=f.last_modified,
                checksum=None,  # Binance archive doesn't provide checksums
            )
            result.append(metadata)

        return result

    async def fetch_file(self, url: str, destination_path: str) -> None:
        """Fetch a single file and write it to destination_path.

        Args:
            url: URL to fetch.
            destination_path: Local path where file should be written.

        Raises:
            aiohttp.ClientError: If request fails.
            IOError: If file write fails.
        """
        timeout = aiohttp.ClientTimeout(total=self._client.timeout_seconds)
        async with aiohttp.ClientSession(
            timeout=timeout, trust_env=self._client.trust_env
        ) as session:
            async with session.get(url) as response:
                response.raise_for_status()

                # Write response to file in chunks
                with open(destination_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

    def parse_symbol(self, raw_symbol: str) -> dict | None:
        """Parse raw symbol string into metadata dict.

        Binance symbols follow the pattern: BASE+QUOTE (e.g., BTCUSDT).
        For common stablecoins and BUSD pairs, this heuristic works well.
        More complex parsing (e.g., separating multi-char base from multi-char quote)
        would require a symbol enumeration or machine learning.

        Args:
            raw_symbol: Raw symbol string (e.g., "BTCUSDT").

        Returns:
            Dict with "symbol", "base_asset", "quote_asset", or None if unparseable.
        """
        # Remove any suffix like _PERP for parsing
        symbol_to_parse = raw_symbol
        suffix = ""
        if "_" in raw_symbol:
            parts = raw_symbol.rsplit("_", 1)
            symbol_to_parse = parts[0]
            suffix = "_" + parts[1]

        # Simple heuristic: assume common quote assets
        common_quotes = [
            "USDT",
            "USDC",
            "BUSD",
            "TUSD",
            "SUSD",
            "DAI",
            "USD",
            "EUR",
            "GBP",
            "JPY",
            "AUD",
            "CAD",
            "BNB",
            "BTC",
            "ETH",
        ]

        # Try to match a quote asset
        for quote in sorted(common_quotes, key=len, reverse=True):
            if symbol_to_parse.endswith(quote):
                base = symbol_to_parse[: -len(quote)]
                if base and len(base) >= 2:  # Base must be at least 2 chars
                    return {
                        "symbol": raw_symbol,
                        "base_asset": base,
                        "quote_asset": quote,
                    }

        # Fallback: assume 3-char base + 4-char quote (common pattern)
        if len(symbol_to_parse) == 7:
            return {
                "symbol": raw_symbol,
                "base_asset": symbol_to_parse[:3],
                "quote_asset": symbol_to_parse[3:],
            }

        # Cannot parse
        return None

    @staticmethod
    def _validate_market_type(market_type: str) -> TradeType:
        """Validate and convert market_type string to TradeType enum.

        Args:
            market_type: Market type string ("spot", "um", "cm").

        Returns:
            TradeType enum value.

        Raises:
            ValueError: If market_type is invalid.
        """
        mapping = {
            "spot": TradeType.spot,
            "um": TradeType.um,
            "cm": TradeType.cm,
        }
        if market_type not in mapping:
            raise ValueError(
                f"Invalid market_type: {market_type}. "
                f"Expected one of: {list(mapping.keys())}"
            )
        return mapping[market_type]

    @staticmethod
    def _validate_partition(partition: str) -> DataFrequency:
        """Validate and convert partition string to DataFrequency enum.

        Args:
            partition: Partition frequency string ("daily", "monthly").

        Returns:
            DataFrequency enum value.

        Raises:
            ValueError: If partition is invalid.
        """
        mapping = {
            "daily": DataFrequency.daily,
            "monthly": DataFrequency.monthly,
        }
        if partition not in mapping:
            raise ValueError(
                f"Invalid partition: {partition}. "
                f"Expected one of: {list(mapping.keys())}"
            )
        return mapping[partition]

    @staticmethod
    def _validate_data_type(data_type: str) -> DataType:
        """Validate and convert data_type string to DataType enum.

        Args:
            data_type: Data type string ("klines", "aggTrades", etc.).

        Returns:
            DataType enum value.

        Raises:
            ValueError: If data_type is invalid.
        """
        # Try direct value match first
        for dt in DataType:
            if dt.value == data_type:
                return dt

        # Try name match (snake_case to enum name)
        for dt in DataType:
            if dt.name == data_type:
                return dt

        raise ValueError(
            f"Invalid data_type: {data_type}. "
            f"Expected one of: {[dt.value for dt in DataType]}"
        )


__all__ = ["BinanceAdapter"]
