FROM python:3.11-slim

WORKDIR /app

# Copy shared contracts
COPY shared/contracts /app/shared/contracts

# Copy app code
COPY apps/agent-orchestrator /app/agent-orchestrator

# Install dependencies
RUN pip install --no-cache-dir /app/agent-orchestrator

# Run the orchestrator
CMD ["python", "-m", "agent-orchestrator.src.orchestrator"]
