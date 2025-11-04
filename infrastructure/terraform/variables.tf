# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "ai-q-udf-hackathon"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "eks_cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "ngc_api_key" {
  description = "NVIDIA NGC API Key for pulling NIM images"
  type        = string
  sensitive   = true
}

variable "tavily_api_key" {
  description = "Tavily API Key for web search"
  type        = string
  sensitive   = true
  default     = ""
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default = {
    Terraform   = "true"
    Environment = "hackathon"
    Project     = "AI-Q-UDF"
  }
}

