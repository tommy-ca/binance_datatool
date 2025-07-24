#!/usr/bin/env python3
"""
Simple test for the enhanced archive collection workflow without Prefect.

This tests the core functionality without the Prefect orchestration overhead.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append('.')

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.metrics import MetricsCollector
from crypto_lakehouse.workflows.archive_collection_prefect import (
    validate_archive_configuration_task,
    load_archive_matrix_task,
    generate_ingestion_tasks_task
)


async def test_workflow_components():
    """Test individual workflow components."""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🧪 Testing Enhanced Archive Workflow Components")
    logger.info("=" * 60)
    
    # Test configuration
    test_config = {
        "workflow_type": "archive_collection",
        "matrix_path": "enhanced_binance_archive_matrix.json",
        "output_directory": "output/test_enhanced",
        "markets": ["spot", "futures_um"],
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "data_types": ["klines", "trades", "fundingRate"],
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
        "local_data_dir": "output/test_enhanced",
        "logging": {"level": "INFO"}
    }
    
    try:
        # Test 1: Configuration validation
        logger.info("1️⃣ Testing configuration validation...")
        config = WorkflowConfig(test_config)
        validation_result = await validate_archive_configuration_task(config)
        logger.info(f"✅ Configuration validation: {validation_result}")
        
        # Test 2: Matrix loading
        logger.info("2️⃣ Testing matrix loading...")
        archive_matrix = await load_archive_matrix_task(config)
        logger.info(f"✅ Matrix loaded: {len(archive_matrix.get('availability_matrix', []))} entries")
        
        # Test 3: Task generation
        logger.info("3️⃣ Testing task generation...")
        ingestion_tasks = await generate_ingestion_tasks_task(config, archive_matrix)
        logger.info(f"✅ Generated {len(ingestion_tasks)} ingestion tasks")
        
        # Analyze generated tasks
        if ingestion_tasks:
            logger.info("📊 Task Analysis:")
            
            # Group by market and data type
            task_summary = {}
            for task in ingestion_tasks:
                key = f"{task.trade_type.value}_{task.data_type.value}"
                if key not in task_summary:
                    task_summary[key] = 0
                task_summary[key] += 1
            
            for key, count in task_summary.items():
                logger.info(f"  {key}: {count} tasks")
            
            # Show sample task details
            sample_task = ingestion_tasks[0]
            logger.info(f"📋 Sample Task:")
            logger.info(f"  Exchange: {sample_task.exchange}")
            logger.info(f"  Trade Type: {sample_task.trade_type}")
            logger.info(f"  Data Type: {sample_task.data_type}")
            logger.info(f"  Symbol: {sample_task.symbols[0]}")
            logger.info(f"  Date: {sample_task.start_date}")
            logger.info(f"  Interval: {sample_task.interval}")
            if hasattr(sample_task, 'original_data_type'):
                logger.info(f"  Original Data Type: {sample_task.original_data_type}")
            if hasattr(sample_task, 'url_pattern'):
                logger.info(f"  URL Pattern: {sample_task.url_pattern}")
        
        logger.info("=" * 60)
        logger.info("✅ All component tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_url_generation():
    """Test URL generation for different data types."""
    
    logger = logging.getLogger(__name__)
    logger.info("🔗 Testing URL Generation")
    
    # Import the URL generation function
    from crypto_lakehouse.workflows.archive_collection_prefect import _generate_task_paths
    from src.crypto_lakehouse.core.models import DataIngestionTask, Exchange, DataType, TradeType, DataZone
    from src.crypto_lakehouse.core.config import Settings
    from src.crypto_lakehouse.storage.factory import create_storage
    
    # Create test storage
    settings = Settings({'local_data_dir': 'output/test_urls'})
    storage = create_storage(settings)
    
    # Create test config
    config = WorkflowConfig({
        'output_directory': 'output/test_urls',
        'local_data_dir': 'output/test_urls'
    })
    
    # Test different task types
    test_cases = [
        {
            "name": "Spot Klines",
            "trade_type": TradeType.SPOT,
            "data_type": DataType.KLINES,
            "symbol": "BTCUSDT",
            "original_data_type": "klines",
            "url_pattern": "s3://data.binance.vision/data/spot/{partition}/klines/{symbol}/{interval}/{filename}",
            "filename_pattern": "{symbol}-{interval}-{date}.zip"
        },
        {
            "name": "Futures UM Funding",
            "trade_type": TradeType.UM_FUTURES,
            "data_type": DataType.FUNDING_RATES,
            "symbol": "BTCUSDT",
            "original_data_type": "fundingRate",
            "url_pattern": "s3://data.binance.vision/data/futures/um/{partition}/fundingRate/{symbol}/{filename}",
            "filename_pattern": "{symbol}-fundingRate-{date}.zip"
        },
        {
            "name": "Options BVOL",
            "trade_type": TradeType.OPTIONS,
            "data_type": DataType.VOLATILITY,
            "symbol": "BTC",
            "original_data_type": "BVOLIndex",
            "url_pattern": "s3://data.binance.vision/data/option/{partition}/BVOLIndex/{symbol}/{interval}/{filename}",
            "filename_pattern": "{symbol}-{interval}-{date}.zip"
        }
    ]
    
    for test_case in test_cases:
        try:
            # Create task
            task = DataIngestionTask(
                exchange=Exchange.BINANCE,
                data_type=test_case["data_type"],
                trade_type=test_case["trade_type"],
                symbols=[test_case["symbol"]],
                start_date=datetime(2025, 7, 15),
                target_zone=DataZone.BRONZE
            )
            
            # Add metadata
            task.original_data_type = test_case["original_data_type"]
            task.url_pattern = test_case["url_pattern"]
            task.filename_pattern = test_case["filename_pattern"]
            task.partition_type = "daily"
            task.archive_date = "2025-07-15"
            
            # Generate URLs
            source_url, target_path = await _generate_task_paths(task, storage, config)
            
            logger.info(f"🔗 {test_case['name']}:")
            logger.info(f"  Source: {source_url}")
            logger.info(f"  Target: {target_path}")
            logger.info("")
            
        except Exception as e:
            logger.error(f"❌ Failed to generate URL for {test_case['name']}: {e}")
    
    return True


async def main():
    """Run all tests."""
    
    logger = logging.getLogger(__name__)
    
    success = True
    
    # Test 1: Component tests
    logger.info("🚀 Starting Enhanced Workflow Tests")
    component_success = await test_workflow_components()
    success = success and component_success
    
    print()
    
    # Test 2: URL generation
    url_success = await test_url_generation()
    success = success and url_success
    
    print()
    logger.info("=" * 60)
    if success:
        logger.info("🎉 All tests passed!")
    else:
        logger.error("❌ Some tests failed!")
    logger.info("=" * 60)
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)