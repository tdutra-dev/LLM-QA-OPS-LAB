#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Scripts for local Kubernetes deployment (kind/minikube)
#
# Usage:
#   ./scripts/k8s/build-images.sh      # Build Docker images
#   ./scripts/k8s/deploy.sh           # Deploy to Kubernetes
#   ./scripts/k8s/undeploy.sh         # Remove from Kubernetes
#   ./scripts/k8s/logs.sh             # View logs
#   ./scripts/k8s/status.sh           # Check status
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" &> /dev/null && pwd)\"
PROJECT_ROOT=\"$(cd \"${SCRIPT_DIR}/../..\" &> /dev/null && pwd)\"

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

log_info() {
    echo -e \"${BLUE}[INFO]${NC} $1\"
}

log_success() {
    echo -e \"${GREEN}[SUCCESS]${NC} $1\"
}

log_warning() {
    echo -e \"${YELLOW}[WARNING]${NC} $1\"
}

log_error() {
    echo -e \"${RED}[ERROR]${NC} $1\"
}