"""Simple registry for source adapters.

This module provides a tiny registry so tests and runtime code can discover
and obtain a configured adapter by name. The registry intentionally stores
callables that return adapters to allow lazy instantiation in tests.
"""

from __future__ import annotations

from collections.abc import Callable

from .adapter import DataSourceAdapter


class SourceRegistry:
    """Registry mapping source name -> adapter factory.

    Example:
        SourceRegistry.register("binance", lambda: BinanceAdapter())
        adapter = SourceRegistry.get("binance")
    """

    _registry: dict[str, Callable[[], DataSourceAdapter]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[[], DataSourceAdapter]) -> None:
        cls._registry[name] = factory

    @classmethod
    def get(cls, name: str) -> DataSourceAdapter:
        try:
            factory = cls._registry[name]
        except KeyError as exc:
            raise KeyError(f"No adapter registered for source {name!r}") from exc
        return factory()
