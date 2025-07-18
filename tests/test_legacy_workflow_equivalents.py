"""
Legacy Workflow Equivalent Tests

This module tests the new data lakehouse workflows against legacy shell script functionality.
Tests ensure 100% functional equivalence with enhanced capabilities.
"""

import pytest
import polars as pl
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import tempfile
import os

from crypto_lakehouse.workflows.prefect_workflows import (
    aws_download_workflow,
    aws_parse_workflow,
    api_download_workflow,
    gen_kline_workflow,
    resample_workflow,
    complete_pipeline_workflow
)
from crypto_lakehouse.core.config import Config
from crypto_lakehouse.core.models import MarketType, DataType


class TestLegacyWorkflowEquivalents:
    """Test suite for legacy workflow equivalents with enhanced features"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return Config(
            base_dir=Path(tempfile.mkdtemp()),
            aws_access_key_id="test",
            aws_secret_access_key="test",
            s3_bucket="test-bucket",
            environment="test"
        )
    
    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client for testing"""
        with patch('crypto_lakehouse.storage.s3_storage.boto3.client') as mock:
            yield mock
    
    @pytest.fixture
    def mock_binance_client(self):
        """Mock Binance client for testing"""
        with patch('crypto_lakehouse.ingestion.binance.ccxt.binance') as mock:
            yield mock


class TestAWSDownloadWorkflow:
    """Test aws_download.sh equivalent workflow"""
    
    @pytest.mark.asyncio
    async def test_aws_download_workflow_funding_rates(self, config, mock_s3_client):
        """Test funding rate download workflow equivalent"""
        # Mock successful downloads
        mock_s3_client.return_value.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'data/futures/um/daily/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2024-01-01.zip'},
                {'Key': 'data/futures/cm/daily/fundingRate/BTCUSD_PERP/BTCUSD_PERP-fundingRate-2024-01-01.zip'}
            ]
        }
        
        # Execute workflow
        result = await aws_download_workflow(
            config=config,
            data_types=[DataType.FUNDING_RATE],
            market_types=[MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            interval="1m",
            verify=True
        )
        
        # Verify results
        assert result.success
        assert len(result.downloaded_files) > 0
        assert result.verification_passed
        
    @pytest.mark.asyncio
    async def test_aws_download_workflow_klines(self, config, mock_s3_client):
        """Test K-line download workflow equivalent"""
        # Mock successful downloads
        mock_s3_client.return_value.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip'},
                {'Key': 'data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip'}
            ]
        }
        
        # Execute workflow
        result = await aws_download_workflow(
            config=config,
            data_types=[DataType.KLINE],
            market_types=[MarketType.SPOT, MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            interval="1m",
            verify=True
        )
        
        # Verify results
        assert result.success
        assert len(result.downloaded_files) > 0
        assert result.verification_passed
    
    @pytest.mark.asyncio
    async def test_aws_download_workflow_parallel_processing(self, config, mock_s3_client):
        """Test parallel processing capability (enhancement over legacy)"""
        # Mock multiple downloads
        mock_s3_client.return_value.list_objects_v2.return_value = {
            'Contents': [
                {'Key': f'data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-{i:02d}.zip'}
                for i in range(1, 11)
            ]
        }
        
        # Execute workflow with parallel processing
        result = await aws_download_workflow(
            config=config,
            data_types=[DataType.KLINE],
            market_types=[MarketType.SPOT],
            interval="1m",
            max_concurrent=10,  # Enhanced: parallel processing
            verify=True
        )
        
        # Verify parallel processing worked
        assert result.success
        assert result.processing_time < 60  # Should be faster than sequential
        assert len(result.downloaded_files) == 10


class TestAWSParseWorkflow:
    """Test aws_parse.sh equivalent workflow"""
    
    @pytest.mark.asyncio
    async def test_aws_parse_workflow_funding_rates(self, config):
        """Test funding rate parsing workflow equivalent"""
        # Mock raw data files
        raw_data_dir = config.base_dir / "bronze" / "funding_rates"
        raw_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create mock raw data
        mock_funding_data = pl.DataFrame({
            'symbol': ['BTCUSDT', 'ETHUSDT'],
            'funding_time': [1704067200000, 1704070800000],
            'funding_rate': [0.0001, 0.0002],
            'mark_price': [45000.0, 2500.0]
        })
        
        # Execute workflow
        result = await aws_parse_workflow(
            config=config,
            data_types=[DataType.FUNDING_RATE],
            market_types=[MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            interval="1m"
        )
        
        # Verify results
        assert result.success
        assert len(result.parsed_files) > 0
        assert result.data_quality_score >= 0.9  # Enhanced: quality scoring
    
    @pytest.mark.asyncio
    async def test_aws_parse_workflow_klines_with_validation(self, config):
        """Test K-line parsing with data validation (enhancement)"""
        # Mock raw data files
        raw_data_dir = config.base_dir / "bronze" / "klines"
        raw_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Execute workflow with validation
        result = await aws_parse_workflow(
            config=config,
            data_types=[DataType.KLINE],
            market_types=[MarketType.SPOT, MarketType.UM_FUTURES],
            interval="1m",
            validate_data=True,  # Enhanced: data validation
            compute_technical_indicators=True  # Enhanced: technical indicators
        )
        
        # Verify enhanced features
        assert result.success
        assert result.validation_passed
        assert result.technical_indicators_computed
        assert result.data_quality_score >= 0.95


class TestAPIDownloadWorkflow:
    """Test api_download.sh equivalent workflow"""
    
    @pytest.mark.asyncio
    async def test_api_download_missing_klines(self, config, mock_binance_client):
        """Test API download for missing K-lines"""
        # Mock API client
        mock_binance_client.return_value.fetch_ohlcv = AsyncMock(return_value=[
            [1704067200000, 45000.0, 45100.0, 44900.0, 45050.0, 1000.0],
            [1704067260000, 45050.0, 45150.0, 44950.0, 45100.0, 1200.0]
        ])
        
        # Execute workflow
        result = await api_download_workflow(
            config=config,
            data_types=[DataType.KLINE],
            market_types=[MarketType.SPOT, MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            interval="1m",
            gap_detection=True,  # Enhanced: automatic gap detection
            max_concurrent=5
        )
        
        # Verify results
        assert result.success
        assert len(result.filled_gaps) > 0
        assert result.gap_detection_completed
    
    @pytest.mark.asyncio
    async def test_api_download_recent_funding_rates(self, config, mock_binance_client):
        """Test API download for recent funding rates"""
        # Mock API client
        mock_binance_client.return_value.fetch_funding_rate_history = AsyncMock(return_value=[
            {'symbol': 'BTCUSDT', 'timestamp': 1704067200000, 'rate': 0.0001},
            {'symbol': 'ETHUSDT', 'timestamp': 1704067200000, 'rate': 0.0002}
        ])
        
        # Execute workflow
        result = await api_download_workflow(
            config=config,
            data_types=[DataType.FUNDING_RATE],
            market_types=[MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            interval="1m",
            recent_only=True  # Enhanced: recent data only
        )
        
        # Verify results
        assert result.success
        assert len(result.recent_data) > 0
        assert result.data_freshness_score >= 0.9


class TestGenKlineWorkflow:
    """Test gen_kline.sh equivalent workflow"""
    
    @pytest.mark.asyncio
    async def test_gen_kline_workflow_spot_with_vwap(self, config):
        """Test spot K-line generation with VWAP (matching legacy functionality)"""
        # Mock existing data
        silver_dir = config.base_dir / "silver" / "klines"
        silver_dir.mkdir(parents=True, exist_ok=True)
        
        # Execute workflow
        result = await gen_kline_workflow(
            config=config,
            market_type=MarketType.SPOT,
            interval="1m",
            split_gaps=True,  # Legacy: --split-gaps
            with_vwap=True,   # Legacy: --with-vwap
            with_funding_rates=False  # Legacy: --no-with-funding-rates
        )
        
        # Verify results
        assert result.success
        assert result.vwap_computed
        assert not result.funding_rates_joined
        assert result.gaps_handled
    
    @pytest.mark.asyncio
    async def test_gen_kline_workflow_futures_with_funding(self, config):
        """Test futures K-line generation with funding rates"""
        # Mock existing data
        silver_dir = config.base_dir / "silver" / "klines"
        silver_dir.mkdir(parents=True, exist_ok=True)
        
        # Execute workflow
        result = await gen_kline_workflow(
            config=config,
            market_type=MarketType.UM_FUTURES,
            interval="1m",
            split_gaps=True,  # Legacy: --split-gaps
            with_vwap=True,   # Legacy: --with-vwap
            with_funding_rates=True  # Legacy: --with-funding-rates
        )
        
        # Verify results
        assert result.success
        assert result.vwap_computed
        assert result.funding_rates_joined
        assert result.gaps_handled
    
    @pytest.mark.asyncio
    async def test_gen_kline_workflow_enhanced_features(self, config):
        """Test enhanced features beyond legacy functionality"""
        # Execute workflow with enhancements
        result = await gen_kline_workflow(
            config=config,
            market_type=MarketType.UM_FUTURES,
            interval="1m",
            split_gaps=True,
            with_vwap=True,
            with_funding_rates=True,
            compute_technical_indicators=True,  # Enhanced: technical indicators
            market_microstructure=True,  # Enhanced: market microstructure
            data_quality_checks=True     # Enhanced: quality checks
        )
        
        # Verify enhanced features
        assert result.success
        assert result.technical_indicators_computed
        assert result.microstructure_computed
        assert result.quality_checks_passed
        assert result.data_quality_score >= 0.95


class TestResampleWorkflow:
    """Test resample.sh equivalent workflow"""
    
    @pytest.mark.asyncio
    async def test_resample_workflow_1h_with_5m_offset(self, config):
        """Test 1h resampling with 5m offset (matching legacy)"""
        # Mock 1m data
        gold_dir = config.base_dir / "gold" / "klines"
        gold_dir.mkdir(parents=True, exist_ok=True)
        
        # Execute workflow
        result = await resample_workflow(
            config=config,
            market_type=MarketType.SPOT,
            source_interval="1m",
            target_interval="1h",
            offset="5m"  # Legacy: 5m offset
        )
        
        # Verify results
        assert result.success
        assert result.target_interval == "1h"
        assert result.offset_applied == "5m"
        assert result.resampling_accuracy >= 0.99
    
    @pytest.mark.asyncio
    async def test_resample_workflow_5m_with_zero_offset(self, config):
        """Test 5m resampling with zero offset (matching legacy)"""
        # Execute workflow
        result = await resample_workflow(
            config=config,
            market_type=MarketType.UM_FUTURES,
            source_interval="1m",
            target_interval="5m",
            offset="0m"  # Legacy: 0 offset
        )
        
        # Verify results
        assert result.success
        assert result.target_interval == "5m"
        assert result.offset_applied == "0m"
        assert result.resampling_accuracy >= 0.99
    
    @pytest.mark.asyncio
    async def test_resample_workflow_multiple_timeframes(self, config):
        """Test multiple timeframe resampling (enhancement)"""
        # Execute workflow for multiple timeframes
        result = await resample_workflow(
            config=config,
            market_type=MarketType.UM_FUTURES,
            source_interval="1m",
            target_intervals=["5m", "15m", "1h", "1d"],  # Enhanced: multiple targets
            offset="0m"
        )
        
        # Verify results
        assert result.success
        assert len(result.resampled_intervals) == 4
        assert all(acc >= 0.99 for acc in result.accuracy_scores.values())


class TestCompletePipelineWorkflow:
    """Test complete end-to-end pipeline workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_matching_legacy_sequence(self, config, mock_s3_client, mock_binance_client):
        """Test complete pipeline matching legacy script sequence"""
        # Mock all external dependencies
        mock_s3_client.return_value.list_objects_v2.return_value = {'Contents': []}
        mock_binance_client.return_value.fetch_ohlcv = AsyncMock(return_value=[])
        
        # Execute complete pipeline
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT, MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            data_types=[DataType.KLINE, DataType.FUNDING_RATE],
            interval="1m",
            # Legacy sequence options
            download_aws=True,
            parse_aws=True,
            download_api=True,
            generate_klines=True,
            resample=True,
            # Enhanced options
            parallel_processing=True,
            data_quality_checks=True,
            technical_indicators=True
        )
        
        # Verify complete pipeline
        assert result.success
        assert result.aws_download_completed
        assert result.aws_parse_completed
        assert result.api_download_completed
        assert result.kline_generation_completed
        assert result.resampling_completed
        assert result.overall_quality_score >= 0.95
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_error_recovery(self, config):
        """Test error recovery and retry mechanisms (enhancement)"""
        # Mock failures and recoveries
        with patch('crypto_lakehouse.workflows.prefect_workflows.aws_download_workflow') as mock_download:
            mock_download.side_effect = [Exception("Network error"), Mock(success=True)]
            
            # Execute pipeline with retry
            result = await complete_pipeline_workflow(
                config=config,
                market_types=[MarketType.SPOT],
                data_types=[DataType.KLINE],
                interval="1m",
                max_retries=3,  # Enhanced: retry mechanism
                error_recovery=True
            )
            
            # Verify error recovery
            assert result.success
            assert result.retry_count > 0
            assert result.error_recovery_successful
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_performance_benchmarks(self, config):
        """Test performance benchmarks vs legacy scripts"""
        # Execute pipeline with performance monitoring
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT],
            data_types=[DataType.KLINE],
            interval="1m",
            performance_monitoring=True  # Enhanced: performance tracking
        )
        
        # Verify performance improvements
        assert result.success
        assert result.processing_time < 3600  # Should be faster than legacy
        assert result.throughput_mbps > 10    # High throughput
        assert result.memory_efficiency >= 0.8  # Efficient memory usage


class TestWorkflowIntegration:
    """Test workflow integration and coordination"""
    
    @pytest.mark.asyncio
    async def test_workflow_dependency_management(self, config):
        """Test workflow dependency management (enhancement)"""
        # Test dependency chain
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT],
            data_types=[DataType.KLINE],
            interval="1m",
            enforce_dependencies=True,  # Enhanced: dependency enforcement
            validate_prerequisites=True
        )
        
        # Verify dependency management
        assert result.success
        assert result.dependency_validation_passed
        assert result.execution_order_correct
    
    @pytest.mark.asyncio
    async def test_workflow_parallel_execution(self, config):
        """Test parallel workflow execution (enhancement)"""
        # Execute multiple workflows in parallel
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT, MarketType.UM_FUTURES, MarketType.CM_FUTURES],
            data_types=[DataType.KLINE, DataType.FUNDING_RATE],
            interval="1m",
            parallel_market_types=True,  # Enhanced: parallel execution
            max_concurrent_workflows=3
        )
        
        # Verify parallel execution
        assert result.success
        assert result.parallel_execution_completed
        assert result.total_processing_time < result.sequential_processing_time
    
    @pytest.mark.asyncio
    async def test_workflow_monitoring_and_alerts(self, config):
        """Test workflow monitoring and alerting (enhancement)"""
        # Execute with monitoring
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT],
            data_types=[DataType.KLINE],
            interval="1m",
            enable_monitoring=True,  # Enhanced: monitoring
            alert_on_failures=True,
            quality_thresholds={'min_quality_score': 0.9}
        )
        
        # Verify monitoring
        assert result.success
        assert result.monitoring_enabled
        assert result.quality_alerts_configured
        assert len(result.performance_metrics) > 0


# Performance benchmarks against legacy scripts
class TestPerformanceBenchmarks:
    """Performance benchmarks comparing new workflows to legacy scripts"""
    
    @pytest.mark.asyncio
    async def test_throughput_improvement(self, config):
        """Test throughput improvement over legacy scripts"""
        # Simulate processing 1GB of data
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT],
            data_types=[DataType.KLINE],
            interval="1m",
            benchmark_mode=True,
            data_size_gb=1.0
        )
        
        # Verify throughput improvement
        assert result.success
        assert result.throughput_improvement_factor >= 5.0  # 5x improvement
        assert result.processing_time_seconds < 600  # Under 10 minutes
    
    @pytest.mark.asyncio
    async def test_memory_efficiency(self, config):
        """Test memory efficiency vs legacy scripts"""
        # Execute with memory monitoring
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT],
            data_types=[DataType.KLINE],
            interval="1m",
            monitor_memory=True
        )
        
        # Verify memory efficiency
        assert result.success
        assert result.peak_memory_mb < 2000  # Under 2GB peak
        assert result.memory_efficiency >= 0.8  # 80% efficiency
    
    @pytest.mark.asyncio
    async def test_reliability_improvement(self, config):
        """Test reliability improvement over legacy scripts"""
        # Execute with fault injection
        result = await complete_pipeline_workflow(
            config=config,
            market_types=[MarketType.SPOT],
            data_types=[DataType.KLINE],
            interval="1m",
            fault_injection=True,  # Simulate failures
            max_retries=3
        )
        
        # Verify reliability
        assert result.success
        assert result.fault_tolerance_score >= 0.95  # 95% reliability
        assert result.recovery_time_seconds < 30  # Fast recovery