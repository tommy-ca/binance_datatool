"""Tests for health check workflow — TDD spec: docs/specs-driven-development.md"""

from pathlib import Path

import duckdb
import pytest

from binance_datatool.workflow.health_check import (
    AnomalyReport,
    _sanitize_identifier,
    check_ducklake_anomalies,
)


# ── AnomalyReport ──────────────────────────────────────────────


def test_anomaly_report_is_clean_by_default() -> None:
    report = AnomalyReport(symbol="BTCUSDT")
    assert report.is_clean


def test_anomaly_report_not_clean_with_null_prices() -> None:
    report = AnomalyReport(symbol="BTCUSDT", null_prices=1)
    assert not report.is_clean


def test_anomaly_report_not_clean_with_zero_volumes() -> None:
    report = AnomalyReport(symbol="BTCUSDT", zero_volumes=1)
    assert not report.is_clean


def test_anomaly_report_not_clean_with_duplicate_timestamps() -> None:
    report = AnomalyReport(symbol="BTCUSDT", duplicate_timestamps=1)
    assert not report.is_clean


def test_anomaly_report_not_clean_with_date_gaps() -> None:
    report = AnomalyReport(symbol="BTCUSDT", date_gaps=["2026-01-01"])
    assert not report.is_clean


def test_anomaly_report_not_clean_with_outliers() -> None:
    report = AnomalyReport(symbol="BTCUSDT", outlier_rows=1)
    assert not report.is_clean


def test_anomaly_report_combined_anomalies() -> None:
    report = AnomalyReport(
        symbol="BTCUSDT",
        null_prices=2,
        zero_volumes=3,
        duplicate_timestamps=1,
        date_gaps=["2026-01-01", "2026-01-02"],
        outlier_rows=5,
    )
    assert not report.is_clean
    assert report.null_prices == 2
    assert report.zero_volumes == 3
    assert report.duplicate_timestamps == 1
    assert len(report.date_gaps) == 2
    assert report.outlier_rows == 5


# ── _sanitize_identifier ────────────────────────────────────────


def test_sanitize_identifier_preserves_alphanumeric_and_underscore() -> None:
    assert _sanitize_identifier("klines_1m") == "klines_1m"


def test_sanitize_identifier_removes_special_chars() -> None:
    assert _sanitize_identifier("k-lines!@#") == "klines"


def test_sanitize_identifier_handles_empty_string() -> None:
    assert _sanitize_identifier("") == ""


def test_sanitize_identifier_handles_dots_and_dashes() -> None:
    assert _sanitize_identifier("funding.rate-v2") == "fundingratev2"


# ── check_ducklake_anomalies ────────────────────────────────────


@pytest.fixture
def mem_con() -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection."""
    return duckdb.connect(":memory:")


def _create_kline_table(con: duckdb.DuckDBPyConnection, rows: list[tuple]) -> None:
    """Create a klines table with given rows."""
    con.execute(
        "CREATE OR REPLACE TABLE klines ("
        "symbol VARCHAR, ts_event BIGINT, ts_date VARCHAR, "
        "open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, "
        "volume DOUBLE"
        ")"
    )
    for row in rows:
        con.execute("INSERT INTO klines VALUES (?, ?, ?, ?, ?, ?, ?, ?)", list(row))


def test_check_empty_table_returns_clean_report(mem_con: duckdb.DuckDBPyConnection) -> None:
    """An empty table returns a default clean report."""
    mem_con.execute(
        "CREATE OR REPLACE TABLE klines ("
        "symbol VARCHAR, ts_event BIGINT, ts_date VARCHAR, "
        "open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE"
        ")"
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert report.is_clean
    assert report.symbol == "BTCUSDT"


def test_check_clean_data_no_anomalies(mem_con: duckdb.DuckDBPyConnection) -> None:
    _create_kline_table(
        mem_con,
        [
            ("BTCUSDT", 1, "2026-01-01", 100.0, 101.0, 99.0, 100.5, 1000.0),
            ("BTCUSDT", 2, "2026-01-01", 101.0, 102.0, 100.0, 101.5, 1100.0),
        ],
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert report.is_clean
    assert report.null_prices == 0
    assert report.zero_volumes == 0
    assert report.duplicate_timestamps == 0


def test_check_detects_null_prices(mem_con: duckdb.DuckDBPyConnection) -> None:
    _create_kline_table(
        mem_con,
        [
            ("BTCUSDT", 1, "2026-01-01", None, 101.0, 99.0, 100.5, 1000.0),
            ("BTCUSDT", 2, "2026-01-01", 0.0, None, 100.0, 101.5, 1100.0),
            ("BTCUSDT", 3, "2026-01-01", 102.0, 103.0, None, 0.0, 1200.0),
        ],
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert not report.is_clean
    assert report.null_prices > 0


def test_check_detects_zero_volumes(mem_con: duckdb.DuckDBPyConnection) -> None:
    _create_kline_table(
        mem_con,
        [
            ("BTCUSDT", 1, "2026-01-01", 100.0, 101.0, 99.0, 100.5, 0.0),
            ("BTCUSDT", 2, "2026-01-01", 101.0, 102.0, 100.0, 101.5, None),
        ],
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert not report.is_clean
    assert report.zero_volumes > 0


def test_check_detects_duplicate_timestamps(mem_con: duckdb.DuckDBPyConnection) -> None:
    _create_kline_table(
        mem_con,
        [
            ("BTCUSDT", 100, "2026-01-01", 100.0, 101.0, 99.0, 100.5, 1000.0),
            ("BTCUSDT", 100, "2026-01-01", 100.0, 101.0, 99.0, 100.5, 1000.0),
            ("BTCUSDT", 200, "2026-01-01", 101.0, 102.0, 100.0, 101.5, 1100.0),
        ],
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert not report.is_clean
    assert report.duplicate_timestamps >= 1


def test_check_skips_other_symbol_data(mem_con: duckdb.DuckDBPyConnection) -> None:
    """Anomaly detection filters by symbol — other symbols' data is ignored."""
    _create_kline_table(
        mem_con,
        [
            ("ETHUSDT", 1, "2026-01-01", None, None, None, None, 0.0),
            ("BTCUSDT", 2, "2026-01-01", 100.0, 101.0, 99.0, 100.5, 1000.0),
        ],
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert report.is_clean


def test_check_handles_missing_table(mem_con: duckdb.DuckDBPyConnection) -> None:
    """Non-existent table returns a clean report (no crash)."""
    report = check_ducklake_anomalies(mem_con, "nonexistent_table", "BTCUSDT")
    assert report.is_clean


def test_check_handles_special_chars_in_symbol(mem_con: duckdb.DuckDBPyConnection) -> None:
    """Symbols with special characters do not cause SQL errors (parameterized)."""
    mem_con.execute(
        "CREATE OR REPLACE TABLE klines ("
        "symbol VARCHAR, ts_event BIGINT, ts_date VARCHAR, "
        "open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE"
        ")"
    )
    mem_con.execute(
        "INSERT INTO klines VALUES ('BTC-USD/T', 1, '2026-01-01', 100.0, 101.0, 99.0, 100.5, 1000.0)"
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTC-USD/T")
    assert report is not None


def test_check_outlier_detection_with_stddev_zero(mem_con: duckdb.DuckDBPyConnection) -> None:
    """STDDEV=0 (all prices identical) does not crash — outlier query may report NaN rows."""
    _create_kline_table(
        mem_con,
        [
            ("BTCUSDT", 1, "2026-01-01", 100.0, 100.0, 100.0, 100.0, 1000.0),
            ("BTCUSDT", 2, "2026-01-01", 100.0, 100.0, 100.0, 100.0, 1000.0),
            ("BTCUSDT", 3, "2026-01-01", 100.0, 100.0, 100.0, 100.0, 1000.0),
        ],
    )
    # Should not raise — outlier query catches and logs instead of crashing
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert report.symbol == "BTCUSDT"


def test_check_anomaly_count_correct(mem_con: duckdb.DuckDBPyConnection) -> None:
    """Validate that anomaly counts are accurate (not just zero/non-zero)."""
    _create_kline_table(
        mem_con,
        [
            ("BTCUSDT", 1, "2026-01-01", 0.0, 1.0, 1.0, 1.0, 100.0),  # null_price: open=0
            ("BTCUSDT", 2, "2026-01-01", 2.0, 0.0, 2.0, 2.0, 0.0),  # null_price: high=0, volume=0
            ("BTCUSDT", 3, "2026-01-01", 3.0, 3.0, 3.0, 3.0, 300.0),  # clean
        ],
    )
    report = check_ducklake_anomalies(mem_con, "klines", "BTCUSDT")
    assert report.null_prices == 2  # open=0 in row1, high=0 in row2
    assert report.zero_volumes == 1  # volume=0 in row2
