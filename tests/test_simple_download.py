#!/usr/bin/env python3
"""
Simple test to verify that the Prefect workflow can download actual files.
This test uses HTTP URLs instead of S3 for more reliable testing.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append('.')

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.metrics import MetricsCollector
from src.crypto_lakehouse.workflows.archive_collection_prefect import archive_collection_flow


async def test_simple_download():
    """Test with a simple, reliable configuration."""
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    logger.info("🧪 Starting simple Prefect workflow test")
    
    # Create minimal configuration
    config_data = {
        'workflow_type': 'archive_collection',
        'matrix_path': 'examples/binance_archive_matrix.json',
        'output_directory': 'test_output/simple_test',
        'markets': ['spot'],  # Only spot
        'symbols': ['BTCUSDT'],  # Only one symbol
        'data_types': ['klines'],  # Only klines
        'date_range': {
            'start': '2024-01-01',  # Use older date that definitely exists
            'end': '2024-01-01'     # Single day
        },
        'max_parallel_downloads': 1,  # Single download to avoid complexity
        'batch_size': 1,
        'enable_batch_mode': False,  # Disable batch mode for simplicity
        'force_redownload': True,   # Force download to see activity
        'download_checksum': False,  # Disable checksum for simplicity
        'timeout_seconds': 60,      # Shorter timeout
        'use_cloud_storage': False,
        'enable_monitoring': True
    }
    
    logger.info(f"Configuration: {json.dumps(config_data, indent=2)}")
    
    try:
        config = WorkflowConfig(config_data)
        metrics = MetricsCollector()
        
        logger.info("🚀 Starting Prefect archive collection flow...")
        
        # Run the workflow
        results = await archive_collection_flow(config, metrics)
        
        logger.info("📊 RESULTS:")
        logger.info("=" * 50)
        logger.info(f"Status: {results.get('status')}")
        
        if 'collection_stats' in results:
            stats = results['collection_stats']
            logger.info(f"Total tasks: {stats.get('total_tasks', 0)}")
            logger.info(f"Successful: {stats.get('successful_tasks', 0)}")
            logger.info(f"Failed: {stats.get('failed_tasks', 0)}")
            logger.info(f"Skipped: {stats.get('skipped_tasks', 0)}")
            logger.info(f"Success rate: {results.get('success_rate', 0):.1f}%")
            logger.info(f"Total size: {results.get('total_size_formatted', 'N/A')}")
            logger.info(f"Processing time: {stats.get('processing_time_seconds', 0):.2f}s")
        
        logger.info(f"Output directory: {results.get('output_directory')}")
        
        # Check what files were created
        output_dir = Path(config_data['output_directory'])
        if output_dir.exists():
            logger.info("\\n📁 Created files:")
            for file_path in output_dir.rglob('*'):
                if file_path.is_file():
                    size = file_path.stat().st_size
                    logger.info(f"  {file_path} ({size} bytes)")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_prefect_status():
    """Check if the test can proceed."""
    logger = logging.getLogger(__name__)
    
    try:
        # Check if we can import everything
        from src.crypto_lakehouse.core.config import WorkflowConfig
        from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
        
        logger.info("✅ All imports successful")
        
        # Check if matrix file exists
        matrix_path = Path('examples/binance_archive_matrix.json')
        if matrix_path.exists():
            logger.info(f"✅ Archive matrix found: {matrix_path}")
        else:
            logger.error(f"❌ Archive matrix not found: {matrix_path}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Pre-flight check failed: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger = logging.getLogger(__name__)
    logger.info("🎯 Simple Prefect Workflow Test")
    logger.info("=" * 50)
    
    # Pre-flight checks
    if not check_prefect_status():
        logger.error("❌ Pre-flight checks failed")
        sys.exit(1)
    
    # Run the test
    try:
        results = asyncio.run(test_simple_download())
        
        if results and results.get('status') == 'success':
            logger.info("\\n🎉 TEST PASSED!")
            logger.info("The Prefect workflow is working correctly.")
            sys.exit(0)
        else:
            logger.error("\\n❌ TEST FAILED!")
            logger.error("The workflow did not complete successfully.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\\n⏹ Test interrupted by user")
        sys.exit(2)
    except Exception as e:
        logger.error(f"\\n💥 Test crashed: {e}")
        sys.exit(3)