"""Prefect workflow definitions for binance-datatool pipelines.

Composes workflow classes directly — no subprocess CLI wrappers.
CLI commands are thin wrappers over these same workflow classes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from prefect import flow, task
from prefect.task_runners import ThreadPoolTaskRunner

from binance_datatool.archive.client import ArchiveClient
from binance_datatool.common import DataFrequency, DataType, TradeType
from binance_datatool.exchange import (
    BinanceCmRestClient,
    BinanceSpotRestClient,
    BinanceUmRestClient,
)
from binance_datatool.lineage import LineageTracker
from binance_datatool.workflow import (
    ArchiveDownloadWorkflow,
    ArchiveListSymbolsWorkflow,
    ArchiveVerifyWorkflow,
    GapFillWorkflow,
    MetadataWorkflow,
    SinkWorkflow,
)

_DEFAULT_ARCHIVE_HOME = Path.home() / ".binance-datatool" / "archive"

_REST_CLIENTS = {
    "spot": BinanceSpotRestClient,
    "um": BinanceUmRestClient,
    "cm": BinanceCmRestClient,
}


# ── Tasks ───────────────────────────────────────────────────────


@task(retries=2, retry_delay_seconds=10)
def download_archive(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str | None = "1h",
    archive_home: Path | None = None,
) -> int:
    """Download archive data via ArchiveDownloadWorkflow."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    dt = DataType(data_type) if data_type in DataType._value2member_map_ else DataType.klines
    wf = ArchiveDownloadWorkflow(
        trade_type=TradeType(trade_type),
        data_freq=DataFrequency.daily,
        data_type=dt,
        symbols=[symbol],
        archive_home=home,
        interval=interval,
    )
    result = wf.run()
    return len(result.to_download) if hasattr(result, "to_download") else 0


@task(retries=1, retry_delay_seconds=5)
def verify_archive(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
) -> int:
    """Verify checksums via ArchiveVerifyWorkflow."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    dt = DataType(data_type) if data_type in DataType._value2member_map_ else DataType.klines
    wf = ArchiveVerifyWorkflow(
        trade_type=TradeType(trade_type),
        data_freq=DataFrequency.daily,
        data_type=dt,
        symbols=[symbol],
        archive_home=home,
        interval=interval,
    )
    result = wf.run()
    return result.verified if hasattr(result, "verified") else 0


@task(retries=1, retry_delay_seconds=5)
def fill_gaps(
    trade_type: TradeType,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    lookback_days: int = 30,
    archive_home: Path | None = None,
) -> list[tuple[str, int, int]]:
    """Detect and fill gaps via GapFillWorkflow."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    Client = _REST_CLIENTS.get(trade_type.value, BinanceSpotRestClient)
    workflow = GapFillWorkflow(
        exchange_client=Client(),
        archive_home=home,
        symbols=[symbol],
        data_type=data_type,
        interval=interval,
        tracker=LineageTracker(),
        lookback_days=lookback_days,
    )
    result = asyncio.run(workflow.run(detect_gaps=True))
    return result.gaps_detected


@task(retries=1, retry_delay_seconds=5)
def sink_silver(
    trade_type: TradeType,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> int:
    """Sink to DuckLake via SinkWorkflow."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    catalog.mkdir(parents=True, exist_ok=True)
    (catalog / "data").mkdir(parents=True, exist_ok=True)
    dt = DataType(data_type) if data_type in DataType._value2member_map_ else DataType.klines
    workflow = SinkWorkflow(
        archive_home=home,
        catalog_path=catalog,
        duckdb_path=catalog / "catalog.duckdb",
        tracker=LineageTracker(),
    )
    stats = workflow.transform(
        trade_type=TradeType(trade_type),
        data_type=dt,
        symbols=[symbol],
        interval=interval,
    )
    return stats.row_count


# ── Composed Flows ───────────────────────────────────────────────


@flow(
    name="Historical Data Pipeline",
    description="Download → verify → gap-fill → sink",
    log_prints=True,
)
def historical_pipeline(
    trade_type: str = "spot",
    symbols: list[str] | None = None,
    data_type: str = "klines",
    interval: str = "1h",
    lookback_days: int = 30,
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Full historical data pipeline composed from workflow classes."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    results: dict[str, Any] = {}

    for symbol in symbols or ["BTCUSDT"]:
        print(f"Processing {symbol} ({trade_type}/{data_type}/{interval})")
        tt = TradeType(trade_type)
        iv = interval if data_type == "klines" else None
        download_archive(trade_type, symbol, data_type, iv, home)
        verify_archive(trade_type, symbol, data_type, iv, home)
        gaps = fill_gaps(tt, symbol, data_type, iv, lookback_days, home)
        rows = sink_silver(tt, symbol, data_type, iv, home, catalog)
        results[symbol] = {"gaps_filled": len(gaps), "rows_sunk": rows}
        print(f"  {symbol}: {len(gaps)} gaps, {rows} rows")

    return results


@flow(name="Metadata Refresh", log_prints=True)
def metadata_refresh(
    trade_type: str = "spot",
    catalog_path: Path | None = None,
    from_api: bool = False,
) -> None:
    """Refresh venue and symbol metadata via MetadataWorkflow."""
    home = _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    client = ArchiveClient()
    wf = MetadataWorkflow(
        archive_client=client, catalog_path=catalog, source_label="api" if from_api else "archive"
    )
    wf.save_venues(wf.refresh_venues())
    symbols = asyncio.run(wf.refresh_symbols(TradeType(trade_type)))
    wf.save_symbols(symbols)
    print(f"Metadata: {len(symbols)} symbols saved to {catalog}")


@flow(
    name="Bulk Historical Backfill",
    log_prints=True,
    task_runner=ThreadPoolTaskRunner(max_workers=4),
)
def bulk_backfill(
    trade_type: str = "spot",
    symbols: list[str] | None = None,
    data_type: str = "klines",
    interval: str = "1h",
    lookback_days: int = 30,
) -> None:
    """Backfill multiple symbols concurrently."""
    if not symbols:
        client = ArchiveClient()
        wf = ArchiveListSymbolsWorkflow(
            client=client,
            trade_type=TradeType(trade_type),
            data_freq=DataFrequency.daily,
            data_type=DataType(data_type),
        )
        result = asyncio.run(wf.run())
        symbols = [s.symbol for s in result.matched[:10]]

    for symbol in symbols:
        historical_pipeline(
            trade_type=trade_type,
            symbols=[symbol],
            data_type=data_type,
            interval=interval,
            lookback_days=lookback_days,
        )


# ── Standalone Flows (callable from CLI) ────────────────────────


@flow(name="Download", log_prints=True)
def download_flow(
    trade_type: str,
    symbols: list[str],
    data_type: str = "klines",
    interval: str | None = None,
    archive_home: Path | None = None,
) -> int:
    """Download archive data. Wraps ArchiveDownloadWorkflow with Prefect."""
    total = 0
    for sym in symbols:
        total += download_archive(trade_type, sym, data_type, interval, archive_home)
    return total


@flow(name="Verify", log_prints=True)
def verify_flow(
    trade_type: str,
    symbols: list[str],
    data_type: str = "klines",
    interval: str | None = None,
    archive_home: Path | None = None,
) -> int:
    """Verify checksums. Wraps ArchiveVerifyWorkflow with Prefect."""
    total = 0
    for sym in symbols:
        total += verify_archive(trade_type, sym, data_type, interval, archive_home)
    return total


@flow(name="Gap Fill", log_prints=True)
def gap_fill_flow(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str | None = None,
    lookback_days: int = 30,
    archive_home: Path | None = None,
) -> int:
    """Auto-detect and fill gaps. Wraps GapFillWorkflow with Prefect."""
    tt = TradeType(trade_type)
    gaps = fill_gaps(tt, symbol, data_type, interval, lookback_days, archive_home)
    return len(gaps)


@flow(name="Sink", log_prints=True)
def sink_flow(
    trade_type: str,
    symbols: list[str],
    data_type: str = "klines",
    interval: str | None = None,
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> int:
    """Sink to DuckLake. Wraps SinkWorkflow with Prefect."""
    tt = TradeType(trade_type)
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    total = 0
    for sym in symbols:
        total += sink_silver(tt, sym, data_type, interval, home, catalog)
    return total


@flow(name="Refresh Metadata", log_prints=True)
def refresh_metadata_flow(
    trade_type: str = "spot",
    catalog_path: Path | None = None,
    from_api: bool = False,
) -> int:
    """Refresh venue/symbol metadata. Wraps MetadataWorkflow with Prefect."""
    home = _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    client = ArchiveClient()
    wf = MetadataWorkflow(
        archive_client=client, catalog_path=catalog, source_label="api" if from_api else "archive"
    )
    wf.save_venues(wf.refresh_venues())
    syms = asyncio.run(wf.refresh_symbols(TradeType(trade_type)))
    wf.save_symbols(syms)
    return len(syms)
