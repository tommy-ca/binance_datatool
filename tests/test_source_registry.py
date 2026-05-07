from __future__ import annotations

import asyncio

from binance_datatool.adapter import DataSourceAdapter
from binance_datatool.source_registry import SourceRegistry


class FakeAdapter:
    """Minimal fake adapter that implements the DataSourceAdapter protocol."""

    @property
    def source_name(self) -> str:
        return "fake"

    async def list_symbols(self, market_type: str, partition: str, data_type: str) -> list[str]:
        return ["AAA", "BBB"]

    async def list_files(self, market_type: str, partition: str, data_type: str, symbol: str, interval: str | None = None):
        # Return an empty list to keep this fake tiny
        return []

    async def fetch_file(self, url: str, destination_path: str) -> None:
        return None

    def parse_symbol(self, raw_symbol: str) -> dict | None:
        return {"symbol": raw_symbol, "base_asset": "EX", "quote_asset": "USD"}


def test_register_and_get_adapter():
    SourceRegistry.register("fake", lambda: FakeAdapter())
    adapter = SourceRegistry.get("fake")
    assert adapter.source_name == "fake"


def test_fake_adapter_list_symbols():
    adapter = FakeAdapter()
    symbols = asyncio.run(adapter.list_symbols("spot", "daily", "klines"))
    assert symbols == ["AAA", "BBB"]
