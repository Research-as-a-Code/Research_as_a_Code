#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Ingest all data collections into NVIDIA RAG Blueprint
# This script:
# 1. Ingests Congress text documents → "congress" collection
# 2. Ingests Sustainability PDFs → "sustainability" collection
# 3. Tariffs are already in "us_tariffs" collection

set -e

echo "================================================================================"
echo "🗄️  Ingesting New Collections into NVIDIA RAG Blueprint"
echo "================================================================================"
echo ""
echo "Collections to be ingested:"
echo "  📜 congress       - 4747 congressional documents (.txt) - NEW"
echo "  🌱 sustainability - 79 sustainability PDFs - NEW"
echo ""
echo "Existing collection (will NOT be re-ingested):"
echo "  💰 us_tariffs     - Already ingested (138 tariff chapter PDFs) ✓"
echo ""
echo "⏱️  Estimated time: 1-2 hours for new collections only"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted"
    exit 1
fi

# Change to script directory
cd "$(dirname "$0")"

# Check if RAG service is accessible
echo ""
echo "📡 Checking RAG service connectivity..."
echo ""

# Try to find the RAG chain-server service
if kubectl get svc -n rag-blueprint chain-server &>/dev/null; then
    echo "✅ Found chain-server in rag-blueprint namespace"
    
    # Set up port forwarding to chain-server (RAG service)
    echo "🔌 Setting up port forwarding to RAG chain-server..."
    kubectl port-forward -n rag-blueprint svc/chain-server 8081:8081 &>/dev/null &
    PORT_FORWARD_PID=$!
    echo "   PID: $PORT_FORWARD_PID"
    
    # Wait for port forward to be ready
    echo "⏳ Waiting for port forward to be ready..."
    sleep 5
    
    export RAG_INGEST_URL="http://localhost:8081/v1"
else
    echo "❌ Cannot find chain-server in rag-blueprint namespace"
    echo "   Available services:"
    kubectl get svc -n rag-blueprint
    echo ""
    echo "   If chain-server is listed above, there may be a connectivity issue"
    exit 1
fi

# Verify connectivity
if ! curl -s http://localhost:8081/health &>/dev/null; then
    echo "❌ Cannot connect to http://localhost:8081"
    echo "   Port forwarding may have failed"
    kill $PORT_FORWARD_PID 2>/dev/null
    exit 1
fi

echo "✅ RAG service is accessible"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    kill $PORT_FORWARD_PID 2>/dev/null
    echo "✅ Port forwarding stopped"
}

trap cleanup EXIT

# ========================================
# 1. Ingest Congress Documents
# ========================================

echo "================================================================================"
echo "📜 Step 1: Ingesting Congress Documents"
echo "================================================================================"
echo ""

python3 ingest_congress_to_rag.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Congress documents ingested successfully"
else
    echo ""
    echo "❌ Congress ingestion failed"
    exit 1
fi

# ========================================
# 2. Ingest Sustainability PDFs
# ========================================

echo ""
echo "================================================================================"
echo "🌱 Step 2: Ingesting Sustainability PDFs"
echo "================================================================================"
echo ""

python3 ingest_sustainability_to_rag.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Sustainability PDFs ingested successfully"
else
    echo ""
    echo "❌ Sustainability ingestion failed"
    exit 1
fi

# ========================================
# Final Summary
# ========================================

echo ""
echo "================================================================================"
echo "🎉 New Collections Ingested Successfully!"
echo "================================================================================"
echo ""
echo "All available RAG collections:"
echo "  📜 congress       - Congressional documents (NEWLY INGESTED)"
echo "  🌱 sustainability - Sustainability research (NEWLY INGESTED)"
echo "  💰 us_tariffs     - US Customs tariff chapters (EXISTING)"
echo ""
echo "Test queries:"
echo ""
echo "Congress:"
echo "  Topic: voting rights legislation"
echo "  Collection: congress"
echo ""
echo "Sustainability:"
echo "  Topic: sustainable development goals"
echo "  Collection: sustainability"
echo ""
echo "Tariffs:"
echo "  Topic: tariff codes for food products"
echo "  Collection: us_tariffs"
echo ""
echo "================================================================================"

