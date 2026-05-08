"""Interval utilities for time-based operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binance_datatool.common.enums import DataFrequency

# Valid intervals for Binance klines
VALID_INTERVALS = frozenset(
    ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
)


def interval_to_ms(interval: str) -> int:
    """Convert interval string to milliseconds.

    Args:
        interval: Interval string (e.g. "1m", "1h", "1d").

    Returns:
        Interval in milliseconds.

    Raises:
        ValueError: If interval is not valid.
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(
            f"Invalid interval: {interval!r}. "
            f"Expected one of: {VALID_INTERVALS}"
        )

    unit = interval[-1]
    value = int(interval[:-1])

    multipliers = {
        "m": 60 * 1000,
        "h": 60 * 60 * 1000,
        "d": 24 * 60 * 60 * 1000,
        "w": 7 * 24 * 60 * 60 * 1000,
        "M": 30 * 24 * 60 * 60 * 1000,
    }

    return value * multipliers[unit]


__all__ = ["VALID_INTERVALS", "interval_to_ms"]
