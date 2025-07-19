"""
Enhanced Archive Collection Workflow for Crypto Lakehouse Platform.

This module provides a system-compliant implementation of the Binance archive
data collection workflow, following current lakehouse architecture patterns,
storage interfaces, and data models.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

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


logger = logging.getLogger(__name__)


class ArchiveCollectionWorkflow(BaseWorkflow):
    """
    System-compliant Binance Archive Collection Workflow.
    
    Provides systematic collection of historical cryptocurrency data from
    Binance's public S3 archive following current lakehouse architecture patterns.
    
    Features:
    - Integration with storage factory and lakehouse zones
    - Type-safe data models and configuration validation
    - Async execution with proper error handling
    - Storage interface compliance for data persistence
    - Comprehensive metrics and monitoring integration
    - Archive matrix compatibility with enhanced validation
    """
    
    def __init__(self, config: WorkflowConfig, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize archive collection workflow with system dependencies.
        
        Args:
            config: Workflow configuration
            metrics_collector: Optional metrics collector
        """
        super().__init__(config, metrics_collector)
        
        # Core components
        self.storage: Optional[BaseStorage] = None
        self.bulk_downloader: Optional[BulkDownloader] = None
        self.archive_matrix: Optional[Dict] = None
        
        # Collection state
        self.ingestion_tasks: List[DataIngestionTask] = []
        self.collection_metadata: Optional[IngestionMetadata] = None
        
        # Enhanced statistics
        self.stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'total_size_bytes': 0,
            'total_records': 0,
            'skipped_tasks': 0,
            'processing_time_seconds': 0.0
        }
    
    def _validate_configuration(self) -> None:
        """Validate archive collection specific configuration with enhanced checks."""
        # Required fields validation
        required_fields = [
            'workflow_type', 'matrix_path', 'output_directory',
            'markets', 'symbols', 'data_types'
        ]
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            raise ConfigurationError(f"Missing required configuration: {missing_fields}")
        
        # Validate matrix file exists
        matrix_path = Path(self.config.get('matrix_path'))
        if not matrix_path.exists():
            raise ConfigurationError(f"Archive matrix file not found: {matrix_path}")
        
        # Validate enum values using system models
        markets = self.config.get('markets', [])
        try:
            validated_markets = [TradeType(market) for market in markets]
        except ValueError as e:
            raise ConfigurationError(f"Invalid markets in configuration: {e}")
        
        data_types = self.config.get('data_types', [])
        try:
            validated_data_types = [DataType(dt) for dt in data_types]
        except ValueError as e:
            raise ConfigurationError(f"Invalid data types in configuration: {e}")
        
        # Environment-specific validation
        if self.config.get('environment') == 'production':
            if not self.config.get('enable_monitoring', True):
                raise ConfigurationError("Monitoring required in production environment")
            
            if self.config.get('max_parallel_downloads', 4) > 10:
                raise ConfigurationError("Max parallel downloads limited to 10 in production")
        
        self.logger.debug("Enhanced configuration validation completed successfully")
    
    def _setup_workflow(self) -> None:
        """Setup archive collection workflow with system integration."""
        self.logger.info("Setting up enhanced archive collection workflow")
        
        # Initialize storage using factory pattern
        self._initialize_storage()
        
        # Initialize bulk downloader
        self._initialize_bulk_downloader()
        
        # Load archive matrix
        self._load_archive_matrix()
        
        # Generate ingestion tasks using system data models
        self._generate_ingestion_tasks()
        
        # Initialize collection metadata
        self._initialize_collection_metadata()
        
        self.logger.info(f"Generated {len(self.ingestion_tasks)} ingestion tasks")
        
    async def _execute_workflow(self) -> Dict[str, Any]:
        """Execute the archive collection workflow with async patterns."""
        self.logger.info("Starting enhanced archive data collection")
        
        start_time = datetime.now()
        self.stats['total_tasks'] = len(self.ingestion_tasks)
        
        # Use enhanced batch download if available
        if hasattr(self.bulk_downloader, 'download_files_batch') and len(self.ingestion_tasks) > 1:
            results = await self._execute_batch_ingestion()
        else:
            # Fallback to individual task execution
            max_concurrent = self.config.get('max_parallel_downloads', 4)
            semaphore = asyncio.Semaphore(max_concurrent)
            
            # Create async tasks for execution
            async_tasks = [
                self._execute_ingestion_task(task, semaphore)
                for task in self.ingestion_tasks
            ]
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        # Process results and update statistics
        self._process_execution_results(results)
        
        # Calculate processing time
        self.stats['processing_time_seconds'] = (datetime.now() - start_time).total_seconds()
        
        # Persist metadata using storage interface
        await self._persist_collection_metadata()
        
        # Calculate success rate
        success_rate = (self.stats['successful_tasks'] / self.stats['total_tasks']) * 100 \
                      if self.stats['total_tasks'] > 0 else 0
        
        results_summary = {
            'collection_stats': self.stats.copy(),
            'success_rate': success_rate,
            'total_size_formatted': self._format_bytes(self.stats['total_size_bytes']),
            'output_directory': str(self.config.get('output_directory')),
            'storage_zones_used': [DataZone.BRONZE.value],  # Archive data goes to Bronze
            'ingestion_metadata_id': self.collection_metadata.task_id if self.collection_metadata else None
        }
        
        self.logger.info(f"Enhanced collection completed - Success rate: {success_rate:.1f}%")
        return results_summary
    
    def _cleanup_workflow(self) -> None:
        """Cleanup archive collection workflow resources."""
        self.logger.info("Cleaning up enhanced archive collection workflow")
        
        # Log final enhanced statistics
        self._log_enhanced_final_stats()
        
        # Update final metadata
        if self.collection_metadata:
            self.collection_metadata.status = "completed"
            self.collection_metadata.updated_at = datetime.now()
            self.collection_metadata.records_processed = self.stats['total_records']
            self.collection_metadata.bytes_processed = self.stats['total_size_bytes']
        
        # Close storage connections if needed
        if hasattr(self.storage, 'close'):
            asyncio.create_task(self.storage.close())
    
    def _initialize_storage(self) -> None:
        """Initialize storage using system factory pattern."""
        try:
            # Create storage configuration from workflow config
            storage_config = self._create_storage_config()
            self.storage = create_storage(storage_config)
            
            self.logger.info(f"Initialized storage: {type(self.storage).__name__}")
            self.metrics.record_event("storage_initialized")
            
        except Exception as e:
            raise WorkflowError(f"Failed to initialize storage: {e}")
    
    def _initialize_bulk_downloader(self) -> None:
        """Initialize enhanced bulk downloader with s5cmd batch capabilities."""
        try:
            downloader_config = {
                'base_url': 's3://data.binance.vision/data/',
                'timeout_seconds': self.config.get('timeout_seconds', 300),
                'verify_checksums': self.config.get('download_checksum', True),
                'storage': self.storage,
                # Enhanced batch configuration
                'batch_size': self.config.get('batch_size', 50),
                'max_concurrent': self.config.get('max_parallel_downloads', 4),
                'part_size_mb': self.config.get('part_size_mb', 50),
                'enable_batch_mode': self.config.get('enable_batch_mode', True)
            }
            
            self.bulk_downloader = BulkDownloader(downloader_config)
            
            self.logger.info("Initialized enhanced bulk downloader with s5cmd batch capabilities")
            self.logger.info(f"Batch size: {downloader_config['batch_size']}, "
                           f"Max concurrent: {downloader_config['max_concurrent']}, "
                           f"Batch mode: {downloader_config['enable_batch_mode']}")
            self.metrics.record_event("bulk_downloader_initialized")
            
        except Exception as e:
            raise WorkflowError(f"Failed to initialize bulk downloader: {e}")
    
    def _load_archive_matrix(self) -> None:
        """Load the Binance archive availability matrix."""
        matrix_path = Path(self.config.get('matrix_path'))
        
        try:
            with open(matrix_path, 'r') as f:
                self.archive_matrix = json.load(f)
            
            # Validate matrix structure
            if 'availability_matrix' not in self.archive_matrix:
                raise WorkflowError("Invalid archive matrix: missing availability_matrix")
            
            self.logger.info(f"Loaded archive matrix from {matrix_path}")
            self.metrics.record_event("archive_matrix_loaded")
            
        except Exception as e:
            raise WorkflowError(f"Failed to load archive matrix: {e}")
    
    def _generate_ingestion_tasks(self) -> None:
        """Generate type-safe ingestion tasks using system data models."""
        self.ingestion_tasks = []
        
        # Get configuration parameters with validation
        markets = [TradeType(m) for m in self.config.get('markets', [])]
        symbols = self.config.get('symbols', [])
        data_types = [DataType(dt) for dt in self.config.get('data_types', [])]
        dates = self._get_date_list()
        
        # Generate tasks from availability matrix
        for entry in self.archive_matrix['availability_matrix']:
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
                else:
                    continue  # Skip unknown market types
                
                # Map data type
                system_data_type = self._map_matrix_data_type(matrix_data_type)
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
                        if partition == "monthly" and self._is_current_month(dates[0]):
                            continue
                        
                        for interval in intervals:
                            for date in dates:
                                date_str = self._format_date_for_partition(date, partition)
                                
                                # Create type-safe ingestion task
                                task = DataIngestionTask(
                                    exchange=Exchange.BINANCE,
                                    data_type=system_data_type,
                                    trade_type=trade_type,
                                    symbols=[symbol],
                                    start_date=datetime.strptime(date_str, '%Y-%m-%d') if partition == 'daily' else datetime.strptime(f"{date_str}-01", '%Y-%m-%d'),
                                    interval=Interval(interval) if interval and self._is_valid_interval(interval) else None,
                                    force_update=self.config.get('force_redownload', False),
                                    target_zone=DataZone.BRONZE  # Archive data goes to Bronze zone
                                )
                                
                                # Add archive-specific metadata
                                task_dict = task.model_dump()
                                task_dict.update({
                                    'partition_type': partition,
                                    'archive_date': date_str,
                                    'matrix_entry': entry
                                })
                                
                                self.ingestion_tasks.append(task)
                                
            except Exception as e:
                self.logger.warning(f"Skipping invalid matrix entry {entry}: {e}")
                continue
    
    def _initialize_collection_metadata(self) -> None:
        """Initialize collection metadata tracking."""
        task_id = f"archive_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.collection_metadata = IngestionMetadata(
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
        
        self.logger.info(f"Initialized collection metadata: {task_id}")
        self.metrics.record_event("collection_metadata_initialized")
    
    async def _execute_ingestion_task(self, task: DataIngestionTask, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Execute a single ingestion task with async patterns."""
        async with semaphore:
            try:
                # Generate file paths using storage interface
                source_path, target_path = await self._generate_task_paths(task)
                
                # Check if file already exists and skip if not forcing redownload
                if await self._file_exists(target_path) and not task.force_update:
                    self.logger.debug(f"Skipping existing file: {target_path}")
                    self.stats['skipped_tasks'] += 1
                    return {
                        'status': 'skipped',
                        'task': task,
                        'target_path': target_path,
                        'reason': 'file_exists'
                    }
                
                # Download file using bulk downloader
                download_result = await self.bulk_downloader.download_file(
                    source_url=source_path,
                    target_path=target_path,
                    validate_checksum=self.config.get('download_checksum', True)
                )
                
                if download_result['success']:
                    # Update statistics
                    file_size = download_result.get('file_size', 0)
                    self.stats['total_size_bytes'] += file_size
                    self.stats['successful_tasks'] += 1
                    
                    # Record metrics
                    self.metrics.record_event("file_downloaded")
                    
                    # Update metadata
                    if self.collection_metadata:
                        self.collection_metadata.source_files.append(source_path)
                        self.collection_metadata.output_files.append(str(target_path))
                    
                    self.logger.info(f"Downloaded {target_path.name} ({self._format_bytes(file_size)})")
                    
                    return {
                        'status': 'success',
                        'task': task,
                        'target_path': target_path,
                        'file_size': file_size
                    }
                else:
                    # Handle download failure
                    error_msg = download_result.get('error', 'Unknown download error')
                    self.stats['failed_tasks'] += 1
                    self.metrics.record_error(f"Download failed: {error_msg}")
                    
                    if self.collection_metadata:
                        self.collection_metadata.errors.append(f"{source_path}: {error_msg}")
                    
                    self.logger.error(f"Failed to download {source_path}: {error_msg}")
                    
                    return {
                        'status': 'failed',
                        'task': task,
                        'source_path': source_path,
                        'error': error_msg
                    }
                    
            except Exception as e:
                self.stats['failed_tasks'] += 1
                self.metrics.record_error(str(e))
                
                if self.collection_metadata:
                    self.collection_metadata.errors.append(f"Task execution failed: {e}")
                
                self.logger.error(f"Exception in task execution: {e}")
                
                return {
                    'status': 'error',
                    'task': task,
                    'error': str(e)
                }
    
    async def _generate_task_paths(self, task: DataIngestionTask) -> tuple[str, Path]:
        """Generate source URL and target path using storage interface."""
        # Build source URL following Binance archive structure
        trade_type_map = {
            TradeType.SPOT: 'spot',
            TradeType.UM_FUTURES: 'futures/um',
            TradeType.CM_FUTURES: 'futures/cm'
        }
        
        data_type_map = {
            DataType.KLINES: 'klines',
            DataType.TRADES: 'trades',
            DataType.FUNDING_RATES: 'fundingRate'
        }
        
        symbol = task.symbols[0]
        trade_path = trade_type_map[task.trade_type]
        data_type_str = data_type_map.get(task.data_type, task.data_type.value)
        
        # Determine partition and date formatting
        if hasattr(task, 'partition_type'):
            partition = getattr(task, 'partition_type', 'daily')
            archive_date = getattr(task, 'archive_date', task.start_date.strftime('%Y-%m-%d'))
        else:
            partition = 'daily'
            archive_date = task.start_date.strftime('%Y-%m-%d')
        
        # Build source path
        base_url = "s3://data.binance.vision/data/"
        source_path = f"{base_url}{trade_path}/{partition}/{data_type_str}/{symbol}"
        
        if task.interval and data_type_str in ['klines']:
            source_path += f"/{task.interval.value}"
            filename = f"{symbol}-{task.interval.value}-{archive_date}.zip"
        else:
            filename = f"{symbol}-{data_type_str}-{archive_date}.zip"
        
        source_url = f"{source_path}/{filename}"
        
        # Generate target path using storage interface
        if self.storage:
            # Use storage interface to get proper lakehouse path
            partition_path = self.storage.get_partition_path(
                zone=task.target_zone,
                exchange=task.exchange,
                data_type=task.data_type,
                trade_type=task.trade_type,
                symbol=symbol,
                partition_date=task.start_date
            )
            
            # Get base output directory from config
            base_output = Path(self.config.get('output_directory', 'output'))
            target_path = base_output / partition_path / filename
        else:
            # Fallback to simple directory structure
            output_dir = Path(self.config.get('output_directory', 'output'))
            target_path = output_dir / trade_path / partition / data_type_str / symbol
            if task.interval:
                target_path = target_path / task.interval.value
            target_path = target_path / filename
        
        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        return source_url, target_path
    
    async def _execute_batch_ingestion(self) -> List[Dict[str, Any]]:
        """
        Execute ingestion using enhanced batch download capabilities.
        
        Specs-driven batch processing:
        - Prepares all download tasks upfront
        - Uses s5cmd batch mode for optimal performance
        - Handles file existence checking and caching
        - Provides comprehensive error handling and statistics
        """
        self.logger.info("Starting batch ingestion with s5cmd optimization")
        
        # Prepare all download tasks
        download_tasks = []
        for task in self.ingestion_tasks:
            try:
                source_url, target_path = await self._generate_task_paths(task)
                download_tasks.append({
                    'source_url': source_url,
                    'target_path': str(target_path),
                    'task': task
                })
            except Exception as e:
                self.logger.error(f"Failed to generate paths for task {task}: {e}")
                self.stats['failed_tasks'] += 1
        
        self.logger.info(f"Prepared {len(download_tasks)} download tasks for batch processing")
        
        # Execute batch download
        try:
            batch_results = await self.bulk_downloader.download_files_batch(download_tasks)
            
            # Process batch results and convert to workflow format
            workflow_results = []
            for i, result in enumerate(batch_results):
                try:
                    task = download_tasks[i]['task'] if i < len(download_tasks) else None
                    
                    if result['success']:
                        # Update statistics for successful downloads
                        file_size = result.get('file_size', 0)
                        cached = result.get('cached', False)
                        
                        if cached:
                            self.stats['skipped_tasks'] += 1
                        else:
                            self.stats['successful_tasks'] += 1
                            self.stats['total_size_bytes'] += file_size
                        
                        # Record metrics
                        self.metrics.record_event("file_downloaded" if not cached else "file_cached")
                        
                        # Update metadata
                        if self.collection_metadata:
                            self.collection_metadata.source_files.append(result['source_url'])
                            self.collection_metadata.output_files.append(result['target_path'])
                        
                        # Log download info
                        status = "cached" if cached else "downloaded"
                        file_name = Path(result['target_path']).name
                        self.logger.info(f"{status.title()}: {file_name} ({self._format_bytes(file_size)})")
                        
                        workflow_results.append({
                            'status': 'skipped' if cached else 'success',
                            'task': task,
                            'target_path': result['target_path'],
                            'file_size': file_size,
                            'cached': cached
                        })
                    else:
                        # Handle download failure
                        error_msg = result.get('error', 'Unknown batch download error')
                        self.stats['failed_tasks'] += 1
                        self.metrics.record_error(f"Batch download failed: {error_msg}")
                        
                        if self.collection_metadata:
                            self.collection_metadata.errors.append(f"{result['source_url']}: {error_msg}")
                        
                        self.logger.error(f"Failed to download {result['source_url']}: {error_msg}")
                        
                        workflow_results.append({
                            'status': 'failed',
                            'task': task,
                            'source_url': result['source_url'],
                            'error': error_msg
                        })
                        
                except Exception as e:
                    self.logger.error(f"Error processing batch result {i}: {e}")
                    self.stats['failed_tasks'] += 1
                    workflow_results.append({
                        'status': 'error',
                        'error': str(e)
                    })
            
            # Log batch statistics
            batch_stats = self.bulk_downloader.get_download_stats()
            self.logger.info(f"Batch download completed - Success rate: {batch_stats['success_rate']:.1f}%")
            self.logger.info(f"Files processed: {batch_stats['files_downloaded'] + batch_stats['files_failed']}")
            self.logger.info(f"Cache hits: {batch_stats['cache_hits']}")
            self.logger.info(f"Batches processed: {batch_stats['batches_processed']}")
            
            return workflow_results
            
        except Exception as e:
            self.logger.error(f"Batch ingestion failed: {e}")
            # Mark all tasks as failed
            self.stats['failed_tasks'] += len(self.ingestion_tasks)
            return [{
                'status': 'error',
                'error': f"Batch ingestion failed: {e}"
            } for _ in self.ingestion_tasks]
    
    async def _file_exists(self, file_path: Path) -> bool:
        """Check if file exists asynchronously."""
        return file_path.exists()
    
    async def _persist_collection_metadata(self) -> None:
        """Persist collection metadata using storage interface."""
        if not self.collection_metadata or not self.storage:
            return
        
        try:
            # Convert metadata to DataFrame for storage
            metadata_dict = self.collection_metadata.model_dump()
            metadata_df = pl.DataFrame([metadata_dict])
            
            # Store in Bronze zone as metadata
            await self.storage.write_data(
                data=metadata_df,
                zone=DataZone.BRONZE,
                exchange=Exchange.BINANCE,
                data_type=DataType.KLINES,  # Use as metadata type
                trade_type=TradeType.SPOT,
                symbol="METADATA",
                partition_date=self.collection_metadata.created_at,
                metadata_type="collection_run"
            )
            
            self.logger.info(f"Persisted collection metadata: {self.collection_metadata.task_id}")
            self.metrics.record_event("metadata_persisted")
            
        except Exception as e:
            self.logger.warning(f"Failed to persist metadata: {e}")
    
    def _process_execution_results(self, results: List[Any]) -> None:
        """Process execution results and update statistics."""
        for result in results:
            if isinstance(result, Exception):
                self.stats['failed_tasks'] += 1
                self.metrics.record_error(str(result))
            elif isinstance(result, dict):
                # Results already processed in individual task execution
                pass
    
    def _create_storage_config(self) -> 'Settings':
        """Create storage configuration from workflow config."""
        # Create a minimal settings object for storage factory
        class MinimalSettings:
            def __init__(self, config: WorkflowConfig):
                self.is_cloud_enabled = config.get('use_cloud_storage', False)
                self.local_data_dir = config.get('output_directory', 'output')
                self.aws_access_key_id = config.get('aws_access_key_id')
                self.aws_secret_access_key = config.get('aws_secret_access_key')
                self.s3_bucket = config.get('s3_bucket')
                self.s3_region = config.get('s3_region', 'us-east-1')
        
        return MinimalSettings(self.config)
    
    def _map_matrix_data_type(self, matrix_data_type: str) -> Optional[DataType]:
        """Map archive matrix data type to system DataType enum."""
        mapping = {
            'klines': DataType.KLINES,
            'trades': DataType.TRADES,
            'aggTrades': DataType.TRADES,  # Map to trades for now
            'fundingRate': DataType.FUNDING_RATES,
            'liquidationSnapshot': DataType.LIQUIDATIONS
        }
        return mapping.get(matrix_data_type)
    
    def _is_valid_interval(self, interval: str) -> bool:
        """Check if interval is valid system Interval enum."""
        try:
            Interval(interval)
            return True
        except ValueError:
            return False
    
    def _get_date_list(self) -> List[str]:
        """Get list of dates to collect based on configuration."""
        if 'date_range' in self.config:
            date_range = self.config['date_range']
            start_date = datetime.strptime(date_range['start'], '%Y-%m-%d')
            end_date = datetime.strptime(date_range['end'], '%Y-%m-%d')
            
            dates = []
            current_date = start_date
            while current_date <= end_date:
                dates.append(current_date.strftime('%Y-%m-%d'))
                current_date += timedelta(days=1)
            return dates
        else:
            return [self.config.get('default_date', '2025-07-15')]
    
    def _is_current_month(self, date_str: str) -> bool:
        """Check if date is in current month."""
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        now = datetime.now()
        return date_obj.year == now.year and date_obj.month == now.month
    
    def _format_date_for_partition(self, date: str, partition: str) -> str:
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
    
    def _format_bytes(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def _log_enhanced_final_stats(self) -> None:
        """Log enhanced final collection statistics."""
        success_rate = (self.stats['successful_tasks'] / self.stats['total_tasks']) * 100 \
                      if self.stats['total_tasks'] > 0 else 0
        
        self.logger.info("="*70)
        self.logger.info("ENHANCED ARCHIVE COLLECTION COMPLETED")
        self.logger.info("="*70)
        self.logger.info(f"Task ID: {self.collection_metadata.task_id if self.collection_metadata else 'N/A'}")
        self.logger.info(f"Total Tasks: {self.stats['total_tasks']}")
        self.logger.info(f"Successful: {self.stats['successful_tasks']}")
        self.logger.info(f"Failed: {self.stats['failed_tasks']}")
        self.logger.info(f"Skipped: {self.stats['skipped_tasks']}")
        self.logger.info(f"Success Rate: {success_rate:.1f}%")
        self.logger.info(f"Total Size: {self._format_bytes(self.stats['total_size_bytes'])}")
        self.logger.info(f"Processing Time: {self.stats['processing_time_seconds']:.2f}s")
        self.logger.info(f"Storage Type: {type(self.storage).__name__ if self.storage else 'None'}")
        self.logger.info(f"Target Zone: {DataZone.BRONZE.value}")
        self.logger.info(f"Output Directory: {self.config.get('output_directory')}")
        self.logger.info("="*70)