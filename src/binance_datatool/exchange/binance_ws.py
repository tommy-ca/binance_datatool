"""Binance WebSocket clients implementing the ExchangeClient protocol."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import aiohttp

from binance_datatool.common.types import KlineData

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ["BinanceSpotWsClient", "BinanceUmWsClient", "BinanceCmWsClient"]

#: WebSocket base URLs for each market type.
_WS_BASE_URLS = {
    "spot": "wss://stream.binance.com:9443/ws",
    "um": "wss://fstream.binance.com/ws",
    "cm": "wss://dstream.binance.com/ws",
}
_TESTNET_WS_BASE = "wss://stream.testnet.binance.vision:9443/ws"


class _BinanceWsClientBase:
    """Base class for Binance WebSocket clients.

    Not intended for direct use — use market-specific subclasses.
    """

    def __init__(self, ws_base: str) -> None:
        self._ws_base = ws_base

    @property
    def trade_type(self) -> str:
        """Return the market segment identifier."""
        if "fstream" in self._ws_base:
            return "um"
        if "dstream" in self._ws_base:
            return "cm"
        return "spot"

    async def close(self) -> None:
        """No-op (connections are per-stream)."""
        return

    async def fetch_ohlcv(self, symbol: str, interval: str, **kwargs) -> list[KlineData]:
        """Not supported over WebSocket — raises NotImplementedError."""
        raise NotImplementedError("Use REST client for historical klines")

    def _build_stream_url(self, stream_name: str) -> str:
        """Build WebSocket URL for a stream name."""
        return f"{self._ws_base}/{stream_name}"


class BinanceSpotWsClient(_BinanceWsClientBase):
    """Binance Spot market WebSocket client.

    Implements the ExchangeClient protocol for spot trading pairs.
    """

    def __init__(self, testnet: bool = False) -> None:
        """Initialize spot WebSocket client.

        Args:
            testnet: Use Binance spot testnet.
        """
        ws_base = _TESTNET_WS_BASE if testnet else _WS_BASE_URLS["spot"]
        super().__init__(ws_base=ws_base)

    @property
    def exchange_id(self) -> str:
        return "binance_spot"

    async def stream_ohlcv(
        self,
        symbol: str,
        interval: str,
    ) -> AsyncIterator[KlineData]:
        """Stream real-time spot klines via WebSocket.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").
            interval: Kline interval (e.g., "1h", "1d").

        Yields:
            KlineData objects as they arrive.
        """
        stream_name = f"{symbol.lower()}@kline_{interval}"
        ws_url = self._build_stream_url(stream_name)

        async with aiohttp.ClientSession() as session, session.ws_connect(
            ws_url
        ) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if "k" in data:
                        k = data["k"]
                        yield KlineData(
                            open_time=int(k["t"]),
                            open=str(k["o"]),
                            high=str(k["h"]),
                            low=str(k["l"]),
                            close=str(k["c"]),
                            volume=str(k["v"]),
                            close_time=int(k["T"]),
                            quote_volume=str(k["q"]),
                            num_trades=int(k["n"]),
                            taker_buy_volume=str(k["V"]),
                            taker_buy_quote_volume=str(k["Q"]),
                        )
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise aiohttp.ClientError(f"WebSocket error: {msg}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break


class BinanceUmWsClient(_BinanceWsClientBase):
    """Binance USDⓈM futures (UM) WebSocket client.

    Implements the ExchangeClient protocol for USD-M perpetual
    and delivery futures.
    """

    def __init__(self) -> None:
        """Initialize UM futures WebSocket client."""
        super().__init__(ws_base=_WS_BASE_URLS["um"])

    @property
    def exchange_id(self) -> str:
        return "binance_um"

    async def stream_ohlcv(
        self,
        symbol: str,
        interval: str,
    ) -> AsyncIterator[KlineData]:
        """Stream real-time USD-M futures klines via WebSocket.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT").

            interval: Kline interval.

        Yields:
            KlineData objects as they arrive.
        """
        stream_name = f"{symbol.lower()}@kline_{interval}"
        ws_url = self._build_stream_url(stream_name)

        async with aiohttp.ClientSession() as session, session.ws_connect(
            ws_url
        ) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if "k" in data:
                        k = data["k"]
                        yield KlineData(
                            open_time=int(k["t"]),
                            open=str(k["o"]),
                            high=str(k["h"]),
                            low=str(k["l"]),
                            close=str(k["c"]),
                            volume=str(k["v"]),
                            close_time=int(k["T"]),
                            quote_volume=str(k["q"]),
                            num_trades=int(k["n"]),
                            taker_buy_volume=str(k["V"]),
                            taker_buy_quote_volume=str(k["Q"]),
                        )
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise aiohttp.ClientError(f"WebSocket error: {msg}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break


class BinanceCmWsClient(_BinanceWsClientBase):
    """Binance COINⓈM futures (CM) WebSocket client.

    Implements the ExchangeClient protocol for COIN-M perpetual
    and delivery futures.
    """

    def __init__(self) -> None:
        """Initialize CM futures WebSocket client."""
        super().__init__(ws_base=_WS_BASE_URLS["cm"])

    @property
    def exchange_id(self) -> str:
        return "binance_cm"

    async def stream_ohlcv(
        self,
        symbol: str,
        interval: str,
    ) -> AsyncIterator[KlineData]:
        """Stream real-time COIN-M futures klines via WebSocket.

        Args:
            symbol: Trading pair (e.g., "BTCUSD_PERP").

            interval: Kline interval.

        Yields:
            KlineData objects as they arrive.
        """
        stream_name = f"{symbol.lower()}@kline_{interval}"
        ws_url = self._build_stream_url(stream_name)

        async with aiohttp.ClientSession() as session, session.ws_connect(
            ws_url
        ) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if "k" in data:
                        k = data["k"]
                        yield KlineData(
                            open_time=int(k["t"]),
                            open=str(k["o"]),
                            high=str(k["h"]),
                            low=str(k["l"]),
                            close=str(k["c"]),
                            volume=str(k["v"]),
                            close_time=int(k["T"]),
                            quote_volume=str(k["q"]),
                            num_trades=int(k["n"]),
                            taker_buy_volume=str(k["V"]),
                            taker_buy_quote_volume=str(k["Q"]),
                        )
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    raise aiohttp.ClientError(f"WebSocket error: {msg}")
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break


# Backward compatibility alias
BinanceWsClient = BinanceSpotWsClient
