#!/bin/bash

# sleep-cluster.sh
# Scales down GPU-intensive components to save costs when not in use
# Keeps Milvus and Frontend running as they're lightweight

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              💤 Putting Cluster to Sleep                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This will scale down GPU-intensive components:"
echo "  • NVIDIA Embedding NIM"
echo "  • NVIDIA Instruct LLM NIM"
echo "  • AIQ Agent Backend"
echo "  • Old Milvus components (if any)"
echo ""
echo "Keeping running (lightweight):"
echo "  • Milvus Standalone (vector database with your data)"
echo "  • Frontend"
echo ""

# Ask for confirmation unless --yes flag is passed
if [[ "$1" != "--yes" && "$1" != "-y" ]]; then
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Aborted"
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}🔄 Scaling down components...${NC}"
echo ""

# Scale down Embedding NIM
echo -n "1️⃣ Embedding NIM... "
kubectl scale deployment embedding-nim -n nim --replicas=0 2>/dev/null && echo -e "${GREEN}✅ Scaled to 0${NC}" || echo -e "${YELLOW}⚠️  Not found${NC}"

# Scale down Instruct LLM NIM
echo -n "2️⃣ Instruct LLM NIM... "
kubectl scale deployment llama-instruct-nim -n nim --replicas=0 2>/dev/null && echo -e "${GREEN}✅ Scaled to 0${NC}" || echo -e "${YELLOW}⚠️  Not found${NC}"

# Scale down Backend
echo -n "3️⃣ Backend... "
kubectl scale deployment aiq-agent-backend -n aiq-agent --replicas=0 2>/dev/null && echo -e "${GREEN}✅ Scaled to 0${NC}" || echo -e "${YELLOW}⚠️  Not found${NC}"

# Scale down OLD Milvus components (if they're somehow running)
echo -n "4️⃣ Old Milvus (cleanup)... "
SCALED_COUNT=0
kubectl scale statefulset milvus-pulsarv3-broker -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
kubectl scale statefulset milvus-pulsarv3-proxy -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
kubectl scale statefulset milvus-pulsarv3-recovery -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
kubectl scale statefulset milvus-pulsarv3-zookeeper -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
kubectl scale statefulset milvus-pulsarv3-bookie -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
kubectl scale deployment milvus-etcd -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
kubectl scale deployment milvus-minio -n rag-blueprint --replicas=0 2>/dev/null && ((SCALED_COUNT++)) || true
if [ $SCALED_COUNT -gt 0 ]; then
    echo -e "${GREEN}✅ Scaled down $SCALED_COUNT components${NC}"
else
    echo -e "${YELLOW}⚠️  Already scaled down${NC}"
fi

echo ""
echo -e "${GREEN}✅ Cluster is now in sleep mode${NC}"
echo ""
echo "💰 Cost savings: ~90% reduction in compute costs"
echo ""
echo "To wake up the cluster:"
echo "  bash /home/csaba/repos/AIML/Research_as_a_Code/infrastructure/scripts/wake-cluster.sh"
echo ""

exit 0

