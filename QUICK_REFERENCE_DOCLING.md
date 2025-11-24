# Docling Ingestion - Quick Reference Card

## 🚀 One-Command Ingestion

```bash
cd /home/csaba/repos/AIML/Research_as_a_Code
./scripts/run_docling_ingestion.sh
```

**Time:** ~75-115 minutes | **Collections:** 3 (tariffs, congress, sustainability)

---

## 📊 Your Questions - Quick Answers

### **1. Chunk Parameters?**
```
Chunk Size:    1000 characters (↑ from 500)
Overlap:       200 characters (↑ from 100)
Batch Size:    10 chunks per API call
Milvus Insert: Every 50 files
```

### **2. Multimodal Support?**
```
❌ NO - Text-only embeddings
Model: snowflake/arctic-embed-l (1024-dim, text-only)
Figures/Charts: Lost during extraction
Tables: ✅ Extracted as text (Docling does well!)
```

### **3. Who Chunks?**
```
Client-side (Python script)
Method: Simple character-based splitting
NOT semantic/sentence-aware
```

### **4. PDF Extraction?**
```
Docling (IBM Research)
- Advanced layout AI
- Better table extraction
- Markdown export (preserves structure)
- Multi-column support
```

### **5. Handle Existing Data?**
```
❌ Full re-ingestion
Drops existing collection
No incremental detection
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `scripts/ingest_with_docling.py` | Core ingestion script |
| `scripts/run_docling_ingestion.sh` | Master orchestrator |
| `k8s/tariffs-docling-ingestion-job.yaml` | Tariffs job + ConfigMap |
| `k8s/congress-docling-ingestion-job.yaml` | Congress job |
| `k8s/sustainability-docling-ingestion-job.yaml` | Sustainability job |

---

## ✅ Verify Collections

```bash
kubectl exec -n rag-blueprint deployment/milvus-standalone-standalone -- python3 -c "
from pymilvus import connections, Collection
connections.connect(host='milvus-standalone', port=19530)
for name in ['us_tariffs', 'congress', 'sustainability']:
    print(f'{name}: {Collection(name).num_entities:,} chunks')
"
```

**Expected:**
```
us_tariffs: ~2,500 chunks
congress: ~10,000 chunks
sustainability: ~2,000 chunks
```

---

## 🔧 Troubleshooting

### **Job Failed?**
```bash
kubectl get jobs -n rag-blueprint
kubectl logs -n rag-blueprint job/[job-name]
kubectl delete job -n rag-blueprint [job-name]
kubectl apply -f k8s/[job-name]-ingestion-job.yaml
```

### **Check Progress:**
```bash
kubectl logs -n rag-blueprint -f job/tariffs-docling-ingestion
kubectl logs -n rag-blueprint -f job/congress-docling-ingestion
kubectl logs -n rag-blueprint -f job/sustainability-docling-ingestion
```

---

## 🎯 Usage in UI

```
Topic: "What are chocolate tariff codes?"
Collection: us_tariffs
Strategy: SIMPLE_RAG or UDR

Topic: "Voting rights legislation history"
Collection: congress
Strategy: SIMPLE_RAG

Topic: "UN Sustainable Development Goals"
Collection: sustainability
Strategy: UDR
```

---

## 📊 Performance

| Collection | Files | Time | Quality |
|------------|-------|------|---------|
| Tariffs | 138 PDFs | 10-15 min | ⭐⭐⭐⭐⭐ |
| Congress | 4,747 .txt | 60-90 min | ⭐⭐⭐⭐ |
| Sustainability | 80 files | 5-10 min | ⭐⭐⭐⭐⭐ |

**Bottleneck:** Congress (large volume of files)

---

## 🆚 Docling vs PyPDF2

| Feature | PyPDF2 | Docling |
|---------|--------|---------|
| Tables | ⚠️ Poor | ✅ Excellent |
| Structure | ❌ None | ✅ Markdown |
| Complex PDFs | ⚠️ Struggles | ✅ Handles |
| Speed | ✅ Fast | ⚠️ Slower |
| Quality | ⚠️ Basic | ✅ Advanced |

**Trade-off:** Slower but significantly better quality

---

## ⚠️ Limitations

- ❌ **Text-only:** Figures/images lost
- ❌ **No incremental:** Full re-ingestion
- ⚠️ **Resource intensive:** 4-8GB RAM needed
- ⚠️ **Large deps:** ~2.6GB to install

---

## 📚 Full Docs

- **Detailed Guide:** `INGESTION_GUIDE.md`
- **Summary:** `DOCLING_INGESTION_SUMMARY.md`
- **This Card:** `QUICK_REFERENCE_DOCLING.md`

---

**Ready?** Run: `./scripts/run_docling_ingestion.sh` 🚀

