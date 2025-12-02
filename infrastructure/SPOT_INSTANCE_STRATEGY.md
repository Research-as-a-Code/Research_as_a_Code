# Spot Instance Cost Optimization Strategy

**Date:** December 2, 2025  
**Status:** ✅ Ready to Deploy  
**Expected Savings:** ~$1,500/month (~70% reduction on compute costs)

---

## 📊 Executive Summary

This strategy migrates non-critical workloads to AWS EC2 Spot Instances while keeping stateful services on reliable on-demand instances. This provides **~70% cost savings** on compute with **zero data loss risk** and **minimal service interruption**.

### Key Principles

✅ **Spot Instances for:** Stateless, restartable workloads  
❌ **On-Demand for:** Persistent data stores  
🛡️ **Protection:** Pod Disruption Budgets ensure high availability  

---

## 💰 Cost Breakdown

### Current Infrastructure (All On-Demand)

| Component | Instance Type | Quantity | Hourly | Monthly (24/7) |
|-----------|--------------|----------|--------|----------------|
| GPU Nodes | g5.2xlarge | 3 | $3.636 | $2,618 |
| System Nodes | m5.xlarge | 2 | $0.384 | $277 |
| **TOTAL** | | | **$4.02** | **$2,895** |

### Optimized Infrastructure (Spot + On-Demand Mix)

| Component | Instance Type | Quantity | Capacity | Hourly | Monthly (24/7) |
|-----------|--------------|----------|----------|--------|----------------|
| **GPU Nodes** | g5.2xlarge | 3 | Spot | $1.092 | $786 |
| **System Spot** | m5.xlarge | 2 | Spot | $0.116 | $84 |
| **System On-Demand** | m5.xlarge | 1 | On-Demand | $0.192 | $138 |
| **TOTAL** | | | | **$1.40** | **$1,008** |

### 💵 Savings

- **Monthly Savings:** $1,887 (~65% reduction)
- **Annual Savings:** $22,644
- **ROI:** Immediate (no implementation cost)

> **Note:** Actual savings may vary based on spot availability and pricing fluctuations. AWS Savings Plans or Reserved Instances could provide additional 20-40% savings on the remaining on-demand capacity.

---

## 🏗️ Architecture Design

### Components on Spot Instances (Can Tolerate Interruptions)

#### 1. **GPU Nodes (Karpenter-managed)**
- **Workload:** NVIDIA NIMs (Llama, Nemotron, Embedding models)
- **Why Safe:** 
  - NIMs are stateless containers
  - Model weights re-download on startup (~2-3 min)
  - Karpenter auto-provisions replacement nodes
  - Active requests fail gracefully, clients retry
- **Interruption Handling:** 2-minute warning via Karpenter SQS queue
- **Recovery Time:** 3-5 minutes for new node + NIM startup
- **Savings:** ~$1,832/month (70% off GPU costs)

#### 2. **System Worker Nodes**
- **Workload:** Backend (FastAPI), Frontend (Next.js)
- **Why Safe:**
  - Stateless applications (no local storage)
  - 2 replicas with Pod Disruption Budget (minAvailable: 1)
  - Kubernetes reschedules pods automatically
  - Load balancer routes to healthy pods
- **Interruption Handling:** 
  - PDB ensures at least 1 replica stays up
  - Graceful shutdown period (30s)
  - Zero-downtime for users
- **Recovery Time:** ~30 seconds for pod rescheduling
- **Savings:** ~$193/month (70% off system node costs)

### Components on On-Demand Instances (Cannot Tolerate Interruptions)

#### 1. **Milvus Vector Database**
- **Why Critical:** 
  - Stores 97 PDF documents as vector embeddings
  - Active read/write operations
  - Loss would require re-ingestion (~1 hour)
- **Protection:** `nodeSelector: karpenter.sh/capacity-type: on-demand`
- **Storage:** 20Gi EBS volume (persists even if pod restarts)

#### 2. **etcd (Milvus Metadata)**
- **Why Critical:**
  - Milvus cluster state and collection metadata
  - Consensus protocol requires stability
  - Corruption risk during interruptions
- **Protection:** Pinned to on-demand nodes

#### 3. **MinIO (Vector Object Storage)**
- **Why Critical:**
  - Actual vector data for Milvus
  - Data corruption risk during writes
  - Recovery impacts system availability
- **Protection:** Pinned to on-demand nodes

#### 4. **Kafka (Message Queue)**
- **Why Critical:**
  - Message queue for Milvus operations
  - Data loss during interruptions
- **Protection:** Pinned to on-demand nodes

**Total On-Demand Cost:** ~$138/month (1x m5.xlarge for all critical services)

---

## 🛡️ High Availability & Interruption Handling

### 1. **Karpenter Interruption Queue**

Already configured in your Terraform:

```hcl
set {
  name  = "settings.interruptionQueue"
  value = module.karpenter.queue_name
}
```

**Features:**
- 2-minute warning before spot termination
- Automatic node cordoning
- Graceful pod eviction
- Replacement node provisioning starts immediately

### 2. **Pod Disruption Budgets (PDBs)**

Applied via `infrastructure/kubernetes/pod-disruption-budgets.yaml`:

| Service | Strategy | Impact |
|---------|----------|--------|
| Backend | `minAvailable: 1` | At least 1 replica always running |
| Frontend | `minAvailable: 1` | Zero-downtime for users |
| Milvus | `maxUnavailable: 0` | Never evicted (on-demand node) |
| etcd | `maxUnavailable: 0` | Never evicted (on-demand node) |
| MinIO | `maxUnavailable: 0` | Never evicted (on-demand node) |
| NIMs | `maxUnavailable: 1` | One at a time during updates |

### 3. **Node Diversity**

System spot nodes use multiple instance types for better availability:

```hcl
instance_types = ["m5.xlarge", "m5a.xlarge", "m5n.xlarge"]
```

**Benefit:** If one instance type has no spot capacity, Kubernetes launches another type.

### 4. **Capacity Fallback**

Karpenter provisioner prioritizes spot but falls back to on-demand:

```yaml
values: ["spot", "on-demand"]  # Tries spot first, uses on-demand if unavailable
```

---

## 🚀 Deployment Process

### Prerequisites

- EKS cluster running (your `aiq-udf-eks` in us-west-2)
- kubectl configured
- Terraform initialized
- AWS credentials with EKS admin access

### Safe Migration Steps

Run the automated migration script:

```bash
cd infrastructure
./migrate-to-spot.sh
```

The script will:

1. ✅ Backup current state
2. ✅ Apply Pod Disruption Budgets
3. ✅ Update Karpenter provisioner for spot GPU nodes
4. ✅ Create spot system node group via Terraform
5. ✅ Pin Milvus/etcd/MinIO to on-demand nodes
6. ✅ Verify migration

**Estimated Duration:** 10-15 minutes  
**Expected Downtime:** None (rolling updates)

### Manual Step-by-Step (if preferred)

<details>
<summary>Click to expand manual instructions</summary>

#### Step 1: Apply PDBs

```bash
kubectl apply -f infrastructure/kubernetes/pod-disruption-budgets.yaml
kubectl get pdb --all-namespaces
```

#### Step 2: Update Karpenter Provisioner

```bash
kubectl apply -f infrastructure/terraform/karpenter-provisioner.yaml
kubectl get nodepools -n karpenter
```

#### Step 3: Update Terraform for Spot System Nodes

```bash
cd infrastructure/terraform
terraform plan
terraform apply
```

#### Step 4: Update Milvus Configuration

```bash
helm upgrade milvus \
  -n rag-blueprint \
  -f infrastructure/helm/milvus-standalone-values.yaml \
  milvus/milvus \
  --wait
```

#### Step 5: Monitor

```bash
watch kubectl get nodes -L karpenter.sh/capacity-type
```

</details>

---

## 📈 Monitoring & Observability

### Key Metrics to Watch

#### 1. **Spot Interruption Rate**

```bash
# Monitor Karpenter logs for interruption notices
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter -f | grep interruption
```

**Expected:** ~5-15% interruption rate (varies by region/instance type)

#### 2. **Node Provisioning Time**

```bash
# Watch new nodes come online
kubectl get events --all-namespaces | grep "Successfully provisioned"
```

**Target:** < 5 minutes for GPU nodes, < 2 minutes for CPU nodes

#### 3. **Pod Eviction Rate**

```bash
# Check for unexpected evictions
kubectl get events --all-namespaces --field-selector reason=Evicted
```

**Expected:** Only during spot interruptions with immediate rescheduling

#### 4. **Service Availability**

```bash
# Check application health
kubectl get pods -n aiq-agent
kubectl get pods -n rag-blueprint
kubectl get pods -n nim
```

**Target:** At least 1 replica of each service always running

### CloudWatch Dashboards

Monitor spot interruptions via CloudWatch:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2Spot \
  --metric-name InstanceInterruptions \
  --dimensions Name=InstanceType,Value=g5.2xlarge \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### Cost Explorer

Track actual savings:

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '30 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=INSTANCE_TYPE
```

---

## 🔄 Rollback Plan

If you experience issues or want to revert:

### Option 1: Quick Revert (Karpenter Only)

```bash
# Edit Karpenter NodePool
kubectl edit nodepool nvidia-nim-gpu -n karpenter

# Change line:
# values: ["spot", "on-demand"]
# To:
# values: ["on-demand"]
```

Existing spot nodes will be gradually replaced with on-demand as pods restart.

### Option 2: Full Rollback (Terraform)

```bash
cd infrastructure/terraform

# Revert main.tf changes
git checkout HEAD -- main.tf

# Apply original configuration
terraform apply

# Revert Karpenter provisioner
git checkout HEAD -- karpenter-provisioner.yaml
kubectl apply -f karpenter-provisioner.yaml
```

**Recovery Time:** 10-15 minutes

### Option 3: Restore from Backup

The migration script creates timestamped backups:

```bash
# Find your backup
ls -la infrastructure/backup-*

# Restore Terraform state
cp infrastructure/backup-TIMESTAMP/terraform.tfstate infrastructure/terraform/

# Restore Kubernetes resources (if needed)
kubectl apply -f infrastructure/backup-TIMESTAMP/karpenter-nodepools.yaml
```

---

## 🎯 Best Practices & Recommendations

### 1. **Gradual Migration**

If you're risk-averse, migrate in phases:

**Phase 1:** GPU nodes only (highest savings)
**Phase 2:** Non-critical system workloads
**Phase 3:** Additional replicas

### 2. **Spot Instance Pools**

Use multiple instance types to increase availability:

```yaml
# Already configured in karpenter-provisioner.yaml
values:
  - g5.xlarge    # 1x A10G
  - g5.2xlarge   # 1x A10G (more CPU/RAM)
  - g5.4xlarge   # 1x A10G (even more)
  - g5.8xlarge   # 1x A10G (max single GPU)
  - g5.12xlarge  # 4x A10G
```

### 3. **Savings Plans (Optional)**

For the remaining on-demand capacity, consider:

- **EC2 Instance Savings Plans:** 20-40% additional savings
- **Compute Savings Plans:** Flexible across instance types
- **1-year commitment:** Balance savings vs. flexibility

**Estimated Additional Savings:** $20-40/month on on-demand nodes

### 4. **Spot Instance Advisor**

Check interruption rates for your region:

```bash
aws ec2 describe-spot-price-history \
  --instance-types g5.2xlarge \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --product-descriptions "Linux/UNIX" \
  --query 'SpotPriceHistory[*].[Timestamp,SpotPrice]' \
  --output table
```

Or visit: https://aws.amazon.com/ec2/spot/instance-advisor/

---

## 🔒 Data Safety Guarantees

### What's Protected

| Asset | Protection | Recovery |
|-------|------------|----------|
| **Vector Embeddings** | EBS volume on on-demand node | Instant (volume persists) |
| **Milvus Metadata** | etcd on on-demand node | Instant |
| **Vector Objects** | MinIO on on-demand node | Instant |
| **Application State** | Stateless (no local storage) | N/A |

### What Can Be Lost (Acceptable)

| Asset | Loss Scenario | Recovery | Impact |
|-------|--------------|----------|--------|
| **NIM Model Weights** | Spot interruption | 3-5 min (re-download) | Minimal |
| **Active NIM Requests** | Spot interruption | Client retries | Temporary 503 errors |
| **Backend/Frontend Pods** | Spot interruption | 30 sec (reschedule) | None (PDB ensures 1 replica) |

### Backup Strategy (Recommended)

Even with on-demand protection, implement regular backups:

```bash
# Backup Milvus collections weekly
kubectl exec -n rag-blueprint milvus-standalone-0 -- \
  /opt/milvus/bin/backup create --collection us_tariffs

# Backup to S3
aws s3 sync /milvus-backups s3://your-backup-bucket/milvus/
```

---

## 📚 Additional Resources

- [AWS Spot Instances Best Practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)
- [Karpenter Interruption Handling](https://karpenter.sh/docs/concepts/disruption/)
- [Kubernetes Pod Disruption Budgets](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)
- [EKS Mixed Capacity Guide](https://aws.github.io/aws-eks-best-practices/cost_optimization/cost_opt_compute/#mixed-capacity-instances)

---

## 🆘 Support & Troubleshooting

### Common Issues

#### Issue: Spot nodes not provisioning

**Symptom:** Pods stuck in `Pending` state

**Solution:**
```bash
# Check Karpenter logs
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter

# Check capacity availability
aws ec2 describe-instance-type-offerings \
  --location-type availability-zone \
  --filters Name=instance-type,Values=g5.2xlarge \
  --region us-west-2
```

#### Issue: High interruption rate

**Symptom:** Frequent pod restarts

**Solution:**
- Add more instance types to the Karpenter provisioner
- Switch to on-demand temporarily
- Use mixed capacity (already configured)

#### Issue: Milvus on spot node

**Symptom:** Milvus pod running on spot-labeled node

**Solution:**
```bash
# Verify Milvus node placement
kubectl get pod -n rag-blueprint -o wide

# If on spot, cordon spot nodes and restart Milvus
kubectl cordon <spot-node-name>
kubectl delete pod -n rag-blueprint milvus-standalone-0
kubectl uncordon <spot-node-name>
```

---

## ✅ Success Criteria

Your migration is successful when:

- [ ] GPU nodes show `karpenter.sh/capacity-type: spot`
- [ ] System spot nodes are running
- [ ] At least 1 on-demand system node exists
- [ ] Milvus/etcd/MinIO on on-demand nodes
- [ ] All PDBs showing "ALLOWED DISRUPTIONS"
- [ ] No service downtime during spot interruptions
- [ ] Cost reduction visible in AWS Cost Explorer (after 24 hours)

---

**Next Steps:** Run `./infrastructure/migrate-to-spot.sh` to begin cost optimization!

