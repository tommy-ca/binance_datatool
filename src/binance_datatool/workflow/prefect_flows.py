"""Prefect workflow definitions for binance-datatool pipelines.

Uses Prefect-native assets and materialization for observable,
cacheable, versioned data pipelines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prefect import flow, task
from prefect.assets import Asset, materialize
from prefect.task_runners import ThreadPoolTaskRunner

from binance_datatool.common import TradeType
from binance_datatool.lineage import LineageTracker
from binance_datatool.workflow import GapFillWorkflow, SinkWorkflow

_DEFAULT_ARCHIVE_HOME = Path.home() / ".binance-datatool" / "archive"

# ── Asset Definitions ────────────────────────────────────────────

ARCHIVE_DATA = Asset(name="archive-data", description="Raw archive ZIPs and CSVs")
VERIFIED_DATA = Asset(name="verified-data", description="Checksum-verified archive files")
FILLED_DATA = Asset(name="filled-data", description="Gap-filled CSV data from REST API")
SILVER_DATA = Asset(name="silver-data", description="Normalized Silver layer in DuckLake")
LINEAGE_EVENTS = Asset(name="lineage-events", description="Data provenance lineage")
VENUE_METADATA = Asset(name="venue-metadata", description="Venue catalog")
SYMBOL_METADATA = Asset(name="symbol-metadata", description="Symbol catalog")


# ── CLI Helpers ──────────────────────────────────────────────────


def _cli(*args: str) -> list[str]:
    """Build a uv-native CLI command."""
    return ["uv", "run", "binance-datatool", *args]


# ── Tasks with Asset Materialization ─────────────────────────────


@task(retries=2, retry_delay_seconds=10)
def download_archive(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
) -> Path:
    """Download archive data and materialize the ARCHIVE_DATA asset."""
    import subprocess

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    cmd = _cli(
        "download",
        trade_type,
        "--type",
        data_type,
        "--freq",
        "daily",
        symbol,
        "--archive-home",
        str(home),
    )
    if interval and data_type in ("klines",):
        cmd.extend(["--interval", interval])
    subprocess.run(cmd, check=True)
    materialize(ARCHIVE_DATA)
    return home


@task(retries=1, retry_delay_seconds=5)
def verify_archive(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
) -> Path:
    """Verify checksums and materialize the VERIFIED_DATA asset."""
    import subprocess

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    cmd = _cli(
        "verify",
        trade_type,
        "--type",
        data_type,
        "--freq",
        "daily",
        symbol,
        "--archive-home",
        str(home),
    )
    if interval:
        cmd.extend(["--interval", interval])
    subprocess.run(cmd, check=True)
    materialize(VERIFIED_DATA)
    return home


@task(retries=1, retry_delay_seconds=5)
def fill_gaps(
    trade_type: TradeType,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    lookback_days: int = 30,
    archive_home: Path | None = None,
) -> list[tuple[str, int, int]]:
    """Detect and fill gaps, materialize FILLED_DATA asset."""
    import asyncio

    from binance_datatool.exchange import (
        BinanceCmRestClient,
        BinanceSpotRestClient,
        BinanceUmRestClient,
    )

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    client_map = {
        "spot": BinanceSpotRestClient,
        "um": BinanceUmRestClient,
        "cm": BinanceCmRestClient,
    }
    Client = client_map.get(trade_type.value, BinanceSpotRestClient)
    client = Client()
    tracker = LineageTracker()
    workflow = GapFillWorkflow(
        exchange_client=client,
        archive_home=home,
        symbols=[symbol],
        data_type=data_type,
        interval=interval,
        tracker=tracker,
        lookback_days=lookback_days,
    )
    result = asyncio.run(workflow.run(detect_gaps=True))
    materialize(FILLED_DATA)
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
    """Sink to DuckLake, materialize SILVER_DATA and LINEAGE_EVENTS."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    duckdb = catalog / "catalog.duckdb"

    tracker = LineageTracker()
    workflow = SinkWorkflow(
        archive_home=home, catalog_path=catalog, duckdb_path=duckdb, tracker=tracker
    )
    stats = workflow.transform(
        trade_type=trade_type,
        data_type=data_type,
        symbols=[symbol],
        interval=interval,
    )
    materialize(SILVER_DATA)
    materialize(LINEAGE_EVENTS)
    return stats.row_count


@task(retries=1, retry_delay_seconds=5)
def refresh_catalog(
    trade_type: str,
    catalog_path: Path,
    archive_home: Path | None = None,
    from_api: bool = False,
) -> None:
    """Refresh metadata, materialize VENUE_METADATA and SYMBOL_METADATA."""
    import subprocess

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    cmd = _cli(
        "refresh-metadata", trade_type, "--catalog", str(catalog_path), "--archive-home", str(home)
    )
    if from_api:
        cmd.append("--from-api")
    subprocess.run(cmd, check=True)
    materialize(VENUE_METADATA)
    materialize(SYMBOL_METADATA)


# ── Composed Flows ───────────────────────────────────────────────


@flow(
    name="Historical Data Pipeline",
    description="Download → verify → gap-fill → sink → health",
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
    """Full historical pipeline with Prefect-native asset materialization."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    results: dict[str, Any] = {}

    for symbol in symbols or ["BTCUSDT"]:
        print(f"Processing {symbol} ({trade_type}/{data_type}/{interval})")

        download_archive(trade_type, symbol, data_type, interval, home)
        verify_archive(trade_type, symbol, data_type, interval, home)
        gaps = fill_gaps(TradeType(trade_type), symbol, data_type, interval, lookback_days, home)
        rows = sink_silver(TradeType(trade_type), symbol, data_type, interval, home, catalog)

        results[symbol] = {
            "gaps_filled": len(gaps),
            "rows_sunk": rows,
        }
        print(f"  {symbol}: {len(gaps)} gaps, {rows} rows sunk")

    return results


@flow(name="Metadata Refresh", log_prints=True)
def metadata_refresh(
    trade_type: str = "spot",
    catalog_path: Path | None = None,
    from_api: bool = False,
) -> None:
    """Refresh venue and symbol metadata."""
    home = _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    refresh_catalog(trade_type, catalog, home, from_api)
    print(f"Metadata refreshed for {trade_type} → {catalog}")


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
    from binance_datatool.common import DataFrequency, DataType

    if not symbols:
        from binance_datatool.archive.client import ArchiveClient
        from binance_datatool.workflow.list_symbols import ArchiveListSymbolsWorkflow

        client = ArchiveClient()
        workflow = ArchiveListSymbolsWorkflow(
            client=client,
            trade_type=TradeType(trade_type),
            data_freq=DataFrequency.daily,
            data_type=DataType(data_type),
        )
        import asyncio

        result = asyncio.run(workflow.run())
        symbols = [s.symbol for s in result.matched[:10]]

    for symbol in symbols:
        historical_pipeline(
            trade_type=trade_type,
            symbols=[symbol],
            data_type=data_type,
            interval=interval,
            lookback_days=lookback_days,
        )
