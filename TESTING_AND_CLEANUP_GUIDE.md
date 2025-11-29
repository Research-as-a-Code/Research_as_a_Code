# Testing & Cleanup Guide

## ✅ All Collections Ready

```
us_tariffs:      29,081 chunks (LangChain semantic)
congress:       414,485 chunks (LangChain)
sustainability:  29,584 chunks (LangChain semantic)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total:          473,150 chunks
```

---

## 🧪 Test Queries (In Your UI)

### **1. Tariffs Collection**

**Query:**
```
What are the tariff codes for chocolate products containing nuts?
```

**Settings:**
- Collection: `us_tariffs`
- Strategy: SIMPLE_RAG
- Search web: No

**What to check:**
- ✅ Specific tariff codes (1806.XX format)
- ✅ Table data appears in citations
- ✅ Structure preserved (headers, sections)
- ✅ Relevant chapters cited (17, 18)

---

### **2. Congress Collection**

**Query:**
```
What voting rights legislation was passed in the 106th Congress?
```

**Settings:**
- Collection: `congress`
- Strategy: SIMPLE_RAG
- Search web: No

**What to check:**
- ✅ Specific bill numbers (H.R. XXXX, H.J.Res. XXX)
- ✅ Bill descriptions accurate
- ✅ Full text content available
- ✅ Citations show source files

---

### **3. Sustainability Collection**

**Query:**
```
What are the UN Sustainable Development Goals for clean energy?
```

**Settings:**
- Collection: `sustainability`
- Strategy: UDR (for comprehensive analysis)
- Search web: No

**What to check:**
- ✅ SDG 7 (Affordable and Clean Energy) mentioned
- ✅ Specific goals and targets
- ✅ Context from multiple documents
- ✅ Quality citations

---

## Quality Indicators

### **Good Results:**
- ✅ Specific, relevant information
- ✅ Proper citations with source files
- ✅ Coherent, well-structured answers
- ✅ No "not found" or empty responses

### **Issues to Watch For:**
- ❌ Generic answers (not using RAG)
- ❌ Missing citations
- ❌ Fragmented/incomplete information
- ❌ Wrong collection responses

---

## 💰 Cleanup After Testing

### **Step 1: Delete Completed Jobs**

```bash
kubectl delete job -n rag-blueprint tariffs-langchain-semantic
kubectl delete job -n rag-blueprint congress-langchain
kubectl delete job -n rag-blueprint sustainability-langchain
kubectl delete job -n rag-blueprint tariffs-semantic-ingestion

# Verify deletion
kubectl get jobs -n rag-blueprint
```

**Result:** Frees up job history, no impact on data

---

### **Step 2: Delete Ingestion Nodepool**

```bash
# Check current nodes
kubectl get nodes -o custom-columns=NAME:.metadata.name,INSTANCE:.metadata.labels.node\\.kubernetes\\.io/instance-type,POOL:.metadata.labels.karpenter\\.sh/nodepool

# Delete the ingestion nodepool
kubectl delete nodepool ingestion-temp

# Verify nodes terminating
kubectl get nodes
```

**Result:**
- Terminates m5.2xlarge ingestion node(s)
- Saves: ~$0.384/hour per node (~$9/day)
- Karpenter will clean up automatically

---

### **Step 3: Optional Cleanup**

```bash
# Delete PodDisruptionBudgets (no longer needed)
kubectl delete pdb -n rag-blueprint ingestion-jobs-pdb congress-ingestion-pdb sustainability-ingestion-pdb

# Delete data uploader pod (if exists)
kubectl delete pod -n rag-blueprint data-uploader 2>/dev/null

# List what remains (should keep these)
kubectl get pvc -n rag-blueprint | grep ingestion  # Keep for future
kubectl get configmap -n rag-blueprint | grep semantic  # Keep for future
```

---

## 📦 What to Keep (For Future Re-ingestion)

**✅ Keep These:**

```bash
# PVC with source data
ingestion-data (2Gi) - Contains:
  /data/tariffs/
  /data/congress/
  /data/sustainability/

# ConfigMap with scripts
langchain-semantic-scripts

# Docker image in ECR
962716963657.dkr.ecr.us-west-2.amazonaws.com/docling-ingestion:v4

# Job YAML files (in k8s/ directory)
k8s/tariffs-langchain-semantic-job.yaml
k8s/congress-langchain-job.yaml
k8s/sustainability-langchain-job.yaml

# Scripts (in scripts/ directory)
scripts/ingest_langchain_semantic.py
scripts/ingest_congress_langchain.py
scripts/replay_failed_chunks.py
scripts/test_text_cleaning.py
scripts/develop_semantic_chunking.py
```

**Cost:** ~$0.07/month for PVC storage (2Gi)

---

## 🔄 Future Re-ingestion

If you ever need to re-ingest:

```bash
# Recreate ingestion nodepool
kubectl apply -f k8s/ingestion-nodepool.yaml

# Run ingestion
kubectl apply -f k8s/tariffs-langchain-semantic-job.yaml

# All scripts and images are ready!
```

---

## Current Cost

**Before cleanup:**
- Ingestion node: ~$0.384/hour
- Regular cluster: ~$X/hour (existing)

**After cleanup:**
- Ingestion node: $0 (deleted)
- Regular cluster: ~$X/hour (unchanged)
- **Savings: ~$9/day**

---

## Summary

**Test queries in UI →** Verify quality  
**If good →** Run cleanup commands  
**Collections stay →** 473K chunks operational  
**Infrastructure cleaned →** Save ~$9/day  

Ready when you are!

