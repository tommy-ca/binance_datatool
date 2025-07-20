#!/bin/bash

# Local k3s Cluster Setup Script
# Crypto Lakehouse Local Development Environment
# Version: 1.0.0
# Date: 2025-07-20

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
K3S_VERSION="v1.28.3+k3s2"
CLUSTER_NAME="crypto-lakehouse-local"
DATA_DIR="$PROJECT_ROOT/data"
CONFIG_DIR="$PROJECT_ROOT/config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Check if running as root for k3s installation
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        warn "Running as root. k3s will be installed system-wide."
    else
        info "Running as non-root user. Will use sudo for k3s installation."
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if k3s is already installed
    if command -v k3s &> /dev/null; then
        local current_version=$(k3s --version | grep -o "k3s version [^+]*" | cut -d' ' -f3)
        info "k3s already installed: $current_version"
        
        # Check if k3s is running
        if sudo systemctl is-active --quiet k3s; then
            info "k3s is already running"
            return 0
        fi
    fi

    # Check available disk space (minimum 10GB)
    local available_space=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    local required_space=10485760  # 10GB in KB
    
    if [[ $available_space -lt $required_space ]]; then
        error "Insufficient disk space. Required: 10GB, Available: $((available_space/1024/1024))GB"
    fi

    # Check memory (minimum 4GB)
    local total_memory=$(free -m | awk 'NR==2{print $2}')
    if [[ $total_memory -lt 4096 ]]; then
        warn "Low memory detected: ${total_memory}MB. Recommended: 4GB+"
    fi

    # Check if Docker is installed (optional but recommended)
    if ! command -v docker &> /dev/null; then
        warn "Docker not found. Installing Docker is recommended for building custom images."
    fi

    log "Prerequisites check completed"
}

# Create directory structure
create_directories() {
    log "Creating directory structure..."

    local dirs=(
        "$DATA_DIR"
        "$DATA_DIR/minio"
        "$DATA_DIR/postgres"
        "$DATA_DIR/redis"
        "$DATA_DIR/prometheus"
        "$DATA_DIR/grafana"
        "$CONFIG_DIR"
        "$PROJECT_ROOT/manifests"
        "$PROJECT_ROOT/docker"
    )

    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            info "Created directory: $dir"
        fi
    done

    # Set proper permissions for data directories
    sudo chown -R $USER:$USER "$DATA_DIR"
    chmod -R 755 "$DATA_DIR"

    log "Directory structure created successfully"
}

# Install k3s
install_k3s() {
    log "Installing k3s cluster..."

    # Create k3s configuration
    cat > /tmp/k3s-config.yaml << EOF
cluster-init: true
write-kubeconfig-mode: "0644"
disable:
  - traefik        # We'll use our own ingress
  - servicelb      # Use NodePort services instead
  - metrics-server # We'll install our own
data-dir: $DATA_DIR/k3s
node-name: $CLUSTER_NAME-node
cluster-cidr: "10.42.0.0/16"
service-cidr: "10.43.0.0/16"
node-taint:
  - "node.kubernetes.io/disk-pressure:NoSchedule"
EOF

    # Install k3s
    if ! command -v k3s &> /dev/null; then
        log "Installing k3s version $K3S_VERSION..."
        curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" sh -s - server --config /tmp/k3s-config.yaml
    else
        info "k3s already installed, starting service..."
        sudo systemctl start k3s
    fi

    # Wait for k3s to be ready
    log "Waiting for k3s to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if sudo k3s kubectl get nodes | grep -q "Ready"; then
            break
        fi
        sleep 5
        ((attempt++))
    done

    if [[ $attempt -eq $max_attempts ]]; then
        error "k3s failed to start within timeout"
    fi

    log "k3s cluster is ready"
}

# Configure kubectl
configure_kubectl() {
    log "Configuring kubectl..."

    # Copy kubeconfig to user's home directory
    mkdir -p ~/.kube
    sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
    sudo chown $USER:$USER ~/.kube/config
    chmod 600 ~/.kube/config

    # Update server URL to use localhost
    sed -i 's/127.0.0.1/localhost/g' ~/.kube/config

    # Verify kubectl access
    if kubectl get nodes &> /dev/null; then
        local node_name=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
        local node_status=$(kubectl get nodes -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}')
        log "kubectl configured successfully. Node: $node_name, Status: $node_status"
    else
        error "Failed to configure kubectl"
    fi
}

# Create storage class
create_storage_class() {
    log "Creating local storage class..."

    cat > /tmp/local-storage-class.yaml << EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-storage
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: rancher.io/local-path
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
parameters:
  nodePath: $DATA_DIR/local-path-provisioner
EOF

    kubectl apply -f /tmp/local-storage-class.yaml
    
    # Remove the default local-path storage class annotation if it exists
    kubectl annotate storageclass local-path storageclass.kubernetes.io/is-default-class- --overwrite || true

    log "Local storage class created"
}

# Create namespaces
create_namespaces() {
    log "Creating namespaces..."

    local namespaces=(
        "prefect"
        "minio" 
        "s5cmd"
        "observability"
        "monitoring"
    )

    for ns in "${namespaces[@]}"; do
        cat > "/tmp/namespace-$ns.yaml" << EOF
apiVersion: v1
kind: Namespace
metadata:
  name: $ns
  labels:
    name: $ns
    environment: local
    managed-by: crypto-lakehouse
EOF
        kubectl apply -f "/tmp/namespace-$ns.yaml"
        info "Created namespace: $ns"
    done

    log "Namespaces created successfully"
}

# Install Helm (if not already installed)
install_helm() {
    if ! command -v helm &> /dev/null; then
        log "Installing Helm..."
        curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    else
        info "Helm already installed: $(helm version --short)"
    fi
}

# Setup basic network policies
setup_network_policies() {
    log "Setting up basic network policies..."

    # Allow all traffic within namespaces (for local development)
    cat > /tmp/allow-namespace-traffic.yaml << EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-namespace-traffic
  namespace: prefect
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: prefect
    - namespaceSelector:
        matchLabels:
          name: minio
    - namespaceSelector:
        matchLabels:
          name: s5cmd
    - namespaceSelector:
        matchLabels:
          name: observability
  egress:
  - {}
EOF

    # Apply to each namespace
    for ns in prefect minio s5cmd observability; do
        sed "s/namespace: prefect/namespace: $ns/" /tmp/allow-namespace-traffic.yaml | kubectl apply -f -
    done

    log "Network policies configured"
}

# Create configuration files
create_config_files() {
    log "Creating configuration files..."

    # OpenTelemetry Collector configuration
    cat > "$CONFIG_DIR/otel-config.yaml" << EOF
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
  prometheus:
    config:
      scrape_configs:
      - job_name: 'otel-collector'
        scrape_interval: 15s
        static_configs:
        - targets: ['localhost:8888', 'localhost:8889']

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  memory_limiter:
    limit_mib: 512
  resource:
    attributes:
    - key: environment
      value: local
      action: upsert

exporters:
  jaeger:
    endpoint: jaeger-collector:14250
    tls:
      insecure: true
  prometheus:
    endpoint: "0.0.0.0:8889"
  logging:
    loglevel: info

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [jaeger, logging]
    metrics:
      receivers: [otlp, prometheus]
      processors: [memory_limiter, batch, resource]
      exporters: [prometheus, logging]
EOF

    # Prometheus configuration
    cat > "$CONFIG_DIR/prometheus.yml" << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "*.rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']

  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
    - role: pod
    relabel_configs:
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
      action: keep
      regex: true
    - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
      action: replace
      target_label: __metrics_path__
      regex: (.+)

  - job_name: 'prefect-server'
    static_configs:
      - targets: ['prefect-server.prefect:4200']
    metrics_path: '/metrics'

  - job_name: 'minio'
    static_configs:
      - targets: ['minio.minio:9000']
    metrics_path: '/minio/v2/metrics/cluster'

  - job_name: 's5cmd-executor'
    static_configs:
      - targets: ['s5cmd-executor.s5cmd:8080']
    metrics_path: '/metrics'
EOF

    log "Configuration files created"
}

# Display next steps
display_next_steps() {
    log "🎉 k3s local cluster setup completed successfully!"
    
    echo ""
    echo "📋 Next Steps:"
    echo "1. Deploy services:    ./scripts/deploy-local.sh"
    echo "2. Validate setup:     ./scripts/validate-local.sh"
    echo "3. Access services:    kubectl port-forward commands"
    echo ""
    echo "🔧 Cluster Information:"
    echo "  Cluster Name: $CLUSTER_NAME"
    echo "  Data Directory: $DATA_DIR"
    echo "  Kubeconfig: ~/.kube/config"
    echo ""
    echo "📊 Useful Commands:"
    echo "  kubectl get nodes"
    echo "  kubectl get pods --all-namespaces"
    echo "  kubectl logs -n prefect deployment/prefect-server"
    echo ""
    echo "🛑 To stop the cluster:"
    echo "  sudo systemctl stop k3s"
    echo ""
    echo "🗑️  To completely remove:"
    echo "  ./scripts/cleanup.sh"
}

# Cleanup function for script interruption
cleanup_on_exit() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        error "Setup failed. Check the logs above for details."
        echo "To retry: ./scripts/local-setup.sh"
        echo "To cleanup: ./scripts/cleanup.sh"
    fi
    exit $exit_code
}

# Main execution
main() {
    trap cleanup_on_exit EXIT

    log "Starting k3s local cluster setup for Crypto Lakehouse..."
    
    check_permissions
    check_prerequisites
    create_directories
    install_k3s
    configure_kubectl
    install_helm
    create_storage_class
    create_namespaces
    setup_network_policies
    create_config_files
    display_next_steps

    log "✅ Local setup completed successfully!"
}

# Execute main function
main "$@"