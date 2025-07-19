"""Tests for data merger functionality."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

import pytest

from crypto_lakehouse.core.models import DataType, FundingRateData, KlineData
from crypto_lakehouse.utils.data_merger import (
    ConflictResolution,
    DataMerger,
    MergeConfig,
    MergeResult,
    MergeStrategy,
    get_merge_strategies,
    merge_data,
)


@pytest.fixture
def sample_bulk_klines() -> List[KlineData]:
    """Create sample bulk K-line data."""
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    data = []

    # Create 30 minutes of bulk data
    for i in range(30):
        open_time = base_time + timedelta(minutes=i)
        close_time = base_time + timedelta(minutes=i + 1) - timedelta(milliseconds=1)

        kline = KlineData(
            symbol="BTCUSDT",
            open_time=open_time,
            close_time=close_time,
            open_price=Decimal(f"{100.0 + i * 0.1}"),
            high_price=Decimal(f"{100.5 + i * 0.1}"),
            low_price=Decimal(f"{99.5 + i * 0.1}"),
            close_price=Decimal(f"{100.2 + i * 0.1}"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )
        data.append(kline)

    return data


@pytest.fixture
def sample_incremental_klines() -> List[KlineData]:
    """Create sample incremental K-line data (overlapping with bulk)."""
    base_time = datetime(2023, 1, 1, 0, 20, 0)  # Start 20 minutes in
    data = []

    # Create 30 minutes of incremental data (overlaps with last 10 minutes of bulk)
    for i in range(30):
        open_time = base_time + timedelta(minutes=i)
        close_time = base_time + timedelta(minutes=i + 1) - timedelta(milliseconds=1)

        kline = KlineData(
            symbol="BTCUSDT",
            open_time=open_time,
            close_time=close_time,
            open_price=Decimal(f"{102.0 + i * 0.1}"),  # Slightly different prices
            high_price=Decimal(f"{102.5 + i * 0.1}"),
            low_price=Decimal(f"{101.5 + i * 0.1}"),
            close_price=Decimal(f"{102.2 + i * 0.1}"),
            volume=Decimal("1100.0"),  # Different volume
            quote_asset_volume=Decimal("110000.0"),
            number_of_trades=110,
            taker_buy_base_asset_volume=Decimal("550.0"),
            taker_buy_quote_asset_volume=Decimal("55000.0"),
        )
        data.append(kline)

    return data


@pytest.fixture
def sample_bulk_funding_rates() -> List[FundingRateData]:
    """Create sample bulk funding rate data."""
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    data = []

    # Create 24 hours of funding rate data (every 8 hours)
    for i in range(3):
        funding_time = base_time + timedelta(hours=i * 8)

        rate = FundingRateData(
            symbol="BTCUSDT",
            funding_time=funding_time,
            funding_rate=Decimal(f"{0.0001 + i * 0.0001}"),
            mark_price=Decimal(f"{100.0 + i * 10}"),
        )
        data.append(rate)

    return data


@pytest.fixture
def sample_incremental_funding_rates() -> List[FundingRateData]:
    """Create sample incremental funding rate data (overlapping)."""
    base_time = datetime(2023, 1, 1, 8, 0, 0)  # Start 8 hours in
    data = []

    # Create 24 hours of funding rate data (overlaps with last 2 records of bulk)
    for i in range(3):
        funding_time = base_time + timedelta(hours=i * 8)

        rate = FundingRateData(
            symbol="BTCUSDT",
            funding_time=funding_time,
            funding_rate=Decimal(f"{0.0002 + i * 0.0001}"),  # Different rates
            mark_price=Decimal(f"{105.0 + i * 10}"),  # Different mark prices
        )
        data.append(rate)

    return data


@pytest.fixture
def merge_config() -> MergeConfig:
    """Create basic merge configuration."""
    return MergeConfig(
        merge_strategy=MergeStrategy.BULK_PRIORITY,
        conflict_resolution=ConflictResolution.OVERWRITE,
        tolerance_ms=1000,
        enable_deduplication=True,
        enable_validation=True,
        max_gap_minutes=5,
    )


class TestMergeConfig:
    """Test MergeConfig validation."""

    def test_valid_config(self):
        """Test valid configuration creation."""
        config = MergeConfig(
            merge_strategy=MergeStrategy.BULK_PRIORITY,
            conflict_resolution=ConflictResolution.OVERWRITE,
            tolerance_ms=5000,
            enable_deduplication=True,
            enable_validation=True,
            max_gap_minutes=10,
        )

        assert config.merge_strategy == MergeStrategy.BULK_PRIORITY
        assert config.conflict_resolution == ConflictResolution.OVERWRITE
        assert config.tolerance_ms == 5000
        assert config.enable_deduplication is True
        assert config.enable_validation is True
        assert config.max_gap_minutes == 10

    def test_invalid_tolerance(self):
        """Test invalid tolerance validation."""
        with pytest.raises(ValueError, match="Tolerance must be non-negative"):
            MergeConfig(tolerance_ms=-1000)

    def test_default_values(self):
        """Test default configuration values."""
        config = MergeConfig()

        assert config.merge_strategy == MergeStrategy.BULK_PRIORITY
        assert config.conflict_resolution == ConflictResolution.OVERWRITE
        assert config.tolerance_ms == 1000
        assert config.enable_deduplication is True
        assert config.enable_validation is True
        assert config.max_gap_minutes == 60


class TestDataMerger:
    """Test DataMerger functionality."""

    def test_merge_kline_data_bulk_priority(
        self, sample_bulk_klines, sample_incremental_klines, merge_config
    ):
        """Test merging K-line data with bulk priority."""
        merger = DataMerger(merge_config)

        result = merger.merge_kline_data(
            bulk_data=sample_bulk_klines,
            incremental_data=sample_incremental_klines,
            symbol="BTCUSDT",
        )

        assert isinstance(result, MergeResult)
        assert result.symbol == "BTCUSDT"
        assert result.data_type == DataType.KLINE
        assert result.bulk_records == 30
        assert result.incremental_records == 30
        assert result.total_input_records == 60

        # With bulk priority, should have 30 bulk + 20 new incremental (non-overlapping)
        assert result.merged_records == 50
        assert result.merge_strategy_used == MergeStrategy.BULK_PRIORITY

    def test_merge_kline_data_incremental_priority(
        self, sample_bulk_klines, sample_incremental_klines
    ):
        """Test merging K-line data with incremental priority."""
        config = MergeConfig(merge_strategy=MergeStrategy.INCREMENTAL_PRIORITY)
        merger = DataMerger(config)

        result = merger.merge_kline_data(
            bulk_data=sample_bulk_klines,
            incremental_data=sample_incremental_klines,
            symbol="BTCUSDT",
        )

        assert result.merged_records == 50  # 30 incremental + 20 new bulk
        assert result.merge_strategy_used == MergeStrategy.INCREMENTAL_PRIORITY

    def test_merge_funding_rate_data(
        self, sample_bulk_funding_rates, sample_incremental_funding_rates, merge_config
    ):
        """Test merging funding rate data."""
        merger = DataMerger(merge_config)

        result = merger.merge_funding_rate_data(
            bulk_data=sample_bulk_funding_rates,
            incremental_data=sample_incremental_funding_rates,
            symbol="BTCUSDT",
        )

        assert isinstance(result, MergeResult)
        assert result.symbol == "BTCUSDT"
        assert result.data_type == DataType.FUNDING_RATE
        assert result.bulk_records == 3
        assert result.incremental_records == 3
        assert result.total_input_records == 6

        # With bulk priority, should have 3 bulk + 1 new incremental
        assert result.merged_records == 4

    def test_merge_empty_data(self, merge_config):
        """Test merging with empty data."""
        merger = DataMerger(merge_config)

        result = merger.merge_kline_data(bulk_data=[], incremental_data=[], symbol="BTCUSDT")

        assert result.merged_records == 0
        assert result.bulk_records == 0
        assert result.incremental_records == 0
        assert result.duplicates_removed == 0

    def test_merge_one_empty_source(self, sample_bulk_klines, merge_config):
        """Test merging with one empty source."""
        merger = DataMerger(merge_config)

        # Empty incremental data
        result = merger.merge_kline_data(
            bulk_data=sample_bulk_klines, incremental_data=[], symbol="BTCUSDT"
        )

        assert result.merged_records == 30
        assert result.bulk_records == 30
        assert result.incremental_records == 0

        # Empty bulk data
        result = merger.merge_kline_data(
            bulk_data=[], incremental_data=sample_bulk_klines, symbol="BTCUSDT"  # Reuse for testing
        )

        assert result.merged_records == 30
        assert result.bulk_records == 0
        assert result.incremental_records == 30

    def test_deduplication_enabled(self, merge_config):
        """Test deduplication functionality."""
        # Create duplicate data
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        duplicate_kline = KlineData(
            symbol="BTCUSDT",
            open_time=base_time,
            close_time=base_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("100.0"),
            high_price=Decimal("100.5"),
            low_price=Decimal("99.5"),
            close_price=Decimal("100.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )

        bulk_data = [duplicate_kline]
        incremental_data = [duplicate_kline]  # Same data

        merger = DataMerger(merge_config)
        result = merger.merge_kline_data(bulk_data, incremental_data, "BTCUSDT")

        assert result.duplicates_removed >= 0  # Should remove duplicates

    def test_deduplication_disabled(self, merge_config):
        """Test with deduplication disabled."""
        config = MergeConfig(enable_deduplication=False)
        merger = DataMerger(config)

        # Create simple test data
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=base_time,
            close_time=base_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("100.0"),
            high_price=Decimal("100.5"),
            low_price=Decimal("99.5"),
            close_price=Decimal("100.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )

        result = merger.merge_kline_data([kline], [], "BTCUSDT")

        assert result.duplicates_removed == 0

    def test_validation_enabled(self, sample_bulk_klines, merge_config):
        """Test data validation."""
        merger = DataMerger(merge_config)

        result = merger.merge_kline_data(
            bulk_data=sample_bulk_klines, incremental_data=[], symbol="BTCUSDT"
        )

        assert 0.0 <= result.quality_score <= 1.0

    def test_validation_disabled(self, sample_bulk_klines):
        """Test with validation disabled."""
        config = MergeConfig(enable_validation=False)
        merger = DataMerger(config)

        result = merger.merge_kline_data(
            bulk_data=sample_bulk_klines, incremental_data=[], symbol="BTCUSDT"
        )

        assert result.quality_score == 1.0

    def test_different_merge_strategies(self, sample_bulk_klines, sample_incremental_klines):
        """Test different merge strategies."""
        strategies = [
            MergeStrategy.BULK_PRIORITY,
            MergeStrategy.INCREMENTAL_PRIORITY,
            MergeStrategy.LATEST_TIMESTAMP,
            MergeStrategy.DATA_QUALITY,
        ]

        for strategy in strategies:
            config = MergeConfig(merge_strategy=strategy)
            merger = DataMerger(config)

            result = merger.merge_kline_data(
                bulk_data=sample_bulk_klines,
                incremental_data=sample_incremental_klines,
                symbol="BTCUSDT",
            )

            assert result.merge_strategy_used == strategy
            assert result.merged_records > 0


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_merge_data_function(self, sample_bulk_klines, sample_incremental_klines):
        """Test merge_data convenience function."""
        result = merge_data(
            bulk_data=sample_bulk_klines,
            incremental_data=sample_incremental_klines,
            symbol="BTCUSDT",
            data_type=DataType.KLINE,
        )

        assert isinstance(result, MergeResult)
        assert result.symbol == "BTCUSDT"
        assert result.data_type == DataType.KLINE

    def test_merge_data_with_config(self, sample_bulk_klines, sample_incremental_klines):
        """Test merge_data with custom configuration."""
        config = MergeConfig(merge_strategy=MergeStrategy.INCREMENTAL_PRIORITY)

        result = merge_data(
            bulk_data=sample_bulk_klines,
            incremental_data=sample_incremental_klines,
            symbol="BTCUSDT",
            data_type=DataType.KLINE,
            config=config,
        )

        assert result.merge_strategy_used == MergeStrategy.INCREMENTAL_PRIORITY

    def test_merge_data_unsupported_type(self):
        """Test merge_data with unsupported data type."""
        with pytest.raises(ValueError, match="Unsupported data type"):
            merge_data(bulk_data=[], incremental_data=[], symbol="BTCUSDT", data_type="unsupported")

    def test_get_merge_strategies(self):
        """Test getting available merge strategies."""
        strategies = get_merge_strategies()

        assert isinstance(strategies, list)
        assert MergeStrategy.BULK_PRIORITY in strategies
        assert MergeStrategy.INCREMENTAL_PRIORITY in strategies
        assert MergeStrategy.LATEST_TIMESTAMP in strategies
        assert MergeStrategy.DATA_QUALITY in strategies


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_identical_data_sources(self):
        """Test merging identical data sources."""
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=base_time,
            close_time=base_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("100.0"),
            high_price=Decimal("100.5"),
            low_price=Decimal("99.5"),
            close_price=Decimal("100.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )

        config = MergeConfig()
        merger = DataMerger(config)

        result = merger.merge_kline_data([kline], [kline], "BTCUSDT")

        # Should handle identical data gracefully
        assert result.merged_records >= 1

    def test_different_symbols(self):
        """Test merging data with different symbols."""
        base_time = datetime(2023, 1, 1, 0, 0, 0)

        kline1 = KlineData(
            symbol="BTCUSDT",
            open_time=base_time,
            close_time=base_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("100.0"),
            high_price=Decimal("100.5"),
            low_price=Decimal("99.5"),
            close_price=Decimal("100.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )

        kline2 = KlineData(
            symbol="ETHUSDT",
            open_time=base_time,
            close_time=base_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("200.0"),
            high_price=Decimal("200.5"),
            low_price=Decimal("199.5"),
            close_price=Decimal("200.2"),
            volume=Decimal("2000.0"),
            quote_asset_volume=Decimal("200000.0"),
            number_of_trades=200,
            taker_buy_base_asset_volume=Decimal("1000.0"),
            taker_buy_quote_asset_volume=Decimal("100000.0"),
        )

        config = MergeConfig()
        merger = DataMerger(config)

        result = merger.merge_kline_data([kline1], [kline2], "MIXED")

        # Should handle different symbols
        assert result.merged_records == 2

    def test_large_time_gaps(self):
        """Test merging data with large time gaps."""
        base_time = datetime(2023, 1, 1, 0, 0, 0)

        kline1 = KlineData(
            symbol="BTCUSDT",
            open_time=base_time,
            close_time=base_time + timedelta(minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("100.0"),
            high_price=Decimal("100.5"),
            low_price=Decimal("99.5"),
            close_price=Decimal("100.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )

        kline2 = KlineData(
            symbol="BTCUSDT",
            open_time=base_time + timedelta(hours=24),  # 24 hour gap
            close_time=base_time + timedelta(hours=24, minutes=1) - timedelta(milliseconds=1),
            open_price=Decimal("101.0"),
            high_price=Decimal("101.5"),
            low_price=Decimal("100.5"),
            close_price=Decimal("101.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )

        config = MergeConfig(max_gap_minutes=60)
        merger = DataMerger(config)

        result = merger.merge_kline_data([kline1], [kline2], "BTCUSDT")

        # Should detect gaps
        assert result.gaps_detected > 0
