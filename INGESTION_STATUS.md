# Ingestion Status - Tariffs Collection

**Last Updated:** 2025-11-26 00:41 PST

---

## Current Status: ✅ RUNNING WITH FULL PROTECTION

### **Progress:**
- **Collection:** us_tariffs
- **Files:** 132 PDFs (6 0-byte files removed)
- **Current:** Processing file 2/132 (just started)
- **Status:** Healthy, no restarts

### **Infrastructure:**
- **Node:** ip-10-0-24-20 (m5.2xlarge)
- **Provisioned:** 2025-11-26 00:37 PST
- **Expires:** 2025-11-28 00:37 PST (48 hours)
- **Memory:** 8Gi request / 16Gi limit

### **Protections Applied:**
- ✅ **48h node expiration** (was 6h)
- ✅ **PodDisruptionBudget** (prevents voluntary eviction)
- ✅ **karpenter.sh/do-not-disrupt: true**
- ✅ **safe-to-evict: false**

---

## Timeline

**Start:** 2025-11-26 00:40 PST  
**ETA:** 2025-11-26 20:00 PST (~20 hours)  
**Node expires:** 2025-11-28 00:37 PST (plenty of time)

---

## What Was Fixed

### **Problem #1: Git LFS Pointers**
- **Issue:** `kubectl cp` copied 131-byte LFS pointer files, not actual PDFs
- **Fix:** Pulled actual LFS files locally, re-uploaded to cluster PVC
- **Result:** Real PDFs (800KB-1.3MB each) now in cluster

### **Problem #2: Missing OpenGL Library**
- **Issue:** Docling needs `libGL.so.1` for PDF rendering
- **Fix:** Rebuilt Docker image with `libgl1` and `libglib2.0-0`
- **Result:** Image v2 pushed to ECR with all dependencies

### **Problem #3: 6-Hour Node Expiration**
- **Issue:** Nodes expired after 6h, evicting long-running jobs
- **Fix:** Extended nodepool `expireAfter: 6h → 48h`
- **Result:** Jobs can run up to 48 hours

### **Problem #4: Voluntary Evictions**
- **Issue:** Karpenter could consolidate/disrupt nodes
- **Fix:** 
  - PodDisruptionBudget (minAvailable: 1)
  - Pod annotations (do-not-disrupt, safe-to-evict: false)
- **Result:** Pods protected from voluntary disruption

### **Problem #5: 0-Byte Files**
- **Issue:** General_Note_19-24.pdf were 0 bytes
- **Fix:** Deleted from cluster PVC
- **Result:** Now processing 132 files instead of 138

---

## Monitoring

### **Check Status:**
```bash
kubectl get job -n rag-blueprint tariffs-docling-ingestion
kubectl get pod -n rag-blueprint -l job=tariffs-docling-ingestion
```

### **View Progress:**
```bash
kubectl logs -n rag-blueprint -l job=tariffs-docling-ingestion | grep "📄" | tail -10
```

### **Check Collection:**
```bash
kubectl exec -n rag-blueprint deployment/milvus-standalone-standalone -- sh -c '
python3 << "EOF"
from pymilvus import connections, Collection
connections.connect(host="localhost", port=19530)
coll = Collection("us_tariffs")
print(f"Chunks indexed: {coll.num_entities:,}")
EOF'
```

---

## Next Steps

### **After Tariffs Completes:**

1. **Congress Collection** (4,747 .txt files)
```bash
kubectl apply -f k8s/congress-docling-ingestion-job.yaml
```
- Already has all protections
- Estimated time: 24-30 hours
- Files are plain text (faster than PDFs)

2. **Sustainability Collection** (79 PDFs + 1 DOCX)
```bash
kubectl apply -f k8s/sustainability-docling-ingestion-job.yaml
```
- Already has all protections
- Estimated time: 5-10 hours
- PDFs already hydrated (not LFS pointers)

---

## Cleanup After Completion

### **Delete Temporary Resources:**
```bash
# Delete nodepool (will terminate nodes)
kubectl delete nodepool ingestion-temp

# Delete PVC (optional, can keep for future ingestions)
kubectl delete pvc ingestion-data -n rag-blueprint

# Delete PDBs
kubectl delete pdb -n rag-blueprint ingestion-jobs-pdb congress-ingestion-pdb sustainability-ingestion-pdb
```

### **Keep for Future:**
- Docker image: `962716963657.dkr.ecr.us-west-2.amazonaws.com/docling-ingestion:v2`
- Job templates: `k8s/*-docling-ingestion-job.yaml`
- Nodepool template: `k8s/ingestion-nodepool.yaml`

---

## Lessons Learned

1. **Git LFS + kubectl cp:** Copies pointers, not files - must pull LFS first
2. **Docling dependencies:** Needs `libgl1` and `libglib2.0-0` system libraries
3. **Docling speed:** ~10-15 min per PDF (slow but high quality)
4. **Node expiration:** Default 6h too short for batch jobs - use 48h+
5. **Eviction protection:** Needs multiple layers (PDB + annotations + expiration)
6. **Memory:** 16Gi sufficient with pre-built image, no OOM issues

---

## Files Created

- `docker/ingestion-docling.Dockerfile` - Pre-built image definition
- `k8s/ingestion-nodepool.yaml` - Temporary CPU nodepool (48h expiration)
- `k8s/ingestion-data-pvc.yaml` - Persistent storage for source files
- `k8s/ingestion-pdb.yaml` - PodDisruptionBudgets
- `k8s/*-docling-ingestion-job.yaml` - Protected job definitions
- `EVICTION_PROTECTION_SUMMARY.md` - Detailed protection guide
- `INGESTION_STATUS.md` - This file

---

**Status:** ✅ Running smoothly, fully protected, ETA ~20 hours

