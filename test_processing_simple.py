#!/usr/bin/env python3
"""
Simple test for the Silver layer processing without Prefect workflow.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
import polars as pl

# Add parent directory to path
sys.path.append('.')

from src.crypto_lakehouse.core.config import Settings
from src.crypto_lakehouse.processing import KlineProcessor, FundingRateProcessor


async def test_simple_processing():
    """Test processors directly without workflow complexity."""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("🧪 Testing Silver Layer Processing (Simple)")
    
    # Create sample kline data
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    sample_klines = []
    
    for i in range(50):  # 50 sample klines
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        
        # Simulate price movement
        base_price = 45000 + (i * 10)
        open_price = base_price + (i % 5 - 2) * 50
        close_price = open_price + ((i % 3) - 1) * 30
        high_price = max(open_price, close_price) + (i % 4) * 20
        low_price = min(open_price, close_price) - (i % 3) * 15
        
        sample_klines.append({
            "symbol": "BTCUSDT",
            "open_time": open_time,
            "close_time": close_time,
            "open_price": float(open_price),
            "high_price": float(high_price),
            "low_price": float(low_price),
            "close_price": float(close_price),
            "volume": float(100 + i * 2),
            "quote_asset_volume": float((100 + i * 2) * open_price),
            "number_of_trades": 50 + i,
            "taker_buy_base_asset_volume": float(50 + i),
            "taker_buy_quote_asset_volume": float((50 + i) * open_price)
        })
    
    kline_df = pl.DataFrame(sample_klines)
    logger.info(f"Created sample kline data: {len(kline_df)} records, {len(kline_df.columns)} columns")
    
    # Test KlineProcessor
    try:
        settings = Settings({'local_data_dir': 'test_output/simple_processing'})
        processor = KlineProcessor(settings)
        
        # Test validation first
        validation = processor.validate_input(kline_df)
        logger.info(f"Validation result: {validation['valid']}")
        if validation['issues']:
            logger.warning(f"Validation issues: {validation['issues']}")
        
        # Process the data
        from src.crypto_lakehouse.core.models import DataZone
        processed_data = await processor.process(
            kline_df, 
            source_zone=DataZone.BRONZE, 
            target_zone=DataZone.SILVER
        )
        
        logger.info(f"✅ KlineProcessor SUCCESS!")
        logger.info(f"  Input: {len(kline_df)} records, {len(kline_df.columns)} columns")
        logger.info(f"  Output: {len(processed_data)} records, {len(processed_data.columns)} columns")
        
        # Show some new columns
        new_columns = set(processed_data.columns) - set(kline_df.columns)
        logger.info(f"  Added columns: {len(new_columns)}")
        logger.info(f"  Sample new columns: {sorted(list(new_columns))[:10]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ KlineProcessor FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_funding_processing():
    """Test funding rate processor."""
    
    logger = logging.getLogger(__name__)
    logger.info("Testing FundingRateProcessor")
    
    # Create sample funding data
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    sample_funding = []
    
    for i in range(20):  # 20 funding rate samples
        funding_time = base_time + timedelta(hours=i * 8)
        funding_rate = (i % 10 - 5) * 0.0001  # Range from -0.0005 to 0.0005
        mark_price = 45000 + (i * 50)
        
        sample_funding.append({
            "symbol": "BTCUSDT",
            "funding_time": funding_time,
            "funding_rate": funding_rate,
            "mark_price": float(mark_price)
        })
    
    funding_df = pl.DataFrame(sample_funding)
    logger.info(f"Created sample funding data: {len(funding_df)} records, {len(funding_df.columns)} columns")
    
    try:
        settings = Settings({'local_data_dir': 'test_output/simple_processing'})
        processor = FundingRateProcessor(settings)
        
        # Process the data
        from src.crypto_lakehouse.core.models import DataZone
        processed_data = await processor.process(
            funding_df, 
            source_zone=DataZone.BRONZE, 
            target_zone=DataZone.SILVER
        )
        
        logger.info(f"✅ FundingRateProcessor SUCCESS!")
        logger.info(f"  Input: {len(funding_df)} records, {len(funding_df.columns)} columns")
        logger.info(f"  Output: {len(processed_data)} records, {len(processed_data.columns)} columns")
        
        # Show some new columns
        new_columns = set(processed_data.columns) - set(funding_df.columns)
        logger.info(f"  Added columns: {len(new_columns)}")
        logger.info(f"  Sample new columns: {sorted(list(new_columns))[:10]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ FundingRateProcessor FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run simple processing tests."""
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 Starting Simple Silver Layer Processing Tests")
    logger.info("=" * 60)
    
    # Test 1: Kline Processing
    kline_success = await test_simple_processing()
    
    print()
    
    # Test 2: Funding Processing  
    funding_success = await test_funding_processing()
    
    print()
    logger.info("=" * 60)
    
    if kline_success and funding_success:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("Silver layer processing is working correctly!")
        return True
    else:
        logger.error("❌ SOME TESTS FAILED!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)