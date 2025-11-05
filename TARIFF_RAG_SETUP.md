# 🎯 US Customs Tariff RAG - Complete Setup Guide

## Overview

This guide shows you how to enable the AI-Q Research Assistant to answer questions about US import tariffs by ingesting all 99 chapters of the US Harmonized Tariff Schedule into the **NVIDIA RAG Blueprint service**.

**Key Advantage:** This approach leverages the existing RAG infrastructure (Milvus + NeMo Retriever) that's already part of the AI-Q deployment, providing production-grade performance with no additional infrastructure needed.

## Architecture

```
┌──────────────────────────┐
│ AI-Q Research Assistant  │
│ (Your deployed agent)    │
└──────────┬───────────────┘
           │
           │ Query with collection="us_tariffs"
           ▼
┌──────────────────────────┐
│ NVIDIA RAG Blueprint     │ ← Uses existing service
│ (rag-server:8081)        │
│ - Milvus vector DB       │
│ - NeMo Retriever embed   │
│ - Multi-modal parsing    │
└──────────────────────────┘
```

## Prerequisites

✅ **NVIDIA RAG Blueprint must be deployed** alongside AI-Q
- If using Docker Compose: RAG services from `deploy/compose/docker-compose.yaml`
- If using Kubernetes: RAG Helm chart deployed

✅ **RAG services must be accessible:**
- Ingest service: Port 8082
- Query service: Port 8081

## 🚀 Quick Start

### Step 1: Verify RAG Service is Running

**For Docker Compose:**
```bash
# Check if RAG services are running
docker ps | grep rag

# You should see:
#   - rag-server (port 8081)
#   - ingestor-server (port 8082)
#   - milvus
```

**For Kubernetes:**
```bash
# Check RAG pods
kubectl get pods -n rag-blueprint

# Port-forward for local access (if needed)
kubectl port-forward -n rag-blueprint svc/rag-server 8081:8081 &
kubectl port-forward -n rag-blueprint svc/ingestor-server 8082:8082 &
```

### Step 2: Run the Ingestion Script

```bash
cd /home/csaba/repos/AIML/Research_as_a_Code

# Run the automated setup
./scripts/setup_tariff_rag_service.sh
```

**What this does:**
1. ✅ Connects to the RAG ingest service
2. ✅ Creates a `us_tariffs` collection
3. ✅ Uploads all 102 tariff PDF files
4. ✅ RAG service processes them (parse, chunk, embed)
5. ✅ Stores in Milvus with NeMo Retriever embeddings
6. ✅ Runs test queries to verify

**Expected time:** 10-20 minutes (depends on GPU)

### Step 3: Use in the UI

1. **Open AI-Q Research Assistant:**
   ```
   http://<your-frontend-url>
   ```

2. **Enter your query:**
   - **Research Topic:** `"Tariff of replacement batteries for a Raritan remote management card"`
   - **RAG Collection:** `us_tariffs` ← **This is the key!**
   - Click **Start Research**

3. **Watch the magic:**
   - Agent queries the `us_tariffs` collection
   - RAG service searches Milvus vector DB
   - Returns relevant HTS codes with citations

## 📋 Example Queries

### Query 1: Electronic Components
```
Research Topic: Tariff of replacement batteries for a Raritan remote management card
RAG Collection: us_tariffs
```
**Expected:** HTS code from Chapter 85 (Electrical machinery), duty rate for batteries

### Query 2: Used Electronics  
```
Research Topic: Tariff of a replacement Roomba vacuum motherboard, used
RAG Collection: us_tariffs
```
**Expected:** HTS code for used electronic parts, explanation of used vs. new rates

### Query 3: Food Products
```
Research Topic: What's the tariff of Reese's Pieces?
RAG Collection: us_tariffs
```
**Expected:** HTS code from Chapter 17/18 (Sugars/Cocoa), candy tariff rates

## 🔧 Advanced Usage

### Manual Ingestion (with options)

```bash
python3 scripts/ingest_tariffs_to_rag.py \
    --rag-ingest-url "http://localhost:8082/v1" \
    --collection-name "us_tariffs" \
    --tariff-dir "data/tariffs" \
    --test-query
```

### Test Queries After Ingestion

```python
import requests

# Query the RAG service directly
url = "http://localhost:8081/v1/generate"
payload = {
    "messages": [{"role": "user", "content": "What is the tariff for batteries?"}],
    "use_knowledge_base": True,
    "enable_citations": True,
    "collection_name": "us_tariffs"
}

response = requests.post(url, json=payload)
print(response.text)
```

### Re-ingest Updated PDFs

If you need to update the tariff data:

```bash
# Delete the old collection
curl -X DELETE http://localhost:8082/v1/collections/us_tariffs

# Re-run ingestion
./scripts/setup_tariff_rag_service.sh
```

## 🏗️ How It Works

### 1. **PDF Upload** (Your machine → RAG service)
```bash
POST /v1/documents
Content-Type: multipart/form-data

file: Chapter_85.pdf
collection_name: us_tariffs
```

### 2. **RAG Service Processing** (Automatic)
- **Parse PDF:** Extract text, tables, images
- **Chunk:** Split into 1000-char segments
- **Embed:** Generate vectors using NeMo Retriever
- **Store:** Save in Milvus vector database

### 3. **Query Time** (Agent → RAG service)
```bash
POST /v1/generate
{
  "messages": [{"role": "user", "content": "tariff for batteries"}],
  "use_knowledge_base": true,
  "enable_citations": true,
  "collection_name": "us_tariffs"
}
```

### 4. **RAG Service Returns**
```json
{
  "choices": [{"message": {"content": "Based on Chapter 85..."}}],
  "citations": {
    "results": [
      {"document_name": "Chapter_85.pdf", "page": 12}
    ]
  }
}
```

## 📊 What's Included

- **99 Chapters** of US Harmonized Tariff Schedule
- **General Notes** and **General Rules of Interpretation**  
- **Table of Contents**
- **Total:** 102 PDF documents (~500 MB)

### Key Chapters for Common Items

| Chapter | Category | Examples |
|---------|----------|----------|
| 17 | Sugars & confectionery | Candy, chocolate (Reese's) |
| 18 | Cocoa preparations | Chocolate products |
| 84 | Machinery | Industrial equipment |
| 85 | Electrical machinery | **Batteries, chips, electronics** |
| 87 | Vehicles | Cars, auto parts |
| 90 | Optical instruments | Medical devices, cameras |
| 95 | Toys & games | Consumer toys |

## 🐛 Troubleshooting

### Issue: "Cannot connect to RAG service"

**Solution:** Ensure RAG Blueprint is running

**Docker Compose:**
```bash
cd /path/to/rag/blueprint
docker-compose up -d rag-server ingestor-server milvus
```

**Kubernetes:**
```bash
kubectl get pods -n rag-blueprint
# All pods should be Running

# If not accessible locally, port-forward:
kubectl port-forward -n rag-blueprint svc/ingestor-server 8082:8082
```

### Issue: "Collection not found"

**Solution:** Verify collection was created
```bash
curl http://localhost:8082/v1/collections
# Should list "us_tariffs"
```

### Issue: "No results returned"

**Solution 1:** Check you entered the collection name correctly
- In the UI, RAG Collection field: `us_tariffs` (exact spelling)

**Solution 2:** Verify documents were ingested
```bash
curl http://localhost:8082/v1/collections/us_tariffs/documents
# Should show list of ingested PDFs
```

### Issue: Ingestion is slow

**Expected:** 10-20 minutes for 102 PDFs with GPU
- RAG service does heavy processing (OCR, embedding, etc.)
- This is normal for production-grade quality

**To monitor progress:**
```bash
# Watch RAG service logs
docker logs -f ingestor-server  # Docker
kubectl logs -f -n rag-blueprint deployment/ingestor-server  # K8s
```

## 🎓 Why This Approach?

### ✅ Advantages vs. Standalone ChromaDB

1. **Production-Grade:** Milvus is enterprise vector DB (used by Airbnb, Walmart)
2. **Better Embeddings:** NeMo Retriever optimized for NVIDIA GPUs
3. **Multi-Modal:** Handles text, tables, charts in PDFs
4. **Existing Infrastructure:** Reuses deployed RAG service
5. **Proven:** Same system powering AI-Q's document search
6. **Scalable:** Milvus handles millions of vectors efficiently

### 📈 Performance Comparison

| Metric | ChromaDB (Local) | Milvus (RAG Service) |
|--------|------------------|----------------------|
| Query Speed | ~2-3s | **~1s** |
| Embedding Quality | Dummy (local dev) | **NeMo Retriever** |
| Multi-modal | No | **Yes (tables, images)** |
| Production Ready | No | **Yes** |
| GPU Optimized | No | **Yes** |

## 📚 Resources

- **AI-Q Research Assistant:** https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant
- **NVIDIA RAG Blueprint:** https://github.com/NVIDIA-AI-Blueprints/rag
- **Milvus Documentation:** https://milvus.io/docs
- **NeMo Retriever:** https://docs.nvidia.com/nemo-framework/

## 🎉 Next Steps

1. ✅ Run `./scripts/setup_tariff_rag_service.sh`
2. ✅ Wait for ingestion to complete
3. ✅ Open AI-Q UI and try the example queries
4. 🚀 **Build your own tariff-aware applications!**

---

**Happy Researching! 🎓**

Questions? The RAG service handles all the vector database complexity - you just query with `collection_name: "us_tariffs"` and it works!

