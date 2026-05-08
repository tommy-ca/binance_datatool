# Formal Requirements & Specification Document

## 1. Project Overview

**Project**: `binance-datatool` — A multi-source cryptocurrency market data ingestion toolkit  
**Current Scope**: Binance public archive (data.binance.vision) with support for spot, USD-M futures, and COIN-M futures  
**Target Scope**: Multi-exchange support (Coinbase, Kraken, Bybit, etc.) with explicit DataOps and MLOps concerns  
**Principles**: SOLID, KISS, DRY, YAGNI with specification-driven development and TDD

---

## 2. Functional Requirements

### 2.1 Core Data Operations

| Requirement | Description | Priority | Status |
|---|---|---|---|
| **FR-1: List Symbols** | Query a data source for all available trading symbols, with optional filtering (quote asset, leverage, stablecoins, contract type) | HIGH | ✅ Implemented |
| **FR-2: List Files** | Query a data source for available data files for one or more symbols, respecting partition and data type | HIGH | ✅ Implemented |
| **FR-3: Download Files** | Fetch data files from source using diff-based sync (only new/updated files), with resumable downloads and retry logic | HIGH | ✅ Implemented |
| **FR-4: Verify Integrity** | Validate downloaded files against SHA256 checksums, with marker caching to avoid re-verification | HIGH | ✅ Implemented |
| **FR-5: Multi-Source Support** | Enable data ingestion from multiple exchanges behind a common adapter interface | HIGH | ✅ Implemented |
| **FR-6: Data Contracts** | Define and validate schema/structure constraints on ingested data | MEDIUM | ✅ Implemented |
| **FR-7: Lineage Tracking** | Record data provenance: source, partition, transformation steps, validation status | MEDIUM | ✅ Implemented |
| **FR-8: CLI Composition** | Support stdin/stdout piping to compose commands into multi-step workflows | HIGH | ✅ Implemented |

### 2.2 Non-Functional Requirements

| Requirement | Description | Priority |
|---|---|---|
| **NFR-1: Testability** | All public behaviours must be testable with dependency injection and fakes | HIGH |
| **NFR-2: Performance** | Download throughput ≥ 50 MB/s for batch operations; parallel file listing; concurrent verification | MEDIUM |
| **NFR-3: Reliability** | Exponential backoff retry on transient HTTP errors; atomic file writes; orphan cleanup | HIGH |
| **NFR-4: Extensibility** | New sources and data types must be addable without modifying core workflows | HIGH |
| **NFR-5: Observability** | Log all operations; emit metrics (counts, durations, error rates); support agent tracing | MEDIUM |
| **NFR-6: Security** | No hard-coded secrets; credentials from environment or secure config; proxy support | HIGH |

---

## 3. Actors & Use Cases

### 3.1 User Personas

1. **Quant Researcher**: Downloads historical OHLCV data for backtesting  
2. **MLOps Engineer**: Ingests data into a lakehouse for feature engineering  
3. **Data Platform Owner**: Orchestrates multi-source data pipelines; monitors quality  
4. **AI Agent / Subagent**: Programmatically discovers, downloads, and verifies data

### 3.2 Key Use Cases

**UC-1: Bulk Historical Download**
- Actor: Quant Researcher
- Steps: 1) List symbols with filters 2) Pipe to download 3) Verify 4) Export to CSV/Parquet
- Success: All files downloaded and verified; checksums match

**UC-2: Incremental Data Lake Ingest**
- Actor: MLOps Engineer
- Steps: 1) Trigger pipeline for new partition 2) List files (diff against local store) 3) Download new files 4) Validate schema 5) Record lineage 6) Merge into Delta Lake
- Success: New data appears in analytics schema with lineage metadata

**UC-3: Multi-Source Unified Interface**
- Actor: Data Platform Owner
- Steps: 1) Configure Binance, Coinbase, Kraken adapters 2) Query all sources for symbols 3) Download from each 4) Normalize schemas 5) Store in unified lakehouse
- Success: Platform exposes one interface for all exchanges

**UC-4: Agent-Driven Discovery & Download**
- Actor: AI Subagent
- Steps: 1) Call `discover_symbols` skill 2) Filter results 3) Call `download_partition` skill for each 4) Monitor status
- Success: Agent autonomously completes workflow with human oversight

---

## 4. Architecture Requirements

### 4.1 Layered Architecture (as-is)

Current four-layer design (working well):

```
CLI Layer
  ↓ (depends on)
Workflow Layer
  ↓ (depends on)
Archive Client Layer
  ↓ (depends on)
Common / Foundation Layer
```

Each layer has a single responsibility:
- **CLI**: Parse arguments, invoke workflows, format output
- **Workflow**: Orchestrate business logic (diff, verify, transform)
- **Archive Client**: Source-specific I/O (S3 listing, HTTP, REST APIs)
- **Foundation**: Shared enums, types, constants, filters

### 4.2 Extended Architecture (proposed)

Add three explicit layers for multi-source and DataOps:

```
CLI / API Layer
  ↓ (depends on)
Orchestration / Pipeline Layer (workflows, DAGs, schedules)
  ↓ (depends on)
DataOps / Transform Layer (validation, contracts, lineage)
  ↓ (depends on)
Source Adapter Layer (Binance, Coinbase, Kraken, etc.)
  ↓ (depends on)
Storage Connector Layer (S3, local, Delta Lake, Parquet)
  ↓ (depends on)
Foundation Layer (enums, types, filters, progress)
```

**Key abstractions to add**:
- `DataSourceAdapter` protocol: unifies list_symbols, list_files, fetch_file, parse_symbol
- `StorageBackend` protocol: unifies put, get, list, delete, exists for local/S3/cloud
- `DataContract`: schema + validation rules for datasets
- `LineageTracker`: record data provenance
- `SourceRegistry`: discover and instantiate adapters by name

### 4.3 Design Principles

**Single Responsibility**: Each module/class owns ONE clear concern  
**Open/Closed**: Open to extension (new adapters) via plugins; closed to modification (core workflows stay stable)  
**Liskov Substitution**: All adapters implement the same protocol; workflows don't know the concrete type  
**Interface Segregation**: Thin protocols (DataSourceAdapter, StorageBackend) not monolithic interfaces  
**Dependency Inversion**: Core depends on abstractions (protocols), not concrete implementations

**KISS**: Keep it simple and focused. No unnecessary abstraction or premature generalization.  
**DRY**: Reuse shared logic via base classes, mixins, or utility functions. Don't duplicate patterns.  
**YAGNI**: Only implement features when explicitly requested. No speculative hooks or "future-proofing".

---

## 5. Data Model & Contracts

### 5.1 Core Data Types

```python
# Foundation Layer

class DataSource(Enum):
    """Exchange or data provider identifier."""
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"

class MarketType(Enum):
    """Market segment or asset class."""
    SPOT = "spot"
    FUTURES_USD_M = "um"         # USD-M perpetual/delivery
    FUTURES_COIN_M = "cm"        # COIN-M perpetual/delivery
    OPTIONS = "options"

class DataCategory(Enum):
    """High-level data category."""
    TRADES = "trades"
    ORDERBOOK = "orderbook"
    FUNDING = "funding"
    INDEX = "index"

class DataType(Enum):
    """Specific dataset type."""
    KLINES = "klines"             # OHLCV candlesticks
    AGGR_TRADES = "aggTrades"     # Aggregated trade records
    TRADES = "trades"             # Raw trade records
    BOOK_DEPTH = "bookDepth"      # Order book depth snapshots
    BOOK_TICKER = "bookTicker"    # Best bid/ask snapshots
    FUNDING_RATE = "fundingRate"  # Perpetual funding rates
    # ... see docs/specs-driven-development.md for full list

class PartitionFreq(Enum):
    """Temporal partitioning strategy."""
    DAILY = "daily"
    MONTHLY = "monthly"
    HOURLY = "hourly"

@dataclass
class FileMetadata:
    """Metadata for a data file."""
    key: str                       # Object store key
    url: str                      # Direct download URL
    size: int                     # File size in bytes
    last_modified: datetime       # Last modification time
    checksum: str | None = None   # SHA256 if available

@dataclass
class SymbolMetadata:
    """Parsed symbol information."""
    symbol: str                   # Trading symbol (e.g., BTCUSDT)
    base_asset: str              # Base asset (e.g., BTC)
    quote_asset: str             # Quote asset (e.g., USDT)
    source: DataSource
    market_type: MarketType
    metadata: dict = {}          # Source-specific fields
```

### 5.2 Data Contracts

```python
@dataclass
class DataContract:
    """Explicit schema and validation rules for a dataset."""
    
    source: DataSource
    market_type: MarketType
    data_type: DataType
    partition_freq: PartitionFreq
    
    # Schema: columns, types, nullability
    schema: dict[str, type]
    
    # Partition keys for organization
    partition_cols: list[str]
    
    # Primary/unique key columns
    key_cols: list[str]
    
    # Validation rules (e.g., "price > 0", "volume >= 0")
    validators: list[Callable[[Any], bool]]
    
    def validate(self, dataframe) -> ValidationResult:
        """Validate a dataframe against this contract."""
        # Check schema, nullability, constraints
        # Return ValidationResult(passed: bool, errors: list[str])
        ...
```

---

## 6. Code & Data Flows

### 6.1 CLI Command Flow: `list-symbols`

```
Command: binance-datatool list-symbols spot --quote USDT --exclude-stables

Flow:
  CLI (cli/archive.py)
    ↓ parses args → TradeType.spot, DataFrequency.daily, DataType.klines
    ↓ builds SymbolFilter(quote_assets=frozenset(["USDT"]), exclude_stables=True)
    ↓ constructs ArchiveListSymbolsWorkflow(client, filter)
    ↓ calls asyncio.run(workflow.run())
    
  Workflow (workflow/list_symbols.py)
    ↓ calls client.list_symbols(trade_type, data_freq, data_type)
    
  Archive Client (archive/client.py)
    ↓ builds S3 prefix: "data/spot/daily/klines/"
    ↓ creates async HTTP session
    ↓ calls list_dir(session, prefix) → paginated S3 listing
    ↓ parses XML responses → list of symbol prefixes
    ↓ returns sorted list: ["BTCUSDT", "ETHUSDT", ...]
    
  Workflow (continued)
    ↓ infers symbol metadata: infer_spot_info("BTCUSDT")
      → SpotSymbolInfo(symbol, base, quote, is_leverage, is_stable_pair)
    ↓ applies filter.matches(info) → True/False
    ↓ splits into matched, filtered_out, unmatched buckets
    ↓ returns ListSymbolsResult(matched=[...], filtered_out=[...], unmatched=[...])
    
  CLI (continued)
    ↓ prints matched symbols one per line to stdout
    ↓ exit code 0
```

### 6.2 CLI Command Flow: `download`

```
Command: binance-datatool download spot --type klines --interval 1m \
         --dry-run BTCUSDT ETHUSDT | \
         binance-datatool download spot --type klines --interval 1m

Flow:
  CLI (cli/archive.py)
    ↓ parses args → trade_type, data_type, interval, symbols (from stdin or args)
    ↓ resolves archive_home from --archive-home or BINANCE_DATATOOL_ARCHIVE_HOME
    ↓ constructs ArchiveDownloadWorkflow(
        trade_type, data_type, symbols, archive_home, 
        interval, dry_run=True
      )
    ↓ calls asyncio.run(workflow.run())
    
  Workflow (workflow/download.py)
    ↓ Step 1: List remote files
      - constructs ArchiveListFilesWorkflow(symbols=...)
      - calls client.list_symbol_files_batch(symbols) concurrently
      - collects files and per-symbol errors
      
    ↓ Step 2: Compute diff (local vs remote)
      - scans local archive_home/data/spot/.../symbol/ for existing files
      - compares last_modified timestamps
      - classifies each remote file as: new, updated, or skipped
      
    ↓ Step 3a (dry_run=True): Return diff
      - returns DiffResult(to_download=[...], skipped=N, listing_errors=[...])
      - CLI prints each entry: "new\tSize\tpath"
      
    ↓ Step 3b (dry_run=False): Download
      - invalidates stale verify markers for updated files
      - deletes local copies of files marked "updated"
      - calls downloader.download(DownloadRequest list)
        - aria2c fetches files in batches with retry logic
      - returns DownloadResult(downloaded=N, failed=M, ...)
      
  CLI (continued)
    ↓ prints results
    ↓ if dry_run: prints diff; exit 0
    ↓ if download failed: exit 2
```

### 6.3 CLI Command Flow: `verify`

```
Command: binance-datatool verify spot --type klines --interval 1m BTCUSDT

Flow:
  CLI (cli/archive.py)
    ↓ resolves archive_home
    ↓ constructs ArchiveVerifyWorkflow(symbols, archive_home, dry_run=False)
    ↓ calls workflow.run()  (note: sync, not async)
    
  Workflow (workflow/verify.py)
    ↓ Step 1: Scan local directory
      - uses ThreadPoolExecutor to scan symbol directories in parallel
      - for each symbol directory:
        - scans .zip files and .zip.CHECKSUM files
        - checks for .verified marker files (timestamped)
        - classifies: to_verify, already_verified (skipped), orphaned
        
    ↓ Step 2a (dry_run=True): Return scan results
      - returns VerifyDiffResult(to_verify=[...], skipped=N, orphan_zips=[...])
      
    ↓ Step 2b (dry_run=False): Verify
      - cleans orphaned files (deletes orphan .zip and .CHECKSUM)
      - uses ProcessPoolExecutor to verify files in parallel
      - for each .zip file:
        - calculates SHA256 hash
        - reads expected hash from .zip.CHECKSUM file
        - compares; records result
      - for passed verifications: writes .zip.TIMESTAMP.verified marker
      - for failed verifications: optionally deletes both .zip and .CHECKSUM
      - returns VerifyResult(verified=N, failed=M, orphan_zips=P, ...)
      
  CLI (continued)
    ↓ prints summary
    ↓ exit 0 if no failures; exit 2 if failures
```

### 6.4 Data Flow: Adapter Protocol (Multi-Source)

```
Proposed Generic Adapter Flow:

CLI / User
  ↓ (specifies source="binance" / "coinbase" / etc.)
  ↓
SourceRegistry.get("binance")
  ↓ returns BinanceAdapter instance
  ↓
Workflow (e.g., ArchiveListSymbolsWorkflow)
  ↓ calls adapter.list_symbols(market_type, partition, data_type)
  ↓
DataSourceAdapter (Protocol)
  ├─ BinanceAdapter (wraps ArchiveClient)
  │   ├─ parses S3 XML responses
  │   ├─ extracts symbol prefixes
  │   └─ returns list[str]
  │
  ├─ CoinbaseAdapter (REST API)
  │   ├─ calls GET /products
  │   ├─ filters by market_type, product_id patterns
  │   └─ returns list[str]
  │
  └─ KrakenAdapter (REST API)
      ├─ calls GET /public/AssetPairs
      ├─ filters by asset classes
      └─ returns list[str]

Workflow (receives list[str] from any adapter, logic is identical)
  ↓ infers symbol metadata
  ↓ applies filters
  ↓ returns results
```

---

## 7. Specification Template & Checklist

### 7.1 Behavior Specification Template

**Use this template for every new feature, adapter, or public function:**

```markdown
## Spec: [Feature Name]

### Purpose
One sentence describing what this feature does and why it's needed.

### Inputs
- Param1: type, description, constraints
- Param2: type, description, constraints
Example: symbol: str (non-empty, uppercase, max 16 chars)

### Outputs
- Return type and shape
Example: list[FileMetadata] (sorted ascending by last_modified)

### Side Effects
- I/O operations, filesystem writes, network calls, logging
Example: Creates directory `archive_home/data/...` if not present

### Success Criteria
- Behavior when all inputs are valid
Example: Returns ALL files for the symbol in ascending date order; empty list if none

### Error Cases
- What can go wrong and how to handle
Example:
  - Symbol not found: return empty list (NOT an error)
  - Network timeout: raise TimeoutError (caller can retry)
  - Invalid symbol format: raise ValueError with details

### Test Cases (Minimal)
- Unit test with fakes
- Integration test (if I/O)
- Edge cases
Example:
  - test_list_files_happy_path: symbol with 10 files
  - test_list_files_empty_symbol: symbol with no files (returns [])
  - test_list_files_network_error: ArchiveClient.list_dir raises; error propagates
```

### 7.2 Pre-Merge Audit Checklist

Before approving any PR:

```
[ ] Requirements
  [ ] Feature addresses explicit requirement (FR-X, NFR-X)
  [ ] Scope is small and focused (avoid scope creep)

[ ] Specification
  [ ] Spec written using template above
  [ ] Spec linked in PR description
  [ ] All error cases documented

[ ] Tests (TDD)
  [ ] Unit tests written FIRST (failing)
  [ ] Implementation added (tests now pass)
  [ ] Integration tests added for I/O (gated by @pytest.mark.integration)
  [ ] Edge cases covered (empty, large, error scenarios)
  [ ] Fakes/mocks used to isolate dependencies

[ ] Design Review (SOLID / KISS / DRY / YAGNI)
  [ ] Single Responsibility: class/module has one clear job
  [ ] Open/Closed: open to extension, closed to modification
  [ ] Liskov Substitution: implementations follow protocol contract
  [ ] Interface Segregation: protocols are small and focused
  [ ] Dependency Inversion: depends on abstractions, not concretes
  [ ] KISS: solution is as simple as possible
  [ ] DRY: no duplicated code or logic
  [ ] YAGNI: no speculative features or hooks

[ ] Documentation
  [ ] Docstrings added (Google style)
  [ ] README updated if user-facing
  [ ] Architecture docs updated if structural change
  [ ] Spec-driven-development.md updated with new patterns

[ ] Security & Compliance
  [ ] No hard-coded secrets, API keys, or credentials
  [ ] No breaking changes to public API (unless major version)
  [ ] No performance regressions

[ ] Code Quality
  [ ] All tests pass locally: `uv run pytest`
  [ ] Linting passes: `uv run ruff check .`
  [ ] Formatting correct: `uv run ruff format .`

[ ] Ready to Merge
  [ ] All boxes above checked
  [ ] Approval from at least one reviewer
  [ ] CI pipeline green
```

---

## 8. Skills & Subagents Specification

### 8.1 Skill Definition

A **skill** is a small, well-specified, testable unit of functionality that an agent or user can invoke.

Structure:
```
skills/
├── SKILL.md                  # Human-readable spec
├── manifest.json             # Machine-readable metadata
└── tests/
    └── test_skill.py         # Unit tests with mocks
```

Example skill:

```yaml
# skills/discover-symbols/manifest.json
{
  "name": "discover_symbols",
  "version": "1.0.0",
  "description": "Discover trading symbols from a data source",
  "input_schema": {
    "source": "string (binance|coinbase|kraken)",
    "market_type": "string (spot|um|cm)",
    "quote_asset": "string|null",
    "exclude_leverage": "boolean",
    "exclude_stables": "boolean"
  },
  "output_schema": {
    "symbols": "array[string]",
    "filtered_out": "array[string]",
    "errors": "array[string]"
  },
  "error_modes": {
    "source_not_found": "return empty symbols, error message",
    "network_timeout": "retry up to 3 times, then fail",
    "invalid_input": "return validation error immediately"
  }
}
```

### 8.2 Subagent Definition

A **subagent** is a stateful actor responsible for a single operation in a larger workflow.

Examples:
- `discover_symbols`: List symbols from all configured sources
- `download_partition`: Download data for symbol(s) on a specific date
- `verify_partition`: Verify integrity of downloaded files
- `transform_partition`: Apply transformation (normalization, schema validation) to a partition
- `publish_partition`: Move verified partition to analytics schema

Each subagent:
- Owns ONE responsibility (SRP)
- Has a Spec (inputs, outputs, error modes)
- Has unit tests with faked I/O
- Can be run independently or composed into workflows
- Reports progress and errors to caller

Example subagent structure:
```python
class DiscoverSymbolsSubagent:
    """Discover symbols from a source."""
    
    def __init__(self, source_registry, logger):
        self.registry = source_registry
        self.logger = logger
    
    async def run(self, 
                  source: str, 
                  market_type: str, 
                  filters: dict) -> dict:
        """Run the subagent.
        
        Returns:
            {
                "success": bool,
                "symbols": list[str],
                "filtered_out": list[str],
                "errors": list[str],
                "duration_seconds": float
            }
        """
        try:
            adapter = self.registry.get(source)
            symbols = await adapter.list_symbols(market_type, ...)
            # apply filters, return results
        except Exception as e:
            self.logger.error(f"Failed: {e}")
            return {"success": False, "errors": [str(e)]}
```

---

## 9. Testing Strategy (TDD)

### 9.1 Test Layers

```
Unit Tests (Fastest, Most Isolated)
├─ No I/O (use fakes for adapters, storage, HTTP)
├─ Test a single class/function
├─ Run in < 100ms total
└─ Example: test_list_files_preserves_order()

Integration Tests (Moderate, Real I/O)
├─ May call real HTTP (or fixtures)
├─ Test workflows end-to-end
├─ Gated by @pytest.mark.integration
├─ Run in < 5 seconds
└─ Example: test_download_workflow_with_real_s3()

End-to-End Tests (Slowest, Full System)
├─ May call real Binance API
├─ Full CLI invocation
├─ CI/CD gates or manual only
└─ Example: test_cli_download_real_data()

### 6.6 Exchange Client Data Flow (Official SDK)

```
ExchangeClient (protocol)
  ↓ fetch_ohlcv(symbol, interval, since, until, limit)

BinanceSpotRestClient (or Um/Cm)
  ↓ SDK rest_api.klines() / rest_api.kline_candlestick_data()

ConfigurationRestAPI (api_key="", base_path=PROD_URL)
  ↓ HTTPS GET
Binance REST API (api.binance.com / fapi.binance.com / dapi.binance.com)
  ↓
SDK ApiResponse.data() → list of 12-element kline arrays
  ↓ KlineData.from_binance_api(kline)
list[KlineData] → returned to caller

---

ExchangeClient (protocol)
  ↓ stream_ohlcv(symbol, interval)

BinanceSpotWsClient (or Um/Cm)
  ↓ SDK websocket_streams.create_connection()
  ↓ connection.kline(symbol, interval) or connection.kline_candlestick_streams()
  ↓
RequestStreamHandle
  ↓ on("message", queue.put_nowait)
  ↓
asyncio.Queue → async generator
  ↓ parse kline JSON
AsyncIterator[KlineData] → yielded to caller
```
```

### 9.2 Test Template (TDD)

**Step 1: Write failing test**
```python
def test_list_files_returns_sorted_results():
    # Arrange
    fake_adapter = FakeAdapter(files=[
        FileMetadata(key="...2026-03.zip", ...),
        FileMetadata(key="...2026-01.zip", ...),
        FileMetadata(key="...2026-02.zip", ...),
    ])
    workflow = ArchiveListFilesWorkflow(adapter=fake_adapter, symbols=["BTCUSDT"])
    
    # Act
    result = asyncio.run(workflow.run())
    
    # Assert
    assert [f.key for f in result.per_symbol[0].files] == [
        "...2026-01.zip",
        "...2026-02.zip",
        "...2026-03.zip",
    ]
```

**Step 2: Implement minimal code**
```python
class ArchiveListFilesWorkflow:
    async def run(self):
        files = await self.adapter.list_files(...)
        files.sort(key=lambda f: f.last_modified)
        return ListFilesResult(per_symbol=[...])
```

**Step 3: Refine**
- Add edge cases
- Add error handling
- Add documentation

---

## 10. Next Steps & Roadmap

### Phase 1: Foundation (Complete)
- ✅ Design four-layer architecture
- ✅ Implement core workflows (list, download, verify)
- ✅ Build test infrastructure (FakeArchiveClient, fixtures)
- ✅ Document specs and extending patterns

### Phase 2: Adapter Abstraction (Complete)
- ✅ Implement `DataSourceAdapter` protocol
- ✅ Implement `SourceRegistry`
- ✅ Wrap existing `ArchiveClient` as `BinanceAdapter`
- ✅ Add unit tests for adapter protocol (35 tests)
- ⏳ Update CLI to use registry (--source flag not yet integrated)

### Phase 3: Data Contracts & Validation (Complete)
- ✅ Implement `DataContract` class
- ✅ Add schema validation to `VerifyTask`
- ✅ Create data contract fixtures for tests (24 tests)

### Phase 4: Lineage & Observability (Partial)
- ✅ Implement `LineageTracker`
- ❌ Implement `MetricsCollector` (removed from scope)
- ✅ Emit logs for all pipeline operations
- ⏳ Add Prometheus metrics (optional, not prioritized)

### Phase 5: Multi-Source CEX (In Progress)
- ✅ Implement `BinanceAdapter` (complete, Binance S3 archive)
- ✅ Implement CCXT exchange clients (Binance Spot/UM/CM)
- 🔄 Implement `OKXAdapter` via CCXT (`ccxt.okx`)
- 🔄 Implement `BybitAdapter` via CCXT (`ccxt.bybit`)
- ⏳ Add integration tests for each CEX
- ⏳ Document configuration per source

**Note**: Coinbase removed from scope. Focus on Tier-1 CEXs (Binance, OKX, Bybit) through CCXT unified API.

### Phase 6: Exchange Clients (Complete)
- ✅ Implement market-type-specific Binance clients (Spot/UM/CM)
- ✅ Add `ExchangeClient` protocol with @runtime_checkable
- ✅ Implement `BinanceSpotRestClient`, `BinanceUmRestClient`, `BinanceCmRestClient`
- ✅ Implement `BinanceSpotWsClient`, `BinanceUmWsClient`, `BinanceCmWsClient`
- ✅ Add optional CCXT integration (`ccxt_rest.py`, `ccxt_pro.py`)
- ✅ Add exchange client tests (18 tests in test_exchange.py)
- ✅ **Migrated to official Binance SDK** (`binance-sdk-spot` for Spot, `binance-sdk-derivatives-trading-usds-futures` for UM, `binance-sdk-derivatives-trading-coin-futures` for CM)
  - Replaced hand-rolled `aiohttp` REST clients with SDK `rest_api.klines()`/`kline_candlestick_data()` calls
  - Replaced hand-rolled `aiohttp` WS clients with SDK `websocket_streams` + async generator wrapper
  - Preserved `ExchangeClient` protocol and backward-compatible aliases
  - Archive client (`archive/` module) kept intact (still uses `aiohttp` for S3 access)
- ✅ **Extended ExchangeClient protocol** with `fetch_agg_trades()` and `fetch_funding_rate()` methods
  - Spot: SDK `rest_api.agg_trades()` for aggTrades
  - UM: `rest_api.compressed_aggregate_trades_list()` + `get_funding_rate_history()`
  - CM: same as UM + `get_funding_rate_history_of_perpetual_futures()`
- ✅ **Gap-fill workflow** (`workflow/gap_fill.py`) detects and fills missing archive data via REST API
  - CLI: `binance-datatool gap-fill` command with `--auto-detect` flag
  - Supports klines, aggTrades, fundingRate with auto gap detection
  - Saves filled data as CSV with SHA256 checksum in `_filled/` subdirectory
  - Records lineage events (LineageEventType.FILLED) for each operation
- ✅ **Health check workflow** (`workflow/health_check.py`) monitors data health
  - CLI: `binance-datatool health` command
  - Checks completeness (missing dates), freshness (staleness), and integrity (checksums)
  - Per-symbol health report with summary
- ✅ **Enhanced LineageEventType**: Added `FILLED` (gap fill) and `HEALTH_CHECKED` events
- ⏳ Implement `ExchangeRegistry` and `create_client()` factory
- ⏳ Wire up new clients to CLI commands (Phase 6c)
- ⏳ Transform/normalize/sink pipeline to DuckDB/Iceberg (Phase 7)

### Phase 7: Transform, Normalize, and Sink (Planned)

Goal: Transform raw archive data into queryable columnar format (Parquet), normalize schemas
across data types and trade types, and sink to DuckDB (local) and/or Apache Iceberg (catalog).

**Rationale**: Raw archive ZIPs are opaque. For analytics, ML feature engineering, and
DataOps pipelines, we need columnar data with consistent schemas.

**Proposed architecture**:
```
Archive (local ZIPs + filled CSVs)
  ↓ Polars (read + transform)
Normalized DataFrames (standardized schema)
  ↓ Partition by (trade_type, data_type, date)
Parquet files (columnar)
  ↓ Load
DuckDB (local analytics) ─ OR ─ Iceberg (catalog-driven lakehouse)
```

**Key design decisions**:
- **Polars**: Already in dependencies. LazyFrame for efficient streaming transforms.
- **Parquet as interchange format**: Universal columnar format, works with DuckDB, Iceberg,
  Polars, Pandas, Spark.
- **DuckDB first**: Local SQL analytics without external infrastructure.
- **Iceberg later**: When catalog-driven schema evolution and multi-engine access are needed.
- **Incremental loads**: Process only new/changed files since last run (track via lineage).

**Normalized schema** (all trade types, all data types):

```python
{
    "trade_type": str,      # "spot" | "um" | "cm"
    "data_type": str,        # "klines" | "aggTrades" | "fundingRate"
    "symbol": str,           # "BTCUSDT"
    "open_time": int,        # epoch ms (for klines)
    "open": Decimal,         # standard price fields
    "high": Decimal,
    "low": Decimal,
    "close": Decimal,
    "volume": Decimal,
    # ... type-specific fields
}
```

**Implementation order**:
1. Polars-based archive reader (read ZIP CSVs + filled CSVs)
2. Schema normalization per data type
3. Parquet writer (partitioned by trade_type/data_type/date)
4. DuckDB sink (CREATE TABLE AS, incremental INSERT)
5. Iceberg catalog integration (pyiceberg)

**Estimated effort**: 2-3 sprints (4-6 weeks)

---

This requirements document formalizes the project vision, architecture, data models, and development process. It serves as:

1. **Specification contract** for features (what + why)
2. **Design guide** for implementers (how + code flows)
3. **Test roadmap** for QA (TDD + audit checklist)
4. **Extensibility guide** for future adapters and skills

All future work should reference this document and follow the TDD + audit checklist patterns described.

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-07  
**Maintainer**: Team  
**Status**: Active (Phase 2 in progress)
