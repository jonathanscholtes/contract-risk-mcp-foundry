#!/bin/bash
# Deploy RabbitMQ using Bitnami Helm chart

set -e

echo "Deploying RabbitMQ..."
helm upgrade --install rabbitmq bitnami/rabbitmq \
  --namespace rabbitmq --create-namespace \
  --set auth.username=user \
  --set auth.password=password \
  --set metrics.enabled=true \
  --set metrics.serviceMonitor.enabled=true \
  --wait

echo "RabbitMQ deployed successfully!"
echo "Management UI: kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672"
echo "Access at http://localhost:15672 (user/password)"
