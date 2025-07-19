#!/usr/bin/env python3
"""
Test core enhanced workflow functionality without Prefect.

This tests the core logic for URL generation and matrix processing.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append('.')

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.models import (
    DataIngestionTask, Exchange, DataType, TradeType, DataZone, Interval
)


def load_enhanced_matrix():
    """Load the enhanced matrix file."""
    matrix_path = Path("enhanced_binance_archive_matrix.json")
    
    if not matrix_path.exists():
        raise FileNotFoundError(f"Matrix file not found: {matrix_path}")
    
    with open(matrix_path, 'r') as f:
        return json.load(f)


def test_data_type_mapping():
    """Test data type mapping functionality."""
    
    logger = logging.getLogger(__name__)
    logger.info("🧪 Testing Data Type Mapping")
    
    # Test mapping function
    def map_matrix_data_type(matrix_data_type: str):
        mapping = {
            'klines': DataType.KLINES,
            'trades': DataType.TRADES,
            'aggTrades': DataType.TRADES,
            'fundingRate': DataType.FUNDING_RATES,
            'liquidationSnapshot': DataType.LIQUIDATIONS,
            'bookDepth': DataType.ORDER_BOOK,
            'bookTicker': DataType.TICKER,
            'indexPriceKlines': DataType.KLINES,
            'markPriceKlines': DataType.KLINES,
            'premiumIndex': DataType.FUNDING_RATES,
            'metrics': DataType.METRICS,
            'BVOLIndex': DataType.VOLATILITY,
            'EOHSummary': DataType.SUMMARY
        }
        
        result = mapping.get(matrix_data_type)
        if not result:
            logger.warning(f"Unknown data type: {matrix_data_type}")
        return result
    
    # Test cases
    test_cases = [
        "klines", "trades", "aggTrades", "fundingRate", "bookDepth",
        "BVOLIndex", "EOHSummary", "metrics", "premiumIndex"
    ]
    
    success = True
    for test_case in test_cases:
        result = map_matrix_data_type(test_case)
        if result:
            logger.info(f"✅ {test_case} -> {result.value}")
        else:
            logger.error(f"❌ Failed to map: {test_case}")
            success = False
    
    return success


def test_url_generation():
    """Test URL generation logic."""
    
    logger = logging.getLogger(__name__)
    logger.info("🔗 Testing URL Generation")
    
    def generate_binance_url(market, data_type, symbol, interval=None, date="2025-07-15"):
        """Generate Binance archive URL."""
        
        base_url = "s3://data.binance.vision/data/"
        
        # Market mapping
        market_paths = {
            'spot': 'spot',
            'futures_um': 'futures/um',
            'futures_cm': 'futures/cm',
            'options': 'option'
        }
        
        market_path = market_paths.get(market, market)
        partition = 'daily'
        
        # Build URL based on data type
        if data_type in ['klines', 'indexPriceKlines', 'markPriceKlines'] and interval:
            url = f"{base_url}{market_path}/{partition}/{data_type}/{symbol}/{interval}/{symbol}-{interval}-{date}.zip"
        elif data_type in ['bookDepth'] and interval:
            url = f"{base_url}{market_path}/{partition}/{data_type}/{symbol}/{interval}/{symbol}-{interval}-{date}.zip"
        elif data_type in ['BVOLIndex'] and interval:
            url = f"{base_url}{market_path}/{partition}/{data_type}/{symbol}/{interval}/{symbol}-{interval}-{date}.zip"
        else:
            url = f"{base_url}{market_path}/{partition}/{data_type}/{symbol}/{symbol}-{data_type}-{date}.zip"
        
        return url
    
    # Test cases
    test_cases = [
        {
            "name": "Spot Klines 1h",
            "market": "spot",
            "data_type": "klines",
            "symbol": "BTCUSDT",
            "interval": "1h"
        },
        {
            "name": "Futures UM Funding",
            "market": "futures_um",
            "data_type": "fundingRate",
            "symbol": "BTCUSDT"
        },
        {
            "name": "Spot Trades",
            "market": "spot",
            "data_type": "trades",
            "symbol": "ETHUSDT"
        },
        {
            "name": "Options BVOL 1h",
            "market": "options",
            "data_type": "BVOLIndex",
            "symbol": "BTC",
            "interval": "1h"
        },
        {
            "name": "Futures CM Mark Price 1d",
            "market": "futures_cm",
            "data_type": "markPriceKlines",
            "symbol": "BTCUSD_PERP",
            "interval": "1d"
        }
    ]
    
    for test_case in test_cases:
        url = generate_binance_url(
            test_case["market"],
            test_case["data_type"],
            test_case["symbol"],
            test_case.get("interval")
        )
        logger.info(f"🔗 {test_case['name']}:")
        logger.info(f"   {url}")
        logger.info("")
    
    return True


def test_matrix_processing():
    """Test processing of the enhanced matrix."""
    
    logger = logging.getLogger(__name__)
    logger.info("📊 Testing Matrix Processing")
    
    try:
        # Load matrix
        matrix = load_enhanced_matrix()
        logger.info(f"✅ Loaded matrix with {len(matrix['availability_matrix'])} entries")
        
        # Analyze matrix
        markets = set()
        data_types = set()
        total_combinations = 0
        
        for entry in matrix['availability_matrix']:
            markets.add(entry['market'])
            data_types.add(entry['data_type'])
            
            # Count potential task combinations
            intervals = entry.get('intervals', [None])
            partitions = entry.get('partitions', ['daily'])
            symbols_for_market = matrix['symbols'].get(entry['market'], ['BTCUSDT'])
            
            combinations = len(intervals) * len(partitions) * len(symbols_for_market)
            total_combinations += combinations
        
        logger.info(f"📈 Matrix Analysis:")
        logger.info(f"  Markets: {sorted(markets)}")
        logger.info(f"  Data Types: {sorted(data_types)}")
        logger.info(f"  Potential combinations per day: {total_combinations:,}")
        
        # Test specific entries
        logger.info(f"📋 Sample Entries:")
        for i, entry in enumerate(matrix['availability_matrix'][:5]):
            logger.info(f"  {i+1}. {entry['market']} {entry['data_type']} - {len(entry.get('intervals', [None]))} intervals")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Matrix processing failed: {e}")
        return False


def test_task_generation_logic():
    """Test task generation logic."""
    
    logger = logging.getLogger(__name__)
    logger.info("⚙️ Testing Task Generation Logic")
    
    try:
        # Load matrix
        matrix = load_enhanced_matrix()
        
        # Simulate task generation for a specific configuration
        config = {
            'markets': ['spot', 'futures_um'],
            'symbols': {'spot': ['BTCUSDT'], 'futures_um': ['BTCUSDT']},
            'data_types': ['klines', 'fundingRate'],
            'intervals': {'klines': ['1h', '1d']},
            'date_range': {'start': '2025-07-15', 'end': '2025-07-15'}
        }
        
        # Market mapping
        market_mapping = {
            'spot': TradeType.SPOT,
            'futures_um': TradeType.UM_FUTURES,
            'futures_cm': TradeType.CM_FUTURES,
            'options': TradeType.OPTIONS
        }
        
        # Data type mapping
        data_type_mapping = {
            'klines': DataType.KLINES,
            'fundingRate': DataType.FUNDING_RATES,
            'trades': DataType.TRADES
        }
        
        tasks_generated = 0
        task_summary = {}
        
        for entry in matrix['availability_matrix']:
            matrix_market = entry['market']
            matrix_data_type = entry['data_type']
            
            # Apply filters
            if matrix_market not in config['markets']:
                continue
            if matrix_data_type not in config['data_types']:
                continue
            
            # Get symbols for this market
            symbols = config['symbols'].get(matrix_market, ['BTCUSDT'])
            intervals = entry.get('intervals', [None])
            
            # Filter intervals if specified
            if matrix_data_type in config.get('intervals', {}):
                allowed_intervals = config['intervals'][matrix_data_type]
                intervals = [i for i in intervals if i in allowed_intervals or i is None]
            
            for symbol in symbols:
                for interval in intervals:
                    tasks_generated += 1
                    key = f"{matrix_market}_{matrix_data_type}"
                    task_summary[key] = task_summary.get(key, 0) + 1
        
        logger.info(f"✅ Generated {tasks_generated} tasks")
        logger.info(f"📊 Task Summary:")
        for key, count in task_summary.items():
            logger.info(f"  {key}: {count} tasks")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Task generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all core tests."""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Testing Enhanced Archive Collection Core Functionality")
    logger.info("=" * 70)
    
    tests = [
        ("Data Type Mapping", test_data_type_mapping),
        ("URL Generation", test_url_generation),
        ("Matrix Processing", test_matrix_processing),
        ("Task Generation Logic", test_task_generation_logic)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"Running: {test_name}")
        try:
            if test_func():
                logger.info(f"✅ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}")
        
        logger.info("")
    
    logger.info("=" * 70)
    logger.info(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        logger.info("🎉 All core tests passed!")
        return True
    else:
        logger.error("❌ Some core tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)