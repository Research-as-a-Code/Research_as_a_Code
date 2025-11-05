#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Script to deploy the AI-Q + UDF agent to EKS

set -e

echo "=================================================="
echo "Deploying AI-Q + UDF Agent to EKS"
echo "=================================================="

# Check prerequisites
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl not installed"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Error: docker not installed"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "Error: AWS CLI not installed"; exit 1; }

# Get AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_DEFAULT_REGION:-us-west-2}

echo ""
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo "Current context: $(kubectl config current-context)"
echo ""

# Check environment variables
if [ -z "$NGC_API_KEY" ]; then
    echo "Warning: NGC_API_KEY not set"
    read -p "Enter NGC API Key: " NGC_API_KEY
fi

if [ -z "$TAVILY_API_KEY" ]; then
    echo "Warning: TAVILY_API_KEY not set (optional for web search)"
    TAVILY_API_KEY=""
fi

# Step 1: Create ECR repositories if they don't exist
echo ""
echo "Step 1/5: Creating ECR repositories..."

aws ecr describe-repositories --repository-names aiq-agent --region $AWS_REGION >/dev/null 2>&1 || \
    aws ecr create-repository --repository-name aiq-agent --region $AWS_REGION

aws ecr describe-repositories --repository-names aiq-frontend --region $AWS_REGION >/dev/null 2>&1 || \
    aws ecr create-repository --repository-name aiq-frontend --region $AWS_REGION

echo "✅ ECR repositories ready"

# Step 2: Build and push Docker images
echo ""
echo "Step 2/5: Building and pushing Docker images..."

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build backend
echo "Building backend image..."
cd ../..  # Go to project root
docker build -f backend/Dockerfile -t aiq-agent:latest .
docker tag aiq-agent:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-agent:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-agent:latest

# Build frontend
echo "Building frontend image..."
docker build -f frontend/Dockerfile -t aiq-frontend:latest .
docker tag aiq-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-frontend:latest

cd infrastructure/kubernetes

echo "✅ Docker images built and pushed"

# Step 3: Apply Kubernetes manifests
echo ""
echo "Step 3/5: Applying Kubernetes manifests..."

# Replace placeholders in manifest
export NGC_API_KEY AWS_ACCOUNT_ID AWS_REGION TAVILY_API_KEY
envsubst < agent-deployment.yaml | kubectl apply -f -

echo "✅ Kubernetes manifests applied"

# Step 4: Wait for deployments
echo ""
echo "Step 4/5: Waiting for deployments to be ready..."

kubectl wait --for=condition=available --timeout=300s \
    deployment/aiq-agent-backend -n aiq-agent

kubectl wait --for=condition=available --timeout=300s \
    deployment/aiq-agent-frontend -n aiq-agent

echo "✅ Deployments ready"

# Step 5: Get LoadBalancer URL
echo ""
echo "Step 5/5: Retrieving application URL..."

echo "Waiting for LoadBalancer to be assigned (this may take a few minutes)..."
kubectl wait --for=jsonpath='{.status.loadBalancer.ingress}' \
    service/aiq-agent-frontend -n aiq-agent --timeout=5m

FRONTEND_URL=$(kubectl get svc aiq-agent-frontend -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo ""
echo "=================================================="
echo "✅ AI-Q + UDF Agent deployed successfully!"
echo "=================================================="
echo ""
echo "Application URL: http://$FRONTEND_URL"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n aiq-agent"
echo "  kubectl logs -n aiq-agent -l app=aiq-agent,component=backend -f"
echo "  kubectl logs -n aiq-agent -l app=aiq-agent,component=frontend -f"
echo ""
echo "To uninstall:"
echo "  kubectl delete namespace aiq-agent"
echo "=================================================="

