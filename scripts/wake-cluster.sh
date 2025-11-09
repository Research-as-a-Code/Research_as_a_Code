#!/bin/bash
# Wake up cluster from sleep
# Scales deployments back up and waits for Karpenter to provision nodes

echo "☀️ Waking up cluster..."

echo ""
echo "Step 1: Scaling up AI agent..."
kubectl scale deployment aiq-agent-backend --replicas=2 -n aiq-agent
kubectl scale deployment aiq-agent-frontend --replicas=2 -n aiq-agent

echo ""
echo "Step 2: Scaling up NIMs..."
kubectl scale deployment llama-instruct-nim --replicas=1 -n nim
kubectl scale deployment embedding-nim --replicas=1 -n nim

echo ""
echo "Step 3: Waiting for Karpenter to provision GPU nodes (this may take 3-5 minutes)..."
echo "⏳ GPU nodes provisioning..."
for i in {1..60}; do
    GPU_NODES=$(kubectl get nodes -l karpenter.sh/nodepool --no-headers 2>/dev/null | wc -l)
    if [ "$GPU_NODES" -ge 2 ]; then
        echo "✅ GPU nodes ready!"
        break
    fi
    sleep 5
done

echo ""
echo "Step 4: Waiting for agent pods to be ready..."
kubectl wait --for=condition=ready pod -l app=aiq-agent -n aiq-agent --timeout=5m 2>/dev/null || echo "⏳ Agent pods still starting..."

echo ""
echo "Step 5: Waiting for NIMs to load models (this takes 5-10 minutes)..."
echo "⏳ NIMs are downloading models and building TensorRT engines..."

# Wait for NIM pods to be Running first
kubectl wait --for=condition=ready pod -l app=llama-instruct-nim -n nim --timeout=10m 2>/dev/null || true
kubectl wait --for=condition=ready pod -l app=embedding-nim -n nim --timeout=10m 2>/dev/null || true

# Wait for NIMs to be actually ready to serve requests
echo "⏳ Checking NIM readiness (this can take several minutes)..."
for i in {1..60}; do
    LLAMA_POD=$(kubectl get pods -n nim -l app=llama-instruct-nim -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    EMBED_POD=$(kubectl get pods -n nim -l app=embedding-nim -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    LLAMA_READY="no"
    EMBED_READY="no"
    
    if [ -n "$LLAMA_POD" ]; then
        LLAMA_HEALTH=$(kubectl exec -n nim "$LLAMA_POD" -- curl -s http://localhost:8000/v1/health/ready 2>/dev/null || echo "not ready")
        if echo "$LLAMA_HEALTH" | grep -q "ready"; then
            LLAMA_READY="yes"
        fi
    fi
    
    if [ -n "$EMBED_POD" ]; then
        EMBED_HEALTH=$(kubectl exec -n nim "$EMBED_POD" -- curl -s http://localhost:8000/v1/health/ready 2>/dev/null || echo "not ready")
        if echo "$EMBED_HEALTH" | grep -q "ready"; then
            EMBED_READY="yes"
        fi
    fi
    
    echo "[$i/60] Llama: $LLAMA_READY | Embedding: $EMBED_READY"
    
    if [ "$LLAMA_READY" = "yes" ] && [ "$EMBED_READY" = "yes" ]; then
        echo "✅ All NIMs are ready to serve requests!"
        break
    fi
    
    sleep 10
done

echo ""
echo "Step 6: Checking cluster status..."
kubectl get nodes
kubectl get pods -n aiq-agent
kubectl get pods -n nim

echo ""
echo "Step 7: Getting service URLs..."
FRONTEND_URL=$(kubectl get svc aiq-agent-frontend -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
BACKEND_URL=$(kubectl get svc aiq-agent-service -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)

echo ""
echo "=================================================="
echo "✅ Cluster is fully awake and ready!"
echo "=================================================="
echo ""
if [ -n "$FRONTEND_URL" ]; then
    echo "🌐 Frontend UI:      http://$FRONTEND_URL"
else
    echo "⏳ Frontend LoadBalancer still provisioning..."
fi
if [ -n "$BACKEND_URL" ]; then
    echo "🔧 Backend API:      http://$BACKEND_URL"
    echo "📚 API Docs:         http://$BACKEND_URL/docs"
else
    echo "⏳ Backend LoadBalancer still provisioning..."
fi
echo ""
echo "🎯 All services are ready to use!"
echo "   - NIMs have loaded models and are serving requests"
echo "   - Backend can connect to NIMs"
echo "   - Frontend can submit research queries"
echo "=================================================="

