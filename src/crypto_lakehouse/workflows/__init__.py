"""
Workflow implementations for the crypto lakehouse platform.

This module contains concrete workflow implementations that extend the base
framework to provide specific data collection and processing capabilities.

MIGRATION NOTICE:
The archive collection functionality has been unified into a single comprehensive
implementation. The old separate implementations are now deprecated:
- archive_collection.py -> Use UnifiedArchiveCollectionWorkflow
- archive_collection_prefect.py -> Use UnifiedArchiveCollectionWorkflow
- archive_collection_updated.py -> Use UnifiedArchiveCollectionWorkflow  
- enhanced_archive_collection.py -> Use UnifiedArchiveCollectionWorkflow

The new unified implementation provides all features from the previous implementations
with improved maintainability and reduced code duplication.
"""

import warnings
from .archive_collection_unified import UnifiedArchiveCollectionWorkflow

# Primary export - use the unified implementation
ArchiveCollectionWorkflow = UnifiedArchiveCollectionWorkflow

# Deprecated imports with warnings for backward compatibility
def _deprecated_import_warning(old_name: str, new_name: str):
    """Issue deprecation warning for old imports."""
    warnings.warn(
        f"{old_name} is deprecated. Use {new_name} instead. "
        f"The old implementation will be removed in a future version.",
        DeprecationWarning,
        stacklevel=3
    )

# Lazy imports with deprecation warnings for backward compatibility
def __getattr__(name: str):
    if name == "PrefectArchiveCollectionWorkflow":
        _deprecated_import_warning("PrefectArchiveCollectionWorkflow", "UnifiedArchiveCollectionWorkflow")
        # Redirect to unified implementation
        return UnifiedArchiveCollectionWorkflow
    elif name == "EnhancedArchiveCollectionWorkflow":
        _deprecated_import_warning("EnhancedArchiveCollectionWorkflow", "UnifiedArchiveCollectionWorkflow")
        # Redirect to unified implementation
        return UnifiedArchiveCollectionWorkflow
    elif name in ["archive_collection_flow", "enhanced_archive_collection_flow"]:
        _deprecated_import_warning(name, "unified_archive_collection_flow")
        from .archive_collection_unified import unified_archive_collection_flow
        return unified_archive_collection_flow
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "ArchiveCollectionWorkflow",
    "UnifiedArchiveCollectionWorkflow",
    # Deprecated but supported for backward compatibility
    "PrefectArchiveCollectionWorkflow", 
    "EnhancedArchiveCollectionWorkflow"
]