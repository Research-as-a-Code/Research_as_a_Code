#!/bin/bash

# monitor-cluster-readiness.sh
# Monitors all critical components and waits until everything is fully operational
# Especially useful after waking up the cluster, as NIMs need time to build TensorRT engines

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CHECK_INTERVAL=15  # seconds between checks
MAX_WAIT_TIME=1800  # 30 minutes max wait
START_TIME=$(date +%s)

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          🔍 Cluster Readiness Monitor                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "⏰ Started at: $(date)"
echo "⏱️  Max wait time: $((MAX_WAIT_TIME / 60)) minutes"
echo "🔄 Check interval: ${CHECK_INTERVAL}s"
echo ""

# Function to check elapsed time
check_timeout() {
    local current_time=$(date +%s)
    local elapsed=$((current_time - START_TIME))
    
    if [ $elapsed -gt $MAX_WAIT_TIME ]; then
        echo ""
        echo -e "${RED}❌ Timeout reached after $((elapsed / 60)) minutes${NC}"
        echo "Some components may still be initializing."
        echo "Check logs manually:"
        echo "  kubectl logs -n nim -l app=llama-instruct-nim"
        echo "  kubectl logs -n aiq-agent -l component=backend"
        exit 1
    fi
    
    echo -e "   ${BLUE}[Elapsed: $((elapsed / 60))m $((elapsed % 60))s]${NC}"
}

# Function to check pod status
check_pod_status() {
    local namespace=$1
    local selector=$2
    local component_name=$3
    
    echo -n "   Checking ${component_name}... "
    
    local ready_count=$(kubectl get pods -n "$namespace" -l "$selector" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    local total_count=$(kubectl get pods -n "$namespace" -l "$selector" --no-headers 2>/dev/null | wc -l)
    
    if [ "$ready_count" -eq "$total_count" ] && [ "$total_count" -gt 0 ]; then
        echo -e "${GREEN}✅ Ready ($ready_count/$total_count)${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ Not ready ($ready_count/$total_count)${NC}"
        return 1
    fi
}

# Function to check NIM readiness (checks if actually serving)
check_nim_ready() {
    local service_name=$1
    local namespace=$2
    local component_name=$3
    
    echo -n "   Testing ${component_name} connectivity... "
    
    # Try to query the models endpoint
    local result=$(kubectl run test-nim-monitor-$RANDOM --image=curlimages/curl:latest --rm -i --restart=Never --namespace=default -- sh -c "curl -s --max-time 3 http://${service_name}.${namespace}.svc.cluster.local:8000/v1/models 2>&1" 2>/dev/null || echo "FAILED")
    
    if echo "$result" | grep -q '"object":"list"'; then
        echo -e "${GREEN}✅ Serving requests${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ Not responding yet${NC}"
        
        # Check if it's still building
        local pod_name=$(kubectl get pods -n "$namespace" -l "app=${service_name%-service}" --no-headers 2>/dev/null | head -1 | awk '{print $1}')
        if [ -n "$pod_name" ]; then
            local last_log=$(kubectl logs -n "$namespace" "$pod_name" --tail=3 2>/dev/null | grep -E "Building|Compiling|startup|Uvicorn" | tail -1)
            if [ -n "$last_log" ]; then
                echo "      └─ Status: $(echo "$last_log" | cut -c1-70)..."
            fi
        fi
        return 1
    fi
}

# Function to check Milvus readiness
check_milvus_ready() {
    echo -n "   Checking Milvus... "
    
    local milvus_pods=$(kubectl get pods -n rag-blueprint 2>/dev/null | grep milvus | grep -c Running || echo "0")
    
    if [ "$milvus_pods" -ge 10 ]; then
        echo -e "${GREEN}✅ Running ($milvus_pods pods)${NC}"
        return 0
    else
        echo -e "${YELLOW}⏳ Not ready ($milvus_pods pods)${NC}"
        return 1
    fi
}

# Function to check backend readiness
check_backend_ready() {
    echo -n "   Checking Backend API... "
    
    local backend_pods=$(kubectl get pods -n aiq-agent -l component=backend --no-headers 2>/dev/null | grep -c Running || echo "0")
    
    if [ "$backend_pods" -eq 0 ]; then
        echo -e "${YELLOW}⏳ No running pods${NC}"
        return 1
    fi
    
    # Simplified check: if pods are Running and have been up for >30s, assume ready
    # This avoids slow log queries
    local first_pod=$(kubectl get pods -n aiq-agent -l component=backend --no-headers 2>/dev/null | head -1 | awk '{print $1}')
    
    if [ -n "$first_pod" ]; then
        # Check pod age (format: 10m, 1h, etc)
        local age=$(kubectl get pod -n aiq-agent "$first_pod" --no-headers 2>/dev/null | awk '{print $5}')
        
        # If age contains 'm' (minutes), 'h' (hours), or 'd' (days), it's been up long enough
        if [[ "$age" =~ [mhd] ]]; then
            echo -e "${GREEN}✅ Ready ($backend_pods pods, up $age)${NC}"
            return 0
        else
            # Pod just started (showing seconds), check logs quickly
            local startup_check=$(timeout 5 kubectl logs -n aiq-agent "$first_pod" 2>/dev/null | grep -m1 "Application startup complete" || echo "")
            if [ -n "$startup_check" ]; then
                echo -e "${GREEN}✅ Ready ($backend_pods pods)${NC}"
                return 0
            else
                echo -e "${YELLOW}⏳ Starting up ($backend_pods pods, age: $age)${NC}"
                return 1
            fi
        fi
    else
        echo -e "${YELLOW}⏳ Starting up ($backend_pods pods)${NC}"
        return 1
    fi
}

# Main monitoring loop
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

all_ready=false
iteration=0

while [ "$all_ready" = false ]; do
    iteration=$((iteration + 1))
    echo -e "${BLUE}🔄 Check #${iteration} - $(date +%H:%M:%S)${NC}"
    echo ""
    
    # Track readiness
    embedding_nim_ready=false
    instruct_nim_ready=false
    milvus_ready=false
    backend_ready=false
    frontend_ready=false
    
    # 1. Check Embedding NIM
    echo -e "${YELLOW}1️⃣ NVIDIA Embedding NIM${NC}"
    if check_pod_status "nim" "app=embedding-nim" "Embedding NIM pods"; then
        if check_nim_ready "embedding-service" "nim" "Embedding NIM"; then
            embedding_nim_ready=true
        fi
    fi
    echo ""
    
    # 2. Check Instruct LLM NIM
    echo -e "${YELLOW}2️⃣ NVIDIA Instruct LLM NIM${NC}"
    if check_pod_status "nim" "app=llama-instruct-nim" "Instruct LLM pods"; then
        if check_nim_ready "instruct-llm-service" "nim" "Instruct LLM"; then
            instruct_nim_ready=true
        fi
    fi
    echo ""
    
    # 3. Check Milvus
    echo -e "${YELLOW}3️⃣ Milvus Vector Database${NC}"
    if check_milvus_ready; then
        milvus_ready=true
    fi
    echo ""
    
    # 4. Check Backend
    echo -e "${YELLOW}4️⃣ AIQ Agent Backend${NC}"
    if check_backend_ready; then
        backend_ready=true
    fi
    echo ""
    
    # 5. Check Frontend
    echo -e "${YELLOW}5️⃣ Frontend${NC}"
    if check_pod_status "aiq-agent" "component=frontend" "Frontend"; then
        frontend_ready=true
    fi
    echo ""
    
    # Check if all components are ready
    if [ "$embedding_nim_ready" = true ] && \
       [ "$instruct_nim_ready" = true ] && \
       [ "$milvus_ready" = true ] && \
       [ "$backend_ready" = true ] && \
       [ "$frontend_ready" = true ]; then
        all_ready=true
        break
    fi
    
    # Show summary
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "📊 Summary:"
    echo "   Embedding NIM:    $([ "$embedding_nim_ready" = true ] && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⏳${NC}")"
    echo "   Instruct LLM:     $([ "$instruct_nim_ready" = true ] && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⏳${NC}")"
    echo "   Milvus:           $([ "$milvus_ready" = true ] && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⏳${NC}")"
    echo "   Backend:          $([ "$backend_ready" = true ] && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⏳${NC}")"
    echo "   Frontend:         $([ "$frontend_ready" = true ] && echo -e "${GREEN}✅${NC}" || echo -e "${YELLOW}⏳${NC}")"
    echo ""
    
    check_timeout
    
    if [ "$all_ready" = false ]; then
        echo "⏰ Next check in ${CHECK_INTERVAL}s..."
        echo ""
        sleep $CHECK_INTERVAL
    fi
done

# All components ready!
END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              🎉 ALL SYSTEMS READY! 🎉                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "✅ All components are fully operational!"
echo "⏱️  Total initialization time: $((TOTAL_TIME / 60))m $((TOTAL_TIME % 60))s"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "🌐 Access Points:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Get external URLs
FRONTEND_URL=$(kubectl get svc -n aiq-agent aiq-agent-frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
BACKEND_URL=$(kubectl get svc -n aiq-agent aiq-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)

if [ -n "$FRONTEND_URL" ]; then
    echo "   Frontend: http://${FRONTEND_URL}"
fi

if [ -n "$BACKEND_URL" ]; then
    echo "   Backend:  http://${BACKEND_URL}"
fi

echo ""
echo "🧪 Ready to test!"
echo ""
echo "Suggested test queries:"
echo "  Simple RAG:  \"What are the tariff rates for smartphones from China?\""
echo "  Dynamic UDF: \"Compare import costs for smartphones vs laptops from China\""
echo ""

exit 0

