# Deploy Fixes - Step by Step

**Status**: Changes are LOCAL only, NOT deployed yet!

---

## 🚨 Current Situation

The code fixes are on your local machine but NOT deployed to AWS:

```
Local (Your Computer) ✅ Fixed
    ↓
    ↓ NOT DEPLOYED YET!
    ↓
AWS EKS (Running) ❌ Still Old Code
```

---

## 🚀 Deploy Steps

### Step 1: Commit Changes

```bash
cd /home/csaba/repos/AIML/Research_as_a_Code

# Stage all changes
git add backend/main.py
git add frontend/app/layout.tsx
git add frontend/app/components/CopilotAgentDisplay.tsx
git add frontend/app/components/ResearchForm.tsx
git add frontend/app/contexts/CopilotResearchContext.tsx
git add infrastructure/kubernetes/agent-deployment.yaml

# Commit
git commit -m "Fix streaming: Add SSE keepalive, fix CopilotKit integration, increase ELB timeout"

# Optional: Push to remote
git push origin main
```

### Step 2: Deploy to EKS

```bash
cd infrastructure/kubernetes

# This will:
# 1. Build new Docker images with fixes
# 2. Push to ECR
# 3. Update Kubernetes deployment
# 4. Rolling restart pods
./deploy-agent.sh
```

**⏱️ This takes ~10-15 minutes**:
- Build backend: ~3 min
- Push backend: ~1 min
- Deploy backend: ~2 min
- Build frontend: ~5 min
- Push frontend: ~1 min
- Deploy frontend: ~2 min

---

## 🔍 Monitor Deployment

### Watch Pods Rolling Update:

```bash
# Watch pods restart
kubectl get pods -n aiq-agent -w

# You'll see:
# aiq-agent-backend-<old-id>   1/1   Running → Terminating
# aiq-agent-backend-<NEW-id>   0/1   ContainerCreating → Running
```

### Check New Pod Logs:

```bash
# Get new pod name
kubectl get pods -n aiq-agent | grep backend

# Check logs
kubectl logs -n aiq-agent aiq-agent-backend-<NEW-POD-ID> --tail=50
```

You should see:
```
INFO: ✅ AI-Q + UDR Agent initialized successfully
INFO: ✅ CopilotKit endpoint registered at /copilotkit
```

---

## 🧪 Test After Deployment

### 1. Check Backend Health:

```bash
curl http://af3615e06391145bc88022ac024a36ca-bd296660cda3522f.elb.us-west-2.amazonaws.com/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "AI-Q Research Assistant with UDR",
  "copilotkit_enabled": true
}
```

### 2. Submit Research Query:

1. Open: http://af2f4f77d44fb4b41bc00856345951e2-974749261.us-west-2.elb.amazonaws.com
2. Enter a topic: "What is the tariff for electronics?"
3. Click "Start Research"
4. **Watch for**: Real-time updates in "Agentic Flow" panel

### 3. Check Logs for Streaming:

```bash
# Watch logs in real-time
kubectl logs -n aiq-agent -f aiq-agent-backend-<POD-NAME>
```

You should now see:
```
INFO: Streaming research request: What is the tariff...
INFO: 🔄 Starting stream for thread_id=research-a1b2c3d4
... (keepalive messages every 15s)
INFO: ✅ Stream completed for thread_id=research-a1b2c3d4
INFO: 10.0.x.x:xxxxx - "POST /research/stream HTTP/1.1" 200 OK
```

### 4. Check Browser Network Tab:

1. Open DevTools → Network tab
2. Submit query
3. Find `/research/stream` request
4. Click → Response tab
5. Should see:
   ```
   : connected
   data: {"type":"update",...}
   : keepalive
   data: {"type":"update",...}
   ...
   ```

---

## ❌ If You Skip Deployment

The error will persist because:
- Backend: Old code without keepalive
- Frontend: Old code without proper handling
- ELB: Default 60s timeout
- Result: Still get `ERR_INCOMPLETE_CHUNKED_ENCODING`

---

## ✅ After Deployment

With fixes deployed:
- Backend: ✅ Sends keepalive every 15s
- Frontend: ✅ Handles keepalive properly
- ELB: ✅ 300s timeout annotation
- Result: ✅ Streaming works!

---

## 🚨 Alternative: Quick Test Locally

If you want to test before deploying:

```bash
# Terminal 1: Start backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev

# Open: http://localhost:3000
# Test with a simple query
```

This lets you verify the fixes work before deploying to production!

---

## 📊 Expected Results After Deploy

### Before (Current):
```
Submit query
  ↓
60 seconds pass
  ↓
❌ ERR_INCOMPLETE_CHUNKED_ENCODING
  ↓
No feedback, connection lost
```

### After (With Fixes):
```
Submit query
  ↓
See "connected" message
  ↓
Keepalive every 15s
  ↓
Real-time updates
  ↓
✅ Stream completes successfully
  ↓
Report displayed
```

---

## 🎯 Bottom Line

**YOU MUST DEPLOY THE FIXES!**

The code changes are only on your local machine. Run:

```bash
cd /home/csaba/repos/AIML/Research_as_a_Code
git add -A
git commit -m "Fix streaming timeout and CopilotKit integration"
cd infrastructure/kubernetes
./deploy-agent.sh
```

Then test again! 🚀

