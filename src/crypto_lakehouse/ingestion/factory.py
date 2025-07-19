"""Ingestion factory for creating exchange-specific ingestors."""

from ..core.config import Settings
from ..core.models import Exchange
from .base import BaseIngestor
from .binance import BinanceIngestor


def create_ingestor(exchange: Exchange, settings: Settings) -> BaseIngestor:
    """Create appropriate ingestor based on exchange."""

    if exchange == Exchange.BINANCE:
        return BinanceIngestor(settings)
    else:
        raise ValueError(f"Unsupported exchange: {exchange}")


def create_binance_ingestor(settings: Settings) -> BinanceIngestor:
    """Create Binance-specific ingestor."""
    return BinanceIngestor(settings)
