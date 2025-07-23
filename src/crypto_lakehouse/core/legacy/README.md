# Legacy Observability Files

## ⚠️ DEPRECATED

These files have been superseded by the unified observability module located at:
`src/crypto_lakehouse/core/observability/`

## Migration Guide

### Old Pattern:
```python
from crypto_lakehouse.core.unified_observability import unified_observability_context
from crypto_lakehouse.core.otel_metrics import CryptoLakehouseMetrics
```

### New Pattern:
```python
from crypto_lakehouse.core.observability import observability_context
from crypto_lakehouse.core.observability import CryptoLakehouseMetrics
```

## Removal Timeline

- **Phase 1** (Current): Files moved to legacy/ directory
- **Phase 2** (3 months): Legacy directory marked for removal
- **Phase 3** (6 months): Complete removal of legacy files

## Files in this Directory

All files in this directory are deprecated and will be removed in a future version:

- `auto_instrumentation.py` → Use `observability/unified.py`
- `context_propagation.py` → Use `observability/tracing.py`
- `crypto_workflow_tracing.py` → Use `observability/tracing.py`
- `logging_adapter.py` → Use `observability/logging.py`
- `manual_instrumentation.py` → Use `observability/unified.py`
- `otel_config.py` → Use `observability/config.py`
- `otel_logging.py` → Use `observability/logging.py`
- `otel_metrics.py` → Use `observability/metrics.py`
- `otel_tracing.py` → Use `observability/tracing.py`
- `performance_monitoring.py` → Use `observability/metrics.py`
- `tracing_exports.py` → Use `observability/tracing.py`
- `unified_observability.py` → Use `observability/unified.py`
- `unified_otel.py` → Use `observability/config.py`

## Support

For migration assistance, refer to the comprehensive refactoring documentation:
- `REFACTORING_COMPLETION_REPORT.md`
- `REFACTORING_SPECIFICATIONS.yml`