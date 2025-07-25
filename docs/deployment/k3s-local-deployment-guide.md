# K3s Local Deployment Guide

## 📋 Document Information

| Field | Value |
|-------|--------|
| **Document Version** | 3.2.0 |
| **Last Updated** | 2025-07-25 |
| **Status** | ✅ Production Ready |
| **Deployment Target** | K3s Local Development |

## 🎯 Overview

This guide provides step-by-step instructions for deploying the crypto lakehouse platform on K3s for local development and testing.

## 📋 Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 4 cores | 8 cores |
| **Memory** | 8 GB | 16 GB |
| **Storage** | 50 GB | 100 GB |
| **OS** | Linux/macOS | Ubuntu 22.04+ |

### Software Dependencies

```bash
# Required tools
- Docker (20.10+)
- kubectl (1.28+)
- curl
- git

# Optional but recommended
- k9s (Kubernetes UI)
- helm (Package manager)
- jq (JSON processor)
```

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/crypto-lakehouse.git
cd crypto-lakehouse
```

### 2. Deploy K3s Infrastructure

```bash
# Basic deployment
./scripts/deploy-k3s-local.sh development basic

# Comprehensive deployment with validation
./scripts/deploy-k3s-local.sh development comprehensive
```

### 3. Verify Deployment

```bash
# Run validation suite
./scripts/validate-k3s-specs.sh comprehensive console

# Check service status
kubectl get pods -n crypto-lakehouse
kubectl get services -n crypto-lakehouse
```

### 4. Access Services

```bash
# Get service URLs
echo "Prefect UI: http://localhost:30420"
echo "MinIO Console: http://localhost:30901"
echo "s5cmd Service: http://localhost:30808"
```

## 📦 Deployment Options

### Development Mode

```bash
# Minimal resource usage
./scripts/deploy-k3s-local.sh development basic

# Features:
# - Single replica services
# - Basic monitoring
# - Local storage
# - Development credentials
```

### Testing Mode

```bash
# Enhanced features for testing
./scripts/deploy-k3s-local.sh staging comprehensive

# Features:
# - Multi-replica services
# - Full observability stack
# - Persistent storage
# - Test data sets
```

### Production Simulation

```bash
# Production-like environment
./scripts/deploy-k3s-local.sh production comprehensive

# Features:
# - High availability
# - Full monitoring
# - Security policies
# - Performance tuning
```

## 🔧 Configuration

### Environment Variables

```bash
# Required environment variables
export ENVIRONMENT=development
export VALIDATION_MODE=comprehensive
export KUBECONFIG=$HOME/.kube/config

# Optional customizations
export NAMESPACE=crypto-lakehouse
export STORAGE_CLASS=local-storage
export REPLICA_COUNT=1
```

### Custom Configuration

```bash
# Edit configuration files
vim k3s-local-infrastructure.yml

# Key sections to customize:
# - Resource limits
# - Storage requirements
# - Service ports
# - Security policies
```

## 📊 Service Architecture

### Core Services

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Prefect       │  │     MinIO       │  │   PostgreSQL    │
│   (Workflows)   │  │   (Storage)     │  │   (Database)    │
│   Port: 30420   │  │   Port: 30901   │  │   Port: 5432    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         |                     |                     |
         └─────────────────────┼─────────────────────┘
                               |
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     Redis       │  │   s5cmd Service │  │  Observability  │
│    (Cache)      │  │  (S3 Operations)│  │     Stack       │
│   Port: 6379    │  │   Port: 30808   │  │  (Monitoring)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### Observability Stack

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Prometheus    │  │     Grafana     │  │     Jaeger      │
│   (Metrics)     │  │ (Visualization) │  │   (Tracing)     │
│   Port: 9090    │  │   Port: 3000    │  │   Port: 16686   │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         |                     |                     |
         └─────────────────────┼─────────────────────┘
                               |
                ┌─────────────────────────┐
                │  OpenTelemetry Collector │
                │      (Aggregation)       │
                │       Port: 4317         │
                └─────────────────────────┘
```

## 🔍 Monitoring and Troubleshooting

### Health Checks

```bash
# Check cluster status
kubectl cluster-info

# Check node status
kubectl get nodes

# Check pod status
kubectl get pods -n crypto-lakehouse -w

# Check service status
kubectl get services -n crypto-lakehouse
```

### Common Issues

#### 1. Pod Stuck in Pending State

```bash
# Check resource constraints
kubectl describe pod <pod-name> -n crypto-lakehouse

# Check node resources
kubectl top nodes

# Solution: Increase resource limits or add nodes
```

#### 2. Service Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n crypto-lakehouse

# Check ingress configuration
kubectl get ingress -n crypto-lakehouse

# Solution: Verify NodePort or port-forward
kubectl port-forward svc/<service-name> <local-port>:<service-port> -n crypto-lakehouse
```

#### 3. Storage Issues

```bash
# Check persistent volumes
kubectl get pv

# Check persistent volume claims
kubectl get pvc -n crypto-lakehouse

# Solution: Ensure storage class is available
kubectl get storageclass
```

### Logs and Debugging

```bash
# View pod logs
kubectl logs <pod-name> -n crypto-lakehouse -f

# View previous container logs
kubectl logs <pod-name> -n crypto-lakehouse --previous

# Execute into pod for debugging
kubectl exec -it <pod-name> -n crypto-lakehouse -- /bin/bash

# View events
kubectl get events -n crypto-lakehouse --sort-by='.lastTimestamp'
```

## 📈 Performance Tuning

### Resource Optimization

```yaml
# Update resource requests and limits
resources:
  requests:
    memory: "256Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### Scaling Configuration

```bash
# Manual scaling
kubectl scale deployment <deployment-name> --replicas=3 -n crypto-lakehouse

# Auto-scaling (if HPA is configured)
kubectl get hpa -n crypto-lakehouse
```

### Storage Optimization

```bash
# Check storage usage
kubectl top pods -n crypto-lakehouse

# Optimize storage class
kubectl get storageclass local-storage -o yaml
```

## 🔒 Security Configuration

### Network Policies

```bash
# Check network policies
kubectl get networkpolicy -n crypto-lakehouse

# Test network connectivity
kubectl exec -it <pod-name> -n crypto-lakehouse -- curl <service-url>
```

### RBAC Configuration

```bash
# Check service accounts
kubectl get serviceaccounts -n crypto-lakehouse

# Check role bindings
kubectl get rolebindings -n crypto-lakehouse
```

### Secrets Management

```bash
# Check secrets
kubectl get secrets -n crypto-lakehouse

# View secret content (base64 encoded)
kubectl get secret <secret-name> -n crypto-lakehouse -o yaml
```

## 🔄 Backup and Recovery

### Data Backup

```bash
# Backup persistent volumes
kubectl get pvc -n crypto-lakehouse
./scripts/backup-k3s-data.sh

# Export configurations
kubectl get all -n crypto-lakehouse -o yaml > k3s-backup.yaml
```

### Disaster Recovery

```bash
# Restore from backup
./scripts/restore-k3s-data.sh <backup-date>

# Recreate resources
kubectl apply -f k3s-backup.yaml
```

## 🔧 Maintenance

### Updates and Upgrades

```bash
# Update K3s
curl -sfL https://get.k3s.io | sh -

# Update application images
kubectl set image deployment/<deployment-name> <container-name>=<new-image> -n crypto-lakehouse

# Rolling restart
kubectl rollout restart deployment/<deployment-name> -n crypto-lakehouse
```

### Cleanup

```bash
# Remove specific deployment
kubectl delete -f k3s-local-infrastructure.yml

# Remove namespace (caution: removes all resources)
kubectl delete namespace crypto-lakehouse

# Uninstall K3s completely
/usr/local/bin/k3s-uninstall.sh
```

## 📚 Advanced Configuration

### Custom Resource Definitions

```bash
# List CRDs
kubectl get crd

# Apply custom resources
kubectl apply -f custom-resources/
```

### Service Mesh Integration

```bash
# Install Istio (optional)
curl -L https://istio.io/downloadIstio | sh -
istioctl install --set values.defaultRevision=default

# Enable sidecar injection
kubectl label namespace crypto-lakehouse istio-injection=enabled
```

### GitOps Integration

```bash
# Install ArgoCD (optional)
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Configure application sync
kubectl apply -f argocd-applications/
```

## 📋 Validation Checklist

### Pre-deployment

- [ ] System requirements met
- [ ] Software dependencies installed
- [ ] Network connectivity verified
- [ ] Storage requirements available

### Post-deployment

- [ ] All pods running
- [ ] Services accessible
- [ ] Health checks passing
- [ ] Monitoring active
- [ ] Data persistence verified

### Production Readiness

- [ ] Security policies configured
- [ ] Backup procedures tested
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Team training completed

## 🎯 Next Steps

### Development Workflow

1. **Deploy Infrastructure**: Use K3s local deployment
2. **Develop Applications**: Code against local services
3. **Test Integration**: Validate with full stack
4. **Deploy to Staging**: Promote to staging environment
5. **Production Release**: Deploy to production cluster

### Migration Path

```bash
# From Docker Compose to K3s
./scripts/migrate-docker-to-k3s.sh

# From K3s Local to Production
./scripts/migrate-k3s-to-production.sh
```

---

**Deployment Status**: ✅ **READY FOR USE**

*K3s local deployment guide verified and ready for implementation.*