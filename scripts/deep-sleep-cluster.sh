#!/bin/bash
# Deep Sleep - Maximum Cost Savings (Alternative Mode)
# 
# This script provides MAXIMUM cost savings by stopping ALL components
# including Milvus and Frontend. Best for extended downtime (weekend/vacation).
#
# WHEN TO USE:
#   ✅ Extended downtime (2+ days)
#   ✅ Maximum cost savings needed (95% vs 90%)
#   ✅ Not urgently needed tomorrow
#
# For daily use, prefer: ./infrastructure/scripts/sleep-cluster.sh
#   - Faster wake times (Milvus stays warm)
#   - 90% cost savings
#   - Better for development workflow

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
echo "To wake up later, run: ./scripts/deep-wake-cluster.sh"
echo ""
echo "💡 TIP: For faster wake times, use the standard scripts:"
echo "   ./infrastructure/scripts/sleep-cluster.sh (keeps Milvus warm)"

