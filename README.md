# AI-Q Research Assistant with Universal Deep Research (UDR)

## AWS & NVIDIA Agentic AI Unleashed Hackathon 2025

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![NVIDIA AI](https://img.shields.io/badge/NVIDIA-AI-76B900)](https://www.nvidia.com/en-us/ai/)
[![AWS EKS](https://img.shields.io/badge/AWS-EKS-FF9900)](https://aws.amazon.com/eks/)

**A two-level agentic system combining NVIDIA AI-Q Research Assistant with Universal Deep Research (UDR) for complex, multi-domain research tasks.**

---

## 🎯 Project Overview

This project implements a novel architecture that synthesizes two distinct NVIDIA AI blueprints:

1. **NVIDIA AI-Q Research Assistant** (https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant) - Production-ready research agent with RAG capabilities
2. **NVIDIA Universal Deep Research (UDR)** - Strategy-as-code engine for dynamic research workflows

### Core Innovation

The system features a **two-level agentic architecture**:

- **Level 1**: AI-Q orchestrator (built on LangGraph) that decides research strategy
- **Level 2**: UDR engine that *dynamically generates and executes* custom research code when complexity warrants

This allows the agent to move beyond predefined RAG pipelines and adapt its strategy on-the-fly for complex queries like "Generate a report on 'NIMs on EKS' and include a cost-benefit analysis."

---

## 🏗️ Architecture

### Architectural Components

| Component | Technology | Purpose |
|-----------|-----------|----------|
| **User Interface** | React/Next.js + CopilotKit | Real-time agentic flow visualization |
| **Agent Backend** | FastAPI + LangGraph | State management and agent orchestration |
| **Reasoning LLM** | Nemotron-Super-49B NIM | Planning and reflection |
| **Instruct LLM** | Llama-3.3-70B NIM | Report writing |
| **Embedding Model** | NeMo Retriever NIM | Vector search |
| **RAG Pipeline** | NVIDIA RAG Blueprint | Multi-modal document retrieval |
| **Dynamic Strategy** | UDR Integration | Strategy-as-code execution |
| **Infrastructure** | AWS EKS + Karpenter | GPU auto-scaling |

### Agent Flow Visualization

```
User Prompt
    ↓
[Planner Node] ← Nemotron NIM
    ↓
Decision: Complex or Simple?
    ├─→ Simple → [Standard RAG Pipeline]
    └─→ Complex → [UDR Strategy Execution]
        ├─→ Compile Strategy (Natural Language → Python)
        ├─→ Execute (Calls NIMs, RAG, Web Search)
        └─→ Synthesize Results
    ↓
[Final Report Node]
    ↓
User receives report + citations
```

**Key Feature**: Every step streams state updates to the CopilotKit UI for real-time visualization.

---

## 🚀 Quick Start

### Prerequisites

- AWS Account with EKS permissions
- NVIDIA NGC API Key ([Get it here](https://ngc.nvidia.com/))
- Tavily API Key (optional, for web search)
- Tools: `terraform`, `kubectl`, `helm`, `docker`, `aws-cli`

### One-Command Deployment

```bash
# Set environment variables
export TF_VAR_ngc_api_key="YOUR_NGC_API_KEY"
export TAVILY_API_KEY="YOUR_TAVILY_KEY"  # Optional
export AWS_DEFAULT_REGION="us-west-2"

# 1. Deploy infrastructure (EKS + Karpenter + GPU Operator)
cd infrastructure/terraform
./install.sh  # ~20 minutes

# 2. Deploy NVIDIA NIMs
cd ../kubernetes
./deploy-nims.sh  # ~30 minutes

# 3. Deploy AI-Q + UDR Agent
./deploy-agent.sh  # ~10 minutes

# 4. Access the application
# The script will output the LoadBalancer URL
```

### Enterprise RAG with US Customs Tariffs

Deploy the NVIDIA RAG Blueprint with Milvus for production-grade document retrieval:

```bash
# 5. Deploy NVIDIA RAG Blueprint (enterprise vector store)
cd ../helm
./deploy-rag-blueprint.sh  # ~15 minutes

# 6. Ingest US Customs Tariff PDFs (99 chapters)
cd ../../scripts
./setup_tariff_rag_enterprise.sh  # ~20 minutes

# Test queries:
# - "What is the tariff for replacement batteries for a Raritan remote management card?"
# - "What's the tariff of Reese's Pieces?"
# - "Tariff of a replacement Roomba vacuum motherboard, used"
```

**Features:**
- ✅ **Milvus Vector Database** - Enterprise-grade, scalable
- ✅ **Hybrid Search** - Vector + keyword (BM25) for tariff codes
- ✅ **GPU-Accelerated PDF Processing** - NVIDIA NIM microservices
- ✅ **Citation Support** - Returns source documents with answers

📖 **Full Guide:** [NVIDIA_RAG_BLUEPRINT_DEPLOYMENT.md](NVIDIA_RAG_BLUEPRINT_DEPLOYMENT.md)  
🚀 **Quick Start:** [QUICKSTART_RAG_ENTERPRISE.md](QUICKSTART_RAG_ENTERPRISE.md)

---

## 📦 What Gets Deployed

### NVIDIA NIM Microservices

1. **Nemotron Reasoning NIM** (llama-3.3-nemotron-super-49b-v1.5)
   - Purpose: Planning, reflection, strategy compilation
   - GPU: 1x NVIDIA A10G (24GB)
   - Service: `nemotron-nano-service.nim.svc.cluster.local:8000`

2. **Llama 3.3 70B Instruct NIM**
   - Purpose: Report writing and Q&A
   - GPU: 2x NVIDIA A10G (48GB)
   - Service: `instruct-llm-service.nim.svc.cluster.local:8000`

3. **Embedding NIM** (Arctic Embed Large)
   - Purpose: Vector embeddings for RAG
   - GPU: 1x NVIDIA A10G (24GB)
   - Service: `embedding-service.nim.svc.cluster.local:8000`

### NVIDIA RAG Blueprint (Optional - Enterprise)

4. **Milvus Vector Database**
   - Purpose: Scalable vector storage for document collections
   - Storage: 100Gi EBS gp3
   - Service: `milvus-standalone.rag-blueprint.svc.cluster.local:19530`

5. **RAG Query Server**
   - Purpose: Search and retrieval with hybrid search (vector + BM25)
   - Replicas: 2 (for HA)
   - Service: `rag-query-server.rag-blueprint.svc.cluster.local:8081`

6. **RAG Ingest Server**
   - Purpose: GPU-accelerated PDF processing and document ingestion
   - GPU: 1x NVIDIA A10G (for PDF processing)
   - Service: `rag-ingest-server.rag-blueprint.svc.cluster.local:8082`

### Custom Services

7. **AI-Q + UDR Agent Backend**
   - FastAPI service with CopilotKit integration
   - Namespace: `aiq-agent`
   - Replicas: 2 (for HA)

8. **Frontend UI**
   - Next.js application with real-time agent visualization
   - Exposed via AWS LoadBalancer

### Infrastructure

- **EKS Cluster** (Kubernetes 1.28)
- **Karpenter** (GPU node auto-scaling)
- **NVIDIA GPU Operator** (Driver management)
- **VPC** (3 AZs, public + private subnets)

**Total GPU Requirement**: 
- Base deployment: 4x NVIDIA A10G GPUs (Reasoning, Instruct, Embedding)
- With enterprise RAG: 5x NVIDIA A10G GPUs (+ PDF processing)

**Estimated Cost**: 
- Base: ~$15-20/hour when fully running
- With RAG Blueprint: ~$20-25/hour
- **Tip**: Use Spot instances to reduce costs by 50-70%

---

## 💤 Cluster Management (Cost Savings)

Save ~90% on compute costs when not actively developing:

### Daily Workflow (Recommended)

```bash
# End of day
bash infrastructure/scripts/sleep-cluster.sh

# Next morning  
bash infrastructure/scripts/wake-cluster.sh
bash infrastructure/scripts/monitor-cluster-readiness.sh  # Auto-exits when ready
```

**What happens:**
- **Sleep**: Scales down NIMs + Backend (GPU-intensive)
- **Keeps running**: Milvus + Frontend (lightweight, ~$1/day)
- **Wake time**: ~17 minutes (Milvus stays warm)
- **Cost savings**: ~90% reduction

### Alternative: Deep Sleep (Extended Downtime)

For maximum savings when gone for 2+ days:

```bash
# Before leaving
bash scripts/deep-sleep-cluster.sh

# When back
bash scripts/deep-wake-cluster.sh
```

**Trade-offs:**
- ✅ 95% cost savings (stops everything)
- ✅ All-in-one script (built-in monitoring)
- ❌ ~20+ minute wake time (Milvus rehydration)

### Available Scripts

| Script | Purpose | Wake Time | Savings |
|--------|---------|-----------|---------|
| `infrastructure/scripts/sleep-cluster.sh` | **Daily use (recommended)** | ~17 min | 90% |
| `infrastructure/scripts/wake-cluster.sh` | Quick wake | - | - |
| `infrastructure/scripts/monitor-cluster-readiness.sh` | Wait for ready (auto-exits) | - | - |
| `infrastructure/scripts/test-sleep-wake-cycle.sh` | Full lifecycle test | 17 min | - |
| `scripts/deep-sleep-cluster.sh` | **Extended downtime (2+ days)** | ~20+ min | 95% |
| `scripts/deep-wake-cluster.sh` | Wake from deep sleep | - | - |

> 💡 **Tip**: Use `infrastructure/scripts/` for daily workflow (faster, modular). Use `scripts/deep-sleep-cluster.sh` only for extended downtime when you need maximum savings. See `scripts/README.md` for details.

---

## 💻 Local Development

### Backend Development

```bash
cd backend

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export NEMOTRON_NIM_URL="http://localhost:8000"  # Or hosted NIM URL
export INSTRUCT_LLM_URL="http://localhost:8001"
export RAG_SERVER_URL="http://localhost:8081/v1"
export NGC_API_KEY="your_key"

# Run backend
python main.py
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run dev server (auto-detects localhost backend)
npm run dev

# Open http://localhost:3000
```

### Frontend Backend URL Configuration

The frontend supports multiple ways to configure the backend URL, in priority order:

1. **Runtime Config (Recommended for Production)** - No rebuild required!
   
   Edit `frontend/public/config.js`:
   ```javascript
   window.__RUNTIME_CONFIG__ = {
     BACKEND_URL: "http://your-backend-url.example.com"
   };
   ```
   
   For Kubernetes deployments, this file is mounted via ConfigMap. Update `values.yaml`:
   ```yaml
   frontend.runtimeConfig:
     backendUrl: "http://your-backend-elb.amazonaws.com"
   ```
   Then run `helm upgrade` - pods restart automatically.

2. **Build-time Environment Variable**
   ```bash
   # During Docker build
   docker build --build-arg NEXT_PUBLIC_BACKEND_URL="http://backend:8000" ...
   ```

3. **Automatic Detection** - The frontend auto-detects:
   - `localhost` → uses `http://localhost:8000`
   - AWS ELB hostname → uses configured backend ELB

> **Note**: `NEXT_PUBLIC_*` variables are baked into the JavaScript bundle at build time in Next.js. For true runtime configuration without rebuilding, use option 1 (Runtime Config).

### Testing UDR Integration

```python
from aiq_aira.udr_integration import UDFIntegration
from langchain_openai import ChatOpenAI

# Initialize UDR
llm = ChatOpenAI(base_url="http://nemotron-nim:8000/v1")
udr = UDFIntegration(
    compiler_llm=llm,
    rag_url="http://rag-server:8081/v1",
    nemotron_nim_url="http://nemotron-nim:8000",
    embedding_nim_url="http://embedding-nim:8000"
)

# Execute a dynamic strategy
strategy = """
1. Search RAG for 'NIMs on EKS deployment patterns'
2. Search web for 'AWS EKS GPU pricing'
3. Synthesize findings into cost-benefit analysis
"""

result = await udr.execute_dynamic_strategy(strategy, context={})
print(result.synthesized_report)
```

---

## 📚 Project Structure

```
Research_as_a_Code/
├── aira/                          # Copied from NVIDIA AI-Q repo
│   └── src/aiq_aira/              # Core AI-Q agent code
│       ├── hackathon_agent.py     # ⭐ Enhanced agent with UDR
│       └── udr_integration.py     # ⭐ UDR strategy-as-code engine
├── backend/                       # FastAPI backend
│   ├── main.py                    # ⭐ CopilotKit integration
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                      # Next.js UI
│   ├── app/
│   │   ├── layout.tsx             # CopilotKit provider
│   │   ├── page.tsx               # Main page
│   │   └── components/
│   │       ├── AgentFlowDisplay.tsx  # ⭐ Real-time flow visualization
│   │       ├── ResearchForm.tsx
│   │       └── ReportDisplay.tsx
│   ├── package.json
│   └── Dockerfile
├── infrastructure/
│   ├── terraform/                 # IaaC for EKS
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── karpenter-provisioner.yaml
│   │   └── install.sh
│   └── kubernetes/                # K8s manifests
│       ├── agent-deployment.yaml
│       ├── deploy-nims.sh
│       └── deploy-agent.sh
├── configs/                       # AI-Q configuration
│   └── config.yml
├── demo/                          # Demo assets
├── deploy/                        # Original AI-Q deployment files
└── README.md                      # This file

⭐ = New files created for the hackathon
```

---

## 🎓 Key Technical Concepts

### 1. CopilotKit AG-UI Protocol

CopilotKit provides the "glue" between the LangGraph backend and React frontend:

**Backend** (Python):
```python
from copilotkit import CopilotKit

copilot = CopilotKit()
copilot.add_langgraph_endpoint(
    app_id="ai_q_researcher",
    endpoint="/copilotkit",
    graph=agent_graph,
    config_factory=lambda: config
)
app.include_router(copilot.router)
```

**Frontend** (TypeScript):
```typescript
import { useCoAgentStateRender } from "@copilotkit/react-core";

const { state } = useCoAgentStateRender<AgentState>({
  name: "ai_q_researcher",  // Must match backend app_id
  render: ({ state }) => {
    // Render state.logs, state.queries, etc.
  }
});
```

### 2. UDR Strategy-as-Code

The UDR module converts natural language plans into executable Python:

```
Natural Language:
"1. Search RAG for X
 2. Search web for Y
 3. Synthesize Z"

        ↓ (Compiler)

Python Code:
result1 = await search_rag("X", collection)
result2 = await search_web("Y")
report = await synthesize_findings([result1, result2])
return {"report": report, "sources": [...]}

        ↓ (Executor)

Actual NIM calls executed in sandbox
```

### 3. Karpenter GPU Auto-Scaling

When a NIM pod requests a GPU:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

Karpenter:
1. Detects unschedulable pod
2. Provisions g5.xlarge Spot instance (~$0.50/hr)
3. NVIDIA GPU Operator installs drivers
4. Pod scheduled on new node
5. When idle, node terminated to save costs

---

## 🧪 Testing

### Test 1: Simple RAG Query

**Prompt**: "What is Amazon EKS?"

**Expected Flow**:
- Planner selects "Simple RAG"
- Standard AI-Q pipeline executes
- Report generated from RAG + web sources

### Test 2: Complex UDR Query

**Prompt**: "Generate a report on 'NIMs on EKS' and include a cost-benefit analysis comparing on-premise vs hosted deployment"

**Expected Flow**:
- Planner selects "Dynamic UDR Strategy"
- UDR compiles multi-step research plan
- Plan executes (RAG + web + synthesis)
- Comprehensive report with analysis

### Test 3: Real-Time Visualization

1. Submit any query
2. Watch the "Agentic Flow" panel
3. Should see logs streaming in real-time:
   - "🤔 Analyzing research complexity..."
   - "✅ Strategy: DYNAMIC_STRATEGY"
   - "🚀 Executing dynamic UDR strategy..."
   - etc.

---

## 🎯 Hackathon Requirements Met

| Requirement | Implementation | Status |
|-------------|---------------|--------|
| ✅ Use NVIDIA NIM | 3x NIMs deployed (Nemotron, Llama, Embedding) | ✅ |
| ✅ Deploy on EKS | Terraform + Karpenter on AWS EKS | ✅ |
| ✅ Agentic Framework | LangGraph (NVIDIA NeMo Agent Toolkit) | ✅ |
| ✅ Visualize Agent Flow | CopilotKit useCoAgentStateRender | ✅ |
| ✅ Infrastructure as Code | Terraform + Helm + K8s manifests | ✅ |
| ✅ Innovation | Two-level agent with UDR strategy-as-code | ✅ |

---

## 📖 Additional Documentation

- **[Design Plan](cursor/design_plan.md)**: Comprehensive architectural design (735 lines)
- **[AI-Q Blueprint](https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant)**: Original AI-Q documentation
- **[UDR Paper](https://arxiv.org/abs/2509.00244)**: Universal Deep Research research paper
- **[Data on EKS](https://github.com/awslabs/data-on-eks)**: AWS EKS blueprints
- **[CopilotKit Docs](https://docs.copilotkit.ai)**: CopilotKit documentation

---

## 🤝 Credits and References

This project integrates and builds upon:

1. **NVIDIA AI-Q Research Assistant** ([GitHub](https://github.com/NVIDIA-AI-Blueprints/aiq-research-assistant))
   - Apache 2.0 License
   - Production-ready research agent with RAG

2. **NVIDIA Universal Deep Research** ([GitHub](https://github.com/NVlabs/UniversalDeepResearch))
   - Strategy-as-code paradigm
   - Dynamic research planning

3. **AWS Data on EKS** ([GitHub](https://github.com/awslabs/data-on-eks))
   - Apache 2.0 License
   - EKS + Karpenter blueprints

4. **CopilotKit** ([Website](https://www.copilotkit.ai/))
   - MIT License
   - AG-UI protocol for agentic UI

---

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Components used:
- NVIDIA AI-Q: Apache 2.0
- NVIDIA UDR: Apache 2.0
- AWS Blueprints: Apache 2.0
- CopilotKit: MIT

---

## 🛠️ Troubleshooting

### Issue: NIMs not starting

**Solution**: Check GPU availability and NGC API key

```bash
kubectl get pods -n nim
kubectl describe pod <nim-pod> -n nim
kubectl logs -n nim <nim-pod>

# Check if Karpenter provisioned GPU nodes
kubectl get nodes --show-labels | grep nvidia
```

### Issue: Frontend can't reach backend

**Symptoms**: 
- `ERR_CONNECTION_REFUSED` errors
- `Failed to load runtime info (http://localhost:8000/copilotkit/info)`
- `Agent ai_q_researcher not found`

**Solution 1**: Check if backend URL is configured correctly

The frontend may be trying to connect to `localhost:8000` instead of the deployed backend. 

For Kubernetes deployments, update the runtime config:
```bash
# Edit values.yaml
frontend.runtimeConfig:
  backendUrl: "http://your-backend-elb.amazonaws.com"

# Apply changes
helm upgrade <release-name> ./deploy/helm/aiq-aira
```

Or directly edit the ConfigMap:
```bash
kubectl edit configmap <release-name>-frontend-config -n <namespace>
```

**Solution 2**: Check service networking

```bash
kubectl get svc -n aiq-agent
kubectl logs -n aiq-agent -l component=backend
```

### Issue: "Strategy-as-code compilation failed"

**Solution**: Check Nemotron NIM connectivity

```bash
kubectl exec -n aiq-agent deployment/aiq-agent-backend -- \
  curl http://nemotron-nano-service.nim.svc.cluster.local:8000/v1/models
```

---

## 🎉 Demo Video Script

1. **Introduction** (30s)
   - "This is the AI-Q Research Assistant enhanced with Universal Deep Research"
   - Show architecture diagram

2. **Simple Query** (1 min)
   - Enter: "What is Amazon EKS?"
   - Show: Agent flow selecting "Simple RAG"
   - Show: Report generated

3. **Complex Query** (2 min)
   - Enter: "Generate a report on NIMs on EKS with cost-benefit analysis"
   - Show: Agent flow selecting "Dynamic UDR Strategy"
   - Show: Real-time logs (compilation, execution)
   - Show: Comprehensive multi-section report

4. **Infrastructure** (1 min)
   - Show: `kubectl get nodes` (Karpenter-provisioned GPUs)
   - Show: `kubectl get pods -n nim` (3 NIMs running)
   - Show: EKS console

5. **Conclusion** (30s)
   - Recap: Two-level agentic system
   - Highlight: Dynamic strategy adaptation
   - Call to action: Try it yourself!

---

## 📧 Contact

For questions about this hackathon submission:
- GitHub Issues: [Create an issue](https://github.com/yourusername/Research_as_a_Code/issues)
- Hackathon: AWS & NVIDIA Agentic AI Unleashed 2025

**Built with ❤️ using NVIDIA AI and AWS EKS**
