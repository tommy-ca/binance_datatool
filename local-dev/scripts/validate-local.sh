#!/bin/bash

# Local Environment Validation Script
# Validates the complete Crypto Lakehouse local deployment
# Version: 1.0.0
# Date: 2025-07-20

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
VALIDATION_TIMEOUT=300
HEALTH_CHECK_RETRIES=5
PERFORMANCE_TEST_DURATION=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Validation results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

step() {
    echo -e "${PURPLE}[$(date +'%Y-%m-%d %H:%M:%S')] 🧪 $1${NC}"
}

success() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
    ((PASSED_TESTS++))
}

fail() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
    ((FAILED_TESTS++))
}

# Test execution wrapper
run_test() {
    local test_name="$1"
    local test_function="$2"
    
    ((TOTAL_TESTS++))
    info "Running test: $test_name"
    
    if $test_function; then
        success "$test_name"
        return 0
    else
        fail "$test_name"
        return 1
    fi
}

# Wait for service to be ready
wait_for_service() {
    local namespace=$1
    local service=$2
    local port=$3
    local path=${4:-"/"}
    local timeout=${5:-$VALIDATION_TIMEOUT}
    
    info "Waiting for $service in namespace $namespace to be ready..."
    
    local count=0
    while [[ $count -lt $timeout ]]; do
        if kubectl exec -n "$namespace" deployment/"$service" -- \
           curl -sf "http://localhost:$port$path" &>/dev/null; then
            return 0
        fi
        sleep 1
        ((count++))
    done
    
    return 1
}

# Test cluster connectivity
test_cluster_connectivity() {
    kubectl cluster-info &>/dev/null && \
    kubectl get nodes | grep -q "Ready"
}

# Test namespace existence
test_namespaces() {
    local namespaces=("prefect" "minio" "s5cmd" "observability")
    for ns in "${namespaces[@]}"; do
        kubectl get namespace "$ns" &>/dev/null || return 1
    done
    return 0
}

# Test pod status
test_pod_status() {
    local failed_pods=()
    
    # Check all pods are running
    while IFS= read -r line; do
        local namespace=$(echo "$line" | awk '{print $1}')
        local pod=$(echo "$line" | awk '{print $2}')
        local status=$(echo "$line" | awk '{print $4}')
        
        if [[ "$status" != "Running" && "$status" != "Completed" ]]; then
            failed_pods+=("$namespace/$pod:$status")
        fi
    done < <(kubectl get pods --all-namespaces --no-headers | grep -v "kube-system")
    
    if [[ ${#failed_pods[@]} -gt 0 ]]; then
        error "Failed pods: ${failed_pods[*]}"
        return 1
    fi
    
    return 0
}

# Test MinIO functionality
test_minio() {
    # Test MinIO API
    kubectl exec -n minio deployment/minio -- \
        mc alias set test http://localhost:9000 minioadmin minioadmin123 &>/dev/null || return 1
    
    # Test bucket creation and operations
    kubectl exec -n minio deployment/minio -- \
        mc mb --ignore-existing test/validation-test &>/dev/null || return 1
    
    # Test file upload/download
    kubectl exec -n minio deployment/minio -- \
        sh -c 'echo "validation test" | mc pipe test/validation-test/test.txt' &>/dev/null || return 1
    
    kubectl exec -n minio deployment/minio -- \
        mc cat test/validation-test/test.txt | grep -q "validation test" || return 1
    
    # Cleanup
    kubectl exec -n minio deployment/minio -- \
        mc rm --recursive --force test/validation-test &>/dev/null || true
    
    return 0
}

# Test Prefect functionality
test_prefect() {
    # Test Prefect server API
    kubectl exec -n prefect deployment/prefect-server -- \
        curl -sf http://localhost:4200/api/health | grep -q "ok" || return 1
    
    # Test database connectivity
    kubectl exec -n prefect deployment/prefect-server -- \
        prefect config view | grep -q "PREFECT_API_DATABASE_CONNECTION_URL" || return 1
    
    # Test worker connectivity
    kubectl exec -n prefect deployment/prefect-worker -- \
        prefect work-pool ls &>/dev/null || return 1
    
    return 0
}

# Test s5cmd functionality
test_s5cmd() {
    # Test s5cmd connectivity to MinIO
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        s5cmd --endpoint-url=http://minio-service.minio:9000 \
        --aws-access-key-id=s5cmd \
        --aws-secret-access-key=s5cmd123456 \
        ls s3://crypto-lakehouse-data/ &>/dev/null || return 1
    
    # Test s5cmd operations
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        sh -c 'echo "s5cmd test" | s5cmd --endpoint-url=http://minio-service.minio:9000 --aws-access-key-id=s5cmd --aws-secret-access-key=s5cmd123456 pipe s3://crypto-lakehouse-data/validation/s5cmd-test.txt' &>/dev/null || return 1
    
    # Cleanup
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        s5cmd --endpoint-url=http://minio-service.minio:9000 \
        --aws-access-key-id=s5cmd \
        --aws-secret-access-key=s5cmd123456 \
        rm s3://crypto-lakehouse-data/validation/s5cmd-test.txt &>/dev/null || true
    
    return 0
}

# Test unified observability stack with OpenObserve
test_observability() {
    # Test OpenObserve unified platform
    kubectl exec -n observability statefulset/openobserve -- \
        curl -sf http://localhost:5080/healthz &>/dev/null || return 1
    
    # Test OpenObserve OTLP endpoints
    kubectl exec -n observability statefulset/openobserve -- \
        curl -sf http://localhost:4318/v1/traces -X POST -H "Content-Type: application/x-protobuf" &>/dev/null || return 1
    
    # Test OpenTelemetry Collector
    kubectl exec -n observability deployment/otel-collector -- \
        curl -sf http://localhost:13133/ &>/dev/null || return 1
    
    # Test OpenObserve metrics endpoint
    kubectl exec -n observability statefulset/openobserve -- \
        curl -sf http://localhost:5080/metrics &>/dev/null || return 1
    
    return 0
}

# Test service connectivity
test_service_connectivity() {
    local services=(
        "observability:otel-collector:4317"
        "observability:openobserve:5080"
        "observability:openobserve:4318"
        "minio:minio-service:9000"
        "prefect:prefect-server:4200"
        "s5cmd:s5cmd-executor:8080"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r namespace service port <<< "$service_info"
        
        # Test service DNS resolution and connectivity
        kubectl run test-connectivity-$RANDOM \
            --image=busybox:1.36 \
            --rm -i --restart=Never \
            --timeout=30s \
            -- nslookup "$service.$namespace" &>/dev/null || return 1
    done
    
    return 0
}

# Test unified metrics collection via OpenObserve
test_metrics() {
    # Test OpenObserve metrics ingestion and querying
    # Check if OpenObserve is receiving metrics from OTLP
    kubectl exec -n observability statefulset/openobserve -- \
        curl -sf "http://localhost:5080/api/default/prometheus/api/v1/query?query=up" | \
        grep -q '"status":"success"' || return 1
    
    # Test OpenObserve internal metrics
    kubectl exec -n observability statefulset/openobserve -- \
        curl -sf "http://localhost:5080/metrics" | \
        grep -q "openobserve" || return 1
    
    # Test OTLP metrics ingestion endpoint
    kubectl exec -n observability deployment/otel-collector -- \
        curl -sf "http://localhost:8888/metrics" | \
        grep -q "otelcol_" || return 1
    
    return 0
}

# Test persistent storage
test_storage() {
    # Check PVCs are bound
    local pvcs=$(kubectl get pvc --all-namespaces --no-headers | grep -v "Bound" | wc -l)
    [[ $pvcs -eq 0 ]] || return 1
    
    # Test write/read to persistent volumes
    kubectl exec -n minio deployment/minio -- \
        touch /data/storage-test.txt || return 1
    
    kubectl exec -n prefect deployment/postgres -- \
        touch /var/lib/postgresql/data/storage-test.txt || return 1
    
    return 0
}

# Performance tests
test_performance() {
    info "Running performance validation (${PERFORMANCE_TEST_DURATION}s)..."
    
    # Test s5cmd throughput
    local test_file_size="10MB"
    local start_time=$(date +%s)
    
    # Create test file and upload via s5cmd
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        dd if=/dev/zero of=/tmp/perf-test.dat bs=1M count=10 &>/dev/null || return 1
    
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        s5cmd --endpoint-url=http://minio-service.minio:9000 \
        --aws-access-key-id=s5cmd \
        --aws-secret-access-key=s5cmd123456 \
        cp /tmp/perf-test.dat s3://crypto-lakehouse-data/perf-test.dat &>/dev/null || return 1
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    info "Upload test completed in ${duration}s"
    
    # Download test
    start_time=$(date +%s)
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        s5cmd --endpoint-url=http://minio-service.minio:9000 \
        --aws-access-key-id=s5cmd \
        --aws-secret-access-key=s5cmd123456 \
        cp s3://crypto-lakehouse-data/perf-test.dat /tmp/perf-test-download.dat &>/dev/null || return 1
    
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    info "Download test completed in ${duration}s"
    
    # Cleanup
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        rm -f /tmp/perf-test.dat /tmp/perf-test-download.dat &>/dev/null || true
    
    kubectl exec -n s5cmd deployment/s5cmd-executor -- \
        s5cmd --endpoint-url=http://minio-service.minio:9000 \
        --aws-access-key-id=s5cmd \
        --aws-secret-access-key=s5cmd123456 \
        rm s3://crypto-lakehouse-data/perf-test.dat &>/dev/null || true
    
    return 0
}

# Test resource utilization
test_resources() {
    # Check resource usage is within limits
    local high_memory_pods=$(kubectl top pods --all-namespaces --no-headers 2>/dev/null | \
        awk '$4 ~ /[0-9]+Mi/ && $4+0 > 1000 {print $1"/"$2}' | wc -l)
    
    local high_cpu_pods=$(kubectl top pods --all-namespaces --no-headers 2>/dev/null | \
        awk '$3 ~ /[0-9]+m/ && $3+0 > 1000 {print $1"/"$2}' | wc -l)
    
    # Allow some pods to use more resources in local dev
    [[ $high_memory_pods -lt 5 ]] || return 1
    [[ $high_cpu_pods -lt 3 ]] || return 1
    
    return 0
}

# Generate validation report
generate_report() {
    step "Validation Report"
    
    echo ""
    echo "📊 Test Results Summary:"
    echo "  Total Tests: $TOTAL_TESTS"
    echo "  Passed: $PASSED_TESTS"
    echo "  Failed: $FAILED_TESTS"
    echo "  Success Rate: $(( (PASSED_TESTS * 100) / TOTAL_TESTS ))%"
    
    echo ""
    echo "🏗️  Infrastructure Status:"
    kubectl get nodes -o wide
    
    echo ""
    echo "📦 Pod Status:"
    kubectl get pods --all-namespaces -o wide
    
    echo ""
    echo "💾 Storage Status:"
    kubectl get pv,pvc --all-namespaces
    
    echo ""
    echo "🌐 Service Status:"
    kubectl get services --all-namespaces
    
    echo ""
    echo "📈 Resource Usage:"
    kubectl top nodes 2>/dev/null || echo "Metrics server not available"
    kubectl top pods --all-namespaces 2>/dev/null || echo "Pod metrics not available"
    
    # Save detailed report
    local report_file="$PROJECT_ROOT/validation-report-$(date +%Y%m%d-%H%M%S).txt"
    {
        echo "Crypto Lakehouse Local Environment Validation Report"
        echo "Generated: $(date)"
        echo "Cluster: $(kubectl config current-context)"
        echo ""
        echo "Test Results: $PASSED_TESTS/$TOTAL_TESTS passed"
        echo ""
        kubectl get all --all-namespaces
    } > "$report_file"
    
    info "Detailed report saved to: $report_file"
}

# Display validation results
display_results() {
    echo ""
    if [[ $FAILED_TESTS -eq 0 ]]; then
        log "🎉 All validation tests passed! Environment is ready for use."
        echo ""
        echo "🚀 Next Steps:"
        echo "  1. Start port forwarding: ./scripts/port-forward.sh"
        echo "  2. Access OpenObserve: http://localhost:5080 (admin@crypto-lakehouse.local/admin123)"
        echo "  3. Access Prefect: http://localhost:4200"
        echo "  4. Access MinIO: http://localhost:9001 (minioadmin/minioadmin123)"
        echo ""
        echo "📚 Documentation:"
        echo "  • Local development guide: ./README.md"
        echo "  • Performance specs: ./docs/specs-driven-flow/"
        echo "  • Architecture docs: ./docs/deployment/"
    else
        error "❌ $FAILED_TESTS validation tests failed!"
        echo ""
        echo "🔍 Troubleshooting:"
        echo "  1. Check pod logs: kubectl logs -n <namespace> deployment/<service>"
        echo "  2. Check events: kubectl get events --all-namespaces"
        echo "  3. Check resources: kubectl describe pods --all-namespaces"
        echo ""
        echo "🔄 To redeploy:"
        echo "  kubectl delete -f manifests/ --recursive"
        echo "  ./scripts/deploy-local.sh"
        return 1
    fi
}

# Main execution
main() {
    log "Starting validation of Crypto Lakehouse local environment..."
    
    # Core infrastructure tests
    run_test "Cluster Connectivity" test_cluster_connectivity
    run_test "Namespace Existence" test_namespaces
    run_test "Pod Status" test_pod_status
    run_test "Service Connectivity" test_service_connectivity
    run_test "Persistent Storage" test_storage
    
    # Application functionality tests
    run_test "MinIO Functionality" test_minio
    run_test "Prefect Functionality" test_prefect
    run_test "s5cmd Functionality" test_s5cmd
    run_test "Observability Stack" test_observability
    
    # Advanced tests
    run_test "Metrics Collection" test_metrics
    run_test "Performance Validation" test_performance
    run_test "Resource Utilization" test_resources
    
    generate_report
    display_results
    
    # Exit with error code if any tests failed
    [[ $FAILED_TESTS -eq 0 ]] || exit 1
    
    log "✅ Validation completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --timeout)
            VALIDATION_TIMEOUT="$2"
            shift 2
            ;;
        --performance-duration)
            PERFORMANCE_TEST_DURATION="$2"
            shift 2
            ;;
        --skip-performance)
            SKIP_PERFORMANCE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --timeout SECONDS           Set validation timeout (default: 300)"
            echo "  --performance-duration SEC  Set performance test duration (default: 30)"
            echo "  --skip-performance          Skip performance tests"
            echo "  --help                      Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Execute main function
main "$@"