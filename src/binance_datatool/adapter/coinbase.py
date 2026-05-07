"""Skeleton adapter for Coinbase exchange data.

This adapter demonstrates extensibility via the DataSourceAdapter protocol.
It would connect to Coinbase's REST API for symbol discovery and file listing.

Note: This is a skeleton implementation for demonstration purposes.
A production implementation would require Coinbase API authentication
and error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import FileMetadata

if TYPE_CHECKING:
    pass


class CoinbaseAdapter:
    """Skeleton adapter for Coinbase exchange data.

    Demonstrates how to implement the DataSourceAdapter protocol for
    a different data source. A production implementation would:
    - Authenticate with Coinbase API
    - Fetch product list (symbols)
    - Download historical data via their API
    - Parse product metadata
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        api_passphrase: str | None = None,
    ) -> None:
        """Initialize CoinbaseAdapter.

        Args:
            api_key: Coinbase API key.
            api_secret: Coinbase API secret.
            api_passphrase: Coinbase API passphrase.

        Note:
            In production, use environment variables for credentials.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    @property
    def source_name(self) -> str:
        """Return the source identifier."""
        return "coinbase"

    async def list_symbols(
        self, market_type: str, partition: str, data_type: str
    ) -> list[str]:
        """List available symbols from Coinbase.

        Args:
            market_type: Market segment ("spot", "futures").
            partition: Partition frequency ("daily", "monthly").
            data_type: Dataset type ("klines", "trades", etc.).

        Returns:
            List of product IDs (e.g., ["BTC-USD", "ETH-USD"]).

        Raises:
            NotImplementedError: Skeleton adapter does not implement this.
            ValueError: If parameters are invalid.
        """
        raise NotImplementedError(
            "CoinbaseAdapter.list_symbols requires Coinbase API integration"
        )

    async def list_files(
        self,
        market_type: str,
        partition: str,
        data_type: str,
        symbol: str,
        interval: str | None = None,
    ) -> list[FileMetadata]:
        """List files available for one product.

        Args:
            market_type: Market segment.
            partition: Partition frequency.
            data_type: Dataset type.
            symbol: Product ID (e.g., "BTC-USD").
            interval: Time interval (optional).

        Returns:
            List of available files for the product.

        Raises:
            NotImplementedError: Skeleton adapter does not implement this.
        """
        raise NotImplementedError(
            "CoinbaseAdapter.list_files requires Coinbase API integration"
        )

    async def fetch_file(self, url: str, destination_path: str) -> None:
        """Fetch a single file and write it to destination_path.

        Args:
            url: URL to fetch from.
            destination_path: Local path where file should be written.

        Raises:
            NotImplementedError: Skeleton adapter does not implement this.
        """
        raise NotImplementedError(
            "CoinbaseAdapter.fetch_file requires Coinbase API integration"
        )

    def parse_symbol(self, raw_symbol: str) -> dict | None:
        """Parse Coinbase product ID into metadata dict.

        Coinbase uses the format BASE-QUOTE (e.g., BTC-USD, ETH-USDC).

        Args:
            raw_symbol: Product ID (e.g., "BTC-USD").

        Returns:
            Dict with "symbol", "base_asset", "quote_asset", or None.
        """
        # Coinbase uses dash-separated format
        if "-" not in raw_symbol:
            return None

        parts = raw_symbol.split("-")
        if len(parts) != 2:
            return None

        base, quote = parts
        if not base or not quote:
            return None

        return {
            "symbol": raw_symbol,
            "base_asset": base,
            "quote_asset": quote,
        }


__all__ = ["CoinbaseAdapter"]
