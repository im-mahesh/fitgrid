FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.13.7

WORKDIR /app

# Dependencies first so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

# Bake the embedding model into the image: no download at run time.
# ONNX Runtime sends usage telemetry to Microsoft unless it is switched off.
ENV FASTEMBED_CACHE_PATH=/opt/models \
    ORT_DISABLE_TELEMETRY=1
COPY app/__init__.py app/embeddings.py ./app/
# chmod: some cache files are written readable by root only, and the app is not root.
RUN python -c "from app import embeddings; embeddings.embed_query('warm up')" \
    && chmod -R a+rX /opt/models
ENV HF_HUB_OFFLINE=1

COPY app ./app

RUN useradd --system --no-create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
