"""
Legacy Equivalent Workflows

This module provides enhanced workflows that match the functionality of legacy shell scripts
while adding modern capabilities like parallel processing, error recovery, and monitoring.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import polars as pl
from prefect import flow
from prefect.logging import get_run_logger

from crypto_lakehouse.core.config import Config
from crypto_lakehouse.core.models import DataType, MarketType, WorkflowResult
from crypto_lakehouse.ingestion.binance import BinanceIngestion
from crypto_lakehouse.processing.data_processor import DataProcessor
from crypto_lakehouse.storage.s3_storage import S3Storage
from crypto_lakehouse.utils.data_merger import DataMerger
from crypto_lakehouse.utils.gap_detection import GapDetector
from crypto_lakehouse.utils.resampler import DataResampler


@dataclass
class WorkflowMetrics:
    """Workflow execution metrics"""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    processing_time: float = 0.0
    throughput_mbps: float = 0.0
    memory_efficiency: float = 0.0
    error_count: int = 0
    retry_count: int = 0
    data_quality_score: float = 0.0

    def finalize(self):
        """Finalize metrics calculation"""
        self.end_time = datetime.now()
        self.processing_time = (self.end_time - self.start_time).total_seconds()


@dataclass
class LegacyWorkflowResult(WorkflowResult):
    """Extended workflow result with legacy compatibility metrics"""

    legacy_equivalent: str = ""
    performance_improvement: float = 0.0
    feature_enhancements: List[str] = field(default_factory=list)
    metrics: WorkflowMetrics = field(default_factory=WorkflowMetrics)


@flow(name="AWS Download Workflow")
async def aws_download_workflow(
    config: Config,
    data_types: List[DataType],
    market_types: List[MarketType],
    interval: str = "1m",
    verify: bool = True,
    max_concurrent: int = 10,
    **kwargs,
) -> LegacyWorkflowResult:
    """
    Enhanced equivalent of aws_download.sh

    Legacy script sequence:
    1. Download funding rates (UM + CM futures)
    2. Verify funding rates
    3. Download klines (spot + UM + CM futures)
    4. Verify klines

    Enhancements:
    - Parallel processing
    - Progress monitoring
    - Error recovery
    - Performance metrics
    """
    logger = get_run_logger()
    metrics = WorkflowMetrics()

    try:
        logger.info("Starting AWS download workflow - Legacy equivalent: aws_download.sh")

        # Initialize components
        ingestion = BinanceIngestion(config)
        storage = S3Storage(config)

        results = []

        # Process each market type in parallel (enhancement)
        async def process_market_type(market_type: MarketType):
            market_results = []

            for data_type in data_types:
                logger.info(f"Processing {data_type.value} for {market_type.value}")

                # Download data
                download_result = await ingestion.download_bulk_data(
                    market_type=market_type,
                    data_type=data_type,
                    interval=interval,
                    max_concurrent=max_concurrent,
                )

                if download_result.success:
                    # Verify data (legacy equivalent)
                    if verify:
                        verify_result = await ingestion.verify_bulk_data(
                            market_type=market_type, data_type=data_type, interval=interval
                        )
                        download_result.verification_passed = verify_result.success

                    market_results.append(download_result)
                else:
                    logger.error(f"Failed to download {data_type.value} for {market_type.value}")
                    metrics.error_count += 1

            return market_results

        # Execute parallel processing (enhancement over legacy)
        tasks = [process_market_type(mt) for mt in market_types]
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for result_group in parallel_results:
            if isinstance(result_group, Exception):
                logger.error(f"Market type processing failed: {result_group}")
                metrics.error_count += 1
            else:
                results.extend(result_group)

        # Calculate metrics
        total_files = sum(
            len(r.downloaded_files) for r in results if hasattr(r, "downloaded_files")
        )
        success_rate = len([r for r in results if r.success]) / len(results) if results else 0

        metrics.data_quality_score = success_rate
        metrics.finalize()

        return LegacyWorkflowResult(
            success=metrics.error_count == 0,
            message=f"Downloaded {total_files} files across {len(market_types)} market types",
            legacy_equivalent="aws_download.sh",
            performance_improvement=metrics.throughput_mbps / 1.0,  # vs legacy baseline
            feature_enhancements=[
                "Parallel processing",
                "Progress monitoring",
                "Error recovery",
                "Performance metrics",
            ],
            metrics=metrics,
            downloaded_files=total_files,
            verification_passed=all(getattr(r, "verification_passed", False) for r in results),
        )

    except Exception as e:
        logger.error(f"AWS download workflow failed: {e}")
        metrics.error_count += 1
        metrics.finalize()

        return LegacyWorkflowResult(
            success=False,
            message=f"Workflow failed: {e}",
            legacy_equivalent="aws_download.sh",
            metrics=metrics,
        )


@flow(name="AWS Parse Workflow")
async def aws_parse_workflow(
    config: Config,
    data_types: List[DataType],
    market_types: List[MarketType],
    interval: str = "1m",
    validate_data: bool = True,
    compute_technical_indicators: bool = True,
    **kwargs,
) -> LegacyWorkflowResult:
    """
    Enhanced equivalent of aws_parse.sh

    Legacy script sequence:
    1. Parse funding rates (UM + CM futures)
    2. Parse klines (spot + UM + CM futures)

    Enhancements:
    - Data validation
    - Technical indicators
    - Quality scoring
    - Parallel processing
    """
    logger = get_run_logger()
    metrics = WorkflowMetrics()

    try:
        logger.info("Starting AWS parse workflow - Legacy equivalent: aws_parse.sh")

        # Initialize components
        processor = DataProcessor(config)
        storage = S3Storage(config)

        results = []

        # Process each combination in parallel
        async def process_data_type(market_type: MarketType, data_type: DataType):
            logger.info(f"Parsing {data_type.value} for {market_type.value}")

            # Parse raw data
            parse_result = await processor.parse_raw_data(
                market_type=market_type,
                data_type=data_type,
                interval=interval,
                validate=validate_data,
                compute_indicators=compute_technical_indicators,
            )

            if parse_result.success:
                # Store in Silver layer
                storage_result = await storage.store_processed_data(
                    data=parse_result.data,
                    market_type=market_type,
                    data_type=data_type,
                    layer="silver",
                )

                parse_result.storage_success = storage_result.success

            return parse_result

        # Execute parallel processing
        tasks = [process_data_type(mt, dt) for mt in market_types for dt in data_types]
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for result in parallel_results:
            if isinstance(result, Exception):
                logger.error(f"Data parsing failed: {result}")
                metrics.error_count += 1
            else:
                results.append(result)

        # Calculate quality metrics
        successful_parses = [r for r in results if r.success]
        total_quality_score = sum(getattr(r, "quality_score", 0.0) for r in successful_parses)
        avg_quality_score = (
            total_quality_score / len(successful_parses) if successful_parses else 0.0
        )

        metrics.data_quality_score = avg_quality_score
        metrics.finalize()

        return LegacyWorkflowResult(
            success=metrics.error_count == 0,
            message=f"Parsed {len(successful_parses)} data types with {avg_quality_score:.2f} quality score",
            legacy_equivalent="aws_parse.sh",
            performance_improvement=metrics.throughput_mbps / 0.5,  # vs legacy baseline
            feature_enhancements=[
                "Data validation",
                "Technical indicators",
                "Quality scoring",
                "Parallel processing",
            ],
            metrics=metrics,
            parsed_files=len(successful_parses),
            data_quality_score=avg_quality_score,
            validation_passed=all(
                getattr(r, "validation_passed", False) for r in successful_parses
            ),
            technical_indicators_computed=compute_technical_indicators,
        )

    except Exception as e:
        logger.error(f"AWS parse workflow failed: {e}")
        metrics.error_count += 1
        metrics.finalize()

        return LegacyWorkflowResult(
            success=False,
            message=f"Workflow failed: {e}",
            legacy_equivalent="aws_parse.sh",
            metrics=metrics,
        )


@flow(name="API Download Workflow")
async def api_download_workflow(
    config: Config,
    data_types: List[DataType],
    market_types: List[MarketType],
    interval: str = "1m",
    gap_detection: bool = True,
    recent_only: bool = False,
    max_concurrent: int = 5,
    **kwargs,
) -> LegacyWorkflowResult:
    """
    Enhanced equivalent of api_download.sh

    Legacy script sequence:
    1. Download missing klines (spot + UM + CM futures)
    2. Download recent funding rates (UM + CM futures)

    Enhancements:
    - Automatic gap detection
    - Smart incremental updates
    - Rate limiting
    - Error recovery
    """
    logger = get_run_logger()
    metrics = WorkflowMetrics()

    try:
        logger.info("Starting API download workflow - Legacy equivalent: api_download.sh")

        # Initialize components
        ingestion = BinanceIngestion(config)
        gap_detector = GapDetector(config)

        results = []
        filled_gaps = []

        # Process each market type
        for market_type in market_types:
            for data_type in data_types:
                logger.info(f"Processing {data_type.value} for {market_type.value}")

                # Detect gaps if enabled (enhancement)
                if gap_detection and not recent_only:
                    gaps = await gap_detector.detect_gaps(
                        market_type=market_type, data_type=data_type, interval=interval
                    )

                    if gaps:
                        logger.info(f"Found {len(gaps)} gaps to fill")

                        # Fill gaps via API
                        for gap in gaps:
                            fill_result = await ingestion.fill_gap_via_api(
                                market_type=market_type,
                                data_type=data_type,
                                interval=interval,
                                start_time=gap.start_time,
                                end_time=gap.end_time,
                            )

                            if fill_result.success:
                                filled_gaps.append(gap)
                            else:
                                metrics.error_count += 1

                # Download recent data
                if recent_only or data_type == DataType.FUNDING_RATE:
                    recent_result = await ingestion.download_recent_data(
                        market_type=market_type,
                        data_type=data_type,
                        interval=interval,
                        max_concurrent=max_concurrent,
                    )

                    if recent_result.success:
                        results.append(recent_result)
                    else:
                        logger.error(
                            f"Failed to download recent {data_type.value} for {market_type.value}"
                        )
                        metrics.error_count += 1

        # Calculate metrics
        success_rate = (
            len(results) / (len(market_types) * len(data_types))
            if market_types and data_types
            else 0
        )
        metrics.data_quality_score = success_rate
        metrics.finalize()

        return LegacyWorkflowResult(
            success=metrics.error_count == 0,
            message=f"Downloaded recent data and filled {len(filled_gaps)} gaps",
            legacy_equivalent="api_download.sh",
            performance_improvement=metrics.throughput_mbps / 0.3,  # vs legacy baseline
            feature_enhancements=[
                "Automatic gap detection",
                "Smart incremental updates",
                "Rate limiting",
                "Error recovery",
            ],
            metrics=metrics,
            filled_gaps=filled_gaps,
            recent_data=results,
            gap_detection_completed=gap_detection,
            data_freshness_score=success_rate,
        )

    except Exception as e:
        logger.error(f"API download workflow failed: {e}")
        metrics.error_count += 1
        metrics.finalize()

        return LegacyWorkflowResult(
            success=False,
            message=f"Workflow failed: {e}",
            legacy_equivalent="api_download.sh",
            metrics=metrics,
        )


@flow(name="Generate Kline Workflow")
async def gen_kline_workflow(
    config: Config,
    market_type: MarketType,
    interval: str = "1m",
    split_gaps: bool = True,
    with_vwap: bool = True,
    with_funding_rates: bool = True,
    compute_technical_indicators: bool = False,
    market_microstructure: bool = False,
    data_quality_checks: bool = True,
    **kwargs,
) -> LegacyWorkflowResult:
    """
    Enhanced equivalent of gen_kline.sh

    Legacy script sequence:
    1. Generate spot klines with VWAP, no funding rates
    2. Generate futures klines with VWAP and funding rates
    3. Apply gap splitting

    Enhancements:
    - Technical indicators
    - Market microstructure features
    - Data quality checks
    - Performance optimization
    """
    logger = get_run_logger()
    metrics = WorkflowMetrics()

    try:
        logger.info("Starting generate kline workflow - Legacy equivalent: gen_kline.sh")
        logger.info(f"Market: {market_type.value}, Interval: {interval}")
        logger.info(
            f"Options: split_gaps={split_gaps}, vwap={with_vwap}, funding={with_funding_rates}"
        )

        # Initialize components
        processor = DataProcessor(config)
        merger = DataMerger(config)
        storage = S3Storage(config)

        # Load processed data from Silver layer
        kline_data = await storage.load_processed_data(
            market_type=market_type, data_type=DataType.KLINE, interval=interval, layer="silver"
        )

        if kline_data.is_empty():
            raise ValueError(f"No kline data found for {market_type.value} {interval}")

        # Merge AWS and API data (enhancement)
        merged_data = await merger.merge_kline_data(
            aws_data=kline_data.filter(pl.col("source") == "aws"),
            api_data=kline_data.filter(pl.col("source") == "api"),
            strategy="quality_priority",
        )

        # Split gaps if enabled
        if split_gaps:
            gap_detector = GapDetector(config)
            gaps = await gap_detector.detect_gaps_in_data(merged_data)

            if gaps:
                logger.info(f"Found {len(gaps)} gaps in data")
                merged_data = await gap_detector.split_at_gaps(merged_data, gaps)

        # Compute VWAP if enabled
        if with_vwap:
            merged_data = await processor.compute_vwap(merged_data)

        # Join funding rates if enabled
        funding_rates_joined = False
        if with_funding_rates and market_type in [MarketType.UM_FUTURES, MarketType.CM_FUTURES]:
            funding_data = await storage.load_processed_data(
                market_type=market_type, data_type=DataType.FUNDING_RATE, layer="silver"
            )

            if not funding_data.is_empty():
                merged_data = await merger.join_funding_rates(merged_data, funding_data)
                funding_rates_joined = True

        # Compute technical indicators if enabled (enhancement)
        technical_indicators_computed = False
        if compute_technical_indicators:
            merged_data = await processor.compute_technical_indicators(
                merged_data, indicators=["rsi", "macd", "bollinger_bands", "ema"]
            )
            technical_indicators_computed = True

        # Compute market microstructure if enabled (enhancement)
        microstructure_computed = False
        if market_microstructure:
            merged_data = await processor.compute_market_microstructure(merged_data)
            microstructure_computed = True

        # Data quality checks if enabled (enhancement)
        quality_checks_passed = True
        quality_score = 1.0
        if data_quality_checks:
            quality_result = await processor.validate_data_quality(merged_data)
            quality_checks_passed = quality_result.passed
            quality_score = quality_result.score

        # Store in Gold layer
        storage_result = await storage.store_processed_data(
            data=merged_data,
            market_type=market_type,
            data_type=DataType.KLINE,
            layer="gold",
            metadata={
                "interval": interval,
                "vwap_computed": with_vwap,
                "funding_rates_joined": funding_rates_joined,
                "technical_indicators": technical_indicators_computed,
                "microstructure": microstructure_computed,
                "quality_score": quality_score,
            },
        )

        metrics.data_quality_score = quality_score
        metrics.finalize()

        return LegacyWorkflowResult(
            success=storage_result.success,
            message=f"Generated {len(merged_data)} klines with quality score {quality_score:.2f}",
            legacy_equivalent="gen_kline.sh",
            performance_improvement=metrics.throughput_mbps / 0.8,  # vs legacy baseline
            feature_enhancements=[
                "Technical indicators" if technical_indicators_computed else None,
                "Market microstructure" if microstructure_computed else None,
                "Data quality checks" if data_quality_checks else None,
                "Performance optimization",
            ],
            metrics=metrics,
            vwap_computed=with_vwap,
            funding_rates_joined=funding_rates_joined,
            gaps_handled=split_gaps,
            technical_indicators_computed=technical_indicators_computed,
            microstructure_computed=microstructure_computed,
            quality_checks_passed=quality_checks_passed,
            data_quality_score=quality_score,
        )

    except Exception as e:
        logger.error(f"Generate kline workflow failed: {e}")
        metrics.error_count += 1
        metrics.finalize()

        return LegacyWorkflowResult(
            success=False,
            message=f"Workflow failed: {e}",
            legacy_equivalent="gen_kline.sh",
            metrics=metrics,
        )


@flow(name="Resample Workflow")
async def resample_workflow(
    config: Config,
    market_type: MarketType,
    source_interval: str = "1m",
    target_interval: str = "1h",
    target_intervals: Optional[List[str]] = None,
    offset: str = "0m",
    **kwargs,
) -> LegacyWorkflowResult:
    """
    Enhanced equivalent of resample.sh

    Legacy script sequence:
    1. Resample 1h with 5m offset
    2. Resample 5m with 0m offset

    Enhancements:
    - Multiple target intervals
    - Accuracy validation
    - Performance optimization
    - Custom aggregation functions
    """
    logger = get_run_logger()
    metrics = WorkflowMetrics()

    try:
        logger.info("Starting resample workflow - Legacy equivalent: resample.sh")
        logger.info(
            f"Market: {market_type.value}, {source_interval} -> {target_interval}, offset: {offset}"
        )

        # Initialize components
        resampler = DataResampler(config)
        storage = S3Storage(config)

        # Load source data from Gold layer
        source_data = await storage.load_processed_data(
            market_type=market_type,
            data_type=DataType.KLINE,
            interval=source_interval,
            layer="gold",
        )

        if source_data.is_empty():
            raise ValueError(f"No source data found for {market_type.value} {source_interval}")

        # Handle multiple target intervals (enhancement)
        intervals_to_process = target_intervals if target_intervals else [target_interval]
        results = {}
        accuracy_scores = {}

        for target_int in intervals_to_process:
            logger.info(f"Resampling to {target_int}")

            # Resample data
            resampled_data = await resampler.resample_klines(
                data=source_data,
                source_interval=source_interval,
                target_interval=target_int,
                offset=offset,
                aggregation_functions={
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                    "vwap": "mean",
                },
            )

            # Validate accuracy (enhancement)
            accuracy = await resampler.validate_resampling_accuracy(
                source_data=source_data,
                resampled_data=resampled_data,
                source_interval=source_interval,
                target_interval=target_int,
            )

            # Store resampled data
            storage_result = await storage.store_processed_data(
                data=resampled_data,
                market_type=market_type,
                data_type=DataType.KLINE,
                layer="gold",
                metadata={
                    "source_interval": source_interval,
                    "target_interval": target_int,
                    "offset": offset,
                    "accuracy": accuracy,
                    "resampling_timestamp": datetime.now().isoformat(),
                },
            )

            results[target_int] = storage_result
            accuracy_scores[target_int] = accuracy

        # Calculate overall metrics
        overall_accuracy = sum(accuracy_scores.values()) / len(accuracy_scores)
        metrics.data_quality_score = overall_accuracy
        metrics.finalize()

        return LegacyWorkflowResult(
            success=all(r.success for r in results.values()),
            message=f"Resampled to {len(intervals_to_process)} intervals with {overall_accuracy:.2f} accuracy",
            legacy_equivalent="resample.sh",
            performance_improvement=metrics.throughput_mbps / 0.2,  # vs legacy baseline
            feature_enhancements=[
                "Multiple target intervals",
                "Accuracy validation",
                "Performance optimization",
                "Custom aggregation functions",
            ],
            metrics=metrics,
            target_interval=target_interval,
            target_intervals=intervals_to_process,
            offset_applied=offset,
            resampling_accuracy=overall_accuracy,
            accuracy_scores=accuracy_scores,
            resampled_intervals=list(results.keys()),
        )

    except Exception as e:
        logger.error(f"Resample workflow failed: {e}")
        metrics.error_count += 1
        metrics.finalize()

        return LegacyWorkflowResult(
            success=False,
            message=f"Workflow failed: {e}",
            legacy_equivalent="resample.sh",
            metrics=metrics,
        )


@flow(name="Complete Pipeline Workflow")
async def complete_pipeline_workflow(
    config: Config,
    market_types: List[MarketType],
    data_types: List[DataType],
    interval: str = "1m",
    download_aws: bool = True,
    parse_aws: bool = True,
    download_api: bool = True,
    generate_klines: bool = True,
    resample: bool = True,
    parallel_processing: bool = True,
    data_quality_checks: bool = True,
    technical_indicators: bool = True,
    max_retries: int = 3,
    error_recovery: bool = True,
    performance_monitoring: bool = True,
    **kwargs,
) -> LegacyWorkflowResult:
    """
    Complete pipeline workflow equivalent to running all legacy scripts in sequence

    Legacy script sequence:
    1. aws_download.sh
    2. aws_parse.sh
    3. api_download.sh
    4. gen_kline.sh
    5. resample.sh

    Enhancements:
    - Parallel processing
    - Error recovery
    - Performance monitoring
    - Data quality tracking
    - End-to-end orchestration
    """
    logger = get_run_logger()
    metrics = WorkflowMetrics()

    try:
        logger.info("Starting complete pipeline workflow - Legacy equivalent: all scripts")

        # Initialize result tracking
        results = {}
        retry_counts = {}

        # Step 1: AWS Download (aws_download.sh equivalent)
        if download_aws:
            logger.info("Step 1: AWS Download")
            for attempt in range(max_retries + 1):
                try:
                    aws_download_result = await aws_download_workflow(
                        config=config,
                        data_types=data_types,
                        market_types=market_types,
                        interval=interval,
                        verify=True,
                        max_concurrent=10 if parallel_processing else 1,
                    )

                    if aws_download_result.success:
                        results["aws_download"] = aws_download_result
                        break
                    else:
                        raise Exception(f"AWS download failed: {aws_download_result.message}")

                except Exception as e:
                    if attempt < max_retries and error_recovery:
                        logger.warning(f"AWS download attempt {attempt + 1} failed, retrying: {e}")
                        retry_counts["aws_download"] = attempt + 1
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        raise

        # Step 2: AWS Parse (aws_parse.sh equivalent)
        if parse_aws:
            logger.info("Step 2: AWS Parse")
            for attempt in range(max_retries + 1):
                try:
                    aws_parse_result = await aws_parse_workflow(
                        config=config,
                        data_types=data_types,
                        market_types=market_types,
                        interval=interval,
                        validate_data=data_quality_checks,
                        compute_technical_indicators=technical_indicators,
                    )

                    if aws_parse_result.success:
                        results["aws_parse"] = aws_parse_result
                        break
                    else:
                        raise Exception(f"AWS parse failed: {aws_parse_result.message}")

                except Exception as e:
                    if attempt < max_retries and error_recovery:
                        logger.warning(f"AWS parse attempt {attempt + 1} failed, retrying: {e}")
                        retry_counts["aws_parse"] = attempt + 1
                        await asyncio.sleep(2**attempt)
                    else:
                        raise

        # Step 3: API Download (api_download.sh equivalent)
        if download_api:
            logger.info("Step 3: API Download")
            for attempt in range(max_retries + 1):
                try:
                    api_download_result = await api_download_workflow(
                        config=config,
                        data_types=data_types,
                        market_types=market_types,
                        interval=interval,
                        gap_detection=True,
                        max_concurrent=5 if parallel_processing else 1,
                    )

                    if api_download_result.success:
                        results["api_download"] = api_download_result
                        break
                    else:
                        raise Exception(f"API download failed: {api_download_result.message}")

                except Exception as e:
                    if attempt < max_retries and error_recovery:
                        logger.warning(f"API download attempt {attempt + 1} failed, retrying: {e}")
                        retry_counts["api_download"] = attempt + 1
                        await asyncio.sleep(2**attempt)
                    else:
                        raise

        # Step 4: Generate Klines (gen_kline.sh equivalent)
        if generate_klines:
            logger.info("Step 4: Generate Klines")
            kline_results = []

            for market_type in market_types:
                for attempt in range(max_retries + 1):
                    try:
                        gen_kline_result = await gen_kline_workflow(
                            config=config,
                            market_type=market_type,
                            interval=interval,
                            split_gaps=True,
                            with_vwap=True,
                            with_funding_rates=(market_type != MarketType.SPOT),
                            compute_technical_indicators=technical_indicators,
                            data_quality_checks=data_quality_checks,
                        )

                        if gen_kline_result.success:
                            kline_results.append(gen_kline_result)
                            break
                        else:
                            raise Exception(f"Generate klines failed: {gen_kline_result.message}")

                    except Exception as e:
                        if attempt < max_retries and error_recovery:
                            logger.warning(
                                f"Generate klines attempt {attempt + 1} failed, retrying: {e}"
                            )
                            retry_counts[f"gen_kline_{market_type.value}"] = attempt + 1
                            await asyncio.sleep(2**attempt)
                        else:
                            raise

            results["gen_klines"] = kline_results

        # Step 5: Resample (resample.sh equivalent)
        if resample:
            logger.info("Step 5: Resample")
            resample_results = []

            for market_type in market_types:
                for attempt in range(max_retries + 1):
                    try:
                        # Resample to multiple intervals (enhancement)
                        resample_result = await resample_workflow(
                            config=config,
                            market_type=market_type,
                            source_interval="1m",
                            target_intervals=["5m", "1h"],
                            offset="0m",
                        )

                        if resample_result.success:
                            resample_results.append(resample_result)
                            break
                        else:
                            raise Exception(f"Resample failed: {resample_result.message}")

                    except Exception as e:
                        if attempt < max_retries and error_recovery:
                            logger.warning(f"Resample attempt {attempt + 1} failed, retrying: {e}")
                            retry_counts[f"resample_{market_type.value}"] = attempt + 1
                            await asyncio.sleep(2**attempt)
                        else:
                            raise

            results["resample"] = resample_results

        # Calculate overall metrics
        total_retry_count = sum(retry_counts.values())
        overall_success = all(
            (
                isinstance(r, list) and all(item.success for item in r)
                if isinstance(r, list)
                else r.success
            )
            for r in results.values()
        )

        # Calculate quality score
        quality_scores = []
        for result in results.values():
            if isinstance(result, list):
                quality_scores.extend([getattr(r, "data_quality_score", 1.0) for r in result])
            else:
                quality_scores.append(getattr(result, "data_quality_score", 1.0))

        overall_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 1.0

        metrics.data_quality_score = overall_quality_score
        metrics.retry_count = total_retry_count
        metrics.finalize()

        return LegacyWorkflowResult(
            success=overall_success,
            message=f"Complete pipeline executed successfully with {total_retry_count} retries",
            legacy_equivalent="aws_download.sh + aws_parse.sh + api_download.sh + gen_kline.sh + resample.sh",
            performance_improvement=metrics.throughput_mbps / 0.1,  # vs legacy baseline
            feature_enhancements=[
                "Parallel processing",
                "Error recovery",
                "Performance monitoring",
                "Data quality tracking",
                "End-to-end orchestration",
            ],
            metrics=metrics,
            aws_download_completed=download_aws and "aws_download" in results,
            aws_parse_completed=parse_aws and "aws_parse" in results,
            api_download_completed=download_api and "api_download" in results,
            kline_generation_completed=generate_klines and "gen_klines" in results,
            resampling_completed=resample and "resample" in results,
            overall_quality_score=overall_quality_score,
            retry_count=total_retry_count,
            error_recovery_successful=error_recovery and total_retry_count > 0,
        )

    except Exception as e:
        logger.error(f"Complete pipeline workflow failed: {e}")
        metrics.error_count += 1
        metrics.finalize()

        return LegacyWorkflowResult(
            success=False,
            message=f"Pipeline failed: {e}",
            legacy_equivalent="Complete pipeline",
            metrics=metrics,
        )
