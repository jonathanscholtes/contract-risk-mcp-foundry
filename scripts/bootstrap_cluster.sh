#!/bin/bash
# Bootstrap AKS cluster with required dependencies

set -e

echo "Installing KEDA..."
helm repo add kedacore https://kedacore.github.io/charts
helm repo update
helm upgrade --install keda kedacore/keda \
  --namespace keda --create-namespace

echo "Installing RabbitMQ Operator (optional) or Bitnami chart..."
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

echo "Cluster bootstrap complete!"
echo "Next steps:"
echo "  1. Run ./deploy_platform.sh to install monitoring"
echo "  2. Run ./deploy_rabbitmq.sh to install RabbitMQ"
echo "  3. Build and push images, then run ./deploy_tools.sh and ./deploy_workers.sh"
