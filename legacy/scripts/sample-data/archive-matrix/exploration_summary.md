# Binance Public Archive Exploration Summary

**Date:** 2025-01-19  
**Archive URL:** s3://data.binance.vision/data/  
**Tool Used:** s5cmd for S3 exploration

## Archive Structure Overview

The Binance public archive follows a hierarchical structure with three main market types:

```
s3://data.binance.vision/data/
├── spot/          # Spot trading data
├── futures/       # Futures trading data
│   ├── um/        # USD-margined futures
│   └── cm/        # Coin-margined futures
└── option/        # Options data (limited)
```

## Market Type Analysis

### 1. Spot Market (`spot/`)
- **Partition Types:** daily, monthly
- **Data Types:** klines, trades, aggTrades
- **Key Features:**
  - Comprehensive klines with 13 intervals (1s to 1d)
  - Historical data from 2017-08-17
  - 2000+ active trading symbols
  - Both daily and monthly aggregations available

### 2. USD-Margined Futures (`futures/um/`)
- **Partition Types:** daily, monthly
- **Data Types:** klines, trades, aggTrades, bookDepth, bookTicker, indexPriceKlines, markPriceKlines, premiumIndexKlines, fundingRate, metrics
- **Key Features:**
  - Extended intervals including 3d, 1w, 1mo
  - Futures-specific data: funding rates, premium indices, mark prices
  - 400+ active symbols including perpetual and quarterly contracts
  - High-frequency book depth data (daily only)
  - Historical data from 2019-12-31

### 3. Coin-Margined Futures (`futures/cm/`)
- **Partition Types:** daily, monthly
- **Data Types:** All USD-margined types plus liquidationSnapshot
- **Key Features:**
  - Coin-margined specific features (liquidation snapshots)
  - 50+ active symbols
  - Perpetual (_PERP) and quarterly contracts
  - Historical data from 2020-08-11

### 4. Options (`option/`)
- **Partition Types:** daily only
- **Data Types:** BVOLIndex, EOHSummary
- **Key Features:**
  - Limited to volatility indices (BTCBVOLUSDT, ETHBVOLUSDT)
  - End-of-hour summary data
  - Much smaller dataset compared to spot/futures

## Data Type Breakdown

### Core Trading Data
1. **klines** - OHLCV candlestick data (most comprehensive)
2. **trades** - Individual trade records
3. **aggTrades** - Aggregated trade data

### Futures-Specific Data
4. **bookDepth** - Order book snapshots (high-frequency)
5. **bookTicker** - Best bid/ask prices
6. **fundingRate** - Funding rate history (8-hour intervals)
7. **indexPriceKlines** - Index price movements
8. **markPriceKlines** - Mark price movements
9. **premiumIndexKlines** - Premium calculations
10. **liquidationSnapshot** - Liquidation events (CM only)
11. **metrics** - Market performance metrics

### Options Data
12. **BVOLIndex** - Bitcoin/Ethereum volatility indices
13. **EOHSummary** - End-of-hour summaries

## File Naming Patterns

### Daily Files
- **Pattern:** `{symbol}-{data_type}-{YYYY-MM-DD}.zip`
- **Examples:** 
  - `BTCUSDT-1m-2023-01-01.zip`
  - `ETHUSDT-trades-2023-01-01.zip`

### Monthly Files  
- **Pattern:** `{symbol}-{data_type}-{YYYY-MM}.zip`
- **Examples:**
  - `BTCUSDT-1m-2023-01.zip`
  - `BTCUSDT-fundingRate-2023-01.zip`

### Checksum Files
- Each ZIP file has a corresponding `.CHECKSUM` file for integrity verification

## Symbol Patterns

### Spot
- **Format:** `{BASE}{QUOTE}`
- **Examples:** BTCUSDT, ETHBTC, BNBBUSD

### USD-Margined Futures
- **Perpetual:** `{BASE}{QUOTE}` (e.g., BTCUSDT)
- **Quarterly:** `{BASE}{QUOTE}_{YYMMDD}` (e.g., BTCUSDT_240329)

### Coin-Margined Futures
- **Perpetual:** `{BASE}USD_PERP` (e.g., BTCUSD_PERP)
- **Quarterly:** `{BASE}USD_{YYMMDD}` (e.g., BTCUSD_240329)

## Key Findings

1. **Comprehensive Coverage:** The archive covers all major Binance markets with extensive historical data
2. **Standardized Structure:** Consistent naming conventions and directory structure across all markets
3. **Multiple Granularities:** Both daily and monthly partitions available for most data types
4. **Rich Futures Data:** Futures markets have significantly more data types than spot
5. **High Frequency Data:** Order book depth data available for detailed market microstructure analysis
6. **Quality Assurance:** Checksum files ensure data integrity
7. **Public Access:** No authentication required, standard S3 access methods work

## Data Volume Estimates

- **Daily Files:** 50-500KB per symbol per data type
- **Monthly Files:** 1-50MB per symbol per data type  
- **Total Symbols:** 2500+ across all markets
- **Update Frequency:** Daily, within 24 hours of trading day end

## Access Methods

The archive can be accessed using:
- `s5cmd` (fastest for bulk operations)
- `aws cli` (standard AWS tooling)
- `rclone` (cross-platform sync tool)
- Direct S3 API calls
- Web browser (for individual file access)

## Recommendations for Users

1. **For Backtesting:** Use monthly files for faster downloads of historical data
2. **For Real-time Analysis:** Use daily files for recent data
3. **For Microstructure Research:** Focus on bookDepth data in futures markets
4. **For Multi-market Analysis:** Leverage the standardized structure across markets
5. **For Data Integrity:** Always verify checksums for critical applications

This comprehensive archive provides an excellent foundation for quantitative research, algorithmic trading development, and market analysis across the entire Binance ecosystem.