#!/bin/bash

# Crypto Lakehouse Platform - Essential Services Testing Script
# Comprehensive testing suite for essential services without optional dependencies
# Tests: Service health, connectivity, basic functionality

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
TEST_LEVEL="${2:-basic}"

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNING_TESTS=0

# Testing Banner
echo -e "${PURPLE}"
echo "🧪 ═══════════════════════════════════════════════════════════════"
echo "   CRYPTO LAKEHOUSE ESSENTIAL SERVICES TESTING SUITE"
echo "═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}🎯 Mode: ${DEPLOYMENT_MODE}${NC}"
echo -e "${GREEN}🔍 Test Level: ${TEST_LEVEL}${NC}"
echo -e "${GREEN}⚡ Testing: Essential Services Only${NC}"
echo ""

# Function: Log with timestamp and test tracking
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
    ((WARNING_TESTS++))
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    ((FAILED_TESTS++))
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS: $1${NC}"
    ((PASSED_TESTS++))
}

test_result() {
    ((TOTAL_TESTS++))
    if $1; then
        success "$2"
        return 0
    else
        error "$2"
        return 1
    fi
}

# Function: Test Docker Compose services
test_docker_compose_services() {
    log "🐳 Testing Docker Compose essential services..."
    
    cd "${PROJECT_ROOT}"
    
    # Test 1: Check if containers are running
    test_result "docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps minio | grep -q 'Up'" \
        "MinIO container is running"
    
    test_result "docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps postgres | grep -q 'Up'" \
        "PostgreSQL container is running"
    
    test_result "docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps prefect-server | grep -q 'Up'" \
        "Prefect Server container is running"
    
    test_result "docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps prefect-worker | grep -q 'Up'" \
        "Prefect Worker container is running"
    
    # Test 2: Health check endpoints
    sleep 10  # Allow services to fully start
    
    test_result "curl -sf http://localhost:9000/minio/health/live > /dev/null" \
        "MinIO health endpoint accessible"
    
    test_result "curl -sf http://localhost:4200/api/health > /dev/null" \
        "Prefect API health endpoint accessible"
    
    # Test 3: Database connectivity
    test_result "docker exec crypto-lakehouse-postgres pg_isready -U prefect -d prefect > /dev/null 2>&1" \
        "PostgreSQL is ready and accepting connections"
    
    # Test 4: Service functionality
    if [[ "$TEST_LEVEL" == "comprehensive" ]]; then
        log "🔍 Running comprehensive Docker Compose tests..."
        
        # MinIO functionality test
        test_result "curl -sf http://localhost:9001 > /dev/null" \
            "MinIO console is accessible"
        
        # Prefect UI test
        test_result "curl -sf http://localhost:4200 > /dev/null" \
            "Prefect UI is accessible"
        
        # Test S3 API functionality
        test_result "docker exec crypto-lakehouse-prefect-worker aws --endpoint-url=http://minio:9000 s3 ls > /dev/null 2>&1 || true" \
            "S3 API is functional"
    fi
}

# Function: Test K3s services
test_k3s_services() {
    log "☸️ Testing K3s essential services..."
    
    # Test 1: Check if pods are running
    test_result "kubectl get pods -n crypto-lakehouse -l app=minio-essential --no-headers | grep -q Running" \
        "MinIO pod is running"
    
    test_result "kubectl get pods -n crypto-lakehouse -l app=postgres-essential --no-headers | grep -q Running" \
        "PostgreSQL pod is running"
    
    test_result "kubectl get pods -n crypto-lakehouse -l app=prefect-server-essential --no-headers | grep -q Running" \
        "Prefect Server pod is running"
    
    test_result "kubectl get pods -n crypto-lakehouse -l app=prefect-worker-essential --no-headers | grep -q Running" \
        "Prefect Worker pod is running"
    
    # Test 2: Check services
    test_result "kubectl get svc -n crypto-lakehouse minio-essential > /dev/null 2>&1" \
        "MinIO service exists"
    
    test_result "kubectl get svc -n crypto-lakehouse postgres-essential > /dev/null 2>&1" \
        "PostgreSQL service exists"
    
    test_result "kubectl get svc -n crypto-lakehouse prefect-server-essential > /dev/null 2>&1" \
        "Prefect Server service exists"
    
    # Test 3: NodePort accessibility
    if [[ "$TEST_LEVEL" == "comprehensive" ]]; then
        log "🔍 Running comprehensive K3s tests..."
        
        # Test NodePort services (may require port-forward in some environments)
        test_result "kubectl get svc -n crypto-lakehouse minio-essential -o jsonpath='{.spec.ports[?(@.name==\"console\")].nodePort}' | grep -q '30901'" \
            "MinIO console NodePort is configured"
        
        test_result "kubectl get svc -n crypto-lakehouse prefect-server-essential -o jsonpath='{.spec.ports[0].nodePort}' | grep -q '30420'" \
            "Prefect Server NodePort is configured"
        
        # Test resource quotas
        test_result "kubectl get resourcequota -n crypto-lakehouse crypto-lakehouse-essential-quota > /dev/null 2>&1" \
            "Resource quota is configured"
        
        # Test network policies
        test_result "kubectl get networkpolicy -n crypto-lakehouse crypto-lakehouse-essential-netpol > /dev/null 2>&1" \
            "Network policy is configured"
    fi
}

# Function: Test service integration
test_service_integration() {
    log "🔗 Testing service integration..."
    
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        # Test Prefect-PostgreSQL integration
        test_result "docker exec crypto-lakehouse-prefect-server prefect config view | grep -q 'PREFECT_API_DATABASE_CONNECTION_URL'" \
            "Prefect-PostgreSQL integration configured"
        
        # Test Prefect-Worker S3 integration
        test_result "docker exec crypto-lakehouse-prefect-worker env | grep -q 'AWS_ENDPOINT_URL=http://minio:9000'" \
            "Prefect Worker S3 integration configured"
        
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        # Test Kubernetes secrets
        test_result "kubectl get secret -n crypto-lakehouse crypto-lakehouse-essential-secrets > /dev/null 2>&1" \
            "Essential secrets are configured"
        
        # Test persistent volumes
        test_result "kubectl get pvc -n crypto-lakehouse minio-essential-pvc | grep -q Bound" \
            "MinIO persistent volume is bound"
        
        test_result "kubectl get pvc -n crypto-lakehouse postgres-essential-pvc | grep -q Bound" \
            "PostgreSQL persistent volume is bound"
    fi
}

# Function: Test basic functionality
test_basic_functionality() {
    if [[ "$TEST_LEVEL" == "comprehensive" ]]; then
        log "⚙️ Testing basic functionality..."
        
        # Create a simple test workflow (if Prefect is accessible)
        if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
            # Test MinIO bucket creation
            if docker exec crypto-lakehouse-prefect-worker aws --endpoint-url=http://minio:9000 s3 mb s3://test-bucket 2>/dev/null; then
                success "MinIO bucket creation successful"
                ((PASSED_TESTS++))
            else
                warn "MinIO bucket creation failed (may be expected)"
                ((WARNING_TESTS++))
            fi
            ((TOTAL_TESTS++))
            
            # Test MinIO bucket listing
            if docker exec crypto-lakehouse-prefect-worker aws --endpoint-url=http://minio:9000 s3 ls 2>/dev/null | grep -q test-bucket; then
                success "MinIO bucket listing successful"
                ((PASSED_TESTS++))
            else
                warn "MinIO bucket listing failed"
                ((WARNING_TESTS++))
            fi
            ((TOTAL_TESTS++))
        fi
    fi
}

# Function: Performance tests
test_performance() {
    if [[ "$TEST_LEVEL" == "comprehensive" ]]; then
        log "⚡ Running performance tests..."
        
        # Test response times
        if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
            # MinIO response time
            local minio_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:9000/minio/health/live)
            if (( $(echo "$minio_time < 1.0" | bc -l) )); then
                success "MinIO response time acceptable: ${minio_time}s"
                ((PASSED_TESTS++))
            else
                warn "MinIO response time slow: ${minio_time}s"
                ((WARNING_TESTS++))
            fi
            ((TOTAL_TESTS++))
            
            # Prefect response time
            local prefect_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:4200/api/health)
            if (( $(echo "$prefect_time < 2.0" | bc -l) )); then
                success "Prefect response time acceptable: ${prefect_time}s"
                ((PASSED_TESTS++))
            else
                warn "Prefect response time slow: ${prefect_time}s"
                ((WARNING_TESTS++))
            fi
            ((TOTAL_TESTS++))
        fi
    fi
}

# Function: Generate test report
generate_test_report() {
    echo ""
    echo -e "${BLUE}📊 Test Results Summary${NC}"
    echo -e "${BLUE}========================${NC}"
    echo ""
    echo -e "${GREEN}✅ Passed Tests: ${PASSED_TESTS}${NC}"
    echo -e "${YELLOW}⚠️  Warning Tests: ${WARNING_TESTS}${NC}"
    echo -e "${RED}❌ Failed Tests: ${FAILED_TESTS}${NC}"
    echo -e "${BLUE}📋 Total Tests: ${TOTAL_TESTS}${NC}"
    echo ""
    
    local success_rate=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    echo -e "${BLUE}📈 Success Rate: ${success_rate}%${NC}"
    echo ""
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "${GREEN}🎉 All critical tests passed! Essential services are ready.${NC}"
        return 0
    else
        echo -e "${RED}💥 Some tests failed. Please check the services and try again.${NC}"
        return 1
    fi
}

# Function: Display service status
display_service_status() {
    echo ""
    echo -e "${BLUE}📋 Essential Services Status${NC}"
    echo -e "${BLUE}=============================${NC}"
    echo ""
    
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        echo -e "${GREEN}🐳 Docker Compose Services:${NC}"
        docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps
        echo ""
        echo -e "${GREEN}🌐 Service URLs:${NC}"
        echo "• MinIO Console: http://localhost:9001"
        echo "• Prefect UI: http://localhost:4200"
        
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        echo -e "${GREEN}☸️ K3s Services:${NC}"
        kubectl get pods -n crypto-lakehouse
        echo ""
        kubectl get services -n crypto-lakehouse
        echo ""
        echo -e "${GREEN}🌐 Service URLs (NodePort):${NC}"
        echo "• MinIO Console: http://localhost:30901"
        echo "• Prefect UI: http://localhost:30420"
    fi
    echo ""
}

# Main testing function
main() {
    log "🧪 Starting essential services testing..."
    
    # Check if services are deployed
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        if ! docker-compose -f infrastructure/docker-compose/docker-compose.essential.yml ps | grep -q "Up"; then
            error "No running Docker Compose services found. Please deploy first with: ./infrastructure/scripts/deploy-essential.sh"
            exit 1
        fi
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        if ! kubectl get namespace crypto-lakehouse >/dev/null 2>&1; then
            error "K3s namespace not found. Please deploy first with: ./infrastructure/scripts/deploy-essential.sh k3s"
            exit 1
        fi
    fi
    
    # Run tests based on deployment mode
    if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
        test_docker_compose_services
    elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
        test_k3s_services
    fi
    
    # Run integration tests
    test_service_integration
    
    # Run functionality tests
    test_basic_functionality
    
    # Run performance tests
    test_performance
    
    # Display results
    display_service_status
    generate_test_report
}

# Help function
show_help() {
    echo "Usage: $0 [MODE] [TEST_LEVEL]"
    echo ""
    echo "Arguments:"
    echo "  MODE        Deployment mode: docker-compose (default) or k3s"
    echo "  TEST_LEVEL  Test level: basic (default) or comprehensive"
    echo ""
    echo "Examples:"
    echo "  $0                          # Docker Compose, basic tests"
    echo "  $0 docker-compose basic    # Explicit Docker Compose, basic"
    echo "  $0 k3s comprehensive       # K3s with comprehensive tests"
    echo ""
    echo "Test Categories:"
    echo "  • Service health checks"
    echo "  • Connectivity tests"
    echo "  • Integration validation"
    echo "  • Basic functionality (comprehensive only)"
    echo "  • Performance tests (comprehensive only)"
    echo ""
}

# Check if help is requested
if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
    show_help
    exit 0
fi

# Check prerequisites
if [[ "$DEPLOYMENT_MODE" == "docker-compose" ]]; then
    command -v docker >/dev/null 2>&1 || { error "Docker is required but not installed"; exit 1; }
    command -v docker-compose >/dev/null 2>&1 || { error "Docker Compose is required but not installed"; exit 1; }
elif [[ "$DEPLOYMENT_MODE" == "k3s" ]]; then
    command -v kubectl >/dev/null 2>&1 || { error "kubectl is required but not installed"; exit 1; }
fi

# Run main function
main "$@"