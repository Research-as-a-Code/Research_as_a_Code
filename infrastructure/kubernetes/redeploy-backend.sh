#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Quick script to redeploy only the backend with latest code changes

set -e

echo "=================================================="
echo "Redeploying Backend with Latest Code"
echo "=================================================="

# Get AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_DEFAULT_REGION:-us-west-2}

echo ""
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"
echo ""

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build backend
echo ""
echo "Building backend Docker image..."
cd ../..  # Go to project root
docker build --no-cache -f backend/Dockerfile -t aiq-agent:latest .

# Tag and push
docker tag aiq-agent:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-agent:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/aiq-agent:latest

echo "✅ Backend image built and pushed"
echo ""

# Restart backend pods to pull new image
echo "Restarting backend pods..."
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent

# Wait for rollout
echo "Waiting for new pods to be ready..."
kubectl rollout status deployment/aiq-agent-backend -n aiq-agent --timeout=5m

echo ""
echo "=================================================="
echo "✅ Backend redeployed successfully!"
echo "=================================================="

