# EKS Cluster Upgrade & Karpenter Operations Guide

> **Last Updated**: December 21, 2025  
> **Cluster**: aiq-udf-eks  
> **Region**: us-west-2
> **Current Version**: Kubernetes 1.34

This document captures learnings from upgrading the EKS cluster from v1.28 to v1.34 and managing Karpenter-provisioned GPU nodes.

---

## Table of Contents

1. [EKS Version Upgrade](#eks-version-upgrade)
2. [Karpenter IAM Permission Issues](#karpenter-iam-permission-issues)
3. [Node Decommissioning](#node-decommissioning)
4. [PodDisruptionBudget (PDB) Blocking](#poddisruptionbudget-pdb-blocking)
5. [Milvus Scheduling Issues](#milvus-scheduling-issues)
6. [Cost Optimization](#cost-optimization)
7. [Terraform IaC Changes](#terraform-iac-changes)
8. [TensorRT-LLM Memory Requirements](#tensorrt-llm-memory-requirements)

---

## EKS Version Upgrade

### Key Learnings

1. **Always use Terraform for upgrades** - Don't use AWS Console "Upgrade" button for Terraform-managed clusters. It causes state drift.

2. **Incremental upgrades only** - EKS only allows single minor version jumps:
   ```
   1.28 → 1.29 → 1.30 → 1.31 ✅
   1.28 → 1.31 ❌ (InvalidParameterException)
   ```

3. **Node groups upgrade separately** - After control plane upgrade, node groups must be upgraded individually.

### Upgrade Process

```bash
# Step 1: Update Terraform variable
# infrastructure/terraform/variables.tf
variable "eks_cluster_version" {
  default = "1.29"  # Increment one version at a time
}

# Step 2: Apply targeting EKS module
cd infrastructure/terraform
terraform apply -target=module.eks -auto-approve

# Step 3: Wait for control plane (~10-15 min)
aws eks describe-cluster --name aiq-udf-eks --query 'cluster.status'

# Step 4: Update node groups (may take 20-30 min each)
aws eks update-nodegroup-version \
  --cluster-name aiq-udf-eks \
  --nodegroup-name aiq-udf-eks-sys-od \
  --kubernetes-version 1.29

# Step 5: Monitor node group update
aws eks describe-nodegroup \
  --cluster-name aiq-udf-eks \
  --nodegroup-name aiq-udf-eks-sys-od \
  --query 'nodegroup.status'

# Repeat steps 1-5 for each version increment
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Unsupported Kubernetes minor version update` | Skipping versions | Do incremental upgrades |
| `PodEvictionFailure` during node group update | PDBs blocking eviction | Temporarily delete blocking PDBs |
| Node group stuck in `UPDATING` | Pods can't be evicted | Check PDBs, delete stuck pods |
| `AMI Type AL2_x86_64 is only supported for kubernetes versions 1.32 or earlier` | AL2 deprecated | Use `AL2023_x86_64_STANDARD` |

### K8s 1.33+ AMI Requirements

**Amazon Linux 2 (AL2) is deprecated for K8s 1.33+**. You must use:

| Component | AMI Type | Notes |
|-----------|----------|-------|
| **Managed Node Groups** | `AL2023_x86_64_STANDARD` | Set in Terraform |
| **Karpenter GPU Nodes** | `Bottlerocket` | AL2023 not supported in Karpenter v0.32 |

```hcl
# Terraform - managed node groups
eks_managed_node_groups = {
  sys_od = {
    ami_type = "AL2023_x86_64_STANDARD"  # Required for K8s 1.33+
    ...
  }
}
```

```yaml
# Karpenter EC2NodeClass - GPU nodes
apiVersion: karpenter.k8s.aws/v1beta1
kind: EC2NodeClass
spec:
  amiFamily: Bottlerocket  # Not AL2!
  # Note: Bottlerocket uses TOML userData, not bash
  # Remove any bash userData when switching to Bottlerocket
```

---

## Karpenter IAM Permission Issues

### Problem: `ec2:RunInstances` Unauthorized

The default Karpenter module IAM policy has a restrictive condition on `ec2:RunInstances` that requires specific tags on launch templates. New launch templates may not have these tags.

**Error Log:**
```
UnauthorizedOperation: You are not authorized to perform: ec2:RunInstances 
on resource: arn:aws:ec2:us-west-2:ACCOUNT:launch-template/*
```

### Problem: `ec2:TerminateInstances` Unauthorized

Karpenter also needs permission to terminate instances it created.

**Error Log:**
```
UnauthorizedOperation: You are not authorized to perform: ec2:TerminateInstances 
on resource: arn:aws:ec2:us-west-2:ACCOUNT:instance/i-xxx
```

### Solution: Additional IAM Policy

Added to `infrastructure/terraform/main.tf`:

```hcl
resource "aws_iam_role_policy" "karpenter_ec2_permissions_fix" {
  name = "KarpenterEC2PermissionsFix"
  role = split("/", module.karpenter.irsa_arn)[1]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRunInstancesWithLaunchTemplate"
        Effect = "Allow"
        Action = "ec2:RunInstances"
        Resource = [
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:launch-template/*"
        ]
      },
      {
        Sid    = "AllowTerminateInstances"
        Effect = "Allow"
        Action = "ec2:TerminateInstances"
        Resource = "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/karpenter.sh/nodepool" = "nvidia-nim-gpu"
          }
        }
      }
    ]
  })
}
```

### Manual Fix (Immediate)

```bash
aws iam put-role-policy \
  --role-name KarpenterIRSA-aiq-udf-eks-20251105001410752000000018 \
  --policy-name KarpenterEC2PermissionsFix \
  --policy-document file://karpenter-iam-fix.json \
  --region us-west-2

# Restart Karpenter to pick up new permissions
kubectl rollout restart deployment karpenter -n karpenter
```

---

## Node Decommissioning

### Decommissioning Karpenter-Managed Nodes

Karpenter nodes are managed via `NodeClaim` CRDs. To decommission:

```bash
# 1. Check what's running on the node
kubectl get pods --all-namespaces -o wide --field-selector spec.nodeName=<node-name>

# 2. Delete the NodeClaim (Karpenter handles draining and EC2 termination)
kubectl delete nodeclaim <nodeclaim-name>

# 3. Verify termination
kubectl get nodes
kubectl get nodeclaims
```

### Dealing with Karpenter Webhook During Deletion

If Karpenter is stopped, you'll get webhook errors:
```
failed calling webhook "validation.webhook.karpenter.sh": no endpoints available
```

**Solution**: Keep Karpenter running when deleting NodeClaims. The delete command marks nodes for deletion, and Karpenter's finalizer handles the actual termination.

### Force Node Removal (Emergency Only)

```bash
# Remove finalizers (use with caution!)
kubectl patch nodeclaim <name> -p '{"metadata":{"finalizers":null}}' --type=merge

# Or cordon and drain manually, then terminate EC2
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data --force
aws ec2 terminate-instances --instance-ids <instance-id>
```

---

## PodDisruptionBudget (PDB) Blocking

### Problem

Node group upgrades stuck with `PodEvictionFailure` due to PDBs preventing pod eviction.

### Identifying Blocking PDBs

```bash
# List all PDBs
kubectl get pdb --all-namespaces

# Check PDB details
kubectl describe pdb <pdb-name> -n <namespace>
```

### Common Blocking PDBs in Our Setup

| PDB | Namespace | Issue |
|-----|-----------|-------|
| `aiq-agent-backend-pdb` | default | minAvailable: 1 with 1 replica |
| `milvus-etcd-pdb` | milvus | minAvailable: 1 |
| `milvus-minio-pdb` | milvus | minAvailable: 1 |
| `milvus-standalone-pdb` | milvus | maxUnavailable: 0 |

### Temporary Fix During Upgrades

```bash
# Delete blocking PDBs temporarily
kubectl delete pdb aiq-agent-backend-pdb -n default
kubectl delete pdb milvus-etcd-pdb -n milvus
kubectl delete pdb milvus-minio-pdb -n milvus
kubectl delete pdb milvus-standalone-pdb -n milvus

# After upgrade, recreate if needed
kubectl apply -f infrastructure/kubernetes/pod-disruption-budgets.yaml
```

---

## Milvus Scheduling Issues

### Common Problems

1. **Volume Node Affinity Conflict** - EBS volumes are AZ-locked. Pod must schedule in same AZ as its PVC.

2. **Insufficient CPU** - Milvus components need significant CPU. May need to scale node groups.

3. **GPU Taints** - Milvus pods may try to schedule on GPU nodes but fail due to taints.

### Solutions

```bash
# Scale up non-GPU nodes
aws eks update-nodegroup-config \
  --cluster-name aiq-udf-eks \
  --nodegroup-name aiq-udf-eks-sys-sp \
  --scaling-config minSize=1,maxSize=6,desiredSize=4

# Remove GPU taint temporarily (emergency)
kubectl taint nodes <node-name> nvidia.com/gpu=true:NoSchedule-

# Check PVC AZ binding
kubectl get pvc -n milvus -o wide
kubectl get pv -o yaml | grep -A5 nodeAffinity
```

### Milvus Recovery Sequence

If Milvus is unhealthy, restart in order:
```bash
kubectl rollout restart statefulset milvus-etcd -n milvus
# Wait for etcd to be ready
kubectl rollout restart statefulset milvus-minio -n milvus  
# Wait for minio to be ready
kubectl rollout restart deployment milvus-standalone -n milvus
```

---

## Cost Optimization

### GPU Instance Costs (us-west-2, On-Demand)

| Instance Type | GPU | vCPUs | Memory | Hourly | Daily |
|---------------|-----|-------|--------|--------|-------|
| g5.xlarge | 1x A10G | 4 | 16 GB | ~$1.00 | ~$24 |
| g5.2xlarge | 1x A10G | 8 | 32 GB | ~$1.21 | ~$29 |
| g5.4xlarge | 1x A10G | 16 | 64 GB | ~$1.62 | ~$39 |

### Our Optimization

| Before | After | Savings |
|--------|-------|---------|
| 2x g5.2xlarge (old v1.28) + 6x new GPU nodes | 2x g5.xlarge | ~$58/day |

### Right-Sizing Recommendations

1. **Embedding NIM**: g5.xlarge is sufficient (small model)
2. **LLM NIM (8B)**: g5.xlarge or g5.2xlarge depending on throughput needs
3. **Large LLM (70B)**: Requires g5.4xlarge or larger

### Enable Karpenter Consolidation

Karpenter can automatically consolidate underutilized nodes:

```yaml
# In NodePool spec
disruption:
  consolidationPolicy: WhenUnderutilized
  consolidateAfter: 30s
```

---

## Terraform IaC Changes

### Summary of Changes Made

| File | Change | Purpose |
|------|--------|---------|
| `variables.tf` | `eks_cluster_version = "1.31"` | EKS upgrade |
| `main.tf` | `sys_sp.desired_size = 4` | More non-GPU capacity |
| `main.tf` | `sys_sp.max_size = 6` | Allow scaling headroom |
| `main.tf` | Added `karpenter_ec2_permissions_fix` | Fix RunInstances/TerminateInstances |

### Verifying State Sync

```bash
cd infrastructure/terraform

# Check for drift
terraform plan

# Should show "No changes" if state is synced
```

### Rolling Back (Emergency)

```bash
# Revert to previous state
git checkout HEAD~1 -- infrastructure/terraform/

# Apply the reverted config
terraform apply
```

---

## Quick Reference Commands

```bash
# Cluster status
kubectl get nodes -o wide
kubectl get nodeclaims

# Check Karpenter logs
kubectl logs -n karpenter deployment/karpenter -c controller --tail=50

# Check NIM status
kubectl get pods -n nim

# EC2 GPU instances
aws ec2 describe-instances \
  --filters "Name=instance-type,Values=g5.*" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].[InstanceId,InstanceType,PrivateIpAddress]' \
  --output table --region us-west-2

# Node group status
aws eks list-nodegroups --cluster-name aiq-udf-eks
aws eks describe-nodegroup --cluster-name aiq-udf-eks --nodegroup-name <name>
```

---

## Lessons Learned

1. **Always codify changes in Terraform** - Manual AWS CLI/Console changes cause drift and confusion.

2. **Karpenter IAM is tricky** - The default module policy is often too restrictive. Expect to add supplementary permissions.

3. **PDBs can block everything** - During maintenance, temporarily removing PDBs is often necessary.

4. **Incremental upgrades only** - Never skip EKS minor versions.

5. **Keep Karpenter running for node operations** - Its webhooks and finalizers are required for proper NodeClaim lifecycle management.

6. **GPU nodes are expensive** - Right-size aggressively and use Karpenter consolidation.

7. **EBS volumes are AZ-locked** - Plan stateful workload placement carefully.

---

## NVIDIA NIM Model Selection for A10G GPUs

### Key Findings (December 2025)

#### Nemotron Nano 8B v1 vs 9B v2

| Model | Architecture | VRAM for Weights | State Cache | Works on A10G (24GB)? |
|-------|--------------|------------------|-------------|----------------------|
| **8B v1** | Transformer (Llama) | ~16GB bf16 | KV cache scales with seq_len | ✅ Yes, with 16K context |
| **9B v2** | Mamba Hybrid (NemotronH) | ~18GB bf16 | **33.75GB fixed Mamba state** | ❌ No, needs 48GB+ |

#### Why 9B v2 Fails on A10G

The Nemotron 9B v2 uses a **hybrid Mamba architecture** with a fixed-size Mamba state cache:
- `MambaCacheManager` allocates 33.75 GiB regardless of batch/seq length
- This is fundamentally different from transformer KV cache
- Even with `NIM_MAX_BATCH_SIZE=1`, the state cache is massive

#### Available NIM Profiles for A10G

| Model | Profiles | Engine | Precision |
|-------|----------|--------|-----------|
| 8B v1 | `tensorrt_llm-trtllm_buildable-bf16-tp1-pp1` | TensorRT-LLM | bf16 |
| 8B v1 | `vllm-bf16-tp1-pp1` | vLLM | bf16 |
| 9B v2 | `vllm-bf16-tp1-pp1` | vLLM only | bf16 |
| 9B v2 | `vllm-bf16-tp2-pp1` | vLLM | bf16 (2 GPUs) |

**Note**: FP8 optimized profiles for 8B v1 are only available on L40S (48GB) or H100 (80GB+).

### Recommended Configuration for A10G

```yaml
env:
- name: NIM_MAX_MODEL_LEN
  value: "16384"  # 16K context - good balance for deep research
```

With this config:
- **Model weights**: ~16GB
- **KV cache**: ~6GB (for 16K context)
- **TensorRT-LLM overhead**: ~2GB
- **Total**: ~24GB (fits A10G)

### Startup Time

TensorRT-LLM builds the engine at first startup (~5-10 minutes). Use generous startup probes:

```yaml
startupProbe:
  httpGet:
    path: /v1/health/ready
    port: 8000
  initialDelaySeconds: 120
  periodSeconds: 30
  failureThreshold: 60  # Allow up to 30 minutes
```

### For Larger Models (9B+)

Use `g5.12xlarge` (4× A10G, 96GB total) or `g5.48xlarge` (8× A10G, 192GB):
- Set `nvidia.com/gpu: "2"` or `"4"` in resource limits
- NIM will automatically select TP=2 or TP=4 profiles
- Ensure NCCL works (AL2023 required, Bottlerocket has issues)

---

## Cross-Node Security Group Issues

### Symptom

Pods on managed node groups cannot communicate with pods on Karpenter-provisioned GPU nodes:
- DNS resolution works
- Direct pod-to-pod IP connections time out
- Same-node communication works fine

### Root Cause

Karpenter GPU nodes use the EKS cluster security group (`eks-cluster-sg-*`), while managed node groups use a separate node security group (`*-node-*`). By default, these don't allow cross-traffic.

### Diagnosis

```bash
# Check which security groups nodes use
aws ec2 describe-instances --filters "Name=tag:kubernetes.io/cluster/YOUR-CLUSTER,Values=owned" \
  --query 'Reservations[].Instances[].[PrivateIpAddress,SecurityGroups[0].GroupId]' --output table

# Example output:
# 10.0.12.0   sg-08900183df289ae5a  (managed node group)
# 10.0.38.236 sg-0c36bbdb818a4d1e0  (Karpenter GPU node)
```

### Fix

Add bidirectional rules allowing all traffic between the two security groups:

```bash
# Allow traffic FROM managed node SG TO GPU cluster SG
aws ec2 authorize-security-group-ingress \
  --group-id sg-0c36bbdb818a4d1e0 \
  --protocol all \
  --source-group sg-08900183df289ae5a

# Allow traffic FROM GPU cluster SG TO managed node SG  
aws ec2 authorize-security-group-ingress \
  --group-id sg-08900183df289ae5a \
  --protocol all \
  --source-group sg-0c36bbdb818a4d1e0
```

### Terraform Fix (Recommended)

Add to `main.tf`:

```hcl
# Allow cross-SG communication between managed nodes and Karpenter nodes
resource "aws_security_group_rule" "node_to_cluster" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "all"
  source_security_group_id = module.eks.node_security_group_id
  security_group_id        = module.eks.cluster_primary_security_group_id
}

resource "aws_security_group_rule" "cluster_to_node" {
  type                     = "ingress"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "all"
  source_security_group_id = module.eks.cluster_primary_security_group_id
  security_group_id        = module.eks.node_security_group_id
}
```

---

## NVIDIA NIM Guided JSON (Structured Output)

### Working Format (Verified Dec 21, 2025)

For NVIDIA NIM with LangChain, you **MUST** use `extra_body` to wrap `nvext`:

```python
# LangChain ChatOpenAI - CORRECT FORMAT
llm = ChatOpenAI(
    base_url=nim_url,
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    model_kwargs={
        "extra_body": {"nvext": {"guided_json": json_schema}}  # ← MUST use extra_body!
    }
)

# Direct API call (for reference)
response = client.chat.completions.create(
    model="nvidia/llama-3.1-nemotron-nano-8b-v1",
    messages=messages,
    extra_body={"nvext": {"guided_json": json_schema}},  # ← extra_body required
)
```

### Why extra_body is Required

LangChain's `ChatOpenAI` passes `model_kwargs` to the OpenAI Python client's `create()` method.
The OpenAI client **validates** kwargs and rejects unknown ones like `nvext`.
Using `extra_body` adds custom parameters to the HTTP request body.

### Formats That DON'T Work

```python
# ❌ OpenAI client rejects unknown kwargs
model_kwargs={"nvext": {"guided_json": json_schema}}
# Error: AsyncCompletions.create() got an unexpected keyword argument 'nvext'

# ❌ guided_json without nvext wrapper
extra_body={"guided_json": json_schema}
```

### Implementation

All TTD-DR components use the correct `extra_body` wrapped format:
- `core.py` (3 locations)
- `evaluator.py`
- `planner.py`
- `denoiser.py`
- `red_team.py`
- `context_pruner.py`
- `search.py`
- `evolver.py`
- `hackathon_agent.py`

See `NVIDIA_GUIDED_JSON_TODO.md` for full implementation details.

---

## AWS Resource Auditing and Cleanup

### Periodic Resource Audit (2025-12-20)

Performed a comprehensive audit of AWS resources in us-west-2 using AWS Global View CSV export.

### Issues Found and Fixed

#### 1. Orphaned Security Group (DELETED)

**Resource:** `sg-090c4651c1ffe4121` (launch-wizard-1)
- **VPC:** Default VPC (vpc-f9df1e9c) - NOT the EKS VPC
- **Created:** 2023-10-31 from a one-off EC2 launch wizard
- **Verification:** Confirmed no ENIs, instances, or other SGs reference it
- **Action:** Deleted

```bash
# Verify SG is truly orphaned before deletion
aws ec2 describe-network-interfaces --filters "Name=group-id,Values=sg-090c4651c1ffe4121" --region us-west-2
aws ec2 describe-instances --filters "Name=instance.group-id,Values=sg-090c4651c1ffe4121" --region us-west-2
aws ec2 describe-security-groups --filters "Name=ip-permission.group-id,Values=sg-090c4651c1ffe4121" --region us-west-2

# Delete if all empty
aws ec2 delete-security-group --group-id sg-090c4651c1ffe4121 --region us-west-2
```

#### 2. Failed Helm Release with Orphaned Pods (CLEANED UP)

**Issue:** `milvus` Helm release in `rag-blueprint` namespace was in FAILED state
- Left ~15 orphaned Pulsar pods running (`milvus-pulsarv3-*`)
- Kafka pod was scheduled on a GPU node (wasting GPU resources)

**Action:** Uninstalled the failed release

```bash
helm uninstall milvus -n rag-blueprint
```

**Follow-up (Dec 21, 2025):** Orphaned Pulsar configmaps remained after pod cleanup:
```bash
# Check for orphaned Pulsar configmaps
kubectl get configmap -n rag-blueprint | grep pulsar

# Delete orphaned configmaps (safe if no Pulsar pods exist)
kubectl delete configmap -n rag-blueprint \
  milvus-standalone-pulsarv3-bookie \
  milvus-standalone-pulsarv3-broker \
  milvus-standalone-pulsarv3-proxy \
  milvus-standalone-pulsarv3-recovery \
  milvus-standalone-pulsarv3-zookeeper
```

**Note:** Milvus standalone v2.6.5+ uses "woodpecker" as its internal message queue, not Pulsar. Pulsar resources from older deployments can be safely removed.

#### 3. Unused GPU Node (DELETED)

**Issue:** Karpenter GPU node `ip-10-0-17-35.us-west-2.compute.internal` had no NIM workloads
- Was only running `milvus-kafka-0` (no GPU needed)
- After milvus release cleanup, node was completely empty

**Action:** Deleted the NodeClaim

```bash
kubectl delete nodeclaim nvidia-nim-gpu-s69ck
```

**Cost Savings:** ~$24/day = ~$720/month

### Resource Inventory After Cleanup

| Resource Type | Count | Purpose |
|---------------|-------|---------|
| GPU Nodes (Karpenter) | 2 | Optimal: 1 for embedding, 1 for LLM |
| Managed Nodes | 5 | 4 spot + 1 on-demand |
| NAT Gateways | 3 | One per AZ (HA) |
| Security Groups | 6 | EKS cluster, nodes, ELBs (1 orphan deleted) |
| Helm Releases | 1 | milvus-standalone only |

### Audit Checklist for Future Reviews

1. **Check for terminated instances in Global View CSV** - CSV may contain stale data
2. **Verify security groups have attachments** before considering orphaned
3. **Check Helm releases** for failed status: `helm list -A | grep -v deployed`
4. **Review GPU node utilization** - ensure GPU workloads on GPU nodes:
   ```bash
   for node in $(kubectl get nodes -l karpenter.sh/nodepool=nvidia-nim-gpu --no-headers | awk '{print $1}'); do
     echo "--- $node ---"
     kubectl get pods -A --field-selector spec.nodeName=$node | grep -v kube-system
   done
   ```
5. **Check for pods with GPU tolerations that don't need GPU** (waste of resources)

### Cost Optimization Opportunities

| Item | Current | Could Reduce To | Monthly Savings |
|------|---------|-----------------|-----------------|
| NAT Gateways | 3 | 1 (for non-HA) | ~$64/mo |
| GPU nodes | 2 | 2 (optimal now) | - |

### Default VPC Resources (Non-EKS)

These exist in the default VPC (vpc-f9df1e9c) and are NOT related to EKS:
- `sg-69fe750c` (default SG) - Normal, cannot delete
- `subnet-*` (4 default subnets) - Normal defaults
- `igw-5b79883e` - Default internet gateway
- `rtb-ea9b568f` - Default route table

These can be left alone unless you want to clean up the default VPC entirely.

---

## TensorRT-LLM Memory Requirements

### Key Discovery (December 2025)

TensorRT-LLM NIMs have **two distinct phases** with very different memory requirements:

| Phase | System RAM | GPU VRAM | Duration |
|-------|------------|----------|----------|
| **Engine Build** | **~64GB** | ~24GB | 3-5 min |
| **Inference** | ~10GB | ~20GB | Ongoing |

**Critical Insight**: The TRT-LLM engine is built at **every pod startup** - it's NOT cached to disk. This means you cannot run TRT-LLM on small instances even if inference would fit.

### Instance Sizing for TRT-LLM

| Instance | RAM | VRAM | TRT-LLM Build | Inference | Cost/hr |
|----------|-----|------|---------------|-----------|---------|
| g5.xlarge | 16GB | 24GB | ❌ OOM | ✅ Works | $1.01 |
| g5.2xlarge | 32GB | 24GB | ❌ OOM | ✅ Works | $1.21 |
| g5.4xlarge | 64GB | 24GB | ✅ Works | ✅ Works | $1.62 |
| g5.8xlarge | 128GB | 24GB | ✅ Works | ✅ Works | $2.45 |

**Recommendation**: Use **g5.4xlarge** for TRT-LLM NIMs. It's the smallest instance that can handle the engine build.

### NIM Backend Selection (NVIDIA Ignores Override)

The NVIDIA NIM container includes both TensorRT-LLM and vLLM backends but **ignores** environment variables attempting to force vLLM:

```yaml
# These environment variables are IGNORED by the NIM:
env:
- name: NIM_BACKEND
  value: "vllm"              # ❌ Ignored
- name: NIM_MANIFEST_PROFILE_ID
  value: "4f904d571fe60ff24695b5ee2aa42da58cb460787a968f1e8a09f5a7e862728d"  # ❌ Ignored
```

The NIM **always prefers TensorRT-LLM** when:
1. GPU is compatible (A10G, L40S, H100, etc.)
2. TRT-LLM buildable profile exists

### PersistentVolume for Model Cache

#### What Gets Cached

A PersistentVolume at `NIM_CACHE_PATH=/model-cache` caches:

| Cached | Not Cached |
|--------|------------|
| ✅ Model weights (15GB) | ❌ TRT-LLM compiled engine |
| ✅ Tokenizer files | ❌ Runtime state |
| ✅ NGC metadata | |

#### PV Setup

```yaml
# PersistentVolumeClaim
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nim-engine-cache
  namespace: nim
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp2  # Or gp3 if available
  resources:
    requests:
      storage: 50Gi
---
# Deployment volume mount
spec:
  template:
    spec:
      securityContext:
        fsGroup: 1000  # Required! NIM runs as uid 1000
      containers:
      - name: nim
        volumeMounts:
        - name: model-cache
          mountPath: /model-cache
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: nim-engine-cache
```

#### PV Benefits and Limitations

| Benefit | Impact |
|---------|--------|
| Faster startup | 3 min vs 15 min (no model download) |
| Resilient to pod restarts | No re-download of 15GB |
| Lower egress costs | Model not downloaded from NGC repeatedly |

| Limitation | Implication |
|------------|-------------|
| TRT-LLM engine still rebuilds | Still needs 64GB RAM at startup |
| Cannot enable g5.xlarge | Engine build will OOM |
| PV is zone-locked (EBS) | Pod must schedule in same AZ |

#### Cost Analysis

| Configuration | Instance | Storage | Monthly Total |
|---------------|----------|---------|---------------|
| g5.8xlarge (no PV) | $1,789 | $0 | **$1,789** |
| g5.4xlarge (no PV) | $1,183 | $0 | **$1,183** |
| g5.4xlarge + PV | $1,183 | $4 | **$1,187** |

**Savings with g5.4xlarge vs g5.8xlarge**: ~$600/month (34%)

### Recommended NIM Deployment Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llama-instruct-nim
  namespace: nim
spec:
  template:
    spec:
      securityContext:
        fsGroup: 1000  # Required for PVC write access
      containers:
      - name: nim
        image: nvcr.io/nim/nvidia/llama-3.1-nemotron-nano-8b-v1:latest
        resources:
          requests:
            memory: "48Gi"      # Ensures g5.4xlarge scheduling
            nvidia.com/gpu: "1"
          limits:
            memory: "60Gi"
            nvidia.com/gpu: "1"
        env:
        - name: NIM_CACHE_PATH
          value: "/model-cache"
        - name: NIM_MAX_MODEL_LEN
          value: "8192"
        - name: NIM_MAX_BATCH_SIZE
          value: "32"
        startupProbe:
          httpGet:
            path: /v1/health/ready
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 10
          failureThreshold: 180  # 30 minutes total
        volumeMounts:
        - name: model-cache
          mountPath: /model-cache
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: nim-engine-cache
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Exists"
        effect: "NoSchedule"
```

### Troubleshooting TRT-LLM OOM

#### Symptoms

```
# Kubernetes shows:
STATUS: OOMKilled
RESTARTS: 15

# Logs show (before kill):
INFO: Building rank 0 with config...
0it [00:00, ?it/s]165it [00:00, 1649.43it/s]...
# Then container killed
```

#### Root Cause

System RAM exhausted during TensorRT engine compilation, NOT GPU VRAM.

#### Fix

Increase instance size to g5.4xlarge (64GB RAM) or larger.

### Future Considerations

1. **Pre-built engines**: NVIDIA may release pre-compiled TRT-LLM engines in future NIM versions
2. **Engine caching**: Future NIM versions may support saving compiled engines to PV
3. **vLLM-only NIMs**: Using a vLLM-only image would eliminate the build step but sacrifice inference performance

