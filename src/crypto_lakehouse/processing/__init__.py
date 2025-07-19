"""
Data processing module for cryptocurrency lakehouse platform.

This module provides specialized processors for transforming raw data from the Bronze zone
into cleaned, validated, and enriched data in the Silver zone.

Available Processors:
- BaseProcessor: Abstract base class for all data processors
- KlineProcessor: Processes candlestick (kline) data
- FundingRateProcessor: Processes funding rate data
- EnrichmentProcessor: Adds derived metrics and indicators
"""

from .base import BaseProcessor
from .kline_processor import KlineProcessor
from .funding_processor import FundingRateProcessor
from .enrichment import EnrichmentProcessor

__all__ = [
    "BaseProcessor",
    "KlineProcessor", 
    "FundingRateProcessor",
    "EnrichmentProcessor"
]