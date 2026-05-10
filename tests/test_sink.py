"""Tests for sink workflow — TDD spec: docs/specs-driven-development.md"""

from pathlib import Path

from binance_datatool.workflow.sink import _parse_symbol_from_path


def test_parse_symbol_exact_match() -> None:
    path = Path("BTCUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["BTCUSDT", "ETHUSDT"])
    assert result == "BTCUSDT"


def test_parse_symbol_prefix_only() -> None:
    """'BTC' must NOT match 'BTCUSDT-1h-2026.zip' (regression: substring bug)."""
    path = Path("BTCUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["BTC", "BTCUSDT"])
    assert result == "BTCUSDT"


def test_parse_symbol_no_match() -> None:
    path = Path("SOLUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["BTCUSDT", "ETHUSDT"])
    assert result is None


def test_parse_symbol_empty_known_symbols() -> None:
    path = Path("BTCUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, [])
    assert result is None


def test_parse_symbol_second_symbol_matches() -> None:
    path = Path("ETHUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["BTCUSDT", "ETHUSDT"])
    assert result == "ETHUSDT"


def test_parse_symbol_different_interval() -> None:
    path = Path("BTCUSDT-1m-2026-01-01.csv")
    result = _parse_symbol_from_path(path, ["BTCUSDT"])
    assert result == "BTCUSDT"


def test_parse_symbol_filled_csv_path() -> None:
    path = Path("/tmp/archive/spot/_filled/BTCUSDT-1h-2026-01-01.csv")
    result = _parse_symbol_from_path(path, ["BTCUSDT"])
    assert result == "BTCUSDT"


def test_parse_symbol_substring_not_matched() -> None:
    """'USDT' must NOT match 'BTCUSDT-1h.zip' — only startswith should match."""
    path = Path("BTCUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["USDT", "BTCUSDT"])
    assert result == "BTCUSDT"


def test_parse_symbol_caret_substring_sym() -> None:
    """'BTC' alone should NOT match 'BTCUSDT' when 'BTCUSDT' is also in the list."""
    path = Path("BTCUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["BTC", "BTCUSDT", "ETHUSDT"])
    assert result == "BTCUSDT"


def test_parse_symbol_nested_path() -> None:
    """Deeply nested paths should still match correctly."""
    path = Path("/data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2026-01-01.zip")
    result = _parse_symbol_from_path(path, ["BTCUSDT"])
    assert result == "BTCUSDT"
