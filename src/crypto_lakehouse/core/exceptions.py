"""Exception classes for the crypto lakehouse platform."""

class LakehouseException(Exception):
    """Base exception for all lakehouse errors."""
    pass

class ConfigurationError(LakehouseException):
    """Configuration related errors."""
    pass

class ValidationError(LakehouseException):
    """Validation errors."""
    pass

class WorkflowError(LakehouseException):
    """Workflow execution errors."""
    pass