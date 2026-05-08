"""Binance REST API clients implementing the ExchangeClient protocol."""

from __future__ import annotations

from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import (
    DERIVATIVES_TRADING_COIN_FUTURES_REST_API_PROD_URL,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
    SPOT_REST_API_PROD_URL,
    SPOT_REST_API_TESTNET_URL,
)
from binance_sdk_derivatives_trading_coin_futures.derivatives_trading_coin_futures import (
    DerivativesTradingCoinFutures,
)
from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
)
from binance_sdk_spot.spot import Spot

from binance_datatool.common.enums import TradeType
from binance_datatool.common.intervals import VALID_INTERVALS
from binance_datatool.common.types import KlineData

__all__ = ["BinanceSpotRestClient", "BinanceUmRestClient", "BinanceCmRestClient"]

_KLINES_LIMIT = 1000

_SDK_CLASSES = {
    TradeType.spot: Spot,
    TradeType.um: DerivativesTradingUsdsFutures,
    TradeType.cm: DerivativesTradingCoinFutures,
}

_SDK_BASE_URLS = {
    TradeType.spot: SPOT_REST_API_PROD_URL,
    TradeType.um: DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
    TradeType.cm: DERIVATIVES_TRADING_COIN_FUTURES_REST_API_PROD_URL,
}

_REST_API_METHOD = {
    TradeType.spot: "klines",
    TradeType.um: "kline_candlestick_data",
    TradeType.cm: "kline_candlestick_data",
}


class _BinanceRestClientBase:
    """Base class for Binance REST clients using official SDK.

    Not intended for direct use — use the market-specific subclasses.
    """

    def __init__(
        self,
        trade_type: TradeType,
        timeout_seconds: int | float = 30,
    ) -> None:
        self._trade_type = trade_type
        base_url = _SDK_BASE_URLS[trade_type]
        config = ConfigurationRestAPI(
            api_key="",
            api_secret="",
            base_path=base_url,
            timeout=timeout_seconds,
        )
        self._client = _SDK_CLASSES[trade_type](config_rest_api=config)

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
        method_name = _REST_API_METHOD[self._trade_type]
        rest_api = self._client.rest_api
        method = getattr(rest_api, method_name)

        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        response = method(**params)
        data = response.data()

        return [KlineData.from_binance_api(kline) for kline in data]

    async def close(self) -> None:
        return


class BinanceSpotRestClient(_BinanceRestClientBase):
    """Binance Spot market REST client.

    Implements the ExchangeClient protocol for spot trading pairs.
    """

    def __init__(
        self,
        timeout_seconds: int | float = 30,
        testnet: bool = False,
    ) -> None:
        self._trade_type = TradeType.spot
        self._timeout_seconds = timeout_seconds
        base_url = SPOT_REST_API_TESTNET_URL if testnet else SPOT_REST_API_PROD_URL
        config = ConfigurationRestAPI(
            api_key="",
            api_secret="",
            base_path=base_url,
            timeout=timeout_seconds,
        )
        self._client = Spot(config_rest_api=config)

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        if interval not in VALID_INTERVALS:
            raise ValueError(f"Invalid interval: {interval!r}. Expected one of: {VALID_INTERVALS}")

        if limit is not None and limit > _KLINES_LIMIT:
            raise ValueError(f"Limit cannot exceed {_KLINES_LIMIT}")

        if limit is not None and limit <= _KLINES_LIMIT:
            return await self._fetch_page(symbol, interval, since, until, limit)

        all_klines: list[KlineData] = []
        current_start = since

        while True:
            batch = await self._fetch_page(symbol, interval, current_start, until, _KLINES_LIMIT)
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
        raise NotImplementedError("Use BinanceSpotWsClient for WebSocket streaming")


class BinanceUmRestClient(_BinanceRestClientBase):
    """Binance USDⓈM futures (UM) REST client.

    Implements the ExchangeClient protocol for USD-M perpetual and
    delivery futures.
    """

    def __init__(
        self,
        timeout_seconds: int | float = 30,
    ) -> None:
        super().__init__(
            trade_type=TradeType.um,
            timeout_seconds=timeout_seconds,
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        if interval not in VALID_INTERVALS:
            raise ValueError(f"Invalid interval: {interval!r}. Expected one of: {VALID_INTERVALS}")

        if limit is not None and limit > _KLINES_LIMIT:
            raise ValueError(f"Limit cannot exceed {_KLINES_LIMIT}")

        if limit is not None and limit <= _KLINES_LIMIT:
            return await self._fetch_page(symbol, interval, since, until, limit)

        all_klines: list[KlineData] = []
        current_start = since

        while True:
            batch = await self._fetch_page(symbol, interval, current_start, until, _KLINES_LIMIT)
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

    def __init__(
        self,
        timeout_seconds: int | float = 30,
    ) -> None:
        super().__init__(
            trade_type=TradeType.cm,
            timeout_seconds=timeout_seconds,
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        if interval not in VALID_INTERVALS:
            raise ValueError(f"Invalid interval: {interval!r}. Expected one of: {VALID_INTERVALS}")

        if limit is not None and limit > _KLINES_LIMIT:
            raise ValueError(f"Limit cannot exceed {_KLINES_LIMIT}")

        if limit is not None and limit <= _KLINES_LIMIT:
            return await self._fetch_page(symbol, interval, since, until, limit)

        all_klines: list[KlineData] = []
        current_start = since

        while True:
            batch = await self._fetch_page(symbol, interval, current_start, until, _KLINES_LIMIT)
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


BinanceRestClient = BinanceSpotRestClient
