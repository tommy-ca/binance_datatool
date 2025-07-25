#!/bin/bash

# Crypto Lakehouse Platform - K3s Local Infrastructure Deployment
# Based on K3s Local Infrastructure Specifications v3.1.0
# Integrated with existing infrastructure deployment patterns

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-development}"
VALIDATION_MODE="${2:-basic}"

# K3s Local Banner
echo -e "${PURPLE}"
echo "☸️ ═══════════════════════════════════════════════════════════════"
echo "   CRYPTO LAKEHOUSE K3S LOCAL INFRASTRUCTURE DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}📌 Environment: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}🎯 Validation: ${VALIDATION_MODE}${NC}"
echo -e "${GREEN}⚡ Mode: K3s Local Development${NC}"
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

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}"
}

# Function: Check prerequisites
check_prerequisites() {
    log "🔍 Checking K3s prerequisites..."
    
    # Check if running as root or with sudo
    if [ "$EUID" -eq 0 ]; then
        warn "Running as root - K3s will install system-wide"
    fi
    
    # Check available resources
    local total_memory=$(free -m | awk 'NR==2{printf "%.0f", $2/1024}')
    if [ "$total_memory" -lt 6 ]; then
        warn "System has ${total_memory}GB RAM - minimum 6GB recommended"
    fi
    
    local available_disk=$(df -BG / | awk 'NR==2{print $4}' | sed 's/G//')
    if [ "$available_disk" -lt 20 ]; then
        warn "Available disk space: ${available_disk}GB - minimum 20GB recommended"
    fi
    
    # Check required ports
    local required_ports=(6443 10250 30420 30900 30901 30808 30686 30909 30300)
    for port in "${required_ports[@]}"; do
        if ss -tuln | grep -q ":${port} "; then
            warn "Port $port is already in use - K3s services may conflict"
        fi
    done
    
    success "Prerequisites checked"
}

# Function: Install K3s
install_k3s() {
    log "📦 Installing K3s..."
    
    if command -v k3s >/dev/null 2>&1; then
        log "K3s already installed - checking version..."
        local k3s_version=$(k3s --version | head -n1 | awk '{print $3}')
        log "Installed K3s version: $k3s_version"
    else
        log "Installing K3s with crypto-lakehouse configuration..."
        
        # Install K3s with specific configuration for crypto-lakehouse
        curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
            --cluster-cidr=10.42.0.0/16 \
            --service-cidr=10.43.0.0/16 \
            --cluster-dns=10.43.0.10 \
            --disable=traefik \
            --disable=servicelb \
            --write-kubeconfig-mode=644 \
            --node-port-range=30000-32767 \
            --kube-apiserver-arg=request-timeout=300s \
            --kube-apiserver-arg=audit-log-maxage=7 \
            --kube-apiserver-arg=audit-log-maxbackup=3 \
            --kube-apiserver-arg=audit-log-maxsize=100" sh -
        
        # Wait for K3s to be ready
        local attempts=0
        local max_attempts=30
        
        while [ $attempts -lt $max_attempts ]; do
            if k3s kubectl get nodes 2>/dev/null | grep -q Ready; then
                success "K3s cluster is ready"
                break
            fi
            
            log "Waiting for K3s cluster to be ready (attempt $((attempts + 1))/$max_attempts)..."
            sleep 10
            ((attempts++))
        done
        
        if [ $attempts -eq $max_attempts ]; then
            error "K3s cluster failed to become ready within 5 minutes"
        fi
    fi
    
    # Configure kubectl context
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    
    # Verify cluster is working
    if ! k3s kubectl get nodes >/dev/null 2>&1; then
        error "K3s cluster is not responding"
    fi
    
    success "K3s installation completed"
}

# Function: Setup crypto-lakehouse namespace and resources
setup_namespace() {
    log "🏗️ Setting up crypto-lakehouse namespace..."
    
    # Create namespace with proper labels
    k3s kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: crypto-lakehouse
  labels:
    name: crypto-lakehouse
    version: "3.1.0"
    environment: ${ENVIRONMENT}
    infrastructure: k3s-local
---
apiVersion: v1
kind: Namespace
metadata:
  name: crypto-lakehouse-monitoring
  labels:
    name: crypto-lakehouse-monitoring
    version: "3.1.0"
    environment: ${ENVIRONMENT}
    infrastructure: k3s-local
EOF

    # Apply resource quota for development limits
    k3s kubectl apply -f - <<EOF
apiVersion: v1
kind: ResourceQuota
metadata:
  name: crypto-lakehouse-quota
  namespace: crypto-lakehouse
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
    persistentvolumeclaims: "10"
    pods: "20"
    services: "15"
EOF

    success "Namespace setup completed"
}

# Function: Deploy core infrastructure
deploy_infrastructure() {
    log "🚀 Deploying crypto-lakehouse infrastructure..."
    
    # Apply K3s local infrastructure manifest
    if [ -f "$PROJECT_ROOT/k3s-local-infrastructure.yml" ]; then
        log "Applying K3s local infrastructure manifest..."
        k3s kubectl apply -f "$PROJECT_ROOT/k3s-local-infrastructure.yml"
    else
        error "K3s local infrastructure manifest not found: $PROJECT_ROOT/k3s-local-infrastructure.yml"
    fi
    
    # Wait for deployments to be ready
    log "⏳ Waiting for deployments to be ready..."
    
    local deployments=("minio-local" "postgres-local" "redis-local" "prefect-server-local" "prefect-worker-local" "s5cmd-service-local")
    
    for deployment in "${deployments[@]}"; do
        log "Waiting for deployment: $deployment"
        
        if ! k3s kubectl wait --for=condition=available deployment "$deployment" -n crypto-lakehouse --timeout=300s; then
            warn "Deployment $deployment did not become available within 5 minutes"
            
            # Show pod status for debugging
            log "Pod status for deployment $deployment:"
            k3s kubectl get pods -l app="$deployment" -n crypto-lakehouse
            
            # Show events for debugging
            log "Recent events in crypto-lakehouse namespace:"
            k3s kubectl get events -n crypto-lakehouse --sort-by='.lastTimestamp' | tail -10
        else
            success "Deployment $deployment is ready"
        fi
    done
    
    success "Infrastructure deployment completed"
}

# Function: Deploy observability stack
deploy_observability() {
    log "📊 Deploying observability stack..."
    
    # Check if observability manifest exists
    if [ -f "$PROJECT_ROOT/k3s-local-observability.yml" ]; then
        log "Applying K3s local observability manifest..."
        k3s kubectl apply -f "$PROJECT_ROOT/k3s-local-observability.yml"
        
        # Wait for observability services
        local obs_deployments=("otel-collector-local" "jaeger-local" "prometheus-local" "grafana-local")
        
        for deployment in "${obs_deployments[@]}"; do
            if k3s kubectl get deployment "$deployment" -n crypto-lakehouse-monitoring >/dev/null 2>&1; then
                log "Waiting for observability deployment: $deployment"
                k3s kubectl wait --for=condition=available deployment "$deployment" -n crypto-lakehouse-monitoring --timeout=300s || warn "Observability deployment $deployment did not become ready"
            else
                log "Observability deployment $deployment not found - may be included in main manifest"
            fi
        done
    else
        log "No separate observability manifest found - assuming included in main manifest"
    fi
    
    success "Observability deployment completed"
}

# Function: Build custom images
build_custom_images() {
    log "🔨 Building custom s5cmd service image..."
    
    if [ -d "$PROJECT_ROOT/docker/s5cmd-service" ]; then
        # Import image to K3s if Docker is available
        if command -v docker >/dev/null 2>&1; then
            cd "$PROJECT_ROOT/docker/s5cmd-service"
            docker build -t crypto-lakehouse/s5cmd-service:latest .
            
            # Import image to K3s
            docker save crypto-lakehouse/s5cmd-service:latest | sudo k3s ctr images import -
            
            success "s5cmd service image built and imported to K3s"
        else
            warn "Docker not available - s5cmd service will use default image or may fail"
        fi
    else
        warn "s5cmd service Docker directory not found - service may use default configuration"
    fi
}

# Function: Validate deployment
validate_deployment() {
    log "🧪 Validating K3s local deployment..."
    
    local validation_passed=0
    local validation_total=0
    
    # Test 1: Check cluster health
    ((validation_total++))
    if k3s kubectl get nodes | grep -q Ready; then
        success "✅ K3s cluster is healthy"
        ((validation_passed++))
    else
        error "❌ K3s cluster is not healthy"
    fi
    
    # Test 2: Check namespaces
    ((validation_total++))
    if k3s kubectl get namespace crypto-lakehouse >/dev/null 2>&1 && k3s kubectl get namespace crypto-lakehouse-monitoring >/dev/null 2>&1; then
        success "✅ Namespaces created successfully"
        ((validation_passed++))
    else
        error "❌ Required namespaces missing"
    fi
    
    # Test 3: Check pod status
    ((validation_total++))
    local running_pods=$(k3s kubectl get pods -n crypto-lakehouse --field-selector=status.phase=Running --no-headers | wc -l)
    if [ "$running_pods" -ge 5 ]; then
        success "✅ Core services are running ($running_pods pods)"
        ((validation_passed++))
    else
        warn "❌ Not enough pods running ($running_pods pods)"
        k3s kubectl get pods -n crypto-lakehouse
    fi
    
    # Test 4: Check service accessibility
    ((validation_total++))
    local node_ip=$(k3s kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    
    if curl -f -s --connect-timeout 10 "http://${node_ip}:30420/api/health" >/dev/null 2>&1; then
        success "✅ Prefect API is accessible"
        ((validation_passed++))
    else
        warn "❌ Prefect API not accessible at http://${node_ip}:30420"
    fi
    
    # Additional validation if comprehensive mode
    if [ "$VALIDATION_MODE" = "comprehensive" ]; then
        # Test MinIO accessibility
        ((validation_total++))
        if curl -f -s --connect-timeout 10 "http://${node_ip}:30901" >/dev/null 2>&1; then
            success "✅ MinIO Console is accessible"
            ((validation_passed++))
        else
            warn "❌ MinIO Console not accessible at http://${node_ip}:30901"
        fi
        
        # Test s5cmd service
        ((validation_total++))
        if curl -f -s --connect-timeout 10 "http://${node_ip}:30808/health" >/dev/null 2>&1; then
            success "✅ s5cmd Service is accessible"
            ((validation_passed++))
        else
            warn "❌ s5cmd Service not accessible at http://${node_ip}:30808"
        fi
    fi
    
    # Calculate success rate
    local success_rate=$((validation_passed * 100 / validation_total))
    
    echo ""
    log "📊 Validation Results:"
    log "   • Tests Passed: $validation_passed/$validation_total"
    log "   • Success Rate: $success_rate%"
    
    if [ "$success_rate" -ge 80 ]; then
        success "🎉 K3s local deployment validation successful!"
        return 0
    else
        warn "⚠️ K3s local deployment has issues - check logs above"
        return 1
    fi
}

# Function: Show access information
show_access_info() {
    local node_ip=$(k3s kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    
    echo ""
    echo -e "${BLUE}☸️ ═══════════════════════════════════════════════════════════════"
    echo "   K3S LOCAL DEPLOYMENT COMPLETE - ACCESS INFORMATION"
    echo "═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    
    echo -e "${GREEN}🎯 Service Access URLs:${NC}"
    echo "   • Prefect UI:     http://${node_ip}:30420"
    echo "   • MinIO Console:  http://${node_ip}:30901 (admin/password123)"
    echo "   • s5cmd Service:  http://${node_ip}:30808"
    echo "   • Jaeger UI:      http://${node_ip}:30686"
    echo "   • Prometheus:     http://${node_ip}:30909"
    echo "   • Grafana:        http://${node_ip}:30300 (admin/admin123)"
    echo ""
    
    echo -e "${GREEN}🔧 K3s Management Commands:${NC}"
    echo "   • View pods:      k3s kubectl get pods -n crypto-lakehouse"
    echo "   • View services:  k3s kubectl get services -n crypto-lakehouse"
    echo "   • Check logs:     k3s kubectl logs -f deployment/[service] -n crypto-lakehouse"
    echo "   • Port forward:   k3s kubectl port-forward -n crypto-lakehouse svc/[service] [local-port]:[service-port]"
    echo ""
    
    echo -e "${GREEN}📊 Monitoring & Observability:${NC}"
    echo "   • All services instrumented with OpenTelemetry"
    echo "   • Distributed tracing available in Jaeger"
    echo "   • Metrics collection via Prometheus"
    echo "   • Custom dashboards in Grafana"
    echo ""
    
    echo -e "${GREEN}🚀 Next Steps:${NC}"
    echo "   1. Configure Prefect workflows at http://${node_ip}:30420"
    echo "   2. Set up MinIO buckets at http://${node_ip}:30901"
    echo "   3. Test s5cmd operations via http://${node_ip}:30808"
    echo "   4. Review monitoring dashboards"
    echo ""
    
    success "🎊 K3s local infrastructure ready for development!"
}

# Function: Cleanup on failure
cleanup_on_failure() {
    warn "🧹 Cleaning up due to deployment failure..."
    
    # Remove deployed resources
    if k3s kubectl get namespace crypto-lakehouse >/dev/null 2>&1; then
        k3s kubectl delete namespace crypto-lakehouse --ignore-not-found=true
    fi
    
    if k3s kubectl get namespace crypto-lakehouse-monitoring >/dev/null 2>&1; then
        k3s kubectl delete namespace crypto-lakehouse-monitoring --ignore-not-found=true
    fi
    
    warn "Cleanup completed - you may need to manually remove K3s installation"
    warn "To completely remove K3s, run: /usr/local/bin/k3s-uninstall.sh"
}

# Function: Main deployment orchestration
main() {
    log "☸️ Starting K3s Local Infrastructure Deployment..."
    
    # Set trap for cleanup on failure
    trap cleanup_on_failure ERR
    
    # Execute deployment steps
    check_prerequisites
    install_k3s
    setup_namespace
    build_custom_images
    deploy_infrastructure
    deploy_observability
    
    # Validate deployment
    if validate_deployment; then
        show_access_info
        success "🎉 K3s local deployment completed successfully!"
    else
        error "K3s local deployment validation failed"
    fi
    
    # Remove trap
    trap - ERR
}

# Show usage if no arguments or help requested
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "Usage: $0 [environment] [validation-mode]"
    echo ""
    echo "Environments:"
    echo "  development    - Development environment (default)"
    echo "  staging        - Staging environment"
    echo "  testing        - Testing environment"
    echo ""
    echo "Validation modes:"
    echo "  basic          - Basic health checks (default)"
    echo "  comprehensive  - Full validation including service accessibility"
    echo ""
    echo "Examples:"
    echo "  $0 development basic"
    echo "  $0 staging comprehensive"
    echo ""
    echo "Requirements:"
    echo "  - 6GB+ RAM recommended"
    echo "  - 20GB+ disk space"
    echo "  - Ports 6443, 30000-32767 available"
    echo "  - Root/sudo access for K3s installation"
    exit 0
fi

# Execute main function
main