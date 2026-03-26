# Step 11: Kubernetes Deployment & Orchestration

This document describes the **Kubernetes deployment** for the LLM-QA-OPS system, providing container orchestration for production scalability.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ingress       │    │   NodePort      │    │   LoadBalancer  │
│   (nginx)       │    │   Services      │    │   (cloud)       │  
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   dash-app   │  │   eval-py    │  │  PostgreSQL  │         │
│  │  (Port 8050) │  │ (Port 8010)  │  │ (Port 5432)  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                       ┌──────────────┐         │
│                                       │    Redis     │         │
│                                       │ (Port 6379)  │         │
│                                       └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

```bash
# Local development cluster (choose one):
kind create cluster --name llmqa
# OR
minikube start

# For Ingress (optional):
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/cloud/deploy.yaml
# OR for minikube:
minikube addons enable ingress
```

### 2. Build and Deploy

```bash
# Build Docker images
./scripts/k8s/build-images.sh

# Deploy complete stack
./scripts/k8s/deploy.sh

# Check status
kubectl get pods -n llmqa
```

### 3. Access Applications

```bash
# Dashboard (Dash) - port forwarding
kubectl port-forward -n llmqa svc/dash-app-svc 8050:8050
# ➜ http://localhost:8050

# FastAPI backend - port forwarding  
kubectl port-forward -n llmqa svc/eval-py-svc 8010:8010
# ➜ http://localhost:8010/docs

# Via Ingress (if configured)
echo "127.0.0.1 llmqa.local" >> /etc/hosts
# ➜ http://llmqa.local (dashboard)
# ➜ http://llmqa.local/api/ (FastAPI)
```

## Components

### Core Services

| Service    | Image                  | Replicas | Resources      | Purpose                    |
|------------|------------------------|----------|----------------|----------------------------|
| postgres   | postgres:16-alpine     | 1        | 256Mi/500m     | Primary data store         |
| redis      | redis:7-alpine         | 1        | 64Mi/200m      | Evaluation cache           |
| eval-py    | llmqa/eval-py:latest   | 1        | 256Mi/1000m    | FastAPI evaluation engine  |
| dash-app   | llmqa/dash-app:latest  | 1        | 256Mi/500m     | Interactive dashboard      |

### Configuration

**ConfigMap** (`llmqa-config`):
- Non-sensitive environment variables
- Database connection parameters
- Service discovery endpoints

**Secret** (`llmqa-secret`):
- PostgreSQL password
- OpenAI API key (base64 encoded)
- Database URL with credentials

### Storage

**PostgreSQL PVC**:
- 2Gi persistent storage
- ReadWriteOnce access mode
- Survives pod restarts and updates
- Remove with `kubectl delete pvc postgres-pvc -n llmqa`

### Networking

**Services**:
- `postgres-svc`: ClusterIP, internal database access
- `redis-svc`: ClusterIP, internal cache access  
- `eval-py-svc`: ClusterIP, FastAPI endpoints
- `dash-app-svc`: NodePort (30050), dashboard access

**Ingress** (optional):
- `llmqa-ingress`: Routes external traffic
- `/` → dashboard (dash-app:8050)
- `/api/*` → FastAPI (eval-py:8010)

## Management Scripts

### Build Images
```bash
./scripts/k8s/build-images.sh
# Builds llmqa/eval-py:latest and llmqa/dash-app:latest
# Auto-loads into kind/minikube clusters
```

### Deploy Stack
```bash
./scripts/k8s/deploy.sh
# Creates namespace, applies all manifests
# Waits for deployments to be ready
# Shows access instructions
```

### Undeploy
```bash
# Remove everything (including data)
./scripts/k8s/undeploy.sh

# Remove but keep PostgreSQL data
./scripts/k8s/undeploy.sh --keep-data
```

### Monitor Status
```bash
kubectl get all -n llmqa
kubectl logs -f deployment/eval-py -n llmqa
kubectl logs -f deployment/dash-app -n llmqa
```

## Production Considerations

### Security
- Update `secret.yaml` with real credentials (do not commit secrets to git)
- Use external secret management (AWS Secrets Manager, HashiCorp Vault)
- Enable RBAC and network policies
- Configure TLS for Ingress

### Scaling
```bash
# Scale eval-py for higher load
kubectl scale deployment/eval-py --replicas=3 -n llmqa

# Scale dash-app for more concurrent users
kubectl scale deployment/dash-app --replicas=2 -n llmqa
```

### Persistence
- Use cloud-managed databases (RDS, Cloud SQL) for production
- Configure Redis with persistence or use cloud Redis (ElastiCache)
- Set up regular PVC backups

### Monitoring
- Add Prometheus ServiceMonitors for metrics collection
- Configure log aggregation (ELK stack, Grafana Loki)
- Set up alerts for pod failures and resource usage

## Troubleshooting

### Common Issues

**Images Not Found**:
```bash
# Rebuild and reload images
./scripts/k8s/build-images.sh

# For cloud clusters, push to registry:
docker tag llmqa/eval-py:latest your-registry/llmqa/eval-py:latest
docker push your-registry/llmqa/eval-py:latest
```

**Database Connection Issues**:
```bash
# Check postgres pod logs
kubectl logs deployment/postgres -n llmqa

# Test database connectivity
kubectl exec -it deployment/eval-py -n llmqa -- nc -zv postgres-svc 5432
```

**Dashboard Cannot Reach FastAPI**:
```bash
# Check eval-py service
kubectl get svc eval-py-svc -n llmqa

# Check network policies
kubectl get networkpolicies -n llmqa

# Test from dashboard pod
kubectl exec -it deployment/dash-app -n llmqa -- curl http://eval-py-svc:8010/health
```

### Useful Commands
```bash
# Resource usage
kubectl top pods -n llmqa

# Events
kubectl get events -n llmqa --sort-by=.lastTimestamp

# Pod shell access  
kubectl exec -it deployment/eval-py -n llmqa -- /bin/bash

# Port forwarding for debugging
kubectl port-forward -n llmqa svc/postgres-svc 5432:5432
kubectl port-forward -n llmqa svc/redis-svc 6379:6379
```

## Next Steps: Steps 12-13

After Step 11 deployment works:
- **Step 12**: Performance monitoring with Prometheus + Grafana, load testing
- **Step 13**: Production readiness with CI/CD pipelines, security hardening, SRE practices

**Step 11 provides a complete Kubernetes deployment foundation for enterprise LLM operations!** 🚀