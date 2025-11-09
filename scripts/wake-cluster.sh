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
kubectl scale deployment instruct-llm-nim --replicas=1 -n nim

echo ""
echo "Step 3: Waiting for Karpenter to provision nodes (this may take 3-5 minutes)..."
sleep 10
kubectl get nodes -w --timeout=5m &
WATCH_PID=$!

echo ""
echo "Step 4: Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=aiq-agent -n aiq-agent --timeout=5m 2>/dev/null || echo "⏳ Agent pods still starting..."
kubectl wait --for=condition=ready pod -l app=instruct-llm -n nim --timeout=10m 2>/dev/null || echo "⏳ NIM pods still starting (can take 5-10 min)..."

kill $WATCH_PID 2>/dev/null

echo ""
echo "Step 5: Checking cluster status..."
kubectl get nodes
kubectl get pods -n aiq-agent
kubectl get pods -n nim

echo ""
echo "Step 6: Getting service URLs..."
FRONTEND_URL=$(kubectl get svc aiq-agent-frontend -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
BACKEND_URL=$(kubectl get svc aiq-agent-service -n aiq-agent -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)

echo ""
echo "✅ Cluster is awake!"
echo ""
if [ -n "$FRONTEND_URL" ]; then
    echo "🌐 Frontend: http://$FRONTEND_URL"
else
    echo "⏳ Frontend LoadBalancer still provisioning..."
fi
if [ -n "$BACKEND_URL" ]; then
    echo "🔧 Backend:  http://$BACKEND_URL"
else
    echo "⏳ Backend LoadBalancer still provisioning..."
fi
echo ""
echo "Note: NIMs may take 5-10 more minutes to fully load models."

