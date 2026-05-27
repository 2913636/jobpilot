# JobPilot Deployment Guide

## Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.5
- Helm >= 3.12
- kubectl >= 1.28
- Docker >= 24
- GitHub Container Registry access

## 1. Infrastructure Provisioning (AWS EKS)

### Option A: Terraform (Recommended)

```bash
cd deploy/terraform

# Initialize
terraform init

# Plan
terraform plan -var="environment=staging" -out=staging.tfplan

# Apply
terraform apply staging.tfplan

# Configure kubectl
aws eks update-kubeconfig --name jobpilot-staging --region us-east-1
kubectl get nodes
```

### Option B: Manual EKS Cluster

```bash
# Create EKS cluster
eksctl create cluster \
  --name jobpilot-staging \
  --region us-east-1 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 10 \
  --managed

# Create namespaces
kubectl create namespace jobpilot
```

## 2. Secrets Management

```bash
# Create secrets from .env
kubectl create secret generic jobpilot-secrets \
  --namespace jobpilot \
  --from-env-file=.env

# Or set individual secrets
kubectl create secret generic jobpilot-db \
  --namespace jobpilot \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -base64 32) \
  --from-literal=JWT_SECRET_KEY=$(openssl rand -base64 64)
```

## 3. Helm Deployment

```bash
# Add Helm repos (if needed)
helm repo add bitnami https://charts.bitnami.com/bitnami

# Install dependencies first (PostgreSQL, Redis, ES, etc.)
# Then deploy JobPilot services
helm upgrade --install jobpilot ./deploy/helm/jobpilot \
  --namespace jobpilot \
  --create-namespace \
  --set global.domain=jobpilot.example.com \
  --set global.environment=staging \
  --set user-service.replicas=2 \
  --set resume-service.replicas=2 \
  --set match-service.replicas=2 \
  --set apply-service.replicas=2 \
  --set interview-service.replicas=1 \
  --set agent-service.replicas=1 \
  --set frontend.replicas=2 \
  --timeout 10m \
  --wait

# Verify deployment
kubectl get pods -n jobpilot
kubectl get svc -n jobpilot
```

### Service Scaling

```bash
# Scale based on load
kubectl scale deployment user-service --replicas=4 -n jobpilot
kubectl scale deployment match-service --replicas=3 -n jobpilot
```

## 4. Health Verification

```bash
# Check all pods healthy
kubectl wait --for=condition=ready pod -l app=jobpilot -n jobpilot --timeout=300s

# Port-forward and check health endpoints
kubectl port-forward svc/user-service 8001:8000 -n jobpilot &
curl http://localhost:8001/health/livez
curl http://localhost:8001/health/readyz

# Run E2E smoke test
bash scripts/demo.sh
```

## 5. Frontend Deployment (Vercel)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd frontend
vercel --prod \
  --env NEXT_PUBLIC_API_URL=https://api.jobpilot.example.com \
  --env NEXT_PUBLIC_LIVEKIT_URL=https://livekit.jobpilot.example.com

# Or via GitHub integration:
# 1. Connect repo to Vercel
# 2. Set build command: cd frontend && npm run build
# 3. Set output directory: frontend/.next
# 4. Configure env vars in Vercel dashboard
```

## 6. Database Migrations

```bash
# Run migrations against production DB
kubectl exec -it deploy/user-service -n jobpilot -- \
  alembic upgrade head

# Or via temporary pod
kubectl run migrate --rm -it --image=jobpilot-user-service:latest \
  --restart=Never -n jobpilot -- \
  alembic upgrade head
```

## 7. Monitoring Setup

```bash
# Port-forward Grafana
kubectl port-forward svc/grafana 3000:3000 -n monitoring

# Import dashboards from
# backend/services/agent_service/monitoring/grafana-alerts.yml

# Verify Prometheus targets
kubectl port-forward svc/prometheus 9090:9090 -n monitoring
```

## 8. Backup Schedule

```bash
# Temporal cron auto-runs BackupWorkflow every Sunday 03:00 UTC
# Manual trigger:
curl -X POST https://api.jobpilot.example.com/api/agents/workflows/backup \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Or use the backup script directly:
bash scripts/backup.sh
```

## 9. Rollback Procedure

```bash
# List Helm history
helm history jobpilot -n jobpilot

# Rollback to previous revision
helm rollback jobpilot -n jobpilot

# Or deploy specific version
helm upgrade --install jobpilot ./deploy/helm/jobpilot \
  --namespace jobpilot \
  --set image.tag=v1.0.0
```

## 10. Certificate Management

```bash
# Traefik handles Let's Encrypt auto-renewal
# For manual certificate check:
kubectl get certificates -n jobpilot

# For custom certificates:
kubectl create secret tls jobpilot-tls \
  --cert=fullchain.pem \
  --key=privkey.pem \
  -n jobpilot
```

## Environment-Specific Configs

| Config | Dev | Staging | Production |
|--------|-----|---------|------------|
| Replicas (min) | 1 | 2 | 3 |
| DB pool_size | 10 | 15 | 20 |
| Log level | DEBUG | INFO | WARNING |
| SMTP enabled | false | true | true |
| OTEL tracing | disabled | sampling 50% | sampling 10% |
| Auto-scaling | off | CPU > 70% | CPU > 60% |
