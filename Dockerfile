# Build stage
FROM python:3.11-slim as builder

# Set work directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
# --force-reinstall ensures motor and pymongo are reinstalled at the pinned
# versions even when Railway replays a cached pip layer with motor 2.x.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --index-url https://pypi.org/simple/ --force-reinstall "motor==3.5.1" "pymongo>=4.5.0,<5.0.0" \
    && pip install --no-cache-dir --index-url https://pypi.org/simple/ -r requirements.txt

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Ensure .env is NOT copied (handled by .gitignore, but explicit check here)
# Usually you inject environment variables via docker-compose or Kubernetes secrets
RUN rm -f .env

# Expose port
EXPOSE 8000

# start.sh force-reinstalls motor/pymongo at container start to override any
# cached wrong versions in the Railway image layer.
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
