#!/bin/bash

# wake-cluster.sh
# Scales up GPU-intensive components after sleep
# Note: NIMs will need 5-20 minutes to build TensorRT engines

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              ⏰ Waking Up Cluster                              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "This will scale up GPU-intensive components:"
echo "  • NVIDIA Embedding NIM"
echo "  • NVIDIA Instruct LLM NIM"
echo "  • AIQ Agent Backend"
echo ""
echo -e "${YELLOW}⚠️  Note: NIMs need 5-20 minutes to build TensorRT engines${NC}"
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
echo -e "${YELLOW}🔄 Scaling up components...${NC}"
echo ""

# Scale up Embedding NIM
echo -n "1️⃣ Embedding NIM... "
kubectl scale deployment embedding-nim -n nim --replicas=1 2>/dev/null && echo -e "${GREEN}✅ Scaled to 1${NC}" || echo -e "${YELLOW}⚠️  Not found${NC}"

# Scale up Instruct LLM NIM
echo -n "2️⃣ Instruct LLM NIM... "
kubectl scale deployment llama-instruct-nim -n nim --replicas=1 2>/dev/null && echo -e "${GREEN}✅ Scaled to 1${NC}" || echo -e "${YELLOW}⚠️  Not found${NC}"

# Scale up Backend
echo -n "3️⃣ Backend... "
kubectl scale deployment aiq-agent-backend -n aiq-agent --replicas=2 2>/dev/null && echo -e "${GREEN}✅ Scaled to 2${NC}" || echo -e "${YELLOW}⚠️  Not found${NC}"

echo ""
echo -e "${GREEN}✅ Wake up initiated${NC}"
echo ""
echo "⏱️  Components are starting up..."
echo "   • Backend: ~30s"
echo "   • Embedding NIM: ~2-5 minutes"
echo "   • Instruct LLM NIM: ~5-20 minutes (TensorRT build)"
echo ""
echo "💡 To monitor readiness and wait for completion:"
echo "   bash /home/csaba/repos/AIML/Research_as_a_Code/infrastructure/scripts/monitor-cluster-readiness.sh"
echo ""

exit 0

