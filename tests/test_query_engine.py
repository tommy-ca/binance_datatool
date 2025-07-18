"""Tests for DuckDB query engine functionality."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import tempfile
import os

import polars as pl
import duckdb

from src.crypto_lakehouse.utils.query_engine import (
    DuckDBQueryEngine,
    QueryConfig,
    QueryResult,
    create_query_engine
)
from src.crypto_lakehouse.core.config import Settings, S3Config, StorageConfig


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        s3=S3Config(
            enabled=False,
            bucket="test-bucket",
            region="us-east-1",
            access_key_id="test-key",
            secret_access_key="test-secret"
        ),
        storage=StorageConfig(
            local_path="/tmp/test-lakehouse"
        )
    )


@pytest.fixture
def query_config():
    """Create basic query configuration."""
    return QueryConfig(
        memory_limit="500MB",
        threads=2,
        enable_s3=False,
        enable_parquet=True
    )


@pytest.fixture
def temp_parquet_file():
    """Create temporary Parquet file for testing."""
    # Create sample data
    data = pl.DataFrame({
        "symbol": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
        "open_time": [datetime(2023, 1, 1, 0, 0), datetime(2023, 1, 1, 1, 0), datetime(2023, 1, 1, 2, 0)],
        "close_time": [datetime(2023, 1, 1, 0, 59), datetime(2023, 1, 1, 1, 59), datetime(2023, 1, 1, 2, 59)],
        "open_price": [100.0, 200.0, 0.5],
        "close_price": [101.0, 201.0, 0.51],
        "volume": [1000.0, 2000.0, 3000.0]
    })
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        data.write_parquet(f.name)
        yield f.name
    
    # Cleanup
    os.unlink(f.name)


class TestQueryConfig:
    """Test QueryConfig validation."""
    
    def test_valid_config(self):
        """Test valid configuration creation."""
        config = QueryConfig(
            memory_limit="1GB",
            threads=4,
            enable_s3=True,
            enable_parquet=True
        )
        
        assert config.memory_limit == "1GB"
        assert config.threads == 4
        assert config.enable_s3 is True
        assert config.enable_parquet is True
    
    def test_invalid_memory_limit(self):
        """Test invalid memory limit validation."""
        with pytest.raises(ValueError, match="Memory limit must end with"):
            QueryConfig(memory_limit="invalid")
    
    def test_default_values(self):
        """Test default configuration values."""
        config = QueryConfig()
        
        assert config.memory_limit == "1GB"
        assert config.threads == 4
        assert config.enable_s3 is True
        assert config.enable_parquet is True
        assert config.temp_directory is None


class TestDuckDBQueryEngine:
    """Test DuckDBQueryEngine functionality."""
    
    def test_initialization(self, mock_settings, query_config):
        """Test query engine initialization."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            assert engine.settings == mock_settings
            assert engine.config == query_config
            assert engine.connection == mock_conn
            
            # Verify DuckDB connection was created
            mock_connect.assert_called_once_with(":memory:")
    
    def test_extension_setup(self, mock_settings, query_config):
        """Test DuckDB extension setup."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            # Verify parquet extension was loaded
            mock_conn.execute.assert_any_call("INSTALL parquet")
            mock_conn.execute.assert_any_call("LOAD parquet")
    
    def test_settings_configuration(self, mock_settings, query_config):
        """Test DuckDB settings configuration."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            # Verify settings were configured
            mock_conn.execute.assert_any_call("SET memory_limit='500MB'")
            mock_conn.execute.assert_any_call("SET threads=2")
    
    def test_execute_query_success(self, mock_settings, query_config):
        """Test successful query execution."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            # Mock query result
            mock_conn.execute.return_value.fetchall.return_value = [
                ("BTCUSDT", 100.0, 101.0),
                ("ETHUSDT", 200.0, 201.0)
            ]
            mock_conn.description = [("symbol",), ("open_price",), ("close_price",)]
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            result = engine.execute_query("SELECT * FROM test_table")
            
            assert isinstance(result, QueryResult)
            assert result.success is True
            assert result.row_count == 2
            assert result.column_count == 3
            assert result.error_message is None
    
    def test_execute_query_failure(self, mock_settings, query_config):
        """Test failed query execution."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            # Mock query failure
            mock_conn.execute.side_effect = Exception("Query failed")
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            result = engine.execute_query("INVALID SQL")
            
            assert isinstance(result, QueryResult)
            assert result.success is False
            assert result.row_count == 0
            assert result.column_count == 0
            assert "Query failed" in result.error_message
    
    def test_query_to_polars(self, mock_settings, query_config):
        """Test query result conversion to Polars DataFrame."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            # Mock query result
            mock_conn.execute.return_value.fetchall.return_value = [
                ("BTCUSDT", 100.0),
                ("ETHUSDT", 200.0)
            ]
            mock_conn.description = [("symbol",), ("price",)]
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            df = engine.query_to_polars("SELECT * FROM test_table")
            
            assert isinstance(df, pl.DataFrame)
            assert df.shape == (2, 2)
            assert df.columns == ["symbol", "price"]
    
    def test_query_to_dict(self, mock_settings, query_config):
        """Test query result conversion to dictionary."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            # Mock query result
            mock_conn.execute.return_value.fetchall.return_value = [
                ("BTCUSDT", 100.0),
                ("ETHUSDT", 200.0)
            ]
            mock_conn.description = [("symbol",), ("price",)]
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            result = engine.query_to_dict("SELECT * FROM test_table")
            
            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0] == {"symbol": "BTCUSDT", "price": 100.0}
            assert result[1] == {"symbol": "ETHUSDT", "price": 200.0}
    
    def test_get_table_info(self, mock_settings, query_config):
        """Test getting table information."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            # Mock DESCRIBE result
            mock_conn.execute.return_value.fetchall.side_effect = [
                [("symbol", "VARCHAR", "YES", None, None, None)],
                [(1000,)]
            ]
            mock_conn.description = [("column_name",), ("data_type",), ("null",), ("key",), ("default",), ("extra",)]
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            info = engine.get_table_info("test_table")
            
            assert info["table_name"] == "test_table"
            assert info["row_count"] == 1000
            assert info["column_count"] == 1
            assert len(info["schema"]) == 1
    
    def test_list_tables(self, mock_settings, query_config):
        """Test listing available tables."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            # Mock SHOW TABLES result
            mock_conn.execute.return_value.fetchall.return_value = [
                ("bronze_data",),
                ("silver_data",),
                ("gold_data",)
            ]
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            
            tables = engine.list_tables()
            
            assert tables == ["bronze_data", "silver_data", "gold_data"]
    
    def test_close_connection(self, mock_settings, query_config):
        """Test closing the connection."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            engine = DuckDBQueryEngine(mock_settings, query_config)
            engine.close()
            
            mock_conn.close.assert_called_once()
    
    def test_context_manager(self, mock_settings, query_config):
        """Test context manager functionality."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            with DuckDBQueryEngine(mock_settings, query_config) as engine:
                assert engine.connection == mock_conn
            
            mock_conn.close.assert_called_once()


class TestQueryEngineIntegration:
    """Integration tests with real DuckDB (if available)."""
    
    @pytest.mark.skipif(not duckdb, reason="DuckDB not available")
    def test_real_duckdb_query(self, mock_settings, query_config, temp_parquet_file):
        """Test with real DuckDB connection."""
        # Use real DuckDB for integration test
        engine = DuckDBQueryEngine(mock_settings, query_config)
        
        try:
            # Create a simple table
            engine.connection.execute("""
                CREATE TABLE test_data AS
                SELECT * FROM read_parquet($1)
            """, [temp_parquet_file])
            
            # Query the table
            result = engine.execute_query("SELECT COUNT(*) FROM test_data")
            
            assert result.success is True
            assert result.row_count == 1
            
            # Query as Polars DataFrame
            df = engine.query_to_polars("SELECT * FROM test_data ORDER BY symbol")
            
            assert isinstance(df, pl.DataFrame)
            assert df.shape[0] == 3  # 3 rows
            assert "symbol" in df.columns
            
        finally:
            engine.close()
    
    @pytest.mark.skipif(not duckdb, reason="DuckDB not available")
    def test_parquet_reading(self, mock_settings, query_config, temp_parquet_file):
        """Test reading Parquet files directly."""
        engine = DuckDBQueryEngine(mock_settings, query_config)
        
        try:
            # Read Parquet file directly
            df = engine.query_to_polars(f"SELECT * FROM read_parquet('{temp_parquet_file}')")
            
            assert isinstance(df, pl.DataFrame)
            assert df.shape[0] == 3
            assert "symbol" in df.columns
            
        finally:
            engine.close()


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_query_engine(self, mock_settings, query_config):
        """Test create_query_engine function."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            engine = create_query_engine(mock_settings, query_config)
            
            assert isinstance(engine, DuckDBQueryEngine)
            assert engine.settings == mock_settings
            assert engine.config == query_config
    
    def test_create_query_engine_default_config(self, mock_settings):
        """Test create_query_engine with default config."""
        with patch('duckdb.connect') as mock_connect:
            mock_conn = Mock()
            mock_connect.return_value = mock_conn
            
            engine = create_query_engine(mock_settings)
            
            assert isinstance(engine, DuckDBQueryEngine)
            assert engine.settings == mock_settings
            assert engine.config is not None