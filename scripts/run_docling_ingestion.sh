#!/usr/bin/env bash
#
# Master script to run Docling-powered ingestion for all collections
# Uses Kubernetes Jobs for fast, cluster-local processing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=========================================="
echo "🚀 Docling-Powered RAG Ingestion"
echo "=========================================="
echo ""
echo "This will:"
echo "  • Re-ingest us_tariffs with better extraction"
echo "  • Ingest congress collection"
echo "  • Ingest sustainability collection"
echo ""
echo "Using: Docling (IBM Research) for advanced PDF segmentation"
echo "Chunk size: 1000 chars (increased from 500)"
echo "Chunk overlap: 200 chars"
echo ""

# Deploy the ConfigMap (contains the Python script)
echo "📝 Deploying ingestion script as ConfigMap..."
kubectl apply -f "${PROJECT_ROOT}/k8s/tariffs-docling-ingestion-job.yaml" --dry-run=client -o yaml | \
  kubectl apply -f - 2>&1 | grep -v "Warning" || true

kubectl get configmap -n rag-blueprint tariffs-docling-ingest-script >/dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ ConfigMap deployed"
else
    echo "❌ Failed to deploy ConfigMap"
    exit 1
fi

echo ""
echo "=========================================="
echo "1️⃣  Tariffs Collection (Re-ingestion)"
echo "=========================================="
echo ""

# Clean up old job if exists
kubectl delete job -n rag-blueprint tariffs-docling-ingestion 2>/dev/null || true
sleep 2

echo "🚀 Starting tariffs ingestion job..."
kubectl apply -f "${PROJECT_ROOT}/k8s/tariffs-docling-ingestion-job.yaml"

echo "📊 Waiting for job to start..."
sleep 5

echo ""
echo "📋 Following logs (Ctrl+C to stop watching, job continues):"
kubectl logs -n rag-blueprint -f job/tariffs-docling-ingestion 2>/dev/null || \
    echo "Job starting up, logs not yet available..."

echo ""
echo "⏳ Waiting for tariffs job to complete..."
kubectl wait --for=condition=complete --timeout=60m -n rag-blueprint job/tariffs-docling-ingestion

echo "✅ Tariffs ingestion complete!"
echo ""

# Congress
echo "=========================================="
echo "2️⃣  Congress Collection"
echo "=========================================="
echo ""

kubectl delete job -n rag-blueprint congress-docling-ingestion 2>/dev/null || true
sleep 2

echo "🚀 Starting congress ingestion job..."
kubectl apply -f "${PROJECT_ROOT}/k8s/congress-docling-ingestion-job.yaml"

echo "📊 Waiting for job to start..."
sleep 5

echo ""
echo "📋 Following logs:"
kubectl logs -n rag-blueprint -f job/congress-docling-ingestion 2>/dev/null || \
    echo "Job starting up..."

echo ""
echo "⏳ Waiting for congress job to complete..."
kubectl wait --for=condition=complete --timeout=120m -n rag-blueprint job/congress-docling-ingestion

echo "✅ Congress ingestion complete!"
echo ""

# Sustainability
echo "=========================================="
echo "3️⃣  Sustainability Collection"
echo "=========================================="
echo ""

kubectl delete job -n rag-blueprint sustainability-docling-ingestion 2>/dev/null || true
sleep 2

echo "🚀 Starting sustainability ingestion job..."
kubectl apply -f "${PROJECT_ROOT}/k8s/sustainability-docling-ingestion-job.yaml"

echo "📊 Waiting for job to start..."
sleep 5

echo ""
echo "📋 Following logs:"
kubectl logs -n rag-blueprint -f job/sustainability-docling-ingestion 2>/dev/null || \
    echo "Job starting up..."

echo ""
echo "⏳ Waiting for sustainability job to complete..."
kubectl wait --for=condition=complete --timeout=60m -n rag-blueprint job/sustainability-docling-ingestion

echo "✅ Sustainability ingestion complete!"
echo ""

# Verify all collections
echo "=========================================="
echo "📊 Final Collection Statistics"
echo "=========================================="
echo ""

kubectl exec -n rag-blueprint deployment/milvus-standalone-standalone -- python3 -c "
from pymilvus import connections, Collection
connections.connect(host='milvus-standalone', port=19530)

collections = ['us_tariffs', 'congress', 'sustainability']
for coll_name in collections:
    try:
        coll = Collection(coll_name)
        print(f'{coll_name}: {coll.num_entities:,} chunks')
    except Exception as e:
        print(f'{coll_name}: Not found or error')
" 2>/dev/null

echo ""
echo "=========================================="
echo "✅ ALL COLLECTIONS INGESTED!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  • Test queries against new collections"
echo "  • Compare quality with old extraction"
echo "  • Clean up jobs: kubectl delete job -n rag-blueprint [job-name]"
echo ""

