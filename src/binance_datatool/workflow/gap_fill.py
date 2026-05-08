"""Workflow for filling archive data gaps via REST API."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from binance_datatool.common.enums import TradeType
    from binance_datatool.common.types import KlineData
    from binance_datatool.exchange.client import ExchangeClient


def _archive_path(
    archive_home: Path,
    trade_type: TradeType,
    data_type: str,
    symbol: str,
    interval: str | None = None,
) -> Path:
    """Build the local archive path for a given symbol."""
    path = archive_home / "data" / trade_type.s3_path / "daily" / data_type / symbol
    if interval:
        path = path / interval
    return path


def _csv_header(data_type: str) -> list[str]:
    """Return CSV header for the given data type.

    Matches Binance archive CSV format.
    """
    if data_type == "klines":
        return [
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
    if data_type == "aggTrades":
        return [
            "agg_trade_id",
            "price",
            "quantity",
            "first_trade_id",
            "last_trade_id",
            "transact_time",
            "is_buyer_maker",
        ]
    if data_type == "fundingRate":
        return [
            "symbol",
            "funding_time",
            "funding_rate",
            "mark_price",
        ]
    return []


def _kline_to_row(kline: KlineData) -> list[str]:
    """Convert a KlineData to a CSV row."""
    return [
        str(kline.open_time),
        kline.open,
        kline.high,
        kline.low,
        kline.close,
        kline.volume,
        str(kline.close_time),
        kline.quote_volume,
        str(kline.num_trades),
        kline.taker_buy_volume,
        kline.taker_buy_quote_volume,
        "0",
    ]


def _write_csv(
    path: Path,
    header: list[str],
    rows: list[list[str]],
) -> None:
    """Write rows to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def _checksum(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class GapFillResult:
    """Result of a gap-fill operation."""

    def __init__(self) -> None:
        self.filled: list[Path] = []
        self.failed: list[tuple[str, str]] = []

    @property
    def files_filled(self) -> int:
        return len(self.filled)

    @property
    def files_failed(self) -> int:
        return len(self.failed)


class GapFillWorkflow:
    """Workflow for filling archive data gaps via REST API."""

    def __init__(
        self,
        exchange_client: ExchangeClient,
        archive_home: Path,
        symbols: Sequence[str],
        data_type: str,
        interval: str | None = None,
    ) -> None:
        self._client = exchange_client
        self._archive_home = Path(archive_home)
        self._symbols = symbols
        self._data_type = data_type
        self._interval = interval

    async def run(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> GapFillResult:
        """Run the gap-fill workflow."""
        result = GapFillResult()
        trade_type = self._client.trade_type

        for symbol in self._symbols:
            logger.info("Filling gaps for {} {}", symbol, self._data_type)
            try:
                data = await self._fetch_data(symbol, start_time, end_time)
                if not data:
                    logger.info("No data returned for {}", symbol)
                    continue
                paths = self._save_filled(trade_type, symbol, data)
                result.filled.extend(paths)
                logger.info("Filled {} files for {}", len(paths), symbol)
            except Exception as e:
                logger.error("Failed to fill {}: {}", symbol, e)
                result.failed.append((symbol, str(e)))

        return result

    async def _fetch_data(
        self,
        symbol: str,
        start_time: int | None,
        end_time: int | None,
    ) -> list:
        """Fetch data from REST API based on data type."""
        client = self._client

        if self._data_type == "klines":
            return await client.fetch_ohlcv(
                symbol=symbol,
                interval=self._interval or "1m",
                since=start_time,
                until=end_time,
            )
        if self._data_type == "aggTrades":
            return await client.fetch_agg_trades(
                symbol=symbol,
                since=start_time,
                until=end_time,
            )
        if self._data_type == "fundingRate":
            return await client.fetch_funding_rate(
                symbol=symbol,
                since=start_time,
                until=end_time,
            )
        msg = f"Unsupported data type: {self._data_type}"
        raise ValueError(msg)

    def _save_filled(
        self,
        trade_type: TradeType,
        symbol: str,
        data: list,
    ) -> list[Path]:
        """Save fetched data as CSV in the archive hierarchy."""
        base = _archive_path(
            self._archive_home,
            trade_type,
            self._data_type,
            symbol,
            self._interval,
        )
        filled_dir = base / "_filled"
        filled_dir.mkdir(parents=True, exist_ok=True)

        header = _csv_header(self._data_type)
        paths = []

        if self._data_type == "klines":
            rows = [_kline_to_row(k) for k in data]
            csv_path = filled_dir / f"{symbol}-{self._interval}-filled.csv"
            _write_csv(csv_path, header, rows)
            paths.append(csv_path)
        elif self._data_type == "aggTrades":
            rows = []
            for t in data:
                if isinstance(t, dict):
                    rows.append(
                        [
                            str(t.get("a", "")),
                            str(t.get("p", "")),
                            str(t.get("q", "")),
                            str(t.get("f", "")),
                            str(t.get("l", "")),
                            str(t.get("T", "")),
                            str(t.get("m", "")),
                        ]
                    )
                else:
                    rows.append([str(x) for x in t])
            csv_path = filled_dir / f"{symbol}-aggTrades-filled.csv"
            _write_csv(csv_path, header, rows)
            paths.append(csv_path)
        elif self._data_type == "fundingRate":
            rows = []
            for fr in data:
                if isinstance(fr, dict):
                    rows.append(
                        [
                            str(fr.get("symbol", "")),
                            str(fr.get("fundingTime", "")),
                            str(fr.get("fundingRate", "")),
                            str(fr.get("markPrice", "")),
                        ]
                    )
                else:
                    rows.append([str(x) for x in fr])
            csv_path = filled_dir / f"{symbol}-fundingRate-filled.csv"
            _write_csv(csv_path, header, rows)
            paths.append(csv_path)

        # Create checksum sidecar
        for p in paths:
            cs = _checksum(p)
            cs_path = p.with_suffix(p.suffix + ".CHECKSUM")
            cs_path.write_text(f"{cs}  {p.name}\n")

        return paths
