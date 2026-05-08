"""CCXT Pro WebSocket client implementing the ExchangeClient protocol."""

from __future__ import annotations

import asyncio
import importlib

from binance_datatool.common.enums import TradeType
from binance_datatool.common.intervals import VALID_INTERVALS
from binance_datatool.common.types import KlineData

__all__ = ["CCXTProExchangeClient"]


class CCXTProExchangeClient:
    """CCXT Pro WebSocket client for Binance Spot, UM, and CM markets.

    Wraps ``ccxt.pro.binance``, ``ccxt.pro.binanceusdm``, or
    ``ccxt.pro.binancecoin`` depending on the requested market type.

    Implements the :class:`~binance_datatool.exchange.client.ExchangeClient`
    protocol.

    Note:
        CCXT Pro is a separate package from CCXT. To use this client,
        install ccxt with ``uv add ccxt`` and obtain a CCXT Pro license
        for access to the ``ccxt.pro`` module.
    """

    def __init__(
        self,
        trade_type: TradeType | str = TradeType.spot,
        enable_rate_limit: bool = True,
    ) -> None:
        """Initialize the CCXT Pro client.

        Args:
            trade_type: Market segment (spot, um, cm).
            enable_rate_limit: Let CCXT handle rate limiting.
        """
        if isinstance(trade_type, str):
            trade_type = TradeType(trade_type)
        self._trade_type = trade_type

        try:
            ccxt_pro = importlib.import_module("ccxt.pro")
        except ImportError as exc:
            raise ImportError(
                "ccxt.pro is required for CCXTProExchangeClient. "
                "Install ccxt and obtain a CCXT Pro license."
            ) from exc

        if trade_type is TradeType.spot:
            self._exchange: ccxt_pro.binance = ccxt_pro.binance(
                {"enableRateLimit": enable_rate_limit}
            )
        elif trade_type is TradeType.um:
            self._exchange = ccxt_pro.binanceusdm(
                {"enableRateLimit": enable_rate_limit}
            )
        elif trade_type is TradeType.cm:
            self._exchange = ccxt_pro.binancecoin(
                {"enableRateLimit": enable_rate_limit}
            )
        else:
            raise ValueError(f"Unsupported trade_type: {trade_type}")

    @property
    def exchange_id(self) -> str:
        """Human-readable exchange identifier."""
        return f"ccxt_pro_binance_{self._trade_type.value}"

    @property
    def trade_type(self) -> TradeType:
        """Return the market segment this client is configured for."""
        return self._trade_type

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        since: int | None = None,
        until: int | None = None,
        limit: int | None = None,
    ) -> list[KlineData]:
        """Not supported over WebSocket — raises NotImplementedError."""
        raise NotImplementedError("Use CCXTExchangeClient for REST API fetching")

    async def stream_ohlcv(
        self,
        symbol: str,
        interval: str,
    ):
        """Stream real-time klines via CCXT Pro WebSocket.

        Args:
            symbol: Trading pair in BASE/QUOTE format (e.g. "BTC/USDT").
            interval: Kline interval (e.g. "1h", "1d").

        Yields:
            KlineData objects as they arrive.
        """
        if interval not in VALID_INTERVALS:
            raise ValueError(
                f"Invalid interval: {interval!r}. "
                f"Expected one of: {VALID_INTERVALS}"
            )

        interval_ms = self._interval_to_ms(interval)

        while True:
            try:
                ohlcv_list = await self._exchange.watch_ohlcv(symbol, interval)

                for ohlcv in ohlcv_list:
                    yield KlineData(
                        open_time=int(ohlcv[0]),
                        open=str(ohlcv[1]),
                        high=str(ohlcv[2]),
                        low=str(ohlcv[3]),
                        close=str(ohlcv[4]),
                        volume=str(ohlcv[5]),
                        close_time=int(ohlcv[0]) + interval_ms - 1,
                        quote_volume="0",
                        num_trades=0,
                        taker_buy_volume="0",
                        taker_buy_quote_volume="0",
                    )
            except Exception as e:
                # CCXT Pro handles reconnection internally, but we log the error
                import logging

                logging.warning(f"WebSocket error: {e}. Continuing...")
                await asyncio.sleep(1)

    async def close(self) -> None:
        """Release CCXT Pro exchange resources."""
        await self._exchange.close()

    def _interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds."""
        from binance_datatool.common.intervals import interval_to_ms

        return interval_to_ms(interval)

    def _to_ccxt_symbol(self, symbol: str) -> str:
        """Convert Binance symbol to CCXT format.

        Args:
            symbol: Binance symbol (e.g. "BTCUSDT").

        Returns:
            CCXT symbol format (e.g. "BTC/USDT" for spot, "BTC/USDT:USDT" for UM).
        """
        if self._trade_type is TradeType.spot:
            base = symbol[:-4] if symbol.endswith(("USDT", "BUSD", "TUSD", "USDC")) else symbol[:-3]
            quote = symbol[-4:] if symbol.endswith(("USDT", "BUSD", "TUSD", "USDC")) else symbol[-3:]
            return f"{base}/{quote}"
        elif self._trade_type is TradeType.um:
            base = symbol[:-4] if symbol.endswith(("USDT", "BUSD", "TUSD", "USDC")) else symbol[:-3]
            return f"{base}/USDT:USDT"
        else:  # cm
            base = symbol[:-4] if symbol.endswith("_PERP") else symbol.rsplit("_", 1)[0]
            return f"{base}/USD:BTC"

    def _to_ccxt_timeframe(self, interval: str) -> str:
        """Convert Binance interval to CCXT timeframe.

        Args:
            interval: Binance interval (e.g. "1h", "1d").

        Returns:
            CCXT timeframe string.
        """
        if interval not in VALID_INTERVALS:
            raise ValueError(
                f"Unsupported interval: {interval!r}. "
                f"Expected one of: {VALID_INTERVALS}"
            )
        return interval
