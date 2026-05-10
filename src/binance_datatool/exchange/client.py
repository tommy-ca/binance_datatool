"""Protocol defining the ExchangeClient interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ExchangeClient(Protocol):
    """Protocol for exchange clients that provide OHLCV data."""

    @property
    def exchange_id(self) -> str:
        """Human-readable exchange identifier."""
        ...

    @property
    def trade_type(self):
        """Return the market segment this client is configured for."""
        ...

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list:
        """Fetch historical OHLCV data.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            interval: Kline interval (e.g. "1h", "1d").
            since: Start time in milliseconds.
            until: End time in milliseconds.
            limit: Maximum number of candles to return.

        Returns:
            List of OHLCV data (format depends on implementation).
        """
        ...

    async def fetch_agg_trades(
        self,
        symbol: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list:
        """Fetch historical aggregated trades.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            since: Start time in milliseconds.
            until: End time in milliseconds.
            limit: Maximum number of records to return.

        Returns:
            List of aggregated trade records.
        """
        ...

    async def fetch_funding_rate(
        self,
        symbol: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list:
        """Fetch historical funding rate data (futures only).

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            since: Start time in milliseconds.
            until: End time in milliseconds.
            limit: Maximum number of records to return.

        Returns:
            List of funding rate records.
        """
        ...

    async def stream_ohlcv(
        self,
        symbol: str,
        interval: str,
    ):
        """Stream real-time OHLCV data.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            interval: Kline interval (e.g. "1h", "1d").

        Yields:
            OHLCV data (format depends on implementation).
        """
        ...

    async def close(self) -> None:
        """Release resources held by the client."""
        ...
