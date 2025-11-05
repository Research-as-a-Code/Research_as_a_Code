#!/bin/bash
# Verify NVIDIA RAG Blueprint Deployment
# Comprehensive health checks for all RAG components

set -e

NAMESPACE="rag-blueprint"

echo "=========================================="
echo "🔍 NVIDIA RAG Blueprint - Health Check"
echo "=========================================="
echo ""

# Function to check pod status
check_pods() {
    local label=$1
    local name=$2
    
    echo "Checking $name..."
    
    if kubectl get pods -n $NAMESPACE -l $label &> /dev/null; then
        POD_COUNT=$(kubectl get pods -n $NAMESPACE -l $label --no-headers | wc -l)
        READY_COUNT=$(kubectl get pods -n $NAMESPACE -l $label --no-headers | grep "Running" | wc -l)
        
        if [ "$POD_COUNT" -eq 0 ]; then
            echo "  ❌ No pods found"
            return 1
        elif [ "$READY_COUNT" -eq "$POD_COUNT" ]; then
            echo "  ✅ $READY_COUNT/$POD_COUNT pods running"
            return 0
        else
            echo "  ⚠️  $READY_COUNT/$POD_COUNT pods running"
            kubectl get pods -n $NAMESPACE -l $label
            return 1
        fi
    else
        echo "  ❌ Not found"
        return 1
    fi
}

# Function to check service
check_service() {
    local svc_name=$1
    local port=$2
    
    echo "Checking $svc_name service..."
    
    if kubectl get svc -n $NAMESPACE $svc_name &> /dev/null; then
        SVC_IP=$(kubectl get svc -n $NAMESPACE $svc_name -o jsonpath='{.spec.clusterIP}')
        echo "  ✅ Service ready at $SVC_IP:$port"
        return 0
    else
        echo "  ❌ Service not found"
        return 1
    fi
}

# Function to test HTTP endpoint
test_endpoint() {
    local svc_name=$1
    local port=$2
    local path=$3
    local desc=$4
    
    echo "Testing $desc..."
    
    # Use kubectl port-forward in background
    kubectl port-forward -n $NAMESPACE svc/$svc_name $port:$port > /dev/null 2>&1 &
    PF_PID=$!
    
    # Wait for port-forward
    sleep 3
    
    # Test endpoint
    if curl -sf http://localhost:$port$path > /dev/null 2>&1; then
        echo "  ✅ Endpoint responding"
        kill $PF_PID 2>/dev/null || true
        return 0
    else
        echo "  ⚠️  Endpoint not responding (may still be starting)"
        kill $PF_PID 2>/dev/null || true
        return 1
    fi
}

echo "Step 1/5: Checking namespace..."
if kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "  ✅ Namespace '$NAMESPACE' exists"
else
    echo "  ❌ Namespace '$NAMESPACE' not found"
    echo ""
    echo "Please deploy the RAG Blueprint first:"
    echo "  cd infrastructure/helm"
    echo "  ./deploy-rag-blueprint.sh"
    exit 1
fi
echo ""

echo "Step 2/5: Checking Milvus Vector Database..."
check_pods "app.kubernetes.io/name=milvus" "Milvus"
check_service "milvus-standalone" "19530" || check_service "milvus" "19530"
echo ""

echo "Step 3/5: Checking RAG Query Server..."
check_pods "app=rag-query-server" "RAG Query Server"
check_service "rag-query-server" "8081"
echo ""

echo "Step 4/5: Checking RAG Ingest Server..."
check_pods "app=rag-ingest-server" "RAG Ingest Server"
check_service "rag-ingest-server" "8082"
echo ""

echo "Step 5/5: Testing API Endpoints (if services are ready)..."
if kubectl get svc -n $NAMESPACE rag-ingest-server &> /dev/null; then
    test_endpoint "rag-ingest-server" "8082" "/health" "Ingest Server Health"
fi

if kubectl get svc -n $NAMESPACE rag-query-server &> /dev/null; then
    test_endpoint "rag-query-server" "8081" "/health" "Query Server Health"
fi
echo ""

echo "=========================================="
echo "📊 Deployment Summary"
echo "=========================================="
echo ""

# Get all pods in namespace
echo "All pods in $NAMESPACE namespace:"
kubectl get pods -n $NAMESPACE -o wide
echo ""

echo "All services in $NAMESPACE namespace:"
kubectl get svc -n $NAMESPACE
echo ""

# Check for persistent volumes
echo "Persistent volumes:"
kubectl get pvc -n $NAMESPACE 2>/dev/null || echo "  No PVCs found"
echo ""

echo "=========================================="
echo "📝 Next Steps"
echo "=========================================="
echo ""

# Check if all critical services are up
MILVUS_OK=$(kubectl get pods -n $NAMESPACE -l app.kubernetes.io/name=milvus --no-headers 2>/dev/null | grep "Running" | wc -l)
QUERY_OK=$(kubectl get pods -n $NAMESPACE -l app=rag-query-server --no-headers 2>/dev/null | grep "Running" | wc -l)
INGEST_OK=$(kubectl get pods -n $NAMESPACE -l app=rag-ingest-server --no-headers 2>/dev/null | grep "Running" | wc -l)

if [ "$MILVUS_OK" -gt 0 ] && [ "$INGEST_OK" -gt 0 ]; then
    echo "✅ RAG Blueprint is operational!"
    echo ""
    echo "You can now ingest the tariff PDFs:"
    echo ""
    echo "  cd ../../scripts"
    echo "  ./setup_tariff_rag_enterprise.sh"
    echo ""
else
    echo "⚠️  Some components are not ready yet"
    echo ""
    echo "Wait a few minutes and run this check again:"
    echo "  ./verify-rag-deployment.sh"
    echo ""
    echo "To view logs:"
    echo "  kubectl logs -n $NAMESPACE -l app=rag-query-server -f"
    echo "  kubectl logs -n $NAMESPACE -l app=rag-ingest-server -f"
    echo "  kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=milvus -f"
    echo ""
fi

echo "=========================================="

