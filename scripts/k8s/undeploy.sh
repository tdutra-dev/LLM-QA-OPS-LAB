#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# undeploy.sh — Remove LLM-QA-OPS from Kubernetes
#
# Removes all resources. Optionally preserve PVC for data persistence.
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
source "$SCRIPT_DIR/common.sh"

PRESERVE_DATA=${1:-"false"}

if [[ "$PRESERVE_DATA" == "--keep-data" ]]; then
    log_info "Removing LLM-QA-OPS (preserving PostgreSQL data)..."
    kubectl delete -k "$PROJECT_ROOT/k8s/" --ignore-not-found
    # Recreate only the PVC
    kubectl apply -f "$PROJECT_ROOT/k8s/namespace.yaml"
    kubectl apply -f "$PROJECT_ROOT/k8s/postgres/pvc.yaml"
    log_warning "PostgreSQL PVC preserved. Data will be restored on next deployment."
else
    log_info "Removing LLM-QA-OPS completely..."
    kubectl delete namespace llmqa --ignore-not-found
    log_info "All resources deleted including data."
fi

log_success "Cleanup complete!"