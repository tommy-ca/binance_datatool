"""
End-to-end integration tests for complete workflow validation.
Implements integration test scenarios from validation criteria specifications.
"""

import pytest
import asyncio
import time
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, List

from crypto_lakehouse.workflows.s3_direct_sync import S3DirectSyncManager
from crypto_lakehouse.workflows.archive_collection import ArchiveCollectionOrchestrator
from crypto_lakehouse.workflows.data_processing import DataProcessingPipeline
from crypto_lakehouse.observability.otel_integration import OpenTelemetryIntegration
from crypto_lakehouse.workflows.orchestration import WorkflowOrchestrator


class TestS3DirectSyncIntegrationWorkflows:
    """Integration validation for S3 Direct Sync workflows - INT001, INT002, INT003."""
    
    @pytest.fixture
    def s3_sync_manager(self, test_settings):
        """Create S3 Direct Sync manager."""
        return S3DirectSyncManager(test_settings)
    
    @pytest.fixture
    def workflow_orchestrator(self, test_settings):
        """Create workflow orchestrator."""
        return WorkflowOrchestrator(test_settings)
    
    @pytest.mark.integration
    @pytest.mark.critical
    async def test_end_to_end_direct_sync_workflow(self, s3_sync_manager, workflow_orchestrator):
        """
        Test INT001: End-to-End Direct Sync Workflow
        Given: Complete workflow from API request to transfer completion
        When: Execute full workflow with S3 Direct Sync
        Then: Workflow completes with performance improvements and metrics
        """
        # Given - Test data from validation criteria
        source_files = 50
        total_size_mb = 250
        expected_improvement = 60  # >60% requirement
        max_execution_time = 2  # <2 seconds requirement
        
        # Submit transfer request via API
        workflow_start = time.time()
        
        transfer_request = {
            "source_bucket": "test-source-bucket",
            "destination_bucket": "test-dest-bucket", 
            "file_pattern": "*.csv",
            "expected_files": source_files,
            "total_size_mb": total_size_mb,
            "sync_strategy": "auto"  # Let system choose optimal strategy
        }
        
        # When - Execute end-to-end workflow
        workflow_result = await workflow_orchestrator.execute_transfer_workflow(
            transfer_request
        )
        
        workflow_end = time.time()
        total_execution_time = workflow_end - workflow_start
        
        # Then - Validate success criteria from INT001
        
        # 1. Request accepted and operation ID returned
        assert workflow_result["request_accepted"] is True
        assert workflow_result["operation_id"] is not None
        
        # 2. Mode selection determines direct sync is optimal
        assert workflow_result["strategy_selected"] == "s5cmd_direct"
        assert workflow_result["strategy_reason"] == "optimal_performance"
        
        # 3. s5cmd direct sync executed successfully
        assert workflow_result["s5cmd_executed"] is True
        assert workflow_result["transfer_status"] == "completed"
        
        # 4. Performance metrics collected and calculated
        metrics = workflow_result["performance_metrics"]
        assert metrics["files_transferred"] == source_files
        assert metrics["performance_improvement_pct"] > expected_improvement
        assert metrics["operation_count"] == source_files  # Direct sync efficiency
        
        # 5. Complete response with performance data
        assert workflow_result["response_complete"] is True
        assert "performance_data" in workflow_result
        
        # Validate success criteria requirements
        assert total_execution_time < max_execution_time, \
            f"Execution time {total_execution_time:.1f}s exceeds {max_execution_time}s limit"
        
        assert metrics["performance_improvement_pct"] > expected_improvement, \
            f"Performance improvement {metrics['performance_improvement_pct']:.1f}% below target {expected_improvement}%"
        
        assert metrics["all_metrics_collected"] is True
        assert workflow_result["api_response_valid"] is True
    
    @pytest.mark.integration
    async def test_fallback_mechanism_integration(self, s3_sync_manager):
        """
        Test INT002: Fallback Mechanism Integration
        Given: s5cmd failure scenario during execution
        When: Execute workflow with simulated s5cmd failure
        Then: Seamless fallback to traditional mode with complete transfer
        """
        # Given - Transfer request with direct sync preferred
        transfer_request = {
            "source_bucket": "test-source-bucket",
            "destination_bucket": "test-dest-bucket",
            "preferred_strategy": "s5cmd_direct",
            "fallback_enabled": True,
            "fallback_timeout": 30
        }
        
        # Simulate s5cmd failure during execution
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("SIMULATE_S5CMD_FAILURE", "true")
            
            fallback_start = time.time()
            
            # When - Execute transfer with simulated failure
            result = await s3_sync_manager.execute_transfer_with_fallback(
                transfer_request
            )
            
            fallback_end = time.time()
            fallback_time = fallback_end - fallback_start
            
            # Then - Validate fallback success criteria from INT002
            
            # 1. Failure detected within timeout
            assert result["s5cmd_failure_detected"] is True
            assert result["failure_detection_time"] < 30  # Within 30 seconds
            
            # 2. Automatic fallback initiated
            assert result["fallback_initiated"] is True
            assert result["fallback_automatic"] is True
            assert result["user_intervention_required"] is False
            
            # 3. Traditional transfer completed successfully
            assert result["fallback_strategy"] == "traditional"
            assert result["transfer_status"] == "completed"
            assert result["data_integrity_verified"] is True
            
            # 4. Fallback metrics recorded accurately
            assert result["fallback_metrics_recorded"] is True
            fallback_metrics = result["fallback_metrics"]
            assert fallback_metrics["fallback_time"] < 30
            assert fallback_metrics["data_loss"] == 0
            assert fallback_metrics["transfer_completion"] == 100
            assert fallback_metrics["alerting_triggered"] is True
    
    @pytest.mark.integration
    async def test_batch_transfer_mixed_strategies(self, workflow_orchestrator):
        """
        Test INT003: Batch Transfer with Mixed Strategies
        Given: Large batch requiring mixed transfer strategies
        When: Execute batch with strategy optimization
        Then: Optimal strategy selection with parallel execution and aggregated metrics
        """
        # Given - Large batch transfer from validation criteria
        batch_size = 200
        expected_strategy_mix = {"direct_sync": 70, "traditional": 30}  # 70%/30% split
        expected_improvement = 40  # >40% overall improvement
        
        # Create mixed batch with various file characteristics
        batch_files = []
        for i in range(batch_size):
            file_size = 5 if i % 3 == 0 else 1  # Mixed file sizes
            priority = "high" if i < 50 else "normal"
            
            batch_files.append({
                "file_id": f"file_{i:03d}.csv",
                "size_mb": file_size,
                "priority": priority,
                "source": f"s3://source/batch/file_{i:03d}.csv",
                "destination": f"s3://dest/batch/file_{i:03d}.csv"
            })
        
        # When - Execute batch transfer with optimization
        batch_result = await workflow_orchestrator.execute_batch_transfer(
            files=batch_files,
            optimization_enabled=True,
            parallel_execution=True
        )
        
        # Then - Validate success criteria from INT003
        
        # 1. Optimal strategy selection for each batch
        strategy_distribution = batch_result["strategy_distribution"]
        direct_sync_pct = strategy_distribution["direct_sync_percentage"]
        traditional_pct = strategy_distribution["traditional_percentage"]
        
        # Allow 10% tolerance for strategy distribution
        assert abs(direct_sync_pct - expected_strategy_mix["direct_sync"]) <= 10, \
            f"Direct sync {direct_sync_pct}% not within tolerance of {expected_strategy_mix['direct_sync']}%"
        
        assert abs(traditional_pct - expected_strategy_mix["traditional"]) <= 10, \
            f"Traditional {traditional_pct}% not within tolerance of {expected_strategy_mix['traditional']}%"
        
        # 2. Parallel execution without conflicts
        assert batch_result["parallel_execution_enabled"] is True
        assert batch_result["execution_conflicts"] == 0
        assert batch_result["concurrent_batches"] > 1
        
        # 3. Accurate aggregated performance metrics
        aggregated_metrics = batch_result["aggregated_metrics"]
        assert aggregated_metrics["total_files_processed"] == batch_size
        assert aggregated_metrics["mixed_strategy_metrics_accurate"] is True
        
        # 4. Overall performance improvement >40%
        overall_improvement = aggregated_metrics["overall_performance_improvement"]
        assert overall_improvement > expected_improvement, \
            f"Overall improvement {overall_improvement:.1f}% below target {expected_improvement}%"


class TestArchiveCollectionIntegration:
    """Integration tests for Enhanced Archive Collection workflows."""
    
    @pytest.fixture
    def archive_orchestrator(self, test_settings):
        """Create archive collection orchestrator."""
        return ArchiveCollectionOrchestrator(test_settings)
    
    @pytest.mark.integration
    async def test_automated_discovery_and_collection_workflow(self, archive_orchestrator):
        """
        Test complete archive discovery and collection workflow.
        Validates automation targets: 70% reduction in manual coordination.
        """
        # Given - Multiple data sources for discovery
        data_sources = [
            {"exchange": "binance", "type": "spot", "priority": "high"},
            {"exchange": "coinbase", "type": "pro", "priority": "normal"},
            {"exchange": "ftx", "type": "historical", "priority": "low"}
        ]
        
        discovery_start = time.time()
        
        # When - Execute automated discovery and collection
        workflow_result = await archive_orchestrator.execute_discovery_workflow(
            sources=data_sources,
            automation_level="full"
        )
        
        discovery_end = time.time()
        total_discovery_time = discovery_end - discovery_start
        
        # Then - Validate automation and efficiency targets
        
        # Discovery automation >90%
        automation_rate = workflow_result["automation_metrics"]["automation_rate"]
        assert automation_rate > 90, f"Automation rate {automation_rate}% below target 90%"
        
        # Discovery success rate >98%
        discovery_success = workflow_result["discovery_metrics"]["success_rate"]
        assert discovery_success > 98, f"Discovery success {discovery_success}% below target 98%"
        
        # Collection completeness >95%
        collection_completeness = workflow_result["collection_metrics"]["completeness"]
        assert collection_completeness > 95, f"Collection completeness {collection_completeness}% below target 95%"
        
        # Manual coordination reduction validation
        manual_steps = workflow_result["workflow_metrics"]["manual_steps_required"]
        total_steps = workflow_result["workflow_metrics"]["total_steps"]
        manual_percentage = (manual_steps / total_steps) * 100
        
        # Should be <30% manual steps (70% reduction target achieved)
        assert manual_percentage < 30, f"Manual steps {manual_percentage:.1f}% exceed 30% target"
    
    @pytest.mark.integration
    async def test_real_time_collection_monitoring(self, archive_orchestrator):
        """Test real-time monitoring and alerting during collection operations."""
        # Given - Collection operations across multiple sources
        collection_sources = [
            {"source": "binance_spot", "priority": "high", "expected_files": 100},
            {"source": "coinbase_pro", "priority": "normal", "expected_files": 50}
        ]
        
        # When - Execute collection with monitoring
        monitoring_result = await archive_orchestrator.execute_monitored_collection(
            sources=collection_sources,
            monitoring_interval=5  # 5 second updates
        )
        
        # Then - Validate monitoring requirements
        
        # Dashboard updates within 30 seconds
        assert monitoring_result["dashboard_update_latency"] < 30
        
        # Alert response within 5 minutes for failures
        if monitoring_result["failures_detected"]:
            assert monitoring_result["alert_response_time"] < 300  # 5 minutes
        
        # Metrics available for >95% of operations
        metrics_coverage = monitoring_result["metrics_coverage_percentage"]
        assert metrics_coverage > 95, f"Metrics coverage {metrics_coverage}% below target 95%"
        
        # Historical data retention for 12 months validated
        assert monitoring_result["historical_retention_months"] >= 12


class TestObservabilityIntegration:
    """Integration tests for Observability platform integration."""
    
    @pytest.fixture
    def otel_integration(self, test_settings):
        """Create OpenTelemetry integration."""
        return OpenTelemetryIntegration(test_settings)
    
    @pytest.mark.integration
    async def test_unified_telemetry_collection_integration(self, otel_integration):
        """
        Test unified telemetry collection across all system components.
        Validates >95% system coverage and trace correlation.
        """
        # Given - System components requiring telemetry
        system_components = [
            "s3_direct_sync",
            "archive_collection", 
            "data_processing",
            "workflow_orchestration"
        ]
        
        # When - Initialize telemetry collection
        telemetry_result = await otel_integration.initialize_unified_telemetry(
            components=system_components
        )
        
        # Then - Validate telemetry coverage and integration
        
        # >95% system coverage
        coverage = telemetry_result["system_coverage_percentage"]
        assert coverage > 95, f"System coverage {coverage}% below target 95%"
        
        # All components emit OTLP format
        for component in system_components:
            component_telemetry = telemetry_result["component_telemetry"][component]
            assert component_telemetry["otlp_format"] is True
            assert component_telemetry["metrics_enabled"] is True
            assert component_telemetry["traces_enabled"] is True
            assert component_telemetry["logs_enabled"] is True
        
        # Trace correlation >90% accuracy
        correlation_accuracy = telemetry_result["correlation_metrics"]["accuracy"]
        assert correlation_accuracy > 90, f"Correlation accuracy {correlation_accuracy}% below target 90%"
    
    @pytest.mark.integration
    async def test_intelligent_alerting_correlation(self, otel_integration):
        """Test intelligent alert correlation and noise reduction."""
        # Given - Multiple related alert scenarios
        alert_scenarios = [
            {"type": "performance_degradation", "component": "s3_sync", "severity": "warning"},
            {"type": "error_rate_spike", "component": "s3_sync", "severity": "critical"},
            {"type": "resource_exhaustion", "component": "kubernetes", "severity": "warning"}
        ]
        
        # When - Generate correlated alerts
        alert_result = await otel_integration.process_correlated_alerts(
            scenarios=alert_scenarios
        )
        
        # Then - Validate alert intelligence
        
        # Related alerts grouped into single incident
        assert alert_result["incidents_created"] < len(alert_scenarios)
        assert alert_result["alert_correlation_applied"] is True
        
        # Critical alerts reach on-call within 2 minutes
        critical_alerts = [a for a in alert_scenarios if a["severity"] == "critical"]
        if critical_alerts:
            assert alert_result["critical_alert_response_time"] < 120  # 2 minutes
        
        # Alert context enrichment provided
        for incident in alert_result["incidents"]:
            assert incident["context_enriched"] is True
            assert "system_context" in incident
            assert "remediation_guidance" in incident


class TestWorkflowOrchestrationIntegration:
    """Integration tests for Workflow Orchestration platform."""
    
    @pytest.fixture
    def workflow_platform(self, test_settings):
        """Create workflow orchestration platform."""
        return WorkflowOrchestrator(test_settings)
    
    @pytest.mark.integration
    async def test_end_to_end_data_pipeline_orchestration(self, workflow_platform):
        """
        Test complete data pipeline orchestration with error recovery.
        Validates 75% reduction in pipeline failures and 60% development efficiency.
        """
        # Given - Complex data pipeline definition
        pipeline_definition = {
            "name": "crypto_data_processing_pipeline",
            "stages": [
                {"name": "data_collection", "type": "archive_collection", "parallel": True},
                {"name": "data_validation", "type": "quality_check", "depends_on": ["data_collection"]},
                {"name": "data_transformation", "type": "processing", "depends_on": ["data_validation"]},
                {"name": "data_storage", "type": "s3_sync", "depends_on": ["data_transformation"]}
            ],
            "error_recovery": True,
            "retry_policy": {"max_retries": 3, "backoff": "exponential"}
        }
        
        pipeline_start = time.time()
        
        # When - Execute complete pipeline
        pipeline_result = await workflow_platform.execute_pipeline(
            pipeline_definition
        )
        
        pipeline_end = time.time()
        execution_time = pipeline_end - pipeline_start
        
        # Then - Validate orchestration success criteria
        
        # Pipeline success rate >99%
        assert pipeline_result["execution_status"] == "completed"
        assert pipeline_result["success_rate"] > 99
        
        # Error recovery functionality
        if pipeline_result["errors_encountered"] > 0:
            assert pipeline_result["auto_recovery_successful"] is True
            assert pipeline_result["recovery_time"] < 900  # <15 minutes MTTR
        
        # Resource utilization >80%
        resource_utilization = pipeline_result["resource_metrics"]["average_utilization"]
        assert resource_utilization > 80, f"Resource utilization {resource_utilization}% below target 80%"
        
        # Development efficiency validation (pipeline-as-code)
        assert pipeline_result["version_controlled"] is True
        assert pipeline_result["automated_deployment"] is True
        assert pipeline_result["rollback_capability"] is True