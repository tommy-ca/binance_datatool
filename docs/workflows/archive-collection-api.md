# Archive Collection API Reference

**Version**: 2.0  
**Last Updated**: July 19, 2025

## Overview

This document provides detailed API reference for the Enhanced Archive Collection Workflow, including all classes, methods, configuration options, and integration patterns.

## Core Classes

### `PrefectArchiveCollectionWorkflow`

**Module**: `src.crypto_lakehouse.workflows.archive_collection_prefect`

Main workflow class that orchestrates archive collection using Prefect for enhanced observability and error handling.

#### Constructor

```python
def __init__(
    self, 
    config: WorkflowConfig, 
    metrics_collector: Optional[MetricsCollector] = None
)
```

**Parameters:**
- `config` (WorkflowConfig): Type-safe configuration object
- `metrics_collector` (MetricsCollector, optional): Metrics collection interface

**Example:**
```python
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from src.crypto_lakehouse.core.config import WorkflowConfig

config = WorkflowConfig({
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/data",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT"],
    "data_types": ["klines"]
})

workflow = PrefectArchiveCollectionWorkflow(config)
```

#### Methods

##### `execute(**kwargs) -> Dict[str, Any]`

Execute the complete archive collection workflow.

**Returns:**
```python
{
    "status": "success",
    "metadata": IngestionMetadata,
    "collection_stats": {
        "total_tasks": int,
        "successful_tasks": int, 
        "failed_tasks": int,
        "skipped_tasks": int,
        "total_size_bytes": int,
        "processing_time_seconds": float
    },
    "success_rate": float,
    "total_size_formatted": str,
    "output_directory": str,
    "storage_zones_used": List[str],
    "ingestion_metadata_id": str
}
```

**Example:**
```python
result = await workflow.execute()
print(f"Success rate: {result['success_rate']:.1f}%")
print(f"Total size: {result['total_size_formatted']}")
```

##### `get_flow_config() -> Dict[str, Any]`

Get Prefect flow configuration settings.

**Returns:**
```python
{
    "name": "archive-collection-flow",
    "description": str,
    "tags": List[str],
    "version": str,
    "task_runner": ConcurrentTaskRunner,
    "retries": int,
    "retry_delay_seconds": int
}
```

### `WorkflowConfig`

**Module**: `src.crypto_lakehouse.core.config`

Type-safe configuration management with validation.

#### Constructor

```python
def __init__(self, config_dict: Dict[str, Any])
```

**Required Fields:**
- `workflow_type` (str): Must be "archive_collection"
- `matrix_path` (str): Path to enhanced matrix file
- `output_directory` (str): Base output directory  
- `markets` (List[str]): Markets to collect from
- `symbols` (Union[List[str], Dict[str, List[str]]]): Symbols configuration
- `data_types` (List[str]): Data types to collect

**Optional Fields:**
- `intervals` (Dict[str, List[str]]): Intervals per data type
- `date_range` (Dict[str, str]): Date range configuration
- `batch_size` (int): Files per batch (default: 100)
- `max_parallel_downloads` (int): Concurrent downloads (default: 8)
- `enable_batch_mode` (bool): Use s5cmd batch mode (default: true)
- `enable_resume` (bool): Skip existing files (default: true)
- `download_checksum` (bool): Verify checksums (default: true)
- `timeout_seconds` (int): Download timeout (default: 300)
- `force_redownload` (bool): Overwrite existing files (default: false)

#### Methods

##### `get(key: str, default: Any = None) -> Any`

Get configuration value with optional default.

##### `to_dict() -> Dict[str, Any]`

Convert configuration to dictionary.

## Core Functions

### `archive_collection_flow`

**Module**: `src.crypto_lakehouse.workflows.archive_collection_prefect`

Main Prefect flow function for orchestrated execution.

```python
@flow(
    name="archive-collection-flow",
    task_runner=ConcurrentTaskRunner(),
    retries=1,
    retry_delay_seconds=300
)
async def archive_collection_flow(
    config: WorkflowConfig,
    metrics_collector: Optional[MetricsCollector] = None
) -> Dict[str, Any]
```

**Parameters:**
- `config` (WorkflowConfig): Validated configuration
- `metrics_collector` (MetricsCollector, optional): Metrics interface

**Returns:** Same as `PrefectArchiveCollectionWorkflow.execute()`

## Task Functions

### Configuration Tasks

#### `validate_archive_configuration_task`

```python
@task(retries=3, retry_delay_seconds=60)
async def validate_archive_configuration_task(config: WorkflowConfig) -> bool
```

Validates configuration parameters including:
- Required field presence
- Matrix file existence
- Enum value validation (markets, data types)
- Environment-specific constraints

**Raises:**
- `ConfigurationError`: Invalid configuration parameters

#### `load_archive_matrix_task`

```python
@task(retries=2, retry_delay_seconds=30)
async def load_archive_matrix_task(config: WorkflowConfig) -> Dict[str, Any]
```

Loads and validates the enhanced archive matrix file.

**Returns:**
```python
{
    "availability_matrix": [
        {
            "market": str,
            "data_type": str,
            "intervals": List[str],
            "partitions": List[str],
            "url_pattern": str,
            "filename_pattern": str
        }
    ],
    "symbols": Dict[str, List[str]],
    "metadata": Dict[str, Any]
}
```

### Task Generation

#### `generate_ingestion_tasks_task`

```python
@task(retries=1, retry_delay_seconds=30)
async def generate_ingestion_tasks_task(
    config: WorkflowConfig, 
    archive_matrix: Dict[str, Any]
) -> List[DataIngestionTask]
```

Generates type-safe ingestion tasks from the archive matrix.

**Process:**
1. Map matrix entries to system enums
2. Apply configuration filters (markets, data types, symbols)
3. Generate tasks for each combination (symbol, interval, date)
4. Add archive-specific metadata for URL generation

**Returns:** List of `DataIngestionTask` objects with enhanced metadata

### Download Tasks

#### `execute_batch_downloads_task`

```python
@task(retries=3, retry_delay_seconds=60)
async def execute_batch_downloads_task(
    tasks: List[DataIngestionTask],
    bulk_downloader: BulkDownloader,
    storage: BaseStorage,
    config: WorkflowConfig
) -> List[Dict[str, Any]]
```

Execute downloads using enhanced s5cmd batch capabilities.

**Features:**
- Automatic batch mode detection
- Fallback to individual downloads with concurrency control
- Comprehensive error handling and retry logic
- Progress tracking and metadata collection

**Returns:**
```python
[
    {
        "status": "success" | "failed" | "skipped" | "error",
        "task": DataIngestionTask,
        "target_path": str,
        "file_size": int,
        "source_url": str,
        "cached": bool,
        "error": str  # Only for failed/error status
    }
]
```

#### `download_archive_file_task`

```python
@task(retries=3, retry_delay_seconds=60)
async def download_archive_file_task(
    task: DataIngestionTask,
    bulk_downloader: BulkDownloader,
    storage: BaseStorage,
    config: WorkflowConfig
) -> Dict[str, Any]
```

Download individual archive file with comprehensive error handling.

### Metadata Tasks

#### `create_collection_metadata_task`

```python
@task(retries=2, retry_delay_seconds=30)
async def create_collection_metadata_task(config: WorkflowConfig) -> IngestionMetadata
```

Initialize collection metadata tracking.

#### `update_collection_metadata_task`

```python
@task(retries=1, retry_delay_seconds=10)
async def update_collection_metadata_task(
    metadata: IngestionMetadata,
    status: str,
    results: Optional[List[Dict[str, Any]]] = None,
    errors: Optional[List[str]] = None
) -> IngestionMetadata
```

Update collection metadata with final results.

#### `persist_collection_metadata_task`

```python
@task(retries=2, retry_delay_seconds=30)
async def persist_collection_metadata_task(
    metadata: IngestionMetadata,
    storage: BaseStorage
) -> bool
```

Persist collection metadata using storage interface.

## Data Models

### `DataIngestionTask`

**Module**: `src.crypto_lakehouse.core.models`

Type-safe task definition for data ingestion workflows.

```python
class DataIngestionTask(BaseModel):
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
    
    # Enhanced metadata (added by workflow)
    partition_type: Optional[str] = None
    archive_date: Optional[str] = None
    matrix_entry: Optional[Dict[str, Any]] = None
    original_data_type: Optional[str] = None
    url_pattern: Optional[str] = None
    filename_pattern: Optional[str] = None
```

### `IngestionMetadata`

**Module**: `src.crypto_lakehouse.core.models`

Metadata for tracking ingestion progress.

```python
class IngestionMetadata(BaseModel):
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
```

## Enums

### `DataType`

**Module**: `src.crypto_lakehouse.core.models`

```python
class DataType(str, Enum):
    KLINES = "klines"
    FUNDING_RATES = "funding_rates"
    LIQUIDATIONS = "liquidations"
    ORDER_BOOK = "order_book"
    TRADES = "trades"
    TICKER = "ticker"
    METRICS = "metrics"
    VOLATILITY = "volatility"
    SUMMARY = "summary"
```

### `TradeType`

```python
class TradeType(str, Enum):
    SPOT = "spot"
    UM_FUTURES = "um_futures"
    CM_FUTURES = "cm_futures"
    OPTIONS = "options"
```

### `Exchange`

```python
class Exchange(str, Enum):
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
```

### `DataZone`

```python
class DataZone(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
```

### `Interval`

```python
class Interval(str, Enum):
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
```

## Helper Functions

### URL Generation

#### `_generate_task_paths`

```python
async def _generate_task_paths(
    task: DataIngestionTask, 
    storage: BaseStorage, 
    config: WorkflowConfig
) -> tuple[str, Path]
```

Generate source URL and target path using storage interface.

**Features:**
- Matrix-driven URL pattern support
- Fallback to legacy URL generation
- Storage interface integration
- Enhanced data type mapping

### Data Type Mapping

#### `_map_matrix_data_type`

```python
def _map_matrix_data_type(matrix_data_type: str) -> Optional[DataType]
```

Map archive matrix data type to system DataType enum.

**Mappings:**
```python
{
    'klines': DataType.KLINES,
    'trades': DataType.TRADES,
    'aggTrades': DataType.TRADES,
    'fundingRate': DataType.FUNDING_RATES,
    'liquidationSnapshot': DataType.LIQUIDATIONS,
    'bookDepth': DataType.ORDER_BOOK,
    'bookTicker': DataType.TICKER,
    'indexPriceKlines': DataType.KLINES,
    'markPriceKlines': DataType.KLINES,
    'premiumIndex': DataType.FUNDING_RATES,
    'metrics': DataType.METRICS,
    'BVOLIndex': DataType.VOLATILITY,
    'EOHSummary': DataType.SUMMARY
}
```

### Utility Functions

#### `_format_bytes`

```python
def _format_bytes(size_bytes: int) -> str
```

Format file size in human readable format.

#### `_is_valid_interval`

```python
def _is_valid_interval(interval: str) -> bool
```

Check if interval is valid system Interval enum.

#### `_get_date_list`

```python
def _get_date_list(config: WorkflowConfig) -> List[str]
```

Get list of dates to collect based on configuration.

## Configuration Schema

### Enhanced Matrix Format

```json
{
    "availability_matrix": [
        {
            "market": "spot",
            "data_type": "klines",
            "intervals": ["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"],
            "partitions": ["daily", "monthly"],
            "url_pattern": "s3://data.binance.vision/data/spot/{partition}/klines/{symbol}/{interval}/{filename}",
            "filename_pattern": "{symbol}-{interval}-{date}.zip"
        }
    ],
    "symbols": {
        "spot": ["BTCUSDT", "ETHUSDT"],
        "futures_um": ["BTCUSDT", "ETHUSDT"],
        "futures_cm": ["BTCUSD_PERP"],
        "options": ["BTC", "ETH"]
    },
    "metadata": {
        "version": "2.0",
        "total_data_types": 28,
        "markets_supported": 4,
        "last_updated": "2025-07-19"
    }
}
```

### Workflow Configuration Schema

```json
{
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/data",
    
    "markets": ["spot", "futures_um", "futures_cm", "options"],
    "symbols": {
        "spot": ["BTCUSDT", "ETHUSDT"],
        "futures_um": ["BTCUSDT", "ETHUSDT"],
        "futures_cm": ["BTCUSD_PERP"],
        "options": ["BTC"]
    },
    "data_types": ["klines", "trades", "fundingRate", "BVOLIndex"],
    "intervals": {
        "klines": ["1m", "1h", "1d"],
        "BVOLIndex": ["1h", "1d"]
    },
    
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    },
    
    "batch_size": 100,
    "max_parallel_downloads": 8,
    "enable_batch_mode": true,
    "enable_resume": true,
    "download_checksum": true,
    "timeout_seconds": 300,
    "force_redownload": false,
    
    "s5cmd_extra_args": ["--no-sign-request", "--retry-count=3"],
    "part_size_mb": 50,
    
    "environment": "production",
    "enable_monitoring": true,
    "local_data_dir": "output/data",
    "logging": {"level": "INFO"}
}
```

## Error Handling

### Exception Types

#### `ConfigurationError`

**Module**: `src.crypto_lakehouse.core.exceptions`

Raised for invalid configuration parameters.

#### `WorkflowError`

**Module**: `src.crypto_lakehouse.core.exceptions`

Raised for workflow execution failures.

### Error Response Format

```python
{
    "status": "failed",
    "error": str,
    "metadata": IngestionMetadata,
    "partial_results": List[Dict[str, Any]]  # Optional
}
```

### Common Error Scenarios

#### Configuration Validation Errors
```python
ConfigurationError("Missing required configuration: ['matrix_path']")
ConfigurationError("Invalid markets in configuration: 'invalid_market' is not a valid market type")
ConfigurationError("Archive matrix file not found: missing_matrix.json")
```

#### Workflow Execution Errors
```python
WorkflowError("Failed to load archive matrix: File not found")
WorkflowError("Archive collection failed: Download timeout")
```

## Integration Examples

### Custom Storage Integration

```python
from src.crypto_lakehouse.storage.base import BaseStorage
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow

class CustomStorage(BaseStorage):
    def get_partition_path(self, **kwargs):
        # Custom path logic
        pass

# Use with workflow
config = WorkflowConfig({...})
workflow = PrefectArchiveCollectionWorkflow(config)
workflow.storage = CustomStorage(settings)
```

### Custom Metrics Integration

```python
from src.crypto_lakehouse.core.metrics import MetricsCollector

class CustomMetrics(MetricsCollector):
    def record_event(self, event_name: str, **kwargs):
        # Custom metrics logic
        pass

# Use with workflow
metrics = CustomMetrics()
workflow = PrefectArchiveCollectionWorkflow(config, metrics)
```

### Batch Processing Integration

```python
from src.crypto_lakehouse.ingestion.bulk_downloader import BulkDownloader

# Custom downloader configuration
downloader_config = {
    'batch_size': 200,  # Larger batches
    'max_concurrent': 16,  # More concurrency
    'enable_batch_mode': True,
    's5cmd_extra_args': ['--no-sign-request', '--numworkers=16']
}

bulk_downloader = BulkDownloader(downloader_config)
```

## Performance Tuning

### Optimal Configuration

```python
# High-performance configuration
config = {
    "batch_size": 100,
    "max_parallel_downloads": 8,
    "enable_batch_mode": True,
    "enable_resume": True,
    "part_size_mb": 50,
    "s5cmd_extra_args": [
        "--no-sign-request",
        "--retry-count=3",
        "--numworkers=8"
    ]
}
```

### Memory Management

```python
# For large collections
config = {
    "batch_size": 50,  # Smaller batches
    "max_parallel_downloads": 4,  # Less concurrency
    "timeout_seconds": 600  # Longer timeout
}
```

### Network Optimization

```python
# For unstable networks
config = {
    "enable_resume": True,
    "download_checksum": True,
    "s5cmd_extra_args": [
        "--no-sign-request",
        "--retry-count=5",
        "--part-size=100MB"
    ]
}
```

---

This API reference provides comprehensive documentation for integrating and extending the Enhanced Archive Collection Workflow.