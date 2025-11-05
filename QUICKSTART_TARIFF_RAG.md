## 🚀 Quick Start: US Customs Tariff RAG

**Get your AI-Q agent answering tariff questions in 3 steps!**

> **Note:** This uses the existing NVIDIA RAG Blueprint service (Milvus + NeMo Retriever)

### Step 1: Run the Setup Script (10-20 minutes)

```bash
cd /home/csaba/repos/AIML/Research_as_a_Code
./scripts/setup_tariff_rag_service.sh
```

This ingests all 102 tariff PDFs into the NVIDIA RAG Blueprint service.

### Step 2: Verify the Collection (Optional)

```bash
# Test the RAG service directly
curl -X POST http://localhost:8081/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the tariff for batteries?"}],
    "use_knowledge_base": true,
    "enable_citations": true,
    "collection_name": "us_tariffs"
  }'
```

### Step 3: Use in the Web UI

1. **Open your deployed frontend:**
   ```
   http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com
   ```

2. **Enter a tariff question:**
   - **Research Topic:** `"Tariff of Reese's Pieces?"`
   - **RAG Collection:** `us_tariffs` ← **Important!**
   - Click **Start Research**

3. **Watch the magic:**
   - Agent searches the tariff RAG
   - Returns relevant HTS codes
   - Provides import duty rates

## 📋 Example Queries

Try these in the UI:

1. **"Tariff of replacement batteries for a Raritan remote management card"**
   - Searches Chapter 85 (Electrical machinery)
   - Returns HTS code for batteries

2. **"Tariff of a replacement Roomba vacuum motherboard, used"**
   - Finds HTS code for used electronic parts
   - Explains duty rates for used items

3. **"What's the tariff of Reese's Pieces?"**
   - Searches Chapter 18 (Cocoa) or Chapter 17 (Sugars)
   - Returns candy tariff codes

## 🎯 How It Works

```
Your Question (with collection="us_tariffs")
     ↓
AI-Q Agent → NVIDIA RAG Blueprint Service
     ↓
RAG Service searches Milvus Vector DB
     ↓
NeMo Retriever embeddings find relevant chunks
     ↓
Relevant Tariff Sections Retrieved
     ↓
AI-Q Agent Synthesizes Answer
     ↓
HTS Code + Duty Rate + Citations
```

**Key Advantage:** Uses production-grade Milvus + NeMo Retriever (not ChromaDB)

## 🐛 Troubleshooting

**Q: "Cannot connect to RAG service"**
- A: Ensure the NVIDIA RAG Blueprint services are running
- Docker: `docker ps | grep rag`
- Kubernetes: `kubectl get pods -n rag-blueprint`

**Q: "No results found"**
- A: Make sure you entered `us_tariffs` in the RAG Collection field (exact spelling!)

**Q: "Connection error"**
- A: Check RAG service URLs:
  - Ingest: http://localhost:8082/v1
  - Query: http://localhost:8081/v1

## 📚 Full Documentation

- **Complete Setup Guide:** `TARIFF_RAG_SETUP.md`
- **Original AI-Q Docs:** https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant

---

**That's it! You now have a tariff-aware AI agent! 🎉**

