"""
Backward-compatible logging adapter that integrates OpenTelemetry logging
with existing legacy logging systems in the crypto lakehouse.

This module provides seamless migration from legacy logging to OpenTelemetry
while maintaining all existing logging interfaces and behaviors.
"""

import logging
import os
from typing import Optional, Dict, Any, Union
from contextlib import contextmanager

from .otel_logging import (
    OpenTelemetryLoggingConfig,
    get_otel_logging_config,
    crypto_logging_context,
    CryptoContextInjector,
    LogSamplingConfig
)

# Import legacy logging for backward compatibility
try:
    # Legacy import not available, using fallback
    from logging import getLogger as legacy_get_logger
    SimonsLogger = None
    LEGACY_LOGGING_AVAILABLE = True
except ImportError:
    LEGACY_LOGGING_AVAILABLE = False
    legacy_get_logger = None


class BackwardCompatibleCryptoLogger:
    """
    Backward-compatible logger that combines legacy SimonsLogger
    with OpenTelemetry structured logging and crypto context.
    """
    
    def __init__(
        self,
        name: str,
        enable_otel: bool = True,
        enable_legacy: bool = True,
        otel_level: int = logging.INFO,
        legacy_level: int = logging.DEBUG
    ):
        self.name = name
        self.enable_otel = enable_otel
        self.enable_legacy = enable_legacy and LEGACY_LOGGING_AVAILABLE
        
        # Initialize OpenTelemetry logger
        if self.enable_otel:
            try:
                config = get_otel_logging_config()
                self.otel_logger = config.setup_logger(name, otel_level)
                self.context_injector = config.context_injector
            except Exception as e:
                logging.warning(f"Failed to initialize OpenTelemetry logging: {e}")
                self.enable_otel = False
                self.otel_logger = None
                self.context_injector = None
        else:
            self.otel_logger = None
            self.context_injector = None
        
        # Initialize legacy logger
        if self.enable_legacy:
            try:
                self.legacy_logger = legacy_get_logger(name)
                self.legacy_logger.setLevel(legacy_level)
            except Exception as e:
                logging.warning(f"Failed to initialize legacy logging: {e}")
                self.enable_legacy = False
                self.legacy_logger = None
        else:
            self.legacy_logger = None
        
        # Fallback to standard logger if both fail
        if not self.enable_otel and not self.enable_legacy:
            self.fallback_logger = logging.getLogger(name)
        else:
            self.fallback_logger = None
    
    def _log_to_all(self, level: int, message: str, *args, **kwargs):
        """Log message to all enabled logging systems."""
        formatted_message = message % args if args else message
        
        # Log to OpenTelemetry
        if self.enable_otel and self.otel_logger:
            try:
                # Add crypto context as extra attributes
                extra = kwargs.get('extra', {})
                if self.context_injector:
                    crypto_context = self.context_injector.get_crypto_context()
                    extra.update(crypto_context)
                
                # Add operation context if provided
                if 'crypto_operation' in kwargs:
                    extra['crypto_operation'] = kwargs['crypto_operation']
                if 'crypto_symbol' in kwargs:
                    extra['crypto_symbol'] = kwargs['crypto_symbol']
                if 'crypto_market' in kwargs:
                    extra['crypto_market'] = kwargs['crypto_market']
                
                self.otel_logger.log(level, formatted_message, extra=extra, **{k: v for k, v in kwargs.items() if k != 'extra'})
            except Exception as e:
                logging.debug(f"OpenTelemetry logging failed: {e}")
        
        # Log to legacy system
        if self.enable_legacy and self.legacy_logger:
            try:
                self.legacy_logger.log(level, formatted_message)
            except Exception as e:
                logging.debug(f"Legacy logging failed: {e}")
        
        # Fallback logging
        if self.fallback_logger:
            self.fallback_logger.log(level, formatted_message)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        self._log_to_all(logging.DEBUG, message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        self._log_to_all(logging.INFO, message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        self._log_to_all(logging.WARNING, message, *args, **kwargs)
    
    def warn(self, message: str, *args, **kwargs):
        """Alias for warning (backward compatibility)."""
        self.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        self._log_to_all(logging.ERROR, message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        self._log_to_all(logging.CRITICAL, message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception with traceback."""
        kwargs['exc_info'] = True
        self.error(message, *args, **kwargs)
    
    def ok(self, message: str, *args, **kwargs):
        """Log success message (legacy compatibility)."""
        # Map 'ok' to info level with success context
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['log_type'] = 'success'
        self.info(f"✅ {message}", *args, **kwargs)
    
    @contextmanager
    def crypto_operation(
        self,
        market: str = "binance",
        symbol: str = None,
        operation: str = None,
        data_type: str = None,
        timeframe: str = None,
        workflow_id: str = None
    ):
        """Context manager for crypto operations with enhanced logging."""
        if self.context_injector:
            with self.context_injector.crypto_operation(
                market=market,
                symbol=symbol,
                operation=operation,
                data_type=data_type,
                timeframe=timeframe,
                workflow_id=workflow_id
            ):
                yield
        else:
            yield
    
    def log_crypto_event(
        self,
        level: int,
        message: str,
        market: str = "binance",
        symbol: str = None,
        operation: str = None,
        data_type: str = None,
        records_count: int = None,
        data_size_bytes: int = None,
        duration_ms: float = None,
        **kwargs
    ):
        """Log crypto-specific event with structured context."""
        extra = kwargs.get('extra', {})
        extra.update({
            'crypto_market': market,
            'crypto_symbol': symbol,
            'crypto_operation': operation,
            'crypto_data_type': data_type
        })
        
        if records_count is not None:
            extra['crypto_records_count'] = records_count
        if data_size_bytes is not None:
            extra['crypto_data_size_bytes'] = data_size_bytes
        if duration_ms is not None:
            extra['crypto_duration_ms'] = duration_ms
        
        kwargs['extra'] = extra
        self._log_to_all(level, message, **kwargs)
    
    def log_ingestion_event(
        self,
        symbol: str,
        records_count: int,
        data_size_bytes: int,
        duration_ms: float = None,
        market: str = "binance",
        data_type: str = "klines",
        timeframe: str = "1m"
    ):
        """Log data ingestion event with metrics."""
        message = f"Ingested {records_count} {data_type} records for {symbol} ({data_size_bytes:,} bytes)"
        if duration_ms:
            message += f" in {duration_ms:.2f}ms"
        
        self.log_crypto_event(
            logging.INFO,
            message,
            market=market,
            symbol=symbol,
            operation="ingestion",
            data_type=data_type,
            records_count=records_count,
            data_size_bytes=data_size_bytes,
            duration_ms=duration_ms,
            extra={'timeframe': timeframe}
        )
    
    def log_processing_event(
        self,
        operation: str,
        symbol: str = None,
        duration_ms: float = None,
        records_processed: int = None,
        success: bool = True,
        error_message: str = None
    ):
        """Log data processing event."""
        level = logging.INFO if success else logging.ERROR
        
        if success:
            message = f"Processing {operation} completed"
            if symbol:
                message += f" for {symbol}"
            if records_processed:
                message += f" ({records_processed:,} records)"
            if duration_ms:
                message += f" in {duration_ms:.2f}ms"
        else:
            message = f"Processing {operation} failed"
            if symbol:
                message += f" for {symbol}"
            if error_message:
                message += f": {error_message}"
        
        self.log_crypto_event(
            level,
            message,
            operation=operation,
            symbol=symbol,
            duration_ms=duration_ms,
            records_count=records_processed,
            extra={'success': success, 'error_message': error_message}
        )
    
    def log_workflow_event(
        self,
        workflow_name: str,
        phase: str,  # 'started', 'completed', 'failed'
        duration_ms: float = None,
        records_processed: int = None,
        error_message: str = None
    ):
        """Log workflow execution event."""
        if phase == 'started':
            level = logging.INFO
            message = f"Workflow {workflow_name} started"
        elif phase == 'completed':
            level = logging.INFO
            message = f"Workflow {workflow_name} completed successfully"
            if records_processed:
                message += f" ({records_processed:,} records processed)"
            if duration_ms:
                message += f" in {duration_ms:.2f}ms"
        elif phase == 'failed':
            level = logging.ERROR
            message = f"Workflow {workflow_name} failed"
            if error_message:
                message += f": {error_message}"
        else:
            level = logging.INFO
            message = f"Workflow {workflow_name} {phase}"
        
        self.log_crypto_event(
            level,
            message,
            operation="workflow",
            extra={
                'workflow_name': workflow_name,
                'workflow_phase': phase,
                'duration_ms': duration_ms,
                'records_processed': records_processed,
                'error_message': error_message
            }
        )


class CryptoLoggerFactory:
    """Factory for creating crypto-aware loggers with backward compatibility."""
    
    def __init__(self):
        self._loggers: Dict[str, BackwardCompatibleCryptoLogger] = {}
        self._default_config = {
            'enable_otel': os.getenv('ENABLE_OTEL_LOGGING', 'true').lower() == 'true',
            'enable_legacy': os.getenv('ENABLE_LEGACY_LOGGING', 'true').lower() == 'true',
            'otel_level': getattr(logging, os.getenv('OTEL_LOG_LEVEL', 'INFO').upper()),
            'legacy_level': getattr(logging, os.getenv('LEGACY_LOG_LEVEL', 'DEBUG').upper())
        }
    
    def get_logger(
        self,
        name: str,
        **config_overrides
    ) -> BackwardCompatibleCryptoLogger:
        """Get or create a crypto-aware logger."""
        if name not in self._loggers:
            config = {**self._default_config, **config_overrides}
            self._loggers[name] = BackwardCompatibleCryptoLogger(name, **config)
        
        return self._loggers[name]
    
    def setup_logging(
        self,
        service_name: str = "crypto-lakehouse",
        environment: str = None,
        sampling_config: LogSamplingConfig = None
    ):
        """Setup global logging configuration."""
        env = environment or os.getenv("ENVIRONMENT", "local")
        
        # Initialize OpenTelemetry logging
        if self._default_config['enable_otel']:
            try:
                get_otel_logging_config(
                    service_name=service_name,
                    environment=env,
                    sampling_config=sampling_config
                )
                logging.info(f"OpenTelemetry logging configured for {service_name} in {env}")
            except Exception as e:
                logging.warning(f"Failed to setup OpenTelemetry logging: {e}")


# Global factory instance
_logger_factory: Optional[CryptoLoggerFactory] = None


def get_crypto_logger(name: str = None, **config_overrides) -> BackwardCompatibleCryptoLogger:
    """Get a crypto-aware logger (convenience function)."""
    global _logger_factory
    
    if _logger_factory is None:
        _logger_factory = CryptoLoggerFactory()
    
    # Use calling module name if no name provided
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'crypto_lakehouse')
    
    return _logger_factory.get_logger(name, **config_overrides)


def setup_crypto_logging(
    service_name: str = "crypto-lakehouse",
    environment: str = None,
    sampling_config: LogSamplingConfig = None
):
    """Setup global crypto logging configuration."""
    global _logger_factory
    
    if _logger_factory is None:
        _logger_factory = CryptoLoggerFactory()
    
    _logger_factory.setup_logging(service_name, environment, sampling_config)


# Backward compatibility aliases
def get_logger(name: str = None) -> BackwardCompatibleCryptoLogger:
    """Backward compatible get_logger function."""
    return get_crypto_logger(name)


# Enhanced context manager for crypto operations
@contextmanager
def crypto_operation_logging(
    operation: str,
    market: str = "binance",
    symbol: str = None,
    data_type: str = None,
    logger: BackwardCompatibleCryptoLogger = None
):
    """Enhanced context manager for crypto operations with automatic logging."""
    if logger is None:
        logger = get_crypto_logger()
    
    with logger.crypto_operation(
        market=market,
        symbol=symbol,
        operation=operation,
        data_type=data_type
    ):
        logger.info(f"Starting {operation}" + (f" for {symbol}" if symbol else ""))
        start_time = None
        
        try:
            import time
            start_time = time.time()
            yield logger
            
            duration_ms = (time.time() - start_time) * 1000 if start_time else None
            logger.info(f"Completed {operation}" + (f" for {symbol}" if symbol else "") + 
                       (f" in {duration_ms:.2f}ms" if duration_ms else ""))
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000 if start_time else None
            logger.error(f"Failed {operation}" + (f" for {symbol}" if symbol else "") +
                        f": {str(e)}" + (f" after {duration_ms:.2f}ms" if duration_ms else ""),
                        exc_info=True)
            raise