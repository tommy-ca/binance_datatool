"""Binance REST API clients implementing the ExchangeClient protocol."""

from __future__ import annotations

import aiohttp

from binance_datatool.common.enums import TradeType
from binance_datatool.common.intervals import VALID_INTERVALS
from binance_datatool.common.types import KlineData

__all__ = ["BinanceSpotRestClient", "BinanceUmRestClient", "BinanceCmRestClient"]

#: Maximum candles per Binance klines request.
_KLINES_LIMIT = 1000

#: Base URLs for each market type.
_BASE_URLS = {
    TradeType.spot: "https://api.binance.com/api/v3",
    TradeType.um: "https://fapi.binance.com/fapi/v1",
    TradeType.cm: "https://dapi.binance.com/dapi/v1",
}

_TESTNET_BASE = "https://testnet.binance.vision/api/v3"


class _BinanceRestClientBase:
    """Base class for Binance REST clients using aiohttp.

    Not intended for direct use — use the market-specific subclasses.
    """

    def __init__(
        self,
        trade_type: TradeType,
        timeout_seconds: int | float = 30,
        trust_env: bool = True,
    ) -> None:
        self._trade_type = trade_type
        self._timeout_seconds = timeout_seconds
        self._trust_env = trust_env
        self._api_base = _BASE_URLS[trade_type]

    @property
    def exchange_id(self) -> str:
        return f"binance_{self._trade_type.value}"

    @property
    def trade_type(self) -> TradeType:
        return self._trade_type

    async def _fetch_page(
        self,
        symbol: str,
        interval: str,
        start_time: int | None,
        end_time: int | None,
        limit: int,
    ) -> list[KlineData]:
        """Fetch a single page of klines from Binance REST API."""
        params: dict[str, str | int] = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
        async with aiohttp.ClientSession(
            timeout=timeout, trust_env=self._trust_env
        ) as session, session.get(
            f"{self._api_base}/klines", params=params
        ) as response:
            response.raise_for_status()
            data = await response.json()

        return [KlineData.from_binance_api(kline) for kline in data]

    async def close(self) -> None:
        """No-op for stateless REST client."""
        return


class BinanceSpotRestClient(_BinanceRestClientBase):
    """Binance Spot market REST client.

    Implements the ExchangeClient protocol for spot trading pairs.
    """

    def __init__(
        self,
        timeout_seconds: int | float = 30,
        trust_env: bool = True,
        testnet: bool = False,
    ) -> None:
        """Initialize spot REST client.

        Args:
            timeout_seconds: HTTP request timeout.
            trust_env: Honour HTTP_PROXY environment variables.
            testnet: Use Binance spot testnet.
        """
        super().__init__(
            trade_type=TradeType.spot,
            timeout_seconds=timeout_seconds,
            trust_env=trust_env,
        )
        if testnet:
            self._api_base = _TESTNET_BASE

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        """Fetch spot klines via REST API with auto-pagination."""
        if interval not in VALID_INTERVALS:
            raise ValueError(
                f"Invalid interval: {interval!r}. "
                f"Expected one of: {VALID_INTERVALS}"
            )

        if limit is not None and limit > _KLINES_LIMIT:
            raise ValueError(f"Limit cannot exceed {_KLINES_LIMIT}")

        # Single request path
        if limit is not None and limit <= _KLINES_LIMIT:
            return await self._fetch_page(symbol, interval, since, until, limit)

        # Auto-pagination path
        all_klines: list[KlineData] = []
        current_start = since

        while True:
            batch = await self._fetch_page(
                symbol, interval, current_start, until, _KLINES_LIMIT
            )
            if not batch:
                break

            all_klines.extend(batch)

            if len(batch) < _KLINES_LIMIT:
                break

            current_start = batch[-1].close_time + 1

            if until is not None and batch[-1].close_time >= until:
                break

        return all_klines

    async def stream_ohlcv(self, symbol: str, interval: str):
        """Not supported over REST — raises NotImplementedError."""
        raise NotImplementedError("Use BinanceSpotWsClient for WebSocket streaming")


class BinanceUmRestClient(_BinanceRestClientBase):
    """Binance USDⓈM futures (UM) REST client.

    Implements the ExchangeClient protocol for USD-M perpetual and
    delivery futures.
    """

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        """Fetch USD-M futures klines via REST API with auto-pagination."""
        if interval not in VALID_INTERVALS:
            raise ValueError(
                f"Invalid interval: {interval!r}. "
                f"Expected one of: {VALID_INTERVALS}"
            )

        if limit is not None and limit > _KLINES_LIMIT:
            raise ValueError(f"Limit cannot exceed {_KLINES_LIMIT}")

        if limit is not None and limit <= _KLINES_LIMIT:
            return await self._fetch_page(symbol, interval, since, until, limit)

        all_klines: list[KlineData] = []
        current_start = since

        while True:
            batch = await self._fetch_page(
                symbol, interval, current_start, until, _KLINES_LIMIT
            )
            if not batch:
                break

            all_klines.extend(batch)

            if len(batch) < _KLINES_LIMIT:
                break

            current_start = batch[-1].close_time + 1

            if until is not None and batch[-1].close_time >= until:
                break

        return all_klines

    async def stream_ohlcv(self, symbol: str, interval: str):
        raise NotImplementedError("Use BinanceUmWsClient for WebSocket streaming")


class BinanceCmRestClient(_BinanceRestClientBase):
    """Binance COINⓈM futures (CM) REST client.

    Implements the ExchangeClient protocol for COIN-M perpetual and
    delivery futures.
    """

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        """Fetch COIN-M futures klines via REST API with auto-pagination."""
        if interval not in VALID_INTERVALS:
            raise ValueError(
                f"Invalid interval: {interval!r}. "
                f"Expected one of: {VALID_INTERVALS}"
            )

        if limit is not None and limit > _KLINES_LIMIT:
            raise ValueError(f"Limit cannot exceed {_KLINES_LIMIT}")

        if limit is not None and limit <= _KLINES_LIMIT:
            return await self._fetch_page(symbol, interval, since, until, limit)

        all_klines: list[KlineData] = []
        current_start = since

        while True:
            batch = await self._fetch_page(
                symbol, interval, current_start, until, _KLINES_LIMIT
            )
            if not batch:
                break

            all_klines.extend(batch)

            if len(batch) < _KLINES_LIMIT:
                break

            current_start = batch[-1].close_time + 1

            if until is not None and batch[-1].close_time >= until:
                break

        return all_klines

    async def stream_ohlcv(self, symbol: str, interval: str):
        raise NotImplementedError("Use BinanceCmWsClient for WebSocket streaming")


# Backward compatibility alias
BinanceRestClient = BinanceSpotRestClient
