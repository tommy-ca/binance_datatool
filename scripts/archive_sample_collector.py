#!/usr/bin/env python3
"""
Binance Archive Sample Collection Workflow

Automated collection tool that uses the Binance archive matrix to systematically
collect sample data from all available market types, data types, and intervals.

Features:
- Matrix-driven collection based on binance_archive_matrix.json
- Configurable symbol and date selection
- Parallel downloads with s5cmd
- Automatic directory structure creation following Binance schema
- Progress tracking and error handling
- Checksum validation support
- Resume capability for interrupted collections

Usage:
    python archive_sample_collector.py --config config.json
    python archive_sample_collector.py --quick-test
    python archive_sample_collector.py --market spot --symbols BTCUSDT,ETHUSDT
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('archive_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BinanceArchiveCollector:
    """Automated Binance archive sample collector using matrix-driven approach."""
    
    def __init__(self, matrix_path: str, output_dir: str = "archive-samples"):
        """Initialize collector with archive matrix and output directory."""
        self.matrix_path = Path(matrix_path)
        self.output_dir = Path(output_dir)
        self.matrix = self._load_matrix()
        self.base_url = "s3://data.binance.vision/data/"
        self.stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_size': 0,
            'start_time': None,
            'end_time': None
        }
        
    def _load_matrix(self) -> Dict:
        """Load the Binance archive availability matrix."""
        try:
            with open(self.matrix_path, 'r') as f:
                matrix = json.load(f)
            logger.info(f"Loaded archive matrix from {self.matrix_path}")
            return matrix
        except Exception as e:
            logger.error(f"Failed to load matrix: {e}")
            sys.exit(1)
    
    def _create_directory_structure(self, market: str, partition: str, data_type: str, 
                                   symbol: str, interval: Optional[str] = None) -> Path:
        """Create directory structure following Binance schema."""
        if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
            dir_path = self.output_dir / market / partition / data_type / symbol / interval
        else:
            dir_path = self.output_dir / market / partition / data_type / symbol
        
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    def _generate_file_url_and_path(self, market: str, partition: str, data_type: str,
                                   symbol: str, interval: Optional[str], date: str) -> Tuple[str, Path]:
        """Generate S3 URL and local file path for a specific data file."""
        
        # Determine base S3 path based on market
        if market == "spot":
            s3_base = f"{self.base_url}spot/{partition}/{data_type}/{symbol}"
        elif market == "futures_um":
            s3_base = f"{self.base_url}futures/um/{partition}/{data_type}/{symbol}"
        elif market == "futures_cm":
            s3_base = f"{self.base_url}futures/cm/{partition}/{data_type}/{symbol}"
        elif market == "options":
            s3_base = f"{self.base_url}option/{partition}/{data_type}"
        else:
            raise ValueError(f"Unknown market type: {market}")
        
        # Add interval to path if applicable
        if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
            s3_base += f"/{interval}"
        
        # Generate filename based on partition type
        if partition == "daily":
            if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
                filename = f"{symbol}-{interval}-{date}.zip"
            else:
                filename = f"{symbol}-{data_type}-{date}.zip"
        else:  # monthly
            if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
                filename = f"{symbol}-{interval}-{date}.zip"
            else:
                filename = f"{symbol}-{data_type}-{date}.zip"
        
        s3_url = f"{s3_base}/{filename}"
        
        # Create local directory and file path
        local_dir = self._create_directory_structure(market, partition, data_type, symbol, interval)
        local_path = local_dir / filename
        
        return s3_url, local_path
    
    def _download_file(self, s3_url: str, local_path: Path, download_checksum: bool = True) -> bool:
        """Download file using s5cmd and optionally its checksum."""
        try:
            # Download main file
            cmd = ["s5cmd", "--no-sign-request", "cp", s3_url, str(local_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.warning(f"Failed to download {s3_url}: {result.stderr}")
                return False
            
            # Download checksum if requested and available
            if download_checksum:
                checksum_url = f"{s3_url}.CHECKSUM"
                checksum_path = Path(str(local_path) + ".CHECKSUM")
                
                cmd_checksum = ["s5cmd", "--no-sign-request", "cp", checksum_url, str(checksum_path)]
                checksum_result = subprocess.run(cmd_checksum, capture_output=True, text=True, timeout=60)
                
                if checksum_result.returncode == 0:
                    logger.debug(f"Downloaded checksum for {local_path.name}")
                else:
                    logger.debug(f"No checksum available for {local_path.name}")
            
            file_size = local_path.stat().st_size
            self.stats['total_size'] += file_size
            logger.info(f"Downloaded {local_path.name} ({file_size:,} bytes)")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout downloading {s3_url}")
            return False
        except Exception as e:
            logger.error(f"Error downloading {s3_url}: {e}")
            return False
    
    def _generate_collection_tasks(self, config: Dict) -> List[Dict]:
        """Generate collection tasks based on configuration and matrix."""
        tasks = []
        
        # Get date range
        if config.get('date_range'):
            dates = self._generate_date_range(config['date_range'])
        else:
            dates = [config.get('default_date', '2025-07-15')]
        
        # Iterate through matrix availability
        for entry in self.matrix['availability_matrix']:
            market = entry['market']
            data_type = entry['data_type']
            intervals = entry.get('intervals', [None])
            partitions = entry.get('partitions', ['daily'])
            
            # Filter by market if specified
            if config.get('markets') and market not in config['markets']:
                continue
            
            # Filter by data type if specified
            if config.get('data_types') and data_type not in config['data_types']:
                continue
            
            # Get symbols for this market
            symbols = self._get_symbols_for_market(market, config)
            
            # Generate tasks for each combination
            for symbol in symbols:
                for partition in partitions:
                    # Skip monthly partitions for recent dates (current month not yet complete)
                    if partition == "monthly" and config.get('default_date', '2025-07-15').startswith('2025-07'):
                        logger.debug(f"Skipping monthly partition for current month: {data_type}")
                        continue
                    
                    for interval in intervals:
                        for date in dates:
                            # Adjust date format for monthly partitions
                            if partition == "monthly":
                                # Use previous month for monthly data
                                date_obj = datetime.strptime(date, '%Y-%m-%d')
                                if date_obj.month == 1:
                                    prev_month = date_obj.replace(year=date_obj.year-1, month=12)
                                else:
                                    prev_month = date_obj.replace(month=date_obj.month-1)
                                date_str = prev_month.strftime('%Y-%m')
                            else:
                                date_str = date  # YYYY-MM-DD format
                            
                            task = {
                                'market': market,
                                'partition': partition,
                                'data_type': data_type,
                                'symbol': symbol,
                                'interval': interval,
                                'date': date_str
                            }
                            tasks.append(task)
        
        return tasks
    
    def _get_symbols_for_market(self, market: str, config: Dict) -> List[str]:
        """Get symbols for a specific market type."""
        if config.get('symbols'):
            return config['symbols']
        
        # Use default symbols from matrix
        if market == "spot":
            return self.matrix['markets']['spot']['sample_symbols'][:3]  # Limit to first 3
        elif market == "futures_um":
            return self.matrix['markets']['futures']['um']['sample_symbols'][:2]  # Limit to first 2
        elif market == "futures_cm":
            return self.matrix['markets']['futures']['cm']['sample_symbols'][:2]  # Limit to first 2
        elif market == "options":
            return ["BTCBVOLUSDT", "ETHBVOLUSDT"]
        else:
            return ["BTCUSDT"]  # Default fallback
    
    def _generate_date_range(self, date_config: Dict) -> List[str]:
        """Generate date range based on configuration."""
        start_date = datetime.strptime(date_config['start'], '%Y-%m-%d')
        end_date = datetime.strptime(date_config['end'], '%Y-%m-%d')
        
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
        
        return dates
    
    def collect_samples(self, config: Dict) -> Dict:
        """Main collection method that orchestrates the entire process."""
        self.stats['start_time'] = datetime.now()
        logger.info("Starting Binance archive sample collection")
        
        # Generate collection tasks
        tasks = self._generate_collection_tasks(config)
        self.stats['total_downloads'] = len(tasks)
        
        logger.info(f"Generated {len(tasks)} collection tasks")
        
        # Execute downloads with parallel processing
        max_workers = config.get('max_parallel_downloads', 4)
        download_checksum = config.get('download_checksum', True)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_task = {}
            for task in tasks:
                s3_url, local_path = self._generate_file_url_and_path(
                    task['market'], task['partition'], task['data_type'],
                    task['symbol'], task['interval'], task['date']
                )
                
                # Skip if file already exists
                if local_path.exists() and not config.get('force_redownload', False):
                    logger.debug(f"Skipping existing file: {local_path.name}")
                    self.stats['successful_downloads'] += 1
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
                    else:
                        self.stats['failed_downloads'] += 1
                        logger.error(f"Failed task: {task}")
                except Exception as e:
                    self.stats['failed_downloads'] += 1
                    logger.error(f"Exception in task {task}: {e}")
        
        self.stats['end_time'] = datetime.now()
        self._log_final_stats()
        return self.stats
    
    def _log_final_stats(self):
        """Log final collection statistics."""
        duration = self.stats['end_time'] - self.stats['start_time']
        success_rate = (self.stats['successful_downloads'] / self.stats['total_downloads']) * 100
        
        logger.info("="*60)
        logger.info("COLLECTION COMPLETED")
        logger.info("="*60)
        logger.info(f"Total Tasks: {self.stats['total_downloads']}")
        logger.info(f"Successful: {self.stats['successful_downloads']}")
        logger.info(f"Failed: {self.stats['failed_downloads']}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Total Size: {self.stats['total_size']:,} bytes ({self.stats['total_size']/1024/1024:.1f} MB)")
        logger.info(f"Duration: {duration}")
        logger.info(f"Output Directory: {self.output_dir}")
        logger.info("="*60)


def create_default_config() -> Dict:
    """Create default configuration for sample collection."""
    return {
        "markets": ["spot", "futures_um", "futures_cm"],
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "data_types": ["klines", "trades", "aggTrades", "fundingRate"],
        "default_date": "2025-07-15",
        "max_parallel_downloads": 4,
        "download_checksum": True,
        "force_redownload": False,
        "output_directory": "archive-samples-workflow"
    }


def create_quick_test_config() -> Dict:
    """Create minimal configuration for quick testing."""
    return {
        "markets": ["spot"],
        "symbols": ["BTCUSDT"],
        "data_types": ["klines"],
        "default_date": "2025-07-15",
        "max_parallel_downloads": 2,
        "download_checksum": True,
        "force_redownload": False,
        "output_directory": "archive-samples-test"
    }


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Binance Archive Sample Collector")
    parser.add_argument("--matrix", default="sample-data/archive-matrix/binance_archive_matrix.json",
                       help="Path to archive matrix JSON file")
    parser.add_argument("--config", help="Path to configuration JSON file")
    parser.add_argument("--output", default="archive-samples-workflow",
                       help="Output directory for collected samples")
    parser.add_argument("--quick-test", action="store_true",
                       help="Run quick test collection (spot klines only)")
    parser.add_argument("--market", help="Single market to collect (spot, futures_um, futures_cm)")
    parser.add_argument("--symbols", help="Comma-separated list of symbols")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load or create configuration
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    elif args.quick_test:
        config = create_quick_test_config()
    else:
        config = create_default_config()
    
    # Override config with CLI arguments
    if args.output:
        config["output_directory"] = args.output
    if args.market:
        config["markets"] = [args.market]
    if args.symbols:
        config["symbols"] = args.symbols.split(",")
    
    # Initialize collector
    collector = BinanceArchiveCollector(args.matrix, config["output_directory"])
    
    # Save configuration for reference
    config_path = Path(config["output_directory"]) / "collection_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Configuration saved to: {config_path}")
    
    # Run collection
    try:
        stats = collector.collect_samples(config)
        logger.info("Collection completed successfully!")
        return 0
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Collection failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())