FROM python:3.11-slim

WORKDIR /app

# Copy shared contracts
COPY shared/contracts /app/shared/contracts

# Copy app code
COPY apps/mcp-contracts /app/mcp-contracts

# Install dependencies
RUN pip install --no-cache-dir /app/mcp-contracts

# Run the server
CMD ["python", "-m", "mcp-contracts.src.main"]
