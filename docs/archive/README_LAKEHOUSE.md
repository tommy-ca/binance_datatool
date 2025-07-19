# Crypto Data Lakehouse v2.0

A modern, scalable data platform for cryptocurrency market data built on data lakehouse principles. This project implements the technical specification outlined in `spec.md` using modern Python tooling and cloud-native architecture.

## 🏗️ Architecture Overview

The Crypto Data Lakehouse follows a layered architecture with clear separation of concerns:

### Data Zones (Lakehouse Pattern)
- **Bronze Zone**: Raw data in original format (CSV/JSON from exchanges)
- **Silver Zone**: Cleaned, validated, and structured data in Parquet format
- **Gold Zone**: Business-ready aggregations and feature-engineered datasets

### Core Components
1. **Ingestion Layer**: Multi-source data acquisition (bulk S3 + incremental API)
2. **Storage Layer**: S3-based lakehouse with local development support
3. **Processing Layer**: Polars-based ETL with containerized execution
4. **Orchestration Layer**: Prefect workflows for dependency management
5. **Query Layer**: DuckDB and Trino for analytics access

## 🚀 Quick Start

### Installation

```bash
# Clone and install
git checkout lakehouse-rewrite
pip install -e .

# Or install with extras
pip install -e ".[dev,aws,orchestration]"
```

### Configuration

```bash
# Set environment variables
export CRYPTO_DATA_DIR="/path/to/data"
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export S3_BUCKET="your-bucket"

# Or create .env file
cp .env.example .env
# Edit .env with your settings
```

### Basic Usage

```bash
# Initialize the lakehouse
crypto-lakehouse admin setup

# Check system status
crypto-lakehouse admin status

# Ingest K-line data
crypto-lakehouse ingest klines --symbols BTCUSDT ETHUSDT --start-date 2024-01-01

# Ingest funding rates
crypto-lakehouse ingest funding-rates --symbols BTCUSDT --trade-type um_futures

# Process data to Silver zone
crypto-lakehouse process transform --data-type klines

# Query data information
crypto-lakehouse query info --exchange binance
```

## 📊 Data Types Supported

### K-Lines (Candlestick Data)
- **Source**: Binance AWS S3 (bulk) + REST API (incremental)
- **Intervals**: 1m, 5m, 15m, 30m, 1h, 4h, 12h, 1d, 1w, 1M
- **Markets**: Spot, USDT-Margined Futures, Coin-Margined Futures
- **Enhanced Features**: VWAP, returns, volatility, technical indicators

### Funding Rates
- **Source**: Binance AWS S3 (bulk) + REST API (incremental)
- **Frequency**: Every 8 hours
- **Markets**: USDT-Margined Futures, Coin-Margined Futures
- **Enhanced Features**: Annualized rates, rolling averages, regime indicators

### Liquidations (Coming Soon)
- **Source**: Binance AWS S3 (bulk only)
- **Markets**: USDT-Margined Futures, Coin-Margined Futures

## 🏛️ Project Structure

```
src/crypto_lakehouse/
├── core/                  # Core models and configuration
│   ├── models.py         # Pydantic data models
│   └── config.py         # Settings and configuration
├── ingestion/            # Data ingestion layer
│   ├── base.py          # Abstract ingestor interfaces
│   ├── binance.py       # Binance-specific implementation
│   └── factory.py       # Ingestor factory
├── storage/              # Storage layer
│   ├── base.py          # Abstract storage interface
│   ├── s3_storage.py    # S3 lakehouse implementation
│   ├── local_storage.py # Local development storage
│   └── factory.py       # Storage factory
├── processing/           # Data processing layer
│   ├── base.py          # Abstract processor interface
│   ├── kline_processor.py    # K-line data processing
│   ├── funding_processor.py  # Funding rate processing
│   └── enrichment.py    # Advanced feature engineering
├── workflows/            # Orchestration layer
│   ├── base.py          # Workflow base classes
│   ├── ingestion_flow.py     # Data ingestion workflows
│   └── processing_flow.py    # Data processing workflows
└── cli.py               # Command-line interface
```

## 🔧 Configuration

The system uses a layered configuration approach:

### Environment Variables
```bash
# Storage
CRYPTO_DATA_DIR="/home/user/crypto_data"
S3_BUCKET="crypto-lakehouse-bucket"
AWS_REGION="us-east-1"

# Processing
CRYPTO_NJOBS=8
PROCESSING_BATCH_SIZE=10000

# Monitoring
LOG_LEVEL="INFO"
ALERT_WEBHOOK_URL="https://hooks.slack.com/..."
```

### Configuration File (.env)
```ini
ENVIRONMENT=production
DEBUG=false

# S3 Configuration
S3__BUCKET_NAME=crypto-lakehouse
S3__REGION=us-east-1

# Workflow Configuration
WORKFLOW__CONCURRENCY_LIMIT=10
WORKFLOW__RETRY_ATTEMPTS=3

# Data Catalog
DATA_CATALOG__ENABLED=true
DATA_CATALOG__DATABASE_NAME=crypto_lakehouse
```

## 🔄 Workflows

### Data Ingestion Workflow

```python
from crypto_lakehouse.core.models import DataIngestionTask
from crypto_lakehouse.workflows import WorkflowRegistry

# Create ingestion task
task = DataIngestionTask(
    exchange=Exchange.BINANCE,
    data_type=DataType.KLINES,
    trade_type=TradeType.SPOT,
    symbols=["BTCUSDT", "ETHUSDT"],
    interval=Interval.MIN_1,
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

# Execute workflow
workflow = WorkflowRegistry.get_workflow("ingestion", settings)
result = await workflow.execute(task=task)
```

### Data Processing Workflow

```python
from crypto_lakehouse.workflows import processing_flow

# Process data from Bronze to Silver
result = await processing_flow(
    exchange=Exchange.BINANCE,
    data_type=DataType.KLINES,
    trade_type=TradeType.SPOT,
    symbols=["BTCUSDT"],
    start_date=datetime(2024, 1, 1)
)
```

## 📈 Data Access

### Using Polars (Direct)

```python
from crypto_lakehouse.storage.factory import create_storage
from crypto_lakehouse.core.config import settings

storage = create_storage(settings)

# Read Silver zone data
data = await storage.read_data(
    zone=DataZone.SILVER,
    exchange=Exchange.BINANCE,
    data_type=DataType.KLINES,
    trade_type=TradeType.SPOT,
    symbols=["BTCUSDT"],
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 1, 31)
)

print(f"Loaded {len(data)} records")
print(data.head())
```

### Using DuckDB (SQL)

```python
import duckdb

# Connect to lakehouse data
conn = duckdb.connect()

# Query Parquet files directly
query = """
SELECT 
    symbol,
    DATE_TRUNC('day', open_time) as date,
    AVG(close_price) as avg_price,
    SUM(volume) as total_volume
FROM 's3://bucket/silver/binance/spot/klines/**/*.parquet'
WHERE symbol = 'BTCUSDT'
GROUP BY symbol, date
ORDER BY date DESC
LIMIT 30
"""

result = conn.execute(query).fetchdf()
print(result)
```

## 🛠️ Development

### Local Development Setup

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Code formatting
black src/
ruff check src/

# Type checking
mypy src/
```

### Adding New Exchanges

1. Create exchange-specific ingestor in `ingestion/`
2. Implement `BaseIngestor` interface
3. Add to `ingestion/factory.py`
4. Update CLI with new exchange option

### Adding New Data Types

1. Add data type to `core/models.py`
2. Create processor in `processing/`
3. Update ingestion and storage layers
4. Add CLI commands

## 🚀 Deployment

### Local Development
- Uses local filesystem storage
- Prefect server for workflow management
- DuckDB for analytics queries

### Cloud Production
- S3 for data lakehouse storage
- AWS Glue for data catalog
- Prefect Cloud for orchestration
- Trino for distributed queries
- AWS Fargate for processing containers

### Infrastructure as Code

```bash
# Deploy AWS infrastructure
cd terraform/
terraform init
terraform plan
terraform apply
```

## 📊 Monitoring & Observability

### Metrics
- Data ingestion rates and volumes
- Processing job success/failure rates
- Storage utilization and costs
- Query performance metrics

### Alerting
- Failed ingestion jobs
- Data quality issues
- Storage quota exceeded
- Processing job delays

### Logging
- Structured logging with JSON format
- Log aggregation in CloudWatch/ELK
- Distributed tracing with OpenTelemetry

## 🔒 Security

### Access Control
- IAM roles for AWS resource access
- Service accounts for processing jobs
- API key management for exchanges

### Data Protection
- Encryption at rest (S3 SSE)
- Encryption in transit (TLS)
- No sensitive data in logs
- Secure secret management

## 📈 Performance

### Benchmarks (Local Development)
- **Ingestion**: 50,000 records/minute
- **Processing**: 100,000 records/minute  
- **Storage**: 500MB/s write throughput
- **Query**: Sub-second response for aggregations

### Optimization
- Partitioned storage by date and symbol
- Columnar Parquet format with compression
- Parallel processing with Polars
- Efficient data schemas with proper types

## 🗺️ Roadmap

### Phase 1: Foundation (✅ Completed)
- [x] Core lakehouse architecture
- [x] Binance ingestion (bulk + incremental)
- [x] Local and S3 storage
- [x] Basic data processing
- [x] CLI interface

### Phase 2: Enhancement (In Progress)
- [ ] Additional exchanges (Coinbase, Kraken)
- [ ] Order book data ingestion
- [ ] Real-time streaming ingestion
- [ ] Advanced technical indicators
- [ ] Data quality monitoring

### Phase 3: Scale (Planned)
- [ ] Trino deployment for large-scale queries
- [ ] Multi-region replication
- [ ] Cost optimization
- [ ] Performance tuning
- [ ] ML feature store integration

## 📚 Documentation

- [Technical Specification](spec.md) - Detailed requirements and design
- [API Reference](docs/api.md) - Complete API documentation
- [User Guide](docs/user-guide.md) - Step-by-step usage examples
- [Operations Manual](docs/operations.md) - Deployment and maintenance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built with ❤️ for the crypto community**

- **Framework**: Python 3.12+ with modern async/await
- **Data Processing**: Polars for high-performance analytics
- **Storage**: Apache Parquet with S3 lakehouse pattern
- **Orchestration**: Prefect for reliable workflow management
- **Interface**: Rich CLI with typer and modern UX