"""S3-based storage implementation for the data lakehouse."""

import boto3
import s3fs
import polars as pl
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
from pathlib import Path

from .base import BaseStorage, DataLakeMetadata
from ..core.models import DataZone, DataType, TradeType, Exchange
from ..core.config import Settings

logger = logging.getLogger(__name__)


class S3Storage(BaseStorage):
    """S3-based storage implementation for the data lakehouse."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.s3_config = settings.s3
        
        # Initialize S3 clients
        self._init_s3_clients()
        
        # Base paths
        self.base_path = settings.storage.base_path.rstrip('/')
        
    def _init_s3_clients(self):
        """Initialize S3 clients and filesystem."""
        session_kwargs = {
            'region_name': self.s3_config.region
        }
        
        if self.s3_config.access_key_id and self.s3_config.secret_access_key:
            session_kwargs.update({
                'aws_access_key_id': self.s3_config.access_key_id,
                'aws_secret_access_key': self.s3_config.secret_access_key
            })
        
        if self.s3_config.endpoint_url:
            session_kwargs['endpoint_url'] = self.s3_config.endpoint_url
        
        self.session = boto3.Session(**session_kwargs)
        self.s3_client = self.session.client('s3')
        
        # S3FS for DataFrame operations
        fs_kwargs = {
            'key': self.s3_config.access_key_id,
            'secret': self.s3_config.secret_access_key,
            'client_kwargs': {'region_name': self.s3_config.region}
        }
        
        if self.s3_config.endpoint_url:
            fs_kwargs['client_kwargs']['endpoint_url'] = self.s3_config.endpoint_url
        
        self.fs = s3fs.S3FileSystem(**fs_kwargs)
    
    async def write_data(
        self,
        data: pl.DataFrame,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: str,
        partition_date: datetime,
        **kwargs
    ) -> str:
        """Write data to S3 in Parquet format with partitioning."""
        try:
            # Generate partition path
            partition_path = self.get_partition_path(
                zone, exchange, data_type, trade_type, symbol, partition_date
            )
            
            full_path = f"{self.base_path}/{partition_path}"
            
            # Add partition columns
            data_with_partitions = data.with_columns([
                pl.lit(symbol).alias("symbol"),
                pl.lit(partition_date.year).alias("year"),
                pl.lit(partition_date.month).alias("month"),
                pl.lit(partition_date.day).alias("day")
            ])
            
            # Write to S3 as Parquet
            s3_path = f"s3://{self.s3_config.bucket_name}/{full_path}/data.parquet"
            
            # Convert to PyArrow and write
            arrow_table = data_with_partitions.to_arrow()
            
            with self.fs.open(s3_path.replace('s3://', ''), 'wb') as f:
                import pyarrow.parquet as pq
                pq.write_table(arrow_table, f, compression='snappy')
            
            logger.info(f"Successfully wrote {len(data)} records to {s3_path}")
            return s3_path
            
        except Exception as e:
            logger.error(f"Failed to write data to S3: {e}")
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
        **kwargs
    ) -> pl.DataFrame:
        """Read data from S3 with optional filtering."""
        try:
            # Build base path
            table_path = self.get_table_path(zone, exchange, data_type, trade_type)
            base_s3_path = f"s3://{self.s3_config.bucket_name}/{self.base_path}/{table_path}"
            
            # List partitions that match criteria
            partitions = await self.list_partitions(
                zone, exchange, data_type, trade_type
            )
            
            # Filter partitions
            filtered_partitions = self._filter_partitions(
                partitions, symbols, start_date, end_date
            )
            
            if not filtered_partitions:
                logger.warning("No matching partitions found")
                return pl.DataFrame()
            
            # Read data from matching partitions
            dataframes = []
            for partition in filtered_partitions:
                partition_path = f"{base_s3_path}/{partition['path']}/data.parquet"
                
                try:
                    df = pl.read_parquet(
                        partition_path,
                        storage_options={
                            'aws_access_key_id': self.s3_config.access_key_id,
                            'aws_secret_access_key': self.s3_config.secret_access_key,
                            'aws_region': self.s3_config.region
                        }
                    )
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
                result = result.filter(pl.col("open_time") >= start_date)
            
            if end_date:
                result = result.filter(pl.col("open_time") <= end_date)
            
            logger.info(f"Successfully read {len(result)} records")
            return result
            
        except Exception as e:
            logger.error(f"Failed to read data from S3: {e}")
            raise
    
    async def list_partitions(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available partitions in S3."""
        try:
            table_path = self.get_table_path(zone, exchange, data_type, trade_type)
            prefix = f"{self.base_path}/{table_path}/"
            
            if symbol:
                prefix += f"symbol={symbol}/"
            
            # List objects with the prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_config.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )
            
            partitions = []
            
            # Process common prefixes (partition directories)
            for prefix_info in response.get('CommonPrefixes', []):
                partition_path = prefix_info['Prefix'].replace(f"{self.base_path}/{table_path}/", "")
                
                # Parse partition info
                partition_info = self._parse_partition_path(partition_path)
                if partition_info:
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
        partition_date: datetime
    ) -> bool:
        """Delete a specific partition from S3."""
        try:
            partition_path = self.get_partition_path(
                zone, exchange, data_type, trade_type, symbol, partition_date
            )
            
            prefix = f"{self.base_path}/{partition_path}/"
            
            # List all objects in the partition
            response = self.s3_client.list_objects_v2(
                Bucket=self.s3_config.bucket_name,
                Prefix=prefix
            )
            
            # Delete all objects
            if 'Contents' in response:
                delete_keys = [{'Key': obj['Key']} for obj in response['Contents']]
                
                self.s3_client.delete_objects(
                    Bucket=self.s3_config.bucket_name,
                    Delete={'Objects': delete_keys}
                )
            
            logger.info(f"Successfully deleted partition: {prefix}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete partition: {e}")
            return False
    
    async def get_schema(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType
    ) -> Optional[pl.Schema]:
        """Get schema by reading a sample file."""
        try:
            # Find a sample partition
            partitions = await self.list_partitions(zone, exchange, data_type, trade_type)
            
            if not partitions:
                return None
            
            # Read schema from first partition
            sample_partition = partitions[0]
            table_path = self.get_table_path(zone, exchange, data_type, trade_type)
            sample_path = f"s3://{self.s3_config.bucket_name}/{self.base_path}/{table_path}/{sample_partition['path']}/data.parquet"
            
            # Read just the schema (no data)
            df = pl.scan_parquet(
                sample_path,
                storage_options={
                    'aws_access_key_id': self.s3_config.access_key_id,
                    'aws_secret_access_key': self.s3_config.secret_access_key,
                    'aws_region': self.s3_config.region
                }
            ).limit(0).collect()
            
            return df.schema
            
        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            return None
    
    async def optimize_partitions(
        self,
        zone: DataZone,
        exchange: Exchange,
        data_type: DataType,
        trade_type: TradeType,
        symbol: Optional[str] = None
    ) -> Dict[str, Any]:
        """Optimize storage partitions (compaction, etc.)."""
        # Future: Implement partition optimization
        # - Combine small files
        # - Rewrite with better compression
        # - Update statistics
        
        return {
            "status": "not_implemented",
            "message": "Partition optimization not yet implemented"
        }
    
    def _filter_partitions(
        self,
        partitions: List[Dict[str, Any]],
        symbols: Optional[List[str]],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[Dict[str, Any]]:
        """Filter partitions based on criteria."""
        filtered = partitions
        
        if symbols:
            filtered = [p for p in filtered if p.get('symbol') in symbols]
        
        if start_date:
            filtered = [p for p in filtered if p.get('date', datetime.min) >= start_date.date()]
        
        if end_date:
            filtered = [p for p in filtered if p.get('date', datetime.max) <= end_date.date()]
        
        return filtered
    
    def _parse_partition_path(self, partition_path: str) -> Optional[Dict[str, Any]]:
        """Parse partition path to extract metadata."""
        try:
            # Expected format: symbol=BTCUSDT/year=2024/month=01/day=15/
            parts = partition_path.strip('/').split('/')
            
            partition_info = {'path': partition_path.strip('/')}
            
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    
                    if key in ['year', 'month', 'day']:
                        partition_info[key] = int(value)
                    else:
                        partition_info[key] = value
            
            # Construct date if year/month/day are present
            if all(k in partition_info for k in ['year', 'month', 'day']):
                partition_info['date'] = datetime(
                    partition_info['year'],
                    partition_info['month'],
                    partition_info['day']
                ).date()
            
            return partition_info
            
        except Exception as e:
            logger.warning(f"Failed to parse partition path {partition_path}: {e}")
            return None


class GlueDataCatalog(DataLakeMetadata):
    """AWS Glue Data Catalog implementation."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.glue_client = boto3.client(
            'glue',
            region_name=settings.data_catalog.region
        )
        self.database_name = settings.data_catalog.database_name
    
    async def register_table(
        self,
        database: str,
        table_name: str,
        schema: pl.Schema,
        location: str,
        partition_columns: List[str],
        **kwargs
    ) -> bool:
        """Register table in Glue Data Catalog."""
        try:
            # Convert Polars schema to Glue format
            columns = []
            for col_name, col_type in schema.items():
                glue_type = self._polars_to_glue_type(col_type)
                
                if col_name not in partition_columns:
                    columns.append({
                        'Name': col_name,
                        'Type': glue_type
                    })
            
            # Partition columns
            partition_keys = []
            for col in partition_columns:
                if col in schema:
                    glue_type = self._polars_to_glue_type(schema[col])
                    partition_keys.append({
                        'Name': col,
                        'Type': glue_type
                    })
            
            # Create table
            table_input = {
                'Name': table_name,
                'StorageDescriptor': {
                    'Columns': columns,
                    'Location': location,
                    'InputFormat': 'org.apache.hadoop.mapred.TextInputFormat',
                    'OutputFormat': 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat',
                    'SerdeInfo': {
                        'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe'
                    }
                },
                'PartitionKeys': partition_keys
            }
            
            self.glue_client.create_table(
                DatabaseName=database,
                TableInput=table_input
            )
            
            logger.info(f"Successfully registered table {table_name} in Glue catalog")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register table in Glue catalog: {e}")
            return False
    
    async def update_partitions(
        self,
        database: str,
        table_name: str,
        partitions: List[Dict[str, Any]]
    ) -> bool:
        """Update partition metadata in Glue."""
        # Future: Implement partition updates
        return True
    
    async def get_table_info(
        self,
        database: str,
        table_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get table metadata from Glue."""
        try:
            response = self.glue_client.get_table(
                DatabaseName=database,
                Name=table_name
            )
            return response['Table']
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return None
    
    async def list_tables(
        self,
        database: str,
        pattern: Optional[str] = None
    ) -> List[str]:
        """List tables in Glue database."""
        try:
            kwargs = {'DatabaseName': database}
            if pattern:
                kwargs['Expression'] = pattern
            
            response = self.glue_client.get_tables(**kwargs)
            return [table['Name'] for table in response['TableList']]
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []
    
    def _polars_to_glue_type(self, polars_type: pl.DataType) -> str:
        """Convert Polars data type to Glue data type."""
        type_mapping = {
            pl.Int32: 'int',
            pl.Int64: 'bigint',
            pl.Float32: 'float',
            pl.Float64: 'double',
            pl.Boolean: 'boolean',
            pl.Utf8: 'string',
            pl.Date: 'date',
            pl.Datetime: 'timestamp'
        }
        
        return type_mapping.get(polars_type, 'string')