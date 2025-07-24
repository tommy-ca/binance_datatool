# s5cmd Specifications for S3 Direct Sync

## Overview

This document provides comprehensive specifications for s5cmd integration in the S3 direct sync functionality, including installation, configuration, usage patterns, and optimization strategies.

## Table of Contents

1. [Tool Overview](#tool-overview)
2. [Installation Requirements](#installation-requirements)
3. [Configuration Specifications](#configuration-specifications)
4. [Command Patterns](#command-patterns)
5. [Batch File Generation](#batch-file-generation)
6. [Performance Optimization](#performance-optimization)
7. [Error Handling](#error-handling)
8. [Security Considerations](#security-considerations)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Best Practices](#best-practices)

## Tool Overview

### What is s5cmd?

s5cmd is a high-performance, parallel, statistical S3 command-line tool designed for efficient S3 operations. It provides significant performance improvements over traditional AWS CLI tools.

**Key Features:**
- **Parallel operations** - Multiple concurrent transfers
- **Statistical reporting** - Detailed performance metrics
- **Efficient memory usage** - Optimized for large-scale operations
- **Cross-platform support** - Linux, macOS, Windows
- **S3 compatibility** - Works with AWS S3 and S3-compatible services

### Why s5cmd for Direct Sync?

| Feature | AWS CLI s3 | s5cmd | Advantage |
|---------|------------|-------|-----------|
| **Parallel Transfers** | Limited | High concurrency | 10x faster transfers |
| **Memory Usage** | High | Optimized | 50% less memory |
| **Batch Operations** | Basic | Advanced | Complex workflows |
| **Progress Reporting** | Limited | Detailed | Real-time monitoring |
| **Error Handling** | Basic | Robust | Better reliability |

## Installation Requirements

### Supported Versions

**Minimum Version**: s5cmd v2.2.0  
**Recommended Version**: s5cmd v2.2.2+  
**Latest Tested**: s5cmd v2.2.2

### Installation Methods

#### 1. Binary Download (Recommended)

```bash
# Linux x64
wget https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz
tar -xzf s5cmd_2.2.2_Linux-64bit.tar.gz
sudo mv s5cmd /usr/local/bin/
chmod +x /usr/local/bin/s5cmd

# macOS x64
wget https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_macOS-64bit.tar.gz
tar -xzf s5cmd_2.2.2_macOS-64bit.tar.gz
sudo mv s5cmd /usr/local/bin/
chmod +x /usr/local/bin/s5cmd

# Windows x64
# Download s5cmd_2.2.2_Windows-64bit.zip and extract to PATH
```

#### 2. Package Managers

```bash
# Homebrew (macOS)
brew install peak/tap/s5cmd

# Go install
go install github.com/peak/s5cmd/v2@latest

# Docker
docker run --rm -v $(pwd):/data peak/s5cmd:latest version
```

### Verification

```bash
# Check installation
s5cmd version

# Expected output:
# s5cmd version v2.2.2
```

### System Requirements

**Minimum System Requirements:**
- **OS**: Linux, macOS, Windows
- **Architecture**: x64, ARM64
- **Memory**: 512MB available RAM
- **Network**: Stable internet connection
- **Permissions**: Read/write access to S3 buckets

**Recommended System Requirements:**
- **Memory**: 2GB+ available RAM
- **CPU**: 4+ cores for optimal parallel processing
- **Network**: High-bandwidth connection (100+ Mbps)
- **Storage**: Minimal local storage for batch files

## Configuration Specifications

### Authentication Methods

#### 1. Environment Variables (Recommended)
```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_REGION="us-east-1"
```

#### 2. AWS Credentials File
```ini
# ~/.aws/credentials
[default]
aws_access_key_id = your-access-key
aws_secret_access_key = your-secret-key

# ~/.aws/config
[default]
region = us-east-1
```

#### 3. IAM Roles (AWS EC2/ECS)
```bash
# Use instance metadata service
# No configuration required when running on AWS infrastructure
```

### S3 Endpoint Configuration

#### AWS S3 (Default)
```bash
# No additional configuration needed
s5cmd ls s3://bucket/
```

#### S3-Compatible Services
```bash
# MinIO Example
s5cmd --endpoint-url https://minio.example.com ls s3://bucket/

# Other S3-compatible services
s5cmd --endpoint-url https://s3.wasabisys.com ls s3://bucket/
```

### Global Configuration Options

```bash
# Basic configuration
s5cmd --help

# Common global options:
--endpoint-url string     # Custom S3 endpoint URL
--no-sign-request        # Use for public buckets (like Binance data)
--profile string         # AWS profile to use
--region string          # Override AWS region
--dry-run               # Show operations without executing
--json                  # JSON output format
--log-level string      # Log level (trace, debug, info, warn, error)
```

## Command Patterns

### Core Commands Used in S3 Direct Sync

#### 1. Copy Command (Primary)

```bash
# Basic copy
s5cmd cp 's3://source/file.zip' 's3://dest/file.zip'

# Copy with options
s5cmd cp \
  --if-size-differ \
  --source-region ap-northeast-1 \
  --part-size 50MB \
  's3://source/file.zip' \
  's3://dest/file.zip'
```

#### 2. Sync Command (Alternative)

```bash
# Sync directories
s5cmd sync 's3://source/prefix/' 's3://dest/prefix/'

# Sync with exclusions
s5cmd sync \
  --exclude "*.tmp" \
  --exclude "*.log" \
  's3://source/prefix/' \
  's3://dest/prefix/'
```

#### 3. List Command (Validation)

```bash
# List objects
s5cmd ls 's3://bucket/prefix/'

# List with details
s5cmd ls --summarize 's3://bucket/prefix/'
```

### Command Options Reference

#### Copy Options
```bash
--if-size-differ         # Copy only if sizes differ
--if-source-newer        # Copy only if source is newer
--source-region string   # Source bucket region
--dest-region string     # Destination bucket region
--part-size string       # Multipart upload part size
--storage-class string   # S3 storage class
--sse string            # Server-side encryption
--sse-kms-key-id string # KMS key for encryption
```

#### Performance Options
```bash
--numworkers int        # Number of parallel workers (default: 256)
--retry-count int       # Number of retries (default: 10)
--request-payer string  # Request payer for S3 operations
```

#### Output Options
```bash
--json                  # JSON output format
--summarize            # Show summary statistics
--human-readable       # Human-readable sizes
```

## Batch File Generation

### Batch File Format

S3 direct sync generates optimized batch files for s5cmd execution:

```bash
# Example batch file: s5cmd_batch_20250719_143022.txt
cp --if-size-differ --source-region ap-northeast-1 --part-size 50MB 's3://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2025-07-15.zip' 's3://crypto-lakehouse-bronze/binance/archive/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2025-07-15.zip'
cp --if-size-differ --source-region ap-northeast-1 --part-size 50MB 's3://data.binance.vision/data/spot/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2025-07-15.zip' 's3://crypto-lakehouse-bronze/binance/archive/spot/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2025-07-15.zip'
cp --if-size-differ --source-region ap-northeast-1 --part-size 50MB 's3://data.binance.vision/data/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-07-15.zip' 's3://crypto-lakehouse-bronze/binance/archive/spot/daily/klines/ETHUSDT/1m/ETHUSDT-1m-2025-07-15.zip'
```

### Batch File Generation Logic

```python
def generate_s5cmd_batch_file(self, source_files: List[Dict[str, str]]) -> str:
    """Generate optimized s5cmd batch file."""
    batch_commands = []
    
    for file_info in source_files:
        source_url = file_info['source_url']
        target_path = file_info['target_path']
        destination_url = f"s3://{self.destination_bucket}/{self.destination_prefix.rstrip('/')}/{target_path}"
        
        # Build command with optimizations
        command_parts = [
            "cp",
            "--if-size-differ",  # Skip if same size
            f"--source-region {self.source_region}",
            f"--part-size {self.part_size_mb}MB"
        ]
        
        # Add optional parameters
        if self.storage_class:
            command_parts.append(f"--storage-class {self.storage_class}")
        
        command = f"{' '.join(command_parts)} '{source_url}' '{destination_url}'"
        batch_commands.append(command)
    
    return '\n'.join(batch_commands)
```

### Batch File Optimization

#### 1. Command Grouping
```python
# Group by common source regions for efficiency
def group_by_source_region(files):
    groups = {}
    for file_info in files:
        region = extract_region_from_url(file_info['source_url'])
        if region not in groups:
            groups[region] = []
        groups[region].append(file_info)
    return groups
```

#### 2. Size-Based Optimization
```python
# Different part sizes for different file sizes
def optimize_part_size(file_size_mb):
    if file_size_mb < 50:
        return "10MB"    # Small files
    elif file_size_mb < 500:
        return "50MB"    # Medium files
    else:
        return "100MB"   # Large files
```

#### 3. Path Organization
```python
# Organize target paths efficiently
def organize_target_path(source_url, organize_by_prefix=True):
    if organize_by_prefix:
        # Group files by symbol/date for better S3 performance
        return generate_partitioned_path(source_url)
    else:
        # Maintain original structure
        return extract_path_from_url(source_url)
```

## Performance Optimization

### Worker Configuration

#### Optimal Worker Counts

```bash
# File size based worker optimization
Small files (< 10MB):   --numworkers 50
Medium files (10-100MB): --numworkers 20
Large files (> 100MB):  --numworkers 10
Mixed workloads:         --numworkers 16 (default optimized)
```

#### Memory Considerations

```python
# Calculate optimal workers based on available memory
def calculate_optimal_workers(available_memory_gb, average_file_size_mb):
    """Calculate optimal number of workers based on system resources."""
    # Reserve 20% memory for system
    usable_memory_gb = available_memory_gb * 0.8
    
    # Estimate memory per worker (empirical data)
    memory_per_worker_mb = max(50, average_file_size_mb * 0.1)
    
    # Calculate maximum workers
    max_workers = int((usable_memory_gb * 1024) / memory_per_worker_mb)
    
    # Apply practical limits
    return min(max_workers, 50)  # Cap at 50 workers
```

### Part Size Optimization

#### Adaptive Part Sizing

```python
def calculate_optimal_part_size(file_size_mb, bandwidth_mbps):
    """Calculate optimal part size for multipart uploads."""
    # Base part size on file size
    if file_size_mb < 50:
        base_part_size = 5   # 5MB for small files
    elif file_size_mb < 500:
        base_part_size = 50  # 50MB for medium files
    else:
        base_part_size = 100 # 100MB for large files
    
    # Adjust for bandwidth (optional)
    if bandwidth_mbps < 10:
        base_part_size = max(5, base_part_size // 2)  # Smaller parts for slow connections
    
    return base_part_size
```

#### Storage Class Optimization

```bash
# Storage class selection for cost optimization
--storage-class STANDARD         # Frequent access
--storage-class STANDARD_IA      # Infrequent access
--storage-class GLACIER         # Archive storage
--storage-class GLACIER_IR      # Glacier Instant Retrieval
```

### Network Optimization

#### Regional Optimization

```python
# Automatic region detection and optimization
def optimize_transfer_regions(source_url, destination_bucket):
    """Optimize transfer based on S3 regions."""
    source_region = detect_bucket_region(source_url)
    dest_region = detect_bucket_region(destination_bucket)
    
    if source_region == dest_region:
        # Same region - optimize for speed
        return {
            'numworkers': 20,
            'part_size': '100MB',
            'retry_count': 3
        }
    else:
        # Cross-region - optimize for reliability
        return {
            'numworkers': 10,
            'part_size': '50MB',
            'retry_count': 5
        }
```

#### Bandwidth Throttling

```bash
# Rate limiting for bandwidth management
s5cmd --rate-limit 50MB/s cp 's3://source/file' 's3://dest/file'
```

## Error Handling

### Common Error Scenarios

#### 1. Access Denied Errors

```bash
# Error
ERROR: Operation failed: Access Denied

# Resolution
# Check IAM permissions
aws iam get-user-policy --user-name your-user --policy-name S3Access

# Verify bucket policies
aws s3api get-bucket-policy --bucket destination-bucket
```

#### 2. Network Timeout Errors

```bash
# Error
ERROR: Request timeout

# s5cmd options for timeout handling
--retry-count 5          # Increase retry attempts
--request-timeout 30s    # Increase timeout duration
```

#### 3. Multipart Upload Failures

```bash
# Error
ERROR: Multipart upload failed

# Resolution strategies
--part-size 25MB         # Reduce part size
--numworkers 5          # Reduce concurrency
```

### Error Recovery Patterns

#### Automatic Retry Logic

```python
def execute_s5cmd_with_retry(batch_file_path, max_retries=3):
    """Execute s5cmd with automatic retry logic."""
    for attempt in range(max_retries):
        try:
            result = execute_s5cmd_batch(batch_file_path)
            if result.returncode == 0:
                return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            # Exponential backoff
            wait_time = (2 ** attempt) * 30
            time.sleep(wait_time)
    
    raise RuntimeError(f"s5cmd execution failed after {max_retries} attempts")
```

#### Partial Success Handling

```python
def handle_partial_success(batch_results):
    """Handle cases where some transfers succeed and others fail."""
    successful_transfers = []
    failed_transfers = []
    
    for transfer in batch_results:
        if transfer['success']:
            successful_transfers.append(transfer)
        else:
            failed_transfers.append(transfer)
    
    # Retry failed transfers with different parameters
    if failed_transfers:
        retry_batch = generate_retry_batch(failed_transfers)
        return execute_s5cmd_with_reduced_concurrency(retry_batch)
    
    return successful_transfers
```

### Fallback Mechanisms

#### Automatic Tool Detection

```python
def check_s5cmd_availability():
    """Check if s5cmd is available and functional."""
    try:
        result = subprocess.run(['s5cmd', 'version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def get_fallback_options():
    """Get available fallback tools if s5cmd is unavailable."""
    fallback_tools = []
    
    if check_aws_cli_availability():
        fallback_tools.append('aws_cli')
    
    if check_boto3_availability():
        fallback_tools.append('boto3')
    
    return fallback_tools
```

## Security Considerations

### Authentication Security

#### 1. Credential Management

```bash
# Secure credential storage
# Use AWS IAM roles when possible (recommended)
# Avoid hardcoded credentials in configuration files
# Use environment variables for local development
# Implement credential rotation policies
```

#### 2. Least Privilege Access

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::source-bucket/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::destination-bucket/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::source-bucket",
                "arn:aws:s3:::destination-bucket"
            ]
        }
    ]
}
```

### Data Protection

#### 1. Encryption in Transit

```bash
# s5cmd automatically uses HTTPS for S3 operations
# No additional configuration required for encryption in transit
```

#### 2. Encryption at Rest

```bash
# Server-side encryption options
s5cmd cp --sse AES256 's3://source/file' 's3://dest/file'
s5cmd cp --sse aws:kms --sse-kms-key-id key-id 's3://source/file' 's3://dest/file'
```

#### 3. Bucket Security

```bash
# Verify bucket encryption
aws s3api get-bucket-encryption --bucket destination-bucket

# Enable bucket versioning for data protection
aws s3api put-bucket-versioning \
  --bucket destination-bucket \
  --versioning-configuration Status=Enabled
```

## Monitoring and Logging

### Performance Monitoring

#### 1. Built-in Statistics

```bash
# s5cmd provides detailed statistics
s5cmd --summarize sync 's3://source/' 's3://dest/'

# Example output:
# Copied: 150 files, 2.5 GB
# Skipped: 25 files (already exist)
# Failed: 0 files
# Total time: 45.2s
# Average speed: 56.7 MB/s
```

#### 2. JSON Output for Monitoring

```bash
# JSON output for programmatic monitoring
s5cmd --json --summarize cp 's3://source/file' 's3://dest/file'

# Parse JSON output for metrics collection
{
  "operation": "cp",
  "success": true,
  "source": "s3://source/file",
  "destination": "s3://dest/file",
  "size": 1048576,
  "duration": "1.234s"
}
```

### Integration with Monitoring Systems

#### 1. CloudWatch Integration

```python
def send_s5cmd_metrics_to_cloudwatch(metrics_data):
    """Send s5cmd performance metrics to CloudWatch."""
    cloudwatch = boto3.client('cloudwatch')
    
    cloudwatch.put_metric_data(
        Namespace='S3DirectSync',
        MetricData=[
            {
                'MetricName': 'TransferSpeed',
                'Value': metrics_data['speed_mbps'],
                'Unit': 'None'
            },
            {
                'MetricName': 'FilesTransferred',
                'Value': metrics_data['files_transferred'],
                'Unit': 'Count'
            },
            {
                'MetricName': 'TransferDuration',
                'Value': metrics_data['duration_seconds'],
                'Unit': 'Seconds'
            }
        ]
    )
```

#### 2. Log Analysis

```python
def parse_s5cmd_logs(log_output):
    """Parse s5cmd output for monitoring and alerting."""
    import re
    
    # Extract performance metrics
    speed_pattern = r'Average speed: ([\d.]+) MB/s'
    files_pattern = r'Copied: (\d+) files'
    errors_pattern = r'Failed: (\d+) files'
    
    metrics = {
        'speed_mbps': float(re.search(speed_pattern, log_output).group(1)),
        'files_copied': int(re.search(files_pattern, log_output).group(1)),
        'files_failed': int(re.search(errors_pattern, log_output).group(1))
    }
    
    return metrics
```

## Best Practices

### Performance Best Practices

#### 1. Batch Size Optimization

```python
# Optimal batch sizes for different scenarios
BATCH_SIZE_RECOMMENDATIONS = {
    'small_files': 500,     # Files < 10MB
    'medium_files': 200,    # Files 10-100MB
    'large_files': 50,      # Files > 100MB
    'mixed_workload': 100   # Default for mixed sizes
}
```

#### 2. Worker Pool Management

```python
def optimize_worker_count(system_info, file_info):
    """Optimize worker count based on system and file characteristics."""
    base_workers = min(16, system_info['cpu_cores'] * 2)
    
    # Adjust for file characteristics
    if file_info['average_size_mb'] > 100:
        return max(4, base_workers // 2)  # Fewer workers for large files
    elif file_info['average_size_mb'] < 10:
        return min(32, base_workers * 2)  # More workers for small files
    else:
        return base_workers  # Standard worker count
```

#### 3. Error Prevention

```python
# Pre-flight checks before executing s5cmd
def validate_s5cmd_execution_environment():
    """Validate environment before executing s5cmd operations."""
    checks = {
        's5cmd_available': check_s5cmd_availability(),
        'credentials_valid': validate_aws_credentials(),
        'destination_writable': test_destination_write_access(),
        'source_readable': test_source_read_access(),
        'network_connectivity': test_s3_connectivity()
    }
    
    failed_checks = [check for check, passed in checks.items() if not passed]
    
    if failed_checks:
        raise EnvironmentError(f"Pre-flight checks failed: {failed_checks}")
    
    return True
```

### Operational Best Practices

#### 1. Configuration Management

```yaml
# Environment-specific s5cmd configurations
development:
  numworkers: 4
  part_size: "25MB"
  retry_count: 3
  
staging:
  numworkers: 8
  part_size: "50MB"
  retry_count: 5
  
production:
  numworkers: 16
  part_size: "100MB"
  retry_count: 5
  enable_monitoring: true
```

#### 2. Progress Tracking

```python
def track_s5cmd_progress(batch_file_path):
    """Track and report progress of s5cmd batch operations."""
    total_operations = count_batch_operations(batch_file_path)
    completed_operations = 0
    
    def progress_callback(line):
        nonlocal completed_operations
        if "Copied:" in line or "Skipped:" in line:
            completed_operations += 1
            progress = (completed_operations / total_operations) * 100
            print(f"Progress: {progress:.1f}% ({completed_operations}/{total_operations})")
    
    execute_s5cmd_with_callback(batch_file_path, progress_callback)
```

#### 3. Resource Management

```python
def manage_s5cmd_resources():
    """Manage system resources during s5cmd operations."""
    # Monitor memory usage
    def check_memory_usage():
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > 85:
            logging.warning(f"High memory usage: {memory_percent}%")
            return False
        return True
    
    # Monitor disk space for batch files
    def check_disk_space():
        disk_usage = psutil.disk_usage('/tmp').percent
        if disk_usage > 90:
            logging.error(f"Low disk space: {100-disk_usage}% available")
            return False
        return True
    
    return check_memory_usage() and check_disk_space()
```

---

**Document Version**: 2.1.0  
**Last Updated**: 2025-07-19  
**s5cmd Version**: v2.2.2+  
**Status**: Production Ready