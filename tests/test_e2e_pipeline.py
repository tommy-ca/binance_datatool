"""End-to-end integration tests for the crypto data lakehouse."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crypto_lakehouse.core.config import S3Config, Settings, StorageConfig
from crypto_lakehouse.core.models import DataType, FundingRateData, KlineData
from crypto_lakehouse.workflows.prefect_workflows import (
    daily_data_refresh_pipeline,
    data_ingestion_pipeline,
    ingest_bulk_data,
    ingest_incremental_data,
    merge_data_sources,
    multi_symbol_ingestion_pipeline,
    setup_clients,
    validate_data_quality,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        s3=S3Config(enabled=False, bucket="test-bucket", region="us-east-1"),
        storage=StorageConfig(local_path="/tmp/test-lakehouse"),
    )


@pytest.fixture
def sample_kline_data():
    """Create sample K-line data for testing."""
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    data = []

    for i in range(5):
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=base_time + timedelta(minutes=i),
            close_time=base_time + timedelta(minutes=i + 1) - timedelta(milliseconds=1),
            open_price=Decimal(f"{100.0 + i}"),
            high_price=Decimal(f"{100.5 + i}"),
            low_price=Decimal(f"{99.5 + i}"),
            close_price=Decimal(f"{100.2 + i}"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0"),
        )
        data.append(kline)

    return data


@pytest.fixture
def sample_funding_rate_data():
    """Create sample funding rate data for testing."""
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    data = []

    for i in range(3):
        rate = FundingRateData(
            symbol="BTCUSDT",
            funding_time=base_time + timedelta(hours=i * 8),
            funding_rate=Decimal(f"{0.0001 + i * 0.0001}"),
            mark_price=Decimal(f"{100.0 + i * 10}"),
        )
        data.append(rate)

    return data


class TestWorkflowTasks:
    """Test individual workflow tasks."""

    @pytest.mark.asyncio
    async def test_setup_clients(self, mock_settings):
        """Test client setup task."""
        with (
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.BinanceIngestionClient"
            ) as mock_ingestion,
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.S3LakehouseStorage"
            ) as mock_storage,
        ):

            mock_ingestion.return_value = Mock()
            mock_storage.return_value = Mock()

            clients = await setup_clients(mock_settings)

            assert "ingestion" in clients
            assert "storage" in clients
            mock_ingestion.assert_called_once_with(mock_settings)
            mock_storage.assert_called_once_with(mock_settings)

    @pytest.mark.asyncio
    async def test_ingest_bulk_data(self, mock_settings, sample_kline_data):
        """Test bulk data ingestion task."""
        mock_ingestion_client = AsyncMock()
        mock_ingestion_client.ingest_kline_data.return_value = sample_kline_data

        clients = {"ingestion": mock_ingestion_client}

        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)

        result = await ingest_bulk_data(clients, "BTCUSDT", DataType.KLINE, start_date, end_date)

        assert result == sample_kline_data
        mock_ingestion_client.ingest_kline_data.assert_called_once_with(
            symbol="BTCUSDT", interval="1m", start_time=start_date, end_time=end_date, use_bulk=True
        )

    @pytest.mark.asyncio
    async def test_ingest_incremental_data(self, mock_settings, sample_kline_data):
        """Test incremental data ingestion task."""
        mock_ingestion_client = AsyncMock()
        mock_ingestion_client.ingest_kline_data.return_value = sample_kline_data

        clients = {"ingestion": mock_ingestion_client}

        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)

        result = await ingest_incremental_data(
            clients, "BTCUSDT", DataType.KLINE, start_date, end_date
        )

        assert result == sample_kline_data
        mock_ingestion_client.ingest_kline_data.assert_called_once_with(
            symbol="BTCUSDT",
            interval="1m",
            start_time=start_date,
            end_time=end_date,
            use_bulk=False,
        )

    @pytest.mark.asyncio
    async def test_merge_data_sources(self, sample_kline_data):
        """Test data merging task."""
        bulk_data = sample_kline_data[:3]
        incremental_data = sample_kline_data[2:]  # Some overlap

        with patch(
            "crypto_lakehouse.workflows.prefect_workflows.DataMerger"
        ) as mock_merger_class:
            mock_merger = Mock()
            mock_merge_result = Mock()
            mock_merge_result.merged_records = 5
            mock_merger.merge_kline_data.return_value = mock_merge_result
            mock_merger_class.return_value = mock_merger

            result = await merge_data_sources(
                bulk_data, incremental_data, "BTCUSDT", DataType.KLINE
            )

            assert "merge_result" in result
            assert result["merge_result"] == mock_merge_result
            mock_merger.merge_kline_data.assert_called_once_with(
                bulk_data, incremental_data, "BTCUSDT"
            )

    @pytest.mark.asyncio
    async def test_validate_data_quality(self, sample_kline_data):
        """Test data quality validation task."""
        result = await validate_data_quality(sample_kline_data, "BTCUSDT", DataType.KLINE)

        assert "total_records" in result
        assert "quality_score" in result
        assert result["total_records"] == len(sample_kline_data)
        assert 0 <= result["quality_score"] <= 1


class TestWorkflowIntegration:
    """Test complete workflow integration."""

    @pytest.mark.asyncio
    async def test_data_ingestion_pipeline_mocked(self, mock_settings, sample_kline_data):
        """Test complete data ingestion pipeline with mocked components."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)

        # Mock all the components
        with (
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.BinanceIngestionClient"
            ) as mock_ingestion_class,
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.S3LakehouseStorage"
            ) as mock_storage_class,
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.GapDetector"
            ) as mock_gap_detector_class,
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.DataMerger"
            ) as mock_merger_class,
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.KlineProcessor"
            ) as mock_processor_class,
            patch(
                "crypto_lakehouse.workflows.prefect_workflows.DataResampler"
            ) as mock_resampler_class,
        ):

            # Setup mocks
            mock_ingestion = AsyncMock()
            mock_ingestion.ingest_kline_data.return_value = sample_kline_data
            mock_ingestion_class.return_value = mock_ingestion

            mock_storage = AsyncMock()
            mock_storage.store_kline_data.return_value = {"stored": True}
            mock_storage_class.return_value = mock_storage

            mock_gap_detector = Mock()
            mock_gap_detector.detect_kline_gaps.return_value = []
            mock_gap_detector.calculate_completeness.return_value = 100.0
            mock_gap_detector_class.return_value = mock_gap_detector

            mock_merger = Mock()
            mock_merge_result = Mock()
            mock_merge_result.merged_records = 5
            mock_merge_result.merge_strategy_used = "bulk_priority"
            mock_merge_result.duplicates_removed = 0
            mock_merge_result.conflicts_resolved = 0
            mock_merger.merge_kline_data.return_value = mock_merge_result
            mock_merger_class.return_value = mock_merger

            mock_processor = Mock()
            mock_processor.process_klines.return_value = sample_kline_data
            mock_processor_class.return_value = mock_processor

            mock_resampler = Mock()
            mock_resample_result = Mock()
            mock_resample_result.target_records = 1
            mock_resampler.resample_klines.return_value = mock_resample_result
            mock_resampler_class.return_value = mock_resampler

            # Mock Prefect artifacts
            with patch(
                "crypto_lakehouse.workflows.prefect_workflows.create_markdown_artifact"
            ) as mock_artifact:
                mock_artifact.return_value = AsyncMock()

                # Run the pipeline
                result = await data_ingestion_pipeline(
                    symbol="BTCUSDT",
                    data_type=DataType.KLINE,
                    start_date=start_date,
                    end_date=end_date,
                    settings=mock_settings,
                )

                # Verify results
                assert result["symbol"] == "BTCUSDT"
                assert result["data_type"] == DataType.KLINE
                assert result["processed_records"] == len(sample_kline_data)
                assert "quality_score" in result
                assert "storage_result" in result
                assert "resampled_timeframes" in result
                assert "report" in result

    @pytest.mark.asyncio
    async def test_multi_symbol_ingestion_pipeline_mocked(self, mock_settings):
        """Test multi-symbol ingestion pipeline with mocked components."""
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)

        # Mock the data_ingestion_pipeline function
        with patch(
            "crypto_lakehouse.workflows.prefect_workflows.data_ingestion_pipeline"
        ) as mock_pipeline:
            mock_pipeline.return_value = {
                "symbol": "BTCUSDT",
                "processed_records": 100,
                "quality_score": 0.95,
            }

            result = await multi_symbol_ingestion_pipeline(
                symbols=symbols,
                data_type=DataType.KLINE,
                start_date=start_date,
                end_date=end_date,
                settings=mock_settings,
            )

            # Verify results
            assert result["successful_symbols"] == symbols
            assert result["failed_symbols"] == []
            assert result["total_records"] == 300  # 100 * 3 symbols
            assert result["success_rate"] == 1.0

            # Verify pipeline was called for each symbol
            assert mock_pipeline.call_count == len(symbols)

    @pytest.mark.asyncio
    async def test_daily_data_refresh_pipeline_mocked(self, mock_settings):
        """Test daily data refresh pipeline with mocked components."""
        symbols = ["BTCUSDT", "ETHUSDT"]
        data_types = [DataType.KLINE, DataType.FUNDING_RATE]

        # Mock the data_ingestion_pipeline function
        with patch(
            "crypto_lakehouse.workflows.prefect_workflows.data_ingestion_pipeline"
        ) as mock_pipeline:
            mock_pipeline.return_value = {
                "symbol": "BTCUSDT",
                "processed_records": 50,
                "quality_score": 0.9,
            }

            result = await daily_data_refresh_pipeline(
                symbols=symbols, data_types=data_types, settings=mock_settings
            )

            # Verify results
            expected_runs = len(symbols) * len(data_types)  # 2 * 2 = 4
            assert result["successful_runs"] == expected_runs
            assert result["failed_runs"] == 0
            assert result["total_records"] == 200  # 50 * 4 runs
            assert result["success_rate"] == 1.0
            assert "date_range" in result

            # Verify pipeline was called for each symbol/data_type combination
            assert mock_pipeline.call_count == expected_runs


class TestErrorHandling:
    """Test error handling in workflows."""

    @pytest.mark.asyncio
    async def test_ingestion_failure_handling(self, mock_settings):
        """Test handling of ingestion failures."""
        mock_ingestion_client = AsyncMock()
        mock_ingestion_client.ingest_kline_data.side_effect = Exception("Ingestion failed")

        clients = {"ingestion": mock_ingestion_client}

        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)

        with pytest.raises(Exception, match="Ingestion failed"):
            await ingest_bulk_data(clients, "BTCUSDT", DataType.KLINE, start_date, end_date)

    @pytest.mark.asyncio
    async def test_multi_symbol_partial_failure(self, mock_settings):
        """Test multi-symbol pipeline with partial failures."""
        symbols = ["BTCUSDT", "ETHUSDT", "INVALID"]
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 1, 2)

        def mock_pipeline_side_effect(symbol, data_type, start_date, end_date, settings):
            if symbol == "INVALID":
                raise Exception("Invalid symbol")
            return {"symbol": symbol, "processed_records": 100, "quality_score": 0.95}

        with patch(
            "crypto_lakehouse.workflows.prefect_workflows.data_ingestion_pipeline"
        ) as mock_pipeline:
            mock_pipeline.side_effect = mock_pipeline_side_effect

            result = await multi_symbol_ingestion_pipeline(
                symbols=symbols,
                data_type=DataType.KLINE,
                start_date=start_date,
                end_date=end_date,
                settings=mock_settings,
            )

            # Verify partial success
            assert len(result["successful_symbols"]) == 2
            assert len(result["failed_symbols"]) == 1
            assert result["failed_symbols"][0]["symbol"] == "INVALID"
            assert result["success_rate"] == 2 / 3


class TestPerformance:
    """Test performance aspects of workflows."""

    @pytest.mark.asyncio
    async def test_concurrent_execution(self, mock_settings):
        """Test that workflows execute tasks concurrently."""
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        execution_times = []

        async def mock_pipeline_with_delay(symbol, data_type, start_date, end_date, settings):
            import time

            start_time = time.time()
            await asyncio.sleep(0.1)  # Simulate processing time
            end_time = time.time()
            execution_times.append(end_time - start_time)
            return {"symbol": symbol, "processed_records": 100, "quality_score": 0.95}

        with patch(
            "crypto_lakehouse.workflows.prefect_workflows.data_ingestion_pipeline"
        ) as mock_pipeline:
            mock_pipeline.side_effect = mock_pipeline_with_delay

            start_time = asyncio.get_event_loop().time()

            result = await multi_symbol_ingestion_pipeline(
                symbols=symbols,
                data_type=DataType.KLINE,
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 1, 2),
                settings=mock_settings,
            )

            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time

            # Verify concurrent execution (should be faster than sequential)
            # With 3 symbols taking 0.1s each, concurrent should be ~0.1s, sequential would be ~0.3s
            assert total_time < 0.2  # Allow some overhead
            assert len(execution_times) == 3
            assert result["successful_runs"] == 3


class TestDataValidation:
    """Test data validation throughout workflows."""

    @pytest.mark.asyncio
    async def test_quality_score_calculation(self):
        """Test quality score calculation with various data conditions."""
        # Test with perfect data
        perfect_data = [
            KlineData(
                symbol="BTCUSDT",
                open_time=datetime(2023, 1, 1, 0, 0),
                close_time=datetime(2023, 1, 1, 0, 1),
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
        ]

        result = await validate_data_quality(perfect_data, "BTCUSDT", DataType.KLINE)
        assert result["quality_score"] == 1.0

        # Test with data containing null values
        imperfect_data = [
            KlineData(
                symbol="BTCUSDT",
                open_time=datetime(2023, 1, 1, 0, 0),
                close_time=datetime(2023, 1, 1, 0, 1),
                open_price=None,  # Null value
                high_price=Decimal("100.5"),
                low_price=Decimal("99.5"),
                close_price=Decimal("100.2"),
                volume=Decimal("1000.0"),
                quote_asset_volume=Decimal("100000.0"),
                number_of_trades=100,
                taker_buy_base_asset_volume=Decimal("500.0"),
                taker_buy_quote_asset_volume=Decimal("50000.0"),
            )
        ]

        result = await validate_data_quality(imperfect_data, "BTCUSDT", DataType.KLINE)
        assert result["quality_score"] < 1.0
        assert result["null_count"] > 0
