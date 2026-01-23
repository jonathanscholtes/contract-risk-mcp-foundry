FROM python:3.11-slim

WORKDIR /app

# Copy shared contracts
COPY shared/contracts /app/shared/contracts

# Copy app code
COPY apps/mcp-risk /app/mcp-risk

# Install dependencies
RUN pip install --no-cache-dir /app/mcp-risk

# Run the server
CMD ["python", "-m", "mcp-risk.src.main"]
