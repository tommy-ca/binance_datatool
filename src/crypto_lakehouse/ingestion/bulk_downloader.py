"""Bulk data downloader using s5cmd for high-performance S3 transfers."""

import asyncio
import subprocess
import tempfile
import zipfile
import gzip
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta
import logging
import polars as pl
from decimal import Decimal

from ..core.models import (
    DataType, TradeType, Exchange, 
    KlineData, FundingRateData, LiquidationData
)
from ..core.config import Settings

logger = logging.getLogger(__name__)


class S5cmdDownloader:
    """High-performance bulk downloader using s5cmd."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.binance_config = settings.binance
        self.base_url = "https://data.binance.vision"
        
    async def download_files_bulk(
        self, 
        file_urls: List[str], 
        local_dir: Path,
        max_concurrent: int = 10
    ) -> List[str]:
        """Download multiple files in parallel using s5cmd."""
        try:
            # Ensure directory exists
            local_dir.mkdir(parents=True, exist_ok=True)
            
            # Create temporary file list for s5cmd
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
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
                's5cmd', 'version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    async def _download_with_s5cmd(
        self, 
        url_list_file: str, 
        max_concurrent: int
    ) -> List[str]:
        """Download using s5cmd for maximum performance."""
        try:
            cmd = [
                's5cmd',
                '--numworkers', str(max_concurrent),
                '--retry-count', '3',
                'cp',
                '--source-region', 'us-east-1',
                '--if-size-differ',
                '--list-type', '2',
                f'--include-from', url_list_file
            ]
            
            logger.info(f"Starting s5cmd bulk download with {max_concurrent} workers")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("s5cmd bulk download completed successfully")
                # Parse downloaded files from stdout
                downloaded_files = []
                for line in stdout.decode().split('\n'):
                    if line.strip() and 'cp' in line:
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
        self, 
        file_urls: List[str], 
        local_dir: Path,
        max_concurrent: int
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
                        'wget',
                        '-O', str(local_path),
                        '-q',  # Quiet mode
                        '--timeout=30',
                        '--tries=3',
                        url,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
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
            result for result in results 
            if isinstance(result, str) and result is not None
        ]
        
        logger.info(f"Downloaded {len(downloaded_files)} of {len(file_urls)} files")
        return downloaded_files


class BinanceDataParser:
    """Parser for Binance historical data files."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    async def parse_kline_file(
        self, 
        file_path: str, 
        symbol: str,
        data_type: DataType = DataType.KLINES
    ) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from CSV file (ZIP or raw)."""
        try:
            # Determine if file is zipped
            path = Path(file_path)
            
            if path.suffix.lower() == '.zip':
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
        self, 
        zip_path: str, 
        symbol: str
    ) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from ZIP file."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Find CSV file in ZIP
                csv_files = [f for f in zip_file.namelist() if f.endswith('.csv')]
                
                if not csv_files:
                    logger.warning(f"No CSV files found in {zip_path}")
                    return
                
                # Parse first CSV file
                csv_filename = csv_files[0]
                
                with zip_file.open(csv_filename) as csv_file:
                    # Read and decode CSV content
                    content = csv_file.read().decode('utf-8')
                    lines = content.strip().split('\n')
                    
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
        self, 
        csv_path: str, 
        symbol: str
    ) -> AsyncGenerator[KlineData, None]:
        """Parse K-line data from raw CSV file."""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                for row in reader:
                    if row:  # Skip empty rows
                        try:
                            kline_data = self._parse_kline_csv_row(','.join(row), symbol)
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
            
            parts = csv_row.strip().split(',')
            
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
                taker_buy_quote_asset_volume=Decimal(parts[10])
            )
            
        except Exception as e:
            logger.error(f"Failed to parse K-line CSV row: {e}")
            return None
    
    async def parse_funding_file(
        self, 
        file_path: str, 
        symbol: str
    ) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from CSV file."""
        try:
            path = Path(file_path)
            
            if path.suffix.lower() == '.zip':
                async for funding in self._parse_zip_funding_file(file_path, symbol):
                    yield funding
            else:
                async for funding in self._parse_csv_funding_file(file_path, symbol):
                    yield funding
                    
        except Exception as e:
            logger.error(f"Failed to parse funding file {file_path}: {e}")
    
    async def _parse_zip_funding_file(
        self, 
        zip_path: str, 
        symbol: str
    ) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from ZIP file."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                csv_files = [f for f in zip_file.namelist() if f.endswith('.csv')]
                
                if not csv_files:
                    return
                
                csv_filename = csv_files[0]
                
                with zip_file.open(csv_filename) as csv_file:
                    content = csv_file.read().decode('utf-8')
                    lines = content.strip().split('\n')
                    
                    for line in lines:
                        if line.strip():
                            funding_data = self._parse_funding_csv_row(line, symbol)
                            if funding_data:
                                yield funding_data
                                
        except Exception as e:
            logger.error(f"Failed to parse funding ZIP file {zip_path}: {e}")
    
    async def _parse_csv_funding_file(
        self, 
        csv_path: str, 
        symbol: str
    ) -> AsyncGenerator[FundingRateData, None]:
        """Parse funding rate data from raw CSV file."""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                for row in reader:
                    if row:
                        funding_data = self._parse_funding_csv_row(','.join(row), symbol)
                        if funding_data:
                            yield funding_data
                            
        except Exception as e:
            logger.error(f"Failed to parse funding CSV file {csv_path}: {e}")
    
    def _parse_funding_csv_row(self, csv_row: str, symbol: str) -> Optional[FundingRateData]:
        """Parse a single funding rate CSV row."""
        try:
            # Binance funding rate CSV format:
            # [0] calc_time, [1] funding_rate, [2] mark_price
            
            parts = csv_row.strip().split(',')
            
            if len(parts) < 2:
                return None
            
            return FundingRateData(
                symbol=symbol,
                funding_time=datetime.fromtimestamp(int(parts[0]) / 1000),
                funding_rate=Decimal(parts[1]),
                mark_price=Decimal(parts[2]) if len(parts) > 2 and parts[2] else None
            )
            
        except Exception as e:
            logger.error(f"Failed to parse funding CSV row: {e}")
            return None