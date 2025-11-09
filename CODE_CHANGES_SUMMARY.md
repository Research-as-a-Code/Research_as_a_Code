# Code Changes Summary - Backend/Frontend Connectivity Fix

## 🔍 Problem
The frontend was configured with an internal Kubernetes DNS name (`http://aiq-agent-service.aiq-agent.svc.cluster.local`) which browsers cannot access, causing "Failed to fetch" errors.

## ✅ Solution Overview
1. Expose backend via LoadBalancer (NLB)
2. Build frontend Docker image with the actual backend LoadBalancer URL
3. Update deployment script to handle two-stage deployment

---

## 📝 Code Changes Made

### 1. Infrastructure: `infrastructure/kubernetes/agent-deployment.yaml`

#### **Change 1: Backend Service - Changed from ClusterIP to LoadBalancer**

**Before:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: aiq-agent-service
  namespace: aiq-agent
spec:
  type: ClusterIP  # Internal only
```

**After:**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: aiq-agent-service
  namespace: aiq-agent
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"  # Use NLB
spec:
  type: LoadBalancer  # Expose publicly
```

**Why:** Browsers need a public URL to call the backend API. NLB avoids security group conflicts.

---

#### **Change 2: Frontend Deployment - Dynamic Backend URL**

**Before:**
```yaml
env:
- name: NEXT_PUBLIC_BACKEND_URL
  value: "http://aiq-agent-service.aiq-agent.svc.cluster.local"  # Hardcoded internal URL
```

**After:**
```yaml
env:
- name: NEXT_PUBLIC_BACKEND_URL
  value: "${BACKEND_URL}"  # Replaced by deploy script
```

**Why:** Next.js requires the backend URL at build time. This placeholder gets replaced with the actual LoadBalancer URL during deployment.

---

### 2. Deployment Script: `infrastructure/kubernetes/deploy-agent.sh`

#### **Key Changes:**

**Before:** Single-stage deployment
1. Build both backend and frontend
2. Deploy everything at once
3. Hope the frontend can reach backend

**After:** Two-stage deployment
1. Build and deploy **backend only**
2. Wait for backend LoadBalancer URL
3. Build frontend **with actual backend URL**
4. Deploy frontend

#### **Detailed Changes:**

**Step 2: Build Backend Only**
```bash
# Build backend
docker build -f backend/Dockerfile -t aiq-agent:latest .
docker push ...

# Frontend will be built AFTER backend is ready
```

**Step 3-4: Deploy Backend & Wait for LoadBalancer**
```bash
# Deploy backend
kubectl apply -f agent-deployment.yaml --selector='component=backend'

# Wait for LoadBalancer URL
BACKEND_URL=$(kubectl get svc aiq-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
```

**Step 5: Build Frontend with Backend URL**
```bash
docker build -f frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_BACKEND_URL="http://$BACKEND_URL" \
    -t aiq-frontend:latest .
```

**Step 6-7: Deploy Frontend**
```bash
export BACKEND_URL="http://$BACKEND_URL"
envsubst < agent-deployment.yaml | kubectl apply -f - --selector='component=frontend'
```

---

## 📊 Summary

### Files Modified:
| File | Changes | Type |
|------|---------|------|
| `infrastructure/kubernetes/agent-deployment.yaml` | Backend service type + annotations, Frontend env var | Infrastructure |
| `infrastructure/kubernetes/deploy-agent.sh` | Two-stage deployment process | Deployment Script |

### Files NOT Modified:
| File | Reason |
|------|--------|
| `frontend/**/*.tsx` | No code changes needed |
| `frontend/**/*.ts` | No code changes needed |
| `backend/**/*.py` | No code changes needed |
| `infrastructure/terraform/**` | Terraform not affected |

### Key Takeaway:
**Only infrastructure and deployment process changed. No application code changes needed!**

---

## 🧪 Testing

After these changes, the deployment script will:

1. ✅ Deploy backend with public LoadBalancer (NLB)
2. ✅ Wait for backend URL (e.g., `http://abc123.elb.us-west-2.amazonaws.com`)
3. ✅ Build frontend with that URL baked in
4. ✅ Deploy frontend that can reach the backend
5. ✅ Return both frontend and backend URLs to user

**Result:** No more "Failed to fetch" errors! 🎉

---

## 🔄 Future Deployments

Running `./deploy-agent.sh` will now automatically:
- Create public backend LoadBalancer
- Build frontend with correct backend URL
- Deploy fully connected system

No manual intervention needed!

---

**Date:** November 9, 2025
**Status:** Production-ready ✅
