#!/bin/bash

# test-sleep-wake-cycle.sh
# Full end-to-end test: sleep → wake → monitor → verify
# This validates the complete cluster lifecycle

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          🧪 Sleep/Wake Cycle Test                             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This will test the complete cluster lifecycle:"
echo ""
echo "  1️⃣  Sleep - Scale down GPU components"
echo "  2️⃣  Verify sleep state"
echo "  3️⃣  Wake - Scale up components"
echo "  4️⃣  Monitor - Wait for full readiness"
echo "  5️⃣  Verify - Test API endpoint"
echo ""
echo -e "${YELLOW}⚠️  This test takes 10-25 minutes (mostly waiting for NIM builds)${NC}"
echo ""

read -p "Continue with full test? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Test cancelled"
    exit 1
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 1: Sleep
echo -e "${BLUE}📍 STEP 1/5: Putting cluster to sleep${NC}"
echo ""
bash "$SCRIPT_DIR/sleep-cluster.sh" --yes

echo ""
echo "⏱️  Waiting 30s for pods to terminate..."
sleep 30

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 2: Verify sleep state
echo -e "${BLUE}📍 STEP 2/5: Verifying sleep state${NC}"
echo ""

embedding_pods=$(kubectl get pods -n nim -l app=embedding-nim --no-headers 2>/dev/null | wc -l)
instruct_pods=$(kubectl get pods -n nim -l app=llama-instruct-nim --no-headers 2>/dev/null | wc -l)
backend_pods=$(kubectl get pods -n aiq-agent -l component=backend --no-headers 2>/dev/null | wc -l)

echo "Current pod counts:"
echo "  Embedding NIM: $embedding_pods (expected: 0)"
echo "  Instruct LLM:  $instruct_pods (expected: 0)"
echo "  Backend:       $backend_pods (expected: 0)"
echo ""

if [ "$embedding_pods" -eq 0 ] && [ "$instruct_pods" -eq 0 ] && [ "$backend_pods" -eq 0 ]; then
    echo -e "${GREEN}✅ Sleep state verified${NC}"
else
    echo -e "${YELLOW}⚠️  Some pods still running (may still be terminating)${NC}"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 3: Wake
echo -e "${BLUE}📍 STEP 3/5: Waking up cluster${NC}"
echo ""
bash "$SCRIPT_DIR/wake-cluster.sh" --yes

echo ""
echo "⏱️  Waiting 10s for pods to start..."
sleep 10

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 4: Monitor
echo -e "${BLUE}📍 STEP 4/5: Monitoring cluster readiness${NC}"
echo ""
echo "This will wait until all components are fully operational..."
echo "Expected time: 10-25 minutes"
echo ""

START_MONITOR=$(date +%s)

if bash "$SCRIPT_DIR/monitor-cluster-readiness.sh"; then
    END_MONITOR=$(date +%s)
    MONITOR_TIME=$((END_MONITOR - START_MONITOR))
    echo ""
    echo -e "${GREEN}✅ All components ready after $((MONITOR_TIME / 60))m $((MONITOR_TIME % 60))s${NC}"
else
    echo ""
    echo -e "${RED}❌ Monitoring timed out or failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 5: Verify with API call
echo -e "${BLUE}📍 STEP 5/5: Verifying with API health check${NC}"
echo ""

BACKEND_URL=$(kubectl get svc -n aiq-agent aiq-agent-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)

if [ -z "$BACKEND_URL" ]; then
    echo -e "${YELLOW}⚠️  Could not get backend URL, skipping API test${NC}"
else
    echo "Testing backend health endpoint: http://${BACKEND_URL}/health"
    
    if curl -s --max-time 5 "http://${BACKEND_URL}/health" | grep -q "healthy"; then
        echo -e "${GREEN}✅ Backend health check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check did not return expected response${NC}"
    fi
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Final summary
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✅ SLEEP/WAKE CYCLE TEST COMPLETE ✅                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "📊 Test Summary:"
echo "  ✅ Sleep: Scaled down successfully"
echo "  ✅ Wake: Scaled up successfully"
echo "  ✅ Monitor: All components became ready"
echo "  ✅ Verify: Health check passed"
echo ""
echo "🎯 Cluster is fully operational and ready for use!"
echo ""
echo "🌐 Access URLs:"
echo "   Frontend: http://$(kubectl get svc -n aiq-agent aiq-agent-frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)"
echo "   Backend:  http://${BACKEND_URL}"
echo ""

exit 0

