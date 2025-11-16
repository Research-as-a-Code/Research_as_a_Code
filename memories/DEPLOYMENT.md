# Deployment Guide

## AI-Q + UDF Research Assistant - AWS & NVIDIA Hackathon

This guide provides step-by-step instructions for deploying the complete system.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Setup](#pre-deployment-setup)
3. [Infrastructure Deployment](#infrastructure-deployment)
4. [NVIDIA NIM Deployment](#nvidia-nim-deployment)
5. [Agent Deployment](#agent-deployment)
6. [Verification](#verification)
7. [Cleanup](#cleanup)

---

## Prerequisites

### Required Tools

Install these tools before starting:

```bash
# Terraform (>= 1.5.0)
brew install terraform  # macOS
# or download from https://www.terraform.io/downloads

# kubectl
brew install kubectl

# Helm
brew install helm

# AWS CLI
brew install awscli
aws configure  # Set your credentials

# Docker
# Install from https://www.docker.com/get-started
```

### Required API Keys

1. **NVIDIA NGC API Key**
   - Sign up at https://ngc.nvidia.com/
   - Generate API key: https://ngc.nvidia.com/setup/api-key
   - Keep this key secure!

2. **Tavily API Key** (Optional, for web search)
   - Sign up at https://tavily.com/
   - Free tier available

3. **AWS Account**
   - Must have permissions to create EKS clusters, VPCs, IAM roles
   - Estimated cost: $15-20/hour when running

---

## Pre-Deployment Setup

### 1. Clone the Repository

```bash
cd ~/repos/AIML
cd Research_as_a_Code
```

### 2. Set Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your keys
nano .env
```

Required variables:
```bash
export TF_VAR_ngc_api_key="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export NGC_API_KEY="nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TAVILY_API_KEY="tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Optional
export AWS_DEFAULT_REGION="us-west-2"  # Or your preferred region
```

Load environment:
```bash
source .env
```

### 3. Verify Prerequisites

```bash
# Check all tools are installed
terraform --version  # Should be >= 1.5.0
kubectl version --client
helm version
aws --version
docker --version

# Verify AWS credentials
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDACKCEVSQ6C2EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/YourUser"
}
```

---

## Infrastructure Deployment

### Step 1: Deploy EKS Cluster

This takes approximately **20 minutes**.

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply (create infrastructure)
./install.sh
```

**What this creates:**
- VPC with public/private subnets across 3 AZs
- EKS cluster (Kubernetes 1.28)
- Managed node group for system workloads
- Karpenter for GPU auto-scaling
- NVIDIA GPU Operator
- All necessary IAM roles and security groups

### Step 2: Configure kubectl

```bash
# This command is output by the install script
aws eks update-kubeconfig --region us-west-2 --name ai-q-udf-hackathon

# Verify connection
kubectl get nodes
```

Expected output:
```
NAME                          STATUS   ROLES    AGE   VERSION
ip-10-0-1-123.ec2.internal   Ready    <none>   5m    v1.28.x
ip-10-0-2-456.ec2.internal   Ready    <none>   5m    v1.28.x
```

### Step 3: Verify Karpenter

```bash
kubectl get pods -n karpenter
```

Expected output:
```
NAME                         READY   STATUS    RESTARTS   AGE
karpenter-xxxxx-xxxxx        1/1     Running   0          5m
karpenter-xxxxx-xxxxx        1/1     Running   0          5m
```

### Step 4: Verify GPU Operator

```bash
kubectl get pods -n gpu-operator
```

You should see multiple pods running (driver daemonset, operator, etc.).

---

## NVIDIA NIM Deployment

This takes approximately **30 minutes** (NIMs are large containers).

```bash
cd infrastructure/kubernetes

# Deploy all three NIMs
./deploy-nims.sh
```

**What this deploys:**

1. **Nemotron Reasoning NIM** (llama-3.3-nemotron-super-49b-v1.5)
   - Pulls ~40GB image
   - Requests 1x GPU
   - Karpenter provisions g5.xlarge node

2. **Llama 3.3 70B Instruct NIM**
   - Pulls ~60GB image
   - Requests 2x GPUs
   - Karpenter provisions g5.4xlarge or larger node

3. **Embedding NIM** (Arctic Embed Large)
   - Pulls ~10GB image
   - Requests 1x GPU

### Monitoring Deployment

Watch the pods:
```bash
kubectl get pods -n nim --watch
```

Watch Karpenter provision nodes:
```bash
kubectl get nodes --watch
```

You'll see new nodes with names like `karpenter-xxxxx` appear as NIMs request GPUs.

### Verify NIMs are Running

```bash
# Check all pods are Running
kubectl get pods -n nim

# Check services
kubectl get svc -n nim

# Test Nemotron NIM
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://nemotron-nano-service.nim.svc.cluster.local:8000/v1/models

# Expected: JSON response with model info
```

---

## Agent Deployment

This takes approximately **10 minutes**.

```bash
# Still in infrastructure/kubernetes directory
./deploy-agent.sh
```

**What this does:**

1. Creates ECR repositories for your images
2. Builds Docker images for:
   - Backend (FastAPI + AI-Q + UDF)
   - Frontend (Next.js + CopilotKit)
3. Pushes images to ECR
4. Deploys to Kubernetes
5. Creates LoadBalancer for frontend

### Monitoring Deployment

```bash
# Watch pods start
kubectl get pods -n aiq-agent --watch

# Check backend logs
kubectl logs -n aiq-agent -l component=backend -f

# Check frontend logs
kubectl logs -n aiq-agent -l component=frontend -f
```

### Get Application URL

```bash
# Get the LoadBalancer URL
kubectl get svc aiq-agent-frontend -n aiq-agent

# Or use this one-liner
kubectl get svc aiq-agent-frontend -n aiq-agent \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

Copy the URL (e.g., `a1234567890abcdef.us-west-2.elb.amazonaws.com`) and open in your browser.

---

## Verification

### 1. Check All Components

```bash
# Infrastructure
kubectl get nodes  # Should show Karpenter-provisioned GPU nodes

# NIMs
kubectl get pods -n nim  # All should be Running
kubectl get svc -n nim   # 3 services

# Agent
kubectl get pods -n aiq-agent  # 4 pods (2 backend, 2 frontend)
kubectl get svc -n aiq-agent   # 2 services
```

### 2. Test the Application

1. Open the LoadBalancer URL in your browser
2. You should see the AI-Q Research Assistant interface
3. Try a simple query: "What is Amazon EKS?"
4. Observe the "Agentic Flow" panel for real-time updates
5. Try a complex query: "Generate a report on NIMs on EKS with cost analysis"

### 3. Verify Agentic Flow Visualization

The left panel should show:
- 🤔 Planning phase
- Strategy selection (Simple RAG or UDF)
- Execution logs
- ✅ Completion status

### 4. Test Backend API Directly

```bash
# Port-forward to backend
kubectl port-forward -n aiq-agent svc/aiq-agent-service 8000:80

# In another terminal, test the health endpoint
curl http://localhost:8000/health

# Test research endpoint
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "What is Kubernetes?",
    "report_organization": "Brief introduction",
    "collection": "",
    "search_web": true
  }'
```

---

## Cleanup

### Option 1: Delete Only the Agent (Keep NIMs)

```bash
kubectl delete namespace aiq-agent
```

### Option 2: Delete Everything (Including NIMs)

```bash
# Delete agent
kubectl delete namespace aiq-agent

# Delete NIMs
helm uninstall nemotron-nano-nim -n nim
helm uninstall instruct-llm-nim -n nim
helm uninstall embedding-nim -n nim
kubectl delete namespace nim
```

### Option 3: Destroy All Infrastructure

```bash
cd infrastructure/terraform
terraform destroy

# Type 'yes' when prompted
```

**Warning**: This will delete:
- EKS cluster
- All nodes (including Karpenter-provisioned)
- VPC and networking
- IAM roles

**Cost stops accumulating once destroyed.**

---

## Cost Management

### Estimated Costs (us-west-2)

| Component | Instance | Cost/Hour | Notes |
|-----------|----------|-----------|-------|
| EKS Cluster | - | $0.10 | Control plane |
| System Nodes (2x) | m5.xlarge | ~$0.38 | Management |
| Nemotron NIM | g5.xlarge | ~$1.00 | 1x A10G GPU |
| Instruct NIM | g5.4xlarge | ~$2.04 | 1x A10G GPU |
| Embedding NIM | g5.xlarge | ~$1.00 | 1x A10G GPU |
| **Total** | | **~$4.50/hr** | **With Spot discounts** |

### Reduce Costs

1. **Use Spot Instances** (Already configured in Karpenter)
   - ~70% discount
   - Configured in `karpenter-provisioner.yaml`

2. **Stop NIMs When Not Using**
   ```bash
   kubectl scale deployment nemotron-nano-nim --replicas=0 -n nim
   kubectl scale deployment instruct-llm-nim --replicas=0 -n nim
   kubectl scale deployment embedding-nim --replicas=0 -n nim
   ```

3. **Destroy Infrastructure When Done**
   ```bash
   cd infrastructure/terraform
   terraform destroy
   ```

---

## Troubleshooting

### Issue: NIMs stuck in Pending

**Cause**: Karpenter hasn't provisioned GPU nodes yet

**Solution**:
```bash
# Check Karpenter logs
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter -f

# Check if nodes are being provisioned
kubectl get nodes --watch

# Check NodePool
kubectl get nodepool
```

### Issue: "ImagePullBackOff" on NIMs

**Cause**: NGC API key is incorrect or expired

**Solution**:
```bash
# Verify NGC API key secret
kubectl get secret ngc-api-key -n nim -o yaml

# Update if needed
kubectl delete secret ngc-api-key -n nim
kubectl create secret generic ngc-api-key \
    --from-literal=NGC_API_KEY=$NGC_API_KEY \
    --namespace=nim

# Restart the failing pod
kubectl delete pod <nim-pod-name> -n nim
```

### Issue: Frontend can't connect to backend

**Cause**: Service networking issue

**Solution**:
```bash
# Check if backend is running
kubectl get pods -n aiq-agent -l component=backend

# Check backend logs
kubectl logs -n aiq-agent -l component=backend --tail=100

# Check if service exists
kubectl get svc -n aiq-agent

# Test connectivity from frontend pod
kubectl exec -n aiq-agent deployment/aiq-agent-frontend -- \
  curl http://aiq-agent-service:80/health
```

### Issue: "UDF execution failed"

**Cause**: Nemotron NIM not reachable or slow

**Solution**:
```bash
# Test Nemotron connectivity from agent pod
kubectl exec -n aiq-agent deployment/aiq-agent-backend -- \
  curl http://nemotron-nano-service.nim.svc.cluster.local:8000/v1/models

# Check Nemotron logs
kubectl logs -n nim -l app.kubernetes.io/instance=nemotron-nano-nim --tail=100

# Increase timeout if needed (edit backend/main.py)
```

### Issue: High costs

**Cause**: GPU nodes running 24/7

**Solution**:
```bash
# Check current node utilization
kubectl top nodes

# Scale down NIMs
kubectl scale deployment --all --replicas=0 -n nim

# Karpenter will terminate idle nodes after 10 minutes

# Or destroy everything
terraform destroy
```

---

## Advanced: Using Hosted NIMs

To use NVIDIA's hosted NIMs instead of self-hosting:

1. Get API key from https://build.nvidia.com/

2. Update backend environment:
   ```yaml
   # In agent-deployment.yaml, update:
   NEMOTRON_NIM_URL: "https://integrate.api.nvidia.com/v1"
   INSTRUCT_LLM_URL: "https://integrate.api.nvidia.com/v1"
   ```

3. Skip NIM deployment:
   ```bash
   # Don't run ./deploy-nims.sh
   # Deploy only the agent
   ./deploy-agent.sh
   ```

**Pros**: No GPU costs, simpler deployment
**Cons**: Rate limits, potential latency, less control

---

## Next Steps

Once deployed:

1. **Explore the UI**: Try different research queries
2. **Watch the Logs**: Observe agentic reasoning in real-time
3. **Customize**: Modify `hackathon_agent.py` to add new capabilities
4. **Scale**: Add more agent replicas for higher throughput
5. **Integrate**: Connect to your own data sources via RAG

---

## Support

- **Issues**: Create a GitHub issue
- **Documentation**: See [README.md](README.md)
- **Design Plan**: See [cursor/design_plan.md](cursor/design_plan.md)

**Happy Hacking!** 🚀

