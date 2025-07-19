"""Enhanced Archive Collection Workflow with S3 Direct Sync Integration.

This module integrates S3 to S3 direct sync capabilities into the existing archive
collection workflow, reducing operations by eliminating local storage requirements
and enabling direct transfers between S3 buckets.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner

from ..core.base import BaseWorkflow
from ..core.config import WorkflowConfig
from ..core.exceptions import WorkflowError, ConfigurationError
from ..core.metrics import MetricsCollector
from ..core.models import (
    DataIngestionTask,
    DataType,
    DataZone,
    Exchange,
    Interval,
    TradeType,
    IngestionMetadata
)
from ..storage.factory import create_storage
from ..storage.base import BaseStorage
from ..ingestion.s3_direct_sync import S3DirectSyncDownloader, EnhancedBulkDownloader

logger = logging.getLogger(__name__)


@task(retries=3, retry_delay_seconds=60, name="validate-enhanced-archive-configuration")
async def validate_enhanced_archive_configuration_task(config: WorkflowConfig) -> bool:
    """Validate enhanced archive collection configuration with S3 direct sync options."""
    logger.info("Validating enhanced archive collection configuration")
    
    # Standard validation
    required_fields = [
        'workflow_type', 'matrix_path', 'output_directory',
        'markets', 'symbols', 'data_types'
    ]
    missing_fields = [field for field in required_fields if not config.get(field)]
    
    if missing_fields:
        raise ConfigurationError(f"Missing required configuration: {missing_fields}")
    
    # Validate S3 direct sync configuration if enabled
    if config.get('enable_s3_direct_sync', False):
        s3_required_fields = ['destination_bucket']
        s3_missing = [field for field in s3_required_fields if not config.get(field)]
        
        if s3_missing:
            raise ConfigurationError(f"S3 direct sync enabled but missing: {s3_missing}")
        
        # Validate sync mode
        sync_mode = config.get('sync_mode', 'copy')
        if sync_mode not in ['copy', 'sync']:
            raise ConfigurationError(f"Invalid sync_mode: {sync_mode}. Must be 'copy' or 'sync'")
        
        logger.info(f"S3 direct sync enabled - Mode: {sync_mode}, Bucket: {config.get('destination_bucket')}")
    
    # Validate operation mode selection
    operation_mode = config.get('operation_mode', 'auto')
    if operation_mode not in ['auto', 'direct_sync', 'traditional']:
        raise ConfigurationError(f"Invalid operation_mode: {operation_mode}")
    
    logger.info("Enhanced configuration validation completed successfully")
    return True


@task(retries=2, retry_delay_seconds=30, name="determine-optimal-operation-mode")
async def determine_optimal_operation_mode_task(
    config: WorkflowConfig,
    ingestion_tasks: List[DataIngestionTask]
) -> str:
    """Determine the optimal operation mode based on configuration and task analysis."""
    
    # Check explicit mode setting
    operation_mode = config.get('operation_mode', 'auto')
    if operation_mode != 'auto':
        logger.info(f"Using explicit operation mode: {operation_mode}")
        return operation_mode
    
    # Auto-determine optimal mode
    s3_direct_available = (
        config.get('enable_s3_direct_sync', False) and 
        config.get('destination_bucket')
    )
    
    if not s3_direct_available:
        logger.info("S3 direct sync not available, using traditional mode")
        return 'traditional'
    
    # Analyze tasks to determine if S3 direct sync is beneficial
    s3_source_count = 0
    total_tasks = len(ingestion_tasks)
    
    for task in ingestion_tasks:
        # Check if task has S3 source (will be determined during path generation)
        # For now, assume Binance archive tasks are S3-based
        if hasattr(task, 'exchange') and task.exchange == Exchange.BINANCE:
            s3_source_count += 1
    
    s3_source_ratio = s3_source_count / total_tasks if total_tasks > 0 else 0
    
    # Use direct sync if majority of sources are S3-based
    if s3_source_ratio >= 0.8:  # 80% threshold
        optimal_mode = 'direct_sync'
        logger.info(f"Auto-selected direct_sync mode ({s3_source_ratio:.1%} S3 sources)")
    else:
        optimal_mode = 'traditional'
        logger.info(f"Auto-selected traditional mode ({s3_source_ratio:.1%} S3 sources)")
    
    return optimal_mode


@task(retries=3, retry_delay_seconds=60, name="execute-enhanced-batch-downloads")
async def execute_enhanced_batch_downloads_task(
    tasks: List[DataIngestionTask],
    operation_mode: str,
    storage: BaseStorage,
    config: WorkflowConfig
) -> List[Dict[str, Any]]:
    """Execute batch downloads using the determined optimal operation mode."""
    logger.info(f"Starting enhanced batch downloads in {operation_mode} mode for {len(tasks)} tasks")
    
    # Initialize enhanced bulk downloader with S3 direct sync capabilities
    downloader_config = {
        'base_url': 's3://data.binance.vision/data/',
        'timeout_seconds': config.get('timeout_seconds', 300),
        'verify_checksums': config.get('download_checksum', True),
        'storage': storage,
        'batch_size': config.get('batch_size', 100),
        'max_concurrent': config.get('max_parallel_downloads', 8),
        'part_size_mb': config.get('part_size_mb', 50),
        'enable_batch_mode': True,
        
        # S3 Direct Sync Configuration
        'enable_s3_direct_sync': operation_mode == 'direct_sync',
        'destination_bucket': config.get('destination_bucket'),
        'destination_prefix': config.get('destination_prefix', ''),
        'sync_mode': config.get('sync_mode', 'copy'),
        'enable_incremental': config.get('enable_incremental', True),
        
        # Performance optimization
        'retry_count': config.get('retry_count', 3),
        's5cmd_extra_args': config.get('s5cmd_extra_args', ['--no-sign-request', '--retry-count=3'])
    }
    
    enhanced_downloader = EnhancedBulkDownloader(downloader_config)
    
    # Prepare download tasks
    download_tasks = []
    for task in tasks:
        try:
            source_url, target_path = await _generate_enhanced_task_paths(task, storage, config)
            download_tasks.append({
                'source_url': source_url,
                'target_path': str(target_path),
                'task': task
            })
        except Exception as e:
            logger.error(f"Failed to generate paths for task {task}: {e}")
    
    # Execute downloads with optimal mode preference
    prefer_direct_sync = operation_mode == 'direct_sync'
    results = await enhanced_downloader.download_files_batch(
        download_tasks, 
        prefer_direct_sync=prefer_direct_sync
    )
    
    # Get combined statistics
    stats = enhanced_downloader.get_combined_stats()
    logger.info(f"Enhanced download completed - Mode: {stats.get('mode', 'unknown')}")
    
    if 'direct_sync_stats' in stats:
        sync_stats = stats['direct_sync_stats']
        logger.info(f"Efficiency improvement: {sync_stats.get('efficiency_improvement', '0%')}")
        logger.info(f"Operations reduced: {sync_stats.get('operations_reduced', 0)}")
    
    return results


@task(retries=2, retry_delay_seconds=30, name="analyze-operation-efficiency")
async def analyze_operation_efficiency_task(
    results: List[Dict[str, Any]],
    operation_mode: str,
    config: WorkflowConfig
) -> Dict[str, Any]:
    """Analyze the efficiency gains from the chosen operation mode."""
    
    total_files = len(results)
    successful_files = sum(1 for r in results if r.get('success', False))
    failed_files = sum(1 for r in results if not r.get('success', False))
    
    # Calculate basic metrics
    success_rate = (successful_files / total_files) * 100 if total_files > 0 else 0
    total_bytes = sum(r.get('file_size', 0) for r in results if r.get('success', False))
    
    efficiency_analysis = {
        'operation_mode': operation_mode,
        'total_files': total_files,
        'successful_files': successful_files,
        'failed_files': failed_files,
        'success_rate': f"{success_rate:.1f}%",
        'total_bytes': total_bytes,
        'total_size_formatted': _format_bytes(total_bytes)
    }
    
    # Add mode-specific efficiency metrics
    if operation_mode == 'direct_sync':
        # Calculate efficiency improvements for direct sync
        operations_reduced = 0
        network_reduction = 0
        
        for result in results:
            if result.get('success') and result.get('operation_type') == 'direct_s3_sync':
                operations_reduced += 2  # Eliminated download + upload
                network_reduction += result.get('file_size', 0)
        
        efficiency_analysis.update({
            'operations_reduced': operations_reduced,
            'network_transfer_reduced_bytes': network_reduction,
            'network_reduction_formatted': _format_bytes(network_reduction),
            'efficiency_improvement': f"{(operations_reduced / (total_files * 2)) * 100:.1f}%" if total_files > 0 else "0%",
            'local_storage_eliminated': True,
            'estimated_time_savings': f"{(operations_reduced / total_files) * 50:.0f}%" if total_files > 0 else "0%"
        })
        
        logger.info(f"Direct sync efficiency: {efficiency_analysis['efficiency_improvement']} improvement")
        logger.info(f"Network reduction: {efficiency_analysis['network_reduction_formatted']}")
    
    else:
        efficiency_analysis.update({
            'operations_reduced': 0,
            'network_transfer_reduced_bytes': 0,
            'efficiency_improvement': "0%",
            'local_storage_eliminated': False,
            'estimated_time_savings': "0%"
        })
    
    return efficiency_analysis


@flow(
    name="enhanced-archive-collection-flow",
    task_runner=ConcurrentTaskRunner(),
    retries=1,
    retry_delay_seconds=300,
    description="Enhanced archive collection with S3 direct sync capabilities"
)
async def enhanced_archive_collection_flow(
    config: WorkflowConfig,
    metrics_collector: Optional[MetricsCollector] = None
) -> Dict[str, Any]:
    """
    Enhanced archive collection flow with S3 to S3 direct sync capabilities.
    
    This flow automatically determines the optimal operation mode and can perform
    either traditional downloads or direct S3 to S3 sync operations for maximum
    efficiency.
    """
    logger.info("Starting enhanced archive collection workflow with S3 direct sync capabilities")
    start_time = datetime.now()
    
    # Step 1: Validate enhanced configuration
    await validate_enhanced_archive_configuration_task(config)
    
    # Step 2: Initialize metadata (reuse from base workflow)
    from .archive_collection_prefect import create_collection_metadata_task
    metadata = await create_collection_metadata_task(config)
    
    try:
        # Step 3: Load archive matrix (reuse from base workflow)
        from .archive_collection_prefect import load_archive_matrix_task
        archive_matrix = await load_archive_matrix_task(config)
        
        # Step 4: Generate ingestion tasks (reuse from base workflow)
        from .archive_collection_prefect import generate_ingestion_tasks_task
        ingestion_tasks = await generate_ingestion_tasks_task(config, archive_matrix)
        
        if not ingestion_tasks:
            logger.warning("No ingestion tasks generated")
            return {
                "status": "completed",
                "metadata": metadata,
                "message": "No tasks to process"
            }
        
        # Step 5: Determine optimal operation mode
        operation_mode = await determine_optimal_operation_mode_task(config, ingestion_tasks)
        
        # Step 6: Initialize storage
        from ..core.config import Settings
        storage_settings = Settings(config.to_dict())
        storage = create_storage(storage_settings)
        
        # Step 7: Execute enhanced downloads
        download_results = await execute_enhanced_batch_downloads_task(
            ingestion_tasks, operation_mode, storage, config
        )
        
        # Step 8: Analyze efficiency
        efficiency_analysis = await analyze_operation_efficiency_task(
            download_results, operation_mode, config
        )
        
        # Step 9: Update metadata and finalize
        from .archive_collection_prefect import update_collection_metadata_task, persist_collection_metadata_task
        
        final_metadata = await update_collection_metadata_task(
            metadata, "completed", download_results
        )
        
        await persist_collection_metadata_task(final_metadata, storage)
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Record metrics if available
        if metrics_collector:
            metrics_collector.record_event("enhanced_archive_collection_completed")
        
        return {
            "status": "success",
            "metadata": final_metadata,
            "operation_mode": operation_mode,
            "efficiency_analysis": efficiency_analysis,
            "processing_time_seconds": processing_time,
            "enhanced_features": {
                "s3_direct_sync_available": config.get('enable_s3_direct_sync', False),
                "auto_mode_selection": config.get('operation_mode', 'auto') == 'auto',
                "incremental_sync": config.get('enable_incremental', True)
            }
        }
        
    except Exception as e:
        logger.error(f"Enhanced archive collection flow failed: {e}")
        
        if metrics_collector:
            metrics_collector.record_error(str(e))
        
        raise WorkflowError(f"Enhanced archive collection failed: {e}")


class EnhancedArchiveCollectionWorkflow(BaseWorkflow):
    """
    Enhanced Archive Collection Workflow with S3 Direct Sync Integration.
    
    This workflow extends the base archive collection with intelligent operation
    mode selection and S3 to S3 direct sync capabilities for optimal efficiency.
    """
    
    def __init__(self, config: WorkflowConfig, metrics_collector: Optional[MetricsCollector] = None):
        """Initialize enhanced archive collection workflow."""
        super().__init__(config, metrics_collector)
    
    def _validate_configuration(self) -> None:
        """Validate configuration (delegated to Prefect task)."""
        pass
    
    def _setup_workflow(self) -> None:
        """Setup workflow (delegated to Prefect tasks)."""
        pass
    
    async def _execute_workflow(self) -> Dict[str, Any]:
        """Execute the enhanced workflow using Prefect flow orchestration."""
        return await enhanced_archive_collection_flow(self.config, self.metrics)
    
    def _cleanup_workflow(self) -> None:
        """Cleanup workflow (handled by Prefect automatically)."""
        pass
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the enhanced workflow."""
        return await self._execute_workflow()
    
    def get_operation_modes(self) -> List[str]:
        """Get available operation modes."""
        return ['auto', 'direct_sync', 'traditional']
    
    def get_efficiency_features(self) -> Dict[str, str]:
        """Get available efficiency features."""
        return {
            'direct_sync': 'S3 to S3 direct copy eliminating local storage',
            'incremental_sync': 'Skip files that already exist in destination',
            'auto_mode_selection': 'Automatically choose optimal operation mode',
            'batch_optimization': 'Group operations by prefix for efficiency',
            'parallel_processing': 'Concurrent operations with configurable workers'
        }


# Helper Functions
async def _generate_enhanced_task_paths(
    task: DataIngestionTask, 
    storage: BaseStorage, 
    config: WorkflowConfig
) -> tuple[str, Path]:
    """Generate enhanced task paths supporting both local and S3 targets."""
    
    # Import the existing path generation function
    from .archive_collection_prefect import _generate_task_paths
    
    # Check if S3 direct sync is enabled
    if config.get('enable_s3_direct_sync', False):
        # Generate S3 target path instead of local path
        source_url, local_target_path = await _generate_task_paths(task, storage, config)
        
        # Convert local path to S3 path for direct sync
        destination_bucket = config.get('destination_bucket')
        destination_prefix = config.get('destination_prefix', '').strip('/')
        
        # Create S3 target path
        relative_path = str(local_target_path).replace(str(config.get('output_directory', 'output')), '').lstrip('/')
        
        if destination_prefix:
            s3_target_path = f"{destination_prefix}/{relative_path}"
        else:
            s3_target_path = relative_path
        
        # Return source URL and S3 target path for direct sync
        return source_url, Path(s3_target_path)
    else:
        # Use traditional local path generation
        return await _generate_task_paths(task, storage, config)


def _format_bytes(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"