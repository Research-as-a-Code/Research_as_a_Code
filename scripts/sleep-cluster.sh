#!/bin/bash
# Sleep cluster to save costs
# Keeps EKS control plane but stops all expensive compute

echo "💤 Putting cluster to sleep..."

echo ""
echo "Step 1: Scaling down all deployments..."
kubectl scale deployment --all --replicas=0 -n aiq-agent
kubectl scale deployment --all --replicas=0 -n nim
kubectl scale deployment --all --replicas=0 -n rag-blueprint 2>/dev/null || true

echo ""
echo "Step 2: Deleting all Karpenter-provisioned GPU nodes..."
kubectl delete nodeclaim --all

echo ""
echo "Step 3: Cluster status:"
kubectl get nodes
kubectl get pods --all-namespaces | grep -v "kube-system\|karpenter\|nvidia-gpu-operator" | grep -v "Completed"

echo ""
echo "✅ Cluster is now sleeping!"
echo ""
echo "💰 Cost: ~$0.10/hour (EKS control plane only)"
echo "📊 Savings: ~$3-5/hour (GPU nodes stopped)"
echo ""
echo "To wake up tomorrow, run: ./scripts/wake-cluster.sh"

