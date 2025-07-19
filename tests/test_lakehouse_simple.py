#!/usr/bin/env python3
"""
Simple test script for crypto lakehouse archive workflow.
Tests the lakehouse implementation directly without complex imports.
"""

import sys
import logging
from pathlib import Path
import json

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import directly to avoid init conflicts
from crypto_lakehouse.workflows.archive_collection import ArchiveCollectionWorkflow
from crypto_lakehouse.core.config import WorkflowConfig
from crypto_lakehouse.core.utils import setup_logging


def main():
    """Test the lakehouse archive collection workflow."""
    # Setup logging
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    logger.info("Starting simple crypto lakehouse workflow test")
    
    # Create simple test configuration dictionary
    config_data = {
        'workflow_type': 'archive_collection',
        'matrix_path': 'legacy/scripts/sample-data/archive-matrix/binance_archive_matrix.json',
        'output_directory': 'lakehouse-simple-test',
        'markets': ['spot'],
        'symbols': ['BTCUSDT'],
        'data_types': ['klines'],
        'default_date': '2025-07-15',
        'max_parallel_downloads': 1,
        'download_checksum': True,
        'force_redownload': False,
        'timeout_seconds': 300
    }
    
    try:
        # Create workflow configuration using simple constructor
        config = WorkflowConfig(config_data, validate=False)  # Skip validation initially
        logger.info("Configuration created successfully")
        
        # Validate manually
        config.validate()
        logger.info("Configuration validated successfully")
        
        # Create and execute workflow
        workflow = ArchiveCollectionWorkflow(config)
        logger.info("Workflow initialized successfully")
        
        # Execute workflow
        logger.info("Starting workflow execution...")
        metrics = workflow.execute()
        
        # Log results
        logger.info("Workflow execution completed!")
        logger.info(f"Execution state: {metrics.execution_state}")
        logger.info(f"Duration: {metrics.duration:.2f} seconds")
        logger.info(f"Results: {metrics.results}")
        
        # Save results for inspection
        results_file = Path("lakehouse-simple-test") / "test_results.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        results_summary = {
            "test_name": "lakehouse_simple_test",
            "execution_state": metrics.execution_state,
            "duration": metrics.duration,
            "results": metrics.results,
            "config": config.to_dict()
        }
        
        with open(results_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        logger.info(f"Test results saved to: {results_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())