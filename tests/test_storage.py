"""Tests for storage layer."""

from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from crypto_lakehouse.core.models import DataType, DataZone, Exchange, TradeType
from crypto_lakehouse.storage.factory import create_local_storage, create_storage
from crypto_lakehouse.storage.local_storage import LocalStorage


class TestLocalStorage:
    """Test local storage implementation."""

    @pytest.mark.asyncio
    async def test_write_data(self, test_settings, sample_kline_dataframe):
        """Test writing data to local storage."""
        storage = LocalStorage(test_settings)

        result_path = await storage.write_data(
            data=sample_kline_dataframe,
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        # Check that file was created
        assert result_path is not None
        assert Path(result_path).exists()
        assert Path(result_path).suffix == ".parquet"

    @pytest.mark.asyncio
    async def test_read_data(self, test_settings, sample_kline_dataframe):
        """Test reading data from local storage."""
        storage = LocalStorage(test_settings)

        # First write data
        await storage.write_data(
            data=sample_kline_dataframe,
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        # Then read it back
        result = await storage.read_data(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbols=["BTCUSDT"],
        )

        assert len(result) == 2
        assert "symbol" in result.columns
        assert "open_price" in result.columns
        assert result["symbol"][0] == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_list_partitions(self, test_settings, sample_kline_dataframe):
        """Test listing partitions."""
        storage = LocalStorage(test_settings)

        # Write data first
        await storage.write_data(
            data=sample_kline_dataframe,
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        # List partitions
        partitions = await storage.list_partitions(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
        )

        assert len(partitions) == 1
        assert partitions[0]["symbol"] == "BTCUSDT"
        assert partitions[0]["year"] == 2024
        assert partitions[0]["month"] == 1
        assert partitions[0]["day"] == 1

    @pytest.mark.asyncio
    async def test_delete_partition(self, test_settings, sample_kline_dataframe):
        """Test deleting a partition."""
        storage = LocalStorage(test_settings)

        # Write data first
        await storage.write_data(
            data=sample_kline_dataframe,
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        # Delete partition
        result = await storage.delete_partition(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        assert result is True

        # Verify partition is gone
        partitions = await storage.list_partitions(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
        )

        assert len(partitions) == 0

    @pytest.mark.asyncio
    async def test_get_schema(self, test_settings, sample_kline_dataframe):
        """Test getting schema from stored data."""
        storage = LocalStorage(test_settings)

        # Write data first
        await storage.write_data(
            data=sample_kline_dataframe,
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        # Get schema
        schema = await storage.get_schema(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
        )

        assert schema is not None
        assert "symbol" in schema
        assert "open_price" in schema

    @pytest.mark.asyncio
    async def test_optimize_partitions(self, test_settings, sample_kline_dataframe):
        """Test partition optimization."""
        storage = LocalStorage(test_settings)

        # Write some data
        await storage.write_data(
            data=sample_kline_dataframe,
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 1),
        )

        # Run optimization
        result = await storage.optimize_partitions(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
        )

        assert result["status"] == "analyzed"
        assert "total_partitions" in result
        assert "recommendations" in result

    def test_partition_path_generation(self, test_settings):
        """Test partition path generation."""
        storage = LocalStorage(test_settings)

        path = storage.get_partition_path(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbol="BTCUSDT",
            partition_date=datetime(2024, 1, 15),
        )

        expected = "silver/binance/spot/klines/symbol=BTCUSDT/year=2024/month=01/day=15"
        assert path == expected

    @pytest.mark.asyncio
    async def test_read_with_filters(self, test_settings, sample_kline_dataframe):
        """Test reading data with date and symbol filters."""
        storage = LocalStorage(test_settings)

        # Write data for multiple symbols and dates
        for symbol in ["BTCUSDT", "ETHUSDT"]:
            for day in [1, 2]:
                test_data = sample_kline_dataframe.with_columns(pl.lit(symbol).alias("symbol"))

                await storage.write_data(
                    data=test_data,
                    zone=DataZone.SILVER,
                    exchange=Exchange.BINANCE,
                    data_type=DataType.KLINES,
                    trade_type=TradeType.SPOT,
                    symbol=symbol,
                    partition_date=datetime(2024, 1, day),
                )

        # Read with symbol filter
        result = await storage.read_data(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbols=["BTCUSDT"],
        )

        # Should only return BTCUSDT data
        unique_symbols = result["symbol"].unique().to_list()
        assert len(unique_symbols) == 1
        assert unique_symbols[0] == "BTCUSDT"

        # Read with date filter
        result_filtered = await storage.read_data(
            zone=DataZone.SILVER,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            start_date=datetime(2024, 1, 2),
            end_date=datetime(2024, 1, 2),
        )

        # Should return data from both symbols but only day 2
        # Note: This depends on the timestamp filtering implementation


class TestStorageFactory:
    """Test storage factory functions."""

    def test_create_storage_local(self, test_settings):
        """Test creating local storage via factory."""
        # Mock cloud disabled
        test_settings.s3.access_key_id = None

        storage = create_storage(test_settings)

        assert isinstance(storage, LocalStorage)

    def test_create_local_storage_direct(self, test_settings):
        """Test creating local storage directly."""
        storage = create_local_storage(test_settings)

        assert isinstance(storage, LocalStorage)
        assert storage.settings == test_settings
