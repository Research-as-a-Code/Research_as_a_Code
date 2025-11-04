# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

/**
 * Terraform Configuration for AI-Q + UDF on AWS EKS
 * 
 * Based on awslabs/data-on-eks blueprint
 * Deploys: EKS cluster + Karpenter + NVIDIA GPU Operator + NIMs
 * 
 * Reference: https://github.com/awslabs/data-on-eks
 */

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
}

# ========================================
# Local Variables
# ========================================

locals {
  name   = var.cluster_name
  region = var.aws_region

  vpc_cidr = "10.0.0.0/16"
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = merge(var.tags, {
    Blueprint  = "ai-q-udf-hackathon"
    GithubRepo = "Research_as_a_Code"
  })
}

# ========================================
# Data Sources
# ========================================

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

# ========================================
# VPC Module
# ========================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 4, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 48)]

  enable_nat_gateway   = true
  single_nat_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Kubernetes tags for subnet discovery
  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
    # Karpenter tags
    "karpenter.sh/discovery" = local.name
  }

  tags = local.tags
}

# ========================================
# EKS Module
# ========================================

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = local.name
  cluster_version = var.eks_cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Cluster endpoint access
  cluster_endpoint_public_access = true
  cluster_endpoint_private_access = true

  # Add-ons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }

  # Managed node groups for system workloads
  eks_managed_node_groups = {
    system = {
      name           = "${local.name}-system"
      instance_types = ["m5.xlarge"]
      
      min_size     = 2
      max_size     = 4
      desired_size = 2

      subnet_ids = module.vpc.private_subnets

      labels = {
        role = "system"
      }

      tags = merge(local.tags, {
        "Name" = "${local.name}-system-node"
      })
    }
  }

  # Enable IRSA (IAM Roles for Service Accounts)
  enable_irsa = true

  tags = local.tags
}

# ========================================
# Karpenter for GPU Auto-Scaling
# ========================================

module "karpenter" {
  source  = "terraform-aws-modules/eks/aws//modules/karpenter"
  version = "~> 19.0"

  cluster_name = module.eks.cluster_name

  irsa_oidc_provider_arn = module.eks.oidc_provider_arn
  
  # Karpenter node IAM role
  node_iam_role_additional_policies = {
    AmazonSSMManagedInstanceCore = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  }

  tags = local.tags
}

# Karpenter Helm Chart
resource "helm_release" "karpenter" {
  namespace        = "karpenter"
  create_namespace = true

  name       = "karpenter"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = "v0.32.0"

  set {
    name  = "settings.clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "settings.clusterEndpoint"
    value = module.eks.cluster_endpoint
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.karpenter.irsa_arn
  }

  set {
    name  = "settings.interruptionQueue"
    value = module.karpenter.queue_name
  }

  depends_on = [
    module.eks
  ]
}

# ========================================
# NVIDIA GPU Operator
# ========================================

resource "helm_release" "nvidia_gpu_operator" {
  namespace        = "gpu-operator"
  create_namespace = true

  name       = "gpu-operator"
  repository = "https://helm.ngc.nvidia.com/nvidia"
  chart      = "gpu-operator"
  version    = "v23.9.1"

  set {
    name  = "operator.defaultRuntime"
    value = "containerd"
  }

  set {
    name  = "driver.enabled"
    value = "true"
  }

  set {
    name  = "toolkit.enabled"
    value = "true"
  }

  depends_on = [
    helm_release.karpenter
  ]
}

# ========================================
# Outputs
# ========================================

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "EKS cluster CA certificate"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${local.region} --name ${module.eks.cluster_name}"
}

output "karpenter_irsa_arn" {
  description = "Karpenter IRSA ARN"
  value       = module.karpenter.irsa_arn
}

output "karpenter_instance_profile" {
  description = "Karpenter instance profile"
  value       = module.karpenter.instance_profile_name
}

