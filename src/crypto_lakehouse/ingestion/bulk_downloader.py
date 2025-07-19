"""Enhanced bulk data downloader with storage interface integration."""

import asyncio
import csv
import hashlib
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections.abc import AsyncGenerator

from ..core.config import Settings
from ..core.models import DataType, FundingRateData, KlineData
from ..storage.base import BaseStorage

logger = logging.getLogger(__name__)


class BulkDownloader:
    """
    Enhanced bulk downloader with s5cmd batch optimization and storage interface integration.
    
    Features:
    - High-performance s5cmd batch download with parallel execution
    - Integration with storage factory pattern
    - Async file download with checksum validation
    - Support for various protocols (HTTP, S3)
    - Intelligent batch optimization and progress tracking
    - Storage interface compatibility
    - Specs-driven performance optimization
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize bulk downloader with configuration.
        
        Args:
            config: Dictionary containing downloader configuration
                   Required keys: base_url
                   Optional keys: timeout_seconds, verify_checksums, storage, batch_size, max_concurrent
        """
        self.base_url = config.get('base_url', 'https://data.binance.vision/data/')
        self.timeout_seconds = config.get('timeout_seconds', 300)
        self.verify_checksums = config.get('verify_checksums', True)
        self.storage: Optional[BaseStorage] = config.get('storage')
        
        # Batch download configuration
        self.batch_size = config.get('batch_size', 50)  # Files per batch
        self.max_concurrent = config.get('max_concurrent', 10)  # s5cmd workers
        self.part_size_mb = config.get('part_size_mb', 50)  # s5cmd part size
        
        # Performance optimization
        self.enable_batch_mode = config.get('enable_batch_mode', True)
        self.s5cmd_available = None  # Cache s5cmd availability
        
        # Download statistics
        self.stats = {
            'files_downloaded': 0,
            'files_failed': 0,
            'total_bytes': 0,
            'download_time': 0.0,
            'batches_processed': 0,
            'cache_hits': 0
        }
    
    async def download_file(
        self, 
        source_url: str, 
        target_path: Path, 
        validate_checksum: bool = True
    ) -> Dict[str, Any]:
        """
        Download a single file with validation and error handling.
        
        Args:
            source_url: Source URL or S3 path
            target_path: Local target file path
            validate_checksum: Whether to validate file checksums
            
        Returns:
            Dictionary with download result information
        """
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file already exists
            if target_path.exists() and target_path.stat().st_size > 0:
                logger.debug(f"File already exists: {target_path}")
                return {
                    'success': True,
                    'file_size': target_path.stat().st_size,
                    'source_url': source_url,
                    'target_path': str(target_path),
                    'cached': True
                }
            
            # Determine download method based on URL
            if source_url.startswith('s3://'):
                success, file_size, error = await self._download_s3_file(source_url, target_path)
            else:
                success, file_size, error = await self._download_http_file(source_url, target_path)
            
            # Calculate download time
            download_time = asyncio.get_event_loop().time() - start_time
            
            if success:
                # Validate checksum if requested
                if validate_checksum and self.verify_checksums:
                    checksum_valid = await self._validate_file_checksum(target_path, source_url)
                    if not checksum_valid:
                        logger.warning(f"Checksum validation failed for {target_path}")
                
                # Update statistics
                self.stats['files_downloaded'] += 1
                self.stats['total_bytes'] += file_size
                self.stats['download_time'] += download_time
                
                return {
                    'success': True,
                    'file_size': file_size,
                    'source_url': source_url,
                    'target_path': str(target_path),
                    'download_time': download_time,
                    'cached': False
                }
            else:
                self.stats['files_failed'] += 1
                return {
                    'success': False,
                    'error': error,
                    'source_url': source_url,
                    'target_path': str(target_path)
                }
                
        except Exception as e:
            self.stats['files_failed'] += 1
            logger.error(f"Download failed for {source_url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'source_url': source_url,
                'target_path': str(target_path)
            }
    
    async def _download_s3_file(self, s3_url: str, target_path: Path) -> tuple[bool, int, Optional[str]]:
        """Download file from S3 using s5cmd or AWS CLI."""
        try:
            # Try s5cmd first (faster)
            if await self._check_s5cmd_available():
                return await self._download_with_s5cmd_single(s3_url, target_path)
            else:
                # Fallback to converting S3 URL to HTTP URL
                http_url = s3_url.replace('s3://data.binance.vision/', 'https://data.binance.vision/')
                return await self._download_http_file(http_url, target_path)
                
        except Exception as e:
            return False, 0, str(e)
    
    async def _download_http_file(self, url: str, target_path: Path) -> tuple[bool, int, Optional[str]]:
        """Download file via HTTP using wget or curl."""
        try:
            # Use wget for HTTP downloads
            process = await asyncio.create_subprocess_exec(
                'wget',
                '-O', str(target_path),
                '-q',  # Quiet mode
                f'--timeout={self.timeout_seconds}',
                '--tries=3',
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and target_path.exists():
                file_size = target_path.stat().st_size
                logger.debug(f"Downloaded {target_path.name} ({file_size} bytes)")
                return True, file_size, None
            else:
                error_msg = stderr.decode() if stderr else "Unknown wget error"
                logger.error(f"wget failed for {url}: {error_msg}")
                return False, 0, error_msg
                
        except Exception as e:
            return False, 0, str(e)
    
    async def _download_with_s5cmd_single(self, s3_url: str, target_path: Path) -> tuple[bool, int, Optional[str]]:
        """Download single file using s5cmd."""
        try:
            cmd = [
                's5cmd',
                '--no-sign-request',  # Required for public buckets
                '--retry-count', '3',
                'cp',
                '--source-region', 'ap-northeast-1',  # Binance archive region
                '--if-size-differ',
                s3_url,
                str(target_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and target_path.exists():
                file_size = target_path.stat().st_size
                logger.debug(f"s5cmd downloaded {target_path.name} ({file_size} bytes)")
                return True, file_size, None
            else:
                error_msg = stderr.decode() if stderr else "Unknown s5cmd error"
                logger.error(f"s5cmd failed for {s3_url}: {error_msg}")
                return False, 0, error_msg
                
        except Exception as e:
            return False, 0, str(e)
    
    async def _check_s5cmd_available(self) -> bool:
        """Check if s5cmd is available."""
        try:
            process = await asyncio.create_subprocess_exec(
                's5cmd', 'version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except FileNotFoundError:
            return False
    
    async def _validate_file_checksum(self, file_path: Path, source_url: str) -> bool:
        """Validate file checksum if available."""
        try:
            # For Binance data, checksums aren't typically provided
            # This is a placeholder for future checksum validation
            # You could implement MD5/SHA256 validation here if checksums are available
            return True
            
        except Exception as e:
            logger.warning(f"Checksum validation failed: {e}")
            return False
    
    async def download_files_batch(
        self, 
        download_tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Download multiple files using optimized batch processing.
        
        Args:
            download_tasks: List of dictionaries with 'source_url' and 'target_path' keys
            
        Returns:
            List of download results for each task
        """
        if not download_tasks:
            return []
        
        # Check s5cmd availability once
        if self.s5cmd_available is None:
            self.s5cmd_available = await self._check_s5cmd_available()
        
        # Use batch mode if enabled and s5cmd is available
        if self.enable_batch_mode and self.s5cmd_available and len(download_tasks) > 1:
            return await self._download_batch_s5cmd(download_tasks)
        else:
            # Fallback to individual downloads
            return await self._download_batch_individual(download_tasks)
    
    async def _download_batch_s5cmd(self, download_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Download files using s5cmd batch mode for optimal performance.
        
        Specs-driven implementation:
        - Uses s5cmd 'run' command with batch file
        - Optimizes for concurrent transfers with configurable workers
        - Handles large batches by splitting them into optimal chunks
        - Provides detailed progress tracking and error reporting
        """
        results = []
        start_time = asyncio.get_event_loop().time()
        
        # Split tasks into optimal batches
        batches = self._split_into_batches(download_tasks, self.batch_size)
        
        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} files)")
            
            # Filter out files that already exist
            filtered_batch = []
            for task in batch:
                target_path = Path(task['target_path'])
                if target_path.exists() and target_path.stat().st_size > 0:
                    # File exists, mark as cached
                    results.append({
                        'success': True,
                        'file_size': target_path.stat().st_size,
                        'source_url': task['source_url'],
                        'target_path': str(target_path),
                        'cached': True
                    })
                    self.stats['cache_hits'] += 1
                else:
                    filtered_batch.append(task)
            
            if not filtered_batch:
                continue  # All files were cached
            
            # Create temporary batch file for s5cmd
            batch_result = await self._execute_s5cmd_batch(filtered_batch)
            results.extend(batch_result)
            
            self.stats['batches_processed'] += 1
        
        # Update total download time
        total_time = asyncio.get_event_loop().time() - start_time
        self.stats['download_time'] += total_time
        
        logger.info(f"Batch download completed: {len(results)} files in {total_time:.2f}s")
        return results
    
    async def _execute_s5cmd_batch(self, batch_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a single batch using s5cmd run command."""
        try:
            # Create temporary batch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for task in batch_tasks:
                    source_url = task['source_url']
                    target_path = task['target_path']
                    
                    # Ensure target directory exists
                    Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write s5cmd cp command with correct parameters for Binance public archive
                    cmd_line = f"cp --source-region ap-northeast-1 --if-size-differ --concurrency {self.max_concurrent} --part-size {self.part_size_mb} '{source_url}' '{target_path}'\n"
                    f.write(cmd_line)
                
                batch_file = f.name
            
            try:
                # Execute s5cmd batch with no-sign-request for public archives
                cmd = [
                    's5cmd',
                    '--no-sign-request',  # Required for public buckets
                    '--numworkers', str(self.max_concurrent),
                    '--retry-count', '3',
                    'run',
                    batch_file
                ]
                
                logger.debug(f"Executing s5cmd batch: {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                # Process results
                return self._process_s5cmd_batch_results(
                    batch_tasks, process.returncode, stdout, stderr
                )
                
            finally:
                # Clean up batch file
                Path(batch_file).unlink(missing_ok=True)
                
        except Exception as e:
            logger.error(f"s5cmd batch execution failed: {e}")
            # Fallback to individual downloads for this batch
            return await self._download_batch_individual(batch_tasks)
    
    def _process_s5cmd_batch_results(
        self, 
        batch_tasks: List[Dict[str, Any]], 
        return_code: int, 
        stdout: bytes, 
        stderr: bytes
    ) -> List[Dict[str, Any]]:
        """Process s5cmd batch execution results."""
        results = []
        
        # Parse stdout for successful downloads
        successful_files = set()
        if stdout:
            for line in stdout.decode().split('\n'):
                if 'cp' in line and 'completed' in line.lower():
                    # Extract file path from s5cmd output
                    parts = line.split()
                    if len(parts) >= 2:
                        successful_files.add(parts[-1])
        
        # Parse stderr for errors
        errors = {}
        if stderr:
            error_text = stderr.decode()
            for line in error_text.split('\n'):
                if 'ERROR' in line or 'error' in line:
                    # Try to extract file path from error message
                    for task in batch_tasks:
                        if task['target_path'] in line or task['source_url'] in line:
                            errors[task['target_path']] = line.strip()
        
        # Create results for each task
        for task in batch_tasks:
            target_path = Path(task['target_path'])
            
            if str(target_path) in successful_files or (target_path.exists() and target_path.stat().st_size > 0):
                # Successful download
                file_size = target_path.stat().st_size if target_path.exists() else 0
                results.append({
                    'success': True,
                    'file_size': file_size,
                    'source_url': task['source_url'],
                    'target_path': str(target_path),
                    'cached': False
                })
                self.stats['files_downloaded'] += 1
                self.stats['total_bytes'] += file_size
            else:
                # Failed download
                error_msg = errors.get(str(target_path), f"s5cmd batch failed (return code: {return_code})")
                results.append({
                    'success': False,
                    'error': error_msg,
                    'source_url': task['source_url'],
                    'target_path': str(target_path)
                })
                self.stats['files_failed'] += 1
        
        return results
    
    async def _download_batch_individual(self, download_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Download files individually using existing download_file method."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def download_single_task(task: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.download_file(
                    task['source_url'],
                    Path(task['target_path']),
                    validate_checksum=self.verify_checksums
                )
        
        # Execute downloads concurrently
        tasks = [download_single_task(task) for task in download_tasks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'error': str(result),
                    'source_url': 'unknown',
                    'target_path': 'unknown'
                })
                self.stats['files_failed'] += 1
            else:
                processed_results.append(result)
        
        return processed_results
    
    def _split_into_batches(self, tasks: List[Any], batch_size: int) -> List[List[Any]]:
        """Split tasks into batches of specified size."""
        batches = []
        for i in range(0, len(tasks), batch_size):
            batches.append(tasks[i:i + batch_size])
        return batches
    
    def get_download_stats(self) -> Dict[str, Any]:
        """Get comprehensive download statistics."""
        stats = self.stats.copy()
        stats.update({
            'success_rate': (stats['files_downloaded'] / (stats['files_downloaded'] + stats['files_failed'])) * 100 
                           if (stats['files_downloaded'] + stats['files_failed']) > 0 else 0,
            's5cmd_available': self.s5cmd_available,
            'batch_mode_enabled': self.enable_batch_mode,
            'avg_batch_size': stats['files_downloaded'] / stats['batches_processed'] 
                             if stats['batches_processed'] > 0 else 0
        })
        return stats


class S5cmdDownloader:
    """High-performance bulk downloader using s5cmd."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.binance_config = settings.binance
        self.base_url = "https://data.binance.vision"

    async def download_files_bulk(
        self, file_urls: List[str], local_dir: Path, max_concurrent: int = 10
    ) -> List[str]:
        """Download multiple files in parallel using s5cmd."""
        try:
            # Ensure directory exists
            local_dir.mkdir(parents=True, exist_ok=True)

            # Create temporary file list for s5cmd
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                for url in file_urls:
                    filename = Path(url).name
                    local_path = local_dir / filename
                    f.write(f"{url} {local_path}\n")

                url_list_file = f.name

            try:
                # Use s5cmd if available, otherwise fall back to wget
                if await self._check_s5cmd_available():
                    return await self._download_with_s5cmd(url_list_file, max_concurrent)
                else:
                    return await self._download_with_wget(file_urls, local_dir, max_concurrent)

            finally:
                # Clean up temp file
                Path(url_list_file).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Bulk download failed: {e}")
            return []

    async def _check_s5cmd_available(self) -> bool:
        """Check if s5cmd is available in PATH."""
        try:
            result = await asyncio.create_subprocess_exec(
                "s5cmd", "version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            return result.returncode == 0
        except FileNotFoundError:
            return False

    async def _download_with_s5cmd(self, url_list_file: str, max_concurrent: int) -> List[str]:
        """Download using s5cmd for maximum performance."""
        try:
            cmd = [
                "s5cmd",
                "--numworkers",
                str(max_concurrent),
                "--retry-count",
                "3",
                "cp",
                "--source-region",
                "us-east-1",
                "--if-size-differ",
                "--list-type",
                "2",
                "--include-from",
                url_list_file,
            ]

            logger.info(f"Starting s5cmd bulk download with {max_concurrent} workers")

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("s5cmd bulk download completed successfully")
                # Parse downloaded files from stdout
                downloaded_files = []
                for line in stdout.decode().split("\n"):
                    if line.strip() and "cp" in line:
                        # Extract local file path from s5cmd output
                        parts = line.split()
                        if len(parts) >= 3:
                            downloaded_files.append(parts[-1])

                return downloaded_files
            else:
                logger.error(f"s5cmd failed: {stderr.decode()}")
                return []

        except Exception as e:
            logger.error(f"s5cmd execution failed: {e}")
            return []

    async def _download_with_wget(
        self, file_urls: List[str], local_dir: Path, max_concurrent: int
    ) -> List[str]:
        """Fallback download using wget with parallel execution."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_single(url: str) -> Optional[str]:
            async with semaphore:
                try:
                    filename = Path(url).name
                    local_path = local_dir / filename

                    # Skip if file already exists and is not empty
                    if local_path.exists() and local_path.stat().st_size > 0:
                        logger.info(f"File already exists, skipping: {filename}")
                        return str(local_path)

                    process = await asyncio.create_subprocess_exec(
                        "wget",
                        "-O",
                        str(local_path),
                        "-q",  # Quiet mode
                        "--timeout=30",
                        "--tries=3",
                        url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )

                    await process.communicate()

                    if process.returncode == 0 and local_path.exists():
                        logger.info(f"Downloaded: {filename}")
                        return str(local_path)
                    else:
                        logger.warning(f"Failed to download: {url}")
                        return None

                except Exception as e:
                    logger.error(f"Download error for {url}: {e}")
                    return None

        # Execute downloads in parallel
        tasks = [download_single(url) for url in file_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful downloads
        downloaded_files = [
            result for result in results if isinstance(result, str) and result is not None
        ]

        logger.info(f"Downloaded {len(downloaded_files)} of {len(file_urls)} files")
        return downloaded_files


class BinanceDataParser:
    """Parser for Binance historical data files."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def parse_kline_file(
        self, file_path: str, symbol: str, data_type: DataType = DataType.KLINES
    ) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from CSV file (ZIP or raw)."""
        try:
            # Determine if file is zipped
            path = Path(file_path)

            if path.suffix.lower() == ".zip":
                # Extract and parse ZIP file
                async for kline in self._parse_zip_kline_file(file_path, symbol):
                    yield kline
            else:
                # Parse raw CSV file
                async for kline in self._parse_csv_kline_file(file_path, symbol):
                    yield kline

        except Exception as e:
            logger.error(f"Failed to parse K-line file {file_path}: {e}")

    async def _parse_zip_kline_file(
        self, zip_path: str, symbol: str
    ) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from ZIP file."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                # Find CSV file in ZIP
                csv_files = [f for f in zip_file.namelist() if f.endswith(".csv")]

                if not csv_files:
                    logger.warning(f"No CSV files found in {zip_path}")
                    return

                # Parse first CSV file
                csv_filename = csv_files[0]

                with zip_file.open(csv_filename) as csv_file:
                    # Read and decode CSV content
                    content = csv_file.read().decode("utf-8")
                    lines = content.strip().split("\n")

                    for line in lines:
                        if line.strip():
                            try:
                                kline_data = self._parse_kline_csv_row(line, symbol)
                                if kline_data:
                                    yield kline_data
                            except Exception as e:
                                logger.warning(f"Failed to parse CSV row: {e}")

        except Exception as e:
            logger.error(f"Failed to parse ZIP file {zip_path}: {e}")

    async def _parse_csv_kline_file(
        self, csv_path: str, symbol: str
    ) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from raw CSV file."""
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.reader(f)

                for row in reader:
                    if row:  # Skip empty rows
                        try:
                            kline_data = self._parse_kline_csv_row(",".join(row), symbol)
                            if kline_data:
                                yield kline_data
                        except Exception as e:
                            logger.warning(f"Failed to parse CSV row: {e}")

        except Exception as e:
            logger.error(f"Failed to parse CSV file {csv_path}: {e}")

    def _parse_kline_csv_row(self, csv_row: str, symbol: str) -> Optional[KlineData]:
        """Parse a single CSV row into KlineData."""
        try:
            # Binance K-line CSV format:
            # [0] Open time, [1] Open, [2] High, [3] Low, [4] Close, [5] Volume,
            # [6] Close time, [7] Quote asset volume, [8] Number of trades,
            # [9] Taker buy base asset volume, [10] Taker buy quote asset volume, [11] Ignore

            parts = csv_row.strip().split(",")

            if len(parts) < 11:
                logger.warning(f"Invalid CSV row format: {csv_row}")
                return None

            return KlineData(
                symbol=symbol,
                open_time=datetime.fromtimestamp(int(parts[0]) / 1000),
                close_time=datetime.fromtimestamp(int(parts[6]) / 1000),
                open_price=Decimal(parts[1]),
                high_price=Decimal(parts[2]),
                low_price=Decimal(parts[3]),
                close_price=Decimal(parts[4]),
                volume=Decimal(parts[5]),
                quote_asset_volume=Decimal(parts[7]),
                number_of_trades=int(parts[8]),
                taker_buy_base_asset_volume=Decimal(parts[9]),
                taker_buy_quote_asset_volume=Decimal(parts[10]),
            )

        except Exception as e:
            logger.error(f"Failed to parse K-line CSV row: {e}")
            return None

    async def parse_funding_file(
        self, file_path: str, symbol: str
    ) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from CSV file."""
        try:
            path = Path(file_path)

            if path.suffix.lower() == ".zip":
                async for funding in self._parse_zip_funding_file(file_path, symbol):
                    yield funding
            else:
                async for funding in self._parse_csv_funding_file(file_path, symbol):
                    yield funding

        except Exception as e:
            logger.error(f"Failed to parse funding file {file_path}: {e}")

    async def _parse_zip_funding_file(
        self, zip_path: str, symbol: str
    ) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from ZIP file."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_file:
                csv_files = [f for f in zip_file.namelist() if f.endswith(".csv")]

                if not csv_files:
                    return

                csv_filename = csv_files[0]

                with zip_file.open(csv_filename) as csv_file:
                    content = csv_file.read().decode("utf-8")
                    lines = content.strip().split("\n")

                    for line in lines:
                        if line.strip():
                            funding_data = self._parse_funding_csv_row(line, symbol)
                            if funding_data:
                                yield funding_data

        except Exception as e:
            logger.error(f"Failed to parse funding ZIP file {zip_path}: {e}")

    async def _parse_csv_funding_file(
        self, csv_path: str, symbol: str
    ) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from raw CSV file."""
        try:
            with open(csv_path, encoding="utf-8") as f:
                reader = csv.reader(f)

                for row in reader:
                    if row:
                        funding_data = self._parse_funding_csv_row(",".join(row), symbol)
                        if funding_data:
                            yield funding_data

        except Exception as e:
            logger.error(f"Failed to parse funding CSV file {csv_path}: {e}")

    def _parse_funding_csv_row(self, csv_row: str, symbol: str) -> Optional[FundingRateData]:
        """Parse a single funding rate CSV row."""
        try:
            # Binance funding rate CSV format:
            # [0] calc_time, [1] funding_rate, [2] mark_price

            parts = csv_row.strip().split(",")

            if len(parts) < 2:
                return None

            return FundingRateData(
                symbol=symbol,
                funding_time=datetime.fromtimestamp(int(parts[0]) / 1000),
                funding_rate=Decimal(parts[1]),
                mark_price=Decimal(parts[2]) if len(parts) > 2 and parts[2] else None,
            )

        except Exception as e:
            logger.error(f"Failed to parse funding CSV row: {e}")
            return None
