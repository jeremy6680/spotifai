# ─────────────────────────────────────────────
# Stage 1: builder — install Python dependencies
# ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy only requirements first (Docker layer caching optimization)
# If requirements.txt doesn't change, this layer is reused on next build
COPY requirements.txt .

# Install dependencies into an isolated directory
# --no-cache-dir : don't store pip cache (keeps image smaller)
# --prefix       : install to /install so we can copy only this folder later
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─────────────────────────────────────────────
# Stage 2: runtime — lean production image
# ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed dependencies from builder stage
COPY --from=builder /install /usr/local

# Copy application source code
COPY . .

# Create data directory for DuckDB persistence
# This directory will be mounted as a volume in Coolify
RUN mkdir -p /app/data

# Expose the port Uvicorn will listen on
EXPOSE 8000

# Start the FastAPI app with Uvicorn
# --host 0.0.0.0 : listen on all interfaces (required inside Docker)
# --port 8000    : must match EXPOSE above
# --workers 1    : DuckDB file doesn't support concurrent writes
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]