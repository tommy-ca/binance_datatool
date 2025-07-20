# S3 Direct Sync Architecture

## Overview

This document provides a comprehensive architectural overview of the S3 to S3 direct sync functionality, including system design, component interactions, data flow patterns, and integration points.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Component Architecture](#component-architecture)
3. [Data Flow Patterns](#data-flow-patterns)
4. [Integration Architecture](#integration-architecture)
5. [Performance Architecture](#performance-architecture)
6. [Security Architecture](#security-architecture)
7. [Deployment Architecture](#deployment-architecture)

## System Architecture

### High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        S3 Direct Sync System Architecture                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Control Plane (Orchestration)                      │ │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │ │
│  │  │ Prefect Flow    │    │ Config Manager  │    │ Metrics Collector   │  │ │
│  │  │ Orchestration   │    │ & Validation    │    │ & Monitoring        │  │ │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                        Data Plane (Transfer Operations)                 │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │              EnhancedBulkDownloader (Router)                        │ │ │
│  │  │                    ┌─────────────────┐                             │ │ │
│  │  │                    │ Mode Selection  │                             │ │ │
│  │  │                    │ & Coordination  │                             │ │ │
│  │  │                    └─────────────────┘                             │ │ │
│  │  └─────────────────────┬─────────────────────┬─────────────────────────┘ │ │
│  │                        │                     │                         │ │ │
│  │  ┌─────────────────────▼─────────────────────▼─────────────────────────┐ │ │
│  │  │              Direct Sync Path    │    Traditional Path              │ │ │
│  │  │  ┌─────────────────────────────┐ │ ┌─────────────────────────────────┐ │ │
│  │  │  │  S3DirectSyncDownloader     │ │ │   TraditionalBulkDownloader     │ │ │
│  │  │  │                             │ │ │                                 │ │ │
│  │  │  │  ┌─────────────────────────┐│ │ │ ┌─────────────────────────────────┐│ │ │
│  │  │  │  │     s5cmd Integration   ││ │ │ │    HTTP Download + S3 Upload    ││ │ │
│  │  │  │  │   (Batch Processing)    ││ │ │ │       (Local Storage)           ││ │ │
│  │  │  │  └─────────────────────────┘│ │ │ └─────────────────────────────────┘│ │ │
│  │  │  └─────────────────────────────┘ │ └─────────────────────────────────────┘ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                      Storage Plane (S3 Infrastructure)                  │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐     Direct Transfer     ┌─────────────────────────┐ │ │
│  │  │   Source S3     │ ═══════════════════════> │  Destination S3         │ │ │
│  │  │  (Binance       │      (s5cmd)             │  (Crypto Lakehouse)     │ │ │
│  │  │   Archive)      │                          │                         │ │ │
│  │  └─────────────────┘                          └─────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Architecture Principles

#### 1. Layered Architecture
- **Control Plane**: Orchestration, configuration, and monitoring
- **Data Plane**: Transfer operations and routing logic
- **Storage Plane**: S3 infrastructure and data storage

#### 2. Hybrid Design Pattern
- **Dual-mode operation**: Direct sync and traditional fallback
- **Intelligent routing**: Automatic mode selection based on conditions
- **Graceful degradation**: Seamless fallback without user intervention

#### 3. Performance-First Design
- **Parallel processing**: Multiple concurrent transfers
- **Optimized batching**: Efficient operation grouping
- **Resource optimization**: Memory and network efficiency

#### 4. Reliability-Focused
- **Comprehensive error handling**: Multiple retry strategies
- **Fallback mechanisms**: Automatic mode switching
- **Data integrity**: Transfer validation and verification

## Component Architecture

### Core Components Detailed View

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Component Interaction Diagram                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     Enhanced Archive Collection Flow                    │ │
│  │                         (Prefect @flow)                                │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │Config       │  │Task         │  │Enhanced     │  │Metrics          │ │ │
│  │  │Validation   │  │Generation   │  │Execution    │  │Collection       │ │ │
│  │  │@task        │  │@task        │  │@task        │  │@task            │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │ │
│  └─────────────────────────┬───────────────────────────────────────────────┘ │
│                            │                                                 │
│  ┌─────────────────────────▼───────────────────────────────────────────────┐ │
│  │                   EnhancedBulkDownloader                                │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │                     Mode Selection Logic                            │ │ │
│  │  │                                                                     │ │ │
│  │  │  def _can_use_direct_sync(download_tasks) -> bool:                 │ │ │
│  │  │    1. Check S3DirectSyncDownloader availability                    │ │ │
│  │  │    2. Validate all source URLs are S3 format                      │ │ │
│  │  │    3. Verify destination bucket configuration                      │ │ │
│  │  │    4. Confirm s5cmd tool availability (optional)                  │ │ │
│  │  │    5. Check operation mode settings                               │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  │                            │                                             │ │
│  │                            ▼                                             │ │
│  │  ┌──────────────────┐                        ┌──────────────────────────┐ │ │
│  │  │                  │                        │                          │ │ │
│  │  │ Direct Sync Path │                        │   Traditional Path       │ │ │
│  │  │                  │                        │                          │ │ │
│  │  └──────────────────┘                        └──────────────────────────┘ │ │
│  └─────────────────────┬───────────────────────────────┬─────────────────────┘ │
│                        │                               │                       │
│  ┌─────────────────────▼─────────────────┐  ┌─────────▼─────────────────────────┐ │
│  │        S3DirectSyncDownloader         │  │     TraditionalBulkDownloader      │ │
│  │                                       │  │                                   │ │
│  │  ┌─────────────────────────────────────┐│  │ ┌─────────────────────────────────┐│ │
│  │  │         Core Methods              ││  │ │          Core Methods           ││ │
│  │  │                                   ││  │ │                                 ││ │
│  │  │ • sync_files_direct()             ││  │ │ • download_files_batch()        ││ │
│  │  │ • sync_directory_direct()         ││  │ │ • process_file()                ││ │
│  │  │ • generate_s5cmd_batch_file()     ││  │ │ • upload_to_s3()                ││ │
│  │  │ • execute_s5cmd_batch()           ││  │ │ • cleanup_local_files()         ││ │
│  │  │ • get_efficiency_stats()          ││  │ │ • get_download_stats()          ││ │
│  │  └─────────────────────────────────────┘│  │ └─────────────────────────────────┘│ │
│  │                                       │  │                                   │ │
│  │  ┌─────────────────────────────────────┐│  │ ┌─────────────────────────────────┐│ │
│  │  │       s5cmd Integration           ││  │ │        HTTP/S3 Integration       ││ │
│  │  │                                   ││  │ │                                 ││ │
│  │  │ • Batch file generation           ││  │ │ • HTTP download (requests/wget)  ││ │
│  │  │ • Parallel worker management      ││  │ │ • Local file management         ││ │
│  │  │ • Error handling & retries        ││  │ │ • S3 upload (boto3)             ││ │
│  │  │ • Performance monitoring          ││  │ │ • Checksum validation           ││ │
│  │  └─────────────────────────────────────┘│  │ └─────────────────────────────────┘│ │
│  └───────────────────────────────────────────┘  └───────────────────────────────────┘ │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### 1. EnhancedBulkDownloader (Router Component)

```python
class EnhancedBulkDownloader:
    """
    Primary router component that decides between direct sync and traditional modes.
    
    Responsibilities:
    - Mode selection logic
    - Configuration validation
    - Performance coordination
    - Fallback management
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.traditional_downloader = BulkDownloader(config)
        self.s3_direct_sync = S3DirectSyncDownloader(config) if self._should_enable_direct_sync(config) else None
        self.config = config
        self.stats = {"direct_sync_used": 0, "traditional_used": 0}
    
    def _can_use_direct_sync(self, download_tasks: List[Dict[str, Any]]) -> bool:
        """Intelligent mode selection logic."""
        # Implementation details in specification
        pass
    
    async def download_files_batch(self, download_tasks: List[Dict[str, Any]], prefer_direct_sync: bool = True) -> List[Dict[str, Any]]:
        """Primary routing method."""
        # Route to appropriate downloader based on conditions
        pass
```

#### 2. S3DirectSyncDownloader (Direct Sync Component)

```python
class S3DirectSyncDownloader:
    """
    Core component for S3 to S3 direct transfer operations.
    
    Responsibilities:
    - s5cmd batch file generation
    - Direct S3 transfer execution
    - Performance optimization
    - Efficiency metrics collection
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.destination_bucket = config['destination_bucket']
        self.destination_prefix = config.get('destination_prefix', '')
        self.max_concurrent = config.get('max_concurrent', 10)
        self.batch_size = config.get('batch_size', 100)
        # Additional configuration parameters
    
    async def sync_files_direct(self, source_files: List[Dict[str, str]], organize_by_prefix: bool = True) -> List[Dict[str, Any]]:
        """Primary direct sync method."""
        # Implementation details in specification
        pass
    
    def generate_s5cmd_batch_file(self, source_files: List[Dict[str, str]]) -> str:
        """Generate optimized s5cmd batch commands."""
        # Implementation details in specification
        pass
```

#### 3. Enhanced Archive Collection Flow (Orchestration Component)

```python
@flow(
    name="enhanced-archive-collection-flow",
    task_runner=ConcurrentTaskRunner(),
    retries=1,
    retry_delay_seconds=300
)
async def enhanced_archive_collection_flow(
    config: WorkflowConfig,
    metrics_collector: Optional[MetricsCollector] = None
) -> Dict[str, Any]:
    """
    Primary orchestration flow for archive collection with S3 direct sync.
    
    Flow Steps:
    1. Configuration validation
    2. Task generation with enhanced path logic
    3. Enhanced execution with mode selection
    4. Efficiency analysis and metrics collection
    5. Results persistence and reporting
    """
    # Implementation details in specification
    pass
```

## Data Flow Patterns

### Primary Data Flow (Direct Sync Mode)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Direct Sync Data Flow                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ 1. Configuration & Initialization                                          │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Workflow Config │────▶│ Mode Selection  │────▶│ S3DirectSync Init   │   │
│    │ Validation      │     │ Logic           │     │ & Validation        │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 2. Task Generation & Batching                                              │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Archive Matrix  │────▶│ Download Task   │────▶│ Batch Optimization  │   │
│    │ Analysis        │     │ Generation      │     │ & Grouping          │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 3. s5cmd Batch Preparation                                                 │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Source URL      │────▶│ Target Path     │────▶│ s5cmd Batch File    │   │
│    │ Processing      │     │ Generation      │     │ Creation            │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 4. Direct Transfer Execution                                               │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ s5cmd Batch     │────▶│ Parallel S3     │────▶│ Transfer Validation │   │
│    │ Execution       │     │ to S3 Transfer  │     │ & Verification      │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 5. Results & Metrics Collection                                            │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Transfer        │────▶│ Efficiency      │────▶│ Performance         │   │
│    │ Results         │     │ Calculation     │     │ Reporting           │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Fallback Data Flow (Traditional Mode)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Traditional Fallback Data Flow                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ 1. Fallback Trigger Conditions                                             │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Direct Sync     │────▶│ Condition Check │────▶│ Fallback Decision   │   │
│    │ Validation      │     │ & Evaluation    │     │ & Mode Switch       │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 2. Traditional Download Process                                            │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ HTTP Download   │────▶│ Local File      │────▶│ File Validation     │   │
│    │ (wget/requests) │     │ Storage         │     │ & Processing        │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 3. S3 Upload Process                                                       │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ S3 Upload       │────▶│ Upload          │────▶│ Local File          │   │
│    │ Preparation     │     │ Execution       │     │ Cleanup             │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ 4. Results & Comparison                                                    │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Traditional     │────▶│ Performance     │────▶│ Comparative         │   │
│    │ Results         │     │ Metrics         │     │ Analysis            │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Error Handling & Recovery Flow                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ Error Detection                                                             │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Operation       │────▶│ Error           │────▶│ Error               │   │
│    │ Execution       │     │ Detection       │     │ Classification      │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ Error Analysis & Decision                                                  │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Error Type      │────▶│ Recovery        │────▶│ Action Selection    │   │
│    │ Analysis        │     │ Strategy        │     │ & Execution         │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                     │                                       │
│ Recovery Actions                                                           │
│    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│    │ Retry with      │     │ Fallback to     │     │ Error Reporting     │   │
│    │ Adjusted Params │     │ Traditional     │     │ & Logging           │   │
│    └─────────────────┘     └─────────────────┘     └─────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Integration Architecture

### Prefect Workflow Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Prefect Integration Architecture                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Prefect Flow Layer                                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    enhanced_archive_collection_flow                     │ │
│  │                                                                         │ │
│  │  @flow(task_runner=ConcurrentTaskRunner(), retries=1)                  │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │ validate_   │  │ generate_   │  │ execute_    │  │ collect_        │ │ │
│  │  │ config      │  │ tasks       │  │ enhanced    │  │ metrics         │ │ │
│  │  │ @task       │  │ @task       │  │ @task       │  │ @task           │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  Business Logic Layer                                                       │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                      S3 Direct Sync Components                          │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │                   EnhancedBulkDownloader                            │ │ │
│  │  │                                                                     │ │ │
│  │  │  ┌─────────────────────────┐    ┌─────────────────────────────────┐  │ │ │
│  │  │  │ S3DirectSyncDownloader  │    │ TraditionalBulkDownloader       │  │ │ │
│  │  │  │                         │    │                                 │  │ │ │
│  │  │  └─────────────────────────┘    └─────────────────────────────────┘  │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  Infrastructure Layer                                                       │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                       External Tool Integration                         │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │ │
│  │  │ s5cmd Tool      │  │ AWS S3 APIs     │  │ Monitoring & Logging    │  │ │
│  │  │ Integration     │  │ (boto3)         │  │ Infrastructure          │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Configuration Integration

```yaml
# Configuration Schema Integration
archive_collection:
  # Legacy configuration (preserved)
  workflow_type: "archive_samples"
  base_output_dir: "output/archive-samples"
  
  # Enhanced S3 Direct Sync configuration
  enable_s3_direct_sync: true
  operation_mode: "auto"  # auto, direct_sync, traditional
  
  s3_direct_sync:
    destination_bucket: "crypto-lakehouse-bronze"
    destination_prefix: "binance/archive"
    sync_mode: "copy"  # copy, sync
    enable_incremental: true
    
    performance_optimization:
      max_concurrent: 16
      batch_size: 200
      part_size_mb: 100
      retry_count: 5
      
    s3_config:
      region: "us-east-1"
      endpoint_url: null  # For S3-compatible services
```

## Performance Architecture

### Parallel Processing Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Parallel Processing Architecture                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Batch Processing Layer                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        Batch Optimization Logic                        │ │
│  │                                                                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │ │
│  │  │File Size    │  │Region       │  │Symbol       │  │Date/Time        │ │ │
│  │  │Grouping     │  │Grouping     │  │Grouping     │  │Grouping         │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ │ │
│  └─────────────────────────┬───────────────────────────────────────────────┘ │
│                            │                                                 │
│  Worker Pool Management                                                     │
│  ┌─────────────────────────▼───────────────────────────────────────────────┐ │
│  │                      s5cmd Worker Pool                                 │ │
│  │                                                                         │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐     ┌──────────┐ ┌──────────┐  │ │
│  │  │Worker 1  │ │Worker 2  │ │Worker 3  │ ... │Worker N-1│ │Worker N  │  │ │
│  │  │          │ │          │ │          │     │          │ │          │  │ │
│  │  │Batch A   │ │Batch B   │ │Batch C   │     │Batch X   │ │Batch Y   │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘     └──────────┘ └──────────┘  │ │
│  └─────────────────────────┬───────────────────────────────────────────────┘ │
│                            │                                                 │
│  Transfer Execution Layer                                                   │
│  ┌─────────────────────────▼───────────────────────────────────────────────┐ │
│  │                    Direct S3 to S3 Transfers                           │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │                  Source S3 (Binance Archive)                       │ │ │
│  │  └─────────────────────────┬───────────────────────────────────────────┘ │ │
│  │                            │                                             │ │
│  │                            ▼ (Parallel transfers)                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │                Destination S3 (Crypto Lakehouse)                   │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Memory Management Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Memory Management Architecture                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Memory Usage Comparison                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  Traditional Mode Memory Pattern:                                      │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Base (100MB) + (File Size × Concurrent Downloads)                  │ │ │
│  │  │ Example: 100MB + (50MB × 10 files) = 600MB peak usage             │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  Direct Sync Mode Memory Pattern:                                      │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Base (100MB) + (1KB × File Count)                                  │ │ │
│  │  │ Example: 100MB + (1KB × 1000 files) = 101MB constant usage        │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Memory Optimization Strategies                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  1. Streaming Processing - No file caching in memory                   │ │
│  │  2. Batch Size Optimization - Optimal batch sizes for memory limits    │ │
│  │  3. Worker Pool Management - Dynamic worker allocation                 │ │
│  │  4. Garbage Collection - Automatic cleanup and resource management    │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Security Architecture

### Access Control Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Security & Access Control Architecture           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Authentication Layer                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │ │
│  │  │ IAM Roles       │  │ Environment     │  │ AWS Credentials         │  │ │
│  │  │ (Preferred)     │  │ Variables       │  │ File                    │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  Permission Management                                                      │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                        IAM Policy Structure                             │ │
│  │                                                                         │ │
│  │  Source Bucket Permissions:          Destination Bucket Permissions:   │ │
│  │  ┌─────────────────────────────┐     ┌─────────────────────────────────┐ │ │
│  │  │ • s3:ListBucket             │     │ • s3:ListBucket                 │ │ │
│  │  │ • s3:GetObject              │     │ • s3:GetObject                  │ │ │
│  │  │ • s3:GetObjectVersion       │     │ • s3:PutObject                  │ │ │
│  │  └─────────────────────────────┘     │ • s3:PutObjectAcl               │ │ │
│  │                                      │ • s3:DeleteObject (optional)    │ │ │
│  │                                      └─────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  Data Protection Layer                                                      │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                         Encryption & Data Protection                    │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Encryption in Transit:                                              │ │ │
│  │  │ • TLS 1.2+ for all S3 operations (automatic with s5cmd)            │ │ │
│  │  │ • HTTPS enforcement for all API calls                              │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Encryption at Rest:                                                 │ │ │
│  │  │ • S3 bucket encryption (AES-256 or KMS)                            │ │ │
│  │  │ • Object-level encryption options                                  │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Multi-Environment Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Multi-Environment Deployment Architecture           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Development Environment                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  Local Development          │  Container Development                     │ │
│  │  ┌─────────────────────────┐ │ ┌─────────────────────────────────────────┐ │ │
│  │  │ • Local s5cmd install   │ │ │ • Docker container with s5cmd           │ │ │
│  │  │ • AWS credentials file  │ │ │ • Environment variable configuration    │ │ │
│  │  │ • Test S3 buckets       │ │ │ • MinIO for S3 simulation              │ │ │
│  │  │ • Limited parallelism   │ │ │ • Full feature testing                 │ │ │
│  │  └─────────────────────────┘ │ └─────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  Staging Environment                                                        │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                          AWS ECS/Fargate Deployment                     │ │
│  │                                                                         │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Container Specifications:                                           │ │ │
│  │  │ • Base Image: python:3.11-slim                                     │ │ │
│  │  │ • s5cmd binary installation                                        │ │ │
│  │  │ • IAM role-based authentication                                    │ │ │
│  │  │ • Staging S3 buckets                                               │ │ │
│  │  │ • Monitoring and logging                                           │ │ │
│  │  └─────────────────────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                     │
│  Production Environment                                                     │
│  ┌─────────────────────────────────────▼─────────────────────────────────────┐ │
│  │                         Production AWS Infrastructure                   │ │
│  │                                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │ │
│  │  │ ECS/Fargate     │  │ Production S3   │  │ CloudWatch Monitoring   │  │ │
│  │  │ Cluster         │  │ Buckets         │  │ & Alerting              │  │ │
│  │  │                 │  │                 │  │                         │  │ │
│  │  │ • Auto-scaling  │  │ • Encryption    │  │ • Performance metrics   │  │ │
│  │  │ • High availability│ │ • Versioning    │  │ • Error alerting        │  │ │
│  │  │ • Resource limits│  │ • Lifecycle     │  │ • Cost monitoring       │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Infrastructure as Code Architecture

```yaml
# Terraform/CloudFormation Template Structure
terraform:
  modules:
    - s3_buckets:
        source_bucket_access: read-only
        destination_bucket: read-write
        encryption: enabled
        versioning: enabled
        
    - iam_roles:
        s3_direct_sync_role:
          policies:
            - S3SourceBucketRead
            - S3DestinationBucketWrite
            - CloudWatchLogs
            
    - ecs_cluster:
        cluster_name: "crypto-lakehouse"
        capacity_providers: ["FARGATE"]
        
    - task_definition:
        family: "s3-direct-sync"
        cpu: 2048
        memory: 4096
        image: "crypto-lakehouse:s3-direct-sync"
        
    - monitoring:
        cloudwatch_logs: enabled
        performance_metrics: enabled
        cost_monitoring: enabled
```

---

**Document Version**: 2.1.0  
**Last Updated**: 2025-07-19  
**Architecture Status**: Production Ready  
**Review Date**: 2025-10-19