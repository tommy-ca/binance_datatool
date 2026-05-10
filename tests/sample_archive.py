"""Sample archive generator mirroring Binance S3 data.binance.vision structure.

Generates minimal zip files for each trade type × frequency × data type
combination that actually exists in the Binance archive. Used for offline
testing of download, verify, and sink workflows.

Usage:
    from tests.sample_archive import SampleArchive
    archive = SampleArchive(tmp_path / "archive")
    archive.create_all()

Real archive structure (as of 2026-05):

    spot/daily/   aggTrades(1000f)    trades(1000f)
    spot/monthly/ aggTrades(210f)     trades(210f)
    um/daily/     aggTrades(1000f)    bookDepth(1000f)  bookTicker(640f)
                  metrics(1000f)      trades(1000f)
    um/monthly/   aggTrades(154f)     bookTicker(24f)   fundingRate(152f)
                  trades(160f)
    cm/           (empty — no archive data)

    klines has per-symbol subdirectories (13 symbols × daily zips)
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

# ── Sample CSV content generators ─────────────────────────────


def _klines_row(i: int, _time_us: int) -> list[str]:
    ot = 1502928000000 + i * 3600000
    return [
        str(ot),
        "40000.00",
        "40100.00",
        "39900.00",
        "40050.00",
        "100.0",
        str(ot + 3599999),
        "4005000.0",
        "300",
        "50.0",
        "2002500.0",
        "0",
    ]


def _agg_trades_row(trade_id: int, time_us: int) -> list[str]:
    return [
        str(trade_id),
        "40000.00",
        "1.5",
        str(trade_id * 10),
        str(trade_id * 10 + 5),
        str(time_us),
        "False",
        "True",
    ]


def _trades_row(trade_id: int, time_us: int) -> list[str]:
    return [
        str(trade_id),
        "40000.00",
        "1.5",
        "60000.00",
        str(time_us),
        "False",
        "True",
    ]


def _funding_rate_row(i: int, _time_us: int) -> list[str]:
    calc_time = 1775001600000 + i * 3600000000
    return [str(calc_time), "8", "0.00001000"]


# ── CSV writers (headerless data for zips, header for filled) ──


def _make_csv(header: list[str] | None, rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    if header:
        w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _write_zip(path: Path, csv_name: str, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(csv_name, content)


def _write_filled_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_make_csv(header, rows))


# ── Data type descriptors ─────────────────────────────────────


KLINE_COLS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]

AGGT_COLS = [
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
    "is_best_match",
]

TRADES_COLS = [
    "trade_id",
    "price",
    "qty",
    "quote_qty",
    "time",
    "is_buyer_maker",
    "is_best_match",
]

FUNDING_COLS = ["calc_time", "funding_interval_hours", "last_funding_rate"]


class SampleArchive:
    """Generates a minimal Binance archive for offline testing.

    Directory layout mirrors ``data.binance.vision``:
        {root}/data/{trade_type.s3_path}/{freq}/{data_type}/{symbol}/{interval?}/
    """

    SYMBOLS = ["BTCUSDT", "ETHUSDT"]
    CM_SYMBOLS = ["BTCUSD_PERP", "ETHUSD_PERP"]

    # Structure: trade_type -> freq -> [(data_type, has_interval, is_monthly_with_header)]
    TYPES: dict[str, dict[str, list[tuple[str, bool, bool]]]] = {
        "spot": {
            "daily": [
                ("klines", True, False),
                ("aggTrades", False, False),
                ("trades", False, False),
            ],
            "monthly": [
                ("aggTrades", False, False),
                ("trades", False, False),
            ],
        },
        "um": {
            "daily": [
                ("aggTrades", False, False),
                ("trades", False, False),
                ("bookDepth", False, False),
                ("bookTicker", False, False),
                ("metrics", False, False),
            ],
            "monthly": [
                ("aggTrades", False, False),
                ("trades", False, False),
                ("fundingRate", False, True),
                ("bookTicker", False, False),
            ],
        },
        "cm": {
            # CM (COIN-M delivery futures) — symbols use USD_PERP naming
            # Real archive: 267 symbols, 10 daily + 8 monthly data types
            "daily": [
                ("aggTrades", False, False),
                ("trades", False, False),
                ("klines", True, False),
                ("indexPriceKlines", True, False),
                ("markPriceKlines", True, False),
                ("premiumIndexKlines", True, False),
            ],
            "monthly": [
                ("aggTrades", False, False),
                ("trades", False, False),
                ("fundingRate", False, True),
                ("klines", True, False),
            ],
        },
    }

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def create_all(self) -> None:
        """Generate sample files for all trade types × frequencies × data types."""
        for trade_type, freqs in self.TYPES.items():
            self._create_trade_type(trade_type, freqs)

    def create_trade_type(self, trade_type: str) -> None:
        """Generate sample files for a single trade type."""
        if trade_type in self.TYPES:
            self._create_trade_type(trade_type, self.TYPES[trade_type])

    def _create_trade_type(
        self, trade_type: str, freqs: dict[str, list[tuple[str, bool, bool]]]
    ) -> None:
        from binance_datatool.common import TradeType

        tt = TradeType(trade_type)
        for freq, data_types in freqs.items():
            for data_type, has_interval, has_header in data_types:
                self._create_data_type(tt, freq, data_type, has_interval, has_header)

    def _create_data_type(
        self,
        trade_type: Any,
        freq: str,
        data_type: str,
        has_interval: bool,
        has_header: bool,
    ) -> None:
        symbols = self.CM_SYMBOLS if trade_type.value == "cm" else self.SYMBOLS
        for symbol in symbols:
            path_parts = [self._root, "data", trade_type.s3_path, freq, data_type, symbol]
            if has_interval:
                path_parts.append("1h")
            base = Path(*path_parts)
            self._write_zip_files(base, symbol, data_type, freq, has_header)
            if data_type == "klines":
                self._write_filled_csv(base, symbol, data_type)

    def _write_zip_files(
        self,
        base: Path,
        symbol: str,
        data_type: str,
        freq: str,
        has_header: bool,
    ) -> None:
        row_fn, cols, ext = self._type_info(data_type)
        date_part = "2026-05-08" if freq == "daily" else "2026-04"
        filename = f"{symbol}-{data_type}-{date_part}"
        csv_name = f"{filename}.csv"
        zip_name = f"{filename}.zip"
        header = cols if has_header else None

        rows = [row_fn(i, 1778198400000000 + i * 3600000000) for i in range(3)]
        content = _make_csv(header, rows)
        _write_zip(base / zip_name, csv_name, content)

    def _write_filled_csv(self, base: Path, symbol: str, data_type: str) -> None:
        row_fn, cols, _ = self._type_info(data_type)
        filled = base / "_filled"
        rows = [row_fn(i, 1778371200000000 + i * 3600000000) for i in range(2)]
        _write_filled_csv(filled / f"{symbol}-{data_type}-filled.csv", cols, rows)

    @staticmethod
    def _type_info(data_type: str) -> tuple[Any, list[str], str]:
        mapping = {
            "klines": (_klines_row, KLINE_COLS, ".csv"),
            "aggTrades": (_agg_trades_row, AGGT_COLS, ".csv"),
            "trades": (_trades_row, TRADES_COLS, ".csv"),
            "fundingRate": (_funding_rate_row, FUNDING_COLS, ".csv"),
            "bookDepth": (_agg_trades_row, AGGT_COLS, ".csv"),
            "bookTicker": (_agg_trades_row, AGGT_COLS, ".csv"),
            "metrics": (_agg_trades_row, AGGT_COLS, ".csv"),
        }
        return mapping.get(data_type, (_agg_trades_row, AGGT_COLS, ".csv"))
