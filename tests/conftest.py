"""Shared test fixtures and pytest configuration."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from binance_datatool.archive import ArchiveFile

if TYPE_CHECKING:
    from pathlib import Path


# ── Fake Archive Client ───────────────────────────────────────


class FakeArchiveClient:
    """Programmable stub for ArchiveClient-based tests."""

    def __init__(
        self,
        *,
        symbols: list[str] | None = None,
        files_by_symbol: dict[str, list[ArchiveFile]] | None = None,
        errors_by_symbol: dict[str, Exception] | None = None,
    ) -> None:
        self._symbols = symbols or []
        self._files = files_by_symbol or {}
        self._errors = errors_by_symbol or {}
        self.last_list_symbol_files_batch_progress_bar: bool | None = None

    async def list_symbols(self, trade_type, data_freq, data_type) -> list[str]:
        return list(self._symbols)

    async def list_symbol_files(
        self,
        trade_type,
        data_freq,
        data_type,
        symbol,
        interval=None,
        *,
        session=None,
    ) -> list[ArchiveFile]:
        del trade_type, data_freq, data_type, interval, session
        if symbol in self._errors:
            raise self._errors[symbol]
        return list(self._files.get(symbol, []))

    async def list_symbol_files_batch(
        self,
        trade_type,
        data_freq,
        data_type,
        symbols,
        interval=None,
        *,
        progress_bar: bool = False,
    ) -> dict[str, tuple[list[ArchiveFile], str | None]]:
        del trade_type, data_freq, data_type, interval
        self.last_list_symbol_files_batch_progress_bar = progress_bar
        return {
            symbol: (
                [],
                str(self._errors[symbol]),
            )
            if symbol in self._errors
            else (
                list(self._files.get(symbol, [])),
                None,
            )
            for symbol in symbols
        }


# ── Sample Archive Files ──────────────────────────────────────


@pytest.fixture
def sample_archive_files() -> list[ArchiveFile]:
    """Return representative archive files for list-files tests."""
    return [
        ArchiveFile(
            key="data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2026-03.zip",
            size=1048,
            last_modified=datetime(2026, 4, 1, 8, 6, 34, tzinfo=UTC),
        ),
        ArchiveFile(
            key=(
                "data/futures/um/monthly/fundingRate/BTCUSDT/"
                "BTCUSDT-fundingRate-2026-03.zip.CHECKSUM"
            ),
            size=105,
            last_modified=datetime(2026, 4, 1, 8, 6, 34, tzinfo=UTC),
        ),
    ]


# ── Trade Type Fixtures ───────────────────────────────────────


@pytest.fixture(params=["spot", "um", "cm"])
def trade_type_str(request) -> str:
    """Parametrized fixture: each trade type as a string."""
    return request.param


@pytest.fixture(params=["spot", "um", "cm"])
def trade_type(request) -> Any:
    """Parametrized fixture: each trade type as a TradeType enum."""
    from binance_datatool.common import TradeType

    return TradeType(request.param)


@pytest.fixture
def all_trade_types() -> list[Any]:
    """All supported trade types."""
    from binance_datatool.common import TradeType

    return list(TradeType)


@pytest.fixture
def all_data_types() -> list[Any]:
    """All supported data types."""
    from binance_datatool.common import DataType

    return list(DataType)


# ── Sample CSV Data Fixtures ──────────────────────────────────


def _csv_rows(header: list[str], rows: list[list[str]]) -> str:
    """Format header + rows as CSV string."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


@pytest.fixture
def sample_klines_csv() -> str:
    """Sample klines data as CSV string (Binance archive format: no header)."""
    lines = [
        "1502928000000,4000.00,4010.00,3990.00,4005.00,100.0,1502931599999,400500.0,300,50.0,200250.0,0",
        "1502931600000,4005.00,4020.00,4000.00,4015.00,150.0,1502935199999,602250.0,450,80.0,321200.0,0",
        "1502935200000,4015.00,4030.00,4010.00,4025.00,200.0,1502938799999,805000.0,600,100.0,402500.0,0",
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_agg_trades_csv() -> str:
    """Sample aggTrades data as CSV string (no header)."""
    lines = [
        "3952950559,80006.00,1.16331,6280951459,6280951459,1778198400018655,False,True",
        "3952950560,80006.00,6.24960,6280951460,6280951460,1778198400018669,False,True",
        "3952950561,80007.00,1.81869,6280951461,6280951461,1778198400018786,True,True",
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_trades_csv() -> str:
    """Sample raw trades CSV (no header)."""
    lines = [
        "3952950559,80006.00,1.16331,93123.45,1778198400018655,False,True",
        "3952950560,80006.00,6.24960,500000.00,1778198400018669,False,True",
        "3952950561,80007.00,1.81869,145600.00,1778198400018786,True,True",
    ]
    return "\n".join(lines)


@pytest.fixture
def sample_funding_rate_csv() -> str:
    """Sample fundingRate data as CSV string (HAS header)."""
    return _csv_rows(
        ["calc_time", "funding_interval_hours", "last_funding_rate"],
        [
            ["1775001600000", "8", "-0.00003449"],
            ["1775030400000", "8", "-0.00000461"],
            ["1775059200000", "8", "0.00001250"],
        ],
    )


# ── Sample Bronze Columns ─────────────────────────────────────


@pytest.fixture
def bronze_klines_cols() -> list[str]:
    from binance_datatool.workflow.sink import _BRONZE_KLINE_COLS

    return _BRONZE_KLINE_COLS


@pytest.fixture
def bronze_agg_trades_cols() -> list[str]:
    from binance_datatool.workflow.sink import _BRONZE_AGGT_COLS

    return _BRONZE_AGGT_COLS


@pytest.fixture
def bronze_trades_cols() -> list[str]:
    from binance_datatool.workflow.sink import _BRONZE_TRADES_COLS

    return _BRONZE_TRADES_COLS


@pytest.fixture
def bronze_funding_rate_cols() -> list[str]:
    from binance_datatool.workflow.sink import _BRONZE_FUNDING_COLS

    return _BRONZE_FUNDING_COLS


# ── Sample Archive Path Fixtures ──────────────────────────────


@pytest.fixture
def sample_archive_root(tmp_path: Path) -> Path:
    """Create a temporary archive root with sample files for all data types."""
    from tests.sample_archive import SampleArchive

    archive = SampleArchive(tmp_path / "archive")
    archive.create_all()
    return archive.root


# ── Pytest Configuration ──────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register local pytest options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests that make real network requests to data.binance.vision.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless explicitly requested."""
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(
        reason="use --run-integration to run network integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
