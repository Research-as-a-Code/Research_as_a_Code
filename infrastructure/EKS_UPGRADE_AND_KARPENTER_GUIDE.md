# EKS Cluster Upgrade & Karpenter Operations Guide

> **Last Updated**: December 20, 2025  
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

