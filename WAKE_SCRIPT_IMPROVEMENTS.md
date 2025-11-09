# Wake Script Improvements

**Date**: November 9, 2025  
**Status**: ✅ **FIXED** - Fully automated wake-up process

---

## 🐛 Bugs Fixed in `wake-cluster.sh`:

### 1. **Wrong Deployment Names**
**Problem**: Script tried to scale `instruct-llm-nim` (doesn't exist)  
**Fix**: Changed to correct names:
- ✅ `llama-instruct-nim`
- ✅ `embedding-nim`

### 2. **Missing Embedding NIM**
**Problem**: Script only scaled up one NIM (Llama), missing embedding service  
**Fix**: Now scales up both NIMs

### 3. **No GPU Node Waiting**
**Problem**: Script didn't wait for Karpenter to provision GPU nodes  
**Fix**: Added proper waiting loop for GPU nodes to be ready

### 4. **No NIM Readiness Check**
**Problem**: Script exited before NIMs were ready to serve requests  
**Fix**: Added health check polling:
- Waits for pods to be Running
- Polls `/v1/health/ready` endpoint
- Confirms both NIMs are serving requests

---

## ✅ New Behavior:

### Before (Broken):
```bash
./scripts/wake-cluster.sh
# ❌ NIMs didn't scale up (wrong name)
# ❌ Script exited before services ready
# ❌ Manual intervention required
# ⏳ 5-10 minutes of manual waiting/debugging
```

### After (Fixed):
```bash
./scripts/wake-cluster.sh
# ✅ Scales up all deployments correctly
# ✅ Waits for GPU nodes (3-5 min)
# ✅ Waits for pods to start (2-3 min)
# ✅ Waits for NIMs to load models (5-10 min)
# ✅ Verifies NIMs are serving requests
# ✅ Shows "ready to use" when complete
# 🎉 Zero manual intervention needed!
```

---

## 📊 Timeline Breakdown:

| Phase | Time | Status Display |
|-------|------|----------------|
| Scale up deployments | ~5s | ✅ Immediate |
| GPU nodes provisioning | 3-5 min | ⏳ Progress updates |
| Pods starting | 2-3 min | ⏳ Pod status |
| NIMs loading models | 5-10 min | ⏳ [X/60] Llama: no \| Embedding: no |
| **Total** | **~10-15 min** | ✅ All services ready! |

---

## 🔍 What the Script Now Checks:

1. **Deployment Scaling**
   ```bash
   kubectl scale deployment llama-instruct-nim --replicas=1 -n nim
   kubectl scale deployment embedding-nim --replicas=1 -n nim
   ```

2. **GPU Node Readiness**
   ```bash
   # Polls until 2+ GPU nodes are ready
   kubectl get nodes -l karpenter.sh/nodepool
   ```

3. **NIM Health Endpoints**
   ```bash
   # Polls until both return {"message":"Service is ready."}
   curl http://localhost:8000/v1/health/ready
   ```

4. **LoadBalancer URLs**
   ```bash
   # Displays frontend and backend URLs when ready
   kubectl get svc -n aiq-agent
   ```

---

## 🎯 Next Time You Wake the Cluster:

### All you need to do:
```bash
cd /home/csaba/repos/AIML/Research_as_a_Code
./scripts/wake-cluster.sh
```

### What happens automatically:
1. ✅ All deployments scaled up
2. ✅ Karpenter provisions GPU nodes
3. ✅ NIMs download models
4. ✅ NIMs build TensorRT engines
5. ✅ Health checks confirm readiness
6. ✅ URLs displayed

### When script completes:
- 🎉 **System is 100% ready to use**
- 🌐 Frontend accepts queries immediately
- 🔧 Backend can connect to NIMs
- 🧠 NIMs are serving requests

**No more manual debugging or waiting!** 🚀

---

## 📝 Other Fixes Today:

1. ✅ **Frontend footer** - Updated model names to Nemotron-Nano-8B
2. ✅ **Deploy script** - Fixed double `http://` prefix in output
3. ✅ **Documentation** - Updated `CLUSTER_SLEEP_STATUS.md`

---

## 🔗 Related Files:

- Wake script: `./scripts/wake-cluster.sh`
- Sleep script: `./scripts/sleep-cluster.sh`
- Status doc: `./CLUSTER_SLEEP_STATUS.md`

---

**Ready for tomorrow! 🌟**

