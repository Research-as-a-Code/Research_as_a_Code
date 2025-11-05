# Quick Start: Enterprise RAG with US Customs Tariffs

**Goal**: Get the NVIDIA RAG Blueprint deployed and tariff PDFs ingested in ~30 minutes.

## Prerequisites (5 minutes)

1. **EKS Cluster Running**
   ```bash
   kubectl cluster-info
   ```
   If not, deploy it first:
   ```bash
   cd infrastructure/terraform
   ./install.sh
   ```

2. **NGC API Key**
   - Get from: https://org.ngc.nvidia.com/setup/api-key
   ```bash
   export NGC_API_KEY="nvapi-..."
   ```

3. **kubectl Configured**
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name aiq-udf-eks
   ```

## Step 1: Deploy RAG Blueprint (15 minutes)

```bash
cd infrastructure/helm
./deploy-rag-blueprint.sh
```

**What's deploying:**
- ✅ Milvus vector database
- ✅ RAG ingest server (PDF processing)
- ✅ RAG query server (search & retrieval)

**Wait for it to finish**, then verify:

```bash
./verify-rag-deployment.sh
```

Expected output:
```
✅ Milvus - 1/1 pods running
✅ RAG Query Server - 2/2 pods running
✅ RAG Ingest Server - 1/1 pods running
```

## Step 2: Ingest Tariff PDFs (20 minutes)

```bash
cd ../../scripts
./setup_tariff_rag_enterprise.sh
```

**What's happening:**
1. Port-forwards to RAG ingest service
2. Creates `us_tariffs` collection
3. Uploads 99 tariff PDF chapters
4. Runs test queries

Expected output:
```
✅ Success: 99
📦 Total:   99
```

## Step 3: Test in UI (2 minutes)

1. **Get frontend URL:**
   ```bash
   kubectl get svc -n aiq-agent aiq-agent-frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
   ```

2. **Open in browser**

3. **Enter these test queries:**
   - "What is the tariff for replacement batteries for a Raritan remote management card?"
   - "What's the tariff of Reese's Pieces?"
   - "Tariff of a replacement Roomba vacuum motherboard, used"

4. **Set collection name:** `us_tariffs`

## Troubleshooting

### Pods not starting?
```bash
kubectl get pods -n rag-blueprint
kubectl describe pod <pod-name> -n rag-blueprint
```

### Ingestion failing?
```bash
# Check port-forward
curl http://localhost:8082/health

# Check logs
kubectl logs -n rag-blueprint -l app=rag-ingest-server -f
```

### No query results?
```bash
# Verify collection was created
kubectl logs -n rag-blueprint -l app=rag-ingest-server | grep "us_tariffs"

# Re-run ingestion
cd scripts
./setup_tariff_rag_enterprise.sh
```

## Architecture At-A-Glance

```
User Query
    ↓
AI-Q Agent Backend
    ↓
RAG Query Server (8081) ← Milvus Vector Store
    ↓                         ↑
Embedding NIM (8000)          |
                              |
                    RAG Ingest Server (8082)
                              ↑
                        Tariff PDFs (99)
```

## What You Get

✅ **Enterprise Vector Store**: Milvus (production-grade)  
✅ **Hybrid Search**: Vector + keyword (BM25) for tariff codes  
✅ **GPU-Accelerated**: PDF processing with NVIDIA NIMs  
✅ **Scalable**: Auto-scales with Karpenter  
✅ **Citation Support**: Returns source documents with answers  

## Next Steps

- Add more document collections (regulations, trade agreements)
- Integrate RAG into UDF dynamic strategies
- Scale query server for production traffic
- Set up monitoring and alerts

## Full Documentation

For detailed configuration, troubleshooting, and operations:
- **[NVIDIA_RAG_BLUEPRINT_DEPLOYMENT.md](NVIDIA_RAG_BLUEPRINT_DEPLOYMENT.md)** - Complete enterprise deployment guide
- **[README.md](README.md)** - Main project documentation
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Full infrastructure deployment

---

**Deployed in ~30 minutes!** Now you have enterprise-grade RAG powered by NVIDIA blueprints. 🚀

