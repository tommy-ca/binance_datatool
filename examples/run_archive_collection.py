#!/usr/bin/env python3
"""
Example script to run the enhanced Archive Collection Workflow.

This script demonstrates how to use the updated ArchiveCollectionWorkflow
with system design compliance and modern lakehouse patterns.
"""

import asyncio
import json
import logging
from pathlib import Path

from src.crypto_lakehouse.core.config import WorkflowConfig
from src.crypto_lakehouse.core.metrics import MetricsCollector
from src.crypto_lakehouse.workflows.archive_collection_updated import ArchiveCollectionWorkflow


async def main():
    """Run the archive collection workflow."""
    
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
        
        # Create workflow configuration
        config = WorkflowConfig(config_data)
        
        # Initialize metrics collector
        metrics_collector = MetricsCollector(
            enable_prometheus=config.get('enable_monitoring', True),
            enable_logging=True
        )
        
        # Create and run workflow
        workflow = ArchiveCollectionWorkflow(config, metrics_collector)
        
        logger.info("Starting enhanced archive collection workflow")
        results = await workflow.run()
        
        # Print results summary
        logger.info("=" * 70)
        logger.info("ARCHIVE COLLECTION COMPLETED")
        logger.info("=" * 70)
        logger.info(f"Total Tasks: {results['collection_stats']['total_tasks']}")
        logger.info(f"Successful: {results['collection_stats']['successful_tasks']}")
        logger.info(f"Failed: {results['collection_stats']['failed_tasks']}")
        logger.info(f"Skipped: {results['collection_stats']['skipped_tasks']}")
        logger.info(f"Success Rate: {results['success_rate']:.1f}%")
        logger.info(f"Total Size: {results['total_size_formatted']}")
        logger.info(f"Processing Time: {results['collection_stats']['processing_time_seconds']:.2f}s")
        logger.info(f"Output Directory: {results['output_directory']}")
        logger.info(f"Storage Zones: {', '.join(results['storage_zones_used'])}")
        
        if results['ingestion_metadata_id']:
            logger.info(f"Metadata ID: {results['ingestion_metadata_id']}")
        
        logger.info("=" * 70)
        
        return results
        
    except Exception as e:
        logger.error(f"Archive collection failed: {e}")
        raise


if __name__ == "__main__":
    # Run the workflow
    results = asyncio.run(main())
    
    # Exit with appropriate code
    if results['success_rate'] >= 90:
        exit(0)  # Success
    elif results['success_rate'] >= 50:
        exit(1)  # Partial success
    else:
        exit(2)  # Mostly failed