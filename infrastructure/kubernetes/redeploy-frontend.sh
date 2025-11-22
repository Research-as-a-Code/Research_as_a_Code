#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Quick script to redeploy only the frontend with latest code changes

set -e

echo "=================================================="
echo "Redeploying Frontend with Latest Code"
echo "=================================================="

# Get AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_DEFAULT_REGION:-us-west-2}

echo ""
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo ""

# Get backend URL
echo "Getting backend URL..."
BACKEND_URL=$(kubectl get svc aiq-agent-service -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Backend URL: http://$BACKEND_URL"
echo ""

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build frontend
echo ""
echo "Building frontend Docker image with StrategyToggle..."
cd ../..  # Go to project root
docker build --no-cache --pull -f frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_BACKEND_URL="http://$BACKEND_URL" \
    -t aiq-frontend:latest .

# Tag and push
docker tag aiq-frontend:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-frontend:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-frontend:latest

echo "✅ Frontend image built and pushed"
echo ""

# Restart frontend pods to pull new image
echo "Restarting frontend pods..."
kubectl rollout restart deployment/aiq-agent-frontend -n aiq-agent

# Wait for rollout
echo "Waiting for new pods to be ready..."
kubectl rollout status deployment/aiq-agent-frontend -n aiq-agent --timeout=5m

echo ""
echo "=================================================="
echo "✅ Frontend redeployed successfully!"
echo "=================================================="
echo ""

FRONTEND_URL=$(kubectl get svc aiq-agent-frontend -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Frontend URL: http://$FRONTEND_URL"
echo ""
echo "The StrategyToggle (UDR vs TTD-DR) should now be visible!"
echo "It's located in the 'Agentic Flow' section below the research form."
echo ""
echo "=================================================="

