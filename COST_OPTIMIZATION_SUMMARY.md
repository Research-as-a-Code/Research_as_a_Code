# Cost Optimization Summary - Spot Instances

**Status:** ✅ Ready to Deploy  
**Date:** December 2, 2025

---

## 💰 Quick Cost Analysis

| Metric | Current (On-Demand) | Optimized (Spot + On-Demand) | Savings |
|--------|---------------------|------------------------------|---------|
| **Monthly Cost** | $2,895 | $1,008 | **$1,887 (65%)** |
| **Annual Cost** | $34,740 | $12,096 | **$22,644** |
| **Hourly Cost** | $4.02 | $1.40 | **$2.62** |

---

## 🎯 What Changed

### ✅ Now Running on Spot (70% cheaper)
- **GPU Nodes (g5.2xlarge):** 3 nodes for NVIDIA NIMs
- **System Worker Nodes (m5.xlarge):** 2 nodes for backend/frontend

### 🛡️ Still on On-Demand (Protected)
- **Milvus Vector Database:** 1 node (data persistence)
- **etcd/MinIO/Kafka:** On same node (critical metadata)

---

## 🚀 How to Deploy

```bash
cd infrastructure
./migrate-to-spot.sh
```

**Duration:** 10-15 minutes  
**Downtime:** None (rolling updates)

---

## 📊 What's Safe / What's Not

### ✅ Safe on Spot (Interruptions OK)

| Component | Why Safe | Recovery Time |
|-----------|----------|---------------|
| **NVIDIA NIMs** | Stateless, model re-downloads | 3-5 minutes |
| **Backend/Frontend** | 2 replicas, PDB protection | 30 seconds |

### ❌ Not Safe on Spot (Data Loss Risk)

| Component | Why Protected | Location |
|-----------|---------------|----------|
| **Milvus** | Vector embeddings (97 PDFs) | On-demand node |
| **etcd** | Milvus metadata | On-demand node |
| **MinIO** | Vector object storage | On-demand node |

---

## 🛡️ Protection Mechanisms

1. **Pod Disruption Budgets:** At least 1 replica always running
2. **Karpenter Interruption Queue:** 2-minute warning before termination
3. **Node Affinity:** Critical services pinned to on-demand
4. **Capacity Fallback:** Spot → on-demand if unavailable

---

## 📈 Monitoring Commands

### Watch Spot Interruptions
```bash
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter -f
```

### Check Node Types
```bash
kubectl get nodes -L karpenter.sh/capacity-type
```

### Verify PDB Protection
```bash
kubectl get pdb --all-namespaces
```

### Monitor Costs (after 24 hours)
```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '7 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost
```

---

## 🔄 Rollback (if needed)

### Quick Revert
```bash
# Revert Karpenter to on-demand
kubectl edit nodepool nvidia-nim-gpu -n karpenter
# Change: values: ["spot", "on-demand"] → values: ["on-demand"]
```

### Full Rollback
```bash
cd infrastructure/terraform
git checkout HEAD -- main.tf karpenter-provisioner.yaml
terraform apply
kubectl apply -f karpenter-provisioner.yaml
```

---

## 📋 Files Modified

1. `infrastructure/terraform/karpenter-provisioner.yaml` - Spot priority for GPU
2. `infrastructure/terraform/main.tf` - Added spot system node group
3. `infrastructure/helm/milvus-standalone-values.yaml` - Pin to on-demand
4. `infrastructure/kubernetes/pod-disruption-budgets.yaml` - New file (PDBs)
5. `infrastructure/migrate-to-spot.sh` - New file (deployment script)

---

## ✅ Success Checklist

After deployment, verify:

- [ ] GPU nodes labeled `capacity-type: spot`
- [ ] System spot nodes running
- [ ] Milvus/etcd/MinIO on on-demand nodes
- [ ] PDBs active (`kubectl get pdb --all-namespaces`)
- [ ] No service interruptions during testing
- [ ] Cost reduction visible in AWS console (next day)

---

## 📚 Full Documentation

See `infrastructure/SPOT_INSTANCE_STRATEGY.md` for complete details.

---

**Ready to save ~$1,900/month?** Run `./infrastructure/migrate-to-spot.sh`

