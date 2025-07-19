"""Data processing workflow for transforming data between lakehouse zones."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import polars as pl
from prefect import flow, task
from prefect.task_runners import ConcurrentTaskRunner

from ..core.config import Settings
from ..core.models import DataType, DataZone, Exchange, TradeType
from ..processing.funding_processor import FundingRateProcessor
from ..processing.kline_processor import KlineProcessor
from ..storage.factory import create_storage
from .base import BaseWorkflow, WorkflowRegistry

logger = logging.getLogger(__name__)


@task(retries=3, retry_delay_seconds=60)
async def read_bronze_data(
    exchange: Exchange,
    data_type: DataType,
    trade_type: TradeType,
    symbols: Optional[List[str]],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    settings: Settings,
) -> pl.DataFrame:
    """Read raw data from Bronze zone."""
    try:
        storage = create_storage(settings)

        data = await storage.read_data(
            zone=DataZone.BRONZE,
            exchange=exchange,
            data_type=data_type,
            trade_type=trade_type,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(f"Read {len(data)} records from Bronze zone")
        return data

    except Exception as e:
        logger.error(f"Failed to read Bronze data: {e}")
        raise


@task(retries=3, retry_delay_seconds=60)
async def process_data(data: pl.DataFrame, data_type: DataType, settings: Settings) -> pl.DataFrame:
    """Process data from Bronze to Silver zone format."""
    try:
        if data_type == DataType.KLINES:
            processor = KlineProcessor(settings)
        elif data_type == DataType.FUNDING_RATES:
            processor = FundingRateProcessor(settings)
        else:
            raise ValueError(f"No processor available for {data_type}")

        processed_data = await processor.process(
            data, source_zone=DataZone.BRONZE, target_zone=DataZone.SILVER
        )

        logger.info(f"Processed {len(processed_data)} records")
        return processed_data

    except Exception as e:
        logger.error(f"Data processing failed: {e}")
        raise


@task(retries=3, retry_delay_seconds=60)
async def validate_processed_data(
    data: pl.DataFrame, data_type: DataType, settings: Settings
) -> Dict[str, Any]:
    """Validate processed data quality."""
    try:
        # Basic validation checks
        validation_report = {
            "total_records": len(data),
            "null_counts": {},
            "data_types": {},
            "validation_passed": True,
            "issues": [],
        }

        # Check for nulls in critical columns
        critical_columns = {
            DataType.KLINES: ["symbol", "open_time", "close_time", "open_price", "close_price"],
            DataType.FUNDING_RATES: ["symbol", "funding_time", "funding_rate"],
        }.get(data_type, [])

        for col in critical_columns:
            if col in data.columns:
                null_count = data[col].null_count()
                validation_report["null_counts"][col] = null_count

                if null_count > 0:
                    validation_report["validation_passed"] = False
                    validation_report["issues"].append(f"Null values in critical column: {col}")

        # Check data types
        for col in data.columns:
            validation_report["data_types"][col] = str(data[col].dtype)

        # Check for duplicate records
        duplicate_count = len(data) - len(data.unique())
        if duplicate_count > 0:
            validation_report["issues"].append(f"Found {duplicate_count} duplicate records")

        return validation_report

    except Exception as e:
        logger.error(f"Data validation failed: {e}")
        raise


@task(retries=3, retry_delay_seconds=60)
async def write_silver_data(
    data: pl.DataFrame,
    exchange: Exchange,
    data_type: DataType,
    trade_type: TradeType,
    partition_date: datetime,
    settings: Settings,
) -> List[str]:
    """Write processed data to Silver zone."""
    try:
        storage = create_storage(settings)
        written_files = []

        # Group by symbol for writing
        if "symbol" in data.columns:
            symbols = data["symbol"].unique().to_list()

            for symbol in symbols:
                symbol_data = data.filter(pl.col("symbol") == symbol)

                file_path = await storage.write_data(
                    data=symbol_data,
                    zone=DataZone.SILVER,
                    exchange=exchange,
                    data_type=data_type,
                    trade_type=trade_type,
                    symbol=symbol,
                    partition_date=partition_date,
                )

                written_files.append(file_path)
        else:
            # Write all data together if no symbol column
            file_path = await storage.write_data(
                data=data,
                zone=DataZone.SILVER,
                exchange=exchange,
                data_type=data_type,
                trade_type=trade_type,
                symbol="ALL",
                partition_date=partition_date,
            )
            written_files.append(file_path)

        logger.info(f"Wrote data to {len(written_files)} Silver zone files")
        return written_files

    except Exception as e:
        logger.error(f"Failed to write Silver data: {e}")
        raise


@flow(
    name="data-processing-flow",
    task_runner=ConcurrentTaskRunner(),
    retries=1,
    retry_delay_seconds=300,
)
async def processing_flow(
    exchange: Exchange,
    data_type: DataType,
    trade_type: TradeType,
    symbols: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    settings: Settings = None,
) -> Dict[str, Any]:
    """Main data processing workflow."""

    if not settings:
        from ..core.config import Settings
        settings = Settings()

    try:
        # Step 1: Read raw data from Bronze zone
        bronze_data = await read_bronze_data(
            exchange, data_type, trade_type, symbols, start_date, end_date, settings
        )

        if len(bronze_data) == 0:
            logger.warning("No data found in Bronze zone")
            return {"status": "no_data", "records_processed": 0, "files_written": []}

        # Step 2: Process data
        silver_data = await process_data(bronze_data, data_type, settings)

        # Step 3: Validate processed data
        validation_report = await validate_processed_data(silver_data, data_type, settings)

        if not validation_report["validation_passed"]:
            logger.error(f"Data validation failed: {validation_report['issues']}")
            raise ValueError("Data validation failed")

        # Step 4: Write to Silver zone
        partition_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        written_files = await write_silver_data(
            silver_data, exchange, data_type, trade_type, partition_date, settings
        )

        return {
            "status": "success",
            "records_processed": len(silver_data),
            "files_written": written_files,
            "validation_report": validation_report,
        }

    except Exception as e:
        logger.error(f"Processing workflow failed: {e}")
        return {"status": "failed", "error": str(e), "records_processed": 0, "files_written": []}


@WorkflowRegistry.register("processing")
class ProcessingFlow(BaseWorkflow):
    """Data processing workflow implementation."""

    def __init__(self, config, metrics_collector=None):
        """Initialize processing workflow."""
        super().__init__(config, metrics_collector)
        # Convert config to Settings if needed
        if hasattr(config, 'to_dict'):
            from ..core.config import Settings
            self.settings = Settings(config.to_dict())
        else:
            from ..core.config import Settings
            self.settings = Settings()

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the processing workflow."""
        return await processing_flow(settings=self.settings, **kwargs)

    def get_flow_config(self) -> Dict[str, Any]:
        """Get Prefect flow configuration."""
        return {
            "name": "data-processing-flow",
            "description": "Process data from Bronze to Silver zone",
            "tags": ["processing", "transformation", "data"],
            "version": "2.0.0",
            "task_runner": ConcurrentTaskRunner(),
            "retries": 1,
            "retry_delay_seconds": 300,
        }
