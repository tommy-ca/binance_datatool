"""Tests for exchange clients implementing the ExchangeClient protocol."""

from __future__ import annotations

import pytest

from binance_datatool.common.enums import TradeType
from binance_datatool.exchange import (
    BinanceRestClient,
    BinanceSpotRestClient,
    BinanceUmRestClient,
    BinanceCmRestClient,
    BinanceWsClient,
    BinanceSpotWsClient,
    BinanceUmWsClient,
    BinanceCmWsClient,
    CCXTExchangeClient,
    CCXTProExchangeClient,
)
from binance_datatool.exchange.client import ExchangeClient


class TestExchangeClientProtocol:
    """Verify market-type-specific clients implement ExchangeClient protocol."""

    def test_spot_rest_implements_protocol(self) -> None:
        client = BinanceSpotRestClient()
        assert isinstance(client, ExchangeClient)
        assert client.exchange_id == "binance_spot"
        assert client.trade_type == TradeType.spot

    def test_um_rest_implements_protocol(self) -> None:
        client = BinanceUmRestClient()
        assert isinstance(client, ExchangeClient)
        assert client.exchange_id == "binance_um"
        assert client.trade_type == TradeType.um

    def test_cm_rest_implements_protocol(self) -> None:
        client = BinanceCmRestClient()
        assert isinstance(client, ExchangeClient)
        assert client.exchange_id == "binance_cm"
        assert client.trade_type == TradeType.cm

    def test_spot_ws_implements_protocol(self) -> None:
        client = BinanceSpotWsClient()
        assert isinstance(client, ExchangeClient)
        assert client.exchange_id == "binance_spot"
        assert client.trade_type == "spot"

    def test_um_ws_implements_protocol(self) -> None:
        client = BinanceUmWsClient()
        assert isinstance(client, ExchangeClient)
        assert client.exchange_id == "binance_um"
        assert client.trade_type == "um"

    def test_cm_ws_implements_protocol(self) -> None:
        client = BinanceCmWsClient()
        assert isinstance(client, ExchangeClient)
        assert client.exchange_id == "binance_cm"
        assert client.trade_type == "cm"


class TestBackwardCompatibility:
    """Verify backward-compatible aliases work correctly."""

    def test_binance_rest_alias(self) -> None:
        client = BinanceRestClient()
        assert isinstance(client, BinanceSpotRestClient)

    def test_binance_ws_alias(self) -> None:
        client = BinanceWsClient()
        assert isinstance(client, BinanceSpotWsClient)


class TestBinanceRestClients:
    """Test REST client configuration and base URL selection."""

    def test_spot_rest_api_base(self) -> None:
        client = BinanceSpotRestClient()
        assert client._api_base == "https://api.binance.com/api/v3"

    def test_spot_rest_testnet(self) -> None:
        client = BinanceSpotRestClient(testnet=True)
        assert "testnet" in client._api_base

    def test_um_rest_api_base(self) -> None:
        client = BinanceUmRestClient()
        assert client._api_base == "https://fapi.binance.com/fapi/v1"

    def test_cm_rest_api_base(self) -> None:
        client = BinanceCmRestClient()
        assert client._api_base == "https://dapi.binance.com/dapi/v1"

    def test_rest_clients_have_same_interface(self) -> None:
        spot = BinanceSpotRestClient()
        um = BinanceUmRestClient()
        cm = BinanceCmRestClient()
        for client in [spot, um, cm]:
            assert hasattr(client, "fetch_ohlcv")
            assert hasattr(client, "stream_ohlcv")
            assert hasattr(client, "close")


class TestBinanceWsClients:
    """Test WebSocket client configuration and URL building."""

    def test_spot_ws_url(self) -> None:
        client = BinanceSpotWsClient()
        url = client._build_stream_url("btcusdt@kline_1h")
        assert url == "wss://stream.binance.com:9443/ws/btcusdt@kline_1h"

    def test_um_ws_url(self) -> None:
        client = BinanceUmWsClient()
        url = client._build_stream_url("btcusdt@kline_1h")
        assert url == "wss://fstream.binance.com/ws/btcusdt@kline_1h"

    def test_cm_ws_url(self) -> None:
        client = BinanceCmWsClient()
        url = client._build_stream_url("btcusdt@kline_1h")
        assert url == "wss://dstream.binance.com/ws/btcusdt@kline_1h"

    def test_spot_ws_testnet_url(self) -> None:
        client = BinanceSpotWsClient(testnet=True)
        url = client._build_stream_url("btcusdt@kline_1h")
        assert "testnet" in url

    def test_ws_clients_have_same_interface(self) -> None:
        spot = BinanceSpotWsClient()
        um = BinanceUmWsClient()
        cm = BinanceCmWsClient()
        for client in [spot, um, cm]:
            assert hasattr(client, "stream_ohlcv")
            assert hasattr(client, "fetch_ohlcv")
            assert hasattr(client, "close")


class TestCCXTExchangeClient:
    """Test CCXT REST client (requires ccxt optional dependency)."""

    def test_ccxt_rest_requires_optional_dep(self) -> None:
        try:
            import ccxt  # noqa: F401
        except ImportError:
            pytest.skip("ccxt not installed")

        client = CCXTExchangeClient(trade_type=TradeType.spot)
        assert client.exchange_id == "binance"
        assert client.trade_type == TradeType.spot


class TestIntervalValidation:
    """Test interval validation in REST clients."""

    def test_valid_intervals_accepted(self) -> None:
        from binance_datatool.common.intervals import VALID_INTERVALS

        assert "1m" in VALID_INTERVALS
        assert "1h" in VALID_INTERVALS
        assert "1d" in VALID_INTERVALS

    def test_invalid_interval_rejected(self) -> None:
        import asyncio

        client = BinanceSpotRestClient()
        with pytest.raises(ValueError, match="Invalid interval"):
            asyncio.run(client.fetch_ohlcv("BTCUSDT", "invalid"))
