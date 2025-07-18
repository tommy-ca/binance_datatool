# Crypto Data Lakehouse: Technical Specification

## 1. Overview & Vision

### 1.1. Vision

To create a robust, scalable, and extensible data platform that systematically ingests, processes, and serves historical and real-time cryptocurrency market data. The platform will serve as a foundational "data lakehouse," providing clean, reliable, and queryable data for quantitative research, algorithmic trading, and data analysis.

### 1.2. Target Users

*   **Quantitative Researchers:** Need access to large historical datasets for backtesting trading strategies.
*   **Data Analysts:** Require clean, structured data to perform market analysis and generate insights.
*   **Machine Learning Engineers:** Need feature-rich datasets to train predictive models.
*   **Algorithmic Traders:** Require low-latency access to recent data for live trading signals.

---

## 2. Requirements

### 2.1. Functional Requirements

*   **F1: Multi-Source Data Ingestion:**
    *   **F1.1 (Bulk Ingestion):** System must efficiently download bulk historical data archives from Binance's S3 repository.
    *   **F1.2 (Incremental Ingestion):** System must fetch recent or missing data points via REST APIs to ensure data completeness.
    *   **F1.3 (Extensibility):** The architecture must be designed to easily add new exchanges (e.g., Coinbase, Kraken) with minimal code changes.

*   **F2: Supported Data Types:**
    *   **F2.1:** K-Lines/OHLCV (at various intervals: 1m, 5m, 1h, 1d).
    *   **F2.2:** Funding Rates (for perpetual futures).
    *   **F2.3:** Forced Liquidations.
    *   **F2.4 (Future):** Order Book Snapshots, Tick-level Trade Data.

*   **F3: Data Processing & Transformation:**
    *   **F3.1 (Parsing & Typing):** Raw data must be parsed into a strongly-typed, structured format.
    *   **F3.2 (Merging):** System must intelligently merge data from bulk and incremental sources.
    *   **F3.3 (Data Enrichment):** System must compute and append value-added features (e.g., VWAP).
    *   **F3.4 (Gap Handling):** System must automatically detect and handle time-based gaps in the data.
    *   **F3.5 (Resampling):** Provide tools to resample data from a base interval to higher timeframes.

*   **F4: Data Storage & Management:**
    *   **F4.1 (Layered Storage):** Data must be stored in a layered S3-based data lake (Bronze/Raw, Silver/Processed, Gold/Aggregated).
    *   **F4.2 (Optimized Format):** Processed data must be stored in partitioned Apache Parquet format.
    *   **F4.3 (Data Catalog):** A central data catalog (AWS Glue) must manage schemas and make data discoverable.

*   **F5: Orchestration & Operations:**
    *   **F5.1 (Workflow Management):** All data pipelines must be defined and managed in a workflow engine, handling dependencies, scheduling, and retries.
    *   **F5.2 (Idempotency):** All pipeline tasks must be idempotent.
    *   **F5.3 (Monitoring & Alerting):** The system must provide robust logging, monitoring, and alerting.

### 2.2. Non-Functional Requirements

*   **NFR1 (Scalability):** The system must scale horizontally to handle terabytes of data.
*   **NFR2 (Reliability):** Data must be accurate and complete; pipelines must be fault-tolerant.
*   **NFR3 (Performance):** High-throughput ingestion and low-latency query times.
*   **NFR4 (Maintainability):** The codebase must be modular, well-tested, and well-documented.

---

## 3. System Architecture & Design

### 3.1. The Layered Data Lakehouse Architecture

The architecture is a layered lakehouse, providing a clear separation of concerns and facilitating scalability and data governance.

*   **Layer 1: Ingestion:** The entry point for all external data, responsible for fetching data and landing it in the raw zone of the data lake.
*   **Layer 2: Storage (S3 Data Lake):** The core storage foundation, organized into zones:
    *   **Bronze Zone (Raw):** Stores data in its original, unaltered format.
    *   **Silver Zone (Processed):** Stores cleaned, merged, and structured data in partitioned Parquet.
    *   **Gold Zone (Aggregated):** Stores business-level aggregations or feature-engineered datasets.
*   **Layer 3: Processing & Orchestration:** A workflow engine triggers and manages containerized processing jobs that transform data between the lakehouse layers.
*   **Layer 4: Query & Access:** A query engine provides SQL access over the lakehouse, and a Python SDK provides programmatic access.

### 3.2. Component Breakdown

*   **Workflow Engine (e.g., Prefect, Dagster):** Replaces shell scripts to manage data pipelines with a UI, dependency management, scheduling, and retries. Workflows will be defined in Python.
*   **Bulk Ingestor (`s5cmd`):** A high-performance, parallelized S3 client for efficiently downloading bulk historical data archives from sources like the Binance Data Vision repository.
*   **Incremental Ingestor (`ccxt`):** A unified REST API client for fetching recent data from over 100 crypto exchanges, abstracting away exchange-specific implementations.
*   **Data Transformation (Polars & AWS Fargate):** Data processing jobs will use the high-performance Polars DataFrame library. These jobs will be packaged as Docker containers and run on AWS Fargate for scalable, serverless compute.
*   **Data Catalog (AWS Glue Catalog):** A central Hive-compatible metastore that allows query engines to treat Parquet files in S3 as queryable database tables.
*   **Query Engine (DuckDB & Trino):**
    *   **DuckDB:** For fast, in-process analytical queries directly on Parquet files within a Python environment.
    *   **Trino:** A distributed SQL query engine for large-scale, federated queries across the entire data lake.

---

## 4. Core Technologies (Tech Stack)

| Category | Technology | Justification |
| :--- | :--- | :--- |
| **Cloud Provider** | AWS | Mature, integrated services for a lakehouse architecture. |
| **Orchestration** | **Prefect** or **Dagster** | Modern, Python-native workflow engines with excellent developer experience. |
| **Infrastructure** | **Terraform** / **OpenTofu** | Standard for Infrastructure as Code (IaC). |
| **Storage** | **AWS S3** | De-facto standard for data lakes. |
| **Data Catalog** | **AWS Glue Data Catalog** | Managed Hive Metastore for S3 data. |
| **Bulk Transfer** | **s5cmd** | Superior performance for mass S3 object transfers. |
| **API Client** | **ccxt** | Industry standard for crypto exchange APIs. |
| **Processing Core** | **Polars** (Python) | High-performance DataFrame library for ETL. |
| **Compute** | **AWS Fargate** | Scalable, cost-efficient, serverless container execution. |
| **Querying** | **DuckDB** & **Trino** | Best-in-class for in-process and distributed querying on Parquet. |
| **Containerization**| **Docker** | Standard for packaging applications and dependencies. |

---

## 5. Implementation Roadmap

### Phase 1: Foundation & Core Ingestion (MVP)
*   [ ] **Task 1 (Infra):** Provision core AWS infrastructure (S3, IAM) using Terraform.
*   [ ] **Task 2 (Orchestration):** Set up a Prefect/Dagster project.
*   [ ] **Task 3 (Pipeline):** Create the first workflow for `spot_kline_1m` data, implementing bulk (`s5cmd`) and incremental (`ccxt`) download tasks.
*   [ ] **Task 4 (Processing):** Create a containerized Polars job to parse data and write to the Silver zone as partitioned Parquet.
*   [ ] **Task 5 (Catalog):** Integrate the processing job with AWS Glue Catalog.
*   [ ] **Task 6 (Access):** Validate the end-to-end pipeline by querying Silver data with DuckDB.

### Phase 2: Expansion & Enrichment
*   [ ] **Task 7 (Data):** Extend pipelines to support all other required data types (Funding Rates, Futures K-lines).
*   [ ] **Task 8 (Enrichment):** Add processing steps for merging data sources and calculating VWAP.
*   [ ] **Task 9 (SDK):** Develop a basic Python SDK for easy data access.
*   [ ] **Task 10 (QA):** Implement data quality checks within the workflows.

### Phase 3: Productionization & Scaling
*   [ ] **Task 11 (CI/CD):** Set up a CI/CD pipeline (e.g., GitHub Actions) for automated testing and deployment.
*   [ ] **Task 12 (Monitoring):** Configure comprehensive monitoring and alerting.
*   [ ] **Task 13 (Query):** Deploy a Trino cluster for large-scale SQL access.
*   [ ] **Task 14 (Security):** Refine IAM policies and security best practices.

### Phase 4: Future Enhancements
*   [ ] **Task 15 (Extensibility):** Onboard a second exchange to validate the multi-exchange design.
*   [ ] **Task 16 (Features):** Add more complex feature engineering jobs.
*   [ ] **Task 17 (UI):** Explore building a simple data exploration UI.
