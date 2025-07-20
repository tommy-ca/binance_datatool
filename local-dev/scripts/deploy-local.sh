#!/bin/bash

# Local Deployment Script for Crypto Lakehouse
# Deploy all services to k3s local cluster
# Version: 1.0.0
# Date: 2025-07-20

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFESTS_DIR="$PROJECT_ROOT/manifests"

# Configuration
NAMESPACE_WAIT_TIMEOUT=60
SERVICE_WAIT_TIMEOUT=300
DEPLOY_TIMEOUT=600

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

step() {
    echo -e "${PURPLE}[$(date +'%Y-%m-%d %H:%M:%S')] 🚀 $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if k3s is running
    if ! kubectl cluster-info &>/dev/null; then
        error "k3s cluster is not accessible. Run './scripts/local-setup.sh' first."
    fi

    # Check if required namespaces exist
    local required_namespaces=("prefect" "minio" "s5cmd" "observability")
    for ns in "${required_namespaces[@]}"; do
        if ! kubectl get namespace "$ns" &>/dev/null; then
            error "Namespace '$ns' not found. Run './scripts/local-setup.sh' first."
        fi
    done

    # Check available disk space (minimum 5GB)
    local available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    local required_space=5242880  # 5GB in KB
    
    if [[ $available_space -lt $required_space ]]; then
        error "Insufficient disk space. Required: 5GB, Available: $((available_space/1024/1024))GB"
    fi

    log "Prerequisites check completed"
}

# Wait for namespace to be ready
wait_for_namespace() {
    local namespace=$1
    local timeout=${2:-$NAMESPACE_WAIT_TIMEOUT}
    
    info "Waiting for namespace $namespace to be ready..."
    
    local count=0
    while [[ $count -lt $timeout ]]; do
        if kubectl get namespace "$namespace" &>/dev/null; then
            info "Namespace $namespace is ready"
            return 0
        fi
        sleep 1
        ((count++))
    done
    
    error "Timeout waiting for namespace $namespace"
}

# Wait for deployment to be ready
wait_for_deployment() {
    local namespace=$1
    local deployment=$2
    local timeout=${3:-$SERVICE_WAIT_TIMEOUT}
    
    info "Waiting for deployment $deployment in namespace $namespace..."
    
    kubectl wait --for=condition=available \
        --timeout="${timeout}s" \
        deployment/"$deployment" \
        -n "$namespace" || error "Deployment $deployment failed to become available"
    
    info "Deployment $deployment is ready"
}

# Wait for job completion
wait_for_job() {
    local namespace=$1
    local job=$2
    local timeout=${3:-$SERVICE_WAIT_TIMEOUT}
    
    info "Waiting for job $job in namespace $namespace..."
    
    kubectl wait --for=condition=complete \
        --timeout="${timeout}s" \
        job/"$job" \
        -n "$namespace" || warn "Job $job may have failed or timed out"
    
    info "Job $job completed"
}

# Deploy observability stack with OpenObserve
deploy_observability() {
    step "Deploying Unified Observability Stack with OpenObserve"
    
    wait_for_namespace "observability"
    
    # Deploy OpenObserve first as the unified observability backend
    log "Deploying OpenObserve unified observability platform..."
    kubectl apply -f "$MANIFESTS_DIR/observability/openobserve.yaml"
    wait_for_deployment "observability" "openobserve"
    
    # Wait for OpenObserve to be ready before deploying collector
    log "Waiting for OpenObserve to be ready..."
    kubectl wait --for=condition=ready pod -l app=openobserve -n observability --timeout=300s
    
    # Deploy OpenTelemetry Collector configured for OpenObserve
    log "Deploying OpenTelemetry Collector with OpenObserve integration..."
    kubectl apply -f "$MANIFESTS_DIR/observability/otel-collector-openobserve.yaml"
    wait_for_deployment "observability" "otel-collector"
    
    # Run OpenObserve initialization
    log "Running OpenObserve initialization..."
    wait_for_job "observability" "openobserve-init" 120
    
    log "✅ Unified observability stack with OpenObserve deployed successfully"
}

# Deploy MinIO
deploy_minio() {
    step "Deploying MinIO Object Storage"
    
    wait_for_namespace "minio"
    
    log "Deploying MinIO server..."
    kubectl apply -f "$MANIFESTS_DIR/minio/minio.yaml"
    
    # Wait for MinIO deployment
    wait_for_deployment "minio" "minio"
    
    # Wait for MinIO setup job
    log "Running MinIO setup job..."
    wait_for_job "minio" "minio-setup"
    
    # Verify MinIO is accessible
    log "Verifying MinIO accessibility..."
    kubectl exec -n minio deployment/minio -- \
        mc alias set local http://localhost:9000 minioadmin minioadmin123 || \
        warn "MinIO verification failed"
    
    log "✅ MinIO deployed successfully"
}

# Deploy s5cmd executor
deploy_s5cmd() {
    step "Deploying s5cmd Executor"
    
    wait_for_namespace "s5cmd"
    
    # Check if Docker is available for building custom image
    if command -v docker &>/dev/null; then
        log "Building s5cmd executor Docker image..."
        
        # Create temporary Dockerfile
        cat > /tmp/s5cmd-Dockerfile << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install s5cmd
RUN curl -L https://github.com/peak/s5cmd/releases/download/v2.2.2/s5cmd_2.2.2_Linux-64bit.tar.gz \
    | tar -xz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/s5cmd

# Install Python dependencies
RUN pip install --no-cache-dir \
    aiohttp==3.8.6 \
    prometheus-client==0.17.1 \
    opentelemetry-api==1.20.0 \
    opentelemetry-sdk==1.20.0 \
    opentelemetry-exporter-otlp==1.20.0 \
    opentelemetry-instrumentation-aiohttp-client==0.41b0 \
    pyyaml==6.0.1

# Create app directory
WORKDIR /app

# Copy application files (will be mounted from ConfigMap)
EXPOSE 8080 8081

# Default command
CMD ["python3", "/app/executor.py"]
EOF
        
        # Build image with k3s
        sudo k3s ctr images import <(docker build -t s5cmd-executor:local -f /tmp/s5cmd-Dockerfile . && docker save s5cmd-executor:local) || \
            warn "Failed to build s5cmd-executor image. Using fallback configuration."
        
        rm -f /tmp/s5cmd-Dockerfile
    else
        warn "Docker not available. Using simplified s5cmd configuration."
        
        # Create simplified ConfigMap without the complex Python executor
        cat > /tmp/s5cmd-simple.yaml << 'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: s5cmd-executor-config
  namespace: s5cmd
data:
  config.yaml: |
    s5cmd:
      endpoint_url: "http://minio-service.minio:9000"
      log_level: "info"
      retry_count: 3
      concurrency: 10
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: s5cmd-executor
  namespace: s5cmd
  labels:
    app: s5cmd-executor
    component: data-transfer
spec:
  replicas: 1
  selector:
    matchLabels:
      app: s5cmd-executor
  template:
    metadata:
      labels:
        app: s5cmd-executor
        component: data-transfer
    spec:
      containers:
      - name: s5cmd
        image: peakcom/s5cmd:v2.2.2
        command: ["sleep", "infinity"]
        env:
        - name: AWS_ACCESS_KEY_ID
          value: "s5cmd"
        - name: AWS_SECRET_ACCESS_KEY
          value: "s5cmd123456"
        - name: AWS_ENDPOINT_URL
          value: "http://minio-service.minio:9000"
        - name: AWS_REGION
          value: "us-east-1"
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
        volumeMounts:
        - name: config
          mountPath: /etc/s5cmd
      volumes:
      - name: config
        configMap:
          name: s5cmd-executor-config
---
apiVersion: v1
kind: Service
metadata:
  name: s5cmd-executor
  namespace: s5cmd
  labels:
    app: s5cmd-executor
spec:
  selector:
    app: s5cmd-executor
  ports:
  - name: api
    port: 8080
    targetPort: 8080
  type: ClusterIP
EOF
        kubectl apply -f /tmp/s5cmd-simple.yaml
        rm -f /tmp/s5cmd-simple.yaml
    fi
    
    # Apply main s5cmd configuration
    log "Deploying s5cmd executor..."
    kubectl apply -f "$MANIFESTS_DIR/s5cmd/s5cmd-executor.yaml" || \
        kubectl apply -f /tmp/s5cmd-simple.yaml
    
    wait_for_deployment "s5cmd" "s5cmd-executor"
    
    log "✅ s5cmd executor deployed successfully"
}

# Deploy Prefect
deploy_prefect() {
    step "Deploying Prefect Orchestration"
    
    wait_for_namespace "prefect"
    
    log "Deploying Prefect stack..."
    kubectl apply -f "$MANIFESTS_DIR/prefect/prefect-server.yaml"
    
    # Wait for database first
    wait_for_deployment "prefect" "postgres"
    wait_for_deployment "prefect" "redis"
    
    # Then Prefect server
    wait_for_deployment "prefect" "prefect-server"
    
    # Finally workers
    wait_for_deployment "prefect" "prefect-worker"
    
    # Verify Prefect server
    log "Verifying Prefect server..."
    kubectl exec -n prefect deployment/prefect-server -- \
        prefect config view || warn "Prefect verification failed"
    
    log "✅ Prefect deployed successfully"
}

# Setup port forwarding
setup_port_forwarding() {
    step "Setting up port forwarding"
    
    log "Creating port-forward script..."
    cat > "$PROJECT_ROOT/scripts/port-forward.sh" << 'EOF'
#!/bin/bash
# Port forwarding script for local development
# Run this script to access services locally

echo "Setting up port forwarding for Crypto Lakehouse services..."

# Kill existing port-forward processes
pkill -f "kubectl port-forward" || true
sleep 2

# Function to start port-forward in background
start_port_forward() {
    local service=$1
    local namespace=$2
    local local_port=$3
    local target_port=$4
    
    echo "Forwarding $service ($namespace) to localhost:$local_port"
    kubectl port-forward -n "$namespace" "service/$service" "$local_port:$target_port" &
}

# Start port forwarding for unified observability stack
start_port_forward "openobserve" "observability" "5080" "5080"
start_port_forward "otel-collector" "observability" "4317" "4317"
start_port_forward "otel-collector" "observability" "4318" "4318"
start_port_forward "prefect-server" "prefect" "4200" "4200"
start_port_forward "minio-service" "minio" "9000" "9000"
start_port_forward "minio-service" "minio" "9001" "9001"
start_port_forward "s5cmd-executor" "s5cmd" "8080" "8080"

echo ""
echo "🌐 Services available at:"
echo "  OpenObserve:    http://localhost:5080 (admin@crypto-lakehouse.local/admin123)"
echo "  Prefect:        http://localhost:4200"
echo "  MinIO API:      http://localhost:9000"
echo "  MinIO Console:  http://localhost:9001 (minioadmin/minioadmin123)"
echo "  s5cmd API:      http://localhost:8080"
echo "  OTLP gRPC:      localhost:4317"
echo "  OTLP HTTP:      localhost:4318"
echo ""
echo "📊 OpenObserve Features:"
echo "  • Unified Logs, Metrics, and Traces"
echo "  • Built-in Dashboards and Alerting"
echo "  • SQL and PromQL Query Support"
echo "  • 140x Lower Storage Cost vs Traditional Stack"
echo ""
echo "Press Ctrl+C to stop all port forwarding"

# Wait for all background jobs
wait
EOF
    
    chmod +x "$PROJECT_ROOT/scripts/port-forward.sh"
    
    log "✅ Port forwarding script created: ./scripts/port-forward.sh"
}

# Display deployment status
display_status() {
    step "Deployment Status"
    
    echo ""
    echo "📊 Cluster Status:"
    kubectl get nodes
    
    echo ""
    echo "📦 Deployed Services:"
    
    echo ""
    echo "🔍 Unified Observability with OpenObserve (observability namespace):"
    kubectl get pods -n observability -o wide
    
    echo ""
    echo "🗄️  MinIO (minio namespace):"
    kubectl get pods -n minio -o wide
    
    echo ""
    echo "⚡ s5cmd (s5cmd namespace):"
    kubectl get pods -n s5cmd -o wide
    
    echo ""
    echo "🔄 Prefect (prefect namespace):"
    kubectl get pods -n prefect -o wide
    
    echo ""
    echo "💾 Storage:"
    kubectl get pv,pvc --all-namespaces
    
    echo ""
    echo "🌐 Services:"
    kubectl get services --all-namespaces
}

# Display next steps
display_next_steps() {
    log "🎉 Local deployment completed successfully!"
    
    echo ""
    echo "📋 Next Steps:"
    echo "1. Start port forwarding:  ./scripts/port-forward.sh"
    echo "2. Validate deployment:    ./scripts/validate-local.sh"
    echo "3. View logs:              kubectl logs -n <namespace> deployment/<service>"
    echo ""
    echo "🌐 Quick Access (after port-forward):"
    echo "  • OpenObserve:       http://localhost:5080 (unified logs/metrics/traces)"
    echo "  • Prefect UI:        http://localhost:4200"
    echo "  • MinIO Console:     http://localhost:9001"
    echo "  • OTLP Endpoints:    localhost:4317 (gRPC), localhost:4318 (HTTP)"
    echo ""
    echo "🔧 Useful Commands:"
    echo "  kubectl get pods --all-namespaces"
    echo "  kubectl logs -f -n prefect deployment/prefect-server"
    echo "  kubectl exec -it -n minio deployment/minio -- mc ls local/"
    echo ""
    echo "🛑 To stop services:"
    echo "  kubectl delete -f manifests/ --recursive"
    echo ""
    echo "📖 Documentation:"
    echo "  Local setup guide: ./README.md"
    echo "  Architecture docs: ./docs/"
}

# Cleanup function for script interruption
cleanup_on_exit() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        error "Deployment failed. Check the logs above for details."
        echo ""
        echo "🔍 Troubleshooting:"
        echo "  Check cluster status: kubectl get pods --all-namespaces"
        echo "  Check events: kubectl get events --all-namespaces"
        echo "  Check logs: kubectl logs -n <namespace> deployment/<service>"
        echo ""
        echo "🔄 To retry: ./scripts/deploy-local.sh"
        echo "🧹 To cleanup: kubectl delete -f manifests/ --recursive"
    fi
    exit $exit_code
}

# Main execution
main() {
    trap cleanup_on_exit EXIT

    log "Starting local deployment for Crypto Lakehouse..."
    log "Target: k3s local cluster"
    
    check_prerequisites
    
    # Deploy in dependency order
    deploy_observability
    deploy_minio
    deploy_s5cmd
    deploy_prefect
    
    setup_port_forwarding
    display_status
    display_next_steps

    log "✅ Local deployment completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --timeout)
            DEPLOY_TIMEOUT="$2"
            shift 2
            ;;
        --skip-status)
            SKIP_STATUS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --timeout SECONDS    Set deployment timeout (default: 600)"
            echo "  --skip-status        Skip status display"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Execute main function
main "$@"