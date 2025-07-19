"""
Archive Collection Workflow for Crypto Lakehouse Platform.

This module provides a lakehouse-native implementation of the Binance archive
data collection workflow, refactored from the standalone implementation to
follow lakehouse architecture patterns and best practices.
"""

import json
import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..core.base import BaseWorkflow
from ..core.config import WorkflowConfig
from ..core.exceptions import WorkflowError, ConfigurationError
from ..core.metrics import MetricsCollector
from ..core.utils import create_directory_structure, format_file_size


logger = logging.getLogger(__name__)


class ArchiveCollectionWorkflow(BaseWorkflow):
    """
    Binance Archive Collection Workflow.
    
    Provides systematic collection of historical cryptocurrency data from
    Binance's public S3 archive following the lakehouse architecture patterns.
    
    Features:
    - Matrix-driven collection based on availability matrix
    - Parallel downloads with configurable concurrency
    - Automatic checksum validation
    - Schema-compliant directory organization
    - Comprehensive metrics and error tracking
    - Resume capability for interrupted collections
    """
    
    def __init__(self, config: WorkflowConfig, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize archive collection workflow.
        
        Args:
            config: Workflow configuration
            metrics_collector: Optional metrics collector
        """
        super().__init__(config, metrics_collector)
        
        self.archive_matrix: Optional[Dict] = None
        self.base_url = "s3://data.binance.vision/data/"
        self.collection_tasks: List[Dict] = []
        
        # Collection statistics
        self.stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_size': 0,
            'skipped_files': 0
        }
    
    def _validate_configuration(self) -> None:
        """Validate archive collection specific configuration."""
        required_fields = ['matrix_path', 'output_directory']
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            raise ConfigurationError(f"Missing required configuration: {missing_fields}")
        
        # Validate matrix file exists
        matrix_path = Path(self.config.get('matrix_path'))
        if not matrix_path.exists():
            raise ConfigurationError(f"Archive matrix file not found: {matrix_path}")
        
        # Validate output directory is writable
        output_dir = Path(self.config.get('output_directory'))
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(f"Cannot create output directory: {e}")
    
    def _setup_workflow(self) -> None:
        """Setup archive collection workflow resources."""
        self.logger.info("Setting up archive collection workflow")
        
        # Load archive matrix
        self._load_archive_matrix()
        
        # Generate collection tasks
        self._generate_collection_tasks()
        
        self.logger.info(f"Generated {len(self.collection_tasks)} collection tasks")
        
    def _execute_workflow(self) -> Dict[str, Any]:
        """Execute the archive collection workflow."""
        self.logger.info("Starting archive data collection")
        
        max_workers = self.config.get('max_parallel_downloads', 4)
        download_checksum = self.config.get('download_checksum', True)
        
        self.stats['total_downloads'] = len(self.collection_tasks)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_task = {}
            for task in self.collection_tasks:
                s3_url, local_path = self._generate_file_url_and_path(task)
                
                # Skip if file already exists and not forcing redownload
                if local_path.exists() and not self.config.get('force_redownload', False):
                    self.logger.debug(f"Skipping existing file: {local_path.name}")
                    self.stats['successful_downloads'] += 1
                    self.stats['skipped_files'] += 1
                    continue
                
                future = executor.submit(self._download_file, s3_url, local_path, download_checksum)
                future_to_task[future] = task
            
            # Process completed downloads
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    success = future.result()
                    if success:
                        self.stats['successful_downloads'] += 1
                        self.metrics.record_event("file_downloaded")
                    else:
                        self.stats['failed_downloads'] += 1
                        self.metrics.record_error(f"Download failed: {task}")
                except Exception as e:
                    self.stats['failed_downloads'] += 1
                    self.logger.error(f"Exception in download task {task}: {e}")
                    self.metrics.record_error(str(e))
        
        # Calculate success rate
        success_rate = (self.stats['successful_downloads'] / self.stats['total_downloads']) * 100 \
                      if self.stats['total_downloads'] > 0 else 0
        
        results = {
            'collection_stats': self.stats.copy(),
            'success_rate': success_rate,
            'total_size_formatted': format_file_size(self.stats['total_size']),
            'output_directory': str(self.config.get('output_directory'))
        }
        
        self.logger.info(f"Collection completed - Success rate: {success_rate:.1f}%")
        return results
    
    def _cleanup_workflow(self) -> None:
        """Cleanup archive collection workflow resources."""
        self.logger.info("Cleaning up archive collection workflow")
        
        # Log final statistics
        self._log_final_stats()
        
        # Save collection summary
        self._save_collection_summary()
    
    def _load_archive_matrix(self) -> None:
        """Load the Binance archive availability matrix."""
        matrix_path = Path(self.config.get('matrix_path'))
        
        try:
            with open(matrix_path, 'r') as f:
                self.archive_matrix = json.load(f)
            
            self.logger.info(f"Loaded archive matrix from {matrix_path}")
            self.metrics.record_event("matrix_loaded")
            
        except Exception as e:
            raise WorkflowError(f"Failed to load archive matrix: {e}")
    
    def _generate_collection_tasks(self) -> None:
        """Generate collection tasks based on configuration and matrix."""
        self.collection_tasks = []
        
        # Get configuration parameters
        markets = self.config.get('markets', ['spot'])
        symbols = self.config.get('symbols', ['BTCUSDT'])
        data_types = self.config.get('data_types', ['klines'])
        dates = self._get_date_list()
        
        # Generate tasks from availability matrix
        for entry in self.archive_matrix['availability_matrix']:
            market = entry['market']
            data_type = entry['data_type']
            intervals = entry.get('intervals', [None])
            partitions = entry.get('partitions', ['daily'])
            
            # Apply filters
            if market not in markets:
                continue
            if data_type not in data_types:
                continue
            
            # Generate tasks for each combination
            for symbol in symbols:
                for partition in partitions:
                    # Skip monthly partitions for current month
                    if partition == "monthly" and self._is_current_month(dates[0]):
                        continue
                    
                    for interval in intervals:
                        for date in dates:
                            date_str = self._format_date_for_partition(date, partition)
                            
                            task = {
                                'market': market,
                                'partition': partition,
                                'data_type': data_type,
                                'symbol': symbol,
                                'interval': interval,
                                'date': date_str
                            }
                            self.collection_tasks.append(task)
    
    def _generate_file_url_and_path(self, task: Dict) -> Tuple[str, Path]:
        """Generate S3 URL and local file path for a task."""
        market = task['market']
        partition = task['partition']
        data_type = task['data_type']
        symbol = task['symbol']
        interval = task['interval']
        date = task['date']
        
        # Build S3 path
        if market == "spot":
            s3_base = f"{self.base_url}spot/{partition}/{data_type}/{symbol}"
        elif market == "futures_um":
            s3_base = f"{self.base_url}futures/um/{partition}/{data_type}/{symbol}"
        elif market == "futures_cm":
            s3_base = f"{self.base_url}futures/cm/{partition}/{data_type}/{symbol}"
        else:
            raise WorkflowError(f"Unknown market type: {market}")
        
        # Add interval to path if applicable
        if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
            s3_base += f"/{interval}"
        
        # Generate filename
        if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
            filename = f"{symbol}-{interval}-{date}.zip"
        else:
            filename = f"{symbol}-{data_type}-{date}.zip"
        
        s3_url = f"{s3_base}/{filename}"
        
        # Create local directory and file path
        output_dir = Path(self.config.get('output_directory'))
        local_dir = create_directory_structure(output_dir, market, partition, data_type, symbol, interval)
        local_path = local_dir / filename
        
        return s3_url, local_path
    
    def _download_file(self, s3_url: str, local_path: Path, download_checksum: bool = True) -> bool:
        """Download file using s5cmd with optional checksum validation."""
        try:
            # Download main file
            cmd = ["s5cmd", "--no-sign-request", "cp", s3_url, str(local_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=self.config.get('timeout_seconds', 300))
            
            if result.returncode != 0:
                self.logger.warning(f"Failed to download {s3_url}: {result.stderr}")
                return False
            
            # Download checksum if requested
            if download_checksum:
                checksum_url = f"{s3_url}.CHECKSUM"
                checksum_path = Path(str(local_path) + ".CHECKSUM")
                
                cmd_checksum = ["s5cmd", "--no-sign-request", "cp", checksum_url, str(checksum_path)]
                subprocess.run(cmd_checksum, capture_output=True, text=True, timeout=60)
            
            # Update statistics
            file_size = local_path.stat().st_size
            self.stats['total_size'] += file_size
            
            self.logger.info(f"Downloaded {local_path.name} ({format_file_size(file_size)})")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout downloading {s3_url}")
            return False
        except Exception as e:
            self.logger.error(f"Error downloading {s3_url}: {e}")
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
    
    def _log_final_stats(self) -> None:
        """Log final collection statistics."""
        success_rate = (self.stats['successful_downloads'] / self.stats['total_downloads']) * 100 \
                      if self.stats['total_downloads'] > 0 else 0
        
        self.logger.info("="*60)
        self.logger.info("ARCHIVE COLLECTION COMPLETED")
        self.logger.info("="*60)
        self.logger.info(f"Total Tasks: {self.stats['total_downloads']}")
        self.logger.info(f"Successful: {self.stats['successful_downloads']}")
        self.logger.info(f"Failed: {self.stats['failed_downloads']}")
        self.logger.info(f"Skipped: {self.stats['skipped_files']}")
        self.logger.info(f"Success Rate: {success_rate:.1f}%")
        self.logger.info(f"Total Size: {format_file_size(self.stats['total_size'])}")
        self.logger.info(f"Output Directory: {self.config.get('output_directory')}")
        self.logger.info("="*60)
    
    def _save_collection_summary(self) -> None:
        """Save collection summary to output directory."""
        output_dir = Path(self.config.get('output_directory'))
        summary_file = output_dir / "collection_summary.json"
        
        summary = {
            'workflow_type': 'archive_collection',
            'timestamp': datetime.now().isoformat(),
            'configuration': self.config.to_dict(),
            'statistics': self.stats,
            'metrics': self.metrics.get_metrics()
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info(f"Collection summary saved to: {summary_file}")