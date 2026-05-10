"""Prefect workflow definitions for binance-datatool pipelines.

Composes workflow classes directly — no subprocess CLI wrappers.
CLI commands are thin wrappers over these same workflow classes.

Design patterns (dataskew.io/blog/data-pipeline-design-patterns):
- Idempotency: DROP TABLE IF EXISTS + CREATE TABLE AS SELECT
- Backfilling: parameterized execution_date / lookback_days
- Schema evolution: DuckLake ALTER TABLE + centralized TABLE_DEFS
- Dead letter queue: dlq table in DuckLake for failed records
- Retry: exponential backoff with jitter
- At-least-once + idempotent operations (no exactly-once needed)
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
    HealthCheckWorkflow,
    MetadataWorkflow,
    SinkWorkflow,
)
from binance_datatool.workflow.health_check import check_ducklake_anomalies

_DEFAULT_ARCHIVE_HOME = Path.home() / ".binance-datatool" / "archive"

# Retry with exponential backoff and jitter
# Prefect 3.x: retry_delay_seconds + retry_jitter_factor
# Pattern 5: https://dataskew.io/blog/data-pipeline-design-patterns
_RETRY_CONFIG = {"retries": 3, "retry_delay_seconds": 10, "retry_jitter_factor": 0.2}
_RETRY_LIGHT = {"retries": 2, "retry_delay_seconds": 10, "retry_jitter_factor": 0.2}

_REST_CLIENTS = {
    "spot": BinanceSpotRestClient,
    "um": BinanceUmRestClient,
    "cm": BinanceCmRestClient,
}


# ── Dead Letter Queue ───────────────────────────────────────────


_log = __import__("logging").getLogger(__name__)


def _route_to_dlq(catalog: Path, symbol: str, data_type: str, errors: list[str]) -> None:
    """Route failed records to DuckLake DLQ table (Pattern 4)."""
    from datetime import datetime

    import duckdb

    meta = catalog / "metadata.ducklake"
    if not meta.exists():
        return
    try:
        con = duckdb.connect(str(catalog / "catalog.duckdb"))
        con.execute("LOAD ducklake")
        con.execute(
            f"ATTACH 'ducklake:{meta}' AS dl (DATA_PATH '{catalog}/data', AUTOMATIC_MIGRATION true)"
        )
        con.execute("USE dl")
        con.execute(
            "CREATE TABLE IF NOT EXISTS dlq ("
            "symbol VARCHAR, data_type VARCHAR, error VARCHAR, "
            "ingested_at BIGINT, source VARCHAR"
            ")"
        )
        now = int(datetime.now().timestamp() * 1000)
        for err in errors:
            con.execute(
                "INSERT INTO dlq VALUES (?, ?, ?, ?, ?)",
                [symbol, data_type, err, now, "sink_silver"],
            )
        cnt = con.execute("SELECT COUNT(*) FROM dlq").fetchone()[0]
        _log.info("DLQ: %d total failures for %s/%s", cnt, symbol, data_type)
        con.close()
    except Exception as e:
        _log.warning("DLQ route failed: %s", e)


# ── Tasks ───────────────────────────────────────────────────────


@task(**_RETRY_CONFIG)
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


@task(**_RETRY_CONFIG)
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


@task(**_RETRY_LIGHT)
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


@task(**_RETRY_LIGHT)
def sink_silver(
    trade_type: TradeType,
    symbol: str,
    data_type: str = "klines",
    interval: str = "1h",
    lookback_days: int = 30,
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> int:
    """Sink to DuckLake via SinkWorkflow. Backfillable by design."""
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
    # Route transform errors to DuckLake DLQ table (Pattern 4)
    if stats.errors:
        _route_to_dlq(catalog, symbol, data_type, stats.errors)
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
    """Full historical data pipeline: metadata → download → verify → gap-fill → sink."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    results: dict[str, Any] = {}

    # Step 0: Refresh metadata first — venues + symbols available for downstream
    refresh_metadata_flow(trade_type=trade_type, catalog_path=catalog)
    print(f"  Metadata refreshed for {trade_type}")

    for symbol in symbols or ["BTCUSDT"]:
        print(f"Processing {symbol} ({trade_type}/{data_type}/{interval})")
        tt = TradeType(trade_type)
        iv = interval if data_type == "klines" else None
        download_archive(trade_type, symbol, data_type, iv, home)
        verify_archive(trade_type, symbol, data_type, iv, home)
        gaps = fill_gaps(tt, symbol, data_type, iv, lookback_days, home)
        rows = sink_silver(tt, symbol, data_type, iv, lookback_days, home, catalog)
        results[symbol] = {"gaps_filled": len(gaps), "rows_sunk": rows}
        print(f"  {symbol}: {len(gaps)} gaps, {rows} rows")

    return results


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
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> None:
    """Backfill multiple symbols concurrently (backfillable by design)."""
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
            archive_home=archive_home,
            catalog_path=catalog_path,
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
    duckdb_path: str | None = None,
) -> int:
    """Refresh venue/symbol metadata. Wraps MetadataWorkflow with Prefect."""
    home = _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    client = ArchiveClient()
    wf = MetadataWorkflow(
        archive_client=client,
        catalog_path=catalog,
        source_label="api" if from_api else "archive",
        duckdb_path=Path(duckdb_path) if duckdb_path else catalog / "catalog.duckdb",
    )
    wf.save_venues(wf.refresh_venues())
    syms = asyncio.run(wf.refresh_symbols(TradeType(trade_type)))
    wf.save_symbols(syms)
    return len(syms)


@flow(name="Health Check", log_prints=True)
def health_flow(
    trade_type: str = "spot",
    symbol: str = "BTCUSDT",
    data_type: str = "klines",
    interval: str = "1h",
    archive_home: Path | None = None,
    catalog_path: Path | None = None,
) -> dict:
    """Run health check and anomaly detection. Wraps HealthCheckWorkflow."""
    home = archive_home or _DEFAULT_ARCHIVE_HOME
    catalog = catalog_path or home.parent / "lake"
    db_file = catalog / "catalog.duckdb"

    from binance_datatool.common import DataFrequency, DataType
    from binance_datatool.common import TradeType as _TT

    file_health = HealthCheckWorkflow(
        trade_type=_TT(trade_type),
        data_freq=DataFrequency.daily,
        data_type=DataType(data_type),
        symbols=[symbol],
        archive_home=home,
        interval=interval,
    )
    report = file_health.run()

    # DuckLake anomaly detection
    import duckdb

    con = duckdb.connect(str(db_file))
    try:
        con.execute("LOAD ducklake")
        con.execute(
            f"ATTACH 'ducklake:{catalog}/metadata.ducklake' AS dl "
            f"(DATA_PATH '{catalog}/data', AUTOMATIC_MIGRATION true)"
        )
        con.execute("USE dl")
        anomalies = check_ducklake_anomalies(con, data_type.replace("-", "_"), symbol)
    finally:
        con.close()

    result = {
        "healthy": report.healthy_symbols == report.total_symbols,
        "missing_dates": report.total_missing_dates,
        "anomalies_clean": anomalies.is_clean,
        "null_prices": anomalies.null_prices,
    }
    print(f"Health: {result}")
    return result


# ── Deployment Entry Points ─────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # `python -m binance_datatool.workflow.prefect_flows serve`
        historical_pipeline.serve(name="daily-backfill", cron="0 6 * * *")
        refresh_metadata_flow.serve(name="hourly-metadata", cron="0 * * * *")
    else:
        historical_pipeline()
