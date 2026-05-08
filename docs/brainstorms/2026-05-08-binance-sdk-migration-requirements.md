---
date: 2026-05-08
topic: binance-sdk-migration
---

# Migrate Binance Exchange Clients to Official SDK

## Problem Frame
The `exchange/` module uses hand-rolled `aiohttp` clients for Binance REST and WebSocket APIs. The official Binance Python SDK (`binance-sdk-spot`, `binance-sdk-derivatives-trading-usds-futures`, `binance-sdk-derivatives-trading-coin-futures`) provides auto-generated, maintained clients from OpenAPI specs. Migrating to the official SDK improves maintainability, API coverage, and alignment with Binance's recommended patterns.

The `archive/` module (S3 access) must remain intact — it serves a different purpose (bulk downloads from `data.binance.vision`).

## Requirements
- R1. Replace `aiohttp`-based REST clients with official Binance SDK (`binance-sdk-spot` for Spot, `binance-sdk-derivatives-trading-usds-futures` for UM, `binance-sdk-derivatives-trading-coin-futures` for CM).
- R2. Replace `aiohttp`-based WebSocket clients with official SDK WebSocket streams/clients.
- R3. Preserve the `ExchangeClient` protocol interface (`fetch_ohlcv`, `stream_ohlcv`, `close`, `exchange_id`, `trade_type`).
- R4. Keep async generator pattern for `stream_ohlcv()` — wrap SDK's callback-based streams internally.
- R5. Keep `archive/` module completely intact (no changes to S3, download, verify workflows).
- R6. Add SDK packages as required dependencies in `pyproject.toml`.
- R7. Update all tests to work with SDK-based clients.
- R8. Follow SOLID, KISS, DRY, YAGNI principles throughout.

## Success Criteria
- All 216+ existing tests pass after migration.
- E2E validation passes for Spot, UM, CM market types.
- Code is simpler or equal in complexity compared to hand-rolled clients.
- `archive/` module untouched — `git diff` shows no changes there.

## Scope Boundaries
- **In scope**: `exchange/binance_rest.py`, `exchange/binance_ws.py`, `pyproject.toml`, tests.
- **Out of scope**: `archive/` module, CLI layer, workflow layer (unless they need minor interface adjustments).
- **Non-goal**: Add new features from SDK (trading, account mgmt) — only replace transport layer.

## Key Decisions
- **Required dependencies**: SDK packages are required, not optional (matching user preference).
- **Async generator preservation**: Wrap callbacks internally to keep `ExchangeClient` protocol unchanged.
- **No archive changes**: S3 archive access remains `aiohttp`-based (different concern).

## Dependencies / Assumptions
- Python >= 3.10 required by SDK packages (current project uses 3.11+).
- SDK packages provide equivalent klines/kline streams endpoints.
- `binance-common` package provides shared `ConfigurationRestAPI`, `ConfigurationWebSocketStreams` base classes.

## Outstanding Questions

### Deferred to Planning
- [Technical] How to map SDK response models (Pydantic) to our `KlineData` dataclass efficiently?
- [Technical] Should we keep the shared `_BinanceRestClientBase` or create separate classes for each market type using SDK?
- [Research] Does SDK provide `exchange_info()` or equivalent for symbol listing, or do we need to keep using REST klines endpoint?

## Next Steps
→ `/ce:plan` for structured implementation planning
