FROM python:3.11-slim

LABEL maintainer="HydroClaw Team"
LABEL description="HydroClaw — 水网智能工作台"

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN pip install -e ".[web,alumina]" --no-cache-dir

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/personality data/memory data/sessions data/interactions data/evolution_reports

EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/gateway/health')" || exit 1

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
