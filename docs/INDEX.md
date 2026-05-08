# Documentation Index & Project Status

## Overview

This index provides a complete picture of the binance-datatool project after comprehensive requirements, specification, and architecture review. It documents the current state, completed work, and clear path forward for implementation.

---

## 📚 Core Documentation (Read in Order)

### 1. **requirements.md** ⭐ START HERE
   - **Purpose**: Formal functional and non-functional requirements
   - **Covers**: Use cases, actors, architecture requirements, data models, pre-merge audit checklist
   - **Length**: ~400 lines
   - **Key Sections**:
     - Functional requirements (FR-1 through FR-8)
     - Non-functional requirements (NFR-1 through NFR-6)
     - Four-layer and six-layer architecture diagrams
     - Data model and contracts

### 2. **architecture.md**
   - **Purpose**: System design and layering
   - **Covers**: Package tree, four-layer design, data flow, extension roadmap
   - **Length**: ~130 lines
   - **Action Items**: Add Mermaid sequence diagrams (Phase 5)

### 3. **data-flows.md** ⭐ DETAILED FLOWS
   - **Purpose**: Step-by-step data and code flows for all commands
   - **Covers**: ASCII sequence diagrams, state transitions, error handling, multi-source adapter flow
   - **Length**: ~700 lines
   - **Key Sections**:
     - list-symbols flow (with state machine)
     - list-files flow (concurrent, resilient)
     - download flow (diff + resume + verify markers)
     - verify flow (parallel hashing)
     - multi-source adapter protocol

### 4. **specs-driven-development.md**
   - **Purpose**: Development process and standards
   - **Covers**: Spec template, TDD workflow, test structure, audit checklist, SOLID principles
   - **Length**: ~250 lines
   - **Key Sections**:
     - Spec template (use for every feature)
     - Pre-merge audit checklist (8 sections, 30+ checkboxes)
     - Test layer classification (unit, integration, E2E)

### 5. **skills-subagents.md** ⭐ AGENT INTERFACE
   - **Purpose**: Formal specification for AI agents and scripts
   - **Covers**: 5 core skills with input/output schemas, error modes, test cases
   - **Length**: ~550 lines
   - **Skills Defined**:
     - discover-symbols (list symbols with filters)
     - list-files (list data files per symbol)
     - download-partition (download with diff + resume)
     - verify-partition (hash and verify files)
     - validate-contract (schema validation + lineage)

### 6. **implementation-guide.md** ⭐ UPDATED
   - **Purpose**: Roadmap for implementing specifications
   - **Covers**: 5 implementation phases, TDD approach, code examples, checklists
   - **Length**: ~400 lines
   - **Current Phase**: Phase 4 Complete (Lineage & Observability)
   - **Completed**:
     - ✅ Phase 2: Adapter Pattern (BinanceAdapter, SourceRegistry)
     - ✅ Phase 3: Data Contracts (datacontract.py, ContractRegistry)
     - ✅ Phase 4: Lineage Tracking (lineage.py, LineageTracker)
     - ✅ Phase 6: Exchange Clients (exchange/ module)
   - **Next Steps**:
     - 🔄 OKX/Bybit via CCXT (CCXTExchangeClient)
     - ⏳ CLI integration with SourceRegistry (--source flag)
     - ⏳ Skills/subagents implementation

### 7. **audit.md**
   - **Purpose**: Findings from code review
   - **Covers**: Current implementation, risks, priorities, recommendations
   - **Priorities**:
     1. Data contracts + validation (✅ DONE: datacontract.py)
     2. Lineage tracking (✅ DONE: lineage.py)
     3. Multi-source adapter (✅ DONE: adapter/binance.py, 🔄 OKX/Bybit via CCXT)
     4. Exchange clients (✅ DONE: exchange/ module)
     5. Skills/subagents (⏳ TODO: implement from skills-subagents.md)

---

## 🔧 Code & Implementation

### DataContract (✅ IMPLEMENTED)
- **File**: `src/binance_datatool/datacontract.py`
- **Status**: Complete (24 tests, all passing)
- **What It Does**: Schema validation, custom validators, nullability rules
- **Example**:
  ```python
  contract = DataContract(
      source=DataSource.BINANCE,
      market_type=MarketType.SPOT,
      data_type=DataType.KLINES,
      schema={"open_time": int, "price": Decimal, "volume": Decimal},
      key_cols=["open_time"],
      validators=[lambda row: row["price"] > 0, ...]
  )
  result = contract.validate(data)
  ```
- **Tests**: `tests/test_datacontract.py` (24 tests)

### Adapter Pattern (🔄 IN PROGRESS)
- **File**: `src/binance_datatool/adapter/`
- **Status**: Protocol defined, awaiting implementations
- **Protocol**: `DataSourceAdapter` (5 methods: list_symbols, list_files, fetch_file, parse_symbol, get_metadata)
- **Implementations Needed**:
  - BinanceAdapter (wrap ArchiveClient)
  - CCXT unified API (okx, bybit, binance)
  - DataSourceAdapter protocol

### Skills (⏳ PLANNED)
- **Directory**: `src/binance_datatool/skills/`
- **Status**: Specifications written (skills-subagents.md)
- **Implementation Order**: Phase 3
- **5 Core Skills**:
  - discover-symbols
  - list-files
  - download-partition
  - verify-partition
  - validate-contract

---

## 📊 Project Status Matrix

| Component | Status | File | Tests | Notes |
|-----------|--------|------|-------|-------|
| **DataContract** | ✅ Complete | datacontract.py | 24 passing | Schema validation + validators |
| **DataContractRegistry** | ✅ Complete | datacontract.py | 24 passing | Lookup by (source, market, type) |
| **LineageTracker** | ✅ Complete | lineage.py | 24 passing | Data provenance tracking |
| **BinanceAdapter** | ✅ Complete | adapter/binance.py | 35 passing | Wraps ArchiveClient |
| **OKX/Bybit Adapter** | 🔄 Via CCXT | exchange/ccxt_rest.py | — | CCXTExchangeClient(trade_type="okx") |
| **SourceRegistry** | ✅ Complete | source_registry.py | 2 passing | Adapter discovery/registration |
| **Exchange Clients** | ✅ Complete | exchange/*.py | 18 passing | SDK-backed Spot/UM/CM REST + WebSocket |
| **Silver Layer** | ✅ Complete | workflow/sink.py | — | Bronze→Silver transform + Parquet/DuckDB |
| **Gap Fill + Health** | ✅ Complete | workflow/gap_fill.py, workflow/health_check.py | — | Auto-detect, lineage, health monitoring |
| **Skills (5x)** | ⏳ Planned | — | — | See skills-subagents.md |
| **MetricsCollector** | ❌ Not Started | — | — | Removed from scope |
| **CLI --source flag** | ⏳ Planned | cli/archive.py | — | Phase 2 remaining work |

---

## 🎯 Implementation Roadmap

### Phase 1: Foundation & Specification (✅ COMPLETE)
- [x] Architecture overview (architecture.md)
- [x] Formal requirements (requirements.md)
- [x] Detailed data flows (data-flows.md)
- [x] DataContract implementation & tests
- [x] Skills specification (skills-subagents.md)
- [x] Specs-driven development guide (specs-driven-development.md)
- [x] Implementation guide (implementation-guide.md)

### Phase 2: Adapter Pattern & Multi-Source (🔄 IN PROGRESS)
- [ ] LineageTracker class + tests
- [ ] BinanceAdapter implementation + tests
- [ ] OKX/Bybit via CCXT + tests
- [ ] SourceRegistry CLI integration
- [ ] Backward compatibility verification

**Estimated**: 1-2 weeks (depends on developer availability)

### Phase 3: Skills Implementation (⏳ NEXT)
- [ ] discover-symbols skill + tests (unit + integration)
- [ ] list-files skill + tests
- [ ] download-partition skill + tests
- [ ] verify-partition skill + tests
- [ ] validate-contract skill + tests

**Estimated**: 2-3 weeks

### Phase 4: Observability & Metrics (⏳ FUTURE)
- [ ] MetricsCollector class
- [ ] Emit operation counts, durations, throughput
- [ ] Optional: Prometheus endpoints

**Estimated**: 1 week

### Phase 5: Documentation & DevEx (⏳ FUTURE)
- [ ] Add Mermaid diagrams to docs
- [ ] Update AGENTS.md with development guidance
- [ ] Create contributor onboarding guide

**Estimated**: 1 week

---

## 🧪 Testing Strategy

### Test Layers

| Layer | Scope | Speed | When |
|-------|-------|-------|------|
| **Unit** | Single class/function; fakes for I/O | <100ms | Always (block merge if fail) |
| **Integration** | Workflows + real I/O (may use fixtures); marked @pytest.mark.integration | <5s | Before merge (can skip in CI) |
| **E2E** | Full CLI + real Binance API | >10s | Pre-release only |

### Current Test Status

```
✅ Exchange client tests: 18 passing (SDK-backed)
✅ DataContract tests: 24 passing
✅ LineageTracker tests: 24 passing
✅ BinanceAdapter tests: 35 passing
✅ All tests combined: 249 passing, 9 skipped
---
Target: 200+ tests — exceeded (249 passing)
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific layer
uv run pytest tests/test_datacontract.py -v

# With coverage
uv run pytest --cov=binance_datatool --cov-report=html

# Integration only
uv run pytest -m integration
```

---

## 📖 How to Use This Documentation

### For Implementers

1. **Read** `requirements.md` (understand the "why")
2. **Read** `data-flows.md` (understand the "how")
3. **Follow** `implementation-guide.md` (build the "what")
4. **Check** `specs-driven-development.md` before PR (audit checklist)

### For Code Reviewers

- Use `specs-driven-development.md` pre-merge audit checklist
- Verify PR implements one of the specifications
- Run `uv run pytest` to check all tests pass
- Run `uv run ruff check .` for linting

### For AI Agents / Subagents

- Reference `skills-subagents.md` for formal skill specifications
- Import and call skill functions from `src/binance_datatool/skills/`
- Follow error modes and retry logic documented per skill
- Example agent code:
  ```python
  from binance_datatool.skills import discover_symbols
  
  result = await discover_symbols(
      source="binance",
      market_type="spot",
      data_type="klines",
      quote_asset="USDT"
  )
  
  if result["success"]:
      print(f"Found {len(result['symbols'])} symbols")
  else:
      print(f"Error: {result['errors']}")
  ```

---

## 🏗️ Architecture at a Glance

### Current (Four Layers)
```
CLI Layer (typer commands)
  ↓
Workflow Layer (business logic)
  ↓
Archive Client Layer (S3 HTTP)
  ↓
Common Layer (enums, types, filters)
```

### Proposed (Six Layers)
```
CLI / API Layer
  ↓
Orchestration / Pipeline Layer
  ↓
DataOps / Transform Layer (validation, contracts)
  ↓
Source Adapter Layer (binance via S3, OKX/Bybit via CCXT)
  ↓
Storage Connector Layer (S3, local, delta, parquet)
  ↓
Foundation Layer (shared types, enums, filters)
```

**Key Addition**: Adapter layer abstracts source-specific behavior; enables multi-source support.

---

## 📋 Pre-Merge Checklist (Audit Checklist)

Every PR must satisfy:

```
[ ] Requirements
  [ ] Addresses explicit requirement (FR-X, NFR-X)
  [ ] Scope is small and focused

[ ] Specification
  [ ] Spec written using template from specs-driven-development.md
  [ ] All error cases documented

[ ] Tests (TDD)
  [ ] Unit tests written FIRST (failing)
  [ ] Implementation added (tests pass)
  [ ] Integration tests for I/O
  [ ] Edge cases covered

[ ] Design (SOLID / KISS / DRY / YAGNI)
  [ ] Single Responsibility
  [ ] Open/Closed
  [ ] Liskov Substitution
  [ ] Interface Segregation
  [ ] Dependency Inversion

[ ] Documentation
  [ ] Docstrings added (Google style)
  [ ] README updated (if user-facing)
  [ ] Architecture docs updated (if structural change)

[ ] Code Quality
  [ ] Tests pass: uv run pytest
  [ ] Linting passes: uv run ruff check .
  [ ] No hard-coded secrets

[ ] Ready
  [ ] All boxes checked
  [ ] Approval from 1+ reviewer
  [ ] CI pipeline green
```

Full checklist in `docs/specs-driven-development.md`.

---

## 🔗 Quick Links

| Document | Purpose | Length |
|----------|---------|--------|
| requirements.md | Formal specs & audit checklist | 400 lines |
| data-flows.md | Step-by-step command flows | 700 lines |
| architecture.md | System design & layers | 130 lines |
| specs-driven-development.md | Development process | 250 lines |
| skills-subagents.md | Agent API specs | 550 lines |
| implementation-guide.md | Build roadmap | 400 lines |
| audit.md | Code review findings | 80 lines |

---

## 💡 Key Design Principles

1. **SOLID** - Single Responsibility, Open/Closed, Liskov, Interface Segregation, Inversion of Control
2. **KISS** - Keep it simple; avoid premature abstraction
3. **DRY** - Don't repeat yourself; reuse shared logic
4. **YAGNI** - You ain't gonna need it; no speculative features
5. **TDD** - Tests first; write failing test before code
6. **Resilient** - Partial failures don't abort entire workflow
7. **Atomic** - Files written completely or not at all
8. **Observable** - Logs, metrics, lineage for debugging

---

## 🎓 Learning Path (For New Contributors)

1. Read `requirements.md` (15 min) — understand the problem
2. Read `architecture.md` (10 min) — understand the solution structure
3. Read `data-flows.md` (30 min) — understand how data moves through system
4. Review `datacontract.py` + tests (20 min) — see TDD in action
5. Follow `implementation-guide.md` Step 1 (60 min) — implement LineageTracker
6. Submit PR with audit checklist (see `specs-driven-development.md`)

Total: ~2.5 hours to complete Phase 2, Step 1.

---

## 📞 Questions & Clarifications

If unclear on:

- **Specification**: Check `skills-subagents.md` or spec template in `specs-driven-development.md`
- **Architecture**: Check `data-flows.md` or architecture diagram in `requirements.md`
- **Code examples**: Check `implementation-guide.md` or existing tests (`test_datacontract.py`, `test_source_registry.py`)
- **Development process**: Check `specs-driven-development.md` pre-merge checklist
- **Next steps**: Check `implementation-guide.md` and TODO list at end of this document

---

## 📌 Project TODO

### Immediate (Next Sprint)

- [ ] **Phase 2, Step 1**: Implement LineageTracker (lineage.py + test_lineage.py)
  - [ ] Record discovery, download, verification, validation
  - [ ] Query and serialize
  - [ ] 10+ unit tests
  - Estimated: 3-4 hours

- [ ] **Phase 2, Step 2**: Implement BinanceAdapter (adapter/binance.py + test_binance_adapter.py)
  - [ ] Wrap ArchiveClient
  - [ ] Implement protocol methods
  - [ ] 10+ unit tests + 5+ integration tests
  - Estimated: 4-5 hours

### Short Term (Phase 6 SDK Migration Complete)

- [x] Migrated exchange clients to official Binance SDK (`binance-sdk-spot`, `binance-sdk-derivatives-trading-usds-futures`, `binance-sdk-derivatives-trading-coin-futures`)
- [x] Archive client (`archive/` module) kept intact (aiohttp-based S3 access)
- [x] Tests: 249 passing, 9 skipped

### Next Steps

- [ ] Phase 2, Step 3: OKX/Bybit via CCXT skeleton
- [ ] Phase 2, Step 4: Adapter integration tests
- [ ] Phase 2, Step 5: CLI integration with SourceRegistry

### Medium Term (Phase 3)

- [ ] Implement 5 core skills (discover-symbols, list-files, download-partition, verify-partition, validate-contract)
- [ ] Write comprehensive skill tests (unit + integration)

### Long Term (Phase 4+)

- [ ] MetricsCollector for observability
- [ ] Mermaid diagrams for documentation
- [ ] Contributor onboarding guide

---

## ✨ Summary

**Status**: Foundation and specifications complete. Ready to implement Phase 2 (Adapter Pattern & Multi-Source).

**Impact**: This work enables:
- Multi-source data pipeline (Binance S3 → OKX/Bybit via CCXT)
- Contract-driven validation and lineage
- Agent-driven workflows with formal skill APIs
- Scalable, maintainable architecture
- DataOps and MLOps readiness

**Next Step**: Start Phase 2, Step 1 (LineageTracker implementation).

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-07  
**Maintainer**: Team  
**Status**: Active; implementation ready
