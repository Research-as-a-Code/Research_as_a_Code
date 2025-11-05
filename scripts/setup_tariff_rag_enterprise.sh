#!/bin/bash
# Setup US Customs Tariff RAG using Enterprise NVIDIA RAG Blueprint
# This script handles both local and cluster-based ingestion

set -e

echo "=========================================="
echo "📚 US Customs Tariff RAG Setup"
echo "   Enterprise Edition with NVIDIA RAG Blueprint"
echo "=========================================="
echo ""

# Configuration
NAMESPACE="rag-blueprint"
COLLECTION_NAME="us_tariffs"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARIFF_DIR="$PROJECT_ROOT/data/tariffs"

# Check if we're running locally or in cluster
if [ -n "$KUBERNETES_SERVICE_HOST" ]; then
    # Running inside cluster
    INGEST_MODE="cluster"
    RAG_INGEST_URL="http://rag-ingest-server.$NAMESPACE.svc.cluster.local:8082"
    echo "🔧 Running in Kubernetes cluster"
else
    # Running locally - need port-forward
    INGEST_MODE="local"
    RAG_INGEST_URL="http://localhost:8082"
    echo "💻 Running locally - will set up port-forward"
fi

echo "   Collection: $COLLECTION_NAME"
echo "   RAG Service: $RAG_INGEST_URL"
echo ""

# Validate tariff directory
if [ ! -d "$TARIFF_DIR" ]; then
    echo "❌ Error: Tariff directory not found: $TARIFF_DIR"
    exit 1
fi

PDF_COUNT=$(find "$TARIFF_DIR" -name "*.pdf" | wc -l)
if [ "$PDF_COUNT" -eq 0 ]; then
    echo "❌ Error: No PDF files found in $TARIFF_DIR"
    exit 1
fi

echo "✅ Found $PDF_COUNT tariff PDF files"
echo ""

# Setup port-forward if running locally
if [ "$INGEST_MODE" = "local" ]; then
    echo "Step 1/3: Setting up port-forward to RAG ingest service..."
    
    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        echo "❌ Error: kubectl is not connected to a cluster"
        echo ""
        echo "To connect to your EKS cluster:"
        echo "  aws eks update-kubeconfig --region <region> --name <cluster-name>"
        echo ""
        exit 1
    fi
    
    # Check if RAG service exists
    if ! kubectl get svc -n $NAMESPACE rag-ingest-server &> /dev/null; then
        echo "❌ Error: RAG ingest service not found in namespace '$NAMESPACE'"
        echo ""
        echo "Please deploy the NVIDIA RAG Blueprint first:"
        echo "  cd infrastructure/helm"
        echo "  ./deploy-rag-blueprint.sh"
        echo ""
        exit 1
    fi
    
    # Kill any existing port-forward on 8082
    pkill -f "port-forward.*8082" || true
    sleep 2
    
    # Start port-forward in background
    echo "   Starting port-forward (8082:8082)..."
    kubectl port-forward -n $NAMESPACE svc/rag-ingest-server 8082:8082 > /tmp/rag-port-forward.log 2>&1 &
    PORT_FORWARD_PID=$!
    
    # Wait for port-forward to be ready
    echo "   Waiting for port-forward to be ready..."
    for i in {1..10}; do
        if curl -s http://localhost:8082/health > /dev/null 2>&1; then
            echo "   ✅ Port-forward ready"
            break
        fi
        sleep 1
    done
    
    # Trap to cleanup port-forward on exit
    trap "echo ''; echo 'Cleaning up port-forward...'; kill $PORT_FORWARD_PID 2>/dev/null || true" EXIT
else
    echo "Step 1/3: Verifying RAG service connectivity..."
fi
echo ""

# Install Python dependencies if needed
echo "Step 2/3: Checking Python dependencies..."
if ! python3 -c "import requests" 2>/dev/null; then
    echo "   Installing requests..."
    pip3 install --user requests
fi

echo "✅ Python dependencies ready"
echo ""

# Run the ingestion script
echo "Step 3/3: Starting PDF ingestion..."
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"
python3 scripts/ingest_tariffs_to_rag.py \
    --rag-ingest-url "$RAG_INGEST_URL" \
    --collection-name "$COLLECTION_NAME" \
    --tariff-dir "$TARIFF_DIR" \
    --test-query

echo ""
echo "=========================================="
echo "🎉 Tariff RAG Setup Complete!"
echo "=========================================="
echo ""
echo "Collection Details:"
echo "  Name: $COLLECTION_NAME"
echo "  Files Ingested: $PDF_COUNT PDFs"
echo "  RAG Service: $RAG_INGEST_URL"
echo ""
echo "Next Steps:"
echo ""
echo "1. Access your AI-Q Research Assistant UI"
echo ""
if [ "$INGEST_MODE" = "local" ]; then
    echo "2. The frontend should be at:"
    FRONTEND_URL=$(kubectl get svc -n aiq-agent aiq-agent-frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "<pending>")
    echo "   http://$FRONTEND_URL"
    echo ""
fi
echo "3. In the UI, enter these example queries:"
echo "   - \"What is the tariff for replacement batteries for a Raritan remote management card?\""
echo "   - \"What's the tariff of Reese's Pieces?\""
echo "   - \"Tariff of a replacement Roomba vacuum motherboard, used\""
echo ""
echo "4. Make sure to specify collection: us_tariffs"
echo ""
echo "=========================================="

