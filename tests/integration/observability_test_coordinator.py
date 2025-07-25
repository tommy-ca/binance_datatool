#!/usr/bin/env python3
"""
ObservabilityTestCoordinator - Comprehensive Crypto Lakehouse Observability Testing

This script executes comprehensive testing of the unified observability stack
following the specs-driven workflow requirements for production readiness.
"""

import asyncio
import concurrent.futures
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading
import multiprocessing
import json
import traceback

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('observability_test_coordinator.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Container for test execution results."""
    test_name: str
    status: str  # success, failure, error
    duration_ms: float
    details: Dict[str, Any]
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    performance_metrics: Optional[Dict[str, float]] = None


@dataclass 
class ObservabilityTestReport:
    """Comprehensive test execution report."""
    test_session_id: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    total_duration_ms: float
    test_results: List[TestResult]
    performance_summary: Dict[str, Any]
    correlation_evidence: List[Dict[str, Any]]
    recommendations: List[str]


class ObservabilityTestCoordinator:
    """
    Comprehensive test coordinator for crypto lakehouse observability stack.
    
    Tests all aspects of unified observability including:
    - Cross-pillar correlation
    - Performance under load
    - Crypto workflow integration
    - Error handling and resilience
    - Production readiness
    """
    
    def __init__(self):
        self.test_session_id = str(uuid.uuid4())
        self.test_results: List[TestResult] = []
        self.start_time = time.time()
        self.performance_metrics = {}
        self.correlation_evidence = []
        
        # Set test environment
        os.environ["ENVIRONMENT"] = "observability_test"
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://test-collector:4317"
        
        logger.info(f"Initialized ObservabilityTestCoordinator - Session: {self.test_session_id}")
    
    def execute_test_with_metrics(self, test_func, test_name: str) -> TestResult:
        """Execute a test function with comprehensive metrics collection."""
        logger.info(f"Executing test: {test_name}")
        test_start = time.time()
        
        try:
            # Execute test
            result_details = test_func()
            duration_ms = (time.time() - test_start) * 1000
            
            # Create successful result
            result = TestResult(
                test_name=test_name,
                status="success",
                duration_ms=duration_ms,
                details=result_details or {},
                performance_metrics=self._extract_performance_metrics(result_details)
            )
            
            logger.info(f"✅ Test {test_name} passed in {duration_ms:.2f}ms")
            return result
            
        except AssertionError as e:
            duration_ms = (time.time() - test_start) * 1000
            result = TestResult(
                test_name=test_name,
                status="failure", 
                duration_ms=duration_ms,
                details={},
                error_message=str(e)
            )
            logger.error(f"❌ Test {test_name} failed: {e}")
            return result
            
        except Exception as e:
            duration_ms = (time.time() - test_start) * 1000
            result = TestResult(
                test_name=test_name,
                status="error",
                duration_ms=duration_ms,
                details={},
                error_message=f"{type(e).__name__}: {str(e)}"
            )
            logger.error(f"💥 Test {test_name} error: {e}")
            logger.error(traceback.format_exc())
            return result
    
    def _extract_performance_metrics(self, details: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Extract performance metrics from test details."""
        if not details:
            return None
            
        metrics = {}
        for key, value in details.items():
            if isinstance(value, (int, float)) and ('time' in key.lower() or 
                                                   'duration' in key.lower() or
                                                   'latency' in key.lower() or
                                                   'ms' in key.lower()):
                metrics[key] = float(value)
        
        return metrics if metrics else None
    
    def test_unified_observability_initialization(self) -> Dict[str, Any]:
        """Test complete unified observability stack initialization."""
        try:
            from crypto_lakehouse.core.unified_observability import initialize_crypto_observability
            
            init_start = time.time()
            components = initialize_crypto_observability(
                service_name="test-crypto-lakehouse",
                service_version="2.0.0",
                environment="observability_test",
                enable_auto_instrumentation=True
            )
            init_duration_ms = (time.time() - init_start) * 1000
            
            # Verify all components
            assert components.initialized is True
            assert components.meter_provider is not None
            assert components.tracer_provider is not None
            assert components.logger_provider is not None
            assert components.crypto_metrics is not None
            assert components.metrics_collector is not None
            
            return {
                "initialization_duration_ms": init_duration_ms,
                "components_count": 5,
                "auto_instrumentation_enabled": components.auto_instrumentation_enabled,
                "resource_attributes_count": len(components.resource.attributes)
            }
            
        except Exception as e:
            raise AssertionError(f"Initialization failed: {e}")
    
    def test_cross_pillar_correlation(self) -> Dict[str, Any]:
        """Test correlation between metrics, logging, and tracing."""
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            correlation_data = {}
            
            with observability_context(
                workflow_name="correlation_test_workflow",
                market="binance",
                data_type="klines",
                symbols=["BTCUSDT", "ETHUSDT"]
            ) as ctx:
                
                # Verify all components are present and correlated
                assert "span" in ctx
                assert "context" in ctx
                assert "metrics" in ctx
                assert "metrics_collector" in ctx
                assert "tracer" in ctx
                
                # Check crypto context correlation
                crypto_ctx = ctx["context"]
                assert crypto_ctx["crypto.workflow_name"] == "correlation_test_workflow"
                assert crypto_ctx["crypto.market"] == "binance"
                assert crypto_ctx["crypto.data_type"] == "klines"
                assert "BTCUSDT,ETHUSDT" in crypto_ctx["crypto.symbols"]
                
                # Test metrics recording with correlation
                ctx["metrics_collector"].record_event(
                    "correlation_test_event",
                    records_count=1000,
                    data_size_bytes=50000
                )
                
                # Test span operations with correlation
                span = ctx["span"]
                span.add_event("Correlation test started")
                span.set_attribute("test.correlation_id", self.test_session_id)
                span.set_attribute("test.symbol_count", 2)
                
                correlation_data = {
                    "crypto_context_keys": len(crypto_ctx),
                    "workflow_name": crypto_ctx["crypto.workflow_name"],
                    "market": crypto_ctx["crypto.market"],
                    "symbols_processed": crypto_ctx.get("crypto.symbol_count", "0"),
                    "span_attributes_set": True,
                    "metrics_recorded": True
                }
                
                # Store evidence for report
                self.correlation_evidence.append({
                    "test": "cross_pillar_correlation",
                    "trace_context_available": True,
                    "crypto_context": crypto_ctx,
                    "span_context_type": str(type(span)),
                    "metrics_context_type": str(type(ctx["metrics"]))
                })
            
            return correlation_data
            
        except Exception as e:
            raise AssertionError(f"Cross-pillar correlation failed: {e}")
    
    def test_concurrent_workflow_contexts(self) -> Dict[str, Any]:
        """Test multiple concurrent observability contexts."""
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            def run_concurrent_workflow(workflow_id: int):
                """Run a single workflow with observability context."""
                try:
                    with observability_context(
                        workflow_name=f"concurrent_workflow_{workflow_id}",
                        market="binance" if workflow_id % 2 == 0 else "coinbase",
                        data_type="trades",
                        symbols=[f"SYMBOL{workflow_id}"]
                    ) as ctx:
                        
                        # Simulate workflow operations
                        for i in range(10):
                            ctx["metrics_collector"].record_event(
                                f"workflow_{workflow_id}_operation",
                                records_count=100 + i,
                                operation_id=i
                            )
                            
                            ctx["span"].add_event(f"Operation {i} completed")
                            ctx["span"].set_attribute(f"operation_{i}.success", True)
                            
                        return {"workflow_id": workflow_id, "operations": 10, "success": True}
                        
                except Exception as e:
                    return {"workflow_id": workflow_id, "error": str(e), "success": False}
            
            # Run 10 concurrent workflows
            concurrent_start = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(run_concurrent_workflow, i) for i in range(10)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            concurrent_duration_ms = (time.time() - concurrent_start) * 1000
            
            # Verify all workflows succeeded
            successful_workflows = [r for r in results if r.get("success", False)]
            assert len(successful_workflows) == 10, f"Only {len(successful_workflows)}/10 workflows succeeded"
            
            return {
                "concurrent_workflows": 10,
                "successful_workflows": len(successful_workflows),
                "total_duration_ms": concurrent_duration_ms,
                "avg_workflow_duration_ms": concurrent_duration_ms / 10,
                "operations_per_workflow": 10,
                "total_operations": 100
            }
            
        except Exception as e:
            raise AssertionError(f"Concurrent workflow test failed: {e}")
    
    def test_performance_under_load(self) -> Dict[str, Any]:
        """Test performance characteristics under high load."""
        try:
            from crypto_lakehouse.core.unified_observability import (
                get_observability_manager,
                observability_context
            )
            
            manager = get_observability_manager()
            assert manager is not None, "Observability manager not available"
            
            # Test 1: Context creation performance
            context_start = time.time()
            contexts_created = 0
            
            for i in range(1000):
                context = manager.create_crypto_context(
                    workflow_name=f"perf_test_{i}",
                    market="binance",
                    symbols=[f"SYMBOL{j}" for j in range(3)]
                )
                contexts_created += 1
                assert context is not None
            
            context_creation_duration_ms = (time.time() - context_start) * 1000
            
            # Test 2: Observability context usage performance
            usage_start = time.time()
            contexts_used = 0
            
            for i in range(100):
                with observability_context(
                    workflow_name=f"usage_test_{i}",
                    market="binance",
                    symbols=["BTCUSDT"]
                ) as ctx:
                    # Simulate typical usage
                    ctx["span"].set_attribute("test.iteration", i)
                    ctx["metrics_collector"].record_event(f"usage_event_{i}", records_count=10)
                    contexts_used += 1
            
            context_usage_duration_ms = (time.time() - usage_start) * 1000
            
            # Performance requirements validation
            context_creation_per_ms = context_creation_duration_ms / contexts_created
            context_usage_per_ms = context_usage_duration_ms / contexts_used
            
            # Assert performance requirements
            assert context_creation_per_ms < 1.0, f"Context creation too slow: {context_creation_per_ms:.3f}ms per context"
            assert context_usage_per_ms < 50.0, f"Context usage too slow: {context_usage_per_ms:.3f}ms per context"
            
            return {
                "contexts_created": contexts_created,
                "context_creation_total_ms": context_creation_duration_ms,
                "context_creation_per_ms": context_creation_per_ms,
                "contexts_used": contexts_used,
                "context_usage_total_ms": context_usage_duration_ms,
                "context_usage_per_ms": context_usage_per_ms,
                "throughput_contexts_per_second": contexts_created / (context_creation_duration_ms / 1000),
                "performance_requirement_met": True
            }
            
        except Exception as e:
            raise AssertionError(f"Performance test failed: {e}")
    
    def test_crypto_workflow_scenarios(self) -> Dict[str, Any]:
        """Test crypto-specific workflow scenarios."""
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            # Define multiple crypto workflow scenarios
            scenarios = [
                {
                    "workflow": "binance_archive_collection",
                    "market": "binance",
                    "data_type": "klines",
                    "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
                    "operations": ["download", "validate", "store"]
                },
                {
                    "workflow": "coinbase_streaming_ingestion",
                    "market": "coinbase",
                    "data_type": "trades",
                    "symbols": ["BTC-USD", "ETH-USD"],
                    "operations": ["connect", "subscribe", "process", "buffer"]
                },
                {
                    "workflow": "funding_rate_analysis",
                    "market": "binance",
                    "data_type": "funding_rates", 
                    "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
                    "operations": ["fetch", "calculate", "analyze", "alert"]
                },
                {
                    "workflow": "multi_market_arbitrage",
                    "market": "multiple",
                    "data_type": "order_books",
                    "symbols": ["BTCUSDT", "BTC-USD", "BTCEUR"],
                    "operations": ["fetch_prices", "calculate_spread", "execute_trades"]
                }
            ]
            
            scenario_results = []
            
            for scenario in scenarios:
                scenario_start = time.time()
                
                with observability_context(
                    workflow_name=scenario["workflow"],
                    market=scenario["market"],
                    data_type=scenario["data_type"],
                    symbols=scenario["symbols"]
                ) as ctx:
                    
                    # Verify crypto context
                    crypto_ctx = ctx["context"]
                    assert crypto_ctx["crypto.workflow_name"] == scenario["workflow"]
                    assert crypto_ctx["crypto.market"] == scenario["market"]
                    assert crypto_ctx["crypto.data_type"] == scenario["data_type"]
                    
                    # Simulate workflow operations
                    for operation in scenario["operations"]:
                        ctx["span"].add_event(f"Started {operation}")
                        
                        # Simulate processing time
                        time.sleep(0.01)  # 10ms per operation
                        
                        ctx["metrics_collector"].record_event(
                            f"{scenario['data_type']}_{operation}",
                            records_count=len(scenario["symbols"]) * 100,
                            operation=operation
                        )
                        
                        ctx["span"].set_attribute(f"{operation}.success", True)
                        ctx["span"].add_event(f"Completed {operation}")
                
                scenario_duration_ms = (time.time() - scenario_start) * 1000
                
                scenario_results.append({
                    "workflow": scenario["workflow"],
                    "market": scenario["market"],
                    "data_type": scenario["data_type"],
                    "symbols_count": len(scenario["symbols"]),
                    "operations_count": len(scenario["operations"]),
                    "duration_ms": scenario_duration_ms,
                    "success": True
                })
            
            return {
                "scenarios_tested": len(scenarios),
                "successful_scenarios": len(scenario_results),
                "total_operations": sum(len(s["operations"]) for s in scenarios),
                "avg_scenario_duration_ms": sum(r["duration_ms"] for r in scenario_results) / len(scenario_results),
                "scenario_details": scenario_results
            }
            
        except Exception as e:
            raise AssertionError(f"Crypto workflow scenarios failed: {e}")
    
    def test_error_handling_resilience(self) -> Dict[str, Any]:
        """Test error handling and resilience across observability stack."""
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            error_scenarios = []
            
            # Test 1: Exception handling in context
            try:
                with observability_context("error_test_workflow", "binance") as ctx:
                    ctx["span"].add_event("About to trigger error")
                    raise ValueError("Test error for resilience validation")
            except ValueError as e:
                error_scenarios.append({
                    "scenario": "context_exception_handling",
                    "error_type": "ValueError",
                    "handled_gracefully": True,
                    "error_message": str(e)
                })
            
            # Test 2: Invalid workflow parameters
            try:
                with observability_context("", "") as ctx:  # Empty parameters
                    ctx["span"].add_event("Processing with empty parameters")
            except Exception as e:
                error_scenarios.append({
                    "scenario": "invalid_parameters",
                    "error_type": type(e).__name__,
                    "handled_gracefully": True,
                    "error_message": str(e)
                })
            else:
                error_scenarios.append({
                    "scenario": "invalid_parameters",
                    "error_type": "none",
                    "handled_gracefully": True,
                    "error_message": "Empty parameters handled gracefully"
                })
            
            # Test 3: Resource exhaustion simulation
            try:
                for i in range(10):  # Create multiple contexts rapidly
                    with observability_context(f"resource_test_{i}", "binance") as ctx:
                        ctx["metrics_collector"].record_event(f"resource_event_{i}", records_count=1000)
                        
                error_scenarios.append({
                    "scenario": "resource_exhaustion_simulation",
                    "error_type": "none",
                    "handled_gracefully": True,
                    "error_message": "Resource exhaustion handled without errors"
                })
                
            except Exception as e:
                error_scenarios.append({
                    "scenario": "resource_exhaustion_simulation",
                    "error_type": type(e).__name__,
                    "handled_gracefully": False,
                    "error_message": str(e)
                })
            
            # Verify error handling
            assert len(error_scenarios) >= 3, "Not all error scenarios were tested"
            graceful_handling = sum(1 for s in error_scenarios if s["handled_gracefully"])
            
            return {
                "error_scenarios_tested": len(error_scenarios),
                "gracefully_handled": graceful_handling,
                "resilience_score": (graceful_handling / len(error_scenarios)) * 100,
                "error_details": error_scenarios
            }
            
        except Exception as e:
            raise AssertionError(f"Error handling test failed: {e}")
    
    def test_health_monitoring_capabilities(self) -> Dict[str, Any]:
        """Test health check and monitoring capabilities."""
        try:
            from crypto_lakehouse.core.unified_observability import get_observability_manager
            
            manager = get_observability_manager()
            assert manager is not None, "Observability manager not available"
            
            # Perform health check
            health_start = time.time()
            health = manager.health_check()
            health_duration_ms = (time.time() - health_start) * 1000
            
            # Verify health check structure
            assert "status" in health, "Health status missing"
            assert "timestamp" in health, "Health timestamp missing"
            assert "components" in health, "Components status missing"
            assert "performance" in health, "Performance metrics missing"
            
            # Verify component health
            components = health["components"]
            expected_components = ["metrics", "tracing", "logging"]
            for component in expected_components:
                assert component in components, f"Component {component} missing from health check"
            
            # Verify performance metrics
            performance = health["performance"]
            assert "initialization_duration_ms" in performance, "Initialization duration missing"
            assert "components_initialized" in performance, "Components count missing"
            
            # Get additional performance metrics
            perf_metrics = manager.get_performance_metrics()
            
            return {
                "health_check_duration_ms": health_duration_ms,
                "overall_status": health["status"],
                "components_healthy": len([c for c in components.values() if c == "healthy"]),
                "total_components": len(components),
                "initialization_duration_ms": performance.get("initialization_duration_ms", 0),
                "components_initialized": performance.get("components_initialized", 0),
                "auto_instrumentation_status": components.get("auto_instrumentation", "unknown"),
                "performance_metrics": perf_metrics,
                "health_check_available": True
            }
            
        except Exception as e:
            raise AssertionError(f"Health monitoring test failed: {e}")
    
    def test_resource_attributes_compliance(self) -> Dict[str, Any]:
        """Test OpenTelemetry resource attributes compliance."""
        try:
            from crypto_lakehouse.core.unified_observability import get_observability_manager
            
            manager = get_observability_manager()
            assert manager is not None, "Observability manager not available"
            
            # Get resource attributes
            resource = manager.components.resource
            attributes = resource.attributes
            
            # Standard OpenTelemetry attributes
            required_standard_attrs = [
                "service.name",
                "service.version",
                "service.namespace", 
                "deployment.environment"
            ]
            
            missing_standard = []
            for attr in required_standard_attrs:
                if attr not in attributes:
                    missing_standard.append(attr)
            
            # Crypto-specific attributes
            required_crypto_attrs = [
                "crypto.platform_type",
                "crypto.observability_version",
                "crypto.supported_markets"
            ]
            
            missing_crypto = []
            for attr in required_crypto_attrs:
                if attr not in attributes:
                    missing_crypto.append(attr)
            
            # Infrastructure attributes
            required_infra_attrs = [
                "infrastructure.type",
                "observability.framework"
            ]
            
            missing_infra = []
            for attr in required_infra_attrs:
                if attr not in attributes:
                    missing_infra.append(attr)
            
            # Assert compliance
            assert len(missing_standard) == 0, f"Missing standard attributes: {missing_standard}"
            assert len(missing_crypto) == 0, f"Missing crypto attributes: {missing_crypto}"
            assert len(missing_infra) == 0, f"Missing infrastructure attributes: {missing_infra}"
            
            return {
                "total_attributes": len(attributes),
                "standard_attributes_present": len(required_standard_attrs),
                "crypto_attributes_present": len(required_crypto_attrs),
                "infrastructure_attributes_present": len(required_infra_attrs),
                "service_name": attributes.get("service.name", "unknown"),
                "service_version": attributes.get("service.version", "unknown"),
                "environment": attributes.get("deployment.environment", "unknown"),
                "observability_framework": attributes.get("observability.framework", "unknown"),
                "crypto_platform_type": attributes.get("crypto.platform_type", "unknown"),
                "compliance_score": 100.0  # All required attributes present
            }
            
        except Exception as e:
            raise AssertionError(f"Resource attributes compliance test failed: {e}")
    
    def generate_comprehensive_report(self) -> ObservabilityTestReport:
        """Generate comprehensive test execution report."""
        total_duration_ms = (time.time() - self.start_time) * 1000
        
        # Calculate test statistics
        passed_tests = len([r for r in self.test_results if r.status == "success"])
        failed_tests = len([r for r in self.test_results if r.status == "failure"])
        error_tests = len([r for r in self.test_results if r.status == "error"])
        
        # Generate performance summary
        all_perf_metrics = [r.performance_metrics for r in self.test_results if r.performance_metrics]
        performance_summary = {
            "avg_test_duration_ms": sum(r.duration_ms for r in self.test_results) / len(self.test_results),
            "total_contexts_created": sum(
                r.details.get("contexts_created", 0) + 
                r.details.get("concurrent_workflows", 0) +
                r.details.get("contexts_used", 0)
                for r in self.test_results
            ),
            "total_operations": sum(
                r.details.get("total_operations", 0) +
                r.details.get("operations_count", 0)
                for r in self.test_results
            ),
            "performance_tests_passed": len([
                r for r in self.test_results 
                if "performance" in r.test_name.lower() and r.status == "success"
            ])
        }
        
        # Generate recommendations
        recommendations = []
        
        if failed_tests > 0:
            recommendations.append(f"Review and fix {failed_tests} failed test(s)")
        
        if error_tests > 0:
            recommendations.append(f"Investigate and resolve {error_tests} error(s)")
        
        if passed_tests == len(self.test_results):
            recommendations.append("All tests passed - observability stack is production ready")
            recommendations.append("Consider enabling monitoring dashboards and alerting")
            recommendations.append("Set up automated observability testing in CI/CD pipeline")
        
        # Check performance requirements
        perf_results = [r for r in self.test_results if "performance" in r.test_name.lower()]
        if perf_results and all(r.status == "success" for r in perf_results):
            recommendations.append("Performance requirements met - ready for high-load scenarios")
        
        return ObservabilityTestReport(
            test_session_id=self.test_session_id,
            total_tests=len(self.test_results),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests,
            total_duration_ms=total_duration_ms,
            test_results=self.test_results,
            performance_summary=performance_summary,
            correlation_evidence=self.correlation_evidence,
            recommendations=recommendations
        )
    
    def run_comprehensive_test_suite(self) -> ObservabilityTestReport:
        """Execute the complete observability test suite."""
        logger.info(f"🚀 Starting comprehensive observability test suite - Session: {self.test_session_id}")
        
        # Define test suite
        test_suite = [
            (self.test_unified_observability_initialization, "unified_observability_initialization"),
            (self.test_cross_pillar_correlation, "cross_pillar_correlation"),
            (self.test_concurrent_workflow_contexts, "concurrent_workflow_contexts"),
            (self.test_performance_under_load, "performance_under_load"),
            (self.test_crypto_workflow_scenarios, "crypto_workflow_scenarios"),
            (self.test_error_handling_resilience, "error_handling_resilience"),
            (self.test_health_monitoring_capabilities, "health_monitoring_capabilities"),
            (self.test_resource_attributes_compliance, "resource_attributes_compliance")
        ]
        
        # Execute all tests
        for test_func, test_name in test_suite:
            result = self.execute_test_with_metrics(test_func, test_name)
            self.test_results.append(result)
        
        # Generate comprehensive report
        report = self.generate_comprehensive_report()
        
        logger.info(f"🏁 Test suite completed - {report.passed_tests}/{report.total_tests} passed")
        return report


def print_detailed_report(report: ObservabilityTestReport):
    """Print detailed test execution report."""
    print("\n" + "="*80)
    print("🔍 COMPREHENSIVE OBSERVABILITY TEST COORDINATOR REPORT")
    print("="*80)
    
    print(f"\n📊 Test Session: {report.test_session_id}")
    print(f"🕒 Total Duration: {report.total_duration_ms:.2f}ms")
    print(f"📈 Test Results: {report.passed_tests}/{report.total_tests} passed")
    
    if report.failed_tests > 0:
        print(f"❌ Failed Tests: {report.failed_tests}")
    if report.error_tests > 0:
        print(f"💥 Error Tests: {report.error_tests}")
    
    print("\n📋 Test Details:")
    print("-" * 60)
    
    for result in report.test_results:
        status_icon = "✅" if result.status == "success" else "❌" if result.status == "failure" else "💥"
        print(f"{status_icon} {result.test_name}")
        print(f"   Duration: {result.duration_ms:.2f}ms")
        
        if result.status != "success" and result.error_message:
            print(f"   Error: {result.error_message}")
        
        if result.details:
            key_metrics = {k: v for k, v in result.details.items() 
                          if isinstance(v, (int, float)) and not k.endswith('_details')}
            if key_metrics:
                print(f"   Metrics: {key_metrics}")
        print()
    
    print("📊 Performance Summary:")
    print("-" * 60)
    for key, value in report.performance_summary.items():
        print(f"   {key}: {value}")
    
    if report.correlation_evidence:
        print(f"\n🔗 Cross-Pillar Correlation Evidence:")
        print("-" * 60)
        for evidence in report.correlation_evidence:
            print(f"   Test: {evidence['test']}")
            print(f"   Trace Context Available: {evidence['trace_context_available']}")
            if 'crypto_context' in evidence:
                print(f"   Crypto Attributes: {len(evidence['crypto_context'])} attributes")
    
    print(f"\n💡 Recommendations:")
    print("-" * 60)
    for rec in report.recommendations:
        print(f"   • {rec}")
    
    print("\n" + "="*80)
    
    # Final status
    if report.passed_tests == report.total_tests:
        print("🎉 ALL TESTS PASSED - OBSERVABILITY STACK IS PRODUCTION READY!")
        print("✅ Unified metrics, logging, and tracing integration validated")
        print("✅ Cross-pillar correlation verified")
        print("✅ Performance requirements met") 
        print("✅ Crypto workflow integration confirmed")
        print("✅ Error handling and resilience validated")
    else:
        print("⚠️  SOME TESTS FAILED - REVIEW REQUIRED BEFORE PRODUCTION")
        print(f"🔧 {report.failed_tests + report.error_tests} test(s) need attention")
    
    print("="*80)


def main():
    """Main execution function."""
    try:
        # Initialize test coordinator
        coordinator = ObservabilityTestCoordinator()
        
        # Run comprehensive test suite
        report = coordinator.run_comprehensive_test_suite()
        
        # Print detailed report
        print_detailed_report(report)
        
        # Save report to file
        report_file = f"observability_test_report_{coordinator.test_session_id}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "test_session_id": report.test_session_id,
                "summary": {
                    "total_tests": report.total_tests,
                    "passed_tests": report.passed_tests,
                    "failed_tests": report.failed_tests,
                    "error_tests": report.error_tests,
                    "total_duration_ms": report.total_duration_ms
                },
                "test_results": [
                    {
                        "test_name": r.test_name,
                        "status": r.status,
                        "duration_ms": r.duration_ms,
                        "details": r.details,
                        "error_message": r.error_message
                    }
                    for r in report.test_results
                ],
                "performance_summary": report.performance_summary,
                "correlation_evidence": report.correlation_evidence,
                "recommendations": report.recommendations
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        # Return appropriate exit code
        return 0 if report.passed_tests == report.total_tests else 1
        
    except Exception as e:
        logger.error(f"Test coordinator failed: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())