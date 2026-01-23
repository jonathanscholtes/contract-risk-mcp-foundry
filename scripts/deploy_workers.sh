#!/bin/bash
# Deploy risk workers with KEDA autoscaling

set -e

# Check if ACR is set
if [ -z "$ACR_NAME" ]; then
  echo "Error: ACR_NAME environment variable not set"
  echo "Usage: export ACR_NAME=myacr.azurecr.io && ./deploy_workers.sh"
  exit 1
fi

echo "Deploying risk workers from $ACR_NAME..."
helm upgrade --install risk-workers k8s/helm/risk-workers \
  --namespace workers --create-namespace \
  --set registry=$ACR_NAME \
  --wait

echo "Risk workers deployed successfully!"
echo "Check autoscaling: kubectl get scaledobject -n workers"
echo "Watch pods: kubectl get pods -n workers -w"
