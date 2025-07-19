"""
DuckDB query engine for fast analytical queries on lakehouse data.

This module provides a high-performance query interface for the data lakehouse,
allowing SQL queries on Parquet files stored in S3 or local storage.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import duckdb
import polars as pl
from pydantic import BaseModel, Field, validator

from ..core.config import Settings

logger = logging.getLogger(__name__)


class QueryConfig(BaseModel):
    """Configuration for DuckDB query engine."""

    memory_limit: str = Field(default="1GB", description="Memory limit for DuckDB")
    threads: int = Field(default=4, description="Number of threads for query execution")
    enable_s3: bool = Field(default=True, description="Enable S3 extension")
    enable_parquet: bool = Field(default=True, description="Enable Parquet extension")
    temp_directory: Optional[str] = Field(default=None, description="Temporary directory for spill")

    @validator("memory_limit")
    def validate_memory_limit(cls, v):
        """Validate memory limit format."""
        if not v.endswith(("KB", "MB", "GB", "TB")):
            raise ValueError("Memory limit must end with KB, MB, GB, or TB")
        return v


class QueryResult(BaseModel):
    """Result of a DuckDB query execution."""

    query: str
    execution_time_ms: int
    row_count: int
    column_count: int
    success: bool
    error_message: Optional[str] = None


class DuckDBQueryEngine:
    """
    High-performance query engine using DuckDB for analytical queries.

    Provides SQL interface to query Parquet files in the data lakehouse,
    with automatic schema discovery and optimized query execution.
    """

    def __init__(self, settings: Settings, config: Optional[QueryConfig] = None):
        self.settings = settings
        self.config = config or QueryConfig()
        self.logger = logging.getLogger(f"{__name__}.DuckDBQueryEngine")

        # Initialize DuckDB connection
        self.connection = self._initialize_connection()

        # Setup extensions and configuration
        self._setup_extensions()
        self._configure_settings()

        # Register views for data lakehouse layers
        self._register_lakehouse_views()

    def _initialize_connection(self) -> duckdb.DuckDBPyConnection:
        """Initialize DuckDB connection."""
        try:
            # Use in-memory database for performance
            conn = duckdb.connect(":memory:")
            self.logger.info("DuckDB connection initialized successfully")
            return conn
        except Exception as e:
            self.logger.error(f"Failed to initialize DuckDB connection: {e}")
            raise

    def _setup_extensions(self):
        """Setup required DuckDB extensions."""
        extensions = []

        if self.config.enable_s3:
            extensions.append("httpfs")  # For S3 access

        if self.config.enable_parquet:
            extensions.append("parquet")  # For Parquet support

        for ext in extensions:
            try:
                self.connection.execute(f"INSTALL {ext}")
                self.connection.execute(f"LOAD {ext}")
                self.logger.info(f"Loaded DuckDB extension: {ext}")
            except Exception as e:
                self.logger.warning(f"Failed to load extension {ext}: {e}")

    def _configure_settings(self):
        """Configure DuckDB settings."""
        try:
            # Set memory limit
            self.connection.execute(f"SET memory_limit='{self.config.memory_limit}'")

            # Set thread count
            self.connection.execute(f"SET threads={self.config.threads}")

            # Set temporary directory if specified
            if self.config.temp_directory:
                self.connection.execute(f"SET temp_directory='{self.config.temp_directory}'")

            # Configure S3 settings if enabled
            if self.config.enable_s3 and self.settings.s3.enabled:
                self.connection.execute(f"SET s3_region='{self.settings.s3.region}'")

                # Set S3 credentials if available
                if self.settings.s3.access_key_id and self.settings.s3.secret_access_key:
                    self.connection.execute(
                        f"SET s3_access_key_id='{self.settings.s3.access_key_id}'"
                    )
                    self.connection.execute(
                        f"SET s3_secret_access_key='{self.settings.s3.secret_access_key}'"
                    )

                # Set S3 endpoint if specified
                if self.settings.s3.endpoint_url:
                    self.connection.execute(f"SET s3_endpoint='{self.settings.s3.endpoint_url}'")

            self.logger.info("DuckDB settings configured successfully")

        except Exception as e:
            self.logger.error(f"Failed to configure DuckDB settings: {e}")
            raise

    def _register_lakehouse_views(self):
        """Register views for data lakehouse layers."""
        try:
            # Bronze layer (raw data)
            if self.settings.s3.enabled:
                bronze_path = f"s3://{self.settings.s3.bucket}/bronze/**/*.parquet"
            else:
                bronze_path = f"{self.settings.storage.local_path}/bronze/**/*.parquet"

            # Silver layer (processed data)
            if self.settings.s3.enabled:
                silver_path = f"s3://{self.settings.s3.bucket}/silver/**/*.parquet"
            else:
                silver_path = f"{self.settings.storage.local_path}/silver/**/*.parquet"

            # Gold layer (aggregated data)
            if self.settings.s3.enabled:
                gold_path = f"s3://{self.settings.s3.bucket}/gold/**/*.parquet"
            else:
                gold_path = f"{self.settings.storage.local_path}/gold/**/*.parquet"

            # Create views for each layer
            self.connection.execute(
                f"""
                CREATE OR REPLACE VIEW bronze_data AS
                SELECT * FROM read_parquet('{bronze_path}')
            """
            )

            self.connection.execute(
                f"""
                CREATE OR REPLACE VIEW silver_data AS
                SELECT * FROM read_parquet('{silver_path}')
            """
            )

            self.connection.execute(
                f"""
                CREATE OR REPLACE VIEW gold_data AS
                SELECT * FROM read_parquet('{gold_path}')
            """
            )

            self.logger.info("Lakehouse views registered successfully")

        except Exception as e:
            self.logger.warning(f"Failed to register lakehouse views: {e}")

    def execute_query(self, query: str) -> QueryResult:
        """
        Execute a SQL query and return results.

        Args:
            query: SQL query to execute

        Returns:
            QueryResult with execution metadata
        """
        start_time = datetime.now()

        try:
            # Execute query
            result = self.connection.execute(query).fetchall()

            # Get column information
            columns = (
                [desc[0] for desc in self.connection.description]
                if self.connection.description
                else []
            )

            # Calculate metrics
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            row_count = len(result)
            column_count = len(columns)

            self.logger.info(f"Query executed successfully: {row_count} rows, {execution_time}ms")

            return QueryResult(
                query=query,
                execution_time_ms=execution_time,
                row_count=row_count,
                column_count=column_count,
                success=True,
            )

        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error(f"Query execution failed: {e}")

            return QueryResult(
                query=query,
                execution_time_ms=execution_time,
                row_count=0,
                column_count=0,
                success=False,
                error_message=str(e),
            )

    def query_to_polars(self, query: str) -> pl.DataFrame:
        """
        Execute query and return results as Polars DataFrame.

        Args:
            query: SQL query to execute

        Returns:
            Polars DataFrame with query results
        """
        try:
            # Execute query and get results
            result = self.connection.execute(query).fetchall()
            columns = (
                [desc[0] for desc in self.connection.description]
                if self.connection.description
                else []
            )

            # Convert to Polars DataFrame
            if result and columns:
                return pl.DataFrame(result, schema=columns)
            else:
                return pl.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to convert query results to Polars: {e}")
            raise

    def query_to_dict(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute query and return results as list of dictionaries.

        Args:
            query: SQL query to execute

        Returns:
            List of dictionaries with query results
        """
        try:
            # Execute query and get results
            result = self.connection.execute(query).fetchall()
            columns = (
                [desc[0] for desc in self.connection.description]
                if self.connection.description
                else []
            )

            # Convert to list of dictionaries
            if result and columns:
                return [dict(zip(columns, row)) for row in result]
            else:
                return []

        except Exception as e:
            self.logger.error(f"Failed to convert query results to dictionary: {e}")
            raise

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Get information about a table or view.

        Args:
            table_name: Name of the table or view

        Returns:
            Dictionary with table information
        """
        try:
            # Get table schema
            schema_result = self.connection.execute(f"DESCRIBE {table_name}").fetchall()
            columns = [desc[0] for desc in self.connection.description]

            schema = [dict(zip(columns, row)) for row in schema_result]

            # Get row count
            count_result = self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0

            return {
                "table_name": table_name,
                "schema": schema,
                "row_count": row_count,
                "column_count": len(schema),
            }

        except Exception as e:
            self.logger.error(f"Failed to get table info for {table_name}: {e}")
            raise

    def list_tables(self) -> List[str]:
        """
        List all available tables and views.

        Returns:
            List of table names
        """
        try:
            result = self.connection.execute("SHOW TABLES").fetchall()
            return [row[0] for row in result]

        except Exception as e:
            self.logger.error(f"Failed to list tables: {e}")
            return []

    def query_kline_data(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> pl.DataFrame:
        """
        Query K-line data with filters.

        Args:
            symbol: Trading symbol
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of records

        Returns:
            Polars DataFrame with K-line data
        """
        query = "SELECT * FROM silver_data WHERE symbol = $1"
        params = [symbol]

        if start_time:
            query += " AND open_time >= $2"
            params.append(start_time)

        if end_time:
            query += " AND open_time <= $3"
            params.append(end_time)

        query += " ORDER BY open_time"

        if limit:
            query += f" LIMIT {limit}"

        try:
            result = self.connection.execute(query, params).fetchall()
            columns = (
                [desc[0] for desc in self.connection.description]
                if self.connection.description
                else []
            )

            if result and columns:
                return pl.DataFrame(result, schema=columns)
            else:
                return pl.DataFrame()

        except Exception as e:
            self.logger.error(f"Failed to query K-line data: {e}")
            raise

    def close(self):
        """Close DuckDB connection."""
        try:
            if self.connection:
                self.connection.close()
                self.logger.info("DuckDB connection closed")
        except Exception as e:
            self.logger.error(f"Failed to close DuckDB connection: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_query_engine(
    settings: Settings, config: Optional[QueryConfig] = None
) -> DuckDBQueryEngine:
    """
    Create a DuckDB query engine instance.

    Args:
        settings: Application settings
        config: Optional query configuration

    Returns:
        DuckDBQueryEngine instance
    """
    return DuckDBQueryEngine(settings, config)
