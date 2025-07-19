"""Tests for core data models."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from crypto_lakehouse.core.models import (
    DataIngestionTask,
    DataType,
    DataZone,
    Exchange,
    FundingRateData,
    IngestionMetadata,
    Interval,
    KlineData,
    TradeType,
)


class TestEnums:
    """Test enum definitions."""

    def test_exchange_enum(self):
        """Test Exchange enum values."""
        assert Exchange.BINANCE == "binance"
        assert Exchange.COINBASE == "coinbase"
        assert Exchange.KRAKEN == "kraken"

    def test_data_type_enum(self):
        """Test DataType enum values."""
        assert DataType.KLINES == "klines"
        assert DataType.FUNDING_RATES == "funding_rates"
        assert DataType.LIQUIDATIONS == "liquidations"

    def test_trade_type_enum(self):
        """Test TradeType enum values."""
        assert TradeType.SPOT == "spot"
        assert TradeType.UM_FUTURES == "um_futures"
        assert TradeType.CM_FUTURES == "cm_futures"

    def test_interval_enum(self):
        """Test Interval enum values."""
        assert Interval.MIN_1 == "1m"
        assert Interval.HOUR_1 == "1h"
        assert Interval.DAY_1 == "1d"


class TestKlineData:
    """Test KlineData model."""

    def test_kline_data_creation(self):
        """Test creating KlineData instance."""
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            close_time=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            open_price=Decimal("50000.00"),
            high_price=Decimal("50100.00"),
            low_price=Decimal("49950.00"),
            close_price=Decimal("50050.00"),
            volume=Decimal("10.5"),
            quote_asset_volume=Decimal("525000.00"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("5.25"),
            taker_buy_quote_asset_volume=Decimal("262500.00"),
        )

        assert kline.symbol == "BTCUSDT"
        assert kline.open_price == Decimal("50000.00")
        assert kline.high_price == Decimal("50100.00")
        assert kline.number_of_trades == 100

    def test_kline_data_with_enhanced_fields(self):
        """Test KlineData with enhanced fields."""
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            close_time=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            open_price=Decimal("50000.00"),
            high_price=Decimal("50100.00"),
            low_price=Decimal("49950.00"),
            close_price=Decimal("50050.00"),
            volume=Decimal("10.5"),
            quote_asset_volume=Decimal("525000.00"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("5.25"),
            taker_buy_quote_asset_volume=Decimal("262500.00"),
            vwap=Decimal("50025.00"),
            returns=Decimal("0.1"),
            log_returns=Decimal("0.000999"),
        )

        assert kline.vwap == Decimal("50025.00")
        assert kline.returns == Decimal("0.1")
        assert kline.log_returns == Decimal("0.000999")

    def test_kline_data_immutable(self):
        """Test that KlineData is immutable."""
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            close_time=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            open_price=Decimal("50000.00"),
            high_price=Decimal("50100.00"),
            low_price=Decimal("49950.00"),
            close_price=Decimal("50050.00"),
            volume=Decimal("10.5"),
            quote_asset_volume=Decimal("525000.00"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("5.25"),
            taker_buy_quote_asset_volume=Decimal("262500.00"),
        )

        with pytest.raises(Exception):  # Should raise validation error for frozen model
            kline.symbol = "ETHUSDT"


class TestFundingRateData:
    """Test FundingRateData model."""

    def test_funding_rate_creation(self):
        """Test creating FundingRateData instance."""
        funding = FundingRateData(
            symbol="BTCUSDT",
            funding_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            funding_rate=Decimal("0.0001"),
            mark_price=Decimal("50000.00"),
        )

        assert funding.symbol == "BTCUSDT"
        assert funding.funding_rate == Decimal("0.0001")
        assert funding.mark_price == Decimal("50000.00")

    def test_funding_rate_optional_mark_price(self):
        """Test FundingRateData with optional mark price."""
        funding = FundingRateData(
            symbol="BTCUSDT",
            funding_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            funding_rate=Decimal("0.0001"),
        )

        assert funding.mark_price is None


class TestDataIngestionTask:
    """Test DataIngestionTask model."""

    def test_ingestion_task_creation(self):
        """Test creating DataIngestionTask instance."""
        task = DataIngestionTask(
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbols=["BTCUSDT", "ETHUSDT"],
            interval=Interval.MIN_1,
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        assert task.exchange == Exchange.BINANCE
        assert task.data_type == DataType.KLINES
        assert len(task.symbols) == 2
        assert task.interval == Interval.MIN_1

    def test_ingestion_task_defaults(self):
        """Test DataIngestionTask default values."""
        task = DataIngestionTask(
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbols=["BTCUSDT"],
        )

        assert task.force_update is False
        assert task.enable_validation is True
        assert task.target_zone == DataZone.SILVER


class TestIngestionMetadata:
    """Test IngestionMetadata model."""

    def test_metadata_creation(self):
        """Test creating IngestionMetadata instance."""
        metadata = IngestionMetadata(
            task_id="test_task_123",
            status="started",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert metadata.task_id == "test_task_123"
        assert metadata.status == "started"
        assert metadata.records_processed == 0
        assert metadata.errors == []

    def test_metadata_with_data(self):
        """Test IngestionMetadata with processing data."""
        metadata = IngestionMetadata(
            task_id="test_task_123",
            status="completed",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            records_processed=1000,
            bytes_processed=50000,
            source_files=["file1.zip", "file2.zip"],
            output_files=["output1.parquet", "output2.parquet"],
        )

        assert metadata.records_processed == 1000
        assert metadata.bytes_processed == 50000
        assert len(metadata.source_files) == 2
        assert len(metadata.output_files) == 2
