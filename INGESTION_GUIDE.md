# RAG Collection Ingestion Guide

## Available Collections

The system now supports three RAG collections:

| Collection | Content | Files | Size | Status |
|------------|---------|-------|------|--------|
| **congress** | Congressional documents | 4,747 .txt | ~data size | ⏳ Ready to ingest |
| **sustainability** | Sustainability research PDFs | 79 PDFs | 324MB | ⏳ Ready to ingest |
| **us_tariffs** | US Customs tariff chapters | 138 PDFs | 131MB | ✅ Already ingested |

---

## Quick Start: Ingest All Collections

### **One Command:**
```bash
cd scripts
./setup_all_rag_collections.sh
```

**This will:**
1. Create "congress" collection → Ingest 4,747 text documents
2. Create "sustainability" collection → Ingest 79 PDFs
3. Report progress and summary

**Time estimate:** 1-2 hours (depending on RAG service performance)

---

## Individual Collection Ingestion

### **Congress Documents:**

```bash
cd scripts

# Set RAG service URL (if not using port-forward)
export RAG_INGEST_URL="http://localhost:8082/v1"

# Run ingestion
python3 ingest_congress_to_rag.py
```

**Expected output:**
```
🏛️ Congress Documents → NVIDIA RAG Blueprint Ingestion
📦 Creating collection...
✅ Collection 'congress' created
📚 Found 4747 congress text files to ingest
📄 Processing 1/4747: 106_hjres_102.txt
✅ Ingested: 106_hjres_102.txt
...
```

---

### **Sustainability PDFs:**

```bash
cd scripts

# Set RAG service URL (if not using port-forward)
export RAG_INGEST_URL="http://localhost:8082/v1"

# Run ingestion
python3 ingest_sustainability_to_rag.py
```

**Expected output:**
```
🌱 Sustainability PDFs → NVIDIA RAG Blueprint Ingestion
📦 Creating collection...
✅ Collection 'sustainability' created
📚 Found 79 sustainability PDFs to ingest
📄 Processing 1/79: 30_Visions_of_Sustainability_2017.pdf
✅ Ingested: 30_Visions_of_Sustainability_2017.pdf
...
```

---

## Prerequisites

### **1. RAG Blueprint Deployed:**
```bash
cd infrastructure/helm
./deploy-rag-blueprint.sh
./verify-rag-deployment.sh
```

### **2. Port Forwarding (for local access):**
```bash
kubectl port-forward -n rag-blueprint svc/rag-ingest-service 8082:8082
```

---

## Using the New Collections

### **In the UI:**

1. Enter research topic
2. Set **RAG Collection Name** to:
   - `congress` - for legislative research
   - `sustainability` - for sustainability topics
   - `us_tariffs` - for tariff/trade topics

### **Example Queries:**

**Congress:**
```
Topic: "What legislation has been passed regarding voting rights?"
Collection: congress
```

**Sustainability:**
```
Topic: "What are the UN Sustainable Development Goals for 2023?"
Collection: sustainability
```

**Multi-Collection Research:**
```
Topic: "How do tariff policies impact sustainable development?"
Collections: Use us_tariffs first, then sustainability
```

---

## Troubleshooting

### **Port Forward Issues:**

```bash
# Kill existing port forwards
pkill -f "port-forward.*8082"

# Restart
kubectl port-forward -n rag-blueprint svc/rag-ingest-service 8082:8082
```

### **Check Collection Status:**

```python
import requests
response = requests.get("http://localhost:8082/v1/collections")
print(response.json())  # Should show: ["congress", "sustainability", "us_tariffs"]
```

### **Test Query:**

```bash
curl -X POST 'http://localhost:8082/query' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "sustainable development",
    "collection": "sustainability",
    "top_k": 5
  }'
```

---

## Performance Notes

### **Ingestion Times (Approximate):**

| Collection | Files | Expected Time |
|------------|-------|---------------|
| Congress | 4,747 .txt | 45-60 minutes |
| Sustainability | 79 PDFs | 15-20 minutes |
| **Total** | **4,826** | **60-80 minutes** |

**Factors affecting speed:**
- RAG service performance
- Network latency
- Document size/complexity
- Batch processing rates

---

## Files Created

```
scripts/
├── ingest_congress_to_rag.py        # Congress .txt ingestion
├── ingest_sustainability_to_rag.py  # Sustainability PDF ingestion
├── setup_all_rag_collections.sh     # Master script (runs both)
└── ingest_tariffs_to_rag.py         # Existing tariff ingestion
```

---

## Next Steps

1. **Run the master script** to ingest both collections
2. **Wait for completion** (~1-2 hours)
3. **Test queries** using the new collections
4. **Update UI** to include new collections in dropdown

---

## Future Enhancements

Potential improvements:
- Add collection selection dropdown in UI
- Implement multi-collection search
- Add collection statistics dashboard
- Support incremental updates

