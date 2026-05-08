---
name: binance-datatool-multi-source
description: Multi-source adapter framework for binance-datatool. Use when the user asks to add a new data source, implement a DataSourceAdapter, work with SourceRegistry, or build multi-source data pipelines.
---

# Multi-Source Adapter Framework

Extensible adapter framework for connecting multiple data sources to binance-datatool workflows.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      CLI Commands                        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                     Workflows                            │
│  ArchiveDownloadWorkflow, ArchiveListFilesWorkflow, etc. │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  DataSourceAdapter (Protocol)            │
│  - source_name                                           │
│  - list_symbols()                                        │
│  - list_files()                                          │
│  - fetch_file()                                          │
│  - parse_symbol()                                        │
└──────────────┬─────────────────────────────┬─────────────┘
               │                             │
┌──────────────▼──────────────┐  ┌──────────▼──────────────┐
│       BinanceAdapter        │  │     CoinbaseAdapter     │
│  (wraps ArchiveClient)      │  │     (skeleton)          │
└─────────────────────────────┘  └─────────────────────────┘
```

## DataSourceAdapter Protocol

The protocol defines the minimal interface all adapters must implement:

```python
class DataSourceAdapter(Protocol):
    @property
    def source_name(self) -> str: ...
    
    async def list_symbols(
        self, market_type: str, partition: str, data_type: str
    ) -> list[str]: ...
    
    async def list_files(
        self, market_type: str, partition: str, data_type: str,
        symbol: str, interval: str | None = None,
    ) -> list[FileMetadata]: ...
    
    async def fetch_file(self, url: str, destination_path: str) -> None: ...
    
    def parse_symbol(self, raw_symbol: str) -> dict | None: ...
```

## SourceRegistry

Central registry for discovering and instantiating adapters.

```python
from binance_datatool.source_registry import SourceRegistry
from binance_datatool.adapter.registry import BinanceAdapter, CoinbaseAdapter

# Register adapters (done in adapter/registry.py at import time)
SourceRegistry.register("binance", lambda: BinanceAdapter())
SourceRegistry.register("coinbase", lambda: CoinbaseAdapter())

# Get adapter by name
adapter = SourceRegistry.get("binance")

# List available sources
sources = SourceRegistry.list()  # ["binance", "coinbase"]
```

### Adding a New Adapter

1. Create adapter class implementing `DataSourceAdapter` protocol:

```python
from binance_datatool.adapter.protocol import DataSourceAdapter
from binance_datatool.models.archive import FileMetadata

class KrakenAdapter(DataSourceAdapter):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
    
    @property
    def source_name(self) -> str:
        return "kraken"
    
    async def list_symbols(
        self, market_type: str, partition: str, data_type: str
    ) -> list[str]:
        # Implementation
        pass
    
    async def list_files(
        self, market_type: str, partition: str, data_type: str,
        symbol: str, interval: str | None = None,
    ) -> list[FileMetadata]:
        # Implementation
        pass
    
    async def fetch_file(self, url: str, destination_path: str) -> None:
        # Implementation
        pass
    
    def parse_symbol(self, raw_symbol: str) -> dict | None:
        # Implementation
        pass
```

2. Register in `adapter/registry.py`:

```python
from binance_datatool.adapter.kraken import KrakenAdapter
SourceRegistry.register("kraken", lambda: KrakenAdapter())
```

3. Update `__all__` in `adapter/registry.py`.

## Built-in Adapters

### BinanceAdapter

Wraps `ArchiveClient` to provide `DataSourceAdapter` protocol for Binance's public data archive (data.binance.vision).

```python
from binance_datatool.adapter.binance import BinanceAdapter

adapter = BinanceAdapter(timeout_seconds=30, trust_env=True)

# List symbols
symbols = await adapter.list_symbols("spot", "daily", "klines")

# List files for a symbol
files = await adapter.list_files("spot", "daily", "klines", "BTCUSDT", interval="1d")

# Fetch a file
await adapter.fetch_file(
    "https://data.binance.vision?key=data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01-01.zip",
    "/tmp/BTCUSDT-1d-2024-01-01.zip"
)

# Parse symbol
info = adapter.parse_symbol("BTCUSDT")
# {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT"}
```

### CoinbaseAdapter

Skeleton adapter demonstrating the pattern. Requires API integration for production use.

```python
from binance_datatool.adapter.coinbase import CoinbaseAdapter

adapter = CoinbaseAdapter(
    api_key=os.environ.get("COINBASE_API_KEY"),
    api_secret=os.environ.get("COINBASE_API_SECRET"),
    api_passphrase=os.environ.get("COINBASE_API_PASSPHRASE"),
)

# Not implemented - raises NotImplementedError
# symbols = await adapter.list_symbols("spot", "daily", "klines")
```

## EnhancedBinanceAdapter

Extends `BinanceAdapter` with REST API, WebSocket, and gap-filling capabilities.

```python
from binance_datatool.adapter.enhanced import EnhancedBinanceAdapter

adapter = EnhancedBinanceAdapter(testnet=False)

# Fetch klines via REST API
klines = await adapter.fetch_klines(
    symbol="BTCUSDT",
    interval="1h",
    start_time=1704067200000,
    end_time=1704153600000,
)

# Detect gaps in kline data
gaps = adapter.detect_gaps(klines, "1h", "BTCUSDT")

# Fill gaps
result = await adapter.fill_gaps(
    symbol="BTCUSDT",
    interval="1h",
    gaps=gaps,
    destination_dir=Path("/tmp/filled"),
)
```

### REST API Methods

| Method | Description |
|--------|-------------|
| `fetch_klines()` | Fetch OHLCV candles from REST API |
| `consume_ws_deltas()` | Stream real-time updates via WebSocket |
| `detect_gaps()` | Find missing candles in kline data |
| `detect_archive_gaps()` | Find missing date files in archive |
| `fill_gaps()` | Fetch and save missing klines |

### WebSocket Streaming

```python
async for delta in adapter.consume_ws_deltas("BTCUSDT", "1h"):
    print(f"New candle: {delta}")
```

## Adapter Bridge

Helper functions for integrating adapters with existing workflows.

```python
from binance_datatool.adapter.bridge import get_adapter_for_source, list_available_sources

# Get adapter by name
adapter = get_adapter_for_source("binance")

# List all registered sources
sources = list_available_sources()  # ["binance", "coinbase"]
```

## FileMetadata Model

Standard file metadata returned by `list_files()`:

```python
from binance_datatool.models.archive import FileMetadata

metadata = FileMetadata(
    key="data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01-01.zip",
    url="https://data.binance.vision?key=data/spot/...",
    size=1234567,
    last_modified=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
    checksum=None,
)
```

## Testing Adapters

```python
import pytest
from binance_datatool.adapter.protocol import DataSourceAdapter

class MockAdapter(DataSourceAdapter):
    """Test double for DataSourceAdapter."""
    
    @property
    def source_name(self) -> str:
        return "mock"
    
    async def list_symbols(self, market_type, partition, data_type):
        return ["BTCUSDT", "ETHUSDT"]
    
    async def list_files(self, market_type, partition, data_type, symbol, interval=None):
        return []
    
    async def fetch_file(self, url, destination_path):
        pass
    
    def parse_symbol(self, raw_symbol):
        return {"symbol": raw_symbol, "base_asset": "BTC", "quote_asset": "USDT"}

@pytest.fixture
def mock_adapter():
    return MockAdapter()

async def test_workflow_with_mock_adapter(mock_adapter):
    workflow = MyWorkflow(adapter=mock_adapter)
    result = await workflow.run()
    assert result.success
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `KeyError: No adapter registered for source 'X'` | Source not in registry | Register adapter in `adapter/registry.py` |
| `NotImplementedError` | Skeleton adapter method | Implement the method or use a different adapter |
| `ValueError: Invalid market_type` | Invalid parameter | Use "spot", "um", or "cm" |
| `ValueError: Invalid partition` | Invalid parameter | Use "daily" or "monthly" |
| `ValueError: Invalid data_type` | Invalid parameter | Use "klines", "aggTrades", "trades", etc. |

## Package Structure

```
src/binance_datatool/
├── adapter/
│   ├── protocol.py      # DataSourceAdapter Protocol
│   ├── binance.py       # BinanceAdapter (wraps ArchiveClient)
│   ├── coinbase.py      # CoinbaseAdapter (skeleton)
│   ├── enhanced.py      # EnhancedBinanceAdapter (REST + WS + gaps)
│   ├── bridge.py        # get_adapter_for_source(), list_available_sources()
│   └── registry.py      # Adapter registration
├── source_registry.py   # SourceRegistry class
└── models/
    └── archive.py       # FileMetadata model
```

---

For CLI usage, see [SKILL.md](SKILL.md).
For gap detection and healing, see [gap-healing.md](gap-healing.md).
