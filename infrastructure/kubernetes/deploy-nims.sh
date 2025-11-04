#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Script to deploy NVIDIA NIMs using Helm charts
# Deploys: Nemotron (reasoning), Llama 3.3 (instruct), Embedding NIM

set -e

echo "=================================================="
echo "Deploying NVIDIA NIMs to EKS Cluster"
echo "=================================================="

# Check prerequisites
command -v helm >/dev/null 2>&1 || { echo "Error: helm not installed"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "Error: kubectl not installed"; exit 1; }

if [ -z "$NGC_API_KEY" ]; then
    echo "Error: NGC_API_KEY environment variable not set"
    exit 1
fi

echo ""
echo "NGC API Key: ${NGC_API_KEY:0:10}..."
echo "Current context: $(kubectl config current-context)"
echo ""

read -p "Continue with NIM deployment? (yes/no) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

# Create namespace
echo ""
echo "Creating namespace 'nim'..."
kubectl create namespace nim --dry-run=client -o yaml | kubectl apply -f -

# Create NGC API key secret
echo ""
echo "Creating NGC API key secret..."
kubectl create secret generic ngc-api-key \
    --from-literal=NGC_API_KEY=$NGC_API_KEY \
    --namespace=nim \
    --dry-run=client -o yaml | kubectl apply -f -

# Add NVIDIA Helm repo
echo ""
echo "Adding NVIDIA Helm repository..."
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Deploy 1: Nemotron Reasoning NIM (llama-3.3-nemotron-super-49b-v1.5)
echo ""
echo "=================================================="
echo "Deploying Nemotron Reasoning NIM..."
echo "=================================================="

helm upgrade --install nemotron-nano-nim nvidia/nim-llm \
    --namespace nim \
    --create-namespace \
    --set model.ngcAPIKey=$NGC_API_KEY \
    --set image.repository="nvcr.io/nim/nvidia/llama-3.3-nemotron-super-49b-v1.5" \
    --set image.tag="latest" \
    --set resources.limits."nvidia\.com/gpu"=1 \
    --set resources.requests."nvidia\.com/gpu"=1 \
    --set service.name="nemotron-nano-service" \
    --set service.type="ClusterIP" \
    --set service.port=8000 \
    --set replicaCount=1 \
    --set persistence.enabled=true \
    --set persistence.size="100Gi" \
    --set nodeSelector."workload-type"="nvidia-nim" \
    --set tolerations[0].key="nvidia.com/gpu" \
    --set tolerations[0].operator="Equal" \
    --set tolerations[0].value="true" \
    --set tolerations[0].effect="NoSchedule" \
    --wait \
    --timeout=20m

echo "✅ Nemotron NIM deployed"

# Deploy 2: Llama 3.3 70B Instruct NIM
echo ""
echo "=================================================="
echo "Deploying Llama 3.3 70B Instruct NIM..."
echo "=================================================="

helm upgrade --install instruct-llm-nim nvidia/nim-llm \
    --namespace nim \
    --set model.ngcAPIKey=$NGC_API_KEY \
    --set image.repository="nvcr.io/nim/meta/llama-3.3-70b-instruct" \
    --set image.tag="latest" \
    --set resources.limits."nvidia\.com/gpu"=2 \
    --set resources.requests."nvidia\.com/gpu"=2 \
    --set service.name="instruct-llm-service" \
    --set service.type="ClusterIP" \
    --set service.port=8000 \
    --set replicaCount=1 \
    --set persistence.enabled=true \
    --set persistence.size="200Gi" \
    --set nodeSelector."workload-type"="nvidia-nim" \
    --set tolerations[0].key="nvidia.com/gpu" \
    --set tolerations[0].operator="Equal" \
    --set tolerations[0].value="true" \
    --set tolerations[0].effect="NoSchedule" \
    --wait \
    --timeout=20m

echo "✅ Instruct LLM NIM deployed"

# Deploy 3: Embedding NIM
echo ""
echo "=================================================="
echo "Deploying Embedding NIM..."
echo "=================================================="

helm upgrade --install embedding-nim nvidia/text-embedding-nim \
    --namespace nim \
    --set model.ngcAPIKey=$NGC_API_KEY \
    --set image.repository="nvcr.io/nim/snowflake/arctic-embed-l" \
    --set image.tag="1.0.1" \
    --set resources.limits."nvidia\.com/gpu"=1 \
    --set resources.requests."nvidia\.com/gpu"=1 \
    --set service.name="embedding-service" \
    --set service.type="ClusterIP" \
    --set service.port=8000 \
    --set persistence.enabled=true \
    --set persistence.size="50Gi" \
    --set nodeSelector."workload-type"="nvidia-nim" \
    --set tolerations[0].key="nvidia.com/gpu" \
    --set tolerations[0].operator="Equal" \
    --set tolerations[0].value="true" \
    --set tolerations[0].effect="NoSchedule" \
    --wait \
    --timeout=15m

echo "✅ Embedding NIM deployed"

echo ""
echo "=================================================="
echo "✅ All NVIDIA NIMs deployed successfully!"
echo "=================================================="
echo ""
echo "Deployed NIMs:"
echo "  1. Nemotron Reasoning  → nemotron-nano-service.nim.svc.cluster.local:8000"
echo "  2. Llama 3.3 Instruct  → instruct-llm-service.nim.svc.cluster.local:8000"
echo "  3. Embedding NIM       → embedding-service.nim.svc.cluster.local:8000"
echo ""
echo "Check status:"
echo "  kubectl get pods -n nim"
echo "  kubectl get svc -n nim"
echo ""
echo "View logs (example):"
echo "  kubectl logs -n nim -l app.kubernetes.io/instance=nemotron-nano-nim -f"
echo ""
echo "Next step: Deploy the AI-Q agent"
echo "  ./deploy-agent.sh"
echo "=================================================="

