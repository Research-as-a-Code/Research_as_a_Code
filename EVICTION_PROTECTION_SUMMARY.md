# Eviction Protection Summary

## What Caused the Eviction?

**Previous pod (`f7v4x`)** was evicted after ~6 hours due to:
- **Karpenter nodepool** had `expireAfter: 6h`
- Node auto-terminated after 6 hours
- Pod lost all progress (job drops collection at start)

---

## Protections Applied ✅

### **1. Extended Node Expiration**
```yaml
disruption:
  expireAfter: 6h → 48h  # Now allows 2-day runs
```
- **Effect:** Nodes won't auto-terminate for 48 hours
- **Applies to:** NEW nodes only
- **Current node:** Created 82 min ago, safe for ~4 more hours

### **2. PodDisruptionBudget**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
spec:
  minAvailable: 1  # At least 1 pod must stay running
```
- **Effect:** Prevents voluntary disruptions (drains, consolidation)
- **Does NOT prevent:** Node expiration, OOM, hardware failures

### **3. Karpenter "Do Not Disrupt" Annotation**
```yaml
annotations:
  karpenter.sh/do-not-disrupt: "true"
```
- **Effect:** Karpenter won't consolidate/disrupt this pod
- **Applied to:**
  - ✅ Current running pod (ffvs6)
  - ✅ Future ingestion job templates

### **4. Safe-to-Evict Annotation**
```yaml
annotations:
  cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
```
- **Effect:** Prevents cluster-autoscaler from evicting
- **Applied to:** All ingestion pods

---

## Current Status

**Node:**
- Name: `ip-10-0-18-182.us-west-2.compute.internal`
- Type: m5.2xlarge (8 vCPU, 32GB RAM)
- Age: 82 minutes
- **Will expire at:** ~2025-11-26 01:11 UTC (18:11 PST) - **~4 hours from now**
- **Protected by:** PDB, do-not-disrupt annotation

**Pod:**
- Age: 81 minutes
- Restarts: 0 (stable)
- Progress: 20/132 files (15%)
- **Protected by:** Annotations, PDB

---

## Risk Assessment

### **Current Node (ip-10-0-18-182):**
- ⚠️ **Still has 6h expiration** (created before nodepool update)
- 🕐 **Will expire in ~4 hours** (around 18:11 PST / 2025-11-26 01:11 UTC)
- ⏱️ **Job needs ~18 hours** to complete (only 15% done)
- 🚨 **WILL BE EVICTED AGAIN** when node expires

### **After This Eviction:**
- ✅ Next node will have 48h expiration
- ✅ Should complete without further evictions

---

## Options

### **Option A: Let Current Pod Run (Will Evict in ~4h)**
- Pod will process ~24 more files before eviction
- Progress lost again
- Next pod starts fresh on new node (48h expiration)
- Total time: Another ~20+ hours

### **Option B: Restart NOW on New Node with 48h Protection**
- Delete current job
- Start fresh on new node (will have 48h expiration)
- No mid-run eviction
- Total time: ~18-20 hours uninterrupted

### **Option C: Switch to PyPDF2**
- Completes in 30 min (too fast for eviction)
- Reliable, proven
- Less sophisticated extraction

---

## Recommendation

**Option B:** Restart the job NOW so it runs on a fresh node with 48h protection.

**Why:**
- Current node will evict in 4 hours anyway (only 15% progress made)
- New node will have 48h expiration → enough time to complete
- All protections (PDB, annotations) will apply to new pod
- Better to restart at 15% than at 50%+

---

## Commands to Restart

```bash
# Delete current job
kubectl delete job -n rag-blueprint tariffs-docling-ingestion

# Wait for node cleanup
sleep 30

# Start fresh (will provision new node with 48h expiration)
kubectl apply -f k8s/tariffs-docling-ingestion-job.yaml

# Verify node has new nodepool settings
kubectl get nodes | grep m5
```

---

## Files Updated

- `k8s/ingestion-nodepool.yaml` - Extended expireAfter to 48h
- `k8s/tariffs-docling-ingestion-job.yaml` - Added do-not-disrupt annotations
- `k8s/congress-docling-ingestion-job.yaml` - Added annotations  
- `k8s/sustainability-docling-ingestion-job.yaml` - Added annotations
- `k8s/ingestion-pdb.yaml` - Created PodDisruptionBudgets

