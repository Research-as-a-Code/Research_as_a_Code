#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Script to deploy NVIDIA NIMs using Helm charts
# Deploys: Nemotron-Nano-8B (reasoning/instruct), Embedding NIM

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

# Deploy NIM Operator first
echo ""
echo "=================================================="
echo "Deploying NVIDIA NIM Operator..."
echo "=================================================="

helm upgrade --install nim-operator nvidia/k8s-nim-operator \
    --namespace nim-operator \
    --create-namespace \
    --wait \
    --timeout=10m

echo "✅ NIM Operator deployed"

# Wait for operator to be ready
echo "Waiting for NIM Operator to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/k8s-nim-operator -n nim-operator || true

# Create NIM Custom Resources using kubectl
echo ""
echo "=================================================="
echo "Deploying NIMs using operator..."
echo "=================================================="

# Create a NIM deployment manifest for Nemotron-Nano-8B (Hackathon requirement)
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llama-instruct-nim
  namespace: nim
spec:
  replicas: 1
  selector:
    matchLabels:
      app: llama-instruct-nim
  template:
    metadata:
      labels:
        app: llama-instruct-nim
    spec:
      containers:
      - name: nim
        image: nvcr.io/nim/nvidia/llama-3.1-nemotron-nano-8b-v1:latest
        env:
        - name: NGC_API_KEY
          valueFrom:
            secretKeyRef:
              name: ngc-api-key
              key: NGC_API_KEY
        - name: NIM_CACHE_PATH
          value: /model-cache
        ports:
        - containerPort: 8000
          name: http
        resources:
          limits:
            nvidia.com/gpu: "1"
          requests:
            nvidia.com/gpu: "1"
        volumeMounts:
        - name: model-cache
          mountPath: /model-cache
      volumes:
      - name: model-cache
        emptyDir: {}
      nodeSelector:
        workload-type: nvidia-nim
      tolerations:
      - key: nvidia.com/gpu
        operator: Equal
        value: "true"
        effect: NoSchedule
---
apiVersion: v1
kind: Service
metadata:
  name: instruct-llm-service
  namespace: nim
spec:
  selector:
    app: llama-instruct-nim
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  type: ClusterIP
EOF

echo "✅ Llama Instruct NIM deployed"

# Deploy a lightweight embedding model
echo ""
echo "Deploying Embedding NIM..."

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: embedding-nim
  namespace: nim
spec:
  replicas: 1
  selector:
    matchLabels:
      app: embedding-nim
  template:
    metadata:
      labels:
        app: embedding-nim
    spec:
      containers:
      - name: nim
        image: nvcr.io/nim/snowflake/arctic-embed-l:1.0.1
        env:
        - name: NGC_API_KEY
          valueFrom:
            secretKeyRef:
              name: ngc-api-key
              key: NGC_API_KEY
        ports:
        - containerPort: 8000
          name: http
        resources:
          limits:
            nvidia.com/gpu: "1"
          requests:
            nvidia.com/gpu: "1"
      nodeSelector:
        workload-type: nvidia-nim
      tolerations:
      - key: nvidia.com/gpu
        operator: Equal
        value: "true"
        effect: NoSchedule
---
apiVersion: v1
kind: Service
metadata:
  name: embedding-service
  namespace: nim
spec:
  selector:
    app: embedding-nim
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  type: ClusterIP
EOF

echo "✅ Embedding NIM deployed"

echo ""
echo "=================================================="
echo "✅ All NVIDIA NIMs deployed successfully!"
echo "=================================================="
echo ""
echo "Deployed NIMs:"
echo "  1. Nemotron-Nano-8B    → instruct-llm-service.nim.svc.cluster.local:8000"
echo "  2. Embedding NIM       → embedding-service.nim.svc.cluster.local:8000"
echo ""
echo "Check status:"
echo "  kubectl get pods -n nim"
echo "  kubectl get pods -n nim-operator"
echo "  kubectl get svc -n nim"
echo ""
echo "View logs (example):"
echo "  kubectl logs -n nim -l app=llama-instruct-nim -f"
echo "  kubectl logs -n nim -l app=embedding-nim -f"
echo ""
echo "Note: NIMs may take 5-10 minutes to pull images and start"
echo "Monitor progress: kubectl get pods -n nim -w"
echo ""
echo "Next step: Deploy the AI-Q agent"
echo "  ./deploy-agent.sh"
echo "=================================================="

