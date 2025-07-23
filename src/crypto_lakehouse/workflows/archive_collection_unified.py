"""
Unified Archive Collection Workflow for Crypto Lakehouse Platform.

This module consolidates all archive collection implementations into a single,
comprehensive workflow that combines the best features from all variants:
- Traditional download capabilities (archive_collection.py)
- Prefect orchestration (archive_collection_prefect.py) 
- Enhanced system integration (archive_collection_updated.py)
- S3 direct sync capabilities (enhanced_archive_collection.py)

Consolidated Features:
- Matrix-driven collection based on availability matrix
- Prefect orchestration with task retry and error handling
- Storage factory integration with lakehouse zones
- Type-safe data models and configuration validation
- S3 to S3 direct sync with operation mode selection
- Enhanced bulk download with s5cmd batch capabilities
- Comprehensive metrics and monitoring integration
- Resume capability for interrupted collections
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
from ..ingestion.bulk_downloader import BulkDownloader
from ..ingestion.s3_direct_sync import EnhancedBulkDownloader


logger = logging.getLogger(__name__)


# Unified Prefect Tasks for Archive Collection
@task(retries=3, retry_delay_seconds=60, name="validate-unified-archive-configuration")
async def validate_unified_archive_configuration_task(config: WorkflowConfig) -> bool:
    """Validate unified archive collection configuration with all supported features."""
    logger.info("Validating unified archive collection configuration")
    
    # Required fields validation
    required_fields = [
        'workflow_type', 'matrix_path', 'output_directory',
        'markets', 'symbols', 'data_types'
    ]
    missing_fields = [field for field in required_fields if not config.get(field)]
    
    if missing_fields:
        raise ConfigurationError(f"Missing required configuration: {missing_fields}")
    
    # Validate matrix file exists
    matrix_path = Path(config.get('matrix_path'))
    if not matrix_path.exists():
        raise ConfigurationError(f"Archive matrix file not found: {matrix_path}")
    
    # Validate S3 direct sync configuration if enabled
    if config.get('enable_s3_direct_sync', False):
        s3_direct_config = config.get('s3_direct_sync_config', {})
        required_s3_fields = ['destination_bucket']
        missing_s3_fields = [field for field in required_s3_fields if not s3_direct_config.get(field)]
        
        if missing_s3_fields:
            raise ConfigurationError(f"Missing S3 direct sync configuration: {missing_s3_fields}")
        
        # Validate operation mode
        operation_mode = s3_direct_config.get('operation_mode', 'auto')
        valid_modes = ['auto', 'direct_sync', 'hybrid', 'traditional']
        if operation_mode not in valid_modes:
            raise ConfigurationError(f"Invalid operation mode '{operation_mode}'. Valid modes: {valid_modes}")
        
        logger.info(f"S3 direct sync enabled with operation mode: {operation_mode}")
    
    # Validate enum values using system models
    markets = config.get('markets', [])
    try:
        # Map external market names to internal TradeType values
        market_mapping = {
            'spot': TradeType.SPOT,
            'futures_um': TradeType.UM_FUTURES,
            'futures_cm': TradeType.CM_FUTURES,
            'options': TradeType.OPTIONS
        }
        validated_markets = []
        for market in markets:
            if market in market_mapping:
                validated_markets.append(market_mapping[market])
            else:
                raise ValueError(f"'{market}' is not a valid market type")
    except ValueError as e:
        raise ConfigurationError(f"Invalid markets in configuration: {e}")
    
    data_types = config.get('data_types', [])
    try:
        # Map external data type names to internal DataType values
        data_type_mapping = {
            'klines': DataType.KLINES,
            'trades': DataType.TRADES,
            'fundingRate': DataType.FUNDING_RATES,
            'funding_rates': DataType.FUNDING_RATES,
            'liquidationSnapshot': DataType.LIQUIDATIONS,
            'liquidations': DataType.LIQUIDATIONS,
            'bookDepth': DataType.ORDER_BOOK,
            'order_book': DataType.ORDER_BOOK,
            'bookTicker': DataType.TICKER,
            'ticker': DataType.TICKER,
            'metrics': DataType.METRICS,
            'BVOLIndex': DataType.VOLATILITY,
            'volatility': DataType.VOLATILITY,
            'EOHSummary': DataType.SUMMARY,
            'summary': DataType.SUMMARY,
            'aggTrades': DataType.TRADES,
            'premiumIndex': DataType.FUNDING_RATES,
            'indexPriceKlines': DataType.KLINES,
            'markPriceKlines': DataType.KLINES
        }
        validated_data_types = []
        for dt in data_types:
            if dt in data_type_mapping:
                validated_data_types.append(data_type_mapping[dt])
            else:
                try:
                    validated_data_types.append(DataType(dt))
                except ValueError:
                    raise ValueError(f"'{dt}' is not a valid data type")
    except ValueError as e:
        raise ConfigurationError(f"Invalid data types in configuration: {e}")
    
    # Environment-specific validation
    if config.get('environment') == 'production':
        if not config.get('enable_monitoring', True):
            raise ConfigurationError("Monitoring required in production environment")
        
        if config.get('max_parallel_downloads', 4) > 10:
            raise ConfigurationError("Max parallel downloads limited to 10 in production")
    
    logger.info("Unified configuration validation completed successfully")
    return True


@task(retries=2, retry_delay_seconds=30, name="create-unified-collection-metadata")
async def create_unified_collection_metadata_task(config: WorkflowConfig) -> IngestionMetadata:
    """Initialize unified collection metadata tracking."""
    task_id = f"unified_archive_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    metadata = IngestionMetadata(
        task_id=task_id,
        status="running",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        records_processed=0,
        bytes_processed=0,
        errors=[],
        source_files=[],
        output_files=[]
    )
    
    logger.info(f"Initialized unified collection metadata: {task_id}")
    return metadata


@task(retries=2, retry_delay_seconds=30, name="load-archive-matrix")
async def load_archive_matrix_task(config: WorkflowConfig) -> Dict[str, Any]:
    """Load the Binance archive availability matrix."""
    matrix_path = Path(config.get('matrix_path'))
    
    try:
        with open(matrix_path, 'r') as f:
            archive_matrix = json.load(f)
        
        # Validate matrix structure
        if 'availability_matrix' not in archive_matrix:
            raise WorkflowError("Invalid archive matrix: missing availability_matrix")
        
        logger.info(f"Loaded archive matrix from {matrix_path}")
        return archive_matrix
        
    except Exception as e:
        raise WorkflowError(f"Failed to load archive matrix: {e}")


@task(retries=1, retry_delay_seconds=30, name="generate-unified-ingestion-tasks")
async def generate_unified_ingestion_tasks_task(
    config: WorkflowConfig, 
    archive_matrix: Dict[str, Any]
) -> List[DataIngestionTask]:
    """Generate type-safe ingestion tasks using unified system data models."""
    logger.info("Generating unified ingestion tasks from archive matrix")
    
    ingestion_tasks = []
    
    # Get configuration parameters with validation
    market_mapping = {
        'spot': TradeType.SPOT,
        'futures_um': TradeType.UM_FUTURES,
        'futures_cm': TradeType.CM_FUTURES,
        'options': TradeType.OPTIONS
    }
    markets = [market_mapping[m] for m in config.get('markets', []) if m in market_mapping]
    symbols = config.get('symbols', [])
    
    # Handle flexible data type validation
    data_types_config = config.get('data_types', [])
    data_types = []
    for dt in data_types_config:
        try:
            data_types.append(DataType(dt))
        except ValueError:
            logger.warning(f"Unknown data type: {dt}, skipping")
    
    dates = _get_date_list(config)
    
    # Generate tasks from availability matrix
    for entry in archive_matrix['availability_matrix']:
        try:
            # Map matrix entry to system enums
            matrix_market = entry['market']
            matrix_data_type = entry['data_type']
            
            # Convert matrix values to system enums
            if matrix_market == 'spot':
                trade_type = TradeType.SPOT
            elif matrix_market == 'futures_um':
                trade_type = TradeType.UM_FUTURES
            elif matrix_market == 'futures_cm':
                trade_type = TradeType.CM_FUTURES
            elif matrix_market == 'options':
                trade_type = TradeType.OPTIONS
            else:
                logger.warning(f"Unknown market type: {matrix_market}")
                continue  # Skip unknown market types
            
            # Map data type
            system_data_type = _map_matrix_data_type(matrix_data_type)
            if not system_data_type:
                continue  # Skip unmapped data types
            
            # Apply filters
            if trade_type not in markets or system_data_type not in data_types:
                continue
            
            intervals = entry.get('intervals', [None])
            partitions = entry.get('partitions', ['daily'])
            
            # Generate tasks for each combination
            for symbol in symbols:
                for partition in partitions:
                    # Skip monthly partitions for current month
                    if partition == "monthly" and _is_current_month(dates[0]):
                        continue
                    
                    for interval in intervals:
                        for date in dates:
                            date_str = _format_date_for_partition(date, partition)
                            
                            # Create type-safe ingestion task
                            task = DataIngestionTask(
                                exchange=Exchange.BINANCE,
                                data_type=system_data_type,
                                trade_type=trade_type,
                                symbols=[symbol],
                                start_date=datetime.strptime(date_str, '%Y-%m-%d') if partition == 'daily' else datetime.strptime(f"{date_str}-01", '%Y-%m-%d'),
                                interval=Interval(interval) if interval and _is_valid_interval(interval) else None,
                                force_update=config.get('force_redownload', False),
                                target_zone=DataZone.BRONZE  # Archive data goes to Bronze zone
                            )
                            
                            # Add archive-specific metadata for enhanced URL generation
                            task.partition_type = partition
                            task.archive_date = date_str
                            task.matrix_entry = entry
                            task.original_data_type = matrix_data_type  # Preserve original data type
                            task.url_pattern = entry.get('url_pattern', '')
                            task.filename_pattern = entry.get('filename_pattern', '')
                            
                            ingestion_tasks.append(task)
                            
        except Exception as e:
            logger.warning(f"Skipping invalid matrix entry {entry}: {e}")
            continue
    
    logger.info(f"Generated {len(ingestion_tasks)} unified ingestion tasks")
    return ingestion_tasks


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
        config.get('s3_direct_sync_config', {}).get('destination_bucket')
    )
    
    if not s3_direct_available:
        logger.info("S3 direct sync not available, using traditional mode")
        return 'traditional'
    
    # Analyze tasks to determine if S3 direct sync is beneficial
    s3_source_count = 0
    total_tasks = len(ingestion_tasks)
    
    for task in ingestion_tasks:
        # Check if task has S3 source (Binance archive tasks are S3-based)
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


@task(retries=3, retry_delay_seconds=60, name="execute-unified-batch-downloads")
async def execute_unified_batch_downloads_task(
    tasks: List[DataIngestionTask],
    operation_mode: str,
    storage: BaseStorage,
    config: WorkflowConfig
) -> List[Dict[str, Any]]:
    """Execute unified batch downloads using the determined optimal operation mode."""
    logger.info(f"Starting unified batch downloads in {operation_mode} mode for {len(tasks)} tasks")
    
    # Initialize appropriate downloader based on operation mode
    if operation_mode == 'direct_sync':
        # Use Enhanced Bulk Downloader with S3 direct sync
        s3_direct_config = config.get('s3_direct_sync_config', {})
        
        downloader_config = {
            'base_url': 's3://data.binance.vision/data/',
            'timeout_seconds': config.get('timeout_seconds', 300),
            'verify_checksums': config.get('download_checksum', True),
            'storage': storage,
            'batch_size': s3_direct_config.get('batch_size', 100),
            'max_concurrent': s3_direct_config.get('max_concurrent', 16),
            'part_size_mb': s3_direct_config.get('part_size_mb', 50),
            'enable_batch_mode': s3_direct_config.get('enable_batch_mode', True),
            'enable_resume': s3_direct_config.get('enable_resume', True),
            's5cmd_extra_args': s3_direct_config.get('s5cmd_extra_args', ['--no-sign-request', '--retry-count=3']),
            
            # S3 direct sync specific configuration
            'enable_s3_direct_sync': True,
            'destination_bucket': s3_direct_config['destination_bucket'],
            'operation_mode': operation_mode,
            'cross_region_optimization': s3_direct_config.get('cross_region_optimization', True),
            'enable_incremental': s3_direct_config.get('enable_incremental', True),
            'sync_delete': s3_direct_config.get('sync_delete', False),
            'preserve_metadata': s3_direct_config.get('preserve_metadata', True),
            'enable_progress_tracking': s3_direct_config.get('enable_progress_tracking', True)
        }
        
        bulk_downloader = EnhancedBulkDownloader(downloader_config)
        logger.info(f"Initialized Enhanced Bulk Downloader with S3 direct sync mode: {operation_mode}")
    else:
        # Use traditional bulk downloader
        downloader_config = {
            'base_url': 's3://data.binance.vision/data/',
            'timeout_seconds': config.get('timeout_seconds', 300),
            'verify_checksums': config.get('download_checksum', True),
            'storage': storage,
            'batch_size': config.get('batch_size', 100),
            'max_concurrent': config.get('max_parallel_downloads', 8),
            'part_size_mb': config.get('part_size_mb', 50),
            'enable_batch_mode': config.get('enable_batch_mode', True),
            'enable_resume': config.get('enable_resume', True),
            's5cmd_extra_args': config.get('s5cmd_extra_args', ['--no-sign-request', '--retry-count=3'])
        }
        bulk_downloader = BulkDownloader(downloader_config)
        logger.info("Initialized traditional Bulk Downloader")
    
    # Prepare download tasks
    download_tasks = []
    for task in tasks:
        try:
            source_url, target_path = await _generate_unified_task_paths(task, storage, config)
            download_tasks.append({
                'source_url': source_url,
                'target_path': str(target_path),
                'task': task
            })
        except Exception as e:
            logger.error(f"Failed to generate paths for task {task}: {e}")
    
    # Execute downloads with batch processing if available
    if hasattr(bulk_downloader, 'download_files_batch') and len(download_tasks) > 1:
        logger.info("Using enhanced batch download mode")
        batch_results = await bulk_downloader.download_files_batch(download_tasks)
        
        # Convert batch results to workflow format
        workflow_results = []
        for i, result in enumerate(batch_results):
            task = download_tasks[i]['task'] if i < len(download_tasks) else None
            
            if result['success']:
                file_size = result.get('file_size', 0)
                cached = result.get('cached', False)
                
                workflow_results.append({
                    'status': 'skipped' if cached else 'success',
                    'task': task,
                    'target_path': result['target_path'],
                    'file_size': file_size,
                    'source_url': result['source_url'],
                    'cached': cached
                })
            else:
                workflow_results.append({
                    'status': 'failed',
                    'task': task,
                    'source_url': result['source_url'],
                    'error': result.get('error', 'Unknown batch download error')
                })
        
        return workflow_results
    else:
        # Fallback to individual downloads with concurrency control
        logger.info("Using individual download mode with concurrency control")
        max_concurrent = config.get('max_parallel_downloads', 4)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_download(task: DataIngestionTask):
            async with semaphore:
                return await _download_unified_archive_file(task, bulk_downloader, storage, config)
        
        # Execute downloads concurrently
        download_coroutines = [bounded_download(task) for task in tasks]
        results = await asyncio.gather(*download_coroutines, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    'status': 'error',
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results


@task(retries=2, retry_delay_seconds=30, name="persist-unified-collection-metadata")
async def persist_unified_collection_metadata_task(
    metadata: IngestionMetadata,
    storage: BaseStorage
) -> bool:
    """Persist unified collection metadata using storage interface."""
    try:
        # Convert metadata to DataFrame for storage
        metadata_dict = metadata.model_dump()
        metadata_df = pl.DataFrame([metadata_dict])
        
        # Store in Bronze zone as metadata
        await storage.write_data(
            data=metadata_df,
            zone=DataZone.BRONZE,
            exchange=Exchange.BINANCE,
            data_type=DataType.KLINES,  # Use as metadata type
            trade_type=TradeType.SPOT,
            symbol="METADATA",
            partition_date=metadata.created_at,
            metadata_type="unified_collection_run"
        )
        
        logger.info(f"Persisted unified collection metadata: {metadata.task_id}")
        return True
        
    except Exception as e:
        logger.warning(f"Failed to persist metadata: {e}")
        return False


@task(retries=1, retry_delay_seconds=10, name="update-unified-collection-metadata")
async def update_unified_collection_metadata_task(
    metadata: IngestionMetadata,
    status: str,
    results: Optional[List[Dict[str, Any]]] = None,
    errors: Optional[List[str]] = None
) -> IngestionMetadata:
    """Update unified collection metadata with final results."""
    metadata.status = status
    metadata.updated_at = datetime.now()
    
    if results:
        # Calculate statistics from results
        successful_downloads = sum(1 for r in results if r.get('status') == 'success')
        cached_files = sum(1 for r in results if r.get('cached', False))
        total_bytes = sum(r.get('file_size', 0) for r in results if r.get('status') in ['success', 'skipped'])
        
        metadata.records_processed = successful_downloads + cached_files
        metadata.bytes_processed = total_bytes
        
        # Update file lists
        for result in results:
            if result.get('status') in ['success', 'skipped']:
                if result.get('source_url'):
                    metadata.source_files.append(result['source_url'])
                if result.get('target_path'):
                    metadata.output_files.append(result['target_path'])
    
    if errors:
        metadata.errors.extend(errors)
    
    logger.info(f"Updated unified metadata {metadata.task_id} with status: {status}")
    return metadata


# Main Unified Prefect Flow
@flow(
    name="unified-archive-collection-flow",
    task_runner=ConcurrentTaskRunner(),
    retries=1,
    retry_delay_seconds=300,
    description="Unified archive collection with all features: Prefect orchestration, S3 direct sync, enhanced batch processing"
)
async def unified_archive_collection_flow(
    config: WorkflowConfig,
    metrics_collector: Optional[MetricsCollector] = None
) -> Dict[str, Any]:
    """
    Unified Prefect flow for archive collection workflow.
    
    This flow consolidates all archive collection functionality into a single
    comprehensive implementation with the best features from all variants:
    - Traditional download capabilities
    - Prefect orchestration with task retry
    - Enhanced system integration
    - S3 direct sync with auto-mode selection
    - Enhanced batch processing
    """
    logger.info("Starting unified archive collection workflow")
    start_time = datetime.now()
    
    # Step 1: Validate unified configuration
    await validate_unified_archive_configuration_task(config)
    
    # Step 2: Initialize unified metadata
    metadata = await create_unified_collection_metadata_task(config)
    
    try:
        # Step 3: Load archive matrix
        archive_matrix = await load_archive_matrix_task(config)
        
        # Step 4: Generate unified ingestion tasks
        ingestion_tasks = await generate_unified_ingestion_tasks_task(config, archive_matrix)
        
        if not ingestion_tasks:
            logger.warning("No ingestion tasks generated")
            final_metadata = await update_unified_collection_metadata_task(
                metadata, "completed", [], ["No tasks generated"]
            )
            return {
                "status": "completed",
                "metadata": final_metadata,
                "message": "No tasks to process"
            }
        
        # Step 5: Determine optimal operation mode
        operation_mode = await determine_optimal_operation_mode_task(config, ingestion_tasks)
        
        # Step 6: Initialize storage
        from ..core.config import Settings
        storage_settings = Settings(config.to_dict())
        storage = create_storage(storage_settings)
        
        # Step 7: Execute unified downloads
        download_results = await execute_unified_batch_downloads_task(
            ingestion_tasks, operation_mode, storage, config
        )
        
        # Step 8: Calculate statistics
        successful_tasks = sum(1 for r in download_results if r.get('status') == 'success')
        failed_tasks = sum(1 for r in download_results if r.get('status') in ['failed', 'error'])
        skipped_tasks = sum(1 for r in download_results if r.get('status') == 'skipped')
        total_size_bytes = sum(r.get('file_size', 0) for r in download_results)
        
        # Step 9: Persist unified metadata
        await persist_unified_collection_metadata_task(metadata, storage)
        
        # Step 10: Update final unified metadata
        final_metadata = await update_unified_collection_metadata_task(
            metadata, "completed", download_results
        )
        
        # Calculate processing time and success rate
        processing_time = (datetime.now() - start_time).total_seconds()
        total_tasks = len(ingestion_tasks)
        success_rate = (successful_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        # Record metrics if available
        if metrics_collector:
            metrics_collector.record_event("unified_archive_collection_completed")
        
        logger.info(f"Unified archive collection completed - Success rate: {success_rate:.1f}%")
        
        return {
            "status": "success",
            "metadata": final_metadata,
            "operation_mode": operation_mode,
            "collection_stats": {
                'total_tasks': total_tasks,
                'successful_tasks': successful_tasks,
                'failed_tasks': failed_tasks,
                'skipped_tasks': skipped_tasks,
                'total_size_bytes': total_size_bytes,
                'processing_time_seconds': processing_time
            },
            "success_rate": success_rate,
            "total_size_formatted": _format_bytes(total_size_bytes),
            "output_directory": str(config.get('output_directory')),
            "storage_zones_used": [DataZone.BRONZE.value],
            "ingestion_metadata_id": final_metadata.task_id,
            "unified_features": {
                "prefect_orchestration": True,
                "s3_direct_sync_available": config.get('enable_s3_direct_sync', False),
                "auto_mode_selection": config.get('operation_mode', 'auto') == 'auto',
                "enhanced_batch_processing": True,
                "storage_factory_integration": True,
                "type_safe_data_models": True,
                "comprehensive_error_handling": True,
                "resume_capability": True
            }
        }
        
    except Exception as e:
        logger.error(f"Unified archive collection flow failed: {e}")
        
        # Update metadata with failure
        error_metadata = await update_unified_collection_metadata_task(
            metadata, "failed", errors=[str(e)]
        )
        
        if metrics_collector:
            metrics_collector.record_error(str(e))
        
        raise WorkflowError(f"Unified archive collection failed: {e}")


# Unified Workflow Class
class UnifiedArchiveCollectionWorkflow(BaseWorkflow):
    """
    Unified Archive Collection Workflow.
    
    This class consolidates all archive collection functionality from the four
    original implementations into a single comprehensive workflow that provides:
    
    1. Traditional download capabilities (from archive_collection.py)
    2. Prefect orchestration with enhanced error handling (from archive_collection_prefect.py)
    3. Enhanced system integration with type-safe models (from archive_collection_updated.py)
    4. S3 direct sync with operation mode selection (from enhanced_archive_collection.py)
    
    Key Features:
    - Matrix-driven collection based on availability matrix
    - Intelligent operation mode selection (auto/direct_sync/traditional)
    - Enhanced bulk download with s5cmd batch capabilities
    - Storage factory integration with lakehouse zones
    - Comprehensive metrics and monitoring integration
    - Resume capability for interrupted collections
    - Type-safe data models and configuration validation
    - Backward compatibility with all original interfaces
    """
    
    def __init__(self, config: WorkflowConfig, metrics_collector: Optional[MetricsCollector] = None):
        """Initialize unified archive collection workflow."""
        super().__init__(config, metrics_collector)
    
    def _validate_configuration(self) -> None:
        """Validate configuration (delegated to Prefect task)."""
        # Configuration validation is handled by unified Prefect tasks
        pass
    
    def _setup_workflow(self) -> None:
        """Setup workflow (delegated to Prefect tasks)."""
        # Setup is handled by unified Prefect tasks
        pass
    
    async def _execute_workflow(self) -> Dict[str, Any]:
        """Execute the unified workflow using Prefect flow orchestration."""
        return await unified_archive_collection_flow(self.config, self.metrics)
    
    def _cleanup_workflow(self) -> None:
        """Cleanup workflow (handled by Prefect automatically)."""
        # Cleanup is handled by Prefect tasks and automatic resource management
        pass
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the unified workflow."""
        return await self._execute_workflow()
    
    def get_flow_config(self) -> Dict[str, Any]:
        """Get unified Prefect flow configuration."""
        return {
            "name": "unified-archive-collection-flow",
            "description": "Unified archive collection with all features: Prefect orchestration, S3 direct sync, enhanced batch processing",
            "tags": ["archive", "collection", "crypto", "binance", "unified", "prefect", "s3-direct-sync"],
            "version": "3.0.0",
            "task_runner": ConcurrentTaskRunner(),
            "retries": self.config.get('retry_attempts', 1),
            "retry_delay_seconds": self.config.get('retry_delay_seconds', 300),
        }
    
    def get_supported_features(self) -> Dict[str, str]:
        """Get all supported features consolidated from original implementations."""
        return {
            "matrix_driven_collection": "Collection based on Binance archive availability matrix",
            "prefect_orchestration": "Task retry, error handling, and observability with Prefect",
            "s3_direct_sync": "S3 to S3 direct copy eliminating local storage requirements",
            "auto_mode_selection": "Automatically choose optimal operation mode based on task analysis",
            "enhanced_batch_processing": "s5cmd batch mode with configurable concurrency",
            "storage_factory_integration": "Lakehouse zones with pluggable storage backends",
            "type_safe_data_models": "Validated data models with enum-based configuration",
            "comprehensive_error_handling": "Retry logic, graceful degradation, and detailed error reporting",
            "resume_capability": "Skip existing files and resume interrupted collections",
            "metrics_integration": "Comprehensive metrics collection and monitoring",
            "backward_compatibility": "Compatible with all original workflow interfaces"
        }
    
    def get_operation_modes(self) -> List[str]:
        """Get available operation modes."""
        return ['auto', 'direct_sync', 'traditional', 'hybrid']


# Helper Functions (Consolidated from all implementations)
def _get_date_list(config: WorkflowConfig) -> List[str]:
    """Get list of dates to collect based on configuration."""
    if 'date_range' in config:
        date_range = config['date_range']
        start_date = datetime.strptime(date_range['start'], '%Y-%m-%d')
        end_date = datetime.strptime(date_range['end'], '%Y-%m-%d')
        
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        return dates
    else:
        return [config.get('default_date', '2025-07-15')]


def _map_matrix_data_type(matrix_data_type: str) -> Optional[DataType]:
    """Map archive matrix data type to system DataType enum."""
    mapping = {
        # Core data types
        'klines': DataType.KLINES,
        'trades': DataType.TRADES,
        'aggTrades': DataType.TRADES,  # Aggregate trades mapped to trades
        'fundingRate': DataType.FUNDING_RATES,
        'liquidationSnapshot': DataType.LIQUIDATIONS,
        
        # Order book data types
        'bookDepth': DataType.ORDER_BOOK,
        'bookTicker': DataType.TICKER,
        
        # Index and mark price data
        'indexPriceKlines': DataType.KLINES,  # Treat as klines variant
        'markPriceKlines': DataType.KLINES,   # Treat as klines variant
        'premiumIndex': DataType.FUNDING_RATES,  # Related to funding
        
        # Metrics and volatility (with fallback handling)
        'metrics': DataType.METRICS if hasattr(DataType, 'METRICS') else DataType.KLINES,
        'BVOLIndex': DataType.VOLATILITY if hasattr(DataType, 'VOLATILITY') else DataType.KLINES,
        'EOHSummary': DataType.SUMMARY if hasattr(DataType, 'SUMMARY') else DataType.KLINES
    }
    
    result = mapping.get(matrix_data_type)
    if not result:
        logger.warning(f"Unknown data type: {matrix_data_type}")
    
    return result


def _is_valid_interval(interval: str) -> bool:
    """Check if interval is valid system Interval enum."""
    try:
        Interval(interval)
        return True
    except ValueError:
        return False


def _is_current_month(date_str: str) -> bool:
    """Check if date is in current month."""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    now = datetime.now()
    return date_obj.year == now.year and date_obj.month == now.month


def _format_date_for_partition(date: str, partition: str) -> str:
    """Format date string based on partition type."""
    if partition == "monthly":
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        # Use previous month for monthly data
        if date_obj.month == 1:
            prev_month = date_obj.replace(year=date_obj.year-1, month=12)
        else:
            prev_month = date_obj.replace(month=date_obj.month-1)
        return prev_month.strftime('%Y-%m')
    else:
        return date


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


async def _generate_unified_task_paths(
    task: DataIngestionTask, 
    storage: BaseStorage, 
    config: WorkflowConfig
) -> tuple[str, Path]:
    """Generate unified source URL and target path supporting all features."""
    # Build source URL following Binance archive structure
    trade_type_map = {
        TradeType.SPOT: 'spot',
        TradeType.UM_FUTURES: 'futures/um',
        TradeType.CM_FUTURES: 'futures/cm',
        TradeType.OPTIONS: 'option'
    }
    
    # Enhanced data type mapping with support for all Binance data types
    data_type_map = {
        DataType.KLINES: 'klines',
        DataType.TRADES: 'trades',
        DataType.FUNDING_RATES: 'fundingRate',
        DataType.LIQUIDATIONS: 'liquidationSnapshot',
        DataType.ORDER_BOOK: 'bookDepth',
        DataType.TICKER: 'bookTicker'
    }
    
    # Get the original data type from task metadata if available
    original_data_type = getattr(task, 'original_data_type', None)
    if original_data_type:
        data_type_str = original_data_type
    else:
        data_type_str = data_type_map.get(task.data_type, task.data_type.value)
    
    symbol = task.symbols[0]
    trade_path = trade_type_map.get(task.trade_type, task.trade_type.value)
    
    # Determine partition and date formatting
    if hasattr(task, 'partition_type'):
        partition = getattr(task, 'partition_type', 'daily')
        archive_date = getattr(task, 'archive_date', task.start_date.strftime('%Y-%m-%d'))
    else:
        partition = 'daily'
        archive_date = task.start_date.strftime('%Y-%m-%d')
    
    # Enhanced URL generation using matrix patterns
    if hasattr(task, 'url_pattern') and task.url_pattern:
        # Use enhanced matrix URL pattern
        url_pattern = task.url_pattern
        filename_pattern = getattr(task, 'filename_pattern', '{symbol}-{data_type}-{date}.zip')
        
        # Replace placeholders in URL pattern
        source_url = url_pattern.format(
            partition=partition,
            symbol=symbol,
            interval=task.interval.value if task.interval else '',
            filename=filename_pattern.format(
                symbol=symbol,
                interval=task.interval.value if task.interval else data_type_str,
                date=archive_date,
                data_type=data_type_str
            )
        )
    else:
        # Fallback to original URL generation
        base_url = "s3://data.binance.vision/data/"
        source_path = f"{base_url}{trade_path}/{partition}/{data_type_str}/{symbol}"
        
        if task.interval and data_type_str in ['klines', 'indexPriceKlines', 'markPriceKlines', 'bookDepth']:
            source_path += f"/{task.interval.value}"
            filename = f"{symbol}-{task.interval.value}-{archive_date}.zip"
        else:
            filename = f"{symbol}-{data_type_str}-{archive_date}.zip"
        
        source_url = f"{source_path}/{filename}"
    
    # Generate target path with S3 direct sync support
    if config.get('enable_s3_direct_sync', False):
        # Generate S3 target path for direct sync
        destination_bucket = config.get('s3_direct_sync_config', {}).get('destination_bucket')
        destination_prefix = config.get('s3_direct_sync_config', {}).get('destination_prefix', '').strip('/')
        
        # Create S3 target path
        if storage:
            partition_path = storage.get_partition_path(
                zone=task.target_zone,
                exchange=task.exchange,
                data_type=task.data_type,
                trade_type=task.trade_type,
                symbol=symbol,
                partition_date=task.start_date
            )
            relative_path = str(partition_path / filename)
        else:
            relative_path = f"{trade_path}/{partition}/{data_type_str}/{symbol}/{filename}"
        
        if destination_prefix:
            s3_target_path = f"{destination_prefix}/{relative_path}"
        else:
            s3_target_path = relative_path
        
        target_path = Path(s3_target_path)
    else:
        # Generate local target path using storage interface
        if storage:
            # Use storage interface to get proper lakehouse path
            partition_path = storage.get_partition_path(
                zone=task.target_zone,
                exchange=task.exchange,
                data_type=task.data_type,
                trade_type=task.trade_type,
                symbol=symbol,
                partition_date=task.start_date
            )
            
            # Get base output directory from config
            base_output = Path(config.get('output_directory', 'output'))
            target_path = base_output / partition_path / filename
        else:
            # Fallback to simple directory structure
            output_dir = Path(config.get('output_directory', 'output'))
            target_path = output_dir / trade_path / partition / data_type_str / symbol
            if task.interval:
                target_path = target_path / task.interval.value
            target_path = target_path / filename
        
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
    
    return source_url, target_path


async def _download_unified_archive_file(
    task: DataIngestionTask,
    bulk_downloader: Union[BulkDownloader, EnhancedBulkDownloader],
    storage: BaseStorage,
    config: WorkflowConfig
) -> Dict[str, Any]:
    """Download individual archive file with unified error handling."""
    try:
        # Generate file paths using unified logic
        source_url, target_path = await _generate_unified_task_paths(task, storage, config)
        
        # Check if file already exists and skip if not forcing redownload
        if target_path.exists() and target_path.stat().st_size > 0 and not task.force_update:
            logger.debug(f"Skipping existing file: {target_path}")
            return {
                'status': 'skipped',
                'task': task,
                'target_path': str(target_path),
                'file_size': target_path.stat().st_size,
                'reason': 'file_exists',
                'cached': True
            }
        
        # Download file using bulk downloader
        download_result = await bulk_downloader.download_file(
            source_url=source_url,
            target_path=target_path,
            validate_checksum=config.get('download_checksum', True)
        )
        
        if download_result['success']:
            file_size = download_result.get('file_size', 0)
            cached = download_result.get('cached', False)
            
            logger.info(f"{'Cached' if cached else 'Downloaded'} {target_path.name} ({_format_bytes(file_size)})")
            
            return {
                'status': 'success',
                'task': task,
                'target_path': str(target_path),
                'file_size': file_size,
                'source_url': source_url,
                'cached': cached
            }
        else:
            # Handle download failure
            error_msg = download_result.get('error', 'Unknown download error')
            logger.error(f"Failed to download {source_url}: {error_msg}")
            
            return {
                'status': 'failed',
                'task': task,
                'source_url': source_url,
                'target_path': str(target_path),
                'error': error_msg
            }
            
    except Exception as e:
        logger.error(f"Exception in unified download task: {e}")
        
        return {
            'status': 'error',
            'task': task,
            'error': str(e)
        }