# Collection Name Correction

## ❌ Incorrect Name (in some docs):
`us_tariff_codes`

## ✅ Correct Name:
**`us_tariffs`**

---

## 📝 Confirmed In Code:

### Ingestion Script: `scripts/ingest_tariffs_to_rag.py`
```python
collection_name: str = "us_tariffs",  # Line 25
```

### Setup Script: `scripts/setup_tariff_rag_enterprise.sh`
```bash
COLLECTION_NAME="us_tariffs"  # Line 15
```

### Frontend Placeholder: `frontend/app/components/ResearchForm.tsx`
```typescript
placeholder="Enter 'us_tariffs' for tariff queries, or leave empty for web-only research"
```

---

## 🧪 How to Use:

When using the research form, enter:
```
RAG Collection: us_tariffs
```

---

## 📊 Collection Contents:
- **97 PDF files** from `data/tariffs/` folder
- Indexed with **NVIDIA NeMo Retriever** embeddings
- Stored in **Milvus** vector database

---

**Status**: Confirmed ✅  
**Date**: November 9, 2025
