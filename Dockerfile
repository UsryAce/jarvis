# Multi-stage build for JARVIS
FROM python:3.11-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 jarvis && \
    mkdir -p /app/data/memory /app/logs /app/config && \
    chown -R jarvis:jarvis /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/jarvis/.local

# Copy application code
COPY --chown=jarvis:jarvis . .

# Set PATH for user packages
ENV PATH=/home/jarvis/.local/bin:$PATH
ENV PYTHONPATH=/app

# Switch to non-root user
USER jarvis

# Create data directories
RUN mkdir -p /app/data/memory /app/logs

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["python", "-m", "src.cli.main", "serve"]