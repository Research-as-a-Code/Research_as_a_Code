#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Installation script for AI-Q + UDF on AWS EKS
# Based on awslabs/data-on-eks pattern

set -e

echo "=================================================="
echo "AI-Q + UDF Hackathon - EKS Deployment Script"
echo "=================================================="

# Check prerequisites
command -v terraform >/dev/null 2>&1 || { echo "Error: terraform not installed"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl not installed"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "Error: AWS CLI not installed"; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "Error: helm not installed"; exit 1; }

# Check environment variables
if [ -z "$TF_VAR_ngc_api_key" ]; then
    echo "Error: TF_VAR_ngc_api_key not set"
    echo "Please export TF_VAR_ngc_api_key=<your_ngc_api_key>"
    exit 1
fi

# Set defaults
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
export TF_VAR_aws_region="$AWS_DEFAULT_REGION"

echo ""
echo "Configuration:"
echo "  AWS Region: $AWS_DEFAULT_REGION"
echo "  NGC API Key: ${TF_VAR_ngc_api_key:0:10}..."
echo ""

read -p "Continue with deployment? (yes/no) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo "Step 1/6: Initializing Terraform..."
terraform init

echo ""
echo "Step 2/6: Deploying EKS cluster first (this will take ~15 minutes)..."
echo "Note: Deploying in two stages to ensure cluster is ready for Helm charts"
terraform apply -target=module.eks -target=module.vpc -target=module.karpenter -auto-approve

echo ""
echo "Step 3/6: Configuring kubectl to connect to new cluster..."
CLUSTER_NAME=$(terraform output -raw cluster_name)
aws eks update-kubeconfig --region $AWS_DEFAULT_REGION --name $CLUSTER_NAME

echo ""
echo "Step 4/6: Deploying Helm charts (Karpenter, GPU Operator)..."
echo "Now that cluster is ready, deploying Helm charts..."
terraform apply -auto-approve

echo ""
echo "Step 5/6: Waiting for Karpenter to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/karpenter -n karpenter || echo "Warning: Karpenter not ready yet"

echo ""
echo "Step 6/6: Applying Karpenter NodePool configuration..."
kubectl apply -f karpenter-provisioner.yaml

echo ""
echo "=================================================="
echo "✅ Infrastructure deployment complete!"
echo "=================================================="
echo ""
echo "Cluster Name: $CLUSTER_NAME"
echo "Region: $AWS_DEFAULT_REGION"
echo ""
echo "Next steps:"
echo "1. Deploy NVIDIA NIMs: cd ../kubernetes && ./deploy-nims.sh"
echo "2. Deploy AI-Q agent: cd ../kubernetes && ./deploy-agent.sh"
echo "3. Access the application via the LoadBalancer URL"
echo ""
echo "To destroy infrastructure: terraform destroy"
echo "=================================================="


