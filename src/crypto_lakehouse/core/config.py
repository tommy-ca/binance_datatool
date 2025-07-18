"""Configuration management for the crypto data lakehouse."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from .models import DataZone


class S3Config(BaseModel):
    """S3 storage configuration."""
    bucket_name: str
    region: str = "us-east-1"
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    endpoint_url: Optional[str] = None


class StorageConfig(BaseModel):
    """Data lakehouse storage configuration."""
    base_path: str = "s3://crypto-data-lakehouse"
    
    @property
    def bronze_path(self) -> str:
        """Raw data storage path."""
        return f"{self.base_path}/bronze"
    
    @property
    def silver_path(self) -> str:
        """Processed data storage path."""
        return f"{self.base_path}/silver"
    
    @property
    def gold_path(self) -> str:
        """Aggregated data storage path."""
        return f"{self.base_path}/gold"
    
    def get_zone_path(self, zone: DataZone) -> str:
        """Get storage path for a specific zone."""
        if zone == DataZone.BRONZE:
            return self.bronze_path
        elif zone == DataZone.SILVER:
            return self.silver_path
        elif zone == DataZone.GOLD:
            return self.gold_path
        else:
            raise ValueError(f"Unknown data zone: {zone}")


class WorkflowConfig(BaseModel):
    """Workflow orchestration configuration."""
    engine: str = "prefect"  # or "dagster"
    concurrency_limit: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: int = 60


class ProcessingConfig(BaseModel):
    """Data processing configuration."""
    batch_size: int = 10000
    memory_limit_gb: int = 8
    cpu_count: Optional[int] = None
    enable_parallel: bool = True
    partition_cols: list[str] = Field(default=["year", "month", "day"])


class BinanceConfig(BaseModel):
    """Binance-specific configuration."""
    aws_base_url: str = "https://data.binance.vision"
    api_base_url: str = "https://api.binance.com"
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    rate_limit_requests_per_minute: int = 1200
    
    # Data availability
    spot_start_date: str = "2017-08-17"
    futures_start_date: str = "2019-09-08"


class DataCatalogConfig(BaseModel):
    """Data catalog configuration."""
    enabled: bool = True
    provider: str = "glue"  # or "hive", "unity"
    database_name: str = "crypto_lakehouse"
    region: str = "us-east-1"


class QueryConfig(BaseModel):
    """Query engine configuration."""
    duckdb_memory_limit: str = "8GB"
    duckdb_threads: Optional[int] = None
    trino_enabled: bool = False
    trino_coordinator_url: Optional[str] = None


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""
    log_level: str = "INFO"
    enable_metrics: bool = True
    metrics_backend: str = "prometheus"
    alert_webhook_url: Optional[str] = None


class Settings(BaseSettings):
    """Main application settings."""
    
    # Core settings
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Storage
    storage: StorageConfig = Field(default_factory=StorageConfig)
    s3: S3Config = Field(default_factory=lambda: S3Config(
        bucket_name=os.getenv("S3_BUCKET", "crypto-data-lakehouse"),
        region=os.getenv("AWS_REGION", "us-east-1"),
        access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    ))
    
    # Processing
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    
    # Data sources
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    
    # Infrastructure
    data_catalog: DataCatalogConfig = Field(default_factory=DataCatalogConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    
    # Local development
    local_data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CRYPTO_DATA_DIR", "~/crypto_data")).expanduser()
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Ensure local data directory exists
        self.local_data_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_cloud_enabled(self) -> bool:
        """Check if cloud storage is properly configured."""
        return bool(self.s3.bucket_name and (
            self.s3.access_key_id or 
            os.getenv("AWS_PROFILE") or 
            os.getenv("AWS_ROLE_ARN")
        ))
    
    @property
    def processing_concurrency(self) -> int:
        """Get optimal processing concurrency."""
        if self.processing.cpu_count:
            return self.processing.cpu_count
        return max(1, os.cpu_count() - 1)
    
    def get_storage_path(self, zone: DataZone, exchange: str, data_type: str) -> str:
        """Get full storage path for a specific data type."""
        base_path = self.storage.get_zone_path(zone)
        return f"{base_path}/{exchange}/{data_type}"
    
    def get_local_cache_path(self, exchange: str, data_type: str) -> Path:
        """Get local cache path for development."""
        return self.local_data_dir / exchange / data_type


# Global settings instance
settings = Settings()