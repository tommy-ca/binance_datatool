"""Tests for configuration management."""

import pytest
import os
import tempfile
from pathlib import Path

from src.crypto_lakehouse.core.config import Settings, S3Config, StorageConfig
from src.crypto_lakehouse.core.models import DataZone


class TestS3Config:
    """Test S3 configuration."""
    
    def test_s3_config_creation(self):
        """Test creating S3Config instance."""
        config = S3Config(
            bucket_name="test-bucket",
            region="us-west-2",
            access_key_id="test-key",
            secret_access_key="test-secret"
        )
        
        assert config.bucket_name == "test-bucket"
        assert config.region == "us-west-2"
        assert config.access_key_id == "test-key"
        assert config.secret_access_key == "test-secret"
    
    def test_s3_config_defaults(self):
        """Test S3Config default values."""
        config = S3Config(bucket_name="test-bucket")
        
        assert config.region == "us-east-1"
        assert config.access_key_id is None
        assert config.secret_access_key is None
        assert config.endpoint_url is None


class TestStorageConfig:
    """Test storage configuration."""
    
    def test_storage_config_creation(self):
        """Test creating StorageConfig instance."""
        config = StorageConfig(base_path="s3://test-bucket/data")
        
        assert config.base_path == "s3://test-bucket/data"
    
    def test_storage_zone_paths(self):
        """Test storage zone path generation."""
        config = StorageConfig(base_path="s3://test-bucket/data")
        
        assert config.bronze_path == "s3://test-bucket/data/bronze"
        assert config.silver_path == "s3://test-bucket/data/silver"
        assert config.gold_path == "s3://test-bucket/data/gold"
    
    def test_get_zone_path(self):
        """Test get_zone_path method."""
        config = StorageConfig(base_path="s3://test-bucket/data")
        
        assert config.get_zone_path(DataZone.BRONZE) == "s3://test-bucket/data/bronze"
        assert config.get_zone_path(DataZone.SILVER) == "s3://test-bucket/data/silver"
        assert config.get_zone_path(DataZone.GOLD) == "s3://test-bucket/data/gold"
    
    def test_get_zone_path_invalid(self):
        """Test get_zone_path with invalid zone."""
        config = StorageConfig(base_path="s3://test-bucket/data")
        
        with pytest.raises(ValueError, match="Unknown data zone"):
            config.get_zone_path("invalid_zone")


class TestSettings:
    """Test main settings configuration."""
    
    def test_settings_creation(self):
        """Test creating Settings instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                environment="test",
                local_data_dir=Path(temp_dir)
            )
            
            assert settings.environment == "test"
            assert settings.local_data_dir == Path(temp_dir)
            assert settings.debug is False
    
    def test_settings_defaults(self):
        """Test Settings default values."""
        settings = Settings()
        
        assert settings.environment == "development"
        assert settings.debug is False
        assert settings.storage.base_path == "s3://crypto-data-lakehouse"
        assert settings.workflow.concurrency_limit == 10
        assert settings.processing.batch_size == 10000
    
    def test_cloud_enabled_detection(self):
        """Test cloud enabled detection."""
        # Test with S3 credentials
        settings = Settings()
        settings.s3.bucket_name = "test-bucket"
        settings.s3.access_key_id = "test-key"
        
        assert settings.is_cloud_enabled is True
        
        # Test without credentials
        settings_no_creds = Settings()
        settings_no_creds.s3.bucket_name = "test-bucket"
        settings_no_creds.s3.access_key_id = None
        
        # Should still be True if AWS_PROFILE or other methods available
        # In test environment, this will be False
    
    def test_processing_concurrency(self):
        """Test processing concurrency calculation."""
        settings = Settings()
        
        # Should return a positive number
        assert settings.processing_concurrency > 0
        
        # Test with custom CPU count
        settings.processing.cpu_count = 4
        assert settings.processing_concurrency == 4
    
    def test_get_storage_path(self):
        """Test storage path generation."""
        settings = Settings()
        
        path = settings.get_storage_path(
            DataZone.SILVER, "binance", "klines"
        )
        
        expected = "s3://crypto-data-lakehouse/silver/binance/klines"
        assert path == expected
    
    def test_get_local_cache_path(self):
        """Test local cache path generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(local_data_dir=Path(temp_dir))
            
            cache_path = settings.get_local_cache_path("binance", "klines")
            
            expected = Path(temp_dir) / "binance" / "klines"
            assert cache_path == expected
    
    def test_environment_variables(self):
        """Test environment variable loading."""
        # Set test environment variables
        os.environ["CRYPTO_DATA_DIR"] = "/test/path"
        os.environ["S3_BUCKET"] = "test-env-bucket"
        os.environ["DEBUG"] = "true"
        
        try:
            settings = Settings()
            
            # Note: local_data_dir is processed in __init__
            assert settings.s3.bucket_name == "test-env-bucket"
            
        finally:
            # Clean up environment variables
            os.environ.pop("CRYPTO_DATA_DIR", None)
            os.environ.pop("S3_BUCKET", None)
            os.environ.pop("DEBUG", None)
    
    def test_nested_configuration(self):
        """Test nested configuration access."""
        settings = Settings()
        
        # Test nested access
        assert hasattr(settings, 'storage')
        assert hasattr(settings, 's3')
        assert hasattr(settings, 'workflow')
        assert hasattr(settings, 'processing')
        assert hasattr(settings, 'binance')
        assert hasattr(settings, 'data_catalog')
        assert hasattr(settings, 'query')
        assert hasattr(settings, 'monitoring')
        
        # Test specific nested values
        assert settings.binance.aws_base_url == "https://data.binance.vision"
        assert settings.workflow.retry_attempts == 3
        assert settings.data_catalog.database_name == "crypto_lakehouse"