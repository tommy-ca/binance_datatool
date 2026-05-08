"""Populate venue and symbol metadata tables from archive and SDK API."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl
from loguru import logger

from binance_datatool.common import TradeType
from binance_datatool.common.types import SymbolMetadata, VenueMetadata
from binance_datatool.workflow.list_symbols import ArchiveListSymbolsWorkflow

if TYPE_CHECKING:
    from binance_datatool.archive.client import ArchiveClient
    from binance_datatool.common import DataFrequency, DataType


class MetadataWorkflow:
    """Populate venue and symbol metadata tables from archive and SDK API."""

    EXCHANGE = "binance"
    VENUES = [
        VenueMetadata(
            venue="binance_spot", trade_type="spot", exchange="binance",
            source="archive", symbol_count=0, data_types=["klines", "aggTrades", "trades"],
            fetched_at=0,
        ),
        VenueMetadata(
            venue="binance_um", trade_type="um", exchange="binance",
            source="archive", symbol_count=0, data_types=["klines", "aggTrades", "fundingRate"],
            fetched_at=0,
        ),
        VenueMetadata(
            venue="binance_cm", trade_type="cm", exchange="binance",
            source="archive", symbol_count=0, data_types=["klines", "aggTrades", "fundingRate"],
            fetched_at=0,
        ),
    ]

    def __init__(
        self,
        archive_client: ArchiveClient,
        catalog_path: Path,
        source_label: str = "archive",
    ) -> None:
        self._archive_client = archive_client
        self._catalog_path = Path(catalog_path)
        self._source = source_label

    def refresh_venues(self) -> list[VenueMetadata]:
        """List all venues available in the archive."""
        now = int(time.time() * 1000)
        venues = []
        for v in self.VENUES:
            v.fetched_at = now
            venues.append(v)
        return venues

    async def refresh_symbols(
        self,
        trade_type: TradeType,
        data_freq: DataFrequency | None = None,
        data_type: DataType | None = None,
    ) -> list[SymbolMetadata]:
        """List symbols for a trade type from the archive."""
        from binance_datatool.common import DataFrequency as DF
        from binance_datatool.common import DataType as DT

        freq = data_freq or DF.daily
        dtype = data_type or DT.klines
        now = int(time.time() * 1000)

        workflow = ArchiveListSymbolsWorkflow(
            client=self._archive_client,
            trade_type=trade_type,
            data_freq=freq,
            data_type=dtype,
        )
        result = await workflow.run()

        symbols = []
        for info in result.matched:
            symbol = SymbolMetadata(
                symbol=info.symbol,
                trade_type=trade_type.value,
                exchange=self.EXCHANGE,
                base_asset=info.base_asset,
                quote_asset=info.quote_asset,
                source=self._source,
                fetched_at=now,
            )
            if hasattr(info, "contract_type") and info.contract_type:
                symbol.contract_type = info.contract_type.value
            if hasattr(info, "is_leverage"):
                symbol.is_leverage = info.is_leverage
            if hasattr(info, "is_stable_pair"):
                symbol.is_stable_pair = info.is_stable_pair
            symbols.append(symbol)
        return symbols

    async def refresh_symbols_from_api(
        self,
        trade_type: TradeType,
        symbols: list[str] | None = None,
    ) -> list[SymbolMetadata]:
        """Fetch symbol metadata from the Binance REST API via SDK."""
        from binance_datatool.exchange import (
            BinanceCmRestClient,
            BinanceSpotRestClient,
            BinanceUmRestClient,
        )

        now = int(time.time() * 1000)
        result: list[SymbolMetadata] = []

        match trade_type:
            case TradeType.spot:
                client = BinanceSpotRestClient()
            case TradeType.um:
                client = BinanceUmRestClient()
            case TradeType.cm:
                client = BinanceCmRestClient()

        api = client._client.rest_api
        resp = api.exchange_info() if hasattr(api, "exchange_info") else api.exchange_information()
        data = resp.data()

        # Binance SDK returns exchange_info with list of symbols
        symbol_list = getattr(data, "symbols", []) if not isinstance(data, list) else data

        for s in symbol_list:
            sym_name = s.get("symbol", "") if isinstance(s, dict) else str(s)
            if symbols and sym_name not in symbols:
                continue
            result.append(SymbolMetadata(
                symbol=sym_name,
                trade_type=trade_type.value,
                exchange=self.EXCHANGE,
                base_asset=(s.get("baseAsset", "") if isinstance(s, dict) else ""),
                quote_asset=(s.get("quoteAsset", "") if isinstance(s, dict) else ""),
                contract_type=(s.get("contractType", "") if isinstance(s, dict) else None),
                status=(s.get("status", "trading") if isinstance(s, dict) else "trading"),
                source="api",
                fetched_at=now,
            ))
        return result

    def save_venues(self, venues: list[VenueMetadata]) -> Path:
        """Save venue metadata to Parquet."""
        rows = [
            {
                "venue": v.venue,
                "trade_type": v.trade_type,
                "exchange": v.exchange,
                "source": v.source,
                "symbol_count": v.symbol_count,
                "data_types": ",".join(v.data_types),
                "fetched_at": v.fetched_at,
            }
            for v in venues
        ]
        df = pl.DataFrame(rows)
        out = self._catalog_path / "venues.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out)
        logger.info("Saved {} venues to {}", len(venues), out)
        return out

    def save_symbols(self, symbols: list[SymbolMetadata]) -> Path:
        """Save symbol metadata to Parquet."""
        rows = [
            {
                "symbol": s.symbol,
                "trade_type": s.trade_type,
                "exchange": s.exchange,
                "base_asset": s.base_asset,
                "quote_asset": s.quote_asset,
                "contract_type": s.contract_type or "",
                "is_leverage": s.is_leverage,
                "is_stable_pair": s.is_stable_pair,
                "source": s.source,
                "status": s.status,
                "fetched_at": s.fetched_at,
            }
            for s in symbols
        ]
        df = pl.DataFrame(rows)
        out = self._catalog_path / "symbols.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out)
        logger.info("Saved {} symbols to {}", len(symbols), out)
        return out
