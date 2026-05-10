---
title: Migrate Binance Exchange Clients to Official SDK
type: refactor
status: completed
date: 2026-05-08
completed: 2026-05-08
origin: docs/brainstorms/2026-05-08-binance-sdk-migration-requirements.md
---

# Migrate Binance Exchange Clients to Official SDK

## Overview

Replace hand-rolled `aiohttp`-based Binance REST and WebSocket clients with official auto-generated SDKs (`binance-sdk-spot`, `binance-sdk-derivatives-trading-usds-futures`, `binance-sdk-derivatives-trading-coin-futures`). Keep the `archive/` module (S3 access) intact.

## Problem Frame

The `exchange/` module uses raw `aiohttp` calls for Binance REST API (`/api/v3/klines`) and WebSocket streams (`@kline_*`). The official Binance Python SDK provides auto-generated, OpenAPI-spec-driven clients with better maintenance, full API coverage, and official support. Migrating reduces hand-maintained transport code and aligns with Binance's recommended patterns.

The `archive/` module (`data.binance.vision` S3 access) is a separate concern and stays unchanged.

## Requirements Trace

- R1. Replace `aiohttp` REST with SDK `rest_api` calls for Spot, UM, CM
- R2. Replace `aiohttp` WS with SDK `websocket_streams` for Spot, UM, CM
- R3. Preserve `ExchangeClient` protocol (async generator interface for `stream_ohlcv`)
- R4. Preserve backward-compatible aliases (`BinanceRestClient`, `BinanceWsClient`)
- R5. Keep `archive/` module unchanged
- R6. Add SDK packages as required dependencies
- R7. Update tests to validate SDK-based clients
- R8. Follow SOLID/KISS/DRY/YAGNI

## Scope Boundaries

- **In scope**: `exchange/binance_rest.py`, `exchange/binance_ws.py`, `exchange/__init__.py`, `pyproject.toml`, test files for exchange clients
- **Out of scope**: `archive/` module, CLI layer, workflow layer, CCXT clients, common/ types
- **Non-goal**: Adding trading features (orders, account mgmt) — only replace transport layer

## Context & Research

### Relevant Code and Patterns

- **ExchangeClient protocol**: `src/binance_datatool/exchange/client.py` — `fetch_ohlcv`, `stream_ohlcv`, `close`, `exchange_id`, `trade_type`
- **Current REST clients**: `src/binance_datatool/exchange/binance_rest.py` — `_BinanceRestClientBase` + market-type subclasses, auto-pagination via `_KLINES_LIMIT = 1000`
- **Current WS clients**: `src/binance_datatool/exchange/binance_ws.py` — `_BinanceWsClientBase` + market-type subclasses, async generator pattern via `aiohttp.ws_connect`
- **Backward compat**: `BinanceRestClient = BinanceSpotRestClient`, `BinanceWsClient = BinanceSpotWsClient`
- **Tests**: `tests/test_exchange.py` — protocol conformance, base URL validation, WS URL building, interval validation
- **KlineData**: `src/binance_datatool/common/types.py` — 10-field dataclass
- **Dependencies**: `pyproject.toml` — `aiohttp`, `python-binance`, `tenacity`, optional `ccxt`

### Official SDK Structure

| Package | Market | Base Class | REST URL | WS URL |
|---------|--------|------------|----------|--------|
| `binance-sdk-spot` | Spot | `Spot` | `api.binance.com/api/v3` | `stream.binance.com:9443` |
| `binance-sdk-derivatives-trading-usds-futures` | UM | `DerivativesTradingUsdsFutures` | `fapi.binance.com/fapi/v1` | `fstream.binance.com` |
| `binance-sdk-derivatives-trading-coin-futures` | CM | `DerivativesTradingUsdsFutures` | `dapi.binance.com/dapi/v1` | `dstream.binance.com` |

All SDKs use `binance_common.configuration` for `ConfigurationRestAPI` and `ConfigurationWebSocketStreams`.

### Institutional Learnings

- `@dataclass` preferred over Pydantic models (29 dataclasses, 0 Pydantic models)
- `aiohttp` used everywhere with `async with` context managers
- Let-it-crash mindset — no silent recovery or defensive branches
- Google-style docstrings for public modules
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"`

### External References

- SDK Migration Guide: https://github.com/binance/binance-connector-python/blob/master/MIGRATION.md
- SDK REST Example: `binance-sdk-spot` REST API via `client.rest_api.klines(symbol, interval, limit)`
- SDK WS Example: `client.websocket_streams.create_connection()` → `connection.kline()` → `stream.on("message", handler)`

## Key Technical Decisions

- **Async generator preservation**: Wrap SDK callback-based WS streams using `asyncio.Queue` bridge. Users of `ExchangeClient` see no API change.
- **No auth**: Pass empty `api_key`/`api_secret` to `ConfigurationRestAPI` — only public market data endpoints are used.
- **SDK response mapping**: SDK REST returns typed Pydantic models → map fields to our `KlineData` dataclass. WS returns raw dicts → parse directly.
- **aiohttp kept**: Still needed by `archive/` module for S3 access. Remove `python-binance` dependency (replaced by SDK).
- **Keep `_api_base` tests**: Expose SDK configuration's `base_path` for URL tests (or remove base URL tests — SDK manages URLs).

## Open Questions

### Resolved During Planning

- Async generator interface → Keep it, wrap SDK callbacks
- Required vs optional deps → Required (user preference)
- Keep aiohttp → Yes, archive module needs it

### Deferred to Implementation

- [Research] Exact SDK method name for klines REST endpoint (likely `rest_api.klines()`)
- [Research] Exact SDK method name for klines WS stream (likely `connection.kline()`)
- [Research] Whether SDK's `ConfigurationRestAPI` works with empty api_key/api_secret for public endpoints
- [Technical] Response model structure — map Pydantic models vs raw JSON to KlineData
- [Technical] Whether SDK WS streams support all three market types (Spot, UM, CM) — need to verify coin-futures SDK

## Implementation Units

- [ ] **Unit 1: Update pyproject.toml dependencies**

**Goal:** Replace `python-binance` with official SDK packages.

**Requirements:** R6

**Dependencies:** None

**Files:**
- Modify: `pyproject.toml`

**Approach:**
- Remove `python-binance>=1.0.32` from dependencies
- Add `binance-sdk-spot>=8.0.0`, `binance-sdk-derivatives-trading-usds-futures>=9.0.0`, `binance-sdk-derivatives-trading-coin-futures>=1.0.0`
- Keep `aiohttp` (needed by `archive/` module)
- Keep `tenacity` (still used elsewhere in the codebase)
- Keep optional `ccxt` dependency (`[exchange]` extra)
- Run `uv sync` to lock dependencies

**Test scenarios:**
- Happy path: `uv sync` succeeds and installs SDK packages
- Verification: `python -c "import binance_sdk_spot; print(binance_sdk_spot.__version__)"` works

**Verification:**
- `uv sync` exits successfully
- SDK packages importable

---

- [ ] **Unit 2: Implement SDK-based Binance REST clients**

**Goal:** Replace `aiohttp`-based `_BinanceRestClientBase` with SDK-based clients.

**Requirements:** R1, R3, R4, R8

**Dependencies:** Unit 1

**Files:**
- Modify: `src/binance_datatool/exchange/binance_rest.py`
- Test: `tests/test_exchange.py` (update `TestBinanceRestClients`)

**Approach:**
- Create new `_BinanceRestClientBase` that initializes SDK client for each market type
- For Spot: initialize `Spot(config_rest_api=ConfigurationRestAPI(api_key="", api_secret="", base_path=SPOT_REST_API_PROD_URL))`
- For UM: initialize `DerivativesTradingUsdsFutures(config_rest_api=...)` with UM base URL
- For CM: initialize the Coin Futures SDK equivalent with CM base URL
- Implement `fetch_ohlcv()` using SDK's `rest_api.klines()` method with auto-pagination (keep pagination logic — SDK does not auto-paginate)
- Map SDK response to `KlineData` — either via `.data()` or direct dict parsing
- Preserve `exchange_id`, `trade_type` properties
- Preserve `testnet` support for Spot
- Preserve backward-compatible aliases

**Patterns to follow:**
- Current pagination logic in `BinanceSpotRestClient.fetch_ohlcv()` — reuse the same auto-pagination loop
- SDK REST example: `client.rest_api.klines(symbol="BTCUSDT", interval="1m", limit=500)`

**Test scenarios:**
- Happy path: Client initializes with correct SDK configuration
- Happy path: `exchange_id` and `trade_type` match expected values
- Happy path: Interval validation rejects invalid intervals (same as current test)
- Error path: Client raises on SDK initialization failure (invalid base URL)
- Verification: `isinstance(client, ExchangeClient)` passes
- Verification: Backward compatibility aliases work

**Deferred:**
- SDK response model — determine `.data()` vs dict parsing during implementation
- Whether empty api_key works — test during implementation, fall back to dummy key if needed

---

- [ ] **Unit 3: Implement SDK-based Binance WebSocket clients**

**Goal:** Replace `aiohttp`-based WS clients with SDK `websocket_streams` using async generator wrapper.

**Requirements:** R2, R3, R4, R8

**Dependencies:** Unit 1

**Files:**
- Modify: `src/binance_datatool/exchange/binance_ws.py`
- Test: `tests/test_exchange.py` (update `TestBinanceWsClients`)

**Approach:**
- Create new `_BinanceWsClientBase` that initializes SDK WS configuration for each market type
- Use `ConfigurationWebSocketStreams(stream_url=...)` per market type
- Initialize Spot SDK with `config_ws_streams` for Spot WS, similarly for UM/CM using their respective SDK classes
- Implement `stream_ohlcv()` as async generator using `asyncio.Queue` bridge:
  ```python
  async def stream_ohlcv(self, symbol, interval):
      queue = asyncio.Queue()
      connection = await self._client.websocket_streams.create_connection()
      stream = await connection.kline(symbol=symbol.lower(), interval=interval)
      stream.on("message", queue.put_nowait)
      try:
          while True:
              data = await queue.get()
              k = data["k"]
              yield KlineData(
                  open_time=int(k["t"]),
                  open=str(k["o"]),
                  high=str(k["h"]),
                  low=str(k["l"]),
                  close=str(k["c"]),
                  volume=str(k["v"]),
                  close_time=int(k["T"]),
                  quote_volume=str(k["q"]),
                  num_trades=int(k["n"]),
                  taker_buy_volume=str(k["V"]),
                  taker_buy_quote_volume=str(k["Q"]),
              )
      finally:
          await connection.close_connection(close_session=True)
  ```
- Keep `exchange_id`, `trade_type` properties
- Keep `close()` method (no longer no-op — needs to clean up resources)
- Keep `fetch_ohlcv()` raising `NotImplementedError`
- Preserve backward-compatible aliases

**Patterns to follow:**
- SDK WS example: `connection = await client.websocket_streams.create_connection()` + `stream.on("message", handler)`
- Current kline data field mapping (same Binance WS JSON structure)

**Test scenarios:**
- Happy path: Client initializes with correct SDK WS configuration
- Happy path: `exchange_id` and `trade_type` match expected values
- Verification: `isinstance(client, ExchangeClient)` passes
- Verification: Backward compatibility aliases work
- Note: Remove `_build_stream_url` and WS base URL tests — SDK manages URLs internally

---

- [ ] **Unit 4: Update `exchange/__init__.py` exports**

**Goal:** Ensure all exports, aliases, and `__all__` list are correct for SDK-based clients.

**Requirements:** R4

**Dependencies:** Units 2, 3

**Files:**
- Modify: `src/binance_datatool/exchange/__init__.py`

**Approach:**
- Verify imports reference new SDK-based client classes
- Verify backward-compatible aliases (`BinanceRestClient`, `BinanceWsClient`) still exported
- Verify CCXT imports unchanged
- No changes needed unless class names changed

**Test scenarios:**
- Happy path: All symbols importable from `binance_datatool.exchange`
- Verification: `from binance_datatool.exchange import BinanceRestClient` works

---

- [ ] **Unit 5: Update exchange tests for SDK-based clients**

**Goal:** Update `test_exchange.py` to validate SDK-based clients instead of aiohttp-based ones.

**Requirements:** R7

**Dependencies:** Units 2, 3, 4

**Files:**
- Modify: `tests/test_exchange.py`

**Approach:**
- Keep `TestExchangeClientProtocol` (protocol conformance tests stay the same)
- Update `TestBackwardCompatibility` (stays the same — aliases unchanged)

- **Update** `TestBinanceRestClients`:
  - Remove tests that check `_api_base` (SDK manages URLs internally)
  - Remove or refactor `test_spot_rest_api_base`, `test_um_rest_api_base`, `test_cm_rest_api_base`
  - Remove `test_spot_rest_testnet` (or re-test via SDK configuration)
  - Keep `test_rest_clients_have_same_interface` (still valid)
  - Add basic tests: client initializes, `exchange_id` is correct, `trade_type` is correct

- **Update** `TestBinanceWsClients`:
  - Remove tests that check `_build_stream_url` and base URL assertions
  - Remove `test_spot_ws_url`, `test_um_ws_url`, `test_cm_ws_url`
  - Remove `test_spot_ws_testnet_url`
  - Keep `test_ws_clients_have_same_interface` (still valid)

- **Keep** `TestIntervalValidation` (interval validation logic should still work)

- **Keep** `TestCCXTExchangeClient` (CCXT unchanged)

- Add new tests:
  - Verify SDK client is initialized correctly for each market type
  - Verify `fetch_ohlcv` raises appropriate errors (NotImplementedError for WS, ValueError for invalid intervals)
  - Verify `close()` method exists and is callable
  - Verify `stream_ohlcv` raises NotImplementedError for REST clients

**Test scenarios:**
- Happy path: Each market type client passes `isinstance(client, ExchangeClient)`
- Happy path: Each market type client has correct `exchange_id` and `trade_type`
- Happy path: `BinanceRestClient` is `BinanceSpotRestClient`
- Happy path: `BinanceWsClient` is `BinanceSpotWsClient`
- Edge case: Interval validation still rejects invalid intervals
- Integration (marked): SDK clients can be initialized (no network call needed for init)

---

- [ ] **Unit 6: Remove unused `python-binance` import if present**

**Goal:** Clean up any remaining references to `python-binance` package.

**Requirements:** R6

**Dependencies:** Units 2, 3

**Files:**
- Read-only search: grep for `python-binance`, `from binance.`, `from binance.client`

**Approach:**
- Search for `python-binance` imports in codebase
- If found in any exchange/ or common/ file, remove/replace them
- Note: This is likely a clean-up pass — the old codebase used `python-binance` but the current code may not import it directly.

**Test scenarios:**
- Verification: No `binance.` imports remain in src/binance_datatool/

---

- [ ] **Unit 7: Update docs (requirements, architecture, specs-driven-development)**

**Goal:** Update documentation to reflect SDK migration and data flows.

**Requirements:** R8

**Dependencies:** All units above

**Files:**
- Modify: `docs/requirements.md`
- Modify: `docs/architecture.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/specs-driven-development.md` (if applicable)

**Approach:**
- **requirements.md**: Add requirements for SDK migration, mark old aiohttp-based requirements as superseded. Include DataOps/MLOps flow descriptions.
- **architecture.md**: Update the exchange/ module description to mention SDK-backed implementation. Add data flow diagrams showing SDK interaction.
- **INDEX.md**: Update status matrix if needed.
- **specs-driven-development.md**: Add SDK migration section if applicable.

**Data flow documentation:**
```
User Code
  ↓ fetch_ohlcv()
ExchangeClient (protocol)
  ↓ SDK rest_api.klines()
Binance REST API (api.binance.com)
  ↓
SDK Response (Pydantic model)
  ↓ map to KlineData
User Code ← list[KlineData]

User Code
  ↓ stream_ohlcv()
ExchangeClient (protocol)
  ↓ SDK websocket_streams.create_connection()
  ↓ stream.on("message", queue.put_nowait)
Binance WebSocket Stream (stream.binance.com)
  ↓
async generator yields KlineData ← asyncio.Queue
```

---

- [ ] **Unit 8: Update AGENTS.md**

**Goal:** Document SDK migration decision and workflow for future agents.

**Requirements:** R8

**Dependencies:** All units above

**Files:**
- Modify: `AGENTS.md`

**Approach:**
- Note: `AGENTS.md` at repo root is the canonical agent instructions
- Add section documenting:
  - SDK dependency: `binance-sdk-spot`, `binance-sdk-derivatives-trading-usds-futures`, `binance-sdk-derivatives-trading-coin-futures`
  - Archive client: remains `aiohttp`-based (intentionally)
  - Async generator WS wrapper pattern
  - How to add/update exchange clients
  - Backward compatibility aliases

---

- [ ] **Unit 9: Run tests and validate**

**Goal:** Ensure all 216+ tests pass after SDK migration, archive module unchanged.

**Requirements:** R5, R7

**Dependencies:** All units above

**Files:**
- Read-only: `tests/` directory

**Approach:**
- Run `uv run pytest` and fix any failures
- Run `uv run ruff check .` to ensure linting passes
- Run `uv run ruff format . --check` to ensure formatting is correct
- Verify `git diff` shows no changes to `archive/` directory
- Run targeted exchange tests: `uv run pytest tests/test_exchange.py -v`

**Test scenarios:**
- Happy path: All 216+ tests pass
- Happy path: Lint and format checks pass
- Edge case: Archive module has zero changes in git diff

---

## System-Wide Impact

- **Interaction graph**: Exchange clients used by workflow layer indirectly (via `adapter/` module). Review `adapter/bridge.py` and `workflow/_shared.py` for any direct `aiohttp` usage that should use SDK instead.
- **Error propagation**: SDK raises its own exceptions (requests, Pydantic validation). Our clients should let them propagate (let-it-crash).
- **State lifecycle risks**: WS connection lifecycle is now managed by SDK + our async generator wrapper. Ensure `close()` properly cleans up connections.
- **API surface parity**: CCXT clients remain unchanged. `ExchangeClient` protocol unchanged.

## Risks & Dependencies

- **SDK Python version**: SDK requires Python >= 3.10. Our project already requires >= 3.11, so no conflict.
- **SDK bug risk**: The SDK is auto-generated and may have bugs. Mitigated by existing tests + E2E validation.
- **WS connection lifecycle**: SDK's `create_connection()` + `close_connection()` pattern differs from current `async with aiohttp.ClientSession()`. Need to ensure proper cleanup.
- **Empty API keys**: Unknown if SDK's `ConfigurationRestAPI` accepts empty api_key/api_secret. Fallback: use dummy key or make config optional. (Deferred to implementation.)
- **CM (coin-futures) SDK availability**: Verify `binance-sdk-derivatives-trading-coin-futures` has the same WebSocket stream API as UM SDK.

## Sources & References

- **Origin document**: [docs/brainstorms/2026-05-08-binance-sdk-migration-requirements.md](path)
- SDK packages: https://github.com/binance/binance-connector-python
- SDK migration guide: https://github.com/binance/binance-connector-python/blob/master/MIGRATION.md
