# NVIDIA RAG Blueprint - Enterprise Deployment Guide

## Overview

This guide covers the **enterprise-grade** deployment of the NVIDIA RAG Blueprint to your AWS EKS cluster for the US Customs Tariff RAG use case.

**Architecture Components:**
- **Milvus Vector Database** - Cloud-native, scalable vector storage
- **NVIDIA NeMo Retriever** - Embedding generation and retrieval
- **RAG Query Server** - Handles search and retrieval requests
- **RAG Ingest Server** - PDF processing and document ingestion
- **Hybrid Search** - Combines vector similarity + keyword (BM25) search

## Why Enterprise RAG Blueprint?

✅ **Production-Ready**: Battle-tested, enterprise-grade architecture  
✅ **Scalable**: Milvus handles billions of vectors  
✅ **Future-Proof**: Industry standard, actively maintained  
✅ **Hybrid Search**: Vector + keyword for complex tariff queries  
✅ **Advanced Document Processing**: GPU-accelerated PDF parsing, OCR, table extraction  
✅ **Observability**: Built-in monitoring and logging  

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS EKS Cluster                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────┐      ┌────────────────┐                 │
│  │  AI-Q Agent    │─────▶│  RAG Query     │                 │
│  │   (Backend)    │      │    Server      │                 │
│  │                │      │   (Port 8081)  │                 │
│  └────────────────┘      └────────┬───────┘                 │
│                                   │                          │
│                          ┌────────▼────────┐                 │
│  ┌────────────────┐      │     Milvus      │                 │
│  │  Tariff PDF    │      │  Vector Store   │                 │
│  │   Ingestion    │──┐   │  (Port 19530)   │                 │
│  │                │  │   └────────▲────────┘                 │
│  └────────────────┘  │            │                          │
│                      │   ┌────────┴────────┐                 │
│                      └──▶│  RAG Ingest     │                 │
│                          │    Server       │                 │
│                          │  (Port 8082)    │                 │
│                          └────────┬────────┘                 │
│                                   │                          │
│                          ┌────────▼────────┐                 │
│                          │  Embedding NIM  │                 │
│                          │  (NeMo Retr.)   │                 │
│                          │  (Port 8000)    │                 │
│                          └─────────────────┘                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

Before deploying the RAG Blueprint:

1. **EKS Cluster** - Already provisioned via Terraform
   ```bash
   kubectl cluster-info
   ```

2. **NGC API Key** - For pulling NVIDIA containers
   - Get it from: https://org.ngc.nvidia.com/setup/api-key
   ```bash
   export NGC_API_KEY="your-ngc-api-key"
   ```

3. **Helm** - For deploying the RAG Blueprint
   ```bash
   helm version
   # If not installed: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
   ```

4. **kubectl** - Configured for your EKS cluster
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name aiq-udf-eks
   ```

5. **Storage Class** - For Milvus persistence (gp3 recommended)
   ```bash
   kubectl get storageclass
   ```

## Deployment Steps

### Step 1: Deploy the NVIDIA RAG Blueprint

Navigate to the Helm directory:
```bash
cd infrastructure/helm
```

Make the deployment script executable:
```bash
chmod +x deploy-rag-blueprint.sh
chmod +x verify-rag-deployment.sh
```

Deploy the RAG Blueprint:
```bash
export NGC_API_KEY="your-ngc-api-key"
./deploy-rag-blueprint.sh
```

**What this does:**
1. Creates `rag-blueprint` namespace
2. Creates NGC secret for image pulling
3. Adds NVIDIA Helm repository
4. Deploys Milvus vector database (standalone mode)
5. Deploys RAG query server (port 8081)
6. Deploys RAG ingest server (port 8082)
7. Configures connection to existing embedding NIM

**Expected duration:** 10-15 minutes

### Step 2: Verify Deployment

Run the verification script:
```bash
./verify-rag-deployment.sh
```

Expected output:
```
✅ Namespace 'rag-blueprint' exists
✅ Milvus - 1/1 pods running
✅ RAG Query Server - 2/2 pods running
✅ RAG Ingest Server - 1/1 pods running
✅ Ingest Server Health - Endpoint responding
✅ Query Server Health - Endpoint responding
```

If services are still starting, wait a few minutes and re-run.

### Step 3: Ingest Tariff PDFs

Navigate to the scripts directory:
```bash
cd ../../scripts
chmod +x setup_tariff_rag_enterprise.sh
```

Run the ingestion script:
```bash
./setup_tariff_rag_enterprise.sh
```

**What this does:**
1. Sets up port-forward to RAG ingest service (if running locally)
2. Creates `us_tariffs` collection in Milvus
3. Uploads and processes all 99 tariff PDF chapters
4. Runs test queries to verify functionality

**Expected duration:** 20-30 minutes (depending on PDF size)

### Step 4: Update AI-Q Agent Configuration

Update your agent backend to use the RAG service:

Edit `infrastructure/kubernetes/agent-deployment.yaml`:

```yaml
env:
- name: RAG_SERVER_URL
  value: "http://rag-query-server.rag-blueprint.svc.cluster.local:8081/v1"
- name: RAG_COLLECTION
  value: "us_tariffs"
```

Apply the changes:
```bash
cd ../infrastructure/kubernetes
kubectl apply -f agent-deployment.yaml
kubectl rollout restart deployment/aiq-agent-backend -n aiq-agent
```

## Using the RAG Collection

### From AI-Q Agent Backend

```python
import requests

RAG_SERVER_URL = "http://rag-query-server.rag-blueprint.svc.cluster.local:8081/v1"
COLLECTION_NAME = "us_tariffs"

def query_tariff_rag(user_query: str) -> dict:
    """Query the tariff RAG collection"""
    response = requests.post(
        f"{RAG_SERVER_URL}/generate",
        json={
            "messages": [{"role": "user", "content": user_query}],
            "use_knowledge_base": True,
            "enable_citations": True,
            "collection_name": COLLECTION_NAME
        },
        timeout=60
    )
    
    return response.json()
```

### Example Queries

1. **Replacement Batteries**
   ```
   "What is the tariff for replacement batteries for a Raritan remote management card?"
   ```

2. **Food Items**
   ```
   "What's the tariff of Reese's Pieces?"
   ```

3. **Used Electronics**
   ```
   "Tariff of a replacement Roomba vacuum motherboard, used"
   ```

4. **Specific HTS Codes**
   ```
   "What items are covered under HTS code 8507.60?"
   ```

## Configuration Files

### `nvidia-rag-values.yaml`

Helm values file for customizing the RAG Blueprint deployment:

**Key configurations:**
- `milvus.standalone.persistence.size: 100Gi` - Vector storage size
- `embeddings.externalService.host` - Points to your embedding NIM
- `queryServer.replicas: 2` - Query server scaling
- `ingestServer.resources.limits.nvidia.com/gpu: 1` - GPU for PDF processing

### `rag-services.yaml`

Kubernetes manifests for deploying RAG services individually (if Helm chart unavailable):
- RAG Query Server Deployment & Service
- RAG Ingest Server Deployment & Service
- Environment variables for Milvus and embedding connections

## Monitoring & Operations

### View Pod Status
```bash
kubectl get pods -n rag-blueprint
kubectl get pods -n rag-blueprint -w  # Watch mode
```

### View Service Endpoints
```bash
kubectl get svc -n rag-blueprint
```

### Check Logs
```bash
# RAG Query Server
kubectl logs -n rag-blueprint -l app=rag-query-server -f

# RAG Ingest Server
kubectl logs -n rag-blueprint -l app=rag-ingest-server -f

# Milvus
kubectl logs -n rag-blueprint -l app.kubernetes.io/name=milvus -f
```

### Port-Forward for Local Access
```bash
# Ingest Server (for running ingestion locally)
kubectl port-forward -n rag-blueprint svc/rag-ingest-server 8082:8082

# Query Server (for testing queries locally)
kubectl port-forward -n rag-blueprint svc/rag-query-server 8081:8081
```

### Health Checks
```bash
# Ingest server
curl http://localhost:8082/health

# Query server
curl http://localhost:8081/health
```

### Manual Query Test
```bash
curl -X POST http://localhost:8081/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the tariff for computers?"}],
    "use_knowledge_base": true,
    "enable_citations": true,
    "collection_name": "us_tariffs"
  }'
```

## Scaling & Performance

### Scale Query Server (for high traffic)
```bash
kubectl scale deployment rag-query-server -n rag-blueprint --replicas=5
```

### Scale Milvus (for more data)

Edit `nvidia-rag-values.yaml`:
```yaml
milvus:
  standalone:
    persistence:
      size: 500Gi  # Increase storage
    resources:
      limits:
        cpu: "8"
        memory: "16Gi"
```

Re-apply:
```bash
helm upgrade nvidia-rag nvidia/rag-blueprint \
  --namespace rag-blueprint \
  --values nvidia-rag-values.yaml
```

### Monitor Resource Usage
```bash
kubectl top pods -n rag-blueprint
kubectl describe node | grep -A 5 "Allocated resources"
```

## Troubleshooting

### Pods Not Starting

**Check events:**
```bash
kubectl get events -n rag-blueprint --sort-by='.lastTimestamp'
```

**Common issues:**
- **ImagePullBackOff**: NGC secret not configured correctly
  ```bash
  kubectl get secret -n rag-blueprint ngc-secret
  # Recreate if needed
  kubectl delete secret -n rag-blueprint ngc-secret
  # Re-run deploy script
  ```

- **Pending (no GPU)**: Karpenter hasn't provisioned GPU nodes yet
  ```bash
  kubectl get nodes -l karpenter.sh/provisioner-name=nvidia-nim
  # Wait 5-10 minutes for Karpenter to provision
  ```

- **OOMKilled**: Increase memory limits in values file

### Ingestion Failing

**Test connectivity:**
```bash
kubectl port-forward -n rag-blueprint svc/rag-ingest-server 8082:8082
curl http://localhost:8082/health
```

**Check logs:**
```bash
kubectl logs -n rag-blueprint -l app=rag-ingest-server -f
```

**Common issues:**
- **Connection refused**: Service not ready yet, wait a few minutes
- **Embedding service unreachable**: Check embedding NIM is running
  ```bash
  kubectl get pods -n nim -l app=embedding-nim
  ```
- **Out of disk space**: Increase `persistence.size` in values file

### Queries Returning No Results

**Verify collection exists:**
```bash
# Connect to Milvus
kubectl port-forward -n rag-blueprint svc/milvus-standalone 19530:19530

# Use Milvus CLI or Python SDK to list collections
```

**Check document count:**
```bash
kubectl logs -n rag-blueprint -l app=rag-ingest-server | grep "ingested"
```

**Re-ingest if needed:**
```bash
cd scripts
./setup_tariff_rag_enterprise.sh
```

## Hybrid Search Explained

The NVIDIA RAG Blueprint uses **hybrid search** combining:

1. **Vector Search (Semantic)**
   - Finds conceptually similar documents
   - Example: "replacement batteries" → matches "rechargeable cells", "power supplies"

2. **Keyword Search (BM25)**
   - Exact term matching
   - Example: "HTS 8507.60" → matches exact tariff codes

3. **Hybrid Ranking**
   - Combines both scores with learned weights
   - Optimal for tariff queries (codes + descriptions)

## Cost Considerations

**AWS Resources:**
- **EBS Volumes**: 
  - Milvus: 100Gi gp3 (~$8/month)
  - Etcd: 10Gi gp3 (~$0.80/month)
  - Documents: 50Gi gp3 (~$4/month)

- **GPU Nodes** (for ingest server):
  - g5.xlarge: ~$1.00/hour (on-demand)
  - Karpenter auto-scales, so only pay when ingesting

- **CPU Nodes** (for query server):
  - c6i.2xlarge: ~$0.34/hour
  - 2 replicas for HA

**Optimization Tips:**
- Use Spot instances for Karpenter provisioner (50-70% savings)
- Scale query server replicas down during low-traffic periods
- Use Fargate for non-GPU workloads

## Security Best Practices

1. **Network Policies**: Restrict traffic to RAG services
   ```bash
   # Apply network policy (create this file)
   kubectl apply -f infrastructure/helm/rag-network-policy.yaml
   ```

2. **RBAC**: Limit service account permissions
   - Already configured in `nvidia-rag-values.yaml`

3. **Secrets Management**: Use AWS Secrets Manager for NGC API key
   ```bash
   # Store in Secrets Manager
   aws secretsmanager create-secret \
     --name ngc-api-key \
     --secret-string "$NGC_API_KEY"
   
   # Use External Secrets Operator to sync to Kubernetes
   ```

4. **Encrypt PVCs**: Enable EBS encryption
   ```yaml
   # In values file
   milvus:
     standalone:
       persistence:
         storageClass: gp3-encrypted
   ```

## Cleanup

To remove the RAG Blueprint:

```bash
cd infrastructure/helm

# Delete the Helm release (if using Helm chart)
helm uninstall nvidia-rag -n rag-blueprint

# Or delete manifests (if deployed manually)
kubectl delete -f rag-services.yaml -n rag-blueprint
helm uninstall milvus -n rag-blueprint

# Delete namespace (this removes all resources)
kubectl delete namespace rag-blueprint
```

**Note**: Persistent volumes may need manual cleanup:
```bash
kubectl get pvc -n rag-blueprint
kubectl delete pvc --all -n rag-blueprint
```

## Next Steps

✅ **RAG Blueprint Deployed**: Milvus + RAG servers running  
✅ **Tariff PDFs Ingested**: 99 chapters in `us_tariffs` collection  
✅ **Agent Configured**: Backend points to RAG service  

**Now you can:**
1. Test complex tariff queries in the UI
2. Integrate RAG into your UDF dynamic strategies
3. Add more document collections (e.g., customs regulations, trade agreements)
4. Monitor and scale based on usage patterns

## Support & Resources

- **NVIDIA NIM Documentation**: https://docs.nvidia.com/nim/
- **Milvus Documentation**: https://milvus.io/docs
- **NeMo Retriever**: https://docs.nvidia.com/nemo/retriever/
- **This Project's README**: `/README.md`

---

**Congratulations!** You now have an enterprise-grade RAG system powered by NVIDIA blueprints running on AWS EKS. 🎉

