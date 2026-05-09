"""Prefect workflow definitions for binance-datatool pipelines.

Composes CLI commands into automated, observable workflows with
retry, logging, and lineage tracking.
"""

from __future__ import annotations

from pathlib import Path

from prefect import flow, task
from prefect.task_runners import ThreadPoolTaskRunner

from binance_datatool.common import TradeType
from binance_datatool.lineage import LineageTracker
from binance_datatool.workflow import (
    GapFillWorkflow,
    SinkWorkflow,
)
from binance_datatool.workflow.health_check import check_ducklake_anomalies

_DEFAULT_ARCHIVE_HOME = Path.home() / ".binance-datatool" / "archive"


# ── Individual Tasks ─────────────────────────────────────────────


def _cli(*args: str) -> list[str]:
    """Build a uv-native CLI command."""
    return ["uv", "run", "binance-datatool", *args]


@task(retries=2, retry_delay_seconds=10)
def download_symbol(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
) -> None:
    """Download archive data for a single symbol."""
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


@task(retries=1, retry_delay_seconds=5)
def verify_symbol(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
) -> None:
    """Verify checksums for a single symbol."""
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


@task(retries=1, retry_delay_seconds=5)
def refresh_metadata(
    trade_type: str,
    catalog_path: Path,
    archive_home: Path | None = None,
    from_api: bool = False,
) -> None:
    """Refresh venue and symbol metadata."""
    import subprocess

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    cmd = _cli(
        "refresh-metadata", trade_type, "--catalog", str(catalog_path), "--archive-home", str(home)
    )
    if from_api:
        cmd.append("--from-api")
    subprocess.run(cmd, check=True)


# ── Data Flows ───────────────────────────────────────────────────


@task
def detect_and_fill_gaps(
    trade_type: TradeType,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    lookback_days: int = 30,
    archive_home: Path | None = None,
) -> list[tuple[str, int, int]]:
    """Detect date gaps and fill via REST API."""
    import asyncio

    from binance_datatool.exchange import BinanceSpotRestClient

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    client = BinanceSpotRestClient()
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
    return result.gaps_detected


@task
def sink_to_ducklake(
    trade_type: TradeType,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> int:
    """Transform Bronze → Silver and sink to DuckLake."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    duckdb = catalog / "catalog.duckdb"

    tracker = LineageTracker()
    workflow = SinkWorkflow(
        archive_home=home,
        catalog_path=catalog,
        duckdb_path=duckdb,
        tracker=tracker,
    )
    stats = workflow.transform(
        trade_type=trade_type,
        data_type=DataType(data_type) if hasattr(DataType, data_type) else data_type,  # type: ignore  # noqa: F821
        symbols=[symbol],
        interval=interval,
    )
    return stats.row_count


@task
def run_health_check(
    trade_type: str,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> dict:
    """Run health check on DuckLake data and detect anomalies."""
    import duckdb

    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    duckdb_file = catalog / "catalog.duckdb"
    meta = catalog / "metadata.ducklake"

    con = duckdb.connect(str(duckdb_file))
    try:
        con.execute("LOAD ducklake")
        con.execute(
            f"ATTACH 'ducklake:{meta}' AS dl (DATA_PATH '{catalog}/data', AUTOMATIC_MIGRATION true)"
        )
        con.execute("USE dl")

        table = data_type.replace("-", "_")
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        report = check_ducklake_anomalies(con, table, symbol)
        return {
            "table": table,
            "row_count": count,
            "is_clean": report.is_clean,
            "null_prices": report.null_prices,
            "zero_volumes": report.zero_volumes,
            "duplicates": report.duplicate_timestamps,
            "gaps": len(report.date_gaps),
        }
    finally:
        con.close()


# ── Composed Flows ───────────────────────────────────────────────


@flow(
    name="Historical Data Pipeline",
    description="Download, verify, gap-fill, sink, and health-check market data",
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
) -> dict[str, any]:
    """Full historical data pipeline: download → verify → gap-fill → sink → health.

    Orchestrates archive download, integrity verification, gap filling
    via REST API, DuckLake-native ingestion, and health/anomaly check.
    """
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    results: dict[str, any] = {}
    sym_list = symbols or ["BTCUSDT"]

    for symbol in sym_list:
        print(f"Processing {symbol} ({trade_type}/{data_type}/{interval})")

        # 1. Download
        download_symbol(trade_type, symbol, data_type, interval, home)
        print(f"  Downloaded archive data for {symbol}")

        # 2. Verify
        verify_symbol(trade_type, symbol, data_type, interval, home)
        print(f"  Verified checksums for {symbol}")

        # 3. Gap fill
        gaps = detect_and_fill_gaps(
            TradeType(trade_type),
            symbol,
            data_type,
            interval,
            lookback_days,
            home,
        )
        print(f"  Filled {len(gaps)} gaps for {symbol}")

        # 4. Sink
        rows = sink_to_ducklake(
            TradeType(trade_type),
            symbol,
            data_type,
            interval,
            home,
            catalog,
        )
        print(f"  Sunk {rows} rows to DuckLake for {symbol}")

        # 5. Health check
        health = run_health_check(trade_type, symbol, data_type, interval, home, catalog)
        print(f"  Health: {health}")

        results[symbol] = {
            "symbol": symbol,
            "gaps_filled": len(gaps),
            "rows_sunk": rows,
            "healthy": health["is_clean"],
            "row_count": health["row_count"],
        }

    return results


@flow(
    name="Metadata Refresh",
    description="Refresh venue and symbol metadata from archive or API",
    log_prints=True,
)
def metadata_refresh(
    trade_type: str = "spot",
    catalog_path: Path | None = None,
    from_api: bool = False,
) -> None:
    """Refresh metadata tables (venues, symbols) for the catalog."""
    home = _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    refresh_metadata(trade_type, catalog, home, from_api)
    print(f"Metadata refreshed for {trade_type} → {catalog}")


@flow(
    name="Bulk Historical Backfill",
    description="Process multiple symbols in parallel for historical backfill",
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
    from binance_datatool.common import DataFrequency as _DF
    from binance_datatool.common import DataType as _DT
    from binance_datatool.common import TradeType as _TT

    if not symbols:
        from binance_datatool.archive.client import ArchiveClient
        from binance_datatool.workflow.list_symbols import ArchiveListSymbolsWorkflow

        client = ArchiveClient()
        workflow = ArchiveListSymbolsWorkflow(
            client=client,
            trade_type=_TT(trade_type),
            data_freq=_DF.daily,
            data_type=_DT(data_type),
        )
        import asyncio

        result = asyncio.run(workflow.run())
        symbols = [s.symbol for s in result.matched[:10]]  # limit to 10

    for symbol in symbols:
        historical_pipeline(
            trade_type=trade_type,
            symbols=[symbol],
            data_type=data_type,
            interval=interval,
            lookback_days=lookback_days,
        )
