"""Local filesystem storage implementation."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

from ..core.config import Settings
from ..core.models import DataType, DataZone, Exchange, TradeType
from .base import BaseStorage

logger = logging.getLogger(__name__)


class LocalStorage(BaseStorage):
    """Local filesystem storage implementation for development."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_path = Path(settings.local_data_dir)

        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def write_data(
        self,
        data: pl.DataFrame,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: str,
        partition_date: datetime,
        **kwargs,
    ) -> str:
        """Write data to local filesystem in Parquet format."""
        try:
            # Generate partition path
            partition_path = self.get_partition_path(
                zone, exchange, data_type, trade_type, symbol, partition_date
            )

            full_path = self.base_path / partition_path
            full_path.mkdir(parents=True, exist_ok=True)

            # Add partition columns
            data_with_partitions = data.with_columns(
                [
                    pl.lit(symbol).alias("symbol"),
                    pl.lit(partition_date.year).alias("year"),
                    pl.lit(partition_date.month).alias("month"),
                    pl.lit(partition_date.day).alias("day"),
                ]
            )

            # Write to Parquet
            file_path = full_path / "data.parquet"
            data_with_partitions.write_parquet(file_path, compression="snappy", use_pyarrow=True)

            # Write metadata
            metadata_path = full_path / "_metadata.json"
            metadata = {
                "zone": zone.value,
                "exchange": exchange.value,
                "data_type": data_type.value,
                "trade_type": trade_type.value,
                "symbol": symbol,
                "partition_date": partition_date.isoformat(),
                "record_count": len(data),
                "created_at": datetime.now().isoformat(),
                "schema": {col: str(dtype) for col, dtype in data.schema.items()},
            }

            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Successfully wrote {len(data)} records to {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to write data to local storage: {e}")
            raise

    async def read_data(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbols: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> pl.DataFrame:
        """Read data from local filesystem."""
        try:
            # Get all matching partitions
            partitions = await self.list_partitions(zone, exchange, data_type, trade_type)

            # Filter partitions
            filtered_partitions = self._filter_partitions(partitions, symbols, start_date, end_date)

            if not filtered_partitions:
                logger.warning("No matching partitions found")
                return pl.DataFrame()

            # Read data from all matching partitions
            dataframes = []
            for partition in filtered_partitions:
                partition_path = self.base_path / partition["path"] / "data.parquet"

                if partition_path.exists():
                    try:
                        df = pl.read_parquet(partition_path)
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to read partition {partition_path}: {e}")

            if not dataframes:
                return pl.DataFrame()

            # Combine all dataframes
            result = pl.concat(dataframes)

            # Apply additional filters
            if symbols:
                result = result.filter(pl.col("symbol").is_in(symbols))

            if start_date:
                # Assume timestamp column exists (adjust based on data type)
                timestamp_col = self._get_timestamp_column(data_type)
                if timestamp_col in result.columns:
                    result = result.filter(pl.col(timestamp_col) >= start_date)

            if end_date:
                timestamp_col = self._get_timestamp_column(data_type)
                if timestamp_col in result.columns:
                    result = result.filter(pl.col(timestamp_col) <= end_date)

            logger.info(f"Successfully read {len(result)} records")
            return result

        except Exception as e:
            logger.error(f"Failed to read data from local storage: {e}")
            raise

    async def list_partitions(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List available partitions in local storage."""
        try:
            table_path = self.get_table_path(zone, exchange, data_type, trade_type)
            base_path = self.base_path / table_path

            partitions = []

            if not base_path.exists():
                return partitions

            # Walk through directory structure to find partitions
            for symbol_dir in base_path.glob("symbol=*"):
                if symbol and not symbol_dir.name.endswith(f"={symbol}"):
                    continue

                for year_dir in symbol_dir.glob("year=*"):
                    for month_dir in year_dir.glob("month=*"):
                        for day_dir in month_dir.glob("day=*"):
                            data_file = day_dir / "data.parquet"
                            metadata_file = day_dir / "_metadata.json"

                            if data_file.exists():
                                # Parse partition info
                                partition_info = self._parse_partition_path(
                                    str(day_dir.relative_to(base_path))
                                )

                                if partition_info:
                                    # Add metadata if available
                                    if metadata_file.exists():
                                        try:
                                            with open(metadata_file) as f:
                                                metadata = json.load(f)
                                                partition_info.update(
                                                    {
                                                        "record_count": metadata.get(
                                                            "record_count", 0
                                                        ),
                                                        "created_at": metadata.get("created_at"),
                                                        "file_size": data_file.stat().st_size,
                                                    }
                                                )
                                        except Exception as e:
                                            logger.warning(f"Failed to read metadata: {e}")

                                    partitions.append(partition_info)

            return partitions

        except Exception as e:
            logger.error(f"Failed to list partitions: {e}")
            return []

    async def delete_partition(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: str,
        partition_date: datetime,
    ) -> bool:
        """Delete a specific partition from local storage."""
        try:
            partition_path = self.get_partition_path(
                zone, exchange, data_type, trade_type, symbol, partition_date
            )

            full_path = self.base_path / partition_path

            if full_path.exists():
                import shutil

                shutil.rmtree(full_path)
                logger.info(f"Successfully deleted partition: {full_path}")
                return True
            else:
                logger.warning(f"Partition not found: {full_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete partition: {e}")
            return False

    async def get_schema(
        self, zone: DataZone, exchange: Exchange, data_type: DataType, trade_type: TradeType
    ) -> Optional[pl.Schema]:
        """Get schema by reading a sample file."""
        try:
            partitions = await self.list_partitions(zone, exchange, data_type, trade_type)

            if not partitions:
                return None

            # Read schema from first partition
            sample_partition = partitions[0]
            sample_path = self.base_path / sample_partition["path"] / "data.parquet"

            if sample_path.exists():
                # Read just the schema
                df = pl.scan_parquet(sample_path).limit(0).collect()
                return df.schema

            return None

        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            return None

    async def optimize_partitions(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Optimize local storage partitions."""
        try:
            partitions = await self.list_partitions(zone, exchange, data_type, trade_type, symbol)

            total_files = len(partitions)
            total_size = sum(p.get("file_size", 0) for p in partitions)

            # Simple optimization: identify small files that could be merged
            small_files = [p for p in partitions if p.get("file_size", 0) < 1024 * 1024]  # < 1MB

            return {
                "status": "analyzed",
                "total_partitions": total_files,
                "total_size_bytes": total_size,
                "small_files_count": len(small_files),
                "recommendations": [
                    (
                        f"Consider merging {len(small_files)} small files"
                        if small_files
                        else "No optimization needed"
                    )
                ],
            }

        except Exception as e:
            logger.error(f"Failed to optimize partitions: {e}")
            return {"status": "error", "message": str(e)}

    def _filter_partitions(
        self,
        partitions: List[Dict[str, Any]],
        symbols: Optional[List[str]],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> List[Dict[str, Any]]:
        """Filter partitions based on criteria."""
        filtered = partitions

        if symbols:
            filtered = [p for p in filtered if p.get("symbol") in symbols]

        if start_date:
            filtered = [
                p for p in filtered if p.get("date", datetime.min.date()) >= start_date.date()
            ]

        if end_date:
            filtered = [
                p for p in filtered if p.get("date", datetime.max.date()) <= end_date.date()
            ]

        return filtered

    def _parse_partition_path(self, partition_path: str) -> Optional[Dict[str, Any]]:
        """Parse partition path to extract metadata."""
        try:
            # Expected format: symbol=BTCUSDT/year=2024/month=01/day=15
            parts = partition_path.split("/")

            partition_info = {"path": partition_path}

            for part in parts:
                if "=" in part:
                    key, value = part.split("=", 1)

                    if key in ["year", "month", "day"]:
                        partition_info[key] = int(value)
                    else:
                        partition_info[key] = value

            # Construct date if year/month/day are present
            if all(k in partition_info for k in ["year", "month", "day"]):
                partition_info["date"] = datetime(
                    partition_info["year"], partition_info["month"], partition_info["day"]
                ).date()

            return partition_info

        except Exception as e:
            logger.warning(f"Failed to parse partition path {partition_path}: {e}")
            return None

    def _get_timestamp_column(self, data_type: DataType) -> str:
        """Get the main timestamp column for a data type."""
        if data_type == DataType.KLINES:
            return "open_time"
        elif data_type == DataType.FUNDING_RATES:
            return "funding_time"
        elif data_type == DataType.LIQUIDATIONS:
            return "time"
        else:
            return "timestamp"
