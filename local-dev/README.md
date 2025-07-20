# Local Development Environment - Crypto Lakehouse

## Overview

This directory contains the local development setup for the Crypto Lakehouse platform using k3s, MinIO, Prefect, and OpenTelemetry observability. This implementation follows the infrastructure specifications from Phase 2 design but optimized for local development.

**Environment**: Local Development  
**Orchestrator**: k3s (Lightweight Kubernetes)  
**Storage**: MinIO (Single-node mode)  
**Workflow Engine**: Prefect v3.0.0+  
**Observability**: OpenTelemetry + Jaeger + Prometheus  
**Based On**: Phase 2 Design Specifications v1.0.0

## Quick Start

```bash
# Start the local environment
./scripts/local-setup.sh

# Deploy all services
./scripts/deploy-local.sh

# Validate deployment
./scripts/validate-local.sh

# Access services
echo "Prefect UI: http://localhost:4200"
echo "MinIO Console: http://localhost:9001"
echo "Jaeger UI: http://localhost:16686"
echo "Prometheus: http://localhost:9090"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT SETUP                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   PRESENTATION  │  │   APPLICATION   │  │      DATA       │  │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤  │
│  │ • Prefect UI    │  │ • Prefect Server│  │ • MinIO Single  │  │
│  │ • MinIO Console │  │ • Worker Pool   │  │ • PostgreSQL    │  │
│  │ • Jaeger UI     │  │ • s5cmd Service │  │ • Redis         │  │
│  │ • Prometheus    │  │ • Config Mgmt   │  │ • Local Storage │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│           │                     │                     │         │
│           └─────────────────────┼─────────────────────┘         │
│                                 │                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ OBSERVABILITY   │  │    SECURITY     │  │   K3S CLUSTER   │  │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤  │
│  │ • OpenTelemetry │  │ • Basic Auth    │  │ • Single Node   │  │
│  │ • Jaeger Trace  │  │ • Network Pol   │  │ • Local Storage │  │
│  │ • Prometheus    │  │ • Pod Security  │  │ • Port Forward  │  │
│  │ • Grafana       │  │ • TLS Optional  │  │ • Auto Scaling  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Services & Ports

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| **Prefect Server** | 4200 | http://localhost:4200 | Workflow orchestration UI |
| **MinIO Console** | 9001 | http://localhost:9001 | Object storage management |
| **MinIO API** | 9000 | http://localhost:9000 | S3-compatible API |
| **PostgreSQL** | 5432 | localhost:5432 | Prefect metadata store |
| **Redis** | 6379 | localhost:6379 | Prefect cache |
| **Jaeger UI** | 16686 | http://localhost:16686 | Distributed tracing |
| **Prometheus** | 9090 | http://localhost:9090 | Metrics collection |
| **Grafana** | 3000 | http://localhost:3000 | Metrics visualization |
| **s5cmd Service** | 8080 | http://localhost:8080 | High-performance S3 ops |

## Directory Structure

```
local-dev/
├── README.md                       # This file
├── scripts/                        # Setup and deployment scripts
│   ├── local-setup.sh              # Initial k3s cluster setup
│   ├── deploy-local.sh             # Deploy all services
│   ├── validate-local.sh           # Validate deployment
│   ├── cleanup.sh                  # Clean up environment
│   └── monitoring/                 # Monitoring setup scripts
├── k3s/                            # k3s configuration
│   ├── cluster-config.yaml         # k3s cluster configuration
│   └── storage-class.yaml          # Local storage class
├── manifests/                      # Kubernetes manifests
│   ├── namespace.yaml              # Namespaces
│   ├── prefect/                    # Prefect deployment
│   │   ├── postgresql.yaml         # Database
│   │   ├── redis.yaml              # Cache
│   │   ├── server.yaml             # Prefect server
│   │   └── worker.yaml             # Worker pool
│   ├── minio/                      # MinIO deployment
│   │   ├── deployment.yaml         # MinIO single-node
│   │   ├── service.yaml            # Service exposure
│   │   └── storage.yaml            # Persistent storage
│   ├── s5cmd/                      # s5cmd executor
│   │   ├── deployment.yaml         # s5cmd service
│   │   ├── configmap.yaml          # Configuration
│   │   └── service.yaml            # Service exposure
│   └── observability/              # OpenTelemetry stack
│       ├── otel-collector.yaml     # OTel collector
│       ├── jaeger.yaml             # Jaeger tracing
│       ├── prometheus.yaml         # Prometheus monitoring
│       └── grafana.yaml            # Grafana dashboards
├── docker/                         # Custom container images
│   ├── s5cmd-local/                # Local s5cmd service
│   │   ├── Dockerfile              # Container definition
│   │   ├── app.py                  # Service implementation
│   │   └── requirements.txt        # Python dependencies
│   └── prefect-worker/             # Enhanced worker
│       ├── Dockerfile              # Worker with s5cmd
│       └── entrypoint.sh           # Worker startup
├── config/                         # Configuration files
│   ├── otel-config.yaml            # OpenTelemetry configuration
│   ├── prometheus.yml              # Prometheus config
│   ├── grafana/                    # Grafana dashboards
│   │   ├── dashboards/             # Dashboard definitions
│   │   └── provisioning/           # Auto-provisioning
│   └── minio/                      # MinIO configuration
└── data/                           # Local data persistence
    ├── minio/                      # MinIO data
    ├── postgres/                   # PostgreSQL data
    └── prometheus/                 # Prometheus data
```

## Components

### k3s Cluster
- **Single-node cluster** optimized for development
- **Local storage provisioner** for persistent volumes
- **Basic network policies** for service isolation
- **Automatic port forwarding** for service access

### Prefect Stack
- **Prefect Server v3.0.0+** with SQLite/PostgreSQL backend
- **Worker pool** with s5cmd integration
- **Web UI** for workflow management
- **API access** for programmatic control

### MinIO Storage
- **Single-node deployment** with local persistence
- **S3-compatible API** for testing
- **Management console** for bucket operations
- **Integration** with s5cmd for performance testing

### s5cmd Executor
- **Lightweight service** wrapping s5cmd binary
- **REST API** for operation management
- **Performance monitoring** with OpenTelemetry
- **Direct sync capabilities** for testing

### OpenTelemetry Observability
- **OTel Collector** for metrics and traces
- **Jaeger** for distributed tracing
- **Prometheus** for metrics collection
- **Grafana** for visualization and dashboards

## Performance Targets (Local)

| Metric | Target | Validation |
|--------|--------|------------|
| **s5cmd Improvement** | 30-50% (vs baseline) | Performance tests |
| **Concurrent Workflows** | 10+ simultaneous | Load testing |
| **API Response Time** | <500ms | Health checks |
| **Storage Throughput** | 1GB/s local | Benchmark tests |
| **System Startup** | <5 minutes | Deployment time |

## Getting Started

### Prerequisites

```bash
# Install required tools
curl -sfL https://get.k3s.io | sh -    # k3s
sudo snap install docker              # Docker
pip install prefect                   # Prefect CLI
```

### Environment Setup

```bash
# Clone and setup
cd local-dev

# Start k3s cluster
./scripts/local-setup.sh

# Deploy services
./scripts/deploy-local.sh

# Wait for services to be ready
kubectl wait --for=condition=ready pod --all --timeout=300s

# Validate deployment
./scripts/validate-local.sh
```

### Service Access

```bash
# Forward ports for local access
kubectl port-forward -n prefect svc/prefect-server 4200:4200 &
kubectl port-forward -n minio svc/minio-console 9001:9001 &
kubectl port-forward -n observability svc/jaeger-ui 16686:16686 &
kubectl port-forward -n observability svc/prometheus 9090:9090 &

# Access services
open http://localhost:4200  # Prefect UI
open http://localhost:9001  # MinIO Console (admin/password123)
open http://localhost:16686 # Jaeger UI
open http://localhost:9090  # Prometheus
```

### Development Workflow

```bash
# 1. Create and test workflows
prefect config set PREFECT_API_URL=http://localhost:4200/api

# 2. Deploy workflows
prefect deployment apply my-workflow.yaml

# 3. Monitor execution
# Use Prefect UI or Jaeger for tracing

# 4. Test s5cmd operations
curl -X POST http://localhost:8080/sync \
  -H "Content-Type: application/json" \
  -d '{"source": "s3://test-bucket/", "destination": "s3://dest-bucket/"}'

# 5. View metrics and traces
# Use Grafana dashboards and Jaeger UI
```

## Configuration

### Environment Variables

```bash
# Prefect Configuration
PREFECT_API_URL=http://localhost:4200/api
PREFECT_LOGGING_LEVEL=INFO

# MinIO Configuration
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=password123
MINIO_ENDPOINT=http://localhost:9000

# OpenTelemetry Configuration
OTEL_EXPORTER_JAEGER_ENDPOINT=http://localhost:14268/api/traces
OTEL_SERVICE_NAME=crypto-lakehouse-local
```

### Resource Limits

```yaml
# Local resource constraints
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 1Gi
```

## Troubleshooting

### Common Issues

1. **k3s not starting**
   ```bash
   sudo systemctl status k3s
   sudo journalctl -u k3s
   ```

2. **Services not accessible**
   ```bash
   kubectl get pods --all-namespaces
   kubectl port-forward --help
   ```

3. **Storage issues**
   ```bash
   kubectl get pv,pvc
   ls -la ./data/
   ```

4. **Performance issues**
   ```bash
   docker stats
   kubectl top nodes
   kubectl top pods
   ```

## Cleanup

```bash
# Stop all services
./scripts/cleanup.sh

# Or manual cleanup
kubectl delete --all deployments,services,pods --all-namespaces
sudo /usr/local/bin/k3s-uninstall.sh

# Clean data
sudo rm -rf ./data/
```

## Next Steps

1. **Production Migration**: Use configurations as basis for production deployment
2. **Performance Tuning**: Optimize based on local testing results
3. **Integration Testing**: Validate workflows end-to-end
4. **Observability Enhancement**: Add custom metrics and alerts

---

**Status**: 🚧 **In Development**  
*Local development environment for crypto lakehouse platform with k3s, MinIO, Prefect, and OpenTelemetry observability.*