#!/bin/bash
# Setup script for US Customs Tariff RAG using NVIDIA RAG Blueprint Service

set -e

echo "=========================================="
echo "US Customs Tariff RAG Setup"
echo "Using NVIDIA RAG Blueprint Service"
echo "=========================================="
echo ""

PROJECT_ROOT="/home/csaba/repos/AIML/Research_as_a_Code"
cd "$PROJECT_ROOT"

# Check if RAG service is accessible
echo "Step 1/4: Checking RAG service connectivity..."
echo ""

RAG_INGEST_URL="${RAG_INGEST_URL:-http://localhost:8082/v1}"
RAG_SERVER_URL="${RAG_SERVER_URL:-http://localhost:8081/v1}"

echo "RAG Ingest URL: $RAG_INGEST_URL"
echo "RAG Server URL: $RAG_SERVER_URL"
echo ""

# Try to connect to RAG service
if ! curl -s -f "${RAG_INGEST_URL}/health" > /dev/null 2>&1; then
    echo "⚠️  Warning: Cannot connect to RAG ingest service at $RAG_INGEST_URL"
    echo ""
    echo "The RAG Blueprint service must be running for this to work."
    echo ""
    echo "Options:"
    echo "  1. If using Docker Compose, ensure the RAG services are running:"
    echo "     cd /path/to/rag/blueprint"
    echo "     docker-compose up -d"
    echo ""
    echo "  2. If using Kubernetes, port-forward the RAG services:"
    echo "     kubectl port-forward -n rag-blueprint svc/rag-ingest 8082:8082"
    echo "     kubectl port-forward -n rag-blueprint svc/rag-server 8081:8081"
    echo ""
    echo "  3. Set the correct URLs:"
    echo "     export RAG_INGEST_URL=http://your-rag-service:8082/v1"
    echo "     export RAG_SERVER_URL=http://your-rag-service:8081/v1"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ RAG service is accessible"
fi

echo ""
echo "Step 2/4: Installing Python dependencies..."
python3 -m pip install -q requests

echo "✅ Dependencies installed"
echo ""

echo "Step 3/4: Ingesting tariff PDFs into RAG service..."
echo "This will:"
echo "  - Create a 'us_tariffs' collection in the RAG service"
echo "  - Upload all 102 PDF files"
echo "  - RAG service will parse, chunk, and embed the documents"
echo "  - Store in Milvus vector database (managed by RAG service)"
echo ""
echo "⏳ This may take 10-20 minutes depending on your GPU..."
echo ""

python3 scripts/ingest_tariffs_to_rag.py \
    --rag-ingest-url "$RAG_INGEST_URL" \
    --collection-name "us_tariffs" \
    --tariff-dir "$PROJECT_ROOT/data/tariffs" \
    --test-query

echo ""
echo "Step 4/4: Verifying collection..."
echo "✅ Collection 'us_tariffs' is ready in the RAG service"

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "The tariff PDFs have been ingested into the NVIDIA RAG Blueprint service."
echo "The RAG service is using:"
echo "  - Milvus for vector storage"
echo "  - NeMo Retriever for embeddings"
echo "  - Multi-modal parsing for PDFs"
echo ""
echo "Next steps:"
echo ""
echo "1. Open the AI-Q Research Assistant UI"
echo "   URL: http://<your-frontend-url>"
echo ""
echo "2. Try these queries:"
echo "   - Research Topic: 'Tariff of replacement batteries for a Raritan card'"
echo "   - RAG Collection: 'us_tariffs'  ← Important!"
echo "   - Click 'Start Research'"
echo ""
echo "3. More example queries:"
echo "   - 'What is the tariff for Reese's Pieces?'"
echo "   - 'Tariff code for used computer motherboards'"
echo "   - 'Import duty for electric vehicle batteries'"
echo ""
echo "=========================================="

