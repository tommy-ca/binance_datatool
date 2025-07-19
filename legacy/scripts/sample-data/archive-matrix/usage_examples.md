# Binance Archive Usage Examples

This guide provides practical examples for accessing and working with the Binance public archive data.

## Prerequisites

```bash
# Install s5cmd (recommended for bulk operations)
go install github.com/peak/s5cmd/v2@latest

# Or use AWS CLI
pip install awscli
```

## Basic Exploration Commands

### List Market Types
```bash
s5cmd --no-sign-request ls s3://data.binance.vision/data/
```

### Explore Spot Market Structure
```bash
# List partition types
s5cmd --no-sign-request ls s3://data.binance.vision/data/spot/

# List data types
s5cmd --no-sign-request ls s3://data.binance.vision/data/spot/daily/

# List available intervals for klines
s5cmd --no-sign-request ls s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/
```

### Explore Futures Market Structure
```bash
# USD-margined futures data types
s5cmd --no-sign-request ls s3://data.binance.vision/data/futures/um/daily/

# Coin-margined futures data types  
s5cmd --no-sign-request ls s3://data.binance.vision/data/futures/cm/daily/

# Check available symbols
s5cmd --no-sign-request ls s3://data.binance.vision/data/futures/um/daily/klines/ | head -20
```

## Data Download Examples

### Download Single Day of BTCUSDT 1-minute Data
```bash
# Spot market
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip" \
  ./btc_spot_1m_20230101.zip

# USD-margined futures
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip" \
  ./btc_futures_um_1m_20230101.zip

# Coin-margined futures  
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/cm/daily/klines/BTCUSD_PERP/1m/BTCUSD_PERP-1m-2023-01-01.zip" \
  ./btc_futures_cm_1m_20230101.zip
```

### Download Monthly Data
```bash
# Download entire month of BTCUSDT 1-minute data
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01.zip" \
  ./btc_spot_1m_202301.zip
```

### Download Multiple Symbols
```bash
# Download BTCUSDT and ETHUSDT for same day
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip" \
  "s3://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2023-01-01.zip" \
  ./
```

### Download Date Range
```bash
# Download entire week of data (Jan 1-7, 2023)
for date in 2023-01-01 2023-01-02 2023-01-03 2023-01-04 2023-01-05 2023-01-06 2023-01-07; do
  s5cmd --no-sign-request cp \
    "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-${date}.zip" \
    ./btc_week/
done
```

## Futures-Specific Data Examples

### Download Funding Rate Data
```bash
# Download monthly funding rates for BTCUSDT
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2023-01.zip" \
  ./btc_funding_202301.zip
```

### Download Order Book Depth Data
```bash
# Download daily book depth snapshots
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2023-01-01.zip" \
  ./btc_bookdepth_20230101.zip
```

### Download Mark Price Data
```bash
# Download mark price klines
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/markPriceKlines/BTCUSDT/1m/BTCUSDT-markPriceKlines-1m-2023-01-01.zip" \
  ./btc_markprice_1m_20230101.zip
```

## Bulk Download Strategies

### Download All Intervals for One Symbol
```bash
# Create directory structure
mkdir -p btcusdt_data/{1m,5m,1h,1d}

# Download multiple intervals
intervals=("1m" "5m" "1h" "1d")
for interval in "${intervals[@]}"; do
  s5cmd --no-sign-request cp \
    "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/${interval}/BTCUSDT-${interval}-2023-01-01.zip" \
    "./btcusdt_data/${interval}/"
done
```

### Sync Entire Directory
```bash
# Sync all 1-minute spot data for BTCUSDT (WARNING: Large download)
s5cmd --no-sign-request sync \
  "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/" \
  "./btcusdt_1m_all/"
```

## Data Processing Examples

### Extract and Process ZIP Files
```bash
# Extract downloaded data
unzip BTCUSDT-1m-2023-01-01.zip

# Process CSV with common tools
head -5 BTCUSDT-1m-2023-01-01.csv
wc -l BTCUSDT-1m-2023-01-01.csv
```

### Verify Data Integrity
```bash
# Download checksum file
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip.CHECKSUM" \
  ./

# Verify checksum (Linux/Mac)
sha256sum -c BTCUSDT-1m-2023-01-01.zip.CHECKSUM
```

## Advanced Use Cases

### Multi-Market Data Collection
```bash
#!/bin/bash
# Script to download same symbol across all markets

SYMBOL_BASE="BTC"
DATE="2023-01-01"

# Spot
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/spot/daily/klines/${SYMBOL_BASE}USDT/1m/${SYMBOL_BASE}USDT-1m-${DATE}.zip" \
  ./multimarket/spot/

# USD-margined futures  
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/klines/${SYMBOL_BASE}USDT/1m/${SYMBOL_BASE}USDT-1m-${DATE}.zip" \
  ./multimarket/futures_um/

# Coin-margined futures
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/cm/daily/klines/${SYMBOL_BASE}USD_PERP/1m/${SYMBOL_BASE}USD_PERP-1m-${DATE}.zip" \
  ./multimarket/futures_cm/
```

### High-Frequency Data Collection
```bash
# Download high-frequency futures data
mkdir -p hf_data/{klines,trades,bookdepth}

# 1-minute klines
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip" \
  ./hf_data/klines/

# Raw trades
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/BTCUSDT-trades-2023-01-01.zip" \
  ./hf_data/trades/

# Order book depth
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2023-01-01.zip" \
  ./hf_data/bookdepth/
```

## AWS CLI Alternative Examples

```bash
# List using AWS CLI
aws s3 ls s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/ --no-sign-request

# Download using AWS CLI
aws s3 cp s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2023-01-01.zip . --no-sign-request

# Sync directory using AWS CLI
aws s3 sync s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1d/ ./btc_daily/ --no-sign-request
```

## Data Format Information

### Klines CSV Format
The klines data contains the following columns:
1. Open time (timestamp)
2. Open price
3. High price  
4. Low price
5. Close price
6. Volume
7. Close time (timestamp)
8. Quote asset volume
9. Number of trades
10. Taker buy base asset volume
11. Taker buy quote asset volume
12. Ignore (unused field)

### Trades CSV Format
The trades data contains:
1. Trade ID
2. Price
3. Quantity
4. Quote quantity
5. Time (timestamp)
6. Is buyer maker (boolean)
7. Is best match (boolean)

## Performance Tips

1. **Use s5cmd for bulk operations** - Much faster than AWS CLI for multiple files
2. **Download monthly files for historical analysis** - Reduces number of API calls
3. **Use parallel downloads** - s5cmd supports concurrent operations
4. **Verify checksums for critical data** - Ensure data integrity
5. **Consider storage costs** - Downloads incur S3 egress charges
6. **Use appropriate intervals** - Don't download 1-second data if you need hourly analysis

## Common Patterns

### Research Workflow
```bash
# 1. Explore available data
s5cmd --no-sign-request ls s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/

# 2. Download sample data
s5cmd --no-sign-request cp \
  "s3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1h/BTCUSDT-1h-2023-01-01.zip" \
  ./sample.zip

# 3. Extract and examine
unzip sample.zip && head sample.csv

# 4. Download full dataset if satisfied
s5cmd --no-sign-request sync \
  "s3://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1h/" \
  ./btc_hourly_full/
```

This guide provides a comprehensive starting point for working with the Binance public archive. Adjust paths, symbols, and dates according to your specific research needs.