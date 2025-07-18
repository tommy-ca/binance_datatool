"""
Crypto Data Lakehouse - A scalable data platform for cryptocurrency market data.

This package provides a comprehensive solution for ingesting, processing, and serving
historical and real-time cryptocurrency market data using modern data lakehouse patterns.

Key Features:
- Multi-source data ingestion (Binance AWS S3, REST APIs)
- Layered storage architecture (Bronze/Silver/Gold zones)
- Workflow orchestration with Prefect
- Modern Python stack with containerized processing
- Query engines (DuckDB, Trino) for analytics
"""

__version__ = "2.0.0"
__author__ = "Crypto Data Lakehouse Team"

from .core.models import DataType, Exchange, Interval
from .core.config import Settings

__all__ = ["DataType", "Exchange", "Interval", "Settings"]