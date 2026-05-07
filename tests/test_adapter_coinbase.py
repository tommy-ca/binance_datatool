"""Tests for CoinbaseAdapter skeleton."""

import pytest

from binance_datatool.adapter.coinbase import CoinbaseAdapter


class TestCoinbaseAdapterProperties:
    """Test CoinbaseAdapter basic properties."""

    def test_source_name(self):
        """Test that source_name returns 'coinbase'."""
        adapter = CoinbaseAdapter()
        assert adapter.source_name == "coinbase"

    def test_initialization_with_defaults(self):
        """Test CoinbaseAdapter initialization with defaults."""
        adapter = CoinbaseAdapter()
        assert adapter.api_key is None
        assert adapter.api_secret is None
        assert adapter.api_passphrase is None

    def test_initialization_with_credentials(self):
        """Test CoinbaseAdapter initialization with credentials."""
        adapter = CoinbaseAdapter(
            api_key="test_key",
            api_secret="test_secret",
            api_passphrase="test_passphrase",
        )
        assert adapter.api_key == "test_key"
        assert adapter.api_secret == "test_secret"
        assert adapter.api_passphrase == "test_passphrase"


@pytest.mark.asyncio
class TestCoinbaseAdapterUnimplemented:
    """Test that skeleton methods raise NotImplementedError."""

    async def test_list_symbols_not_implemented(self):
        """Test that list_symbols is not implemented."""
        adapter = CoinbaseAdapter()

        with pytest.raises(
            NotImplementedError, match="requires Coinbase API integration"
        ):
            await adapter.list_symbols("spot", "daily", "klines")

    async def test_list_files_not_implemented(self):
        """Test that list_files is not implemented."""
        adapter = CoinbaseAdapter()

        with pytest.raises(
            NotImplementedError, match="requires Coinbase API integration"
        ):
            await adapter.list_files("spot", "daily", "klines", "BTC-USD")

    async def test_fetch_file_not_implemented(self):
        """Test that fetch_file is not implemented."""
        adapter = CoinbaseAdapter()

        with pytest.raises(
            NotImplementedError, match="requires Coinbase API integration"
        ):
            await adapter.fetch_file("https://example.com/file.zip", "/tmp/file.zip")


class TestCoinbaseAdapterParseSymbol:
    """Test parse_symbol method."""

    def test_parse_symbol_btc_usd(self):
        """Test parsing BTC-USD product ID."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("BTC-USD")

        assert result is not None
        assert result["symbol"] == "BTC-USD"
        assert result["base_asset"] == "BTC"
        assert result["quote_asset"] == "USD"

    def test_parse_symbol_eth_usdc(self):
        """Test parsing ETH-USDC product ID."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("ETH-USDC")

        assert result is not None
        assert result["base_asset"] == "ETH"
        assert result["quote_asset"] == "USDC"

    def test_parse_symbol_bnb_usdt(self):
        """Test parsing BNB-USDT product ID."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("BNB-USDT")

        assert result is not None
        assert result["base_asset"] == "BNB"
        assert result["quote_asset"] == "USDT"

    def test_parse_symbol_no_dash(self):
        """Test parsing symbol without dash."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("BTCUSD")

        assert result is None

    def test_parse_symbol_empty_base(self):
        """Test parsing symbol with empty base."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("-USD")

        assert result is None

    def test_parse_symbol_empty_quote(self):
        """Test parsing symbol with empty quote."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("BTC-")

        assert result is None

    def test_parse_symbol_multiple_dashes(self):
        """Test parsing symbol with multiple dashes."""
        adapter = CoinbaseAdapter()
        result = adapter.parse_symbol("BTC-USD-EUR")

        # Should not parse (too many parts)
        assert result is None
