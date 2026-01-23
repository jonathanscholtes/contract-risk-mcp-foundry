#!/bin/bash
# Deploy platform components (Prometheus, Grafana, OTel)

set -e

echo "Deploying platform add-ons..."
helm upgrade --install platform k8s/helm/platform \
  --namespace platform --create-namespace \
  --wait

echo "Platform deployed successfully!"
echo "Grafana URL: kubectl port-forward -n platform svc/grafana 3000:3000"
echo "Access Grafana at http://localhost:3000 (admin/admin)"
