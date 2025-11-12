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
docker build --no-cache --pull -f backend/Dockerfile -t aiq-agent:latest .
docker tag aiq-agent:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-agent:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-agent:latest

echo "✅ Backend image built and pushed"
echo ""
echo "Note: Frontend will be built after backend LoadBalancer is ready"

cd infrastructure/kubernetes

# Step 3: Deploy backend only first
echo ""
echo "Step 3/7: Deploying backend..."

# Replace placeholders and deploy only backend and namespace
export NGC_API_KEY AWS_ACCOUNT_ID AWS_REGION TAVILY_API_KEY BACKEND_URL=""
envsubst < agent-deployment.yaml | kubectl apply -f - --dry-run=client -o yaml > /tmp/agent-full.yaml

# Extract and apply only namespace, backend, and backend service
kubectl apply -f /tmp/agent-full.yaml --selector='!component' 2>/dev/null || true
kubectl apply -f /tmp/agent-full.yaml --selector='component=backend' 2>/dev/null || true

echo "✅ Backend deployed"

# Step 4: Wait for backend LoadBalancer
echo ""
echo "Step 4/7: Waiting for backend LoadBalancer..."

kubectl wait --for=condition=available --timeout=300s \
    deployment/aiq-agent-backend -n aiq-agent

echo "Waiting for backend LoadBalancer URL (this may take 2-3 minutes)..."
kubectl wait --for=jsonpath='{.status.loadBalancer.ingress}' \
    service/aiq-agent-service -n aiq-agent --timeout=5m

BACKEND_URL=$(kubectl get svc aiq-agent-service -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "✅ Backend URL: http://$BACKEND_URL"

# Step 5: Build frontend with backend URL
echo ""
echo "Step 5/7: Building frontend with backend URL..."

cd ../..
docker build --no-cache --pull -f frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_BACKEND_URL="http://$BACKEND_URL" \
    -t aiq-frontend:latest .
docker tag aiq-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-frontend:latest

cd infrastructure/kubernetes
echo "✅ Frontend image built and pushed"

# Step 6: Deploy frontend
echo ""
echo "Step 6/7: Deploying frontend..."

export BACKEND_URL="http://$BACKEND_URL"
envsubst < agent-deployment.yaml | kubectl apply -f - --selector='component=frontend'

kubectl wait --for=condition=available --timeout=300s \
    deployment/aiq-agent-frontend -n aiq-agent

echo "✅ Frontend deployed"

# Step 7: Get frontend LoadBalancer URL
echo ""
echo "Step 7/7: Retrieving frontend URL..."

echo "Waiting for frontend LoadBalancer (this may take 2-3 minutes)..."
kubectl wait --for=jsonpath='{.status.loadBalancer.ingress}' \
    service/aiq-agent-frontend -n aiq-agent --timeout=5m

FRONTEND_URL=$(kubectl get svc aiq-agent-frontend -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo ""
echo "=================================================="
echo "✅ AI-Q + UDF Agent deployed successfully!"
echo "=================================================="
echo ""
echo "Application URLs:"
echo "  Frontend UI:      http://$FRONTEND_URL"
echo "  Backend API Docs: $BACKEND_URL/docs"
echo "  Backend Health:   $BACKEND_URL/health"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n aiq-agent"
echo "  kubectl logs -n aiq-agent -l app=aiq-agent,component=backend -f"
echo "  kubectl logs -n aiq-agent -l app=aiq-agent,component=frontend -f"
echo ""
echo "To uninstall:"
echo "  kubectl delete namespace aiq-agent"
echo "=================================================="

