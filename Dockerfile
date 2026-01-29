# Stage 1: Builder (runs as root; pip --user installs to /root/.local)
# Use full python image instead of slim for better build tool compatibility
FROM python:3.11 AS builder
WORKDIR /app

# Install build dependencies for compiling Python packages (scipy, numpy, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    gfortran \
    make \
    pkg-config \
    cmake \
    ninja-build \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip, setuptools, and wheel to latest versions for better wheel support
RUN pip install --upgrade pip setuptools wheel

# Install requirements (pip will prefer wheels when available)
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for PDF processing (unstructured library)
RUN apt-get update && apt-get install -y \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-privileged user
RUN useradd -m appuser

# Copy installed packages from builder (root's .local)
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

# Create data/temp directory and ensure appuser owns it
RUN mkdir -p /app/data/temp && \
    chown -R appuser:appuser /app/data

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
# Set port from environment variable (Cloud Run uses PORT env var)
ENV PORT=8000

EXPOSE 8000
# Use PORT env var for Cloud Run compatibility
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
