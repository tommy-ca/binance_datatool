#!/bin/bash

# Enhanced Deployment Script for Crypto Lakehouse Infrastructure
# Based on Phase 2: Design Specifications
# Version: 3.0.0
# Date: 2025-07-20

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
KUBERNETES_DIR="$PROJECT_ROOT/kubernetes"
HELM_DIR="$PROJECT_ROOT/helm"

# Default values
ENVIRONMENT="development"
COMPONENT="all"
DRY_RUN=false
VERBOSE=false
SKIP_VALIDATION=false
PARALLEL_DEPLOYMENT=true

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

debug() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] DEBUG: $1${NC}"
    fi
}

# Help function
show_help() {
    cat << EOF
Enhanced Deployment Script for Crypto Lakehouse Infrastructure

USAGE:
    $0 [OPTIONS]

OPTIONS:
    -e, --environment ENVIRONMENT    Target environment (development|staging|production)
                                    Default: development
    
    -c, --component COMPONENT       Component to deploy (all|infrastructure|prefect|minio|s5cmd|monitoring)
                                    Default: all
    
    -d, --dry-run                   Show what would be deployed without making changes
                                    Default: false
    
    -v, --verbose                   Enable verbose output
                                    Default: false
    
    -s, --skip-validation           Skip pre-deployment validation
                                    Default: false
    
    -p, --no-parallel               Disable parallel deployment (deploy components sequentially)
                                    Default: false (parallel enabled)
    
    -h, --help                      Show this help message

EXAMPLES:
    # Deploy everything to development environment
    $0 --environment development

    # Deploy only Prefect components to production
    $0 --environment production --component prefect

    # Dry run for staging environment
    $0 --environment staging --dry-run

    # Verbose deployment with validation
    $0 --environment production --verbose

COMPONENTS:
    infrastructure  - Terraform infrastructure (VPC, EKS, IAM, etc.)
    prefect        - Prefect orchestration stack
    minio          - MinIO distributed storage cluster
    s5cmd          - s5cmd executor service
    monitoring     - Prometheus, Grafana, Jaeger observability stack
    all            - Deploy all components in correct order

DEPLOYMENT ORDER (when using 'all'):
    1. Infrastructure (Terraform)
    2. Core Services (Istio, External Secrets, Storage Classes)
    3. Data Services (Prefect, MinIO, s5cmd) - Parallel if enabled
    4. Monitoring Stack (Prometheus, Grafana, Jaeger)
    5. Validation and Health Checks

EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -c|--component)
                COMPONENT="$2"
                shift 2
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -s|--skip-validation)
                SKIP_VALIDATION=true
                shift
                ;;
            -p|--no-parallel)
                PARALLEL_DEPLOYMENT=false
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done

    # Validate environment
    case $ENVIRONMENT in
        development|staging|production)
            ;;
        *)
            error "Invalid environment: $ENVIRONMENT. Must be one of: development, staging, production"
            ;;
    esac

    # Validate component
    case $COMPONENT in
        all|infrastructure|prefect|minio|s5cmd|monitoring)
            ;;
        *)
            error "Invalid component: $COMPONENT. Must be one of: all, infrastructure, prefect, minio, s5cmd, monitoring"
            ;;
    esac
}

# Prerequisites check
check_prerequisites() {
    log "Checking prerequisites..."

    # Check required tools
    local tools=("terraform" "kubectl" "helm" "aws")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "$tool is required but not installed"
        fi
        debug "$tool is available"
    done

    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured or invalid"
    fi
    debug "AWS credentials validated"

    # Check Terraform version
    local tf_version=$(terraform version -json | jq -r '.terraform_version')
    if [[ $(printf '%s\n' "1.5.0" "$tf_version" | sort -V | head -n1) != "1.5.0" ]]; then
        error "Terraform version must be >= 1.5.0, found: $tf_version"
    fi
    debug "Terraform version: $tf_version"

    # Check Helm version
    local helm_version=$(helm version --short | cut -d' ' -f2 | tr -d 'v')
    if [[ $(printf '%s\n' "3.12.0" "$helm_version" | sort -V | head -n1) != "3.12.0" ]]; then
        error "Helm version must be >= 3.12.0, found: $helm_version"
    fi
    debug "Helm version: $helm_version"

    log "Prerequisites check completed successfully"
}

# Validate configuration
validate_configuration() {
    if [[ "$SKIP_VALIDATION" == "true" ]]; then
        warn "Skipping configuration validation"
        return 0
    fi

    log "Validating configuration for environment: $ENVIRONMENT"

    # Check if environment configuration file exists
    local env_file="$TERRAFORM_DIR/environments/${ENVIRONMENT}.tfvars"
    if [[ ! -f "$env_file" ]]; then
        error "Environment configuration file not found: $env_file"
    fi
    debug "Environment configuration file found: $env_file"

    # Validate Terraform configuration
    cd "$TERRAFORM_DIR"
    if ! terraform validate; then
        error "Terraform configuration validation failed"
    fi
    debug "Terraform configuration validated"

    # Check Kubernetes manifests
    local k8s_dirs=("namespaces" "prefect" "minio" "s5cmd" "monitoring" "security")
    for dir in "${k8s_dirs[@]}"; do
        if [[ -d "$KUBERNETES_DIR/$dir" ]]; then
            for file in "$KUBERNETES_DIR/$dir"/*.yaml; do
                if [[ -f "$file" ]]; then
                    if ! kubectl apply --dry-run=client -f "$file" &> /dev/null; then
                        warn "Kubernetes manifest may have issues: $file"
                    fi
                fi
            done
        fi
    done

    log "Configuration validation completed"
}

# Deploy infrastructure using Terraform
deploy_infrastructure() {
    log "Deploying infrastructure with Terraform..."

    cd "$TERRAFORM_DIR"

    # Initialize Terraform
    log "Initializing Terraform..."
    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would initialize Terraform"
    else
        terraform init
    fi

    # Plan deployment
    log "Planning Terraform deployment..."
    local plan_file="/tmp/terraform-plan-${ENVIRONMENT}.tfplan"
    if [[ "$DRY_RUN" == "true" ]]; then
        terraform plan -var-file="environments/${ENVIRONMENT}.tfvars" -out="$plan_file"
        log "DRY RUN: Terraform plan completed. Review the plan above."
        return 0
    else
        terraform plan -var-file="environments/${ENVIRONMENT}.tfvars" -out="$plan_file"
    fi

    # Apply deployment
    log "Applying Terraform deployment..."
    terraform apply "$plan_file"

    # Wait for EKS cluster to be ready
    log "Waiting for EKS cluster to be ready..."
    local cluster_name=$(terraform output -raw cluster_name)
    aws eks wait cluster-active --name "$cluster_name"

    # Update kubeconfig
    log "Updating kubeconfig..."
    aws eks update-kubeconfig --name "$cluster_name" --region "$(terraform output -raw aws_region)"

    log "Infrastructure deployment completed successfully"
}

# Deploy Prefect stack
deploy_prefect() {
    log "Deploying Prefect orchestration stack..."

    # Create namespace if it doesn't exist
    kubectl create namespace prefect-prod --dry-run=client -o yaml | kubectl apply -f -

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would deploy Prefect stack"
        return 0
    fi

    # Deploy PostgreSQL cluster
    log "Deploying PostgreSQL database cluster..."
    kubectl apply -f "$KUBERNETES_DIR/prefect/database/"

    # Wait for database to be ready
    log "Waiting for PostgreSQL cluster to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n prefect-prod --timeout=300s

    # Deploy Prefect server
    log "Deploying Prefect server..."
    kubectl apply -f "$KUBERNETES_DIR/prefect/server/"

    # Wait for Prefect server to be ready
    log "Waiting for Prefect server to be ready..."
    kubectl wait --for=condition=available deployment/prefect-server -n prefect-prod --timeout=300s

    # Deploy worker pools
    log "Deploying Prefect worker pools..."
    kubectl apply -f "$KUBERNETES_DIR/prefect/workers/"

    log "Prefect stack deployment completed successfully"
}

# Deploy MinIO cluster
deploy_minio() {
    log "Deploying MinIO distributed storage cluster..."

    # Create namespace if it doesn't exist
    kubectl create namespace minio-prod --dry-run=client -o yaml | kubectl apply -f -

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would deploy MinIO cluster"
        return 0
    fi

    # Deploy MinIO cluster
    log "Deploying MinIO StatefulSet..."
    kubectl apply -f "$KUBERNETES_DIR/minio/cluster/"

    # Wait for MinIO cluster to be ready
    log "Waiting for MinIO cluster to be ready..."
    kubectl wait --for=condition=ready pod -l app=minio -n minio-prod --timeout=600s

    # Deploy MinIO console
    log "Deploying MinIO console..."
    kubectl apply -f "$KUBERNETES_DIR/minio/console/"

    # Apply storage policies
    log "Applying MinIO storage policies..."
    kubectl apply -f "$KUBERNETES_DIR/minio/policies/"

    log "MinIO cluster deployment completed successfully"
}

# Deploy s5cmd executor service
deploy_s5cmd() {
    log "Deploying s5cmd executor service..."

    # Create namespace if it doesn't exist
    kubectl create namespace s5cmd-prod --dry-run=client -o yaml | kubectl apply -f -

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would deploy s5cmd executor service"
        return 0
    fi

    # Deploy s5cmd service
    log "Deploying s5cmd executor..."
    kubectl apply -f "$KUBERNETES_DIR/s5cmd/service/"

    # Apply configuration
    log "Applying s5cmd configuration..."
    kubectl apply -f "$KUBERNETES_DIR/s5cmd/configmaps/"

    # Apply secrets
    log "Applying s5cmd secrets..."
    kubectl apply -f "$KUBERNETES_DIR/s5cmd/secrets/"

    # Wait for s5cmd service to be ready
    log "Waiting for s5cmd executor to be ready..."
    kubectl wait --for=condition=available deployment/s5cmd-executor -n s5cmd-prod --timeout=300s

    log "s5cmd executor service deployment completed successfully"
}

# Deploy monitoring stack
deploy_monitoring() {
    log "Deploying monitoring and observability stack..."

    # Create namespace if it doesn't exist
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would deploy monitoring stack"
        return 0
    fi

    # Deploy Prometheus stack (already deployed via Terraform/Helm)
    log "Verifying Prometheus stack deployment..."
    kubectl wait --for=condition=available deployment/prometheus-stack-grafana -n monitoring --timeout=300s
    kubectl wait --for=condition=available deployment/prometheus-stack-kube-prom-operator -n monitoring --timeout=300s

    # Deploy custom monitoring resources
    log "Deploying custom monitoring resources..."
    kubectl apply -f "$KUBERNETES_DIR/monitoring/prometheus/"
    kubectl apply -f "$KUBERNETES_DIR/monitoring/grafana/"

    # Deploy Jaeger if enabled
    if kubectl get namespace istio-system &> /dev/null; then
        log "Deploying Jaeger tracing..."
        kubectl apply -f "$KUBERNETES_DIR/monitoring/jaeger/"
    fi

    log "Monitoring stack deployment completed successfully"
}

# Deploy security policies
deploy_security() {
    log "Deploying security policies..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: Would deploy security policies"
        return 0
    fi

    # Deploy network policies
    log "Deploying network policies..."
    kubectl apply -f "$KUBERNETES_DIR/security/network-policies/"

    # Deploy pod security policies
    log "Deploying pod security policies..."
    kubectl apply -f "$KUBERNETES_DIR/security/pod-security/"

    # Deploy RBAC configurations
    log "Deploying RBAC configurations..."
    kubectl apply -f "$KUBERNETES_DIR/security/rbac/"

    log "Security policies deployment completed successfully"
}

# Parallel deployment function
deploy_data_services_parallel() {
    log "Deploying data services in parallel..."

    local pids=()

    # Deploy Prefect in background
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "prefect" ]]; then
        deploy_prefect &
        pids+=($!)
    fi

    # Deploy MinIO in background
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "minio" ]]; then
        deploy_minio &
        pids+=($!)
    fi

    # Deploy s5cmd in background
    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "s5cmd" ]]; then
        deploy_s5cmd &
        pids+=($!)
    fi

    # Wait for all background jobs to complete
    for pid in "${pids[@]}"; do
        wait $pid
        local exit_code=$?
        if [[ $exit_code -ne 0 ]]; then
            error "Parallel deployment failed with exit code: $exit_code"
        fi
    done

    log "Parallel data services deployment completed successfully"
}

# Sequential deployment function
deploy_data_services_sequential() {
    log "Deploying data services sequentially..."

    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "prefect" ]]; then
        deploy_prefect
    fi

    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "minio" ]]; then
        deploy_minio
    fi

    if [[ "$COMPONENT" == "all" || "$COMPONENT" == "s5cmd" ]]; then
        deploy_s5cmd
    fi

    log "Sequential data services deployment completed successfully"
}

# Health check function
perform_health_checks() {
    log "Performing post-deployment health checks..."

    # Check cluster health
    log "Checking cluster health..."
    if ! kubectl get nodes | grep -q "Ready"; then
        warn "Some nodes may not be ready"
    fi

    # Check namespace status
    local namespaces=("prefect-prod" "minio-prod" "s5cmd-prod" "monitoring" "istio-system")
    for ns in "${namespaces[@]}"; do
        if kubectl get namespace "$ns" &> /dev/null; then
            local pod_count=$(kubectl get pods -n "$ns" --no-headers | wc -l)
            local ready_count=$(kubectl get pods -n "$ns" --field-selector=status.phase=Running --no-headers | wc -l)
            log "Namespace $ns: $ready_count/$pod_count pods running"
        fi
    done

    # Check service endpoints
    log "Checking service endpoints..."
    local services=("prefect-server-service.prefect-prod" "minio-service.minio-prod" "s5cmd-executor-service.s5cmd-prod")
    for service in "${services[@]}"; do
        if kubectl get service "${service%%.*}" -n "${service##*.}" &> /dev/null; then
            debug "Service $service exists"
        else
            warn "Service $service not found"
        fi
    done

    log "Health checks completed"
}

# Main deployment function
main_deploy() {
    log "Starting deployment for environment: $ENVIRONMENT, component: $COMPONENT"

    case $COMPONENT in
        infrastructure)
            deploy_infrastructure
            ;;
        prefect)
            deploy_prefect
            ;;
        minio)
            deploy_minio
            ;;
        s5cmd)
            deploy_s5cmd
            ;;
        monitoring)
            deploy_monitoring
            ;;
        all)
            # Deploy infrastructure first
            deploy_infrastructure

            # Deploy security policies
            deploy_security

            # Deploy data services (parallel or sequential)
            if [[ "$PARALLEL_DEPLOYMENT" == "true" ]]; then
                deploy_data_services_parallel
            else
                deploy_data_services_sequential
            fi

            # Deploy monitoring stack
            deploy_monitoring

            # Perform health checks
            perform_health_checks
            ;;
    esac

    log "Deployment completed successfully!"
}

# Error handling
trap 'error "Deployment failed at line $LINENO"' ERR

# Main execution
main() {
    parse_arguments "$@"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN MODE - No changes will be made"
    fi

    if [[ "$VERBOSE" == "true" ]]; then
        log "Verbose mode enabled"
        set -x
    fi

    check_prerequisites
    validate_configuration
    main_deploy

    log "🎉 Deployment completed successfully for environment: $ENVIRONMENT"
    log "📊 Use './scripts/validate.sh --environment $ENVIRONMENT' to validate the deployment"
}

# Execute main function with all arguments
main "$@"