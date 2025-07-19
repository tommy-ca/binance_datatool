#!/usr/bin/env python3
"""
Example script to run the Prefect-based Archive Collection Workflow.

This script demonstrates how to use the Prefect-orchestrated ArchiveCollectionWorkflow
with enhanced observability, error handling, and parallel execution capabilities.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.metrics import MetricsCollector
from src.crypto_lakehouse.workflows.archive_collection_prefect import (
    PrefectArchiveCollectionWorkflow,
    archive_collection_flow
)


async def main():
    """Run the Prefect-based archive collection workflow."""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config_path = Path(__file__).parent / "archive_collection_config.json"
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        # Create smaller test configuration for demonstration
        test_config_data = {
            'workflow_type': 'archive_collection',
            'matrix_path': str(Path(__file__).parent / "binance_archive_matrix.json"),
            'output_directory': 'test_output/prefect_archive',
            'markets': ['spot'],  # Only spot for testing
            'symbols': ['BTCUSDT'],  # Only one symbol for testing
            'data_types': ['klines'],  # Only klines for testing
            'date_range': {
                'start': '2025-07-15',
                'end': '2025-07-15'  # Single day for testing
            },
            'max_parallel_downloads': 2,
            'batch_size': 5,
            'enable_batch_mode': True,
            'force_redownload': False,
            'download_checksum': True,
            'timeout_seconds': 300,
            'environment': 'development',
            'enable_monitoring': True,
            'use_cloud_storage': False
        }
        
        # Create workflow configuration
        config = WorkflowConfig(test_config_data)
        
        # Initialize metrics collector
        metrics_collector = MetricsCollector()
        
        logger.info("Starting Prefect-orchestrated archive collection workflow")
        logger.info("=" * 70)
        logger.info("PREFECT WORKFLOW CONFIGURATION")
        logger.info("=" * 70)
        logger.info(f"Markets: {config.get('markets')}")
        logger.info(f"Symbols: {config.get('symbols')}")
        logger.info(f"Data Types: {config.get('data_types')}")
        logger.info(f"Date Range: {config.get('date_range')}")
        logger.info(f"Batch Mode: {config.get('enable_batch_mode')}")
        logger.info(f"Batch Size: {config.get('batch_size')}")
        logger.info(f"Max Parallel: {config.get('max_parallel_downloads')}")
        logger.info("=" * 70)
        
        # Option 1: Run the flow directly
        logger.info("🚀 Running Prefect flow directly...")
        results = await archive_collection_flow(config, metrics_collector)
        
        # Option 2: Use the workflow class (uncomment to use this instead)
        # workflow = PrefectArchiveCollectionWorkflow(config, metrics_collector)
        # results = await workflow.execute()
        
        # Print results summary
        logger.info("=" * 70)
        logger.info("PREFECT ARCHIVE COLLECTION COMPLETED")
        logger.info("=" * 70)
        logger.info(f"Status: {results.get('status', 'unknown')}")
        
        if 'collection_stats' in results:
            stats = results['collection_stats']
            logger.info(f"Total Tasks: {stats['total_tasks']}")
            logger.info(f"Successful: {stats['successful_tasks']}")
            logger.info(f"Failed: {stats['failed_tasks']}")
            logger.info(f"Skipped: {stats['skipped_tasks']}")
            logger.info(f"Success Rate: {results.get('success_rate', 0):.1f}%")
            logger.info(f"Total Size: {results.get('total_size_formatted', 'N/A')}")
            logger.info(f"Processing Time: {stats['processing_time_seconds']:.2f}s")
        
        logger.info(f"Output Directory: {results.get('output_directory', 'N/A')}")
        logger.info(f"Storage Zones: {', '.join(results.get('storage_zones_used', []))}")
        
        if results.get('ingestion_metadata_id'):
            logger.info(f"Metadata ID: {results['ingestion_metadata_id']}")
        
        logger.info("=" * 70)
        
        # Print Prefect-specific information
        logger.info("🎯 PREFECT ORCHESTRATION BENEFITS")
        logger.info("=" * 70)
        logger.info("✅ Enhanced Error Handling: Automatic retries and error propagation")
        logger.info("✅ Task Observability: Individual task tracking and logging")
        logger.info("✅ Parallel Execution: Concurrent task runner for optimal performance")
        logger.info("✅ State Management: Automatic workflow and task state tracking")
        logger.info("✅ Retry Logic: Configurable retry policies for robustness")
        logger.info("✅ Monitoring: Built-in metrics and performance tracking")
        logger.info("=" * 70)
        
        # Log completion
        logger.info("✅ Prefect workflow completed successfully!")
        
        return results
        
    except Exception as e:
        logger.error(f"Prefect archive collection failed: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_prefect_configuration():
    """Test Prefect workflow configuration."""
    print("🧪 Testing Prefect Configuration")
    print("=" * 50)
    
    try:
        # Test configuration
        config_data = {
            'workflow_type': 'archive_collection',
            'matrix_path': 'examples/binance_archive_matrix.json',
            'output_directory': 'test_output',
            'markets': ['spot'],
            'symbols': ['BTCUSDT'],
            'data_types': ['klines'],
            'max_parallel_downloads': 2
        }
        
        config = WorkflowConfig(config_data)
        workflow = PrefectArchiveCollectionWorkflow(config)
        
        # Test flow configuration
        flow_config = workflow.get_flow_config()
        
        print("✅ Prefect workflow initialization: SUCCESS")
        print(f"✅ Flow name: {flow_config['name']}")
        print(f"✅ Flow description: {flow_config['description']}")
        print(f"✅ Flow tags: {flow_config['tags']}")
        print(f"✅ Flow version: {flow_config['version']}")
        print(f"✅ Task runner: {type(flow_config['task_runner']).__name__}")
        print(f"✅ Retries: {flow_config['retries']}")
        print(f"✅ Retry delay: {flow_config['retry_delay_seconds']}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Prefect configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        # Test configuration first
        config_success = test_prefect_configuration()
        
        if config_success:
            print("\n" + "=" * 70)
            print("RUNNING PREFECT WORKFLOW")
            print("=" * 70)
            
            # Run the workflow
            results = asyncio.run(main())
            
            # Print final summary
            print("\n" + "🎉 PREFECT WORKFLOW COMPLETED!")
            print(f"Status: {results.get('status', 'unknown')}")
            if 'collection_stats' in results:
                stats = results['collection_stats']
                print(f"Files processed: {stats.get('successful_tasks', 0)}")
                print(f"Success rate: {results.get('success_rate', 0):.1f}%")
            
            # Exit with appropriate code
            if results and results.get('status') == 'success':
                success_rate = results.get('success_rate', 0)
                if success_rate >= 90:
                    print("✅ EXCELLENT SUCCESS RATE!")
                    exit(0)  # Great success
                elif success_rate >= 50:
                    print("⚠️ PARTIAL SUCCESS")
                    exit(1)  # Partial success
                else:
                    print("❌ LOW SUCCESS RATE")
                    exit(2)  # Mostly failed
            else:
                print("❌ WORKFLOW FAILED")
                exit(3)  # Workflow failed
        else:
            print("❌ Configuration test failed, skipping workflow execution")
            exit(4)  # Configuration error
            
    except KeyboardInterrupt:
        print("\n⏹ Workflow interrupted by user")
        exit(5)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(6)