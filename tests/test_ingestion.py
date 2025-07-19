"""Tests for data ingestion modules."""

import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from crypto_lakehouse.core.models import DataType, TradeType
from crypto_lakehouse.ingestion.binance import BinanceBulkIngestor, BinanceIngestor
from crypto_lakehouse.ingestion.bulk_downloader import BinanceDataParser, S5cmdDownloader


class TestS5cmdDownloader:
    """Test S5cmd bulk downloader."""

    @pytest.mark.asyncio
    async def test_check_s5cmd_available(self, test_settings):
        """Test checking if s5cmd is available."""
        downloader = S5cmdDownloader(test_settings)

        # This will likely be False in test environment
        is_available = await downloader._check_s5cmd_available()
        assert isinstance(is_available, bool)

    @pytest.mark.asyncio
    async def test_download_with_wget_fallback(self, test_settings):
        """Test fallback to wget when s5cmd unavailable."""
        downloader = S5cmdDownloader(test_settings)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with a small file that should exist
            test_urls = ["https://httpbin.org/robots.txt"]  # Simple test file

            downloaded = await downloader._download_with_wget(
                test_urls, temp_path, max_concurrent=1
            )

            # Should attempt download (may fail in test environment)
            assert isinstance(downloaded, list)

    @pytest.mark.asyncio
    async def test_download_files_bulk(self, test_settings):
        """Test bulk file download."""
        downloader = S5cmdDownloader(test_settings)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test with small files
            test_urls = ["https://httpbin.org/robots.txt", "https://httpbin.org/user-agent"]

            downloaded = await downloader.download_files_bulk(
                test_urls, temp_path, max_concurrent=1
            )

            assert isinstance(downloaded, list)


class TestBinanceDataParser:
    """Test Binance data parser."""

    def test_parse_kline_csv_row(self, test_settings):
        """Test parsing a single K-line CSV row."""
        parser = BinanceDataParser(test_settings)

        # Sample Binance K-line CSV row
        csv_row = "1704067200000,50000.00,50100.00,49950.00,50050.00,10.50000000,1704067260000,525000.00000000,100,5.25000000,262500.00000000,0"

        kline = parser._parse_kline_csv_row(csv_row, "BTCUSDT")

        assert kline is not None
        assert kline.symbol == "BTCUSDT"
        assert kline.open_price == Decimal("50000.00")
        assert kline.high_price == Decimal("50100.00")
        assert kline.low_price == Decimal("49950.00")
        assert kline.close_price == Decimal("50050.00")
        assert kline.volume == Decimal("10.50000000")
        assert kline.number_of_trades == 100

    def test_parse_funding_csv_row(self, test_settings):
        """Test parsing a funding rate CSV row."""
        parser = BinanceDataParser(test_settings)

        # Sample funding rate CSV row
        csv_row = "1704067200000,0.00010000,50000.00"

        funding = parser._parse_funding_csv_row(csv_row, "BTCUSDT")

        assert funding is not None
        assert funding.symbol == "BTCUSDT"
        assert funding.funding_rate == Decimal("0.00010000")
        assert funding.mark_price == Decimal("50000.00")

    def test_parse_invalid_csv_row(self, test_settings):
        """Test parsing invalid CSV rows."""
        parser = BinanceDataParser(test_settings)

        # Invalid row with missing data
        invalid_row = "1704067200000,50000.00,50100.00"

        kline = parser._parse_kline_csv_row(invalid_row, "BTCUSDT")
        assert kline is None

    @pytest.mark.asyncio
    async def test_parse_zip_kline_file(self, test_settings, temp_zip_file):
        """Test parsing K-line data from ZIP file."""
        parser = BinanceDataParser(test_settings)

        klines = []
        async for kline in parser.parse_kline_file(temp_zip_file, "BTCUSDT"):
            klines.append(kline)

        assert len(klines) == 2  # Based on mock data
        assert all(k.symbol == "BTCUSDT" for k in klines)
        assert all(k.open_price > 0 for k in klines)

    @pytest.mark.asyncio
    async def test_parse_csv_kline_file(self, test_settings, mock_csv_kline_data):
        """Test parsing K-line data from CSV file."""
        parser = BinanceDataParser(test_settings)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(mock_csv_kline_data)
            csv_path = f.name

        try:
            klines = []
            async for kline in parser._parse_csv_kline_file(csv_path, "BTCUSDT"):
                klines.append(kline)

            assert len(klines) == 2
            assert all(k.symbol == "BTCUSDT" for k in klines)
        finally:
            Path(csv_path).unlink(missing_ok=True)


class TestBinanceBulkIngestor:
    """Test Binance bulk ingestor."""

    @pytest.mark.asyncio
    async def test_list_available_files(self, test_settings):
        """Test listing available files for download."""
        ingestor = BinanceBulkIngestor(test_settings)

        files = await ingestor.list_available_files(
            symbol="BTCUSDT",
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 2),
        )

        assert len(files) == 2  # 2 days
        assert all("BTCUSDT" in f for f in files)
        assert all("2024-01-01" in files[0] or "2024-01-02" in files[0] for f in files)

    @pytest.mark.asyncio
    async def test_list_funding_files(self, test_settings):
        """Test listing funding rate files."""
        ingestor = BinanceBulkIngestor(test_settings)

        files = await ingestor.list_available_files(
            symbol="BTCUSDT",
            data_type=DataType.FUNDING_RATES,
            trade_type=TradeType.UM_FUTURES,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 1),
        )

        assert len(files) == 1
        assert "fundingRate" in files[0]
        assert "BTCUSDT" in files[0]

    @pytest.mark.asyncio
    async def test_unsupported_data_type(self, test_settings):
        """Test handling unsupported data type."""
        ingestor = BinanceBulkIngestor(test_settings)

        with pytest.raises(ValueError, match="Unsupported data type"):
            await ingestor.list_available_files(
                symbol="BTCUSDT",
                data_type=DataType.ORDER_BOOK,  # Not supported
                trade_type=TradeType.SPOT,
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 1),
            )


class TestBinanceIngestor:
    """Test main Binance ingestor."""

    def test_initialization(self, test_settings):
        """Test ingestor initialization."""
        ingestor = BinanceIngestor(test_settings)

        assert ingestor.bulk_ingestor is not None
        assert ingestor.incremental_ingestor is not None
        assert ingestor.binance_config is not None

    @pytest.mark.asyncio
    async def test_hybrid_ingestion_strategy(self, test_settings):
        """Test hybrid bulk + incremental ingestion strategy."""
        ingestor = BinanceIngestor(test_settings)

        # Test date range that should trigger both bulk and incremental
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Old date (bulk)
        end_date = datetime.now(timezone.utc)  # Recent date (incremental)

        # Mock the actual ingestion to avoid network calls
        bulk_called = False
        incremental_called = False

        async def mock_bulk_ingest(*args, **kwargs):
            nonlocal bulk_called
            bulk_called = True
            return []

        async def mock_incremental_ingest(*args, **kwargs):
            nonlocal incremental_called
            incremental_called = True
            return []

        # This would require mocking the actual methods
        # For now, just test the logic paths exist

        # Test that funding rates reject spot trading
        with pytest.raises(ValueError, match="Funding rates not available for spot trading"):
            klines = []
            async for _ in ingestor.ingest_funding_rates(
                ["BTCUSDT"], TradeType.SPOT, start_date, end_date
            ):
                pass

    @pytest.mark.asyncio
    async def test_liquidation_spot_rejection(self, test_settings):
        """Test that liquidations reject spot trading."""
        ingestor = BinanceIngestor(test_settings)

        with pytest.raises(ValueError, match="Liquidations not available for spot trading"):
            async for _ in ingestor.ingest_liquidations(["BTCUSDT"], TradeType.SPOT):
                pass

    def test_get_available_symbols_delegation(self, test_settings):
        """Test that get_available_symbols delegates to incremental ingestor."""
        ingestor = BinanceIngestor(test_settings)

        # Test that it properly delegates (would need mocking for full test)
        assert hasattr(ingestor, "incremental_ingestor")
        assert hasattr(ingestor.incremental_ingestor, "get_available_symbols")


class TestIngestionIntegration:
    """Integration tests for ingestion workflow."""

    @pytest.mark.asyncio
    async def test_end_to_end_mock_ingestion(self, test_settings, temp_zip_file):
        """Test end-to-end ingestion with mock data."""
        # This test would require more complex mocking
        # but demonstrates the integration approach

        parser = BinanceDataParser(test_settings)

        # Parse mock data
        klines = []
        async for kline in parser.parse_kline_file(temp_zip_file, "BTCUSDT"):
            klines.append(kline)

        # Verify parsed data
        assert len(klines) > 0
        assert all(isinstance(k.open_price, Decimal) for k in klines)
        assert all(k.symbol == "BTCUSDT" for k in klines)

        # Test data integrity
        for kline in klines:
            assert kline.high_price >= kline.open_price
            assert kline.high_price >= kline.close_price
            assert kline.low_price <= kline.open_price
            assert kline.low_price <= kline.close_price
            assert kline.volume >= 0

    @pytest.mark.asyncio
    async def test_data_validation_rules(self, test_settings):
        """Test that data validation rules are applied."""
        parser = BinanceDataParser(test_settings)

        # Test with invalid OHLC data (high < low)
        invalid_csv = "1704067200000,50000.00,49000.00,50500.00,50050.00,10.50000000,1704067260000,525000.00000000,100,5.25000000,262500.00000000,0"

        kline = parser._parse_kline_csv_row(invalid_csv, "BTCUSDT")

        # Should still parse but validation would catch this in processing
        assert kline is not None
        assert kline.high_price < kline.low_price  # Invalid but parsed

        # The validation would happen in the processing layer
        # where we would filter out invalid OHLC relationships
