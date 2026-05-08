"""Exchange client package for live market data access."""

from __future__ import annotations

from binance_datatool.exchange.binance_rest import (
    BinanceCmRestClient,
    BinanceRestClient,  # backward compatibility alias
    BinanceSpotRestClient,
    BinanceUmRestClient,
)
from binance_datatool.exchange.binance_ws import (
    BinanceCmWsClient,
    BinanceSpotWsClient,
    BinanceUmWsClient,
    BinanceWsClient,  # backward compatibility alias
)
from binance_datatool.exchange.ccxt_pro import CCXTProExchangeClient
from binance_datatool.exchange.ccxt_rest import CCXTExchangeClient
from binance_datatool.exchange.client import ExchangeClient

__all__ = [
    "ExchangeClient",
    "BinanceSpotRestClient",
    "BinanceUmRestClient",
    "BinanceCmRestClient",
    "BinanceRestClient",  # backward compatibility
    "BinanceSpotWsClient",
    "BinanceUmWsClient",
    "BinanceCmWsClient",
    "BinanceWsClient",  # backward compatibility
    "CCXTExchangeClient",
    "CCXTProExchangeClient",
]
