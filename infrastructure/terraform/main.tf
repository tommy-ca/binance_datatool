# Enhanced Terraform Configuration for Crypto Lakehouse Infrastructure
# Based on Phase 2: Design Specifications
# Version: 3.0.0
# Date: 2025-07-20

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }
  
  backend "s3" {
    bucket = "crypto-lakehouse-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "us-west-2"
    
    dynamodb_table = "crypto-lakehouse-terraform-locks"
    encrypt        = true
  }
}

# Configure providers
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = local.common_tags
  }
}

provider "kubernetes" {
  host                   = module.eks_cluster.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks_cluster.cluster_certificate_authority_data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}

provider "helm" {
  kubernetes {
    host                   = module.eks_cluster.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks_cluster.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.cluster.token
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks_cluster.cluster_id
}

# Local values
locals {
  cluster_name = "crypto-lakehouse-${var.environment}"
  
  common_tags = {
    Project     = "crypto-lakehouse"
    Environment = var.environment
    ManagedBy   = "terraform"
    Owner       = "platform-team"
    CostCenter  = "data-infrastructure"
    CreatedDate = "2025-07-20"
  }
  
  # Node pool configurations based on Phase 2 design
  node_groups = {
    control_plane = {
      name           = "control-plane"
      instance_types = ["m5.large"]
      capacity_type  = "ON_DEMAND"
      min_size       = 3
      max_size       = 3
      desired_size   = 3
      disk_size      = 100
      
      labels = {
        "node-role" = "control-plane"
      }
      
      taints = [{
        key    = "node-role.kubernetes.io/control-plane"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
    
    general_workload = {
      name           = "general-workload"
      instance_types = ["m5.xlarge", "m5.2xlarge"]
      capacity_type  = "ON_DEMAND"
      min_size       = 3
      max_size       = 10
      desired_size   = 3
      disk_size      = 200
      
      labels = {
        "workload"  = "general"
        "node-role" = "worker"
      }
      
      taints = []
    }
    
    data_intensive = {
      name           = "data-intensive"
      instance_types = ["c5n.2xlarge", "c5n.4xlarge"]
      capacity_type  = "ON_DEMAND"
      min_size       = 2
      max_size       = 8
      desired_size   = 2
      disk_size      = 500
      
      labels = {
        "workload"           = "data-intensive"
        "node-role"          = "worker"
        "network-performance" = "high"
      }
      
      taints = [{
        key    = "workload"
        value  = "data-intensive"
        effect = "NO_SCHEDULE"
      }]
    }
    
    storage_nodes = {
      name           = "storage-nodes"
      instance_types = ["i3.xlarge", "i3.2xlarge"]
      capacity_type  = "ON_DEMAND"
      min_size       = 4
      max_size       = 4
      desired_size   = 4
      disk_size      = 1000
      
      labels = {
        "workload"  = "storage"
        "node-role" = "storage"
      }
      
      taints = [{
        key    = "workload"
        value  = "storage"
        effect = "NO_SCHEDULE"
      }]
    }
  }
}

# Networking Module
module "networking" {
  source = "./modules/networking"
  
  cluster_name = local.cluster_name
  environment  = var.environment
  
  vpc_cidr = var.vpc_cidr
  availability_zones = data.aws_availability_zones.available.names
  
  tags = local.common_tags
}

# Security Module
module "security" {
  source = "./modules/security"
  
  cluster_name = local.cluster_name
  environment  = var.environment
  
  vpc_id = module.networking.vpc_id
  
  tags = local.common_tags
}

# EKS Cluster Module
module "eks_cluster" {
  source = "./modules/eks"
  
  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version
  environment     = var.environment
  
  vpc_id     = module.networking.vpc_id
  subnet_ids = module.networking.private_subnet_ids
  
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  
  # Enable logging
  cluster_enabled_log_types = [
    "api",
    "audit", 
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
  
  # Node groups
  node_groups = local.node_groups
  
  # Add-ons
  cluster_addons = {
    coredns = {
      addon_version = "v1.10.1-eksbuild.1"
    }
    
    kube-proxy = {
      addon_version = "v1.28.1-eksbuild.1"
    }
    
    vpc-cni = {
      addon_version = "v1.13.4-eksbuild.1"
    }
    
    aws-ebs-csi-driver = {
      addon_version = "v1.21.0-eksbuild.1"
    }
  }
  
  tags = local.common_tags
}

# Kubernetes namespaces
resource "kubernetes_namespace" "application_namespaces" {
  for_each = toset([
    "prefect-prod",
    "prefect-staging", 
    "minio-prod",
    "minio-staging",
    "s5cmd-prod",
    "s5cmd-staging",
    "monitoring",
    "security",
    "istio-system"
  ])
  
  metadata {
    name = each.value
    
    labels = {
      environment = var.environment
      managed-by  = "terraform"
    }
    
    # Apply pod security standards
    annotations = {
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/audit"   = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
    }
  }
  
  depends_on = [module.eks_cluster]
}

# Istio Service Mesh Installation
resource "helm_release" "istio_base" {
  name       = "istio-base"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "base"
  namespace  = "istio-system"
  version    = "1.19.0"
  
  create_namespace = false
  
  depends_on = [kubernetes_namespace.application_namespaces]
}

resource "helm_release" "istiod" {
  name       = "istiod"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "istiod"
  namespace  = "istio-system"
  version    = "1.19.0"
  
  values = [
    yamlencode({
      global = {
        meshID = "crypto-lakehouse"
        multiCluster = {
          clusterName = local.cluster_name
        }
        network = "crypto-lakehouse-network"
      }
      
      pilot = {
        env = {
          EXTERNAL_ISTIOD = false
        }
        
        resources = {
          requests = {
            cpu    = "500m"
            memory = "2Gi"
          }
        }
      }
    })
  ]
  
  depends_on = [helm_release.istio_base]
}

resource "helm_release" "istio_gateway" {
  name       = "istio-ingressgateway"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "gateway"
  namespace  = "istio-system"
  version    = "1.19.0"
  
  values = [
    yamlencode({
      service = {
        type = "LoadBalancer"
        annotations = {
          "service.beta.kubernetes.io/aws-load-balancer-type" = "nlb"
          "service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled" = "true"
        }
      }
      
      resources = {
        requests = {
          cpu    = "100m"
          memory = "128Mi"
        }
      }
    })
  ]
  
  depends_on = [helm_release.istiod]
}

# Monitoring Stack
resource "helm_release" "prometheus_stack" {
  name       = "prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = "monitoring"
  version    = "51.0.0"
  
  create_namespace = false
  
  values = [
    templatefile("${path.module}/helm-values/prometheus-stack.yaml", {
      storage_class           = "gp3"
      retention              = "30d"
      prometheus_storage_size = "100Gi"
      grafana_storage_size   = "10Gi"
      alertmanager_storage_size = "10Gi"
      grafana_admin_password = var.grafana_admin_password
      cluster_name           = local.cluster_name
      environment           = var.environment
    })
  ]
  
  depends_on = [kubernetes_namespace.application_namespaces]
}

# External Secrets Operator
resource "helm_release" "external_secrets" {
  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  namespace  = "security"
  version    = "0.9.5"
  
  create_namespace = false
  
  values = [
    yamlencode({
      installCRDs = true
      
      resources = {
        requests = {
          cpu    = "100m"
          memory = "128Mi"
        }
      }
      
      webhook = {
        port = 9443
      }
    })
  ]
  
  depends_on = [kubernetes_namespace.application_namespaces]
}

# Cluster Autoscaler
resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  namespace  = "kube-system"
  version    = "9.29.0"
  
  values = [
    yamlencode({
      autoDiscovery = {
        clusterName = local.cluster_name
        enabled     = true
      }
      
      awsRegion = var.aws_region
      
      resources = {
        requests = {
          cpu    = "100m"
          memory = "300Mi"
        }
        limits = {
          cpu    = "100m"
          memory = "300Mi"
        }
      }
      
      nodeSelector = {
        "node-role" = "control-plane"
      }
      
      tolerations = [{
        key    = "node-role.kubernetes.io/control-plane"
        effect = "NoSchedule"
      }]
      
      extraArgs = {
        scale-down-delay-after-add       = "10m"
        scale-down-unneeded-time         = "10m"
        scale-down-delay-after-delete    = "10s"
        scale-down-delay-after-failure   = "3m"
        skip-nodes-with-local-storage    = false
        balance-similar-node-groups      = true
        skip-nodes-with-system-pods      = false
        expander                         = "least-waste"
      }
    })
  ]
  
  depends_on = [module.eks_cluster]
}

# Storage Classes
resource "kubernetes_storage_class" "gp3" {
  metadata {
    name = "gp3"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }
  
  storage_provisioner    = "ebs.csi.aws.com"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true
  
  parameters = {
    type       = "gp3"
    encrypted  = "true"
    fsType     = "ext4"
    throughput = "1000"
    iops       = "3000"
  }
  
  depends_on = [module.eks_cluster]
}

resource "kubernetes_storage_class" "fast_ssd" {
  metadata {
    name = "fast-ssd"
  }
  
  storage_provisioner    = "ebs.csi.aws.com"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true
  
  parameters = {
    type       = "gp3"
    encrypted  = "true"
    fsType     = "ext4"
    throughput = "1000"
    iops       = "16000"
  }
  
  depends_on = [module.eks_cluster]
}

resource "kubernetes_storage_class" "local_storage" {
  metadata {
    name = "local-storage"
  }
  
  storage_provisioner = "kubernetes.io/no-provisioner"
  volume_binding_mode = "WaitForFirstConsumer"
  
  depends_on = [module.eks_cluster]
}

# Network Policies
resource "kubectl_manifest" "default_deny_all" {
  for_each = toset([
    "prefect-prod",
    "minio-prod", 
    "s5cmd-prod"
  ])
  
  yaml_body = yamlencode({
    apiVersion = "networking.k8s.io/v1"
    kind       = "NetworkPolicy"
    metadata = {
      name      = "default-deny-all"
      namespace = each.value
    }
    spec = {
      podSelector = {}
      policyTypes = ["Ingress", "Egress"]
    }
  })
  
  depends_on = [kubernetes_namespace.application_namespaces]
}

# S3 Buckets for Application Data
resource "aws_s3_bucket" "application_buckets" {
  for_each = toset([
    "crypto-lakehouse-bronze-${var.environment}",
    "crypto-lakehouse-silver-${var.environment}",
    "crypto-lakehouse-gold-${var.environment}",
    "crypto-lakehouse-backups-${var.environment}"
  ])
  
  bucket = "${each.value}-${random_string.bucket_suffix.result}"
  
  tags = merge(local.common_tags, {
    Purpose = split("-", each.value)[2] # bronze, silver, gold, or backups
  })
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 Bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "application_bucket_encryption" {
  for_each = aws_s3_bucket.application_buckets
  
  bucket = each.value.id
  
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = module.security.s3_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# S3 Bucket versioning
resource "aws_s3_bucket_versioning" "application_bucket_versioning" {
  for_each = aws_s3_bucket.application_buckets
  
  bucket = each.value.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket lifecycle policies
resource "aws_s3_bucket_lifecycle_configuration" "application_bucket_lifecycle" {
  for_each = {
    for bucket in aws_s3_bucket.application_buckets :
    bucket.bucket => bucket
    if contains(["bronze", "silver"], split("-", bucket.bucket)[2])
  }
  
  bucket = each.value.id
  
  rule {
    id     = "data_lifecycle"
    status = "Enabled"
    
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
    
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# Outputs
output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks_cluster.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks_cluster.cluster_id
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks_cluster.cluster_arn
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

output "s3_buckets" {
  description = "S3 bucket names"
  value = {
    for bucket in aws_s3_bucket.application_buckets :
    split("-", bucket.bucket)[2] => bucket.bucket
  }
}

output "istio_gateway_ip" {
  description = "Istio ingress gateway external IP"
  value       = helm_release.istio_gateway.status[0].load_balancer[0].ingress[0].ip
}

output "monitoring_endpoints" {
  description = "Monitoring service endpoints"
  value = {
    prometheus = "http://prometheus.monitoring.svc.cluster.local:9090"
    grafana    = "http://grafana.monitoring.svc.cluster.local:3000"
    alertmanager = "http://alertmanager.monitoring.svc.cluster.local:9093"
  }
}