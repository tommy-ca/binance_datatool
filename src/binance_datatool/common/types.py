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


__all__ = [
    "SymbolInfoBase",
    "SpotSymbolInfo",
    "UmSymbolInfo",
    "CmSymbolInfo",
    "SymbolInfo",
    "KlineData",
]
