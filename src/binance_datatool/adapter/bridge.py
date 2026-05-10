"""Adapter bridge to integrate DataSourceAdapter with existing workflows.

This module provides backward-compatible functions that wrap the new
DataSourceAdapter protocol to work with existing workflow code. This allows
gradual migration from ArchiveClient to the multi-source adapter framework.

Example:
    ```python
    # Get an adapter via source name
    adapter = get_adapter_for_source("binance")

    # Use it with existing workflow parameters
    symbols = await adapter.list_symbols("spot", "daily", "klines")
    ```
"""

from __future__ import annotations

from binance_datatool.source_registry import SourceRegistry


def get_adapter_for_source(source: str):
    """Get a data source adapter by name.

    Args:
        source: Source name (e.g., "binance", "coinbase").

    Returns:
        DataSourceAdapter instance for the requested source.

    Raises:
        KeyError: If source is not registered.
    """
    return SourceRegistry.get(source)


def list_available_sources() -> list[str]:
    """List all registered data sources.

    Returns:
        List of source names (e.g., ["binance", "coinbase"]).
    """
    # Access the registry's internal dict to get all keys
    # This is a temporary solution; ideally SourceRegistry would have a list() method
    return list(SourceRegistry._registry.keys())


__all__ = ["get_adapter_for_source", "list_available_sources"]
