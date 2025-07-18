"""Tests for data processing modules."""

import pytest
import polars as pl
from datetime import datetime, timezone

from crypto_lakehouse.processing.kline_processor import KlineProcessor
from crypto_lakehouse.processing.funding_processor import FundingRateProcessor
from crypto_lakehouse.core.models import DataZone


class TestKlineProcessor:
    """Test K-line data processor."""
    
    @pytest.mark.asyncio
    async def test_process_klines(self, test_settings, sample_kline_dataframe):
        """Test processing K-line data from Bronze to Silver."""
        processor = KlineProcessor(test_settings)
        
        result = await processor.process(
            data=sample_kline_dataframe,
            source_zone=DataZone.BRONZE,
            target_zone=DataZone.SILVER
        )
        
        # Check that enhanced features were added
        assert "vwap" in result.columns
        assert "returns" in result.columns
        assert "log_returns" in result.columns
        assert "price_change" in result.columns
        assert "volatility" in result.columns
        
        # Check that metadata was added
        assert "_processed_at" in result.columns
        assert "_source_zone" in result.columns
        assert "_target_zone" in result.columns
        
        # Verify data integrity
        assert len(result) == len(sample_kline_dataframe)
        assert result["symbol"][0] == "BTCUSDT"
    
    @pytest.mark.asyncio
    async def test_clean_data(self, test_settings):
        """Test data cleaning functionality."""
        processor = KlineProcessor(test_settings)
        
        # Create data with invalid entries
        dirty_data = pl.DataFrame({
            "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT"],
            "open_time": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc)
            ],
            "close_time": [
                datetime(2024, 1, 1, 0, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 2, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 0, 3, tzinfo=timezone.utc)
            ],
            "open_price": [50000.0, 0.0, 50200.0],  # Zero price (invalid)
            "high_price": [50100.0, 50000.0, 50300.0],
            "low_price": [49950.0, 49900.0, 50150.0],
            "close_price": [50050.0, 49950.0, 50250.0],
            "volume": [10.5, 8.3, -5.0],  # Negative volume (invalid)
            "quote_asset_volume": [525000.0, 416250.0, 251250.0],
            "number_of_trades": [100, 85, 95],
            "taker_buy_base_asset_volume": [5.25, 4.15, 2.5],
            "taker_buy_quote_asset_volume": [262500.0, 208125.0, 125625.0]
        })
        
        cleaned = await processor._clean_data(dirty_data)
        
        # Should remove invalid rows
        assert len(cleaned) < len(dirty_data)
        assert all(cleaned["open_price"] > 0)
        assert all(cleaned["volume"] >= 0)
    
    @pytest.mark.asyncio
    async def test_add_features(self, test_settings, sample_kline_dataframe):
        """Test feature engineering."""
        processor = KlineProcessor(test_settings)
        
        enhanced = await processor._add_features(sample_kline_dataframe)
        
        # Check technical indicators
        assert "vwap" in enhanced.columns
        assert "returns" in enhanced.columns
        assert "log_returns" in enhanced.columns
        assert "typical_price" in enhanced.columns
        assert "volatility" in enhanced.columns
        
        # Verify calculations are reasonable
        vwap_values = enhanced["vwap"].to_list()
        assert all(v > 0 for v in vwap_values if v is not None)
    
    @pytest.mark.asyncio
    async def test_calculate_additional_indicators(self, test_settings, sample_kline_dataframe):
        """Test additional technical indicators."""
        processor = KlineProcessor(test_settings)
        
        # Create larger dataset for meaningful indicators
        larger_data = sample_kline_dataframe
        for i in range(25):  # Add more rows for 20-period indicators
            larger_data = pl.concat([larger_data, sample_kline_dataframe])
        
        enhanced = await processor.calculate_additional_indicators(
            larger_data, 
            indicators=["sma_20", "ema_20", "bollinger_bands"]
        )
        
        # Check indicators were added
        assert "sma_20" in enhanced.columns
        assert "ema_20" in enhanced.columns
        assert "bb_upper" in enhanced.columns
        assert "bb_lower" in enhanced.columns
        assert "bb_middle" in enhanced.columns
    
    def test_get_schema_bronze(self, test_settings):
        """Test getting Bronze zone schema."""
        processor = KlineProcessor(test_settings)
        
        schema = processor.get_schema(DataZone.BRONZE)
        
        # Check required columns
        assert "symbol" in schema
        assert "open_time" in schema
        assert "close_time" in schema
        assert "open_price" in schema
        assert "high_price" in schema
        assert "low_price" in schema
        assert "close_price" in schema
        assert "volume" in schema
    
    def test_get_schema_silver(self, test_settings):
        """Test getting Silver zone schema."""
        processor = KlineProcessor(test_settings)
        
        schema = processor.get_schema(DataZone.SILVER)
        
        # Check enhanced columns
        assert "vwap" in schema
        assert "returns" in schema
        assert "log_returns" in schema
        assert "_processed_at" in schema
    
    def test_validate_schema(self, test_settings, sample_kline_dataframe):
        """Test schema validation."""
        processor = KlineProcessor(test_settings)
        
        bronze_schema = processor.get_schema(DataZone.BRONZE)
        
        # Should pass validation
        assert processor.validate_schema(sample_kline_dataframe, bronze_schema) is True
        
        # Test with missing column
        invalid_data = sample_kline_dataframe.drop("volume")
        assert processor.validate_schema(invalid_data, bronze_schema) is False


class TestFundingRateProcessor:
    """Test funding rate processor."""
    
    @pytest.mark.asyncio
    async def test_process_funding_rates(self, test_settings):
        """Test processing funding rate data."""
        processor = FundingRateProcessor(test_settings)
        
        # Create sample funding rate data
        funding_data = pl.DataFrame({
            "symbol": ["BTCUSDT", "BTCUSDT"],
            "funding_time": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
            ],
            "funding_rate": [0.0001, 0.0002],
            "mark_price": [50000.0, 50100.0]
        })
        
        result = await processor.process(
            data=funding_data,
            source_zone=DataZone.BRONZE,
            target_zone=DataZone.SILVER
        )
        
        # Check enhanced features
        assert "funding_rate_bps" in result.columns
        assert "annualized_rate" in result.columns
        assert "rate_change" in result.columns
        assert "rolling_avg_7d" in result.columns
        assert "cumulative_funding" in result.columns
        
        # Verify calculations
        bps_values = result["funding_rate_bps"].to_list()
        assert bps_values[0] == 1.0  # 0.0001 * 10000
        assert bps_values[1] == 2.0  # 0.0002 * 10000
    
    @pytest.mark.asyncio
    async def test_clean_funding_data(self, test_settings):
        """Test cleaning funding rate data."""
        processor = FundingRateProcessor(test_settings)
        
        # Create data with outliers
        dirty_data = pl.DataFrame({
            "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT"],
            "funding_time": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 16, 0, tzinfo=timezone.utc)
            ],
            "funding_rate": [0.0001, 0.01, 0.0002],  # 0.01 is extreme outlier
            "mark_price": [50000.0, 50100.0, 50200.0]
        })
        
        cleaned = await processor._clean_data(dirty_data)
        
        # Should remove extreme outlier
        assert len(cleaned) < len(dirty_data)
        rates = cleaned["funding_rate"].to_list()
        assert all(-0.0075 <= rate <= 0.0075 for rate in rates)
    
    @pytest.mark.asyncio
    async def test_add_funding_features(self, test_settings):
        """Test adding funding rate features."""
        processor = FundingRateProcessor(test_settings)
        
        # Create larger dataset for meaningful calculations
        funding_data = pl.DataFrame({
            "symbol": ["BTCUSDT"] * 100,
            "funding_time": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc) + 
                pd.Timedelta(hours=8*i) for i in range(100)
            ],
            "funding_rate": [0.0001 + (i % 10) * 0.00001 for i in range(100)],
            "mark_price": [50000.0 + i * 10 for i in range(100)]
        })
        
        enhanced = await processor._add_features(funding_data)
        
        # Check all features were added
        assert "funding_rate_bps" in enhanced.columns
        assert "annualized_rate" in enhanced.columns
        assert "rate_change" in enhanced.columns
        assert "rolling_avg_7d" in enhanced.columns
        assert "rolling_avg_30d" in enhanced.columns
        assert "volatility_7d" in enhanced.columns
        assert "cumulative_funding" in enhanced.columns
    
    @pytest.mark.asyncio
    async def test_calculate_funding_statistics(self, test_settings):
        """Test funding rate statistics calculation."""
        processor = FundingRateProcessor(test_settings)
        
        # Create test data with varying rates
        funding_data = pl.DataFrame({
            "symbol": ["BTCUSDT"] * 100,
            "funding_time": [
                datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc) + 
                pd.Timedelta(hours=8*i) for i in range(100)
            ],
            "funding_rate": [
                0.0001 if i % 2 == 0 else -0.0001 
                for i in range(100)
            ],
            "mark_price": [50000.0] * 100
        })
        
        stats = await processor.calculate_funding_statistics(funding_data, window_days=30)
        
        # Check statistics columns
        assert "min_rate_30d" in stats.columns
        assert "max_rate_30d" in stats.columns
        assert "positive_count_30d" in stats.columns
        assert "negative_count_30d" in stats.columns
        assert "rate_regime_30d" in stats.columns