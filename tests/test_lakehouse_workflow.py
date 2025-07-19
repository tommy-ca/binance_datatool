#!/usr/bin/env python3
"""
Test script for crypto lakehouse archive workflow.

This script demonstrates the lakehouse workflow implementation by executing
an archive collection using the new architecture patterns.
"""

import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from crypto_lakehouse.workflows.archive_collection import ArchiveCollectionWorkflow
from crypto_lakehouse.core.config import WorkflowConfig
from crypto_lakehouse.core.utils import setup_logging


def main():
    """Test the lakehouse archive collection workflow."""
    # Setup logging
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("Starting crypto lakehouse workflow test")
    
    # Create test configuration
    config_data = {
        'workflow_type': 'archive_collection',
        'matrix_path': 'legacy/scripts/sample-data/archive-matrix/binance_archive_matrix.json',
        'output_directory': 'lakehouse-test-output',
        'markets': ['spot'],
        'symbols': ['BTCUSDT'],
        'data_types': ['klines'],
        'default_date': '2025-07-15',
        'max_parallel_downloads': 2,
        'download_checksum': True,
        'force_redownload': False,
        'timeout_seconds': 300
    }
    
    try:
        # Create workflow configuration
        config = WorkflowConfig.from_dict(config_data)
        logger.info("Configuration created successfully")
        
        # Create and execute workflow
        workflow = ArchiveCollectionWorkflow(config)
        logger.info("Workflow initialized successfully")
        
        # Execute workflow
        metrics = workflow.execute()
        
        # Log results
        logger.info("Workflow execution completed!")
        logger.info(f"Execution state: {metrics.execution_state}")
        logger.info(f"Duration: {metrics.duration:.2f} seconds")
        logger.info(f"Results: {metrics.results}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Workflow test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())