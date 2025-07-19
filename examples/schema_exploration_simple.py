#!/usr/bin/env python3
"""
Simple script to download samples of each Binance data type and analyze schemas.

This script downloads small samples directly using s5cmd to analyze data structures.
"""

import asyncio
import csv
import json
import logging
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd

# Add parent directory to path
sys.path.append('.')


def run_s5cmd(command: List[str]) -> subprocess.CompletedProcess:
    """Run s5cmd command safely."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120
        )
        return result
    except subprocess.TimeoutExpired:
        raise Exception("s5cmd command timed out")


def download_sample_file(url: str, output_path: Path) -> bool:
    """Download a single sample file using s5cmd."""
    logger = logging.getLogger(__name__)
    
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use s5cmd to download
        cmd = ["s5cmd", "cp", url, str(output_path)]
        result = run_s5cmd(cmd)
        
        if result.returncode == 0:
            logger.info(f"✅ Downloaded: {output_path.name}")
            return True
        else:
            logger.warning(f"❌ Failed to download {url}: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error downloading {url}: {e}")
        return False


def analyze_csv_schema(csv_path: Path) -> Dict[str, Any]:
    """Analyze schema of CSV file."""
    logger = logging.getLogger(__name__)
    
    try:
        # Read first few rows to determine structure
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = [next(reader) for _ in range(min(5, sum(1 for _ in f) + 1))]
        
        if not rows:
            return {"error": "Empty file"}
        
        # Analyze structure
        first_row = rows[0]
        sample_data = rows[1:] if len(rows) > 1 else []
        
        schema = {
            "file_format": "CSV",
            "column_count": len(first_row),
            "has_header": False,  # Binance data typically has no headers
            "sample_rows": len(sample_data),
            "columns": []
        }
        
        # Try to determine column types from sample data
        for i, col_name in enumerate([f"col_{j}" for j in range(len(first_row))]):
            col_info = {
                "position": i,
                "name": col_name,
                "sample_values": []
            }
            
            # Collect sample values
            for row in sample_data:
                if i < len(row):
                    col_info["sample_values"].append(row[i])
            
            # Try to infer type
            if col_info["sample_values"]:
                sample_val = col_info["sample_values"][0]
                try:
                    float(sample_val)
                    col_info["inferred_type"] = "numeric"
                except ValueError:
                    try:
                        int(sample_val)
                        col_info["inferred_type"] = "integer"
                    except ValueError:
                        col_info["inferred_type"] = "string"
            else:
                col_info["inferred_type"] = "unknown"
            
            schema["columns"].append(col_info)
        
        return schema
        
    except Exception as e:
        logger.error(f"Error analyzing CSV {csv_path}: {e}")
        return {"error": str(e)}


def extract_and_analyze_zip(zip_path: Path) -> Dict[str, Any]:
    """Extract ZIP file and analyze its contents."""
    logger = logging.getLogger(__name__)
    
    try:
        # Extract to temporary directory
        extract_dir = zip_path.parent / f"{zip_path.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find CSV file(s) in extracted content
        csv_files = list(extract_dir.glob("*.csv"))
        
        if not csv_files:
            return {"error": "No CSV files found in ZIP"}
        
        # Analyze the first CSV file
        csv_file = csv_files[0]
        schema = analyze_csv_schema(csv_file)
        
        # Add ZIP-specific info
        schema["zip_info"] = {
            "compressed_size": zip_path.stat().st_size,
            "extracted_files": [f.name for f in csv_files],
            "extraction_path": str(extract_dir)
        }
        
        return schema
        
    except Exception as e:
        logger.error(f"Error extracting/analyzing ZIP {zip_path}: {e}")
        return {"error": str(e)}


async def download_and_analyze_data_type(market: str, data_type: str, symbol: str, date: str = "2025-07-15") -> Dict[str, Any]:
    """Download and analyze a specific data type."""
    logger = logging.getLogger(__name__)
    
    # URL patterns based on Binance structure
    url_patterns = {
        "spot": "s3://data.binance.vision/data/spot/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date}.zip",
        "futures_um": "s3://data.binance.vision/data/futures/um/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date}.zip",
        "futures_cm": "s3://data.binance.vision/data/futures/cm/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date}.zip"
    }
    
    if market not in url_patterns:
        return {"error": f"Unknown market: {market}"}
    
    # Special handling for klines - need to specify interval
    if data_type == "klines":
        url = url_patterns[market].format(
            data_type="klines",
            symbol=symbol,
            date=date
        ).replace("/klines/", "/klines/1h/")  # Use 1h interval
        interval = "1h"
    else:
        url = url_patterns[market].format(
            data_type=data_type,
            symbol=symbol,
            date=date
        )
        interval = None
    
    # Output path
    output_dir = Path(f"test_output/schema_samples/{market}_{data_type}")
    filename = f"{symbol}-{data_type}-{date}.zip"
    if interval:
        filename = f"{symbol}-{interval}-{date}.zip"
    output_path = output_dir / filename
    
    logger.info(f"🔍 Analyzing {market} {data_type} ({symbol})")
    logger.info(f"   URL: {url}")
    
    # Download sample
    success = download_sample_file(url, output_path)
    
    if not success:
        return {
            "market": market,
            "data_type": data_type,
            "symbol": symbol,
            "date": date,
            "download_success": False,
            "url": url,
            "error": "Download failed"
        }
    
    # Analyze downloaded file
    schema = extract_and_analyze_zip(output_path)
    
    return {
        "market": market,
        "data_type": data_type,
        "symbol": symbol,
        "date": date,
        "interval": interval,
        "download_success": True,
        "url": url,
        "local_path": str(output_path),
        "schema": schema
    }


async def main():
    """Main function to explore all data types."""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Binance Data Type Schema Exploration")
    logger.info("=" * 80)
    
    # Define data types to explore
    data_types_to_explore = [
        ("spot", "klines", "BTCUSDT"),
        ("spot", "trades", "BTCUSDT"),
        ("futures", "klines", "BTCUSDT"),  # Will map to futures_um
        ("futures", "trades", "BTCUSDT"),
        ("futures", "fundingRate", "BTCUSDT"),
    ]
    
    all_results = []
    
    for market, data_type, symbol in data_types_to_explore:
        # Map futures to futures_um for URL generation
        url_market = "futures_um" if market == "futures" else market
        
        try:
            result = await download_and_analyze_data_type(url_market, data_type, symbol)
            all_results.append(result)
            
            if result["download_success"]:
                logger.info(f"✅ {market} {data_type}: Schema analyzed")
            else:
                logger.warning(f"❌ {market} {data_type}: {result.get('error', 'Failed')}")
                
        except Exception as e:
            logger.error(f"❌ {market} {data_type}: Exception: {e}")
            all_results.append({
                "market": market,
                "data_type": data_type,
                "symbol": symbol,
                "download_success": False,
                "error": str(e)
            })
        
        # Small delay between downloads
        await asyncio.sleep(1)
    
    # Save comprehensive results
    results_path = Path("test_output/schema_samples/schema_analysis_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    logger.info("=" * 80)
    logger.info(f"📝 Results saved to: {results_path}")
    
    # Generate summary report
    generate_schema_report(all_results, results_path.parent / "BINANCE_DATA_SCHEMAS.md")
    
    return all_results


def generate_schema_report(results: List[Dict], output_path: Path):
    """Generate a comprehensive schema documentation report."""
    
    with open(output_path, 'w') as f:
        f.write("# Binance Public Archive Data Schemas\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("This document provides comprehensive schemas for all Binance public archive data types.\n\n")
        
        f.write("## Summary\n\n")
        f.write("| Market | Data Type | Symbol | Status | Columns | Format |\n")
        f.write("|--------|-----------|--------|--------|---------|--------|\n")
        
        for result in results:
            status = "✅ Success" if result.get("download_success") else "❌ Failed"
            columns = len(result.get("schema", {}).get("columns", [])) if result.get("schema") else "N/A"
            format_info = result.get("schema", {}).get("file_format", "N/A")
            
            f.write(f"| {result['market']} | {result['data_type']} | {result['symbol']} | {status} | {columns} | {format_info} |\n")
        
        f.write("\n## Detailed Schemas\n\n")
        
        for result in results:
            if not result.get("download_success"):
                continue
                
            market = result['market']
            data_type = result['data_type']
            
            f.write(f"### {market.title()} - {data_type.title()}\n\n")
            f.write(f"**Symbol**: {result['symbol']}\n")
            f.write(f"**Sample Date**: {result['date']}\n")
            if result.get('interval'):
                f.write(f"**Interval**: {result['interval']}\n")
            f.write(f"**Download URL**: `{result['url']}`\n\n")
            
            schema = result.get('schema', {})
            if 'error' in schema:
                f.write(f"**Error**: {schema['error']}\n\n")
                continue
            
            f.write(f"**File Format**: {schema.get('file_format', 'Unknown')}\n")
            f.write(f"**Column Count**: {schema.get('column_count', 'Unknown')}\n")
            f.write(f"**Sample Rows**: {schema.get('sample_rows', 'Unknown')}\n\n")
            
            if 'zip_info' in schema:
                zip_info = schema['zip_info']
                f.write(f"**Compressed Size**: {zip_info.get('compressed_size', 'Unknown')} bytes\n")
                f.write(f"**Extracted Files**: {', '.join(zip_info.get('extracted_files', []))}\n\n")
            
            # Column details
            f.write("#### Column Schema\n\n")
            f.write("| Position | Name | Type | Sample Values |\n")
            f.write("|----------|------|------|---------------|\n")
            
            for col in schema.get('columns', []):
                sample_vals = ', '.join(str(v) for v in col.get('sample_values', [])[:3])
                f.write(f"| {col.get('position', 'N/A')} | {col.get('name', 'N/A')} | {col.get('inferred_type', 'N/A')} | {sample_vals} |\n")
            
            f.write("\n")
        
        f.write("## Notes\n\n")
        f.write("- All timestamps are in milliseconds since Unix epoch\n")
        f.write("- Numeric values are provided as strings in CSV format\n")
        f.write("- Files are compressed in ZIP format with CSV content\n")
        f.write("- Data availability varies by symbol and date range\n")
        f.write("- Some recent data may not be available immediately\n\n")
    
    logging.getLogger(__name__).info(f"📋 Schema documentation saved to: {output_path}")


if __name__ == "__main__":
    results = asyncio.run(main())
    print(f"\nExploration completed! Check test_output/schema_samples/ for results.")