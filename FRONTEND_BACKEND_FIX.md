# Frontend "Failed to fetch" Error - Solutions

## 🔍 Root Cause
The frontend was built with an internal Kubernetes backend URL (`http://aiq-agent-service.aiq-agent.svc.cluster.local`) that browsers cannot reach.

## ✅ SOLUTION 1: Local Testing with Port-Forward (IMMEDIATE)

**Terminal 1 - Backend:**
```bash
kubectl port-forward -n aiq-agent svc/aiq-agent-service 8000:80
```

**Terminal 2 - Frontend:**
```bash
kubectl port-forward -n aiq-agent svc/aiq-agent-frontend 3000:80
```

**Then access:**
- Frontend UI: http://localhost:3000
- Backend API Docs: http://localhost:8000/docs

**Note**: You'll need to update your browser's frontend code to call `http://localhost:8000` instead of the internal URL.

## ✅ SOLUTION 2: Rebuild Frontend with Correct Backend URL (RECOMMENDED)

### Step 1: Create a working backend LoadBalancer (clean approach)

```bash
# Delete and recreate the backend service as LoadBalancer
kubectl delete svc aiq-agent-service -n aiq-agent

cat <<YAML | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: aiq-agent-service
  namespace: aiq-agent
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"  # Use NLB to avoid security group issues
spec:
  type: LoadBalancer
  selector:
    app: aiq-agent
    component: backend
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
YAML

# Wait for LoadBalancer
kubectl wait --for=jsonpath='{.status.loadBalancer.ingress}' --timeout=300s svc/aiq-agent-service -n aiq-agent

# Get backend URL
BACKEND_URL=$(kubectl get svc -n aiq-agent aiq-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "Backend URL: http://$BACKEND_URL"
```

### Step 2: Rebuild frontend with new backend URL

```bash
cd infrastructure/kubernetes
export BACKEND_URL="http://<backend-loadbalancer-url>"
./deploy-agent.sh
```

## ✅ SOLUTION 3: Use NGINX Ingress (PRODUCTION-READY)

This gives you a single URL for both frontend and backend with path-based routing.

Example:
- `http://your-app.com/` → Frontend
- `http://your-app.com/api/` → Backend

(This requires additional setup which can be done if needed)

## 🚀 Quick Test

Test if backend is reachable:
```bash
kubectl exec -n aiq-agent deployment/aiq-agent-backend -- curl -s http://localhost:8000/health
```

Expected output: `{"status":"ok"}`
