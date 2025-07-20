# Terraform Variables for Crypto Lakehouse Infrastructure
# Based on Phase 2: Design Specifications
# Version: 3.0.0
# Date: 2025-07-20

# General Configuration
variable "environment" {
  description = "Environment name (development, staging, production)"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "aws_region" {
  description = "AWS region for infrastructure deployment"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "crypto-lakehouse"
}

# Networking Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "VPC CIDR must be a valid IPv4 CIDR block."
  }
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

# EKS Configuration
variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
  validation {
    condition     = can(regex("^1\\.(2[8-9]|[3-9][0-9])$", var.kubernetes_version))
    error_message = "Kubernetes version must be 1.28 or higher."
  }
}

variable "cluster_endpoint_private_access" {
  description = "Enable private API server endpoint"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access" {
  description = "Enable public API server endpoint"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDR blocks that can access the public endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# Node Group Configuration
variable "node_groups_config" {
  description = "Configuration for EKS node groups"
  type = map(object({
    instance_types = list(string)
    capacity_type  = string
    min_size       = number
    max_size       = number
    desired_size   = number
    disk_size      = number
    labels         = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
  
  default = {
    general_workload = {
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
      instance_types = ["c5n.2xlarge", "c5n.4xlarge"]
      capacity_type  = "ON_DEMAND"
      min_size       = 2
      max_size       = 8
      desired_size   = 2
      disk_size      = 500
      labels = {
        "workload"            = "data-intensive"
        "node-role"           = "worker"
        "network-performance" = "high"
      }
      taints = [{
        key    = "workload"
        value  = "data-intensive"
        effect = "NO_SCHEDULE"
      }]
    }
    
    storage_nodes = {
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

# Application Configuration
variable "prefect_config" {
  description = "Prefect configuration parameters"
  type = object({
    server_replicas     = number
    worker_pool_configs = map(object({
      replicas     = number
      resources = object({
        requests = object({
          cpu    = string
          memory = string
        })
        limits = object({
          cpu    = string
          memory = string
        })
      })
    }))
  })
  
  default = {
    server_replicas = 3
    worker_pool_configs = {
      general = {
        replicas = 5
        resources = {
          requests = {
            cpu    = "500m"
            memory = "1Gi"
          }
          limits = {
            cpu    = "2000m"
            memory = "4Gi"
          }
        }
      }
      s5cmd_optimized = {
        replicas = 3
        resources = {
          requests = {
            cpu    = "2000m"
            memory = "4Gi"
          }
          limits = {
            cpu    = "4000m"
            memory = "8Gi"
          }
        }
      }
    }
  }
}

variable "minio_config" {
  description = "MinIO configuration parameters"
  type = object({
    replicas       = number
    storage_size   = string
    storage_class  = string
    erasure_coding = string
    resources = object({
      requests = object({
        cpu    = string
        memory = string
      })
      limits = object({
        cpu    = string
        memory = string
      })
    })
  })
  
  default = {
    replicas       = 4
    storage_size   = "25Ti"
    storage_class  = "local-storage"
    erasure_coding = "EC:4"
    resources = {
      requests = {
        cpu    = "2000m"
        memory = "4Gi"
      }
      limits = {
        cpu    = "4000m"
        memory = "8Gi"
      }
    }
  }
}

variable "s5cmd_config" {
  description = "s5cmd executor configuration parameters"
  type = object({
    replicas         = number
    version          = string
    max_concurrent   = number
    part_size_mb     = number
    resources = object({
      requests = object({
        cpu    = string
        memory = string
      })
      limits = object({
        cpu    = string
        memory = string
      })
    })
  })
  
  default = {
    replicas       = 3
    version        = "v2.2.2"
    max_concurrent = 32
    part_size_mb   = 50
    resources = {
      requests = {
        cpu    = "1000m"
        memory = "2Gi"
      }
      limits = {
        cpu    = "4000m"
        memory = "8Gi"
      }
    }
  }
}

# Monitoring Configuration
variable "monitoring_config" {
  description = "Monitoring and observability configuration"
  type = object({
    prometheus = object({
      retention     = string
      storage_size  = string
      storage_class = string
    })
    grafana = object({
      admin_password = string
      storage_size   = string
      storage_class  = string
    })
    alertmanager = object({
      storage_size  = string
      storage_class = string
    })
    jaeger = object({
      enabled       = bool
      storage_type  = string
      retention     = string
    })
  })
  
  default = {
    prometheus = {
      retention     = "30d"
      storage_size  = "100Gi"
      storage_class = "gp3"
    }
    grafana = {
      admin_password = "admin123"  # Should be overridden in environment files
      storage_size   = "10Gi"
      storage_class  = "gp3"
    }
    alertmanager = {
      storage_size  = "10Gi"
      storage_class = "gp3"
    }
    jaeger = {
      enabled      = true
      storage_type = "elasticsearch"
      retention    = "7d"
    }
  }
}

# Security Configuration
variable "security_config" {
  description = "Security configuration parameters"
  type = object({
    enable_pod_security_policy     = bool
    enable_network_policies        = bool
    enable_service_mesh_security   = bool
    secrets_backend                = string
    kms_key_rotation_enabled       = bool
    audit_logging_enabled          = bool
  })
  
  default = {
    enable_pod_security_policy   = true
    enable_network_policies      = true
    enable_service_mesh_security = true
    secrets_backend             = "aws_secrets_manager"
    kms_key_rotation_enabled    = true
    audit_logging_enabled       = true
  }
}

# Backup Configuration
variable "backup_config" {
  description = "Backup and disaster recovery configuration"
  type = object({
    retention_days = number
    backup_schedule = string
    cross_region_replication = bool
    backup_encryption = bool
  })
  
  default = {
    retention_days           = 30
    backup_schedule         = "0 2 * * *"  # Daily at 2 AM
    cross_region_replication = true
    backup_encryption       = true
  }
}

# Cost Optimization Configuration
variable "cost_optimization" {
  description = "Cost optimization settings"
  type = object({
    enable_spot_instances     = bool
    spot_instance_percentage  = number
    enable_cluster_autoscaler = bool
    enable_vpa               = bool
    reserved_instance_coverage = number
  })
  
  default = {
    enable_spot_instances      = true
    spot_instance_percentage   = 50
    enable_cluster_autoscaler  = true
    enable_vpa                = true
    reserved_instance_coverage = 70
  }
}

# Environment-specific overrides
variable "environment_overrides" {
  description = "Environment-specific configuration overrides"
  type = map(object({
    node_count_multiplier = number
    storage_size_multiplier = number
    monitoring_level = string
    backup_retention_days = number
  }))
  
  default = {
    development = {
      node_count_multiplier   = 0.5
      storage_size_multiplier = 0.1
      monitoring_level       = "basic"
      backup_retention_days  = 7
    }
    staging = {
      node_count_multiplier   = 0.75
      storage_size_multiplier = 0.5
      monitoring_level       = "enhanced"
      backup_retention_days  = 14
    }
    production = {
      node_count_multiplier   = 1.0
      storage_size_multiplier = 1.0
      monitoring_level       = "comprehensive"
      backup_retention_days  = 30
    }
  }
}

# Feature Flags
variable "feature_flags" {
  description = "Feature flags for enabling/disabling components"
  type = object({
    enable_istio_service_mesh = bool
    enable_argocd_gitops     = bool
    enable_external_secrets   = bool
    enable_cluster_autoscaler = bool
    enable_vertical_pod_autoscaler = bool
    enable_prometheus_stack   = bool
    enable_jaeger_tracing    = bool
    enable_vault_integration = bool
  })
  
  default = {
    enable_istio_service_mesh     = true
    enable_argocd_gitops         = true
    enable_external_secrets       = true
    enable_cluster_autoscaler     = true
    enable_vertical_pod_autoscaler = true
    enable_prometheus_stack       = true
    enable_jaeger_tracing        = true
    enable_vault_integration     = false  # Set to true if using HashiCorp Vault
  }
}

# Additional Configuration
variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
  default     = "admin123"  # Should be overridden
}

variable "slack_webhook_url" {
  description = "Slack webhook URL for alerting"
  type        = string
  sensitive   = true
  default     = ""
}

variable "domain_name" {
  description = "Domain name for ingress resources"
  type        = string
  default     = "crypto-lakehouse.local"
}

variable "enable_cross_region_backup" {
  description = "Enable cross-region backup replication"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be a valid CloudWatch retention period."
  }
}

# Resource Tagging
variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}