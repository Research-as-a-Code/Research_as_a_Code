# Semantic Chunking Implementation Guide

## Overview

Upgrading from **simple character-based chunking** (1000 chars, 200 overlap) to **semantic chunking** using LlamaIndex for better retrieval quality.

---

## Why Semantic Chunking?

### **Simple Chunking (Current):**
```
"The tariff code for chocolate is 1806.32. This applies to products
containing cocoa. The rate is 5.6%. <SPLIT> Special provisions apply
for organic chocolate under code 1806.32.10..."
```
- ❌ Splits mid-concept
- ❌ May break tables
- ❌ Loses semantic coherence

### **Semantic Chunking (New):**
```
Chunk 1: "The tariff code for chocolate is 1806.32. This applies to
         products containing cocoa. The rate is 5.6%."
         
Chunk 2: "Special provisions apply for organic chocolate under code
         1806.32.10. These require certification..."
```
- ✅ Keeps related concepts together
- ✅ Tables extracted and handled specially
- ✅ Better retrieval quality

---

## Implementation

### **Pipeline:**

```
1. Docling Extraction
   ↓ (Markdown with structure preserved)
2. LlamaIndex MarkdownElementNodeParser
   ↓ (Extract tables)
3. LlamaIndex SemanticSplitterNodeParser  
   ↓ (Semantic text chunking)
4. NVIDIA NIM Embeddings
   ↓ (1024-dim vectors)
5. Milvus Indexing
   ✅ (HNSW index)
```

---

## Key Features

### **1. Semantic Splitting**
```python
SemanticSplitterNodeParser(
    buffer_size=1,  # Group sentences
    breakpoint_percentile_threshold=95,  # Split when similarity drops
    embed_model=nvidia_nim_wrapper
)
```
- Uses embeddings to detect topic changes
- Splits at semantic boundaries
- Preserves conceptual coherence

### **2. Table Extraction**
```python
MarkdownElementNodeParser(llm=None, num_workers=1)
```
- Identifies tables in markdown
- Extracts them whole (no mid-table splits)
- Creates dedicated table nodes

### **3. Failure Persistence** (NEW!)

When chunks fail after all retries:
```python
persist_failed_chunks(chunks, filename, error, collection)
```

Saves to: `/data/ingestion_failures/{collection}/{timestamp}_{filename}.json`

**Format:**
```json
{
  "timestamp": "2025-11-27T10:30:00",
  "collection": "us_tariffs",
  "source_file": "Chapter_17.pdf",
  "error": "HTTP 400 after 3 retries",
  "chunk_count": 3,
  "chunks": [
    {
      "text": "First 500 chars...",
      "full_text": "Complete chunk text",
      "type": "text",
      "metadata": {...},
      "error": "HTTP 400",
      "batch_index": 42
    }
  ]
}
```

### **4. Replay Mechanism**

```bash
python scripts/replay_failed_chunks.py us_tariffs
```

**What it does:**
1. Scans `/data/ingestion_failures/us_tariffs/`
2. Loads all failure logs
3. Retries each failed chunk individually
4. Inserts successful chunks to Milvus
5. Archives processed logs to `processed/` subdirectory
6. Reports recovery statistics

---

## Recovery Strategy (4-Tier)

### **Tier 1: Batch with Retry**
```
Send 10 chunks as batch
→ Fail → Wait 1s, retry
→ Fail → Wait 2s, retry  
→ Fail → Wait 4s, retry
```

### **Tier 2: Individual Chunk Processing**
```
Split batch into 10 individual chunks
→ Try each separately
→ Success: Index to Milvus
→ Fail: Move to Tier 3
```

### **Tier 3: Persist to Disk**
```
Save failed chunk to JSON:
  /data/ingestion_failures/{collection}/{timestamp}_{file}.json
→ Continue with other chunks
→ Job completes successfully
```

### **Tier 4: Manual Replay** (Later)
```
python replay_failed_chunks.py {collection}
→ Load persisted failures
→ Retry with fresh API state
→ Report recovery rate
```

---

## Comparison: Simple vs Semantic

| Aspect | Simple (Current) | Semantic (New) |
|--------|------------------|----------------|
| **Method** | Character-based (1000 chars) | Embedding similarity-based |
| **Boundaries** | Arbitrary | Semantic topic changes |
| **Tables** | May split mid-table | Extracted whole |
| **Coherence** | ⚠️ Can break concepts | ✅ Keeps ideas together |
| **Retrieval** | Good | ⭐ Excellent |
| **Speed** | Fast (~2-5s per file) | Slower (~10-15s per file) |
| **Quality** | Adequate | Superior |

---

## Current Collections (Simple Chunking)

| Collection | Chunks | Files | Status |
|------------|--------|-------|--------|
| **us_tariffs** | 24,452 | 132 PDFs | ✅ Complete |
| **congress** | 1,710,693 | 4,747 txt | ✅ Complete |
| **sustainability** | 19,626 | 80 files | ✅ Complete |

**Total:** 1,754,771 chunks with simple chunking

---

## Re-ingestion Plan with Semantic Chunking

### **Option A: Fresh Start (Recommended)**
```bash
# Drop existing collections and reingest with semantic chunking
DROP_EXISTING=true
```
- ✅ Clean slate
- ✅ Consistent chunking strategy
- ✅ Best quality
- ⏱️ Time: 6-8 hours total

### **Option B: Incremental Addition**
```bash
# Keep existing, add semantic versions as new collections
# us_tariffs_semantic, congress_semantic, sustainability_semantic
```
- ✅ Keep current collections working
- ✅ Compare quality side-by-side
- ✅ Can A/B test
- ⏱️ Time: 6-8 hours (parallel to existing)

### **Option C: Test First**
```bash
# Reingest just sustainability with semantic (smallest collection)
# Compare quality in UI
# Then decide on tariffs/congress
```
- ✅ Low risk
- ✅ Quick validation
- ⏱️ Time: 1-2 hours for test

---

## Files Created

**Scripts:**
- `scripts/ingest_with_semantic_chunking.py` - Main semantic ingestion
- `scripts/replay_failed_chunks.py` - Failure replay tool

**Docker:**
- `docker/ingestion-docling.Dockerfile` - Updated with LlamaIndex

**Docs:**
- `SEMANTIC_CHUNKING_GUIDE.md` - This file

---

## Failure Persistence Details

### **Storage Location:**
```
/data/ingestion_failures/
├── us_tariffs/
│   ├── 20251127_103045_Chapter_17.pdf.json
│   ├── 20251127_114523_Chapter_85.pdf.json
│   └── processed/  (archived after replay)
├── congress/
│   └── ...
└── sustainability/
    └── ...
```

### **PVC Mount:**
The ingestion jobs already mount `/data` PVC, so failures persist across:
- Pod restarts
- Job restarts
- Node replacements

### **Replay Usage:**
```bash
# From local machine
kubectl run replay-tool --rm -i --restart=Never \
  --image=962716963657.dkr.ecr.us-west-2.amazonaws.com/docling-ingestion:v3 \
  -n rag-blueprint \
  --overrides='...(mount /data PVC)...' \
  -- python /scripts/replay_failed_chunks.py us_tariffs

# Or from within cluster as a Job
kubectl apply -f k8s/replay-failures-job.yaml
```

---

## Next Steps

1. **Build new Docker image with LlamaIndex:**
   ```bash
   docker build -f docker/ingestion-docling.Dockerfile -t docling-ingestion:v3-semantic .
   docker push {ECR}/docling-ingestion:v3-semantic
   ```

2. **Test on sustainability first:**
   ```bash
   # Small collection, quick to test
   kubectl apply -f k8s/sustainability-semantic-job.yaml
   ```

3. **Compare quality in UI**

4. **Decide on full re-ingestion**

---

## Benefits of This Approach

✅ **Retry Logic:** 3 attempts with exponential backoff  
✅ **Batch-Splitting:** Try individually if batch fails  
✅ **Failure Persistence:** Save failures to disk  
✅ **Replay Tool:** Recover failed chunks later  
✅ **Incremental:** Survives restarts  
✅ **Size-Aware:** Prevents gRPC crashes  
✅ **Semantic Quality:** Better retrieval  
✅ **Table Handling:** Tables stay intact  

**Result:** Bulletproof ingestion with superior chunk quality! 🎯

---

## Questions to Consider

1. **Re-ingest all 3 collections or test semantic on sustainability first?**
2. **Drop existing collections or create parallel `_semantic` versions?**
3. **Build Docker image now or test locally first?**

What would you like to do?

