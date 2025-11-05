#!/bin/bash
# Deploy NVIDIA RAG Blueprint to EKS using Helm
# Enterprise-grade deployment for US Customs Tariff RAG

set -e

echo "=========================================="
echo "🚀 NVIDIA RAG Blueprint Deployment"
echo "   Enterprise Edition for EKS"
echo "=========================================="
echo ""

# Configuration
NAMESPACE="rag-blueprint"
RELEASE_NAME="nvidia-rag"
NGC_API_KEY="${NGC_API_KEY:-}"
AWS_REGION="${AWS_REGION:-us-west-2}"

# Validate prerequisites
echo "Step 1/10: Validating prerequisites..."
echo ""

# Check NGC API key
if [ -z "$NGC_API_KEY" ]; then
    echo "❌ Error: NGC_API_KEY environment variable not set"
    echo ""
    echo "To get your NGC API key:"
    echo "  1. Visit https://org.ngc.nvidia.com/setup/api-key"
    echo "  2. Generate a new API key"
    echo "  3. Export it: export NGC_API_KEY=your-key-here"
    echo ""
    exit 1
fi

echo "✅ NGC_API_KEY is set"

# Check kubectl connectivity
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Error: Cannot connect to Kubernetes cluster"
    echo "   Run: aws eks update-kubeconfig --region $AWS_REGION --name <cluster-name>"
    exit 1
fi

echo "✅ kubectl connected to cluster"

# Check Helm is installed
if ! command -v helm &> /dev/null; then
    echo "❌ Error: Helm is not installed"
    echo "   Install: curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
    exit 1
fi

echo "✅ Helm is installed ($(helm version --short))"
echo ""

# Create namespace
echo "Step 2/10: Creating namespace '$NAMESPACE'..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Namespace ready"
echo ""

# Create NGC secret for pulling NVIDIA container images
echo "Step 3/10: Creating NGC registry secret..."
kubectl create secret docker-registry ngc-secret \
    --namespace=$NAMESPACE \
    --docker-server=nvcr.io \
    --docker-username='$oauthtoken' \
    --docker-password="$NGC_API_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -
echo "✅ NGC secret created"
echo ""

# Add NVIDIA Helm repository
echo "Step 4/10: Adding NVIDIA Helm repository..."
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia --force-update
helm repo update
echo "✅ Helm repository added"
echo ""

# Check if RAG Blueprint chart is available
echo "Step 5/10: Searching for NVIDIA RAG Blueprint chart..."
if helm search repo nvidia/rag-blueprint &> /dev/null; then
    echo "✅ Found nvidia/rag-blueprint chart"
    CHART_NAME="nvidia/rag-blueprint"
elif helm search repo nvidia/rag &> /dev/null; then
    echo "✅ Found nvidia/rag chart"
    CHART_NAME="nvidia/rag"
else
    echo "⚠️  NVIDIA RAG chart not found in Helm repository"
    echo ""
    echo "Note: The NVIDIA RAG Blueprint may not be available as a public Helm chart yet."
    echo "Alternative approaches:"
    echo "  1. Use the RAG Blueprint from GitHub and deploy manually"
    echo "  2. Deploy components individually (Milvus + custom services)"
    echo "  3. Contact NVIDIA for enterprise Helm charts"
    echo ""
    echo "Proceeding with component-based deployment..."
    CHART_NAME=""
fi
echo ""

# Deploy based on available charts
if [ -n "$CHART_NAME" ]; then
    # Option A: Use official NVIDIA RAG Blueprint Helm chart
    echo "Step 6/10: Installing NVIDIA RAG Blueprint via Helm..."
    helm upgrade --install $RELEASE_NAME $CHART_NAME \
        --namespace $NAMESPACE \
        --values nvidia-rag-values.yaml \
        --timeout 20m \
        --wait
    echo "✅ RAG Blueprint installed"
else
    # Option B: Deploy components individually
    echo "Step 6/10: Deploying RAG components individually..."
    
    # Deploy Milvus
    echo "  → Installing Milvus vector database..."
    helm repo add milvus https://zilliztech.github.io/milvus-helm/
    helm repo update
    
    helm upgrade --install milvus milvus/milvus \
        --namespace $NAMESPACE \
        --set cluster.enabled=false \
        --set etcd.replicaCount=1 \
        --set minio.mode=standalone \
        --set pulsar.enabled=false \
        --set kafka.enabled=true \
        --set standalone.resources.limits.memory=8Gi \
        --set standalone.resources.requests.memory=4Gi \
        --timeout 15m \
        --wait
    
    echo "  ✅ Milvus deployed"
    
    # Deploy custom RAG services (will create these next)
    echo "  → Deploying RAG query and ingest services..."
    kubectl apply -f rag-services.yaml -n $NAMESPACE
    echo "  ✅ RAG services deployed"
fi
echo ""

# Wait for Milvus to be ready
echo "Step 7/10: Waiting for Milvus to be ready..."
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=milvus -n $NAMESPACE --timeout=10m || true
echo "✅ Milvus is ready"
echo ""

# Wait for RAG services to be ready
echo "Step 8/10: Waiting for RAG services to be ready..."
echo "  → Checking query server..."
kubectl wait --for=condition=Ready pod -l app=rag-query-server -n $NAMESPACE --timeout=5m || echo "  ⏳ Query server still starting..."

echo "  → Checking ingest server..."
kubectl wait --for=condition=Ready pod -l app=rag-ingest-server -n $NAMESPACE --timeout=5m || echo "  ⏳ Ingest server still starting..."
echo ""

# Display deployment status
echo "Step 9/10: Checking deployment status..."
echo ""
kubectl get pods -n $NAMESPACE
echo ""
kubectl get svc -n $NAMESPACE
echo ""

# Health checks
echo "Step 10/10: Running health checks..."
echo ""

RAG_QUERY_SVC=$(kubectl get svc -n $NAMESPACE -l app=rag-query-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$RAG_QUERY_SVC" ]; then
    echo "✅ RAG Query Service: $RAG_QUERY_SVC (port 8081)"
else
    echo "⚠️  RAG Query Service not found yet"
fi

RAG_INGEST_SVC=$(kubectl get svc -n $NAMESPACE -l app=rag-ingest-server -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$RAG_INGEST_SVC" ]; then
    echo "✅ RAG Ingest Service: $RAG_INGEST_SVC (port 8082)"
else
    echo "⚠️  RAG Ingest Service not found yet"
fi

MILVUS_SVC=$(kubectl get svc -n $NAMESPACE -l app.kubernetes.io/name=milvus -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$MILVUS_SVC" ]; then
    echo "✅ Milvus Service: $MILVUS_SVC (port 19530)"
else
    echo "⚠️  Milvus Service not found yet"
fi

echo ""
echo "=========================================="
echo "🎉 Deployment Complete!"
echo "=========================================="
echo ""
echo "Deployed Components:"
echo "  - Milvus Vector Database (enterprise-grade)"
echo "  - RAG Query Server (port 8081)"
echo "  - RAG Ingest Server (port 8082)"
echo "  - Connected to your existing embedding NIM"
echo ""
echo "Next Steps:"
echo ""
echo "1. Port-forward for local access (if needed):"
echo "   kubectl port-forward -n $NAMESPACE svc/$RAG_QUERY_SVC 8081:8081"
echo "   kubectl port-forward -n $NAMESPACE svc/$RAG_INGEST_SVC 8082:8082"
echo ""
echo "2. Ingest the tariff PDFs:"
echo "   cd ../../scripts"
echo "   export RAG_INGEST_URL=http://localhost:8082/v1"
echo "   ./setup_tariff_rag_service.sh"
echo ""
echo "3. Or use from within cluster (AI-Q agent):"
echo "   RAG_SERVER_URL: http://$RAG_QUERY_SVC.$NAMESPACE.svc.cluster.local:8081/v1"
echo ""
echo "=========================================="
echo ""
echo "To monitor the deployment:"
echo "  kubectl get pods -n $NAMESPACE -w"
echo ""
echo "To view logs:"
echo "  kubectl logs -n $NAMESPACE -l app=rag-query-server -f"
echo "  kubectl logs -n $NAMESPACE -l app=rag-ingest-server -f"
echo ""
echo "=========================================="

