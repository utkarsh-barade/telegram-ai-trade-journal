# ── Stage 1: Build React Frontend ─────────────────────────────────────────────
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python Backend & Monitoring Runner ──────────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application backend code
COPY . .

# Copy compiled frontend static bundle from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose Hugging Face Spaces port
EXPOSE 7860

# Run FastAPI & Telegram Bot background worker
CMD ["python", "-m", "bot.main"]
