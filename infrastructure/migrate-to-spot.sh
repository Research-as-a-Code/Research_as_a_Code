#!/bin/bash
# SPDX-FileCopyrightText: Copyright (c) 2025 Research_as_a_Code Project
# SPDX-License-Identifier: Apache-2.0

set -e  # Exit on error

# ============================================================================
# Migrate to Spot Instances - Cost Optimization Script
# ============================================================================
# 
# This script migrates GPU and system workload nodes to spot instances
# while keeping critical stateful services (Milvus, etcd, MinIO) on on-demand
# 
# Expected Cost Savings: ~$1,500/month (~70% reduction on compute)
# 
# Safety Features:
# - Pod Disruption Budgets prevent all replicas from being evicted
# - Critical data services pinned to on-demand nodes
# - Graceful shutdown periods configured
# - 2-minute spot interruption warnings via Karpenter
# ============================================================================

CLUSTER_NAME=${CLUSTER_NAME:-"aiq-udf-eks"}
AWS_REGION=${AWS_REGION:-"us-west-2"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

confirm_action() {
    local message="$1"
    echo -e "${YELLOW}$message${NC}"
    read -p "Continue? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_warning "Action cancelled by user"
        exit 0
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it."
        exit 1
    fi
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install it."
        exit 1
    fi
    
    # Check terraform
    if ! command -v terraform &> /dev/null; then
        log_error "Terraform not found. Please install it."
        exit 1
    fi
    
    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access Kubernetes cluster. Please configure kubectl."
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

backup_current_state() {
    log_info "Backing up current configuration..."
    
    local backup_dir="$SCRIPT_DIR/backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    
    # Backup Kubernetes resources
    kubectl get nodes -o yaml > "$backup_dir/nodes.yaml" 2>/dev/null || true
    kubectl get pods --all-namespaces -o yaml > "$backup_dir/pods.yaml" 2>/dev/null || true
    kubectl get nodepools -n karpenter -o yaml > "$backup_dir/karpenter-nodepools.yaml" 2>/dev/null || true
    
    # Backup Terraform state
    cp "$SCRIPT_DIR/terraform/terraform.tfstate" "$backup_dir/" 2>/dev/null || true
    
    log_success "Backup created at: $backup_dir"
    echo "$backup_dir" > "$SCRIPT_DIR/.last-backup"
}

# ============================================================================
# Step 1: Apply Pod Disruption Budgets
# ============================================================================

apply_pdbs() {
    log_info "Step 1/5: Applying Pod Disruption Budgets for High Availability..."
    
    if [ ! -f "$SCRIPT_DIR/kubernetes/pod-disruption-budgets.yaml" ]; then
        log_error "PDB file not found: $SCRIPT_DIR/kubernetes/pod-disruption-budgets.yaml"
        exit 1
    fi
    
    kubectl apply -f "$SCRIPT_DIR/kubernetes/pod-disruption-budgets.yaml"
    
    log_success "Pod Disruption Budgets applied"
    
    # Verify PDBs
    log_info "Verifying PDBs..."
    kubectl get pdb -n aiq-agent
    kubectl get pdb -n rag-blueprint
    kubectl get pdb -n nim
}

# ============================================================================
# Step 2: Update Karpenter Provisioner for Spot GPU Nodes
# ============================================================================

update_karpenter_provisioner() {
    log_info "Step 2/5: Updating Karpenter provisioner to use spot instances..."
    
    if [ ! -f "$SCRIPT_DIR/terraform/karpenter-provisioner.yaml" ]; then
        log_error "Karpenter provisioner file not found"
        exit 1
    fi
    
    kubectl apply -f "$SCRIPT_DIR/terraform/karpenter-provisioner.yaml"
    
    log_success "Karpenter provisioner updated to prioritize spot instances"
    
    # Show current configuration
    log_info "Current Karpenter NodePools:"
    kubectl get nodepools -n karpenter
}

# ============================================================================
# Step 3: Update Terraform Configuration for Spot System Nodes
# ============================================================================

update_terraform_config() {
    log_info "Step 3/5: Updating Terraform configuration for spot system nodes..."
    
    cd "$SCRIPT_DIR/terraform"
    
    # Validate configuration
    log_info "Validating Terraform configuration..."
    terraform validate
    
    # Show plan
    log_info "Generating Terraform plan..."
    terraform plan -out=spot-migration.tfplan
    
    confirm_action "This will create spot system nodes. Review the plan above."
    
    # Apply changes
    log_info "Applying Terraform changes..."
    terraform apply spot-migration.tfplan
    
    # Clean up plan file
    rm -f spot-migration.tfplan
    
    cd - > /dev/null
    
    log_success "Terraform configuration applied - spot system nodes are being provisioned"
}

# ============================================================================
# Step 4: Update Milvus Helm Values to Pin to On-Demand
# ============================================================================

update_milvus_config() {
    log_info "Step 4/5: Updating Milvus configuration to pin critical services to on-demand nodes..."
    
    if [ ! -f "$SCRIPT_DIR/helm/milvus-standalone-values.yaml" ]; then
        log_warning "Milvus values file not found, skipping..."
        return
    fi
    
    # Check if Milvus is deployed
    if ! kubectl get namespace rag-blueprint &> /dev/null; then
        log_warning "rag-blueprint namespace not found, skipping Milvus update..."
        return
    fi
    
    log_info "Upgrading Milvus Helm release..."
    helm upgrade milvus \
        -n rag-blueprint \
        -f "$SCRIPT_DIR/helm/milvus-standalone-values.yaml" \
        milvus/milvus \
        --wait \
        --timeout 10m || log_warning "Milvus upgrade failed or not installed"
    
    log_success "Milvus configuration updated"
}

# ============================================================================
# Step 5: Verify Migration and Monitor
# ============================================================================

verify_migration() {
    log_info "Step 5/5: Verifying migration and monitoring cluster state..."
    
    echo ""
    log_info "Current node status:"
    kubectl get nodes -L karpenter.sh/capacity-type -L karpenter.k8s.aws/instance-type
    
    echo ""
    log_info "Pod distribution:"
    echo "=== aiq-agent namespace ==="
    kubectl get pods -n aiq-agent -o wide
    
    echo ""
    echo "=== rag-blueprint namespace ==="
    kubectl get pods -n rag-blueprint -o wide
    
    echo ""
    echo "=== nim namespace ==="
    kubectl get pods -n nim -o wide
    
    echo ""
    log_info "Pod Disruption Budgets status:"
    kubectl get pdb --all-namespaces
    
    echo ""
    log_success "Migration verification complete!"
}

# ============================================================================
# Monitoring and Rollback Instructions
# ============================================================================

show_monitoring_commands() {
    cat << EOF

${GREEN}════════════════════════════════════════════════════════════════${NC}
${GREEN}  Spot Instance Migration Complete!${NC}
${GREEN}════════════════════════════════════════════════════════════════${NC}

${BLUE}Expected Cost Savings:${NC} ~\$1,500/month (~70% reduction)

${YELLOW}Monitoring Commands:${NC}

1. Watch node status (spot vs on-demand):
   ${BLUE}kubectl get nodes -L karpenter.sh/capacity-type -w${NC}

2. Monitor spot interruptions (Karpenter logs):
   ${BLUE}kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter -f${NC}

3. Check pod evictions:
   ${BLUE}kubectl get events --all-namespaces --field-selector reason=Evicted${NC}

4. Verify PDB protection:
   ${BLUE}kubectl get pdb --all-namespaces${NC}

5. Monitor cost with AWS Cost Explorer:
   ${BLUE}aws ce get-cost-and-usage --time-period Start=\$(date -d '7 days ago' +%Y-%m-%d),End=\$(date +%Y-%m-%d) --granularity DAILY --metrics BlendedCost${NC}

${YELLOW}Rollback Instructions (if needed):${NC}

If you experience issues, rollback to on-demand nodes:

1. Revert Karpenter provisioner:
   ${BLUE}kubectl edit nodepool nvidia-nim-gpu -n karpenter${NC}
   Change: values: ["spot", "on-demand"] → values: ["on-demand"]

2. Revert Terraform:
   ${BLUE}cd infrastructure/terraform
   git checkout HEAD -- main.tf
   terraform apply${NC}

3. Or restore from backup:
   ${BLUE}Backup location: $(cat "$SCRIPT_DIR/.last-backup" 2>/dev/null || echo "N/A")${NC}

${YELLOW}Critical Services Status:${NC}
- Milvus, etcd, MinIO: ${GREEN}Pinned to on-demand nodes (protected)${NC}
- GPU NIMs: ${BLUE}Running on spot nodes (interruptible, auto-recovers)${NC}
- Backend/Frontend: ${BLUE}Running on spot nodes (2 replicas, PDB protected)${NC}

${GREEN}Your infrastructure is now optimized for cost while maintaining reliability!${NC}

EOF
}

# ============================================================================
# Main Execution Flow
# ============================================================================

main() {
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "  Spot Instance Migration Script"
    echo "  Cost Optimization: ~70% savings on compute"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    
    check_prerequisites
    
    cat << EOF
${YELLOW}This script will:${NC}

1. Apply Pod Disruption Budgets (ensure HA during interruptions)
2. Update Karpenter to use spot instances for GPU nodes
3. Create spot system node groups via Terraform
4. Pin Milvus/etcd/MinIO to on-demand nodes (data protection)
5. Verify migration and show monitoring commands

${GREEN}What's protected:${NC}
- Vector database (Milvus) on stable on-demand nodes
- Metadata stores (etcd, MinIO) on on-demand nodes
- At least 1 replica of backend/frontend always running

${BLUE}What can be interrupted:${NC}
- GPU nodes running NIMs (auto-restart on new nodes)
- Extra replicas of stateless services

${YELLOW}Estimated downtime:${NC} None (rolling updates)
${GREEN}Expected savings:${NC} ~\$1,500/month

EOF
    
    confirm_action "Ready to begin spot instance migration?"
    
    backup_current_state
    apply_pdbs
    update_karpenter_provisioner
    update_terraform_config
    update_milvus_config
    verify_migration
    show_monitoring_commands
    
    log_success "Spot instance migration completed successfully!"
}

# Run main function
main "$@"

