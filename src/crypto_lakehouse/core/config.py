"""
Configuration management for crypto lakehouse workflows.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from .exceptions import ValidationError


class TradeType(Enum):
    """Trading type enumeration for compatibility."""
    SPOT = "spot"
    FUTURES = "futures"
    OPTIONS = "options"


class DataZone(str, Enum):
    """Data zones for the lakehouse architecture."""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class S3Config(BaseModel):
    """S3 configuration settings."""
    
    bucket_name: str
    region: str = "us-east-1"
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    use_ssl: bool = True


class StorageConfig(BaseModel):
    """Storage configuration for the lakehouse."""
    
    base_path: str
    
    @property
    def bronze_path(self) -> str:
        """Get bronze zone path."""
        return f"{self.base_path}/bronze"
    
    @property
    def silver_path(self) -> str:
        """Get silver zone path."""
        return f"{self.base_path}/silver"
    
    @property
    def gold_path(self) -> str:
        """Get gold zone path."""
        return f"{self.base_path}/gold"
    
    def get_zone_path(self, zone: Union[DataZone, str]) -> str:
        """Get path for specific data zone."""
        if isinstance(zone, str):
            try:
                zone = DataZone(zone)
            except ValueError:
                raise ValueError(f"Unknown data zone: {zone}")
        
        if zone == DataZone.BRONZE:
            return self.bronze_path
        elif zone == DataZone.SILVER:
            return self.silver_path
        elif zone == DataZone.GOLD:
            return self.gold_path
        else:
            raise ValueError(f"Unknown data zone: {zone}")


class WorkflowConfig(BaseModel):
    """Workflow configuration settings."""
    
    concurrency_limit: int = 10
    retry_attempts: int = 3
    timeout_seconds: int = 3600


class ProcessingConfig(BaseModel):
    """Processing configuration settings."""
    
    batch_size: int = 10000
    cpu_count: Optional[int] = None
    memory_limit_gb: int = 8


class BinanceConfig(BaseModel):
    """Binance-specific configuration."""
    
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: str = "https://api.binance.com"
    aws_base_url: str = "https://data.binance.vision"
    testnet: bool = False
    timeout: int = 30


class DataCatalogConfig(BaseModel):
    """Data catalog configuration."""
    
    database_name: str = "crypto_lakehouse"
    table_prefix: str = "crypto_"


class QueryConfig(BaseModel):
    """Query engine configuration."""
    
    engine: str = "duckdb"
    cache_size_mb: int = 1024


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""
    
    enabled: bool = True
    metrics_port: int = 8000
    tracing_enabled: bool = True


class Config:
    """Legacy configuration class for backward compatibility."""
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize legacy configuration."""
        self._config = config_data.copy()
        storage_data = config_data.get('storage', {})
        s3_data = config_data.get('s3', {})
        
        # Handle legacy format
        if 'base_path' not in storage_data:
            storage_data['base_path'] = storage_data.get('local_path', 'output')
        if 'bucket_name' not in s3_data:
            s3_data['bucket_name'] = s3_data.get('bucket', 'crypto-data-lakehouse')
        
        self.storage = StorageConfig(**storage_data)
        self.s3 = S3Config(**s3_data)
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)


class Settings:
    """System settings for storage and configuration."""
    
    def __init__(
        self, 
        config_data: Optional[Dict[str, Any]] = None,
        environment: str = "development",
        local_data_dir: Optional[Path] = None
    ):
        """Initialize settings from configuration data."""
        self._config = config_data or {}
        self.environment = environment
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Set local data directory
        if local_data_dir:
            self.local_data_dir = local_data_dir
        else:
            self.local_data_dir = Path(os.getenv("CRYPTO_DATA_DIR", "output"))
        
        # Initialize configuration components
        self.storage = StorageConfig(
            base_path=os.getenv("S3_BUCKET", "s3://crypto-data-lakehouse")
        )
        
        self.s3 = S3Config(
            bucket_name=os.getenv("S3_BUCKET", "crypto-data-lakehouse"),
            region=os.getenv("S3_REGION", "us-east-1"),
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL")
        )
        
        self.workflow = WorkflowConfig()
        self.processing = ProcessingConfig()
        self.binance = BinanceConfig()
        self.data_catalog = DataCatalogConfig()
        self.query = QueryConfig()
        self.monitoring = MonitoringConfig()
        
        # Legacy compatibility
        self.is_cloud_enabled = self._is_cloud_enabled()
        self.aws_access_key_id = self.s3.access_key_id
        self.aws_secret_access_key = self.s3.secret_access_key
        self.s3_bucket = self.s3.bucket_name
        self.s3_region = self.s3.region
        
        # Legacy binance settings
        self.binance_legacy = BinanceSettings(self._config.get('binance', {}))
    
    def _is_cloud_enabled(self) -> bool:
        """Check if cloud storage is enabled."""
        return bool(
            self.s3.bucket_name and (
                self.s3.access_key_id or 
                os.getenv("AWS_PROFILE") or
                os.getenv("AWS_DEFAULT_PROFILE")
            )
        )
    
    @property
    def processing_concurrency(self) -> int:
        """Calculate processing concurrency."""
        if self.processing.cpu_count:
            return self.processing.cpu_count
        return max(1, os.cpu_count() or 1)
    
    def get_storage_path(self, zone: DataZone, *path_components: str) -> str:
        """Get storage path for a data zone with additional path components."""
        base_path = self.storage.get_zone_path(zone)
        if path_components:
            return "/".join([base_path] + list(path_components))
        return base_path
    
    def get_local_cache_path(self, *path_components: str) -> Path:
        """Get local cache path with path components."""
        path = self.local_data_dir
        for component in path_components:
            path = path / component
        return path


class BinanceSettings:
    """Legacy Binance settings for backward compatibility."""
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize Binance settings."""
        self.api_key = config_data.get('api_key')
        self.api_secret = config_data.get('api_secret')
        self.base_url = config_data.get('base_url', 'https://api.binance.com')
        self.testnet = config_data.get('testnet', False)
        self.timeout = config_data.get('timeout', 30)


# Simple legacy workflow config for test compatibility
class LegacyWorkflowConfig:
    """Simple workflow configuration class for legacy tests."""
    
    def __init__(self, config_data: Dict[str, Any], validate: bool = True):
        """Initialize configuration."""
        self._config = config_data.copy()
        if validate:
            self.validate()
    
    def validate(self) -> None:
        """Validate required fields."""
        required = ['workflow_type', 'matrix_path', 'output_directory']
        missing = [f for f in required if f not in self._config]
        if missing:
            raise ValidationError(f"Missing required fields: {missing}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self._config.copy()
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in configuration."""
        return key in self._config
    
    def __getitem__(self, key: str) -> Any:
        """Enable dictionary-style access."""
        return self._config[key]