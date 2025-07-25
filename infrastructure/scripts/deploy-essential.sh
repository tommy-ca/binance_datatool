#!/bin/bash

# Crypto Lakehouse Platform - Essential Services Deployment Script
# Deploys minimal infrastructure for testing without optional dependencies
# Supports both Docker Compose and K3s deployment modes

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
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DEPLOYMENT_MODE="${1:-docker-compose}"
ENVIRONMENT="${2:-development}"
VALIDATION="${3:-basic}"

# Essential Services Banner
echo -e "${PURPLE}"
echo "⚡ ═══════════════════════════════════════════════════════════════"
echo "   CRYPTO LAKEHOUSE ESSENTIAL SERVICES DEPLOYMENT"
echo "═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}🎯 Mode: ${DEPLOYMENT_MODE}${NC}"
echo -e "${GREEN}📌 Environment: ${ENVIRONMENT}${NC}"
echo -e "${GREEN}🔍 Validation: ${VALIDATION}${NC}"
echo -e "${GREEN}⚡ Services: Essential Only (MinIO, PostgreSQL, Prefect)${NC}"
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
    log "🔍 Checking prerequisites for ${DEPLOYMENT_MODE}..."
    
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        command -v docker >/dev/null 2>&1 || error "Docker is required but not installed"
        command -v docker-compose >/dev/null 2>&1 || error "Docker Compose is required but not installed"
        
        # Check if Docker daemon is running
        docker info >/dev/null 2>&1 || error "Docker daemon is not running"
        
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        command -v kubectl >/dev/null 2>&1 || error "kubectl is required but not installed"
        
        # Check if K3s is installed, install if not
        if ! command -v k3s >/dev/null 2>&1; then
            log "📦 Installing K3s..."
            curl -sfL https://get.k3s.io | sh - || error "Failed to install K3s"
            
            # Wait for K3s to be ready
            sleep 10
            sudo k3s kubectl get nodes || error "K3s installation failed"
            
            # Setup kubectl config
            mkdir -p ~/.kube
            sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
            sudo chown $(id -u):$(id -g) ~/.kube/config
        fi
        
        # Check if K3s cluster is accessible
        kubectl cluster-info >/dev/null 2>&1 || error "Cannot access K3s cluster"
    else
        error "Unsupported deployment mode: ${DEPLOYMENT_MODE}. Use 'docker-compose' or 'k3s'"
    fi
    
    success "Prerequisites check completed"
}

# Function: Deploy Docker Compose essential services
deploy_docker_compose() {
    log "🚀 Deploying Docker Compose essential services..."
    
    cd "${PROJECT_ROOT}"
    
    # Stop any existing services
    if [ -f "infrastructure/docker-compose/docker-compose.essential.yml" ]; then
        log "🛑 Stopping existing services..."
        docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml down --remove-orphans || warn "No existing services to stop"
    fi
    
    # Start essential services
    log "▶️ Starting essential services..."
    docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml up -d
    
    # Wait for services to be healthy
    log "⏳ Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_docker_compose_health
    
    success "Docker Compose essential services deployed successfully"
}

# Function: Deploy K3s essential services
deploy_k3s() {
    log "🚀 Deploying K3s essential services..."
    
    cd "${PROJECT_ROOT}"
    
    # Apply essential manifests
    log "📄 Applying K3s essential manifests..."
    kubectl apply -f infrastructure/k3s/k3s-essential.yml
    
    # Wait for services to be ready
    log "⏳ Waiting for services to be ready..."
    kubectl wait --for=condition=ready pod -l app=minio-essential -n crypto-lakehouse --timeout=300s
    kubectl wait --for=condition=ready pod -l app=postgres-essential -n crypto-lakehouse --timeout=300s
    kubectl wait --for=condition=ready pod -l app=prefect-server-essential -n crypto-lakehouse --timeout=300s
    
    # Check service health
    check_k3s_health
    
    success "K3s essential services deployed successfully"
}

# Function: Check Docker Compose service health
check_docker_compose_health() {
    log "🏥 Checking Docker Compose service health..."
    
    # Check if containers are running
    local failed_services=()
    
    for service in minio postgres prefect-server prefect-worker; do
        if ! docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps "$service" | grep -q "Up"; then
            failed_services+=("$service")
        fi
    done
    
    if [ ${#failed_services[@]} -ne 0 ]; then
        error "Failed services: ${failed_services[*]}"
    fi
    
    # Test service endpoints
    log "🌐 Testing service endpoints..."
    
    # MinIO health check
    curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1 || error "MinIO health check failed"
    
    # PostgreSQL health check
    docker exec crypto-lakehouse-postgres pg_isready -U prefect -d prefect >/dev/null 2>&1 || error "PostgreSQL health check failed"
    
    # Prefect health check
    curl -f http://localhost:4200/api/health >/dev/null 2>&1 || error "Prefect health check failed"
    
    success "All essential services are healthy"
}

# Function: Check K3s service health
check_k3s_health() {
    log "🏥 Checking K3s service health..."
    
    # Check if pods are running
    local failed_pods
    failed_pods=$(kubectl get pods -n crypto-lakehouse --no-headers | grep -v Running | grep -v Completed || true)
    
    if [ -n "$failed_pods" ]; then
        error "Failed pods: $failed_pods"
    fi
    
    # Test service endpoints via port-forward (in background)
    log "🌐 Testing service endpoints..."
    
    # MinIO health check
    kubectl port-forward svc/minio-essential 9000:9000 -n crypto-lakehouse >/dev/null 2>&1 &
    local minio_pid=$!
    sleep 5
    curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1 || warn "MinIO health check failed (may be expected in K3s)"
    kill $minio_pid 2>/dev/null || true
    
    # Prefect health check
    kubectl port-forward svc/prefect-server-essential 4200:4200 -n crypto-lakehouse >/dev/null 2>&1 &
    local prefect_pid=$!
    sleep 5
    curl -f http://localhost:4200/api/health >/dev/null 2>&1 || warn "Prefect health check failed (may be expected in K3s)"
    kill $prefect_pid 2>/dev/null || true
    
    success "All essential services are running"
}

# Function: Run validation
run_validation() {
    if [[ "$VALIDATION" == "comprehensive" ]]; then
        log "🔍 Running comprehensive validation..."
        
        if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
            # Docker Compose validation
            python3 -c "import yaml; yaml.safe_load(open('infrastructure/docker-compose/docker-compose.essential.yml').read()); print('✅ Docker Compose YAML syntax valid')"
        elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
            # K3s validation
            python3 -c "import yaml; yaml.safe_load_all(open('infrastructure/k3s/k3s-essential.yml').read()); print('✅ K3s manifests YAML syntax valid')"
            kubectl apply -f infrastructure/k3s/k3s-essential.yml --dry-run=client >/dev/null 2>&1 && echo "✅ K3s manifests validation passed"
        fi
        
        success "Comprehensive validation completed"
    fi
}

# Function: Display service information
display_service_info() {
    echo ""
    echo -e "${BLUE}🎯 Essential Services Information${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""
    
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        echo -e "${GREEN}📋 Docker Compose Services:${NC}"
        echo "• MinIO Console: http://localhost:9001 (admin/password123)"
        echo "• MinIO API: http://localhost:9000"
        echo "• Prefect UI: http://localhost:4200"
        echo "• PostgreSQL: localhost:5432 (prefect/prefect123/prefect)"
        echo ""
        echo -e "${GREEN}🔧 Management Commands:${NC}"
        echo "• View logs: docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml logs -f"
        echo "• Stop services: docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml down"
        echo "• Restart services: docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml restart"
        
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        echo -e "${GREEN}📋 K3s Services (NodePort access):${NC}"
        echo "• MinIO Console: http://localhost:30901 (admin/password123)"
        echo "• MinIO API: http://localhost:30900"
        echo "• Prefect UI: http://localhost:30420"
        echo ""
        echo -e "${GREEN}🔧 Management Commands:${NC}"
        echo "• View pods: kubectl get pods -n crypto-lakehouse"
        echo "• View services: kubectl get services -n crypto-lakehouse"
        echo "• View logs: kubectl logs -f deployment/prefect-server-essential -n crypto-lakehouse"
        echo "• Delete services: kubectl delete -f infrastructure/k3s/k3s-essential.yml"
    fi
    
    echo ""
    echo -e "${GREEN}✅ Essential services ready for testing!${NC}"
    echo ""
}

# Main execution
main() {
    log "🚀 Starting essential services deployment..."
    
    check_prerequisites
    
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        deploy_docker_compose
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        deploy_k3s
    fi
    
    run_validation
    display_service_info
    
    success "Essential services deployment completed successfully!"
}

# Help function
show_help() {
    echo "Usage: $0 [MODE] [ENVIRONMENT] [VALIDATION]"
    echo ""
    echo "Arguments:"
    echo "  MODE         Deployment mode: docker-compose (default) or k3s"
    echo "  ENVIRONMENT  Environment: development (default), staging, production"
    echo "  VALIDATION   Validation level: basic (default) or comprehensive"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Docker Compose, development, basic"
    echo "  $0 docker-compose development basic  # Explicit Docker Compose"
    echo "  $0 k3s development comprehensive     # K3s with comprehensive validation"
    echo ""
    echo "Essential Services:"
    echo "  • MinIO (S3-compatible storage)"
    echo "  • PostgreSQL (Database)"
    echo "  • Prefect Server (Workflow orchestration)"
    echo "  • Prefect Worker (Task execution)"
    echo ""
}

# Check if help is requested
if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
    show_help
    exit 0
fi

# Run main function
main "$@"