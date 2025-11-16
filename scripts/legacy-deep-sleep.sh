#!/bin/bash
# LEGACY: Deep Sleep (Maximum Cost Savings)
# 
# ⚠️  This script provides MAXIMUM cost savings by stopping ALL components
# including Milvus and Frontend. Use this for extended downtime (weekend/vacation).
#
# For daily use, prefer: ./infrastructure/scripts/sleep-cluster.sh
# - Faster wake times (Milvus stays warm)
# - 90% cost savings (vs 95% here)
# - Better for development workflow

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
echo "To wake up tomorrow, run: ./scripts/legacy-deep-wake.sh"
echo ""
echo "💡 TIP: For faster wake times, use the new scripts:"
echo "   ./infrastructure/scripts/wake-cluster.sh (keeps Milvus warm)"

