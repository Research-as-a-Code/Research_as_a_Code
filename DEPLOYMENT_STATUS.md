# Current Deployment Status

## ✅ Infrastructure Configuration (All Changes Saved)

### Region
- **Location**: `us-west-2` (moved from `us-east-1` due to GPU quota)
- **File**: `infrastructure/terraform/variables.tf`

### Karpenter GPU Nodes
- **Instance Types**: `g5.xlarge`, `g5.2xlarge`, `g5.4xlarge`, `g5.8xlarge`, `g5.12xlarge`
- **Currently Provisioned**: 3x `g5.2xlarge` (32GB RAM, 24GB GPU each)
- **File**: `infrastructure/terraform/karpenter-provisioner.yaml`

### Models Deployed
1. **LLM/Reasoning**: Nemotron-Nano-8B (Hackathon requirement)
   - Image: `nvcr.io/nim/nvidia/llama-3.1-nemotron-nano-8b-v1:latest`
   - Engine: TensorRT-LLM (optimized)
   - Status: ✅ Running on g5.2xlarge
   - File: `infrastructure/kubernetes/deploy-nims.sh`

2. **Embedding**: Snowflake Arctic Embed
   - Image: `nvcr.io/nim/snowflake/arctic-embed-l:1.0.1`
   - Status: ✅ Running
   - File: `infrastructure/kubernetes/deploy-nims.sh`

### Backend Configuration
- **Model Names**: `nvidia/llama-3.1-nemotron-nano-8b-v1`
- **NIM Endpoint**: `instruct-llm-service.nim.svc.cluster.local:8000`
- **File**: `backend/main.py` (lines 67-69)

### Frontend Configuration
- **Example Queries**: US Customs Tariff queries
  - Replacement batteries for Raritan remote management card
  - Replacement Roomba vacuum motherboard (used)
  - Reese's Pieces tariff
- **File**: `frontend/app/components/ResearchForm.tsx`

## 📦 RAG Blueprint (Enterprise)
- **Vector DB**: Milvus Standalone (simplified)
- **Collection**: `us_tariff_codes`
- **Documents**: 97 PDF files from `data/tariffs`
- **Status**: ✅ Deployed and operational

## 🚀 Current System State

### Running Pods
```
nim namespace:
  - embedding-nim: Running (1/1)
  - llama-instruct-nim: Running (1/1) - Nemotron-Nano-8B with TensorRT

default namespace:
  - (backend needs redeployment)
```

### Next Step
Redeploy the agent backend to connect to the new Nemotron NIM:
```bash
sudo /etc/init.d/docker start
bash infrastructure/kubernetes/deploy-agent.sh
```

## 🎯 Hackathon Compliance
- ✅ NVIDIA NIM on AWS EKS
- ✅ Nemotron-Nano-8B model
- ✅ GPU acceleration (A10G)
- ✅ US Customs Tariff use case
- ✅ RAG with Milvus + NeMo Retriever

## 💰 Cost Optimization Notes
- **Current**: 3x g5.2xlarge (~$3.00/hr)
- **Recommendation**: Scale down to 1-2 nodes after testing
- **Commands**:
  ```bash
  kubectl scale deployment -n nim --replicas=1 --all
  kubectl scale deployment -n rag-blueprint --replicas=0 --all
  ```
