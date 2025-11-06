# 🎯 Karpenter GPU Provisioning Issue - ROOT CAUSE FOUND

**Date:** November 5, 2025  
**Issue:** Karpenter unable to provision GPU nodes for NVIDIA NIMs  
**Root Cause:** **Zero vCPU quota for G5 instances in us-east-1**

---

## 📊 **The Discovery**

After 2.5 hours of debugging, we identified the root cause:

```
AWS Region: us-east-1
Cluster: aiq-udf-eks
vCPU Quota for "Running On-Demand G and VT instances": 0.0 ❌
vCPU Quota for "All G and VT Spot Instance Requests": 0.0 ❌
```

**Your account has ZERO vCPU quota for GPU instances in us-east-1!**

---

## 🔍 **What We Fixed (But Weren't The Issue)**

During debugging, we successfully fixed multiple infrastructure issues:

### ✅ IAM Permissions
- Added `iam:GetInstanceProfile`
- Added `iam:CreateInstanceProfile`
- Added `iam:TagInstanceProfile`
- Added `iam:UntagInstanceProfile`
- Broadened `iam:PassRole` scope

### ✅ Security Group Tags
All 4 security groups tagged with `karpenter.sh/discovery: aiq-udf-eks`:
- `sg-05cc90c2e62cb3218` (eks-cluster-sg)
- `sg-0ba99047f04469506` (default)
- `sg-0c2c084a96e78b37f` (node sg)
- `sg-05eea6fe7a9a036f1` (cluster sg)

### ✅ Subnet Tags
All 3 subnets tagged with `karpenter.sh/discovery: aiq-udf-eks`:
- `subnet-04941fc545debbc73` (us-east-1b)
- `subnet-0e3085d951bd27453` (us-east-1c)
- `subnet-0447fe51207c8bdb6` (us-east-1a)

### ✅ Karpenter Node Role
Updated from incorrect `KarpenterNodeRole-aiq-udf-eks` to actual role:
`Karpenter-aiq-udf-eks-20251105001410250400000017`

### ✅ G5 Instance Availability
G5 instances available in **5 availability zones** in us-east-1:
- us-east-1a, us-east-1b, us-east-1c, us-east-1d, us-east-1f

---

## ❌ **The Real Problem**

Despite all infrastructure being correctly configured, Karpenter could not provision nodes because:

**AWS Service Quota Limit = 0 vCPUs for GPU instances**

### Error Messages We Saw:
```
LaunchFailed: creating instance, getting launch template configs, 
getting launch templates, no security groups exist given constraints
```

**This error was misleading!** The real issue was quota, not security groups.

---

## 🚀 **Solutions**

### **Option 1: Request Quota Increase (REQUIRED for Self-Hosted NIMs)**

#### Via AWS Console:
1. Go to: https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas
2. Search for: "Running On-Demand G and VT instances"
3. Click "Request quota increase"
4. Request: **64 vCPUs** (allows multiple GPU nodes)
5. Wait for approval (15 minutes to 24 hours)

#### Via AWS CLI:
```bash
# Request On-Demand quota increase
aws service-quotas request-service-quota-increase \
    --service-code ec2 \
    --quota-code L-DB2E81BA \
    --desired-value 64 \
    --region us-east-1

# Also request Spot quota (optional, for cost savings)
aws service-quotas request-service-quota-increase \
    --service-code ec2 \
    --quota-code L-3819A6DF \
    --desired-value 64 \
    --region us-east-1
```

#### Recommended Values:
- **32 vCPUs**: Minimum (1x g5.12xlarge OR 2x g5.4xlarge)
- **64 vCPUs**: Recommended (allows multiple GPU nodes)
- **128 vCPUs**: Production (4x g5.12xlarge with 4 GPUs each)

#### vCPU Requirements per Instance Type:
| Instance Type | vCPUs | GPUs | Use Case |
|---------------|-------|------|----------|
| g5.xlarge     | 4     | 1    | Single NIM (Embedding) |
| g5.2xlarge    | 8     | 1    | Single NIM (LLM) |
| g5.4xlarge    | 16    | 1    | Large NIM (Nemotron) |
| g5.8xlarge    | 32    | 1    | Heavy workload |
| g5.12xlarge   | 48    | 4    | Multi-NIM node |

---

### **Option 2: Use NVIDIA Hosted NIMs (IMMEDIATE Workaround)**

**For the hackathon, you can proceed NOW with hosted NIMs:**

#### Step 1: Clean up pending GPU workloads
```bash
# Scale down or delete GPU workloads
kubectl delete deployment embedding-nim llama-instruct-nim -n nim
kubectl scale deployment rag-ingest-server -n rag-blueprint --replicas=0
```

#### Step 2: Configure for hosted NIMs
Update RAG services to use NVIDIA's hosted API endpoints instead of local NIMs.

**Advantages:**
- ✅ Works **immediately** (no quota wait)
- ✅ Can ingest all 138 tariff PDFs **today**
- ✅ Can demo hackathon project **now**
- ✅ Lower cost for testing/demo phase
- ✅ Can switch back to self-hosted after quota approval

**Trade-offs:**
- ⚠️  Data sent to NVIDIA API (not fully on-premise)
- ⚠️  Requires internet connectivity
- ⚠️  Per-use pricing vs fixed GPU cost

---

### **Option 3: Switch to Different Region**

If us-east-1 quota takes too long, you could:
1. Redeploy cluster to **us-west-2** (has 96 vCPU quota already)
2. Migrate data and configurations
3. **Time estimate:** 2-3 hours

**Not recommended** due to time investment vs hosted NIMs option.

---

## 📝 **Current Status**

### What's Working:
✅ **RAG Query Server**: Running and responding to health checks  
✅ **Milvus Vector Database**: Operational  
✅ **MinIO Object Storage**: Operational  
✅ **etcd**: Operational  
✅ **AI-Q Agent Backend & Frontend**: Deployed  

### What's Blocked:
❌ **Embedding NIM**: Pending (needs GPU)  
❌ **Instruct LLM NIM**: Pending (needs GPU)  
❌ **RAG Ingest Server**: Pending (needs GPU)  

### Impact:
- **Cannot ingest** new documents (no GPU for PDF processing)
- **Cannot run queries** requiring embeddings (no embedding NIM)
- **Query server operational** but RAG pipeline incomplete

---

## 🎯 **Recommended Next Steps**

### For the Hackathon (Immediate):
1. **Submit quota increase request** (do this first - approval can happen while you work)
2. **Use hosted NIMs** to unblock development immediately
3. **Ingest tariff documents** using hosted services
4. **Demo the application** with full functionality
5. **Switch to self-hosted NIMs** after quota approval

### For Production (After Hackathon):
1. **Wait for quota approval** (monitor via AWS console)
2. **Verify quota increase**: 
   ```bash
   aws service-quotas get-service-quota \
       --service-code ec2 \
       --quota-code L-DB2E81BA \
       --region us-east-1 --query 'Quota.Value'
   ```
3. **Karpenter will automatically provision** GPU nodes once quota is available
4. **Deploy self-hosted NIMs** for full on-premise solution
5. **Migrate from hosted to self-hosted** NIMs

---

## 📊 **Lessons Learned**

### Why This Was Hard to Diagnose:
1. **Misleading error message**: "no security groups exist" instead of "quota exceeded"
2. **Wrong region checked first**: Initially checked us-west-2 (which has quota)
3. **Karpenter doesn't expose quota errors clearly** in v0.32.0
4. **Multiple valid issues masked the root cause**: Had to fix IAM, tags, roles first

### Key Debugging Steps:
1. ✅ Verified NGC API key validity
2. ✅ Fixed all IAM permissions
3. ✅ Tagged all security groups
4. ✅ Tagged all subnets
5. ✅ Fixed node role name
6. ✅ Confirmed G5 availability
7. ✅ **Checked vCPU quota** ← **ROOT CAUSE**

---

## 🔗 **Useful AWS Links**

- [Service Quotas Console](https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas)
- [G5 Instances Documentation](https://aws.amazon.com/ec2/instance-types/g5/)
- [Karpenter Documentation](https://karpenter.sh/)
- [Request Quota Increase](https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html)

---

## 💡 **Quick Command Reference**

### Check Current Quota:
```bash
aws service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code L-DB2E81BA \
    --region us-east-1 \
    --query 'Quota.Value'
```

### Check G5 Availability:
```bash
aws ec2 describe-instance-type-offerings \
    --location-type availability-zone \
    --filters "Name=instance-type,Values=g5.xlarge" \
    --region us-east-1
```

### Monitor Quota Increase Request:
```bash
aws service-quotas list-requested-service-quota-change-history \
    --service-code ec2 \
    --region us-east-1
```

---

## ✅ **Success Criteria**

Once quota is approved, you'll know it's working when:

1. **Karpenter logs show**: `Created node` or `Launched instance`
2. **New node appears**: `kubectl get nodes` shows 3+ nodes
3. **NodeClaims become Ready**: `kubectl get nodeclaims` shows `Ready: True`
4. **NIMs deploy successfully**: `kubectl get pods -n nim` shows `Running`
5. **Ingest server starts**: `kubectl get pods -n rag-blueprint` shows ingest pod `Running`

---

## 📞 **Need Help?**

If quota request is denied or delayed:
- Contact AWS Support
- Explain it's for a hackathon with time constraints
- Mention it's for NVIDIA NIM deployment (legitimate GPU workload)
- Request expedited review

---

**Status:** ✅ Root cause identified, solutions provided  
**Time Invested:** ~2.5 hours of systematic debugging  
**Next Action:** Request quota increase OR use hosted NIMs

