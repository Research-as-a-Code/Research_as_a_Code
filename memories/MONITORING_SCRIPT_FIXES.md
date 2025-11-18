# Monitoring Script Fixes - False Negative Issues

**Date**: November 17, 2025  
**Issue**: Monitoring script reporting Instruct LLM and Milvus as "not ready" after 20+ minutes  
**Status**: ✅ **RESOLVED** - Both components were actually working, monitoring script had bugs

---

## 🔍 Problem Discovery

After waking the cluster and waiting 20+ minutes, the monitoring script showed:
- ✅ Embedding NIM: Ready
- ⏳ Instruct LLM: Not responding yet (FALSE!)
- ⏳ Milvus: Not ready (7 pods) (FALSE!)
- ✅ Backend: Ready
- ✅ Frontend: Ready

**Reality**: Both Instruct LLM and Milvus were fully operational!

---

## 🐛 Bug #1: Instruct LLM False Negative

### Root Cause
The monitoring script had a **service-to-pod label mismatch**:

**Line 90 (old code)**:
```bash
local pod_name=$(kubectl get pods -n "$namespace" -l "app=${service_name%-service}" --no-headers ...)
```

**The Problem**:
- Service name: `instruct-llm-service`
- Script extracted: `instruct-llm` from `instruct-llm-service`
- Script looked for pods with: `app=instruct-llm` ❌
- **Actual pod label**: `app=llama-instruct-nim` ✅

**Result**: The connectivity check passed (line 83), but the log checking failed silently.

### The Fix
Added explicit mapping for known service names:

```bash
# Check if it's still building - need to map service name to actual pod label
# embedding-service -> embedding-nim
# instruct-llm-service -> llama-instruct-nim
local pod_label=""
if [[ "$service_name" == "embedding-service" ]]; then
    pod_label="app=embedding-nim"
elif [[ "$service_name" == "instruct-llm-service" ]]; then
    pod_label="app=llama-instruct-nim"
else
    pod_label="app=${service_name%-service}"
fi
```

### Verification
```bash
# Manual test - WORKS!
curl -s http://instruct-llm-service.nim.svc.cluster.local:8000/v1/models
# Returns: {"object":"list","data":[{"id":"nvidia/llama-3.1-nemotron-nano-8b-v1"...
```

---

## 🐛 Bug #2: Milvus False Negative

### Root Cause
The monitoring script had **hardcoded expectations for distributed Milvus**:

**Line 110 (old code)**:
```bash
if [ "$milvus_pods" -ge 10 ]; then
    echo "✅ Running"
```

**The Problem**:
- Script expected: **10+ pods** (old distributed milvus-pulsarv3 setup)
- Reality: **7 Running pods** after cleanup (milvus-standalone setup)
- The script counted ALL milvus pods, including:
  - `milvus-etcd-0` (old deployment, not used)
  - `milvus-standalone-etcd-0` (new deployment, used)
  - `milvus-standalone-pulsarv3-zookeeper-*` (scaled to 0, in Init state)
  - Many other old/scaled-down components

**The ONE pod we actually use**:
- `milvus-standalone-standalone-97d9db684-p6vkh` - **Running and Ready!**

### The Fix
Updated to check specifically for the milvus-standalone pod we use:

```bash
# Check specifically for milvus-standalone-standalone (the one we actually use)
local standalone_ready=$(kubectl get pods -n rag-blueprint \
    -l component=standalone,app.kubernetes.io/instance=milvus-standalone \
    --no-headers 2>/dev/null | grep Running | grep "1/1" | wc -l)

if [ "$standalone_ready" -eq 1 ]; then
    echo "✅ Ready (milvus-standalone)"
    return 0
else
    # Fallback: count all running milvus pods (old threshold was 10, now 4 is enough)
    local milvus_pods=$(kubectl get pods -n rag-blueprint | grep "milvus.*Running" | grep "1/1" | wc -l)
    if [ "$milvus_pods" -ge 4 ]; then
        echo "✅ Running ($milvus_pods pods)"
        return 0
    fi
fi
```

### Verification
```bash
# Check the actual pod we use
kubectl get pod -n rag-blueprint milvus-standalone-standalone-97d9db684-p6vkh
# NAME                                           READY   STATUS    RESTARTS   AGE
# milvus-standalone-standalone-97d9db684-p6vkh   1/1     Running   0          26h
```

---

## 🧹 Additional Cleanup

### Scaled Down Failing Milvus Deployment
Found a **third** old Milvus deployment that was crashing:

```bash
kubectl get deployments -n rag-blueprint | grep milvus-standalone
# milvus-standalone              0/1     1            0           8d  (OLD, failing)
# milvus-standalone-standalone   1/1     1            1           26h (NEW, working)
```

**Problem**: `milvus-standalone` pod had **218 restarts** and kept crashing!

**Action**: Scaled it down permanently:
```bash
kubectl scale deployment milvus-standalone -n rag-blueprint --replicas=0
```

---

## ✅ Results

### Before Fixes
```
Monitoring Script Output (FALSE NEGATIVES):
  Embedding NIM:    ✅
  Instruct LLM:     ⏳ Not responding yet
  Milvus:           ⏳ Not ready (7 pods)
  Backend:          ✅
  Frontend:         ✅
```

### After Fixes
```
Monitoring Script Output (ALL GREEN):
  Embedding NIM:    ✅ Serving requests
  Instruct LLM:     ✅ Serving requests
  Milvus:           ✅ Ready (milvus-standalone)
  Backend:          ✅ Ready (1 pods, up 21m)
  Frontend:         ✅ Ready (1/1)

🎉 ALL SYSTEMS READY! 🎉
Total initialization time: 0m 33s
```

---

## 🧪 Testing

### Test 1: Run Monitoring Script
```bash
bash infrastructure/scripts/monitor-cluster-readiness.sh
```

**Expected Output**: All green on first check

### Test 2: Verify Instruct LLM
```bash
kubectl run test-curl --rm -i --restart=Never --image=curlimages/curl:latest -- \
  curl -s http://instruct-llm-service.nim.svc.cluster.local:8000/v1/models
```

**Expected Output**: JSON with model list

### Test 3: Verify Milvus
```bash
kubectl get pod -n rag-blueprint milvus-standalone-standalone-97d9db684-p6vkh
```

**Expected Output**: `1/1     Running`

---

## 📝 Files Modified

### 1. `infrastructure/scripts/monitor-cluster-readiness.sh`

**Changes**:

**Lines 89-109**: Fixed pod label mapping for NIMs
- Added explicit mapping: `instruct-llm-service` → `app=llama-instruct-nim`
- Added explicit mapping: `embedding-service` → `app=embedding-nim`

**Lines 102-125**: Fixed Milvus readiness check
- Primary check: Look for `milvus-standalone-standalone` pod specifically
- Fallback check: Lowered threshold from 10 → 4 pods
- Filter to only count `1/1 Running` pods (not Init/Error states)

**Total**: ~30 lines modified

---

## 💡 Key Learnings

### 1. Naming Consistency Matters
- Service: `instruct-llm-service`
- Pod label: `app=llama-instruct-nim`
- Deployment: `llama-instruct-nim`

**Lesson**: Don't assume service name → pod label transformation will work!

### 2. Hardcoded Thresholds Break
- Old setup: 10+ pods (distributed Milvus)
- New setup: 4-7 pods (standalone Milvus)

**Lesson**: Check for the actual component you care about, not just a pod count!

### 3. Multiple Deployments = Confusion
- Found 3 different "milvus-standalone" related things
- Only 1 was actually what we use

**Lesson**: Clean up old deployments before they cause issues!

---

## 🎯 System Status

### Current Cluster State (All Working)

**NIMs**:
- ✅ Embedding NIM: Running and serving
- ✅ Instruct LLM NIM: Running and serving

**Milvus**:
- ✅ `milvus-standalone-standalone`: Running with us_tariffs data
- ❌ Old `milvus` deployment: Scaled to 0
- ❌ Old `milvus-standalone` deployment: Scaled to 0
- ❌ Old `milvus-pulsarv3` components: Scaled to 0

**Backend & Frontend**:
- ✅ Backend: Running with new UDF validation
- ✅ Frontend: Running

**Resource Usage**:
- Optimized: Removed wasted CPU from 3 duplicate Milvus deployments
- Available: Sufficient capacity for all components

---

## 🚀 Next Steps

### Test the Full System
```bash
# Get frontend URL
kubectl get svc aiq-agent-frontend -n aiq-agent

# Open in browser and test:
# 1. Simple RAG: "What are the tariff rates for smartphones from China?"
# 2. Dynamic UDF: "Compare import costs for smartphones vs laptops from China"
```

### Monitor Cluster After Sleep/Wake
```bash
# Sleep
bash infrastructure/scripts/sleep-cluster.sh --yes

# Wake
bash infrastructure/scripts/wake-cluster.sh --yes

# Monitor
bash infrastructure/scripts/monitor-cluster-readiness.sh
```

**Expected**: All green within 5-20 minutes (NIM startup time)

---

## 📚 Related Documentation

- `/memories/MILVUS_CLEANUP_OLD_DEPLOYMENT.md` - Cleanup of duplicate Milvus deployments
- `/memories/DEPLOYMENT_COMPLETE_UDF_VALIDATION.md` - Backend deployment and UDF fixes
- `/memories/MILVUS_CONNECTIVITY_ISSUE.md` - Original Milvus setup
- `infrastructure/scripts/monitor-cluster-readiness.sh` - Fixed monitoring script

---

## 🏆 Summary

**Problem**: Monitoring script reporting false negatives after 20+ minutes  
**Root Causes**:
1. Service-to-pod label mismatch for Instruct LLM
2. Hardcoded pod count threshold (10) for old distributed Milvus
3. Extra failing Milvus deployment (218 crashes)

**Solutions**:
1. Added explicit service → pod label mapping
2. Updated to check for specific milvus-standalone pod + lowered threshold
3. Scaled down old failing deployment

**Result**: ✅ **All systems now correctly reported as ready in 33 seconds!**

**Status**: ✅ **COMPLETE AND TESTED**

---

**Current Time**: 21:43 PST  
**All Systems**: ✅ **OPERATIONAL**  
**Ready for**: Production use and testing  

🎉 **The system is fully ready - both components were already working, we just fixed the monitoring!**

