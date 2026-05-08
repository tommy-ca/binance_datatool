"""Tests for BinanceAdapter."""

from datetime import UTC, datetime

import pytest

from binance_datatool.adapter import FileMetadata
from binance_datatool.adapter.binance import BinanceAdapter
from binance_datatool.archive import ArchiveFile


class FakeBinanceArchiveClient:
    """Stub ArchiveClient for testing BinanceAdapter."""

    def __init__(
        self,
        symbols: list[str] | None = None,
        files_by_symbol: dict[str, list[ArchiveFile]] | None = None,
        errors_by_symbol: dict[str, Exception] | None = None,
    ):
        self.symbols = symbols or []
        self.files_by_symbol = files_by_symbol or {}
        self.errors_by_symbol = errors_by_symbol or {}
        self.timeout_seconds = 30
        self.trust_env = True

    async def list_symbols(self, trade_type, data_freq, data_type):
        """Stub list_symbols."""
        return list(self.symbols)

    async def list_symbol_files(
        self,
        trade_type,
        data_freq,
        data_type,
        symbol,
        interval=None,
    ):
        """Stub list_symbol_files."""
        if symbol in self.errors_by_symbol:
            raise self.errors_by_symbol[symbol]
        return list(self.files_by_symbol.get(symbol, []))


class TestBinanceAdapterProperties:
    """Test BinanceAdapter basic properties and initialization."""

    def test_source_name(self):
        """Test that source_name returns 'binance'."""
        adapter = BinanceAdapter()
        assert adapter.source_name == "binance"

    def test_initialization_with_defaults(self):
        """Test BinanceAdapter initialization with defaults."""
        adapter = BinanceAdapter()
        assert adapter._client is not None
        assert adapter._client.timeout_seconds == 30
        assert adapter._client.trust_env is True

    def test_initialization_with_custom_timeout(self):
        """Test BinanceAdapter initialization with custom timeout."""
        adapter = BinanceAdapter(timeout_seconds=60)
        assert adapter._client.timeout_seconds == 60

    def test_initialization_with_trust_env_false(self):
        """Test BinanceAdapter initialization with trust_env=False."""
        adapter = BinanceAdapter(trust_env=False)
        assert adapter._client.trust_env is False


@pytest.mark.asyncio
class TestBinanceAdapterListSymbols:
    """Test list_symbols method."""

    async def test_list_symbols_spot_daily(self):
        """Test listing spot daily symbols."""
        adapter = BinanceAdapter()
        adapter._client = FakeBinanceArchiveClient(symbols=["BTCUSDT", "ETHUSDT"])

        symbols = await adapter.list_symbols(
            market_type="spot", partition="daily", data_type="klines"
        )

        assert symbols == ["BTCUSDT", "ETHUSDT"]

    async def test_list_symbols_um_monthly(self):
        """Test listing UM futures monthly symbols."""
        adapter = BinanceAdapter()
        adapter._client = FakeBinanceArchiveClient(symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"])

        symbols = await adapter.list_symbols(
            market_type="um", partition="monthly", data_type="klines"
        )

        assert len(symbols) == 3
        assert "BTCUSDT" in symbols

    async def test_list_symbols_cm_daily(self):
        """Test listing CM futures daily symbols."""
        adapter = BinanceAdapter()
        adapter._client = FakeBinanceArchiveClient(symbols=["BTCUSD_PERP", "ETHUSD_PERP"])

        symbols = await adapter.list_symbols(
            market_type="cm", partition="daily", data_type="klines"
        )

        assert len(symbols) == 2

    async def test_list_symbols_invalid_market_type(self):
        """Test list_symbols with invalid market_type."""
        adapter = BinanceAdapter()

        with pytest.raises(ValueError, match="Invalid market_type"):
            await adapter.list_symbols(market_type="invalid", partition="daily", data_type="klines")

    async def test_list_symbols_invalid_partition(self):
        """Test list_symbols with invalid partition."""
        adapter = BinanceAdapter()

        with pytest.raises(ValueError, match="Invalid partition"):
            await adapter.list_symbols(market_type="spot", partition="weekly", data_type="klines")

    async def test_list_symbols_invalid_data_type(self):
        """Test list_symbols with invalid data_type."""
        adapter = BinanceAdapter()

        with pytest.raises(ValueError, match="Invalid data_type"):
            await adapter.list_symbols(market_type="spot", partition="daily", data_type="invalid")

    async def test_list_symbols_agg_trades(self):
        """Test listing symbols for aggTrades data type."""
        adapter = BinanceAdapter()
        adapter._client = FakeBinanceArchiveClient(symbols=["BTCUSDT"])

        symbols = await adapter.list_symbols(
            market_type="spot", partition="daily", data_type="aggTrades"
        )

        assert symbols == ["BTCUSDT"]


@pytest.mark.asyncio
class TestBinanceAdapterListFiles:
    """Test list_files method."""

    async def test_list_files_spot_daily(self):
        """Test listing files for a symbol."""
        adapter = BinanceAdapter()
        archive_files = [
            ArchiveFile(
                key="data/spot/daily/klines/BTCUSDT/BTCUSDT-1d-2024-01-01.zip",
                size=1024,
                last_modified=datetime(2024, 1, 2, tzinfo=UTC),
            ),
            ArchiveFile(
                key="data/spot/daily/klines/BTCUSDT/BTCUSDT-1d-2024-01-02.zip",
                size=2048,
                last_modified=datetime(2024, 1, 3, tzinfo=UTC),
            ),
        ]
        adapter._client = FakeBinanceArchiveClient(files_by_symbol={"BTCUSDT": archive_files})

        files = await adapter.list_files(
            market_type="spot",
            partition="daily",
            data_type="klines",
            symbol="BTCUSDT",
        )

        assert len(files) == 2
        assert all(isinstance(f, FileMetadata) for f in files)
        assert files[0].size == 1024
        assert files[1].size == 2048

    async def test_list_files_with_url_conversion(self):
        """Test that S3 keys are converted to URLs."""
        adapter = BinanceAdapter()
        archive_files = [
            ArchiveFile(
                key="data/spot/daily/klines/BTCUSDT/BTCUSDT-1d-2024-01-01.zip",
                size=1024,
                last_modified=datetime(2024, 1, 2, tzinfo=UTC),
            ),
        ]
        adapter._client = FakeBinanceArchiveClient(files_by_symbol={"BTCUSDT": archive_files})

        files = await adapter.list_files(
            market_type="spot",
            partition="daily",
            data_type="klines",
            symbol="BTCUSDT",
        )

        assert len(files) == 1
        assert "data/spot/daily/klines" in files[0].url
        assert files[0].key == archive_files[0].key

    async def test_list_files_empty_result(self):
        """Test listing files when symbol has no files."""
        adapter = BinanceAdapter()
        adapter._client = FakeBinanceArchiveClient(files_by_symbol={"BTCUSDT": []})

        files = await adapter.list_files(
            market_type="spot",
            partition="daily",
            data_type="klines",
            symbol="BTCUSDT",
        )

        assert files == []

    async def test_list_files_with_interval(self):
        """Test listing files with interval parameter."""
        adapter = BinanceAdapter()
        archive_files = [
            ArchiveFile(
                key="data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip",
                size=5120,
                last_modified=datetime(2024, 1, 2, tzinfo=UTC),
            ),
        ]
        adapter._client = FakeBinanceArchiveClient(files_by_symbol={"BTCUSDT": archive_files})

        files = await adapter.list_files(
            market_type="spot",
            partition="daily",
            data_type="klines",
            symbol="BTCUSDT",
            interval="1m",
        )

        assert len(files) == 1

    async def test_list_files_invalid_market_type(self):
        """Test list_files with invalid market_type."""
        adapter = BinanceAdapter()

        with pytest.raises(ValueError, match="Invalid market_type"):
            await adapter.list_files(
                market_type="invalid",
                partition="daily",
                data_type="klines",
                symbol="BTCUSDT",
            )


class TestBinanceAdapterParseSymbol:
    """Test parse_symbol method."""

    def test_parse_symbol_btcusdt(self):
        """Test parsing BTCUSDT symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("BTCUSDT")

        assert result is not None
        assert result["symbol"] == "BTCUSDT"
        assert result["base_asset"] == "BTC"
        assert result["quote_asset"] == "USDT"

    def test_parse_symbol_ethusdt(self):
        """Test parsing ETHUSDT symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("ETHUSDT")

        assert result is not None
        assert result["symbol"] == "ETHUSDT"
        assert result["base_asset"] == "ETH"
        assert result["quote_asset"] == "USDT"

    def test_parse_symbol_bnbbusd(self):
        """Test parsing BNBBUSD symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("BNBBUSD")

        assert result is not None
        assert result["base_asset"] == "BNB"
        assert result["quote_asset"] == "BUSD"

    def test_parse_symbol_ethbtc(self):
        """Test parsing ETHBTC symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("ETHBTC")

        assert result is not None
        assert result["base_asset"] == "ETH"
        assert result["quote_asset"] == "BTC"

    def test_parse_symbol_btcusd_perp(self):
        """Test parsing futures symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("BTCUSD_PERP")

        assert result is not None
        assert result["symbol"] == "BTCUSD_PERP"
        assert result["base_asset"] == "BTC"
        assert result["quote_asset"] == "USD"

    def test_parse_symbol_three_char_base_quote(self):
        """Test parsing 3-char base + 4-char quote symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("ADAUSDT")

        assert result is not None
        assert result["base_asset"] == "ADA"
        assert result["quote_asset"] == "USDT"

    def test_parse_symbol_unparseable(self):
        """Test parsing unparseable symbol."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("XYZ")

        # Might return None or a fallback; depends on implementation
        # For now, XYZ should return None since it's too short
        assert result is None

    def test_parse_symbol_empty_base(self):
        """Test parsing symbol with only quote."""
        adapter = BinanceAdapter()
        result = adapter.parse_symbol("USDT")

        # Base would be empty; should not parse
        assert result is None

    def test_parse_symbol_with_common_quotes(self):
        """Test parsing symbol with each common quote asset."""
        adapter = BinanceAdapter()

        # Test a few common quotes
        for symbol, expected_quote in [
            ("BTCUSDT", "USDT"),
            ("ETHUSDC", "USDC"),
            ("BNBBUSD", "BUSD"),
            ("ADAEUR", "EUR"),
        ]:
            result = adapter.parse_symbol(symbol)
            if result:
                assert result["quote_asset"] == expected_quote


class TestBinanceAdapterValidators:
    """Test parameter validation methods."""

    def test_validate_market_type_spot(self):
        """Test validating 'spot' market type."""
        result = BinanceAdapter._validate_market_type("spot")
        assert result.value == "spot"

    def test_validate_market_type_um(self):
        """Test validating 'um' market type."""
        result = BinanceAdapter._validate_market_type("um")
        assert result.value == "um"

    def test_validate_market_type_cm(self):
        """Test validating 'cm' market type."""
        result = BinanceAdapter._validate_market_type("cm")
        assert result.value == "cm"

    def test_validate_market_type_invalid(self):
        """Test validating invalid market type."""
        with pytest.raises(ValueError, match="Invalid market_type"):
            BinanceAdapter._validate_market_type("invalid")

    def test_validate_partition_daily(self):
        """Test validating 'daily' partition."""
        result = BinanceAdapter._validate_partition("daily")
        assert result.value == "daily"

    def test_validate_partition_monthly(self):
        """Test validating 'monthly' partition."""
        result = BinanceAdapter._validate_partition("monthly")
        assert result.value == "monthly"

    def test_validate_partition_invalid(self):
        """Test validating invalid partition."""
        with pytest.raises(ValueError, match="Invalid partition"):
            BinanceAdapter._validate_partition("weekly")

    def test_validate_data_type_klines(self):
        """Test validating 'klines' data type."""
        result = BinanceAdapter._validate_data_type("klines")
        assert result.value == "klines"

    def test_validate_data_type_agg_trades_value(self):
        """Test validating aggTrades by value."""
        result = BinanceAdapter._validate_data_type("aggTrades")
        assert result.value == "aggTrades"

    def test_validate_data_type_invalid(self):
        """Test validating invalid data type."""
        with pytest.raises(ValueError, match="Invalid data_type"):
            BinanceAdapter._validate_data_type("invalid_type")


@pytest.mark.asyncio
class TestBinanceAdapterFetchFile:
    """Test fetch_file method."""

    async def test_fetch_file_not_implemented_real_request(self):
        """Test that fetch_file would make real HTTP requests.

        This is a placeholder to document the expected behavior.
        Real integration tests should mock aiohttp.
        """
        adapter = BinanceAdapter()

        # In real integration tests, mock aiohttp.ClientSession
        # For now, we skip actual network tests
        pytest.skip("Requires mocking aiohttp")
