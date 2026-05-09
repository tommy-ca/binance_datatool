---
date: 2026-05-09
topic: realtime-streaming-relay
---

# Real-Time WebSocket Streaming: Batch Sink + Live Relay

## Dual Pipeline Architecture

WebSocket data flows through two parallel paths:

```
Binance WS Stream (fstream.binance.com)
  │
  ├── Path A: Batch Sink ──────────────────────────────────┐
  │   │                                                      │
  │   ▼                                                      │
  │  DataBuffer (asyncio.Queue per symbol+channel)           │
  │   │                                                      │
  │   ├── micro-batch every N seconds (configurable)         │
  │   │   format: list[dict] → Polars DataFrame              │
  │   │   normalize: Bronze→Silver transform                 │
  │   │                                                        │
  │   ├── DuckLake: INSERT INTO klines / fundingRate         │
  │   │   (ACID, snapshot managed by DuckLake)               │
  │   │                                                        │
  │   └── Parquet: write to catalog path (same as sink)      │
  │      data/exchange=.../data-type=.../symbol=.../.../      │
  │      filename: data.parquet                               │
  │                                                            │
  ├── Path B: Live Relay ───────────────────────────────────┐
  │   │                                                      │
  │   ▼                                                      │
  │  Normalizer (→ SilverSchema)                             │
  │   │                                                      │
  │   ├── ExchangeClient.stream_ohlcv() → AsyncIterator      │
  │   │   (existing, used by traders)                        │
  │   │                                                      │
  │   └── StreamingForwarder                                 │
  │       publish normalized records to:                     │
  │       ├── asyncio.Queue (in-process subscribers)         │
  │       ├── WebSocket (out-of-process relay)               │
  │       └── ZeroMQ / NATS (future, for multi-server)       │
```

## Path A: Batch Sink

### Micro-Batch Collector

```python
class StreamBatcher:
    """Buffer WS messages and flush in micro-batches."""

    def __init__(self, table_name: str, batch_interval: float = 5.0):
        self._table = table_name
        self._buf: list[dict] = []
        self._interval = batch_interval
        self._lock = asyncio.Lock()

    def on_message(self, msg: dict) -> None:
        self._buf.append(msg)

    async def flush(self, sink: SinkWorkflow) -> int:
        """Convert buffer to DataFrame, write to DuckLake/Silver."""
        async with self._lock:
            if not self._buf:
                return 0
            batch = self._buf
            self._buf = []
        df = pl.DataFrame(batch)
        df = _bronze_to_silver(df, ...)  # reuse existing transform
        df = _add_silver_metadata(df, ...)
        # Write to DuckLake via ingest_parquet
        # Or write Parquet directly
        return len(df)
```

### Configuration

```python
@dataclass
class StreamConfig:
    symbols: list[str]
    channels: list[str]       # "markPrice", "kline_1m", "aggTrade"
    batch_interval: float = 5.0
    batch_max_rows: int = 10000
    sink_target: str = "duckdb"  # parquet, duckdb, both
    relay_enabled: bool = False
```

## Path B: Live Relay

### Existing Pattern (already works)

```python
# Current ExchangeClient.stream_ohlcv() returns AsyncIterator[KlineData]
async for kline in client.stream_ohlcv("BTCUSDT", "1m"):
    # Process each kline as it arrives
    # latency: ~100-500ms from exchange event
    print(kline)
```

### Proposed Extension: stream_funding_rate()

```python
class BinanceUmWsClient(_BinanceWsClientBase):

    async def stream_funding_rate(
        self, symbol: str
    ) -> AsyncIterator[FundingRateData]:
        """Stream real-time funding rate data (markPrice stream)."""
        queue: asyncio.Queue = asyncio.Queue()
        await self._connect()

        stream = self._connection.mark_price_stream(symbol=symbol.lower())
        stream.on("message", lambda msg: queue.put_nowait(msg))

        try:
            while True:
                data = await queue.get()
                yield FundingRateData(
                    ts_event=int(data["E"]),
                    funding_rate=float(data.get("r", 0)),
                    mark_price=float(data.get("p", 0)),
                    index_price=float(data.get("i", 0)),
                    predicted_funding_rate=float(data.get("R", 0)),
                )
        finally:
            await self.close()
```

### WebSocket Relay Server

```python
class StreamRelay:
    """Relay normalized Silver records to external subscribers."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(q)
        return q

    async def publish(self, channel: str, record: Any) -> None:
        for q in self._subscribers.get(channel, []):
            await q.put(record)
```

## CLI Commands

```bash
# Start streaming with batch sink (Phase 8)
binance-datatool stream funding-rate \
    --symbol BTCUSDT \
    --batch-interval 5 \
    --target duckdb

binance-datatool stream klines \
    --symbol BTCUSDT \
    --interval 1m \
    --batch-interval 10 \
    --target parquet

# Start streaming with live relay
binance-datatool stream mark-price \
    --symbol BTCUSDT \
    --relay-port 8765

# List active streams
binance-datatool stream list
```

## Schema Extensions for WS Fields

### FundingRate (16 cols, +4 from WS)

| Field | Source | WS Key |
|-------|--------|--------|
| `funding_rate` | Archive/REST/WS | `markPrice.r` |
| `mark_price` | Archive/REST/WS | `markPrice.p` |
| `index_price` | **WS only** | `markPrice.i` |
| `predicted_funding_rate` | **WS only** | `markPrice.R` |
| `last_price` | **WS only** | `24hrTicker.c` |
| `open_interest` | **WS only** | `contractInfo.oi` |

## File Organization (proposed)

```
src/binance_datatool/
├── exchange/              (existing — WS clients)
├── workflow/
│   ├── sink.py            (existing — batch Bronze→Silver)
│   └── stream.py          (new — WS streaming pipeline)
├── cli/
│   └── stream.py          (new — stream command)
└── ...
```
