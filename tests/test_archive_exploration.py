#!/usr/bin/env python3
"""
Test script to explore and download all different types of data from Binance public archive.

This script will systematically download samples of each data type and analyze their schemas.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.append('.')

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.metrics import MetricsCollector
from src.crypto_lakehouse.workflows.archive_collection_updated import ArchiveCollectionWorkflow


async def download_data_type_sample(market: str, data_type: str, symbols: list, date: str):
    """Download a small sample of a specific data type."""
    
    logger = logging.getLogger(__name__)
    
    # Create targeted configuration for this data type
    config_data = {
        "workflow_type": "archive_collection",
        "matrix_path": "examples/binance_archive_matrix.json",
        "output_directory": f"test_output/schema_exploration/{market}_{data_type}",
        "markets": [market],
        "symbols": symbols[:2],  # Just 2 symbols for sampling
        "data_types": [data_type],
        "date_range": {
            "start": date,
            "end": date  # Single day for quick sampling
        },
        "max_parallel_downloads": 2,
        "force_redownload": False,
        "download_checksum": True,
        "timeout_seconds": 120,
        "batch_size": 10,
        "enable_monitoring": False,
        "use_cloud_storage": False,
        "local_data_dir": f"test_output/schema_exploration/{market}_{data_type}",
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "storage": {
            "type": "local",
            "compression": True,
            "partition_format": "year/month/day"
        }
    }
    
    # Create workflow configuration
    config = WorkflowConfig(config_data)
    
    # Initialize metrics collector
    metrics_collector = MetricsCollector()
    
    try:
        # Create and run workflow
        workflow = ArchiveCollectionWorkflow(config, metrics_collector)
        
        logger.info(f"Downloading {market} {data_type} sample for schema analysis...")
        results = await workflow.run()
        
        logger.info(f"✅ {market} {data_type}: {results['collection_stats']['successful_tasks']} successful")
        return results
        
    except Exception as e:
        logger.error(f"❌ {market} {data_type} failed: {e}")
        return None


async def explore_all_data_types():
    """Systematically explore all Binance archive data types."""
    
    logger = logging.getLogger(__name__)
    
    # Load the archive matrix
    matrix_path = Path("examples/binance_archive_matrix.json")
    with open(matrix_path, 'r') as f:
        matrix = json.load(f)
    
    logger.info("🔍 Starting systematic exploration of Binance archive data types")
    logger.info("=" * 80)
    
    # Use recent date for sampling
    sample_date = "2025-07-15"
    
    exploration_results = {}
    
    for entry in matrix["availability_matrix"]:
        market = entry["market"]
        data_type = entry["data_type"]
        
        # Get appropriate symbols for this market
        symbols = matrix["symbols"].get(market, ["BTCUSDT"])
        
        logger.info(f"🎯 Exploring {market} - {data_type}")
        
        # Download sample
        result = await download_data_type_sample(market, data_type, symbols, sample_date)
        
        exploration_results[f"{market}_{data_type}"] = {
            "market": market,
            "data_type": data_type,
            "symbols_tested": symbols[:2],
            "sample_date": sample_date,
            "download_result": result,
            "schema_analysis": "pending"
        }
        
        # Small delay between downloads
        await asyncio.sleep(1)
    
    logger.info("=" * 80)
    logger.info("🎉 Exploration phase completed!")
    
    return exploration_results


async def main():
    """Main function to run the exploration."""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Binance Archive Data Type Exploration")
    
    try:
        # Run exploration
        results = await explore_all_data_types()
        
        # Save results for analysis
        results_path = Path("test_output/schema_exploration/exploration_results.json")
        results_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"📝 Exploration results saved to: {results_path}")
        
        # Print summary
        logger.info("=" * 80)
        logger.info("EXPLORATION SUMMARY")
        logger.info("=" * 80)
        
        for key, result in results.items():
            market = result["market"]
            data_type = result["data_type"]
            download_success = result["download_result"] is not None
            
            status = "✅ SUCCESS" if download_success else "❌ FAILED"
            logger.info(f"{market:12} | {data_type:12} | {status}")
        
        logger.info("=" * 80)
        
        return results
        
    except Exception as e:
        logger.error(f"Exploration failed: {e}")
        raise


if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0)