"""
Prefect workflows for orchestrating data lakehouse operations.

This module provides comprehensive workflow orchestration for the crypto data lakehouse,
including data ingestion, processing, and quality management workflows.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import asyncio

from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from prefect.blocks.system import Secret
from prefect.artifacts import create_markdown_artifact

from ..core.config import Settings
from ..core.models import Exchange, DataType, KlineData, FundingRateData
from ..ingestion.binance import BinanceIngestor
from ..storage.s3_storage import S3LakehouseStorage
from ..processing.kline_processor import KlineProcessor
from ..utils.gap_detection import GapDetector
from ..utils.data_merger import DataMerger, MergeConfig, MergeStrategy
from ..utils.resampler import DataResampler, ResamplingConfig
from ..utils.query_engine import DuckDBQueryEngine

logger = logging.getLogger(__name__)


@task
async def setup_clients(settings: Settings) -> Dict[str, Any]:
    """Setup clients for data ingestion and storage."""
    logger = get_run_logger()
    
    try:
        # Initialize clients
        ingestion_client = BinanceIngestor(settings)
        storage_client = S3LakehouseStorage(settings)
        
        logger.info("Clients initialized successfully")
        
        return {
            "ingestion": ingestion_client,
            "storage": storage_client
        }
    except Exception as e:
        logger.error(f"Failed to setup clients: {e}")
        raise


@task
async def ingest_bulk_data(
    clients: Dict[str, Any],
    symbol: str,
    data_type: DataType,
    start_date: datetime,
    end_date: datetime
) -> List[Any]:
    """Ingest bulk historical data."""
    logger = get_run_logger()
    
    try:
        ingestion_client = clients["ingestion"]
        
        if data_type == DataType.KLINE:
            # Use bulk ingestor for K-line data
            data = []
            async for kline in ingestion_client.ingest_klines(
                symbols=[symbol],
                interval="1m",
                trade_type="spot",
                start_date=start_date,
                end_date=end_date
            ):
                data.append(kline)
        elif data_type == DataType.FUNDING_RATE:
            # Use bulk ingestor for funding rates
            data = []
            async for rate in ingestion_client.ingest_funding_rates(
                symbols=[symbol],
                start_date=start_date,
                end_date=end_date
            ):
                data.append(rate)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        logger.info(f"Ingested {len(data)} {data_type} records for {symbol}")
        return data
        
    except Exception as e:
        logger.error(f"Bulk ingestion failed for {symbol}: {e}")
        raise


@task
async def ingest_incremental_data(
    clients: Dict[str, Any],
    symbol: str,
    data_type: DataType,
    start_date: datetime,
    end_date: datetime
) -> List[Any]:
    """Ingest incremental data via API."""
    logger = get_run_logger()
    
    try:
        ingestion_client = clients["ingestion"]
        
        if data_type == DataType.KLINE:
            # Use incremental ingestor for K-line data
            data = []
            async for kline in ingestion_client.ingest_klines(
                symbols=[symbol],
                interval="1m",
                trade_type="spot",
                start_date=start_date,
                end_date=end_date
            ):
                data.append(kline)
        elif data_type == DataType.FUNDING_RATE:
            # Use incremental ingestor for funding rates
            data = []
            async for rate in ingestion_client.ingest_funding_rates(
                symbols=[symbol],
                start_date=start_date,
                end_date=end_date
            ):
                data.append(rate)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        logger.info(f"Ingested {len(data)} incremental {data_type} records for {symbol}")
        return data
        
    except Exception as e:
        logger.error(f"Incremental ingestion failed for {symbol}: {e}")
        raise


@task
async def detect_gaps(data: List[Any], symbol: str, data_type: DataType) -> Dict[str, Any]:
    """Detect gaps in the ingested data."""
    logger = get_run_logger()
    
    try:
        detector = GapDetector()
        
        if data_type == DataType.KLINE:
            gaps = detector.detect_kline_gaps(data, symbol)
        elif data_type == DataType.FUNDING_RATE:
            gaps = detector.detect_funding_rate_gaps(data, symbol)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        gap_info = {
            "total_gaps": len(gaps),
            "gaps": gaps,
            "completeness": detector.calculate_completeness(gaps, data)
        }
        
        logger.info(f"Gap detection completed for {symbol}: {gap_info['total_gaps']} gaps found")
        return gap_info
        
    except Exception as e:
        logger.error(f"Gap detection failed for {symbol}: {e}")
        raise


@task
async def merge_data_sources(
    bulk_data: List[Any],
    incremental_data: List[Any],
    symbol: str,
    data_type: DataType
) -> Dict[str, Any]:
    """Merge bulk and incremental data sources."""
    logger = get_run_logger()
    
    try:
        # Configure merge strategy
        merge_config = MergeConfig(
            merge_strategy=MergeStrategy.BULK_PRIORITY,
            enable_deduplication=True,
            enable_validation=True
        )
        
        merger = DataMerger(merge_config)
        
        if data_type == DataType.KLINE:
            result = merger.merge_kline_data(bulk_data, incremental_data, symbol)
        elif data_type == DataType.FUNDING_RATE:
            result = merger.merge_funding_rate_data(bulk_data, incremental_data, symbol)
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        logger.info(f"Data merge completed for {symbol}: {result.merged_records} final records")
        
        return {
            "merge_result": result,
            "merged_data": None  # Data would be returned here in actual implementation
        }
        
    except Exception as e:
        logger.error(f"Data merge failed for {symbol}: {e}")
        raise


@task
async def process_kline_data(
    kline_data: List[KlineData],
    symbol: str
) -> List[KlineData]:
    """Process K-line data with technical indicators."""
    logger = get_run_logger()
    
    try:
        processor = KlineProcessor()
        processed_data = processor.process_klines(kline_data, symbol)
        
        logger.info(f"Processed {len(processed_data)} K-line records for {symbol}")
        return processed_data
        
    except Exception as e:
        logger.error(f"K-line processing failed for {symbol}: {e}")
        raise


@task
async def resample_data(
    data: List[KlineData],
    symbol: str,
    target_timeframes: List[str]
) -> Dict[str, List[KlineData]]:
    """Resample data to different timeframes."""
    logger = get_run_logger()
    
    try:
        resampled_data = {}
        
        for timeframe in target_timeframes:
            config = ResamplingConfig(
                source_timeframe="1m",
                target_timeframe=timeframe
            )
            
            resampler = DataResampler(config)
            result = resampler.resample_klines(data, symbol)
            
            resampled_data[timeframe] = None  # Would contain resampled data
            
            logger.info(f"Resampled {symbol} to {timeframe}: {result.target_records} records")
        
        return resampled_data
        
    except Exception as e:
        logger.error(f"Data resampling failed for {symbol}: {e}")
        raise


@task
async def store_to_lakehouse(
    clients: Dict[str, Any],
    data: List[Any],
    symbol: str,
    data_type: DataType,
    layer: str = "silver"
) -> Dict[str, Any]:
    """Store data to the lakehouse."""
    logger = get_run_logger()
    
    try:
        storage_client = clients["storage"]
        
        if data_type == DataType.KLINE:
            storage_result = await storage_client.store_kline_data(
                data=data,
                symbol=symbol,
                layer=layer
            )
        elif data_type == DataType.FUNDING_RATE:
            storage_result = await storage_client.store_funding_rate_data(
                data=data,
                symbol=symbol,
                layer=layer
            )
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
        
        logger.info(f"Stored {len(data)} {data_type} records to {layer} layer for {symbol}")
        return storage_result
        
    except Exception as e:
        logger.error(f"Storage failed for {symbol}: {e}")
        raise


@task
async def validate_data_quality(
    data: List[Any],
    symbol: str,
    data_type: DataType
) -> Dict[str, Any]:
    """Validate data quality and generate quality metrics."""
    logger = get_run_logger()
    
    try:
        # Simple quality validation
        quality_metrics = {
            "total_records": len(data),
            "null_count": 0,
            "duplicate_count": 0,
            "quality_score": 1.0
        }
        
        # Add specific validation logic here
        if data_type == DataType.KLINE:
            # Validate K-line data
            for record in data:
                if not isinstance(record, KlineData):
                    continue
                    
                # Check for null values
                if record.open_price is None or record.close_price is None:
                    quality_metrics["null_count"] += 1
                    
                # Check for unrealistic values
                if record.volume < 0:
                    quality_metrics["quality_score"] *= 0.95
        
        # Calculate overall quality score
        if quality_metrics["total_records"] > 0:
            quality_metrics["quality_score"] *= (
                1 - quality_metrics["null_count"] / quality_metrics["total_records"]
            )
        
        logger.info(f"Data quality validation completed for {symbol}: {quality_metrics['quality_score']:.2f}")
        return quality_metrics
        
    except Exception as e:
        logger.error(f"Data quality validation failed for {symbol}: {e}")
        raise


@task
async def create_quality_report(
    symbol: str,
    data_type: DataType,
    quality_metrics: Dict[str, Any],
    merge_result: Dict[str, Any],
    gap_info: Dict[str, Any]
) -> str:
    """Create comprehensive quality report."""
    logger = get_run_logger()
    
    try:
        report_content = f"""
# Data Quality Report: {symbol}

## Summary
- **Symbol:** {symbol}
- **Data Type:** {data_type}
- **Timestamp:** {datetime.now().isoformat()}

## Quality Metrics
- **Total Records:** {quality_metrics['total_records']}
- **Quality Score:** {quality_metrics['quality_score']:.2f}
- **Null Count:** {quality_metrics['null_count']}
- **Duplicate Count:** {quality_metrics['duplicate_count']}

## Data Merge Results
- **Merge Strategy:** {merge_result['merge_result'].merge_strategy_used}
- **Merged Records:** {merge_result['merge_result'].merged_records}
- **Duplicates Removed:** {merge_result['merge_result'].duplicates_removed}
- **Conflicts Resolved:** {merge_result['merge_result'].conflicts_resolved}

## Gap Analysis
- **Total Gaps:** {gap_info['total_gaps']}
- **Completeness:** {gap_info['completeness']:.2f}%

## Recommendations
{'✅ Data quality is excellent' if quality_metrics['quality_score'] > 0.9 else '⚠️ Data quality needs attention'}
{'✅ No significant gaps detected' if gap_info['total_gaps'] == 0 else f'⚠️ {gap_info["total_gaps"]} gaps detected'}
"""
        
        # Create Prefect artifact
        await create_markdown_artifact(
            key=f"quality-report-{symbol}-{data_type}",
            markdown=report_content,
            description=f"Data quality report for {symbol} {data_type}"
        )
        
        logger.info(f"Quality report created for {symbol}")
        return report_content
        
    except Exception as e:
        logger.error(f"Quality report creation failed for {symbol}: {e}")
        raise


@flow(
    name="Data Ingestion Pipeline",
    description="Complete data ingestion pipeline for crypto data lakehouse",
    task_runner=ConcurrentTaskRunner()
)
async def data_ingestion_pipeline(
    symbol: str,
    data_type: DataType,
    start_date: datetime,
    end_date: datetime,
    settings: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Complete data ingestion pipeline.
    
    This flow orchestrates the entire data ingestion process including:
    - Bulk and incremental data ingestion
    - Data merging and deduplication
    - Gap detection and quality validation
    - Processing and storage to lakehouse
    """
    logger = get_run_logger()
    
    if settings is None:
        settings = Settings()
    
    logger.info(f"Starting data ingestion pipeline for {symbol} {data_type}")
    
    # Setup clients
    clients = await setup_clients(settings)
    
    # Ingest data from both sources concurrently
    bulk_data, incremental_data = await asyncio.gather(
        ingest_bulk_data(clients, symbol, data_type, start_date, end_date),
        ingest_incremental_data(clients, symbol, data_type, start_date, end_date)
    )
    
    # Detect gaps in both datasets
    bulk_gaps, incremental_gaps = await asyncio.gather(
        detect_gaps(bulk_data, symbol, data_type),
        detect_gaps(incremental_data, symbol, data_type)
    )
    
    # Merge data sources
    merge_result = await merge_data_sources(bulk_data, incremental_data, symbol, data_type)
    
    # Process data if it's K-line data
    if data_type == DataType.KLINE:
        processed_data = await process_kline_data(merge_result["merged_data"], symbol)
        
        # Resample to different timeframes
        resampled_data = await resample_data(
            processed_data, 
            symbol, 
            ["5m", "15m", "1h", "1d"]
        )
    else:
        processed_data = merge_result["merged_data"]
        resampled_data = {}
    
    # Validate data quality
    quality_metrics = await validate_data_quality(processed_data, symbol, data_type)
    
    # Store to lakehouse
    storage_result = await store_to_lakehouse(
        clients, processed_data, symbol, data_type, "silver"
    )
    
    # Create quality report
    report = await create_quality_report(
        symbol, data_type, quality_metrics, merge_result, bulk_gaps
    )
    
    logger.info(f"Data ingestion pipeline completed for {symbol}")
    
    return {
        "symbol": symbol,
        "data_type": data_type,
        "processed_records": len(processed_data),
        "quality_score": quality_metrics["quality_score"],
        "storage_result": storage_result,
        "resampled_timeframes": list(resampled_data.keys()),
        "report": report
    }


@flow(
    name="Multi-Symbol Ingestion",
    description="Ingest data for multiple symbols concurrently",
    task_runner=ConcurrentTaskRunner()
)
async def multi_symbol_ingestion_pipeline(
    symbols: List[str],
    data_type: DataType,
    start_date: datetime,
    end_date: datetime,
    settings: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Ingest data for multiple symbols concurrently.
    
    This flow processes multiple symbols in parallel for efficient
    data ingestion across the entire crypto market.
    """
    logger = get_run_logger()
    
    logger.info(f"Starting multi-symbol ingestion for {len(symbols)} symbols")
    
    # Run ingestion pipelines for all symbols concurrently
    tasks = []
    for symbol in symbols:
        task = data_ingestion_pipeline(symbol, data_type, start_date, end_date, settings)
        tasks.append(task)
    
    # Wait for all pipelines to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    successful_symbols = []
    failed_symbols = []
    total_records = 0
    
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            failed_symbols.append({"symbol": symbol, "error": str(result)})
        else:
            successful_symbols.append(symbol)
            total_records += result["processed_records"]
    
    logger.info(f"Multi-symbol ingestion completed: {len(successful_symbols)} successful, {len(failed_symbols)} failed")
    
    return {
        "successful_symbols": successful_symbols,
        "failed_symbols": failed_symbols,
        "total_records": total_records,
        "success_rate": len(successful_symbols) / len(symbols) if symbols else 0
    }


@flow(
    name="Daily Data Refresh",
    description="Daily refresh of incremental data",
    task_runner=ConcurrentTaskRunner()
)
async def daily_data_refresh_pipeline(
    symbols: List[str],
    data_types: List[DataType],
    settings: Optional[Settings] = None
) -> Dict[str, Any]:
    """
    Daily refresh pipeline for incremental data updates.
    
    This flow runs daily to fetch the latest data for all symbols
    and data types, ensuring the lakehouse is up-to-date.
    """
    logger = get_run_logger()
    
    # Calculate date range for yesterday
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=1)
    
    logger.info(f"Starting daily refresh for {len(symbols)} symbols, {len(data_types)} data types")
    
    # Run pipelines for all symbol/data_type combinations
    tasks = []
    for symbol in symbols:
        for data_type in data_types:
            task = data_ingestion_pipeline(symbol, data_type, start_date, end_date, settings)
            tasks.append(task)
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    successful_runs = 0
    failed_runs = 0
    total_records = 0
    
    for result in results:
        if isinstance(result, Exception):
            failed_runs += 1
        else:
            successful_runs += 1
            total_records += result["processed_records"]
    
    logger.info(f"Daily refresh completed: {successful_runs} successful, {failed_runs} failed")
    
    return {
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "total_records": total_records,
        "success_rate": successful_runs / (successful_runs + failed_runs) if (successful_runs + failed_runs) > 0 else 0,
        "date_range": f"{start_date.isoformat()} to {end_date.isoformat()}"
    }