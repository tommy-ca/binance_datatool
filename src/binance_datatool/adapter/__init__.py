"""Adapter protocol and small helper types for external data sources.

This module contains a minimal, intentionally-small protocol to make it easy
to write and test source adapters. Keep the surface area tiny: adapters should
only implement the small Protocol below so tests can stub them easily.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(slots=True)
class FileMetadata:
    """Metadata for a file on a remote data source."""

    key: str
    url: str
    size: int
    last_modified: datetime
    checksum: str | None = None


class DataSourceAdapter(Protocol):
    """Minimal protocol that source adapters should implement.

    The protocol is intentionally small to keep tests easy to write and to
    allow adapters to wrap existing client code (for example, wrapping
    :class:`binance_datatool.archive.ArchiveClient`).
    """

    @property
    def source_name(self) -> str:  # human readable id, e.g. "binance"
        ...

    async def list_symbols(self, market_type: str, partition: str, data_type: str) -> list[str]:
        """Return available symbols for the requested parameters."""

    async def list_files(
        self,
        market_type: str,
        partition: str,
        data_type: str,
        symbol: str,
        interval: str | None = None,
    ) -> list[FileMetadata]:
        """Return files available for one symbol.

        Implementations should raise exceptions from underlying HTTP
        libraries unchanged so callers can surface raw error messages in
        workflows and logs.
        """

    async def fetch_file(self, url: str, destination_path: str) -> None:
        """Fetch a single file and write it to destination_path.

        This method may be implemented synchronously if the adapter uses
        blocking I/O, but most adapters should prefer async implementations.
        """

    def parse_symbol(self, raw_symbol: str) -> dict | None:
        """Parse raw symbol string into a lightweight metadata dict.

        Return a dict containing at minimum `symbol`, `base_asset`, `quote_asset`.
        Return ``None`` when the symbol cannot be parsed by this adapter.
        """


__all__ = ["DataSourceAdapter", "FileMetadata", "BinanceAdapter"]

# Import adapters to register them with SourceRegistry
from binance_datatool.adapter.binance import BinanceAdapter  # noqa: F401
from binance_datatool.adapter.registry import *  # noqa: F401,F403
