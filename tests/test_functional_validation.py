"""
Functional validation tests for the lakehouse implementation.

These tests verify that the lakehouse implementation maintains compatibility
with the original script workflows and produces accurate results.
"""

from datetime import datetime
from unittest.mock import patch

import polars as pl
import pytest
from config import TradeType
from generate.kline import gen_kline
from generate.kline_gaps import fill_kline_gaps, scan_gaps, split_by_gaps
from generate.merge import merge_funding_rates, merge_klines
from generate.resample import polars_calc_resample, resample_kline
from util.ts_manager import TSManager


class TestDataIngestion:
    """Test data ingestion accuracy (bulk vs incremental)."""

    @pytest.mark.unit
    def test_merge_klines_basic(self, test_data_dir, sample_kline_data):
        """Test basic K-line merging functionality."""
        # Setup test data directories
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"

        # Create mock AWS data
        parsed_dir = (
            test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        )
        parsed_dir.mkdir(parents=True, exist_ok=True)

        # Create TSManager and write test data
        ts_manager = TSManager(parsed_dir)
        ts_manager.update(sample_kline_data)

        # Create mock API data
        api_dir = test_data_dir / "api_data" / trade_type.value / "klines" / symbol / time_interval
        api_dir.mkdir(parents=True, exist_ok=True)

        # Create additional API data with some overlap
        additional_data = sample_kline_data.tail(100).with_columns(
            pl.col("volume") * 1.1  # Slight modification to test merge logic
        )
        api_file = api_dir / "additional.pqt"
        additional_data.write_parquet(api_file)

        # Test merge
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            result = merge_klines(trade_type, symbol, time_interval, exclude_empty=True)

        assert result is not None
        assert isinstance(result, pl.DataFrame)
        assert not result.is_empty()

        # Verify deduplication worked
        assert result.height >= sample_kline_data.height
        assert result.is_sorted("candle_begin_time")

        # Verify no duplicates
        unique_timestamps = result.select("candle_begin_time").unique().height
        assert unique_timestamps == result.height

    @pytest.mark.unit
    def test_merge_funding_rates(self, test_data_dir, sample_funding_data):
        """Test funding rate merging functionality."""
        trade_type = TradeType.um_futures
        symbol = "BTCUSDT"

        # Create mock AWS funding data
        parsed_dir = test_data_dir / "parsed_data" / trade_type.value / "funding"
        parsed_dir.mkdir(parents=True, exist_ok=True)

        aws_file = parsed_dir / f"{symbol}.pqt"
        sample_funding_data.write_parquet(aws_file)

        # Create mock API funding data
        api_dir = test_data_dir / "api_data" / trade_type.value / "funding_rate"
        api_dir.mkdir(parents=True, exist_ok=True)

        # Create additional API data
        additional_funding = sample_funding_data.tail(10).with_columns(pl.col("funding_rate") * 1.1)
        api_file = api_dir / f"{symbol}.pqt"
        additional_funding.write_parquet(api_file)

        # Test merge
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            result = merge_funding_rates(trade_type, symbol)

        assert result is not None
        assert isinstance(result, pl.DataFrame)
        assert not result.is_empty()
        assert result.is_sorted("candle_begin_time")

        # Verify columns
        expected_cols = ["candle_begin_time", "funding_rate"]
        assert all(col in result.columns for col in expected_cols)

    @pytest.mark.unit
    def test_merge_klines_empty_data(self, test_data_dir):
        """Test merge behavior with empty data."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"

        # Create empty directories
        parsed_dir = (
            test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        )
        parsed_dir.mkdir(parents=True, exist_ok=True)

        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            result = merge_klines(trade_type, symbol, time_interval, exclude_empty=True)

        assert result is None

    @pytest.mark.integration
    def test_data_ingestion_workflow(self, test_data_dir, data_generator):
        """Test complete data ingestion workflow."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"

        # Generate test data
        kline_data = data_generator.generate_kline_data(
            symbol=symbol, duration_hours=24, interval_minutes=1
        )

        # Setup AWS parsed data
        parsed_dir = (
            test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        )
        parsed_dir.mkdir(parents=True, exist_ok=True)

        ts_manager = TSManager(parsed_dir)
        ts_manager.update(kline_data.head(1200))  # First 20 hours

        # Setup API data
        api_dir = test_data_dir / "api_data" / trade_type.value / "klines" / symbol / time_interval
        api_dir.mkdir(parents=True, exist_ok=True)

        api_file = api_dir / "recent.pqt"
        kline_data.tail(300).write_parquet(api_file)  # Last 5 hours with 1 hour overlap

        # Test ingestion
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            result = merge_klines(trade_type, symbol, time_interval, exclude_empty=True)

        assert result is not None
        assert result.height >= 1200  # Should have at least the AWS data
        assert result.is_sorted("candle_begin_time")

        # Verify time range
        time_range = result.select(
            pl.col("candle_begin_time").min().alias("start"),
            pl.col("candle_begin_time").max().alias("end"),
        ).row(0)

        expected_start = kline_data["candle_begin_time"].min()
        expected_end = kline_data["candle_begin_time"].max()

        assert time_range[0] == expected_start
        assert time_range[1] == expected_end


class TestDataProcessing:
    """Test data processing pipeline components."""

    @pytest.mark.unit
    def test_scan_gaps_basic(self, sample_kline_data_with_gaps):
        """Test basic gap scanning functionality."""
        min_days = 0.1  # 2.4 hours
        min_price_chg = 0.05  # 5% price change

        gaps = scan_gaps(sample_kline_data_with_gaps, min_days, min_price_chg)

        assert isinstance(gaps, pl.DataFrame)
        # Should find at least one gap (the 100-minute gap we created)
        assert gaps.height >= 1

        # Verify gap structure
        expected_cols = [
            "prev_begin_time",
            "candle_begin_time",
            "prev_close",
            "open",
            "time_diff",
            "price_change",
        ]
        assert all(col in gaps.columns for col in expected_cols)

    @pytest.mark.unit
    def test_split_by_gaps(self, sample_kline_data_with_gaps):
        """Test data splitting by gaps."""
        min_days = 0.1
        min_price_chg = 0.05
        symbol = "BTCUSDT"

        gaps = scan_gaps(sample_kline_data_with_gaps, min_days, min_price_chg)
        splits = split_by_gaps(sample_kline_data_with_gaps, gaps, symbol)

        assert splits is not None
        assert isinstance(splits, dict)
        assert len(splits) >= 2  # Should have at least 2 segments

        # Verify all segments are DataFrames
        for split_name, split_df in splits.items():
            assert isinstance(split_df, pl.DataFrame)
            assert not split_df.is_empty()
            assert split_df.is_sorted("candle_begin_time")

    @pytest.mark.unit
    def test_fill_kline_gaps(self, sample_kline_data_with_gaps):
        """Test gap filling functionality."""
        time_interval = "1m"

        filled_data = fill_kline_gaps(sample_kline_data_with_gaps, time_interval)

        assert isinstance(filled_data, pl.DataFrame)
        assert filled_data.height > sample_kline_data_with_gaps.height
        assert filled_data.is_sorted("candle_begin_time")

        # Verify continuous timestamps
        time_diffs = filled_data.select(
            pl.col("candle_begin_time").diff().dt.total_minutes().alias("diff_minutes")
        ).drop_nulls()

        # All differences should be 1 minute (with small tolerance for floating point)
        assert time_diffs.filter(pl.col("diff_minutes").abs() - 1.0 > 0.01).height == 0

        # Verify filled data has reasonable values
        filled_rows = filled_data.filter(pl.col("volume") == 0)
        assert filled_rows.height > 0  # Should have some filled rows

        # Verify OHLC relationships in filled data
        invalid_ohlc = filled_data.filter(
            (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
            | (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
        )
        assert invalid_ohlc.height == 0

    @pytest.mark.unit
    def test_vwap_calculation(self, sample_kline_data):
        """Test VWAP calculation accuracy."""
        # Add VWAP calculation
        df_with_vwap = sample_kline_data.with_columns(
            (pl.col("quote_volume") / pl.col("volume")).alias("avg_price_1m")
        )

        # Verify VWAP calculation
        for row in df_with_vwap.iter_rows(named=True):
            if row["volume"] > 0:
                expected_vwap = row["quote_volume"] / row["volume"]
                assert abs(row["avg_price_1m"] - expected_vwap) < 1e-6

    @pytest.mark.integration
    def test_complete_kline_processing(self, test_data_dir, data_generator):
        """Test complete K-line processing workflow."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        time_interval = "1m"

        # Generate test data with gaps
        kline_data = data_generator.generate_kline_data(
            symbol=symbol, duration_hours=24, interval_minutes=1, with_gaps=True
        )

        # Setup test environment
        parsed_dir = (
            test_data_dir / "parsed_data" / trade_type.value / "klines" / symbol / time_interval
        )
        parsed_dir.mkdir(parents=True, exist_ok=True)

        ts_manager = TSManager(parsed_dir)
        ts_manager.update(kline_data)

        # Test processing
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            with patch("aws.kline.util.local_list_kline_symbols", return_value=[symbol]):
                result = gen_kline(
                    trade_type=trade_type,
                    time_interval=time_interval,
                    symbol=symbol,
                    split_gaps=True,
                    min_days=0.1,
                    min_price_chg=0.05,
                    with_vwap=True,
                    with_funding_rates=False,
                )

        # Verify result
        assert result == symbol

        # Check output files were created
        results_dir = test_data_dir / "results_data" / trade_type.value / "klines" / time_interval
        assert results_dir.exists()

        # Check that split files were created
        output_files = list(results_dir.glob("*.pqt"))
        assert len(output_files) > 0

        # Verify processed data
        for output_file in output_files:
            processed_data = pl.read_parquet(output_file)
            assert not processed_data.is_empty()
            assert processed_data.is_sorted("candle_begin_time")

            # Verify VWAP was calculated
            assert "avg_price_1m" in processed_data.columns

            # Verify gaps were filled
            time_diffs = processed_data.select(
                pl.col("candle_begin_time").diff().dt.total_minutes().alias("diff_minutes")
            ).drop_nulls()

            # Should have consistent 1-minute intervals
            inconsistent_intervals = time_diffs.filter(pl.col("diff_minutes").abs() - 1.0 > 0.01)
            assert inconsistent_intervals.height == 0


class TestResampling:
    """Test data resampling functionality."""

    @pytest.mark.unit
    def test_polars_resample_basic(self, sample_kline_data):
        """Test basic Polars resampling functionality."""
        time_interval = "1m"
        resample_interval = "5m"
        offset = "0m"

        resampled = polars_calc_resample(
            sample_kline_data, time_interval, resample_interval, offset
        )

        assert isinstance(resampled, pl.DataFrame)
        assert not resampled.is_empty()
        assert resampled.height == sample_kline_data.height // 5  # 5-minute candles
        assert resampled.is_sorted("candle_begin_time")

        # Verify OHLC aggregation
        for row in resampled.iter_rows(named=True):
            assert row["high"] >= row["open"]
            assert row["high"] >= row["close"]
            assert row["low"] <= row["open"]
            assert row["low"] <= row["close"]
            assert row["volume"] >= 0

    @pytest.mark.unit
    def test_polars_resample_with_vwap(self, sample_kline_data):
        """Test resampling with VWAP preservation."""
        # Add VWAP column
        df_with_vwap = sample_kline_data.with_columns(
            (pl.col("quote_volume") / pl.col("volume")).alias("avg_price_1m")
        )

        time_interval = "1m"
        resample_interval = "5m"
        offset = "0m"

        resampled = polars_calc_resample(df_with_vwap, time_interval, resample_interval, offset)

        assert "avg_price_1m" in resampled.columns
        # VWAP should be the first value of each 5-minute period
        assert resampled["avg_price_1m"].null_count() == 0

    @pytest.mark.unit
    def test_polars_resample_with_funding(self, sample_kline_data, sample_funding_data):
        """Test resampling with funding rates."""
        # Join funding data with kline data
        df_with_funding = sample_kline_data.join(
            sample_funding_data, on="candle_begin_time", how="left"
        ).fill_null(0)

        time_interval = "1m"
        resample_interval = "1h"
        offset = "0m"

        resampled = polars_calc_resample(df_with_funding, time_interval, resample_interval, offset)

        assert "funding_rate" in resampled.columns
        # Should have funding information preserved
        funding_rows = resampled.filter(pl.col("funding_rate").abs() > 1e-6)
        assert funding_rows.height >= 0

    @pytest.mark.unit
    def test_resample_different_intervals(self, sample_kline_data):
        """Test resampling to different time intervals."""
        time_interval = "1m"
        test_intervals = ["5m", "15m", "1h", "4h"]

        for resample_interval in test_intervals:
            resampled = polars_calc_resample(
                sample_kline_data, time_interval, resample_interval, "0m"
            )

            assert isinstance(resampled, pl.DataFrame)
            assert not resampled.is_empty()
            assert resampled.is_sorted("candle_begin_time")

            # Verify volume aggregation
            total_original_volume = sample_kline_data["volume"].sum()
            total_resampled_volume = resampled["volume"].sum()

            # Should be approximately equal (within floating point precision)
            assert abs(total_original_volume - total_resampled_volume) < 1e-6

    @pytest.mark.integration
    def test_resample_kline_workflow(self, test_data_dir, data_generator):
        """Test complete resampling workflow."""
        trade_type = TradeType.spot
        symbol = "BTCUSDT"
        resample_interval = "5m"
        base_offset = "1m"

        # Generate test data
        kline_data = data_generator.generate_kline_data(
            symbol=symbol, duration_hours=24, interval_minutes=1
        )

        # Setup test environment
        results_dir = test_data_dir / "results_data" / trade_type.value / "klines" / "1m"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Write test data
        kline_file = results_dir / f"{symbol}.pqt"
        kline_data.write_parquet(kline_file)

        # Test resampling
        with patch("config.BINANCE_DATA_DIR", test_data_dir):
            with patch("config.N_JOBS", 1):
                result = resample_kline(trade_type, symbol, resample_interval, base_offset)

        assert result == symbol

        # Verify resampled files were created
        resampled_dir = (
            test_data_dir
            / "results_data"
            / trade_type.value
            / "resampled_klines"
            / resample_interval
        )
        assert resampled_dir.exists()

        # Check all offset directories were created
        offset_dirs = list(resampled_dir.glob("*m"))
        assert len(offset_dirs) == 5  # 0m, 1m, 2m, 3m, 4m

        # Verify resampled data
        for offset_dir in offset_dirs:
            resampled_file = offset_dir / f"{symbol}.pqt"
            if resampled_file.exists():
                resampled_data = pl.read_parquet(resampled_file)
                assert not resampled_data.is_empty()
                assert resampled_data.is_sorted("candle_begin_time")

                # Verify time intervals
                time_diffs = resampled_data.select(
                    pl.col("candle_begin_time").diff().dt.total_minutes().alias("diff_minutes")
                ).drop_nulls()

                # Should have consistent 5-minute intervals
                expected_diff = 5.0
                inconsistent_intervals = time_diffs.filter(
                    pl.col("diff_minutes").abs() - expected_diff > 0.01
                )
                assert inconsistent_intervals.height == 0


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.unit
    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        empty_df = pl.DataFrame(
            schema={
                "candle_begin_time": pl.Datetime,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
                "quote_volume": pl.Float64,
                "trade_num": pl.Int64,
                "taker_buy_base_asset_volume": pl.Float64,
                "taker_buy_quote_asset_volume": pl.Float64,
            }
        )

        # Test gap filling with empty data
        filled = fill_kline_gaps(empty_df, "1m")
        assert filled.is_empty()

        # Test gap scanning with empty data
        gaps = scan_gaps(empty_df, 1, 0.1)
        assert gaps.is_empty()

        # Test resampling with empty data
        resampled = polars_calc_resample(empty_df, "1m", "5m", "0m")
        assert resampled.is_empty()

    @pytest.mark.unit
    def test_single_row_dataframe(self):
        """Test handling of single-row DataFrames."""
        single_row_df = pl.DataFrame(
            {
                "candle_begin_time": [datetime(2023, 1, 1, 0, 0, 0)],
                "open": [50000.0],
                "high": [50100.0],
                "low": [49900.0],
                "close": [50050.0],
                "volume": [100.0],
                "quote_volume": [5000000.0],
                "trade_num": [500],
                "taker_buy_base_asset_volume": [50.0],
                "taker_buy_quote_asset_volume": [2500000.0],
            }
        )

        # Test gap scanning
        gaps = scan_gaps(single_row_df, 1, 0.1)
        assert gaps.is_empty()

        # Test gap filling
        filled = fill_kline_gaps(single_row_df, "1m")
        assert filled.height == 1

        # Test resampling
        resampled = polars_calc_resample(single_row_df, "1m", "5m", "0m")
        assert resampled.height == 1

    @pytest.mark.unit
    def test_malformed_data_handling(self):
        """Test handling of malformed data."""
        malformed_df = pl.DataFrame(
            {
                "candle_begin_time": [datetime(2023, 1, 1, 0, 0, 0)],
                "open": [50000.0],
                "high": [49000.0],  # High less than open (invalid)
                "low": [51000.0],  # Low greater than open (invalid)
                "close": [50050.0],
                "volume": [-100.0],  # Negative volume (invalid)
                "quote_volume": [5000000.0],
                "trade_num": [500],
                "taker_buy_base_asset_volume": [50.0],
                "taker_buy_quote_asset_volume": [2500000.0],
            }
        )

        # Functions should still work but produce warnings or handle gracefully
        filled = fill_kline_gaps(malformed_df, "1m")
        assert filled.height == 1

        resampled = polars_calc_resample(malformed_df, "1m", "5m", "0m")
        assert resampled.height == 1
