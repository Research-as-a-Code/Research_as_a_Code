# Critical Issue: RAG Collection Empty

## 🐛 Problem Summary

The backend is NOW correctly configured and passing all parameters to the agent, but the RAG service returns **zero results** because the `us_tariffs` collection is empty.

## ✅ What WAS Fixed

1. **Parameter Passing**: ✅ WORKING
   - Topic, collection, report_organization all correctly passed from frontend → backend → agent nodes
   - Debug logs confirm: `topic=What's the tariff of Reese's Pieces...`, `collection=us_tariffs`

2. **RAG Service URL**: ✅ FIXED
   - Was: `http://rag-server.rag.svc.cluster.local:8081/v1` (wrong)
   - Now: `http://rag-query-server.rag-blueprint.svc.cluster.local:8081/v1` (correct)

3. **RAG Service Health**: ✅ WORKING
   - Service is running and responding
   - `/generate` endpoint works
   - Returns: `"citations":{"total_results":0,"results":[]}`

## ❌ The Actual Problem

### Root Cause
The `us_tariffs` Milvus collection **has no documents** because:
1. The RAG ingest server is scaled to **0 replicas** (has been for 3 days)
2. The tariff PDFs in `data/tariffs/` were **never ingested**
3. The ingest server requires GPU to run (all GPUs currently in use by NIMs)

### Evidence
```bash
# RAG Query Test
$ curl POST /v1/generate -d '{"collection_names":["us_tariffs"],"messages":[...]}'
Response: {"citations":{"total_results":0,"results":[]}}  # <-- EMPTY!

# Ingest Server Status
$ kubectl get deployment -n rag-blueprint rag-ingest-server
NAME                READY   UP-TO-DATE   AVAILABLE   AGE
rag-ingest-server   0/0     0            0           3d8h  # <-- 0 replicas!

# Ingest Server Logs
$ kubectl logs deployment/rag-ingest-server --tail=50
error: timed out waiting for the condition  # <-- No logs, not running
```

## 📊 Current System State

| Component | Status | Issue |
|-----------|--------|-------|
| Frontend → Backend | ✅ Working | Parameters passed correctly |
| Backend → Agent | ✅ Working | Config passed correctly |
| Agent → RAG Service | ✅ Working | URL correct, service responsive |
| RAG Collection | ❌ **EMPTY** | No documents ingested |
| Ingest Server | ❌ Scaled to 0 | Needs GPU to run |

## 🔧 Solutions

### Option A: Ingest Tariff Documents (Recommended)
**Requirements**: 1 GPU available for ingest server

```bash
# 1. Scale up ingest server (requires free GPU)
kubectl scale deployment/rag-ingest-server --replicas=1 -n rag-blueprint

# 2. Wait for pod to be ready
kubectl wait --for=condition=available deployment/rag-ingest-server -n rag-blueprint --timeout=5m

# 3. Run ingest script
cd /home/csaba/repos/AIML/Research_as_a_Code
python3 scripts/ingest_tariffs_to_rag.py

# 4. Verify collection has documents
# (Test RAG query again, should return results)
```

**Pros**: Full RAG functionality, meets hackathon requirements  
**Cons**: Requires freeing up a GPU or scaling to larger instance

### Option B: Temporarily Disable RAG (Quick Fix)
**No GPU required**

Update agent to use web search only:
```python
# backend/main.py - line 207
initial_state = {
    ...
    "collection": "",  # Empty = skip RAG, use web only
    "search_web": True,
    ...
}
```

**Pros**: Works immediately, no infrastructure changes  
**Cons**: Doesn't meet hackathon RAG requirement, answers won't be tariff-specific

### Option C: Scale to Larger GPU Instances
Add more GPU capacity:
```bash
# Allow g5.12xlarge (4 GPUs per node)
# Edit karpenter-provisioner.yaml to include:
- g5.12xlarge

# This gives 4 GPUs per node instead of 1
```

**Pros**: More GPUs = can run NIMs + ingest server  
**Cons**: Higher cost

## 🎯 Recommended Action

**Scale one Nemotron NIM to 0 replicas temporarily**, freeing 1 GPU for document ingestion:

```bash
# Free up a GPU
kubectl scale deployment/llama-instruct-nim --replicas=0 -n nim

# Start ingest server
kubectl scale deployment/rag-ingest-server --replicas=1 -n rag-blueprint

# Ingest documents
cd /home/csaba/repos/AIML/Research_as_a_Code
python3 scripts/ingest_tariffs_to_rag.py \
  --rag-url http://rag-ingest-server.rag-blueprint.svc.cluster.local:8082 \
  --collection-name us_tariffs \
  --data-dir data/tariffs

# Scale NIM back up
kubectl scale deployment/llama-instruct-nim --replicas=1 -n nim
kubectl scale deployment/rag-ingest-server --replicas=0 -n rag-blueprint
```

## ✅ Success Criteria

After ingestion, the RAG query should return:
```json
{
  "citations": {
    "total_results": 5,  // <-- NOT ZERO!
    "results": [
      {"document_name": "Chapter_18.pdf", "content": "...", "score": 0.95},
      ...
    ]
  }
}
```

Then the agent will generate **specific tariff answers** instead of generic templates.

---

**Date**: November 9, 2025  
**Status**: ⚠️ Identified - Awaiting document ingestion  
**Severity**: High (blocks hackathon requirement)  
**ETA to Fix**: 10-15 minutes (document ingestion time)
