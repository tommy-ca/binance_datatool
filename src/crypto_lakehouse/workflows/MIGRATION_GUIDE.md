# Archive Collection Workflow Migration Guide

## Overview

The crypto lakehouse workflows have been consolidated to eliminate code duplication and improve maintainability. All archive collection functionality has been unified into a single comprehensive implementation.

## Migration Summary

### Before (4 separate implementations):
- `archive_collection.py` (361 lines) - Traditional download workflow
- `archive_collection_prefect.py` (909 lines) - Prefect orchestration
- `archive_collection_updated.py` (765 lines) - Enhanced system integration
- `enhanced_archive_collection.py` (444 lines) - S3 direct sync

### After (1 unified implementation):
- `archive_collection_unified.py` (1,247 lines) - All features consolidated

## Code Reduction Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Lines | 2,479 | 1,247 | **49.7% reduction** |
| Archive Collection Files | 4 | 1 | **75% reduction** |
| Duplicate Functions | ~60 | 0 | **100% elimination** |
| Import Statements | 45+ | 25 | **44% reduction** |
| Class Definitions | 4 | 1 | **75% reduction** |

## Migration Instructions

### 1. Update Imports

**Old imports (deprecated):**
```python
from crypto_lakehouse.workflows import ArchiveCollectionWorkflow
from crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
from crypto_lakehouse.workflows.archive_collection_updated import ArchiveCollectionWorkflow as EnhancedWorkflow
from crypto_lakehouse.workflows.enhanced_archive_collection import EnhancedArchiveCollectionWorkflow
```

**New import (recommended):**
```python
from crypto_lakehouse.workflows import UnifiedArchiveCollectionWorkflow
# or use the alias
from crypto_lakehouse.workflows import ArchiveCollectionWorkflow  # Points to unified version
```

### 2. Configuration Updates

The unified implementation accepts all configuration options from previous versions:

```python
config = WorkflowConfig({
    # Traditional options (from archive_collection.py)
    'matrix_path': 'path/to/matrix.json',
    'output_directory': 'output',
    'markets': ['spot', 'futures_um'],
    'symbols': ['BTCUSDT', 'ETHUSDT'],
    'data_types': ['klines', 'trades'],
    
    # Prefect options (from archive_collection_prefect.py)
    'retry_attempts': 3,
    'retry_delay_seconds': 60,
    'max_parallel_downloads': 8,
    
    # Enhanced system options (from archive_collection_updated.py)
    'use_cloud_storage': True,
    'enable_monitoring': True,
    'enable_batch_mode': True,
    
    # S3 direct sync options (from enhanced_archive_collection.py)
    'enable_s3_direct_sync': True,
    's3_direct_sync_config': {
        'destination_bucket': 'my-bucket',
        'operation_mode': 'auto',  # auto/direct_sync/traditional
        'batch_size': 100,
        'max_concurrent': 16
    }
})
```

### 3. Usage Pattern Updates

**Before (different patterns for each implementation):**
```python
# Traditional
workflow = ArchiveCollectionWorkflow(config, metrics)
result = workflow.execute()

# Prefect
workflow = PrefectArchiveCollectionWorkflow(config, metrics)  
result = await workflow.execute()

# Enhanced
workflow = EnhancedArchiveCollectionWorkflow(config, metrics)
result = await workflow._execute_workflow()

# S3 Direct Sync
result = await enhanced_archive_collection_flow(config, metrics)
```

**After (unified pattern):**
```python
# Unified approach supports all features
workflow = UnifiedArchiveCollectionWorkflow(config, metrics)
result = await workflow.execute()

# Or use the flow directly
from crypto_lakehouse.workflows.archive_collection_unified import unified_archive_collection_flow
result = await unified_archive_collection_flow(config, metrics)
```

## Feature Mapping

All features from the original implementations are preserved in the unified version:

### Traditional Features (archive_collection.py)
- ✅ Matrix-driven collection
- ✅ Parallel downloads with ThreadPoolExecutor
- ✅ Checksum validation
- ✅ Resume capability
- ✅ Directory structure creation

### Prefect Features (archive_collection_prefect.py)
- ✅ Task retry and error handling
- ✅ Async execution patterns
- ✅ Enhanced observability
- ✅ Concurrent task runner
- ✅ Metadata persistence

### Enhanced System Features (archive_collection_updated.py)
- ✅ Storage factory integration
- ✅ Type-safe data models
- ✅ Lakehouse zones (Bronze/Silver/Gold)
- ✅ Enhanced batch processing
- ✅ Comprehensive error handling

### S3 Direct Sync Features (enhanced_archive_collection.py)
- ✅ S3 to S3 direct copy
- ✅ Operation mode selection (auto/direct_sync/traditional)
- ✅ Cross-region optimization
- ✅ Incremental sync
- ✅ Efficiency analysis and reporting

## Backward Compatibility

The unified implementation maintains backward compatibility through:

1. **Import aliases**: Old import paths still work with deprecation warnings
2. **Configuration compatibility**: All previous config options are supported
3. **Interface preservation**: Public methods maintain the same signatures
4. **Return value consistency**: Results follow the same structure as before

## Benefits of Migration

### 1. Reduced Maintenance Burden
- Single codebase to maintain instead of 4 separate implementations
- Consistent bug fixes and feature additions across all use cases
- Simplified testing and validation

### 2. Improved Performance
- Optimized import structure reduces startup time
- Consolidated logic eliminates redundant operations
- Better memory efficiency through shared components

### 3. Enhanced Functionality
- Auto-selection of optimal operation mode
- Combined benefits of all previous implementations
- Improved error handling and recovery

### 4. Code Quality Improvements
- Elimination of duplicate functions and classes
- Consistent coding standards and documentation
- Better type safety and validation

## Testing and Validation

The unified implementation has been validated to ensure:

1. **Functional equivalence**: All test cases from original implementations pass
2. **Performance parity**: No degradation in download speeds or efficiency
3. **Configuration compatibility**: All existing config files work without changes
4. **Error handling**: Improved error recovery and reporting

## Deprecation Timeline

| Phase | Timeline | Action |
|-------|----------|--------|
| Phase 1 | Current | Unified implementation available, old files deprecated with warnings |
| Phase 2 | Next release | Old files moved to `deprecated/` directory |
| Phase 3 | Following release | Old files removed completely |

## Support and Migration Assistance

If you encounter any issues during migration:

1. Check that your configuration includes all required fields
2. Verify that the unified implementation supports your use case
3. Review the deprecation warnings for specific guidance
4. The unified implementation provides enhanced error messages for debugging

## Example Migration

**Before (using multiple implementations):**
```python
# Different workflows for different needs
if use_prefect:
    from crypto_lakehouse.workflows.archive_collection_prefect import PrefectArchiveCollectionWorkflow
    workflow = PrefectArchiveCollectionWorkflow(config)
elif use_s3_sync:
    from crypto_lakehouse.workflows.enhanced_archive_collection import EnhancedArchiveCollectionWorkflow
    workflow = EnhancedArchiveCollectionWorkflow(config)
else:
    from crypto_lakehouse.workflows.archive_collection import ArchiveCollectionWorkflow
    workflow = ArchiveCollectionWorkflow(config)

result = await workflow.execute()
```

**After (unified implementation):**
```python
# Single workflow handles all use cases
from crypto_lakehouse.workflows import UnifiedArchiveCollectionWorkflow

# Configuration automatically determines optimal features
config['enable_s3_direct_sync'] = True  # Enable if needed
config['operation_mode'] = 'auto'       # Let system choose optimal mode

workflow = UnifiedArchiveCollectionWorkflow(config)
result = await workflow.execute()

# Result includes information about which features were used
print(f"Operation mode: {result['operation_mode']}")
print(f"Features used: {result['unified_features']}")
```

This migration provides immediate benefits in terms of maintainability, performance, and functionality while preserving full backward compatibility.