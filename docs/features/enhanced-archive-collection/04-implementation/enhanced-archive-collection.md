# Enhanced Archive Collection Workflow

**Version**: 2.0  
**Status**: Production Ready ✅  
**Last Updated**: July 19, 2025

## Overview

The Enhanced Archive Collection Workflow provides comprehensive access to all Binance public archive data across all markets with optimized s5cmd performance. This workflow supports **4 markets**, **28 data type combinations**, and advanced batch processing capabilities.

## Features

### Market Coverage
- ✅ **Spot Market** (`spot/`) - 5 data types + intervals
- ✅ **Futures UM** (`futures/um/`) - 10 data types + intervals  
- ✅ **Futures CM** (`futures/cm/`) - 9 data types + intervals
- ✅ **Options** (`option/`) - 2 data types + intervals

### Performance Enhancements
- **Batch Processing**: Up to 100 files per batch
- **Parallel Downloads**: 8 concurrent streams
- **Resume Capability**: Skip existing files
- **Checksum Validation**: Data integrity verification
- **Error Recovery**: Progressive retry with backoff

### Data Types Supported

#### Spot Market (5 data types)
- `klines` - Candlestick data (16 intervals: 1s to 1M)
- `trades` - Individual trade records
- `aggTrades` - Aggregated trade data
- `bookDepth` - Order book snapshots (6 intervals)
- `bookTicker` - Best bid/ask data

#### Futures UM (10 data types)
- `klines` - Candlestick data (16 intervals)
- `trades` - Individual trade records
- `aggTrades` - Aggregated trade data
- `fundingRate` - Funding rate data
- `premiumIndex` - Premium index data
- `metrics` - Open interest, long-short ratios
- `indexPriceKlines` - Index price klines (16 intervals)
- `markPriceKlines` - Mark price klines (16 intervals)
- `bookDepth` - Order book snapshots (6 intervals)
- `bookTicker` - Best bid/ask data
- `liquidationSnapshot` - Liquidation data

#### Futures CM (9 data types)
- `klines` - Candlestick data (16 intervals)
- `trades` - Individual trade records
- `aggTrades` - Aggregated trade data
- `fundingRate` - Funding rate data
- `premiumIndex` - Premium index data
- `indexPriceKlines` - Index price klines (16 intervals)
- `markPriceKlines` - Mark price klines (16 intervals)
- `bookDepth` - Order book snapshots (6 intervals)
- `bookTicker` - Best bid/ask data
- `liquidationSnapshot` - Liquidation data

#### Options (2 data types)
- `BVOLIndex` - Binance Volatility Index (4 intervals)
- `EOHSummary` - End of hour summary

## Quick Start

### Installation

Ensure you have the required dependencies:

```bash
# Install crypto lakehouse package
pip install -e .

# Install s5cmd for optimized downloads
# Download from: https://github.com/peak/s5cmd/releases
```

### Basic Usage

```python
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from src.crypto_lakehouse.core.config import WorkflowConfig

# Configure collection
config = WorkflowConfig({
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/archive_data",
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
    }
})

# Execute workflow
workflow = PrefectArchiveCollectionWorkflow(config)
result = await workflow.execute()
```

### Configuration Examples

#### Full Market Collection
```json
{
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/full_collection",
    "markets": ["spot", "futures_um", "futures_cm", "options"],
    "symbols": {
        "spot": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
        "futures_um": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
        "futures_cm": ["BTCUSD_PERP", "ETHUSD_PERP"],
        "options": ["BTC", "ETH"]
    },
    "data_types": ["klines", "trades", "fundingRate", "liquidationSnapshot", "BVOLIndex"],
    "intervals": {
        "klines": ["1m", "5m", "1h", "1d"],
        "indexPriceKlines": ["1h", "1d"],
        "markPriceKlines": ["1h", "1d"],
        "BVOLIndex": ["1h", "1d"],
        "bookDepth": ["100ms", "1000ms"]
    },
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    },
    "batch_size": 100,
    "max_parallel_downloads": 8,
    "enable_batch_mode": true,
    "enable_resume": true,
    "s5cmd_extra_args": ["--no-sign-request", "--retry-count=3"]
}
```

#### Market-Specific Collection
```json
{
    "workflow_type": "archive_collection", 
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/spot_only",
    "markets": ["spot"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": ["klines", "trades", "bookDepth"],
    "intervals": {
        "klines": ["1m", "1h"],
        "bookDepth": ["100ms"]
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    }
}
```

## Architecture

### Component Overview

```
Enhanced Archive Collection Workflow
├── Configuration Layer
│   ├── WorkflowConfig (type-safe configuration)
│   ├── Enhanced Matrix (28 data type definitions)
│   └── Symbol & Interval Filtering
├── Orchestration Layer (Prefect)
│   ├── validate_archive_configuration_task
│   ├── load_archive_matrix_task
│   ├── generate_ingestion_tasks_task
│   ├── execute_batch_downloads_task
│   └── persist_collection_metadata_task
├── Download Layer
│   ├── BulkDownloader (s5cmd integration)
│   ├── Batch Processing (100 files/batch)
│   └── Parallel Execution (8 concurrent)
└── Storage Layer
    ├── Lakehouse Integration (Bronze/Silver/Gold)
    ├── BaseStorage Interface
    └── Metadata Tracking
```

### Data Flow

1. **Configuration Validation** - Validate markets, data types, and symbols
2. **Matrix Loading** - Load enhanced data type matrix with URL patterns
3. **Task Generation** - Create type-safe ingestion tasks from matrix
4. **Batch Processing** - Group tasks for optimal s5cmd performance
5. **Parallel Execution** - Download files concurrently with error handling
6. **Metadata Persistence** - Track progress and results in lakehouse

### Storage Structure

```
output/
├── bronze/              # Raw archive data
│   ├── spot/
│   │   ├── klines/
│   │   ├── trades/
│   │   └── bookDepth/
│   ├── futures_um/
│   │   ├── klines/
│   │   ├── fundingRate/
│   │   └── liquidationSnapshot/
│   ├── futures_cm/
│   │   ├── klines/
│   │   └── fundingRate/
│   └── options/
│       ├── BVOLIndex/
│       └── EOHSummary/
├── silver/              # Processed data
└── gold/                # Analytics-ready data
```

## Performance Specifications

### Throughput Metrics
- **Batch Mode**: 100+ files per batch
- **Parallel Processing**: 8 concurrent downloads
- **Expected Speed**: 10-50 MB/s depending on file sizes
- **Resume Capability**: Skip existing files for incremental updates

### Scale Estimates
- **Daily Volume**: 3,134+ potential file combinations per day
- **Symbol Support**: 15+ symbols per market
- **Interval Coverage**: 16 intervals for kline data types
- **Partition Support**: Daily and monthly partitions

### Error Handling
- **Retry Logic**: 3 attempts with exponential backoff
- **Checksum Validation**: SHA256 verification (configurable)
- **Resume Support**: Skip existing valid files
- **Error Recovery**: Continue processing on individual failures

## Configuration Reference

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `workflow_type` | string | Must be "archive_collection" |
| `matrix_path` | string | Path to enhanced matrix file |
| `output_directory` | string | Base output directory |
| `markets` | array | Markets to collect from |
| `symbols` | object | Symbols per market |
| `data_types` | array | Data types to collect |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `intervals` | object | {} | Intervals per data type |
| `date_range` | object | single day | Date range to collect |
| `batch_size` | number | 100 | Files per batch |
| `max_parallel_downloads` | number | 8 | Concurrent downloads |
| `enable_batch_mode` | boolean | true | Use s5cmd batch mode |
| `enable_resume` | boolean | true | Skip existing files |
| `download_checksum` | boolean | true | Verify checksums |
| `timeout_seconds` | number | 300 | Download timeout |
| `force_redownload` | boolean | false | Overwrite existing files |

### s5cmd Configuration

```json
{
    "s5cmd_extra_args": [
        "--no-sign-request",
        "--retry-count=3",
        "--numworkers=8"
    ],
    "part_size_mb": 50,
    "enable_batch_mode": true,
    "enable_resume": true
}
```

## Integration Patterns

### Prefect Integration

```python
from prefect import flow
from src.crypto_lakehouse.workflows.archive_collection_prefect import archive_collection_flow

@flow(name="daily-archive-collection")
async def daily_collection():
    config = WorkflowConfig({
        # ... configuration
    })
    
    result = await archive_collection_flow(config)
    return result
```

### Storage Integration

```python
from src.crypto_lakehouse.storage.factory import create_storage
from src.crypto_lakehouse.core.config import Settings

# Create storage interface
settings = Settings({'local_data_dir': 'output/data'})
storage = create_storage(settings)

# Use with workflow
workflow = PrefectArchiveCollectionWorkflow(config)
workflow.storage = storage
```

### Metrics Integration

```python
from src.crypto_lakehouse.core.metrics import MetricsCollector

metrics = MetricsCollector()
workflow = PrefectArchiveCollectionWorkflow(config, metrics)
result = await workflow.execute()

# Metrics are automatically recorded
```

## Testing

### Core Functionality Tests

```bash
# Test core logic without Prefect
python test_core_functionality.py

# Test workflow components  
python test_enhanced_workflow_simple.py

# Test specific functionality
python -m pytest tests/ -v
```

### Test Coverage

- ✅ **All Markets**: Spot, Futures UM/CM, Options
- ✅ **All Data Types**: 13 unique data types
- ✅ **URL Patterns**: Verified for all combinations
- ✅ **Configuration**: Flexible symbol and interval filtering
- ✅ **Error Handling**: Retry logic and validation

## Troubleshooting

### Common Issues

#### Matrix File Not Found
```bash
Error: Archive matrix file not found: enhanced_binance_archive_matrix.json
```
**Solution**: Ensure the enhanced matrix file exists in the working directory.

#### Invalid Data Types
```bash
Error: 'unknown_type' is not a valid data type
```
**Solution**: Check supported data types in the matrix file and configuration.

#### s5cmd Not Found
```bash
Error: s5cmd command not available
```
**Solution**: Install s5cmd from https://github.com/peak/s5cmd/releases

#### Permission Errors
```bash
Error: Permission denied writing to output directory
```
**Solution**: Ensure write permissions for the output directory.

### Performance Optimization

#### Slow Downloads
- Increase `max_parallel_downloads` (max: 10 in production)
- Enable `enable_batch_mode` for better s5cmd performance
- Use SSD storage for better I/O performance

#### Memory Usage
- Reduce `batch_size` if memory issues occur
- Monitor system resources during large collections
- Use streaming processing for large files

### Debugging

#### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Prefect Debugging
```bash
# Start Prefect server for flow monitoring
prefect server start

# Monitor flow execution
prefect deployment run archive-collection-flow
```

## Migration Guide

### From Legacy Workflow

The enhanced workflow is backward compatible with existing configurations:

```python
# Legacy configuration still works
legacy_config = {
    "symbols": ["BTCUSDT"],
    "data_types": ["klines"],
    "output_directory": "output"
}

# Enhanced features available
enhanced_config = {
    **legacy_config,
    "markets": ["spot", "futures_um"],  # NEW: Multiple markets
    "symbols": {                        # NEW: Per-market symbols
        "spot": ["BTCUSDT"],
        "futures_um": ["BTCUSDT"]
    },
    "batch_size": 100,                  # NEW: Batch processing
    "enable_batch_mode": True           # NEW: s5cmd optimization
}
```

### Breaking Changes

- `symbols` parameter now supports per-market configuration
- New required parameter: `matrix_path`
- Enhanced data type validation (automatic mapping)

## API Reference

### Classes

#### `PrefectArchiveCollectionWorkflow`
Main workflow class with Prefect orchestration.

**Methods:**
- `__init__(config, metrics_collector=None)`
- `execute(**kwargs) -> Dict[str, Any]`
- `get_flow_config() -> Dict[str, Any]`

#### `WorkflowConfig`
Type-safe configuration management.

**Methods:**
- `__init__(config_dict)`
- `get(key, default=None)`
- `to_dict() -> Dict[str, Any]`

### Functions

#### `archive_collection_flow(config, metrics_collector=None)`
Main Prefect flow for orchestrated execution.

**Parameters:**
- `config`: WorkflowConfig instance
- `metrics_collector`: Optional MetricsCollector

**Returns:** Dict with status, metadata, and statistics

#### `validate_archive_configuration_task(config)`
Validates configuration parameters.

#### `generate_ingestion_tasks_task(config, archive_matrix)`
Generates type-safe ingestion tasks from matrix.

#### `execute_batch_downloads_task(tasks, downloader, storage, config)`
Executes downloads with batch optimization.

## Contributing

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd binance_datatool

# Install dependencies
pip install -e .

# Run tests
python -m pytest tests/ -v

# Run core tests
python test_core_functionality.py
```

### Adding New Data Types

1. Update `enhanced_binance_archive_matrix.json`
2. Add enum value to `DataType` in `core/models.py` 
3. Update data type mapping in workflow
4. Add tests for new data type
5. Update documentation

### Performance Improvements

- Optimize batch processing logic
- Enhance error recovery mechanisms
- Improve memory usage for large collections
- Add caching mechanisms

## License

This project is licensed under the terms specified in the LICENSE file.

## Support

For issues and questions:
- Review troubleshooting section
- Check test results and logs
- Open GitHub issue with detailed description

---

**Ready for Production Use! 🚀**

The Enhanced Archive Collection Workflow provides comprehensive, high-performance access to all Binance public archive data with optimized s5cmd integration and robust error handling.