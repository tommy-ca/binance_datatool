"""CCXT REST client implementing the ExchangeClient protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ccxt

from binance_datatool.common.enums import TradeType
from binance_datatool.common.intervals import VALID_INTERVALS
from binance_datatool.common.types import KlineData

__all__ = ["CCXTExchangeClient"]


class CCXTExchangeClient:
    """CCXT REST client for Binance Spot, UM, and CM markets.

    Wraps ``ccxt.binance``, ``ccxt.binanceusdm``, or ``ccxt.binancecoinm``
    depending on the requested market type.

    Implements the :class:`~binance_datatool.exchange.client.ExchangeClient`
    protocol.

    Note:
        CCXT is optional. Install with ``uv add binance-datatool[exchange]``.
    """

    def __init__(
        self,
        trade_type: TradeType | str = TradeType.spot,
        enable_rate_limit: bool = True,
    ) -> None:
        """Initialize the CCXT client.

        Args:
            trade_type: Market segment (spot, um, cm).
            enable_rate_limit: Let CCXT handle rate limiting.

        Raises:
            ImportError: If ccxt is not installed.
        """
        if isinstance(trade_type, str):
            trade_type = TradeType(trade_type)
        self._trade_type = trade_type

        try:
            import ccxt
        except ImportError as exc:
            raise ImportError(
                "ccxt is required for CCXTExchangeClient. "
                "Install with: uv add binance-datatool[exchange]"
            ) from exc

        if trade_type is TradeType.spot:
            self._exchange: ccxt.binance = ccxt.binance(
                {"enableRateLimit": enable_rate_limit}
            )
        elif trade_type is TradeType.um:
            self._exchange = ccxt.binanceusdm(
                {"enableRateLimit": enable_rate_limit}
            )
        elif trade_type is TradeType.cm:
            self._exchange = ccxt.binancecoinm(
                {"enableRateLimit": enable_rate_limit}
            )
        else:
            raise ValueError(f"Unsupported trade_type: {trade_type}")

    @property
    def exchange_id(self) -> str:
        """Human-readable exchange identifier."""
        return f"ccxt_binance_{self._trade_type.value}"

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
        """Fetch historical klines via CCXT.

        Args:
            symbol: Trading pair in BASE/QUOTE format (e.g. "BTC/USDT").
            interval: Kline interval (e.g. "1h", "1d").
            since: Start time in milliseconds (optional).
            until: End time in milliseconds (optional).
            limit: Maximum candles to fetch (optional).

        Returns:
            List of KlineData objects.
        """
        if interval not in VALID_INTERVALS:
            raise ValueError(
                f"Invalid interval: {interval!r}. "
                f"Expected one of: {VALID_INTERVALS}"
            )

        # CCXT expects since as keyword arg, limit as keyword arg
        kwargs: dict = {}
        if since is not None:
            kwargs["since"] = since
        if limit is not None:
            kwargs["limit"] = limit

        # CCXT returns [[timestamp, open, high, low, close, volume], ...]
        ohlcv_list = await self._exchange.fetch_ohlcv(
            symbol, interval, **kwargs
        )

        # Convert CCXT OHLCV (6 fields) to KlineData (10 fields)
        result: list[KlineData] = []
        interval_ms = self._interval_to_ms(interval)

        for ohlcv in ohlcv_list:
            result.append(
                KlineData(
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
            )

        return result

    async def stream_ohlcv(self, symbol: str, interval: str):
        """Not supported over CCXT REST — raises NotImplementedError."""
        raise NotImplementedError("Use CCXTProExchangeClient for WebSocket streaming")

    async def close(self) -> None:
        """Release CCXT exchange resources."""
        await self._exchange.close()

    def _interval_to_ms(self, interval: str) -> int:
        """Convert interval string to milliseconds."""
        from binance_datatool.common.intervals import interval_to_ms

        return interval_to_ms(interval)
