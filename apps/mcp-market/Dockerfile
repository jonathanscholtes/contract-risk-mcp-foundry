FROM python:3.11-slim

WORKDIR /app

# Copy shared contracts
COPY shared/contracts /app/shared/contracts

# Copy app code
COPY apps/mcp-market /app/mcp-market

# Install dependencies
RUN pip install --no-cache-dir /app/mcp-market

# Run the server
CMD ["python", "-m", "mcp-market.src.main"]
