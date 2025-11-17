# Embedding Model Clarification

## Summary

**All components are using the same Arctic Embed L model as planned.** The issue we fixed today was a **model name mismatch** in the ingestion script, not a different model being used.

## Current Setup ✅

### Embedding NIM Deployed
- **Image**: `nvcr.io/nim/snowflake/arctic-embed-l:1.0.1`
- **Service**: `embedding-service.nim.svc.cluster.local:8000`
- **Model Name**: `snowflake/arctic-embed-l`
- **Dimension**: 1024
- **This IS the planned "text-embedding-nim" from the original architecture**

### Components Using This Model

1. **Ingestion Script** (`scripts/ingest_tariffs.py`)
   - ✅ Fixed to use: `snowflake/arctic-embed-l`
   - Previously had: `nvidia/nv-embedqa-e5-v5` (WRONG - caused 404 errors)

2. **Main Agent RAG Tool** (`aira/src/aiq_aira/tools.py`)
   - ✅ Uses: `snowflake/arctic-embed-l`

3. **UDF RAG Tool** (`aira/src/aiq_aira/udf_integration.py`)
   - ✅ Uses: `snowflake/arctic-embed-l`

4. **Milvus Collection** (`us_tariffs`)
   - Vector dimension: 1024 (matches Arctic Embed L)
   - Entries: 198 (Chapters 17 & 18)

## What Was the Problem?

### The Bug
The ingestion script (`scripts/ingest_tariffs.py`) was configured with:
```python
"model": "nvidia/nv-embedqa-e5-v5"  # ❌ WRONG - This model doesn't exist on the NIM
```

### The Fix
Changed to the correct model name:
```python
"model": "snowflake/arctic-embed-l"  # ✅ CORRECT - Matches the NIM's registered model
```

### Why the Confusion?
- **Different naming conventions**: NVIDIA has various embedding models with similar names
- `nvidia/nv-embedqa-e5-v5` might have been:
  - A placeholder from documentation
  - A different NVIDIA embedding model
  - Or a typo/outdated reference

- The actual model deployed is **Snowflake Arctic Embed L**, which is:
  - Part of NVIDIA NIM catalog
  - 1024-dimensional embeddings
  - Optimized for retrieval tasks

## Original Milvus (Scaled Down)

**Unknown - Cannot verify without scaling it up**, but likely scenarios:

### Scenario A: Same Model (Most Likely)
If the original ingestion worked, it must have used the correct model name (`snowflake/arctic-embed-l`), meaning:
- Original data is compatible with current setup
- Can potentially scale up original Milvus and use existing data

### Scenario B: Different Script
If a different ingestion method was used (e.g., RAG Blueprint's ingest service), it would have:
- Used whatever embedding model the RAG service was configured with
- Potentially different dimensions or model

## Verification Commands

### Check Current NIM
```bash
kubectl get deployment embedding-nim -n nim -o jsonpath='{.spec.template.spec.containers[0].image}'
# Output: nvcr.io/nim/snowflake/arctic-embed-l:1.0.1
```

### Check Model Name
```bash
EMBED_POD=$(kubectl get pods -n nim -l app=embedding-nim -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n nim $EMBED_POD -- curl -s http://localhost:8000/v1/models
# Output: {"id": "snowflake/arctic-embed-l", ...}
```

### Test Embedding
```bash
kubectl exec -n nim $EMBED_POD -- curl -s -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": ["test"], "model": "snowflake/arctic-embed-l"}'
# Should return 1024-dimensional vector
```

## Conclusion

✅ **Everything is using the correct Arctic Embed L model now**
- NIM: `snowflake/arctic-embed-l` (1024-dim)
- Ingestion: Fixed to use correct model name
- Agent RAG: Using correct model
- UDF RAG: Using correct model
- Milvus: 1024-dim vectors

The original plan's "text-embedding-nim" IS the Arctic Embed L NIM we're using. There's no mismatch - just a bug in the ingestion script that has been fixed.

## Files Fixed

1. ✅ `scripts/ingest_tariffs.py` - Updated model name
2. ✅ `aira/src/aiq_aira/udf_integration.py` - Already correct
3. ✅ `aira/src/aiq_aira/tools.py` - Already correct

---

**Status**: All embedding operations now use `snowflake/arctic-embed-l` consistently across the entire stack.

