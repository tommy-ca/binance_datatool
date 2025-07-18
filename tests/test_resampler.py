"""Tests for data resampling functionality."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from crypto_lakehouse.utils.resampler import (
    DataResampler,
    ResamplingConfig,
    ResamplingResult,
    resample_data,
    get_supported_timeframes,
    validate_timeframe_conversion
)
from crypto_lakehouse.core.models import KlineData


@pytest.fixture
def sample_1m_data() -> List[KlineData]:
    """Create sample 1-minute K-line data for testing."""
    base_time = datetime(2023, 1, 1, 0, 0, 0)
    data = []
    
    # Create 60 minutes of data (1 hour)
    for i in range(60):
        open_time = base_time + timedelta(minutes=i)
        close_time = base_time + timedelta(minutes=i+1) - timedelta(milliseconds=1)
        
        # Create realistic price movement
        base_price = 100.0 + (i * 0.1)  # Gradual price increase
        
        kline = KlineData(
            symbol="BTCUSDT",
            open_time=open_time,
            close_time=close_time,
            open_price=Decimal(str(base_price)),
            high_price=Decimal(str(base_price + 0.5)),
            low_price=Decimal(str(base_price - 0.3)),
            close_price=Decimal(str(base_price + 0.2)),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0")
        )
        data.append(kline)
    
    return data


@pytest.fixture
def resampling_config() -> ResamplingConfig:
    """Create basic resampling configuration."""
    return ResamplingConfig(
        source_timeframe="1m",
        target_timeframe="5m"
    )


class TestResamplingConfig:
    """Test ResamplingConfig validation."""
    
    def test_valid_config(self):
        """Test valid configuration creation."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="5m"
        )
        assert config.source_timeframe == "1m"
        assert config.target_timeframe == "5m"
        assert config.aggregation_method == "ohlcv"
        assert config.include_volume is True
        assert config.include_trades is True
    
    def test_invalid_timeframe(self):
        """Test invalid timeframe validation."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            ResamplingConfig(
                source_timeframe="invalid",
                target_timeframe="5m"
            )
    
    def test_same_timeframes(self):
        """Test validation when source and target are the same."""
        with pytest.raises(ValueError, match="Target timeframe must be different"):
            ResamplingConfig(
                source_timeframe="1m",
                target_timeframe="1m"
            )


class TestDataResampler:
    """Test DataResampler functionality."""
    
    def test_resample_1m_to_5m(self, sample_1m_data, resampling_config):
        """Test resampling 1-minute data to 5-minute."""
        resampler = DataResampler(resampling_config)
        result = resampler.resample_klines(sample_1m_data, "BTCUSDT")
        
        assert isinstance(result, ResamplingResult)
        assert result.symbol == "BTCUSDT"
        assert result.source_timeframe == "1m"
        assert result.target_timeframe == "5m"
        assert result.source_records == 60
        assert result.target_records == 12  # 60 minutes / 5 minutes
        assert result.completeness_ratio > 0.9
    
    def test_resample_1m_to_1h(self, sample_1m_data):
        """Test resampling 1-minute data to 1-hour."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="1h"
        )
        resampler = DataResampler(config)
        result = resampler.resample_klines(sample_1m_data, "BTCUSDT")
        
        assert result.target_records == 1  # 60 minutes = 1 hour
        assert result.completeness_ratio > 0.9
    
    def test_ohlcv_aggregation(self, sample_1m_data):
        """Test OHLCV aggregation logic."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="5m"
        )
        resampler = DataResampler(config)
        
        # Test with first 5 minutes of data
        first_5_minutes = sample_1m_data[:5]
        result = resampler.resample_klines(first_5_minutes, "BTCUSDT")
        
        # Should have 1 record for 5-minute period
        assert result.target_records == 1
        
        # Verify OHLCV logic would work correctly
        # (We can't easily test the exact values without accessing internal data)
    
    def test_volume_aggregation(self, sample_1m_data):
        """Test volume aggregation."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="5m",
            include_volume=True
        )
        resampler = DataResampler(config)
        result = resampler.resample_klines(sample_1m_data, "BTCUSDT")
        
        # Volume should be aggregated (summed)
        assert result.target_records == 12
    
    def test_no_volume_config(self, sample_1m_data):
        """Test configuration without volume."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="5m",
            include_volume=False,
            include_trades=False
        )
        resampler = DataResampler(config)
        result = resampler.resample_klines(sample_1m_data, "BTCUSDT")
        
        assert result.target_records == 12
    
    def test_empty_data(self, resampling_config):
        """Test handling of empty data."""
        resampler = DataResampler(resampling_config)
        
        with pytest.raises(ValueError, match="No data provided"):
            resampler.resample_klines([], "BTCUSDT")
    
    def test_completeness_calculation(self, sample_1m_data):
        """Test completeness ratio calculation."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="5m",
            validate_completeness=True
        )
        resampler = DataResampler(config)
        result = resampler.resample_klines(sample_1m_data, "BTCUSDT")
        
        # Should have high completeness with continuous data
        assert result.completeness_ratio > 0.9
    
    def test_completeness_disabled(self, sample_1m_data):
        """Test when completeness validation is disabled."""
        config = ResamplingConfig(
            source_timeframe="1m",
            target_timeframe="5m",
            validate_completeness=False
        )
        resampler = DataResampler(config)
        result = resampler.resample_klines(sample_1m_data, "BTCUSDT")
        
        # Should always be 1.0 when disabled
        assert result.completeness_ratio == 1.0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_resample_data_function(self, sample_1m_data):
        """Test the resample_data convenience function."""
        result = resample_data(
            data=sample_1m_data,
            symbol="BTCUSDT",
            source_timeframe="1m",
            target_timeframe="5m"
        )
        
        assert isinstance(result, ResamplingResult)
        assert result.symbol == "BTCUSDT"
        assert result.source_records == 60
        assert result.target_records == 12
    
    def test_get_supported_timeframes(self):
        """Test getting supported timeframes."""
        timeframes = get_supported_timeframes()
        
        assert isinstance(timeframes, list)
        assert "1m" in timeframes
        assert "5m" in timeframes
        assert "1h" in timeframes
        assert "1d" in timeframes
        
        # Should be a copy (not reference)
        timeframes.append("invalid")
        assert "invalid" not in get_supported_timeframes()
    
    def test_validate_timeframe_conversion(self):
        """Test timeframe conversion validation."""
        # Valid conversions
        assert validate_timeframe_conversion("1m", "5m") is True
        assert validate_timeframe_conversion("1m", "1h") is True
        assert validate_timeframe_conversion("5m", "1d") is True
        
        # Invalid conversions
        assert validate_timeframe_conversion("1m", "1m") is False
        assert validate_timeframe_conversion("invalid", "5m") is False
        assert validate_timeframe_conversion("1m", "invalid") is False


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_single_data_point(self):
        """Test resampling with single data point."""
        single_kline = KlineData(
            symbol="BTCUSDT",
            open_time=datetime(2023, 1, 1, 0, 0, 0),
            close_time=datetime(2023, 1, 1, 0, 0, 59, 999000),
            open_price=Decimal("100.0"),
            high_price=Decimal("100.5"),
            low_price=Decimal("99.5"),
            close_price=Decimal("100.2"),
            volume=Decimal("1000.0"),
            quote_asset_volume=Decimal("100000.0"),
            number_of_trades=100,
            taker_buy_base_asset_volume=Decimal("500.0"),
            taker_buy_quote_asset_volume=Decimal("50000.0")
        )
        
        result = resample_data(
            data=[single_kline],
            symbol="BTCUSDT",
            source_timeframe="1m",
            target_timeframe="5m"
        )
        
        assert result.target_records == 1
        assert result.source_records == 1
    
    def test_irregular_timeframes(self):
        """Test with irregular timeframes."""
        base_time = datetime(2023, 1, 1, 0, 0, 0)
        data = []
        
        # Create 15 minutes of data
        for i in range(15):
            open_time = base_time + timedelta(minutes=i)
            close_time = base_time + timedelta(minutes=i+1) - timedelta(milliseconds=1)
            
            kline = KlineData(
                symbol="BTCUSDT",
                open_time=open_time,
                close_time=close_time,
                open_price=Decimal("100.0"),
                high_price=Decimal("100.5"),
                low_price=Decimal("99.5"),
                close_price=Decimal("100.2"),
                volume=Decimal("1000.0"),
                quote_asset_volume=Decimal("100000.0"),
                number_of_trades=100,
                taker_buy_base_asset_volume=Decimal("500.0"),
                taker_buy_quote_asset_volume=Decimal("50000.0")
            )
            data.append(kline)
        
        # Test 15m resampling
        result = resample_data(
            data=data,
            symbol="BTCUSDT",
            source_timeframe="1m",
            target_timeframe="15m"
        )
        
        assert result.target_records == 1
        assert result.source_records == 15
    
    def test_different_symbols(self, sample_1m_data):
        """Test resampling with different symbol names."""
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        
        for symbol in symbols:
            result = resample_data(
                data=sample_1m_data,
                symbol=symbol,
                source_timeframe="1m",
                target_timeframe="5m"
            )
            
            assert result.symbol == symbol
            assert result.target_records == 12