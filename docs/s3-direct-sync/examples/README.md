# S3 Direct Sync Configuration Examples

This directory contains practical configuration examples for different use cases and environments.

## Available Examples

### 1. Basic Configuration (`basic-configuration.json`)
**Use Case**: Development and testing environments  
**Characteristics**:
- Minimal configuration for getting started
- Basic S3 direct sync settings
- Limited data scope (2 symbols, 3 intervals)
- Auto-mode operation for intelligent fallback

**Performance Expectations**:
- 40-60% improvement over traditional mode
- Suitable for small datasets (< 100 files)
- Memory usage: < 200MB

### 2. Production Configuration (`production-configuration.json`)
**Use Case**: Production environments with balanced performance and reliability  
**Characteristics**:
- Comprehensive monitoring and logging
- Multiple markets and data types
- Quality control and validation
- Performance optimization settings

**Performance Expectations**:
- 60%+ improvement over traditional mode
- Handles medium-large datasets (100-1000 files)
- Memory usage: < 500MB
- Enhanced reliability and error handling

### 3. High Performance Configuration (`high-performance-configuration.json`)
**Use Case**: Enterprise environments requiring maximum performance  
**Characteristics**:
- Maximum concurrency and throughput
- Advanced features enabled
- Real-time monitoring
- Resource optimization

**Performance Expectations**:
- 65%+ improvement over traditional mode
- Handles large datasets (1000+ files)
- Memory usage: < 1GB
- Maximum transfer rates and efficiency

### 4. Cost Optimized Configuration (`cost-optimized-configuration.json`)
**Use Case**: Budget-conscious operations with cost constraints  
**Characteristics**:
- Optimized for cost reduction
- Intelligent storage tiering
- Resource constraints
- Cost tracking and monitoring

**Performance Expectations**:
- 40-50% improvement over traditional mode
- Optimized for cost per GB transferred
- Reduced resource consumption
- Long-term storage optimization

## Quick Start Guide

### 1. Choose Your Configuration

```bash
# Copy the appropriate template
cp docs/s3-direct-sync/examples/basic-configuration.json my-config.json

# Or for production
cp docs/s3-direct-sync/examples/production-configuration.json my-config.json
```

### 2. Customize Your Configuration

Edit the configuration file to match your requirements:

```json
{
  "destination_bucket": "your-lakehouse-bucket",
  "symbols": ["YOUR_SYMBOL1", "YOUR_SYMBOL2"],
  "date_range": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  }
}
```

### 3. Run the Enhanced Workflow

```bash
python examples/run_enhanced_archive_collection.py --config my-config.json
```

## Configuration Sections Explained

### Core S3 Direct Sync Settings

```json
{
  "enable_s3_direct_sync": true,        // Enable S3 direct sync functionality
  "operation_mode": "auto",             // auto|direct_sync|traditional
  "destination_bucket": "bucket-name",  // Target S3 bucket
  "destination_prefix": "path/prefix",  // Optional S3 prefix
  "sync_mode": "copy",                  // copy|sync
  "enable_incremental": true            // Skip existing files
}
```

### Performance Optimization

```json
{
  "performance_optimization": {
    "max_concurrent": 16,               // Parallel workers (1-50)
    "batch_size": 200,                  // Files per batch (1-1000)
    "part_size_mb": 100,               // S3 multipart size (1-1000)
    "retry_count": 5                    // Retry attempts (1-10)
  }
}
```

### S3 Configuration

```json
{
  "s3_config": {
    "region": "us-east-1",             // AWS region
    "storage_class": "STANDARD",       // S3 storage class
    "use_accelerated_endpoint": false  // S3 Transfer Acceleration
  }
}
```

### Monitoring and Quality Control

```json
{
  "monitoring": {
    "enable_performance_tracking": true,
    "enable_cost_tracking": true,
    "log_level": "INFO"
  },
  "quality_control": {
    "enable_checksum_validation": true,
    "enable_size_verification": true,
    "max_retry_attempts": 3
  }
}
```

## Environment-Specific Configurations

### Development Environment

```bash
# Use basic configuration with verbose logging
{
  "enable_s3_direct_sync": true,
  "operation_mode": "auto",
  "verbose": true,
  "dry_run": false,
  "performance_optimization": {
    "max_concurrent": 4,
    "batch_size": 50
  }
}
```

### Staging Environment

```bash
# Use production configuration with reduced scale
{
  "enable_s3_direct_sync": true,
  "operation_mode": "direct_sync",
  "performance_optimization": {
    "max_concurrent": 8,
    "batch_size": 100
  },
  "monitoring": {
    "enable_performance_tracking": true
  }
}
```

### Production Environment

```bash
# Use production or high-performance configuration
{
  "enable_s3_direct_sync": true,
  "operation_mode": "direct_sync",
  "performance_optimization": {
    "max_concurrent": 16,
    "batch_size": 200
  },
  "monitoring": {
    "enable_performance_tracking": true,
    "enable_cost_tracking": true
  }
}
```

## Performance Tuning Guidelines

### By Workload Size

| Workload Size | Files | Recommended Config |
|---------------|-------|-------------------|
| **Small** | 1-100 | basic-configuration.json |
| **Medium** | 100-1000 | production-configuration.json |
| **Large** | 1000+ | high-performance-configuration.json |

### By File Size Distribution

| Average File Size | Optimal Settings |
|------------------|------------------|
| **< 10MB** | `max_concurrent: 32, batch_size: 500` |
| **10-50MB** | `max_concurrent: 16, batch_size: 200` |
| **> 50MB** | `max_concurrent: 8, batch_size: 100` |

### By Network Environment

| Network Type | Configuration Adjustments |
|--------------|---------------------------|
| **High Bandwidth** | Increase `max_concurrent`, larger `part_size_mb` |
| **Limited Bandwidth** | Reduce `max_concurrent`, smaller `part_size_mb` |
| **Unstable Network** | Increase `retry_count`, reduce `max_concurrent` |

## Validation and Testing

### Configuration Validation

```bash
# Validate configuration syntax
python -m json.tool my-config.json

# Test configuration with dry run
python examples/run_enhanced_archive_collection.py --config my-config.json --dry-run
```

### Performance Testing

```bash
# Run with small dataset first
python examples/run_enhanced_archive_collection.py --config my-config.json --limit 10

# Monitor performance metrics
tail -f logs/enhanced_archive_collection.log
```

## Troubleshooting

### Common Issues

1. **Configuration Errors**
   - Validate JSON syntax
   - Check required fields
   - Verify bucket permissions

2. **Performance Issues**
   - Start with basic configuration
   - Gradually increase concurrency
   - Monitor system resources

3. **Permission Issues**
   - Verify IAM policies
   - Check bucket policies
   - Test with AWS CLI

### Getting Help

- Review [Best Practices Guide](../best-practices.md)
- Check [Troubleshooting Guide](../troubleshooting.md)
- Monitor performance with [Performance Guide](../performance.md)

## Contributing Examples

### Adding New Examples

1. Create configuration file following naming convention
2. Add description and use case documentation
3. Include performance expectations
4. Test configuration thoroughly
5. Update this README with new example

### Example Template

```json
{
  "workflow_type": "archive_samples",
  "description": "Your Example Description",
  "version": "2.1.0",
  
  // Your configuration here
  
  "metadata": {
    "description": "Detailed description",
    "author": "Your Name",
    "created_date": "YYYY-MM-DD",
    "environment": "development|staging|production"
  }
}
```

---

**Examples Version**: 2.1.0  
**Last Updated**: 2025-07-19  
**Compatibility**: S3 Direct Sync v2.1.0+  
**Maintainer**: Crypto Lakehouse Platform Team