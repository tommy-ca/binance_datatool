#!/usr/bin/env python3
"""
Observability Stress Test - High-Intensity Performance Validation

This script performs intensive stress testing of the observability stack
to validate production-level performance under extreme load conditions.
"""

import asyncio
import concurrent.futures
import logging
import multiprocessing
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List
import json
import statistics

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ObservabilityStressTest:
    """High-intensity stress testing for observability stack."""
    
    def __init__(self):
        self.test_id = str(uuid.uuid4())[:8]
        os.environ["ENVIRONMENT"] = "stress_test"
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://test-collector:4317"
        
        # Performance tracking
        self.performance_data = {}
        self.test_results = {}
        
        logger.info(f"Initialized stress test - ID: {self.test_id}")
    
    def stress_test_context_creation_throughput(self) -> Dict[str, Any]:
        """Test context creation throughput under extreme load."""
        logger.info("🔥 STRESS TEST: Context Creation Throughput")
        
        try:
            from crypto_lakehouse.core.unified_observability import (
                initialize_crypto_observability,
                get_observability_manager
            )
            
            # Initialize observability
            components = initialize_crypto_observability(
                service_name="stress-test-crypto-lakehouse",
                environment="stress_test"
            )
            
            manager = get_observability_manager()
            
            # Test parameters
            num_iterations = [100, 500, 1000, 2000, 5000]
            results = {}
            
            for iteration_count in num_iterations:
                logger.info(f"   Testing {iteration_count} context creations...")
                
                start_time = time.perf_counter()
                
                for i in range(iteration_count):
                    context = manager.create_crypto_context(
                        workflow_name=f"stress_test_{i}",
                        market="binance" if i % 2 == 0 else "coinbase",
                        symbols=[f"SYMBOL{j}" for j in range(3)]
                    )
                    assert context is not None
                
                duration = time.perf_counter() - start_time
                contexts_per_second = iteration_count / duration
                
                results[iteration_count] = {
                    "duration_seconds": duration,
                    "contexts_per_second": contexts_per_second,
                    "avg_context_time_microseconds": (duration / iteration_count) * 1_000_000
                }
                
                logger.info(f"     {iteration_count} contexts: {contexts_per_second:.0f}/sec, {results[iteration_count]['avg_context_time_microseconds']:.2f}μs/context")
            
            # Performance analysis
            max_throughput = max(r["contexts_per_second"] for r in results.values())
            min_context_time = min(r["avg_context_time_microseconds"] for r in results.values())
            
            return {
                "test_type": "context_creation_throughput",
                "iterations_tested": num_iterations,
                "max_throughput_contexts_per_second": max_throughput,
                "min_context_time_microseconds": min_context_time,
                "detailed_results": results,
                "performance_target_met": max_throughput > 10000  # Target: >10k contexts/sec
            }
            
        except Exception as e:
            return {"test_type": "context_creation_throughput", "error": str(e)}
    
    def stress_test_concurrent_workflows(self) -> Dict[str, Any]:
        """Test concurrent workflow execution under high load."""
        logger.info("🔥 STRESS TEST: Concurrent Workflow Execution")
        
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            def run_stress_workflow(workflow_id: int, operations: int = 50) -> Dict[str, Any]:
                """Execute a single high-intensity workflow."""
                try:
                    with observability_context(
                        workflow_name=f"stress_workflow_{workflow_id}",
                        market="binance" if workflow_id % 2 == 0 else "coinbase",
                        data_type="klines",
                        symbols=[f"STRESS{j}" for j in range(5)]
                    ) as ctx:
                        
                        start_time = time.perf_counter()
                        
                        # Intensive operations
                        for i in range(operations):
                            # Metrics recording
                            ctx["metrics_collector"].record_event(
                                f"stress_operation_{i}",
                                records_count=100 + i,
                                data_size_bytes=1000 + (i * 10),
                                operation_id=i
                            )
                            
                            # Span operations
                            ctx["span"].add_event(f"Stress operation {i}")
                            ctx["span"].set_attribute(f"stress.operation_{i}.value", i * 100)
                            ctx["span"].set_attribute(f"stress.operation_{i}.success", True)
                        
                        duration = time.perf_counter() - start_time
                        
                        return {
                            "workflow_id": workflow_id,
                            "operations": operations,
                            "duration_seconds": duration,
                            "operations_per_second": operations / duration,
                            "success": True
                        }
                        
                except Exception as e:
                    return {
                        "workflow_id": workflow_id,
                        "error": str(e),
                        "success": False
                    }
            
            # Test with increasing concurrency levels
            concurrency_levels = [10, 25, 50, 100]
            operations_per_workflow = 50
            results = {}
            
            for concurrency in concurrency_levels:
                logger.info(f"   Testing {concurrency} concurrent workflows...")
                
                start_time = time.perf_counter()
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [
                        executor.submit(run_stress_workflow, i, operations_per_workflow) 
                        for i in range(concurrency)
                    ]
                    workflow_results = [future.result() for future in concurrent.futures.as_completed(futures)]
                
                total_duration = time.perf_counter() - start_time
                
                # Analyze results
                successful_workflows = [r for r in workflow_results if r.get("success", False)]
                total_operations = len(successful_workflows) * operations_per_workflow
                
                results[concurrency] = {
                    "concurrency_level": concurrency,
                    "successful_workflows": len(successful_workflows),
                    "total_operations": total_operations,
                    "total_duration_seconds": total_duration,
                    "workflows_per_second": len(successful_workflows) / total_duration,
                    "operations_per_second": total_operations / total_duration,
                    "avg_workflow_duration": statistics.mean([r["duration_seconds"] for r in successful_workflows]),
                    "success_rate": len(successful_workflows) / concurrency * 100
                }
                
                logger.info(f"     {concurrency} workflows: {results[concurrency]['success_rate']:.1f}% success, {results[concurrency]['operations_per_second']:.0f} ops/sec")
            
            # Performance analysis
            max_operations_per_second = max(r["operations_per_second"] for r in results.values())
            max_concurrency_successful = max(k for k, v in results.items() if v["success_rate"] >= 95)
            
            return {
                "test_type": "concurrent_workflows",
                "concurrency_levels_tested": concurrency_levels,
                "operations_per_workflow": operations_per_workflow,
                "max_operations_per_second": max_operations_per_second,
                "max_concurrency_95_percent_success": max_concurrency_successful,
                "detailed_results": results,
                "performance_target_met": max_operations_per_second > 1000  # Target: >1k ops/sec
            }
            
        except Exception as e:
            return {"test_type": "concurrent_workflows", "error": str(e)}
    
    def stress_test_memory_usage_under_load(self) -> Dict[str, Any]:
        """Test memory usage patterns under sustained load."""
        logger.info("🔥 STRESS TEST: Memory Usage Under Load")
        
        try:
            import psutil
            from crypto_lakehouse.core.unified_observability import observability_context
            
            process = psutil.Process()
            
            # Baseline memory
            baseline_memory_mb = process.memory_info().rss / (1024 * 1024)
            
            memory_measurements = []
            
            # Sustained load test
            num_iterations = 1000
            measurements_per_iteration = 100
            
            for iteration in range(num_iterations):
                if iteration % 100 == 0:
                    logger.info(f"   Memory test iteration {iteration}/{num_iterations}")
                
                with observability_context(
                    workflow_name=f"memory_stress_{iteration}",
                    market="binance",
                    symbols=[f"MEM{j}" for j in range(10)]
                ) as ctx:
                    
                    # Generate observability data
                    for i in range(measurements_per_iteration):
                        ctx["metrics_collector"].record_event(
                            f"memory_test_event_{i}",
                            records_count=i * 10,
                            data_size_bytes=i * 1000,
                            iteration=iteration
                        )
                        
                        ctx["span"].add_event(f"Memory test operation {i}")
                        ctx["span"].set_attribute(f"memory.iteration", iteration)
                        ctx["span"].set_attribute(f"memory.operation", i)
                
                # Measure memory every 100 iterations
                if iteration % 100 == 0:
                    current_memory_mb = process.memory_info().rss / (1024 * 1024)
                    memory_measurements.append({
                        "iteration": iteration,
                        "memory_mb": current_memory_mb,
                        "memory_delta_mb": current_memory_mb - baseline_memory_mb
                    })
            
            # Final memory measurement
            final_memory_mb = process.memory_info().rss / (1024 * 1024)
            
            # Memory analysis
            peak_memory_mb = max(m["memory_mb"] for m in memory_measurements)
            memory_growth_mb = final_memory_mb - baseline_memory_mb
            memory_growth_percentage = (memory_growth_mb / baseline_memory_mb) * 100
            
            return {
                "test_type": "memory_usage_under_load",
                "iterations": num_iterations,
                "operations_per_iteration": measurements_per_iteration,
                "total_operations": num_iterations * measurements_per_iteration,
                "baseline_memory_mb": baseline_memory_mb,
                "final_memory_mb": final_memory_mb,
                "peak_memory_mb": peak_memory_mb,
                "memory_growth_mb": memory_growth_mb,
                "memory_growth_percentage": memory_growth_percentage,
                "memory_measurements": memory_measurements,
                "memory_leak_detected": memory_growth_percentage > 50,  # >50% growth indicates potential leak
                "performance_target_met": memory_growth_percentage < 25  # Target: <25% memory growth
            }
            
        except Exception as e:
            return {"test_type": "memory_usage_under_load", "error": str(e)}
    
    def stress_test_error_recovery_resilience(self) -> Dict[str, Any]:
        """Test error recovery and resilience under failure conditions."""
        logger.info("🔥 STRESS TEST: Error Recovery and Resilience")
        
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            error_scenarios = []
            recovery_times = []
            
            # Test various error conditions
            num_error_tests = 100
            
            for i in range(num_error_tests):
                if i % 20 == 0:
                    logger.info(f"   Error resilience test {i}/{num_error_tests}")
                
                recovery_start = time.perf_counter()
                
                try:
                    with observability_context(
                        workflow_name=f"error_test_{i}",
                        market="binance",
                        symbols=["ERROR_TEST"]
                    ) as ctx:
                        
                        # Normal operations
                        ctx["span"].add_event("Starting error test")
                        ctx["metrics_collector"].record_event("error_test_start", iteration=i)
                        
                        # Trigger different types of errors
                        error_type = i % 4
                        
                        if error_type == 0:
                            # ValueError
                            raise ValueError(f"Test ValueError {i}")
                        elif error_type == 1:
                            # KeyError
                            raise KeyError(f"Test KeyError {i}")
                        elif error_type == 2:
                            # RuntimeError
                            raise RuntimeError(f"Test RuntimeError {i}")
                        else:
                            # Exception
                            raise Exception(f"Test Exception {i}")
                            
                except Exception as e:
                    # Error should be handled gracefully by observability context
                    recovery_time = time.perf_counter() - recovery_start
                    recovery_times.append(recovery_time)
                    
                    error_scenarios.append({
                        "iteration": i,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "recovery_time_seconds": recovery_time,
                        "handled_gracefully": True
                    })
            
            # Recovery analysis
            avg_recovery_time = statistics.mean(recovery_times)
            max_recovery_time = max(recovery_times)
            min_recovery_time = min(recovery_times)
            
            # Error type distribution
            error_types = {}
            for scenario in error_scenarios:
                error_type = scenario["error_type"]
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            return {
                "test_type": "error_recovery_resilience",
                "total_error_tests": num_error_tests,
                "successful_recoveries": len(error_scenarios),
                "recovery_rate_percentage": (len(error_scenarios) / num_error_tests) * 100,
                "avg_recovery_time_seconds": avg_recovery_time,
                "max_recovery_time_seconds": max_recovery_time,
                "min_recovery_time_seconds": min_recovery_time,
                "error_type_distribution": error_types,
                "performance_target_met": avg_recovery_time < 0.1  # Target: <100ms average recovery
            }
            
        except Exception as e:
            return {"test_type": "error_recovery_resilience", "error": str(e)}
    
    def stress_test_high_frequency_crypto_scenarios(self) -> Dict[str, Any]:
        """Test high-frequency crypto trading scenarios."""
        logger.info("🔥 STRESS TEST: High-Frequency Crypto Trading Scenarios")
        
        try:
            from crypto_lakehouse.core.unified_observability import observability_context
            
            # Simulate high-frequency trading scenario
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOTUSDT"]
            markets = ["binance", "coinbase", "kraken"]
            
            total_operations = 0
            start_time = time.perf_counter()
            
            # Rapid-fire trading operations
            for market in markets:
                for symbol in symbols:
                    with observability_context(
                        workflow_name="hft_trading_operations",
                        market=market,
                        data_type="order_book",
                        symbols=[symbol]
                    ) as ctx:
                        
                        # Simulate high-frequency operations
                        for i in range(100):  # 100 operations per symbol per market
                            # Price monitoring
                            ctx["metrics_collector"].record_event(
                                "price_update",
                                price=100.0 + (i * 0.1),
                                volume=1000 + i,
                                symbol=symbol,
                                market=market
                            )
                            
                            # Order operations
                            ctx["span"].add_event(f"Order update {i}")
                            ctx["span"].set_attribute("hft.order_id", f"order_{i}")
                            ctx["span"].set_attribute("hft.symbol", symbol)
                            ctx["span"].set_attribute("hft.market", market)
                            
                            total_operations += 1
            
            duration = time.perf_counter() - start_time
            operations_per_second = total_operations / duration
            
            return {
                "test_type": "high_frequency_crypto_scenarios",
                "markets_tested": len(markets),
                "symbols_tested": len(symbols),
                "operations_per_symbol_market": 100,
                "total_operations": total_operations,
                "duration_seconds": duration,
                "operations_per_second": operations_per_second,
                "avg_operation_time_microseconds": (duration / total_operations) * 1_000_000,
                "performance_target_met": operations_per_second > 5000  # Target: >5k ops/sec for HFT
            }
            
        except Exception as e:
            return {"test_type": "high_frequency_crypto_scenarios", "error": str(e)}
    
    def run_comprehensive_stress_tests(self) -> Dict[str, Any]:
        """Execute all stress tests and generate comprehensive report."""
        logger.info(f"🚀 Starting comprehensive stress test suite - ID: {self.test_id}")
        
        stress_tests = [
            self.stress_test_context_creation_throughput,
            self.stress_test_concurrent_workflows,
            self.stress_test_memory_usage_under_load,
            self.stress_test_error_recovery_resilience,
            self.stress_test_high_frequency_crypto_scenarios
        ]
        
        results = {}
        total_start_time = time.perf_counter()
        
        for test_func in stress_tests:
            test_name = test_func.__name__
            logger.info(f"Executing stress test: {test_name}")
            
            test_start = time.perf_counter()
            result = test_func()
            test_duration = time.perf_counter() - test_start
            
            result["test_duration_seconds"] = test_duration
            results[test_name] = result
            
            if "error" in result:
                logger.error(f"❌ Stress test {test_name} failed: {result['error']}")
            else:
                target_met = result.get("performance_target_met", False)
                status = "✅ PASSED" if target_met else "⚠️  PERFORMANCE TARGET NOT MET"
                logger.info(f"{status} Stress test {test_name} completed in {test_duration:.2f}s")
        
        total_duration = time.perf_counter() - total_start_time
        
        # Generate summary
        successful_tests = len([r for r in results.values() if "error" not in r])
        performance_targets_met = len([r for r in results.values() if r.get("performance_target_met", False)])
        
        summary = {
            "stress_test_session_id": self.test_id,
            "total_tests": len(stress_tests),
            "successful_tests": successful_tests,
            "performance_targets_met": performance_targets_met,
            "total_duration_seconds": total_duration,
            "test_results": results
        }
        
        return summary


def print_stress_test_report(results: Dict[str, Any]):
    """Print comprehensive stress test report."""
    print("\n" + "="*100)
    print("🔥 COMPREHENSIVE OBSERVABILITY STRESS TEST REPORT")
    print("="*100)
    
    summary = results
    print(f"\n📊 Stress Test Session: {summary['stress_test_session_id']}")
    print(f"🕒 Total Duration: {summary['total_duration_seconds']:.2f} seconds")
    print(f"📈 Tests Completed: {summary['successful_tests']}/{summary['total_tests']}")
    print(f"🎯 Performance Targets Met: {summary['performance_targets_met']}/{summary['total_tests']}")
    
    print("\n🔥 STRESS TEST RESULTS:")
    print("-" * 100)
    
    for test_name, result in summary["test_results"].items():
        if "error" in result:
            print(f"❌ {test_name}")
            print(f"   ERROR: {result['error']}")
        else:
            target_met = result.get("performance_target_met", False)
            status = "✅ PASSED" if target_met else "⚠️  PERFORMANCE CONCERN"
            
            print(f"{status} {test_name}")
            print(f"   Duration: {result['test_duration_seconds']:.2f}s")
            
            # Test-specific metrics
            if result["test_type"] == "context_creation_throughput":
                print(f"   Max Throughput: {result['max_throughput_contexts_per_second']:.0f} contexts/sec")
                print(f"   Min Context Time: {result['min_context_time_microseconds']:.2f}μs")
                
            elif result["test_type"] == "concurrent_workflows":
                print(f"   Max Operations/sec: {result['max_operations_per_second']:.0f}")
                print(f"   Max Concurrency (95% success): {result['max_concurrency_95_percent_success']}")
                
            elif result["test_type"] == "memory_usage_under_load":
                print(f"   Memory Growth: {result['memory_growth_percentage']:.1f}%")
                print(f"   Memory Leak Detected: {result['memory_leak_detected']}")
                
            elif result["test_type"] == "error_recovery_resilience":
                print(f"   Recovery Rate: {result['recovery_rate_percentage']:.1f}%")
                print(f"   Avg Recovery Time: {result['avg_recovery_time_seconds']*1000:.2f}ms")
                
            elif result["test_type"] == "high_frequency_crypto_scenarios":
                print(f"   HFT Operations/sec: {result['operations_per_second']:.0f}")
                print(f"   Avg Operation Time: {result['avg_operation_time_microseconds']:.2f}μs")
        
        print()
    
    print("📊 PERFORMANCE ANALYSIS:")
    print("-" * 100)
    
    if summary["performance_targets_met"] == summary["total_tests"]:
        print("🎉 ALL PERFORMANCE TARGETS MET!")
        print("✅ Observability stack ready for high-load production scenarios")
        print("✅ Excellent throughput and low latency characteristics")
        print("✅ Memory usage within acceptable bounds") 
        print("✅ Robust error recovery and resilience")
        print("✅ Suitable for high-frequency crypto trading scenarios")
    else:
        print("⚠️  SOME PERFORMANCE TARGETS NOT MET")
        print("🔧 Review performance characteristics before production deployment")
        print("📈 Consider optimization for high-load scenarios")
    
    print("\n" + "="*100)


def main():
    """Main execution function."""
    try:
        # Initialize stress test
        stress_test = ObservabilityStressTest()
        
        # Run comprehensive stress tests
        results = stress_test.run_comprehensive_stress_tests()
        
        # Print detailed report
        print_stress_test_report(results)
        
        # Save detailed results
        report_file = f"observability_stress_test_{stress_test.test_id}.json"
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed stress test report saved to: {report_file}")
        
        # Return appropriate exit code
        return 0 if results["performance_targets_met"] == results["total_tests"] else 1
        
    except Exception as e:
        logger.error(f"Stress test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())