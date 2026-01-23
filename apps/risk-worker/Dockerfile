FROM python:3.11-slim

WORKDIR /app

# Copy shared contracts
COPY shared/contracts /app/shared/contracts

# Copy app code
COPY apps/risk-worker /app/risk-worker

# Install dependencies
RUN pip install --no-cache-dir /app/risk-worker

# Run the worker
CMD ["python", "-m", "risk-worker.src.worker"]
