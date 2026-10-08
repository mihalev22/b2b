# Две цели сборки: backend и Ollama с заранее скачанными моделями.
FROM ollama/ollama:latest AS ollama-runtime
ARG TEXT_MODEL=qwen3.5:2b-q4_K_M
ARG EMBED_MODEL=embeddinggemma:300m
ENV OLLAMA_MODELS=/opt/models
ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_NUM_PARALLEL=1
ENV OLLAMA_MAX_LOADED_MODELS=1
RUN set -eu; \
    ollama serve > /tmp/ollama-build.log 2>&1 & pid=$!; \
    trap 'kill "$pid" 2>/dev/null || true' EXIT; \
    attempts=0; \
    until ollama list > /dev/null 2>&1; do \
      attempts=$((attempts + 1)); \
      if [ "$attempts" -ge 60 ]; then cat /tmp/ollama-build.log; exit 1; fi; \
      sleep 1; \
    done; \
    ollama pull "$TEXT_MODEL"; \
    ollama pull "$EMBED_MODEL"

FROM python:3.11-slim AS backend
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY step*.py app.py ./
RUN useradd --create-home appuser && mkdir /app/data && chown appuser /app/data
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
