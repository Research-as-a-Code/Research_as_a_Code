# RAG Collection Ingestion Guide

**Updated:** Now using **Docling** (IBM Research) for superior PDF extraction!

---

## Overview

The system uses **client-side chunking** with **IBM Docling** for advanced PDF extraction and **Snowflake Arctic-Embed-L** for text-only embeddings.

### **Key Parameters:**

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Extraction** | Docling | IBM Research's advanced PDF segmentation |
| **Chunk Size** | 1000 chars | Increased from 500 for research papers |
| **Chunk Overlap** | 200 chars | Provides context continuity |
| **Batch Size** | 10 chunks | Per embedding API call |
| **Embedding Model** | arctic-embed-l | Text-only, 1024 dimensions |
| **Vector DB** | Milvus (HNSW) | M=16, efConstruction=200 |

---

## FAQ: Chunking & Extraction

### **1. Who performs chunking?**
**Client-side** (Python ingestion script)
- Simple character-based splitting (1000 chars/chunk)
- 200 character overlap for context preservation
- Works for all document types (PDF, TXT, DOCX)

### **2. How are PDFs extracted?**

**Now using Docling (IBM Research):**
```python
from docling.document_converter import DocumentConverter
converter = DocumentConverter()
result = converter.convert(pdf_path)
text = result.document.export_to_markdown()
```

**Advantages over PyPDF2:**
- ✅ Better layout understanding
- ✅ Improved table extraction
- ✅ Smart heading detection
- ✅ Enhanced structure preservation
- ✅ Exports to Markdown (preserves hierarchy)

### **3. Are figures/images handled?**
**❌ No** - Text-only embeddings
- Embedding model: `snowflake/arctic-embed-l` (text-only)
- Figures, charts, diagrams are **not captured**
- Only text content is indexed

**To add multimodal support**, would need:
- Different embedding model (CLIP, multimodal NIM)
- Different extraction pipeline
- Updated vector DB schema
- More complex ingestion

### **4. How are existing chunks handled?**
**⚠️ Full re-ingestion** (no incremental detection)
- Script **drops existing collection** if it exists
- Starts fresh every time
- All files are reprocessed

For incremental updates, would need:
- Query existing collection for processed files
- Skip already-ingested documents
- Or implement upsert logic

### **5. File type support:**

| Type | Extraction | Notes |
|------|-----------|-------|
| **PDF** | Docling | Advanced segmentation |
| **DOCX** | Docling | Full support |
| **TXT** | Plain read | Simple fallback |
| **Other** | ❌ | Not supported |

---

## Available Collections

| Collection | Content | Files | Size | Extraction |
|------------|---------|-------|------|------------|
| **us_tariffs** | US Customs tariff chapters | 138 PDFs | 131MB | Docling |
| **congress** | Congressional documents | 4,747 .txt | ~data size | Plain text |
| **sustainability** | Sustainability research | 79 PDFs + 1 DOCX | 324MB | Docling |

---

## Quick Start: Ingest All Collections

### **One Command:**
```bash
cd scripts
./run_docling_ingestion.sh
```

**This will:**
1. ✅ **Re-ingest us_tariffs** with Docling extraction
2. ✅ **Ingest congress** collection (4,747 .txt files)
3. ✅ **Ingest sustainability** collection (79 PDFs + 1 DOCX)

**Features:**
- 🚀 Runs as Kubernetes Jobs (cluster-local, fast!)
- 📊 Real-time progress logs
- 💪 Batched embeddings (10x speedup)
- 💾 Bulk Milvus inserts (50 files at a time)
- 🔄 Auto-cleanup after 24 hours

**Time estimate:** 
- Tariffs: ~10-15 minutes
- Congress: ~60-90 minutes (large volume)
- Sustainability: ~5-10 minutes

**Total: ~75-115 minutes** (vs 10 days with old method!)

---

## How It Works

### **Architecture:**

```
┌─────────────────────────────────────────────────┐
│ 1. Kubernetes Job Pod (in EKS cluster)         │
│    • Pulls Python 3.11 image                   │
│    • Installs: pymilvus, httpx, docling        │
│    • Mounts data directory (hostPath)          │
│    • Mounts script (ConfigMap)                 │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 2. Docling Extraction                          │
│    • Reads PDF/DOCX with advanced layout AI    │
│    • Exports to Markdown (preserves structure) │
│    • Handles tables, headings, formatting      │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 3. Client-Side Chunking                        │
│    • Splits text: 1000 chars, 200 overlap      │
│    • Filters small chunks (<50 chars)          │
│    • Maintains file source metadata            │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 4. Batched Embeddings                          │
│    • Sends 10 chunks per API call              │
│    • embedding-service.nim (cluster-local)     │
│    • Model: snowflake/arctic-embed-l           │
│    • Returns: 1024-dim vectors                 │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ 5. Bulk Milvus Insert                          │
│    • Accumulates embeddings + texts            │
│    • Inserts every 50 files                    │
│    • Creates HNSW index                        │
│    • Loads collection for search               │
└─────────────────────────────────────────────────┘
```

---

## Manual Ingestion

### **Option A: Run Individual Jobs**

```bash
# 1. Tariffs
kubectl apply -f k8s/tariffs-docling-ingestion-job.yaml
kubectl logs -n rag-blueprint -f job/tariffs-docling-ingestion

# 2. Congress
kubectl apply -f k8s/congress-docling-ingestion-job.yaml
kubectl logs -n rag-blueprint -f job/congress-docling-ingestion

# 3. Sustainability
kubectl apply -f k8s/sustainability-docling-ingestion-job.yaml
kubectl logs -n rag-blueprint -f job/sustainability-docling-ingestion
```

### **Option B: Local Ingestion (slower)**

```bash
# Activate venv
source venv/bin/activate

# Install dependencies (if needed)
pip install pymilvus httpx docling

# Port-forward services
kubectl port-forward -n rag-blueprint svc/milvus-standalone 19530:19530 &
kubectl port-forward -n nim svc/embedding-service 8000:8000 &

# Run ingestion
python scripts/ingest_with_docling.py us_tariffs data/tariffs --pattern "*.pdf" --drop
python scripts/ingest_with_docling.py congress data/congress --pattern "*.txt" --drop
python scripts/ingest_with_docling.py sustainability data/sustainability --pattern "*.*" --drop

# Cleanup
pkill -f "port-forward"
```

---

## Verification

### **Check Collection Status:**

```bash
kubectl exec -n rag-blueprint deployment/milvus-standalone-standalone -- python3 -c "
from pymilvus import connections, Collection
connections.connect(host='milvus-standalone', port=19530)

for name in ['us_tariffs', 'congress', 'sustainability']:
    try:
        coll = Collection(name)
        print(f'{name}: {coll.num_entities:,} chunks')
    except:
        print(f'{name}: Not found')
"
```

**Expected output:**
```
us_tariffs: ~2,000-3,000 chunks
congress: ~8,000-12,000 chunks
sustainability: ~1,500-2,500 chunks
```

### **Test Query:**

```bash
# Port-forward Milvus
kubectl port-forward -n rag-blueprint svc/milvus-standalone 19530:19530 &

# Query via Python
python3 << 'EOF'
from pymilvus import connections, Collection
import numpy as np

connections.connect(host='localhost', port=19530)
coll = Collection('sustainability')
coll.load()

# Random vector for test
test_vec = np.random.rand(1024).tolist()
results = coll.search(
    data=[test_vec],
    anns_field="embedding",
    param={"metric_type": "L2", "params": {"ef": 50}},
    limit=3
)

for hit in results[0]:
    print(f"Source: {hit.entity.source}")
    print(f"Text: {hit.entity.text[:100]}...")
    print()
EOF
```

---

## Using the Collections

### **In the UI:**

1. Enter research topic
2. Set **RAG Collection Name** to:
   - `us_tariffs` - for tariff/trade topics
   - `congress` - for legislative research
   - `sustainability` - for SDG/sustainability topics

### **Example Queries:**

**Tariffs (with Docling enhancement):**
```
Topic: "What factors determine sweet tariff codes?"
Collection: us_tariffs
Strategy: SIMPLE_RAG or UDR
```

**Congress:**
```
Topic: "What legislation has been passed regarding voting rights?"
Collection: congress
Strategy: SIMPLE_RAG
```

**Sustainability:**
```
Topic: "What are the UN Sustainable Development Goals for 2023?"
Collection: sustainability
Strategy: UDR (for deep analysis)
```

---

## Troubleshooting

### **Job Failed:**

```bash
# Check job status
kubectl get jobs -n rag-blueprint

# View logs
kubectl logs -n rag-blueprint job/[job-name]

# Describe for events
kubectl describe job -n rag-blueprint [job-name]

# Delete and retry
kubectl delete job -n rag-blueprint [job-name]
kubectl apply -f k8s/[job-name]-ingestion-job.yaml
```

### **OOM (Out of Memory):**

Edit job YAML to increase resources:
```yaml
resources:
  requests:
    memory: "8Gi"  # Increase from 4Gi
    cpu: "4"       # Increase from 2
  limits:
    memory: "16Gi"
    cpu: "8"
```

### **Slow Ingestion:**

- ✅ **Use Kubernetes Jobs** (cluster-local, no network latency)
- ✅ **Batching enabled** (10 chunks per embedding call)
- ✅ **Bulk inserts** (every 50 files)
- ❌ **Don't use local ingestion** (slow due to network hops)

### **Docling Installation Issues:**

```bash
# If Docling fails to install in job
# Check Python version (needs 3.11+)
# Check available disk space
# Try pulling image manually:
docker pull python:3.11-slim
```

---

## Comparison: Docling vs PyPDF2

| Feature | PyPDF2 (Old) | Docling (New) |
|---------|-------------|---------------|
| **Layout understanding** | ❌ Basic | ✅ Advanced AI |
| **Table extraction** | ⚠️ Poor | ✅ Excellent |
| **Heading detection** | ❌ None | ✅ Smart |
| **Structure preservation** | ❌ None | ✅ Markdown export |
| **Complex PDFs** | ⚠️ Struggles | ✅ Handles well |
| **Speed** | ✅ Fast | ⚠️ Slower (but better) |
| **Dependencies** | Minimal | Large (~2.6GB) |

**Trade-off:** Docling is slower but produces **significantly better** text extraction quality.

---

## Files Created

```
scripts/
├── ingest_with_docling.py           # New: Docling-powered ingestion
├── run_docling_ingestion.sh         # Master script for all collections
├── ingest_congress_to_rag.py        # Legacy (deprecated)
├── ingest_sustainability_to_rag.py  # Legacy (deprecated)
└── setup_all_rag_collections.sh     # Legacy (deprecated)

k8s/
├── tariffs-docling-ingestion-job.yaml        # Job + ConfigMap
├── congress-docling-ingestion-job.yaml       # Job manifest
└── sustainability-docling-ingestion-job.yaml # Job manifest
```

---

## Next Steps

1. ✅ **Run ingestion:** `./scripts/run_docling_ingestion.sh`
2. ⏳ **Wait for completion** (~75-115 minutes)
3. ✅ **Verify collections** (see Verification section)
4. 🧪 **Test queries** in the UI
5. 📊 **Compare quality** with old extraction

---

## Future Enhancements

### **Short-term:**
- ✅ Better extraction (Docling) - **DONE!**
- 🔲 Incremental ingestion (detect existing chunks)
- 🔲 UI collection dropdown (pre-populated)
- 🔲 Collection statistics dashboard

### **Medium-term:**
- 🔲 Multi-collection search (query across collections)
- 🔲 Semantic chunking (sentence-aware)
- 🔲 Chunk size optimization per document type

### **Long-term:**
- 🔲 Multimodal support (figure extraction)
- 🔲 Table-specific indexing
- 🔲 Automated re-ingestion on data updates

---

## Performance Metrics

### **Expected Throughput:**

| Collection | Files | Avg Chunks/File | Total Chunks | Time |
|------------|-------|-----------------|--------------|------|
| Tariffs | 138 PDFs | ~15-25 | ~2,500 | 10-15 min |
| Congress | 4,747 .txt | ~2-4 | ~10,000 | 60-90 min |
| Sustainability | 80 files | ~20-30 | ~2,000 | 5-10 min |

**Bottlenecks:**
1. Docling extraction (CPU-bound)
2. Embedding API calls (I/O-bound, mitigated by batching)
3. Milvus inserts (I/O-bound, mitigated by bulk inserts)

**Optimization:**
- ✅ Batched embeddings (10x speedup)
- ✅ Bulk inserts (50-file batches)
- ✅ Cluster-local communication (no network latency)
- ✅ Parallel processing potential (run 3 jobs at once)

---

## Acknowledgments

- **Docling:** IBM Research's open-source document processing library
- **Milvus:** High-performance vector database
- **Snowflake Arctic-Embed-L:** Efficient text embedding model
- **NVIDIA RAG Blueprint:** Architecture foundation
