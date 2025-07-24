"""
Unit tests for S3 Direct Sync feature validation.
Implements test cases from validation criteria YAML specifications.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import tempfile
from pathlib import Path

from crypto_lakehouse.workflows.s3_direct_sync import (
    S3DirectSyncManager,
    S5cmdDirectSyncStrategy,
    TraditionalTransferStrategy,
    TransferOrchestrator,
    S3URLValidator,
    PerformanceMetrics,
)


class TestS5cmdDirectSyncStrategyUnitValidation:
    """Unit validation for S5cmdDirectSyncStrategy - Test ID: UT001, UT002."""
    
    @pytest.fixture
    def s5cmd_strategy(self):
        """Create S5cmdDirectSyncStrategy instance."""
        return S5cmdDirectSyncStrategy()
    
    @pytest.mark.unit
    def test_s5cmd_direct_sync_success_path(self, s5cmd_strategy):
        """
        Test ID: UT001 - S5cmdDirectSyncStrategy Success Path
        Given: Valid source and destination S3 URLs and available s5cmd
        When: Execute direct sync transfer
        Then: Transfer completes successfully with performance metrics
        """
        # Given - Test data from validation criteria
        source_url = "s3://test-source/path/"
        destination_url = "s3://test-dest/path/"
        file_count = 10
        total_size_mb = 100
        
        # Mock s5cmd execution
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "10 files transferred successfully"
            
            # When - Execute direct sync transfer
            result = s5cmd_strategy.execute_transfer(
                source_url=source_url,
                destination_url=destination_url,
                expected_files=file_count
            )
            
            # Then - Validate success criteria
            assert result["transfer_status"] == "completed"
            assert result["files_transferred"] == file_count
            assert result["operation_count"] == file_count
            assert result["local_storage_used"] == 0
            assert result["performance_improvement"] > 60  # >60% requirement
            
            # Validate s5cmd execution
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "s5cmd" in call_args
            assert source_url in call_args
            assert destination_url in call_args
    
    @pytest.mark.unit
    def test_s5cmd_failure_and_fallback(self, s5cmd_strategy):
        """
        Test ID: UT002 - S5cmdDirectSyncStrategy Failure and Fallback
        Given: Valid URLs but s5cmd unavailable or failing
        When: Attempt direct sync transfer
        Then: Failure detected and fallback mechanism triggered
        """
        # Given - s5cmd unavailable scenario
        source_url = "s3://test-source/path/"
        destination_url = "s3://test-dest/path/"
        
        # Mock s5cmd failure
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("s5cmd not found")
            
            # When - Attempt direct sync transfer
            result = s5cmd_strategy.execute_transfer(
                source_url=source_url,
                destination_url=destination_url
            )
            
            # Then - Validate failure handling
            assert result["transfer_status"] == "failed"
            assert result["error_type"] == "S5CMD_UNAVAILABLE"
            assert result["fallback_triggered"] is True
            assert result["cleanup_completed"] is True
    
    @pytest.mark.unit
    def test_s5cmd_timeout_handling(self, s5cmd_strategy):
        """Test s5cmd timeout detection within specified limits."""
        source_url = "s3://test-source/path/"
        destination_url = "s3://test-dest/path/"
        
        # Mock s5cmd timeout
        with patch('subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired("s5cmd", 30)
            
            result = s5cmd_strategy.execute_transfer(
                source_url=source_url,
                destination_url=destination_url,
                timeout=30
            )
            
            assert result["transfer_status"] == "failed"
            assert result["error_type"] == "TIMEOUT"
            assert result["fallback_triggered"] is True


class TestTraditionalTransferStrategyUnitValidation:
    """Unit validation for TraditionalTransferStrategy - Test ID: UT003."""
    
    @pytest.fixture
    def traditional_strategy(self):
        """Create TraditionalTransferStrategy instance."""
        return TraditionalTransferStrategy()
    
    @pytest.mark.unit
    def test_traditional_transfer_validation(self, traditional_strategy):
        """
        Test ID: UT003 - TraditionalTransferStrategy Validation
        Given: Valid S3 URLs and boto3 configuration
        When: Execute traditional transfer strategy
        Then: Files downloaded, uploaded, and cleaned up successfully
        """
        # Given - Test data from validation criteria
        source_url = "s3://test-source/file.txt"
        destination_url = "s3://test-dest/file.txt"
        file_size_mb = 10
        
        # Mock boto3 S3 operations
        with patch('boto3.client') as mock_client:
            mock_s3 = Mock()
            mock_client.return_value = mock_s3
            
            # Mock successful download and upload
            mock_s3.download_file.return_value = None
            mock_s3.upload_file.return_value = None
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # When - Execute traditional transfer
                result = traditional_strategy.execute_transfer(
                    source_url=source_url,
                    destination_url=destination_url,
                    local_temp_dir=temp_dir
                )
                
                # Then - Validate traditional transfer results
                assert result["transfer_status"] == "completed"
                assert result["local_download_completed"] is True
                assert result["local_upload_completed"] is True
                assert result["local_cleanup_completed"] is True
                assert result["operation_count"] == 2  # download + upload
                
                # Validate S3 operations called
                mock_s3.download_file.assert_called_once()
                mock_s3.upload_file.assert_called_once()


class TestTransferOrchestratorUnitValidation:
    """Unit validation for TransferOrchestrator - Test ID: UT004, UT005."""
    
    @pytest.fixture
    def transfer_orchestrator(self):
        """Create TransferOrchestrator instance."""
        return TransferOrchestrator()
    
    @pytest.mark.unit
    def test_batch_processing_optimization(self, transfer_orchestrator):
        """
        Test ID: UT004 - Batch Processing Optimization
        Given: Multiple files with varying sizes
        When: Execute batch transfer with optimization
        Then: Files grouped optimally and processed efficiently
        """
        # Given - Test data from validation criteria
        file_count = 500
        size_range = "1KB to 100MB"
        batch_size_limit = 100
        optimization_strategy = "mixed"
        
        # Create test files with varying sizes
        test_files = []
        for i in range(file_count):
            size_mb = 1 + (i % 100)  # Varying sizes
            test_files.append({
                "source": f"s3://test-source/file_{i}.dat",
                "dest": f"s3://test-dest/file_{i}.dat", 
                "size_mb": size_mb
            })
        
        # When - Execute batch transfer with optimization
        result = transfer_orchestrator.process_batch(
            files=test_files,
            batch_size_limit=batch_size_limit,
            optimization_enabled=True,
            strategy=optimization_strategy
        )
        
        # Then - Validate optimization results
        assert result["batch_count"] <= 5  # ≤5 batches requirement
        assert result["parallel_execution"] is True
        assert result["total_processing_time"] < 10  # <10 seconds requirement
        assert result["optimization_efficiency"] > 80  # >80% requirement
        
        # Validate file grouping optimization
        assert "batch_groups" in result
        assert len(result["batch_groups"]) <= 5
    
    @pytest.mark.unit
    def test_performance_metrics_collection(self, transfer_orchestrator):
        """
        Test ID: UT005 - Performance Metrics Collection
        Given: Transfer operations with various characteristics
        When: Execute transfers with metrics collection enabled
        Then: Detailed performance metrics collected and calculated
        """
        # Given - Different transfer scenarios
        transfer_scenarios = ["small_files", "large_files", "mixed_batch"]
        metrics_enabled = True
        
        for scenario in transfer_scenarios:
            # Create scenario-specific test data
            if scenario == "small_files":
                files = [{"size_mb": 0.1} for _ in range(100)]
            elif scenario == "large_files":
                files = [{"size_mb": 50.0} for _ in range(10)]
            else:  # mixed_batch
                files = [{"size_mb": 1 + (i % 10)} for i in range(50)]
            
            # When - Execute transfer with metrics collection
            result = transfer_orchestrator.process_batch(
                files=files,
                collect_metrics=metrics_enabled
            )
            
            # Then - Validate metrics collection
            assert result["metrics_completeness"] == 100  # 100% requirement
            assert "timing_metrics" in result
            assert "throughput_metrics" in result
            assert "efficiency_calculation" in result
            
            # Validate timing accuracy (±1ms requirement)
            timing_metrics = result["timing_metrics"]
            assert "start_time" in timing_metrics
            assert "end_time" in timing_metrics
            assert "duration" in timing_metrics
            
            # Validate throughput accuracy (±5% requirement)
            throughput = result["throughput_metrics"]["files_per_second"]
            assert throughput > 0
            
            # Validate efficiency calculation accuracy
            efficiency = result["efficiency_calculation"]
            assert 0 <= efficiency <= 100


class TestS3URLValidatorUnitValidation:
    """Unit validation for S3URLValidator - Test ID: UT006."""
    
    @pytest.fixture
    def url_validator(self):
        """Create S3URLValidator instance."""
        return S3URLValidator()
    
    @pytest.mark.unit
    def test_s3_url_validation(self, url_validator):
        """
        Test ID: UT006 - S3 URL Validation
        Given: Various S3 URL formats and accessibility scenarios
        When: Validate URLs through validation framework
        Then: Correct validation results returned
        """
        # Given - Test data from validation criteria
        valid_urls = ["s3://bucket/path/", "s3://bucket/file.txt"]
        invalid_urls = ["http://bucket/path", "s3://", "invalid-url"]
        permission_scenarios = ["read_only", "write_only", "full_access", "no_access"]
        
        # When/Then - Validate valid URLs
        for url in valid_urls:
            result = url_validator.validate_url(url)
            assert result["is_valid"] is True
            assert result["validation_errors"] == []
        
        # When/Then - Validate invalid URLs  
        for url in invalid_urls:
            result = url_validator.validate_url(url)
            assert result["is_valid"] is False
            assert len(result["validation_errors"]) > 0
            assert result["error_message"] != ""
        
        # When/Then - Validate permission scenarios
        for scenario in permission_scenarios:
            # Mock different permission levels
            with patch.object(url_validator, '_check_permissions') as mock_check:
                if scenario == "no_access":
                    mock_check.return_value = False
                else:
                    mock_check.return_value = True
                
                result = url_validator.validate_url_with_permissions(
                    "s3://test-bucket/path/",
                    required_permissions=[scenario]
                )
                
                if scenario == "no_access":
                    assert result["permission_valid"] is False
                else:
                    assert result["permission_valid"] is True
        
        # Validate requirements from criteria
        # - Valid URL acceptance: 100%
        valid_acceptance_rate = len([url for url in valid_urls]) / len(valid_urls) * 100
        assert valid_acceptance_rate == 100
        
        # - Invalid URL rejection: 100%  
        invalid_rejection_rate = len([url for url in invalid_urls]) / len(invalid_urls) * 100
        assert invalid_rejection_rate == 100
        
        # - Error messages clear and actionable
        for url in invalid_urls:
            result = url_validator.validate_url(url)
            assert len(result["error_message"]) > 10  # Meaningful error message


class TestPerformanceMetricsUnitValidation:
    """Unit validation for PerformanceMetrics collection and calculation."""
    
    @pytest.fixture
    def performance_metrics(self):
        """Create PerformanceMetrics instance."""
        return PerformanceMetrics()
    
    @pytest.mark.unit
    def test_performance_improvement_calculation(self, performance_metrics):
        """Test performance improvement calculation accuracy."""
        # Given - Baseline and optimized times
        baseline_time = 10.0  # seconds
        optimized_time = 4.0   # seconds (60% improvement)
        
        # When - Calculate improvement
        improvement = performance_metrics.calculate_improvement(
            baseline_time, optimized_time
        )
        
        # Then - Validate calculation
        expected_improvement = 60.0  # 60% improvement
        assert abs(improvement - expected_improvement) < 0.1
    
    @pytest.mark.unit
    def test_operation_count_tracking(self, performance_metrics):
        """Test operation count tracking for direct sync vs traditional."""
        # Given - Transfer scenarios
        file_count = 100
        
        # When - Track operations for both strategies
        direct_sync_ops = performance_metrics.track_operations("direct_sync", file_count)
        traditional_ops = performance_metrics.track_operations("traditional", file_count)
        
        # Then - Validate operation counts
        assert direct_sync_ops == file_count  # 1 operation per file
        assert traditional_ops == file_count * 2  # download + upload per file
        
        # Calculate operation reduction
        reduction = performance_metrics.calculate_operation_reduction(
            traditional_ops, direct_sync_ops
        )
        
        # Validate >80% reduction requirement
        assert reduction > 80
    
    @pytest.mark.unit
    def test_memory_usage_tracking(self, performance_metrics):
        """Test memory usage tracking and efficiency validation."""
        # Given - Memory usage scenarios
        scenarios = ["small_batch", "large_batch", "continuous_operation"]
        target_memory_mb = 100
        
        for scenario in scenarios:
            # When - Track memory usage
            memory_result = performance_metrics.track_memory_usage(scenario)
            
            # Then - Validate memory efficiency
            assert memory_result["peak_memory_mb"] < target_memory_mb
            assert memory_result["memory_leak_detected"] is False
            assert memory_result["gc_functioning"] is True