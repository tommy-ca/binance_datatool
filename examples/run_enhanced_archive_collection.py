#!/usr/bin/env python3
"""
Enhanced Archive Collection Example.

This script demonstrates the enhanced Prefect-based archive collection workflow
with support for all Binance markets (spot, futures UM/CM, options) and all data types.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.metrics import MetricsCollector
from src.crypto_lakehouse.workflows.archive_collection_prefect import (
    PrefectArchiveCollectionWorkflow,
    archive_collection_flow
)


async def main():
    """Run the enhanced archive collection workflow."""
    
    # Setup comprehensive logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🚀 Starting Enhanced Binance Archive Collection")
        logger.info("=" * 80)
        logger.info("Markets: Spot, Futures UM/CM, Options")
        logger.info("Data Types: All available types per market")
        logger.info("=" * 80)
        
        # Load enhanced configuration
        config_path = Path(__file__).parent / "enhanced_archive_collection_config.json"
        
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return False
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Update matrix path to use enhanced matrix
        matrix_path = Path(__file__).parent.parent / "enhanced_binance_archive_matrix.json"
        config_data['matrix_path'] = str(matrix_path)
        
        # Create workflow configuration
        config = WorkflowConfig(config_data)
        
        # Initialize enhanced metrics collector
        metrics_collector = MetricsCollector()
        
        # Create and run enhanced workflow
        workflow = PrefectArchiveCollectionWorkflow(config, metrics_collector)
        
        logger.info("📊 Configuration Summary:")
        logger.info(f"  Markets: {config.get('markets', [])}")
        logger.info(f"  Data Types: {len(config.get('data_types', []))} types")
        logger.info(f"  Date Range: {config.get('date_range', {})}")
        logger.info(f"  Max Parallel: {config.get('max_parallel_downloads', 8)}")
        logger.info(f"  Batch Size: {config.get('batch_size', 100)}")
        logger.info(f"  Output: {config.get('output_directory', 'output')}")
        logger.info("")
        
        # Execute the enhanced workflow
        logger.info("🔄 Starting enhanced archive collection...")
        results = await workflow.execute()
        
        # Display comprehensive results
        logger.info("=" * 80)
        logger.info("🎉 ENHANCED ARCHIVE COLLECTION COMPLETED")
        logger.info("=" * 80)
        
        collection_stats = results.get('collection_stats', {})
        logger.info(f"📈 Collection Statistics:")
        logger.info(f"  Total Tasks: {collection_stats.get('total_tasks', 0):,}")
        logger.info(f"  Successful: {collection_stats.get('successful_tasks', 0):,}")
        logger.info(f"  Failed: {collection_stats.get('failed_tasks', 0):,}")
        logger.info(f"  Skipped: {collection_stats.get('skipped_tasks', 0):,}")
        logger.info(f"  Success Rate: {results.get('success_rate', 0):.1f}%")
        logger.info("")
        
        logger.info(f"💾 Data Summary:")
        logger.info(f"  Total Size: {results.get('total_size_formatted', '0B')}")
        logger.info(f"  Processing Time: {collection_stats.get('processing_time_seconds', 0):.2f}s")
        logger.info(f"  Output Directory: {results.get('output_directory', 'Unknown')}")
        logger.info(f"  Storage Zones: {', '.join(results.get('storage_zones_used', []))}")
        
        if results.get('ingestion_metadata_id'):
            logger.info(f"  Metadata ID: {results['ingestion_metadata_id']}")
        
        logger.info("")
        
        # Performance metrics
        total_tasks = collection_stats.get('total_tasks', 0)
        processing_time = collection_stats.get('processing_time_seconds', 1)
        if total_tasks > 0 and processing_time > 0:
            throughput = total_tasks / processing_time
            logger.info(f"⚡ Performance Metrics:")
            logger.info(f"  Throughput: {throughput:.1f} tasks/second")
            
            total_bytes = collection_stats.get('total_size_bytes', 0)
            if total_bytes > 0:
                mbps = (total_bytes / 1024 / 1024) / processing_time
                logger.info(f"  Bandwidth: {mbps:.1f} MB/s")
        
        logger.info("=" * 80)
        
        # Determine exit status
        success_rate = results.get('success_rate', 0)
        if success_rate >= 95:
            logger.info("✅ Collection completed successfully!")
            return True
        elif success_rate >= 80:
            logger.warning("⚠️  Collection completed with some failures")
            return True
        else:
            logger.error("❌ Collection had significant failures")
            return False
        
    except Exception as e:
        logger.error(f"💥 Enhanced archive collection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_single_market(market: str, data_types: list, symbols: list):
    """Test collection for a single market with specific data types."""
    
    logger = logging.getLogger(__name__)
    logger.info(f"🧪 Testing {market} market collection")
    
    # Create test configuration
    test_config = {
        "workflow_type": "archive_collection",
        "matrix_path": str(Path(__file__).parent.parent / "enhanced_binance_archive_matrix.json"),
        "output_directory": f"output/test_{market}",
        "markets": [market],
        "symbols": {market: symbols},
        "data_types": data_types,
        "date_range": {
            "start": "2025-07-15",
            "end": "2025-07-15"
        },
        "max_parallel_downloads": 4,
        "batch_size": 20,
        "force_redownload": False,
        "download_checksum": True,
        "timeout_seconds": 300,
        "enable_batch_mode": True,
        "environment": "testing",
        "enable_monitoring": False,
        "local_data_dir": f"output/test_{market}",
        "logging": {"level": "INFO"}
    }
    
    config = WorkflowConfig(test_config)
    metrics = MetricsCollector()
    
    try:
        results = await archive_collection_flow(config, metrics)
        success_rate = results.get('success_rate', 0)
        total_tasks = results.get('collection_stats', {}).get('total_tasks', 0)
        
        logger.info(f"✅ {market} test: {total_tasks} tasks, {success_rate:.1f}% success")
        return success_rate > 80
        
    except Exception as e:
        logger.error(f"❌ {market} test failed: {e}")
        return False


async def run_market_tests():
    """Run individual market tests before full collection."""
    
    logger = logging.getLogger(__name__)
    logger.info("🧪 Running individual market tests...")
    
    # Test configurations for each market
    test_configs = [
        {
            "market": "spot",
            "data_types": ["klines", "trades"],
            "symbols": ["BTCUSDT"]
        },
        {
            "market": "futures_um", 
            "data_types": ["klines", "fundingRate"],
            "symbols": ["BTCUSDT"]
        },
        {
            "market": "futures_cm",
            "data_types": ["klines", "fundingRate"],
            "symbols": ["BTCUSD_PERP"]
        },
        {
            "market": "options",
            "data_types": ["BVOLIndex"],
            "symbols": ["BTC"]
        }
    ]
    
    results = []
    for test_config in test_configs:
        success = await test_single_market(
            test_config["market"],
            test_config["data_types"],
            test_config["symbols"]
        )
        results.append((test_config["market"], success))
    
    # Summary
    successful_markets = sum(1 for _, success in results if success)
    total_markets = len(results)
    
    logger.info(f"🧪 Market tests completed: {successful_markets}/{total_markets} successful")
    for market, success in results:
        status = "✅" if success else "❌"
        logger.info(f"  {status} {market}")
    
    return successful_markets == total_markets


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Binance Archive Collection")
    parser.add_argument("--test-markets", action="store_true", 
                       help="Run individual market tests first")
    parser.add_argument("--market", type=str, 
                       help="Test specific market only")
    args = parser.parse_args()
    
    if args.test_markets:
        success = asyncio.run(run_market_tests())
        sys.exit(0 if success else 1)
    elif args.market:
        # Test specific market
        market_configs = {
            "spot": (["klines", "trades", "aggTrades"], ["BTCUSDT", "ETHUSDT"]),
            "futures_um": (["klines", "fundingRate", "premiumIndex"], ["BTCUSDT", "ETHUSDT"]),
            "futures_cm": (["klines", "fundingRate"], ["BTCUSD_PERP", "ETHUSD_PERP"]),
            "options": (["BVOLIndex", "EOHSummary"], ["BTC", "ETH"])
        }
        
        if args.market in market_configs:
            data_types, symbols = market_configs[args.market]
            success = asyncio.run(test_single_market(args.market, data_types, symbols))
            sys.exit(0 if success else 1)
        else:
            print(f"Unknown market: {args.market}")
            print(f"Available markets: {', '.join(market_configs.keys())}")
            sys.exit(1)
    else:
        # Run full enhanced collection
        success = asyncio.run(main())
        sys.exit(0 if success else 1)