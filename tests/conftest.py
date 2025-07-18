"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
import polars as pl

from src.crypto_lakehouse.core.config import Settings
from src.crypto_lakehouse.core.models import (
    Exchange, DataType, TradeType, Interval, 
    KlineData, FundingRateData, DataIngestionTask
)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Create test settings with temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        settings = Settings(
            environment="test",
            debug=True,
            local_data_dir=Path(temp_dir),
            storage__base_path=f"file://{temp_dir}",
            s3__bucket_name="test-bucket",
            workflow__concurrency_limit=2,
            processing__batch_size=100
        )
        yield settings


@pytest.fixture
def sample_kline_data():
    """Create sample K-line data for testing."""
    return [
        KlineData(
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
            taker_buy_quote_asset_volume=Decimal("262500.00")
        ),
        KlineData(
            symbol="BTCUSDT",
            open_time=datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            close_time=datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc),
            open_price=Decimal("50050.00"),
            high_price=Decimal("50200.00"),
            low_price=Decimal("50000.00"),
            close_price=Decimal("50150.00"),
            volume=Decimal("8.3"),
            quote_asset_volume=Decimal("416250.00"),
            number_of_trades=85,
            taker_buy_base_asset_volume=Decimal("4.15"),
            taker_buy_quote_asset_volume=Decimal("208125.00")
        )
    ]


@pytest.fixture
def sample_funding_data():
    """Create sample funding rate data for testing."""
    return [
        FundingRateData(
            symbol="BTCUSDT",
            funding_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            funding_rate=Decimal("0.0001"),
            mark_price=Decimal("50000.00")
        ),
        FundingRateData(
            symbol="BTCUSDT",
            funding_time=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
            funding_rate=Decimal("0.0002"),
            mark_price=Decimal("50100.00")
        )
    ]


@pytest.fixture
def sample_kline_dataframe():
    """Create sample K-line Polars DataFrame."""
    return pl.DataFrame({
        "symbol": ["BTCUSDT", "BTCUSDT"],
        "open_time": [
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc)
        ],
        "close_time": [
            datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc)
        ],
        "open_price": [50000.0, 50050.0],
        "high_price": [50100.0, 50200.0],
        "low_price": [49950.0, 50000.0],
        "close_price": [50050.0, 50150.0],
        "volume": [10.5, 8.3],
        "quote_asset_volume": [525000.0, 416250.0],
        "number_of_trades": [100, 85],
        "taker_buy_base_asset_volume": [5.25, 4.15],
        "taker_buy_quote_asset_volume": [262500.0, 208125.0]
    })


@pytest.fixture
def sample_ingestion_task():
    """Create sample data ingestion task."""
    return DataIngestionTask(
        exchange=Exchange.BINANCE,
        data_type=DataType.KLINES,
        trade_type=TradeType.SPOT,
        symbols=["BTCUSDT", "ETHUSDT"],
        interval=Interval.MIN_1,
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 1, 2, tzinfo=timezone.utc),
        force_update=False,
        enable_validation=True
    )


@pytest.fixture
def mock_csv_kline_data():
    """Mock CSV data for K-line testing."""
    return """1704067200000,50000.00,50100.00,49950.00,50050.00,10.50000000,1704067260000,525000.00000000,100,5.25000000,262500.00000000,0
1704067260000,50050.00,50200.00,50000.00,50150.00,8.30000000,1704067320000,416250.00000000,85,4.15000000,208125.00000000,0"""


@pytest.fixture
def mock_csv_funding_data():
    """Mock CSV data for funding rate testing."""
    return """1704067200000,0.00010000,50000.00
1704096000000,0.00020000,50100.00"""


@pytest.fixture
def temp_zip_file(tmp_path, mock_csv_kline_data):
    """Create temporary ZIP file with CSV data."""
    import zipfile
    
    zip_path = tmp_path / "test_data.zip"
    csv_path = "BTCUSDT-1m-2024-01-01.csv"
    
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr(csv_path, mock_csv_kline_data)
    
    return str(zip_path)