"""Adapter registration for built-in and extensible data sources.

This module registers all available adapters with the SourceRegistry,
making them discoverable by CLI commands and workflows.

To add a new adapter:
    1. Create a new adapter class implementing DataSourceAdapter protocol
    2. Import it here
    3. Register it with SourceRegistry
    4. Update __all__ to export the adapter class
"""

from __future__ import annotations

from binance_datatool.adapter.binance import BinanceAdapter
from binance_datatool.source_registry import SourceRegistry

# Register adapters
SourceRegistry.register("binance", lambda: BinanceAdapter())

__all__ = ["BinanceAdapter"]
