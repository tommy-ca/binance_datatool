"""Shared typed models for parsed Binance symbols and OHLCV data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binance_datatool.common.enums import ContractType


@dataclass(slots=True)
class SymbolInfoBase:
    """Base class for parsed symbol metadata."""

    symbol: str  # Original input, including any settled suffix (e.g. "LUNAUSDT_SETTLED")
    base_asset: str  # Parsed base asset (e.g. "LUNA")
    quote_asset: str  # Parsed quote asset (e.g. "USDT")


@dataclass(slots=True)
class SpotSymbolInfo(SymbolInfoBase):
    """Parsed metadata for a spot trading symbol."""

    is_leverage: bool  # True when the base is a leveraged token (e.g. BNBUP, BTCDOWN)
    is_stable_pair: bool  # True when both base and quote are in STABLECOINS


@dataclass(slots=True)
class UmSymbolInfo(SymbolInfoBase):
    """Parsed metadata for a USD-M futures symbol."""

    contract_type: ContractType  # Perpetual or dated delivery
    is_stable_pair: bool  # True when both base and quote are in STABLECOINS


@dataclass(slots=True)
class CmSymbolInfo(SymbolInfoBase):
    """Parsed metadata for a COIN-M futures symbol."""

    contract_type: ContractType  # Perpetual or dated delivery


SymbolInfo = SpotSymbolInfo | UmSymbolInfo | CmSymbolInfo


@dataclass(slots=True)
class KlineData:
    """OHLCV kline/candlestick data from an exchange."""

    open_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    close_time: int
    quote_volume: str
    num_trades: int
    taker_buy_volume: str
    taker_buy_quote_volume: str

    @classmethod
    def from_binance_api(cls, kline: list) -> KlineData:
        """Create a KlineData from a Binance REST API kline response.

        The Binance klines endpoint returns an array of 12 elements:
        [open_time, open, high, low, close, volume, close_time,
         quote_volume, num_trades, taker_buy_volume, taker_buy_quote_volume, ignore]
        """
        return cls(
            open_time=int(kline[0]),
            open=str(kline[1]),
            high=str(kline[2]),
            low=str(kline[3]),
            close=str(kline[4]),
            volume=str(kline[5]),
            close_time=int(kline[6]),
            quote_volume=str(kline[7]),
            num_trades=int(kline[8]),
            taker_buy_volume=str(kline[9]),
            taker_buy_quote_volume=str(kline[10]),
        )


@dataclass(slots=True)
class SilverKline:
    """Normalized silver-layer kline record.

    Unifies spot/um/cm klines from all sources (archive, API, WS).
    """

    ts_event: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    taker_buy_volume: float
    taker_buy_quote_volume: float
    source: str
    trade_type: str
    symbol: str
    interval: str
    data_type: str
    ingested_at: int


@dataclass(slots=True)
class SilverTrade:
    """Normalized silver-layer trade record.

    Unifies trades/aggTrades from all trade types.
    """

    ts_event: int
    price: float
    size: float
    side: str | None
    trade_id: int
    agg_trade_id: int | None = None
    is_buyer_maker: int | None = None
    source: str = ""
    trade_type: str = ""
    symbol: str = ""
    data_type: str = ""
    ingested_at: int = 0


@dataclass(slots=True)
class SilverFundingRate:
    """Normalized silver-layer funding rate record."""

    ts_event: int
    funding_rate: float
    mark_price: float
    source: str = ""
    trade_type: str = ""
    symbol: str = ""
    data_type: str = ""
    ingested_at: int = 0


__all__ = [
    "SymbolInfoBase",
    "SpotSymbolInfo",
    "UmSymbolInfo",
    "CmSymbolInfo",
    "SymbolInfo",
    "KlineData",
    "SilverKline",
    "SilverTrade",
    "SilverFundingRate",
]
