"""CCXT REST client implementing the ExchangeClient protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from binance_datatool.common.intervals import VALID_INTERVALS
from binance_datatool.common.types import KlineData

if TYPE_CHECKING:
    from binance_datatool.common.enums import TradeType

__all__ = ["CCXTExchangeClient"]


class CCXTExchangeClient:
    """CCXT REST client for multi-exchange OHLCV data.

    Supports Binance (spot/um/cm), OKX, Bybit, and 100+ other exchanges
    via CCXT's unified API.

    Implements the :class:`~binance_datatool.exchange.client.ExchangeClient`
    protocol.

    Note:
        CCXT is optional. Install with ``uv add binance-datatool[exchange]``.
    """

    def __init__(
        self,
        exchange_id: str = "binance",
        market_type: str = "spot",
        enable_rate_limit: bool = True,
    ) -> None:
        """Initialize the CCXT client.

        Args:
            exchange_id: Exchange identifier (binance, okex, bybit, etc.).
            market_type: Market type (spot, swap, future, option).
            enable_rate_limit: Let CCXT handle rate limiting.

        Raises:
            ImportError: If ccxt is not installed.
            ValueError: If exchange_id is not supported.
        """
        self._exchange_id = exchange_id
        self._market_type = market_type

        try:
            import ccxt
        except ImportError as exc:
            raise ImportError(
                "ccxt is required for CCXTExchangeClient. "
                "Install with: uv add binance-datatool[exchange]"
            ) from exc

        # Map exchange_id to CCXT class
        exchange_map = {
            "binance": self._init_binance,
            "okex": self._init_okx,
            "bybit": self._init_bybit,
        }

        init_func = exchange_map.get(exchange_id)
        if init_func is None:
            # Generic CCXT exchange (may not support all features)
            if not hasattr(ccxt, exchange_id):
                raise ValueError(f"Unsupported exchange_id: {exchange_id}")
            exchange_class = getattr(ccxt, exchange_id)
            self._exchange = exchange_class({"enableRateLimit": enable_rate_limit})
        else:
            init_func(self, ccxt, enable_rate_limit)

        # Set market type for exchanges that support it
        if market_type != "spot" and hasattr(self._exchange, "options"):
            self._exchange.options["defaultType"] = market_type

    def _init_binance(self, ccxt, enable_rate_limit: bool) -> None:
        """Initialize Binance with market type mapping."""
        if self._market_type == "spot":
            self._exchange = ccxt.binance({"enableRateLimit": enable_rate_limit})
        elif self._market_type in ("um", "swap"):
            self._exchange = ccxt.binanceusdm({"enableRateLimit": enable_rate_limit})
        elif self._market_type in ("cm", "future"):
            self._exchange = ccxt.binancecoinm({"enableRateLimit": enable_rate_limit})
        else:
            raise ValueError(f"Unsupported Binance market_type: {self._market_type}")

    def _init_okx(self, ccxt, enable_rate_limit: bool) -> None:
        """Initialize OKX (ccxt.okex)."""
        self._exchange = ccxt.okex(  # type: ignore[attr-defined]
            {"enableRateLimit": enable_rate_limit}
        )

    def _init_bybit(self, ccxt, enable_rate_limit: bool) -> None:
        """Initialize Bybit."""
        self._exchange = ccxt.bybit(  # type: ignore[attr-defined]
            {"enableRateLimit": enable_rate_limit}
        )

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
            raise ValueError(f"Invalid interval: {interval!r}. Expected one of: {VALID_INTERVALS}")

        # CCXT expects since as keyword arg, limit as keyword arg
        kwargs: dict = {}
        if since is not None:
            kwargs["since"] = since
        if limit is not None:
            kwargs["limit"] = limit

        # CCXT returns [[timestamp, open, high, low, close, volume], ...]
        ohlcv_list = await self._exchange.fetch_ohlcv(symbol, interval, **kwargs)

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
