#!/usr/bin/env python3
"""
Analyze schemas from existing downloaded Binance archive data.

This script analyzes the structure of already downloaded files.
"""

import csv
import json
import logging
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def analyze_csv_content(csv_content: str, data_type: str) -> Dict[str, Any]:
    """Analyze CSV content and infer schema."""
    
    lines = csv_content.strip().split('\n')
    if not lines:
        return {"error": "Empty file"}
    
    # Parse CSV data
    reader = csv.reader(lines)
    rows = list(reader)
    
    if not rows:
        return {"error": "No data rows"}
    
    # Binance files typically don't have headers
    sample_rows = rows[:min(5, len(rows))]
    
    schema = {
        "file_format": "CSV",
        "data_type": data_type,
        "total_rows": len(rows),
        "sample_rows": len(sample_rows),
        "column_count": len(rows[0]) if rows else 0,
        "columns": []
    }
    
    # Define known column mappings for Binance data types
    column_mappings = {
        "klines": [
            {"name": "open_time", "type": "timestamp_ms", "description": "Kline open time"},
            {"name": "open_price", "type": "decimal", "description": "Open price"},
            {"name": "high_price", "type": "decimal", "description": "High price"},
            {"name": "low_price", "type": "decimal", "description": "Low price"},
            {"name": "close_price", "type": "decimal", "description": "Close price"},
            {"name": "volume", "type": "decimal", "description": "Volume"},
            {"name": "close_time", "type": "timestamp_ms", "description": "Kline close time"},
            {"name": "quote_asset_volume", "type": "decimal", "description": "Quote asset volume"},
            {"name": "number_of_trades", "type": "integer", "description": "Number of trades"},
            {"name": "taker_buy_base_asset_volume", "type": "decimal", "description": "Taker buy base asset volume"},
            {"name": "taker_buy_quote_asset_volume", "type": "decimal", "description": "Taker buy quote asset volume"},
            {"name": "ignore", "type": "string", "description": "Ignore field"}
        ],
        "trades": [
            {"name": "trade_id", "type": "integer", "description": "Trade ID"},
            {"name": "price", "type": "decimal", "description": "Trade price"},
            {"name": "quantity", "type": "decimal", "description": "Trade quantity"},
            {"name": "quote_quantity", "type": "decimal", "description": "Quote quantity"},
            {"name": "time", "type": "timestamp_ms", "description": "Trade time"},
            {"name": "is_buyer_maker", "type": "boolean", "description": "Is buyer the market maker?"},
            {"name": "is_best_match", "type": "boolean", "description": "Is best price match?"}
        ],
        "fundingRate": [
            {"name": "symbol", "type": "string", "description": "Symbol"},
            {"name": "funding_time", "type": "timestamp_ms", "description": "Funding time"},
            {"name": "funding_rate", "type": "decimal", "description": "Funding rate"}
        ]
    }
    
    # Get column definitions for this data type
    expected_columns = column_mappings.get(data_type, [])
    
    # Analyze each column
    for i in range(schema["column_count"]):
        if i < len(expected_columns):
            col_info = expected_columns[i].copy()
            col_info["position"] = i
        else:
            col_info = {
                "position": i,
                "name": f"unknown_col_{i}",
                "type": "unknown",
                "description": "Unknown column"
            }
        
        # Add sample values
        col_info["sample_values"] = []
        for row in sample_rows:
            if i < len(row):
                col_info["sample_values"].append(row[i])
        
        # Try to validate inferred type with actual data
        if col_info["sample_values"]:
            sample_val = col_info["sample_values"][0]
            if col_info["type"] == "timestamp_ms":
                try:
                    timestamp = int(sample_val)
                    col_info["sample_datetime"] = datetime.fromtimestamp(timestamp / 1000).isoformat()
                except (ValueError, OSError):
                    col_info["validation_error"] = f"Invalid timestamp: {sample_val}"
            elif col_info["type"] == "decimal":
                try:
                    float(sample_val)
                    col_info["validated"] = True
                except ValueError:
                    col_info["validation_error"] = f"Invalid decimal: {sample_val}"
            elif col_info["type"] == "integer":
                try:
                    int(sample_val)
                    col_info["validated"] = True
                except ValueError:
                    col_info["validation_error"] = f"Invalid integer: {sample_val}"
            elif col_info["type"] == "boolean":
                if sample_val.lower() in ["true", "false"]:
                    col_info["validated"] = True
                else:
                    col_info["validation_error"] = f"Invalid boolean: {sample_val}"
        
        schema["columns"].append(col_info)
    
    return schema


def analyze_zip_file(zip_path: Path) -> Dict[str, Any]:
    """Analyze a single ZIP file."""
    logger = logging.getLogger(__name__)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get file list
            file_list = zip_ref.namelist()
            csv_files = [f for f in file_list if f.endswith('.csv')]
            
            if not csv_files:
                return {"error": "No CSV files found in ZIP"}
            
            # Read the CSV file (usually just one)
            csv_file = csv_files[0]
            with zip_ref.open(csv_file) as f:
                csv_content = f.read().decode('utf-8')
            
            # Extract data type from filename
            filename = zip_path.name
            if "klines" in filename or any(interval in filename for interval in ["1m", "5m", "15m", "30m", "1h", "4h", "12h", "1d"]):
                data_type = "klines"
            elif "trades" in filename:
                data_type = "trades"
            elif "fundingRate" in filename:
                data_type = "fundingRate"
            else:
                data_type = "unknown"
            
            # Analyze schema
            schema = analyze_csv_content(csv_content, data_type)
            
            # Add metadata
            schema["zip_info"] = {
                "filename": filename,
                "compressed_size": zip_path.stat().st_size,
                "contained_files": file_list,
                "csv_file": csv_file
            }
            
            return schema
            
    except Exception as e:
        logger.error(f"Error analyzing {zip_path}: {e}")
        return {"error": str(e)}


def find_archive_files() -> List[Path]:
    """Find all archive files in the test output directory."""
    
    archive_dirs = [
        Path("examples/test_output/prefect_archive"),
        Path("test_output"),
        Path("archive-samples"),
        Path("output")
    ]
    
    zip_files = []
    for archive_dir in archive_dirs:
        if archive_dir.exists():
            zip_files.extend(archive_dir.rglob("*.zip"))
    
    return zip_files


def main():
    """Main function to analyze all available schemas."""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 Analyzing Binance Archive Data Schemas")
    logger.info("=" * 80)
    
    # Find all available ZIP files
    zip_files = find_archive_files()
    
    if not zip_files:
        logger.error("No ZIP files found in archive directories")
        return
    
    logger.info(f"Found {len(zip_files)} archive files to analyze")
    
    # Group files by data type and market
    analysis_results = {}
    
    for zip_file in zip_files:
        logger.info(f"📊 Analyzing: {zip_file.name}")
        
        # Extract metadata from path
        path_parts = zip_file.parts
        
        # Try to determine market and data type from path
        market = "unknown"
        if "spot" in path_parts:
            market = "spot"
        elif "futures" in path_parts:
            market = "futures_um"
        
        # Analyze the file
        schema = analyze_zip_file(zip_file)
        
        if "error" not in schema:
            data_type = schema.get("data_type", "unknown")
            key = f"{market}_{data_type}"
            
            if key not in analysis_results:
                analysis_results[key] = {
                    "market": market,
                    "data_type": data_type,
                    "samples": []
                }
            
            analysis_results[key]["samples"].append({
                "file_path": str(zip_file),
                "schema": schema
            })
            
            logger.info(f"✅ {market} {data_type}: {schema['column_count']} columns, {schema['total_rows']} rows")
        else:
            logger.warning(f"❌ Failed to analyze {zip_file.name}: {schema['error']}")
    
    # Save results
    output_dir = Path("test_output/schema_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = output_dir / "schema_analysis_results.json"
    with open(results_file, 'w') as f:
        json.dump(analysis_results, f, indent=2, default=str)
    
    logger.info(f"📝 Results saved to: {results_file}")
    
    # Generate comprehensive documentation
    generate_schema_documentation(analysis_results, output_dir / "BINANCE_DATA_SCHEMAS.md")
    
    logger.info("=" * 80)
    logger.info("📋 Schema analysis completed!")
    
    return analysis_results


def generate_schema_documentation(results: Dict[str, Any], output_path: Path):
    """Generate comprehensive schema documentation."""
    
    with open(output_path, 'w') as f:
        f.write("# Binance Public Archive Data Schemas\n\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("This document provides comprehensive schemas for Binance public archive data types based on actual downloaded samples.\n\n")
        
        # Table of contents
        f.write("## Table of Contents\n\n")
        for key in sorted(results.keys()):
            result = results[key]
            market = result['market'].replace('_', ' ').title()
            data_type = result['data_type'].title()
            f.write(f"- [{market} {data_type}](#{key.lower().replace('_', '-')})\n")
        
        f.write("\n## Overview\n\n")
        f.write("| Market | Data Type | Samples | Avg Columns | Format |\n")
        f.write("|--------|-----------|---------|-------------|--------|\n")
        
        for key in sorted(results.keys()):
            result = results[key]
            market = result['market'].replace('_', ' ').title()
            data_type = result['data_type'].title()
            sample_count = len(result['samples'])
            
            if result['samples']:
                avg_columns = sum(s['schema']['column_count'] for s in result['samples']) / len(result['samples'])
                format_info = result['samples'][0]['schema']['file_format']
            else:
                avg_columns = 0
                format_info = "Unknown"
            
            f.write(f"| {market} | {data_type} | {sample_count} | {avg_columns:.0f} | {format_info} |\n")
        
        # Detailed schemas
        f.write("\n## Detailed Schemas\n\n")
        
        for key in sorted(results.keys()):
            result = results[key]
            market = result['market'].replace('_', ' ').title()
            data_type = result['data_type'].title()
            
            f.write(f"### {market} {data_type}\n\n")
            f.write(f"**Market**: {result['market']}\n")
            f.write(f"**Data Type**: {result['data_type']}\n")
            f.write(f"**Sample Files**: {len(result['samples'])}\n\n")
            
            if not result['samples']:
                f.write("No samples available.\n\n")
                continue
            
            # Use the first sample as reference schema
            sample = result['samples'][0]
            schema = sample['schema']
            
            f.write(f"**File Format**: {schema['file_format']}\n")
            f.write(f"**Columns**: {schema['column_count']}\n")
            f.write(f"**Sample Rows**: {schema.get('total_rows', 'Unknown')}\n\n")
            
            # Column schema table
            f.write("#### Column Schema\n\n")
            f.write("| Position | Name | Type | Description | Sample Value |\n")
            f.write("|----------|------|------|-------------|-------------|\n")
            
            for col in schema.get('columns', []):
                sample_val = col.get('sample_values', [''])[0] if col.get('sample_values') else ''
                # Truncate long sample values
                if len(str(sample_val)) > 20:
                    sample_val = str(sample_val)[:17] + "..."
                
                f.write(f"| {col.get('position', 'N/A')} | ")
                f.write(f"`{col.get('name', 'N/A')}` | ")
                f.write(f"{col.get('type', 'N/A')} | ")
                f.write(f"{col.get('description', 'N/A')} | ")
                f.write(f"`{sample_val}` |\n")
            
            # Sample files
            f.write("\n#### Sample Files\n\n")
            for i, sample in enumerate(result['samples'][:5]):  # Show up to 5 samples
                zip_info = sample['schema'].get('zip_info', {})
                filename = zip_info.get('filename', 'Unknown')
                size = zip_info.get('compressed_size', 0)
                rows = sample['schema'].get('total_rows', 0)
                
                f.write(f"- **{filename}**: {size:,} bytes, {rows:,} rows\n")
            
            if len(result['samples']) > 5:
                f.write(f"- ... and {len(result['samples']) - 5} more files\n")
            
            f.write("\n")
        
        # Technical notes
        f.write("## Technical Notes\n\n")
        f.write("### Data Types\n\n")
        f.write("- **timestamp_ms**: Unix timestamp in milliseconds\n")
        f.write("- **decimal**: Floating-point number (stored as string in CSV)\n")
        f.write("- **integer**: Whole number (stored as string in CSV)\n")
        f.write("- **boolean**: True/false value\n")
        f.write("- **string**: Text data\n\n")
        
        f.write("### File Format\n\n")
        f.write("- All data is provided in ZIP-compressed CSV format\n")
        f.write("- CSV files have no headers\n")
        f.write("- Numeric values are stored as strings\n")
        f.write("- Timestamps are Unix milliseconds\n")
        f.write("- Boolean values are typically 'true'/'false' strings\n\n")
        
        f.write("### URL Patterns\n\n")
        f.write("```\n")
        f.write("Spot: s3://data.binance.vision/data/spot/daily/{data_type}/{symbol}/{symbol}-{interval}-{date}.zip\n")
        f.write("Futures UM: s3://data.binance.vision/data/futures/um/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date}.zip\n")
        f.write("Futures CM: s3://data.binance.vision/data/futures/cm/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date}.zip\n")
        f.write("```\n\n")
    
    logging.getLogger(__name__).info(f"📋 Schema documentation generated: {output_path}")


if __name__ == "__main__":
    results = asyncio.run(main()) if 'asyncio' in sys.modules else main()
    print("\n🎉 Schema analysis completed! Check test_output/schema_analysis/ for results.")