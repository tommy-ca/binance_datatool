"""Utility functions for crypto lakehouse operations."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_timestamp() -> str:
    """Get current timestamp as string."""
    return datetime.now().isoformat()


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def create_directory_structure(base_dir: Path, market: str, partition: str, 
                              data_type: str, symbol: str, 
                              interval: Optional[str] = None) -> Path:
    """Create directory structure following Binance schema."""
    if interval and data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
        dir_path = base_dir / market / partition / data_type / symbol / interval
    else:
        dir_path = base_dir / market / partition / data_type / symbol
    
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path