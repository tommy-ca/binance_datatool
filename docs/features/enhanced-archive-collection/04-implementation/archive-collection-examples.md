# Archive Collection Examples

**Version**: 2.0  
**Last Updated**: July 19, 2025

## Overview

This document provides comprehensive examples and use cases for the Enhanced Archive Collection Workflow, covering everything from basic usage to advanced configurations and integration patterns.

## Quick Start Examples

### Basic Collection - Single Market

```python
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from src.crypto_lakehouse.core.config import WorkflowConfig

# Simple spot market collection
config = WorkflowConfig({
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/basic_collection",
    "markets": ["spot"],
    "symbols": ["BTCUSDT"],
    "data_types": ["klines"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    }
})

# Execute
workflow = PrefectArchiveCollectionWorkflow(config)
result = await workflow.execute()

print(f"Status: {result['status']}")
print(f"Files downloaded: {result['collection_stats']['successful_tasks']}")
print(f"Total size: {result['total_size_formatted']}")
```

### Multi-Market Collection

```python
# Collect from all markets
config = WorkflowConfig({
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/multi_market",
    "markets": ["spot", "futures_um", "futures_cm", "options"],
    "symbols": {
        "spot": ["BTCUSDT", "ETHUSDT"],
        "futures_um": ["BTCUSDT", "ETHUSDT"],
        "futures_cm": ["BTCUSD_PERP"],
        "options": ["BTC"]
    },
    "data_types": ["klines", "trades"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-10",
        "end": "2025-07-15"
    },
    "batch_size": 100,
    "max_parallel_downloads": 8
})

workflow = PrefectArchiveCollectionWorkflow(config)
result = await workflow.execute()
```

## Market-Specific Examples

### Spot Market - Complete Dataset

```python
# Comprehensive spot market data collection
spot_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/spot_complete",
    "markets": ["spot"],
    "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"],
    "data_types": ["klines", "trades", "aggTrades", "bookDepth", "bookTicker"],
    "intervals": {
        "klines": ["1m", "5m", "15m", "1h", "4h", "1d"],
        "bookDepth": ["100ms", "1000ms"]
    },
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    },
    "batch_size": 150,
    "enable_batch_mode": True,
    "enable_resume": True
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(spot_config))
result = await workflow.execute()

# Expected: ~1000+ files for 15 days, 5 symbols, multiple data types
print(f"Spot collection completed: {result['collection_stats']['total_tasks']} tasks")
```

### Futures UM - Trading Analysis Dataset

```python
# Futures data for trading analysis
futures_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/futures_trading",
    "markets": ["futures_um"],
    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "data_types": [
        "klines", 
        "fundingRate", 
        "premiumIndex",
        "liquidationSnapshot",
        "metrics"
    ],
    "intervals": {
        "klines": ["1m", "5m", "15m", "1h", "4h"],
        "indexPriceKlines": ["1h", "4h"],
        "markPriceKlines": ["1h", "4h"]
    },
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    },
    "max_parallel_downloads": 10
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(futures_config))
result = await workflow.execute()

# Analyze funding rates
funding_files = [f for f in result['metadata'].output_files if 'fundingRate' in f]
print(f"Funding rate files collected: {len(funding_files)}")
```

### Options - Volatility Analysis

```python
# Options data for volatility analysis
options_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/options_volatility",
    "markets": ["options"],
    "symbols": ["BTC", "ETH"],
    "data_types": ["BVOLIndex", "EOHSummary"],
    "intervals": {
        "BVOLIndex": ["1m", "5m", "1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    }
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(options_config))
result = await workflow.execute()

# Options data is typically smaller volume
print(f"Options files: {result['collection_stats']['successful_tasks']}")
```

## Data Type-Specific Examples

### Comprehensive Klines Collection

```python
# All kline variants across markets
klines_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/all_klines",
    "markets": ["spot", "futures_um", "futures_cm"],
    "symbols": {
        "spot": ["BTCUSDT", "ETHUSDT"],
        "futures_um": ["BTCUSDT", "ETHUSDT"],
        "futures_cm": ["BTCUSD_PERP", "ETHUSD_PERP"]
    },
    "data_types": ["klines", "indexPriceKlines", "markPriceKlines"],
    "intervals": {
        "klines": ["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"],
        "indexPriceKlines": ["1m", "5m", "1h", "1d"],
        "markPriceKlines": ["1m", "5m", "1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    }
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(klines_config))
result = await workflow.execute()

# Massive dataset with all intervals
print(f"Total kline files: {result['collection_stats']['successful_tasks']}")
```

### Order Book Analysis

```python
# Order book depth data
orderbook_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/orderbook_analysis",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": ["bookDepth", "bookTicker"],
    "intervals": {
        "bookDepth": ["100ms", "1000ms"]  # High-frequency snapshots
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    },
    "batch_size": 50,  # Smaller batches for high-frequency data
    "max_parallel_downloads": 6
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(orderbook_config))
result = await workflow.execute()

# High-frequency data generates many files
print(f"Order book files: {result['collection_stats']['successful_tasks']}")
```

### Liquidation Events

```python
# Liquidation data for risk analysis
liquidation_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/liquidations",
    "markets": ["futures_um", "futures_cm"],
    "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
    "data_types": ["liquidationSnapshot"],
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    }
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(liquidation_config))
result = await workflow.execute()

# Analyze liquidation patterns
liquidation_files = result['metadata'].output_files
print(f"Liquidation files collected: {len(liquidation_files)}")
```

## Performance Optimization Examples

### High-Throughput Configuration

```python
# Optimized for maximum download speed
high_performance_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/high_performance",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": ["klines", "trades"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    },
    
    # Performance optimizations
    "batch_size": 200,  # Larger batches
    "max_parallel_downloads": 10,  # More concurrency
    "enable_batch_mode": True,
    "enable_resume": True,
    "download_checksum": False,  # Skip checksums for speed
    
    # s5cmd optimizations
    "s5cmd_extra_args": [
        "--no-sign-request",
        "--retry-count=3",
        "--numworkers=16",
        "--part-size=100MB"
    ],
    "part_size_mb": 100
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(high_performance_config))
result = await workflow.execute()

# Monitor performance
processing_time = result['collection_stats']['processing_time_seconds']
total_mb = result['collection_stats']['total_size_bytes'] / 1024 / 1024
throughput = total_mb / processing_time if processing_time > 0 else 0

print(f"Throughput: {throughput:.2f} MB/s")
```

### Memory-Optimized Configuration

```python
# Optimized for limited memory environments
memory_optimized_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/memory_optimized",
    "markets": ["spot"],
    "symbols": ["BTCUSDT"],
    "data_types": ["klines"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    },
    
    # Memory optimizations
    "batch_size": 20,  # Smaller batches
    "max_parallel_downloads": 2,  # Less concurrency
    "enable_batch_mode": False,  # Individual downloads
    "part_size_mb": 10,  # Smaller parts
    
    "timeout_seconds": 600  # Longer timeout for slower processing
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(memory_optimized_config))
result = await workflow.execute()
```

### Network-Resilient Configuration

```python
# Optimized for unstable network connections
resilient_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/resilient",
    "markets": ["spot"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": ["klines", "trades"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    },
    
    # Network resilience
    "enable_resume": True,
    "download_checksum": True,  # Verify integrity
    "timeout_seconds": 900,  # Longer timeout
    "force_redownload": False,  # Don't re-download existing files
    
    # Enhanced retry configuration
    "s5cmd_extra_args": [
        "--no-sign-request",
        "--retry-count=5",  # More retries
        "--part-size=50MB"
    ]
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(resilient_config))
result = await workflow.execute()
```

## Date Range Examples

### Single Day Collection

```python
# Collect data for a specific day
single_day_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/single_day",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT"],
    "data_types": ["klines", "trades", "fundingRate"],
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    }
}
```

### Weekly Collection

```python
# Collect a week of data
weekly_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/weekly",
    "markets": ["spot"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": ["klines"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-08",
        "end": "2025-07-15"
    }
}
```

### Monthly Collection

```python
# Collect a month of data
monthly_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/monthly",
    "markets": ["spot"],
    "symbols": ["BTCUSDT"],
    "data_types": ["klines"],
    "intervals": {
        "klines": ["1d"]  # Daily only for large ranges
    },
    "date_range": {
        "start": "2025-06-15",
        "end": "2025-07-15"
    },
    "batch_size": 50  # Smaller batches for large collections
}
```

## Integration Examples

### Prefect Deployment

```python
from prefect import flow
from prefect.deployments import Deployment
from src.crypto_lakehouse.workflows.archive_collection_prefect import archive_collection_flow

@flow(name="daily-crypto-collection")
async def daily_collection_flow():
    config = WorkflowConfig({
        "workflow_type": "archive_collection",
        "matrix_path": "enhanced_binance_archive_matrix.json",
        "output_directory": "output/daily",
        "markets": ["spot", "futures_um"],
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "data_types": ["klines", "trades"],
        "intervals": {
            "klines": ["1h", "1d"]
        },
        "date_range": {
            "start": "2025-07-15",
            "end": "2025-07-15"
        }
    })
    
    result = await archive_collection_flow(config)
    return result

# Create deployment
deployment = Deployment.build_from_flow(
    flow=daily_collection_flow,
    name="daily-crypto-collection",
    schedule="0 6 * * *",  # Daily at 6 AM
    tags=["crypto", "daily", "archive"]
)

deployment.apply()
```

### Custom Storage Integration

```python
from src.crypto_lakehouse.storage.base import BaseStorage
from pathlib import Path
import polars as pl

class CustomS3Storage(BaseStorage):
    def __init__(self, s3_bucket: str):
        self.s3_bucket = s3_bucket
    
    def get_partition_path(self, **kwargs):
        # Custom S3 path structure
        zone = kwargs['zone']
        exchange = kwargs['exchange']
        data_type = kwargs['data_type']
        trade_type = kwargs['trade_type']
        symbol = kwargs['symbol']
        date = kwargs['partition_date']
        
        return f"{zone.value}/{exchange.value}/{trade_type.value}/{data_type.value}/{symbol}/{date.strftime('%Y/%m/%d')}"

# Use with workflow
custom_storage = CustomS3Storage("my-crypto-bucket")
config = WorkflowConfig({...})
workflow = PrefectArchiveCollectionWorkflow(config)
workflow.storage = custom_storage
```

### Metrics and Monitoring

```python
from src.crypto_lakehouse.core.metrics import MetricsCollector
import logging
import json

class DetailedMetricsCollector(MetricsCollector):
    def __init__(self):
        self.events = []
        self.errors = []
    
    def record_event(self, event_name: str, **kwargs):
        self.events.append({
            "event": event_name,
            "timestamp": datetime.now().isoformat(),
            "details": kwargs
        })
    
    def record_error(self, error_message: str, **kwargs):
        self.errors.append({
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
            "details": kwargs
        })
    
    def export_metrics(self, filename: str):
        with open(filename, 'w') as f:
            json.dump({
                "events": self.events,
                "errors": self.errors
            }, f, indent=2)

# Use with workflow
metrics = DetailedMetricsCollector()
workflow = PrefectArchiveCollectionWorkflow(config, metrics)
result = await workflow.execute()

# Export metrics
metrics.export_metrics("collection_metrics.json")
```

## Error Handling Examples

### Robust Collection with Retry Logic

```python
import asyncio
from src.crypto_lakehouse.core.exceptions import WorkflowError, ConfigurationError

async def robust_collection():
    config = WorkflowConfig({
        "workflow_type": "archive_collection",
        "matrix_path": "enhanced_binance_archive_matrix.json",
        "output_directory": "output/robust",
        "markets": ["spot"],
        "symbols": ["BTCUSDT"],
        "data_types": ["klines"],
        "date_range": {
            "start": "2025-07-15",
            "end": "2025-07-15"
        },
        "enable_resume": True  # Resume on failure
    })
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            workflow = PrefectArchiveCollectionWorkflow(config)
            result = await workflow.execute()
            
            if result['status'] == 'success':
                print(f"Collection completed successfully!")
                return result
            else:
                print(f"Collection failed: {result.get('error', 'Unknown error')}")
                
        except ConfigurationError as e:
            print(f"Configuration error: {e}")
            break  # Don't retry configuration errors
            
        except WorkflowError as e:
            print(f"Workflow error (attempt {retry_count + 1}): {e}")
            retry_count += 1
            
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
    
    print(f"Collection failed after {max_retries} attempts")
    return None

# Execute robust collection
result = await robust_collection()
```

### Partial Collection Handling

```python
async def partial_collection_handler():
    config = WorkflowConfig({
        "workflow_type": "archive_collection",
        "matrix_path": "enhanced_binance_archive_matrix.json",
        "output_directory": "output/partial",
        "markets": ["spot", "futures_um"],
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "data_types": ["klines", "trades"],
        "date_range": {
            "start": "2025-07-10",
            "end": "2025-07-15"
        }
    })
    
    workflow = PrefectArchiveCollectionWorkflow(config)
    result = await workflow.execute()
    
    # Analyze results
    stats = result['collection_stats']
    total_tasks = stats['total_tasks']
    successful_tasks = stats['successful_tasks']
    failed_tasks = stats['failed_tasks']
    
    success_rate = (successful_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    
    print(f"Collection Summary:")
    print(f"  Total tasks: {total_tasks}")
    print(f"  Successful: {successful_tasks}")
    print(f"  Failed: {failed_tasks}")
    print(f"  Success rate: {success_rate:.1f}%")
    
    if success_rate < 90:
        print("⚠️ Low success rate detected!")
        
        # Analyze failures
        if 'errors' in result['metadata'].__dict__:
            errors = result['metadata'].errors
            print(f"Error patterns:")
            for error in errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
    
    return result

result = await partial_collection_handler()
```

## Advanced Use Cases

### Research Dataset Creation

```python
# Create comprehensive research dataset
research_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/research_dataset",
    "markets": ["spot", "futures_um", "futures_cm", "options"],
    "symbols": {
        "spot": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT"],
        "futures_um": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOTUSDT"],
        "futures_cm": ["BTCUSD_PERP", "ETHUSD_PERP"],
        "options": ["BTC", "ETH"]
    },
    "data_types": [
        # Core price data
        "klines", "trades", "aggTrades",
        # Market structure
        "bookDepth", "bookTicker", 
        # Derivatives data
        "fundingRate", "premiumIndex", "liquidationSnapshot",
        # Advanced metrics
        "metrics", "BVOLIndex", "EOHSummary",
        # Index data
        "indexPriceKlines", "markPriceKlines"
    ],
    "intervals": {
        "klines": ["1m", "5m", "15m", "1h", "4h", "1d"],
        "indexPriceKlines": ["1h", "4h", "1d"],
        "markPriceKlines": ["1h", "4h", "1d"],
        "BVOLIndex": ["1h", "1d"],
        "bookDepth": ["1000ms"]
    },
    "date_range": {
        "start": "2025-07-01",
        "end": "2025-07-15"
    },
    "batch_size": 100,
    "max_parallel_downloads": 8,
    "enable_batch_mode": True,
    "download_checksum": True
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(research_config))
result = await workflow.execute()

# Generate dataset summary
print(f"Research Dataset Summary:")
print(f"Total files: {result['collection_stats']['successful_tasks']}")
print(f"Total size: {result['total_size_formatted']}")
print(f"Markets covered: {len(research_config['markets'])}")
print(f"Data types: {len(research_config['data_types'])}")
```

### Trading System Backtesting Data

```python
# Collect data for trading system backtesting
backtest_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/backtest_data",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": [
        "klines",  # Price data
        "trades",  # Execution data
        "fundingRate",  # Cost of capital
        "liquidationSnapshot"  # Risk events
    ],
    "intervals": {
        "klines": ["1m", "5m", "1h"]  # Multiple timeframes
    },
    "date_range": {
        "start": "2025-06-01",  # 1.5 months of data
        "end": "2025-07-15"
    },
    "batch_size": 150,
    "enable_resume": True  # Important for large collections
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(backtest_config))
result = await workflow.execute()

# Verify data completeness for backtesting
expected_days = 45  # June 1 to July 15
kline_files_per_day = len(backtest_config['symbols']) * len(backtest_config['intervals']['klines']) * 2  # 2 markets
expected_kline_files = expected_days * kline_files_per_day

actual_kline_files = len([f for f in result['metadata'].output_files if 'klines' in f])
completeness = (actual_kline_files / expected_kline_files) * 100

print(f"Backtest Data Completeness: {completeness:.1f}%")
```

### Real-time Data Pipeline Initialization

```python
# Initialize real-time pipeline with historical context
pipeline_init_config = {
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/pipeline_init",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    "data_types": [
        "klines",  # For trend analysis
        "trades",  # For volume profiling
        "fundingRate",  # For futures context
        "bookTicker"  # For spread analysis
    ],
    "intervals": {
        "klines": ["1m", "5m", "1h"]
    },
    "date_range": {
        "start": "2025-07-14",  # Last 2 days for context
        "end": "2025-07-15"
    },
    "force_redownload": True,  # Ensure fresh data
    "download_checksum": True
}

workflow = PrefectArchiveCollectionWorkflow(WorkflowConfig(pipeline_init_config))
result = await workflow.execute()

print(f"Pipeline initialized with {result['collection_stats']['successful_tasks']} files")
```

## Testing Examples

### Unit Test Configuration

```python
import pytest
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from src.crypto_lakehouse.core.config import WorkflowConfig

@pytest.fixture
def test_config():
    return WorkflowConfig({
        "workflow_type": "archive_collection",
        "matrix_path": "enhanced_binance_archive_matrix.json",
        "output_directory": "output/test",
        "markets": ["spot"],
        "symbols": ["BTCUSDT"],
        "data_types": ["klines"],
        "intervals": {
            "klines": ["1h"]
        },
        "date_range": {
            "start": "2025-07-15",
            "end": "2025-07-15"
        },
        "batch_size": 5,  # Small for testing
        "max_parallel_downloads": 2,
        "timeout_seconds": 60
    })

@pytest.mark.asyncio
async def test_basic_collection(test_config):
    workflow = PrefectArchiveCollectionWorkflow(test_config)
    result = await workflow.execute()
    
    assert result['status'] == 'success'
    assert result['collection_stats']['total_tasks'] > 0
    assert result['success_rate'] >= 0

@pytest.mark.asyncio
async def test_invalid_configuration():
    invalid_config = WorkflowConfig({
        "workflow_type": "archive_collection",
        "matrix_path": "nonexistent_matrix.json",
        "output_directory": "output/test",
        "markets": ["invalid_market"],
        "symbols": ["BTCUSDT"],
        "data_types": ["invalid_type"]
    })
    
    workflow = PrefectArchiveCollectionWorkflow(invalid_config)
    
    with pytest.raises(Exception):
        await workflow.execute()
```

### Performance Test

```python
import time
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow

async def performance_test():
    config = WorkflowConfig({
        "workflow_type": "archive_collection",
        "matrix_path": "enhanced_binance_archive_matrix.json",
        "output_directory": "output/performance_test",
        "markets": ["spot"],
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "data_types": ["klines", "trades"],
        "intervals": {
            "klines": ["1h", "1d"]
        },
        "date_range": {
            "start": "2025-07-15",
            "end": "2025-07-15"
        },
        "batch_size": 100,
        "max_parallel_downloads": 8
    })
    
    start_time = time.time()
    workflow = PrefectArchiveCollectionWorkflow(config)
    result = await workflow.execute()
    end_time = time.time()
    
    # Calculate performance metrics
    processing_time = end_time - start_time
    total_files = result['collection_stats']['successful_tasks']
    total_bytes = result['collection_stats']['total_size_bytes']
    
    files_per_second = total_files / processing_time
    bytes_per_second = total_bytes / processing_time
    mbps = bytes_per_second / 1024 / 1024
    
    print(f"Performance Test Results:")
    print(f"  Processing time: {processing_time:.2f} seconds")
    print(f"  Files per second: {files_per_second:.2f}")
    print(f"  Throughput: {mbps:.2f} MB/s")
    print(f"  Success rate: {result['success_rate']:.1f}%")
    
    # Performance assertions
    assert files_per_second > 1.0, "Should process at least 1 file per second"
    assert result['success_rate'] > 95.0, "Should have >95% success rate"

await performance_test()
```

## Command Line Examples

### Direct Execution

```bash
# Create configuration file
cat > config.json << EOF
{
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/cli_test",
    "markets": ["spot"],
    "symbols": ["BTCUSDT"],
    "data_types": ["klines"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "2025-07-15",
        "end": "2025-07-15"
    }
}
EOF

# Execute workflow
python -c "
import asyncio
import json
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from src.crypto_lakehouse.core.config import WorkflowConfig

async def main():
    with open('config.json') as f:
        config_dict = json.load(f)
    
    config = WorkflowConfig(config_dict)
    workflow = PrefectArchiveCollectionWorkflow(config)
    result = await workflow.execute()
    
    print(f'Status: {result[\"status\"]}')
    print(f'Files: {result[\"collection_stats\"][\"successful_tasks\"]}')

asyncio.run(main())
"
```

### Batch Script Execution

```bash
#!/bin/bash
# batch_collect.sh - Collect data for multiple date ranges

DATES=(
    "2025-07-10"
    "2025-07-11"
    "2025-07-12"
    "2025-07-13"
    "2025-07-14"
    "2025-07-15"
)

for date in "${DATES[@]}"; do
    echo "Collecting data for $date"
    
    cat > "config_$date.json" << EOF
{
    "workflow_type": "archive_collection",
    "matrix_path": "enhanced_binance_archive_matrix.json",
    "output_directory": "output/batch_$date",
    "markets": ["spot", "futures_um"],
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "data_types": ["klines", "trades"],
    "intervals": {
        "klines": ["1h", "1d"]
    },
    "date_range": {
        "start": "$date",
        "end": "$date"
    },
    "enable_resume": true
}
EOF

    python -c "
import asyncio
import json
from src.crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from src.crypto_lakehouse.core.config import WorkflowConfig

async def main():
    with open('config_$date.json') as f:
        config_dict = json.load(f)
    
    config = WorkflowConfig(config_dict)
    workflow = PrefectArchiveCollectionWorkflow(config)
    result = await workflow.execute()
    
    print(f'$date: {result[\"status\"]} - {result[\"collection_stats\"][\"successful_tasks\"]} files')

asyncio.run(main())
    " || echo "Failed for $date"
    
    rm "config_$date.json"
    echo "---"
done

echo "Batch collection complete!"
```

---

These examples provide comprehensive coverage of the Enhanced Archive Collection Workflow capabilities, from basic usage to advanced configurations and integration patterns.