#!/bin/bash

# Crypto Lakehouse Platform - Unified Infrastructure Deployment Script
# Hive Mind Integration | Specs-Driven Flow Implementation
# Version: 1.0.0 | Production Ready

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_MODE="${1:-docker-compose}"
ENVIRONMENT="${2:-development}"

# Hive Mind Banner
echo -e "${BLUE}"
echo "🧠 ═══════════════════════════════════════════════════════════════"
echo "   HIVE MIND COLLECTIVE INTELLIGENCE INFRASTRUCTURE DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}📌 Deployment Mode: ${DEPLOYMENT_MODE}${NC}"
echo -e "${GREEN}🎯 Environment: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}👑 Queen Coordinator: Infrastructure Orchestration${NC}"
echo ""

# Function: Log with timestamp
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Function: Check dependencies
check_dependencies() {
    log "🔍 Checking dependencies..."
    
    case $DEPLOYMENT_MODE in
        "docker-compose")
            command -v docker >/dev/null 2>&1 || error "Docker not found"
            command -v docker-compose >/dev/null 2>&1 || error "Docker Compose not found"
            ;;
        "k3s")
            command -v kubectl >/dev/null 2>&1 || error "kubectl not found"
            command -v k3s >/dev/null 2>&1 || warn "k3s not found - will attempt installation"
            ;;
        *)
            error "Unknown deployment mode: $DEPLOYMENT_MODE"
            ;;
    esac
    
    log "✅ Dependencies validated"
}

# Function: Setup directories
setup_directories() {
    log "📁 Setting up directories..."
    
    # Create required directories
    mkdir -p "$PROJECT_ROOT/config/"{postgres,prometheus,grafana/dashboards,grafana/provisioning,otel,s5cmd,prefect}
    mkdir -p "$PROJECT_ROOT/data/"{minio,postgres,prometheus,grafana,jaeger}
    mkdir -p "$PROJECT_ROOT/logs/"{prefect,s5cmd,postgres,grafana}
    mkdir -p "$PROJECT_ROOT/docker/s5cmd-service"
    mkdir -p "$PROJECT_ROOT/flows"
    mkdir -p "$PROJECT_ROOT/notebooks"
    
    log "✅ Directories created"
}

# Function: Generate configuration files
generate_configs() {
    log "⚙️ Generating configuration files..."
    
    # PostgreSQL initialization
    cat > "$PROJECT_ROOT/config/postgres/init.sql" << 'EOF'
-- Crypto Lakehouse Platform - PostgreSQL Initialization
-- Hive Mind Integration

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create additional databases
CREATE DATABASE metrics;
CREATE DATABASE observability;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE prefect TO prefect;
GRANT ALL PRIVILEGES ON DATABASE metrics TO prefect;
GRANT ALL PRIVILEGES ON DATABASE observability TO prefect;

-- Create tables for custom metrics
\c metrics;
CREATE TABLE IF NOT EXISTS hive_mind_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    service_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    tags JSONB DEFAULT '{}'::jsonb
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_hive_metrics_timestamp ON hive_mind_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_hive_metrics_service ON hive_mind_metrics(service_name);
EOF

    # OpenTelemetry Collector Configuration
    cat > "$PROJECT_ROOT/config/otel/otel-collector.yaml" << 'EOF'
# OpenTelemetry Collector Configuration
# Hive Mind Observability Integration

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins:
            - "http://localhost:*"
            - "http://127.0.0.1:*"
  
  prometheus:
    config:
      scrape_configs:
        - job_name: 'otel-collector'
          static_configs:
            - targets: ['localhost:8888']
        
        - job_name: 'prefect-server'
          static_configs:
            - targets: ['prefect-server:4200']
          metrics_path: '/api/admin/metrics'
        
        - job_name: 'minio'
          static_configs:
            - targets: ['minio:9000']
          metrics_path: '/minio/v2/metrics/cluster'
        
        - job_name: 's5cmd-service'
          static_configs:
            - targets: ['s5cmd-service:8080']
          metrics_path: '/metrics'

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  
  memory_limiter:
    limit_mib: 256
  
  resource:
    attributes:
      - key: hive.mind.deployment
        value: "crypto-lakehouse"
        action: insert
      - key: hive.mind.environment
        value: "${ENVIRONMENT}"
        action: insert

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  
  prometheus:
    endpoint: "0.0.0.0:8889"
    namespace: "crypto_lakehouse"
    const_labels:
      deployment: "hive-mind"
  
  logging:
    loglevel: info

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [jaeger, logging]
    
    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, resource, batch]
      exporters: [prometheus]
  
  extensions: [health_check]
EOF

    # Prometheus Configuration  
    cat > "$PROJECT_ROOT/config/prometheus/prometheus.yml" << 'EOF'
# Prometheus Configuration
# Hive Mind Collective Intelligence Monitoring

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    hive_mind_deployment: 'crypto-lakehouse'
    environment: '${ENVIRONMENT}'

rule_files:
  - "hive_mind_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
    scrape_interval: 10s
  
  - job_name: 'prefect-server'
    static_configs:
      - targets: ['prefect-server:4200']
    metrics_path: '/api/admin/metrics'
    scrape_interval: 30s
  
  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
    metrics_path: '/minio/v2/metrics/cluster'
    scrape_interval: 30s
  
  - job_name: 's5cmd-service'
    static_configs:
      - targets: ['s5cmd-service:8080']
    metrics_path: '/metrics'
    scrape_interval: 10s
  
  - job_name: 'docker-containers'
    static_configs:
      - targets: ['host.docker.internal:9323']
    scrape_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []
EOF

    # s5cmd Service Dockerfile
    cat > "$PROJECT_ROOT/docker/s5cmd-service/Dockerfile" << 'EOF'
# s5cmd Service Container
# High-Performance S3 Operations with OpenTelemetry

FROM golang:1.21-alpine AS builder

# Install s5cmd
RUN apk add --no-cache git ca-certificates && \
    go install github.com/peak/s5cmd/v2@latest

FROM python:3.11-alpine

# Install s5cmd binary from builder
COPY --from=builder /go/bin/s5cmd /usr/local/bin/s5cmd

# Install Python dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    opentelemetry-api==1.21.0 \
    opentelemetry-sdk==1.21.0 \
    opentelemetry-exporter-otlp==1.21.0 \
    opentelemetry-instrumentation-fastapi==0.42b0 \
    prometheus-client==0.19.0 \
    boto3==1.34.0

WORKDIR /app

# Copy application code
COPY app.py requirements.txt ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
EOF

    # s5cmd Service Application
    cat > "$PROJECT_ROOT/docker/s5cmd-service/app.py" << 'EOF'
"""
s5cmd Service - High-Performance S3 Operations
Hive Mind Integration with OpenTelemetry
"""

import os
import subprocess
import json
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import prometheus_client
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Initialize OpenTelemetry
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure OTLP exporters
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
span_processor = BatchSpanProcessor(span_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Metrics setup
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
    export_interval_millis=30000
)
metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
meter = metrics.get_meter(__name__)

# Prometheus metrics
operations_total = Counter('s5cmd_operations_total', 'Total s5cmd operations', ['operation', 'status'])
operation_duration = Histogram('s5cmd_operation_duration_seconds', 'Duration of s5cmd operations', ['operation'])
active_operations = Gauge('s5cmd_active_operations', 'Number of active s5cmd operations')

# FastAPI app
app = FastAPI(
    title="s5cmd Service",
    description="High-Performance S3 Operations with Hive Mind Integration",
    version="1.0.0"
)

# Instrument FastAPI
FastAPIInstrumentor.instrument_app(app)

class SyncRequest(BaseModel):
    source: str
    destination: str
    options: Optional[Dict[str, Any]] = {}

class OperationResult(BaseModel):
    success: bool
    message: str
    duration: float
    bytes_transferred: Optional[int] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test s5cmd availability
        result = subprocess.run(["s5cmd", "version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {"status": "healthy", "s5cmd_version": result.stdout.strip()}
        else:
            raise HTTPException(status_code=503, detail="s5cmd not available")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return JSONResponse(
        content=generate_latest().decode(),
        media_type="text/plain"
    )

@app.post("/sync", response_model=OperationResult)
async def sync_operation(request: SyncRequest, background_tasks: BackgroundTasks):
    """Execute s5cmd sync operation"""
    with tracer.start_as_current_span("s5cmd_sync") as span:
        span.set_attribute("source", request.source)
        span.set_attribute("destination", request.destination)
        
        active_operations.inc()
        start_time = time.time()
        
        try:
            # Build s5cmd command
            cmd = ["s5cmd", "sync"]
            
            # Add options
            if request.options.get("delete", False):
                cmd.append("--delete")
            if request.options.get("dry_run", False):
                cmd.append("--dry-run")
            
            cmd.extend([request.source, request.destination])
            
            # Execute command
            with operation_duration.labels(operation="sync").time():
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                operations_total.labels(operation="sync", status="success").inc()
                span.set_attribute("success", True)
                
                return OperationResult(
                    success=True,
                    message="Sync completed successfully",
                    duration=duration
                )
            else:
                operations_total.labels(operation="sync", status="error").inc()
                span.set_attribute("success", False)
                span.set_attribute("error", result.stderr)
                
                raise HTTPException(
                    status_code=500,
                    detail=f"s5cmd sync failed: {result.stderr}"
                )
                
        except subprocess.TimeoutExpired:
            operations_total.labels(operation="sync", status="timeout").inc()
            span.set_attribute("success", False)
            span.set_attribute("error", "timeout")
            
            raise HTTPException(
                status_code=408,
                detail="Sync operation timed out"
            )
        except Exception as e:
            operations_total.labels(operation="sync", status="error").inc()
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            
            raise HTTPException(
                status_code=500,
                detail=f"Sync operation failed: {str(e)}"
            )
        finally:
            active_operations.dec()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
EOF

    # s5cmd Service Requirements
    cat > "$PROJECT_ROOT/docker/s5cmd-service/requirements.txt" << 'EOF'
fastapi==0.104.1
uvicorn==0.24.0
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp==1.21.0
opentelemetry-instrumentation-fastapi==0.42b0
prometheus-client==0.19.0
boto3==1.34.0
pydantic==2.5.0
EOF

    log "✅ Configuration files generated"
}

# Function: Deploy with Docker Compose
deploy_docker_compose() {
    log "🐳 Deploying with Docker Compose..."
    
    cd "$PROJECT_ROOT"
    
    # Build custom images
    log "🔨 Building custom s5cmd service image..."
    docker build -t crypto-lakehouse/s5cmd-service:latest ./docker/s5cmd-service/
    
    # Start services
    log "🚀 Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log "⏳ Waiting for services to be ready..."
    sleep 30
    
    # Health checks
    check_service_health "MinIO" "http://localhost:9000/minio/health/live"
    check_service_health "Prefect Server" "http://localhost:4200/api/health"
    check_service_health "s5cmd Service" "http://localhost:8080/health"
    check_service_health "Prometheus" "http://localhost:9090/-/ready"
    check_service_health "Grafana" "http://localhost:3000/api/health"
    
    log "✅ Docker Compose deployment completed"
}

# Function: Deploy with K3s
deploy_k3s() {
    log "☸️ Deploying with K3s..."
    
    # Install K3s if needed
    if ! command -v k3s >/dev/null 2>&1; then
        log "📦 Installing K3s..."
        curl -sfL https://get.k3s.io | sh -
        sleep 10
    fi
    
    # Apply manifests
    log "🚀 Applying K3s manifests..."
    kubectl apply -f "$PROJECT_ROOT/k3s-production.yml"
    kubectl apply -f "$PROJECT_ROOT/k3s-observability.yml"
    
    # Wait for deployments
    log "⏳ Waiting for deployments to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment --all -n crypto-lakehouse
    kubectl wait --for=condition=available --timeout=300s deployment --all -n crypto-lakehouse-monitoring
    
    log "✅ K3s deployment completed"
}

# Function: Check service health
check_service_health() {
    local service_name="$1"
    local health_url="$2"
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$health_url" >/dev/null 2>&1; then
            log "✅ $service_name is healthy"
            return 0
        fi
        
        warn "$service_name not ready (attempt $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done
    
    error "$service_name failed to become healthy"
}

# Function: Display deployment summary
show_deployment_summary() {
    echo ""
    echo -e "${BLUE}🧠 ═══════════════════════════════════════════════════════════════"
    echo "   HIVE MIND DEPLOYMENT COMPLETE - ACCESS INFORMATION"
    echo "═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    if [ "$DEPLOYMENT_MODE" = "docker-compose" ]; then
        echo -e "${GREEN}🎯 Service Access URLs:${NC}"
        echo "   • Prefect UI:     http://localhost:4200"
        echo "   • MinIO Console:  http://localhost:9001 (admin/password123)"
        echo "   • s5cmd Service:  http://localhost:8080"
        echo "   • Jaeger UI:      http://localhost:16686"
        echo "   • Prometheus:     http://localhost:9090"
        echo "   • Grafana:        http://localhost:3000 (admin/admin123)"
        echo "   • pgAdmin:        http://localhost:5050"
        echo "   • Jupyter:        http://localhost:8888 (token: crypto-lakehouse-token)"
        echo ""
        echo -e "${GREEN}💾 Database Connections:${NC}"
        echo "   • PostgreSQL:     localhost:5432 (prefect/prefect123/prefect)"
        echo "   • Redis:          localhost:6379"
        echo ""
        echo -e "${GREEN}🔧 Management Commands:${NC}"
        echo "   • View logs:      docker-compose logs -f [service]"
        echo "   • Stop services:  docker-compose down"
        echo "   • Restart:        docker-compose restart [service]"
    else
        echo -e "${GREEN}☸️ K3s Cluster Information:${NC}"
        echo "   • Cluster status: kubectl get nodes"
        echo "   • Pod status:     kubectl get pods --all-namespaces"
        echo "   • Port forward:   kubectl port-forward -n crypto-lakehouse svc/prefect-server 4200:4200"
        echo ""
        echo -e "${GREEN}🔧 Management Commands:${NC}"
        echo "   • View pods:      kubectl get pods -n crypto-lakehouse"
        echo "   • View logs:      kubectl logs -f deployment/[service] -n crypto-lakehouse"
        echo "   • Scale service:  kubectl scale deployment/[service] --replicas=N -n crypto-lakehouse"
    fi
    
    echo ""
    echo -e "${GREEN}📊 Monitoring & Observability:${NC}"
    echo "   • All services instrumented with OpenTelemetry"
    echo "   • Distributed tracing available in Jaeger"
    echo "   • Metrics collection via Prometheus"
    echo "   • Custom dashboards in Grafana"
    echo ""
    echo -e "${GREEN}🚀 Next Steps:${NC}"
    echo "   1. Configure Prefect workflows"
    echo "   2. Set up MinIO buckets"
    echo "   3. Test s5cmd operations"
    echo "   4. Review monitoring dashboards"
    echo ""
    
    log "🎉 Hive Mind infrastructure deployment successful!"
}

# Main execution
main() {
    log "🧠 Starting Hive Mind Infrastructure Deployment..."
    
    check_dependencies
    setup_directories
    generate_configs
    
    case $DEPLOYMENT_MODE in
        "docker-compose")
            deploy_docker_compose
            ;;
        "k3s")
            deploy_k3s
            ;;
    esac
    
    show_deployment_summary
}

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <deployment-mode> [environment]"
    echo ""
    echo "Deployment modes:"
    echo "  docker-compose  - Deploy using Docker Compose (default)"
    echo "  k3s            - Deploy using K3s Kubernetes"
    echo ""
    echo "Environments:"
    echo "  development    - Development environment (default)"
    echo "  staging        - Staging environment"
    echo "  production     - Production environment"
    echo ""
    echo "Examples:"
    echo "  $0 docker-compose development"
    echo "  $0 k3s production"
    exit 0
fi

# Execute main function
main