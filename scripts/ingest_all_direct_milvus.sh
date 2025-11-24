#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

# Ingest congress and sustainability collections using direct Milvus access
# This uses the same method as the backend (pymilvus + embedding NIM)

set -e

echo "================================================================================"
echo "📥 Direct Milvus Ingestion - Congress + Sustainability"
echo "================================================================================"
echo ""
echo "This script will:"
echo "  1. Set up port-forwarding to Milvus and Embedding NIM"
echo "  2. Ingest 4,747 congressional documents → 'congress' collection"
echo "  3. Ingest 79 sustainability PDFs → 'sustainability' collection"
echo ""
echo "⏱️  Estimated time: 1-2 hours"
echo ""
echo "Note: us_tariffs collection is NOT touched (already exists)"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Aborted"
    exit 1
fi

# Change to script directory
cd "$(dirname "$0")"

# ========================================
# Setup Port Forwarding
# ========================================

echo ""
echo "================================================================================"
echo "🔌 Setting up port forwarding..."
echo "================================================================================"
echo ""

# Check if services exist
echo "Checking services..."
if ! kubectl get svc -n rag-blueprint milvus-standalone &>/dev/null; then
    echo "❌ milvus-standalone service not found"
    exit 1
fi

if ! kubectl get svc -n nim embedding-service &>/dev/null; then
    echo "❌ embedding-service not found"
    exit 1
fi

echo "✅ Services found"
echo ""

# Kill any existing port forwards
pkill -f "port-forward.*19530" 2>/dev/null || true
pkill -f "port-forward.*8000" 2>/dev/null || true
sleep 2

# Set up Milvus port forward
echo "🔌 Port-forwarding Milvus (19530)..."
kubectl port-forward -n rag-blueprint svc/milvus-standalone 19530:19530 &>/dev/null &
MILVUS_PID=$!
echo "   PID: $MILVUS_PID"

# Set up Embedding NIM port forward
echo "🔌 Port-forwarding Embedding NIM (8000)..."
kubectl port-forward -n nim svc/embedding-service 8000:8000 &>/dev/null &
EMBEDDING_PID=$!
echo "   PID: $EMBEDDING_PID"

# Wait for port forwards to be ready
echo ""
echo "⏳ Waiting for port forwards to establish..."
sleep 10

# Cleanup function
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    kill $MILVUS_PID 2>/dev/null || true
    kill $EMBEDDING_PID 2>/dev/null || true
    echo "✅ Port forwarding stopped"
}

trap cleanup EXIT INT TERM

# Verify connectivity
echo ""
echo "🔍 Testing connectivity..."

# Test Embedding NIM
if curl -s http://localhost:8000/v1/models &>/dev/null; then
    echo "✅ Embedding NIM accessible"
else
    echo "❌ Cannot connect to Embedding NIM on localhost:8000"
    echo "   Port forward may have failed"
    exit 1
fi

# Note: Milvus doesn't have HTTP health check, but we'll test it during ingestion

echo "✅ Services ready"
echo ""

# ========================================
# 1. Ingest Congress Documents
# ========================================

echo "================================================================================"
echo "📜 Step 1/2: Ingesting Congress Documents"
echo "================================================================================"
echo ""
echo "Collection: congress"
echo "Files: 4,747 .txt documents"
echo "Method: pymilvus + arctic-embed-l"
echo ""

../venv/bin/python ingest_via_pymilvus.py \
    congress \
    ../data/congress \
    --pattern '*.txt' \
    --milvus-host localhost \
    --embedding-url http://localhost:8000

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
echo "🌱 Step 2/2: Ingesting Sustainability PDFs"
echo "================================================================================"
echo ""
echo "Collection: sustainability"
echo "Files: 79 PDF documents"
echo "Method: pymilvus + arctic-embed-l"
echo ""

../venv/bin/python ingest_via_pymilvus.py \
    sustainability \
    ../data/sustainability \
    --pattern '*.pdf' \
    --milvus-host localhost \
    --embedding-url http://localhost:8000

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
echo "🎉 All Collections Ingested Successfully!"
echo "================================================================================"
echo ""
echo "Collections now available in Milvus:"
echo "  📜 congress       - Congressional documents (NEWLY INGESTED)"
echo "  🌱 sustainability - Sustainability research (NEWLY INGESTED)"
echo "  💰 us_tariffs     - US Customs tariffs (ALREADY EXISTS)"
echo ""
echo "Test queries:"
echo ""
echo "Congress:"
echo "  Topic: 'voting rights legislation'"
echo "  Collection: congress"
echo ""
echo "Sustainability:"
echo "  Topic: 'sustainable development goals'"
echo "  Collection: sustainability"
echo ""
echo "Tariffs:"
echo "  Topic: 'tariff codes for food products'"
echo "  Collection: us_tariffs"
echo ""
echo "================================================================================"

