"""Automatic instrumentation setup for crypto lakehouse components."""

import logging
import os
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.trace import Span

logger = logging.getLogger(__name__)


class AutoInstrumentationManager:
    """Manages automatic instrumentation for crypto lakehouse components."""
    
    def __init__(self):
        self._instrumented_modules: List[str] = []
        self._excluded_urls: List[str] = [
            "health", "metrics", "ping", "status", 
            "localhost:8000/health", "127.0.0.1:8000/health"
        ]
        
    def initialize_all_instrumentation(
        self,
        enable_requests: bool = True,
        enable_aiohttp: bool = True,
        enable_boto3: bool = True,
        enable_database: bool = True,
        enable_redis: bool = True,
        custom_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize all available automatic instrumentation."""
        config = custom_config or {}
        
        if enable_requests:
            self._setup_requests_instrumentation(config.get("requests", {}))
            
        if enable_aiohttp:
            self._setup_aiohttp_instrumentation(config.get("aiohttp", {}))
            
        if enable_boto3:
            self._setup_boto3_instrumentation(config.get("boto3", {}))
            
        if enable_database:
            self._setup_database_instrumentation(config.get("database", {}))
            
        if enable_redis:
            self._setup_redis_instrumentation(config.get("redis", {}))
            
        logger.info(f"Auto-instrumentation initialized for modules: {self._instrumented_modules}")
    
    def _setup_requests_instrumentation(self, config: Dict[str, Any]):
        """Setup requests library instrumentation."""
        try:
            RequestsInstrumentor().instrument(
                span_callback=self._enrich_requests_span,
                excluded_urls=config.get("excluded_urls", self._excluded_urls)
            )
            self._instrumented_modules.append("requests")
            logger.info("Requests instrumentation enabled")
            
        except Exception as e:
            logger.warning(f"Failed to instrument requests: {e}")
    
    def _setup_aiohttp_instrumentation(self, config: Dict[str, Any]):
        """Setup aiohttp client instrumentation."""
        try:
            AioHttpClientInstrumentor().instrument(
                span_callback=self._enrich_aiohttp_span,
                excluded_urls=config.get("excluded_urls", self._excluded_urls)
            )
            self._instrumented_modules.append("aiohttp_client")
            logger.info("AioHTTP client instrumentation enabled")
            
        except Exception as e:
            logger.warning(f"Failed to instrument aiohttp: {e}")
    
    def _setup_boto3_instrumentation(self, config: Dict[str, Any]):
        """Setup AWS Boto3 instrumentation."""
        try:
            from opentelemetry.instrumentation.boto3sqs import Boto3SQSInstrumentor
            
            Boto3SQSInstrumentor().instrument()
            self._instrumented_modules.append("boto3_sqs")
            logger.info("Boto3 SQS instrumentation enabled")
            
        except ImportError:
            logger.debug("Boto3 SQS instrumentation not available")
        except Exception as e:
            logger.warning(f"Failed to instrument Boto3: {e}")
    
    def _setup_database_instrumentation(self, config: Dict[str, Any]):
        """Setup database instrumentation (PostgreSQL, SQLAlchemy)."""
        # PostgreSQL instrumentation
        try:
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
            
            Psycopg2Instrumentor().instrument(
                enable_commenter=True,
                commenter_options={"opentelemetry_values": False}
            )
            self._instrumented_modules.append("psycopg2")
            logger.info("PostgreSQL (psycopg2) instrumentation enabled")
            
        except ImportError:
            logger.debug("psycopg2 instrumentation not available")
        except Exception as e:
            logger.warning(f"Failed to instrument psycopg2: {e}")
        
        # SQLAlchemy instrumentation
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            
            SQLAlchemyInstrumentor().instrument(
                enable_commenter=True,
                commenter_options={"opentelemetry_values": False}
            )
            self._instrumented_modules.append("sqlalchemy")
            logger.info("SQLAlchemy instrumentation enabled")
            
        except ImportError:
            logger.debug("SQLAlchemy instrumentation not available")
        except Exception as e:
            logger.warning(f"Failed to instrument SQLAlchemy: {e}")
    
    def _setup_redis_instrumentation(self, config: Dict[str, Any]):
        """Setup Redis instrumentation."""
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            
            RedisInstrumentor().instrument()
            self._instrumented_modules.append("redis")
            logger.info("Redis instrumentation enabled")
            
        except ImportError:
            logger.debug("Redis instrumentation not available")
        except Exception as e:
            logger.warning(f"Failed to instrument Redis: {e}")
    
    def _enrich_requests_span(self, span: Span, request, response=None):
        """Enrich requests spans with crypto-specific attributes."""
        if not span or not request:
            return
            
        url = getattr(request, 'url', str(request))
        
        # Parse URL for crypto market detection
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or ""
        
        # Crypto exchange detection
        crypto_market = self._detect_crypto_market(hostname, url)
        if crypto_market:
            span.set_attribute("crypto.market", crypto_market)
            span.set_attribute("crypto.api_type", "rest")
            
            # Extract data type from URL path
            data_type = self._extract_data_type_from_url(url)
            if data_type:
                span.set_attribute("crypto.data_type", data_type)
                
            # Extract symbol if present
            symbol = self._extract_symbol_from_url(url)
            if symbol:
                span.set_attribute("crypto.symbol", symbol)
        
        # Add request size if available
        content_length = getattr(request, 'content-length', None)
        if content_length:
            span.set_attribute("http.request.body.size", content_length)
        
        # Add response attributes
        if response:
            # Response size
            response_size = len(getattr(response, 'content', b''))
            if response_size:
                span.set_attribute("http.response.body.size", response_size)
            
            # Rate limiting headers for crypto APIs
            if hasattr(response, 'headers'):
                self._add_rate_limit_attributes(span, response.headers)
                
            # Crypto-specific response attributes
            if crypto_market and hasattr(response, 'json'):
                try:
                    json_data = response.json() if callable(response.json) else response.json
                    self._add_crypto_response_attributes(span, json_data, crypto_market)
                except:
                    pass  # Ignore JSON parsing errors
    
    def _enrich_aiohttp_span(self, span: Span, params: Dict[str, Any]):
        """Enrich aiohttp spans with crypto-specific attributes."""
        if not span:
            return
            
        url = params.get('url', '')
        
        # Parse URL for crypto market detection
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or ""
        
        # Crypto exchange detection
        crypto_market = self._detect_crypto_market(hostname, url)
        if crypto_market:
            span.set_attribute("crypto.market", crypto_market)
            span.set_attribute("crypto.api_type", "rest_async")
            
            # Extract data type from URL path
            data_type = self._extract_data_type_from_url(url)
            if data_type:
                span.set_attribute("crypto.data_type", data_type)
                
            # Extract symbol if present
            symbol = self._extract_symbol_from_url(url)
            if symbol:
                span.set_attribute("crypto.symbol", symbol)
    
    def _detect_crypto_market(self, hostname: str, url: str) -> Optional[str]:
        """Detect crypto market from hostname or URL."""
        hostname_lower = hostname.lower()
        url_lower = url.lower()
        
        # Binance detection
        if any(binance_domain in hostname_lower for binance_domain in 
               ["binance.com", "binance.us", "data.binance.vision"]):
            return "binance"
        
        # Coinbase detection
        if any(coinbase_domain in hostname_lower for coinbase_domain in 
               ["coinbase.com", "pro.coinbase.com", "api.coinbase.com"]):
            return "coinbase"
        
        # Kraken detection
        if any(kraken_domain in hostname_lower for kraken_domain in 
               ["kraken.com", "api.kraken.com"]):
            return "kraken"
        
        # FTX detection (historical)
        if "ftx.com" in hostname_lower:
            return "ftx"
        
        # Generic crypto API detection
        if any(keyword in url_lower for keyword in ["crypto", "btc", "eth", "trading"]):
            return "unknown_crypto_exchange"
            
        return None
    
    def _extract_data_type_from_url(self, url: str) -> Optional[str]:
        """Extract crypto data type from URL path."""
        url_lower = url.lower()
        
        # Common crypto data endpoints
        data_type_mappings = {
            "klines": "klines",
            "candlestick": "klines", 
            "ohlc": "klines",
            "trades": "trades",
            "aggTrades": "aggTrades",
            "depth": "order_book",
            "orderbook": "order_book",
            "ticker": "ticker",
            "24hr": "ticker_24hr",
            "price": "price",
            "funding": "funding_rate",
            "fundingRate": "funding_rate",
            "liquidation": "liquidation",
            "bookTicker": "book_ticker",
            "exchangeInfo": "exchange_info"
        }
        
        for endpoint, data_type in data_type_mappings.items():
            if endpoint.lower() in url_lower:
                return data_type
                
        return None
    
    def _extract_symbol_from_url(self, url: str) -> Optional[str]:
        """Extract trading symbol from URL parameters."""
        from urllib.parse import parse_qs, urlparse
        
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            # Common symbol parameter names
            symbol_params = ["symbol", "pair", "market", "instrument"]
            
            for param in symbol_params:
                if param in query_params:
                    symbol = query_params[param][0]
                    return symbol.upper()
                    
        except Exception:
            pass
            
        return None
    
    def _add_rate_limit_attributes(self, span: Span, headers: Dict[str, str]):
        """Add rate limiting attributes from response headers."""
        rate_limit_headers = {
            "x-ratelimit-limit": "api.rate_limit.limit",
            "x-ratelimit-remaining": "api.rate_limit.remaining",
            "x-ratelimit-reset": "api.rate_limit.reset",
            "x-mbx-used-weight": "api.binance.weight_used",
            "x-mbx-used-weight-1m": "api.binance.weight_used_1m",
            "retry-after": "api.retry_after"
        }
        
        for header_name, attr_name in rate_limit_headers.items():
            header_value = headers.get(header_name) or headers.get(header_name.upper())
            if header_value:
                try:
                    # Try to convert to int if it's numeric
                    numeric_value = int(header_value)
                    span.set_attribute(attr_name, numeric_value)
                except ValueError:
                    span.set_attribute(attr_name, header_value)
    
    def _add_crypto_response_attributes(self, span: Span, response_data: Any, market: str):
        """Add crypto-specific response attributes."""
        if not isinstance(response_data, (dict, list)):
            return
            
        # For list responses (like klines, trades)
        if isinstance(response_data, list):
            span.set_attribute("crypto.response.record_count", len(response_data))
            
            # Estimate data size
            import sys
            data_size = sys.getsizeof(response_data)
            span.set_attribute("crypto.response.size_bytes", data_size)
            
        # For dict responses
        elif isinstance(response_data, dict):
            # Binance-specific attributes
            if market == "binance":
                # Server time for synchronization monitoring
                if "serverTime" in response_data:
                    span.set_attribute("crypto.server_time", response_data["serverTime"])
                
                # Symbol information
                if "symbol" in response_data:
                    span.set_attribute("crypto.symbol", response_data["symbol"])
                
                # Price information
                if "price" in response_data:
                    span.set_attribute("crypto.price", float(response_data["price"]))
                
                # Volume information
                if "volume" in response_data:
                    span.set_attribute("crypto.volume", float(response_data["volume"]))
    
    def get_instrumented_modules(self) -> List[str]:
        """Get list of successfully instrumented modules."""
        return self._instrumented_modules.copy()
    
    def is_module_instrumented(self, module_name: str) -> bool:
        """Check if a specific module is instrumented."""
        return module_name in self._instrumented_modules


# Global auto-instrumentation manager
_auto_instrumentation: Optional[AutoInstrumentationManager] = None


def get_auto_instrumentation_manager() -> AutoInstrumentationManager:
    """Get global auto-instrumentation manager."""
    global _auto_instrumentation
    if _auto_instrumentation is None:
        _auto_instrumentation = AutoInstrumentationManager()
    return _auto_instrumentation


def initialize_auto_instrumentation(
    enable_requests: bool = True,
    enable_aiohttp: bool = True,
    enable_boto3: bool = True,
    enable_database: bool = True,
    enable_redis: bool = True,
    custom_config: Optional[Dict[str, Any]] = None
):
    """Initialize automatic instrumentation (convenience function)."""
    manager = get_auto_instrumentation_manager()
    manager.initialize_all_instrumentation(
        enable_requests=enable_requests,
        enable_aiohttp=enable_aiohttp,
        enable_boto3=enable_boto3,
        enable_database=enable_database,
        enable_redis=enable_redis,
        custom_config=custom_config
    )
    return manager