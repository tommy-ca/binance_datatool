"""
Simple configuration management for crypto lakehouse workflows.
"""

from typing import Dict, Any, Optional
from .exceptions import ValidationError


class Settings:
    """System settings for storage and configuration."""
    
    def __init__(self, config_data: Optional[Dict[str, Any]] = None):
        """Initialize settings from configuration data."""
        self._config = config_data or {}
        
        # Storage configuration
        self.is_cloud_enabled = self._config.get('use_cloud_storage', False)
        self.local_data_dir = self._config.get('output_directory', 'output')
        
        # AWS/S3 configuration
        self.aws_access_key_id = self._config.get('aws_access_key_id')
        self.aws_secret_access_key = self._config.get('aws_secret_access_key')
        self.s3_bucket = self._config.get('s3_bucket')
        self.s3_region = self._config.get('s3_region', 'us-east-1')
        
        # Binance configuration  
        self.binance = BinanceSettings(self._config.get('binance', {}))


class BinanceSettings:
    """Binance-specific settings."""
    
    def __init__(self, config_data: Dict[str, Any]):
        """Initialize Binance settings."""
        self.api_key = config_data.get('api_key')
        self.api_secret = config_data.get('api_secret')
        self.base_url = config_data.get('base_url', 'https://api.binance.com')
        self.testnet = config_data.get('testnet', False)
        self.timeout = config_data.get('timeout', 30)


class WorkflowConfig:
    """Simple workflow configuration class."""
    
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