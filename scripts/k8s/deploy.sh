#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — Deploy LLM-QA-OPS to Kubernetes
#
# Deploys the complete stack: PostgreSQL, Redis, eval-py, dash-app, Ingress
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
source "$SCRIPT_DIR/common.sh"

log_info "Deploying LLM-QA-OPS to Kubernetes..."

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Apply all manifests using Kustomize
log_info "Applying Kubernetes manifests..."
kubectl apply -k "$PROJECT_ROOT/k8s/"

# Wait for deployments to be ready
log_info "Waiting for deployments to be ready..."
kubectl wait --for=condition=Available deployment/postgres -n llmqa --timeout=120s
kubectl wait --for=condition=Available deployment/redis -n llmqa --timeout=120s
kubectl wait --for=condition=Available deployment/eval-py -n llmqa --timeout=180s
kubectl wait --for=condition=Available deployment/dash-app -n llmqa --timeout=180s

# Show status
log_success "Deployment complete!"
echo ""
log_info "Checking pod status:"
kubectl get pods -n llmqa

echo ""
log_info "Services:"
kubectl get svc -n llmqa

echo ""
log_info "Access URLs:"
echo "  • Dashboard (NodePort): kubectl port-forward -n llmqa svc/dash-app-svc 8050:8050"
echo "  • FastAPI (NodePort):   kubectl port-forward -n llmqa svc/eval-py-svc 8010:8010"
echo "  • Ingress (if enabled): http://llmqa.local (add to /etc/hosts)"

log_success "LLM-QA-OPS is now running on Kubernetes! 🚀"