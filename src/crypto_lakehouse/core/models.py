"""Core data models and types for the crypto data lakehouse."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Exchange(str, Enum):
    """Supported cryptocurrency exchanges."""

    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"


class DataType(str, Enum):
    """Types of market data supported by the lakehouse."""

    KLINES = "klines"
    FUNDING_RATES = "funding_rates"
    LIQUIDATIONS = "liquidations"
    ORDER_BOOK = "order_book"
    TRADES = "trades"
    TICKER = "ticker"
    METRICS = "metrics"
    VOLATILITY = "volatility"
    SUMMARY = "summary"


class Interval(str, Enum):
    """Time intervals for K-line data."""

    SEC_1 = "1s"
    SEC_5 = "5s"
    SEC_10 = "10s"
    MIN_1 = "1m"
    MIN_3 = "3m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    DAY_3 = "3d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class TradeType(str, Enum):
    """Types of trading instruments."""

    SPOT = "spot"
    UM_FUTURES = "um_futures"  # USDT-Margined Futures
    CM_FUTURES = "cm_futures"  # Coin-Margined Futures
    OPTIONS = "options"  # Options contracts


class ContractType(str, Enum):
    """Contract types for futures."""

    PERPETUAL = "PERPETUAL"
    DELIVERY = "DELIVERY"


class DataZone(str, Enum):
    """Data lakehouse storage zones."""

    BRONZE = "bronze"  # Raw data
    SILVER = "silver"  # Processed data
    GOLD = "gold"  # Aggregated/feature-engineered data


class KlineData(BaseModel):
    """K-line (candlestick) data model."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    quote_asset_volume: Decimal
    number_of_trades: int
    taker_buy_base_asset_volume: Decimal
    taker_buy_quote_asset_volume: Decimal

    # Enhanced fields (computed in Silver zone)
    vwap: Optional[Decimal] = None
    returns: Optional[Decimal] = None
    log_returns: Optional[Decimal] = None


class FundingRateData(BaseModel):
    """Funding rate data model for perpetual futures."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    funding_time: datetime
    funding_rate: Decimal
    mark_price: Optional[Decimal] = None


class LiquidationData(BaseModel):
    """Liquidation data model."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    time: datetime
    side: str  # "BUY" or "SELL"
    price: Decimal
    quantity: Decimal
    last_quantity_filled: Decimal
    event_time: datetime


class DataIngestionTask(BaseModel):
    """Task definition for data ingestion workflows."""

    exchange: Exchange
    data_type: DataType
    trade_type: TradeType
    symbols: List[str]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    interval: Optional[Interval] = None
    contract_type: Optional[ContractType] = None

    # Processing options
    force_update: bool = False
    enable_validation: bool = True
    target_zone: DataZone = DataZone.SILVER


class IngestionMetadata(BaseModel):
    """Metadata for tracking ingestion progress."""

    task_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    records_processed: int = 0
    bytes_processed: int = 0
    errors: List[str] = Field(default_factory=list)

    # File tracking
    source_files: List[str] = Field(default_factory=list)
    output_files: List[str] = Field(default_factory=list)
