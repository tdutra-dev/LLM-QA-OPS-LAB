#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build-images.sh — Build Docker images for K8s deployment
#
# Builds both eval-py and dash-app images and loads them into the K8s cluster.
# For kind: uses kind load docker-image
# For minikube: uses minikube image load
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
source "$SCRIPT_DIR/common.sh"

log_info "Building Docker images for LLM-QA-OPS..."

# Build eval-py image
log_info "Building eval-py FastAPI service..."
docker build -t llmqa/eval-py:latest "$PROJECT_ROOT/packages/eval-py/"
log_success "eval-py image built"

# Build dash-app image  
log_info "Building dash-app Dash dashboard..."
docker build -t llmqa/dash-app:latest "$PROJECT_ROOT/packages/dash-app/"
log_success "dash-app image built"

# Detect cluster type and load images
if kubectl config current-context | grep -q "kind"; then
    log_info "Detected kind cluster, loading images..."
    kind load docker-image llmqa/eval-py:latest
    kind load docker-image llmqa/dash-app:latest
    log_success "Images loaded into kind cluster"
elif kubectl config current-context | grep -q "minikube"; then
    log_info "Detected minikube cluster, loading images..."
    minikube image load llmqa/eval-py:latest
    minikube image load llmqa/dash-app:latest
    log_success "Images loaded into minikube cluster"
elif docker context inspect default | grep -q "desktop-linux"; then
    log_warning "Docker Desktop detected. Images should be available automatically."
else
    log_warning "Unknown cluster type. You may need to push images to a registry."
fi

log_success "All images ready for deployment!"