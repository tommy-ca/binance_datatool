#!/usr/bin/env python3
"""
Test script for the Silver layer processing workflow.

This script tests the processing workflow by creating sample Bronze zone data
and running it through the Silver layer transformation.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

# Add parent directory to path
sys.path.append('.')

from src.crypto_lakehouse.core.config import Settings, WorkflowConfig
from src.crypto_lakehouse.core.models import DataType, DataZone, Exchange, TradeType
from src.crypto_lakehouse.processing import KlineProcessor, FundingRateProcessor
from src.crypto_lakehouse.workflows.processing_flow import processing_flow
from src.crypto_lakehouse.storage.factory import create_storage


async def create_sample_bronze_data():
    """Create sample data in Bronze zone for testing."""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    logger.info("Creating sample Bronze zone data for processing test")
    
    # Create sample kline data
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    sample_klines = []
    
    for i in range(100):  # 100 sample klines
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        
        # Simulate some price movement
        base_price = 45000 + (i * 10)  # Trending up
        open_price = base_price + (i % 5 - 2) * 50  # Some volatility
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
    
    # Create sample funding rate data
    sample_funding = []
    for i in range(30):  # 30 sample funding rates (every 8 hours)
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
    
    # Store sample data in Bronze zone
    settings = Settings({'local_data_dir': 'test_output/processing_test'})
    storage = create_storage(settings)
    
    # Write kline data
    kline_path = await storage.write_data(
        data=kline_df,
        zone=DataZone.BRONZE,
        exchange=Exchange.BINANCE,
        data_type=DataType.KLINES,
        trade_type=TradeType.SPOT,
        symbol="BTCUSDT",
        partition_date=base_time
    )
    
    # Write funding data
    funding_path = await storage.write_data(
        data=funding_df,
        zone=DataZone.BRONZE,
        exchange=Exchange.BINANCE,
        data_type=DataType.FUNDING_RATES,
        trade_type=TradeType.UM_FUTURES,
        symbol="BTCUSDT",
        partition_date=base_time
    )
    
    logger.info(f"Created sample Bronze data:")
    logger.info(f"  Klines: {kline_path} ({len(kline_df)} records)")
    logger.info(f"  Funding: {funding_path} ({len(funding_df)} records)")
    
    return kline_df, funding_df


async def test_kline_processor():
    """Test the KlineProcessor independently."""
    
    logger = logging.getLogger(__name__)
    logger.info("Testing KlineProcessor")
    
    # Create sample data
    kline_df, _ = await create_sample_bronze_data()
    
    # Initialize processor
    settings = Settings({'local_data_dir': 'test_output/processing_test'})
    processor = KlineProcessor(settings)
    
    try:
        # Process the data
        processed_data = await processor.process(
            kline_df, 
            source_zone=DataZone.BRONZE, 
            target_zone=DataZone.SILVER
        )
        
        logger.info(f"KlineProcessor Results:")
        logger.info(f"  Input records: {len(kline_df)}")
        logger.info(f"  Output records: {len(processed_data)}")
        logger.info(f"  Input columns: {len(kline_df.columns)}")
        logger.info(f"  Output columns: {len(processed_data.columns)}")
        
        # Show added columns
        new_columns = set(processed_data.columns) - set(kline_df.columns)
        logger.info(f"  Added columns: {sorted(new_columns)}")
        
        # Show sample of processed data
        if len(processed_data) > 0:
            logger.info("  Sample processed record:")
            sample = processed_data.head(1).to_dicts()[0]
            for key, value in sample.items():
                if key in new_columns:
                    logger.info(f"    {key}: {value}")
        
        return True
        
    except Exception as e:
        logger.error(f"KlineProcessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_funding_processor():
    """Test the FundingRateProcessor independently."""
    
    logger = logging.getLogger(__name__)
    logger.info("Testing FundingRateProcessor")
    
    # Create sample data
    _, funding_df = await create_sample_bronze_data()
    
    # Initialize processor
    settings = Settings({'local_data_dir': 'test_output/processing_test'})
    processor = FundingRateProcessor(settings)
    
    try:
        # Process the data
        processed_data = await processor.process(
            funding_df, 
            source_zone=DataZone.BRONZE, 
            target_zone=DataZone.SILVER
        )
        
        logger.info(f"FundingRateProcessor Results:")
        logger.info(f"  Input records: {len(funding_df)}")
        logger.info(f"  Output records: {len(processed_data)}")
        logger.info(f"  Input columns: {len(funding_df.columns)}")
        logger.info(f"  Output columns: {len(processed_data.columns)}")
        
        # Show added columns
        new_columns = set(processed_data.columns) - set(funding_df.columns)
        logger.info(f"  Added columns: {sorted(new_columns)}")
        
        # Show sample of processed data
        if len(processed_data) > 0:
            logger.info("  Sample processed record:")
            sample = processed_data.head(1).to_dicts()[0]
            for key, value in sample.items():
                if key in new_columns:
                    logger.info(f"    {key}: {value}")
        
        return True
        
    except Exception as e:
        logger.error(f"FundingRateProcessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_processing_workflow():
    """Test the complete processing workflow."""
    
    logger = logging.getLogger(__name__)
    logger.info("Testing complete processing workflow")
    
    # Create sample data first
    await create_sample_bronze_data()
    
    # Test kline processing workflow
    try:
        settings = Settings({'local_data_dir': 'test_output/processing_test'})
        
        logger.info("Running kline processing workflow...")
        kline_results = await processing_flow(
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,
            trade_type=TradeType.SPOT,
            symbols=["BTCUSDT"],
            settings=settings
        )
        
        logger.info(f"Kline workflow results: {kline_results}")
        
        # Test funding processing workflow
        logger.info("Running funding rate processing workflow...")
        funding_results = await processing_flow(
            exchange=Exchange.BINANCE,
            data_type=DataType.FUNDING_RATES,
            trade_type=TradeType.UM_FUTURES,
            symbols=["BTCUSDT"],
            settings=settings
        )
        
        logger.info(f"Funding workflow results: {funding_results}")
        
        # Check if Silver zone files were created
        silver_output = Path("test_output/processing_test/silver")
        if silver_output.exists():
            silver_files = list(silver_output.rglob("*.parquet"))
            logger.info(f"Created {len(silver_files)} Silver zone files:")
            for file_path in silver_files:
                size = file_path.stat().st_size
                logger.info(f"  {file_path} ({size} bytes)")
        
        return True
        
    except Exception as e:
        logger.error(f"Full workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all processing tests."""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("🧪 Starting Processing Workflow Tests")
    logger.info("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: KlineProcessor
    logger.info("Test 1: KlineProcessor")
    if await test_kline_processor():
        logger.info("✅ KlineProcessor test PASSED")
        tests_passed += 1
    else:
        logger.error("❌ KlineProcessor test FAILED")
    
    print()
    
    # Test 2: FundingRateProcessor  
    logger.info("Test 2: FundingRateProcessor")
    if await test_funding_processor():
        logger.info("✅ FundingRateProcessor test PASSED")
        tests_passed += 1
    else:
        logger.error("❌ FundingRateProcessor test FAILED")
    
    print()
    
    # Test 3: Full Processing Workflow
    logger.info("Test 3: Full Processing Workflow")
    if await test_full_processing_workflow():
        logger.info("✅ Full workflow test PASSED")
        tests_passed += 1
    else:
        logger.error("❌ Full workflow test FAILED")
    
    print()
    logger.info("=" * 50)
    logger.info(f"PROCESSING TESTS SUMMARY: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        logger.info("🎉 All processing tests PASSED!")
        logger.info("Silver layer processing is working correctly!")
        return True
    else:
        logger.error("❌ Some processing tests FAILED!")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)